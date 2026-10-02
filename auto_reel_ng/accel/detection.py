"""Turn raw ffmpeg capability text + the self-test into a usable inventory.

This is the orchestration layer: it parses ffmpeg's ``-encoders/-decoders/-hwaccels/
-filters`` listings, enumerates devices, runs the self-test, and folds the results into
per-accelerator capability flags — where *only* self-test-passing ops are reported usable
(presence in a listing is never enough; that was the whole lesson of the AMD spikes).

Results are cached in-process and optionally to a file, keyed by a host fingerprint
(ffmpeg version + enumerated device set) so the self-test does not re-run every startup;
a mismatching fingerprint (driver/hardware change) invalidates the cache.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Mapping, Optional, Sequence

from ..ffmpeg.runtime import FfmpegRuntime
from ..probe.media import get_default_runtime
from .devices import enumerate_devices
from .models import (
    AcceleratorCapabilities,
    CapabilityInventory,
    Device,
    OpStatus,
    Vendor,
)
from .selftest import _HW_ENCODERS, Probe, run_selftest

logger = logging.getLogger(__name__)

#: vendor -> ffmpeg ``-hwaccel`` value used for hardware decode.
_DECODE_METHOD = {Vendor.AMD: "vaapi", Vendor.NVIDIA: "cuda", Vendor.INTEL: "qsv"}

#: vendor -> the pad filter its normalize uses (CPU ``pad`` for the no-native-pad vendors).
_PAD_FILTER = {Vendor.AMD: "pad_vaapi", Vendor.NVIDIA: "pad", Vendor.INTEL: "pad"}

#: vendor -> source codec -> the highest bit depth its hardware decoder handles. A static
#: table (the self-test keeps its single h264 decode probe), kept only when that probe
#: passed. A missing entry costs speed (software decode); a wrong one costs one logged
#: retry in the orchestrator. AMD lists only what the Mesa VAAPI stack is known to decode;
#: ``mpeg4`` was reproduced failing on the AMD Radeon 860M. NVIDIA and Intel are unverified here.
_HW_DECODE: Mapping[Vendor, Mapping[str, int]] = {
    Vendor.AMD: {"h264": 8, "hevc": 10, "vp9": 10, "av1": 10},
    Vendor.NVIDIA: {
        "h264": 8,
        "hevc": 10,
        "vp9": 10,
        "av1": 10,
        "mpeg2video": 8,
        "vc1": 8,
        "mpeg4": 8,
        "mjpeg": 8,
    },
    Vendor.INTEL: {
        "h264": 8,
        "hevc": 10,
        "vp9": 10,
        "av1": 10,
        "mpeg2video": 8,
        "vc1": 8,
        "mjpeg": 8,
    },
}

#: Bumped whenever what detection records changes, so an older cache file is re-detected.
#: 2 = ``pad_fill_ok`` (vaapi-pad-fill); 3 = ``hw_decode`` (render-vaapi-software-decode-fallback).
_CACHE_SCHEMA = 3

#: Process-wide cache keyed by host fingerprint.
_INVENTORY_CACHE: dict[tuple[object, ...], CapabilityInventory] = {}


# -- listing parsers ---------------------------------------------------------


def parse_codec_listing(text: str) -> frozenset[str]:
    """Parse ``ffmpeg -encoders``/``-decoders`` text into the set of codec names.

    Capability lines carry a six-character flag field then the name, e.g.
    `` V....D libx264   libx264 H.264 ...`` -> ``libx264``.
    """
    names: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^\s*[A-Z.]{6}\s+(\S+)", line)
        if match and match.group(1) != "=":
            names.add(match.group(1))
    return frozenset(names)


def parse_filter_listing(text: str) -> frozenset[str]:
    """Parse ``ffmpeg -filters`` text into the set of filter names.

    Filter lines carry a leading flag field, the name, then an ``in->out`` arrow,
    e.g. `` T.C scale_vaapi      V->V    Scale ...`` -> ``scale_vaapi``. The flag field
    is **2 or 3 characters** depending on the ffmpeg build: older builds expose three
    columns (timeline/slice/command, ``T.C``), while ffmpeg >= 8 dropped the command
    column and emits two (``TS``). The ``in->out`` arrow is the reliable signal.
    """
    names: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^\s*[A-Za-z.|]{2,3}\s+(\w+)\s+\S+->\S+", line)
        if match:
            names.add(match.group(1))
    return frozenset(names)


def parse_hwaccel_listing(text: str) -> frozenset[str]:
    """Parse ``ffmpeg -hwaccels`` text (a header line then one method per line)."""
    names: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.endswith(":"):
            continue
        # The header is "Hardware acceleration methods:"; methods are single tokens.
        if " " in stripped:
            continue
        names.add(stripped)
    return frozenset(names)


# -- capability computation --------------------------------------------------


def compute_accelerator(
    vendor: Vendor,
    device: Optional[Device],
    selftest: Mapping[str, OpStatus],
) -> AcceleratorCapabilities:
    """Fold the self-test results for one vendor into its capability flags.

    Every flag reflects a ``WORKING`` self-test result; an op that was unsupported or
    faulting is excluded, regardless of whether ffmpeg listed it.
    """
    prefix = vendor.value

    def works(key: str) -> bool:
        return selftest.get(key) is OpStatus.WORKING

    decode_method = _DECODE_METHOD[vendor] if works(f"{prefix}.decode") else None
    pad_filter = _PAD_FILTER[vendor] if works(f"{prefix}.normalize") else None
    # Only the native VAAPI pad is measured; the other vendors pad with CPU ``pad``.
    pad_fill_ok = works(f"{prefix}.pad_fill") if vendor is Vendor.AMD else True

    usable_encoders: dict[str, str] = {}
    for codec, encoder in _HW_ENCODERS[vendor].items():
        if works(f"{prefix}.encode.{codec}"):
            usable_encoders[codec] = encoder

    usable = bool(decode_method or pad_filter or usable_encoders)
    return AcceleratorCapabilities(
        vendor=vendor,
        usable=usable,
        device=device,
        pad_filter=pad_filter,
        can_overlay_hw=works(f"{prefix}.overlay"),
        can_tonemap_hw=works(f"{prefix}.tonemap"),
        usable_encoders=usable_encoders,
        decode_method=decode_method,
        pad_fill_ok=pad_fill_ok,
        hw_decode=dict(_HW_DECODE[vendor]) if decode_method else {},
    )


def build_inventory(
    *,
    encoders: frozenset[str],
    decoders: frozenset[str],
    hwaccels: frozenset[str],
    filters: frozenset[str],
    devices: Sequence[Device],
    selftest: Mapping[str, OpStatus],
    ffmpeg_version: tuple[int, int],
) -> CapabilityInventory:
    """Assemble a :class:`CapabilityInventory` from parsed listings + self-test results.

    One :class:`AcceleratorCapabilities` is produced per hardware vendor that has a
    device, plus a CPU accelerator that is always usable.
    """
    accelerators: list[AcceleratorCapabilities] = []
    seen_vendors: set[Vendor] = set()
    for device in devices:
        if device.vendor in seen_vendors or device.vendor is Vendor.CPU:
            continue
        seen_vendors.add(device.vendor)
        accelerators.append(compute_accelerator(device.vendor, device, selftest))

    accelerators.append(
        AcceleratorCapabilities(
            vendor=Vendor.CPU,
            usable=True,
            device=None,
            pad_filter="pad",
            can_overlay_hw=True,
            can_tonemap_hw=True,
            usable_encoders={"h264": "libx264", "hevc": "libx265", "av1": "libsvtav1"},
            decode_method=None,
        )
    )
    return CapabilityInventory(
        encoders=encoders,
        decoders=decoders,
        hwaccels=hwaccels,
        filters=filters,
        devices=tuple(devices),
        accelerators=tuple(accelerators),
        selftest=dict(selftest),
        ffmpeg_version=ffmpeg_version,
    )


# -- top-level detection with caching ---------------------------------------


def detect_capabilities(
    runtime: Optional[FfmpegRuntime] = None,
    *,
    force_refresh: bool = False,
    cache_path: Optional[Path] = None,
    selftest: bool = True,
    extra_probes: Sequence[Probe] = (),
) -> CapabilityInventory:
    """Detect the host's self-tested capability inventory, with caching.

    Args:
        runtime: ffmpeg runtime to use; the shared default is built if omitted.
        force_refresh: re-run parsing + self-test even if a cached result exists.
        cache_path: optional file to read/write the inventory; a fingerprint mismatch
            (different ffmpeg version or device set) invalidates it.
        selftest: when False, skip the empirical self-test (no op is marked usable);
            useful where running tiny encodes at startup is undesirable.
        extra_probes: additional self-test probes (e.g. tests injecting a bad op).
    """
    runtime = runtime or get_default_runtime()
    devices = enumerate_devices()
    fingerprint = _fingerprint(runtime.version, devices)

    if not force_refresh:
        cached = _INVENTORY_CACHE.get(fingerprint)
        if cached is not None:
            return cached
        if cache_path is not None:
            from_file = _load_cache(cache_path, fingerprint)
            if from_file is not None:
                _INVENTORY_CACHE[fingerprint] = from_file
                return from_file

    selftest_results: dict[str, OpStatus] = {}
    encoders = parse_codec_listing(runtime.encoders())
    decoders = parse_codec_listing(runtime.decoders())
    filters = parse_filter_listing(runtime.filters())
    hwaccels = parse_hwaccel_listing(runtime.hwaccels())

    if selftest:
        selftest_results = run_selftest(
            runtime, devices, encoders=encoders, filters=filters, extra_probes=extra_probes
        )

    inventory = build_inventory(
        encoders=encoders,
        decoders=decoders,
        hwaccels=hwaccels,
        filters=filters,
        devices=devices,
        selftest=selftest_results,
        ffmpeg_version=runtime.version,
    )

    _INVENTORY_CACHE[fingerprint] = inventory
    if cache_path is not None:
        _write_cache(cache_path, fingerprint, inventory)
    return inventory


def clear_cache() -> None:
    """Drop the in-process inventory cache (mainly for tests)."""
    _INVENTORY_CACHE.clear()


def _fingerprint(ffmpeg_version: tuple[int, int], devices: Sequence[Device]) -> tuple[object, ...]:
    """A host fingerprint: cache schema + ffmpeg version + the sorted enumerated device ids."""
    return (_CACHE_SCHEMA, ffmpeg_version, tuple(sorted(d.id for d in devices)))


def _write_cache(
    cache_path: Path, fingerprint: tuple[object, ...], inventory: CapabilityInventory
) -> None:
    """Persist the inventory + fingerprint to ``cache_path`` (best-effort)."""
    payload = {"fingerprint": _jsonable(fingerprint), "inventory": inventory.to_dict()}
    try:
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as exc:
        logger.debug("Could not write capability cache %s: %s", cache_path, exc)


def _load_cache(cache_path: Path, fingerprint: tuple[object, ...]) -> Optional[CapabilityInventory]:
    """Load a cached inventory if present and its fingerprint still matches, else None."""
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("fingerprint") != _jsonable(fingerprint):
        logger.debug("Capability cache %s fingerprint mismatch; ignoring", cache_path)
        return None
    try:
        return _inventory_from_dict(payload["inventory"])
    except (KeyError, ValueError) as exc:
        logger.debug("Capability cache %s unreadable: %s", cache_path, exc)
        return None


def _jsonable(value: object) -> object:
    """Round-trip a fingerprint through JSON-native types for stable comparison."""
    return json.loads(json.dumps(value))


def _inventory_from_dict(data: Mapping[str, object]) -> CapabilityInventory:
    """Reconstruct a :class:`CapabilityInventory` from its ``to_dict()`` form."""
    devices = tuple(_device_from_dict(d) for d in _as_list(data["devices"]))
    accelerators = tuple(_accelerator_from_dict(a) for a in _as_list(data["accelerators"]))
    selftest = {key: OpStatus(value) for key, value in _as_dict(data["selftest"]).items()}
    version = tuple(_as_list(data["ffmpeg_version"]))
    return CapabilityInventory(
        encoders=frozenset(_as_list(data["encoders"])),
        decoders=frozenset(_as_list(data["decoders"])),
        hwaccels=frozenset(_as_list(data["hwaccels"])),
        filters=frozenset(_as_list(data["filters"])),
        devices=devices,
        accelerators=accelerators,
        selftest=selftest,
        ffmpeg_version=(int(version[0]), int(version[1])),
    )


def _device_from_dict(data: Mapping[str, object]) -> Device:
    return Device(
        id=str(data["id"]),
        vendor=Vendor(data["vendor"]),
        name=str(data["name"]),
        render_node=data["render_node"],  # type: ignore[arg-type]
    )


def _accelerator_from_dict(data: Mapping[str, object]) -> AcceleratorCapabilities:
    device = data.get("device")
    return AcceleratorCapabilities(
        vendor=Vendor(data["vendor"]),
        usable=bool(data["usable"]),
        device=_device_from_dict(device) if device else None,  # type: ignore[arg-type]
        pad_filter=data["pad_filter"],  # type: ignore[arg-type]
        can_overlay_hw=bool(data["can_overlay_hw"]),
        can_tonemap_hw=bool(data["can_tonemap_hw"]),
        usable_encoders=_as_dict(data["usable_encoders"]),
        decode_method=data["decode_method"],  # type: ignore[arg-type]
        # Indexed, not .get(): a cache written before the flag existed is a mismatch.
        pad_fill_ok=bool(data["pad_fill_ok"]),
        hw_decode={str(k): int(v) for k, v in _as_dict(data["hw_decode"]).items()},
    )


def _as_list(value: object) -> list:
    """Narrow a JSON value to a list for mypy and reject malformed cache payloads."""
    if not isinstance(value, list):
        raise ValueError(f"expected a list, got {type(value).__name__}")
    return value


def _as_dict(value: object) -> dict:
    """Narrow a JSON value to a dict for mypy and reject malformed cache payloads."""
    if not isinstance(value, dict):
        raise ValueError(f"expected a dict, got {type(value).__name__}")
    return value
