"""The job-scheduler worker (7b): claims jobs from the durable store and drives
the render engine, enforcing per-device capacity and surviving restarts.

See ``openspec/changes/job-scheduler/design.md`` for the decisions (D-S1..D-S8).
"""

from __future__ import annotations

from .config import (
    DEFAULT_CPU_SLOTS,
    DEFAULT_GPU_SESSIONS_PER_DEVICE,
    DEFAULT_POLL_INTERVAL_S,
    WorkerConfig,
    resolve_worker_config,
    worker_identity,
)
from .pools import CapacityPools, classify_encoder
from .progress import ThrottledProgress
from .worker import BuildJob, KindHandler, RunRender, Worker, default_build_job

__all__ = [
    "Worker",
    "BuildJob",
    "KindHandler",
    "RunRender",
    "default_build_job",
    "CapacityPools",
    "classify_encoder",
    "ThrottledProgress",
    "WorkerConfig",
    "resolve_worker_config",
    "worker_identity",
    "DEFAULT_POLL_INTERVAL_S",
    "DEFAULT_GPU_SESSIONS_PER_DEVICE",
    "DEFAULT_CPU_SLOTS",
]
