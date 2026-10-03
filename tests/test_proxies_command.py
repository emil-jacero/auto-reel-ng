"""Golden ffmpeg arguments and the encode ladder of the proxy builder (D-21, clip-proxies).

No ffmpeg and no GPU are needed: the builder is pure, and the profiles are built from
:class:`AcceleratorCapabilities` values.
"""

from __future__ import annotations

import dataclasses
import re
import subprocess
from pathlib import Path
from typing import Optional

import pytest

from auto_reel_ng.accel.models import (
    AcceleratorCapabilities,
    Device,
    FrameLocation,
    OpClass,
    OpParams,
    Vendor,
)
from auto_reel_ng.accel.profiles import AccelProfile, CPUProfile, NvencProfile, VaapiProfile
from auto_reel_ng.accel.profiles.cpu import CPU_TONEMAP_FILTER
from auto_reel_ng.probe.metadata import AudioStream, ClipMetadata
from auto_reel_ng.proxies import spec
from auto_reel_ng.proxies.command import (
    EncodePath,
    ProxyCommand,
    build_proxy_command,
    plan_encode,
)
from auto_reel_ng.proxies.spec import proxy_dimensions

NODE = "/dev/dri/renderD128"
SOURCE = Path("/lib/2020/event/C0123.MP4")
OUTPUT = Path("/cache/.key.unique.part/proxy.mp4")


def make_meta(**overrides: object) -> ClipMetadata:
    """The Sony 1080p25 PCM clip, with ``overrides``."""
    values: dict[str, object] = {
        "path": SOURCE,
        "duration": 24.96,
        "fps": 25.0,
        "video_codec": "h264",
        "profile": "High",
        "width": 1920,
        "height": 1080,
        "sample_aspect_ratio": None,
        "display_aspect_ratio": None,
        "pix_fmt": "yuv420p",
        "video_bitrate": 50_000_000,
        "rotation": None,
        "color_transfer": None,
        "is_hdr": False,
        "audio": AudioStream("pcm_s16be", 48000, 2, "stereo"),
        "creation_time": None,
    }
    values.update(overrides)
    return ClipMetadata(**values)  # type: ignore[arg-type]


def vaapi_profile(**caps: object) -> VaapiProfile:
    values: dict[str, object] = {
        "vendor": Vendor.AMD,
        "usable": True,
        "device": Device("pci-0", Vendor.AMD, "RX 9070 XT", NODE),
        "pad_filter": "pad_vaapi",
        "can_overlay_hw": False,
        "can_tonemap_hw": False,
        "usable_encoders": {"h264": "h264_vaapi"},
        "decode_method": "vaapi",
        "hw_decode": {"h264": 8, "hevc": 10},
    }
    values.update(caps)
    return VaapiProfile(AcceleratorCapabilities(**values))  # type: ignore[arg-type]


def cuda_profile() -> NvencProfile:
    """A profile whose hardware decode leaves frames in CUDA memory."""
    return NvencProfile(
        AcceleratorCapabilities(
            vendor=Vendor.NVIDIA,
            usable=True,
            device=None,
            pad_filter="pad",
            can_overlay_hw=False,
            can_tonemap_hw=False,
            usable_encoders={"h264": "h264_nvenc"},
            decode_method="cuda",
            hw_decode={"h264": 8, "hevc": 10},
        )
    )


def command(
    meta: ClipMetadata, profile: AccelProfile, path: Optional[EncodePath] = None
) -> ProxyCommand:
    size = proxy_dimensions(meta.width, meta.height, meta.sample_aspect_ratio, meta.rotation)
    chosen = path or plan_encode(meta, profile, render_node=NODE)
    return build_proxy_command(
        meta,
        source=SOURCE,
        output=OUTPUT,
        path=chosen,
        profile=profile,
        render_node=NODE,
        size=size,
    )


def encode_options(gop: int) -> list[str]:
    return [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-bf",
        "0",
        "-g",
        str(gop),
        "-sc_threshold",
        "0",
    ]


AUDIO = ["-map", "0:a:0", "-c:a", "aac", "-b:a", "128k", "-ac", "2"]
TAIL = ["-movflags", "+faststart", str(OUTPUT)]
HYBRID_FILTER = "scale_vaapi=w=960:h=540:format=nv12,hwdownload,format=nv12,setsar=1"


# --------------------------------------------------------------------------- #
# golden arguments
# --------------------------------------------------------------------------- #


def test_golden_hybrid_arguments_for_the_sony_clip() -> None:
    built = command(make_meta(), vaapi_profile())

    assert built.path is EncodePath.HYBRID
    assert (built.width, built.height, built.duration) == (960, 540, 24.96)
    assert list(built.args) == [
        "-hide_banner",
        "-nostdin",
        "-y",
        "-init_hw_device",
        f"vaapi=va:{NODE}",
        "-filter_hw_device",
        "va",
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        "va",
        "-hwaccel_output_format",
        "vaapi",
        "-i",
        str(SOURCE),
        "-map",
        "0:v:0",
        "-vf",
        HYBRID_FILTER,
        "-fps_mode",
        "passthrough",
        *encode_options(12),
        *AUDIO,
        *TAIL,
    ]


