"""Tests for two-pool capacity: classification and per-render-node semaphores (D-S3)."""

from __future__ import annotations

import threading

from auto_reel_ng.accel.models import (
    AcceleratorCapabilities,
    CapabilityInventory,
    Device,
    Vendor,
)
from auto_reel_ng.scheduler.pools import CapacityPools, classify_encoder

# --------------------------------------------------------------------------- #
# classify_encoder
# --------------------------------------------------------------------------- #


def test_cpu_encoders_classify_as_cpu() -> None:
    assert classify_encoder("libx264") == "cpu"
    assert classify_encoder("libx265") == "cpu"
    assert classify_encoder("libsvtav1") == "cpu"


def test_hardware_encoders_classify_as_gpu() -> None:
    assert classify_encoder("h264_vaapi") == "gpu"
    assert classify_encoder("hevc_nvenc") == "gpu"
    assert classify_encoder("av1_qsv") == "gpu"


# --------------------------------------------------------------------------- #
# CapacityPools
# --------------------------------------------------------------------------- #


def _inventory_with_amd_device() -> CapabilityInventory:
    device = Device(
        id="pci-0000:03:00.0",
        vendor=Vendor.AMD,
        name="RX 9070 XT",
        render_node="/dev/dri/renderD128",
    )
    accel = AcceleratorCapabilities(
        vendor=Vendor.AMD,
        usable=True,
        device=device,
        pad_filter="pad_vaapi",
        can_overlay_hw=False,
        can_tonemap_hw=False,
        usable_encoders={"h264": "h264_vaapi"},
        decode_method="vaapi",
    )
    cpu = AcceleratorCapabilities(
        vendor=Vendor.CPU,
        usable=True,
        device=None,
        pad_filter="pad",
        can_overlay_hw=True,
        can_tonemap_hw=True,
        usable_encoders={"h264": "libx264"},
        decode_method=None,
    )
    return CapabilityInventory(
        encoders=frozenset(),
        decoders=frozenset(),
        hwaccels=frozenset(),
        filters=frozenset(),
        devices=(device,),
        accelerators=(accel, cpu),
    )


def test_from_inventory_builds_one_semaphore_per_hardware_render_node() -> None:
    pools = CapacityPools.from_inventory(_inventory_with_amd_device(), gpu_cap=1, cpu_cap=2)
    gpu_token = pools.token_for(video_encoder="h264_vaapi", render_node="/dev/dri/renderD128")
    cpu_token = pools.token_for(video_encoder="libx264", render_node=None)
    assert gpu_token is not cpu_token
    # cap-1 GPU semaphore: a second acquire without a release must block, proven
    # by acquiring non-blockingly.
    assert gpu_token.acquire(blocking=False) is True
    assert gpu_token.acquire(blocking=False) is False
    gpu_token.release()


def test_token_for_falls_back_to_cpu_for_unconfigured_render_node() -> None:
    pools = CapacityPools.from_inventory(_inventory_with_amd_device(), gpu_cap=1, cpu_cap=1)
    token = pools.token_for(video_encoder="h264_vaapi", render_node="/dev/dri/renderD999")
    cpu_token = pools.token_for(video_encoder="libx264", render_node=None)
    assert token is cpu_token


def test_cpu_and_gpu_jobs_use_independent_pools() -> None:
    pools = CapacityPools.from_inventory(_inventory_with_amd_device(), gpu_cap=1, cpu_cap=1)
    gpu_token = pools.token_for(video_encoder="h264_vaapi", render_node="/dev/dri/renderD128")
    cpu_token = pools.token_for(video_encoder="libx264", render_node=None)

    assert gpu_token.acquire(blocking=False) is True
    # The CPU pool is untouched by the GPU token being held.
    assert cpu_token.acquire(blocking=False) is True
    gpu_token.release()
    cpu_token.release()


def test_gpu_cap_of_two_admits_two_concurrent_holders() -> None:
    pools = CapacityPools.from_inventory(_inventory_with_amd_device(), gpu_cap=2, cpu_cap=1)
    token = pools.token_for(video_encoder="h264_vaapi", render_node="/dev/dri/renderD128")
    assert token.acquire(blocking=False) is True
    assert token.acquire(blocking=False) is True
    assert token.acquire(blocking=False) is False
    token.release()
    token.release()


def test_total_capacity_sums_every_pool() -> None:
    pools = CapacityPools.from_inventory(_inventory_with_amd_device(), gpu_cap=2, cpu_cap=3)
    assert pools.total_capacity == 5


def test_total_capacity_with_no_gpu_devices_is_just_the_cpu_cap() -> None:
    pools = CapacityPools(gpu_caps={}, cpu_cap=4)
    assert pools.total_capacity == 4


def test_pools_are_thread_safe_semaphores() -> None:
    # Not a correctness proof, just confirms the returned object is a real
    # threading semaphore usable from another thread.
    pools = CapacityPools.from_inventory(_inventory_with_amd_device(), gpu_cap=1, cpu_cap=1)
    token = pools.token_for(video_encoder="libx264", render_node=None)
    acquired_in_thread = threading.Event()

    def _worker() -> None:
        with token:
            acquired_in_thread.set()

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join(timeout=2)
    assert acquired_in_thread.is_set()
