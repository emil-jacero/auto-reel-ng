"""Round-trip-preserving writer for ``reel.yaml`` documents (decision **D-G**).

A document loaded from disk carries its ruamel round-trip structure (``_data``);
writing it back re-emits that structure so comments and key order survive a
machine write byte-stable. A document built in memory (seeded, imported, or
mutated by a reconcile apply-operation) is serialized from its typed fields in a
canonical key order. Either way the output always declares ``version: 0``.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import re
import stat
import time
import uuid
from pathlib import Path
from typing import Any, Union

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .document import SCHEMA_VERSION, ClipOrder, ReelDocument

_LOG = logging.getLogger(__name__)

#: How old an abandoned ``.reel.yaml.<hex>.tmp`` must be before a later write removes it. Far
#: longer than any write takes, so a concurrent writer's live temporary is never in range.
TEMPORARY_MAX_AGE_SECONDS = 24 * 60 * 60


def round_trip_yaml() -> YAML:
    """A ruamel round-trip YAML in the engine's canonical block style.

    The single definition of that style: the writer and any tooling that must rewrite a
    ``reel.yaml`` outside :func:`write_document` (``scripts/make_dev_library.py``) use it.

    The indentation (2-space mappings, 4-space sequences, offset 2) is the style
    a hand-authored ``reel.yaml`` is expected to use; documents in this style
    rewrite byte-stable (the round-trip guarantee, D-G). ruamel cannot reproduce
    arbitrary foreign indentation, so the schema is constrained to this style.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def document_to_data(doc: ReelDocument) -> CommentedMap:
    """Return a round-trip mapping for ``doc``, suitable for writing or mutation.

    If the document still carries its source structure, that structure is reused
    (a deep copy, so callers may mutate freely) with ``version`` forced to ``0``.
    Otherwise a fresh :class:`CommentedMap` is built from the typed fields in
    canonical order. Empty sections are omitted; ``version`` is always present.
    """
    if doc.raw is not None:
        data = round_trip_yaml().load(_dump_to_str(doc.raw))  # cheap structural deep copy
        data["version"] = SCHEMA_VERSION
        return data  # type: ignore[no-any-return]
    return _build_fresh(doc)


def dumps_document(doc: ReelDocument) -> str:
    """Serialize ``doc`` to a YAML string (always ``version: 0``)."""
    return _dump_to_str(document_to_data(doc))


def write_document(doc: ReelDocument, path: Union[str, Path]) -> None:
    """Write ``doc`` to ``path`` as ``reel.yaml`` (always ``version: 0``), atomically.

    The content goes in full to a uniquely named hidden sibling
    (``.reel.yaml.<hex>.tmp``), is ``fsync``ed, and only then renamed over
    ``path``: a failed or interrupted write leaves the previous document intact,
    never a truncated one. The name is unique (``O_EXCL``) because the API can run
    two saves at once in one process. On any failure the temporary file is removed
    when the filesystem still allows it, and the error propagates. A leftover is
    never read as the document: loaders read only ``reel.yaml``. A leftover from a write
    that was killed outright is removed by a later successful write once it is a day old
    (:func:`sweep_abandoned_temporaries`).
    """
    path = Path(path)
    text = dumps_document(doc)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)  # the umask applies
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    sweep_abandoned_temporaries(path)


