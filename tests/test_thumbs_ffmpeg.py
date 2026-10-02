"""Real-ffmpeg tests for clip thumbnails: fit, rotation, SAR, no-frame failures (D-11).

Every test uses the real runtime and generated clips (``make_clip``), so they skip
when no ffmpeg >= 7.1 is available. Output sizes are read back with ffprobe.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Sequence

import pytest

from auto_reel_ng.errors import FfmpegError, ThumbnailError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.probe import probe_media
from auto_reel_ng.thumbs import (
    recorded_duration,
    recorded_failure,
)
from auto_reel_ng.thumbs import thumbnail as thumbnail_module
from auto_reel_ng.thumbs import thumbnail_args, thumbnail_for, thumbnail_path

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


def test_a_corrupt_clip_with_a_non_utf8_name_reports_the_probes_failure(
    tmp_path: Path, runtime: FfmpegRuntime
) -> None:
    # ffprobe's stderr echoes the name's raw bytes; the runtime shows them as escapes.
    clip = tmp_path / os.fsdecode(b"caf\xe9.mp4")
    clip.write_bytes(b"this is not a video " * 50)
    cache_dir = tmp_path / "cache"
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    assert exc.value.reason.startswith("ffprobe could not read: Command exited 1: ")
    assert "Invalid data found when processing input" in exc.value.reason
    assert "could not be decoded" not in exc.value.reason
    assert [f.suffix for f in _cache_files(cache_dir, "*")] == [".fail"]  # no .jpg, no duration


#: A stand-in ffmpeg/ffprobe: answers ``-version``, records its pid, then hangs.
_HANGING_BINARY = """#!{python}
import os, sys, time
if "-version" in sys.argv:
    print("ffmpeg version 8.1 fake")
    sys.exit(0)
with open({pidfile!r}, "a") as handle:
    handle.write(str(os.getpid()) + "\\n")
