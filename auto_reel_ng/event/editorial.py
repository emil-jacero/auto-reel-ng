"""Apply a desired editorial state onto an event's document and persist it (decision D-E1).

The operation loads the event's current document (or starts from an empty one, if
it has no ``reel.yaml`` yet) and merges the caller's desired editorial state onto
its existing round-trip structure **field by field** — it never constructs a
fresh mapping from the desired state alone, which would retain a plain mapping as
the document's source structure and silently strip every comment from a
hand-authored ``reel.yaml`` on first save. List entries get the same care: an
unchanged chapter clip list or ``ignore`` list is left untouched, and in a changed
one every entry keeps its own comments and quotes wherever it lands. A chapter renamed
in the same write is paired with its existing node by its clips, so it keeps its comments,
and the comment lines between chapters stay with the chapter below them through a reorder
or a removal. The merged result is
validated exactly as a loaded document is (fail-loud, schema + cross-references)
*before* anything is written, so a rejected write leaves the existing file
untouched.

The operation never renders, enqueues, or probes media, and never touches the
render manifest: an editorial write only moves the fingerprint's editorial
component, and the caller's next read reports the event stale on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as DateType
from datetime import datetime as DateTimeType
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import CommentMark
from ruamel.yaml.tokens import CommentToken

from ..reel.document import ReelDocument
from ..reel.parser import load_document
from ..reel.schema import build_document
from ..reel.writer import document_to_data, write_document
from .metadata import reel_exists, require_processable, with_resolved_metadata

#: The editorial document file name within an event directory (mirrors cli/adoption.py;
#: not imported from there to avoid a cli <-> event import cycle).
REEL_FILENAME = "reel.yaml"

_METADATA_KEYS = ("title", "date", "location", "description")


def apply_editorial_write(
    event_dir: Path, desired_data: Mapping[str, Any], *, today: Optional[DateType] = None
) -> ReelDocument:
    """Apply ``desired_data`` onto ``event_dir``'s document and persist it.

    ``desired_data`` is a v0-vocabulary mapping (optional ``metadata``/``look``/
    ``chapters``/``clips``/``ignore`` keys, in the same shape :func:`build_document`
    parses) describing the *complete* desired editorial state (decision D-E2: a
    coarse request). It is merged onto the event's existing structure — or an
    empty one, if the event has no ``reel.yaml`` yet — so only the sections/keys
    that actually change differ in the persisted file. The merged mapping is
    validated exactly as a loaded document is; a validation failure raises and
    nothing is written. Referencing a clip absent from disk is legal here (D-E4):
    this operation never scans disk and never probes media.

    The merged document must also keep the event processable: its metadata,
    resolved over the folder name as every consumer resolves it, needs a real date
    and a title, and the date must not be after ``today`` (default: the current
    day). Otherwise :class:`~auto_reel_ng.errors.EventMetadataError` is raised and
    nothing is written. The resolution is only checked, never persisted: the file
    holds the document as authored.

    An event folder the process may not search raises its :class:`PermissionError`
    (nothing is written) rather than reading as an event with no ``reel.yaml``.
    """
    event_dir = Path(event_dir)
    reel_path = event_dir / REEL_FILENAME
    current = load_document(reel_path) if reel_exists(reel_path) else ReelDocument()

    data = document_to_data(current)
    _apply_metadata(data, desired_data.get("metadata"))
    _apply_look(data, desired_data.get("look"))
    _apply_chapters(data, desired_data.get("chapters"))
    _apply_clips(data, desired_data.get("clips"))
    _apply_ignore(data, desired_data.get("ignore"))

    document = build_document(data, source=f"<editorial write: {event_dir}>")
    resolved = with_resolved_metadata(document, event_dir).metadata
    require_processable(event_dir, resolved, today=today or DateType.today())
    write_document(document, reel_path)
    return document


# --------------------------------------------------------------------------- #
# Section merges: each mutates ``data`` in place, touching only what changes.
# --------------------------------------------------------------------------- #


def _apply_metadata(data: CommentedMap, desired: Optional[Mapping[str, Any]]) -> None:
    """Merge the four metadata fields in place; drop the section if left empty."""
    desired = desired or {}
    if "metadata" not in data and not any(desired.get(k) is not None for k in _METADATA_KEYS):
        return
    section = data.get("metadata")
    if not isinstance(section, CommentedMap):
        section = CommentedMap()
        data["metadata"] = section
    for key in _METADATA_KEYS:
        value = desired.get(key)
        if value is None:
            section.pop(key, None)
        else:
            section[key] = _coerce_date(value) if key == "date" else value
    if not section:
        data.pop("metadata", None)


def _coerce_date(value: Any) -> Any:
    """Normalize a metadata date to a native ``date`` so it dumps unquoted.

    A JSON caller (the API) sends an ISO string; assigning it verbatim would make
    ruamel quote it on dump (to keep a plain scalar from being re-read as a
    timestamp), corrupting the byte-stable round-trip for an otherwise-unchanged
    date. Parse failures are left as-is so :func:`build_document`'s own
    validation raises the user-facing error, rather than failing here.
    """
    if value is None or isinstance(value, DateType):
        return value
    if isinstance(value, DateTimeType):
        return value.date()
    if isinstance(value, str):
        try:
            return DateTimeType.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return value
    return value


def _apply_look(data: CommentedMap, desired: Optional[Mapping[str, Any]]) -> None:
    """Merge ``look`` (opaque, D-I) key by key; drop the section if left empty."""
    desired = desired or {}
    if "look" not in data and not desired:
        return
    section = data.get("look")
    if not isinstance(section, CommentedMap):
        section = CommentedMap()
        data["look"] = section
    for key in list(section.keys()):
        if key not in desired:
            del section[key]
    for key, value in desired.items():
        section[key] = value
    if not section:
        data.pop("look", None)


def _apply_ignore(data: CommentedMap, desired: Optional[Iterable[str]]) -> None:
    """Rewrite ``ignore`` in place, keeping each entry's comments; drop the key if emptied.

    An ``ignore`` that is already empty (``[]``, a bare key, or absent) stays as written.
    An emptied one followed by comment lines stays as ``ignore: []``, so they still
    introduce what follows it.
    """
    desired_list = list(desired or [])
    section = data.get("ignore")
    if not desired_list and not section:
        return
    if not isinstance(section, CommentedSeq):
        data["ignore"] = CommentedSeq(desired_list)
        return
    comments, ends = _entry_comments(data, "ignore")
    if not desired_list and not ends.trailing:
        data.pop("ignore", None)
        return
    _rewrite_identity_list(data, "ignore", desired_list, comments, ends)


def _apply_chapters(data: CommentedMap, desired: Optional[Iterable[Mapping[str, Any]]]) -> None:
    """Rebuild the ``chapters`` sequence, reusing existing chapter nodes.

    A desired chapter takes an existing node by name; failing that, by its clips (see
    :func:`_pair_by_clips`), which makes it that node *renamed*. A reused node keeps
    whatever comments it carries; only its ``clips`` list is rewritten, each clip keeping
    its own comments — even one moved in from another existing chapter. A chapter with no
    node to take is a fresh one. A chapter absent from ``desired`` is dropped with its own
    comments — "coarse" describes the request, not the write, but the request is still the
    complete desired structure (D-E2).

    When the sequence has to be replaced, the comment lines between chapters travel with
    the chapter below them (:func:`_rehome_chapter_comments`).
    """
    desired_chapters = list(desired or [])
    current = data.get("chapters")
    if not desired_chapters:
        if current:  # already empty (``[]``, a bare key, or absent): stays as written
            data.pop("chapters", None)
        return

    comments: dict[str, _EntryComments] = {}
    ends: dict[int, _ListComments] = {}  # by node: a renamed chapter has no name to find it by
    existing = [
        entry
        for entry in (current if isinstance(current, (list, tuple)) else ())
        if isinstance(entry, CommentedMap)
    ]
    for entry in existing:
        # Collected before any list is rewritten. An identity appears in at most one
        # chapter, so a clip moved between chapters still finds its own.
        chapter_comments, ends[id(entry)] = _entry_comments(entry, "clips")
        comments.update(chapter_comments)
    nodes = _match_chapters(existing, desired_chapters)

    rebuilt = CommentedSeq()
    for desired_chapter, node in zip(desired_chapters, nodes):
        name = desired_chapter["name"]
        clips = list(desired_chapter.get("clips") or [])
        if node is None:
            node = CommentedMap()
            node["name"] = name
            node["clips"] = CommentedSeq(clips)
        else:
            if node.get("name") != name:  # a renamed chapter keeps its name line's comment
                node["name"] = name
            if isinstance(node.get("clips"), CommentedSeq):
                _rewrite_identity_list(node, "clips", clips, comments, ends[id(node)])
            elif clips:  # a missing or bare ``clips`` stays as written while it lists nothing
                node["clips"] = CommentedSeq(clips)
        rebuilt.append(node)

    # Existing chapters that all keep their place, with any new ones appended after them,
    # keep their sequence node: it can hold comment lines between two chapters (after a
    # flow list such as ``clips: []``) by index, and the lines after the last chapter.
    in_place = (
        isinstance(current, CommentedSeq)
        and len(current) <= len(rebuilt)
        and all(old is new for old, new in zip(current, rebuilt))
    )
    if not in_place:
        if isinstance(current, CommentedSeq):
            _rehome_chapter_comments(data, current, rebuilt, ends)
        else:
            data["chapters"] = rebuilt
        return
    appended = rebuilt[len(current) :]
    if current and appended:
        # The lines after the last chapter's clips introduce what follows the chapters,
        # so they move to the end of the new last chapter's clips.
        moved = _entry_comments(current[-1], "clips")[1].trailing
        if moved:
            _set_trailing(current[-1], "clips", "")
            _set_trailing(appended[-1], "clips", moved)
    current.extend(appended)


def _match_chapters(
    existing: list[CommentedMap], desired: list[Mapping[str, Any]]
) -> list[Optional[CommentedMap]]:
    """For each desired chapter, the existing node it reuses (``None``: a fresh chapter).

    By name first; a chapter that matches no name is then paired by its clips
    (:func:`_pair_by_clips`) with an existing node no chapter took by name.
    """
    by_name = {entry.get("name"): entry for entry in existing}
    nodes: list[Optional[CommentedMap]] = [by_name.get(chapter["name"]) for chapter in desired]
    claimed = {id(node) for node in nodes if node is not None}
    wanted = [
        (index, list(chapter.get("clips") or []))
        for index, chapter in enumerate(desired)
        if nodes[index] is None
    ]
    paired = _pair_by_clips(wanted, [e for e in existing if id(e) not in claimed])
    return [node or paired.get(index) for index, node in enumerate(nodes)]


def _pair_by_clips(
    wanted: list[tuple[int, list[str]]], unclaimed: list[CommentedMap]
) -> dict[int, CommentedMap]:
    """Pair each wanted chapter (``(desired index, clips)``) with an unclaimed existing node.

    A renamed chapter arrives as a name that matches nothing, with clips that were
    somewhere. It takes the node whose clip list equals its own (same order), else the one
    it shares the most clips with (at least one), so it keeps that node's comments. The
    pairing is greedy and total-ordered — exact matches, larger overlaps, then desired
    order, then existing order — and takes each node at most once. A chapter with no clips
    pairs with nothing.
    """
    candidates = []
    for existing_index, node in enumerate(unclaimed):
        clips = node.get("clips")
        held = [str(clip) for clip in clips] if isinstance(clips, CommentedSeq) else []
        for index, desired_clips in wanted:
            overlap = len(set(held) & set(desired_clips))
            if overlap:
                exact = held == desired_clips
                candidates.append((not exact, -overlap, index, existing_index))
    taken: set[int] = set()
    paired: dict[int, CommentedMap] = {}
    for _, _, index, existing_index in sorted(candidates):
        if index not in paired and existing_index not in taken:
            paired[index] = unclaimed[existing_index]
            taken.add(existing_index)
    return paired


def _rehome_chapter_comments(
    data: CommentedMap,
    current: CommentedSeq,
    rebuilt: CommentedSeq,
    ends: Mapping[int, _ListComments],
) -> None:
    """Replace ``data["chapters"]`` with ``rebuilt``; each chapter keeps the lines above it.

    ruamel files the lines between two chapters by where the previous chapter's list ends:
    on its last clip, on its flow list's key, or on the ``chapters`` sequence by index. A
    reader takes them as introducing the chapter below, so they are collected per old node
    before anything moves, written back above that node at its new index, and dropped with
    it if it is. The lines under ``chapters:`` are the first chapter's, and the lines after
    the last chapter stay after whichever chapter ends up last.
    """
    above: dict[int, str] = {}
    previous = ""  # the previous chapter's trailing lines
    for index, node in enumerate(current):
        if index == 0:
            text = _header_text(data, "chapters", current) or _key_token_tail(data, "chapters")
        else:
            slot = current.ca.items.get(index)
            text = previous + _render_tokens(slot[1] if slot else None)
        above[id(node)] = text
        previous = ends[id(node)].trailing if id(node) in ends else ""
    after_last = previous
    end_comment = current.ca.end

    for node in rebuilt:
        if id(node) in ends and isinstance(node.get("clips"), CommentedSeq):
            _set_trailing(node, "clips", "")  # now carried above the chapter below it

    data["chapters"] = rebuilt
    if end_comment:
        # ruamel's representer appends the end comment to the sequence's own comment list, and
        # drops it silently when there is none.
        rebuilt.ca.comment = rebuilt.ca.comment or [None, None]
        rebuilt.ca.end = end_comment
    first = above.get(id(rebuilt[0]), "")
    _set_key_tail(data, "chapters", rebuilt, "")  # a block list's key tail was its old header
    _set_header(data, "chapters", rebuilt, first)
    for index in range(1, len(rebuilt)):
        text = above.get(id(rebuilt[index]), "")
        if text:
            rebuilt.ca.items[index] = [None, [CommentToken(text, CommentMark(0))], None, None]
    if after_last:
        last = rebuilt[-1]
        if not isinstance(last.get("clips"), CommentedSeq):
            last["clips"] = CommentedSeq()
        _set_trailing(last, "clips", after_last)


def _apply_clips(data: CommentedMap, desired: Optional[Mapping[str, Mapping[str, Any]]]) -> None:
    """Rebuild the ``clips`` property map, reusing existing per-identity nodes."""
    desired_clips = dict(desired or {})
    if not desired_clips:
        data.pop("clips", None)
        return

    current = data.get("clips")
    existing: Mapping[str, Any] = current if isinstance(current, Mapping) else {}

    rebuilt = CommentedMap()
    for identity, props in desired_clips.items():
        entry = existing.get(identity)
        if not isinstance(entry, CommentedMap):
            entry = CommentedMap()
        _apply_clip_properties(entry, props or {})
        rebuilt[identity] = entry
    data["clips"] = rebuilt


def _apply_clip_properties(entry: CommentedMap, desired: Mapping[str, Any]) -> None:
    """Merge one clip's properties (trims/title/rotate/exclude) in place."""
    _apply_trims(entry, desired.get("trims"))

    for key in ("title", "rotate"):
        value = desired.get(key)
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = value

    if desired.get("exclude", False):
        entry["exclude"] = True
    else:
        entry.pop("exclude", None)


