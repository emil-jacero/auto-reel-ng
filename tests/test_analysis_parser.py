"""Pure log-parser tests, fixtured from exp-005 recorded artifacts (task 3.x).

The black and white artifacts carry full ``black_start:..black_end:..`` lines and are
read verbatim. The exp-005 freeze artifacts were grep-filtered to ``freeze_start``
lines only, so the paired start/end path is exercised against a representative full
``freezedetect`` block (the shape real ffmpeg emits) plus the recorded starts.
"""

from __future__ import annotations

from pathlib import Path

from auto_reel_ng.analysis.models import COARSE_CONFIDENCE, SegmentKind
from auto_reel_ng.analysis.parser import (
    parse_blackdetect_spans,
    parse_freeze_spans,
    parse_pass1,
    parse_pass2,
    spans_to_segments,
)

ARTIFACTS = (
    Path(__file__).resolve().parent.parent
    / "experiments"
    / "005-detection-thresholds"
    / "artifacts"
)

# A representative full freezedetect block (start + duration + end), the shape ffmpeg
# emits unfiltered; the recorded artifact was grepped down to the freeze_start lines.
FREEZE_LOG = """\
[freezedetect @ 0x55] lavfi.freezedetect.freeze_start: 16
[freezedetect @ 0x55] lavfi.freezedetect.freeze_duration: 4
[freezedetect @ 0x55] lavfi.freezedetect.freeze_end: 20
"""


def test_parse_black_artifact() -> None:
    """The recorded blackdetect artifact parses to the BLACK[0,3] ground-truth span."""
    log = (ARTIFACTS / "black_gt.txt").read_text(encoding="utf-8")
    spans = parse_blackdetect_spans(log)
    assert [(s.start, s.end) for s in spans] == [(0.0, 3.0)]


def test_parse_white_artifact() -> None:
    """The recorded negate,blackdetect artifact parses to the WHITE[8,11] span."""
    log = (ARTIFACTS / "white_gt.txt").read_text(encoding="utf-8")
    segments = parse_pass2(log, min_duration=2.0)
    assert [(s.start, s.end, s.kind) for s in segments] == [(8.0, 11.0, SegmentKind.WHITE)]


def test_freeze_artifact_starts_recognized() -> None:
    """The grep-filtered freeze artifact's start timestamps are all recognized."""
    from auto_reel_ng.analysis.parser import _FREEZE_START_RE  # noqa: PLC0415

    log = (ARTIFACTS / "freeze_gt_n0.003.txt").read_text(encoding="utf-8")
    starts = [float(m.group(1)) for m in _FREEZE_START_RE.finditer(log)]
    assert starts == [0.0, 8.0, 16.0]
    # With no freeze_end lines, no complete span can be formed.
    assert parse_freeze_spans(log) == []


def test_freeze_full_block_pairs_start_and_end() -> None:
    """A full freezedetect block pairs into the FREEZE[16,20] span."""
    spans = parse_freeze_spans(FREEZE_LOG)
    assert [(s.start, s.end) for s in spans] == [(16.0, 20.0)]


def test_dangling_freeze_start_closed_at_duration() -> None:
    """A freeze that runs to EOF (no freeze_end) is closed at the known duration."""
    log = "[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 18\n"
    spans = parse_freeze_spans(log, clip_duration=20.0)
    assert [(s.start, s.end) for s in spans] == [(18.0, 20.0)]


def test_dangling_freeze_start_dropped_without_duration() -> None:
    """Without a known duration, an unbounded freeze start cannot become a span."""
    log = "[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 18\n"
    assert parse_freeze_spans(log) == []


def test_min_duration_filters_short_spans() -> None:
    """spans_to_segments drops spans shorter than the configured minimum."""
    from auto_reel_ng.analysis.parser import RawSpan  # noqa: PLC0415

    spans = [RawSpan(0.0, 1.0), RawSpan(5.0, 9.0)]
    segments = spans_to_segments(spans, SegmentKind.BLACK, min_duration=2.0)
    assert [(s.start, s.end) for s in segments] == [(5.0, 9.0)]


def test_coarse_confidence_on_every_segment() -> None:
    """Every emitted segment carries the coarse v1 confidence in [0, 1]."""
    log = (ARTIFACTS / "black_gt.txt").read_text(encoding="utf-8")
    segments = parse_pass1(log, min_duration=2.0)
    assert segments
    for segment in segments:
        assert segment.confidence == COARSE_CONFIDENCE
        assert 0.0 <= segment.confidence <= 1.0


def test_pass1_combines_black_and_freeze() -> None:
    """parse_pass1 surfaces both a black and a freeze span from one log."""
    log = (ARTIFACTS / "black_gt.txt").read_text(encoding="utf-8") + FREEZE_LOG
    segments = parse_pass1(log, min_duration=2.0)
    kinds = sorted(s.kind.value for s in segments)
    assert kinds == ["black", "freeze"]


def test_clean_log_yields_no_segments() -> None:
    """Ordinary footage (no detector lines) yields no segments on either pass.

    This is the zero-false-positive guarantee exp-005 confirmed: a clip with nothing
    to flag must produce an empty suggestion list, not a spurious span.
    """
    clean_log = "frame=  100 fps= 25 q=-0.0 size=N/A time=00:00:04.00 bitrate=N/A speed=8x\n"
    assert parse_pass1(clean_log, min_duration=2.0, clip_duration=4.0) == []
    assert parse_pass2(clean_log, min_duration=2.0) == []
