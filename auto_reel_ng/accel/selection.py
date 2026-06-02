"""Pick the acceleration profile for a render request (decision D-3 / D-4).

Auto-selection prefers a usable hardware accelerator over the CPU, ranking by how much
of the pipeline it covers on-GPU. An explicit override (a vendor name or a specific
enumerated device id) is honored or fails with a clear error. Each request also carries
a ``device`` selector that defaults to ``auto`` — v1 simply uses the first usable device
of the chosen vendor, with the field reserved for future multi-GPU targeting (D-4).
"""

from __future__ import annotations

import logging
from typing import Optional

from ..errors import AccelError
from .models import AcceleratorCapabilities, CapabilityInventory, Vendor
from .profiles import AccelProfile, CPUProfile, NvencProfile, QsvProfile, VaapiProfile

logger = logging.getLogger(__name__)

#: Hardware vendor -> the profile class that emits its fragments.
_PROFILE_CLASSES = {
    Vendor.AMD: VaapiProfile,
    Vendor.NVIDIA: NvencProfile,
    Vendor.INTEL: QsvProfile,
}

#: The literal default device selector (D-4 reserved field).
AUTO = "auto"


def select_profile(
    inventory: CapabilityInventory,
    *,
    override: Optional[str] = None,
    device: str = AUTO,
) -> AccelProfile:
    """Select an :class:`AccelProfile` for the inventory.

    Args:
        inventory: the detected, self-tested capabilities.
        override: force a specific accelerator by vendor name (``"amd"``/``"nvidia"``/
            ``"intel"``/``"cpu"``) or by enumerated device id. Unusable -> ``AccelError``.
        device: per-request device selector; ``"auto"`` (default) lets the engine pick a
            usable device, otherwise names a specific device id (also strict).

    Raises:
        AccelError: when an explicit ``override``/``device`` cannot be satisfied.
    """
    cpu = CPUProfile()

    if override is not None:
        return _resolve_explicit(inventory, override, cpu, what="override")
    if device != AUTO:
        return _resolve_explicit(inventory, device, cpu, what="device")

    return _auto_select(inventory, cpu)


def _auto_select(inventory: CapabilityInventory, cpu: CPUProfile) -> AccelProfile:
    """Auto-pick: best usable hardware accelerator, else the CPU profile."""
    hardware = [
        accel for accel in inventory.usable_accelerators() if accel.vendor is not Vendor.CPU
    ]
    if not hardware:
        logger.debug("No usable hardware accelerator; selecting CPU profile")
        return cpu
    best = max(hardware, key=_coverage_rank)
    logger.debug("Auto-selected %s accelerator", best.vendor.value)
    return _build_profile(best, cpu)


def _resolve_explicit(
    inventory: CapabilityInventory, selector: str, cpu: CPUProfile, *, what: str
) -> AccelProfile:
    """Resolve a vendor-name or device-id selector strictly, raising if unusable."""
    if selector == Vendor.CPU.value:
        return cpu

    # Vendor-name selector.
    vendor = _vendor_or_none(selector)
    if vendor is not None:
        accel = inventory.accelerator(vendor)
        if accel is None or not accel.usable:
            raise AccelError(
                f"{what} requested {selector!r} but no usable {selector} accelerator "
                f"was detected"
            )
        return _build_profile(accel, cpu)

    # Device-id selector.
    accel = _accelerator_for_device(inventory, selector)
    if accel is None:
        raise AccelError(f"{what} requested device {selector!r} but it is not a usable accelerator")
    return _build_profile(accel, cpu)


def _build_profile(accel: AcceleratorCapabilities, cpu: CPUProfile) -> AccelProfile:
    """Construct the vendor profile for ``accel``, sharing the CPU fallback."""
    if accel.vendor is Vendor.CPU:
        return cpu
    profile_class = _PROFILE_CLASSES[accel.vendor]
    return profile_class(accel, cpu)


def _coverage_rank(accel: AcceleratorCapabilities) -> tuple[int, int, str]:
    """Rank an accelerator by how much of the pipeline it covers on-GPU.

    More usable hardware encoders ranks higher, then native decode/normalize, with the
    vendor name as a stable final tiebreak (the cross-vendor rank is an open question
    on the single-vendor dev host).
    """
    coverage = (
        len(accel.usable_encoders)
        + (1 if accel.decode_method else 0)
        + (1 if accel.pad_filter else 0)
    )
    return (coverage, len(accel.usable_encoders), accel.vendor.value)


def _vendor_or_none(name: str) -> Optional[Vendor]:
    """Return the :class:`Vendor` for a name, or None if it is not a vendor name."""
    try:
        return Vendor(name)
    except ValueError:
        return None


def _accelerator_for_device(
    inventory: CapabilityInventory, device_id: str
) -> Optional[AcceleratorCapabilities]:
    """Find the usable accelerator whose device matches ``device_id``, else None."""
    for accel in inventory.usable_accelerators():
        if accel.device is not None and accel.device.id == device_id:
            return accel
    return None