def _apply_trims(entry: CommentedMap, desired: Optional[Iterable[Mapping[str, Any]]]) -> None:
    """Replace ``trims`` only if its content actually changed.

    Rebuilding unconditionally would replace an unchanged, hand-authored flow-style
    span (``{in: 0, out: 3.2, reason: black}``) with a fresh block-style mapping —
    same content, different formatting, which is exactly the spurious diff the
    round-trip guarantee forbids. Leaving the existing node alone when nothing
    changed keeps its original style.
    """
    desired_list = [dict(t) for t in (desired or [])]
    if not desired_list:
        entry.pop("trims", None)
        return
    current = entry.get("trims")
    if isinstance(current, (list, tuple)) and _trims_equal(current, desired_list):
        return
    entry["trims"] = CommentedSeq(_trim_entry(t) for t in desired_list)


def _trims_equal(current: Iterable[Any], desired: list) -> bool:
    """Compare trims by content (``in``/``out``/``reason``), ignoring node style."""
    current_norm = [
        {"in": c.get("in"), "out": c.get("out"), "reason": c.get("reason")}
        for c in current
        if isinstance(c, Mapping)
    ]
    desired_norm = [
        {"in": d.get("in"), "out": d.get("out"), "reason": d.get("reason")} for d in desired
    ]
    return current_norm == desired_norm


