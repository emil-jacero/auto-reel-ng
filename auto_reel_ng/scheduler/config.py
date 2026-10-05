"""Worker identity and ``worker.*`` config resolution (D-S1, D-S5, D-2 layering).

Each worker boot gets a fresh, unique identity (:func:`worker_identity`) so startup
reconciliation can tell "my own in-flight work" from an orphan left by a previous
life. Pool capacities and the poll interval layer CLI flags over a project's
``config.yaml`` ``worker.*`` map over built-in defaults, the same precedence every
other CLI option follows (D-2).
"""

from __future__ import annotations

import math
import os
import socket
import uuid
from dataclasses import dataclass
from typing import Mapping, Optional

from ..config.project import ConfigError, ProjectConfig

#: Poll interval when the queue is empty (D-S4): renders take minutes, so
#: sub-second pickup buys nothing yet.
DEFAULT_POLL_INTERVAL_S = 2.0

#: Per-render-node GPU session cap (D-S3): conservative default of one concurrent
#: encode session per device.
DEFAULT_GPU_SESSIONS_PER_DEVICE = 1

#: Global CPU-pool slot cap (D-S3): conservative default of one concurrent
#: software-encoded render.
DEFAULT_CPU_SLOTS = 1


#: How many ``proxy`` jobs one worker runs at once (``proxy-job``): two gained only 20 to 35 %
#: on the research host and doubled the load on one disk.
DEFAULT_PROXY_SLOTS = 1

#: How many ``analysis`` jobs one worker runs at once (``analysis-job``): each holds one CPU
#: token and decodes originals in software, and with the default single CPU slot a second one
#: would only wait for that token.
DEFAULT_ANALYSIS_SLOTS = 1

#: Whether the worker sweeps its project for events whose analysis is due (``analysis-auto-sweep``):
#: on, so an idle worker brings every event's black/white/freeze suggestions up to date itself.
DEFAULT_AUTO_ANALYZE = True

#: Seconds between automatic analysis sweeps: "every few minutes"; analysis takes minutes per
#: event (D-27), so a faster sweep buys nothing.
DEFAULT_AUTO_ANALYZE_INTERVAL_S = 300.0

#: At most this many events a sweep enqueues, so the first sweep over a large archive trickles.
DEFAULT_AUTO_ANALYZE_MAX_EVENTS = 2


def worker_identity() -> str:
    """A fresh, unique worker id: ``host:pid:nonce`` (D-S5).

    Generated anew on every process start — never persisted or reused — so
    startup reconciliation can treat every ``running`` row from a previous life as
    an orphan, regardless of whether it crashed or was cleanly restarted.
    """
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class WorkerConfig:
    """Resolved worker settings: pool capacities and the poll interval."""

    poll_interval: float
    gpu_sessions_per_device: int
    cpu_slots: int
    proxy_slots: int = DEFAULT_PROXY_SLOTS
    analysis_slots: int = DEFAULT_ANALYSIS_SLOTS
    auto_analyze: bool = DEFAULT_AUTO_ANALYZE
    auto_analyze_interval: float = DEFAULT_AUTO_ANALYZE_INTERVAL_S
    auto_analyze_max_events: int = DEFAULT_AUTO_ANALYZE_MAX_EVENTS


def _resolve_float(
    flag: Optional[float], config_value: object, default: float, *, key: str
) -> float:
    """Layer a CLI flag over a ``worker.<key>`` config value over ``default`` (D-2)."""
    if flag is not None:
        return flag
    if config_value is None:
        return default
    if isinstance(config_value, (int, float)) and not isinstance(config_value, bool):
        return float(config_value)
    raise ConfigError(f"worker.{key} must be a number, got {type(config_value).__name__}")


def _resolve_int(flag: Optional[int], config_value: object, default: int, *, key: str) -> int:
    """Layer a CLI flag over a ``worker.<key>`` config value over ``default`` (D-2)."""
    if flag is not None:
        return flag
    if config_value is None:
        return default
    if isinstance(config_value, int) and not isinstance(config_value, bool):
        return config_value
    raise ConfigError(f"worker.{key} must be an integer, got {type(config_value).__name__}")


def _resolve_bool(config_value: object, default: bool, *, key: str) -> bool:
    """A ``worker.<key>`` boolean over ``default``; anything but ``true``/``false`` fails loud."""
    if config_value is None:
        return default
    if isinstance(config_value, bool):
        return config_value
    raise ConfigError(f"worker.{key} must be true or false, got {config_value!r}")


