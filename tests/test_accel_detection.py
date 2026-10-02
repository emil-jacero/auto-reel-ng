"""Capability detection: listing parsers + folding self-test results into flags."""

from __future__ import annotations

import pytest

from auto_reel_ng.accel.detection import (
    build_inventory,
    compute_accelerator,
    parse_codec_listing,
    parse_filter_listing,
    parse_hwaccel_listing,
)
from auto_reel_ng.accel.models import Device, OpStatus, Vendor

# A trimmed but realistic slice of `ffmpeg -encoders` output.
ENCODERS_TEXT = """Encoders:
 V..... = Video
 ------
 V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC
 V....D hevc_vaapi           H.265/HEVC (VAAPI)
 V....D h264_vaapi           H.264/AVC (VAAPI)
 V....D av1_vaapi            AV1 (VAAPI)
 A....D aac                  AAC (Advanced Audio Coding)
"""

FILTERS_TEXT = """Filters:
  T.. = Timeline support
 ... = stuff
 ... scale            V->V       Scale the input video
 ..C scale_vaapi      V->V       Scale to/from VAAPI surfaces
 ..C pad_vaapi        V->V       Pad the input video
 ..C overlay_vaapi    VV->V      Overlay one video on top of another
 TS overlay           VV->V      Overlay a video source on top of the input.
 .. tonemap_vaapi     V->V       VAAPI HDR to SDR tonemapping
"""

HWACCELS_TEXT = """Hardware acceleration methods:
vaapi
vdpau
"""


def test_inventory_reflects_ffmpeg_reported_encoder() -> None:
    """A host whose ffmpeg lists hevc_vaapi reports it as an available encoder."""
    encoders = parse_codec_listing(ENCODERS_TEXT)
    assert "hevc_vaapi" in encoders
    assert "libx264" in encoders
    assert "aac" in encoders
    assert "=" not in encoders  # the legend line is not mistaken for a codec


def test_parse_filter_and_hwaccel_listings() -> None:
    """Filter and hwaccel listings parse into clean name sets."""
    filters = parse_filter_listing(FILTERS_TEXT)
    # Covers both the 3-char (older) and 2-char (ffmpeg >= 8) flag-field layouts.
    assert {
        "scale",
        "scale_vaapi",
        "pad_vaapi",
        "overlay_vaapi",
        "overlay",
        "tonemap_vaapi",
    } <= filters
    hwaccels = parse_hwaccel_listing(HWACCELS_TEXT)
    assert hwaccels == frozenset({"vaapi", "vdpau"})


def test_compute_accelerator_reflects_verified_amd_reality() -> None:
    """AMD flags mirror exp 002-004: pad usable, no hw overlay/tonemap, all encoders."""
    selftest = {
        "amd.decode": OpStatus.WORKING,
        "amd.normalize": OpStatus.WORKING,
        "amd.overlay": OpStatus.UNSUPPORTED,
        "amd.tonemap": OpStatus.FAULTING,
        "amd.encode.h264": OpStatus.WORKING,
        "amd.encode.hevc": OpStatus.WORKING,
        "amd.encode.av1": OpStatus.WORKING,
    }
    device = Device(
        id="pci-0000:03:00.0",
        vendor=Vendor.AMD,
        name="RX 9070 XT",
        render_node="/dev/dri/renderD128",
    )
    caps = compute_accelerator(Vendor.AMD, device, selftest)

    assert caps.usable is True
    assert caps.pad_filter == "pad_vaapi"
    assert caps.can_overlay_hw is False
    assert caps.can_tonemap_hw is False
    assert caps.usable_encoders == {"h264": "h264_vaapi", "hevc": "hevc_vaapi", "av1": "av1_vaapi"}
    assert caps.decode_method == "vaapi"


def test_presence_without_pass_is_excluded() -> None:
    """An encoder that fails the self-test is not reported usable (presence != usable)."""
    selftest = {
        "amd.encode.h264": OpStatus.WORKING,
        "amd.encode.hevc": OpStatus.UNSUPPORTED,  # listed by ffmpeg, but failed the probe
    }
    caps = compute_accelerator(Vendor.AMD, None, selftest)
    assert caps.usable_encoders == {"h264": "h264_vaapi"}
    assert "hevc" not in caps.usable_encoders


