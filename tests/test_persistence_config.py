"""Tests for ``DATABASE_URL`` resolution precedence (env -> config.yaml -> default)."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.config.project import ConfigError
from auto_reel_ng.persistence.config import DEFAULT_DATABASE_URL, resolve_database_url


def test_env_wins_over_config(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "database:\n  url: postgresql+psycopg://config/db\n", encoding="utf-8"
    )
    url = resolve_database_url(tmp_path, env={"DATABASE_URL": "postgresql+psycopg://env/db"})
    assert url == "postgresql+psycopg://env/db"


def test_falls_back_to_config_when_env_unset(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "database:\n  url: postgresql+psycopg://config/db\n", encoding="utf-8"
    )
    url = resolve_database_url(tmp_path, env={})
    assert url == "postgresql+psycopg://config/db"


def test_falls_back_to_dev_default_when_neither_set(tmp_path: Path) -> None:
    url = resolve_database_url(tmp_path, env={})
    assert url == DEFAULT_DATABASE_URL


def test_falls_back_to_dev_default_with_no_root() -> None:
    assert resolve_database_url(env={}) == DEFAULT_DATABASE_URL


def test_wrongly_typed_database_url_fails_loud(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("database:\n  url: 42\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        resolve_database_url(tmp_path, env={})


def test_wrongly_typed_database_section_fails_loud(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("database: not-a-mapping\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        resolve_database_url(tmp_path, env={})
