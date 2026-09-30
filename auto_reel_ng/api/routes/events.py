"""Events + analysis read routes (tasks 2.2-2.4): thin wiring over ``events_read``.

Every route here is scan-on-request (D-A3) — no caching, no database copy of
event/clip state; the freshest possible read of ``reel.yaml``/disk on every call.
The one media read, a clip's thumbnail, is served from the engine's cache outside
the library (D-11): a per-clip read on request, never a field of the read model.
"""

from __future__ import annotations

import logging
import time
from functools import partial
from pathlib import Path
from typing import List, Optional, Union

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from ...config.project import ConfigError
from ...errors import EventMetadataError, ReelError, ThumbnailCacheError, ThumbnailError
from ...event.editorial import apply_editorial_write
from ...ingest import LayoutError
from ...reel.document import ReelDocument
from ...staleness.fingerprint import editorial_hash
from ...thumbs import is_cached, one_line_cause, thumbnail_for
from .. import events_read
from ..problem import (
    bad_gateway,
    bad_request,
    not_found,
    precondition_failed,
    service_unavailable,
)
from ..schemas import (
    AnalysisOut,
    EditorialDocumentBody,
    EditorialWriteResult,
    EventDetailOut,
    EventFailure,
    EventRowOut,
    ProblemOut,
    ThumbnailFailure,
)
from ..serialize import document_to_body
from ..settings import ApiSettings
from ..thumbnails import ThumbnailGate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


#: The ``ETag`` header of a successful editorial read or write, as published in the schema.
_ETAG_RESPONSE = {
    "headers": {
        "ETag": {
            "description": "Strong entity-tag of the editorial state, for If-Match on the write",
            "schema": {"type": "string"},
        }
    }
}


#: How long a browser may reuse a thumbnail without asking: a day. ``private`` keeps
#: shared caches out of the archive's pictures.
THUMBNAIL_CACHE_CONTROL = "private, max-age=86400"

#: The validator headers of a thumbnail's 200 and 304, as published in the schema.
_THUMBNAIL_HEADERS = {
    "ETag": {
        "description": "Strong entity-tag of the thumbnail: the engine's cache key, quoted",
        "schema": {"type": "string"},
    },
    "Cache-Control": {
        "description": f"Always `{THUMBNAIL_CACHE_CONTROL}`",
        "schema": {"type": "string"},
    },
}


def _settings(request: Request) -> ApiSettings:
    return request.app.state.settings  # type: ignore[no-any-return]


def _job_store_unavailable(exc: SQLAlchemyError, **extra: object) -> JSONResponse:
    """The shared mapping for an unreachable job store on an events read (D-A6).

    Both events reads consult the job store for ``latest_job``; when it cannot be
    reached the read fails loud in the same 503 problem shape ``/healthz`` returns,
    carrying the same ``check="database"``, so a client has one predicate for "the
    service cannot reach its database" rather than three. The read is never
    softened into a partial answer: reporting ``latest_job`` as absent because it
    could not be read would fabricate "no job" out of "unknown" (Principle I).
    """
    logger.warning("events read: job store unreachable: %s", exc)
    return service_unavailable(f"job store unreachable: {exc}", check="database", **extra)


def _etag(document: ReelDocument) -> str:
    """The entity-tag for an editorial state: the fingerprint's own hash (D-R1).

    Quoted per RFC 9110 and strong: it is canonical over the document's typed
    fields, so a comment-only or formatting-only edit to ``reel.yaml`` leaves it
    unchanged and cannot raise a spurious 412.
    """
    return f'"{editorial_hash(document)}"'


def _event_read_failed(exc: events_read.EventReadError, event_id: str) -> JSONResponse:
    """The scan-failure 502 every event read and the write's pre-read answer with.

    Unprefixed: ``detail`` and ``failure`` are exactly the list's error row.
    """
    failure = exc.failure.value if exc.failure is not None else None
    return bad_gateway(exc.detail, event_id=event_id, failure=failure)


def _if_match_satisfied(header: str, current: str) -> bool:
    """RFC 9110 ``If-Match``: ``*`` matches any state, otherwise strong comparison.

    A weak tag (``W/"..."``) never matches under strong comparison and is simply
    not equal to ``current``, so it falls through to a 412 without a special case.
    """
    candidates = [candidate.strip() for candidate in header.split(",") if candidate.strip()]
    if "*" in candidates:
        return True
    return any(candidate == current for candidate in candidates)


