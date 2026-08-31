"""Events + analysis read routes (tasks 2.2-2.4): thin wiring over ``events_read``.

Every route here is scan-on-request (D-A3) — no caching, no database copy of
event/clip state; the freshest possible read of ``reel.yaml``/disk on every call.
"""

from __future__ import annotations

import logging
import time
from typing import List, Union

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ...errors import ReelError
from ...event.editorial import apply_editorial_write
from .. import events_read
from ..problem import bad_gateway, bad_request, not_found
from ..schemas import (
    AnalysisOut,
    EditorialDocumentBody,
    EditorialWriteResult,
    EventDetailOut,
    EventSummaryOut,
)
from ..serialize import document_to_body
from ..settings import ApiSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


def _settings(request: Request) -> ApiSettings:
    return request.app.state.settings  # type: ignore[no-any-return]


@router.get("/events", response_model=List[EventSummaryOut])
def get_events(request: Request) -> List[EventSummaryOut]:
    """``GET /api/v1/events`` (task 2.2): every event, freshly scanned."""
    settings = _settings(request)
    started = time.monotonic()
    result = events_read.list_events(settings, request.app.state.job_store)
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


@router.get("/events/{event_id:path}", response_model=EventDetailOut)
def get_event(event_id: str, request: Request) -> Union[EventDetailOut, Response]:
    """``GET /api/v1/events/{event_id}`` (task 2.3): current detail from disk."""
    settings = _settings(request)
    try:
        return events_read.get_event(
            settings, event_id, request.app.state.job_store, request.app.state.runtime
        )
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {event_id!r} under the configured project root", event_id=event_id
        )
    except events_read.EventReadError as exc:
        return bad_gateway(f"event {event_id!r}: {exc.detail}", event_id=event_id)


@router.put("/events/{event_id:path}/reel", response_model=EditorialWriteResult)
def put_reel(
    event_id: str, payload: EditorialDocumentBody, request: Request
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
    """
    settings = _settings(request)
    try:
        event_dir = events_read.resolve_event_dir(settings, event_id)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {event_id!r} under the configured project root", event_id=event_id
        )

    desired_data = payload.model_dump(by_alias=True)
    try:
        document = apply_editorial_write(event_dir, desired_data)
    except ReelError as exc:
        return bad_request(str(exc), event_id=event_id)

    runtime = request.app.state.runtime
    return EditorialWriteResult(
        document=document_to_body(document),
        staleness=events_read.staleness_for(settings, event_dir, document, runtime),
    )


__all__ = ["router"]