def test_golden_cpu_arguments_for_a_rotated_phone_clip() -> None:
    meta = make_meta(width=1280, height=720, fps=30.0, rotation=270)
    built = command(meta, vaapi_profile())

    assert built.path is EncodePath.CPU
    assert (built.width, built.height) == (540, 960)
    assert list(built.args) == [
        "-hide_banner",
        "-nostdin",
        "-y",
        "-i",
        str(SOURCE),
        "-map",
        "0:v:0",
        "-vf",
        "scale=540:960:flags=bicubic,setsar=1",
        "-fps_mode",
        "passthrough",
        *encode_options(15),
        *AUDIO,
        *TAIL,
    ]


def test_the_cpu_arguments_never_rotate_by_hand() -> None:
    args = command(make_meta(rotation=90), CPUProfile()).args
    assert "-noautorotate" not in args
    assert not any("transpose" in arg for arg in args)


@pytest.mark.parametrize(
    ("fps", "gop"), [(50.0, 25), (30000 / 1001, 15), (25.0, 12), (24000 / 1001, 12)]
)
def test_the_keyframe_interval_is_half_a_second_of_frames(fps: float, gop: int) -> None:
    args = list(command(make_meta(fps=fps), CPUProfile()).args)
    assert args[args.index("-g") + 1] == str(gop)
    assert args[args.index("-sc_threshold") + 1] == "0"
    assert args[args.index("-bf") + 1] == "0"


def test_a_sub_second_clip_keeps_the_half_second_interval() -> None:
    meta = make_meta(duration=0.48, fps=25.0)  # 12 frames: one keyframe, at the start
    args = list(command(meta, CPUProfile()).args)
    assert args[args.index("-g") + 1] == "12"


def test_a_clip_without_audio_gets_no_audio_options() -> None:
    args = list(command(make_meta(audio=None), CPUProfile()).args)
    assert "0:a:0" not in args
    assert "-c:a" not in args
    assert "-b:a" not in args
    assert args[-3:] == TAIL


def test_an_hdr_clip_is_tone_mapped_ahead_of_the_scale() -> None:
    meta = make_meta(is_hdr=True, color_transfer="arib-std-b67")
    built = command(meta, vaapi_profile())
    assert built.path is EncodePath.CPU
    args = list(built.args)
    assert (
        args[args.index("-vf") + 1] == f"{CPU_TONEMAP_FILTER},scale=960:540:flags=bicubic,setsar=1"
    )


def test_a_legacy_mpeg4_clip_has_no_hardware_flag() -> None:
    meta = make_meta(video_codec="mpeg4", width=1280, height=720, pix_fmt="yuv420p")
    built = command(meta, vaapi_profile())
    assert built.path is EncodePath.CPU
    assert "-hwaccel" not in built.args
    assert not any("vaapi" in arg for arg in built.args)


def test_the_anamorphic_size_is_planned_from_the_display_picture() -> None:
    meta = make_meta(width=720, height=576, sample_aspect_ratio="16:15", fps=25.0)
    built = command(meta, CPUProfile())
    assert (built.width, built.height) == (720, 540)
    assert "scale=720:540:flags=bicubic,setsar=1" in built.args


def test_the_hybrid_arguments_use_the_profile_decode_flags_and_the_planned_size() -> None:
    meta = make_meta(width=3840, height=2160, fps=50.0, video_codec="hevc", pix_fmt="yuv420p")
    built = command(meta, vaapi_profile())
    assert built.path is EncodePath.HYBRID
    args = list(built.args)
    assert args[args.index("-vf") + 1].startswith("scale_vaapi=w=960:h=540:format=nv12,hwdownload")
    decode_flags = vaapi_profile().fragment(OpClass.DECODE, OpParams(render_node=NODE)).input_flags
    assert args[3 : 3 + len(decode_flags)] == list(decode_flags)