def test_build_inventory_always_has_complete_cpu() -> None:
    """The CPU accelerator is always present, usable, and complete."""
    inventory = build_inventory(
        encoders=parse_codec_listing(ENCODERS_TEXT),
        decoders=frozenset(),
        hwaccels=parse_hwaccel_listing(HWACCELS_TEXT),
        filters=parse_filter_listing(FILTERS_TEXT),
        devices=(),
        selftest={},
        ffmpeg_version=(7, 1),
    )
    cpu = inventory.accelerator(Vendor.CPU)
    assert cpu is not None
    assert cpu.usable is True
    assert cpu.usable_encoders == {"h264": "libx264", "hevc": "libx265", "av1": "libsvtav1"}
    # With no devices and no self-test, the CPU is the only usable accelerator.
    assert inventory.usable_accelerators() == (cpu,)


def test_build_inventory_one_accelerator_per_vendor() -> None:
    """Two AMD render nodes collapse to a single AMD accelerator (+ CPU)."""
    devices = (
        Device(
            id="pci-0000:03:00.0", vendor=Vendor.AMD, name="dGPU", render_node="/dev/dri/renderD128"
        ),
        Device(
            id="pci-0000:0f:00.0", vendor=Vendor.AMD, name="iGPU", render_node="/dev/dri/renderD129"
        ),
    )
    inventory = build_inventory(
        encoders=frozenset(),
        decoders=frozenset(),
        hwaccels=frozenset(),
        filters=frozenset(),
        devices=devices,
        selftest={"amd.encode.h264": OpStatus.WORKING},
        ffmpeg_version=(7, 1),
    )
    amd_accels = [a for a in inventory.accelerators if a.vendor is Vendor.AMD]
    assert len(amd_accels) == 1
    # The accelerator keeps the first device of that vendor.
    assert amd_accels[0].device is not None
    assert amd_accels[0].device.id == "pci-0000:03:00.0"


def test_pad_fill_ok_follows_the_amd_fill_probe() -> None:
    """AMD's pad_fill_ok is the pad-fill probe's result; normalize stays usable either way."""
    base = {"amd.decode": OpStatus.WORKING, "amd.normalize": OpStatus.WORKING}

    faulty = compute_accelerator(Vendor.AMD, None, {**base, "amd.pad_fill": OpStatus.UNSUPPORTED})
    assert faulty.pad_fill_ok is False
    assert faulty.pad_filter == "pad_vaapi"

    missing = compute_accelerator(Vendor.AMD, None, base)
    assert missing.pad_fill_ok is False

    correct = compute_accelerator(Vendor.AMD, None, {**base, "amd.pad_fill": OpStatus.WORKING})
    assert correct.pad_fill_ok is True


def test_pad_fill_ok_is_true_for_cpu_pad_vendors() -> None:
    """NVIDIA and Intel pad with CPU ``pad`` inside their normalize, so the fill is trusted."""
    for vendor in (Vendor.NVIDIA, Vendor.INTEL):
        caps = compute_accelerator(vendor, None, {f"{vendor.value}.normalize": OpStatus.WORKING})
        assert caps.pad_fill_ok is True


def test_hw_decode_table_is_filled_when_the_decode_probe_works() -> None:
    """The per-vendor hardware-decodable codec set is recorded only on a passing decode."""
    amd = compute_accelerator(Vendor.AMD, None, {"amd.decode": OpStatus.WORKING})
    assert amd.hw_decode == {"h264": 8, "hevc": 10, "vp9": 10, "av1": 10}
    assert "mpeg4" not in amd.hw_decode  # reproduced failing on the RX 9070 XT
    for vendor in (Vendor.NVIDIA, Vendor.INTEL):
        caps = compute_accelerator(vendor, None, {f"{vendor.value}.decode": OpStatus.WORKING})
        assert caps.hw_decode["h264"] == 8
        assert caps.hw_decode["hevc"] == 10


@pytest.mark.parametrize("status", [OpStatus.UNSUPPORTED, OpStatus.FAULTING, None])
def test_hw_decode_is_empty_when_the_decode_probe_did_not_pass(status: object) -> None:
    """A host whose hardware decode failed (or never ran) records no hardware-decodable codec."""
    selftest = {} if status is None else {"amd.decode": status}
    caps = compute_accelerator(Vendor.AMD, None, selftest)  # type: ignore[arg-type]
    assert caps.decode_method is None
    assert not caps.hw_decode