time.sleep(60)
"""


def _hanging(tmp_path: Path) -> Path:
    path = tmp_path / "hang"
    path.write_text(
        _HANGING_BINARY.format(python=sys.executable, pidfile=str(tmp_path / "pids")),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _pids(tmp_path: Path) -> List[int]:
    pidfile = tmp_path / "pids"
    return [int(line) for line in pidfile.read_text().split()] if pidfile.exists() else []


def _assert_none_alive(pids: List[int]) -> None:
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_a_probe_that_hangs_times_out_without_running_ffmpeg(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = make_clip("clip.mp4")
    hang = _hanging(tmp_path)
    hung = FfmpegRuntime(ffmpeg_path=str(hang), ffprobe_path=str(hang))  # one binary, one pid
    monkeypatch.setattr(thumbnail_module, "THUMBNAIL_TIMEOUT", 0.5)
    cache_dir = tmp_path / "cache"

    started = time.monotonic()
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=hung)

    assert time.monotonic() - started < 15
    assert exc.value.clip == str(clip)
    assert "timed out after 0.5s" in exc.value.reason
    assert len(_pids(tmp_path)) == 1  # only the probe ran: ffmpeg never did
    _assert_none_alive(_pids(tmp_path))
    assert _cache_files(cache_dir, "*.jpg") == []
    assert _cache_files(cache_dir, ".*") == []


def test_an_extraction_that_hangs_times_out_naming_the_time(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = make_clip("clip.mp4", duration=4)
    hang = _hanging(tmp_path)
    hung = FfmpegRuntime(ffmpeg_path=str(hang), ffprobe_path=runtime.ffprobe_path)
    monkeypatch.setattr(thumbnail_module, "THUMBNAIL_TIMEOUT", 0.5)
    cache_dir = tmp_path / "cache"

    started = time.monotonic()
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=hung)

    assert time.monotonic() - started < 15
    assert exc.value.reason.startswith("ffmpeg timed out extracting the frame at 1.000s: ")
    assert "timed out after 0.5s" in exc.value.reason
    assert len(_pids(tmp_path)) == 1  # one attempt, no other timestamp
    _assert_none_alive(_pids(tmp_path))
    assert [f.suffix for f in _cache_files(cache_dir, "*")] == [".fail", ".json"]  # no .jpg


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


# --------------------------------------------------------------------------- #
# HDR tone-mapping and a full disk, against the real ffmpeg
# --------------------------------------------------------------------------- #


def _hlg_clip(runtime: FfmpegRuntime, path: Path) -> Path:
    """A 640x360 clip fully tagged BT.2020 / HLG / bt2020nc, or skip when it cannot be made."""
    try:
        subprocess.run(
            [
                runtime.ffmpeg_path,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=640x360:rate=30:duration=1",
                "-vf",
                "setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        pytest.skip(f"cannot encode a tagged HLG clip: {exc}")
    return path


def test_an_hlg_clip_is_tone_mapped_into_a_320x180_jpeg(
    tmp_path: Path, runtime: FfmpegRuntime
) -> None:
    clip = _hlg_clip(runtime, tmp_path / "hlg.mp4")
    assert probe_media(clip, runtime=runtime).is_hdr
    jpg = thumbnail_for(clip, position=0.25, cache_dir=tmp_path / "cache", runtime=runtime)
    assert _size(runtime, jpg) == "320,180"

    plain = tmp_path / "plain.jpg"
    runtime.run(thumbnail_args(clip.resolve(), at=0.25, output=plain, hdr=False))
    assert plain.read_bytes() != jpg.read_bytes()  # the plain chain range-clips the HDR signal


def test_a_pq_clip_tagged_only_with_a_transfer_has_no_thumbnail(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime
) -> None:
    clip = make_clip("pq.mp4", color_trc="smpte2084")
    cache_dir = tmp_path / "cache"
    with pytest.raises(ThumbnailError) as exc:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    assert str(exc.value).startswith(f"{clip}: no frame extracted at 0.250s of ")
    assert _cache_files(cache_dir, "*.jpg") == []
    assert _cache_files(cache_dir, ".*.tmp") == []


def test_an_sdr_clip_still_has_its_thumbnail(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime
) -> None:
    clip = make_clip("sdr.mp4", width=640, height=360)
    jpg = thumbnail_for(clip, position=0.25, cache_dir=tmp_path / "cache", runtime=runtime)
    assert _size(runtime, jpg) == "320,180"


@pytest.mark.skipif(not Path("/dev/full").exists(), reason="no /dev/full")
def test_the_stderr_of_a_real_full_disk_is_classified_as_one(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime
) -> None:
    clip = make_clip("clip.mp4")
    with pytest.raises(FfmpegError) as exc:
        runtime.run(thumbnail_args(clip, at=0.25, output=Path("/dev/full")))
    phrase = thumbnail_module._full_disk_phrase(exc.value)  # pylint: disable=protected-access
    assert phrase is not None


def _count_probes(monkeypatch: pytest.MonkeyPatch) -> List[Path]:
    """Record every ``probe_media`` call the thumbnail path makes for this test only."""
    probed: List[Path] = []
    real_probe = thumbnail_module.probe_media

    def spy(path: Path, **kwargs: object) -> object:
        probed.append(Path(path))
        return real_probe(path, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(thumbnail_module, "probe_media", spy)
    return probed


def test_a_generated_clip_records_the_duration_the_probe_reports(
    tmp_path: Path, make_clip, runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = make_clip("clip.mp4", width=640, height=360, duration=1.0)
    cache_dir = tmp_path / "cache"
    probed = _count_probes(monkeypatch)
    runs = _spy_on_run(runtime, monkeypatch)

    jpg = thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    expected = probe_media(clip, runtime=runtime).duration
    assert expected > 0
    assert json.loads(jpg.with_suffix(".json").read_text()) == {"duration": expected}
    assert recorded_duration(jpg) == expected
    assert len(probed) == 1 and len(runs) == 1  # reading the duration ran nothing

    assert thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime) == jpg
    assert len(probed) == 1 and len(runs) == 1  # a cache hit


def test_a_clip_that_fails_is_remembered_and_not_probed_again(
    tmp_path: Path, runtime: FfmpegRuntime, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = tmp_path / "random.mp4"
    clip.write_bytes(os.urandom(4096))
    cache_dir = tmp_path / "cache"
    probed = _count_probes(monkeypatch)
    runs = _spy_on_run(runtime, monkeypatch)

    with pytest.raises(ThumbnailError) as first:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)
    marker = thumbnail_path(clip, position=0.25, cache_dir=cache_dir).with_suffix(".fail")
    assert json.loads(marker.read_text()) == {"reason": first.value.reason}
    assert len(probed) == 1

    with pytest.raises(ThumbnailError) as second:
        thumbnail_for(clip, position=0.25, cache_dir=cache_dir, runtime=runtime)

    assert second.value.reason == first.value.reason
    assert str(second.value) == str(first.value)
    assert len(probed) == 1 and runs == []  # neither ffprobe nor ffmpeg ran again
    target = thumbnail_path(clip, position=0.25, cache_dir=cache_dir)
    assert isinstance(recorded_failure(clip, target), ThumbnailError)
