"""Caching: in-process identity, file round-trip, and fingerprint invalidation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from auto_reel_ng.accel import clear_cache, detect_capabilities, detection
from auto_reel_ng.accel.detection import (
    _inventory_from_dict,
    _load_cache,
    _write_cache,
    build_inventory,
)
from auto_reel_ng.accel.models import Device, OpStatus, Vendor
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime


def _sample_inventory():
    device = Device(
        id="pci-0000:03:00.0",
        vendor=Vendor.AMD,
        name="RX 9070 XT",
        render_node="/dev/dri/renderD128",
    )
    return build_inventory(
        encoders=frozenset({"hevc_vaapi", "libx264"}),
        decoders=frozenset({"h264"}),
        hwaccels=frozenset({"vaapi"}),
        filters=frozenset({"scale_vaapi", "pad_vaapi"}),
        devices=(device,),
        selftest={"amd.encode.hevc": OpStatus.WORKING, "amd.overlay": OpStatus.UNSUPPORTED},
        ffmpeg_version=(7, 1),
    )


def test_in_process_cache_returns_same_object(runtime: FfmpegRuntime) -> None:
    """Two detections (no refresh) return the identical cached inventory object."""
    clear_cache()
    first = detect_capabilities(runtime=runtime, selftest=False)
    second = detect_capabilities(runtime=runtime, selftest=False)
    assert first is second


def test_force_refresh_recomputes_equal_inventory(runtime: FfmpegRuntime) -> None:
    """force_refresh rebuilds a fresh (non-identical) but equal inventory."""
    clear_cache()
    first = detect_capabilities(runtime=runtime, selftest=False)
    refreshed = detect_capabilities(runtime=runtime, selftest=False, force_refresh=True)
    assert refreshed is not first
    assert refreshed.to_dict() == first.to_dict()


def test_file_cache_round_trip(runtime: FfmpegRuntime, tmp_path: Path) -> None:
    """A file-cached inventory is reloaded across an in-process cache clear."""
    clear_cache()
    cache_path = tmp_path / "caps.json"
    first = detect_capabilities(runtime=runtime, selftest=False, cache_path=cache_path)
    assert cache_path.exists()

    clear_cache()  # force the next call to consult the file, not the in-process cache
    loaded = detect_capabilities(runtime=runtime, selftest=False, cache_path=cache_path)
    assert loaded.to_dict() == first.to_dict()


def test_fingerprint_mismatch_invalidates_file_cache(tmp_path: Path) -> None:
    """A cached fingerprint that no longer matches the host is ignored."""
    cache_path = tmp_path / "caps.json"
    _write_cache(cache_path, ("old-host",), _sample_inventory())

    assert _load_cache(cache_path, ("different-host",)) is None
    assert _load_cache(cache_path, ("old-host",)) is not None


def test_inventory_dict_round_trips() -> None:
    """A built inventory survives to_dict()/from_dict() unchanged (cache serialization)."""
    inventory = _sample_inventory()
    restored = _inventory_from_dict(inventory.to_dict())
    assert restored.to_dict() == inventory.to_dict()


def test_cache_without_pad_fill_ok_is_redetected(tmp_path: Path) -> None:
    """A cache written before pad_fill_ok existed is not reused."""
    cache_path = tmp_path / "caps.json"
    fingerprint = ("host",)
    _write_cache(cache_path, fingerprint, _sample_inventory())
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    for accel in payload["inventory"]["accelerators"]:
        del accel["pad_fill_ok"]
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    assert _load_cache(cache_path, fingerprint) is None


def test_old_cache_schema_triggers_redetection(
    runtime: FfmpegRuntime, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache file fingerprinted under an older schema is ignored and rewritten."""
    clear_cache()
    cache_path = tmp_path / "caps.json"
    monkeypatch.setattr(detection, "_CACHE_SCHEMA", 1)
    detect_capabilities(runtime=runtime, selftest=False, cache_path=cache_path)
    old = json.loads(cache_path.read_text(encoding="utf-8"))
    assert old["fingerprint"][0] == 1

    monkeypatch.setattr(detection, "_CACHE_SCHEMA", 2)
    clear_cache()
    calls: list[object] = []
    real_build = detection.build_inventory

    def counting_build(**kwargs: object) -> object:
        calls.append(kwargs)
        return real_build(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(detection, "build_inventory", counting_build)
    inventory = detect_capabilities(runtime=runtime, selftest=False, cache_path=cache_path)
    assert len(calls) == 1  # re-detected, not loaded
    new = json.loads(cache_path.read_text(encoding="utf-8"))
    assert new["fingerprint"][0] == 2
    assert all("pad_fill_ok" in a for a in new["inventory"]["accelerators"])
    assert inventory.accelerator(Vendor.CPU) is not None
