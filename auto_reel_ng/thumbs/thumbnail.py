"""One JPEG thumbnail per clip, cached outside the library (D-11).

The frame is the one at ``position × duration``, where the duration is the engine's
own ffprobe result (Principle I: never guessed). Extraction is attempted exactly
once: a clip with no frame at that time has no thumbnail, and no other timestamp,
first frame or placeholder is tried in its place.

The pure pieces — :func:`thumbnail_key`, :func:`thumbnail_path` and
:func:`thumbnail_args` — compute the cache location and the ffmpeg arguments;
:func:`thumbnail_for` composes them around one probe and one ffmpeg run through
:class:`FfmpegRuntime`. The cache key covers the resolved clip path, its size and
``mtime_ns``, the position, the box and :data:`THUMBNAIL_VERSION`, so a changed clip
gets a new file by itself and a cache hit costs one ``stat`` and one hash. Files are
written like ``reel/writer.write_document``: a uniquely named hidden temporary file,
``fsync``, then ``os.replace``, so ``<key>.jpg`` only ever appears complete.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import os
import re
import uuid
from pathlib import Path
from typing import List, Optional

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

#: Bump whenever :func:`thumbnail_args` changes the output bytes: it re-keys every file.
THUMBNAIL_VERSION = 1

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
    """The cache key: sha256 hex over the clip's resolved path, stat signal and settings.

    Symlinks are followed, so every link to one file shares one key. The stat's
    :class:`OSError` propagates unchanged (``FileNotFoundError`` for a vanished clip);
    each caller decides what it means.
    """
    resolved = Path(clip_path).resolve()
    stat = resolved.stat()
    # A JSON list is a canonical, unambiguous encoding; ensure_ascii keeps a
    # non-UTF-8 file name (surrogate escapes) encodable.
    payload = json.dumps(
        [
            str(resolved),
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


def thumbnail_args(clip: Path, *, at: float, output: Path) -> List[str]:
    """The ffmpeg arguments that write the frame at ``at`` seconds of ``clip`` as a JPEG.

    Input seek (``-ss`` before ``-i``) lands on the frame at ``at``; CPU decode (no
    ``-hwaccel``) applies the container's display rotation before the filters. The
    first ``scale`` makes pixels square so anamorphic footage is not squashed, the
    second fits the box keeping the aspect ratio. ``-update 1`` makes ``image2``
    write ``output`` literally, so a ``%`` in the cache path is never a pattern.
    """
    width, height = THUMBNAIL_BOX
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
        (
            "scale=trunc(iw*sar/2)*2:ih,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,setsar=1"
        ),
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

    A cache hit returns without running ffprobe or ffmpeg. A miss probes the
    clip's resolved path for its duration, extracts the frame at
    ``position × duration`` into a temporary file in ``cache_dir`` (created when
    absent), ``fsync``s it and renames it to ``<key>.jpg``. The source clip is only
    read. On any failure, interruption included, the temporary file is removed.

    Raises:
        ThumbnailError: the clip cannot be statted or probed, has no usable
            duration, or gave no frame at that time; the message starts with the
            clip's path, and ``reason`` names the cause without it.
        ThumbnailCacheError: ``cache_dir`` cannot be created, read or written.
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

    runtime = (runtime or get_default_runtime()).with_timeout(THUMBNAIL_TIMEOUT)
    # The resolved, absolute path: a relative ``file:x.mp4`` would be read as a protocol.
    source = clip_path.resolve()
    duration = _probe_duration(clip_path, source, runtime)
    at = position * duration

    tmp = cache_dir / f".{key}.{uuid.uuid4().hex}.tmp"
    try:
        _create_temporary(cache_dir, tmp)
        _extract(clip_path, source, runtime, at=at, duration=duration, output=tmp)
        _finalize(cache_dir, tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise
    logger.debug("Thumbnail of %s at %.3fs: %s", clip_path, at, target)
    return target


def _probe_duration(clip_path: Path, source: Path, runtime: FfmpegRuntime) -> float:
    """The clip's ffprobe duration; a probe failure or no usable duration raises."""
    try:
        duration = probe_media(source, runtime=runtime).duration
    except ProbeError as exc:
        raise ThumbnailError(str(clip_path), _probe_reason(exc, source)) from exc
    # The probe reports 0.0 when neither the format nor the stream carries one.
    if not math.isfinite(duration) or duration <= 0:
        raise ThumbnailError(str(clip_path), f"ffprobe reported no usable duration ({duration})")
    return duration


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


def _escaped(path: "Path | str") -> str:
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
    forbidden cache as the cache's fault, not as ffmpeg failing on this clip.
    """
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
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
    output: Path,
) -> None:
    """Run the one extraction; no frame (any ffmpeg failure, or nothing written) raises."""
    no_frame = f"no frame extracted at {at:.3f}s of {duration:.3f}s"
    try:
        runtime.run(thumbnail_args(source, at=at, output=output))
    except FfmpegTimeoutError as exc:
        # Nothing is known about the frame: the read did not finish, so say that.
        raise ThumbnailError(
            str(clip_path), f"ffmpeg timed out extracting the frame at {at:.3f}s: {exc}"
        ) from exc
    except FfmpegError as exc:
        # ffmpeg reports "nothing decoded at t" as an encoder-open error; lead with
        # the real cause and keep the command and stderr after it.
        raise ThumbnailError(str(clip_path), f"{no_frame}: {exc}") from exc
    if not output.is_file() or output.stat().st_size == 0:
        raise ThumbnailError(str(clip_path), f"{no_frame}: ffmpeg exited 0 but wrote no image")


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
    "THUMBNAIL_BOX",
    "THUMBNAIL_TIMEOUT",
    "THUMBNAIL_VERSION",
    "is_cached",
    "one_line_cause",
    "thumbnail_args",
    "thumbnail_for",
    "thumbnail_key",
    "thumbnail_path",
]
