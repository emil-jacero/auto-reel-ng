"""Discovery: seed a complete v0 document from folder structure (decision **D-A**).

Folder layout is used only as a *hint* on first discovery: subdirectories become
chapters, root-level clips become the default chapter, and the folder name
(``[YYYY-MM-DD - ]Title[ - Location]``, parsed leniently) seeds ``metadata``. After seeding, structure
lives in the document and the loader never consults folder layout again. Seeding
is expressed as :func:`~auto_reel_ng.event.reconcile.reconcile` against an empty
document — every disk clip is NEW and becomes part of the seeded structure.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Optional, Sequence

from ..reel.document import (
    DEFAULT_CHAPTER_NAME,
    DEFAULT_CLIP_ORDER,
    Chapter,
    ClipOrder,
    ClipRef,
    Metadata,
    ReelDocument,
    SortMethod,
)
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


_DIGITS_RE = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple[tuple[int, int | str], ...]:
    """Digit runs as ints, everything else casefolded: clip2 < clip10, img_4863 < IMG_4933."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in _DIGITS_RE.split(name)
        if part
    )


def order_clips(identities: Sequence[str], event_dir: Path, order: ClipOrder) -> tuple[str, ...]:
    """Order event-relative ``identities`` by ``order``; never probes (``datetime`` = ``st_mtime``).

    ``stat`` follows symlinks, so a symlinked clip sorts by its target's mtime.
    ``custom`` places clips whose file name is in ``custom_order`` first, by position
    (ties by filename), then every other clip by filename.
    """
    event_dir = Path(event_dir)

    def filename_key(identity: str) -> tuple[tuple[tuple[int, int | str], ...], str]:
        return natural_key(Path(identity).name), identity

    if order.method is SortMethod.DATETIME:
        mtimes = {identity: os.stat(event_dir / identity).st_mtime for identity in identities}
        ordered = sorted(identities, key=lambda i: (mtimes[i], filename_key(i)))
    elif order.method is SortMethod.CUSTOM:
        positions = order.custom_order
        ordered = sorted(
            identities,
            key=lambda i: (
                (0, positions[Path(i).name]) if Path(i).name in positions else (1, 0),
                filename_key(i),
            ),
        )
    else:
        ordered = sorted(identities, key=filename_key)
    if order.reverse:
        ordered.reverse()
    return tuple(ordered)


def seed_document(event_dir: Path, *, order: ClipOrder = DEFAULT_CLIP_ORDER) -> ReelDocument:
    """Seed a complete v0 :class:`ReelDocument` from ``event_dir`` folder structure.

    Metadata comes from the folder name; structure comes from the disk scan, with
    each chapter's clips placed in ``order``. The seed is validated as reconcile
    against an empty document (every clip NEW).
    """
    event_dir = Path(event_dir)
    listing = scan_event(event_dir)

    # Seeding is reconcile against an absent document: everything must be NEW.
    result = reconcile(listing.identities, None)
    assert all(s is ClipStatus.NEW for s in result.classification.values())  # nosec B101

    metadata = _metadata_from_folder_name(event_dir.name)
    chapters = tuple(
        Chapter(
            name=name,
            clips=tuple(ClipRef(identity) for identity in order_clips(clips, event_dir, order)),
        )
        for name, clips in listing.by_chapter
    )
    return ReelDocument(metadata=metadata, chapters=chapters)


# --------------------------------------------------------------------------- #
# Folder-name metadata
# --------------------------------------------------------------------------- #


class FolderNameProblem(StrEnum):
    """Why a folder name could not supply a field (a closed set; messages are built at the error site)."""

    IMPOSSIBLE_DATE = "impossible_date"  # well-formed YYYY-MM-DD that is not a calendar date
    YEAR_ONLY = "year_only"  # a leading 4-digit year and no month/day
    NO_DATE = "no_date"  # no leading date token at all
    NO_TITLE = "no_title"  # nothing left after the date token


@dataclass(frozen=True)
class FolderName:
    """What an event folder name ``[<date> - ]<title>[ - <location>]`` states.

    Every field the name supplies is extracted, whether or not the date part is
    usable; a field it cannot supply is ``None`` with the reason in ``problems``.
    Nothing is fabricated. ``raw_date`` is the date token as written, for messages.
    """

    date: Optional[date]
    title: Optional[str]
    location: Optional[str]
    problems: tuple[FolderNameProblem, ...] = ()
    raw_date: Optional[str] = None


_FOLDER_NAME_RE = re.compile(r"^(?:(?P<token>\d{4}(?:-\d{2}-\d{2})?)(?:\s*-\s*|$))?(?P<rest>.*)$")
_LOCATION_SEPARATOR_RE = re.compile(r"\s+-\s+")


def _metadata_from_folder_name(folder_name: str) -> Metadata:
    """Seed metadata from whatever the folder name supplies (never a placeholder)."""
    parsed = parse_folder_name(folder_name)
    if parsed.problems:
        logger.debug("Folder name %r: %s", folder_name, ", ".join(p.value for p in parsed.problems))
    return Metadata(title=parsed.title, date=parsed.date, location=parsed.location)


def parse_folder_name(folder_name: str) -> FolderName:
    """Parse ``[<date> - ]<title>[ - <location>]`` leniently; never raises.

    The date is set only for a real ``YYYY-MM-DD`` calendar date; otherwise the
    result states why (impossible date, year only, no date). Title and location
    are extracted from the remainder regardless of the date.
    """
    match = _FOLDER_NAME_RE.match(folder_name.strip())
    assert match is not None  # nosec B101 - the pattern matches every string
    token = match.group("token")
    problems: list[FolderNameProblem] = []

    event_date: Optional[date] = None
    if token is None:
        problems.append(FolderNameProblem.NO_DATE)
    elif len(token) == 4:
        problems.append(FolderNameProblem.YEAR_ONLY)
    else:
        try:
            event_date = datetime.strptime(token, "%Y-%m-%d").date()
        except ValueError:
            problems.append(FolderNameProblem.IMPOSSIBLE_DATE)

    title: Optional[str] = None
    location: Optional[str] = None
    rest = match.group("rest").strip(" -")
    if rest:
        parts = _LOCATION_SEPARATOR_RE.split(rest)
        if len(parts) > 1:
            title = format_title_case(" - ".join(parts[:-1]).strip())
            location = format_title_case(parts[-1].strip())
        else:
            title = format_title_case(rest)
    if not title:
        title = None
        problems.append(FolderNameProblem.NO_TITLE)

    return FolderName(
        date=event_date,
        title=title,
        location=location or None,
        problems=tuple(problems),
        raw_date=token,
    )


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
