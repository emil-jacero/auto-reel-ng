"""Real renders of the Provklipp case (``vaapi-sar-uniform``).

A 1080p25 H.264 clip (SAR 1:1) and a HEVC clip with no SAR, a display rotation of 90 and
``rotate: 270`` (a net turn of 0) in one chapter. On VAAPI the second segment used to probe
``sample_aspect_ratio=N/A`` beside ``1:1`` and the render failed with "segments could not be
made copy-uniform". The samples of ``auto-reel-media/samples`` are read-only: they are
symlinked into a tmp library, never written; the test skips when they are absent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Sequence

import pytest
from test_render_rotate import SAMPLES, _hardware_profile

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.accel.profiles.base import AccelProfile
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.probe import probe_media
from auto_reel_ng.reel.document import Metadata
from auto_reel_ng.render import RenderOptions
from auto_reel_ng.render import orchestrator as orch
from auto_reel_ng.render import render_movie

pytestmark = pytest.mark.has_ffmpeg

_PLAIN = "h264-1080p25-aac.mp4"
_NO_SAR = "hevc-mov-rotate90-aac.mov"


def _raw_sar(runtime: FfmpegRuntime, path: Path) -> Optional[str]:
    """The video stream's ``sample_aspect_ratio`` exactly as ffprobe reports it."""
    result = runtime.run_ffprobe(
        ["-v", "error", "-select_streams", "v:0", "-show_streams", "-of", "json", str(path)]
    )
    value = json.loads(result.stdout)["streams"][0].get("sample_aspect_ratio")
    return None if value is None else str(value)


def _library(tmp_path: Path) -> Path:
    event = tmp_path / "library" / "2025" / "2025-01-15 - Provklipp"
    event.mkdir(parents=True)
    for name in (_PLAIN, _NO_SAR):
        sample = SAMPLES / name
        if not sample.exists():
            pytest.skip(f"{name} is not in the sample library")
        (event / name).symlink_to(sample)
    return event


def _render(
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, list[dict[str, Optional[str]]]]:
    event = _library(tmp_path)
    assert _raw_sar(runtime, event / _NO_SAR) in (None, "N/A", "0:1")  # the case is real
    facts = {name: probe_media(event / name, runtime=runtime) for name in (_PLAIN, _NO_SAR)}
    plan = RenderPlan(
        metadata=Metadata(),
        look={"target_resolution": [1920, 1080], "video_codec": "h264"},
        chapters=(
            ResolvedChapter(
                name="",
                clips=(ResolvedClip(identity=_PLAIN), ResolvedClip(identity=_NO_SAR, rotate=270)),
            ),
        ),
    )
    # Record every intermediate's raw SAR at each pre-flight, while the segments exist.
    seen: list[dict[str, Optional[str]]] = []
    real = orch.is_copy_uniform

    def _spy(rt: FfmpegRuntime, paths: Sequence[Path]) -> bool:
        seen.append({Path(p).name: _raw_sar(runtime, Path(p)) for p in paths})
        return real(rt, paths)

    monkeypatch.setattr(orch, "is_copy_uniform", _spy)
    options = RenderOptions(
        event_dir=event,
        output_dir=tmp_path / "out",
        clip_facts=facts,
        runtime=runtime,
        overwrite=True,
    )
    result = render_movie(plan, profile, options)
    return result.output_path, seen


def _assert_square_throughout(
    runtime: FfmpegRuntime, movie: Path, seen: list[dict[str, Optional[str]]]
) -> None:
    assert seen, "the concat pre-flight never ran"
    for snapshot in seen:
        assert len(snapshot) == 2, snapshot
        assert set(snapshot.values()) == {"1:1"}, snapshot
    assert _raw_sar(runtime, movie) == "1:1"


def test_the_provklipp_case_renders_with_square_pixels_on_the_cpu(
    runtime: FfmpegRuntime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    movie, seen = _render(runtime, CPUProfile(), tmp_path, monkeypatch)
    _assert_square_throughout(runtime, movie, seen)


@pytest.mark.gpu
def test_the_provklipp_case_renders_with_square_pixels_on_vaapi(
    runtime: FfmpegRuntime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    movie, seen = _render(runtime, _hardware_profile(runtime), tmp_path, monkeypatch)
    _assert_square_throughout(runtime, movie, seen)
