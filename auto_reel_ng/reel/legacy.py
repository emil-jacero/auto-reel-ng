"""Import of the auto-reel legacy ``metadata.yaml``/``reel.yaml`` format into v0.

The legacy format never recorded structure (chapters and clip order were derived
from folder layout at scan time); it carried only editorial *metadata*: a
``metadata`` block, top-level ``title``/``description``, a ``sort`` rule, and a
``title_card`` styling block. This importer maps what it can into a v0 document
(``metadata`` -> ``metadata``, ``title_card`` -> opaque ``look``) and **reports**
anything it cannot faithfully represent rather than dropping it silently. The
resulting document has no chapters/clips: structure is materialized later by
discovery seeding, which honors the legacy ordering intent then.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from ruamel.yaml.comments import CommentedMap

from .document import ReelDocument
from .schema import build_document

logger = logging.getLogger(__name__)

# Top-level keys the legacy format defined and this importer understands.
_KNOWN_TOP_LEVEL = frozenset({"metadata", "title", "description", "sort", "title_card"})
# Keys inside the legacy ``metadata`` block this importer understands.
_KNOWN_METADATA = frozenset({"title", "date", "location"})


@dataclass(frozen=True)
class ImportResult:
    """A best-effort import: the v0 document plus everything that could not map.

    ``unmapped`` is never silently empty when data was dropped — each entry names
    a legacy field the importer could not faithfully represent in v0.
    """

    document: ReelDocument
    unmapped: tuple[str, ...]


def import_legacy(data: Mapping[str, Any], *, source: str = "<legacy>") -> ImportResult:
    """Import an auto-reel legacy document into a v0 :class:`ReelDocument`.

    Returns the document and a list of unmappable fields (also logged at WARNING).
    """
    unmapped: list[str] = []

    legacy_metadata = data.get("metadata") or {}
    if legacy_metadata and not isinstance(legacy_metadata, Mapping):
        legacy_metadata = {}
        unmapped.append("metadata (not a mapping)")

    out: CommentedMap = CommentedMap()
    out["version"] = 0

    metadata = _import_metadata(data, legacy_metadata, unmapped)
    if metadata:
        out["metadata"] = metadata

    title_card = data.get("title_card")
    if title_card is not None:
        if isinstance(title_card, Mapping):
            # title_card maps straight to the opaque v0 look (no inner interpretation).
            out["look"] = CommentedMap(title_card)
        else:
            unmapped.append("title_card (not a mapping)")

    _report_sort(data.get("sort"), unmapped)
    _report_unknown_keys(data, unmapped)

    document = build_document(out, source=source)

    for field in unmapped:
        logger.warning("%s: legacy import could not map: %s", source, field)

    return ImportResult(document=document, unmapped=tuple(unmapped))


def import_legacy_data(data: Mapping[str, Any], *, source: str = "<legacy>") -> ReelDocument:
    """Import a legacy document, returning only the v0 document (warnings logged)."""
    return import_legacy(data, source=source).document


def _import_metadata(
    data: Mapping[str, Any],
    legacy_metadata: Mapping[str, Any],
    unmapped: list[str],
) -> CommentedMap:
    """Translate the legacy metadata/title/description into a v0 metadata map."""
    metadata: CommentedMap = CommentedMap()

    # Top-level ``title`` is the legacy movie-title override; it takes precedence
    # over the metadata block's title (the closest v0 field is metadata.title).
    title = data.get("title") if data.get("title") is not None else legacy_metadata.get("title")
    if title is not None:
        metadata["title"] = title
    if legacy_metadata.get("date") is not None:
        metadata["date"] = legacy_metadata["date"]
    if legacy_metadata.get("location") is not None:
        metadata["location"] = legacy_metadata["location"]
    if data.get("description") is not None:
        metadata["description"] = data["description"]

    for key in legacy_metadata:
        if key not in _KNOWN_METADATA:
            unmapped.append(f"metadata.{key}")
    return metadata


def _report_sort(sort: Any, unmapped: list[str]) -> None:
    """Report any ``sort`` rule that cannot be represented without a clip list.

    ``datetime``/``filename`` ordering is the natural seeding order and is honored
    implicitly when discovery materializes structure, so it needs no carry. A
    ``custom`` order (or ``reverse``) names specific clips this importer does not
    yet have, so it is reported rather than silently dropped.
    """
    if sort is None:
        return
    if not isinstance(sort, Mapping):
        unmapped.append("sort (not a mapping)")
        return
    method = str(sort.get("method", "datetime")).lower()
    if method not in {"datetime", "filename"}:
        unmapped.append(f"sort.method={method!r} (no clip list to materialize at import)")
    if sort.get("custom_order") is not None:
        unmapped.append("sort.custom_order (manual order needs the clip list; apply on seeding)")
    if sort.get("reverse"):
        unmapped.append("sort.reverse (cannot apply without a clip list at import)")


def _report_unknown_keys(data: Mapping[str, Any], unmapped: list[str]) -> None:
    """Report any top-level legacy key the importer does not understand."""
    for key in data:
        if key not in _KNOWN_TOP_LEVEL:
            unmapped.append(f"unknown top-level key {key!r}")
