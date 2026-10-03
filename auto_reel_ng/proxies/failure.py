"""The failure marker: ``<cache_dir>/<key>.fail`` records why a clip's proxy could not be made.

A failed ``ensure_proxy`` leaves no entry (its build directory is removed), so nothing on disk
would say the clip was tried. The marker is a small JSON object ``{"reason": "<one line>"}``
beside the entry directory, as D-11 keeps ``<key>.fail`` beside a thumbnail, with two
differences. It has **no expiry**: a thumbnail is attempted on every page view, so its failure
must be forgotten after a minute, while a proxy is attempted only when an operator or a job
asks, and "did it fail" must not flip back to "never tried". And it is never cleaned up: a
complete entry outranks it (:func:`~.state.read_proxy_state`), and the key moves with the
file and the proxy version, so a changed clip never inherits it.

Writing is best effort and never replaces the attempt's own error; reading writes nothing.
The reason carries no absolute path (:func:`~auto_reel_ng.thumbs.one_line_cause`), on the way
in and on the way out, because the file is data a person could edit.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from ..errors import ProxyCacheError
from ..thumbs import one_line_cause

logger = logging.getLogger(__name__)

#: The marker's suffix: ``<key>.fail``.
MARKER_SUFFIX = ".fail"


def marker_path(cache_dir: Path, key: str) -> Path:
    """Where the failure marker of the entry ``key`` lives; computes only."""
    return Path(cache_dir) / f"{key}{MARKER_SUFFIX}"


def record_failure(cache_dir: Path, key: str, clip_path: Path, reason: str) -> None:
    """Record ``reason`` as the cause of the clip's failure under ``key``; never raises.

    Atomic (a temporary file, ``fsync``, rename) and best effort: a cache that cannot be written
    logs one warning and the caller's own error stands.
    """
    cause = one_line_cause(reason, clip_path) or "unknown failure"
    cache_dir = Path(cache_dir)
    tmp = cache_dir / f".{key}.{uuid.uuid4().hex}.tmp"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)  # umask applies
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"reason": cause}, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, marker_path(cache_dir, key))
        except BaseException:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise
    except OSError as exc:
        logger.warning(
            "Cannot record the proxy failure of %s in %s: %s", clip_path.name, cache_dir, exc
        )


def read_failure(cache_dir: Path, key: str, clip_path: Path) -> Optional[str]:
    """The recorded one-line cause for ``key``, or ``None`` when there is none to report.

    No marker, one that is not JSON, not an object or without a non-blank string ``reason`` is
    ``None`` (a damaged marker is not a cause). Runs no process and writes nothing.

    Raises:
        ProxyCacheError: the marker (or the cache directory) cannot be read for a reason other
            than not being there.
    """
    marker = marker_path(cache_dir, key)
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return None
    except ValueError as exc:  # invalid JSON or text
        logger.debug("Cannot use the recorded proxy failure %s: %s", marker, exc)
        return None
    except OSError as exc:
        raise ProxyCacheError(f"{marker.parent}: cannot read proxies: {exc}") from exc
    reason = document.get("reason") if isinstance(document, dict) else None
    if not isinstance(reason, str) or not reason.strip():
        return None
    return one_line_cause(reason, clip_path) or None


__all__ = ["MARKER_SUFFIX", "marker_path", "read_failure", "record_failure"]
