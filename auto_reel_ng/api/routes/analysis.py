"""The analysis routes (``analysis-enqueue-api``): the read, the per-event enqueue, Analyze all.

Thin wiring over :mod:`..analysis_read`. The read and the per-event enqueue take an event id
with ``/`` in it, so this router is included before the events router: both are greedy
``{event_id:path}`` patterns, Starlette matches in registration order, and the events router's
detail route would otherwise swallow an id ending in ``/analysis``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError

from ...analysis.state import ClipAnalysis, clip_analysis_states, needs_analysis
from ...errors import AnalysisStateError
from ...ingest import LayoutError
from ...persistence.job_store import JobStore
from ...persistence.models import JobKind, JobStatus
from ...scheduler import submit_analysis
from .. import analysis_read, events_read
from ..problem import bad_gateway, conflict, not_found, service_unavailable
from ..schemas import (
    AnalysisEnqueueRequest,
    AnalysisFreshResult,
    AnalysisOut,
    AnalyzeAllResult,
    EnqueueConflict,
    JobOut,
    ProblemOut,
)
from ..serialize import job_to_out
from ..settings import ApiSettings
from .guards import job_store_unreachable

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


def _folder_unreadable(exc: OSError, event_id: str) -> JSONResponse:
    """An event folder that cannot be listed: the 502 with the list's ``unreadable_disk`` kind."""
    failure = events_read.classify_event_failure(exc)
    return bad_gateway(
        str(exc), event_id=event_id, failure=failure.value if failure is not None else None
    )


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


def _listed_event_dir(settings: ApiSettings, event_id: str) -> Union[Path, JSONResponse]:
    """The event folder the id names when the events list shows it, else the 404 or 502."""
    try:
        return events_read.listed_event_dir(settings, event_id)
    except events_read.EventNotFoundError:
        return _not_found(event_id)
    except LayoutError as exc:
        return bad_gateway(f"event scan failed: {exc}", event_id=event_id)
    except OSError as exc:  # the walk, on the id's own folder
        return _folder_unreadable(exc, event_id)


def _clip_states(event_dir: Path, event_id: str) -> Union[List[ClipAnalysis], JSONResponse]:
    """The event's clips' disk states, else the 502 of what could not be read."""
    try:
        return clip_analysis_states(event_dir)
    except OSError as exc:  # the event folder cannot be listed
        return _folder_unreadable(exc, event_id)
    except AnalysisStateError as exc:
        return _state_unreadable(exc, event_id)


def _analysis_job_active(job_id: object, event_id: str) -> JSONResponse:
    """The 409 for an event that already has a queued or running analysis job."""
    return conflict(
        f"an analysis job is already active for event {event_id!r}",
        job_id=str(job_id),
        conflict=EnqueueConflict.ACTIVE_JOB.value,
    )


@router.post(
    "/events/{event_id:path}/analysis",
    response_model=JobOut,
    status_code=201,
    responses={
        200: {
            "model": AnalysisFreshResult,
            "description": "No clip needs analysis; nothing was enqueued",
        },
        404: {"model": ProblemOut},
        409: {"model": ProblemOut},
        502: {"model": ProblemOut},
        503: {"model": ProblemOut},
    },
)
@job_store_unreachable
def enqueue_analysis(
    event_id: str,
    request: Request,
    body: Optional[AnalysisEnqueueRequest] = Body(default=None),
) -> Union[JobOut, AnalysisFreshResult, Response]:
    """``POST /api/v1/events/{event_id}/analysis``: enqueue the event's analysis job.

    Optional body ``{"force": true}`` is Re-analyze: the job analyzes every clip again,
    overriding results and recorded failures when it runs (the request itself writes nothing
    but the job row). 201 with the queued job; 200 ``fresh`` when no clip reads ``never`` or
    ``stale`` and ``force`` is false, or when the folder lists no clip; 409 ``active_job`` with
    the job's id while an analysis job is queued or running for the event, also when a
    concurrent request inserted first (a forced request first gives a ``queued`` unforced job
    ``force``); 404 for an id the events list does not show; 502 for an event folder, a clip or
    a cache entry that cannot be read; 503 when the job store is unreachable. The event's
    render and proxy jobs are independent of it. ``reel.yaml`` is never read.
    """
    force = body.force if body is not None else False
    settings = _settings(request)
    store: JobStore = request.app.state.job_store
    event_dir = _listed_event_dir(settings, event_id)
    if isinstance(event_dir, JSONResponse):
        return event_dir

    project_root = str(settings.project_root)
    active = store.active_job(project_root, event_id, kind=JobKind.ANALYSIS)
    if active is not None:
        if force and active.status is JobStatus.QUEUED:
            store.force_queued(active.id)  # Re-analyze is not lost behind a queued job
        return _analysis_job_active(active.id, event_id)

    clips = _clip_states(event_dir, event_id)
    if isinstance(clips, JSONResponse):
        return clips
    if not clips or (not force and not needs_analysis(clips)):
        # A raw response: the declared response_model is JobOut (see ``create_job``).
        result = AnalysisFreshResult(
            event_id=event_id,
            status="fresh",
            clip_count=len(clips),
            failed_count=analysis_read.failed_count(clips),
        )
        return JSONResponse(status_code=200, content=result.model_dump(mode="json"))

    submission = submit_analysis(store, settings.project_root, [event_dir], force=force)[0]
    if not submission.created:
        # A concurrent request inserted after the pre-check: the insertion decides.
        return _analysis_job_active(submission.job_id, event_id)
    job = store.get(submission.job_id)
    assert job is not None  # nosec B101 - just inserted, must be readable
    return job_to_out(job)


@router.post(
    "/analysis",
    response_model=AnalyzeAllResult,
    responses={502: {"model": ProblemOut}, 503: {"model": ProblemOut}},
)
@job_store_unreachable
def analyze_all(request: Request) -> Union[AnalyzeAllResult, Response]:
    """``POST /api/v1/analysis``: Analyze all.

    Considers every event the events list shows, in its order: an event with a queued or
    running analysis job counts ``active``; one whose folder, a clip or a cache entry cannot
    be read is listed in ``unreadable`` and the others are still considered; one where no clip
    reads ``never`` or ``stale`` counts ``fresh``; every other event gets an unforced analysis
    job and counts ``queued``. No body. A project walk that fails is a 502 with nothing
    enqueued; an unreachable job store a 503 (jobs inserted before it stay queued, and a repeat
    counts them ``active``). Nothing is started or written but job rows; ``reel.yaml`` is never
    read.
    """
    try:
        return analysis_read.analyze_all(_settings(request), request.app.state.job_store)
    except (LayoutError, OSError) as exc:
        return bad_gateway(f"event scan failed: {exc}")


__all__ = ["router"]
