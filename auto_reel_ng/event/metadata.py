"""Event metadata resolution (D-2) and the processable-event rule.

The folder name is the lowest metadata layer: date, title and location each take
the ``reel.yaml`` value when set, else the folder name's. Resolution happens at
load and is never written back — :func:`load_event_document` returns the resolved
document, while :func:`load_authored_document` returns the document as authored
(what a writer persists). :func:`require_processable` is the project-level rule
that an event needs a real date and a title; the loaders themselves stay lenient.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Optional, Tuple, TypeVar

from ..errors import EventMetadataError
from ..reel import ReelDocument, load_document
from ..reel.document import Metadata
from .discovery import (
    ClipOrder,
    FolderName,
    FolderNameProblem,
    parse_folder_name,
    seed_document,
)

#: The editorial document file name within an event directory.
REEL_FILENAME = "reel.yaml"

_T = TypeVar("_T")

_FIX_DATE = "set metadata.date in reel.yaml or correct the folder name"
_FIX_TITLE = "set metadata.title in reel.yaml or correct the folder name"


def resolve_metadata(authored: Metadata, folder: FolderName) -> Metadata:
    """Per field, the authored value when set and not blank, else the folder's."""
    return replace(
        authored,
        title=_pick(_non_blank(authored.title), folder.title),
        date=_pick(authored.date, folder.date),
        location=_pick(_non_blank(authored.location), folder.location),
    )


def reel_exists(path: Path) -> bool:
    """Whether the disk has a ``reel.yaml`` at ``path``; a refusal to answer is not "no".

    ``False`` only when the disk says there is no such file (including a parent that is not a
    directory). Any other failure, a :class:`PermissionError` for an event folder that can be
    listed but not searched above all, propagates: ``Path.exists()`` reads it as absent, which
    seeds a document from the folder name over a ``reel.yaml`` that was never looked at. ``stat``
    follows symlinks, so a dangling link is absent and a symlinked file is present.
    """
    try:
        Path(path).stat()
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def load_authored_document(event_dir: Path, *, order: ClipOrder) -> Tuple[ReelDocument, bool]:
    """``<event>/reel.yaml`` as authored if present, else a folder seed; ``(doc, seeded)``.

    A seed places each chapter's clips in ``order`` (the project's sort rule); an
    existing ``reel.yaml`` keeps its own order. A folder the disk will not let us look into
    raises its :class:`PermissionError` rather than seeding (see :func:`reel_exists`).
    """
    reel_path = Path(event_dir) / REEL_FILENAME
    if reel_exists(reel_path):
        return load_document(reel_path), False
    return seed_document(event_dir, order=order), True


def with_resolved_metadata(document: ReelDocument, event_dir: Path) -> ReelDocument:
    """``document`` with its metadata resolved against ``event_dir``'s folder name."""
    folder = parse_folder_name(Path(event_dir).name)
    return replace(document, metadata=resolve_metadata(document.metadata, folder))


def load_event_document(event_dir: Path, *, order: ClipOrder) -> Tuple[ReelDocument, bool]:
    """Load or seed ``event_dir``'s document with resolved metadata; ``(doc, seeded)``."""
    document, seeded = load_authored_document(event_dir, order=order)
    return with_resolved_metadata(document, event_dir), seeded


def require_processable(event_dir: Path, metadata: Metadata, *, today: date) -> None:
    """Raise :class:`EventMetadataError` unless ``metadata`` has a real date and a title.

    ``metadata`` is the resolved metadata. When a field is missing, the reason is
    the folder name's stated problem for it; a date after ``today`` is rejected
    as a typo.
    """
    event_dir = Path(event_dir)
    folder = parse_folder_name(event_dir.name)
    if metadata.date is None:
        raise EventMetadataError(event_dir.name, f"{_date_problem(folder)}; {_FIX_DATE}")
    if metadata.title is None:
        raise EventMetadataError(event_dir.name, f"folder name has no title; {_FIX_TITLE}")
    if metadata.date > today:
        raise EventMetadataError(
            event_dir.name,
            f"date {metadata.date.isoformat()} is in the future (today is "
            f"{today.isoformat()}); {_FIX_DATE}",
        )


def _date_problem(folder: FolderName) -> str:
    """The folder name's reason for supplying no date, as a phrase."""
    if FolderNameProblem.IMPOSSIBLE_DATE in folder.problems:
        return f"no date: folder name date {folder.raw_date} is not a real date"
    if FolderNameProblem.YEAR_ONLY in folder.problems:
        return f"no date: folder name has a year only ({folder.raw_date})"
    return "no date: folder name has no date"


def _non_blank(value: Optional[str]) -> Optional[str]:
    """``value`` unless it is empty or whitespace-only."""
    return value if value is not None and value.strip() else None


def _pick(authored: Optional[_T], folder: Optional[_T]) -> Optional[_T]:
    return authored if authored is not None else folder


__all__ = [
    "REEL_FILENAME",
    "load_authored_document",
    "load_event_document",
    "reel_exists",
    "require_processable",
    "resolve_metadata",
    "with_resolved_metadata",
]
