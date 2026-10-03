"""Real-render orientation tests for ``clip-rotate-engine``.

``rotate`` is an extra clockwise turn on top of the clip's display rotation, applied by the
engine itself on every profile. These tests render real clips and measure the picture: a
synthetic clip with a white left half and a black right half (so the direction of every
turn is unambiguous), and the rotated samples of ``auto-reel-media/samples`` (read-only,
skipped when absent) compared by SSIM with the source turned the same way.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.accel import detect_capabilities, select_profile
from auto_reel_ng.accel.profiles import CPUProfile, VaapiProfile
from auto_reel_ng.accel.profiles.base import AccelProfile
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.probe import probe_media
from auto_reel_ng.reel.document import Metadata
from auto_reel_ng.render import (
    RenderOptions,
    Segment,
    TargetSpec,
    build_normalize_command,
    copy_eligible,
    render_movie,
)

pytestmark = pytest.mark.has_ffmpeg

SAMPLES = Path(__file__).resolve().parents[2] / "auto-reel-media" / "samples"
TURNS = (None, 90, 180, 270)


def _hardware_profile(runtime: FfmpegRuntime) -> VaapiProfile:
    profile = select_profile(detect_capabilities(runtime))
    if not isinstance(profile, VaapiProfile):
        pytest.skip(f"needs a VAAPI profile; this host selected {profile.vendor.value}")
    if "h264" not in profile.capabilities.usable_encoders:
        pytest.skip("no hardware h264 encoder on this host")
    return profile


def _luma(runtime: FfmpegRuntime, video: Path, crop: str) -> float:
    """Mean luma of ``crop`` (``w:h:x:y``) in the first frame of ``video``."""
    result = runtime.run(
        ["-i", str(video), "-frames:v", "1"]
        + ["-vf", f"crop={crop},signalstats,metadata=mode=print:file=-", "-f", "null", "-"]
    )
    match = re.search(r"lavfi\.signalstats\.YAVG=([0-9.]+)", result.stdout)
    assert match, result.stdout
    return float(match.group(1))


def _make_half_clip(runtime: FfmpegRuntime, tmp_path: Path, display_rotation: int) -> Path:
    """1280x720, 30 fps, AAC 48 kHz stereo: white left half, black right half, with a matrix.

    ``display_rotation`` is ffmpeg's ``-display_rotation``, counter-clockwise degrees.
    """
    stored = tmp_path / "stored.mp4"
    runtime.run(
        ["-y", "-f", "lavfi", "-i", "color=white:size=1280x720:rate=30:duration=1"]
        + ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1"]
        + ["-vf", "drawbox=x=640:y=0:w=640:h=720:color=black:t=fill"]
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-shortest"]
        + [str(stored)]
    )
    clip = tmp_path / "phone.mp4"
    runtime.run(
        ["-y", "-display_rotation:v:0", str(display_rotation), "-i", str(stored)]
        + ["-map", "0", "-c", "copy", str(clip)]
    )
    return clip


def _render_movie(
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    clip: Path,
    tmp_path: Path,
    rotate: Optional[int],
) -> Path:
    facts = {clip.name: probe_media(clip, runtime=runtime)}
    plan = RenderPlan(
        metadata=Metadata(),
        look={"target_resolution": [1280, 720], "video_codec": "h264"},
        chapters=(
            ResolvedChapter(name="", clips=(ResolvedClip(identity=clip.name, rotate=rotate),)),
        ),
    )
    options = RenderOptions(
        event_dir=clip.parent,
        output_dir=tmp_path / f"out-{rotate}",
        clip_facts=facts,
        runtime=runtime,
    )
    result = render_movie(plan, profile, options)
    return result.output_path


# Where the white half of the upright picture lands, per extra clockwise turn. The clip is
# stored white-left and displayed turned 90 degrees counter-clockwise, so the player shows a
# portrait picture with white at the bottom; each further clockwise quarter turn moves it
# bottom -> left -> top -> right.
_WHITE_AT = {None: "bottom", 90: "left", 180: "top", 270: "right"}
# Sample regions (w:h:x:y) inside the 1280x720 canvas: a portrait picture is pillarboxed
# around x=437..842, a landscape one fills the canvas.
_REGIONS = {
    "bottom": "100:100:590:560",
    "top": "100:100:590:60",
    "left": "100:100:200:310",
    "right": "100:100:980:310",
}
_OPPOSITE = {"bottom": "top", "top": "bottom", "left": "right", "right": "left"}


@pytest.mark.parametrize("rotate", TURNS)
def test_rotate_turns_the_displayed_picture_further_clockwise(
    runtime: FfmpegRuntime, tmp_path: Path, rotate: Optional[int]
) -> None:
    clip = _make_half_clip(runtime, tmp_path, display_rotation=90)
    assert probe_media(clip, runtime=runtime).rotation == 90  # the matrix is there

    output = _render_movie(runtime, CPUProfile(), clip, tmp_path, rotate)

    white = _WHITE_AT[rotate]
    assert _luma(runtime, output, _REGIONS[white]) > 200
    assert _luma(runtime, output, _REGIONS[_OPPOSITE[white]]) < 40
    meta = probe_media(output, runtime=runtime)
    assert (meta.width, meta.height) == (1280, 720)
    assert meta.rotation in (None, 0)  # the output carries no display matrix of its own


@pytest.mark.parametrize("rotate", [None, 360, 0])
def test_a_display_rotated_clip_of_the_target_size_is_normalized_not_copied(
    runtime: FfmpegRuntime, tmp_path: Path, rotate: Optional[int]
) -> None:
    # The measured defect: this clip matches the target in every stored parameter, took the
    # stream-copy path, and the finished movie reported rotation=90.
    clip = _make_half_clip(runtime, tmp_path, display_rotation=90)

    output = _render_movie(runtime, CPUProfile(), clip, tmp_path, rotate)

    assert probe_media(output, runtime=runtime).rotation in (None, 0)
    assert _luma(runtime, output, _REGIONS["bottom"]) > 200  # upright, not the stored picture


def test_a_clip_without_a_matrix_is_still_copied_when_it_conforms(
    runtime: FfmpegRuntime, tmp_path: Path
) -> None:
    clip = tmp_path / "plain.mp4"
    runtime.run(
        ["-y", "-f", "lavfi", "-i", "color=white:size=1280x720:rate=30:duration=1"]
        + ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1"]
        + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-shortest"]
        + [str(clip)]
    )
    facts = probe_media(clip, runtime=runtime)
    target = TargetSpec(
        width=1280,
        height=720,
        fps=facts.fps,
        video_codec="h264",
        video_encoder="libx264",
        pix_fmt="yuv420p",
        sample_aspect_ratio="1:1",
        fill_color="black",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
    )
    segment = Segment(chapter="", identity=clip.name, source_path=clip, is_full_clip=True)
    assert copy_eligible(segment, facts, target) is True


# --------------------------------------------------------------------------- #
# The rotated samples: first frame against the source turned the same way       #
# --------------------------------------------------------------------------- #

_SAMPLES = (
    "h264-720p-rotate90-aac.mp4",
    "hevc-mov-rotate90-aac.mov",
    "h264-portrait-1080x1920-aac.mp4",
)
_CANVAS = (640, 360)
_TRANSPOSE = {0: "null", 90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}


def _ssim(runtime: FfmpegRuntime, first: Path, second: Path) -> float:
    result = runtime.run(["-i", str(first), "-i", str(second), "-lavfi", "ssim", "-f", "null", "-"])
    match = re.search(r"All:([0-9.]+)", result.stderr)
    assert match, result.stderr
    return float(match.group(1))


def _fit(extra: str) -> str:
    width, height = _CANVAS
    return (
        f"{extra},scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=rgb24"
    )


def _reference_frame(runtime: FfmpegRuntime, sample: Path, turn: int, out: Path) -> Path:
    """The source frame at 1 s, autorotated by ffmpeg, turned ``turn`` further, fitted."""
    runtime.run(
        ["-y", "-ss", "1", "-i", str(sample), "-frames:v", "1"]
        + ["-vf", _fit(_TRANSPOSE[turn]), str(out)]
    )
    return out


def _normalized_frame(
    runtime: FfmpegRuntime, profile: AccelProfile, sample: Path, rotate: Optional[int], out: Path
) -> Path:
    facts = probe_media(sample, runtime=runtime)
    encoder = (
        profile.capabilities.usable_encoders["h264"]
        if hasattr(profile, "capabilities")
        else "libx264"
    )
    target = TargetSpec(
        width=_CANVAS[0],
        height=_CANVAS[1],
        fps=30.0,
        video_codec="h264",
        video_encoder=encoder,
        pix_fmt="yuv420p",
        sample_aspect_ratio="1:1",
        fill_color="black",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channels=2,
    )
    segment = Segment(
        chapter="",
        identity=sample.name,
        source_path=sample,
        start=1.0,
        end=2.0,
        rotate=rotate,
    )
    movie = out.with_suffix(".mp4")
    command = build_normalize_command(segment, facts, target, profile, movie)
    runtime.run(list(command.args))
    runtime.run(["-y", "-i", str(movie), "-frames:v", "1", "-vf", "format=rgb24", str(out)])
    return out


def _check_sample(
    runtime: FfmpegRuntime, profile: AccelProfile, name: str, rotate: Optional[int], tmp_path: Path
) -> None:
    sample = SAMPLES / name
    if not sample.exists():
        pytest.skip(f"{name} is not in the sample library")
    frame = _normalized_frame(runtime, profile, sample, rotate, tmp_path / "frame.png")
    scores = {
        turn: _ssim(
            runtime, frame, _reference_frame(runtime, sample, turn, tmp_path / f"r{turn}.png")
        )
        for turn in _TRANSPOSE
    }
    expected = (rotate or 0) % 360
    best = max(scores, key=lambda turn: scores[turn])
    assert best == expected, scores
    assert scores[expected] > 0.85, scores


@pytest.mark.parametrize("rotate", TURNS)
@pytest.mark.parametrize("name", _SAMPLES)
def test_samples_render_upright_plus_rotate_on_the_cpu_profile(
    runtime: FfmpegRuntime, tmp_path: Path, name: str, rotate: Optional[int]
) -> None:
    _check_sample(runtime, CPUProfile(), name, rotate, tmp_path)


@pytest.mark.gpu
@pytest.mark.parametrize("rotate", TURNS)
@pytest.mark.parametrize("name", _SAMPLES)
def test_samples_render_upright_plus_rotate_on_the_vaapi_profile(
    runtime: FfmpegRuntime, tmp_path: Path, name: str, rotate: Optional[int]
) -> None:
    # The same answer as the CPU profile; before the engine applied the display rotation
    # itself, a phone clip rendered sideways here (extra turn 270 with rotate unset).
    _check_sample(runtime, _hardware_profile(runtime), name, rotate, tmp_path)
