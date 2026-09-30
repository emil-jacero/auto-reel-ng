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

Two verbs report what they did instead of leaving the caller to infer it from an
earlier read (jobs-client-contract): ``submit`` says whether it created the job,
and ``cancel`` which :class:`CancelOutcome` it applied under the row's lock.
``enqueue`` and ``request_cancel`` wrap them for callers that need only what those
verbs always returned.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Iterable, Optional

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..errors import IllegalJobTransitionError
from .engine import session_scope
from .models import Job, JobStatus

_TERMINAL_STATUSES = {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED}
_ACTIVE_STATUSES = (JobStatus.QUEUED, JobStatus.RUNNING)


# Owned by the store, beside the transition that produces it (as ``JobStatus`` is), so
# the API publishes it as an enumeration instead of restating it (HLD §4.10). The
# docstring is published in the OpenAPI schema, so it speaks to a client.
class CancelOutcome(StrEnum):
    """What a cancel request did to a job (D-S6): the outcome the store applied."""

    #: A ``running`` job had ``cancel_requested`` set; the worker makes the terminal transition.
    FLAGGED_RUNNING = "flagged-running"
    #: A ``queued`` job was moved to ``canceled`` directly; no worker will claim it.
    CANCELED_QUEUED = "canceled-queued"
    #: The job was already ``done``, ``failed`` or ``canceled``; nothing changed.
    NO_OP_TERMINAL = "no-op-terminal"


@dataclass(frozen=True)
class Submission:
    """What :meth:`JobStore.submit` did: the active job's id, and whether this call created it."""

    job_id: uuid.UUID
    created: bool


@dataclass(frozen=True)
class Cancellation:
    """What :meth:`JobStore.cancel` did: the outcome it applied, and the job as it left it."""

    job: Job
    outcome: CancelOutcome


@dataclass(frozen=True)
class FinishedJobs:
    """The jobs whose terminal transition was stamped since an instant (``list_finished_since``)."""

    #: The database's ``now()`` in the read's own transaction: the caller's next ``since``.
    as_of: datetime
    #: Every job with ``finished_at >= (since or as_of) - overlap``, by ``finished_at`` ascending.
    jobs: list[Job]