# --------------------------------------------------------------------------- #
# the ladder
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("meta", "profile", "expected"),
    [
        (make_meta(), vaapi_profile(), EncodePath.HYBRID),
        (make_meta(video_codec="hevc"), vaapi_profile(), EncodePath.HYBRID),
        (make_meta(rotation=0), vaapi_profile(), EncodePath.HYBRID),
        (make_meta(rotation=270), vaapi_profile(), EncodePath.CPU),
        (make_meta(rotation=90, video_codec="hevc"), vaapi_profile(), EncodePath.CPU),
        (make_meta(video_codec="mpeg4"), vaapi_profile(), EncodePath.CPU),
        (make_meta(video_codec="hevc", pix_fmt="yuv420p10le"), vaapi_profile(), EncodePath.CPU),
        (make_meta(is_hdr=True), vaapi_profile(), EncodePath.CPU),
        (make_meta(), CPUProfile(), EncodePath.CPU),
        (make_meta(), cuda_profile(), EncodePath.CPU),
        (make_meta(), vaapi_profile(hw_decode={}), EncodePath.CPU),
        (make_meta(), vaapi_profile(decode_method=None), EncodePath.CPU),
        (make_meta(pix_fmt="yuv422p"), vaapi_profile(), EncodePath.CPU),
    ],
    ids=[
        "h264",
        "hevc",
        "rotation-0",
        "rotation-270",
        "rotated-hevc",
        "mpeg4",
        "hevc-10bit",
        "hdr",
        "cpu-profile",
        "cuda-profile",
        "no-hw-decode-set",
        "decode-self-test-failed",
        "422-chroma",
    ],
)
def test_the_encode_ladder(meta: ClipMetadata, profile: AccelProfile, expected: EncodePath) -> None:
    assert plan_encode(meta, profile, render_node=NODE) is expected


def test_a_hardware_profile_whose_frames_have_no_verified_scale_filter_takes_the_cpu() -> None:
    profile = cuda_profile()
    assert profile.can_hw_decode("h264", "yuv420p")  # it does decode ...
    decode = profile.fragment(OpClass.DECODE, OpParams())
    assert decode.frames_out is FrameLocation.CUDA  # ... but its frames have no row in the table
    assert plan_encode(make_meta(), profile) is EncodePath.CPU


def test_a_hybrid_command_on_a_profile_without_a_scale_row_is_refused() -> None:
    with pytest.raises(ValueError, match="no verified hardware scale filter"):
        command(make_meta(), cuda_profile(), EncodePath.HYBRID)


# --------------------------------------------------------------------------- #
# native AAC, and no vendor in the module
# --------------------------------------------------------------------------- #

GOLDEN_CASES = [
    (make_meta(), vaapi_profile()),
    (make_meta(width=1280, height=720, fps=30.0, rotation=270), vaapi_profile()),
    (make_meta(fps=50.0), vaapi_profile()),
    (make_meta(fps=30000 / 1001), CPUProfile()),
    (make_meta(duration=0.48), CPUProfile()),
    (make_meta(is_hdr=True), CPUProfile()),
    (make_meta(video_codec="mpeg4", audio=AudioStream("mp3", 44100, 2, "stereo")), CPUProfile()),
    (make_meta(audio=AudioStream("ac3", 48000, 6, "5.1")), vaapi_profile()),
]


@pytest.mark.parametrize(("meta", "profile"), GOLDEN_CASES)
def test_the_audio_encoder_is_the_native_aac_whatever_the_host_offers(
    meta: ClipMetadata, profile: AccelProfile
) -> None:
    """The builder takes no encoder list: libfdk_aac is never reachable from it.

    The host's ffmpeg lists ``libfdk_aac`` as well (see the ffmpeg-backed check below); this
    fails if a code change ever names it, or any second ``-c:a``.
    """
    args = list(command(meta, profile).args)
    assert args.count("-c:a") == 1
    assert args[args.index("-c:a") + 1] == "aac"
    assert not any("fdk" in arg.lower() for arg in args)


@pytest.mark.has_ffmpeg
def test_the_native_aac_encoder_is_present_in_the_host_ffmpeg(runtime: object) -> None:
    listing = subprocess.run(
        [runtime.ffmpeg_path, "-hide_banner", "-encoders"],  # type: ignore[attr-defined]
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert any(line.split()[1:2] == ["aac"] for line in listing.splitlines() if line.strip())


def test_a_libfdk_selection_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spec, "PROXY_AUDIO_ENCODER", "libfdk_aac")
    args = list(command(make_meta(), CPUProfile()).args)
    assert any("fdk" in arg for arg in args)  # the check above would fail on this


def test_no_vendor_name_appears_in_the_proxies_package() -> None:
    package = Path(__file__).resolve().parents[1] / "auto_reel_ng" / "proxies"
    pattern = re.compile(r"amd|nvidia|intel|nvenc|qsv", re.IGNORECASE)
    offenders = [
        f"{path.name}:{number}: {line.strip()}"
        for path in package.glob("*.py")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert offenders == []


def test_no_subprocess_in_the_command_module() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "auto_reel_ng" / "proxies" / "command.py"
    ).read_text(encoding="utf-8")
    assert "subprocess" not in source


def test_command_is_a_frozen_value() -> None:
    built = command(make_meta(), CPUProfile())
    with pytest.raises(dataclasses.FrozenInstanceError):
        built.width = 1  # type: ignore[misc]