def _trim_entry(trim: Mapping[str, Any]) -> CommentedMap:
    """Build one cut-span mapping using the YAML vocabulary (``in``/``out``)."""
    entry = CommentedMap()
    entry["in"] = trim["in"]
    entry["out"] = trim["out"]
    if trim.get("reason") is not None:
        entry["reason"] = trim["reason"]
    return entry


# --------------------------------------------------------------------------- #
# Identity lists (chapter clips, ignore): each entry keeps its own comments.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _EntryComments:
    """One list entry's own comments, lifted out of ruamel's comment table."""

    above: str = ""  # own-line comments / blank lines above the entry, verbatim (indented)
    eol: str = ""  # end-of-line comment text, e.g. "# MISSING" ("" when none)
    column: int = 0  # the column the eol comment's '#' was written at
    stored: Any = None  # the scalar as loaded, quotes included (``None`` for an added entry)


@dataclass(frozen=True)
class _ListComments:
    """A list's own comment lines, which stay with the list rather than with an entry."""

    header: str = ""  # lines above a flow list's "[" (a block list's go with its first entry)
    trailing: str = ""  # lines after the last entry, introducing whatever follows the list


def _entry_comments(
    parent: CommentedMap, key: str
) -> tuple[dict[str, _EntryComments], _ListComments]:
    """Split ``parent[key]``'s comments by entry; also return the list's own lines.

    ruamel files the lines *between* two entries in the comment token of the entry
    above them, after that entry's end-of-line comment, while a reader takes them as
    introducing the entry below. So each token is split at its first newline: the
    end-of-line part is its entry's, and the rest is the next entry's ``above``
    text — or, after the last entry, the list's trailing text, which introduces
    whatever follows the list. The lines above a block list's first entry are that
    entry's. A flow or empty list (``[a.mp4, b.mp4]``, ``[]``) keeps the lines above
    it as its own header, and the lines after it trail the key's end-of-line comment
    token, which follows its ``]``.
    """
    seq = parent.get(key)
    if not isinstance(seq, CommentedSeq):
        return {}, _ListComments()
    flow = not seq or bool(seq.fa.flow_style())
    header = _header_text(parent, key, seq)
    above = "" if flow else header or _key_token_tail(parent, key)
    comments: dict[str, _EntryComments] = {}
    for index, identity in enumerate(seq):
        slot = seq.ca.items.get(index)
        value, column = (slot[0].value, slot[0].column) if slot and slot[0] else ("", 0)
        eol, _, below = value.partition("\n")
        comments[identity] = _EntryComments(above, eol, column if eol else 0, identity)
        above = below
    if flow:
        return comments, _ListComments(header, _key_token_tail(parent, key))
    return comments, _ListComments(trailing=above)