class JobStore:
    """Repository over the ``jobs`` table; one instance per session factory."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def submit(
        self,
        project_root: str,
        event_dir: str,
        *,
        device: str = "auto",
        output_path: Optional[str] = None,
        force: bool = False,
        fingerprint: Optional[str] = None,
    ) -> Submission:
        """Insert a new ``queued`` job for ``event_dir`` (project-root-relative), saying if it did.

        ``force`` bypasses the staleness gate and replaces output (survives to
        claim time); ``fingerprint`` is the gate's enqueue-time value, stamped for
        observability (change-detection, §8.14) — the staleness decision itself
        belongs to the caller, not the store.

        Idempotent (D-S7/D-S8): when an active (``queued``/``running``) job already
        exists for the same ``(project_root, event_dir)``, no row is inserted and the
        existing job's id is reported with ``created=False``. The database's partial
        unique index is the source of truth for this — a concurrent submit for the
        same identity races safely against it — so the insert is attempted first and
        a unique violation falls back to looking the existing job up, rather than a
        check-then-insert with its own race window. The report is therefore the
        insertion's own verdict: of two concurrent calls, exactly one says created.
        """
        job = Job(
            project_root=project_root,
            event_dir=event_dir,
            device=device,
            output_path=output_path,
            force=force,
            fingerprint=fingerprint,
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
                return Submission(job_id=existing.id, created=False)
            return Submission(job_id=job.id, created=True)

    def enqueue(
        self,
        project_root: str,
        event_dir: str,
        *,
        device: str = "auto",
        output_path: Optional[str] = None,
        force: bool = False,
        fingerprint: Optional[str] = None,
    ) -> uuid.UUID:
        """:meth:`submit`, returning only the job's id: the new job's, or the active one's."""
        return self.submit(
            project_root,
            event_dir,
            device=device,
            output_path=output_path,
            force=force,
            fingerprint=fingerprint,
        ).job_id

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

        Used by callers that look before doing further work: the API refuses a
        duplicate before running the staleness gate, and the ``enqueue`` CLI command
        classifies its report. Being a read, it can race a concurrent insert; whether
        a call created a job is :meth:`submit`'s report, not this lookup's.
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

    def list_finished_since(self, since: Optional[datetime], *, overlap: timedelta) -> FinishedJobs:
        """The jobs whose terminal transition was stamped at or after ``since - overlap``.

        Only a terminal transition stamps ``finished_at``, so every job returned is
        ``done``/``failed``/``canceled``. ``as_of`` is the database's ``now()`` in this
        read's own transaction, and ``since=None`` means that instant. Both are
        database time — the clock that stamps ``finished_at`` — so a caller passing
        ``as_of`` back as its next ``since`` never depends on its own host's clock.
        ``now()`` is a transaction's *start*, so a terminal row can commit after a
        read whose ``as_of`` is already past its ``finished_at``: ``overlap`` re-reads
        that stretch, and the caller de-duplicates what it has seen.
        """
        with session_scope(self._session_factory) as session:
            as_of = session.execute(select(func.now())).scalar_one()  # pylint: disable=not-callable
            start = (since if since is not None else as_of) - overlap
            stmt = select(Job).where(Job.finished_at >= start).order_by(Job.finished_at.asc())
            return FinishedJobs(as_of=as_of, jobs=list(session.execute(stmt).scalars().all()))

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

    def cancel(self, job_id: uuid.UUID) -> Optional[Cancellation]:
        """Decide and apply a cancellation of ``job_id`` in one transaction (D-S6).

        The job is read ``FOR UPDATE`` — deliberately without ``SKIP LOCKED``, so a
        claim, terminal transition or requeue holding the row is waited for, and the
        branch below acts on the row's committed state rather than on a version
        another transaction is replacing:

        - ``running``: only ``cancel_requested`` is set — the worker remains the sole
          writer of ``status`` and performs the terminal transition itself once it
          next checks the flag between segments (``FLAGGED_RUNNING``);
        - ``queued``: canceled directly, as :meth:`cancel_queued` does
          (``CANCELED_QUEUED``); a ``claim_next`` meeting the lock skips the row and
          finds it ``canceled`` afterwards;
        - terminal: nothing changes (``NO_OP_TERMINAL``).

        Returns the outcome with the job as the transaction left it, or ``None`` when
        no job has ``job_id`` — a missing job is not a terminal one. An unlocked read
        here would let a cancel meeting an uncommitted claim overwrite the claim's
        ``running`` with ``canceled`` while the worker, never flagged, renders on.
        """
        with session_scope(self._session_factory) as session:
            job = session.get(Job, job_id, with_for_update=True)
            if job is None:
                return None
            if job.status == JobStatus.RUNNING:
                job.cancel_requested = True
                outcome = CancelOutcome.FLAGGED_RUNNING
            elif job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELED
                job.finished_at = func.now()  # pylint: disable=not-callable
                outcome = CancelOutcome.CANCELED_QUEUED
            else:
                return Cancellation(job=job, outcome=CancelOutcome.NO_OP_TERMINAL)
            session.flush()
            session.refresh(job)
            return Cancellation(job=job, outcome=outcome)

    def request_cancel(self, job_id: uuid.UUID) -> Optional[Job]:
        """Request cancellation of ``job_id``: :meth:`cancel`, returning only the job.

        The flagged ``running`` job or the canceled ``queued`` one; ``None`` for a
        job already in a terminal state, or missing — the contract the ``jobs
        cancel`` command has always relied on.
        """
        result = self.cancel(job_id)
        if result is None or result.outcome is CancelOutcome.NO_OP_TERMINAL:
            return None
        return result.job

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
