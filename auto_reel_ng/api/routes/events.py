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

from .. import events_read
from ..problem import bad_gateway, not_found
from ..schemas import AnalysisOut, EventDetailOut, EventSummaryOut
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


__all__ = ["router"]
