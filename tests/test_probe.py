"""Tests for probe_media/probe_many using synthetic lavfi clips (task 5.3)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pytest

from auto_reel_ng.errors import ProbeError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.probe.media import probe_many, probe_media

MakeClip = Callable[..., Path]


def test_valid_clip_yields_complete_metadata(make_clip: MakeClip, runtime: FfmpegRuntime) -> None:
    """A valid clip produces a fully populated metadata object."""
    clip = make_clip(width=640, height=480, fps=30, duration=1.0)
    meta = probe_media(clip, runtime=runtime)
    assert meta.width == 640
    assert meta.height == 480
    assert meta.fps == pytest.approx(30.0, abs=0.5)
    assert meta.duration == pytest.approx(1.0, abs=0.2)
    assert meta.video_codec == "h264"
    assert meta.pix_fmt == "yuv420p"
    assert meta.has_audio is True


def test_exactly_one_ffprobe_per_file(
    make_clip: MakeClip,
    runtime: FfmpegRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extracting metadata invokes ffprobe exactly once for the file."""
    clip = make_clip()
    calls: list[Any] = []
    original = runtime.run_ffprobe

    def spy(args: Any) -> Any:
        calls.append(args)
        return original(args)

    monkeypatch.setattr(runtime, "run_ffprobe", spy)
    probe_media(clip, runtime=runtime)
    assert len(calls) == 1


def test_missing_file_raises(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    with pytest.raises(ProbeError):
        probe_media(tmp_path / "nope.mp4", runtime=runtime)


def test_empty_file_raises(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    empty = tmp_path / "empty.mp4"
    empty.touch()
    with pytest.raises(ProbeError) as excinfo:
        probe_media(empty, runtime=runtime)
    assert "empty" in str(excinfo.value).lower()


def test_garbage_file_raises(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.mp4"
    garbage.write_bytes(b"this is not a media file at all")
    with pytest.raises(ProbeError):
        probe_media(garbage, runtime=runtime)


def test_no_video_stream_raises(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    """An audio-only file has no video stream and must raise."""
    audio_only = tmp_path / "audio.m4a"
    runtime.run(
        [
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:a",
            "aac",
            str(audio_only),
        ]
    )
    with pytest.raises(ProbeError):
        probe_media(audio_only, runtime=runtime)


def test_rotated_clip_reports_90(make_clip: MakeClip, runtime: FfmpegRuntime) -> None:
    clip = make_clip(rotate=90)
    meta = probe_media(clip, runtime=runtime)
    assert meta.rotation == 90


def test_non_square_sar_reported(make_clip: MakeClip, runtime: FfmpegRuntime) -> None:
    clip = make_clip(setsar="4/3")
    meta = probe_media(clip, runtime=runtime)
    assert meta.sample_aspect_ratio == "4:3"
    assert meta.display_aspect_ratio is not None


def test_pq_clip_flagged_hdr(make_clip: MakeClip, runtime: FfmpegRuntime) -> None:
    clip = make_clip(color_trc="smpte2084")
    meta = probe_media(clip, runtime=runtime)
    assert meta.is_hdr is True
    assert meta.color_transfer == "smpte2084"


def test_bt709_clip_not_hdr(make_clip: MakeClip, runtime: FfmpegRuntime) -> None:
    clip = make_clip(color_trc="bt709")
    meta = probe_media(clip, runtime=runtime)
    assert meta.is_hdr is False


def test_video_only_clip_reports_no_audio(make_clip: MakeClip, runtime: FfmpegRuntime) -> None:
    clip = make_clip(audio=False)
    meta = probe_media(clip, runtime=runtime)
    assert meta.has_audio is False
    assert meta.audio is None


def test_creation_time_from_tag_without_exiftool(
    make_clip: MakeClip,
    runtime: FfmpegRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creation time comes from the ffprobe tag and no exiftool process is spawned."""
    import auto_reel_ng.probe.media as media_module

    # Build the clip first, then guard the exiftool seam: with use_exiftool off and a
    # creation-time tag present, this fallback must never be reached.
    clip = make_clip(creation_time="2024-06-01T12:00:00.000000Z")

    def fail_exiftool(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("exiftool must not be spawned when a tag is present")

    monkeypatch.setattr(media_module, "_exiftool_creation_time", fail_exiftool)

    meta = probe_media(clip, runtime=runtime)
    assert isinstance(meta.creation_time, datetime)
    assert meta.creation_time.year == 2024
    assert meta.creation_time.month == 6
    assert meta.creation_time.day == 1


def test_batch_continues_past_bad_file(
    make_clip: MakeClip,
    runtime: FfmpegRuntime,
    tmp_path: Path,
) -> None:
    """probe_many skips and reports a bad file while probing the rest."""
    good1 = make_clip(name="good1.mp4")
    good2 = make_clip(name="good2.mp4")
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"garbage")

    results, failures = probe_many([good1, bad, good2], runtime=runtime)
    assert len(results) == 2
    assert len(failures) == 1
    assert failures[0][0] == bad
    assert isinstance(failures[0][1], ProbeError)


def test_implausible_fps_raises(
    make_clip: MakeClip,
    runtime: FfmpegRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero/unparseable frame-rate fields raise rather than assume a default."""
    import auto_reel_ng.probe.media as media_module

    clip = make_clip()
    real_run = runtime.run_ffprobe

    def patched(args: Any) -> Any:
        result = real_run(args)
        import json

        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                stream["avg_frame_rate"] = "0/0"
                stream["r_frame_rate"] = "0/0"
        result.stdout = json.dumps(data)
        return result

    monkeypatch.setattr(runtime, "run_ffprobe", patched)
    with pytest.raises(ProbeError):
        probe_media(clip, runtime=runtime)
    # silence unused import warning
    assert media_module is not None
