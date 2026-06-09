"""Detection-runner tests: two-pass invocation, fail-loud, and a live integration run.

The headless tests drive :func:`analyze_clip` with a fake runtime that returns canned
detector logs (chosen by which filter chain the pass carries) and a stubbed probe, so
the runner's composition is verified without a decode. The integration test, behind
the ``has_ffmpeg`` marker, runs the real two passes against a generated clip.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional, Sequence

import pytest

from auto_reel_ng.analysis import runner as runner_module
from auto_reel_ng.analysis.models import SegmentKind
from auto_reel_ng.analysis.runner import analyze_clip
from auto_reel_ng.errors import AnalysisError, FfmpegError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime

# Canned detector logs keyed by which pass produced them.
PASS1_LOG = (
    "[blackdetect @ 0x1] black_start:0 black_end:3 black_duration:3\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 0\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 3\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 3\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 16\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 4\n"
    "[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 20\n"
)
PASS2_LOG = "[blackdetect @ 0x2] black_start:8 black_end:11 black_duration:3\n"


class FakeRuntime:
    """A stand-in for :class:`FfmpegRuntime` that records calls and returns canned logs."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: List[List[str]] = []
        self._fail = fail

    def run(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        if self._fail:
            raise FfmpegError("Command exited 1: ffmpeg ...\nstderr:\nbad")
        vf = list(args)[list(args).index("-vf") + 1]
        stderr = PASS2_LOG if vf.startswith("negate") else PASS1_LOG
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr=stderr)


def _stub_probe(monkeypatch: pytest.MonkeyPatch, duration: Optional[float] = 20.0) -> None:
    class _Meta:
        pass

    def fake_probe(_path: Path, *, runtime: object = None) -> object:
        meta = _Meta()
        meta.duration = duration  # type: ignore[attr-defined]
        return meta

    monkeypatch.setattr(runner_module, "probe_media", fake_probe)


def test_exactly_two_invocations_per_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    """analyze_clip issues exactly two ffmpeg passes: black+freeze, then white."""
    _stub_probe(monkeypatch)
    fake = FakeRuntime()

    analyze_clip("/clips/a.mp4", runtime=fake)  # type: ignore[arg-type]

    assert len(fake.calls) == 2
    first_vf = fake.calls[0][fake.calls[0].index("-vf") + 1]
    second_vf = fake.calls[1][fake.calls[1].index("-vf") + 1]
    assert "blackdetect" in first_vf and "freezedetect" in first_vf
    assert second_vf.startswith("negate,blackdetect")


def test_segments_parsed_and_overlap_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    """The two canned logs resolve to black, white, and a freeze that survives overlap."""
    _stub_probe(monkeypatch)
    segments = analyze_clip("/clips/a.mp4", runtime=FakeRuntime())  # type: ignore[arg-type]
    assert [(s.start, s.end, s.kind) for s in segments] == [
        (0.0, 3.0, SegmentKind.BLACK),
        (8.0, 11.0, SegmentKind.WHITE),
        (16.0, 20.0, SegmentKind.FREEZE),
    ]


def test_ffmpeg_failure_raises_analysis_error_naming_clip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero ffmpeg exit raises AnalysisError that names the offending clip."""
    _stub_probe(monkeypatch)
    with pytest.raises(AnalysisError) as excinfo:
        analyze_clip("/clips/broken.mp4", runtime=FakeRuntime(fail=True))  # type: ignore[arg-type]
    assert "/clips/broken.mp4" in str(excinfo.value)


def test_undecodable_clip_raises_analysis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unprobeable clip raises AnalysisError, never an empty-result fallback."""
    from auto_reel_ng.errors import ProbeError  # noqa: PLC0415

    def fail_probe(_path: Path, *, runtime: object = None) -> object:
        raise ProbeError("no video stream")

    monkeypatch.setattr(runner_module, "probe_media", fail_probe)
    with pytest.raises(AnalysisError) as excinfo:
        analyze_clip("/clips/undecodable.mp4", runtime=FakeRuntime())  # type: ignore[arg-type]
    assert "/clips/undecodable.mp4" in str(excinfo.value)


@pytest.mark.has_ffmpeg
def test_integration_detects_black_span(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    """A generated black-then-motion clip yields exactly one BLACK segment."""
    clip = tmp_path / "blackish.mp4"
    subprocess.run(
        [
            runtime.ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=320x240:r=25:d=3",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=320x240:r=25:d=3",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    segments = analyze_clip(clip, runtime=runtime)

    black = [s for s in segments if s.kind is SegmentKind.BLACK]
    assert len(black) == 1
    assert black[0].start == pytest.approx(0.0, abs=0.5)
    assert black[0].end == pytest.approx(3.0, abs=0.5)
