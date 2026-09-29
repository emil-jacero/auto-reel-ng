"""Events + analysis read routes (tasks 2.2-2.4): thin wiring over ``events_read``.

Every route here is scan-on-request (D-A3) — no caching, no database copy of
event/clip state; the freshest possible read of ``reel.yaml``/disk on every call.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Union

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from ...errors import ReelError
from ...event.editorial import apply_editorial_write
from ...ingest import LayoutError
from ...reel.document import ReelDocument
from ...staleness.fingerprint import editorial_hash
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
    EventRowOut,
    ProblemOut,
)
from ..serialize import document_to_body
from ..settings import ApiSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


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


@router.get("/events/{event_id:path}/reel", response_model=EditorialDocumentBody)
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
        return bad_gateway(f"event {event_id!r}: {exc.detail}", event_id=event_id)

    response.headers["ETag"] = _etag(document)
    return document_to_body(document)


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
    """``GET /api/v1/events/{event_id}`` (task 2.3): current detail from disk."""
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
        return bad_gateway(f"event {event_id!r}: {exc.detail}", event_id=event_id)


@router.put("/events/{event_id:path}/reel", response_model=EditorialWriteResult)
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
    """
    settings = _settings(request)
    try:
        event_dir = events_read.resolve_event_dir(settings, event_id)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {event_id!r} under the configured project root", event_id=event_id
        )

    if if_match is not None:
        try:
            current = events_read.get_reel(settings, event_id)
        except events_read.EventReadError as exc:
            return bad_gateway(f"event {event_id!r}: {exc.detail}", event_id=event_id)
        if not _if_match_satisfied(if_match, _etag(current)):
            return precondition_failed(
                f"event {event_id!r} changed since it was read; re-read and re-apply the edit",
                event_id=event_id,
            )

    desired_data = payload.model_dump(by_alias=True)
    try:
        document = apply_editorial_write(event_dir, desired_data)
    except ReelError as exc:
        return bad_request(str(exc), event_id=event_id)

    runtime = request.app.state.runtime
    response.headers["ETag"] = _etag(document)
    return EditorialWriteResult(
        document=document_to_body(document),
        staleness=events_read.staleness_for(
            settings, event_dir, document, runtime, events_read.project_look_defaults(settings)
        ),
    )


__all__ = ["router"]
