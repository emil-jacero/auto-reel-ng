"""The output-collision and claimed-movie rules (D-9), shared by the CLI, the API and the worker.

:func:`output_collision` answers "which other events of this project claim the output
path of ``event_dir``?" from what every caller has: the walk root, the layout name and
the clip order. It takes no ``ApiSettings`` and no CLI context. Which events claim a
path at all is :func:`..event.claims.checked_claim` (a failure claims nothing); the
comparison itself is :func:`~.orchestrator.find_output_collisions` (case-insensitive,
NFC-normalised, never auto-suffixed). Read-only.

:func:`claimed_movie` is the other half: it asks whether a file a render would *replace* is the
recorded output of another event's render manifest (the kept, old-named movie of a renamed
event). It differs from :func:`output_collision` in that the path is a *recorded*, no-longer-
current one, and a forced render bypasses it (a collision is never bypassed).

It lives in ``render/`` rather than ``event/`` because it needs both the ingest layout
walk and the output-naming rule, and ``event/`` is a lower layer than either.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, Optional, Sequence, Tuple

from ..event.claims import checked_claim
from ..event.discovery import ClipOrder
from ..ingest import get_layout
from ..staleness.manifest import records_output
from .orchestrator import find_output_collisions, output_relpath


@dataclass(frozen=True)
class OutputCollision:
    """The named event's output path and the other events that claim it."""

    #: Relative to the output directory, as :func:`~.orchestrator.output_relpath` gives it.
    output_path: PurePosixPath
    #: The other claimants' event directories as the layout yields them, sorted by path.
    claimed_by: Tuple[Path, ...]


def output_collision(
    event_dir: Path, *, walk_root: Path, layout: str, order: ClipOrder, today: date
) -> Optional[OutputCollision]:
    """The output collision ``event_dir`` is part of, over every event ``layout`` walks.

    The claimants are the events the layout walks from ``walk_root`` plus ``event_dir``
    itself, which a caller may name although the walk does not reach it. An event that
    fails on its own claims nothing (:func:`..event.claims.checked_claim`), so ``None``
    is returned, without walking, when ``event_dir`` itself fails. Claimants are keyed by
    the path as the layout spells it, never resolved: a symlinked alias the caller names (the
    layout itself walks each real directory once) is a claimant of its own, claiming the path
    its own folder name and ``reel.yaml`` give it. The named
    event is recognised in the walk by its *lexically* normalised path (``os.path.abspath``:
    relative vs absolute, ``..`` segments), never by resolving symlinks, so a caller may
    spell ``event_dir`` and ``walk_root`` from different bases without the event
    colliding with itself.

    The walk's own failure (``LayoutError`` for an unknown layout, ``OSError``)
    propagates: a caller must not enqueue or render an event whose collision it could not
    check (Principle I).
    """
    document, _reason = checked_claim(event_dir, order=order, today=today)
    if document is None:
        return None
    target = output_relpath(document.metadata)
    claims: Dict[Path, PurePosixPath] = {event_dir: target}
    named = os.path.abspath(event_dir)
    for ref in get_layout(layout)(walk_root):
        if os.path.abspath(ref.event_dir) == named:
            continue  # the named event itself: already claimed above
        other, _reason = checked_claim(ref.event_dir, order=order, today=today)
        if other is not None:
            claims[ref.event_dir] = output_relpath(other.metadata)
    others = find_output_collisions(claims).get(event_dir, ())
    if not others:
        return None
    return OutputCollision(output_path=target, claimed_by=tuple(sorted(others, key=str)))


def output_collision_message(output_path: PurePosixPath, claimants: Sequence[str]) -> str:
    """The one wording of the refusal the CLI, the API and the worker print."""
    return (
        f"output path {output_path} is also claimed by {', '.join(claimants)}; "
        "set a distinct title or location in reel.yaml"
    )


@dataclass(frozen=True)
class ClaimedMovie:
    """A file a render would replace, and the other events whose manifests record it."""

    output_path: Path
    #: The other events' directories as the caller spelled them, sorted by path.
    recorded_by: Tuple[Path, ...]


def claimed_movie(
    event_dir: Path, output_path: Path, *, events: Iterable[Path]
) -> Optional[ClaimedMovie]:
    """The other events among ``events`` whose render manifest records ``output_path``.

    ``None`` unless ``output_path`` is an existing regular file: a render that creates a new file
    replaces nothing. ``event_dir`` itself is never a claimant (compared lexically with
    ``os.path.abspath``, never resolving symlinks, as :func:`output_collision` does). The other
    event need not load or be processable: its manifest records a file on disk whatever state its
    ``reel.yaml`` is in. An unreadable manifest claims nothing (the manifest module's fail-open
    convention). Read-only.
    """
    if not output_path.is_file():
        return None
    named = os.path.abspath(event_dir)
    claimants = {
        other
        for other in events
        if os.path.abspath(other) != named and records_output(other, output_path)
    }
    if not claimants:
        return None
    return ClaimedMovie(output_path=output_path, recorded_by=tuple(sorted(claimants, key=str)))


def claimed_movie_message(output_path: PurePosixPath, claimants: Sequence[str]) -> str:
    """The one wording of the claimed-movie refusal the CLI and the worker print.

    ``output_path`` is relative to the output directory (:func:`~.orchestrator.output_relpath`),
    so the text carries no machine path.
    """
    return (
        f"movie {output_path} is recorded as the output of {', '.join(claimants)}; "
        "rendering would replace it (render with force to replace it)"
    )


__all__ = [
    "ClaimedMovie",
    "OutputCollision",
    "claimed_movie",
    "claimed_movie_message",
    "output_collision",
    "output_collision_message",
]