def _header_text(parent: CommentedMap, key: str, seq: CommentedSeq) -> str:
    """The comment lines between ``key:`` and the list, as verbatim (indented) text.

    The loader files them twice, on the parent's key (comment slot 3, which the
    dumper prefers) and on the list, as one token per comment line: the line
    unindented plus the blank lines after it, and the column its ``#`` was written
    at. When the key line has a comment of its own (``clips:   # root list``), a
    block list's are the tail of that comment's token instead.
    """
    slot = parent.ca.items.get(key)
    return _render_tokens(
        (slot[3] if slot else None) or (seq.ca.comment[1] if seq.ca.comment else None)
    )


def _render_tokens(tokens: Optional[Iterable[CommentToken]]) -> str:
    """Comment-line tokens as verbatim text: each line indented to the column it was written at."""
    return "".join(
        t.value if t.value.startswith("\n") else " " * t.column + t.value for t in tokens or ()
    )


def _key_token_tail(parent: CommentedMap, key: str) -> str:
    """The text after the first line of the key's end-of-line comment token ("" without one)."""
    slot = parent.ca.items.get(key)
    token = slot[2] if slot else None
    return "" if token is None else str(token.value.partition("\n")[2])


def _rewrite_identity_list(
    parent: CommentedMap,
    key: str,
    desired: list[str],
    comments: Mapping[str, _EntryComments],
    own: _ListComments,
) -> None:
    """Make ``parent[key]`` (a ``CommentedSeq``) hold ``desired``, keeping each entry's comments.

    An unchanged list is left untouched, so its bytes are too. A changed list is
    refilled in place, which keeps its node and the key's own comment, and its
    comment tokens are rebuilt from ``comments``: every entry keeps its end-of-line
    comment, at its column, and the lines above it, wherever it lands, and it is written
    as stored (quotes included). An entry missing from ``comments`` (an added one) gets
    none and is plain, and a removed entry's comments are not written. The list's own
    lines (``own``) stay at its top and end.

    A list with no entry comment to carry is written flow style when it is emptied
    or already was flow: ruamel would emit entry comments inside a flow list's
    brackets, and a key comment before an empty block list's ``[]``. Any other list
    is block style, with a flow list's header above its first entry.
    """
    seq = parent[key]
    if list(seq) == desired:
        return
    del seq[:]
    seq.ca.items.clear()
    entries = [comments.get(identity, _EntryComments()) for identity in desired]
    # A retained entry is written as it was stored, so ``"a.mp4"`` keeps its quotes.
    seq.extend(
        entry.stored if entry.stored is not None else identity
        for identity, entry in zip(desired, entries)
    )
    carries = any(entry.above or entry.eol for entry in entries)
    if not carries and (not entries or seq.fa.flow_style()):
        seq.fa.set_flow_style()
        _set_header(parent, key, seq, own.header)
    else:
        seq.fa.set_block_style()
        _set_key_tail(parent, key, seq, "")  # a block list's key tail was its old header
        _set_header(parent, key, seq, own.header + entries[0].above)
        for index, entry in enumerate(entries):
            below = entries[index + 1].above if index + 1 < len(entries) else ""
            if entry.eol or below:
                token = CommentToken(f"{entry.eol}\n{below}", CommentMark(entry.column))
                seq.ca.items[index] = [token, None, None, None]
    _set_trailing(parent, key, own.trailing)


