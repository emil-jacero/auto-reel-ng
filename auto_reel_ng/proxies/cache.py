"""The proxy cache: entry directories, atomic publish and the stale-build sweep (D-21).

An entry is a directory ``<cache_dir>/<key>/`` holding ``proxy.mp4`` and ``facts.json``. A
build happens in a hidden sibling ``.<key>.<unique>.part``; once the proxy is verified and
both files are flushed the whole directory is renamed to ``<key>``, so a reader never sees
half an entry: a killed, cancelled or failed encode leaves nothing that looks complete. The
cache is a rebuildable file cache (never Postgres, D-7) and nothing is evicted.

Every filesystem failure on the cache directory is a :class:`ProxyCacheError`, kept apart from
:class:`ProxyError` (a property of one clip), as for thumbnails (D-11).
"""

from __future__ import annotations

import errno
import logging
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

from ..errors import ProxyCacheError
from . import spec
from .facts import ProxyFacts, read_facts

logger = logging.getLogger(__name__)

#: A hidden build directory older than this many seconds belongs to an encode that was killed
#: (an encode that advances is never anywhere near this old).
STALE_PART_AGE = 24 * 60 * 60

#: The engine's build-directory name: ``.<sha256 key>.<uuid4 hex>.part``.
_PART_NAME = re.compile(r"^\.[0-9a-f]{64}\.[0-9a-f]{32}\.part$")

#: What ffmpeg (the C library's ``strerror``) prints when the cache's disk or quota is full.
FULL_DISK_PHRASES = ("No space left on device", "Disk quota exceeded")

#: Cache directories this process has already swept, and the lock that guards the set.
_swept: Set[Path] = set()
_swept_lock = threading.Lock()

#: How often a publish retries when another process keeps winning or replacing the entry.
_PUBLISH_ATTEMPTS = 3


@dataclass(frozen=True)
class ProxyEntry:
    """A complete cache entry: both files exist and the facts are valid."""

    key: str
    directory: Path
    proxy_path: Path
    facts_path: Path
    facts: ProxyFacts
    #: True when the call that returned this entry built it; False for a cache hit or when
    #: another process finished first.
    generated: bool = False


def read_entry(directory: Path) -> Optional[ProxyEntry]:
    """The complete entry at ``directory``, or ``None`` when it is absent or incomplete.

    One ``stat`` of the proxy and one JSON read of the facts; no process. A directory that
    lacks either file, or whose facts are damaged or from another version, is absent.

    Raises:
        ProxyCacheError: the cache directory cannot be read (not merely absent).
    """
    proxy_path = directory / spec.PROXY_FILENAME
    facts_path = directory / spec.FACTS_FILENAME
    try:
        if not proxy_path.is_file():
            return None
    except OSError as exc:  # Python 3.13's is_file lets a PermissionError through
        raise ProxyCacheError(f"{directory.parent}: cannot read proxies: {exc}") from exc
    facts = read_facts(facts_path)
    if facts is None:
        return None
    return ProxyEntry(
        key=directory.name,
        directory=directory,
        proxy_path=proxy_path,
        facts_path=facts_path,
        facts=facts,
    )


def new_part_dir(cache_dir: Path, key: str) -> Path:
    """Create the cache directory (when absent), sweep it once, and make a fresh build directory.

    Creating the directory before ffmpeg runs classifies a missing, read-only or forbidden
    cache as the cache's fault, not as ffmpeg failing on this clip.

    Raises:
        ProxyCacheError: the cache directory cannot be created or written.
    """
    part = cache_dir / f".{key}.{uuid.uuid4().hex}.part"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        sweep_once(cache_dir)
        part.mkdir()
    except OSError as exc:
        raise ProxyCacheError(f"{cache_dir}: cannot write proxies: {exc}") from exc
    return part


def discard(directory: Path) -> None:
    """Remove a build directory, best effort: a failure is logged, never raised."""
    try:
        shutil.rmtree(directory)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Cannot remove the proxy build directory %s: %s", directory, exc)


