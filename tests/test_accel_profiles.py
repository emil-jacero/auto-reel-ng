"""Golden-fragment tests (no GPU needed) + frame-location transfer insertion."""

from __future__ import annotations

import dataclasses

import pytest

from auto_reel_ng.accel.models import (
    AcceleratorCapabilities,
    Device,
    FrameLocation,
    OpClass,
    OpFragment,
    OpParams,
    TransferMarker,
    Vendor,
)
from auto_reel_ng.accel.pixfmt import pix_fmt_traits
from auto_reel_ng.accel.profiles import (
    AccelProfile,
    CPUProfile,
    NvencProfile,
    QsvProfile,
    VaapiProfile,
    insert_transfers,
    needs_transfer,
)
from auto_reel_ng.accel.profiles.cpu import CPU_TONEMAP_FILTER

HD = OpParams(width=1920, height=1080, codec="hevc")


def _amd_caps() -> AcceleratorCapabilities:
    return AcceleratorCapabilities(
        vendor=Vendor.AMD,
        usable=True,
        device=Device(
            id="pci-0000:03:00.0",
            vendor=Vendor.AMD,
            name="RX 9070 XT",
            render_node="/dev/dri/renderD128",
        ),
        pad_filter="pad_vaapi",
        can_overlay_hw=False,
        can_tonemap_hw=False,
        usable_encoders={"h264": "h264_vaapi", "hevc": "hevc_vaapi", "av1": "av1_vaapi"},
        decode_method="vaapi",
        hw_decode={"h264": 8, "hevc": 10},
    )


def _caps_for(vendor: Vendor, method: str, **overrides: object) -> AcceleratorCapabilities:
    """Hardware capabilities for ``vendor`` with a decoder set of h264 8-bit and hevc 10-bit."""
    values: dict[str, object] = {
        "vendor": vendor,
        "usable": True,
        "device": None,
        "pad_filter": "pad",
        "can_overlay_hw": False,
        "can_tonemap_hw": False,
        "usable_encoders": {"h264": "x"},
        "decode_method": method,
        "hw_decode": {"h264": 8, "hevc": 10},
    }
    values.update(overrides)
    return AcceleratorCapabilities(**values)  # type: ignore[arg-type]


# -- CPU profile -------------------------------------------------------------


