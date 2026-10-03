"""The event's rendered movie as the API reads it (change ``movie-facts-read``).

One rule for "which file is the event's movie" (:func:`rendered_movie_path`), used by the movie
route (``api.media``) and by the event detail's ``movie`` (:func:`movie_facts`), so the two cannot
disagree; and the one expected output path (:func:`expected_output`) the staleness verdict, the
lookup and the route share. Reads and ``stat`` only: no probe, no write, no database.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from ..reel.document import Metadata
from ..render import output_relpath
from ..staleness import ChapterTime, read_manifest, rendered_output
from .schemas import MovieChapterOut, MovieOut
from .settings import ApiSettings

logger = logging.getLogger(__name__)


def expected_output(settings: ApiSettings, metadata: Metadata) -> Path:
    """The path the event's next render writes: the one verdict, lookup and route share."""
    return settings.output_dir / output_relpath(metadata)


def _inside(path: Path, directory: Path) -> bool:
    """Whether ``path`` lies under ``directory`` once ``.`` and ``..`` are removed lexically."""
    return Path(os.path.abspath(path)).is_relative_to(os.path.abspath(directory))


def rendered_movie_path(
    settings: ApiSettings, event_dir: Path, metadata: Metadata
) -> Optional[Path]:
    """The event's rendered movie: the file the staleness gate counts, or ``None``.

    The one rule behind both ``GET …/movie`` and the detail's ``movie``, so they cannot
    disagree. ``metadata`` is the resolved metadata. The gate's
    :func:`~auto_reel_ng.staleness.rendered_output` decides (none without a readable render
    record; the expected file; else the file under the event's old name), and the path, with
    ``.`` and ``..`` removed lexically, must lie inside the output directory: a title is
    writable through ``PUT …/reel`` and the naming rule could once climb out with ``..``.
    Lexical on purpose, never ``resolve()``: a symbolic link inside the output directory (a
    year folder on another disk) is followed, as the gate follows it.
    """
    movie = rendered_output(event_dir, expected_output(settings, metadata))
    return movie if movie is not None and _inside(movie, settings.output_dir) else None


def movie_facts(settings: ApiSettings, event_dir: Path, metadata: Metadata) -> Optional[MovieOut]:
    """The detail's ``movie``: the movie's version and chapters, the three from one manifest read.

    ``None`` without a movie (:func:`rendered_movie_path`), without a readable manifest at this
    read, or when its ``written_at`` is not a timezone-aware date-time the clock can hold in UTC:
    no version can be told, and none is invented from the file's mtime or the clock. The lookup
    reads the manifest on its own, so a render that lands between the two reads can give the new
    render's facts for the old render's file; the facts themselves always agree with each other.
    A recorded chapter list whose times cannot be turned into seconds is unknown (``None``), as
    any other unreadable list is.
    """
    if rendered_movie_path(settings, event_dir, metadata) is None:
        return None
    manifest = read_manifest(event_dir)
    if manifest is None:
        return None
    try:
        recorded_at = datetime.fromisoformat(manifest.written_at)
        if recorded_at.utcoffset() is None:
            logger.debug("Render manifest of %s has a written_at without a UTC offset", event_dir)
            return None
        recorded_at = recorded_at.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        logger.debug("Render manifest of %s has no usable written_at", event_dir)
        return None
    return MovieOut(
        recorded_at=recorded_at,
        fingerprint=manifest.fingerprint[:12],
        chapters=_chapters(manifest.chapters, event_dir),
    )


def _chapters(
    recorded: Optional[Sequence[ChapterTime]], event_dir: Path
) -> Optional[List[MovieChapterOut]]:
    """The recorded chapters as seconds, in recorded order; ``None`` when unknown or unusable."""
    if recorded is None:
        return None
    try:
        return [
            MovieChapterOut(name=chapter.name, start=chapter.start_ms / 1000)
            for chapter in recorded
        ]
    except OverflowError:
        logger.debug("Render manifest of %s has a chapter time beyond a float", event_dir)
        return None


__all__ = ["expected_output", "movie_facts", "rendered_movie_path"]