@router.get(
    "/events",
    response_model=List[EventRowOut],
    responses={502: {"model": ProblemOut}, 503: {"model": ProblemOut}},
)
def get_events(request: Request) -> Union[List[EventRowOut], Response]:
    """``GET /api/v1/events`` (task 2.2): every event, freshly scanned.

    One unreadable event costs one error row, never the list (``list_events``
    isolates per event). What remains are the whole-list failures, reported
    distinctly in the shared problem shape: an unreachable job store as the 503
    ``/healthz`` returns, a walk of the project root that fails as the scan-failure
    502. Neither is retried and neither degrades into a partial list.
    """
    settings = _settings(request)
    started = time.monotonic()
    try:
        result = events_read.list_events(
            settings, request.app.state.job_store, request.app.state.runtime
        )
    except SQLAlchemyError as exc:
        return _job_store_unavailable(exc)
    except (ReelError, LayoutError, OSError) as exc:
        return bad_gateway(f"event scan failed: {exc}")
    logger.info(
        "events scan: %d event(s) under %s in %.3fs",
        len(result),
        settings.walk_root,
        time.monotonic() - started,
    )
    return result


@router.get("/events/{event_id:path}/analysis", response_model=AnalysisOut)
def get_analysis(event_id: str, request: Request) -> Union[AnalysisOut, Response]:
    """``GET /api/v1/events/{event_id}/analysis`` (task 2.4): cached segments only.

    Registered *before* the ``{event_id:path}`` detail route below: both patterns
    are greedy over ``/``, and Starlette matches routes in registration order, so
    the more specific ``/analysis`` suffix must be tried first or the detail route
    would swallow it (``event_id`` ending in literal ``/analysis``).
    """
    settings = _settings(request)
    try:
        return events_read.get_analysis(settings, event_id)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {event_id!r} under the configured project root", event_id=event_id
        )


@router.get(
    "/events/{event_id:path}/reel",
    response_model=EditorialDocumentBody,
    responses={
        200: _ETAG_RESPONSE,
        404: {"model": ProblemOut},
        502: {"model": ProblemOut},
    },
)
def get_reel(
    event_id: str, request: Request, response: Response
) -> Union[EditorialDocumentBody, Response]:
    """``GET /api/v1/events/{event_id}/reel``: the editorial document as authored.

    The exact inverse of the PUT below — same model, same serializer — so a client
    may submit what it read without hand-building a write body. Registered *before*
    the greedy ``{event_id:path}`` detail route for the reason the ``/analysis``
    route documents. The response carries an ``ETag`` for the optional ``If-Match``
    precondition on the write; there is deliberately no conditional GET (D-R4).
    """
    settings = _settings(request)
    try:
        document = events_read.get_reel(settings, event_id)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {event_id!r} under the configured project root", event_id=event_id
        )
    except events_read.EventReadError as exc:
        return _event_read_failed(exc, event_id)

    response.headers["ETag"] = _etag(document)
    return document_to_body(document)


def _thumbnail_headers(etag: str) -> dict[str, str]:
    return {"ETag": etag, "Cache-Control": THUMBNAIL_CACHE_CONTROL}


async def _revalidated(if_none_match: str, source: events_read.ThumbnailSource) -> bool:
    """RFC 9110 ``If-None-Match`` under weak comparison, decided before any extraction.

    A ``W/`` prefix is ignored and a comma-separated list is accepted. ``*`` matches
    only when the JPEG is already cached: only then does a current representation exist.
    """
    candidates = [candidate.strip() for candidate in if_none_match.split(",") if candidate.strip()]
    if any(candidate.removeprefix("W/") == source.etag for candidate in candidates):
        return True
    return "*" in candidates and await run_in_threadpool(is_cached, source.cache_path)


def _read_cached_thumbnail(path: Path) -> Optional[bytes]:
    """The cached JPEG's bytes, or ``None`` when it is not cached (yet).

    Any other ``OSError`` is the cache's fault, reported as the engine reports an
    unreadable cache.
    """
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ThumbnailCacheError(f"{path.parent}: cannot read thumbnails: {exc}") from exc


def _read_extracted_thumbnail(path: Path) -> bytes:
    """The JPEG the engine just returned; failing to read it is the cache's fault."""
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ThumbnailCacheError(f"{path.parent}: cannot read thumbnails: {exc}") from exc


