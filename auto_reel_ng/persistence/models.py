"""SQLAlchemy models for the persistence layer: the ``jobs`` table (D-P4).

Schema was sized for the scheduler (7b) and API (7c); 7b's job-scheduler change
(D-S6/D-S7) added ``cancel_requested``, ``project_root``, and ``requeue_count``
via an additive migration. ``fingerprint`` is reserved-unused (§8.14, parked);
nothing here writes editorial state back to ``reel.yaml`` (D-7/D-P6).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for every persistence-layer model."""


class JobStatus(str, enum.Enum):
    """The five lifecycle states a job may occupy (D-P4)."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


class Job(Base):
    """A unit of render work tracked in the durable queue (the ``jobs`` table).

    The queue *is* this table (D-P2): there is no in-memory queue or external
    broker. A worker (7b) claims rows via ``claim_next`` (race-free, ``FOR UPDATE
    SKIP LOCKED``); ``status``/``priority``/``created_at`` back that query, hence
    the composite claim-next index.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_claim_next", "status", "priority", "created_at"),
        # An event has at most one active (queued/running) job (job-scheduler): a
        # DB-level guarantee, not an application-level check, against a duplicate
        # concurrent render of the same event.
        Index(
            "ux_jobs_active_identity",
            "project_root",
            "event_dir",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_dir: Mapped[str] = mapped_column(Text, nullable=False)
    project_root: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    device: Mapped[str] = mapped_column(String, nullable=False, default="auto")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requeue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # pylint: disable=not-callable
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
