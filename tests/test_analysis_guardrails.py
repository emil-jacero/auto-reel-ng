"""Integration-boundary guardrails: no reel.yaml writes, scan stays side-effect-free."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pytest

from auto_reel_ng.analysis import cache as cache_module
from auto_reel_ng.analysis.cache import analyze_event, cache_dir
from auto_reel_ng.analysis.models import AnalysisConfig, Segment, SegmentKind
from auto_reel_ng.event.discovery import scan_event
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime

SEGMENTS = [Segment(start=0.0, end=3.0, kind=SegmentKind.BLACK, confidence=0.5)]


def _stub_detector(monkeypatch: pytest.MonkeyPatch) -> None:
    def detector(
        path: Path,
        *,
        runtime: Optional[FfmpegRuntime] = None,
        config: Optional[AnalysisConfig] = None,
    ) -> List[Segment]:
        return list(SEGMENTS)

    monkeypatch.setattr(cache_module, "analyze_clip", detector)


def test_analysis_does_not_modify_reel_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running analysis over an event leaves any reel.yaml byte-for-byte unchanged."""
    _stub_detector(monkeypatch)
    (tmp_path / "clip.mp4").write_bytes(b"clip")
    reel = tmp_path / "reel.yaml"
    original = "version: 0\nmetadata:\n  title: Test\n"
    reel.write_text(original, encoding="utf-8")

    analyze_event(tmp_path)

    assert reel.read_text(encoding="utf-8") == original


def test_scan_event_runs_no_detection_and_writes_no_cache(tmp_path: Path) -> None:
    """scan_event is a pure directory read: no detection, no .auto-reel/cache/ sidecar."""
    (tmp_path / "clip.mp4").write_bytes(b"clip")

    listing = scan_event(tmp_path)

    assert listing.identities == ("clip.mp4",)
    assert not cache_dir(tmp_path).exists()
    assert not (tmp_path / ".auto-reel").exists()
