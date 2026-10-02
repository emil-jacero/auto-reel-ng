"""One JPEG thumbnail per clip, cached outside the library (D-11).

The frame is the one at ``position × duration``, where the duration is the engine's
own ffprobe result (Principle I: never guessed). Extraction is attempted exactly
once: a clip with no frame at that time has no thumbnail, and no other timestamp,
first frame or placeholder is tried in its place.

The pure pieces — :func:`thumbnail_key`, :func:`thumbnail_path` and
:func:`thumbnail_args` — compute the cache location and the ffmpeg arguments;
:func:`thumbnail_for` composes them around one probe and one ffmpeg run through
:class:`FfmpegRuntime`. The cache key covers the resolved file's name (not its
directory), its size and ``mtime_ns``, the position, the box and
:data:`THUMBNAIL_VERSION`, so a changed clip gets a new file by itself, a library
that is moved, copied or remounted keeps its cache, and a cache hit costs one
``stat`` and one hash. Files are written like ``reel/writer.write_document``: a
uniquely named hidden temporary file, ``fsync``, then ``os.replace``, so
``<key>.jpg`` only ever appears complete.

A clip the engine's probe flags as HDR (PQ or HLG) is tone-mapped to SDR on the CPU with the
renderer's own chain before it is scaled. A full cache disk is one :class:`ThumbnailCacheError`,
not a failure of the clip, and temporaries that a killed extraction left behind are swept once
per process (:func:`sweep_stale_temporaries`).

Two small sidecars sit beside ``<key>.jpg``, named by the same key so they inherit its
invalidation and written atomically like it: ``<key>.json`` holds the duration the probe
reported (:func:`recorded_duration` reads it with no process), and ``<key>.fail`` holds the
reason a clip failed, remembered for :data:`FAILURE_TTL_SECONDS` so a broken clip is not
re-probed on every request (:func:`recorded_failure`). Neither is a thumbnail, and a cache
fault is never remembered against a clip.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import List, NamedTuple, Optional, Set

from ..accel.profiles.cpu import CPU_TONEMAP_FILTER
from ..errors import (
    FfmpegError,
    FfmpegTimeoutError,
    ProbeError,
    ThumbnailCacheError,
    ThumbnailError,
)
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe.media import get_default_runtime, probe_media

logger = logging.getLogger(__name__)

#: Seconds the probe, and then the extraction, of one clip are each given. A healthy
#: thumbnail takes well under a second; the bound frees a service extraction slot when a
#: read stalls (a removable drive that went away). Fixed: not a ``config.yaml`` setting.
THUMBNAIL_TIMEOUT = 60.0

#: Bump whenever :func:`thumbnail_args` changes the output bytes for any input class, or the
#: key's payload changes: it re-keys every file. 2: the key holds the file's name, not its
#: path. 3: an HDR clip is tone-mapped (the key is computed before any probe, so it cannot
#: carry an ``hdr`` flag; a cache hit must not run ffprobe).
THUMBNAIL_VERSION = 3

#: Seconds a clip's failure is remembered in ``<key>.fail``, counted from the failed attempt.
#: Fixed: not a ``config.yaml`` setting.
FAILURE_TTL_SECONDS = 60.0

#: A hidden temporary file older than this many seconds belongs to an extraction that was
#: killed, not to a live writer (an extraction is bounded to :data:`THUMBNAIL_TIMEOUT`).
STALE_TEMPORARY_AGE = 24 * 60 * 60

#: The engine's temporary-file name: ``.<sha256 key>.<uuid4 hex>.tmp``.
_TEMPORARY_NAME = re.compile(r"^\.[0-9a-f]{64}\.[0-9a-f]{32}\.tmp$")

#: What ffmpeg (the C library's ``strerror``) prints when the cache's disk or quota is full.
_FULL_DISK_PHRASES = ("No space left on device", "Disk quota exceeded")

#: Cache directories this process has already swept, and the lock that guards the set.
_swept: Set[Path] = set()
_swept_lock = threading.Lock()

#: The ``(width, height)`` box a thumbnail is fitted inside, keeping its aspect ratio.
THUMBNAIL_BOX = (320, 180)

#: How :class:`FfmpegRuntime` reports a failed command inside a reason.
_FAILED_COMMAND = re.compile(r": Command exited -?\d+: ")

#: ffmpeg's ``[component @ 0x…]`` prefixes on a stderr line.
_LOG_TAGS = re.compile(r"^(?:\[[^\]]*\]\s*)+")

#: Where an absolute path starts in a message: a ``/`` opening a word or a quoted or
#: bracketed value (``'0/0'`` and ``in#0/mov`` do not start one).
_ABSOLUTE_PATH = re.compile(r"(?:^|(?<=[\s'\"(\[=]))/(?=[^\s/])")


def thumbnail_key(clip_path: Path, *, position: float) -> str:
    """The cache key: sha256 hex over the clip's file name, stat signal and settings.

    Symlinks are followed, so every link to one file shares one key, and the name
    hashed is the file's own, not a link's. The directory is left out on purpose: a
    library that is moved, copied or remounted keeps its cache. Two different files
    with the same name, size and ``mtime_ns`` would share a key (negligible for camera
    clips; deleting the cache directory repairs it). The stat's
    :class:`OSError` propagates unchanged (``FileNotFoundError`` for a vanished clip);
    each caller decides what it means.
    """
    resolved = Path(clip_path).resolve()
    stat = resolved.stat()
    # A JSON list is a canonical, unambiguous encoding; ensure_ascii keeps a
    # non-UTF-8 file name (surrogate escapes) encodable.
    payload = json.dumps(
        [
            resolved.name,
            stat.st_size,
            stat.st_mtime_ns,
            position,
            list(THUMBNAIL_BOX),
            THUMBNAIL_VERSION,
        ]
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def thumbnail_path(clip_path: Path, *, position: float, cache_dir: Path) -> Path:
    """Where the clip's thumbnail is cached: ``<cache_dir>/<key>.jpg``.

    Computes only: nothing is created or generated. The stat's :class:`OSError`
    propagates unchanged, as in :func:`thumbnail_key`.
    """
    return Path(cache_dir) / f"{thumbnail_key(clip_path, position=position)}.jpg"


def is_cached(target: Path) -> bool:
    """True when the thumbnail file ``target`` exists; a cache that cannot be read raises.

    Python 3.13's ``Path.is_file`` lets a ``PermissionError`` through (an unsearchable
    cache directory); that is the cache's fault, never a clip's.

    Raises:
        ThumbnailCacheError: the cache directory cannot be read.
    """
    try:
        return target.is_file()
    except OSError as exc:
        raise ThumbnailCacheError(f"{target.parent}: cannot read thumbnails: {exc}") from exc


def thumbnail_args(clip: Path, *, at: float, output: Path, hdr: bool = False) -> List[str]:
    """The ffmpeg arguments that write the frame at ``at`` seconds of ``clip`` as a JPEG.

    Input seek (``-ss`` before ``-i``) lands on the frame at ``at``; CPU decode (no
    ``-hwaccel``) applies the container's display rotation before the filters. The
    first ``scale`` makes pixels square so anamorphic footage is not squashed, the
    second fits the box keeping the aspect ratio. ``-update 1`` makes ``image2``
    write ``output`` literally, so a ``%`` in the cache path is never a pattern.

    With ``hdr`` (the probe flagged the clip PQ or HLG) the render's CPU tone-map chain comes
    first, ahead of both scales, so the frame is SDR before it is resized; otherwise the
    arguments are exactly those of an SDR clip.
    """
    width, height = THUMBNAIL_BOX
    scales = (
        "scale=trunc(iw*sar/2)*2:ih,"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1"
    )
    return [
        "-hide_banner",
        "-nostdin",
        "-v",
        "error",
        "-ss",
        f"{at:.3f}",
        "-i",
        str(clip),
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-vf",
        f"{CPU_TONEMAP_FILTER},{scales}" if hdr else scales,
        "-c:v",
        "mjpeg",
        "-q:v",
        "5",
        "-f",
        "image2",
        "-update",
        "1",
        "-y",
        str(output),
    ]


def thumbnail_for(
    clip_path: Path,
    *,
    position: float,
    cache_dir: Path,
    runtime: Optional[FfmpegRuntime] = None,
) -> Path:
    """The cached JPEG for the clip, generating it first when absent.

    A cache hit returns without running ffprobe or ffmpeg. A clip whose failure was recorded
    less than :data:`FAILURE_TTL_SECONDS` ago raises that failure, also with no process. A
    miss probes the clip's resolved path for its duration (recorded in ``<key>.json``),
    extracts the frame at ``position × duration`` (tone-mapped first when the probe flags the
    clip HDR) into a temporary file in ``cache_dir`` (created when absent, and swept of stale
    temporaries once per process), ``fsync``s it and renames it to ``<key>.jpg``. The source
    clip is only read. On any failure, interruption included, the temporary file is removed;
    a :class:`ThumbnailError` is also recorded in ``<key>.fail``, a success removes it.

    Raises:
        ThumbnailError: the clip cannot be statted or probed, has no usable
            duration, or gave no frame at that time (or this was recorded in the last
            minute); the message starts with the clip's path, and ``reason`` names the
            cause without it.
        ThumbnailCacheError: ``cache_dir`` cannot be created, read or written, or is full.
    """
    clip_path = Path(clip_path)
    cache_dir = Path(cache_dir)
    try:
        key = thumbnail_key(clip_path, position=position)
    except OSError as exc:
        raise ThumbnailError(str(clip_path), f"cannot stat the clip: {_os_reason(exc)}") from exc
    target = cache_dir / f"{key}.jpg"
    if is_cached(target):
        return target
    # Outside the recording handler below: reading a failure must not renew it.
    failure = recorded_failure(clip_path, target)
    if failure is not None:
        raise failure

    try:
        generated = _generate(
            clip_path,
            key=key,
            target=target,
            cache_dir=cache_dir,
            position=position,
            runtime=runtime,
        )
    except ThumbnailError as exc:
        _record_failure(target, exc.reason)
        raise
    with contextlib.suppress(OSError):
        _sidecar(target, ".fail").unlink()
    return generated


def _generate(
    clip_path: Path,
    *,
    key: str,
    target: Path,
    cache_dir: Path,
    position: float,
    runtime: Optional[FfmpegRuntime],
) -> Path:
    """Probe the clip, record its duration, extract the frame and rename it to ``target``."""
    runtime = (runtime or get_default_runtime()).with_timeout(THUMBNAIL_TIMEOUT)
    # The resolved, absolute path: a relative ``file:x.mp4`` would be read as a protocol.
    source = clip_path.resolve()
    probed = _probe_clip(clip_path, source, runtime)
    duration = probed.duration
    at = position * duration

    tmp = cache_dir / f".{key}.{uuid.uuid4().hex}.tmp"
    try:
        _create_temporary(cache_dir, tmp)
        _record_duration(cache_dir, target, duration)
        _extract(clip_path, source, runtime, at=at, duration=duration, hdr=probed.hdr, output=tmp)
        _finalize(cache_dir, tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    logger.debug("Thumbnail of %s at %.3fs: %s", clip_path, at, target)
    return target


def _sidecar(target: Path, suffix: str) -> Path:
    """The sidecar beside the JPEG ``target``: the same key with ``.json`` or ``.fail``."""
    return target.with_suffix(suffix)


def _write_sidecar(cache_dir: Path, target: Path, suffix: str, payload: object) -> None:
    """Write ``payload`` as JSON to the sidecar of ``target``: temporary, ``fsync``, rename.

    The temporary has the engine's temporary-file name, so a crash mid-write is swept like
    a crashed extraction. It is removed on any failure; an :class:`OSError` propagates.
    """
    destination = _sidecar(target, suffix)
    tmp = cache_dir / f".{target.stem}.{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)  # umask applies
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, destination)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def _record_duration(cache_dir: Path, target: Path, duration: float) -> None:
    """Record the probed ``duration`` in ``<key>.json``; failing to write it is a cache error."""
    try:
        _write_sidecar(cache_dir, target, ".json", {"duration": duration})
    except OSError as exc:
        raise ThumbnailCacheError(f"{cache_dir}: cannot write thumbnails: {exc}") from exc


def recorded_duration(target: Path) -> Optional[float]:
    """The duration recorded beside the thumbnail ``target``, or ``None`` when unknown.

    Reads ``<key>.json`` and nothing else: no ffprobe, no ffmpeg, no write. The file being
    absent or unreadable, not a JSON object, or holding a ``duration`` that is not a number
    (a bool is not one), not finite or not positive all read as ``None``; a damaged file is
    never turned into a number and this never raises.
    """
    sidecar = _sidecar(Path(target), ".json")
    try:
        document = json.loads(sidecar.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:  # ValueError: invalid JSON or text
        logger.debug("Cannot use the recorded duration %s: %s", sidecar, exc)
        return None
    duration = document.get("duration") if isinstance(document, dict) else None
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        return None
    if not math.isfinite(duration) or duration <= 0:
        return None
    return float(duration)


def recorded_failure(clip_path: Path, target: Path) -> Optional[ThumbnailError]:
    """The :class:`ThumbnailError` recorded for the thumbnail ``target`` if it is still fresh.

    Fresh means ``<key>.fail`` is valid JSON with a string ``reason`` and was written less
    than :data:`FAILURE_TTL_SECONDS` ago (its modification time; a time in the future counts
    as expired). Expired, damaged or absent is ``None`` and the clip is attempted again. Runs
    no process and writes nothing, so reading never renews the window.

    Raises:
        ThumbnailCacheError: the cache directory cannot be read.
    """
    marker = _sidecar(Path(target), ".fail")
    try:
        age = time.time() - marker.stat().st_mtime
        if not 0 <= age < FAILURE_TTL_SECONDS:
            return None
        document = json.loads(marker.read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):  # no such marker
        return None
    except ValueError as exc:  # invalid JSON or text
        logger.debug("Cannot use the recorded failure %s: %s", marker, exc)
        return None
    except OSError as exc:
        raise ThumbnailCacheError(f"{marker.parent}: cannot read thumbnails: {exc}") from exc
    reason = document.get("reason") if isinstance(document, dict) else None
    if not isinstance(reason, str):
        return None
    return ThumbnailError(str(clip_path), reason)


def _record_failure(target: Path, reason: str) -> None:
    """Remember a clip's failure in ``<key>.fail``; best effort, never replaces the error."""
    cache_dir = target.parent
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _write_sidecar(cache_dir, target, ".fail", {"reason": reason})
    except OSError as exc:
        logger.warning("Cannot record the thumbnail failure in %s: %s", cache_dir, exc)


