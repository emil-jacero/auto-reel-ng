"""Media reads: which file a media route serves, and how (change ``media-endpoints``).

Two per-request reads stream a file exactly as it is on disk, like the thumbnail
(D-11) a read *of* a file rather than a field of the events read model (HLD §4.9):

- a **clip** of an event (:func:`clip_media`): an identity discovery lists, found by
  the thumbnail's own lookup (:func:`~.events_read.listed_clip`);
- the event's **rendered movie** (:func:`movie_media`): the file the staleness gate
  counts as the event's movie (:func:`~auto_reel_ng.staleness.rendered_output`), so
  the route and a verdict can never disagree.

Nothing here writes, probes or decodes, and nothing touches the database. A file is
statted and opened once before the route answers (:func:`open_media`), so a file that
cannot be read is a problem body, never a 200 that breaks off; Starlette's
``FileResponse`` then streams it in bounded chunks, with byte ranges and ``If-Range``
(:func:`media_response`). Bytes are served unchanged: a clip whose audio a browser
cannot decode (the PCM audio of Sony XAVC clips, silent in Firefox) is a v2 matter
for the proxy work (§8.11), not a transcode here.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping, Optional

from fastapi.responses import FileResponse, Response

from ..errors import ReelError
from ..event.metadata import load_event_document, require_processable
from ..render import output_relpath
from ..staleness import rendered_output
from .events_read import EventReadError, classify_event_failure, listed_clip, listed_event_dir
from .schemas import EventFailure
from .settings import ApiSettings

#: The ``Content-Type`` of every extension discovery lists (``VIDEO_EXTENSIONS``), keyed
#: lowercase. A fixed table, never the host's ``mimetypes``: the same file gets the same
#: type on every host. A test keeps the keys equal to discovery's set.
MEDIA_TYPES: Mapping[str, str] = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mts": "video/mp2t",
    ".m2ts": "video/mp2t",
    ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg",
    ".wmv": "video/x-ms-wmv",
    ".3gp": "video/3gpp",
    ".flv": "video/x-flv",
}

#: The fallback for a name outside the table. Unreachable for a clip (discovery lists
#: only the table's extensions) and for a movie (renders and adoptions write ``.mp4``).
_UNKNOWN_MEDIA_TYPE = "application/octet-stream"

#: A browser revalidates before it reuses stored bytes, so ranges of an old and a new
#: version of a file rewritten in place are never spliced. ``private`` keeps shared
#: caches out of the archive.
MEDIA_CACHE_CONTROL = "private, no-cache"


class MediaGoneError(Exception):
    """The listed file is no longer there, or is not a regular file: answered 404.

    ``label`` is the clip's identity or the movie's file name, never a server path.
    """

    def __init__(self, label: str, reason: str) -> None:
        super().__init__(f"{label}: {reason}")
        self.label = label
        self.reason = reason


class MediaReadError(Exception):
    """The file exists but cannot be statted or opened (a permission, a dead drive): 502.

    ``str()`` is ``<label>: cannot read the file: <reason>``, free of server paths; the
    route adds the event.
    """

    def __init__(self, label: str, reason: str) -> None:
        super().__init__(f"{label}: cannot read the file: {reason}")
        self.label = label
        self.reason = reason


class MovieNotFoundError(Exception):
    """The event has no rendered movie the gate counts, inside the output directory: 404."""

    def __init__(self, event_id: str) -> None:
        super().__init__(f"event {event_id!r} has no rendered movie")
        self.event_id = event_id


@dataclass(frozen=True)
class MediaFile:
    """A file a media route serves, statted and proven readable once."""

    #: The clip as discovery listed it (``event_dir / identity``), or the movie file.
    path: Path
    #: ``os.stat`` following symlinks: a linked clip's size and mtime are its target's.
    stat: os.stat_result

    @property
    def name(self) -> str:
        """The file's own name, for ``Content-Disposition``."""
        return self.path.name

    @property
    def media_type(self) -> str:
        """The ``Content-Type`` by extension, case-insensitively (:data:`MEDIA_TYPES`)."""
        return MEDIA_TYPES.get(self.path.suffix.lower(), _UNKNOWN_MEDIA_TYPE)

    @property
    def etag(self) -> str:
        """A strong entity-tag: the size and the nanosecond mtime, in hex.

        Both change on every rewrite a camera, a copy or a render makes, and neither
        needs the file's bytes, so a revalidation reads none.
        """
        return f'"{self.stat.st_size:x}-{self.stat.st_mtime_ns:x}"'


def open_media(path: Path, *, label: str) -> MediaFile:
    """Stat ``path`` (following links), require a regular file, then open and close it.

    The open happens here, before any status line is sent: ``FileResponse`` opens the
    file only after it has started a 200 or 206, so an unreadable file would otherwise
    break off a response that already claimed success. Nothing is read.

    Raises:
        MediaGoneError: nothing at ``path`` (a deleted file, a dangling link), or
            something that is not a regular file (a directory is never opened).
        MediaReadError: the stat or the open is refused for another reason.
    """
    try:
        file_stat = os.stat(path)
    except FileNotFoundError:
        raise MediaGoneError(label, "no such file") from None
    except OSError as exc:
        raise MediaReadError(label, exc.strerror or type(exc).__name__) from exc
    if not stat.S_ISREG(file_stat.st_mode):
        raise MediaGoneError(label, "not a regular file")
    try:
        with open(path, "rb"):
            pass
    except FileNotFoundError:
        raise MediaGoneError(label, "no such file") from None
    except OSError as exc:
        raise MediaReadError(label, exc.strerror or type(exc).__name__) from exc
    return MediaFile(path=path, stat=file_stat)


