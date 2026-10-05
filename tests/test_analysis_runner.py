"""Detection-runner tests: two-pass invocation, fail-loud, and a live integration run.

The headless tests drive :func:`analyze_clip` with a fake runtime that returns canned
detector logs (chosen by which filter chain the pass carries) and a stubbed probe, so
the runner's composition is verified without a decode. The integration test, behind
the ``has_ffmpeg`` marker, runs the real two passes against a generated clip.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest

from auto_reel_ng.analysis import runner as runner_module
from auto_reel_ng.analysis.models import SegmentKind
from auto_reel_ng.analysis.runner import ANALYSIS_STALL_TIMEOUT_S, analyze_clip
from auto_reel_ng.errors import (
    AnalysisError,
    FfmpegCancelledError,
    FfmpegError,
    FfmpegStalledError,
)
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


# -- analysis-job: progress and cancel hooks (task 1.2) -------------------------------------


class ProgressRuntime(FakeRuntime):
    """A fake whose ``run_with_progress`` reports two in-pass fractions and returns the log.

    ``cancel_in`` names a pass label (``"pass1"``/``"pass2"``) during which the fake asks
    ``should_cancel`` and raises the engine's cancellation when it answers true, as the real
    runtime does.
    """

    def __init__(self, *, cancel_in: Optional[str] = None) -> None:
        super().__init__()
        self.progress_calls: List[Dict[str, object]] = []
        self._cancel_in = cancel_in

    def run_with_progress(self, args: Sequence[str], **kwargs: Any) -> str:
        self.calls.append(list(args))
        self.progress_calls.append(dict(kwargs))
        vf = list(args)[list(args).index("-vf") + 1]
        label = "pass2" if vf.startswith("negate") else "pass1"
        should_cancel = kwargs.get("should_cancel")
        if self._cancel_in == label and should_cancel is not None and should_cancel():
            raise FfmpegCancelledError("ffmpeg canceled: fake")
        on_progress = kwargs.get("on_progress")
        if on_progress is not None:
            for fraction in (0.25, 0.75, 1.0):
                on_progress(fraction)
        return PASS2_LOG if label == "pass2" else PASS1_LOG


def test_progress_maps_pass_one_to_the_first_half_and_pass_two_to_the_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fractions rise through 0.0-0.5 in pass 1 and 0.5-1.0 in pass 2, ending at 1.0."""
    _stub_probe(monkeypatch, duration=20.0)
    fake = ProgressRuntime()
    fractions: List[float] = []

    analyze_clip("/clips/a.mp4", runtime=fake, on_progress=fractions.append)  # type: ignore[arg-type]

    assert fractions == [0.125, 0.375, 0.5, 0.625, 0.875, 1.0]
    assert all(call["duration"] == 20.0 for call in fake.progress_calls)
    assert all(call["stall_timeout"] == ANALYSIS_STALL_TIMEOUT_S for call in fake.progress_calls)


def test_hooks_do_not_change_the_detection_arguments_or_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With and without hooks, ffmpeg gets the same pass arguments and the segments match."""
    _stub_probe(monkeypatch)
    plain, hooked = FakeRuntime(), ProgressRuntime()

    without = analyze_clip("/clips/a.mp4", runtime=plain)  # type: ignore[arg-type]
    with_hooks = analyze_clip(
        "/clips/a.mp4",
        runtime=hooked,  # type: ignore[arg-type]
        on_progress=lambda _f: None,
        should_cancel=lambda: False,
    )

    assert hooked.calls == plain.calls
    assert with_hooks == without


def test_no_hooks_keeps_the_blocking_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without hooks the runner uses ``run`` exactly as before (inline ``auto-reel analyze``)."""
    _stub_probe(monkeypatch)
    fake = ProgressRuntime()

    analyze_clip("/clips/a.mp4", runtime=fake)  # type: ignore[arg-type]

    assert len(fake.calls) == 2 and fake.progress_calls == []


def test_without_a_duration_no_fraction_is_invented(monkeypatch: pytest.MonkeyPatch) -> None:
    """No probed duration: ffmpeg gets no progress callback and the clip reports 1.0 at the end."""
    _stub_probe(monkeypatch, duration=None)
    fake = ProgressRuntime()
    fractions: List[float] = []

    analyze_clip("/clips/a.mp4", runtime=fake, on_progress=fractions.append)  # type: ignore[arg-type]

    assert fractions == [1.0]
    assert all(call.get("on_progress") is None for call in fake.progress_calls)


def test_cancel_inside_a_pass_is_the_engine_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cancel in pass 1 raises FfmpegCancelledError, not AnalysisError; pass 2 never starts."""
    _stub_probe(monkeypatch)
    fake = ProgressRuntime(cancel_in="pass1")

    with pytest.raises(FfmpegCancelledError) as excinfo:
        analyze_clip(
            "/clips/a.mp4", runtime=fake, should_cancel=lambda: True  # type: ignore[arg-type]
        )

    assert not isinstance(excinfo.value, AnalysisError)
    assert len(fake.calls) == 1


def test_cancel_between_passes_starts_no_second_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cancel that arrives as pass 1 ends is seen before pass 2 is launched."""
    _stub_probe(monkeypatch)
    fake = ProgressRuntime()
    asked: List[int] = []

    def should_cancel() -> bool:
        asked.append(len(fake.calls))
        return len(fake.calls) >= 1  # true once pass 1 has run

    with pytest.raises(FfmpegCancelledError):
        analyze_clip(
            "/clips/a.mp4", runtime=fake, should_cancel=should_cancel  # type: ignore[arg-type]
        )

    assert len(fake.calls) == 1


def test_a_failing_pass_with_hooks_is_still_an_analysis_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero exit or a stall through ``run_with_progress`` is the clip's AnalysisError."""
    _stub_probe(monkeypatch)

    class Stalling(ProgressRuntime):
        def run_with_progress(self, args: Sequence[str], **kwargs: Any) -> str:
            raise FfmpegStalledError("ffmpeg stalled: no progress for 600s")

    with pytest.raises(AnalysisError, match="stalled") as excinfo:
        analyze_clip(
            "/clips/a.mp4", runtime=Stalling(), on_progress=lambda _f: None  # type: ignore[arg-type]
        )
    assert "/clips/a.mp4" in str(excinfo.value)


@pytest.mark.has_ffmpeg
def test_integration_cancel_kills_ffmpeg_within_two_seconds(
    runtime: FfmpegRuntime, tmp_path: Path
) -> None:
    """Cancelling pass 1 of a 60 s clip ends its ffmpeg within 2 s and raises the cancellation."""
    clip = tmp_path / "long.mp4"
    subprocess.run(
        [
            runtime.ffmpeg_path,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=1280x720:r=50:d=60",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
    )
    cancel_at: List[float] = []

    def on_progress(fraction: float) -> None:
        if fraction > 0.0 and not cancel_at:
            cancel_at.append(time.monotonic())

    with pytest.raises(FfmpegCancelledError):
        analyze_clip(
            clip, runtime=runtime, on_progress=on_progress, should_cancel=lambda: bool(cancel_at)
        )
    elapsed = time.monotonic() - cancel_at[0]
    assert cancel_at and elapsed < 2.0, f"cancel took {elapsed:.2f}s"
    assert not _ffmpeg_running_on(clip)


def _ffmpeg_running_on(clip: Path) -> bool:
    """Whether any process's command line names ``clip`` (Linux ``/proc``)."""
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            if str(clip).encode() in cmdline.read_bytes():
                return True
        except OSError:
            continue
    return False