def sweep_abandoned_temporaries(path: Union[str, Path]) -> None:
    """Remove the hidden temporaries an earlier write of ``path`` left behind.

    Only regular files (not symlinks) named exactly ``.<name>.<32 lowercase hex>.tmp`` in
    ``path``'s folder, last modified more than :data:`TEMPORARY_MAX_AGE_SECONDS` ago: a
    younger one may be a concurrent write in progress, and any other name is not ours.
    Housekeeping only, so an ``OSError`` listing, inspecting or removing is logged at
    debug level and never fails the write that already succeeded.
    """
    path = Path(path)
    pattern = re.compile(rf"\.{re.escape(path.name)}\.[0-9a-f]{{32}}\.tmp")
    cutoff = time.time() - TEMPORARY_MAX_AGE_SECONDS
    try:
        names = [name for name in os.listdir(path.parent) if pattern.fullmatch(name)]
    except OSError as exc:
        _LOG.debug("not sweeping %s: %s", path.parent, exc)
        return
    for name in names:
        candidate = path.parent / name
        try:
            info = candidate.lstat()
            if stat.S_ISREG(info.st_mode) and info.st_mtime < cutoff:
                candidate.unlink()
        except OSError as exc:
            _LOG.debug("not removing %s: %s", candidate, exc)


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _dump_to_str(data: Any) -> str:
    """Dump a ruamel structure (or plain data) to a string."""
    stream = io.StringIO()
    round_trip_yaml().dump(data, stream)
    return stream.getvalue()


def _build_fresh(doc: ReelDocument) -> CommentedMap:
    """Build a canonical :class:`CommentedMap` from a document's typed fields."""
    data: CommentedMap = CommentedMap()
    data["version"] = SCHEMA_VERSION

    meta = _metadata_map(doc)
    if meta:
        data["metadata"] = meta
    if doc.look:
        data["look"] = CommentedMap(doc.look)
    if doc.chapters:
        data["chapters"] = _chapters_seq(doc)
    clips = _clips_map(doc)
    if clips:
        data["clips"] = clips
    if doc.ignore:
        data["ignore"] = CommentedSeq(doc.ignore)
    if doc.sort is not None:
        data["sort"] = _sort_map(doc.sort)
    return data


def _metadata_map(doc: ReelDocument) -> CommentedMap:
    """Build a metadata mapping, omitting unset fields."""
    meta = CommentedMap()
    if doc.metadata.title is not None:
        meta["title"] = doc.metadata.title
    if doc.metadata.date is not None:
        meta["date"] = doc.metadata.date
    if doc.metadata.location is not None:
        meta["location"] = doc.metadata.location
    if doc.metadata.description is not None:
        meta["description"] = doc.metadata.description
    return meta


def _chapters_seq(doc: ReelDocument) -> CommentedSeq:
    """Build the chapters sequence (name + ordered identity references)."""
    seq = CommentedSeq()
    for chapter in doc.chapters:
        entry = CommentedMap()
        entry["name"] = chapter.name
        entry["clips"] = CommentedSeq(ref.identity for ref in chapter.clips)
        seq.append(entry)
    return seq


def _clips_map(doc: ReelDocument) -> CommentedMap:
    """Build the clips property map, omitting default-valued properties."""
    clips = CommentedMap()
    for identity, props in doc.clips.items():
        entry = CommentedMap()
        if props.trims:
            entry["trims"] = CommentedSeq(_trim_map(t) for t in props.trims)
        if props.title is not None:
            entry["title"] = props.title
        if props.rotate is not None:
            entry["rotate"] = props.rotate
        if props.exclude:
            entry["exclude"] = props.exclude
        # An identity with only default properties still serializes as an empty
        # mapping so the round-trip preserves that the entry existed.
        clips[identity] = entry
    return clips


def _sort_map(sort: ClipOrder) -> CommentedMap:
    """Build the event ``sort`` mapping; ``custom_order`` only when it has entries."""
    entry = CommentedMap()
    entry["method"] = sort.method.value
    entry["reverse"] = sort.reverse
    if sort.custom_order:
        entry["custom_order"] = CommentedMap(sort.custom_order)
    return entry


def _trim_map(trim: Any) -> CommentedMap:
    """Build a single cut-span mapping using the YAML vocabulary (in/out)."""
    entry = CommentedMap()
    entry["in"] = trim.start
    entry["out"] = trim.end
    if trim.reason is not None:
        entry["reason"] = trim.reason
    return entry
