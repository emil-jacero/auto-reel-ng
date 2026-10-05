"""Sidecar cache for detection results under ``<event>/.auto-reel/cache/`` (D-AN4).

The sidecar is the source of truth: it travels with the media and survives a Postgres
rebuild. Each clip gets one JSON entry keyed by clip identity plus a content-change
signal (size + mtime by default, an optional content hash for correctness-sensitive
runs). When the signal differs the entry is stale and detection re-runs; a missing,
unreadable, or unparseable entry is treated as cold. The key shape is a deliberate,
forward-compatible down-payment on the §8.14 render fingerprint — the same family of
signals — without committing to that fingerprint's composition here.

An entry may instead be a **failure marker** (``analysis-job``): the same key, a
one-line ``failure`` cause and no ``segments``. It is not a result (:func:`read_entry`
answers ``None`` for it, as an older build does), but it lets the analysis job see that
the clip's current content already failed and not retry it in a loop.

Every write is atomic: the payload goes to a temporary file in the cache directory,
which is then renamed over the entry, so a concurrent reader sees the previous entry or
the complete new one. A temporary file a killed writer left behind is never read (its
name is not an entry's).

The on-disk format is private to this module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path
from typing import Dict, List, Optional, Union

from ..event.discovery import scan_event
from ..ffmpeg.runtime import FfmpegRuntime
from .models import AnalysisConfig, Segment, SegmentKind
from .runner import analyze_clip

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

#: Sidecar layout under the event directory and the entry-format version.
CACHE_SUBDIR = Path(".auto-reel") / "cache"
_ENTRY_VERSION = 1
_HASH_CHUNK = 1024 * 1024


def cache_dir(event_dir: PathLike) -> Path:
    """The ``.auto-reel/cache/`` directory for ``event_dir`` (not created here)."""
    return Path(event_dir) / CACHE_SUBDIR


def _entry_path(event_dir: PathLike, identity: str) -> Path:
    """Map a clip identity to its cache entry path.

    Identities are event-relative posix paths (which may contain ``/``), so the file
    name is a stable hash of the identity; the identity is also stored inside the
    entry for debuggability.
    """
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return cache_dir(event_dir) / f"{digest}.json"


def clip_signal(clip_path: PathLike, *, use_hash: bool = False) -> Dict[str, object]:
    """Compute the content-change signal for a clip (size+mtime, or a content hash)."""
    stat = Path(clip_path).stat()
    signal: Dict[str, object] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if use_hash:
        signal = {"size": stat.st_size, "sha256": _content_hash(Path(clip_path))}
    return signal


def _content_hash(clip_path: Path) -> str:
    """SHA-256 of the clip's bytes, streamed so large files stay out of memory."""
    digest = hashlib.sha256()
    with clip_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _segment_to_dict(segment: Segment) -> Dict[str, object]:
    return {
        "start": segment.start,
        "end": segment.end,
        "kind": segment.kind.value,
        "confidence": segment.confidence,
    }


def _segment_from_dict(data: Dict[str, object]) -> Segment:
    return Segment(
        start=float(data["start"]),  # type: ignore[arg-type]
        end=float(data["end"]),  # type: ignore[arg-type]
        kind=SegmentKind(data["kind"]),
        confidence=float(data["confidence"]),  # type: ignore[arg-type]
    )


