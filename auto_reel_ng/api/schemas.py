"""Pydantic response schemas (task 2.1): mirror what ``scan``/``jobs`` print, no new semantics.

These are read models only — the API never accepts a body that mutates
``reel.yaml`` (events reads are read-only, D-7) or writes a job's ``status``
(D-A6). Field names intentionally match the CLI's own vocabulary (``event_dir``,
``status``, ``progress``, ...) so a client that has read the CLI output already
recognizes the shape.
"""

from __future__ import annotations

import uuid

# Aliased: a field named ``date`` below would otherwise shadow this type name
# during pydantic's postponed-annotation resolution (``Optional[date]`` would
# resolve to the field's own class attribute instead of the stdlib type).
from datetime import date as DateValue
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ClipOut(BaseModel):
    """One clip identity and its reconcile status within a chapter."""

    identity: str
    status: str  # ClipStatus.value: new / active / missing / ignored


class ChapterOut(BaseModel):
    """One chapter: its name (``""`` is the default/root chapter) and ordered clips."""

    name: str
    clips: List[ClipOut] = []


class JobSummaryOut(BaseModel):
    """The latest job for an event, as embedded in the events list (D-A3)."""

    id: uuid.UUID
    status: str
    progress: float
    created_at: datetime


class EventSummaryOut(BaseModel):
    """One event as listed by ``GET /api/v1/events``."""

    event_id: str
    title: Optional[str] = None
    date: Optional[DateValue] = None
    location: Optional[str] = None
    clip_count: int
    new_count: int
    missing_count: int
    latest_job: Optional[JobSummaryOut] = None


class EventDetailOut(BaseModel):
    """One event's full detail: metadata, ordered chapters/clips, reconcile state."""

    event_id: str
    title: Optional[str] = None
    date: Optional[DateValue] = None
    location: Optional[str] = None
    description: Optional[str] = None
    chapters: List[ChapterOut] = []
    missing: List[str] = []
    latest_job: Optional[JobSummaryOut] = None


class SegmentOut(BaseModel):
    """One detected segment (black/white/freeze span) for a clip."""

    start: float
    end: float
    kind: str
    confidence: float


class AnalysisOut(BaseModel):
    """An event's cached analysis (D-A3 open question: raw sidecar segments, per clip).

    ``analyzed`` distinguishes "never analyzed" (``False``, ``segments`` empty)
    from "analyzed, found nothing" (``True``, ``segments`` empty) — the sidecar
    cache is per-clip, so this is true when at least one clip has a cache entry.
    """

    analyzed: bool
    segments: dict[str, List[SegmentOut]] = {}


class JobOut(BaseModel):
    """One job's full detail, mirroring ``jobs show`` (task 3.2)."""

    id: uuid.UUID
    status: str
    event_dir: str
    project_root: Optional[str] = None
    device: str
    progress: float
    worker_id: Optional[str] = None
    cancel_requested: bool
    requeue_count: int
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class EnqueueRequest(BaseModel):
    """The body of ``POST /api/v1/jobs``."""

    event_id: str
    device: str = "auto"


class CancelResult(BaseModel):
    """The body of ``POST /api/v1/jobs/{id}/cancel`` (D-S6 tri-state, task 3.3)."""

    id: uuid.UUID
    status: str
    outcome: str  # "flagged-running" / "canceled-queued" / "no-op-terminal"


class WsMessage(BaseModel):
    """One frame on ``WS /api/v1/ws/jobs`` (D-A4): a snapshot or a delta batch."""

    type: str  # "snapshot" | "delta"
    jobs: List[JobOut] = []


__all__ = [
    "ClipOut",
    "ChapterOut",
    "JobSummaryOut",
    "EventSummaryOut",
    "EventDetailOut",
    "SegmentOut",
    "AnalysisOut",
    "JobOut",
    "EnqueueRequest",
    "CancelResult",
    "WsMessage",
]
