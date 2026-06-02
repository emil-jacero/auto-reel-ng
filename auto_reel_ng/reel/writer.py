"""Round-trip-preserving writer for ``reel.yaml`` documents (decision **D-G**).

A document loaded from disk carries its ruamel round-trip structure (``_data``);
writing it back re-emits that structure so comments and key order survive a
machine write byte-stable. A document built in memory (seeded, imported, or
mutated by a reconcile apply-operation) is serialized from its typed fields in a
canonical key order. Either way the output always declares ``version: 0``.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Union

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .document import SCHEMA_VERSION, ReelDocument


def _yaml() -> YAML:
    """A ruamel round-trip YAML in the engine's canonical block style.

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
        data = _yaml().load(_dump_to_str(doc.raw))  # cheap structural deep copy
        data["version"] = SCHEMA_VERSION
        return data  # type: ignore[no-any-return]
    return _build_fresh(doc)


def dumps_document(doc: ReelDocument) -> str:
    """Serialize ``doc`` to a YAML string (always ``version: 0``)."""
    return _dump_to_str(document_to_data(doc))


def write_document(doc: ReelDocument, path: Union[str, Path]) -> None:
    """Write ``doc`` to ``path`` as ``reel.yaml`` (always ``version: 0``)."""
    Path(path).write_text(dumps_document(doc), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _dump_to_str(data: Any) -> str:
    """Dump a ruamel structure (or plain data) to a string."""
    stream = io.StringIO()
    _yaml().dump(data, stream)
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


def _trim_map(trim: Any) -> CommentedMap:
    """Build a single cut-span mapping using the YAML vocabulary (in/out)."""
    entry = CommentedMap()
    entry["in"] = trim.start
    entry["out"] = trim.end
    if trim.reason is not None:
        entry["reason"] = trim.reason
    return entry
