"""A drawn poster frame, cached beside the thumbnails (change ``event-poster-gui``).

The sidecar ``<movie stem>-poster.jpg`` exists only after a render. Until then the service draws
the same frame with the engine's own extraction (:func:`~auto_reel_ng.render.poster.extract_poster`:
rotation, SAR and HDR handled as the render does) at a smaller size, into the thumbnail cache
directory, outside the library. The key covers the clip's name, size and mtime, the frame time,
the editorial turn, the size and :data:`POSTER_DRAW_VERSION`, so a repeat costs one ``stat`` and no
process. Written like a thumbnail (temporary, ``fsync``, rename) and a failure is remembered for
:data:`~auto_reel_ng.thumbs.FAILURE_TTL_SECONDS` in ``<key>.fail`` through the thumbnails' own marker.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import uuid
from pathlib import Path
from typing import Optional

from ..errors import (
    ProbeError,
    RenderError,
    ThumbnailError,
)
from ..ffmpeg.runtime import FfmpegRuntime
from ..probe.media import get_default_runtime, probe_media
from ..render.poster import PosterChoice, extract_poster
from ..render.target import (
    DEFAULT_AUDIO_CHANNELS,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_SAMPLE_RATE,
    DEFAULT_FILL_COLOR,
    DEFAULT_PIX_FMT,
    DEFAULT_VIDEO_CODEC,
    TargetSpec,
)
from .thumbnail import (
    THUMBNAIL_TIMEOUT,
    _create_temporary,
    _finalize,
    _probe_reason,
    _record_failure,
    is_cached,
    recorded_failure,
)

#: The ``(width, height)`` a drawn poster is fitted and padded to: 16:9, like the render's.
POSTER_DRAW_BOX = (640, 360)

#: Bump when :func:`poster_draw_key`'s payload or the drawn bytes for an input class change.
POSTER_DRAW_VERSION = 1


def poster_draw_key(clip_path: Path, *, at: float, rotate: Optional[int]) -> str:
    """The cache key: sha256 hex over the clip's file name and stat signal and the frame.

    The stat's :class:`OSError` propagates unchanged, as in :func:`~.thumbnail.thumbnail_key`.
    """
    resolved = Path(clip_path).resolve()
    stat = resolved.stat()
    payload = json.dumps(
        [
            "poster",
            resolved.name,
            stat.st_size,
            stat.st_mtime_ns,
            round(at, 3),
            rotate,
            list(POSTER_DRAW_BOX),
            POSTER_DRAW_VERSION,
        ]
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def poster_draw_path(clip_path: Path, *, at: float, rotate: Optional[int], cache_dir: Path) -> Path:
    """Where the drawn frame is cached: ``<cache_dir>/<key>.jpg``. Computes only."""
    return Path(cache_dir) / f"{poster_draw_key(clip_path, at=at, rotate=rotate)}.jpg"


def _target() -> TargetSpec:
    width, height = POSTER_DRAW_BOX
    return TargetSpec(
        width=width,
        height=height,
        fps=25.0,
        video_codec=DEFAULT_VIDEO_CODEC,
        video_encoder=DEFAULT_VIDEO_CODEC,
        pix_fmt=DEFAULT_PIX_FMT,
        sample_aspect_ratio="1:1",
        fill_color=DEFAULT_FILL_COLOR,
        audio_codec=DEFAULT_AUDIO_CODEC,
        audio_sample_rate=DEFAULT_AUDIO_SAMPLE_RATE,
        audio_channels=DEFAULT_AUDIO_CHANNELS,
    )


def poster_draw_for(
    clip_path: Path,
    *,
    at: float,
    rotate: Optional[int],
    cache_dir: Path,
    runtime: Optional[FfmpegRuntime] = None,
) -> Path:
    """The cached JPEG of the clip's frame at ``at`` (seconds, before cuts), drawn when absent.

    A hit returns with no process; a failure recorded in the last minute is raised with none.

    Raises:
        ThumbnailError: the clip cannot be statted or probed, or has no frame at ``at`` (a time
            at or past its end included).
        ThumbnailCacheError: ``cache_dir`` cannot be created, written or is full.
    """
    clip_path = Path(clip_path)
    cache_dir = Path(cache_dir)
    try:
        key = poster_draw_key(clip_path, at=at, rotate=rotate)
    except OSError as exc:
        raise ThumbnailError(
            str(clip_path), f"cannot stat the clip: {exc.strerror or exc}"
        ) from exc
    target = cache_dir / f"{key}.jpg"
    if is_cached(target):
        return target
    failure = recorded_failure(clip_path, target)
    if failure is not None:
        raise failure
    try:
        _draw(clip_path, at=at, rotate=rotate, key=key, target=target, runtime=runtime)
    except ThumbnailError as exc:
        _record_failure(target, exc.reason)
        raise
    with contextlib.suppress(OSError):
        target.with_suffix(".fail").unlink()
    return target


def _draw(
    clip_path: Path,
    *,
    at: float,
    rotate: Optional[int],
    key: str,
    target: Path,
    runtime: Optional[FfmpegRuntime],
) -> None:
    runtime = (runtime or get_default_runtime()).with_timeout(THUMBNAIL_TIMEOUT)
    source = clip_path.resolve()
    try:
        metadata = probe_media(source, runtime=runtime)
    except ProbeError as exc:
        raise ThumbnailError(str(clip_path), _probe_reason(exc, source)) from exc
    if at >= metadata.duration:
        raise ThumbnailError(
            str(clip_path),
            f"the poster time {at:g}s is not before the end of the clip ({metadata.duration:g}s)",
        )
    cache_dir = target.parent
    tmp = cache_dir / f".{key}.{uuid.uuid4().hex}.tmp"
    try:
        _create_temporary(cache_dir, tmp)
        choice = PosterChoice(clip_path.name, at, rotate, "explicit")
        try:
            extract_poster(runtime, metadata, choice, target=_target(), output=tmp)
        except RenderError as exc:
            raise ThumbnailError(str(clip_path), str(exc)) from exc
        _finalize(cache_dir, tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


__all__ = [
    "POSTER_DRAW_BOX",
    "POSTER_DRAW_VERSION",
    "poster_draw_for",
    "poster_draw_key",
    "poster_draw_path",
]
