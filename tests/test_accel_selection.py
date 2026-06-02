"""Selection: auto-pick hardware over CPU, honor/ reject overrides, default device."""

from __future__ import annotations

import pytest

from auto_reel_ng.accel import select_profile
from auto_reel_ng.accel.detection import build_inventory
from auto_reel_ng.accel.models import Device, OpStatus, Vendor
from auto_reel_ng.accel.profiles import CPUProfile, VaapiProfile
from auto_reel_ng.errors import AccelError

_AMD_DEVICE = Device(
    id="pci-0000:03:00.0", vendor=Vendor.AMD, name="RX 9070 XT", render_node="/dev/dri/renderD128"
)

_AMD_SELFTEST = {
    "amd.decode": OpStatus.WORKING,
    "amd.normalize": OpStatus.WORKING,
    "amd.encode.h264": OpStatus.WORKING,
    "amd.encode.hevc": OpStatus.WORKING,
    "amd.encode.av1": OpStatus.WORKING,
}


def _amd_inventory():
    return build_inventory(
        encoders=frozenset(),
        decoders=frozenset(),
        hwaccels=frozenset(),
        filters=frozenset(),
        devices=(_AMD_DEVICE,),
        selftest=_AMD_SELFTEST,
        ffmpeg_version=(7, 1),
    )


def _cpu_only_inventory():
    return build_inventory(
        encoders=frozenset(),
        decoders=frozenset(),
        hwaccels=frozenset(),
        filters=frozenset(),
        devices=(),
        selftest={},
        ffmpeg_version=(7, 1),
    )


def test_auto_picks_hardware_over_cpu() -> None:
    """With a usable AMD accelerator and no override, the hardware profile is chosen."""
    profile = select_profile(_amd_inventory())
    assert isinstance(profile, VaapiProfile)
    assert profile.vendor is Vendor.AMD


def test_cpu_only_host_yields_cpu_profile() -> None:
    """No usable hardware -> the complete CPU profile."""
    profile = select_profile(_cpu_only_inventory())
    assert isinstance(profile, CPUProfile)


def test_default_selector_requires_no_input() -> None:
    """The default device selector is auto and needs no caller argument."""
    # Calling with no override/device keyword still resolves a usable device.
    profile = select_profile(_amd_inventory())
    assert isinstance(profile, VaapiProfile)
    assert profile.capabilities.device == _AMD_DEVICE


def test_override_vendor_honored() -> None:
    assert isinstance(select_profile(_amd_inventory(), override="amd"), VaapiProfile)
    assert isinstance(select_profile(_amd_inventory(), override="cpu"), CPUProfile)


def test_override_unusable_vendor_raises() -> None:
    """Overriding to a vendor that is not usable fails with a clear error."""
    with pytest.raises(AccelError) as excinfo:
        select_profile(_amd_inventory(), override="nvidia")
    assert "nvidia" in str(excinfo.value)


def test_override_device_id_resolves_and_rejects() -> None:
    """A device-id override resolves a usable device, or fails clearly when unknown."""
    profile = select_profile(_amd_inventory(), override="pci-0000:03:00.0")
    assert isinstance(profile, VaapiProfile)
    with pytest.raises(AccelError):
        select_profile(_amd_inventory(), override="pci-0000:de:ad.0")


def test_device_selector_strict_when_named() -> None:
    """A named (non-auto) device selector resolves it, else fails clearly."""
    assert isinstance(select_profile(_amd_inventory(), device="pci-0000:03:00.0"), VaapiProfile)
    with pytest.raises(AccelError):
        select_profile(_amd_inventory(), device="pci-0000:de:ad.0")
