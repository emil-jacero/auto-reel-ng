"""The durable job-store repository (D-P2): the ``jobs`` table *is* the queue.

There is no in-memory queue and no external broker — a worker process (7b) claims
work by calling :meth:`JobStore.claim_next`, which must be race-free at the DB
level (D-P3, ``FOR UPDATE SKIP LOCKED``) since two workers may call it
concurrently. Every operation opens its own transaction via
:func:`~auto_reel_ng.persistence.engine.session_scope`.

Two verbs describe different failure handling, deliberately: an *illegal*
transition (``transition`` on a non-``running`` job) raises
:class:`~auto_reel_ng.errors.IllegalJobTransitionError` — the caller's assumption
about job state was wrong. A stale write (``set_progress``/``cancel_queued`` on a
job no longer in the expected state) is silently ignored — the caller's
information may simply be stale by the time the write lands.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..errors import IllegalJobTransitionError
from .engine import session_scope
from .models import Job, JobStatus

_TERMINAL_STATUSES = {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED}
_ACTIVE_STATUSES = (JobStatus.QUEUED, JobStatus.RUNNING)


class JobStore:
    """Repository over the ``jobs`` table; one instance per session factory."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def enqueue(
        self,
        project_root: str,
        event_dir: str,
        *,
        device: str = "auto",
        output_path: Optional[str] = None,
    ) -> uuid.UUID:
        """Insert a new ``queued`` job for ``event_dir`` (project-root-relative).

        Idempotent (D-S7/D-S8): when an active (``queued``/``running``) job already
        exists for the same ``(project_root, event_dir)``, no row is inserted and the
        existing job's id is returned instead. The database's partial unique index
        is the source of truth for this — a concurrent enqueue for the same identity
        races safely against it — so the insert is attempted first and a unique
        violation falls back to looking the existing job up, rather than a
        check-then-insert with its own race window.
        """
        job = Job(
            project_root=project_root, event_dir=event_dir, device=device, output_path=output_path
        )
        with session_scope(self._session_factory) as session:
            session.add(job)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                existing = self._active_job(session, project_root, event_dir)
                if existing is None:
                    raise  # pragma: no cover - defensive, the index caused the conflict
                return existing.id
            return job.id

    @staticmethod
    def _active_job(session: Session, project_root: str, event_dir: str) -> Optional[Job]:
        """The active (``queued``/``running``) job for this identity, if any."""
        stmt = select(Job).where(
            Job.project_root == project_root,
            Job.event_dir == event_dir,
            Job.status.in_(_ACTIVE_STATUSES),
        )
        return session.execute(stmt).scalar_one_or_none()

    def active_job(self, project_root: str, event_dir: str) -> Optional[Job]:
        """Read-only lookup of the active (``queued``/``running``) job for this identity.

        Used by callers (the ``enqueue`` CLI command) that want to report whether
        a job already existed, without relying on :meth:`enqueue`'s own return
        value to distinguish the two cases.
        """
        with session_scope(self._session_factory) as session:
            return self._active_job(session, project_root, event_dir)

    def claim_next(self, worker_id: str, device_filter: Optional[str] = None) -> Optional[Job]:
        """Atomically claim the oldest eligible ``queued`` job (D-P3).

        Race-free via ``FOR UPDATE SKIP LOCKED``: two concurrent callers never
        claim the same row. Ordered ``priority`` descending, ``created_at``
        ascending (FIFO within a priority). A job is eligible for
        ``device_filter`` when its ``device`` is ``"auto"`` or equals
        ``device_filter``; passing ``None`` claims across every device.
        """
        with session_scope(self._session_factory) as session:
            stmt = select(Job).where(Job.status == JobStatus.QUEUED)
            if device_filter is not None:
                stmt = stmt.where(or_(Job.device == "auto", Job.device == device_filter))
            stmt = (
                stmt.order_by(Job.priority.desc(), Job.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            job = session.execute(stmt).scalar_one_or_none()
            if job is None:
                return None
            job.status = JobStatus.RUNNING
            job.worker_id = worker_id
            job.started_at = func.now()  # pylint: disable=not-callable
            session.flush()
            session.refresh(job)
            return job

    def transition(
        self,
        job_id: uuid.UUID,
        terminal_status: JobStatus,
        *,
        error: Optional[str] = None,
    ) -> Job:
        """Move a ``running`` job to ``done``/``failed``/``canceled``, stamping ``finished_at``.

        Raises :class:`~auto_reel_ng.errors.IllegalJobTransitionError` if the job
        is missing or not currently ``running`` — the row is left unchanged.
        """
        if terminal_status not in _TERMINAL_STATUSES:
            raise ValueError(f"{terminal_status!r} is not a terminal status")
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is None or job.status != JobStatus.RUNNING:
                found = job.status.value if job is not None else "missing"
                raise IllegalJobTransitionError(
                    f"cannot transition job {job_id} to {terminal_status.value}: "
                    f"job is not running (status={found})"
                )
            job.status = terminal_status
            job.finished_at = func.now()  # pylint: disable=not-callable
            job.error = error if terminal_status == JobStatus.FAILED else None
            session.flush()
            session.refresh(job)
            return job

    def set_progress(self, job_id: uuid.UUID, fraction: float) -> None:
        """Persist ``progress`` (clamped to ``[0.0, 1.0]``) for a ``running`` job.

        Silently ignored for a missing or non-``running`` job.
        """
        clamped = max(0.0, min(1.0, fraction))
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is None or job.status != JobStatus.RUNNING:
                return
            job.progress = clamped

    def get(self, job_id: uuid.UUID) -> Optional[Job]:
        """Fetch a job by id, or ``None`` if it does not exist."""
        with session_scope(self._session_factory) as session:
            return session.get(Job, job_id)

    def list_by_status(self, status: JobStatus) -> list[Job]:
        """List jobs with the given ``status``, ordered by ``created_at`` ascending."""
        with session_scope(self._session_factory) as session:
            stmt = select(Job).where(Job.status == status).order_by(Job.created_at.asc())
            return list(session.execute(stmt).scalars().all())

    def latest_by_project(self, project_root: str) -> dict[str, Job]:
        """The most recent job (any status) per ``event_dir`` under ``project_root``.

        One query (Postgres ``DISTINCT ON``) rather than a per-event lookup or a
        full-table scan per status — the events-list read model (API, D-A3) needs
        "latest job per event" for a project without an N+1 query per event.
        """
        with session_scope(self._session_factory) as session:
            stmt = (
                select(Job)
                .where(Job.project_root == project_root)
                .distinct(Job.event_dir)
                .order_by(Job.event_dir, Job.created_at.desc())
            )
            jobs = session.execute(stmt).scalars().all()
            return {job.event_dir: job for job in jobs}

    def cancel_queued(self, job_id: uuid.UUID) -> Optional[Job]:
        """Move a ``queued`` job to ``canceled``, stamping ``finished_at``.

        Silently ignored (returns ``None``) for a missing or non-``queued`` job,
        so it is safe to call without first checking the job's current status.
        """
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is None or job.status != JobStatus.QUEUED:
                return None
            job.status = JobStatus.CANCELED
            job.finished_at = func.now()  # pylint: disable=not-callable
            session.flush()
            session.refresh(job)
            return job

    def request_cancel(self, job_id: uuid.UUID) -> Optional[Job]:
        """Request cancellation of ``job_id`` (D-S6).

        A ``running`` job only has its ``cancel_requested`` flag set — the worker
        remains the sole writer of ``status`` and performs the terminal transition
        itself once it next checks the flag between segments. A ``queued`` job is
        canceled directly (equivalent to :meth:`cancel_queued`). A job already in a
        terminal state, or missing, is a no-op returning ``None``.
        """
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is None:
                return None
            if job.status == JobStatus.RUNNING:
                job.cancel_requested = True
                session.flush()
                session.refresh(job)
                return job
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELED
                job.finished_at = func.now()  # pylint: disable=not-callable
                session.flush()
                session.refresh(job)
                return job
            return None

    def requeue(self, job_id: uuid.UUID) -> Job:
        """Reset a ``running`` job to ``queued`` for a fresh claim (D-S5).

        Clears ``worker_id``/``started_at``/``progress`` and increments
        ``requeue_count`` (so a crash-requeue loop is visible); ``cancel_requested``
        is left intact so a cancel requested before a crash still applies once the
        requeued job is claimed and checked again. Rejects (raises
        :class:`~auto_reel_ng.errors.IllegalJobTransitionError`) a job that is not
        currently ``running`` — the row is left unchanged.
        """
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id)
            if job is None or job.status != JobStatus.RUNNING:
                found = job.status.value if job is not None else "missing"
                raise IllegalJobTransitionError(
                    f"cannot requeue job {job_id}: job is not running (status={found})"
                )
            job.status = JobStatus.QUEUED
            job.worker_id = None
            job.started_at = None
            job.progress = 0.0
            job.requeue_count += 1
            session.flush()
            session.refresh(job)
            return job

    def find_orphaned_running(
        self,
        *,
        live_workers: Optional[Iterable[str]] = None,
        cutoff: Optional[datetime] = None,
    ) -> list[Job]:
        """Return ``running`` jobs orphaned by a dead/restarted worker.

        A job is orphaned if its ``worker_id`` is not among ``live_workers``, or
        its ``started_at`` is older than ``cutoff`` (either or both may be given;
        a job matching either condition is returned). This is the detection query
        only — the requeue *policy* belongs to the scheduler (7b, D-P5).
        """
        if live_workers is None and cutoff is None:
            raise ValueError("find_orphaned_running requires live_workers and/or cutoff")
        with session_scope(self._session_factory) as session:
            conditions: list[ColumnElement[bool]] = []
            if live_workers is not None:
                conditions.append(Job.worker_id.notin_(list(live_workers)))
            if cutoff is not None:
                conditions.append(Job.started_at < cutoff)
            stmt = (
                select(Job)
                .where(Job.status == JobStatus.RUNNING)
                .where(or_(*conditions))
                .order_by(Job.created_at.asc())
            )
            return list(session.execute(stmt).scalars().all())
