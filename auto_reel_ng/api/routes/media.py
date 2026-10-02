"""Media routes (change ``media-endpoints``): an event's clip and its rendered movie, streamed.

Thin wiring over :mod:`auto_reel_ng.api.media`: the lookup decides which file, the
response helper streams it with byte ranges and validators, and this module maps
each outcome to one status by cause. Both routes are per-request reads of a file,
like the thumbnail (D-11), never fields of the events read model (HLD §4.9). They
never touch the database, never run ffmpeg or ffprobe, and never write.

``app.py`` includes this router **before** the events router: the event detail's
``{event_id:path}`` route is greedy over ``/`` and Starlette matches in registration
order, so ``…/media`` and ``…/movie`` must be tried first or the detail would swallow
them, as the ``/reel`` and ``/thumbnail`` suffixes are registered before it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, Response

from ...ingest import LayoutError
from .. import events_read
from ..media import (
    MEDIA_CACHE_CONTROL,
    MediaGoneError,
    MediaReadError,
    MovieNotFoundError,
    clip_media,
    media_response,
    movie_media,
)
from ..problem import bad_gateway, not_found
from ..schemas import ProblemOut
from ..settings import ApiSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


def _header(description: str) -> Dict[str, Any]:
    return {"description": description, "schema": {"type": "string"}}


_ETAG_HEADER = _header("Strong entity-tag of the file: its size and mtime, in hex")
_CACHE_CONTROL_HEADER = _header(f"Always `{MEDIA_CACHE_CONTROL}`")

#: The headers of a 200 and a 206, as published in the schema.
_MEDIA_HEADERS = {
    "ETag": _ETAG_HEADER,
    "Last-Modified": _header("The file's modification time"),
    "Cache-Control": _CACHE_CONTROL_HEADER,
    "Accept-Ranges": _header("Always `bytes`"),
    "Content-Disposition": _header("`inline`, with the file's own name"),
}

#: The bytes of a 200 and a 206: the exact type is the `Content-Type` header's.
_VIDEO = {"video/*": {"schema": {"type": "string", "format": "binary"}}}

#: Every response both media routes answer with, as published in the schema. The 400
#: and the 416 are Starlette's plain-text answers, produced after the route returned.
MEDIA_RESPONSES: Dict[int | str, Dict[str, Any]] = {
    200: {"description": "The whole file", "content": _VIDEO, "headers": _MEDIA_HEADERS},
    206: {
        "description": "One byte range of the file",
        "content": _VIDEO,
        "headers": {
            **_MEDIA_HEADERS,
            "Content-Range": _header("`bytes <first>-<last>/<size>`"),
        },
    },
    304: {
        "description": "Not modified: `If-None-Match` names the current file, or, without it, "
        "`If-Modified-Since` is not before its modification time",
        "headers": {"ETag": _ETAG_HEADER, "Cache-Control": _CACHE_CONTROL_HEADER},
    },
    400: {"description": "A malformed `Range` header (plain text)"},
    404: {"model": ProblemOut},
    416: {
        "description": "The range starts at or past the end of the file (plain text)",
        "headers": {"Content-Range": _header("`bytes */<size>`")},
    },
    502: {"model": ProblemOut},
}

_VERSION_DESCRIPTION = (
    "An opaque version a client may send to give a changed file a new URL; ignored"
)


def _settings(request: Request) -> ApiSettings:
    settings: ApiSettings = request.app.state.settings
    return settings


def _if_none_match(request: Request) -> Optional[str]:
    """``If-None-Match`` from every header line: the declared parameter holds only the first."""
    return ", ".join(request.headers.getlist("if-none-match")) or None


def _if_modified_since(request: Request) -> Optional[str]:
    """``If-Modified-Since`` when sent on exactly one line: a repeated field is no HTTP-date."""
    lines = request.headers.getlist("if-modified-since")
    return lines[0] if len(lines) == 1 else None


def _media_failed(
    event_id: str,
    label: str,
    detail: str,
    failure: Optional[str] = None,
    *,
    log_reason: Optional[str] = None,
) -> JSONResponse:
    """A media 502, logged with the event and the file it is about; no caching headers.

    ``log_reason`` replaces ``detail`` in the log when the detail already starts with the
    label (a :class:`MediaReadError`'s), so the line names the file once.
    """
    logger.warning("media: %s: %s: %s", event_id, label, log_reason or detail)
    if failure is None:
        return bad_gateway(detail, event_id=event_id)
    return bad_gateway(detail, event_id=event_id, failure=failure)


def _unreadable(event_id: str, exc: MediaReadError) -> JSONResponse:
    """The 502 of a file that exists but cannot be read: no kind, a path-free detail."""
    return _media_failed(
        event_id, exc.label, str(exc), log_reason=f"cannot read the file: {exc.reason}"
    )


def _event_not_found(event_id: str) -> JSONResponse:
    return not_found(f"no event {event_id!r} under the configured project root", event_id=event_id)


@router.head("/events/{event_id:path}/media", response_class=Response, responses=MEDIA_RESPONSES)
@router.get("/events/{event_id:path}/media", response_class=Response, responses=MEDIA_RESPONSES)
def get_clip_media(
    event_id: str,
    request: Request,
    clip: str = Query(
        description="The clip's identity as the event detail lists it: its event-relative path",
    ),
    _version: Optional[str] = Query(default=None, alias="v", description=_VERSION_DESCRIPTION),
    _if_none_match_header: Optional[str] = Header(default=None, alias="If-None-Match"),
    _if_modified_since_header: Optional[str] = Header(default=None, alias="If-Modified-Since"),
    _range: Optional[str] = Header(default=None, alias="Range"),
    _if_range: Optional[str] = Header(default=None, alias="If-Range"),
) -> Response:
    """``GET`` and ``HEAD /api/v1/events/{event_id}/media?clip=``: one clip's file, unchanged.

    ``HEAD`` is the ``GET`` without its body: the same lookup, open and status, the same
    headers (``FileResponse`` drops the body). ``If-None-Match`` and ``If-Modified-Since``
    answer 304 for both.

    The clip must be one discovery lists on disk for an event the events list shows,
    matched exactly: the thumbnail's lookup. 404 for an unknown event, an unlisted
    identity, or a file gone by the time it is opened; 502 with the list's ``failure``
    when the event cannot be listed, and with no kind for an unknown layout or a file
    that cannot be read. Sync on purpose: the lookup is a listing, a stat and an open,
    run in the threadpool; ``FileResponse`` then streams on the event loop.
    """
    try:
        media = clip_media(_settings(request), event_id, clip)
    except events_read.EventNotFoundError:
        return _event_not_found(event_id)
    except events_read.ClipNotFoundError as exc:
        return not_found(str(exc), event_id=event_id)
    except MediaGoneError as exc:
        return not_found(str(exc), event_id=event_id)
    except events_read.EventReadError as exc:
        failure = exc.failure.value if exc.failure is not None else None
        return _media_failed(event_id, clip, exc.detail, failure)
    except LayoutError as exc:
        return _media_failed(event_id, clip, str(exc))
    except MediaReadError as exc:
        return _unreadable(event_id, exc)
    return media_response(media, _if_none_match(request), _if_modified_since(request))


@router.head("/events/{event_id:path}/movie", response_class=Response, responses=MEDIA_RESPONSES)
@router.get("/events/{event_id:path}/movie", response_class=Response, responses=MEDIA_RESPONSES)
def get_movie(
    event_id: str,
    request: Request,
    _version: Optional[str] = Query(default=None, alias="v", description=_VERSION_DESCRIPTION),
    _if_none_match_header: Optional[str] = Header(default=None, alias="If-None-Match"),
    _if_modified_since_header: Optional[str] = Header(default=None, alias="If-Modified-Since"),
    _range: Optional[str] = Header(default=None, alias="Range"),
    _if_range: Optional[str] = Header(default=None, alias="If-Range"),
) -> Response:
    """``GET`` and ``HEAD /api/v1/events/{event_id}/movie``: the event's rendered movie, streamed.

    ``HEAD`` and the conditional headers behave as for the clip route.

    The movie is the file the staleness gate counts (``staleness.rendered_output``):
    it exists exactly when the event's staleness cites neither ``no_manifest`` nor
    ``output``. 404 for an unknown event, no render record, a recorded movie that is
    gone, a name outside the output directory, or something other than a file; 502
    with the ``failure`` the event detail gives when the event cannot be read, and with
    no kind for an unknown layout or a movie that cannot be read.
    """
    try:
        media = movie_media(_settings(request), event_id)
    except events_read.EventNotFoundError:
        return _event_not_found(event_id)
    except (MovieNotFoundError, MediaGoneError) as exc:
        return not_found(str(exc), event_id=event_id)
    except events_read.EventReadError as exc:
        failure = exc.failure.value if exc.failure is not None else None
        return _media_failed(event_id, "movie", exc.detail, failure)
    except LayoutError as exc:
        return _media_failed(event_id, "movie", str(exc))
    except MediaReadError as exc:
        return _unreadable(event_id, exc)
    return media_response(media, _if_none_match(request), _if_modified_since(request))
