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
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..persistence.models import JobStatus
from ..staleness.gate import StalenessReason


class ClipOut(BaseModel):
    """One clip: identity, reconcile status, and the file facts a reorder view needs.

    ``size`` (bytes) and ``mtime`` (timezone-aware UTC) come from the clip's own
    directory entry — **file** facts, never media facts. Nothing here is decoded or
    probed, so the detail response stays probe-free (Principle IV); duration,
    dimensions and codec belong to the analysis cache, not this shape. Both are
    ``None`` for a clip the document references but disk does not have: absence is
    reported, never fabricated as a zero or an epoch (Principle I).
    """

    identity: str
    status: str  # ClipStatus.value: new / active / missing / ignored
    size: Optional[int] = None
    mtime: Optional[datetime] = None


class ChapterOut(BaseModel):
    """One chapter: its name (``""`` is the default/root chapter) and ordered clips."""

    name: str
    clips: List[ClipOut] = []


class JobSummaryOut(BaseModel):
    """The latest job for an event, as embedded in the events list (D-A3).

    ``status`` is typed with the job store's own closed vocabulary, so the schema
    publishes the enumeration and generated clients get an exhaustive union
    (D-8, §4.10). ``JobStatus`` is a ``str`` enum: the wire values are unchanged.
    """

    id: uuid.UUID
    status: JobStatus
    progress: float
    created_at: datetime


class StalenessOut(BaseModel):
    """An event's staleness verdict: fresh, or stale with the changed components.

    ``reasons`` is typed with the gate's own closed vocabulary rather than
    ``List[str]``, so the OpenAPI schema publishes the enumeration and the
    generated client types get an exhaustive union: renaming a reason in the
    engine becomes a client build error instead of a silent runtime change
    (D-8, §4.10). The wire values are the gate's strings, unchanged.
    """

    stale: bool
    reasons: List[StalenessReason] = []


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
    #: The same verdict shape the detail response carries, so one list request
    #: answers "which of these need a render?" without a per-event follow-up.
    #: Derived from disk on every request — never read from or written to the DB,
    #: and never inferred from ``latest_job`` (a completed job is not freshness).
    staleness: StalenessOut


class EventDetailOut(BaseModel):
    """One event's full detail: metadata, ordered chapters/clips, reconcile state,
    and its staleness verdict (change-detection, §8.14)."""

    event_id: str
    title: Optional[str] = None
    date: Optional[DateValue] = None
    location: Optional[str] = None
    description: Optional[str] = None
    chapters: List[ChapterOut] = []
    missing: List[str] = []
    latest_job: Optional[JobSummaryOut] = None
    staleness: StalenessOut


class TrimBody(BaseModel):
    """One cut span (``in``/``out``/``reason``), the reel.yaml YAML vocabulary.

    ``in`` is a Python keyword, so the field is renamed and aliased for the wire.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    in_: float = Field(alias="in")
    out: float
    reason: Optional[str] = None


class ClipPropertiesBody(BaseModel):
    """Per-clip editorial properties in the ``clips`` map (editorial-write, D-E2)."""

    model_config = ConfigDict(extra="forbid")

    trims: List[TrimBody] = []
    title: Optional[bool] = None
    rotate: Optional[int] = None
    exclude: bool = False


class ChapterBody(BaseModel):
    """One chapter in an editorial write: a name and its ordered clip identities."""

    model_config = ConfigDict(extra="forbid")

    name: str
    clips: List[str] = []


class MetadataBody(BaseModel):
    """Event metadata in an editorial write."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    date: Optional[DateValue] = None
    location: Optional[str] = None
    description: Optional[str] = None


class EditorialDocumentBody(BaseModel):
    """The complete desired (request) or persisted (response) editorial state.

    A coarse whole-document shape (D-E2): the client sends every editable
    section, and the server merges it onto the event's existing structure rather
    than replacing the file (D-E1). Unknown fields are rejected (fail-loud) rather
    than silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    metadata: MetadataBody = MetadataBody()
    look: Dict[str, Any] = {}
    chapters: List[ChapterBody] = []
    clips: Dict[str, ClipPropertiesBody] = {}
    ignore: List[str] = []


class EditorialWriteResult(BaseModel):
    """The response of ``PUT /api/v1/events/{event_id}/reel``: persisted state + verdict.

    Echoing the persisted document lets the client observe server-side
    normalization and the event's new staleness verdict without a follow-up GET
    (open question, design.md, settled here).
    """

    document: EditorialDocumentBody
    staleness: StalenessOut


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
    status: JobStatus
    event_dir: str
    project_root: Optional[str] = None
    device: str
    progress: float
    worker_id: Optional[str] = None
    cancel_requested: bool
    requeue_count: int
    force: bool = False
    fingerprint: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class EnqueueRequest(BaseModel):
    """The body of ``POST /api/v1/jobs``."""

    event_id: str
    device: str = "auto"
    force: bool = False


class FreshResult(BaseModel):
    """The body of ``POST /api/v1/jobs`` when the event is fresh and not enqueued (D-C3)."""

    event_id: str
    status: str = "fresh"
    fingerprint: str
    manifest: str


class CancelResult(BaseModel):
    """The body of ``POST /api/v1/jobs/{id}/cancel`` (D-S6 tri-state, task 3.3)."""

    id: uuid.UUID
    status: JobStatus
    outcome: str  # "flagged-running" / "canceled-queued" / "no-op-terminal"


class ProblemOut(BaseModel):
    """The shared problem body every deliberate error uses (D-A6), as published in the schema.

    Schema-only: routes still return ``problem.problem_response``'s ``JSONResponse``,
    which FastAPI does not validate against this model. ``extra="allow"`` keeps
    route-specific fields (e.g. a 409's existing job ``id``) legal without this
    model enumerating them; the named optional fields are the ones clients branch on.
    """

    model_config = ConfigDict(extra="allow")

    title: str
    status: int
    detail: str
    #: The failing dependency on a 503 (``"database"``), as ``/healthz`` reports it.
    check: Optional[str] = None
    #: The event a per-event failure is about (502/404/400 on the events routes).
    event_id: Optional[str] = None


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
    "TrimBody",
    "ClipPropertiesBody",
    "ChapterBody",
    "MetadataBody",
    "EditorialDocumentBody",
    "EditorialWriteResult",
    "SegmentOut",
    "AnalysisOut",
    "JobOut",
    "EnqueueRequest",
    "FreshResult",
    "StalenessOut",
    "CancelResult",
    "ProblemOut",
    "WsMessage",
]
