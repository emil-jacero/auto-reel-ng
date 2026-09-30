"""Tests for the project config.yaml loader and D-2 layered resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.config import (
    ConfigError,
    ProjectConfig,
    default_output_dir,
    load_project_config,
    loads_project_config,
    resolve_look_defaults,
)
from auto_reel_ng.event import ClipOrder, SortMethod, resolve
from auto_reel_ng.reel.document import Metadata, ReelDocument

# --------------------------------------------------------------------------- #
# loader: missing / present / malformed
# --------------------------------------------------------------------------- #


def test_missing_config_is_tolerated(tmp_path: Path) -> None:
    config = load_project_config(tmp_path)
    assert config == ProjectConfig()
    assert config.layout is None
    assert config.look == {}


def test_config_supplies_layout_name(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("layout: flat\n", encoding="utf-8")
    assert load_project_config(tmp_path).layout == "flat"


def test_config_look_and_paths(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "look:\n  resolution: 1080p\ninput: media\noutput: out\n", encoding="utf-8"
    )
    config = load_project_config(tmp_path)
    assert config.look == {"resolution": "1080p"}
    assert config.input_dir == Path("media")
    assert config.output_dir == Path("out")


def test_malformed_yaml_fails_loud(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("look: [unterminated\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_project_config(tmp_path)


def test_a_config_that_is_not_utf8_fails_loud(tmp_path: Path) -> None:
    """A Latin-1 byte is a ConfigError naming the file, never a bare UnicodeDecodeError."""
    (tmp_path / "config.yaml").write_bytes(b"# kommentar p\xe5 latin-1\nlayout: flat\n")
    with pytest.raises(ConfigError, match="not valid UTF-8") as caught:
        load_project_config(tmp_path)
    assert str(tmp_path / "config.yaml") in str(caught.value)


def test_wrong_typed_layout_fails_loud() -> None:
    with pytest.raises(ConfigError):
        loads_project_config("layout: 42\n")


def test_wrong_typed_look_fails_loud() -> None:
    with pytest.raises(ConfigError):
        loads_project_config("look: not-a-mapping\n")


def test_config_supplies_worker_settings(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "worker:\n  gpu_sessions_per_device: 2\n  cpu_slots: 4\n  poll_interval: 1.5\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.worker == {
        "gpu_sessions_per_device": 2,
        "cpu_slots": 4,
        "poll_interval": 1.5,
    }


def test_wrong_typed_worker_fails_loud() -> None:
    with pytest.raises(ConfigError):
        loads_project_config("worker: not-a-mapping\n")


def test_wrong_typed_thumbnails_fails_loud() -> None:
    with pytest.raises(ConfigError, match="'thumbnails'"):
        loads_project_config("thumbnails: 3\n")


# --------------------------------------------------------------------------- #
# D-2 layering through resolve()
# --------------------------------------------------------------------------- #


def test_config_default_applies_when_nothing_overrides() -> None:
    config = ProjectConfig(look={"resolution": "1080p"})
    document = ReelDocument(metadata=Metadata(title="x"))
    plan = resolve(document, look_defaults=resolve_look_defaults(config))
    assert plan.look["resolution"] == "1080p"


def test_reel_yaml_overrides_config() -> None:
    config = ProjectConfig(look={"resolution": "1080p"})
    document = ReelDocument(metadata=Metadata(title="x"), look={"resolution": "4k"})
    plan = resolve(document, look_defaults=resolve_look_defaults(config))
    assert plan.look["resolution"] == "4k"


def test_default_output_dir_is_a_sibling_of_the_root(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "sorted"
    root.mkdir()
    assert default_output_dir(root) == tmp_path / "sorted-output"
    monkeypatch.chdir(root)
    assert default_output_dir(Path(".")) == tmp_path / "sorted-output"


# --------------------------------------------------------------------------- #
# sort rule (clip-order)
# --------------------------------------------------------------------------- #


def test_absent_sort_defaults_to_datetime() -> None:
    assert loads_project_config("layout: flat\n").sort == ClipOrder(
        method=SortMethod.DATETIME, reverse=False
    )


def test_sort_filename_reverse_parses() -> None:
    config = loads_project_config("sort:\n  method: filename\n  reverse: true\n")
    assert config.sort == ClipOrder(method=SortMethod.FILENAME, reverse=True)


def test_unknown_sort_method_fails_loud() -> None:
    with pytest.raises(ConfigError, match="sort.method"):
        loads_project_config("sort:\n  method: custom\n")


def test_wrong_typed_sort_reverse_fails_loud() -> None:
    with pytest.raises(ConfigError, match="sort.reverse"):
        loads_project_config('sort:\n  reverse: "yes"\n')
