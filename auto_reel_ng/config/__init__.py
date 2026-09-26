"""Project configuration: the ``config.yaml`` schema and D-2 layered resolution."""

from __future__ import annotations

from .project import (
    CONFIG_FILENAME,
    ConfigError,
    ProjectConfig,
    default_output_dir,
    load_project_config,
    loads_project_config,
    resolve_look_defaults,
)

__all__ = [
    "CONFIG_FILENAME",
    "ConfigError",
    "ProjectConfig",
    "default_output_dir",
    "load_project_config",
    "loads_project_config",
    "resolve_look_defaults",
]
