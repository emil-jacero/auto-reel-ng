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
from ..persistence.models import JobKind, JobStatus
from ..staleness.gate import StalenessReason


class ProxyState(StrEnum):
    """A clip's proxy state: a closed vocabulary the schema publishes (D-8, §4.10, D-21).

    ``absent``: no usable entry and nothing recorded (never prepared, or the file or the
    proxy version changed, which moves the cache key). ``ready``: a usable proxy, filmstrip
    and facts. ``stale``: an entry exists for the clip as it is now but cannot be used
    (damaged facts, an empty file). ``failed``: the last attempt failed and nothing usable
    exists. The wire values are the engine's :class:`~auto_reel_ng.proxies.ProxyStatus`.
    """

    ABSENT = "absent"
    READY = "ready"
    STALE = "stale"
    FAILED = "failed"


class ProxyFilmstripOut(BaseModel):
    """The filmstrip sprite's geometry, as the proxy job recorded it.

    Tile ``k`` is at column ``k % columns`` and row ``k // columns`` of the sprite, each
    ``tile_width`` by ``tile_height`` pixels; ``interval`` is the whole seconds of footage per
    tile and ``tiles`` the count.
    """

    tile_width: int
    tile_height: int
    columns: int
    tiles: int
    interval: int


class ProxyFactsOut(BaseModel):
    """The media facts the proxy job recorded for a clip, copied, never computed or defaulted.

    ``duration`` is the **source's** probed duration (seconds), not the proxy's, which can be
    a few tens of milliseconds longer. ``fps_num``/``fps_den`` are the frame rate as the exact
    fraction (30000/1001, not 29.97). ``vfr`` is ``None`` when the container gave no average
    rate to compare. ``width``/``height`` are the proxy's displayed size (sample aspect ratio
    and display rotation applied). ``rotation`` is the source's display rotation as the probe
    reported it (0 to 359), ``None`` when the source declares none; ``audio_codec`` is the
    source's, ``None`` when it has no audio.
    """

    duration: float
    fps_num: int
    fps_den: int
    vfr: Optional[bool]
    width: int
    height: int
    rotation: Optional[int]
    audio_codec: Optional[str]
    filmstrip: ProxyFilmstripOut


class ProxyOut(BaseModel):
    """A clip's proxy state, read from the proxy cache with ``stat`` and one JSON read.

    ``facts`` and ``version`` are set only when ``state`` is ``ready``: ``version`` is the
    proxy file's entity tag without quotes (``"{size:x}-{mtime_ns:x}"``), the tag the media
    routes send, so a client can put it in the media URL as ``v`` (D-15). ``reason`` is set
    only when ``failed``: one line, no server path. All three are nullable and optional.
    """

    state: ProxyState
    facts: Optional[ProxyFactsOut] = None
    version: Optional[str] = None
    reason: Optional[str] = None


class ClipOut(BaseModel):
    """One clip: identity, reconcile status, and the file facts a reorder view needs.

    ``size`` (bytes) and ``mtime`` (timezone-aware UTC) come from the clip's own
    directory entry — **file** facts, never media facts. Nothing here is decoded or
    probed, so the detail response stays probe-free (Principle IV); dimensions and codec
    belong to the analysis cache, not this shape. Both are ``None`` for a clip the
    document references but disk does not have: absence is reported, never fabricated as
    a zero or an epoch (Principle I).

    ``duration`` (seconds) is the first media fact, and it is **not probed here**: it is the
    number the thumbnail operation measured for this exact file (name, size, mtime), read
    from the thumbnail cache's sidecar. ``None`` means unknown — a missing clip, a
    thumbnail not yet made for the file as it is now, an unusable sidecar or
    ``thumbnails`` configuration — never zero or a guess. It is the probe's number, so a
    browser may read a few tens of milliseconds more from the same file.

    ``proxy`` is the second media-fact exception, again **not probed here**: it is the state
    of the clip's proxy in the proxy cache (D-21) and, when ``ready``, the facts the proxy job
    recorded (see :class:`ProxyOut`). ``None`` means unknown — never ``absent`` — for a
    missing clip and for every clip when the ``proxies`` configuration or the cache cannot be
    read. ``proxy.facts.duration`` is the proxy job's number and is independent of
    ``duration`` above (the thumbnail sidecar's), which is unchanged.

    ``status`` is typed with reconcile's own closed vocabulary, so the schema
    publishes the enumeration and generated clients get an exhaustive union
    (D-8, §4.10). ``ClipStatus`` is a ``StrEnum``: the wire values are unchanged.

    ``excluded`` is a flag **beside** ``status``, not a member of it: it is true when the
    document's ``clips`` map marks the identity ``exclude: true``, so a render drops the
    clip from the movie without probing it. An excluded clip reports its own status (an
    excluded clip whose file is gone is ``missing`` and ``excluded``). It is false for a
    NEW or IGNORED clip (the document holds no properties for a clip no chapter lists)
    and for every clip of an event without a ``reel.yaml``.
    """

    identity: str
    status: ClipStatus
    size: Optional[int] = None
    mtime: Optional[datetime] = None
    duration: Optional[float] = None
    proxy: Optional[ProxyOut] = None
    excluded: bool = False


