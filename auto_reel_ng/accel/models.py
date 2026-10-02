"""Typed, immutable models for the acceleration layer.

These mirror the ``capability-detection`` and ``acceleration-profile`` specs one-to-one.
Everything here is frozen so a detected inventory can be cached and shared across threads
without anyone mutating it, and each model carries a ``to_dict()`` for structured logging.

The guiding rule (locked by the hardware spikes in ``experiments/002-004``) is *assume
nothing*: a capability is only ever marked usable after the self-test confirms it, never
from ffmpeg's listing alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional


class Vendor(str, Enum):
    """The accelerator vendors the engine knows how to emit fragments for."""

    AMD = "amd"
    NVIDIA = "nvidia"
    INTEL = "intel"
    CPU = "cpu"


class OpClass(str, Enum):
    """The logical render operations a profile emits fragments for."""

    DECODE = "decode"
    NORMALIZE = "normalize"  # scale + letterbox/pillarbox pad to a common canvas
    OVERLAY = "overlay"
    TONEMAP = "tonemap"  # HDR -> SDR
    ENCODE = "encode"


class FrameLocation(str, Enum):
    """Where an operation's frames live: system memory or a hardware frame context.

    The composer (change #4) inserts an ``hwdownload``/``hwupload`` only where two
    adjacent operations disagree on this; see :func:`auto_reel_ng.accel.profiles`.
    """

    SYSTEM = "system"
    VAAPI = "vaapi"
    CUDA = "cuda"
    QSV = "qsv"


class OpStatus(str, Enum):
    """Self-test classification of a single candidate operation.

    * ``WORKING`` — ran clean (exit 0) and produced the expected output.
    * ``UNSUPPORTED`` — a clean ffmpeg/driver rejection (non-zero exit, e.g. AMD's
      ``overlay_vaapi`` "not supported").
    * ``FAULTING`` — a crash, signal kill, or hang (e.g. ``tonemap_opencl`` faulting
      the GPU). Contained in a child process; recorded, never fatal.
    """

    WORKING = "working"
    UNSUPPORTED = "unsupported"
    FAULTING = "faulting"


#: PCI vendor ids (``/sys/class/drm/renderD*/device/vendor``) -> engine vendor.
PCI_VENDOR_IDS: Mapping[str, Vendor] = {
    "0x1002": Vendor.AMD,
    "0x10de": Vendor.NVIDIA,
    "0x8086": Vendor.INTEL,
}


@dataclass(frozen=True)
class Device:
    """One enumerated accelerator device.

    ``id`` is derived from a stable attribute (PCI address where available) so it
    survives ``renderD12N`` renumbering across reboots; ``render_node`` is the DRM
    path (``/dev/dri/renderD128``) when the device is a render node, else ``None``.
    """

    id: str
    vendor: Vendor
    name: str
    render_node: Optional[str]

    def to_dict(self) -> dict[str, Optional[str]]:
        """Plain-dict view for logging."""
        return {
            "id": self.id,
            "vendor": self.vendor.value,
            "name": self.name,
            "render_node": self.render_node,
        }


@dataclass(frozen=True)
class AcceleratorCapabilities:  # pylint: disable=too-many-instance-attributes
    """Per-accelerator capability flags, every value reflecting the self-test result.

    These are exactly the flags later stages consume to decide fallbacks: which pad
    filter to use, whether overlay/tonemap can run on the GPU, which hardware encoders
    are usable per codec, and how to decode.
    """

    vendor: Vendor
    usable: bool
    device: Optional[Device]
    pad_filter: Optional[str]
    can_overlay_hw: bool
    can_tonemap_hw: bool
    #: codec name (``"h264"``/``"hevc"``/``"av1"``) -> usable hardware encoder.
    usable_encoders: Mapping[str, str] = field(default_factory=dict)
    #: ffmpeg ``-hwaccel`` value for hardware decode, or ``None`` for software decode.
    decode_method: Optional[str] = None
    #: Whether this accelerator's pad fills with the requested colour. Measured for
    #: ``pad_vaapi`` (exp 006: Mesa paints green); true for CPU ``pad``-based vendors.
    pad_fill_ok: bool = True
    #: source codec name (``"h264"``/``"hevc"``/...) -> the highest bit depth its hardware
    #: decoder handles. Empty when hardware decode did not pass the self-test; the codec
    #: set is a static per-vendor table, only kept when the decode probe worked.
    hw_decode: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Plain-dict view for logging."""
        return {
            "vendor": self.vendor.value,
            "usable": self.usable,
            "device": self.device.to_dict() if self.device else None,
            "pad_filter": self.pad_filter,
            "can_overlay_hw": self.can_overlay_hw,
            "can_tonemap_hw": self.can_tonemap_hw,
            "usable_encoders": dict(self.usable_encoders),
            "decode_method": self.decode_method,
            "pad_fill_ok": self.pad_fill_ok,
            "hw_decode": dict(self.hw_decode),
        }


@dataclass(frozen=True)
class CapabilityInventory:  # pylint: disable=too-many-instance-attributes
    """The full, self-tested capability picture of the host.

    Combines ffmpeg's reported capabilities (the ``*`` listings) with enumerated
    devices and the per-accelerator flags computed from the self-test.
    """

    encoders: frozenset[str]
    decoders: frozenset[str]
    hwaccels: frozenset[str]
    filters: frozenset[str]
    devices: tuple[Device, ...]
    accelerators: tuple[AcceleratorCapabilities, ...]
    #: Raw self-test results keyed by probe key (e.g. ``"amd.normalize"``).
    selftest: Mapping[str, OpStatus] = field(default_factory=dict)
    #: ffmpeg ``(major, minor)`` version, part of the cache fingerprint.
    ffmpeg_version: tuple[int, int] = (0, 0)

    def accelerator(self, vendor: Vendor) -> Optional[AcceleratorCapabilities]:
        """Return the capabilities for ``vendor``, or ``None`` if not present."""
        for accel in self.accelerators:
            if accel.vendor is vendor:
                return accel
        return None

    def usable_accelerators(self) -> tuple[AcceleratorCapabilities, ...]:
        """Return only the accelerators that passed the self-test."""
        return tuple(a for a in self.accelerators if a.usable)

    def to_dict(self) -> dict[str, object]:
        """Plain-dict view for logging (listings rendered as sorted lists)."""
        return {
            "encoders": sorted(self.encoders),
            "decoders": sorted(self.decoders),
            "hwaccels": sorted(self.hwaccels),
            "filters": sorted(self.filters),
            "devices": [d.to_dict() for d in self.devices],
            "accelerators": [a.to_dict() for a in self.accelerators],
            "selftest": {k: v.value for k, v in self.selftest.items()},
            "ffmpeg_version": list(self.ffmpeg_version),
        }


@dataclass(frozen=True)
class OpFragment:
    """The ffmpeg argument fragments for one logical operation.

    A fragment is *data*, not a command: profiles return it and the render change (#4)
    composes the fragments into a full ffmpeg invocation. Each fragment also declares
    where its frames live before and after, so transfers can be inserted explicitly.
    """

    op: OpClass
    #: Input-side flags, e.g. ``("-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi")``.
    input_flags: tuple[str, ...] = ()
    #: A ``-filter`` snippet for this op, e.g. ``"scale_vaapi=w=1920:h=1080,pad_vaapi=..."``.
    filter: Optional[str] = None
    #: Output/encoder flags, e.g. ``("-c:v", "hevc_vaapi")``.
    output_flags: tuple[str, ...] = ()
    frames_in: FrameLocation = FrameLocation.SYSTEM
    frames_out: FrameLocation = FrameLocation.SYSTEM

    def to_dict(self) -> dict[str, object]:
        """Plain-dict view for logging and golden-test comparison."""
        return {
            "op": self.op.value,
            "input_flags": list(self.input_flags),
            "filter": self.filter,
            "output_flags": list(self.output_flags),
            "frames_in": self.frames_in.value,
            "frames_out": self.frames_out.value,
        }


@dataclass(frozen=True)
class TransferMarker:
    """An ``hwdownload``/``hwupload`` round-trip inserted between two operations.

    Emitted by :func:`auto_reel_ng.accel.profiles.insert_transfers` wherever an
    operation's output frame location does not match the next operation's input.
    """

    filter: str  # "hwdownload" or "hwupload"
    frames_in: FrameLocation
    frames_out: FrameLocation

    def to_dict(self) -> dict[str, str]:
        """Plain-dict view for logging."""
        return {
            "filter": self.filter,
            "frames_in": self.frames_in.value,
            "frames_out": self.frames_out.value,
        }


@dataclass(frozen=True)
class OpParams:
    """Inputs a caller passes when asking a profile for a fragment.

    All fields are optional; an op uses only what it needs (``NORMALIZE`` reads the
    target resolution, ``ENCODE`` reads the codec, hardware ops read ``render_node``).
    """

    width: Optional[int] = None
    height: Optional[int] = None
    codec: Optional[str] = None  # "h264" / "hevc" / "av1"
    render_node: Optional[str] = None
    fill_color: str = "black"
    #: ``NORMALIZE`` only: the clip's pixel or display aspect differs from the canvas, so
    #: the normalize must pad. Stated by ``render/`` as a geometric fact about the clip.
    needs_pad: bool = False
    #: ``DECODE`` only: decode in software even where the profile has a hardware decoder,
    #: because the clip is not hardware-decodable (or its hardware decode just failed).
    software_decode: bool = False
