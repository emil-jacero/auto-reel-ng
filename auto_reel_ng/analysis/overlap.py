"""Pure overlap resolution: ``black``/``white`` win over ``freeze`` (decision D-AN3).

A static black or white region is also frozen, so ``freezedetect`` reports it too.
Emitting both would double-count the same footage, so the resolver subtracts every
black/white region from each freeze span. What remains of a freeze span (possibly
nothing, possibly one or two clipped pieces) is kept as ``freeze``; black and white
pass through untouched. Every output region therefore carries exactly one ``kind``.
"""

from __future__ import annotations

from typing import List, Tuple

from .models import Segment, SegmentKind

_PRIORITY_KINDS = (SegmentKind.BLACK, SegmentKind.WHITE)


def _subtract(span: Segment, blockers: List[Segment]) -> List[Tuple[float, float]]:
    """Return the parts of ``span`` not covered by any blocker, as ``(start, end)``."""
    pieces: List[Tuple[float, float]] = [(span.start, span.end)]
    for blocker in blockers:
        remaining: List[Tuple[float, float]] = []
        for start, end in pieces:
            if blocker.end <= start or blocker.start >= end:
                remaining.append((start, end))  # disjoint
                continue
            if blocker.start > start:
                remaining.append((start, blocker.start))  # piece before the blocker
            if blocker.end < end:
                remaining.append((blocker.end, end))  # piece after the blocker
        pieces = remaining
    return pieces


def resolve_overlap(segments: List[Segment]) -> List[Segment]:
    """Resolve black/white-over-freeze overlap, returning segments sorted by start.

    Black and white segments are kept verbatim; each freeze segment has the union of
    black/white regions carved out of it, and only the surviving (``end > start``)
    pieces are re-emitted as ``freeze``.
    """
    priority = [s for s in segments if s.kind in _PRIORITY_KINDS]
    freezes = [s for s in segments if s.kind is SegmentKind.FREEZE]

    resolved: List[Segment] = list(priority)
    for freeze in freezes:
        for start, end in _subtract(freeze, priority):
            if end > start:
                resolved.append(
                    Segment(
                        start=start,
                        end=end,
                        kind=SegmentKind.FREEZE,
                        confidence=freeze.confidence,
                    )
                )
    resolved.sort(key=lambda s: (s.start, s.end))
    return resolved
