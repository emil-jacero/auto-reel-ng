"""SQLAlchemy models for the persistence layer: the ``jobs`` table (D-P4).

Schema is sized for the scheduler (7b) and API (7c) so no migration churn lands
with them — see ``design.md`` D-P4. ``fingerprint`` is reserved-unused (§8.14,
parked); nothing here writes editorial state back to ``reel.yaml`` (D-7/D-P6).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, Index, Integer, String, Text, func
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
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_dir: Mapped[str] = mapped_column(Text, nullable=False)
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
