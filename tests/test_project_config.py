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


def test_config_supplies_thumbnail_settings(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "thumbnails:\n  position: 0.5\n  cache_dir: /data/cache/auto-reel/thumbnails\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.thumbnails == {"position": 0.5, "cache_dir": "/data/cache/auto-reel/thumbnails"}


def test_config_without_thumbnails_carries_an_empty_map(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("layout: flat\n", encoding="utf-8")
    assert load_project_config(tmp_path).thumbnails == {}


def test_config_supplies_api_settings(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("worker:\n  cpu_slots: 4\napi:\n  port: 9000\n", "utf-8")
    config = load_project_config(tmp_path)
    assert config.worker == {"cpu_slots": 4}
    assert config.api == {"port": 9000}


def test_wrong_typed_api_fails_loud() -> None:
    with pytest.raises(ConfigError, match="'api'"):
        loads_project_config("api: 9000\n")


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


# --------------------------------------------------------------------------- #
# loader: every failure is a ConfigError (config-yaml-hardening)
# --------------------------------------------------------------------------- #

_HEX_5000 = "0x" + "f" * 5000


@pytest.mark.parametrize(
    "text",
    [
        "look: {a: 2024-02-30}\n",  # ValueError from the date constructor
        "a: !!bool maybe\n",  # KeyError from the bool constructor
        "a: " + "[" * 100_000 + "\n",  # RecursionError (or a scanner error) when too deep
    ],
    ids=["impossible-date", "unknown-bool", "deeply-nested"],
)
def test_builtin_errors_from_the_yaml_load_are_config_errors(text: str) -> None:
    with pytest.raises(ConfigError, match="malformed YAML") as caught:
        loads_project_config(text, source="/lib/config.yaml")
    assert "/lib/config.yaml" in str(caught.value)


def test_an_unknown_bool_message_names_the_exception_type() -> None:
    with pytest.raises(ConfigError, match="KeyError: 'maybe'"):
        loads_project_config("a: !!bool maybe\n")


def test_an_impossible_date_through_the_file_form_names_the_file(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("look: {a: 2024-02-30}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="malformed YAML") as caught:
        load_project_config(tmp_path)
    assert str(tmp_path / "config.yaml") in str(caught.value)


@pytest.mark.parametrize(
    ("text", "path"),
    [
        ('layout: "x\\ud800"\n', "layout"),
        ('look: {a: "x\\ud800"}\n', "look.a"),
        ('look: {"k\\ud800": 1}\n', "look"),
        ('database: {url: "postgres://\\udfff"}\n', "database.url"),
        ('worker: {names: [ok, "bad\\ud800"]}\n', "worker.names[1]"),
        ("look: {2024-01-01: x}\n", "look"),
        ("look: {1: a, b: c}\n", "look"),
        ("look: {title: {1: x}}\n", "look.title"),
        (f"look: {{a: {_HEX_5000}}}\n", "look.a"),
        ("look: &a {x: *a}\n", "look.x"),
        ("worker: &w [*w]\n", "worker[0]"),
        (f"worker:\n  ? {_HEX_5000}\n  : a\n", "worker[<int key>]"),
        (f"look:\n  ? {_HEX_5000}\n  : a\n", "look[<int key>]"),
        (f"? {_HEX_5000}\n: a\n", "[<int key>]"),
        (f"worker:\n  ? [{_HEX_5000}]\n  : a\n", "worker[<int key>]"),
        (f"look:\n  t:\n    ? {_HEX_5000}\n    : a\n", "look.t[<int key>]"),
    ],
    ids=[
        "layout-surrogate",
        "look-value-surrogate",
        "look-key-surrogate",
        "database-url-surrogate",
        "worker-list-surrogate",
        "look-date-key",
        "look-mixed-keys",
        "look-nested-int-key",
        "huge-hex-int",
        "self-referencing-mapping",
        "self-referencing-list",
        "huge-int-key-under-worker",
        "huge-int-key-under-look",
        "huge-int-key-top-level",
        "huge-int-in-sequence-key",
        "huge-int-key-nested-under-look",
    ],
)
def test_content_that_breaks_later_is_refused_at_load_with_its_path(text: str, path: str) -> None:
    with pytest.raises(ConfigError, match="/lib/config.yaml") as caught:
        loads_project_config(text, source="/lib/config.yaml")
    assert path in str(caught.value)
    assert "\ud800" not in str(caught.value)  # the message never carries the bad text


def test_the_refusal_messages_say_why() -> None:
    with pytest.raises(ConfigError, match="lone surrogate"):
        loads_project_config('layout: "x\\ud800"\n')
    with pytest.raises(ConfigError, match="a date, not a string"):
        loads_project_config("look: {2024-01-01: x}\n")
    with pytest.raises(ConfigError, match="too large to print"):
        loads_project_config(f"look: {{a: {_HEX_5000}}}\n")
    with pytest.raises(ConfigError, match="integer key is too large to print"):
        loads_project_config(f"look:\n  ? {_HEX_5000}\n  : a\n")
    with pytest.raises(ConfigError, match="refers to itself"):
        loads_project_config("look: &a {x: *a}\n")


def test_valid_text_and_non_look_int_keys_still_load() -> None:
    config = loads_project_config(
        "layout: flat\nlook: {title: Café, sub: 日本語, n: {k: 1}}\nworker: {1: one}\n"
    )
    assert config.layout == "flat"
    assert config.look == {"title": "Café", "sub": "日本語", "n": {"k": 1}}
    assert config.worker == {1: "one"}


def test_a_shared_alias_that_is_not_a_cycle_is_accepted() -> None:
    config = loads_project_config("look: {a: &s {k: v}, b: *s}\nworker: {x: *s}\n")
    assert config.look["a"] == config.look["b"] == {"k": "v"}
