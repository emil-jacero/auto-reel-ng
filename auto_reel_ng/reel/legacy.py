"""Import of the auto-reel legacy ``metadata.yaml``/``reel.yaml`` format into v0.

The legacy format never recorded structure (chapters and clip order were derived
from folder layout at scan time); it carried only editorial *metadata*: a
``metadata`` block, top-level ``title``/``description``, a ``sort`` rule, and a
``title_card`` styling block. This importer maps what it can into a v0 document
(``metadata`` -> ``metadata``, ``title_card`` -> opaque ``look``, ``sort`` -> the
event's v0 ``sort``) and **reports** anything it cannot faithfully represent rather
than dropping it silently. The resulting document has no chapters/clips: every clip
enters it later through NEW-clip adoption, which orders them by the carried ``sort``.

A legacy top-level ``title`` is auto-reel's full movie-name stem, which it composed
as ``"<YYYY-MM-DD> - <title>"``; a matching date prefix is split off so output
naming does not prefix the date twice.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Optional

from ruamel.yaml.comments import CommentedMap

from .document import ReelDocument, SortMethod
from .schema import build_document

logger = logging.getLogger(__name__)

# Top-level keys the legacy format defined and this importer understands.
_KNOWN_TOP_LEVEL = frozenset({"metadata", "title", "description", "sort", "title_card"})
# Keys inside the legacy ``metadata`` block this importer understands.
_KNOWN_METADATA = frozenset({"title", "date", "location"})
# auto-reel's composed movie-name stem: "<YYYY-MM-DD> - <title>".
_DATED_TITLE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) - (.+)$")


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

    sort = _import_sort(data.get("sort"), unmapped)
    if sort:
        out["sort"] = sort
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
    top_title = data.get("title")
    title = top_title if top_title is not None else legacy_metadata.get("title")
    event_date = legacy_metadata.get("date")
    if top_title is not None:
        title, event_date = _split_dated_title(top_title, event_date)
    if title is not None:
        metadata["title"] = title
    if event_date is not None:
        metadata["date"] = event_date
    if legacy_metadata.get("location") is not None:
        metadata["location"] = legacy_metadata["location"]
    if data.get("description") is not None:
        metadata["description"] = data["description"]

    for key in legacy_metadata:
        if key not in _KNOWN_METADATA:
            unmapped.append(f"metadata.{key}")
    return metadata


def _split_dated_title(title: Any, event_date: Any) -> tuple[Any, Any]:
    """Split auto-reel's ``"<YYYY-MM-DD> - <rest>"`` stem into ``(rest, date)``.

    Only when the prefix is a real date and ``event_date`` is absent or equal to
    it; otherwise both come back unchanged (the title is valid text as written).
    """
    if not isinstance(title, str):
        return title, event_date
    match = _DATED_TITLE_RE.match(title)
    if match is None:
        return title, event_date
    prefix = _real_date(match.group(1))
    if prefix is None:
        return title, event_date
    if event_date is not None and _as_date(event_date) != prefix:
        return title, event_date
    return match.group(2), event_date if event_date is not None else prefix


def _real_date(text: str) -> Optional[date]:
    """``text`` as a calendar date, or ``None`` when it is not one (``2019-04-31``)."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _as_date(value: Any) -> Optional[date]:
    """A legacy ``metadata.date`` (a ruamel date or an ISO string) as a date, if it is one."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return _real_date(value)
    return None


def _import_sort(sort: Any, unmapped: list[str]) -> CommentedMap:
    """Carry the legacy ``sort`` rule onto the v0 ``sort``; report what cannot map.

    ``method``, ``reverse`` and (for ``custom``) ``custom_order`` map one to one.
    An unknown method drops the whole rule (it cannot be applied), and a wrong-typed
    field drops only that field; each is reported. auto-reel ignored
    ``custom_order`` without ``method: custom``, so it is reported, not carried.
    """
    out: CommentedMap = CommentedMap()
    if sort is None:
        return out
    if not isinstance(sort, Mapping):
        unmapped.append("sort (not a mapping)")
        return out

    method_raw = sort.get("method", SortMethod.DATETIME.value)
    method = str(method_raw).lower()
    if method not in {m.value for m in SortMethod}:
        unmapped.append(f"sort.method={method_raw!r} (unknown sort method)")
        return out
    out["method"] = method

    reverse = sort.get("reverse")
    if isinstance(reverse, bool):
        out["reverse"] = reverse
    elif reverse is not None:
        unmapped.append(f"sort.reverse={reverse!r} (not a boolean)")

    custom_order = sort.get("custom_order")
    if custom_order is None:
        return out
    if method != SortMethod.CUSTOM.value:
        unmapped.append(f"sort.custom_order (ignored without method 'custom', got {method!r})")
    elif _is_position_map(custom_order):
        out["custom_order"] = CommentedMap(custom_order)
    else:
        unmapped.append("sort.custom_order (not a mapping of file name to integer position)")
    return out


def _is_position_map(value: Any) -> bool:
    """Whether ``value`` is a ``{file name: integer position}`` mapping."""
    return isinstance(value, Mapping) and all(
        isinstance(name, str)
        and name.strip()
        and isinstance(position, int)
        and not isinstance(position, bool)
        for name, position in value.items()
    )


def _report_unknown_keys(data: Mapping[str, Any], unmapped: list[str]) -> None:
    """Report any top-level legacy key the importer does not understand."""
    for key in data:
        if key not in _KNOWN_TOP_LEVEL:
            unmapped.append(f"unknown top-level key {key!r}")
