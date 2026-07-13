"""Shared ``Job`` -> :class:`JobOut` conversion (routes/jobs.py and the WS hub, ws.py)."""

from __future__ import annotations

from .schemas import JobOut


def job_to_out(job: object) -> JobOut:
    """Convert a store ``Job`` row (or a duck-typed stand-in, for hub tests) to :class:`JobOut`."""
    return JobOut(
        id=job.id,  # type: ignore[attr-defined]
        status=job.status.value,  # type: ignore[attr-defined]
        event_dir=job.event_dir,  # type: ignore[attr-defined]
        project_root=job.project_root,  # type: ignore[attr-defined]
        device=job.device,  # type: ignore[attr-defined]
        progress=job.progress,  # type: ignore[attr-defined]
        worker_id=job.worker_id,  # type: ignore[attr-defined]
        cancel_requested=job.cancel_requested,  # type: ignore[attr-defined]
        requeue_count=job.requeue_count,  # type: ignore[attr-defined]
        force=job.force,  # type: ignore[attr-defined]
        fingerprint=job.fingerprint,  # type: ignore[attr-defined]
        error=job.error,  # type: ignore[attr-defined]
        created_at=job.created_at,  # type: ignore[attr-defined]
        started_at=job.started_at,  # type: ignore[attr-defined]
        finished_at=job.finished_at,  # type: ignore[attr-defined]
    )


__all__ = ["job_to_out"]