class _Probed(NamedTuple):
    """What a thumbnail takes from the one probe of a clip."""

    duration: float
    hdr: bool


def _probe_clip(clip_path: Path, source: Path, runtime: FfmpegRuntime) -> _Probed:
    """The clip's ffprobe duration and HDR flag; a probe failure or no usable duration raises."""
    try:
        metadata = probe_media(source, runtime=runtime)
    except ProbeError as exc:
        raise ThumbnailError(str(clip_path), _probe_reason(exc, source)) from exc
    duration = metadata.duration
    # The probe reports 0.0 when neither the format nor the stream carries one.
    if not math.isfinite(duration) or duration <= 0:
        raise ThumbnailError(str(clip_path), f"ffprobe reported no usable duration ({duration})")
    return _Probed(duration, bool(metadata.is_hdr))


def _probe_reason(exc: ProbeError, source: Path) -> str:
    """The probe's message without the probed path, which the error names already.

    Probe messages name the path after ``:``, ``for``, ``in`` or a plain space; only
    that first mention is dropped, so a failing ffprobe command quoted after it keeps
    its arguments. A message of another shape is kept verbatim.
    """
    message = str(exc)
    for mention in (f": {source}", f" for {source}", f" in {source}", f" {source}"):
        if mention in message:
            return message.replace(mention, "", 1)
    return message