async def _serve_thumbnail(
    request: Request, source: events_read.ThumbnailSource, if_none_match: Optional[str]
) -> Response:
    """The 304, the cached 200, or the 200 of an extraction under the gate.

    A cached thumbnail never waits for a slot. The engine's errors propagate to the
    route, which answers them by cause.
    """
    if if_none_match is not None and await _revalidated(if_none_match, source):
        return Response(status_code=304, headers=_thumbnail_headers(source.etag))
    body = await run_in_threadpool(_read_cached_thumbnail, source.cache_path)
    if body is not None:
        return Response(body, media_type="image/jpeg", headers=_thumbnail_headers(source.etag))

    gate: ThumbnailGate = request.app.state.thumbnail_gate
    extract = partial(
        thumbnail_for,
        source.clip_path,
        position=source.position,
        cache_dir=source.cache_dir,
        runtime=request.app.state.runtime,
    )
    path = await gate.produce(source.cache_path.stem, extract)
    body = await run_in_threadpool(_read_extracted_thumbnail, path)
    # The key of the bytes served, not the one computed before extraction: a clip that
    # changed mid-request must not get the old key's strong tag.
    return Response(body, media_type="image/jpeg", headers=_thumbnail_headers(f'"{path.stem}"'))


def _thumbnail_failed(event_id: str, clip: str, detail: str) -> JSONResponse:
    """A thumbnail 502 that is not the clip's fault: no kind, and no caching headers.

    Logged like the editorial write's refused save.
    """
    logger.warning("thumbnail: %s: %s: %s", event_id, clip, detail)
    return bad_gateway(detail, event_id=event_id)


def _clip_failed(event_id: str, clip: str, exc: ThumbnailError) -> JSONResponse:
    """The 502 of a clip the engine cannot make a thumbnail of, with the thumbnail kind.

    The detail is the requested identity and the reason cut to one line with no server
    path (:func:`~auto_reel_ng.thumbs.one_line_cause`, as the CLI's ERROR line); the
    log keeps the full reason, failing command and stderr included.
    """
    detail = f"{clip}: {one_line_cause(exc.reason, Path(exc.clip))}"
    logger.warning("thumbnail: %s: %s: %s", event_id, clip, exc.reason)
    return bad_gateway(
        detail, event_id=event_id, thumbnail_failure=ThumbnailFailure.THUMBNAIL_FAILED.value
    )


@router.get(
    "/events/{event_id:path}/thumbnail",
    response_class=Response,
    responses={
        200: {
            "description": "The clip's thumbnail: a JPEG fitted within 320x180",
            "content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}},
            "headers": _THUMBNAIL_HEADERS,
        },
        304: {
            "description": "Not modified: `If-None-Match` names the current thumbnail",
            "headers": _THUMBNAIL_HEADERS,
        },
        404: {"model": ProblemOut},
        502: {"model": ProblemOut},
    },
)
async def get_thumbnail(
    event_id: str,
    request: Request,
    clip: str = Query(
        description="The clip's identity as the event detail lists it: its event-relative path",
    ),
    _version: Optional[str] = Query(
        default=None,
        alias="v",
        description="An opaque cache-busting version; accepted and ignored",
    ),
    _if_none_match: Optional[str] = Header(default=None, alias="If-None-Match"),
) -> Response:
    """``GET /api/v1/events/{event_id}/thumbnail?clip=``: one clip's thumbnail (D-11).

    Registered *before* the greedy ``{event_id:path}`` detail route for the reason
    the ``/analysis`` route documents; the clip identity is a query parameter
    because two greedy path parameters cannot be told apart.

    ``async`` on purpose: a request waiting for an extraction slot waits on the
    gate's ``asyncio`` primitives and holds no threadpool worker, so a page of cold
    thumbnails cannot starve the other routes. Every blocking step (the listing,
    the stat, reading the JPEG, the extraction) runs in the threadpool.

    Failures answer by cause and carry no caching headers: 404 for an id the events
    list does not show as an event, or a clip that is not on disk in it; 502 with
    ``thumbnail_failure`` when the engine cannot make this clip's thumbnail, with the
    list's ``failure`` when the event cannot be listed, and with neither for the cache
    or ``config.yaml``. Nothing is written into the library, and the database is
    never touched.

    ``If-None-Match`` is published as a parameter, but read from every header line
    the request carries: the parameter would hold only the first.
    """
    settings = _settings(request)
    if_none_match = ", ".join(request.headers.getlist("if-none-match")) or None
    try:
        source = await run_in_threadpool(events_read.thumbnail_source, settings, event_id, clip)
        return await _serve_thumbnail(request, source, if_none_match)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {event_id!r} under the configured project root", event_id=event_id
        )
    except events_read.ClipNotFoundError as exc:
        return not_found(str(exc), event_id=event_id)
    except events_read.EventReadError as exc:
        logger.warning("thumbnail: %s: %s: %s", event_id, clip, exc.detail)
        return _event_read_failed(exc, event_id)
    except (ConfigError, LayoutError) as exc:
        return _thumbnail_failed(event_id, clip, str(exc))
    except ThumbnailError as exc:
        return _clip_failed(event_id, clip, exc)
    except ThumbnailCacheError as exc:
        return _thumbnail_failed(event_id, clip, str(exc))


