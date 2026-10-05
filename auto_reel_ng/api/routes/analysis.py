"""The analysis routes (``analysis-enqueue-api``): the read of an event's analysis state.

Thin wiring over :mod:`..analysis_read`. The read and the per-event enqueue take an event id
with ``/`` in it, so this router is included before the events router: both are greedy
``{event_id:path}`` patterns, Starlette matches in registration order, and the events router's
detail route would otherwise swallow an id ending in ``/analysis``.
"""

from __future__ import annotations

import logging
from typing import Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from ...errors import AnalysisStateError
from ...ingest import LayoutError
from .. import analysis_read, events_read
from ..problem import bad_gateway, not_found, service_unavailable
from ..schemas import AnalysisOut, ProblemOut
from ..settings import ApiSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["events"])


def _settings(request: Request) -> ApiSettings:
    return request.app.state.settings  # type: ignore[no-any-return]


def _not_found(event_id: str) -> JSONResponse:
    return not_found(f"no event {event_id!r} under the configured project root", event_id=event_id)


def _event_read_failed(exc: events_read.EventReadError, event_id: str) -> JSONResponse:
    """The scan-failure 502 the events reads answer with: the list's ``failure`` kind."""
    failure = exc.failure.value if exc.failure is not None else None
    return bad_gateway(exc.detail, event_id=event_id, failure=failure)


def _state_unreadable(exc: AnalysisStateError, event_id: str) -> JSONResponse:
    """A clip or a cache entry that cannot be read: a 502 with no kind, never a guessed state."""
    logger.warning("analysis: %s: %s", event_id, exc)
    return bad_gateway(f"analysis state unreadable: {exc}", event_id=event_id)


@router.get(
    "/events/{event_id:path}/analysis",
    response_model=AnalysisOut,
    responses={404: {"model": ProblemOut}, 502: {"model": ProblemOut}, 503: {"model": ProblemOut}},
)
def get_analysis(event_id: str, request: Request) -> Union[AnalysisOut, Response]:
    """``GET /api/v1/events/{event_id}/analysis``: cached segments and the analysis state.

    Answers only for an id the events list shows, like the thumbnail and media
    routes: 404 for any other directory (a year folder, an event's ``original/``, a
    ``.reelignore``d event). ``state`` and every clip's ``state`` are read by ``stat`` and
    JSON only, with ``analyzing`` from the event's queued or running analysis job (in
    ``job``); nothing is started or written and ``reel.yaml`` is never read. ``analyzed`` is
    legacy. 502 for an event folder that cannot be listed (with the list's ``failure``
    kind), and with no kind for a layout the service cannot resolve or a clip or cache entry
    that cannot be read; 503 when the job store is unreachable.
    """
    settings = _settings(request)
    try:
        return analysis_read.get_analysis(settings, event_id, request.app.state.job_store)
    except events_read.EventNotFoundError:
        return _not_found(event_id)
    except events_read.EventReadError as exc:
        return _event_read_failed(exc, event_id)
    except LayoutError as exc:
        return bad_gateway(str(exc), event_id=event_id)
    except AnalysisStateError as exc:
        return _state_unreadable(exc, event_id)
    except SQLAlchemyError as exc:
        logger.warning("analysis: job store unreachable: %s", exc)
        return service_unavailable(
            f"job store unreachable: {exc}", check="database", event_id=event_id
        )


__all__ = ["router"]
