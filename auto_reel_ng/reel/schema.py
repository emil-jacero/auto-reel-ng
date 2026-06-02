"""v0 schema validation: build a typed :class:`ReelDocument` from parsed data.

This module turns an already-parsed mapping (from YAML, a legacy import, or a
reconcile mutation) into a validated, typed document. It is **fail-loud**: a
malformed or invalid structure raises :class:`ReelParseError` naming the
offending location, never fabricating a value and never silently dropping
editorial data. It deliberately imports nothing from :mod:`parser` or
:mod:`legacy`, so both can depend on it without an import cycle.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Any, Mapping, Optional

from ..errors import ReelParseError
from .document import (
    SCHEMA_VERSION,
    Chapter,
    ClipProperties,
    ClipRef,
    Metadata,
    ReelDocument,
    Trim,
)


def build_document(data: Mapping[str, Any], *, source: str = "<document>") -> ReelDocument:
    """Validate an already-parsed v0 mapping into a :class:`ReelDocument`.

    ``data`` is retained on the returned document as ``_data`` so the writer can
    re-emit it byte-stable. Callers that construct ``data`` as a ruamel
    ``CommentedMap`` get comment/key-order preservation for free.
    """
    _validate_version(data.get("version"), source=source)

    metadata = _parse_metadata(data.get("metadata"), source=source)
    look = _parse_look(data.get("look"), source=source)
    chapters = _parse_chapters(data.get("chapters"), source=source)
    clips = _parse_clips(data.get("clips"), source=source)
    ignore = _parse_ignore(data.get("ignore"), source=source)

    _validate_cross_references(chapters, clips, ignore, source=source)

    return ReelDocument(
        version=SCHEMA_VERSION,
        metadata=metadata,
        look=look,
        chapters=chapters,
        clips=clips,
        ignore=ignore,
        _data=data,
    )


# --------------------------------------------------------------------------- #
# Section parsers
# --------------------------------------------------------------------------- #


def _validate_version(version: Any, *, source: str) -> None:
    """Reject any version this engine does not define (only ``0``)."""
    if version != SCHEMA_VERSION:
        raise ReelParseError(
            f"{source}: unsupported version {version!r}; this engine supports "
            f"version {SCHEMA_VERSION}"
        )


def _parse_metadata(raw: Any, *, source: str) -> Metadata:
    """Parse the optional ``metadata`` mapping (title/date/location/description)."""
    if raw is None:
        return Metadata()
    if not isinstance(raw, Mapping):
        raise ReelParseError(f"{source}: 'metadata' must be a mapping, got {type(raw).__name__}")
    return Metadata(
        title=_opt_str(raw.get("title"), loc=f"{source}: metadata.title"),
        date=_parse_date(raw.get("date"), loc=f"{source}: metadata.date"),
        location=_opt_str(raw.get("location"), loc=f"{source}: metadata.location"),
        description=_opt_str(raw.get("description"), loc=f"{source}: metadata.description"),
    )


def _parse_look(raw: Any, *, source: str) -> Mapping[str, Any]:
    """Carry ``look`` opaquely (D-I): keep it as a map, never inspect inner keys."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ReelParseError(f"{source}: 'look' must be a mapping, got {type(raw).__name__}")
    # Shallow copy to a plain dict for the typed view; the round-trip structure
    # lives on the document's _data. Inner values are kept as-is (opaque).
    return dict(raw)


def _parse_chapters(raw: Any, *, source: str) -> tuple[Chapter, ...]:
    """Parse ``chapters`` as an ordered list of {name, clips: [identity, ...]}."""
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ReelParseError(f"{source}: 'chapters' must be a list, got {type(raw).__name__}")

    chapters: list[Chapter] = []
    seen_names: set[str] = set()
    for index, entry in enumerate(raw):
        loc = f"{source}: chapters[{index}]"
        if not isinstance(entry, Mapping):
            raise ReelParseError(f"{loc} must be a mapping, got {type(entry).__name__}")
        name = entry.get("name")
        # The empty string is the valid name of the default (root-level) chapter;
        # only a missing or non-string name is an error.
        if not isinstance(name, str):
            raise ReelParseError(f"{loc} is missing a string 'name'")
        if name in seen_names:
            raise ReelParseError(f"{loc}: duplicate chapter name {name!r}")
        seen_names.add(name)

        refs_raw = entry.get("clips", [])
        if refs_raw is None:
            refs_raw = []
        if not isinstance(refs_raw, (list, tuple)):
            raise ReelParseError(f"{loc}.clips must be a list, got {type(refs_raw).__name__}")
        refs = tuple(
            ClipRef(_parse_identity(ref, loc=f"{loc}.clips[{i}]")) for i, ref in enumerate(refs_raw)
        )
        chapters.append(Chapter(name=name, clips=refs))
    return tuple(chapters)


