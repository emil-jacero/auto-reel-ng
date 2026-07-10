"""``DATABASE_URL`` resolution: env -> project ``config.yaml`` -> dev default.

Precedence: the ``DATABASE_URL`` environment variable wins outright; else a
project's ``database.url`` (``config.yaml``, D-2 layering, see
:mod:`auto_reel_ng.config.project`); else the documented dev default below, which
points at a containerized Postgres a developer starts locally (see the venv/test
notes). Resolution never invents a value: reading ``config.yaml`` still fails loud
(:class:`~auto_reel_ng.config.project.ConfigError`, naming the config file and
field) if ``database.url`` is present but wrongly typed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from ..config.project import load_project_config

#: A developer-started containerized Postgres (see the venv/test setup notes);
#: never assumed in production, where ``DATABASE_URL`` or ``config.yaml`` is expected.
DEFAULT_DATABASE_URL = "postgresql+psycopg://auto_reel_ng:auto_reel_ng@localhost:5432/auto_reel_ng"

_DATABASE_URL_ENV = "DATABASE_URL"


def resolve_database_url(
    root: Optional[Path] = None, *, env: Optional[Mapping[str, str]] = None
) -> str:
    """Resolve the ``DATABASE_URL``: env var -> project ``config.yaml`` -> dev default.

    ``root`` is the project root :func:`~auto_reel_ng.config.project.load_project_config`
    reads ``config.yaml`` from; pass ``None`` to skip that source (env and default
    only). A missing ``config.yaml`` is tolerated (falls through to the default); a
    malformed file or a wrongly-typed ``database.url`` fails loud.
    """
    environ = env if env is not None else os.environ
    env_url = environ.get(_DATABASE_URL_ENV)
    if env_url:
        return env_url
    if root is not None:
        config_url = load_project_config(root).database_url
        if config_url:
            return config_url
    return DEFAULT_DATABASE_URL
