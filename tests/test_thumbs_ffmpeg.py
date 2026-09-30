"""Real-ffmpeg tests for clip thumbnails: fit, rotation, SAR, no-frame failures (D-11).

Every test uses the real runtime and generated clips (``make_clip``), so they skip
when no ffmpeg >= 7.1 is available. Output sizes are read back with ffprobe.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence

import pytest

from auto_reel_ng.errors import ThumbnailError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.probe import probe_media
from auto_reel_ng.thumbs import thumbnail_for, thumbnail_path

pytestmark = pytest.mark.has_ffmpeg


def _size(runtime: FfmpegRuntime, jpg: Path) -> str:
    """``width,height`` of an image, as ffprobe reports it."""
    result = runtime.run_ffprobe(
        ["-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(jpg)]
    )
    return result.stdout.strip()


def _cache_files(cache_dir: Path, pattern: str) -> List[Path]:
    return sorted(cache_dir.glob(pattern)) if cache_dir.exists() else []


def _spy_on_run(runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch) -> List[List[str]]:
    """Record every ffmpeg run of the (session-scoped) runtime for this test only."""
    runs: List[List[str]] = []
    real_run = runtime.run

    def spy(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        runs.append(list(args))
        return real_run(args)

    monkeypatch.setattr(runtime, "run", spy)
    return runs


@pytest.mark.parametrize(
    ("width", "height", "setsar", "rotate", "fps", "expected"),
    [
        pytest.param(1920, 1080, None, None, 30, "320,180", id="1080p-fills-the-box"),
        pytest.param(1080, 1920, None, None, 30, "101,180", id="coded-portrait"),
        pytest.param(1920, 1080, None, 90, 30, "101,180", id="display-rotation-90"),
        pytest.param(720, 576, "64/45", None, 25, "320,180", id="anamorphic-not-squashed"),
        pytest.param(720, 576, "64/45", 90, 25, "101,180", id="anamorphic-rotated"),
        pytest.param(3840, 2160, None, None, 10, "320,180", id="4k-scaled-down"),
    ],
)
def test_the_thumbnail_fits_the_box_as_displayed(
    tmp_path: Path,
    make_clip,
    runtime: FfmpegRuntime,
    width: int,
    height: int,
    setsar: Optional[str],
    rotate: Optional[int],
    fps: int,
    expected: str,
) -> None:
    clip = make_clip("clip.mp4", width=width, height=height, fps=fps, setsar=setsar, rotate=rotate)
    jpg = thumbnail_for(clip, position=0.25, cache_dir=tmp_path / "cache", runtime=runtime)
    assert jpg.suffix == ".jpg"
    assert _size(runtime, jpg) == expected


def test_a_zero_byte_clip_has_no_thumbnail(tmp_path: Path, runtime: FfmpegRuntime) -> None:
    clip = tmp_path / "trasig.mp4"
    clip.write_bytes(b"")
    cache_dir = tmp_path / "cache"
    with pytest.raises(ThumbnailError, match="File is empty") as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    assert str(exc.value).startswith(f"{clip}: ")
    assert exc.value.reason == "File is empty (zero bytes)"  # the path is not repeated
    assert _cache_files(cache_dir, "*.jpg") == []


def test_a_corrupt_clip_with_a_non_utf8_name_is_a_thumbnail_error(
    tmp_path: Path, runtime: FfmpegRuntime
) -> None:
    # ffprobe's stderr echoes the name's raw bytes, which the runtime cannot decode.
    clip = tmp_path / os.fsdecode(b"caf\xe9.mp4")
    clip.write_bytes(b"this is not a video " * 50)
    cache_dir = tmp_path / "cache"
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    assert exc.value.reason.startswith("ffprobe's output could not be decoded")
    assert _cache_files(cache_dir, "*") == []


def test_a_truncated_copy_past_its_cut_has_no_thumbnail(
    tmp_path: Path, runtime: FfmpegRuntime
) -> None:
    full = tmp_path / "full.mp4"
    runtime.run(
        [
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=25:duration=4",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(full),
        ]
    )
    # An interrupted copy: the index (moov, at the front) survives, most media does not.
    data = full.read_bytes()
    clip = tmp_path / "cut.mp4"
    clip.write_bytes(data[: len(data) // 4])
    cache_dir = tmp_path / "cache"

    with pytest.raises(ThumbnailError, match="no frame extracted") as exc:
        thumbnail_for(clip, position=0.75, cache_dir=cache_dir, runtime=runtime)

    assert str(exc.value).startswith(f"{clip}: no frame extracted at 3.000s of 4.000s")
    assert _cache_files(cache_dir, "*.jpg") == []
    assert _cache_files(cache_dir, ".*.tmp") == []


def test_a_one_frame_clip_has_no_thumbnail_and_no_other_time_is_tried(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = make_clip("one.mp4", fps=30, duration=1 / 30, audio=False)
    duration = probe_media(clip, runtime=runtime).duration
    cache_dir = tmp_path / "cache"
    runs = _spy_on_run(runtime, monkeypatch)

    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    assert f"no frame extracted at {0.25 * duration:.3f}s of {duration:.3f}s" in str(exc.value)
    assert len(runs) == 1  # D-11: a single attempt
    assert _cache_files(cache_dir, "*.jpg") == []
    assert _cache_files(cache_dir, ".*.tmp") == []


def test_a_percent_sign_in_the_cache_path_is_literal(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime
) -> None:
    clip = make_clip("clip.mp4", width=640, height=360)
    cache_dir = tmp_path / "p%d"
    jpg = thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    assert jpg == thumbnail_path(clip, position=0.25, cache_dir=cache_dir)
    assert jpg.parent == cache_dir and jpg.is_file()
    assert not (tmp_path / "p1").exists()


def test_the_source_clip_is_only_read_and_a_second_call_is_cached(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = make_clip("clip.mp4", width=640, height=360)
    before = (clip.read_bytes(), clip.stat().st_mtime_ns)
    cache_dir = tmp_path / "cache"

    first = thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    assert (clip.read_bytes(), clip.stat().st_mtime_ns) == before

    runs = _spy_on_run(runtime, monkeypatch)
    second = thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    assert second == first
    assert runs == []