def _parse_clips(raw: Any, *, source: str) -> dict[str, ClipProperties]:
    """Parse the ``clips`` map of identity -> per-clip properties."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ReelParseError(f"{source}: 'clips' must be a mapping, got {type(raw).__name__}")

    clips: dict[str, ClipProperties] = {}
    for key, props_raw in raw.items():
        identity = _parse_identity(key, loc=f"{source}: clips key")
        loc = f"{source}: clips[{identity!r}]"
        if props_raw is None:
            clips[identity] = ClipProperties()
            continue
        if not isinstance(props_raw, Mapping):
            raise ReelParseError(f"{loc} must be a mapping, got {type(props_raw).__name__}")
        clips[identity] = ClipProperties(
            trims=_parse_trims(props_raw.get("trims"), loc=loc),
            title=_opt_bool(props_raw.get("title"), loc=f"{loc}.title"),
            rotate=_opt_int(props_raw.get("rotate"), loc=f"{loc}.rotate"),
            exclude=_req_bool(props_raw.get("exclude", False), loc=f"{loc}.exclude"),
        )
    return clips


def _parse_trims(raw: Any, *, loc: str) -> tuple[Trim, ...]:
    """Parse an ordered list of cut spans {in, out, reason?}; multiple allowed (D-D)."""
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ReelParseError(f"{loc}.trims must be a list, got {type(raw).__name__}")

    trims: list[Trim] = []
    for index, span in enumerate(raw):
        sloc = f"{loc}.trims[{index}]"
        if not isinstance(span, Mapping):
            raise ReelParseError(f"{sloc} must be a mapping, got {type(span).__name__}")
        start = _req_time(span.get("in"), loc=f"{sloc}.in")
        end = _req_time(span.get("out"), loc=f"{sloc}.out")
        if end <= start:
            raise ReelParseError(
                f"{sloc}: invalid cut span, out ({end}) must be greater than in ({start})"
            )
        reason = _opt_str(span.get("reason"), loc=f"{sloc}.reason")
        trims.append(Trim(start=start, end=end, reason=reason))
    return tuple(trims)


def _parse_ignore(raw: Any, *, source: str) -> tuple[str, ...]:
    """Parse the ``ignore`` list of dismissed clip identities."""
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ReelParseError(f"{source}: 'ignore' must be a list, got {type(raw).__name__}")
    return tuple(
        _parse_identity(entry, loc=f"{source}: ignore[{i}]") for i, entry in enumerate(raw)
    )


# --------------------------------------------------------------------------- #
# Cross-reference validation
# --------------------------------------------------------------------------- #


def _validate_cross_references(
    chapters: tuple[Chapter, ...],
    clips: Mapping[str, ClipProperties],
    ignore: tuple[str, ...],
    *,
    source: str,
) -> None:
    """Reject duplicate references, orphaned properties, and ignore/structure conflicts.

    These checks are disk-independent (a referenced clip merely absent from disk is
    a *reconcile* MISSING, not a parse error). Internally: a clip identity must be
    referenced at most once across all chapters; a ``clips`` property entry must
    attach to a referenced clip; an ``ignore`` entry must not also be in structure.
    """
    referenced: set[str] = set()
    for chapter in chapters:
        for ref in chapter.clips:
            if ref.identity in referenced:
                raise ReelParseError(
                    f"{source}: duplicate clip reference {ref.identity!r} "
                    f"(an identity may appear in chapters at most once)"
                )
            referenced.add(ref.identity)

    for identity in clips:
        if identity not in referenced:
            raise ReelParseError(
                f"{source}: dangling clip properties for {identity!r}; "
                f"no chapter references this identity"
            )

    for identity in ignore:
        if identity in referenced:
            raise ReelParseError(
                f"{source}: clip {identity!r} is both referenced in a chapter and "
                f"listed in 'ignore'"
            )


# --------------------------------------------------------------------------- #
# Scalar coercion helpers (each names its location on failure)
# --------------------------------------------------------------------------- #


def _parse_identity(value: Any, *, loc: str) -> str:
    """Validate and normalize a clip identity (an event-relative POSIX path, D-C)."""
    if not isinstance(value, str) or not value.strip():
        raise ReelParseError(f"{loc}: clip identity must be a non-empty string, got {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute():
        raise ReelParseError(f"{loc}: clip identity must be event-relative, got {value!r}")
    if ".." in pure.parts:
        raise ReelParseError(f"{loc}: clip identity must not escape the event root: {value!r}")
    return pure.as_posix()


def _opt_str(value: Any, *, loc: str) -> Optional[str]:
    """Coerce an optional string field; reject non-string non-null values."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReelParseError(f"{loc}: expected a string, got {type(value).__name__}")
    return value


def _parse_date(value: Any, *, loc: str) -> Optional[date]:
    """Parse an optional ISO ``YYYY-MM-DD`` date (ruamel may already yield a date)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ReelParseError(f"{loc}: invalid date {value!r}, expected YYYY-MM-DD") from exc
    raise ReelParseError(f"{loc}: expected a YYYY-MM-DD date, got {type(value).__name__}")


def _opt_bool(value: Any, *, loc: str) -> Optional[bool]:
    """Coerce an optional three-state boolean (None/True/False)."""
    if value is None:
        return None
    return _req_bool(value, loc=loc)


def _req_bool(value: Any, *, loc: str) -> bool:
    """Coerce a required boolean; reject truthy non-booleans (e.g. 1, 'yes')."""
    if not isinstance(value, bool):
        raise ReelParseError(f"{loc}: expected a boolean, got {type(value).__name__}")
    return value


def _opt_int(value: Any, *, loc: str) -> Optional[int]:
    """Coerce an optional integer (used for ``rotate``); reject bools and floats."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReelParseError(f"{loc}: expected an integer, got {type(value).__name__}")
    return value


def _req_time(value: Any, *, loc: str) -> float:
    """Coerce a required, non-negative time in seconds; reject bools and negatives."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReelParseError(f"{loc}: expected a number of seconds, got {type(value).__name__}")
    if value < 0:
        raise ReelParseError(f"{loc}: time must be non-negative, got {value}")
    return float(value)