def _write_atomic(path: Path, payload: Dict[str, object]) -> None:
    """Write ``payload`` as JSON to ``path`` through a temporary file and a rename.

    The temporary file lives beside ``path`` (same filesystem, so the rename is atomic),
    is flushed to disk before the rename, and is removed when any step fails.

    Raises:
        OSError: the directory cannot be created or written, or the rename failed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.part-{os.getpid()}-{secrets.token_hex(4)}")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_entry(
    event_dir: PathLike,
    identity: str,
    signal: Dict[str, object],
    segments: List[Segment],
) -> Path:
    """Write a cache entry for ``identity`` atomically and return its path (creating the dir).

    The entry replaces whatever was there, a failure marker included.

    Raises:
        OSError: the cache directory cannot be created or written.
    """
    path = _entry_path(event_dir, identity)
    _write_atomic(
        path,
        {
            "version": _ENTRY_VERSION,
            "identity": identity,
            "signal": signal,
            "segments": [_segment_to_dict(s) for s in segments],
        },
    )
    return path


def write_failure(
    event_dir: PathLike, identity: str, signal: Dict[str, object], reason: str
) -> Path:
    """Record atomically that analyzing ``identity`` at ``signal`` failed with ``reason``.

    The marker takes the entry's place (one file per clip) and carries no ``segments``,
    so every reader of results sees the clip as unanalyzed.

    Raises:
        OSError: the cache directory cannot be created or written.
    """
    path = _entry_path(event_dir, identity)
    _write_atomic(
        path,
        {
            "version": _ENTRY_VERSION,
            "identity": identity,
            "signal": signal,
            "failure": reason,
        },
    )
    return path


def _read_payload(
    event_dir: PathLike, identity: str, signal: Dict[str, object]
) -> Optional[Dict[str, object]]:
    """The parsed entry of ``identity`` when it is of this version and for ``signal``."""
    path = _entry_path(event_dir, identity)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != _ENTRY_VERSION:
        return None
    if payload.get("signal") != signal:
        return None  # stale: the clip changed since this entry was written
    return payload


class EntryFileKind(StrEnum):
    """What a clip's sidecar entry file holds, judged against the clip's current signal."""

    #: No entry file: the clip was never analyzed, and never failed.
    ABSENT = "absent"
    #: A result (segments) for the clip as it is now.
    RESULT = "result"
    #: A failure marker for the clip as it is now.
    FAILURE = "failure"
    #: Anything else: an entry or marker for another signal, another version, or unparseable.
    OTHER = "other"


@dataclass(frozen=True)
class EntryRecord:
    """:func:`inspect_entry`'s answer: the entry's kind, with its segments or its cause."""

    kind: EntryFileKind
    segments: Optional[List[Segment]] = None
    failure: Optional[str] = None


def inspect_entry(event_dir: PathLike, identity: str, signal: Dict[str, object]) -> EntryRecord:
    """Tell what the entry of ``identity`` holds for ``signal``, without the "cold" softening.

    For the analysis state (``analysis-enqueue-api``): unlike :func:`read_entry`, an entry file
    that is absent (:attr:`EntryFileKind.ABSENT`) is told apart from one that exists but is of
    another signal or version or cannot be parsed (:attr:`EntryFileKind.OTHER`), and a file that
    exists but cannot be read raises. Reads one file; never writes.

    Raises:
        OSError: the entry file exists but cannot be read (any error but its absence).
    """
    path = _entry_path(event_dir, identity)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return EntryRecord(EntryFileKind.ABSENT)
    except UnicodeDecodeError:  # bytes that are not text: not an entry this build wrote
        return EntryRecord(EntryFileKind.OTHER)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return EntryRecord(EntryFileKind.OTHER)
    if (
        not isinstance(payload, dict)
        or payload.get("version") != _ENTRY_VERSION
        or payload.get("signal") != signal
    ):
        return EntryRecord(EntryFileKind.OTHER)
    if "segments" in payload:
        try:
            segments = [_segment_from_dict(s) for s in payload["segments"]]
        except (KeyError, TypeError, ValueError):
            return EntryRecord(EntryFileKind.OTHER)
        return EntryRecord(EntryFileKind.RESULT, segments=segments)
    failure = payload.get("failure")
    if isinstance(failure, str):
        return EntryRecord(EntryFileKind.FAILURE, failure=failure)
    return EntryRecord(EntryFileKind.OTHER)


def read_failure(event_dir: PathLike, identity: str, signal: Dict[str, object]) -> Optional[str]:
    """The recorded cause when analyzing ``identity`` at ``signal`` failed, else ``None``.

    A marker for another signal (the clip changed since) is not a failure of this one.
    """
    payload = _read_payload(event_dir, identity, signal)
    if payload is None or "segments" in payload:
        return None
    failure = payload.get("failure")
    return failure if isinstance(failure, str) else None


def read_entry(
    event_dir: PathLike, identity: str, signal: Dict[str, object]
) -> Optional[List[Segment]]:
    """Read cached segments for ``identity`` if the entry is valid, else ``None``.

    Returns ``None`` (treat as cold/stale, re-run) when the entry is missing,
    unreadable, unparseable, of an unknown version, a failure marker, or its stored
    signal differs from ``signal``.
    """
    payload = _read_payload(event_dir, identity, signal)
    if payload is None:
        return None
    try:
        raw_segments = payload["segments"]  # a failure marker has none: not a result
        return [_segment_from_dict(s) for s in raw_segments]  # type: ignore[attr-defined]
    except (KeyError, TypeError, ValueError):
        return None


class EntryKind(Enum):
    """What the sidecar holds for a clip at its current signal (the three entry states)."""

    #: An entry for this signal: the clip's segments (possibly none) are known.
    CURRENT = "current"
    #: A failure marker for this signal: analyzing this content failed; not a result.
    FAILED = "failed"
    #: Anything else (no file, unreadable, another version or signal): it needs analysis.
    MISSING = "missing"


@dataclass(frozen=True)
class EntryState:
    """A clip's :class:`EntryKind` and, for ``FAILED``, the recorded one-line cause."""

    kind: EntryKind
    failure: Optional[str] = None


