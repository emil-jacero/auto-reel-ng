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
from ..event.discovery import IGNORE_MARKER, is_reelignored, parse_folder_name

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
    """A hint when the folder name states a real date and a title, else None."""
    parsed = parse_folder_name(name)
    if parsed.date is None or parsed.title is None:
        return None
    return FolderHint(date=parsed.date, title=parsed.title, location=parsed.location)


def _subdirs(directory: Path) -> list[Path]:
    """Immediate subdirectories of ``directory``, sorted by name."""
    return sorted((p for p in directory.iterdir() if p.is_dir()), key=lambda p: p.name)


def _is_canonical(root: Path, event_dir: Path) -> bool:
    """True when ``event_dir`` is reached from ``root`` without crossing a symlink."""
    return event_dir.resolve() == root.resolve() / event_dir.relative_to(root)


def _walk_dirs(root: Path, rows: Iterable[Path]) -> list[Path]:
    """The event directories to yield: ``.reelignore`` skipped, then aliases collapsed.

    Rows that resolve to the same real directory are one event. The row reached without
    crossing a symlink wins, else the first in walk order; every other row is dropped with
    a WARNING naming it, the kept row and the real target. Walk order is preserved.
    """
    live: list[Path] = []
    for event_dir in rows:
        if is_reelignored(event_dir):
            logger.info("skipping %s: %s", event_dir, IGNORE_MARKER)
            continue
        live.append(event_dir)

    groups: dict[Path, list[Path]] = {}
    for event_dir in live:
        groups.setdefault(event_dir.resolve(), []).append(event_dir)

    kept: set[Path] = set()
    for target, members in groups.items():
        if len(members) == 1:
            kept.add(members[0])
            continue
        winner = next((m for m in members if _is_canonical(root, m)), members[0])
        kept.add(winner)
        for alias in members:
            if alias is not winner:
                logger.warning("skipping %s: alias of %s (-> %s)", alias, winner, target)

    return [event_dir for event_dir in live if event_dir in kept]


def _event_refs(event_dirs: Iterable[Path]) -> Iterable[EventRef]:
    """Yield an :class:`EventRef` per (already filtered and de-aliased) directory."""
    for event_dir in event_dirs:
        yield EventRef(event_dir=event_dir, metadata_hint=_folder_hint(event_dir.name))


def year_event_layout(root: Path, years: Optional[Iterable[str]] = None) -> Iterable[EventRef]:
    """Walk ``<root>/<year>/<event>/``; optionally restrict to ``years`` (D-6).

    Aliases are collapsed over *every* year before the year filter applies, so an alias
    of an event in an excluded year is still recognised (and dropped, with a WARNING). A
    year outside the filter is listed best-effort: one that cannot be read is logged and
    skipped, while a selected year (or the root) that cannot be read still raises.
    """
    root = Path(root)
    year_filter = {str(y) for y in years} if years is not None else None
    rows: list[Path] = []
    for year_dir in _subdirs(root):
        if year_filter is None or year_dir.name in year_filter:
            rows.extend(_subdirs(year_dir))
            continue
        try:
            rows.extend(_subdirs(year_dir))
        except OSError as exc:
            logger.warning("not listing %s (outside the year filter): %s", year_dir, exc)
    event_dirs = _walk_dirs(root, rows)
    if year_filter is not None:
        event_dirs = [d for d in event_dirs if d.parent.name in year_filter]
    yield from _event_refs(event_dirs)


def flat_layout(root: Path, years: Optional[Iterable[str]] = None) -> Iterable[EventRef]:
    """Yield each immediate subdirectory of ``root`` as an event (no year level)."""
    if years:
        logger.debug("flat layout has no year level; ignoring the year filter %s", list(years))
    root = Path(root)
    yield from _event_refs(_walk_dirs(root, _subdirs(root)))


register_layout("year-event", year_event_layout)
register_layout("flat", flat_layout)
