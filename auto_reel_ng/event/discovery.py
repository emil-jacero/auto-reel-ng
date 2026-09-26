"""Discovery: seed a complete v0 document from folder structure (decision **D-A**).

Folder layout is used only as a *hint* on first discovery: subdirectories become
chapters, root-level clips become the default chapter, and the folder name
(``YYYY-MM-DD - Title [- Location]``) seeds ``metadata``. After seeding, structure
lives in the document and the loader never consults folder layout again. Seeding
is expressed as :func:`~auto_reel_ng.event.reconcile.reconcile` against an empty
document — every disk clip is NEW and becomes part of the seeded structure.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from ..reel.document import DEFAULT_CHAPTER_NAME, Chapter, ClipRef, Metadata, ReelDocument
from .reconcile import ClipStatus, reconcile

logger = logging.getLogger(__name__)

# Video file extensions discovery scans for (lowercased, with leading dot).
VIDEO_EXTENSIONS = frozenset(
    {
        ".mp4",
        ".mov",
        ".m4v",
        ".avi",
        ".mkv",
        ".mts",
        ".m2ts",
        ".mpg",
        ".mpeg",
        ".wmv",
        ".3gp",
        ".flv",
        ".webm",
    }
)

# Legacy archive conventions (carried from auto-reel): a camera's pre-conversion
# originals live in ``original/``; a ``.reelignore`` file (contents unread) marks an
# event or chapter directory that must not be discovered.
ORIGINALS_DIR = "original"
IGNORE_MARKER = ".reelignore"

# Swedish/English short words kept lowercase in title-case (carried from auto-reel).
_LOWERCASE_WORDS = frozenset(
    {
        "och",
        "eller",
        "men",
        "utan",
        "av",
        "på",
        "i",
        "för",
        "till",
        "från",
        "med",
        "över",
        "under",
        "vid",
        "genom",
        "mot",
        "om",
        "åt",
        "ur",
        "and",
        "or",
        "but",
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
    }
)


@dataclass(frozen=True)
class DiskListing:
    """A scan of an event directory: clips grouped into disk-derived chapters.

    ``by_chapter`` preserves order (default chapter first, then subdirs by name);
    each entry is (chapter name, ordered clip identities). ``identities`` is the
    flat, sorted set of every clip seen — the input :func:`reconcile` consumes.
    """

    by_chapter: tuple[tuple[str, tuple[str, ...]], ...]

    @property
    def identities(self) -> tuple[str, ...]:
        """Every clip identity on disk, deterministically sorted."""
        flat = [identity for _, clips in self.by_chapter for identity in clips]
        return tuple(sorted(flat))


def scan_event(event_dir: Path) -> DiskListing:
    """Scan ``event_dir`` for video clips grouped into disk-derived chapters.

    Root-level videos form the default chapter; each immediate subdirectory that
    contains videos forms a named chapter, except ``original/`` (any case) and a
    subdirectory holding ``.reelignore``. Discovery is one level deep. Ordering is
    deterministic (subdirs and files sorted by name). Empty groups are omitted.
    """
    event_dir = Path(event_dir)
    groups: list[tuple[str, tuple[str, ...]]] = []

    root_clips = _video_identities(event_dir, event_dir)
    if root_clips:
        groups.append((DEFAULT_CHAPTER_NAME, root_clips))

    subdirs = (p for p in event_dir.iterdir() if p.is_dir() and _is_chapter_dir(p))
    for subdir in sorted(subdirs, key=lambda p: p.name):
        sub_clips = _video_identities(subdir, event_dir)
        if sub_clips:
            groups.append((subdir.name, sub_clips))

    return DiskListing(by_chapter=tuple(groups))


def is_reelignored(directory: Path) -> bool:
    """True when ``directory`` carries the legacy ``.reelignore`` marker (contents unread)."""
    return (directory / IGNORE_MARKER).is_file()


def _is_chapter_dir(subdir: Path) -> bool:
    """An event subdirectory contributes clips unless it holds originals or is ignored."""
    return subdir.name.casefold() != ORIGINALS_DIR and not is_reelignored(subdir)


def seed_document(event_dir: Path) -> ReelDocument:
    """Seed a complete v0 :class:`ReelDocument` from ``event_dir`` folder structure.

    Metadata comes from the folder name; structure comes from the disk scan. The
    seed is validated as reconcile against an empty document (every clip NEW).
    """
    event_dir = Path(event_dir)
    listing = scan_event(event_dir)

    # Seeding is reconcile against an absent document: everything must be NEW.
    result = reconcile(listing.identities, None)
    assert all(s is ClipStatus.NEW for s in result.classification.values())  # nosec B101

    metadata = _metadata_from_folder_name(event_dir.name)
    chapters = tuple(
        Chapter(name=name, clips=tuple(ClipRef(identity) for identity in clips))
        for name, clips in listing.by_chapter
    )
    return ReelDocument(metadata=metadata, chapters=chapters)


# --------------------------------------------------------------------------- #
# Folder-name metadata
# --------------------------------------------------------------------------- #


def _metadata_from_folder_name(folder_name: str) -> Metadata:
    """Parse ``YYYY-MM-DD - Title [- Location]`` into metadata (lenient on failure)."""
    parsed = parse_folder_name(folder_name)
    if parsed is None:
        logger.debug("Could not parse metadata from folder name: %s", folder_name)
        return Metadata()
    event_date, title, location = parsed
    return Metadata(title=title, date=event_date, location=location)


def parse_folder_name(folder_name: str) -> Optional[tuple[date, str, Optional[str]]]:
    """Parse ``YYYY-MM-DD - Title [- Location]``; return None if it does not match."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", folder_name)
    if not match:
        return None
    try:
        event_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None

    remaining = folder_name[len(match.group(1)) :].strip(" -")
    if not remaining:
        return None

    parts = remaining.rsplit(" - ", 1)
    title = format_title_case(parts[0].strip())
    location = format_title_case(parts[1].strip()) if len(parts) == 2 else None
    return event_date, title, location


def format_title_case(text: str) -> str:
    """Title-case ``text`` keeping Swedish/English short words lowercase (carried over)."""
    if not text:
        return text
    words = text.split()
    out: list[str] = []
    for index, word in enumerate(words):
        clean = re.sub(r"[^\w\såäöÅÄÖ]", "", word.lower())
        if index == 0:
            out.append(word.capitalize())
        elif re.match(r"\d+\w*", clean):
            out.append(word.lower())
        elif clean in _LOWERCASE_WORDS:
            out.append(word.lower())
        else:
            out.append(word.capitalize())
    return " ".join(out)


def _video_identities(directory: Path, event_root: Path) -> tuple[str, ...]:
    """Event-relative identities of immediate video files in ``directory``, sorted."""
    identities = [
        path.relative_to(event_root).as_posix()
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return tuple(sorted(identities))