class TitleCardsOut(BaseModel):
    """Whether a render draws title cards, and which layer decided it (D-25).

    ``source`` is ``event`` (the event's ``look.decorators``), ``project`` (the ``config.yaml``
    one) or ``default`` (neither sets it: the effective decorators are ``[title]``).
    """

    enabled: bool
    source: Literal["event", "project", "default"]


class TitleStyleOut(BaseModel):
    """The title-card style the engine resolves: the layers' result, never a null.

    The project ``config.yaml`` ``look``, then the event's ``look.title_card``, then (for a
    chapter's :class:`ResolvedCardOut`) the chapter's own overrides, resolved by the engine's
    own function. ``background`` is ``black`` or ``video``; ``position`` is ``center``, ``top``
    or ``bottom``; ``font_family`` is a family of ``GET /api/v1/fonts``.
    """

    duration: float
    background: str
    font_family: str
    title_font_size: int
    subtitle_font_size: int
    text_color: str
    position: str


class ResolvedCardOut(TitleStyleOut):
    """What a render draws for one chapter's card: its text and its effective style.

    ``title`` is the chapter's override, else the chapter name (the event title for the default
    chapter); ``subtitle`` is the effective one: the override when the card has the key (``""``
    included), else ``default_subtitle`` - the opening card's date and place text (possibly
    empty), and ``""`` for any other chapter.
    """

    title: str
    subtitle: str
    default_subtitle: str


class ChapterOut(BaseModel):
    """One chapter: its name (``""`` is the default/root chapter), ordered clips and card.

    ``card`` is the resolved title card, or ``null`` when it cannot be resolved (then
    ``card_error`` says why: the event-wide style, or this chapter's own card).
    """

    name: str
    clips: List[ClipOut] = []
    card: Optional[ResolvedCardOut] = None
    card_error: Optional[str] = None


class JobSummaryOut(BaseModel):
    """The latest job for an event, as embedded in the events list and detail (D-A3).

    A projection of the job's detail (``JobOut``): every field here has the same value,
    meaning and schema definition there. ``started_at``/``finished_at`` are null until the
    store stamps them (a claim; a terminal transition), never substituted.

    ``cancel_requested`` and ``requeue_count`` are required (never null in the store) so a
    reader can tell a cancel pending and a job that went back to the queue after a claim
    from a read alone; a requeue leaves ``cancel_requested`` as it was.

    ``status`` is typed with the job store's own closed vocabulary, so the schema
    publishes the enumeration and generated clients get an exhaustive union
    (D-8, §4.10). ``JobStatus`` is a ``str`` enum: the wire values are unchanged.

    The summary is always of a ``render`` job: an event's latest job is its latest render, and a
    proxy job never stands in it. ``kind`` is still on it, with the definition ``JobOut`` has.
    """

    id: uuid.UUID
    kind: JobKind
    status: JobStatus
    progress: float
    created_at: datetime
    cancel_requested: bool
    requeue_count: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class StalenessOut(BaseModel):
    """An event's staleness verdict: fresh, or stale with the changed components.

    ``reasons`` is typed with the gate's own closed vocabulary rather than
    ``List[str]``, so the OpenAPI schema publishes the enumeration and the
    generated client types get an exhaustive union: renaming a reason in the
    engine becomes a client build error instead of a silent runtime change
    (D-8, §4.10). The wire values are the gate's strings, unchanged.

    ``renamed_from`` and ``output_name`` are the gate's own: the bare names of the movie
    the last render wrote (still on disk) and of the one the next render writes. Both are
    set exactly when ``output_renamed`` is among ``reasons`` and null otherwise; they are
    always present on the wire.
    """

    stale: bool
    reasons: List[StalenessReason] = []
    renamed_from: Optional[str] = None
    output_name: Optional[str] = None


