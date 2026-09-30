"""Thumbnail settings: the project ``config.yaml`` ``thumbnails.*`` map (D-2, D-11).

Two optional keys: ``position``, the fraction of a clip's duration the frame is taken
at, and ``cache_dir``, where the JPEGs are cached. Like ``worker.*``, the map is
opaque in :class:`~auto_reel_ng.config.project.ProjectConfig` and validated here, so
a wrong value fails loud with :class:`ConfigError` naming ``thumbnails.<key>``.

The cache is derived state that lives outside the library (the archive is often
mounted read-only), so the chosen directory, configured or default, is refused when
it falls inside the project root or the ``input`` directory the layout walks.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

from ..config.project import ConfigError, ProjectConfig

#: A quarter of the way in: past a camera clip's opening lens cap, ground or fade.
DEFAULT_POSITION = 0.25


@dataclass(frozen=True)
class ThumbnailSettings:
    """Resolved thumbnail settings: the frame position and the absolute cache directory."""

    position: float
    cache_dir: Path


def default_cache_dir() -> Path:
    """The cache used when ``config.yaml`` sets no ``thumbnails.cache_dir``.

    ``$XDG_CACHE_HOME/auto-reel/thumbnails`` when ``XDG_CACHE_HOME`` is an absolute
    path, else ``~/.cache/auto-reel/thumbnails``; a relative ``XDG_CACHE_HOME`` is
    ignored, as the XDG base-directory spec says.

    Raises:
        ConfigError: neither applies, because no home directory can be determined
            (no ``HOME`` and no passwd entry, as in some containers).
    """
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME", "")
    if xdg_cache_home and Path(xdg_cache_home).is_absolute():
        base = Path(xdg_cache_home)
    else:
        try:
            base = Path.home() / ".cache"
        except RuntimeError as exc:
            raise ConfigError(
                "thumbnails.cache_dir is not set and no home directory could be determined; "
                "set thumbnails.cache_dir"
            ) from exc
    return base / "auto-reel" / "thumbnails"


def resolve_thumbnail_settings(config: ProjectConfig, project_root: Path) -> ThumbnailSettings:
    """Validate ``config.thumbnails`` into :class:`ThumbnailSettings` (D-2).

    Unknown keys are ignored, as under ``worker``. A wrong-typed or out-of-range
    ``position``, a relative ``cache_dir``, and a cache directory inside the project
    root or its ``input`` directory each raise :class:`ConfigError` naming the key;
    nothing is clamped.
    """
    thumbnails = config.thumbnails
    position = _resolve_position(thumbnails.get("position"))
    configured = thumbnails.get("cache_dir")
    cache_dir = default_cache_dir() if configured is None else _resolve_cache_dir(configured)
    _require_outside_library(cache_dir, config, Path(project_root), defaulted=configured is None)
    return ThumbnailSettings(position=position, cache_dir=cache_dir)


def _resolve_position(value: object) -> float:
    """``thumbnails.position``: a finite number strictly between 0 and 1, else fail loud."""
    if value is None:
        return DEFAULT_POSITION
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 < value < 1
    ):
        return float(value)
    raise ConfigError(
        f"thumbnails.position must be a number between 0 and 1 (exclusive), got {value!r}"
    )


def _resolve_cache_dir(value: object) -> Path:
    """``thumbnails.cache_dir``: a path that is absolute once ``~`` is expanded."""
    if not isinstance(value, str):
        raise ConfigError(f"thumbnails.cache_dir must be a string, got {type(value).__name__}")
    try:
        path = Path(value).expanduser()
    except RuntimeError as exc:  # ``~user`` for an unknown user, or no home directory
        raise ConfigError(f"thumbnails.cache_dir cannot be expanded: {value!r}: {exc}") from exc
    if not path.is_absolute():
        # A relative path would name a different directory for ``serve`` and the CLI.
        raise ConfigError(
            f"thumbnails.cache_dir must be an absolute path (a leading ~ is expanded), "
            f"got {value!r}"
        )
    return path


def _require_outside_library(
    cache_dir: Path, config: ProjectConfig, project_root: Path, *, defaulted: bool
) -> None:
    """Refuse a cache directory inside the project root or the walked ``input`` directory.

    Symlinks are resolved on both sides, so a link into the library is caught too.
    Directories are also compared by identity (device and inode): on a
    case-insensitive mount such as the archive's NTFS drive, or through a bind
    mount, another spelling of a library directory is the same directory. The
    default is checked as well: an ``XDG_CACHE_HOME`` inside the library would
    otherwise put the cache there.
    """
    resolved = cache_dir.resolve()
    library_dirs = [("the project root", project_root.resolve())]
    if config.input_dir is not None:
        library_dirs.append(("the input directory", (project_root / config.input_dir).resolve()))
    for label, library_dir in library_dirs:
        if not (
            resolved.is_relative_to(library_dir) or _same_directory_above(resolved, library_dir)
        ):
            continue
        if defaulted:
            raise ConfigError(
                f"thumbnails.cache_dir is not set, and the default {cache_dir} lies inside "
                f"{label} {library_dir}; set thumbnails.cache_dir to a directory outside "
                "the library"
            )
        raise ConfigError(
            f"thumbnails.cache_dir {cache_dir} lies inside {label} {library_dir}; "
            "the thumbnail cache must be outside the library"
        )


def _same_directory_above(path: Path, directory: Path) -> bool:
    """True when ``path`` or one of its existing ancestors is ``directory`` itself.

    Compared with :func:`os.path.samestat`, so a differently spelled or mounted
    alias of ``directory`` counts. Ancestors that cannot be statted (not created
    yet) are skipped; a ``directory`` that does not exist holds nothing.
    """
    try:
        directory_stat = os.stat(directory)
    except OSError:
        return False
    for candidate in (path, *path.parents):
        try:
            candidate_stat = os.stat(candidate)
        except OSError:
            continue
        if os.path.samestat(candidate_stat, directory_stat):
            return True
    return False


__all__ = [
    "DEFAULT_POSITION",
    "ThumbnailSettings",
    "default_cache_dir",
    "resolve_thumbnail_settings",
]
