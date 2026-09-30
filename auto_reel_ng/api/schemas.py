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
from enum import StrEnum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from ..event.reconcile import ClipStatus
from ..persistence.job_store import CancelOutcome
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

    ``status`` is typed with reconcile's own closed vocabulary, so the schema
    publishes the enumeration and generated clients get an exhaustive union
    (D-8, §4.10). ``ClipStatus`` is a ``StrEnum``: the wire values are unchanged.
    """

    identity: str
    status: ClipStatus
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

    #: The list's discriminator. Declared without a default so the schema marks it
    #: required and generated clients get a non-optional ``kind: "event"``.
    kind: Literal["event"]
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


class EventFailure(StrEnum):
    """Why an event could not be listed: the API's classification of engine errors."""

    #: A ``reel.yaml`` that is malformed, fails validation, or cannot be imported.
    UNPARSEABLE_REEL_YAML = "unparseable_reel_yaml"
    #: No real date or title, or a future date (``EventMetadataError``).
    UNUSABLE_METADATA = "unusable_metadata"
    #: The event's files cannot be listed or stat'ed (``OSError``).
    UNREADABLE_DISK = "unreadable_disk"


class EventErrorOut(BaseModel):
    """An event the list could not read, in place of its summary (per-event isolation).

    Carries no clip counts, staleness or title: those are exactly what could not be
    read, and absence is reported, never faked as zero (Principle I).
    """

    kind: Literal["error"]
    event_id: str
    failure: EventFailure
    #: The engine's own message, which names the fix (the text the CLI prints).
    detail: str


#: One row of ``GET /api/v1/events``: a summary, or an error row, by ``kind``.
EventRowOut = Annotated[Union[EventSummaryOut, EventErrorOut], Field(discriminator="kind")]


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
    #: The API enqueues an event under the id the events routes use, so a client
    #: matches a job to its event by equality; the description makes that contractual.
    event_dir: str = Field(
        description=(
            "The event's id: the root-relative event directory, the same value the events"
            " routes take as {event_id} and return as event_id"
        )
    )
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
    #: A constant, declared without a default so the schema marks it required and
    #: generated clients get a non-optional ``status: "fresh"``.
    status: Literal["fresh"]
    fingerprint: str
    manifest: str


class CancelResult(BaseModel):
    """The body of ``POST /api/v1/jobs/{id}/cancel``: the outcome the store applied (D-S6).

    ``outcome`` and ``status`` come from the one transaction that applied the cancel,
    so they always agree. ``outcome`` is typed with the store's own closed vocabulary,
    so the schema publishes the enumeration and generated clients get an exhaustive
    union (D-8, §4.10); the wire values are unchanged.
    """

    id: uuid.UUID
    status: JobStatus
    outcome: CancelOutcome


class EnqueueConflict(StrEnum):
    """Why ``POST /api/v1/jobs`` refused an event with a 409: the API's classification."""

    #: An active (``queued`` or ``running``) job already exists for the event: ``job_id``.
    ACTIVE_JOB = "active_job"
    #: Another event of the project renders to the same output path: ``claimed_by``.
    OUTPUT_COLLISION = "output_collision"


class ProblemOut(BaseModel):
    """The shared problem body every deliberate error uses (D-A6), as published in the schema.

    Schema-only: routes still return ``problem.problem_response``'s ``JSONResponse``,
    which FastAPI does not validate against this model. ``extra="allow"`` keeps an
    undeclared route-specific field legal; a field clients branch on is declared
    below as a named optional field, so the generated types carry it without a cast.
    """

    model_config = ConfigDict(extra="allow")

    title: str
    status: int
    detail: str
    #: The failing dependency on a 503 (``"database"``), as ``/healthz`` reports it.
    check: Optional[str] = None
    #: The event a per-event failure is about (502/404/400 on the events routes, and
    #: the enqueue's 404 for an unknown event).
    event_id: Optional[str] = None
    #: Why the event could not be read, on the detail's 502: the list's error-row kind.
    failure: Optional[EventFailure] = None
    #: The job a jobs problem is about: the active job on the enqueue's 409, the
    #: requested id on the 404 of a job's detail or its cancel.
    job_id: Optional[uuid.UUID] = None
    #: Which conflict an enqueue's 409 is, so a client picks its reaction from the
    #: published type, never from the detail text.
    conflict: Optional[EnqueueConflict] = None
    #: On an ``output_collision``: the other events claiming the same output path, as
    #: sorted event ids (a collision can be three-way).
    claimed_by: Optional[List[str]] = None


class WsMessageType(StrEnum):
    """The closed set of frame types on ``WS /api/v1/ws/jobs`` (D-A4)."""

    #: The first frame of every connection: every active job, replacing a client's state.
    SNAPSHOT = "snapshot"
    #: Every later frame: the jobs that changed since the previous poll, merged by id.
    DELTA = "delta"


class WsMessage(BaseModel):
    """One frame on ``WS /api/v1/ws/jobs`` (D-A4): a snapshot or a delta batch.

    A WebSocket route is not an HTTP operation, so no path in the schema references
    this model: the application publishes it into the schema's components itself,
    so a client generated from the schema gets the frame's type without declaring it
    by hand (D-8, §4.10).
    """

    type: WsMessageType
    #: Always sent (a snapshot of no active jobs is an empty list), so declared without
    #: a default: the schema marks it required and generated clients need no fallback.
    jobs: List[JobOut]


__all__ = [
    "ClipOut",
    "ChapterOut",
    "JobSummaryOut",
    "EventSummaryOut",
    "EventFailure",
    "EventErrorOut",
    "EventRowOut",
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
    "EnqueueConflict",
    "ProblemOut",
    "WsMessageType",
    "WsMessage",
]
