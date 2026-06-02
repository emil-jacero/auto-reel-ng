"""Enumerate accelerator devices from the system, degrading gracefully.

The base source is the set of DRM render nodes (``/dev/dri/renderD*``); each is
classified by its PCI vendor id from sysfs, given a stable id from its PCI address
(so it survives ``renderD12N`` renumbering across reboots), and named. Optional tools
enrich the picture and their absence is never fatal:

* ``nvidia-smi -L`` — human names for NVIDIA cards.
* ``vainfo`` per render node — driver/name for VAAPI (AMD/Intel) cards.

The dev host is dual-GPU (RX 9070 XT on ``renderD128`` + Radeon 780M on ``renderD129``),
so the two-render-nodes-to-two-devices path is exercised for real.

Each helper that touches the filesystem or spawns a tool is a module-level function so
tests can monkeypatch one seam at a time.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from .models import PCI_VENDOR_IDS, Device, Vendor

logger = logging.getLogger(__name__)

#: Default locations; overridable so tests can point at fixtures.
DEFAULT_DRI_DIR = "/dev/dri"
DEFAULT_SYSFS_DRM = "/sys/class/drm"

_VENDOR_DISPLAY = {
    Vendor.AMD: "AMD GPU",
    Vendor.NVIDIA: "NVIDIA GPU",
    Vendor.INTEL: "Intel GPU",
}


def enumerate_devices(
    *,
    dri_dir: str = DEFAULT_DRI_DIR,
    sysfs_drm: str = DEFAULT_SYSFS_DRM,
) -> list[Device]:
    """Return the enumerated accelerator devices, best-effort.

    Render nodes are the base; ``nvidia-smi``/``vainfo`` only refine names. Any probe
    failing (tool absent, sysfs unreadable) is logged at debug and skipped, never raised.
    """
    nodes = render_nodes(dri_dir)
    if not nodes:
        logger.debug("No render nodes under %s", dri_dir)
        return []

    nvidia_names = _nvidia_names()
    nvidia_seen = 0

    devices: list[Device] = []
    for node in nodes:
        basename = os.path.basename(node)
        vendor = pci_vendor(basename, sysfs_drm)
        if vendor is None:
            logger.debug("Skipping %s: unknown PCI vendor", node)
            continue

        address = pci_address(basename, sysfs_drm)
        device_id = f"pci-{address}" if address else basename

        name = vainfo_name(node)
        if name is None and vendor is Vendor.NVIDIA and nvidia_seen < len(nvidia_names):
            name = nvidia_names[nvidia_seen]
            nvidia_seen += 1
        if name is None:
            name = _VENDOR_DISPLAY[vendor]

        devices.append(Device(id=device_id, vendor=vendor, name=name, render_node=node))
    return devices


def render_nodes(dri_dir: str = DEFAULT_DRI_DIR) -> list[str]:
    """Return sorted ``/dev/dri/renderD*`` paths, or ``[]`` if the dir is absent."""
    directory = Path(dri_dir)
    if not directory.is_dir():
        return []
    return sorted(str(p) for p in directory.glob("renderD*"))


def pci_vendor(node_basename: str, sysfs_drm: str = DEFAULT_SYSFS_DRM) -> Optional[Vendor]:
    """Classify a render node by its PCI vendor id, or ``None`` if not determinable."""
    vendor_file = Path(sysfs_drm) / node_basename / "device" / "vendor"
    try:
        raw = vendor_file.read_text(encoding="ascii").strip().lower()
    except OSError:
        return None
    return PCI_VENDOR_IDS.get(raw)


def pci_address(node_basename: str, sysfs_drm: str = DEFAULT_SYSFS_DRM) -> Optional[str]:
    """Return the stable PCI address (``0000:03:00.0``) backing a render node, or None."""
    device_link = Path(sysfs_drm) / node_basename / "device"
    try:
        target = os.readlink(device_link)
    except OSError:
        return None
    # The link points at e.g. ../../../0000:03:00.0; the basename is the address.
    return os.path.basename(target.rstrip("/")) or None


def vainfo_name(render_node: str) -> Optional[str]:
    """Best-effort human name for a VAAPI device via ``vainfo``; None if unavailable."""
    try:
        result = subprocess.run(
            ["vainfo", "--display", "drm", "--device", render_node],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    text = result.stdout + result.stderr
    # vainfo prints e.g. "Driver version: Mesa Gallium driver 26.0.4 for AMD Radeon RX 9070 XT".
    match = re.search(r"driver .*? for (.+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _nvidia_names() -> list[str]:
    """Best-effort NVIDIA card names from ``nvidia-smi -L``; ``[]`` if absent."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    names: list[str] = []
    for line in result.stdout.splitlines():
        # "GPU 0: NVIDIA GeForce RTX 4090 (UUID: GPU-...)"
        match = re.match(r"GPU \d+:\s*(.+?)\s*\(UUID:", line)
        if match:
            names.append(match.group(1).strip())
    return names
