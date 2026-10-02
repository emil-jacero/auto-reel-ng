"""The layout-aware output-collision rule (D-9), shared by the CLI, the API and the worker.

:func:`output_collision` answers "which other events of this project claim the output
path of ``event_dir``?" from what every caller has: the walk root, the layout name and
the clip order. It takes no ``ApiSettings`` and no CLI context. Which events claim a
path at all is :func:`..event.claims.checked_claim` (a failure claims nothing); the
comparison itself is :func:`~.orchestrator.find_output_collisions` (case-insensitive,
NFC-normalised, never auto-suffixed). Read-only.

It lives in ``render/`` rather than ``event/`` because it needs both the ingest layout
walk and the output-naming rule, and ``event/`` is a lower layer than either.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Dict, Optional, Sequence, Tuple

from ..event.claims import checked_claim
from ..event.discovery import ClipOrder
from ..ingest import get_layout
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
    the path as the layout spells it, never resolved: a symlinked alias is a claimant of
    its own, claiming the path its own folder name and ``reel.yaml`` give it.

    The walk's own failure (``LayoutError`` for an unknown layout, ``OSError``)
    propagates: a caller must not enqueue or render an event whose collision it could not
    check (Principle I).
    """
    document, _reason = checked_claim(event_dir, order=order, today=today)
    if document is None:
        return None
    target = output_relpath(document.metadata)
    claims: Dict[Path, PurePosixPath] = {event_dir: target}
    for ref in get_layout(layout)(walk_root):
        if ref.event_dir == event_dir:
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


__all__ = ["OutputCollision", "output_collision", "output_collision_message"]
