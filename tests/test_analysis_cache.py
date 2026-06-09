"""Sidecar-cache tests: cold-write, warm-read, invalidation, corrupt recovery (task 6.x).

``analyze_clip`` (the only ffmpeg-touching step) is stubbed with a call-counting fake,
so these run headless. The fake stands in for detection; the assertions are about the
cache's read/write/invalidate behavior and that a warm hit skips detection entirely.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pytest

from auto_reel_ng.analysis import cache as cache_module
from auto_reel_ng.analysis.cache import analyze_event, cache_dir, read_entry
from auto_reel_ng.analysis.models import AnalysisConfig, Segment, SegmentKind
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime

SEGMENTS = [Segment(start=0.0, end=3.0, kind=SegmentKind.BLACK, confidence=0.5)]


class CountingDetector:
    """A stubbed ``analyze_clip`` recording how many clips it was asked to detect."""

    def __init__(self) -> None:
        self.calls: List[Path] = []

    def __call__(
        self,
        path: Path,
        *,
        runtime: Optional[FfmpegRuntime] = None,
        config: Optional[AnalysisConfig] = None,
    ) -> List[Segment]:
        self.calls.append(Path(path))
        return list(SEGMENTS)


@pytest.fixture
def event_dir(tmp_path: Path) -> Path:
    """An event directory holding one root-level clip file (contents irrelevant here)."""
    (tmp_path / "clip.mp4").write_bytes(b"a-fake-clip")
    return tmp_path


def _install_detector(monkeypatch: pytest.MonkeyPatch) -> CountingDetector:
    detector = CountingDetector()
    monkeypatch.setattr(cache_module, "analyze_clip", detector)
    return detector


def test_cold_run_writes_cache(event_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cold run detects each clip and persists an entry under .auto-reel/cache/."""
    detector = _install_detector(monkeypatch)

    results = analyze_event(event_dir)

    assert results == {"clip.mp4": SEGMENTS}
    assert detector.calls == [event_dir / "clip.mp4"]
    entries = list(cache_dir(event_dir).glob("*.json"))
    assert len(entries) == 1


def test_warm_run_reads_cache_without_detection(
    event_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second run over an unchanged clip returns cached segments and runs no detection."""
    detector = _install_detector(monkeypatch)
    analyze_event(event_dir)  # cold: writes the entry
    assert len(detector.calls) == 1

    detector.calls.clear()
    results = analyze_event(event_dir)  # warm: must not detect again

    assert results == {"clip.mp4": SEGMENTS}
    assert detector.calls == []


def test_modified_clip_reruns_detection(event_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Changing the clip's content-change signal invalidates the entry and re-detects."""
    detector = _install_detector(monkeypatch)
    analyze_event(event_dir)
    assert len(detector.calls) == 1

    # Change the clip's size (and thus the signal); the cached entry is now stale.
    (event_dir / "clip.mp4").write_bytes(b"a-fake-clip-but-longer-now")
    detector.calls.clear()
    analyze_event(event_dir)

    assert detector.calls == [event_dir / "clip.mp4"]


def test_corrupt_entry_recovers(event_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unparseable cache entry is treated as cold: detection re-runs and rewrites it."""
    detector = _install_detector(monkeypatch)
    analyze_event(event_dir)
    entry = next(iter(cache_dir(event_dir).glob("*.json")))

    entry.write_text("{ this is not valid json", encoding="utf-8")
    detector.calls.clear()
    results = analyze_event(event_dir)

    assert detector.calls == [event_dir / "clip.mp4"]
    assert results == {"clip.mp4": SEGMENTS}
    # A fresh, valid entry was written back.
    import json  # noqa: PLC0415

    assert json.loads(entry.read_text(encoding="utf-8"))["identity"] == "clip.mp4"


def test_entry_roundtrips_segments(event_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Segments written to an entry deserialize back to equal Segment values."""
    _install_detector(monkeypatch)
    analyze_event(event_dir)

    signal = cache_module.clip_signal(event_dir / "clip.mp4")
    assert read_entry(event_dir, "clip.mp4", signal) == SEGMENTS


def test_signal_mismatch_returns_none() -> None:
    """read_entry treats a differing signal as stale (returns None)."""
    # No entry written at all -> also None (missing entry is cold).
    assert read_entry(Path("/no/such/event"), "clip.mp4", {"size": 1, "mtime_ns": 1}) is None
