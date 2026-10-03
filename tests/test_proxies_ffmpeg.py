"""Real-encode tests for the proxy engine (D-21): the contract, the geometry, the audio rule,
sub-second clips, variable frame rate, verification, and the sample library.

Every test needs a real ffmpeg >= 7.1 (``has_ffmpeg``) and uses the CPU profile unless it is
marked ``gpu``. Synthetic clips are 1 to 2 seconds; the samples under
``auto-reel-media/samples`` are read-only and skipped when absent.
"""

from __future__ import annotations

import json
import struct
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from auto_reel_ng.accel import detect_capabilities, select_profile
from auto_reel_ng.accel.models import Vendor
from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.errors import ProxyError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.probe.media import probe_media
from auto_reel_ng.proxies import ProxySettings, ensure, ensure_proxy, lookup_proxy

pytestmark = pytest.mark.has_ffmpeg

MakeClip = Callable[..., Path]
SAMPLES = Path(__file__).resolve().parents[2] / "auto-reel-media" / "samples"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def probe_json(runtime: FfmpegRuntime, path: Path, *extra: str) -> dict[str, Any]:
    args = ["-v", "error", "-show_streams", "-show_format", "-print_format", "json", *extra]
    return json.loads(runtime.run_ffprobe([*args, str(path)]).stdout)


