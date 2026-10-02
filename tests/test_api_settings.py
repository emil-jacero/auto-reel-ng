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
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.config.project import ConfigError, loads_project_config


def test_defaults_when_nothing_configured(tmp_path: Path) -> None:
    settings = resolve_api_settings(tmp_path, env={})
    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT
    assert settings.poll_interval == DEFAULT_POLL_INTERVAL_S
    assert settings.project_root == tmp_path
    assert settings.walk_root == tmp_path
    assert settings.layout_name == "year-event"
    assert settings.output_dir == default_output_dir(tmp_path)


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


def test_output_dir_shifts_with_config(tmp_path: Path) -> None:
    # The staleness gate's expected-output path (change-detection, §8.14) follows
    # the same D-2 layering as the CLI's own `project_context` output resolution.
    config = loads_project_config("input: media\noutput: renders\n")
    settings = resolve_api_settings(tmp_path, config=config, env={})
    assert settings.output_dir == tmp_path / "renders"


# --------------------------------------------------------------------------- #
# project-config: the output directory never lies inside the walked root
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("output", ["out", "out/renders", "."])
def test_output_inside_or_equal_to_the_walked_root_is_refused(tmp_path: Path, output: str) -> None:
    config = loads_project_config(f"output: {output}\n")
    with pytest.raises(ConfigError, match="inside the walked root") as excinfo:
        resolve_api_settings(tmp_path, config=config, env={})
    message = str(excinfo.value)
    assert str(tmp_path) in message  # names the walked root
    assert str(default_output_dir(tmp_path)) in message  # and the sibling to use


def test_output_symlinked_into_the_walked_root_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "out").mkdir(parents=True)
    (tmp_path / "shortcut").symlink_to(root / "out")
    config = loads_project_config("output: ../shortcut\n")
    with pytest.raises(ConfigError, match="inside the walked root"):
        resolve_api_settings(root, config=config, env={})


def test_output_symlinked_out_of_the_walked_root_is_allowed(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root).mkdir()
    (tmp_path / "elsewhere").mkdir()
    (root / "out").symlink_to(tmp_path / "elsewhere")
    config = loads_project_config("output: out\n")
    settings = resolve_api_settings(root, config=config, env={})
    assert settings.output_dir == root / "out"


@pytest.mark.parametrize(
    "yaml_text, expected",
    [
        ("output: ../renders\n", "../renders"),
        ("input: media\noutput: out\n", "out"),
        ("input: media\noutput: .\n", "."),
    ],
)
def test_output_outside_the_walked_root_is_allowed(
    tmp_path: Path, yaml_text: str, expected: str
) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    settings = resolve_api_settings(root, config=loads_project_config(yaml_text), env={})
    assert settings.output_dir == root / expected


def test_refusal_under_input_suggests_the_project_root_sibling(tmp_path: Path) -> None:
    config = loads_project_config("input: media\noutput: media/out\n")
    with pytest.raises(ConfigError) as excinfo:
        resolve_api_settings(tmp_path, config=config, env={})
    assert str(default_output_dir(tmp_path)) in str(excinfo.value)
