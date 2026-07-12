"""Tests for :mod:`auto_reel_ng.api.settings` D-2 precedence (task 1.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.api.settings import (
    DEFAULT_HOST,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_PORT,
    resolve_api_settings,
)
from auto_reel_ng.config.project import ConfigError, loads_project_config


def test_defaults_when_nothing_configured(tmp_path: Path) -> None:
    settings = resolve_api_settings(tmp_path, env={})
    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT
    assert settings.poll_interval == DEFAULT_POLL_INTERVAL_S
    assert settings.project_root == tmp_path
    assert settings.walk_root == tmp_path
    assert settings.layout_name == "year-event"


def test_config_yaml_overrides_defaults(tmp_path: Path) -> None:
    config = loads_project_config("api:\n  host: 0.0.0.0\n  port: 9090\n  poll_interval: 2.5\n")
    settings = resolve_api_settings(tmp_path, config=config, env={})
    assert settings.host == "0.0.0.0"
    assert settings.port == 9090
    assert settings.poll_interval == 2.5


def test_flags_override_config_yaml(tmp_path: Path) -> None:
    config = loads_project_config("api:\n  host: 0.0.0.0\n  port: 9090\n")
    settings = resolve_api_settings(tmp_path, config=config, host="10.0.0.1", port=1234, env={})
    assert settings.host == "10.0.0.1"
    assert settings.port == 1234


def test_wrong_typed_port_fails_loud(tmp_path: Path) -> None:
    config = loads_project_config("api:\n  port: not-a-number\n")
    with pytest.raises(ConfigError, match="api.port"):
        resolve_api_settings(tmp_path, config=config, env={})


def test_database_url_env_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = resolve_api_settings(tmp_path, env={"DATABASE_URL": "postgresql+psycopg://x/y"})
    assert settings.database_url == "postgresql+psycopg://x/y"


def test_input_dir_shifts_walk_root(tmp_path: Path) -> None:
    config = loads_project_config("input: media\n")
    settings = resolve_api_settings(tmp_path, config=config, env={})
    assert settings.walk_root == tmp_path / "media"
