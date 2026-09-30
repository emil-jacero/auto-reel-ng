"""Apply a desired editorial state onto an event's document and persist it (decision D-E1).

The operation loads the event's current document (or starts from an empty one, if
it has no ``reel.yaml`` yet) and merges the caller's desired editorial state onto
its existing round-trip structure **field by field** — it never constructs a
fresh mapping from the desired state alone, which would retain a plain mapping as
the document's source structure and silently strip every comment from a
hand-authored ``reel.yaml`` on first save. The merged result is validated exactly
as a loaded document is (fail-loud, schema + cross-references) *before* anything
is written, so a rejected write leaves the existing file untouched.

The operation never renders, enqueues, or probes media, and never touches the
render manifest: an editorial write only moves the fingerprint's editorial
component, and the caller's next read reports the event stale on its own.
"""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime as DateTimeType
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ..reel.document import ReelDocument
from ..reel.parser import load_document
from ..reel.schema import build_document
from ..reel.writer import document_to_data, write_document
from .metadata import require_processable, with_resolved_metadata

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
    """
    event_dir = Path(event_dir)
    reel_path = event_dir / REEL_FILENAME
    current = load_document(reel_path) if reel_path.exists() else ReelDocument()

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
    """Replace the ``ignore`` list's contents in place; drop the key if emptied."""
    desired_list = list(desired or [])
    if not desired_list:
        data.pop("ignore", None)
        return
    section = data.get("ignore")
    if not isinstance(section, CommentedSeq):
        section = CommentedSeq()
        data["ignore"] = section
    else:
        del section[:]
    section.extend(desired_list)


def _apply_chapters(data: CommentedMap, desired: Optional[Iterable[Mapping[str, Any]]]) -> None:
    """Rebuild the ``chapters`` sequence, reusing existing chapter nodes by name.

    A chapter whose name matches an existing entry keeps that entry's own node
    (and whatever comments it carries); only its ``clips`` list is replaced. A
    chapter with no match in the current structure is a fresh node. A chapter
    absent from ``desired`` is dropped — "coarse" describes the request, not the
    write, but the request is still the complete desired structure (D-E2).
    """
    desired_chapters = list(desired or [])
    if not desired_chapters:
        data.pop("chapters", None)
        return

    current = data.get("chapters")
    existing_by_name: dict[Any, CommentedMap] = {}
    if isinstance(current, (list, tuple)):
        for entry in current:
            if isinstance(entry, Mapping):
                existing_by_name[entry.get("name")] = entry  # type: ignore[assignment]

    rebuilt = CommentedSeq()
    for desired_chapter in desired_chapters:
        name = desired_chapter["name"]
        clips = list(desired_chapter.get("clips") or [])
        entry = existing_by_name.get(name)
        if entry is None:
            entry = CommentedMap()
            entry["name"] = name
            entry["clips"] = CommentedSeq(clips)
        else:
            existing_clips = entry.get("clips")
            if isinstance(existing_clips, CommentedSeq):
                del existing_clips[:]
                existing_clips.extend(clips)
            else:
                entry["clips"] = CommentedSeq(clips)
        rebuilt.append(entry)
    data["chapters"] = rebuilt


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


__all__ = ["REEL_FILENAME", "apply_editorial_write"]
