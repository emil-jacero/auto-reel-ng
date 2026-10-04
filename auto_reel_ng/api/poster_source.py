"""The poster route's source: which picture to serve and where it is cached (change ``event-poster-gui``).

Read-only, probe-free and database-free, like the other media lookups in :mod:`.events_read`,
whose listing, loading and verdict helpers it reuses.
"""

# The listing, load and verdict helpers are this package's own: the poster lookup is a sibling of
# the other media lookups in ``events_read`` and must not re-derive what they decide.
# pylint: disable=protected-access

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from ..config.project import load_project_config, resolve_look_defaults
from ..errors import ReelError, ThumbnailError
from ..ffmpeg.runtime import FfmpegRuntime
from ..render.poster import poster_path
from ..staleness.manifest import records_poster
from ..thumbs import resolve_thumbnail_settings, thumbnail_path
from ..thumbs.poster import poster_draw_path
from . import events_read
from .events_read import EventReadError, classify_event_failure
from .movie_read import rendered_movie_path
from .poster_read import poster_for
from .schemas import PosterSource
from .settings import ApiSettings


class PosterUnavailableError(Exception):
    """The event has no clip a render plays, so it has no poster."""

    def __init__(self, event_id: str) -> None:
        super().__init__(f"event {event_id!r} has no clip a render plays, so no poster")
        self.event_id = event_id


@dataclass(frozen=True)
class PosterImage:
    """Where the event's poster comes from, as the poster route serves it.

    ``sidecar`` is the rendered ``<movie stem>-poster.jpg``, served as it is. Otherwise the frame
    is drawn and cached at ``cache_path``: ``chosen`` at ``at`` of ``clip_path`` (turned by
    ``rotate``) with the engine's poster extraction, ``default`` as the clip's thumbnail.
    """

    kind: Literal["sidecar", "chosen", "default"]
    clip: str
    clip_path: Path
    cache_dir: Path
    cache_path: Path
    etag: str
    at: float = 0.0
    rotate: Optional[int] = None
    position: float = 0.0

    @property
    def is_sidecar(self) -> bool:
        """Whether the bytes are the render's own file."""
        return self.kind == "sidecar"


def _sidecar_etag(sidecar: Path) -> str:
    stat = sidecar.stat()
    return f'"sidecar-{stat.st_size:x}-{stat.st_mtime_ns:x}"'


def poster_image(
    settings: ApiSettings, event_id: str, runtime: FfmpegRuntime
) -> PosterImage:  # pylint: disable=too-many-locals
    """``GET /api/v1/events/{event_id}/poster.jpg``: the poster to serve and where it is cached.

    Read-only, probe-free and database-free: nothing is generated here. The effective poster is
    the detail's (:func:`~.poster_read.poster_for`). A fresh event whose render manifest claims
    the sidecar serves that file; otherwise the frame is drawn from the original and cached next
    to the thumbnails.

    Raises:
        EventNotFoundError: not an event the list shows.
        PosterUnavailableError: the event plays no clip.
        EventReadError: the event cannot be read.
        ConfigError: ``config.yaml`` cannot be read.
        ThumbnailError: the clip can no longer be statted.
    """
    try:
        event_dir = events_read.listed_event_dir(settings, event_id)
        config = load_project_config(settings.project_root)
        document, listing, result = events_read._load_for_reconcile(event_dir, config.sort)
        chapters = events_read._build_chapters(document, listing, result, event_dir, config.sort)
        poster, _note = poster_for(document, chapters)
        if poster is None:
            raise PosterUnavailableError(event_id)
        resolved = events_read._resolved_document(settings, event_dir, document)
        stale = events_read._verdict(
            settings, event_dir, resolved, runtime, resolve_look_defaults(config)
        ).stale
    except (ReelError, OSError) as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc
    thumbnails = resolve_thumbnail_settings(config, settings.project_root)
    clip_path = event_dir / poster.clip
    if not stale:
        movie = rendered_movie_path(settings, event_dir, resolved.metadata)
        sidecar = poster_path(movie) if movie is not None else None
        if sidecar is not None and sidecar.is_file() and records_poster(event_dir, sidecar):
            return PosterImage(
                kind="sidecar",
                clip=poster.clip,
                clip_path=clip_path,
                cache_dir=thumbnails.cache_dir,
                cache_path=sidecar,
                etag=_sidecar_etag(sidecar),
            )
    try:
        if poster.source == PosterSource.EVENT and poster.at is not None:
            props = document.clips.get(poster.clip) if document is not None else None
            rotate = props.rotate if props is not None else None
            cache_path = poster_draw_path(
                clip_path, at=poster.at, rotate=rotate, cache_dir=thumbnails.cache_dir
            )
            return PosterImage(
                kind="chosen",
                clip=poster.clip,
                clip_path=clip_path,
                cache_dir=thumbnails.cache_dir,
                cache_path=cache_path,
                etag=f'"{cache_path.stem}"',
                at=poster.at,
                rotate=rotate,
            )
        cache_path = thumbnail_path(
            clip_path, position=thumbnails.position, cache_dir=thumbnails.cache_dir
        )
    except OSError as exc:
        raise ThumbnailError(
            str(clip_path), f"cannot stat the clip: {exc.strerror or exc}"
        ) from exc
    return PosterImage(
        kind="default",
        clip=poster.clip,
        clip_path=clip_path,
        cache_dir=thumbnails.cache_dir,
        cache_path=cache_path,
        etag=f'"{cache_path.stem}"',
        position=thumbnails.position,
    )


__all__ = ["PosterImage", "PosterUnavailableError", "poster_image"]