def one_line_cause(reason: str, clip_path: Path) -> str:
    """The one-line cause of a :class:`ThumbnailError`'s ``reason``, without server paths.

    What a clip's failure shows after the clip's own name: the CLI's ERROR line and
    the service's problem detail. A reason that quotes a failed command (``…: Command
    exited N: <cmd>`` then ``stderr:`` and ffmpeg's output) is cut before the command,
    and ffmpeg's last stderr line, without its ``[component @ 0x…]`` tags and with the
    clip's path shortened to its file name, is kept as the gist: ``ffprobe could not
    read: Invalid data found when processing input``. Any other reason keeps its first
    line. Anything from a remaining absolute path on (a cache file ffmpeg names, say)
    is dropped, so the result carries no server path; the full reason is for the logs.
    """
    source = _resolved(Path(clip_path))
    head, _, stderr = reason.partition("\nstderr:\n")
    lines = head.splitlines()
    head = lines[0] if lines else head
    failed = _FAILED_COMMAND.search(head)
    if failed is None:
        return _before_any_path(_shorten(head, source))
    cause = _before_any_path(head[: failed.start()])
    last = next((line.strip() for line in reversed(stderr.splitlines()) if line.strip()), "")
    gist = _before_any_path(_shorten(_LOG_TAGS.sub("", last), source))
    return f"{cause}: {gist}" if gist else cause


