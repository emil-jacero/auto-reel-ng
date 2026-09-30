"""Jobs lifecycle routes (tasks 3.1-3.3): thin wiring over the existing ``JobStore``.

Every write goes through a store verb that reports what it did — ``submit``
(whether it created the job) and ``cancel`` (the outcome it applied, under the
row's lock) — so a response maps the store's facts to a status code rather than
predicting them from an earlier read. The API never transitions ``status`` itself
(D-A6).
"""

from __future__ import annotations

import uuid
from typing import List, Optional, Union

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from ...cli.adoption import load_or_seed
from ...config.project import load_project_config, resolve_look_defaults
from ...persistence.job_store import JobStore
from ...persistence.models import JobStatus
from ...render import output_relpath
from ...staleness.fingerprint import compute_fingerprint
from ...staleness.gate import evaluate
from ...staleness.manifest import manifest_path
from .. import events_read
from ..problem import conflict, not_found
from ..schemas import CancelResult, EnqueueRequest, FreshResult, JobOut, ProblemOut
from ..serialize import job_to_out as _job_out

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post(
    "/jobs",
    response_model=JobOut,
    status_code=201,
    responses={
        200: {"model": FreshResult, "description": "The event is fresh; nothing was enqueued"},
        404: {"model": ProblemOut},
        409: {"model": ProblemOut},
    },
)
def create_job(payload: EnqueueRequest, request: Request) -> Union[JobOut, FreshResult, Response]:
    """``POST /api/v1/jobs`` (task 3.1, gated per change-detection §8.14).

    Idempotent enqueue, 409 on active duplicate, 200 "fresh — not enqueued" when
    the event is fresh and ``force`` is false. The API never transitions job
    status itself (D-A6) — the gate decision is made here, at enqueue, the same
    as the CLI's own ``enqueue``.
    """
    settings = request.app.state.settings
    store: JobStore = request.app.state.job_store

    try:
        event_dir = events_read.resolve_event_dir(settings, payload.event_id)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {payload.event_id!r} under the configured project root",
            event_id=payload.event_id,
        )

    project_root = str(settings.project_root)
    existing = store.active_job(project_root, payload.event_id)
    if existing is not None:
        return conflict(
            f"an active job already exists for event {payload.event_id!r}",
            job_id=str(existing.id),
        )

    runtime = request.app.state.runtime
    look_defaults = resolve_look_defaults(load_project_config(settings.project_root))
    document = load_or_seed(event_dir, order=settings.clip_order)[0]
    fingerprint = compute_fingerprint(
        document, event_dir=event_dir, look_defaults=look_defaults, ffmpeg_version=runtime.version
    )

    if not payload.force:
        output_path = settings.output_dir / output_relpath(document.metadata)
        verdict = evaluate(event_dir, output_path, fingerprint)
        if not verdict.stale:
            # A raw Response (task 3.1's not_found/conflict pattern): the declared
            # response_model is JobOut, so a differently-shaped 200 body must
            # bypass response_model serialization rather than being coerced into it;
            # ``responses=`` above publishes its shape.
            fresh = FreshResult(
                event_id=payload.event_id,
                status="fresh",
                fingerprint=fingerprint.combined,
                manifest=str(manifest_path(event_dir).relative_to(settings.project_root)),
            )
            return JSONResponse(status_code=200, content=fresh.model_dump(mode="json"))

    submission = store.submit(
        project_root,
        payload.event_id,
        device=payload.device,
        force=payload.force,
        fingerprint=fingerprint.combined,
    )
    if not submission.created:
        # A concurrent request inserted after the pre-check above: the insertion
        # decides, so losing that race is the same visible conflict, never a 201.
        return conflict(
            f"an active job already exists for event {payload.event_id!r}",
            job_id=str(submission.job_id),
        )
    job = store.get(submission.job_id)
    assert job is not None  # pragma: no cover - just inserted, must be readable
    return _job_out(job)


@router.get("/jobs", response_model=List[JobOut])
def list_jobs(request: Request, status: Optional[JobStatus] = Query(None)) -> List[JobOut]:
    """``GET /api/v1/jobs`` (task 3.2): optionally filtered by status, oldest first."""
    store: JobStore = request.app.state.job_store
    if status is not None:
        jobs = store.list_by_status(status)
    else:
        jobs = sorted(
            (job for one_status in JobStatus for job in store.list_by_status(one_status)),
            key=lambda job: job.created_at,
        )
    return [_job_out(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobOut, responses={404: {"model": ProblemOut}})
def get_job(job_id: uuid.UUID, request: Request) -> Union[JobOut, Response]:
    """``GET /api/v1/jobs/{id}`` (task 3.2): one job's full detail."""
    store: JobStore = request.app.state.job_store
    job = store.get(job_id)
    if job is None:
        return not_found(f"no job with id {job_id}", job_id=str(job_id))
    return _job_out(job)


@router.post(
    "/jobs/{job_id}/cancel", response_model=CancelResult, responses={404: {"model": ProblemOut}}
)
def cancel_job(job_id: uuid.UUID, request: Request) -> Union[CancelResult, Response]:
    """``POST /api/v1/jobs/{id}/cancel`` (task 3.3): the store's cancel and its outcome.

    One store call and no pre-read: the outcome and the echoed status come from the
    locked transaction that applied the cancel, so a worker's claim landing
    in between can never make them disagree.
    """
    store: JobStore = request.app.state.job_store
    result = store.cancel(job_id)
    if result is None:
        return not_found(f"no job with id {job_id}", job_id=str(job_id))
    return CancelResult(id=result.job.id, status=result.job.status, outcome=result.outcome)


__all__ = ["router"]
