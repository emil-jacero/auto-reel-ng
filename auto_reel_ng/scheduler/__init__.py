"""The job-scheduler worker (7b): claims jobs from the durable store and drives
the render engine, enforcing per-device capacity and surviving restarts.

See ``openspec/changes/job-scheduler/design.md`` for the decisions (D-S1..D-S8).
"""

from __future__ import annotations

from .analysis_job import AnalysisJobError, AnalysisJobHandler, submit_analysis
from .analysis_sweep import AnalysisSweep, SweepReport, start_analysis_sweep
from .config import (
    DEFAULT_ANALYSIS_SLOTS,
    DEFAULT_CPU_SLOTS,
    DEFAULT_GPU_SESSIONS_PER_DEVICE,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_PROXY_SLOTS,
    WorkerConfig,
    resolve_worker_config,
    worker_identity,
)
from .pools import CapacityPools, classify_encoder
from .progress import ThrottledProgress
from .proxy_job import ProxyJobError, ProxyJobHandler
from .worker import (
    BuildJob,
    JobInterrupted,
    KindHandler,
    RunRender,
    Worker,
    default_build_job,
)

__all__ = [
    "AnalysisJobError",
    "AnalysisJobHandler",
    "submit_analysis",
    "AnalysisSweep",
    "SweepReport",
    "start_analysis_sweep",
    "Worker",
    "BuildJob",
    "JobInterrupted",
    "KindHandler",
    "ProxyJobError",
    "ProxyJobHandler",
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
    "DEFAULT_PROXY_SLOTS",
    "DEFAULT_ANALYSIS_SLOTS",
]
