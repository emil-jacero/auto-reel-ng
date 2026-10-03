"""Proxy settings: the project ``config.yaml`` ``proxies.*`` map (D-2, D-21).

One optional key, ``cache_dir``, where the proxies are cached. Like ``thumbnails.*``, the
map is opaque in :class:`~auto_reel_ng.config.project.ProjectConfig` and validated here, so
a wrong value fails loud with :class:`ConfigError` naming ``proxies.cache_dir``. The
contract's own values (short side, CRF, keyframe interval, audio rate) are constants of
:mod:`~auto_reel_ng.proxies.spec`, not settings.

The cache is derived state that lives outside the library (the archive is often mounted
read-only, and a USB drive is the wrong place for 40 GB of scratch), so the chosen
directory, configured or default, is refused when it falls inside the project root or the
``input`` directory the layout walks. The three location helpers are copies of the ones in
``thumbs/settings.py`` with the key and the leaf name changed: sharing them would mean
editing ``thumbs/`` for no requirement (HLD D-21 records the duplication).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..config.project import ConfigError, ProjectConfig


@dataclass(frozen=True)
class ProxySettings:
    """Resolved proxy settings: the absolute cache directory."""

    cache_dir: Path


def default_cache_dir() -> Path:
    """The cache used when ``config.yaml`` sets no ``proxies.cache_dir``.

    ``$XDG_CACHE_HOME/auto-reel/proxies`` when ``XDG_CACHE_HOME`` is an absolute path, else
    ``~/.cache/auto-reel/proxies``; a relative ``XDG_CACHE_HOME`` is ignored, as the XDG
    base-directory spec says.

    Raises:
        ConfigError: neither applies, because no home directory can be determined (no
            ``HOME`` and no passwd entry, as in some containers).
    """
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME", "")
    if xdg_cache_home and Path(xdg_cache_home).is_absolute():
        base = Path(xdg_cache_home)
    else:
        try:
            base = Path.home() / ".cache"
        except RuntimeError as exc:
            raise ConfigError(
                "proxies.cache_dir is not set and no home directory could be determined; "
                "set proxies.cache_dir"
            ) from exc
    return base / "auto-reel" / "proxies"


def resolve_proxy_settings(config: ProjectConfig, project_root: Path) -> ProxySettings:
    """Validate ``config.proxies`` into :class:`ProxySettings` (D-2).

    Unknown keys are ignored, as under ``thumbnails``. A relative or non-string
    ``cache_dir``, and a cache directory inside the project root or its ``input``
    directory, each raise :class:`ConfigError` naming ``proxies.cache_dir``; nothing is
    clamped or corrected.
    """
    configured = config.proxies.get("cache_dir")
    cache_dir = default_cache_dir() if configured is None else _resolve_cache_dir(configured)
    _require_outside_library(cache_dir, config, Path(project_root), defaulted=configured is None)
    return ProxySettings(cache_dir=cache_dir)


def _resolve_cache_dir(value: object) -> Path:
    """``proxies.cache_dir``: a path that is absolute once ``~`` is expanded."""
    if not isinstance(value, str):
        raise ConfigError(f"proxies.cache_dir must be a string, got {type(value).__name__}")
    try:
        path = Path(value).expanduser()
    except RuntimeError as exc:  # ``~user`` for an unknown user, or no home directory
        raise ConfigError(f"proxies.cache_dir cannot be expanded: {value!r}: {exc}") from exc
    if not path.is_absolute():
        # A relative path would name a different directory for ``serve`` and the CLI.
        raise ConfigError(
            f"proxies.cache_dir must be an absolute path (a leading ~ is expanded), "
            f"got {value!r}"
        )
    return path


def _require_outside_library(
    cache_dir: Path, config: ProjectConfig, project_root: Path, *, defaulted: bool
) -> None:
    """Refuse a cache directory inside the project root or the walked ``input`` directory.

    Symlinks are resolved on both sides, so a link into the library is caught too.
    Directories are also compared by identity (device and inode): on a case-insensitive
    mount such as the archive's NTFS drive, or through a bind mount, another spelling of a
    library directory is the same directory. The default is checked as well: an
    ``XDG_CACHE_HOME`` inside the library would otherwise put the cache there.
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
                f"proxies.cache_dir is not set, and the default {cache_dir} lies inside "
                f"{label} {library_dir}; set proxies.cache_dir to a directory outside "
                "the library"
            )
        raise ConfigError(
            f"proxies.cache_dir {cache_dir} lies inside {label} {library_dir}; "
            "the proxy cache must be outside the library"
        )


def _same_directory_above(path: Path, directory: Path) -> bool:
    """True when ``path`` or one of its existing ancestors is ``directory`` itself.

    Compared with :func:`os.path.samestat`, so a differently spelled or mounted alias of
    ``directory`` counts. Ancestors that cannot be statted (not created yet) are skipped; a
    ``directory`` that does not exist holds nothing.
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


__all__ = ["ProxySettings", "default_cache_dir", "resolve_proxy_settings"]