def entry_state(event_dir: PathLike, identity: str, signal: Dict[str, object]) -> EntryState:
    """The sidecar's state for ``identity`` at ``signal``: current, failed (with cause) or missing.

    The one rule that decides whether a non-forced run analyzes a clip (``missing`` only),
    shared by the ``analysis`` job and the worker's automatic sweep so they never disagree.
    Reads one small JSON file; never runs ffmpeg or ffprobe and never reads the clip.
    """
    if read_entry(event_dir, identity, signal) is not None:
        return EntryState(EntryKind.CURRENT)
    failure = read_failure(event_dir, identity, signal)
    if failure is not None:
        return EntryState(EntryKind.FAILED, failure)
    return EntryState(EntryKind.MISSING)


def pending_clips(event_dir: PathLike) -> List[str]:
    """The identities a non-forced analysis of ``event_dir`` would analyze, in listing order.

    Every clip discovery lists (IGNORED included, as the job does) whose :func:`entry_state`
    at its size+mtime signal is ``MISSING``. Metadata only: a directory listing, one ``stat``
    and one small JSON read per clip; no ffprobe, no ffmpeg, no content hash, no write.

    Raises:
        OSError: the event folder cannot be listed or a clip cannot be statted.
    """
    event_path = Path(event_dir)
    return [
        identity
        for identity in scan_event(event_path).identities
        if entry_state(event_path, identity, clip_signal(event_path / identity)).kind
        is EntryKind.MISSING
    ]


def analyze_event(
    event_dir: PathLike,
    *,
    runtime: Optional[FfmpegRuntime] = None,
    config: Optional[AnalysisConfig] = None,
    use_hash: bool = False,
    force: bool = False,
) -> Dict[str, List[Segment]]:
    """Analyze every clip in ``event_dir``, using the sidecar cache.

    For each clip: a valid cached entry is returned with no ffmpeg pass (warm); a
    missing/stale/unparseable entry triggers :func:`analyze_clip` and the fresh
    result is written back (cold). Returns a mapping of clip identity to its segments.
    ``force`` ignores every existing entry and detects each clip again. Failure markers
    are never read here: the first clip that cannot be analyzed raises, as it always has.

    This is an explicit pass and never runs as a side effect of scanning.
    """
    event_path = Path(event_dir)
    listing = scan_event(event_path)
    results: Dict[str, List[Segment]] = {}

    for identity in listing.identities:
        clip_path = event_path / identity
        signal = clip_signal(clip_path, use_hash=use_hash)

        cached = None if force else read_entry(event_path, identity, signal)
        if cached is not None:
            logger.debug("Analysis cache hit for %s", identity)
            results[identity] = cached
            continue

        segments = analyze_clip(clip_path, runtime=runtime, config=config)
        write_entry(event_path, identity, signal, segments)
        results[identity] = segments

    return results
