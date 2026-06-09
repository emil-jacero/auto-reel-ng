"""Pure parsing of ffmpeg detector log text into :class:`Segment`s (decision D-AN1).

``str -> list[Segment]`` with no I/O, so the bulk of the suite runs against recorded
log text (exp-005 artifacts) instead of a live decode. Two log shapes are handled:

- ``blackdetect`` (used for both black and the inverted white pass)::

      [blackdetect @ 0x..] black_start:0 black_end:3 black_duration:3

- ``freezedetect``, which logs start/end on separate lines::

      [freezedetect @ 0x..] lavfi.freezedetect.freeze_start: 16
      [freezedetect @ 0x..] lavfi.freezedetect.freeze_duration: 4
      [freezedetect @ 0x..] lavfi.freezedetect.freeze_end: 20
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from .models import COARSE_CONFIDENCE, Segment, SegmentKind

#: A blackdetect span; the same line shape carries both black and white results.
_BLACK_RE = re.compile(r"black_start\s*:\s*([\d.]+)\s+black_end\s*:\s*([\d.]+)")
#: freezedetect logs each boundary on its own line, with a metadata-key prefix.
_FREEZE_START_RE = re.compile(r"freezedetect\.freeze_start\s*:\s*([\d.]+)")
_FREEZE_END_RE = re.compile(r"freezedetect\.freeze_end\s*:\s*([\d.]+)")


@dataclass(frozen=True)
class RawSpan:
    """A parsed ``[start, end)`` pair before min-duration filtering or typing."""

    start: float
    end: float


def parse_blackdetect_spans(log: str) -> List[RawSpan]:
    """Extract every ``black_start``/``black_end`` pair from ``log`` in order."""
    return [RawSpan(float(m.group(1)), float(m.group(2))) for m in _BLACK_RE.finditer(log)]


def parse_freeze_spans(log: str, *, clip_duration: Optional[float] = None) -> List[RawSpan]:
    """Pair ``freeze_start`` lines with their following ``freeze_end`` lines.

    A trailing ``freeze_start`` with no matching ``freeze_end`` means the clip ended
    while still frozen; it is closed at ``clip_duration`` when that is known, and
    dropped otherwise (an unbounded span cannot become a :class:`Segment`).
    """
    spans: List[RawSpan] = []
    pending_start: Optional[float] = None
    for line in log.splitlines():
        start_match = _FREEZE_START_RE.search(line)
        if start_match is not None:
            pending_start = float(start_match.group(1))
            continue
        end_match = _FREEZE_END_RE.search(line)
        if end_match is not None and pending_start is not None:
            spans.append(RawSpan(pending_start, float(end_match.group(1))))
            pending_start = None
    if pending_start is not None and clip_duration is not None and clip_duration > pending_start:
        spans.append(RawSpan(pending_start, clip_duration))
    return spans


def spans_to_segments(
    spans: List[RawSpan], kind: SegmentKind, *, min_duration: float
) -> List[Segment]:
    """Type raw spans as ``kind`` segments, dropping any shorter than ``min_duration``.

    ffmpeg's ``d=`` already filters by duration, but applying it here too keeps the
    parser honest under the override scenario and independent of the runner.
    """
    segments: List[Segment] = []
    for span in spans:
        if span.end - span.start < min_duration:
            continue
        segments.append(
            Segment(start=span.start, end=span.end, kind=kind, confidence=COARSE_CONFIDENCE)
        )
    return segments


def parse_pass1(
    log: str, *, min_duration: float, clip_duration: Optional[float] = None
) -> List[Segment]:
    """Parse a pass-1 log into black + freeze segments (pre-overlap-resolution)."""
    black = spans_to_segments(
        parse_blackdetect_spans(log), SegmentKind.BLACK, min_duration=min_duration
    )
    freeze = spans_to_segments(
        parse_freeze_spans(log, clip_duration=clip_duration),
        SegmentKind.FREEZE,
        min_duration=min_duration,
    )
    return black + freeze


def parse_pass2(log: str, *, min_duration: float) -> List[Segment]:
    """Parse a pass-2 (``negate,blackdetect``) log into white segments."""
    return spans_to_segments(
        parse_blackdetect_spans(log), SegmentKind.WHITE, min_duration=min_duration
    )
