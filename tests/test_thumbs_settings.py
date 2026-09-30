"""Tests for the ``thumbnails.*`` settings: defaults, XDG layering, validation (D-11).

Every test points ``HOME`` at ``tmp_path / "home"`` and sets or deletes
``XDG_CACHE_HOME``, so neither ``Path.home()`` nor ``~`` expansion reaches the real
home directory. The project root is ``tmp_path / "library"``, a sibling of both.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from auto_reel_ng.config import ConfigError, loads_project_config
from auto_reel_ng.thumbs import ThumbnailSettings, resolve_thumbnail_settings
from auto_reel_ng.thumbs.settings import DEFAULT_POSITION


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake ``$HOME`` with ``XDG_CACHE_HOME`` unset."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    return home_dir


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """The project root, a sibling of the fake home."""
    root = tmp_path / "library"
    root.mkdir()
    return root


def _resolve(text: str, library: Path) -> ThumbnailSettings:
    return resolve_thumbnail_settings(loads_project_config(text), library)


# --------------------------------------------------------------------------- #
# defaults and the XDG layering
# --------------------------------------------------------------------------- #


def test_no_settings_use_the_defaults(home: Path, library: Path) -> None:
    settings = _resolve("", library)
    assert settings.position == DEFAULT_POSITION == 0.25
    assert settings.cache_dir == home / ".cache" / "auto-reel" / "thumbnails"


def test_xdg_cache_home_moves_the_default(
    home: Path, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/var/cache/emil")
    settings = _resolve("", library)
    assert settings.cache_dir == Path("/var/cache/emil/auto-reel/thumbnails")


def test_a_relative_xdg_cache_home_is_ignored(
    home: Path, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "relative/cache")
    settings = _resolve("", library)
    assert settings.cache_dir == home / ".cache" / "auto-reel" / "thumbnails"


def test_an_explicit_cache_dir_wins_over_xdg_cache_home(
    home: Path, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/var/cache/emil")
    settings = _resolve("thumbnails:\n  cache_dir: ~/thumbs\n", library)
    assert settings.cache_dir == home / "thumbs"


def test_a_configured_position_is_accepted(home: Path, library: Path) -> None:
    assert _resolve("thumbnails:\n  position: 0.5\n", library).position == 0.5


def test_unknown_keys_are_ignored(home: Path, library: Path) -> None:
    assert _resolve("thumbnails:\n  box: 640x360\n", library).position == DEFAULT_POSITION


# --------------------------------------------------------------------------- #
# position validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", ["0", "1", "1.5", '"a quarter"', "true", ".nan"])
def test_a_bad_position_fails_loud(home: Path, library: Path, value: str) -> None:
    with pytest.raises(ConfigError, match=r"thumbnails\.position"):
        _resolve(f"thumbnails:\n  position: {value}\n", library)


# --------------------------------------------------------------------------- #
# cache_dir validation: absolute, and outside the library
# --------------------------------------------------------------------------- #


def test_a_relative_cache_dir_fails_loud(home: Path, library: Path) -> None:
    with pytest.raises(ConfigError, match=r"thumbnails\.cache_dir"):
        _resolve("thumbnails:\n  cache_dir: thumbs\n", library)


def test_an_unexpandable_cache_dir_fails_loud(home: Path, library: Path) -> None:
    with pytest.raises(ConfigError, match=r"thumbnails\.cache_dir"):
        _resolve("thumbnails:\n  cache_dir: ~no-such-user-here/thumbs\n", library)


def test_a_non_string_cache_dir_fails_loud(home: Path, library: Path) -> None:
    with pytest.raises(ConfigError, match=r"thumbnails\.cache_dir"):
        _resolve("thumbnails:\n  cache_dir: 42\n", library)


def test_a_cache_dir_under_the_project_root_is_refused(home: Path, library: Path) -> None:
    with pytest.raises(ConfigError, match=r"thumbnails\.cache_dir"):
        _resolve(f"thumbnails:\n  cache_dir: {library / '.thumbs'}\n", library)


def test_a_cache_dir_reaching_the_project_root_through_a_symlink_is_refused(
    tmp_path: Path, home: Path, library: Path
) -> None:
    link = tmp_path / "link"
    link.symlink_to(library, target_is_directory=True)
    with pytest.raises(ConfigError, match=r"thumbnails\.cache_dir"):
        _resolve(f"thumbnails:\n  cache_dir: {link / 'thumbs'}\n", library)


def test_a_cache_dir_under_an_input_directory_outside_the_root_is_refused(
    tmp_path: Path, home: Path, library: Path
) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    text = f"input: {archive}\nthumbnails:\n  cache_dir: {archive / '.thumbs'}\n"
    with pytest.raises(ConfigError, match=r"thumbnails\.cache_dir"):
        _resolve(text, library)


def test_a_case_insensitive_alias_of_the_input_directory_is_refused(
    tmp_path: Path, home: Path, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The archive is a case-insensitive NTFS mount: "videos/sorted" names "Videos/Sorted".
    archive = tmp_path / "MOL" / "Videos" / "Sorted"
    archive.mkdir(parents=True)
    alias = tmp_path / "MOL" / "videos" / "sorted"
    real_stat = os.stat

    def casefold_stat(path: object, *args: object, **kwargs: object) -> os.stat_result:
        if str(path).casefold() == str(archive).casefold():
            return real_stat(archive)
        return real_stat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "stat", casefold_stat)
    text = f"input: {archive}\nthumbnails:\n  cache_dir: {alias / '.thumbs'}\n"
    with pytest.raises(
        ConfigError, match=r"thumbnails\.cache_dir .* lies inside the input directory"
    ):
        _resolve(text, library)


def test_no_home_directory_is_a_config_error(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)

    def no_home(cls: type) -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", classmethod(no_home))
    with pytest.raises(ConfigError, match="no home directory could be determined"):
        _resolve("", library)


def test_a_default_inside_the_project_root_is_refused_too(
    home: Path, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(library / ".cache"))
    with pytest.raises(ConfigError, match=r"thumbnails\.cache_dir is not set.*set thumbnails"):
        _resolve("", library)