def test_cpu_normalize_fragment() -> None:
    frag = CPUProfile().fragment(OpClass.NORMALIZE, HD)
    assert frag.filter == (
        "scale=w=1920:h=1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    )
    assert frag.frames_in is FrameLocation.SYSTEM
    assert frag.frames_out is FrameLocation.SYSTEM


def test_cpu_tonemap_and_overlay_and_encode() -> None:
    cpu = CPUProfile()
    assert cpu.fragment(OpClass.TONEMAP, HD).filter == CPU_TONEMAP_FILTER
    assert cpu.fragment(OpClass.OVERLAY, HD).filter == "overlay"
    assert cpu.fragment(OpClass.ENCODE, OpParams(codec="hevc")).output_flags == ("-c:v", "libx265")
    assert cpu.fragment(OpClass.ENCODE, OpParams(codec="av1")).output_flags == ("-c:v", "libsvtav1")


def test_cpu_profile_supplies_every_op() -> None:
    """CPU-only host: a working fragment for decode, normalize, overlay, tonemap, encode."""
    cpu = CPUProfile()
    for op in OpClass:
        assert isinstance(cpu.fragment(op, HD), OpFragment)


# -- AMD VAAPI profile -------------------------------------------------------


def test_amd_normalize_uses_native_scale_pad() -> None:
    """A clip needing bars, with a correct hardware fill, uses scale_vaapi+pad_vaapi."""
    params = dataclasses.replace(HD, needs_pad=True)
    frag = VaapiProfile(_amd_caps()).fragment(OpClass.NORMALIZE, params)
    assert frag.filter == (
        "scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease,"
        "pad_vaapi=w=1920:h=1080:x=(ow-iw)/2:y=(oh-ih)/2:color=black"
    )
    assert frag.frames_in is FrameLocation.VAAPI
    assert frag.frames_out is FrameLocation.VAAPI


@pytest.mark.parametrize("pad_fill_ok", [True, False])
def test_amd_normalize_without_bars_is_scale_vaapi_alone(pad_fill_ok: bool) -> None:
    """An exact-aspect clip fills the canvas: scale_vaapi alone, whatever the fill flag."""
    caps = dataclasses.replace(_amd_caps(), pad_fill_ok=pad_fill_ok)
    frag = VaapiProfile(caps).fragment(OpClass.NORMALIZE, HD)
    assert frag.filter == "scale_vaapi=w=1920:h=1080:force_original_aspect_ratio=decrease"
    assert frag.frames_in is FrameLocation.VAAPI
    assert frag.frames_out is FrameLocation.VAAPI


def test_amd_normalize_with_faulty_fill_falls_back_to_cpu_pad() -> None:
    """A clip needing bars on a host whose pad_vaapi ignores its colour pads on the CPU."""
    caps = dataclasses.replace(_amd_caps(), pad_fill_ok=False)
    params = dataclasses.replace(HD, needs_pad=True)
    frag = VaapiProfile(caps).fragment(OpClass.NORMALIZE, params)
    assert frag == CPUProfile().fragment(OpClass.NORMALIZE, params)
    assert frag.frames_in is FrameLocation.SYSTEM


def test_amd_decode_and_encode_fragments() -> None:
    profile = VaapiProfile(_amd_caps())
    decode = profile.fragment(OpClass.DECODE, HD)
    assert decode.input_flags == (
        "-init_hw_device",
        "vaapi=va:/dev/dri/renderD128",
        "-filter_hw_device",
        "va",
        "-hwaccel",
        "vaapi",
        "-hwaccel_device",
        "va",
        "-hwaccel_output_format",
        "vaapi",
    )
    assert decode.frames_out is FrameLocation.VAAPI

    encode = profile.fragment(OpClass.ENCODE, OpParams(codec="hevc"))
    assert encode.output_flags == ("-c:v", "hevc_vaapi")
    assert encode.frames_in is FrameLocation.VAAPI
    assert encode.frames_out is FrameLocation.SYSTEM


def test_amd_overlay_and_tonemap_fall_back_to_cpu() -> None:
    """overlay_vaapi unsupported + no GPU tonemap on AMD -> CPU fragments."""
    profile = VaapiProfile(_amd_caps())
    assert profile.fragment(OpClass.OVERLAY, HD).filter == "overlay"
    assert profile.fragment(OpClass.TONEMAP, HD).filter == CPU_TONEMAP_FILTER
    # Frames are back in system memory for the fallback ops.
    assert profile.fragment(OpClass.TONEMAP, HD).frames_out is FrameLocation.SYSTEM


def test_amd_unusable_encoder_falls_back_to_cpu() -> None:
    """A codec without a usable VAAPI encoder falls back to the CPU encoder."""
    caps = _amd_caps()
    profile = VaapiProfile(
        AcceleratorCapabilities(
            vendor=caps.vendor,
            usable=True,
            device=caps.device,
            pad_filter="pad_vaapi",
            can_overlay_hw=False,
            can_tonemap_hw=False,
            usable_encoders={"h264": "h264_vaapi"},
            decode_method="vaapi",
        )
    )
    frag = profile.fragment(OpClass.ENCODE, OpParams(codec="av1"))
    assert frag.output_flags == ("-c:v", "libsvtav1")
    assert frag.frames_in is FrameLocation.SYSTEM


# -- NVIDIA / Intel best-guess profiles --------------------------------------


def test_nvidia_fragments() -> None:
    caps = AcceleratorCapabilities(
        vendor=Vendor.NVIDIA,
        usable=True,
        device=None,
        pad_filter="pad",
        can_overlay_hw=True,
        can_tonemap_hw=False,
        usable_encoders={"h264": "h264_nvenc"},
        decode_method="cuda",
    )
    profile = NvencProfile(caps)
    assert profile.fragment(OpClass.DECODE, HD).input_flags == (
        "-hwaccel",
        "cuda",
        "-hwaccel_output_format",
        "cuda",
    )
    assert profile.fragment(OpClass.NORMALIZE, HD).filter == (
        "scale_cuda=w=1920:h=1080:force_original_aspect_ratio=decrease,"
        "hwdownload,format=nv12,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    )
    assert profile.fragment(OpClass.OVERLAY, HD).filter == "overlay_cuda"
    assert profile.fragment(OpClass.ENCODE, OpParams(codec="h264")).output_flags == (
        "-c:v",
        "h264_nvenc",
    )


def test_intel_fragments() -> None:
    caps = AcceleratorCapabilities(
        vendor=Vendor.INTEL,
        usable=True,
        device=None,
        pad_filter="pad",
        can_overlay_hw=False,
        can_tonemap_hw=False,
        usable_encoders={"hevc": "hevc_qsv"},
        decode_method="qsv",
    )
    profile = QsvProfile(caps)
    assert profile.fragment(OpClass.NORMALIZE, HD).filter == (
        "vpp_qsv=w=1920:h=1080,hwdownload,format=nv12,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    )
    encode = profile.fragment(OpClass.ENCODE, OpParams(codec="hevc"))
    assert encode.output_flags == ("-c:v", "hevc_qsv")
    assert encode.frames_in is FrameLocation.QSV


# -- per-clip hardware decode choice -----------------------------------------


@pytest.mark.parametrize(
    ("pix_fmt", "expected"),
    [
        ("yuv420p", (8, True)),
        ("yuvj420p", (8, True)),
        ("nv12", (8, True)),
        ("yuv420p10le", (10, True)),
        ("p010le", (10, True)),
        ("yuv422p", (8, False)),
        ("yuv444p10le", (10, False)),
        ("gray", None),
        ("rgb24", None),
    ],
)
def test_pix_fmt_traits(pix_fmt: str, expected: object) -> None:
    """Bit depth and 4:2:0-ness come from the format name; an unknown format is unknown."""
    assert pix_fmt_traits(pix_fmt) == expected


def _profiles() -> list[AccelProfile]:
    return [
        VaapiProfile(_amd_caps()),
        NvencProfile(_caps_for(Vendor.NVIDIA, "cuda")),
        QsvProfile(_caps_for(Vendor.INTEL, "qsv")),
    ]


@pytest.mark.parametrize("profile", _profiles(), ids=lambda p: p.vendor.value)
@pytest.mark.parametrize(
    ("codec", "pix_fmt", "expected"),
    [
        ("mpeg4", "yuv420p", False),  # codec not in the decoder set
        ("h264", "yuv420p", True),
        ("h264", "yuvj420p", True),
        ("h264", "yuv420p10le", False),  # deeper than the h264 limit of 8
        ("hevc", "yuv420p10le", True),  # exactly the hevc limit
        ("hevc", "yuv420p12le", False),
        ("h264", "yuv422p", False),  # not 4:2:0 whatever the table says
        ("hevc", "yuv444p10le", False),
        ("h264", "gray", False),  # unrecognised format: software is always correct
        ("h264", None, True),  # no pix_fmt reported: codec alone, nothing invented
        ("mpeg4", None, False),
    ],
)
def test_hardware_profiles_decide_hw_decode_per_clip(
    profile: AccelProfile, codec: str, pix_fmt: object, expected: bool
) -> None:
    assert profile.can_hw_decode(codec, pix_fmt) is expected  # type: ignore[arg-type]


def test_hw_decode_is_false_when_the_decode_self_test_failed() -> None:
    """No decode_method (the probe did not pass) -> nothing is hardware-decodable."""
    failed = VaapiProfile(dataclasses.replace(_amd_caps(), decode_method=None, hw_decode={}))
    assert failed.can_hw_decode("h264", "yuv420p") is False
    # A stale non-empty set is still ignored without a passing probe.
    stale = VaapiProfile(dataclasses.replace(_amd_caps(), decode_method=None))
    assert stale.can_hw_decode("h264", "yuv420p") is False
    assert stale.fragment(OpClass.DECODE, HD) == CPUProfile().fragment(OpClass.DECODE, HD)


def test_cpu_profile_never_hw_decodes() -> None:
    assert CPUProfile().can_hw_decode("h264", "yuv420p") is False
    assert CPUProfile().can_hw_decode("h264", None) is False


@pytest.mark.parametrize("profile", _profiles(), ids=lambda p: p.vendor.value)
def test_software_decode_param_yields_the_cpu_decode_fragment(profile: AccelProfile) -> None:
    """software_decode=True -> no hardware flags, system frames; unset keeps the hardware one."""
    soft = profile.fragment(OpClass.DECODE, dataclasses.replace(HD, software_decode=True))
    assert soft == OpFragment(op=OpClass.DECODE)
    assert soft.frames_out is FrameLocation.SYSTEM
    hard = profile.fragment(OpClass.DECODE, HD)
    assert hard.input_flags and hard.frames_out is not FrameLocation.SYSTEM


def test_software_decode_leaves_other_ops_alone() -> None:
    """The flag only concerns DECODE: normalize stays the hardware fragment."""
    profile = VaapiProfile(_amd_caps())
    params = dataclasses.replace(HD, software_decode=True)
    assert profile.fragment(OpClass.NORMALIZE, params) == profile.fragment(OpClass.NORMALIZE, HD)


# -- frame-location tracking & transfer insertion ----------------------------


def test_needs_transfer_directions() -> None:
    assert needs_transfer(FrameLocation.VAAPI, FrameLocation.SYSTEM) == "hwdownload"
    assert needs_transfer(FrameLocation.SYSTEM, FrameLocation.VAAPI) == "hwupload"
    assert needs_transfer(FrameLocation.VAAPI, FrameLocation.VAAPI) is None
    assert needs_transfer(FrameLocation.SYSTEM, FrameLocation.SYSTEM) is None


def test_insert_transfers_marks_mixed_chain() -> None:
    """A VAAPI decode/normalize -> CPU tonemap -> VAAPI encode chain gets two markers."""
    profile = VaapiProfile(_amd_caps())
    chain = [
        profile.fragment(OpClass.DECODE, HD),
        profile.fragment(OpClass.NORMALIZE, HD),
        profile.fragment(OpClass.TONEMAP, HD),  # CPU fallback -> system frames
        profile.fragment(OpClass.ENCODE, OpParams(codec="hevc")),
    ]
    planned = insert_transfers(chain)

    kinds = [item.filter if isinstance(item, TransferMarker) else item.op.value for item in planned]
    assert kinds == [
        "decode",
        "normalize",
        "hwdownload",  # vaapi normalize -> system tonemap
        "tonemap",
        "hwupload",  # system tonemap -> vaapi encode
        "encode",
    ]


def test_insert_transfers_no_markers_when_aligned() -> None:
    """An all-system CPU chain needs no transfer markers."""
    cpu = CPUProfile()
    chain = [
        cpu.fragment(OpClass.NORMALIZE, HD),
        cpu.fragment(OpClass.ENCODE, OpParams(codec="hevc")),
    ]
    planned = insert_transfers(chain)
    assert all(isinstance(item, OpFragment) for item in planned)
    assert len(planned) == 2