def clip_media(settings: ApiSettings, event_id: str, clip: str) -> MediaFile:
    """The clip ``clip`` of ``event_id``: the thumbnail's lookup, then :func:`open_media`.

    ``reel.yaml`` is never read, so a broken document does not stop a clip, and an
    IGNORED clip on disk is served like any other. The errors are
    :func:`~.events_read.listed_clip`'s and :func:`open_media`'s.
    """
    return open_media(listed_clip(settings, event_id, clip), label=clip)


def movie_media(settings: ApiSettings, event_id: str) -> MediaFile:
    """The rendered movie of ``event_id``: exactly the file the staleness gate counts.

    1. The id must be one the events list shows (``EventNotFoundError``); a walk that
       fails is an :class:`EventReadError` with the ``unreadable_disk`` kind.
    2. The metadata is read as the enqueue's output claim reads it: the resolving loader
       and the processable rule. A failure is an :class:`EventReadError` with the kind
       and detail the event detail gives (``unparseable_reel_yaml``,
       ``unusable_metadata``, ``unreadable_disk``).
    3. The expected path is the one the event's staleness verdict is computed against.
    4. :func:`~auto_reel_ng.staleness.rendered_output` decides the movie: none without a
       render record (an un-adopted legacy movie included), the expected file, else the
       movie under the event's old name. ``None`` is :class:`MovieNotFoundError`.
    5. The movie's path, with ``.`` and ``..`` removed lexically, must lie inside the
       output directory, else :class:`MovieNotFoundError`. A title is writable through
       ``PUT …/reel`` and the naming rule does not refuse ``/`` in it, so a name could
       climb out with ``..``. Lexical on purpose, never ``resolve()``: a symbolic link
       inside the output directory (a year folder on another disk) is followed, as the
       gate follows it.
    6. :func:`open_media`, labelled with the movie's file name.
    """
    try:
        event_dir = listed_event_dir(settings, event_id)
    except OSError as exc:
        raise EventReadError(event_id, str(exc), EventFailure.UNREADABLE_DISK) from exc
    try:
        document, _seeded = load_event_document(event_dir, order=settings.clip_order)
        require_processable(event_dir, document.metadata, today=date.today())
    except (ReelError, OSError) as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc
    expected = settings.output_dir / output_relpath(document.metadata)
    movie = rendered_output(event_dir, expected)
    if movie is None or not _inside(movie, settings.output_dir):
        raise MovieNotFoundError(event_id)
    return open_media(movie, label=movie.name)


def _inside(path: Path, directory: Path) -> bool:
    """Whether ``path`` lies under ``directory`` once ``.`` and ``..`` are removed lexically."""
    return Path(os.path.abspath(path)).is_relative_to(os.path.abspath(directory))


def etag_matches(header: str, etag: str) -> bool:
    """RFC 9110 weak comparison of ``etag`` with a comma-separated ``If-None-Match`` value.

    A ``W/`` prefix is ignored. No ``*`` rule: what ``*`` matches is the caller's to say.
    """
    candidates = [candidate.strip() for candidate in header.split(",") if candidate.strip()]
    return any(candidate.removeprefix("W/") == etag for candidate in candidates)


def _revalidates(header: str, etag: str) -> bool:
    """``If-None-Match`` names the file: its tag, or ``*`` (the file has just been opened)."""
    return etag_matches(header, etag) or "*" in (c.strip() for c in header.split(","))


def media_response(media: MediaFile, if_none_match: Optional[str]) -> Response:
    """The 304 for a matching ``If-None-Match``, else the streamed file.

    ``If-None-Match`` is evaluated first, before any ``Range``, as RFC 9110 orders the
    preconditions; ``FileResponse`` does not evaluate it. The file response gets the
    route's own stat (it never stats again), and the ``ETag`` in ``headers=`` wins over
    Starlette's own (it is set with ``setdefault``), so the tag sent, the one ``If-Range``
    is checked against and the one a 304 compares are the same string. ``FileResponse``
    answers ``Range`` itself: 206 for one range, 416 past the end, 400 malformed.
    """
    headers = {"ETag": media.etag, "Cache-Control": MEDIA_CACHE_CONTROL}
    if if_none_match is not None and _revalidates(if_none_match, media.etag):
        return Response(status_code=304, headers=headers)
    return FileResponse(
        media.path,
        media_type=media.media_type,
        headers=headers,
        stat_result=media.stat,
        filename=media.name,
        content_disposition_type="inline",
    )


__all__ = [
    "MEDIA_CACHE_CONTROL",
    "MEDIA_TYPES",
    "MediaFile",
    "MediaGoneError",
    "MediaReadError",
    "MovieNotFoundError",
    "clip_media",
    "etag_matches",
    "media_response",
    "movie_media",
    "open_media",
]
