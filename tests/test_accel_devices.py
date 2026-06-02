"""Device enumeration: render nodes -> devices, with graceful optional-tool absence."""

from __future__ import annotations

import pytest

from auto_reel_ng.accel import devices as dev
from auto_reel_ng.accel.models import Vendor


def test_two_render_nodes_two_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two render nodes backed by different GPUs enumerate as two distinct devices."""
    monkeypatch.setattr(
        dev,
        "render_nodes",
        lambda dri_dir=dev.DEFAULT_DRI_DIR: ["/dev/dri/renderD128", "/dev/dri/renderD129"],
    )
    vendors = {"renderD128": Vendor.AMD, "renderD129": Vendor.NVIDIA}
    addresses = {"renderD128": "0000:03:00.0", "renderD129": "0000:0f:00.0"}
    monkeypatch.setattr(
        dev, "pci_vendor", lambda node, sysfs_drm=dev.DEFAULT_SYSFS_DRM: vendors[node]
    )
    monkeypatch.setattr(
        dev, "pci_address", lambda node, sysfs_drm=dev.DEFAULT_SYSFS_DRM: addresses[node]
    )
    monkeypatch.setattr(dev, "vainfo_name", lambda node: None)
    monkeypatch.setattr(dev, "_nvidia_names", lambda: ["NVIDIA GeForce RTX 4090"])

    result = dev.enumerate_devices()

    assert len(result) == 2
    assert {d.vendor for d in result} == {Vendor.AMD, Vendor.NVIDIA}
    assert {d.id for d in result} == {"pci-0000:03:00.0", "pci-0000:0f:00.0"}
    assert [d.render_node for d in result] == ["/dev/dri/renderD128", "/dev/dri/renderD129"]
    nvidia = next(d for d in result if d.vendor is Vendor.NVIDIA)
    assert nvidia.name == "NVIDIA GeForce RTX 4090"


def test_missing_nvidia_smi_still_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing nvidia-smi (no names) does not stop enumeration of present devices."""
    monkeypatch.setattr(
        dev, "render_nodes", lambda dri_dir=dev.DEFAULT_DRI_DIR: ["/dev/dri/renderD128"]
    )
    monkeypatch.setattr(dev, "pci_vendor", lambda node, sysfs_drm=dev.DEFAULT_SYSFS_DRM: Vendor.AMD)
    monkeypatch.setattr(
        dev, "pci_address", lambda node, sysfs_drm=dev.DEFAULT_SYSFS_DRM: "0000:03:00.0"
    )
    monkeypatch.setattr(dev, "vainfo_name", lambda node: None)
    # Simulate nvidia-smi absent: the helper returns [].
    monkeypatch.setattr(dev, "_nvidia_names", lambda: [])

    result = dev.enumerate_devices()

    assert len(result) == 1
    assert result[0].vendor is Vendor.AMD
    # Falls back to the vendor display name when no tool named it.
    assert result[0].name == "AMD GPU"


def test_unknown_vendor_node_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A render node whose PCI vendor cannot be classified is skipped, not fatal."""
    monkeypatch.setattr(
        dev, "render_nodes", lambda dri_dir=dev.DEFAULT_DRI_DIR: ["/dev/dri/renderD200"]
    )
    monkeypatch.setattr(dev, "pci_vendor", lambda node, sysfs_drm=dev.DEFAULT_SYSFS_DRM: None)
    monkeypatch.setattr(dev, "pci_address", lambda node, sysfs_drm=dev.DEFAULT_SYSFS_DRM: None)
    monkeypatch.setattr(dev, "vainfo_name", lambda node: None)
    monkeypatch.setattr(dev, "_nvidia_names", lambda: [])

    assert dev.enumerate_devices() == []


def test_no_render_dir_returns_empty(tmp_path) -> None:
    """A host with no /dev/dri returns no devices rather than raising."""
    assert dev.render_nodes(str(tmp_path / "missing")) == []