def _set_trailing(parent: CommentedMap, key: str, text: str) -> None:
    """Make ``text`` the lines after the list ``parent[key]``, where its style keeps them.

    After a block list, they are the tail of its last entry's comment token. After a
    flow or empty list, which is then flow style, they are the tail of the key's
    end-of-line comment token, which follows the ``]``.
    """
    seq = parent[key]
    if not seq or seq.fa.flow_style():
        seq.fa.set_flow_style()
        _set_key_tail(parent, key, seq, text)
        return
    last = len(seq) - 1
    slot = seq.ca.items.get(last)
    eol, column = "", 0
    if slot and slot[0] is not None:
        eol, column = slot[0].value.partition("\n")[0], slot[0].column
    if eol or text:
        seq.ca.items[last] = [CommentToken(f"{eol}\n{text}", CommentMark(column)), None, None, None]
    else:
        seq.ca.items.pop(last, None)


def _set_header(parent: CommentedMap, key: str, seq: CommentedSeq, text: str) -> None:
    """Make ``text`` (verbatim, indented) the lines between ``key:`` and the list."""
    _set_list_slot(parent, key, seq, 1, [CommentToken(text, CommentMark(0))] if text else None)


def _set_key_tail(parent: CommentedMap, key: str, seq: CommentedSeq, tail: str) -> None:
    """Make ``tail`` follow the key's own end-of-line comment, which keeps its column."""
    slot = parent.ca.items.get(key)
    eol, column = "", 0
    if slot and slot[2] is not None:
        eol, column = slot[2].value.partition("\n")[0], slot[2].column
    token = CommentToken(f"{eol}\n{tail}", CommentMark(column)) if eol or tail else None
    _set_list_slot(parent, key, seq, 0, token)


def _set_list_slot(
    parent: CommentedMap, key: str, seq: CommentedSeq, index: int, value: Any
) -> None:
    """Set a list's comment slot ``index`` (0: the key's token, 1: the lines above it).

    It is written in both places the loader files it, on the parent's key (slot
    ``2 + index``, which the dumper prefers) and on the list, so the copies agree.
    """
    if value is not None or key in parent.ca.items:
        parent.ca.items.setdefault(key, [None, None, None, None])[2 + index] = value
    if value is not None or seq.ca.comment is not None:
        if seq.ca.comment is None:
            seq.ca.comment = [None, None]
        seq.ca.comment[index] = value


__all__ = ["REEL_FILENAME", "apply_editorial_write"]