@router.get(
    "/events/{event_id:path}",
    response_model=EventDetailOut,
    responses={
        404: {"model": ProblemOut},
        502: {"model": ProblemOut},
        503: {"model": ProblemOut},
    },
)
def get_event(event_id: str, request: Request) -> Union[EventDetailOut, Response]:
    """``GET /api/v1/events/{event_id}`` (task 2.3): current detail from disk.

    An event the list would show as an error row is the scan-failure 502 here,
    carrying the same ``failure`` kind and ``detail`` as that row, never a 500.
    """
    settings = _settings(request)
    try:
        return events_read.get_event(
            settings, event_id, request.app.state.job_store, request.app.state.runtime
        )
    except SQLAlchemyError as exc:
        return _job_store_unavailable(exc, event_id=event_id)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {event_id!r} under the configured project root", event_id=event_id
        )
    except events_read.EventReadError as exc:
        return _event_read_failed(exc, event_id)


@router.put(
    "/events/{event_id:path}/reel",
    response_model=EditorialWriteResult,
    responses={
        200: _ETAG_RESPONSE,
        400: {"model": ProblemOut},
        404: {"model": ProblemOut},
        412: {"model": ProblemOut},
        502: {"model": ProblemOut},
    },
)
def put_reel(
    event_id: str,
    payload: EditorialDocumentBody,
    request: Request,
    response: Response,
    if_match: Optional[str] = Header(default=None, alias="If-Match"),
) -> Union[EditorialWriteResult, Response]:
    """``PUT /api/v1/events/{event_id}/reel``: apply a desired editorial state (D-E2).

    A coarse whole-document write: ``payload`` is the complete desired editorial
    state, merged onto the event's existing structure (never replacing the file
    outright, D-E1) and validated fail-loud before anything is persisted. The
    route carries no editorial logic of its own (D-E6) — it resolves the event,
    delegates to the engine operation, and echoes the persisted document plus the
    event's resulting staleness verdict (computed free, D-E5) so the client needs
    no follow-up GET. The write never enqueues and never touches the render
    manifest.

    A successful write carries an ``ETag`` for the state it just persisted,
    computed from the returned document by the same helper ``get_reel`` uses, so a
    client may chain conditional writes with no intervening read. A ``412`` carries
    none: a client that lost the race must re-read before it overwrites.

    Failures answer by cause and write nothing: 400 for an invalid submitted state
    (with ``failure: unusable_metadata`` when the engine refuses a state that
    leaves the event without a real date or title), 404, 412, and 502 for the disk:
    an existing document that cannot be read (with its ``failure`` kind, as the
    reads report it) or a save the filesystem refuses (naming the OS error).
    """
    settings = _settings(request)
    try:
        event_dir = events_read.resolve_event_dir(settings, event_id)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {event_id!r} under the configured project root", event_id=event_id
        )

    # Read on every request, not only with If-Match, so both paths answer a broken
    # file identically: the disk's fault (502), never the request's (400).
    try:
        current = events_read.get_reel(settings, event_id)
    except events_read.EventReadError as exc:
        return _event_read_failed(exc, event_id)
    if if_match is not None and not _if_match_satisfied(if_match, _etag(current)):
        return precondition_failed(
            f"event {event_id!r} changed since it was read; re-read and re-apply the edit",
            event_id=event_id,
        )

    desired_data = payload.model_dump(by_alias=True)
    try:
        document = apply_editorial_write(event_dir, desired_data)
    except EventMetadataError as exc:  # before ReelError: it is a subclass
        return bad_request(
            str(exc), event_id=event_id, failure=EventFailure.UNUSABLE_METADATA.value
        )
    except ReelError as exc:  # the submitted state is invalid
        return bad_request(str(exc), event_id=event_id)
    except OSError as exc:  # the filesystem refused the save
        logger.warning("editorial write: %s: %s", event_id, exc)
        return bad_gateway(f"reel.yaml could not be saved: {exc}", event_id=event_id)

    runtime = request.app.state.runtime
    response.headers["ETag"] = _etag(document)
    return EditorialWriteResult(
        document=document_to_body(document),
        staleness=events_read.staleness_for(
            settings, event_dir, document, runtime, events_read.project_look_defaults(settings)
        ),
    )


__all__ = ["router"]
