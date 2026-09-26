"""Project ``config.yaml``: shared defaults and the D-2 layering.

A project root may carry a ``config.yaml`` declaring a default ``look`` map, the
ingest ``layout`` name, default ``input``/``output`` paths, a ``database.url``
override consumed by :mod:`auto_reel_ng.persistence.config`, and a ``worker`` map
consumed by :mod:`auto_reel_ng.scheduler.config`. Every field is optional: a
missing file yields all-defaults (tolerated), while malformed YAML or a
wrong-typed field fails loud (engine convention).

Layered resolution (decision **D-2 / D-CLI2**): folder/layout seed ->
``config.yaml`` -> event ``reel.yaml`` -> CLI overrides, each later layer winning.
The ``look`` map is composed here into the ``look_defaults`` passed to
:func:`~auto_reel_ng.event.resolution.resolve`, which then layers the event
``reel.yaml`` ``look`` over it opaquely (D-J) — so an event setting wins over the
project default while a project default with no event override carries through.
The map is treated opaquely; this layer never interprets its inner keys.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from ..errors import EngineError

logger = logging.getLogger(__name__)

#: The project config file name, read from the project root the layout walks.
CONFIG_FILENAME = "config.yaml"


class ConfigError(EngineError):
    """A project ``config.yaml`` was malformed or carried a wrong-typed field."""


@dataclass(frozen=True)
class ProjectConfig:
    """Project-level shared defaults (every field optional, D-2)."""

    look: Mapping[str, object] = field(default_factory=dict)
    layout: Optional[str] = None
    input_dir: Optional[Path] = None
    output_dir: Optional[Path] = None
    database_url: Optional[str] = None
    #: The job-scheduler worker's ``worker.*`` settings (opaque, like ``look``); see
    #: :func:`auto_reel_ng.scheduler.config.resolve_worker_config`.
    worker: Mapping[str, object] = field(default_factory=dict)
    #: The API service's ``api.*`` settings (opaque, like ``worker``); see
    #: :func:`auto_reel_ng.api.settings.resolve_api_settings`.
    api: Mapping[str, object] = field(default_factory=dict)


def load_project_config(root: Path) -> ProjectConfig:
    """Load ``<root>/config.yaml`` if present; tolerate absence, fail loud on malformed."""
    config_path = Path(root) / CONFIG_FILENAME
    if not config_path.exists():
        logger.debug("No %s at %s; using built-in defaults", CONFIG_FILENAME, root)
        return ProjectConfig()
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"{config_path}: cannot read config: {exc}") from exc
    return loads_project_config(text, source=str(config_path))


def loads_project_config(text: str, *, source: str = "<string>") -> ProjectConfig:
    """Parse a ``config.yaml`` document from a string into a :class:`ProjectConfig`."""
    yaml = YAML(typ="safe")
    try:
        data = yaml.load(text)
    except YAMLError as exc:
        raise ConfigError(f"{source}: malformed YAML: {exc}") from exc

    if data is None:
        return ProjectConfig()
    if not isinstance(data, Mapping):
        raise ConfigError(
            f"{source}: top-level config must be a mapping, got {type(data).__name__}"
        )

    database = _require_mapping(data.get("database"), "database", source)
    return ProjectConfig(
        look=dict(_require_mapping(data.get("look"), "look", source)),
        layout=_require_str(data.get("layout"), "layout", source),
        input_dir=_require_path(data.get("input"), "input", source),
        output_dir=_require_path(data.get("output"), "output", source),
        database_url=_require_str(database.get("url"), "database.url", source),
        worker=dict(_require_mapping(data.get("worker"), "worker", source)),
        api=dict(_require_mapping(data.get("api"), "api", source)),
    )


def resolve_look_defaults(config: ProjectConfig) -> dict[str, object]:
    """The ``look_defaults`` map for :func:`resolve`: the project ``look`` (D-2).

    ``resolve()`` layers the event ``reel.yaml`` ``look`` over this opaquely (D-J):
    an event setting wins over the project default, and a project default with no
    event override carries through unchanged.
    """
    return dict(config.look)


def default_output_dir(project_root: Path) -> Path:
    """The output directory used when neither ``-o`` nor ``config.yaml`` sets one.

    ``<parent>/<root-name>-output``: a sibling of the project root, outside every
    ingest layout's walk, so rendered movies filed into year folders are never
    scanned back in as events. The root is resolved first so ``.`` still yields a
    named sibling.
    """
    root = Path(project_root).resolve()
    return root.parent / f"{root.name}-output"


def _require_mapping(value: object, key: str, source: str) -> Mapping[str, object]:
    """Return ``value`` as a mapping, defaulting missing to empty; else fail loud."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError(f"{source}: {key!r} must be a mapping, got {type(value).__name__}")
    return value


def _require_str(value: object, key: str, source: str) -> Optional[str]:
    """Return ``value`` as a string (None passes through); else fail loud."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{source}: {key!r} must be a string, got {type(value).__name__}")
    return value


def _require_path(value: object, key: str, source: str) -> Optional[Path]:
    """Return ``value`` as a path (None passes through); else fail loud."""
    text = _require_str(value, key, source)
    return Path(text) if text is not None else None
