"""Jobs lifecycle routes (tasks 3.1-3.3): thin wiring over the existing ``JobStore``.

Every write goes through an existing store verb (``enqueue``/``request_cancel``);
the API never transitions ``status`` itself (D-A6).
"""

from __future__ import annotations

import uuid
from typing import List, Optional, Union

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from ...persistence.job_store import JobStore
from ...persistence.models import JobStatus
from .. import events_read
from ..problem import conflict, not_found
from ..schemas import CancelResult, EnqueueRequest, JobOut
from ..serialize import job_to_out as _job_out

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/jobs", response_model=JobOut, status_code=201)
def create_job(payload: EnqueueRequest, request: Request) -> Union[JobOut, Response]:
    """``POST /api/v1/jobs`` (task 3.1): idempotent enqueue, 409 on active duplicate."""
    settings = request.app.state.settings
    store: JobStore = request.app.state.job_store

    try:
        events_read.resolve_event_dir(settings, payload.event_id)
    except events_read.EventNotFoundError:
        return not_found(
            f"no event {payload.event_id!r} under the configured project root",
            event_id=payload.event_id,
        )

    project_root = str(settings.project_root)
    existing = store.active_job(project_root, payload.event_id)
    if existing is not None:
        return conflict(
            f"an active job already exists for event {payload.event_id!r}", id=str(existing.id)
        )

    job_id = store.enqueue(project_root, payload.event_id, device=payload.device)
    job = store.get(job_id)
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


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, request: Request) -> Union[JobOut, Response]:
    """``GET /api/v1/jobs/{id}`` (task 3.2): one job's full detail."""
    store: JobStore = request.app.state.job_store
    job = store.get(job_id)
    if job is None:
        return not_found(f"no job with id {job_id}", id=str(job_id))
    return _job_out(job)


@router.post("/jobs/{job_id}/cancel", response_model=CancelResult)
def cancel_job(job_id: uuid.UUID, request: Request) -> Union[CancelResult, Response]:
    """``POST /api/v1/jobs/{id}/cancel`` (task 3.3): request_cancel, tri-state outcome."""
    store: JobStore = request.app.state.job_store
    job = store.get(job_id)
    if job is None:
        return not_found(f"no job with id {job_id}", id=str(job_id))

    if job.status == JobStatus.RUNNING:
        outcome = "flagged-running"
    elif job.status == JobStatus.QUEUED:
        outcome = "canceled-queued"
    else:
        outcome = "no-op-terminal"

    result = store.request_cancel(job_id)
    final = result if result is not None else job
    return CancelResult(id=final.id, status=final.status.value, outcome=outcome)


__all__ = ["router"]
