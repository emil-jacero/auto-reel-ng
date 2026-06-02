"""Acceleration layer: probe what the host can really do, then emit the right fragments.

This package turns the raw capability text from :class:`FfmpegRuntime` into a usable
acceleration-profile API for the render pipeline (change #4):

- :func:`detect_capabilities` builds a self-tested :class:`CapabilityInventory` — ffmpeg's
  listings + enumerated devices + an empirical self-test that classifies each candidate op
  as working / unsupported / faulting, so only ops that *actually* run are reported usable.
- :func:`select_profile` picks the best usable accelerator (hardware over CPU) with an
  optional vendor/device override, returning an :class:`AccelProfile`.
- The profile classes (:class:`CPUProfile`, :class:`VaapiProfile`, :class:`NvencProfile`,
  :class:`QsvProfile`) emit per-op :class:`OpFragment`\\ s with frame-location tracking and
  a guaranteed CPU fallback.

The guiding rule, locked by ``experiments/002-004``: assume nothing, verify everything.
"""

from __future__ import annotations

from ..errors import AccelError
from .detection import build_inventory, clear_cache, detect_capabilities
from .devices import enumerate_devices
from .models import (
    AcceleratorCapabilities,
    CapabilityInventory,
    Device,
    FrameLocation,
    OpClass,
    OpFragment,
    OpParams,
    OpStatus,
    TransferMarker,
    Vendor,
)
from .profiles import (
    AccelProfile,
    CPUProfile,
    NvencProfile,
    QsvProfile,
    VaapiProfile,
    insert_transfers,
    needs_transfer,
)
from .selection import select_profile

__all__ = [
    # detection & selection
    "detect_capabilities",
    "select_profile",
    "build_inventory",
    "enumerate_devices",
    "clear_cache",
    # profiles
    "AccelProfile",
    "CPUProfile",
    "VaapiProfile",
    "NvencProfile",
    "QsvProfile",
    "insert_transfers",
    "needs_transfer",
    # models
    "CapabilityInventory",
    "AcceleratorCapabilities",
    "Device",
    "OpFragment",
    "OpParams",
    "TransferMarker",
    "OpClass",
    "FrameLocation",
    "OpStatus",
    "Vendor",
    # errors
    "AccelError",
]