def stream_of(document: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [s for s in document["streams"] if s["codec_type"] == kind]


def packets(runtime: FfmpegRuntime, path: Path) -> list[dict[str, Any]]:
    out = runtime.run_ffprobe(
        [
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "packet=flags,pts_time,dts_time",
            "-print_format",
            "json",
            str(path),
        ]
    ).stdout
    return json.loads(out)["packets"]


def frame_times(runtime: FfmpegRuntime, path: Path) -> list[float]:
    out = runtime.run_ffprobe(
        [
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=best_effort_timestamp_time",
            "-print_format",
            "json",
            str(path),
        ]
    ).stdout
    return sorted(float(f["best_effort_timestamp_time"]) for f in json.loads(out)["frames"])


def top_level_boxes(path: Path, limit: int = 16) -> list[str]:
    """The first top-level MP4 box types of ``path``."""
    types: list[str] = []
    with path.open("rb") as handle:
        for _ in range(limit):
            header = handle.read(8)
            if len(header) < 8:
                break
            size, kind = struct.unpack(">I4s", header)
            types.append(kind.decode("latin-1"))
            if size == 1:
                size = struct.unpack(">Q", handle.read(8))[0]
                handle.seek(size - 16, 1)
            elif size == 0:
                break
            else:
                handle.seek(size - 8, 1)
    return types


def raw_frame(runtime: FfmpegRuntime, path: Path, width: int, height: int) -> bytes:
    """The first frame of ``path`` as ``width``x``height`` rgb24 (display rotation applied)."""
    result = subprocess.run(
        [
            runtime.ffmpeg_path,
            "-v",
            "error",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:{height}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return result.stdout


def pixel(frame: bytes, width: int, x: int, y: int) -> tuple[int, int, int]:
    offset = (y * width + x) * 3
    return frame[offset], frame[offset + 1], frame[offset + 2]


def make(runtime: FfmpegRuntime, out: Path, *input_args: str, output_args: list[str]) -> Path:
    subprocess.run(
        [runtime.ffmpeg_path, "-y", "-v", "error", *input_args, *output_args, str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    return out


def proxy_of(runtime: FfmpegRuntime, clip: Path, cache: Path, profile: Any = None):  # type: ignore[no-untyped-def]
    return ensure_proxy(
        clip, settings=ProxySettings(cache), runtime=runtime, profile=profile or CPUProfile()
    )


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "proxies"


# --------------------------------------------------------------------------- #
# the contract
# --------------------------------------------------------------------------- #


def test_a_1080p25_clip_gets_the_contract(
    runtime: FfmpegRuntime, make_clip: MakeClip, cache: Path
) -> None:
    clip = make_clip("c.mp4", width=1920, height=1080, fps=25, duration=2.0)

    entry = proxy_of(runtime, clip, cache)

    document = probe_json(runtime, entry.proxy_path)
    (video,) = stream_of(document, "video")
    (audio,) = stream_of(document, "audio")
    assert (video["codec_name"], video["profile"], video["pix_fmt"]) == ("h264", "High", "yuv420p")
    assert (video["width"], video["height"]) == (960, 540)
    assert video.get("sample_aspect_ratio", "1:1") in ("1:1", "N/A")
    assert 0 <= video["has_b_frames"] <= 2
    assert (audio["codec_name"], audio["channels"]) == ("aac", 2)
    assert audio["profile"] == "LC"
    flags = [p["flags"] for p in packets(runtime, entry.proxy_path)]
    assert len(flags) == 50
    assert [i for i, f in enumerate(flags) if f.startswith("K")] == [0, 25]
    boxes = top_level_boxes(entry.proxy_path)
    assert boxes.index("moov") < boxes.index("mdat")
    assert entry.facts.frames == 50 and entry.facts.audio_codec == "aac"


def test_a_50fps_clip_gets_a_keyframe_every_50_frames(
    runtime: FfmpegRuntime, make_clip: MakeClip, cache: Path
) -> None:
    clip = make_clip("fifty.mp4", width=1280, height=720, fps=50, duration=3.0)
    entry = proxy_of(runtime, clip, cache)
    flags = [p["flags"] for p in packets(runtime, entry.proxy_path)]
    assert len(flags) == 150
    assert [i for i, f in enumerate(flags) if f.startswith("K")] == [0, 50, 100]


def test_the_encode_really_uses_b_frames_within_the_limit(
    runtime: FfmpegRuntime, make_clip: MakeClip, cache: Path
) -> None:
    clip = make_clip("c.mp4", width=640, height=360, fps=25, duration=2.0)
    entry = proxy_of(runtime, clip, cache)
    pts = [p for p in packets(runtime, entry.proxy_path)]
    # B-frames reorder frames: some packet's presentation time is earlier than its predecessor's.
    reordered = any(float(b["pts_time"]) < float(a["pts_time"]) for a, b in zip(pts, pts[1:]))
    assert reordered
    (video,) = stream_of(probe_json(runtime, entry.proxy_path), "video")
    assert video["has_b_frames"] == 2


def test_portrait_and_small_clips(runtime: FfmpegRuntime, make_clip: MakeClip, cache: Path) -> None:
    portrait = proxy_of(runtime, make_clip("p.mp4", width=1080, height=1920, duration=1.0), cache)
    small = proxy_of(runtime, make_clip("s.mp4", width=640, height=360, duration=1.0), cache)
    assert (portrait.facts.width, portrait.facts.height) == (540, 960)
    assert (small.facts.width, small.facts.height) == (640, 360)
    assert [
        (s["width"], s["height"])
        for e in (portrait, small)
        for s in stream_of(probe_json(runtime, e.proxy_path), "video")
    ] == [(540, 960), (640, 360)]


def test_rotation_is_applied_upright_and_the_picture_is_not_squashed(
    runtime: FfmpegRuntime, tmp_path: Path, cache: Path
) -> None:
    src = make(
        runtime,
        tmp_path / "halves.mp4",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=640x720:r=25:d=1",
        "-f",
        "lavfi",
        "-i",
        "color=c=green:s=640x720:r=25:d=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        output_args=[
            "-filter_complex",
            "[0][1]hstack[v]",
            "-map",
            "[v]",
            "-map",
            "2:a",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
        ],
    )
    clip = make(
        runtime,
        tmp_path / "rotated.mp4",
        "-display_rotation:v:0",
        "-90",
        "-i",
        str(src),
        output_args=["-map", "0", "-c", "copy"],
    )
    assert probe_media(clip, runtime=runtime).rotation in (270, -90)

    entry = proxy_of(runtime, clip, cache)

    assert (entry.facts.width, entry.facts.height) == (540, 960)
    assert (entry.facts.source_width, entry.facts.source_height) == (1280, 720)
    frame = raw_frame(runtime, entry.proxy_path, 540, 960)
    reference = raw_frame(runtime, clip, 540, 960)  # a player's view of the source
    top, bottom = pixel(frame, 540, 270, 240), pixel(frame, 540, 270, 720)
    assert top != bottom  # the halves are stacked, not side by side
    left, right = pixel(frame, 540, 135, 480), pixel(frame, 540, 405, 480)
    assert abs(left[0] - right[0]) < 30 and abs(left[1] - right[1]) < 30  # same colour across
    assert top == pytest.approx(pixel(reference, 540, 270, 240), abs=24)
    assert bottom == pytest.approx(pixel(reference, 540, 270, 720), abs=24)
    # not squashed: the boundary between the halves is at mid height
    boundary = [pixel(frame, 540, 270, y) for y in (440, 520)]
    assert boundary[0] == pytest.approx(top, abs=24) and boundary[1] == pytest.approx(
        bottom, abs=24
    )


def test_an_anamorphic_clip_is_not_squashed(
    runtime: FfmpegRuntime, make_clip: MakeClip, cache: Path
) -> None:
    clip = make_clip("pal.mp4", width=720, height=576, fps=25, duration=1.0, setsar="16/15")
    entry = proxy_of(runtime, clip, cache)
    (video,) = stream_of(probe_json(runtime, entry.proxy_path), "video")
    assert (video["width"], video["height"]) == (720, 540)
    assert video.get("sample_aspect_ratio", "1:1") in ("1:1", "N/A")


# --------------------------------------------------------------------------- #
# audio
# --------------------------------------------------------------------------- #


def audio_clip(
    runtime: FfmpegRuntime, tmp_path: Path, name: str, audio_source: str, *audio_args: str
) -> Path:
    return make(
        runtime,
        tmp_path / name,
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=320x240:rate=25:duration=1",
        "-f",
        "lavfi",
        "-i",
        audio_source,
        output_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", *audio_args, "-shortest"],
    )


@pytest.mark.parametrize(
    ("name", "audio_source", "audio_args", "source_codec"),
    [
        ("mono.mp4", "sine=frequency=440:duration=1", ["-ac", "1", "-c:a", "aac"], "aac"),
        (
            "surround.mp4",
            "anoisesrc=d=1:c=pink:r=48000,aformat=channel_layouts=5.1",
            ["-c:a", "ac3"],
            "ac3",
        ),
        ("sony.mov", "sine=frequency=440:duration=1", ["-c:a", "pcm_s16be"], "pcm_s16be"),
        (
            "mp3.mp4",
            "sine=frequency=440:duration=1:sample_rate=44100",
            ["-c:a", "libmp3lame"],
            "mp3",
        ),
    ],
)
def test_every_audio_source_becomes_stereo_aac(
    runtime: FfmpegRuntime,
    tmp_path: Path,
    cache: Path,
    name: str,
    audio_source: str,
    audio_args: list[str],
    source_codec: str,
) -> None:
    clip = audio_clip(runtime, tmp_path, name, audio_source, *audio_args)
    entry = proxy_of(runtime, clip, cache)
    (audio,) = stream_of(probe_json(runtime, entry.proxy_path), "audio")
    assert (audio["codec_name"], audio["channels"]) == ("aac", 2)
    assert entry.facts.audio_codec == source_codec


def test_a_clip_without_audio_gets_none(
    runtime: FfmpegRuntime, make_clip: MakeClip, cache: Path
) -> None:
    entry = proxy_of(runtime, make_clip("mute.mp4", audio=False, duration=1.0), cache)
    assert stream_of(probe_json(runtime, entry.proxy_path), "audio") == []
    assert entry.facts.audio_codec is None


# --------------------------------------------------------------------------- #
# sub-second clips and variable frame rate
# --------------------------------------------------------------------------- #


def test_a_12_frame_clip_publishes_with_one_keyframe(
    runtime: FfmpegRuntime, make_clip: MakeClip, cache: Path
) -> None:
    clip = make_clip("short.mp4", width=1920, height=1080, fps=25, duration=0.48)
    entry = proxy_of(runtime, clip, cache)
    flags = [p["flags"] for p in packets(runtime, entry.proxy_path)]
    assert len(flags) == 12 == entry.facts.frames
    assert [i for i, f in enumerate(flags) if f.startswith("K")] == [0]
    assert entry.facts.duration == pytest.approx(0.48, abs=0.01)


def test_a_one_frame_clip_publishes(runtime: FfmpegRuntime, tmp_path: Path, cache: Path) -> None:
    clip = make(
        runtime,
        tmp_path / "one.mp4",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=30:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        output_args=[
            "-frames:v",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
        ],
    )
    entry = proxy_of(runtime, clip, cache)
    assert entry.facts.frames == 1
    assert [p["flags"][0] for p in packets(runtime, entry.proxy_path)] == ["K"]


def test_a_variable_frame_rate_clip_keeps_its_frames_and_timing(
    runtime: FfmpegRuntime, tmp_path: Path, cache: Path
) -> None:
    clip = make(
        runtime,
        tmp_path / "vfr.mp4",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=30:duration=4",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=4",
        output_args=[
            "-vf",
            "select='not(mod(n,3))+not(mod(n,7))'",
            "-fps_mode",
            "passthrough",
            "-video_track_timescale",
            "90000",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
        ],
    )
    source_times = frame_times(runtime, clip)

    entry = proxy_of(runtime, clip, cache)

    proxy_times = frame_times(runtime, entry.proxy_path)
    assert entry.facts.vfr is True
    assert len(proxy_times) == len(source_times) == entry.facts.frames
    assert proxy_times[0] == pytest.approx(source_times[0], abs=1 / 30)
    assert proxy_times[-1] == pytest.approx(source_times[-1], abs=1 / 30)


def test_an_hdr_clip_is_tone_mapped_on_the_cpu(
    runtime: FfmpegRuntime, tmp_path: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = make(
        runtime,
        tmp_path / "hlg.mp4",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=1920x1080:rate=25:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        output_args=[
            "-vf",
            "setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
        ],
    )
    assert probe_media(clip, runtime=runtime).is_hdr
    runs: list[list[str]] = []
    real = FfmpegRuntime.run_with_progress
    monkeypatch.setattr(
        FfmpegRuntime,
        "run_with_progress",
        lambda self, args, **k: (runs.append(list(args)), real(self, args, **k))[1],
    )

    entry = proxy_of(runtime, clip, cache)

    assert len(runs) == 1 and "zscale=t=linear" in " ".join(runs[0])
    assert (entry.facts.width, entry.facts.height, entry.facts.encode_path) == (960, 540, "cpu")


# --------------------------------------------------------------------------- #
# verification, idempotency, failures
# --------------------------------------------------------------------------- #


def test_verification_catches_a_proxy_that_lost_its_audio(
    runtime: FfmpegRuntime, make_clip: MakeClip, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_build = ensure.build_proxy_command

    def no_audio(*args: Any, **kwargs: Any) -> Any:
        built = real_build(*args, **kwargs)
        arguments = list(built.args)
        start = arguments.index("-map", arguments.index("0:v:0") + 1)  # the audio map
        del arguments[start : start + 8]  # -map 0:a:0 -c:a aac -b:a 128k -ac 2
        return type(built)(tuple(arguments), built.path, built.width, built.height, built.duration)

    monkeypatch.setattr(ensure, "build_proxy_command", no_audio)
    clip = make_clip("c.mp4", duration=1.0)

    with pytest.raises(ProxyError, match=r"audio streams check: found 0, expected 1 \(cpu path\)"):
        proxy_of(runtime, clip, cache)

    assert list(cache.iterdir()) == []


def test_a_zero_byte_clip_fails_and_a_good_clip_is_served_from_the_cache_the_second_time(
    runtime: FfmpegRuntime,
    make_clip: MakeClip,
    tmp_path: Path,
    cache: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = tmp_path / "trasig.mp4"
    broken.write_bytes(b"")
    with pytest.raises(ProxyError, match="zero bytes"):
        proxy_of(runtime, broken, cache)

    clip = make_clip("good.mp4", duration=1.0)
    before = (clip.read_bytes(), clip.stat().st_mtime_ns)
    first = proxy_of(runtime, clip, cache)
    runs: list[Any] = []
    real = FfmpegRuntime.run_with_progress
    monkeypatch.setattr(
        FfmpegRuntime,
        "run_with_progress",
        lambda self, *a, **k: (runs.append(a), real(self, *a, **k))[1],
    )
    second = proxy_of(runtime, clip, cache)

    assert first.generated is True and second.generated is False
    assert first.directory == second.directory
    assert runs == []
    assert (clip.read_bytes(), clip.stat().st_mtime_ns) == before
    assert lookup_proxy(clip, settings=ProxySettings(cache)) is not None


def test_a_garbage_clip_is_a_proxy_error(
    runtime: FfmpegRuntime, tmp_path: Path, cache: Path
) -> None:
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(b"this is not a video " * 50)
    with pytest.raises(ProxyError):
        proxy_of(runtime, junk, cache)
    assert not cache.exists() or list(cache.iterdir()) == []


# --------------------------------------------------------------------------- #
# the hardware path (gpu)
# --------------------------------------------------------------------------- #


@pytest.mark.gpu
def test_the_hybrid_path_matches_the_cpu_path(
    runtime: FfmpegRuntime, make_clip: MakeClip, tmp_path: Path
) -> None:
    profile = select_profile(detect_capabilities(runtime))
    if profile.vendor is Vendor.CPU:
        pytest.skip("no usable hardware accelerator on this host")
    node = getattr(getattr(profile, "capabilities", None), "device", None)
    clip = make_clip("hd.mp4", width=1920, height=1080, fps=25, duration=2.0)

    hybrid = ensure_proxy(
        clip,
        settings=ProxySettings(tmp_path / "hybrid"),
        runtime=runtime,
        profile=profile,
        render_node=node.render_node if node else None,
    )
    cpu = proxy_of(runtime, clip, tmp_path / "cpu")

    assert hybrid.facts.encode_path == "hybrid"
    assert cpu.facts.encode_path == "cpu"
    assert (hybrid.facts.width, hybrid.facts.height) == (cpu.facts.width, cpu.facts.height)
    assert hybrid.facts.frames == cpu.facts.frames
    assert hybrid.key == cpu.key  # the encode path is not part of the key


# --------------------------------------------------------------------------- #
# the sample library (read-only)
# --------------------------------------------------------------------------- #

#: sample -> the proxy's (width, height)
SAMPLE_SIZES = {
    "h264-1080p25-aac.mp4": (960, 540),
    "h264-1080p50-aac.mp4": (960, 540),
    "h264-4k50-aac-119mbps.mp4": (960, 540),
    "h264-720p25-aac-msnv.mp4": (960, 540),
    "h264-portrait-1080x1920-aac.mp4": (540, 960),
    "h264-720p-rotate90-aac.mp4": (540, 960),
    "hevc-mov-rotate90-aac.mov": (540, 960),
    "sony-xavc-1080p25-pcm.mp4": (960, 540),
    "sony-xavc-4k25-pcm.mp4": (960, 540),
}
LEGACY = "legacy-render-mpeg4-mp3.mp4"


def check_sample(
    runtime: FfmpegRuntime, sample: Path, cache: Path, profile: Any, node: Optional[str]
) -> None:
    entry = ensure_proxy(
        sample, settings=ProxySettings(cache), runtime=runtime, profile=profile, render_node=node
    )
    source = probe_json(runtime, sample)
    proxy = probe_json(runtime, entry.proxy_path, "-count_packets")
    (source_video,) = stream_of(source, "video")[:1]
    (video,) = stream_of(proxy, "video")
    (audio,) = stream_of(proxy, "audio")
    assert (audio["codec_name"], audio["channels"]) == ("aac", 2)
    assert (video["width"], video["height"]) == SAMPLE_SIZES.get(sample.name, (960, 540))
    assert abs(float(video["duration"]) - float(source_video["duration"])) <= 0.05
    assert int(video["nb_read_packets"]) == int(source_video["nb_frames"])
    assert float(video["start_time"]) == pytest.approx(float(source_video["start_time"]), abs=1e-6)
    assert entry.facts.audio_codec == stream_of(source, "audio")[0]["codec_name"]


def test_the_sony_sample_facts_are_the_specs_values(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    sample = SAMPLES / "sony-xavc-1080p25-pcm.mp4"
    if not sample.is_file():
        pytest.skip(f"{sample} not present")
    facts = proxy_of(runtime, sample, tmp_path / "cpu").facts
    assert (facts.duration, facts.fps_num, facts.fps_den, facts.vfr) == (24.96, 25, 1, False)
    assert (facts.frames, facts.width, facts.height) == (624, 960, 540)
    assert (facts.source_width, facts.source_height) == (1920, 1080)
    assert (facts.rotation, facts.audio_codec) == (None, "pcm_s16be")


@pytest.mark.parametrize("name", sorted(SAMPLE_SIZES))
def test_sample_on_the_cpu_path(runtime: FfmpegRuntime, tmp_path: Path, name: str) -> None:
    sample = SAMPLES / name
    if not sample.is_file():
        pytest.skip(f"{sample} not present")
    before = (sample.stat().st_size, sample.stat().st_mtime_ns)
    check_sample(runtime, sample, tmp_path / "cpu", CPUProfile(), None)
    assert (sample.stat().st_size, sample.stat().st_mtime_ns) == before


def test_the_legacy_mpeg4_sample_on_the_cpu_path(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    sample = SAMPLES / LEGACY
    if not sample.is_file():
        pytest.skip(f"{sample} not present")
    check_sample(runtime, sample, tmp_path / "cpu", CPUProfile(), None)


@pytest.mark.gpu
@pytest.mark.parametrize("name", sorted(SAMPLE_SIZES))
def test_sample_on_the_hardware_profile(runtime: FfmpegRuntime, tmp_path: Path, name: str) -> None:
    sample = SAMPLES / name
    if not sample.is_file():
        pytest.skip(f"{sample} not present")
    profile = select_profile(detect_capabilities(runtime))
    if profile.vendor is Vendor.CPU:
        pytest.skip("no usable hardware accelerator on this host")
    device = getattr(getattr(profile, "capabilities", None), "device", None)
    check_sample(runtime, sample, tmp_path / "hw", profile, device.render_node if device else None)