class EventSummaryOut(BaseModel):
    """One event as listed by ``GET /api/v1/events``.

    ``clip_count`` is the clips the event lists that are not ignored (ACTIVE, NEW and
    MISSING), the number the event's detail page counts; ``ignored_count`` is the IGNORED
    ones, which ``clip_count`` leaves out. ``missing_count`` counts every missing clip;
    ``blocking_missing_count`` only those a render needs (the detail's ``blocking_missing``).
    """

    #: The list's discriminator. Declared without a default so the schema marks it
    #: required and generated clients get a non-optional ``kind: "event"``.
    kind: Literal["event"]
    event_id: str
    title: Optional[str] = None
    date: Optional[DateValue] = None
    location: Optional[str] = None
    clip_count: int
    ignored_count: int
    new_count: int
    missing_count: int
    blocking_missing_count: int
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


class MovieChapterOut(BaseModel):
    """One chapter of the rendered movie, as the render recorded it.

    ``name`` is the chapter's name in the movie (``""`` for the default chapter when it was so
    recorded); ``start`` is seconds from the beginning of the rendered movie: the recorded
    millisecond count divided by 1000, finite and not negative. Copied, never computed from the
    reel or the movie.
    """

    name: str
    start: float


class MovieOut(BaseModel):
    """The rendered movie's version and chapter times, read from the render manifest.

    Probe-free: the manifest and a ``stat`` are the only reads. The facts describe the movie
    **on disk**, the last render's, not the current editorial state (the staleness verdict says
    whether it is outdated).

    ``recorded_at`` is when the render record was written (timezone-aware UTC): the engine writes
    it only after the atomic finalize verified the movie, so for a render it is when the render
    finished; for a movie ``adopt-renders`` recorded it is when it was adopted. It is not the
    file's modification time. ``fingerprint`` is the first 12 hexadecimal characters of the
    manifest's combined fingerprint: the identity of the **inputs** the render was made from, not
    a hash of the movie's bytes (two renders of identical inputs share it). Together they are
    the movie's version.

    ``chapters`` is the recorded chapter list, in recorded order. ``None`` means unknown: the
    manifest records no chapter times (written before they were recorded, or adopted rather than
    rendered) or its list is unreadable. It is never ``[]`` for unknown; a recorded empty list is
    reported as empty.
    """

    recorded_at: datetime
    fingerprint: str
    chapters: Optional[List[MovieChapterOut]] = None


class PosterSource(StrEnum):
    """Where the effective poster comes from: the document's choice or the default frame."""

    EVENT = "event"
    DEFAULT = "default"


class PosterOut(BaseModel):
    """The event's effective poster, as the engine's rules give it, probe-free.

    ``source`` is ``event`` when ``reel.yaml`` names a clip the movie plays (then ``clip`` and
    ``at``, seconds into that clip before its cuts, are its values) and ``default`` otherwise
    (then ``clip`` is the first played clip and ``at`` is ``null``: the default frame's time
    depends on a duration this read does not probe).
    """

    clip: str
    at: Optional[float] = None
    source: PosterSource


