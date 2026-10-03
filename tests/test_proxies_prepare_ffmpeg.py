"""Real-ffmpeg tests for ``prepare_clip``: progress to one on a synthesized clip, and a cancel
in the middle of the encode that ends the process quickly and leaves the cache as it was.

Every test needs a real ffmpeg >= 7.1 (``has_ffmpeg``) and uses the CPU profile.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, List

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.errors import FfmpegCancelledError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.proxies import ProxySettings, lookup_filmstrip, lookup_proxy, prepare_clip

pytestmark = pytest.mark.has_ffmpeg

MakeClip = Callable[..., Path]


def listing(root: Path) -> List[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")) if root.exists() else []


def test_progress_rises_to_one_only_after_the_filmstrip(
    runtime: FfmpegRuntime, make_clip: MakeClip, tmp_path: Path
) -> None:
    clip = make_clip("c.mp4", width=640, height=360, fps=25, duration=4.0)
    settings = ProxySettings(tmp_path / "cache")
    seen: List[float] = []

    prepared = prepare_clip(
        clip, settings=settings, runtime=runtime, profile=CPUProfile(), on_progress=seen.append
    )

    assert seen[-1] == 1.0 and seen.count(1.0) == 1
    assert seen == sorted(seen) and len(seen) >= 2
    assert prepared.filmstrip.path.is_file()
    assert lookup_filmstrip(prepared.entry) is not None
    # Everything but the last report was made before the filmstrip existed.
    assert all(fraction < 1.0 for fraction in seen[:-1])


def test_a_prepared_clip_reports_one_at_once_without_a_process(
    runtime: FfmpegRuntime, make_clip: MakeClip, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = make_clip("c.mp4", width=320, height=240, fps=25, duration=2.0)
    settings = ProxySettings(tmp_path / "cache")
    prepare_clip(clip, settings=settings, runtime=runtime, profile=CPUProfile())

    def no_process(*args: object, **kwargs: object) -> None:
        raise AssertionError("a process started for a prepared clip")

    for name in ("run_with_progress", "run_ffprobe", "run_ffmpeg"):
        if hasattr(FfmpegRuntime, name):
            monkeypatch.setattr(FfmpegRuntime, name, no_process)
    seen: List[float] = []

    prepare_clip(
        clip, settings=settings, runtime=runtime, profile=CPUProfile(), on_progress=seen.append
    )

    assert seen == [1.0]


def test_a_cancel_mid_encode_ends_ffmpeg_quickly_and_leaves_the_cache_unchanged(
    runtime: FfmpegRuntime, make_clip: MakeClip, tmp_path: Path
) -> None:
    clip = make_clip("long.mp4", width=1920, height=1080, fps=50, duration=40.0)
    settings = ProxySettings(tmp_path / "cache")
    settings.cache_dir.mkdir()
    before = listing(settings.cache_dir)
    flagged_at: List[float] = []
    progressed: List[float] = []

    def on_progress(fraction: float) -> None:
        progressed.append(fraction)

    def should_cancel() -> bool:
        if progressed and not flagged_at:
            flagged_at.append(time.monotonic())
        return bool(flagged_at)

    with pytest.raises(FfmpegCancelledError):
        prepare_clip(
            clip,
            settings=settings,
            runtime=runtime,
            profile=CPUProfile(),
            on_progress=on_progress,
            should_cancel=should_cancel,
        )

    assert flagged_at, "the encode finished before it could be canceled; the clip is too short"
    assert time.monotonic() - flagged_at[0] < 2.5
    assert 1.0 not in progressed
    assert listing(settings.cache_dir) == before
    assert lookup_proxy(clip, settings=settings) is None


def test_a_sub_second_clip_gets_a_proxy_and_a_one_tile_filmstrip(
    runtime: FfmpegRuntime, make_clip: MakeClip, tmp_path: Path
) -> None:
    clip = make_clip("short.mp4", width=640, height=360, fps=25, duration=0.48)
    settings = ProxySettings(tmp_path / "cache")
    seen: List[float] = []

    prepared = prepare_clip(
        clip, settings=settings, runtime=runtime, profile=CPUProfile(), on_progress=seen.append
    )

    assert prepared.filmstrip.tiles == 1
    assert lookup_proxy(clip, settings=settings) is not None
    assert seen[-1] == 1.0
