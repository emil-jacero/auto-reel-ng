"""Tests for ``facts.json`` and the post-encode verification, against canned ffprobe output.

A fake runtime answers ``run_ffprobe`` with JSON, so every check is exercised without ffmpeg;
the real-encode tests are in ``test_proxies_ffmpeg.py``.
"""

from __future__ import annotations

import copy
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

import pytest

from auto_reel_ng.errors import FfmpegError, ProxyError
from auto_reel_ng.probe.metadata import AudioStream, ClipMetadata
from auto_reel_ng.proxies import spec
from auto_reel_ng.proxies.facts import (
    ProxyFacts,
    SourceFacts,
    make_facts,
    read_facts,
    read_source_facts,
    write_facts,
)
from auto_reel_ng.proxies.verify import ExpectedProxy, verify_proxy


@pytest.fixture(autouse=True)
def enabled_loggers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the proxy loggers enabled: an Alembic ``fileConfig`` run by an earlier test disables
    every logger that already exists (``disable_existing_loggers``)."""
    for name in ("auto_reel_ng.proxies.verify", "auto_reel_ng.proxies.facts"):
        monkeypatch.setattr(logging.getLogger(name), "disabled", False)


class FakeRuntime:
    """``run_ffprobe`` returns the queued document (or raises the queued error)."""

    def __init__(self, document: Any) -> None:
        self.document = document
        self.calls: list[list[str]] = []

    def run_ffprobe(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        if isinstance(self.document, BaseException):
            raise self.document
        return subprocess.CompletedProcess(args, 0, json.dumps(self.document), "")


def good_probe(**video: Any) -> dict[str, Any]:
    """The probe of a good 960x540, 624-frame, 24.96 s proxy with stereo AAC."""
    stream = {
        "codec_type": "video",
        "codec_name": "h264",
        "pix_fmt": "yuv420p",
        "width": 960,
        "height": 540,
        "sample_aspect_ratio": "1:1",
        "duration": "24.960000",
        "nb_read_packets": "624",
    }
    stream.update(video)
    return {
        "streams": [
            stream,
            {"codec_type": "audio", "codec_name": "aac", "channels": 2, "duration": "24.981"},
        ],
        "format": {"duration": "24.981000"},
    }


def expected(**overrides: Any) -> ExpectedProxy:
    values: dict[str, Any] = {
        "clip": "2020/event/C0123.MP4",
        "width": 960,
        "height": 540,
        "duration": 24.96,
        "has_audio": True,
        "declared_frames": 624,
        "path": "cpu",
    }
    values.update(overrides)
    return ExpectedProxy(**values)


def verify(document: Any, **overrides: Any) -> int:
    return verify_proxy(Path("/cache/.k.part/proxy.mp4"), expected=expected(**overrides), runtime=FakeRuntime(document))  # type: ignore[arg-type]


def sony_meta(**overrides: Any) -> ClipMetadata:
    values: dict[str, Any] = {
        "path": Path("/lib/C0123.MP4"),
        "duration": 24.96,
        "fps": 25.0,
        "video_codec": "h264",
        "profile": "High",
        "width": 1920,
        "height": 1080,
        "sample_aspect_ratio": None,
        "display_aspect_ratio": None,
        "pix_fmt": "yuv420p",
        "video_bitrate": None,
        "rotation": None,
        "color_transfer": None,
        "is_hdr": False,
        "audio": AudioStream("pcm_s16be", 48000, 2, "stereo"),
        "creation_time": None,
    }
    values.update(overrides)
    return ClipMetadata(**values)


# --------------------------------------------------------------------------- #
# facts
# --------------------------------------------------------------------------- #


def test_facts_for_the_sony_clip() -> None:
    source = SourceFacts(fps_num=25, fps_den=1, vfr=False, declared_frames=624)
    facts = make_facts(
        clip=sony_meta(),
        source=source,
        frames=624,
        size=(960, 540),
        encode_path="hybrid",
        fallback_reason=None,
    )
    assert facts.to_json() == {
        "proxy_version": spec.PROXY_VERSION,
        "duration": 24.96,
        "fps": {"num": 25, "den": 1},
        "vfr": False,
        "frames": 624,
        "width": 960,
        "height": 540,
        "source_width": 1920,
        "source_height": 1080,
        "rotation": None,
        "audio_codec": "pcm_s16be",
        "encode_path": "hybrid",
        "fallback_reason": None,
    }


def test_facts_for_a_rotated_phone_clip_and_one_without_audio() -> None:
    source = SourceFacts(fps_num=30, fps_den=1, vfr=False, declared_frames=60)
    facts = make_facts(
        clip=sony_meta(width=1280, height=720, rotation=270, audio=None, duration=2.0),
        source=source,
        frames=60,
        size=(540, 960),
        encode_path="cpu",
        fallback_reason="Failed setup for format vaapi",
    )
    assert (facts.width, facts.height, facts.source_width, facts.source_height) == (
        540,
        960,
        1280,
        720,
    )
    assert facts.rotation == 270
    assert facts.audio_codec is None
    assert facts.fallback_reason == "Failed setup for format vaapi"


def test_the_duration_is_the_sources_not_the_proxys() -> None:
    """A proxy container 21 ms longer (AAC priming) passes verification; facts keep 24.96."""
    document = good_probe()
    assert document["format"]["duration"] == "24.981000"
    frames = verify(document)
    facts = make_facts(
        clip=sony_meta(),
        source=SourceFacts(25, 1, False, 624),
        frames=frames,
        size=(960, 540),
        encode_path="cpu",
        fallback_reason=None,
    )
    assert facts.duration == 24.96
    assert facts.frames == 624


def _source_probe(rate: str, average: str, frames: Optional[str] = "624") -> dict[str, Any]:
    stream: dict[str, Any] = {"r_frame_rate": rate, "avg_frame_rate": average}
    if frames is not None:
        stream["nb_frames"] = frames
    return {"streams": [stream]}


@pytest.mark.parametrize(
    ("rate", "average", "vfr"),
    [("30/1", "300003/10000", False), ("30/1", "24/1", True), ("30/1", "30/1", False)],
)
def test_vfr_flags_a_rate_more_than_one_percent_off(rate: str, average: str, vfr: bool) -> None:
    facts = read_source_facts(Path("/x.mp4"), FakeRuntime(_source_probe(rate, average)), clip="x.mp4")  # type: ignore[arg-type]
    assert facts.vfr is vfr
    assert (facts.fps_num, facts.fps_den) == (30, 1)
    assert facts.declared_frames == 624


def test_fractional_rates_stay_exact() -> None:
    facts = read_source_facts(Path("/x.mp4"), FakeRuntime(_source_probe("30000/1001", "30000/1001")), clip="x")  # type: ignore[arg-type]
    assert (facts.fps_num, facts.fps_den) == (30000, 1001)


def test_an_unknown_average_rate_leaves_vfr_null_not_false() -> None:
    facts = read_source_facts(Path("/x.mp4"), FakeRuntime(_source_probe("25/1", "0/0")), clip="x")  # type: ignore[arg-type]
    assert facts.vfr is None


def test_the_video_streams_own_duration_is_read() -> None:
    document = _source_probe("25/1", "25/1")
    document["streams"][0]["duration"] = "3.000000"
    runtime = FakeRuntime(document)
    facts = read_source_facts(Path("/x.mp4"), runtime, clip="x")  # type: ignore[arg-type]
    assert facts.video_duration == 3.0
    assert "stream=r_frame_rate,avg_frame_rate,nb_frames,duration" in runtime.calls[0]


@pytest.mark.parametrize("duration", [None, "N/A", "garbage", "0.000000", "-1", "nan", "inf"])
def test_a_video_duration_the_container_does_not_give_is_none(duration: Optional[str]) -> None:
    document = _source_probe("25/1", "25/1")
    if duration is not None:
        document["streams"][0]["duration"] = duration
    facts = read_source_facts(Path("/x.mp4"), FakeRuntime(document), clip="x")  # type: ignore[arg-type]
    assert facts.video_duration is None


def test_no_declared_frame_count_is_none() -> None:
    facts = read_source_facts(Path("/x.mp4"), FakeRuntime(_source_probe("25/1", "25/1", None)), clip="x")  # type: ignore[arg-type]
    assert facts.declared_frames is None
    facts = read_source_facts(Path("/x.mp4"), FakeRuntime(_source_probe("25/1", "25/1", "N/A")), clip="x")  # type: ignore[arg-type]
    assert facts.declared_frames is None


@pytest.mark.parametrize(
    "document",
    [{"streams": []}, {"streams": [{"r_frame_rate": "0/0", "avg_frame_rate": "0/0"}]}, {}],
)
def test_a_source_with_no_usable_frame_rate_is_a_proxy_error(document: Any) -> None:
    with pytest.raises(ProxyError, match="C0001"):
        read_source_facts(Path("/x.mp4"), FakeRuntime(document), clip="C0001")  # type: ignore[arg-type]


def test_a_failing_ffprobe_is_a_proxy_error() -> None:
    with pytest.raises(ProxyError, match="frame rate"):
        read_source_facts(Path("/x.mp4"), FakeRuntime(FfmpegError("boom")), clip="C0001")  # type: ignore[arg-type]


def test_facts_round_trip(tmp_path: Path) -> None:
    facts = make_facts(
        clip=sony_meta(),
        source=SourceFacts(25, 1, None, 624),
        frames=624,
        size=(960, 540),
        encode_path="cpu",
        fallback_reason=None,
    )
    path = write_facts(tmp_path, facts)
    assert path == tmp_path / "facts.json"
    assert read_facts(path) == facts
    assert json.loads(path.read_text())["fps"] == {"den": 1, "num": 25}


@pytest.mark.parametrize(
    "mutate",
    [
        "missing-key",
        "wrong-version",
        "bad-json",
        "not-an-object",
        "bool-frames",
        "zero-rate",
        "empty",
        "zero-width",
        "negative-height",
        "rotation-360",
        "rotation-negative",
        "infinite-duration",
    ],
)
def test_damaged_facts_read_as_absent_never_as_defaults(tmp_path: Path, mutate: str) -> None:
    facts = make_facts(
        clip=sony_meta(),
        source=SourceFacts(25, 1, False, 624),
        frames=624,
        size=(960, 540),
        encode_path="cpu",
        fallback_reason=None,
    )
    document = copy.deepcopy(facts.to_json())
    text: Optional[str] = None
    if mutate == "missing-key":
        del document["frames"]
    elif mutate == "wrong-version":
        document["proxy_version"] = spec.PROXY_VERSION + 1
    elif mutate == "bad-json":
        text = '{"proxy_version": 1,'
    elif mutate == "not-an-object":
        text = "[1, 2]"
    elif mutate == "bool-frames":
        document["frames"] = True
    elif mutate == "zero-rate":
        document["fps"] = {"num": 0, "den": 1}
    elif mutate == "empty":
        text = ""
    elif mutate == "zero-width":
        document["width"] = 0
    elif mutate == "negative-height":
        document["height"] = -540
    elif mutate == "rotation-360":
        document["rotation"] = 360
    elif mutate == "rotation-negative":
        document["rotation"] = -90
    elif mutate == "infinite-duration":
        text = json.dumps(document).replace(str(document["duration"]), "Infinity", 1)
    target = tmp_path / "facts.json"
    target.write_text(text if text is not None else json.dumps(document), encoding="utf-8")
    assert read_facts(target) is None


def test_missing_facts_read_as_absent(tmp_path: Path) -> None:
    assert read_facts(tmp_path / "facts.json") is None
    assert read_facts(tmp_path) is None  # a directory is no facts either


def test_proxy_facts_is_a_complete_dataclass() -> None:
    assert ProxyFacts.from_json(None) is None


# --------------------------------------------------------------------------- #
# verification
# --------------------------------------------------------------------------- #


def test_a_good_proxy_passes_and_returns_its_frame_count() -> None:
    assert verify(good_probe()) == 624


def _drop_audio(document: dict[str, Any]) -> dict[str, Any]:
    document["streams"] = [s for s in document["streams"] if s["codec_type"] != "audio"]
    return document


def test_missing_audio_fails_naming_the_audio_check() -> None:
    with pytest.raises(ProxyError, match=r"audio streams check: found 0, expected 1 \(cpu path\)"):
        verify(_drop_audio(good_probe()))


def test_an_unexpected_audio_stream_fails_when_the_source_has_none() -> None:
    with pytest.raises(ProxyError, match=r"audio streams check: found 1, expected 0"):
        verify(good_probe(), has_audio=False)


def test_a_source_without_audio_passes_without_one() -> None:
    assert verify(_drop_audio(good_probe()), has_audio=False) == 624


def test_two_video_streams_fail() -> None:
    document = good_probe()
    document["streams"].append(dict(document["streams"][0]))
    with pytest.raises(ProxyError, match="video streams check: found 2, expected 1"):
        verify(document)


def test_a_non_h264_video_stream_fails() -> None:
    with pytest.raises(ProxyError, match="video codec check: found hevc, expected h264"):
        verify(good_probe(codec_name="hevc"))


def test_a_non_aac_audio_stream_fails() -> None:
    document = good_probe()
    document["streams"][1]["codec_name"] = "mp3"
    with pytest.raises(ProxyError, match="audio codec check: found mp3, expected aac"):
        verify(document)


def test_mono_audio_fails() -> None:
    document = good_probe()
    document["streams"][1]["channels"] = 1
    with pytest.raises(ProxyError, match="audio channels check: found 1, expected 2"):
        verify(document)


def test_the_wrong_dimensions_fail_with_both_values() -> None:
    with pytest.raises(ProxyError, match=r"dimensions check: found 960x540, expected 540x960"):
        verify(good_probe(), width=540, height=960)


def test_a_non_square_pixel_fails() -> None:
    with pytest.raises(ProxyError, match="pixel aspect ratio check: found 16:15, expected 1:1"):
        verify(good_probe(sample_aspect_ratio="16:15"))


def test_an_unset_pixel_aspect_ratio_counts_as_square() -> None:
    document = good_probe()
    del document["streams"][0]["sample_aspect_ratio"]
    assert verify(document) == 624


def test_a_wrong_pixel_format_fails() -> None:
    with pytest.raises(ProxyError, match="pixel format check: found yuv444p, expected yuv420p"):
        verify(good_probe(pix_fmt="yuv444p"))


def test_a_video_duration_60_ms_short_fails_and_40_ms_short_passes() -> None:
    with pytest.raises(
        ProxyError, match=r"video duration check: found 24.900s, expected 24.960s within 50 ms"
    ):
        verify(good_probe(duration="24.900000"))
    assert verify(good_probe(duration="24.920000")) == 624


def test_a_video_duration_60_ms_long_fails() -> None:
    with pytest.raises(ProxyError, match="video duration check"):
        verify(good_probe(duration="25.020000"))


def test_a_missing_video_duration_fails_rather_than_passing() -> None:
    with pytest.raises(ProxyError, match="video duration check"):
        verify(good_probe(duration="N/A"))


def test_one_frame_short_fails_the_frame_count_check() -> None:
    with pytest.raises(ProxyError, match="video frames check: found 623, expected 624"):
        verify(good_probe(nb_read_packets="623"))


def test_no_declared_frame_count_skips_only_that_check_and_logs_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="auto_reel_ng.proxies.verify"):
        assert verify(good_probe(nb_read_packets="623"), declared_frames=None) == 623
    assert "frame-count check was not possible" in caplog.text
    # every other check still runs
    with pytest.raises(ProxyError, match="dimensions check"):
        verify(good_probe(), declared_frames=None, width=540, height=960)


def test_an_unreadable_proxy_is_a_proxy_error() -> None:
    with pytest.raises(ProxyError, match="cannot be probed"):
        verify(FfmpegError("moov atom not found"))


def test_the_error_names_the_clip() -> None:
    with pytest.raises(ProxyError) as error:
        verify(good_probe(codec_name="vp9"))
    assert error.value.clip == "2020/event/C0123.MP4"
    assert "2020/event/C0123.MP4: the encoded proxy failed" in str(error.value)
