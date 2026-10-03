"""Two-pool capacity: per-render-node GPU semaphores + a global CPU semaphore (D-S3).

The worker selects its acceleration profile once at startup, then classifies each
claimed job by its *resolved encoder* (:func:`auto_reel_ng.render.resolve_target`)
after rebuilding the plan: a hardware encoder acquires that device's GPU token, a
software encoder acquires the CPU token. A job holds exactly one token for its
full duration — no mid-job handoff (D-S3, 4a/4b).
"""

from __future__ import annotations

import threading
from typing import Mapping, Optional

from ..accel.models import CapabilityInventory, Vendor
from ..accel.profiles.cpu import CPU_ENCODERS

#: Every CPU-encoder name (``libx264``/``libx265``/``libsvtav1``): a resolved
#: encoder in this set classifies a job as CPU-bound regardless of which profile
#: produced it (a hardware profile can still fall back to a CPU encoder).
_CPU_ENCODER_NAMES = frozenset(CPU_ENCODERS.values())


def classify_encoder(video_encoder: str) -> str:
    """Return ``"cpu"`` or ``"gpu"`` for a resolved ffmpeg encoder name (D-S3)."""
    return "cpu" if video_encoder in _CPU_ENCODER_NAMES else "gpu"


class CapacityPools:
    """Owns one semaphore per hardware render node plus a global CPU semaphore."""

    def __init__(self, *, gpu_caps: Mapping[str, int], cpu_cap: int) -> None:
        self._gpu = {node: threading.BoundedSemaphore(cap) for node, cap in gpu_caps.items()}
        self._cpu = threading.BoundedSemaphore(cpu_cap)
        self._total_capacity = sum(gpu_caps.values()) + cpu_cap

    @property
    def total_capacity(self) -> int:
        """Sum of every pool's capacity: the upper bound on usefully in-flight jobs (D-S3).

        The worker uses this to bound how many jobs it claims and spawns
        concurrently, so a burst of queued work never spawns more waiting
        threads than there is eventual token capacity to run them.
        """
        return self._total_capacity

    @classmethod
    def from_inventory(
        cls, inventory: CapabilityInventory, *, gpu_cap: int, cpu_cap: int
    ) -> "CapacityPools":
        """Build one ``gpu_cap``-capacity semaphore per usable hardware render node."""
        gpu_caps = {
            accel.device.render_node: gpu_cap
            for accel in inventory.usable_accelerators()
            if accel.vendor is not Vendor.CPU
            and accel.device is not None
            and accel.device.render_node is not None
        }
        return cls(gpu_caps=gpu_caps, cpu_cap=cpu_cap)

    def cpu_token(self) -> threading.BoundedSemaphore:
        """The CPU pool's semaphore: what a job of CPU work that is not a render holds (D-S3).

        A ``proxy`` job (its x264 encode is CPU work even on the hybrid path) holds this one
        token for its whole run and never a GPU token.
        """
        return self._cpu

    def token_for(
        self, *, video_encoder: str, render_node: Optional[str]
    ) -> threading.BoundedSemaphore:
        """The semaphore a job with this resolved encoder/device must hold (D-S3).

        A GPU-classified job whose ``render_node`` has no configured pool (e.g. a
        device absent from the startup inventory) falls back to the CPU pool
        rather than raising — the classification is best-effort capacity shaping,
        not a correctness gate.
        """
        if classify_encoder(video_encoder) == "gpu" and render_node is not None:
            semaphore = self._gpu.get(render_node)
            if semaphore is not None:
                return semaphore
        return self._cpu


__all__ = ["CapacityPools", "classify_encoder"]