class EventDetailOut(BaseModel):
    """One event's full detail: metadata, ordered chapters/clips, reconcile state,
    and its staleness verdict (change-detection, §8.14).

    ``missing`` lists every clip the document lists that disk does not have, excluded or
    not. ``blocking_missing`` is the subset a render needs: the missing clips the document
    does not exclude (an excluded clip is never probed, so its absence cannot fail a
    render).

    ``movie`` is ``None`` when the event has no rendered movie, by the rule
    ``GET …/movie`` uses (see :class:`MovieOut` for what it holds). It is always present on
    the wire, and the events list does not carry it.

    ``title_card`` is the event's resolved card style (the event-wide layer, before any
    chapter's overrides) and each chapter's ``card`` the card a render would draw. When the
    event-wide ``look.title_card`` cannot be resolved, ``title_card`` and every ``card`` are
    ``null`` and ``title_card_error`` names the field; the rest of the detail is unaffected.

    ``title_cards`` is whether the effective decorators include ``title`` and where that was
    decided; it is present unless ``look.decorators`` is not a list, when it is ``null`` and
    ``title_cards_error`` names the field.

    ``poster`` is the effective poster (see :class:`PosterOut`), ``null`` when no clip is played;
    ``poster_note`` says why a poster ``reel.yaml`` names is not used (its clip is missing,
    ignored or excluded), else ``null``. A poster the loader refuses is the event's failure.
    """

    event_id: str
    title: Optional[str] = None
    date: Optional[DateValue] = None
    location: Optional[str] = None
    description: Optional[str] = None
    chapters: List[ChapterOut] = []
    missing: List[str] = []
    blocking_missing: List[str] = []
    latest_job: Optional[JobSummaryOut] = None
    staleness: StalenessOut
    movie: Optional[MovieOut] = None
    title_card: Optional[TitleStyleOut] = None
    title_card_error: Optional[str] = None
    title_cards: Optional[TitleCardsOut] = None
    title_cards_error: Optional[str] = None
    poster: Optional[PosterOut] = None
    poster_note: Optional[str] = None


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


