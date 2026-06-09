"""Pluggable ingest layouts: map a project root to its event directories (D-6).

A *layout* is a callable ``(root, years?) -> Iterable[EventRef]`` that yields the
event directories under a project root. It never opens clips — that stays
:func:`~auto_reel_ng.event.discovery.scan_event`. Layouts register by name so
configuration/CLI can select one and new layouts can be added later without
touching the walk callers (decision **D-CLI1**).

Two built-ins ship: ``year-event`` (the auto-reel ``<year>/<event>/`` convention,
with an optional year filter) and ``flat`` (events directly under the root).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Optional, Protocol

from ..errors import EngineError
from ..event.discovery import parse_folder_name

logger = logging.getLogger(__name__)

#: The layout used when neither config.yaml nor the CLI selects one.
DEFAULT_LAYOUT = "year-event"


class LayoutError(EngineError):
    """A layout was requested by a name that is not registered (fail-loud, D-CLI1)."""


@dataclass(frozen=True)
class FolderHint:
    """Folder-name metadata parsed from an event directory name (a *hint* only).

    Discovery seeding re-derives metadata from the same folder name, so this is
    advisory context for the CLI (a title/date to display or filter on), never the
    source of truth for a rendered document.
    """

    date: date
    title: str
    location: Optional[str] = None


@dataclass(frozen=True)
class EventRef:
    """One event directory yielded by a layout, plus its folder-name hint."""

    event_dir: Path
    metadata_hint: Optional[FolderHint] = None


class Layout(Protocol):
    """A project-root walk: ``(root, years?) -> Iterable[EventRef]`` (D-CLI1)."""

    def __call__(self, root: Path, years: Optional[Iterable[str]] = None) -> Iterable[EventRef]: ...


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

_REGISTRY: dict[str, Layout] = {}


def register_layout(name: str, layout: Layout) -> None:
    """Register ``layout`` under ``name`` (a later registration replaces an earlier)."""
    _REGISTRY[name] = layout


def get_layout(name: str) -> Layout:
    """Return the layout registered as ``name``, or fail loud naming the unknown one."""
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "<none>"
        raise LayoutError(
            f"unknown ingest layout {name!r}; registered layouts are: {known}"
        ) from None


def layout_names() -> tuple[str, ...]:
    """Every registered layout name, sorted."""
    return tuple(sorted(_REGISTRY))


# --------------------------------------------------------------------------- #
# Built-in layouts
# --------------------------------------------------------------------------- #


def _folder_hint(name: str) -> Optional[FolderHint]:
    """Parse ``YYYY-MM-DD - Title [- Location]`` into a hint, or None."""
    parsed = parse_folder_name(name)
    if parsed is None:
        return None
    event_date, title, location = parsed
    return FolderHint(date=event_date, title=title, location=location)


def _subdirs(directory: Path) -> list[Path]:
    """Immediate subdirectories of ``directory``, sorted by name."""
    return sorted((p for p in directory.iterdir() if p.is_dir()), key=lambda p: p.name)


def year_event_layout(root: Path, years: Optional[Iterable[str]] = None) -> Iterable[EventRef]:
    """Walk ``<root>/<year>/<event>/``; optionally restrict to ``years`` (D-6)."""
    root = Path(root)
    year_filter = {str(y) for y in years} if years is not None else None
    for year_dir in _subdirs(root):
        if year_filter is not None and year_dir.name not in year_filter:
            continue
        for event_dir in _subdirs(year_dir):
            yield EventRef(event_dir=event_dir, metadata_hint=_folder_hint(event_dir.name))


def flat_layout(root: Path, years: Optional[Iterable[str]] = None) -> Iterable[EventRef]:
    """Yield each immediate subdirectory of ``root`` as an event (no year level)."""
    if years:
        logger.debug("flat layout has no year level; ignoring the year filter %s", list(years))
    for event_dir in _subdirs(Path(root)):
        yield EventRef(event_dir=event_dir, metadata_hint=_folder_hint(event_dir.name))


register_layout("year-event", year_event_layout)
register_layout("flat", flat_layout)