def _resolve_auto_analyze(worker_cfg: Mapping[str, object]) -> tuple[bool, float, int]:
    """``worker.auto_analyze``, ``auto_analyze_interval`` and ``auto_analyze_max_events``."""
    enabled = _resolve_bool(
        worker_cfg.get("auto_analyze"), DEFAULT_AUTO_ANALYZE, key="auto_analyze"
    )
    interval = _resolve_float(
        None,
        worker_cfg.get("auto_analyze_interval"),
        DEFAULT_AUTO_ANALYZE_INTERVAL_S,
        key="auto_analyze_interval",
    )
    if not math.isfinite(interval) or interval <= 0:
        raise ConfigError(
            f"worker.auto_analyze_interval must be a number of seconds above 0, got {interval}"
        )
    max_events = _resolve_int(
        None,
        worker_cfg.get("auto_analyze_max_events"),
        DEFAULT_AUTO_ANALYZE_MAX_EVENTS,
        key="auto_analyze_max_events",
    )
    if max_events < 1:
        raise ConfigError(f"worker.auto_analyze_max_events must be at least 1, got {max_events}")
    return enabled, interval, max_events


def resolve_worker_config(
    config: ProjectConfig,
    *,
    poll_interval: Optional[float] = None,
    gpu_sessions_per_device: Optional[int] = None,
    cpu_slots: Optional[int] = None,
    proxy_slots: Optional[int] = None,
    analysis_slots: Optional[int] = None,
) -> WorkerConfig:
    """Layer CLI-flag overrides over ``config.yaml`` ``worker.*`` over defaults (D-2).

    ``poll_interval``/``gpu_sessions_per_device``/``cpu_slots`` are the explicit
    CLI-flag values (``None`` when the flag was not passed); ``config.worker`` is
    the opaque map parsed from the project's ``config.yaml``. A wrong-typed
    ``worker.*`` value fails loud (:class:`ConfigError`), matching the engine's
    convention for a malformed ``config.yaml`` field.
    """
    worker_cfg = config.worker
    resolved_proxy_slots = _resolve_int(
        proxy_slots, worker_cfg.get("proxy_slots"), DEFAULT_PROXY_SLOTS, key="proxy_slots"
    )
    if resolved_proxy_slots < 1:
        raise ConfigError(f"worker.proxy_slots must be at least 1, got {resolved_proxy_slots}")
    resolved_analysis_slots = _resolve_int(
        analysis_slots,
        worker_cfg.get("analysis_slots"),
        DEFAULT_ANALYSIS_SLOTS,
        key="analysis_slots",
    )
    if resolved_analysis_slots < 1:
        raise ConfigError(
            f"worker.analysis_slots must be at least 1, got {resolved_analysis_slots}"
        )
    auto_analyze, auto_analyze_interval, auto_analyze_max_events = _resolve_auto_analyze(worker_cfg)
    return WorkerConfig(
        poll_interval=_resolve_float(
            poll_interval,
            worker_cfg.get("poll_interval"),
            DEFAULT_POLL_INTERVAL_S,
            key="poll_interval",
        ),
        gpu_sessions_per_device=_resolve_int(
            gpu_sessions_per_device,
            worker_cfg.get("gpu_sessions_per_device"),
            DEFAULT_GPU_SESSIONS_PER_DEVICE,
            key="gpu_sessions_per_device",
        ),
        cpu_slots=_resolve_int(
            cpu_slots, worker_cfg.get("cpu_slots"), DEFAULT_CPU_SLOTS, key="cpu_slots"
        ),
        proxy_slots=resolved_proxy_slots,
        analysis_slots=resolved_analysis_slots,
        auto_analyze=auto_analyze,
        auto_analyze_interval=auto_analyze_interval,
        auto_analyze_max_events=auto_analyze_max_events,
    )


__all__ = [
    "WorkerConfig",
    "worker_identity",
    "resolve_worker_config",
    "DEFAULT_POLL_INTERVAL_S",
    "DEFAULT_GPU_SESSIONS_PER_DEVICE",
    "DEFAULT_CPU_SLOTS",
    "DEFAULT_PROXY_SLOTS",
    "DEFAULT_ANALYSIS_SLOTS",
    "DEFAULT_AUTO_ANALYZE",
    "DEFAULT_AUTO_ANALYZE_INTERVAL_S",
    "DEFAULT_AUTO_ANALYZE_MAX_EVENTS",
]