def _resolved(path: Path) -> Path:
    """``path`` resolved as the engine runs ffmpeg on it, or as given when it cannot be."""
    try:
        return path.resolve()
    except (OSError, RuntimeError):  # a symlink loop
        return path


def _shorten(text: str, source: Path) -> str:
    """``text`` with the clip's path, which ffmpeg repeats, shortened to its file name.

    A path that is not valid UTF-8 is spelled twice: with surrogate escapes in the engine's
    ``source``, and with backslash escapes (``caf\\xe9.mp4``) in the stderr the runtime decoded.
    """
    for spelling, name in ((str(source), source.name), (_escaped(source), _escaped(source.name))):
        text = text.replace(f"{spelling}: ", "").replace(spelling, name)
    return text


def _escaped(path: Path | str) -> str:
    """``path`` with the bytes that are not valid UTF-8 as backslash escapes, as stderr shows."""
    return os.fsencode(path).decode("utf-8", "backslashreplace")


def _before_any_path(text: str) -> str:
    """``text`` up to the first absolute path it still names, if any."""
    found = _ABSOLUTE_PATH.search(text)
    return text if found is None else text[: found.start()].rstrip(" :'\"([=")


def _os_reason(exc: OSError) -> str:
    """An ``OSError``'s cause without the path it repeats (``No such file or directory``)."""
    return exc.strerror or str(exc)