class CardBody(BaseModel):
    """A chapter's title-card **overrides**, named as the ``reel.yaml`` ``card`` keys.

    Shape only: the key set and the JSON types. Every value rule (ranges, the ``background``
    and ``position`` vocabularies, the font registry) is the engine's and arrives as a 400
    naming the field, so no vocabulary is defined twice. ``null``/absent means "no override".
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    title: Optional[str] = None
    subtitle: Optional[str] = None
    duration: Optional[float] = None
    background: Optional[str] = None
    font_family: Optional[str] = None
    title_font_size: Optional[int] = None
    subtitle_font_size: Optional[int] = None
    text_color: Optional[str] = None
    position: Optional[str] = None


class PreviewCardBody(CardBody):
    """A draft card for the preview: the editorial card plus the preview's text bounds.

    The bounds belong to the preview only; the editorial ``card`` has no length limit of
    its own, so a longer hand-written title still round-trips.
    """

    title: Optional[str] = Field(default=None, max_length=200)
    subtitle: Optional[str] = Field(default=None, max_length=400)


class TitleCardPreviewBody(BaseModel):
    """A draft title card to draw: nothing here is saved.

    ``chapter`` is the chapter's name (``""`` for the opening card). ``style`` is an optional
    draft of the event-wide ``look.title_card`` (the event's saved one when absent) and
    ``event_title`` an optional draft of the title the opening card defaults to.
    """

    model_config = ConfigDict(extra="forbid")

    chapter: str = ""
    card: Optional[PreviewCardBody] = None
    style: Optional[Dict[str, Any]] = None
    event_title: Optional[str] = Field(default=None, max_length=200)


class FontOut(BaseModel):
    """One bundled title-card font, as the registry lists it."""

    family: str
    display_name: str
    weights: List[int]
    default: bool


class ChapterBody(BaseModel):
    """One chapter in an editorial write: a name, its ordered clip identities and its card.

    ``card`` is ``null`` for a chapter with no card entry. Written ``null`` or absent it keeps
    the card ``reel.yaml`` holds; written with no field set (``{}``) it removes it.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    clips: List[str] = []
    card: Optional[CardBody] = None


class PosterBody(BaseModel):
    """The event's chosen poster frame, named as the ``reel.yaml`` ``poster`` keys.

    Shape only: the key set and the JSON types. ``clip`` is a clip identity and ``at`` seconds into
    that clip before its cuts; the value rules are the engine's and arrive as a 400 naming
    ``poster.clip`` or ``poster.at``. Whether ``at`` is inside the clip needs a probe and is
    checked at render.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    clip: str
    at: float


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
    poster: Optional[PosterBody] = Field(
        default=None,
        description=(
            "The chosen poster frame. Absent in a write keeps the poster reel.yaml holds;"
            " `null` removes it; `{clip, at}` sets it. A document with none reads `null`."
        ),
    )


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
    """One job's full detail, mirroring ``jobs show`` (task 3.2).

    ``kind`` says what sort of work the job is (``render`` or ``proxy``), typed with the job
    store's closed vocabulary so generated clients get an exhaustive union (D-8, §4.10).
    """

    id: uuid.UUID
    kind: JobKind
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


class ProxiesFreshResult(BaseModel):
    """The body of ``POST /api/v1/events/{event_id}/proxies`` when nothing needs preparing.

    Every clip of the event already has a ``ready`` proxy, so no job was enqueued. A proxy has
    no fingerprint or manifest (it is not a staleness input), so this is not :class:`FreshResult`.
    """

    event_id: str
    #: A constant, declared without a default so the schema marks it required.
    status: Literal["fresh"]
    #: How many clips of the event folder were checked; 0 for an event with none.
    clip_count: int


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
    """Why an enqueue (``POST /api/v1/jobs``, or the proxy enqueue) refused with a 409."""

    #: An active (``queued`` or ``running``) job already exists for the event: ``job_id``.
    ACTIVE_JOB = "active_job"
    #: Another event of the project renders to the same output path: ``claimed_by``.
    OUTPUT_COLLISION = "output_collision"
    #: The event plays a clip that is absent from disk, so its render would fail at probe:
    #: ``missing``.
    MISSING_CLIPS = "missing_clips"


class ThumbnailFailure(StrEnum):
    """Why a clip's thumbnail could not be served: the API's classification of engine errors.

    A kind describes the *clip*, never the service: a thumbnail cache that cannot be
    written or an invalid ``config.yaml`` answers 502 with no kind at all.
    """

    #: The engine could not produce the clip's thumbnail (``ThumbnailError``): the clip
    #: cannot be statted or probed, has no usable duration, or gave no frame.
    THUMBNAIL_FAILED = "thumbnail_failed"


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
    #: On a ``missing_clips`` 409: the played clips absent from disk (referenced, not
    #: excluded), as sorted identities, the ones the event detail's ``blocking_missing`` lists.
    missing: Optional[List[str]] = None
    #: Why a clip's thumbnail could not be produced, on the thumbnail route's 502. A
    #: field of its own, never ``failure``: that one describes an event, not a clip.
    thumbnail_failure: Optional[ThumbnailFailure] = None


class WsMessageType(StrEnum):
    """The closed set of frame types on ``WS /api/v1/ws/jobs`` (D-A4)."""

    #: The first frame of every connection: every active job, replacing a client's state.
    SNAPSHOT = "snapshot"
    #: Every later frame: the jobs that changed since the previous poll, merged by id.
    DELTA = "delta"
    #: Sent to a connection that has been sent no frame for 15 s, with no jobs: proof of
    #: life for a client that cannot see the transport's pings. Changes nothing it shows.
    HEARTBEAT = "heartbeat"


class WsMessage(BaseModel):
    """One frame on ``WS /api/v1/ws/jobs`` (D-A4): a snapshot, a delta batch or a heartbeat.

    A WebSocket route is not an HTTP operation, so no path in the schema references
    this model: the application publishes it into the schema's components itself,
    so a client generated from the schema gets the frame's type without declaring it
    by hand (D-8, §4.10).
    """

    type: WsMessageType
    #: Always sent (a snapshot of no active jobs, and every heartbeat, is an empty list), so
    #: declared without a default: the schema marks it required and generated clients need no
    #: fallback.
    jobs: List[JobOut]


__all__ = [
    "ClipOut",
    "MovieChapterOut",
    "MovieOut",
    "ProxyState",
    "ProxyFilmstripOut",
    "ProxyFactsOut",
    "ProxyOut",
    "ChapterOut",
    "JobSummaryOut",
    "EventSummaryOut",
    "EventFailure",
    "EventErrorOut",
    "EventRowOut",
    "EventDetailOut",
    "TrimBody",
    "ClipPropertiesBody",
    "CardBody",
    "FontOut",
    "PreviewCardBody",
    "TitleCardPreviewBody",
    "ChapterBody",
    "ResolvedCardOut",
    "TitleStyleOut",
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
    "ThumbnailFailure",
    "ProblemOut",
    "WsMessageType",
    "WsMessage",
]
