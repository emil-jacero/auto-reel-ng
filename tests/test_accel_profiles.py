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
from auto_reel_ng.accel.profiles import (
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
    )


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