def publish(part: Path, entry: Path) -> ProxyEntry:
    """Flush the build directory ``part`` and rename it to ``entry``; return the entry.

    The proxy and the facts are ``fsync``ed, then the directory, then renamed (and the cache
    directory ``fsync``ed). When another process finished first the build is discarded and
    its complete entry is returned (with ``generated`` False); an incomplete ``entry``
    directory is removed and replaced. The caller removes ``part`` on failure.

    Raises:
        ProxyCacheError: the files cannot be flushed or the directory cannot be renamed.
    """
    cache_dir = entry.parent
    try:
        for name in (spec.PROXY_FILENAME, spec.FACTS_FILENAME):
            fsync(part / name)
        fsync(part)
        for _ in range(_PUBLISH_ATTEMPTS):
            winner = read_entry(entry)
            if winner is not None:
                logger.debug("Another process published %s first; discarding this build", entry)
                discard(part)
                return winner
            if entry.exists():
                # Another process may have renamed its complete build in since the read above:
                # look again, and remove only what is still incomplete.
                winner = read_entry(entry)
                if winner is not None:
                    logger.debug("Another process published %s first; discarding", entry)
                    discard(part)
                    return winner
                shutil.rmtree(entry, ignore_errors=True)  # an incomplete leftover
            try:
                os.rename(part, entry)
            except OSError as exc:
                if exc.errno in (errno.ENOTEMPTY, errno.EEXIST):
                    continue  # lost the race: look at the winner on the next pass
                raise
            fsync(cache_dir)
            published = read_entry(entry)
            if published is None:
                raise ProxyCacheError(f"{entry}: the published proxy entry is incomplete")
            return ProxyEntry(
                key=published.key,
                directory=published.directory,
                proxy_path=published.proxy_path,
                facts_path=published.facts_path,
                facts=published.facts,
                generated=True,
            )
    except OSError as exc:
        raise ProxyCacheError(f"{cache_dir}: cannot write proxies: {exc}") from exc
    raise ProxyCacheError(
        f"{entry}: could not publish the proxy; another process keeps replacing it"
    )


def fsync(path: Path) -> None:
    """``fsync`` a file or a directory."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def is_full_disk(stderr_text: str) -> Optional[str]:
    """The full-disk phrase in ffmpeg's stderr part of a failed command's message, if any.

    Only the text after ``stderr:`` counts: the quoted command above it holds the clip's file
    name, which may say anything.
    """
    _, _, stderr = stderr_text.partition("\nstderr:\n")
    return next((phrase for phrase in FULL_DISK_PHRASES if phrase in stderr), None)


def sweep_stale_parts(
    cache_dir: Path, *, older_than: float = STALE_PART_AGE, now: Optional[float] = None
) -> int:
    """Delete the engine's hidden build directories in ``cache_dir`` untouched for ``older_than`` s.

    A candidate is a real directory (not a symlink) directly in ``cache_dir`` named
    ``.<64 hex>.<32 hex>.part`` whose modification time is more than ``older_than`` seconds
    before ``now`` (epoch seconds, default the current time). A younger one may belong to a
    concurrent build; entries and every other name are never touched. Never raises: an
    unreadable directory or one that will not go is logged and left.

    Returns:
        How many directories were removed.
    """
    now = time.time() if now is None else now
    removed = 0
    try:
        with os.scandir(cache_dir) as entries:
            for entry in entries:
                try:
                    if not _PART_NAME.match(entry.name):
                        continue
                    if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                        continue
                    if now - entry.stat(follow_symlinks=False).st_mtime <= older_than:
                        continue
                    shutil.rmtree(entry.path)
                    removed += 1
                except OSError as exc:
                    logger.warning("Cannot sweep %s: %s", entry.path, exc)
    except OSError as exc:
        logger.warning("Cannot sweep %s: %s", cache_dir, exc)
    return removed


def sweep_once(cache_dir: Path) -> None:
    """Sweep ``cache_dir`` the first time this process asks, and never raise."""
    try:
        key = cache_dir.resolve()
        with _swept_lock:
            if key in _swept:
                return
            _swept.add(key)  # marked before the scan: a failing scan is not retried in a loop
        removed = sweep_stale_parts(cache_dir)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Cannot sweep %s: %s", cache_dir, exc)
        return
    if removed:
        logger.info("Removed %d stale proxy build directories from %s", removed, cache_dir)


__all__ = [
    "FULL_DISK_PHRASES",
    "STALE_PART_AGE",
    "ProxyEntry",
    "discard",
    "fsync",
    "is_full_disk",
    "new_part_dir",
    "publish",
    "read_entry",
    "sweep_once",
    "sweep_stale_parts",
]