def _create_temporary(cache_dir: Path, tmp: Path) -> None:
    """Create the cache directory and an empty ``tmp`` in it, or raise a cache error.

    Creating the file before ffmpeg runs classifies a missing, read-only or
    forbidden cache as the cache's fault, not as ffmpeg failing on this clip. The first
    time this process gets here for a directory it also sweeps that directory's stale
    temporaries; a process that only serves cache hits never reaches this.
    """
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _sweep_once(cache_dir)
        os.close(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666))  # umask applies
    except OSError as exc:
        raise ThumbnailCacheError(f"{cache_dir}: cannot write thumbnails: {exc}") from exc


def _extract(
    clip_path: Path,
    source: Path,
    runtime: FfmpegRuntime,
    *,
    at: float,
    duration: float,
    hdr: bool,
    output: Path,
) -> None:
    """Run the one extraction; no frame (any ffmpeg failure, or nothing written) raises.

    A failure that ffmpeg's own stderr says is a full disk or quota is the cache's fault,
    raised as :class:`ThumbnailCacheError`, not as this clip's.
    """
    no_frame = f"no frame extracted at {at:.3f}s of {duration:.3f}s"
    try:
        runtime.run(thumbnail_args(source, at=at, output=output, hdr=hdr))
    except FfmpegTimeoutError as exc:
        # Nothing is known about the frame: the read did not finish, so say that.
        raise ThumbnailError(
            str(clip_path), f"ffmpeg timed out extracting the frame at {at:.3f}s: {exc}"
        ) from exc
    except FfmpegError as exc:
        full = _full_disk_phrase(exc)
        if full is not None:
            raise ThumbnailCacheError(f"{output.parent}: cannot write thumbnails: {full}") from exc
        # ffmpeg reports "nothing decoded at t" as an encoder-open error; lead with
        # the real cause and keep the command and stderr after it.
        raise ThumbnailError(str(clip_path), f"{no_frame}: {exc}") from exc
    if not output.is_file() or output.stat().st_size == 0:
        raise ThumbnailError(str(clip_path), f"{no_frame}: ffmpeg exited 0 but wrote no image")


