"""Pure overlap-resolution tests: black/white > freeze precedence (task 4.x)."""

from __future__ import annotations

from auto_reel_ng.analysis.models import Segment, SegmentKind
from auto_reel_ng.analysis.overlap import resolve_overlap


def _seg(start: float, end: float, kind: SegmentKind) -> Segment:
    return Segment(start=start, end=end, kind=kind, confidence=0.5)


def test_freeze_fully_inside_black_is_dropped() -> None:
    """A freeze entirely within a black span is suppressed; only black remains."""
    segments = [
        _seg(0.0, 5.0, SegmentKind.BLACK),
        _seg(1.0, 4.0, SegmentKind.FREEZE),
    ]
    resolved = resolve_overlap(segments)
    assert [(s.start, s.end, s.kind) for s in resolved] == [(0.0, 5.0, SegmentKind.BLACK)]


def test_freeze_partially_overlapping_is_clipped() -> None:
    """A freeze straddling a black span keeps only its non-overlapping remainder."""
    segments = [
        _seg(0.0, 5.0, SegmentKind.BLACK),
        _seg(3.0, 9.0, SegmentKind.FREEZE),
    ]
    resolved = resolve_overlap(segments)
    assert [(s.start, s.end, s.kind) for s in resolved] == [
        (0.0, 5.0, SegmentKind.BLACK),
        (5.0, 9.0, SegmentKind.FREEZE),
    ]


def test_freeze_spanning_a_block_splits_into_two() -> None:
    """A freeze that contains a shorter black span splits around it."""
    segments = [
        _seg(2.0, 4.0, SegmentKind.BLACK),
        _seg(0.0, 6.0, SegmentKind.FREEZE),
    ]
    resolved = resolve_overlap(segments)
    assert [(s.start, s.end, s.kind) for s in resolved] == [
        (0.0, 2.0, SegmentKind.FREEZE),
        (2.0, 4.0, SegmentKind.BLACK),
        (4.0, 6.0, SegmentKind.FREEZE),
    ]


def test_non_overlapping_freeze_is_kept() -> None:
    """A freeze disjoint from every black/white span passes through unchanged."""
    segments = [
        _seg(0.0, 3.0, SegmentKind.BLACK),
        _seg(10.0, 14.0, SegmentKind.FREEZE),
    ]
    resolved = resolve_overlap(segments)
    assert [(s.start, s.end, s.kind) for s in resolved] == [
        (0.0, 3.0, SegmentKind.BLACK),
        (10.0, 14.0, SegmentKind.FREEZE),
    ]


def test_black_white_freeze_same_region_resolves_to_one_kind() -> None:
    """Black, white, and freeze over the exp-005 ground truth resolve cleanly.

    The synthetic clip has BLACK[0,3], WHITE[8,11] and a real FREEZE[16,20], plus
    freeze firing over the static black/white spans (freeze starts at 0, 8, 16).
    After resolution each region carries exactly one kind and the freeze-over-black
    and freeze-over-white duplicates are gone.
    """
    segments = [
        _seg(0.0, 3.0, SegmentKind.BLACK),
        _seg(8.0, 11.0, SegmentKind.WHITE),
        _seg(0.0, 3.0, SegmentKind.FREEZE),  # freeze over the black span
        _seg(8.0, 11.0, SegmentKind.FREEZE),  # freeze over the white span
        _seg(16.0, 20.0, SegmentKind.FREEZE),  # the genuine freeze
    ]
    resolved = resolve_overlap(segments)
    assert [(s.start, s.end, s.kind) for s in resolved] == [
        (0.0, 3.0, SegmentKind.BLACK),
        (8.0, 11.0, SegmentKind.WHITE),
        (16.0, 20.0, SegmentKind.FREEZE),
    ]
