"""``ApiSettings`` resolution: the D-2 layering for the API service (decision D-A1/D-A7).

Mirrors :func:`auto_reel_ng.scheduler.config.resolve_worker_config`: CLI-flag
overrides layer over a project's ``config.yaml`` ``api.*`` map, which layers over
built-in defaults. ``project_root``/``layout_name`` reuse the same resolution the
CLI's ``_project_context`` performs, so the API walks exactly the events ``scan``
would report for the same root.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from ..config.project import ConfigError, ProjectConfig, load_project_config
from ..ingest import DEFAULT_LAYOUT
from ..persistence.config import resolve_database_url

#: Bind defaults (D-A8): localhost-only until an operator explicitly widens it.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080

#: The WS hub's poller interval (D-A4): matches the worker's ≥1 s progress throttle.
DEFAULT_POLL_INTERVAL_S = 1.0


@dataclass(frozen=True)
class ApiSettings:
    """The resolved settings a ``create_app`` call is built from (D-A1).

    ``project_root`` is the single configured project the service serves
    (no multi-project model, D-A1); ``walk_root`` is where the ingest layout
    walks from (``project_root`` unless ``config.yaml`` sets ``input``);
    ``output_dir`` is where the staleness gate (§8.14) expects rendered output
    (``project_root`` unless ``config.yaml`` sets ``output``, mirroring the CLI).
    """

    project_root: Path
    walk_root: Path
    layout_name: str
    output_dir: Path
    host: str
    port: int
    poll_interval: float
    database_url: str


def _resolve_str(flag: Optional[str], config_value: object, default: str, *, key: str) -> str:
    """Layer a CLI-flag/explicit override over an ``api.<key>`` config value (D-2)."""
    if flag is not None:
        return flag
    if config_value is None:
        return default
    if isinstance(config_value, str):
        return config_value
    raise ConfigError(f"api.{key} must be a string, got {type(config_value).__name__}")


def _resolve_int(flag: Optional[int], config_value: object, default: int, *, key: str) -> int:
    """Layer a CLI-flag/explicit override over an ``api.<key>`` config value (D-2)."""
    if flag is not None:
        return flag
    if config_value is None:
        return default
    if isinstance(config_value, int) and not isinstance(config_value, bool):
        return config_value
    raise ConfigError(f"api.{key} must be an integer, got {type(config_value).__name__}")


def _resolve_float(
    flag: Optional[float], config_value: object, default: float, *, key: str
) -> float:
    """Layer a CLI-flag/explicit override over an ``api.<key>`` config value (D-2)."""
    if flag is not None:
        return flag
    if config_value is None:
        return default
    if isinstance(config_value, (int, float)) and not isinstance(config_value, bool):
        return float(config_value)
    raise ConfigError(f"api.{key} must be a number, got {type(config_value).__name__}")


def resolve_api_settings(
    project_root: Path,
    *,
    layout: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    poll_interval: Optional[float] = None,
    config: Optional[ProjectConfig] = None,
    env: Optional[Mapping[str, str]] = None,
) -> ApiSettings:
    """Resolve :class:`ApiSettings` for ``project_root`` (D-2, D-A1, D-A7).

    ``config`` may be passed pre-loaded (tests, ``serve``'s caller); otherwise it
    is loaded from ``project_root``. ``host``/``port``/``poll_interval`` are
    explicit overrides (CLI flags, ``None`` when not passed); ``env`` is forwarded
    to :func:`~auto_reel_ng.persistence.config.resolve_database_url`.
    """
    project_root = Path(project_root)
    resolved_config = config if config is not None else load_project_config(project_root)
    walk_root = (
        (project_root / resolved_config.input_dir) if resolved_config.input_dir else project_root
    )
    layout_name = layout or resolved_config.layout or DEFAULT_LAYOUT
    output_dir = (
        (project_root / resolved_config.output_dir)
        if resolved_config.output_dir
        else project_root / "output"
    )

    api_cfg = resolved_config.api
    return ApiSettings(
        project_root=project_root,
        walk_root=walk_root,
        layout_name=layout_name,
        output_dir=output_dir,
        host=_resolve_str(host, api_cfg.get("host"), DEFAULT_HOST, key="host"),
        port=_resolve_int(port, api_cfg.get("port"), DEFAULT_PORT, key="port"),
        poll_interval=_resolve_float(
            poll_interval,
            api_cfg.get("poll_interval"),
            DEFAULT_POLL_INTERVAL_S,
            key="poll_interval",
        ),
        database_url=resolve_database_url(project_root, env=env),
    )


__all__ = [
    "ApiSettings",
    "resolve_api_settings",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_POLL_INTERVAL_S",
]