def _full_disk_phrase(exc: FfmpegError) -> Optional[str]:
    """The full-disk phrase in the stderr part of a failed command's message, if any.

    Only the text after ``stderr:`` counts: the quoted command above it holds the clip's
    file name, which may say anything.
    """
    _, _, stderr = str(exc).partition("\nstderr:\n")
    return next((phrase for phrase in _FULL_DISK_PHRASES if phrase in stderr), None)


def sweep_stale_temporaries(
    cache_dir: Path,
    *,
    older_than: float = STALE_TEMPORARY_AGE,
    now: Optional[float] = None,
) -> int:
    """Delete the engine's hidden temporaries in ``cache_dir`` untouched for ``older_than`` s.

    A candidate is a regular file (not a symlink or directory) directly in ``cache_dir``
    named ``.<64 hex>.<32 hex>.tmp`` whose modification time is more than ``older_than``
    seconds before ``now`` (epoch seconds, default the current time). A younger file may
    belong to a concurrent writer; ``<key>.jpg`` and every other name are never touched.
    Never raises: an unreadable directory or a file that will not go is logged and left.

    Returns:
        How many files were removed.
    """
    now = time.time() if now is None else now
    removed = 0
    try:
        with os.scandir(cache_dir) as entries:
            for entry in entries:
                try:
                    if not _TEMPORARY_NAME.match(entry.name):
                        continue
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        continue
                    if now - entry.stat(follow_symlinks=False).st_mtime <= older_than:
                        continue
                    os.unlink(entry.path)
                    removed += 1
                except OSError as exc:
                    logger.debug("Cannot sweep %s: %s", entry.path, exc)
    except OSError as exc:
        logger.debug("Cannot sweep %s: %s", cache_dir, exc)
    return removed


def _sweep_once(cache_dir: Path) -> None:
    """Sweep ``cache_dir`` the first time this process asks, and never raise."""
    try:
        key = cache_dir.resolve()
        with _swept_lock:
            if key in _swept:
                return
            _swept.add(key)  # marked before the scan: a failing scan is not retried in a loop
        removed = sweep_stale_temporaries(cache_dir)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.debug("Cannot sweep %s: %s", cache_dir, exc)
        return
    if removed:
        logger.info("Removed %d stale thumbnail temporaries from %s", removed, cache_dir)


def _finalize(cache_dir: Path, tmp: Path, target: Path) -> None:
    """``fsync`` the written ``tmp`` and rename it over ``target``, or raise a cache error."""
    try:
        fd = os.open(tmp, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, target)
    except OSError as exc:
        raise ThumbnailCacheError(f"{cache_dir}: cannot write thumbnails: {exc}") from exc


__all__ = [
    "FAILURE_TTL_SECONDS",
    "STALE_TEMPORARY_AGE",
    "THUMBNAIL_BOX",
    "THUMBNAIL_TIMEOUT",
    "THUMBNAIL_VERSION",
    "is_cached",
    "one_line_cause",
    "recorded_duration",
    "recorded_failure",
    "sweep_stale_temporaries",
    "thumbnail_args",
    "thumbnail_for",
    "thumbnail_key",
    "thumbnail_path",
]
