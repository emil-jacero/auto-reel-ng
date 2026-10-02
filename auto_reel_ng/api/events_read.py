"""Scan-on-request events/analysis read model (decision D-A3, tasks 2.2-2.4).

Reuses the CLI's own building blocks unchanged: the ingest layout walk, disk
scan + reconcile, the resolving loader (reel.yaml over folder name) plus the
processable-event rule, and the analysis sidecar cache reader. No
new semantics — this module only shapes the same data ``scan``/``analyze``
already compute into the API's pydantic schemas. The enqueue's output-collision
check (:func:`output_collision`) is the same kind of read: the batch commands'
rule (D-9), from ``render/``, over the served project's events. So is the
thumbnail lookup (:func:`thumbnail_source`): discovery's own listing decides which
clips have one, and ``thumbs/`` computes where it is cached (D-11).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as DateValue
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Dict, List, Mapping, Optional, Tuple

from ..analysis.cache import CACHE_SUBDIR, clip_signal, read_entry
from ..cli.adoption import REEL_FILENAME, place_disk_clips
from ..config.project import (
    ConfigError,
    ProjectConfig,
    load_project_config,
    resolve_look_defaults,
)
from ..errors import EventMetadataError, ReelError, ThumbnailError
from ..event.discovery import (
    ClipOrder,
    DiskListing,
    order_clips,
    parse_folder_name,
    scan_event,
    seed_document,
)
from ..event.metadata import (
    load_event_document,
    reel_exists,
    require_processable,
    with_resolved_metadata,
)
from ..event.reconcile import ClipStatus, ReconcileResult, reconcile
from ..ffmpeg.runtime import FfmpegRuntime
from ..ingest import EventRef, get_layout
from ..persistence.job_store import JobStore
from ..persistence.models import Job
from ..reel import ReelDocument, is_excluded, load_document
from ..render import output_relpath
from ..render.claims import output_collision as engine_output_collision
from ..staleness.fingerprint import compute_fingerprint
from ..staleness.gate import evaluate
from ..thumbs import (
    ThumbnailSettings,
    recorded_duration,
    resolve_thumbnail_settings,
    thumbnail_path,
)
from .schemas import (
    AnalysisOut,
    ChapterOut,
    ClipOut,
    EventDetailOut,
    EventErrorOut,
    EventFailure,
    EventRowOut,
    EventSummaryOut,
    JobSummaryOut,
    SegmentOut,
    StalenessOut,
)
from .settings import ApiSettings

logger = logging.getLogger(__name__)


class EventNotFoundError(Exception):
    """``event_id`` does not resolve to an existing directory under the project root."""

    def __init__(self, event_id: str) -> None:
        super().__init__(f"no event directory for id {event_id!r}")
        self.event_id = event_id


class EventReadError(Exception):
    """An event could not be read: its ``reel.yaml``, its metadata, or its files.

    ``failure`` is the kind :func:`classify_event_failure` gives it, set by the
    detail and editorial reads so their 502 names the same kind the list's error
    row would. (D-A6: loud, never fabricated.)
    """

    def __init__(self, event_id: str, detail: str, failure: Optional[EventFailure] = None) -> None:
        super().__init__(detail)
        self.event_id = event_id
        self.detail = detail
        self.failure = failure


class ClipNotFoundError(Exception):
    """``clip`` is not one of the clips discovery lists on disk for the event.

    A MISSING clip, a file under ``original/``, and any identity naming something
    outside the event are all simply not in the listing.
    """

    def __init__(self, event_id: str, clip: str) -> None:
        super().__init__(f"no clip {clip!r} on disk in event {event_id!r}")
        self.event_id = event_id
        self.clip = clip


def event_id_for(settings: ApiSettings, event_dir: Path) -> str:
    """The root-relative, URL-safe identity for ``event_dir`` (D-A2)."""
    return event_dir.relative_to(settings.project_root).as_posix()


def resolve_event_dir(settings: ApiSettings, event_id: str) -> Path:
    """Root-relative ``event_id`` -> an existing directory under the project root.

    Rejects any id that escapes ``project_root`` (``..`` traversal) the same way
    an unknown directory is rejected: :class:`EventNotFoundError`.
    """
    root = settings.project_root.resolve()
    try:
        candidate = (root / event_id).resolve()
        candidate.relative_to(root)
    except ValueError:  # outside the root, or not a path at all (an embedded NUL byte)
        raise EventNotFoundError(event_id) from None
    if not candidate.is_dir():
        raise EventNotFoundError(event_id)
    return candidate


def named_event_dir(settings: ApiSettings, event_id: str) -> Path:
    """The event directory exactly as ``event_id`` spells it: ``project_root / event_id``.

    A job stores the id verbatim and the worker renders ``project_root / event_dir``,
    so an enqueue judges this path — its folder name, its ``reel.yaml`` — never the
    folder a symlink resolves to: an in-project symlinked event is an event of its own,
    as the layout walk and the CLI's batch commands see it. :func:`resolve_event_dir`
    still decides whether the id names a directory inside the root, and the spelled
    path must be one too (a ``..`` through a missing folder resolves lexically, but no
    worker could open it): otherwise :class:`EventNotFoundError`.
    """
    resolve_event_dir(settings, event_id)
    event_dir = settings.project_root / event_id
    if not event_dir.is_dir():
        raise EventNotFoundError(event_id)
    return event_dir


def listed_event_dir(settings: ApiSettings, event_id: str) -> Path:
    """The event directory ``event_id`` names, only when the events list shows that id.

    The configured layout decides what an event is, exactly as ``GET /api/v1/events``
    lists them: the project root, a year folder, an event's ``original/`` or chapter
    folder and a ``.reelignore``d event are directories but not events, so each is
    :class:`EventNotFoundError`, as an unknown id is. The walk is narrowed to the id's
    first folder under the walk root (the year of ``year-event``; ``flat`` ignores the
    hint), so only that year's events are yielded; ``year-event`` still lists every year
    folder to recognise aliases, but an unreadable other year is skipped, not fatal. A
    walk that fails on the id's own folder raises its ``OSError``, and an unknown layout
    its ``LayoutError``.
    """
    event_dir = named_event_dir(settings, event_id)
    try:
        first = event_dir.relative_to(settings.walk_root).parts[0]
    except (ValueError, IndexError):  # outside the walked tree, or the walk root itself
        raise EventNotFoundError(event_id) from None
    layout = get_layout(settings.layout_name)
    refs = layout(settings.walk_root, years=[first])
    if any(event_id_for(settings, ref.event_dir) == event_id for ref in refs):
        return event_dir
    raise EventNotFoundError(event_id)


def _list_event_refs(settings: ApiSettings) -> List[EventRef]:
    """Walk the configured layout from ``settings.walk_root`` (reuses the CLI's scan path)."""
    layout = get_layout(settings.layout_name)
    return list(layout(settings.walk_root))


def _load_for_reconcile(
    event_dir: Path, order: ClipOrder
) -> tuple[Optional[ReelDocument], DiskListing, ReconcileResult]:
    """Load the document (if any) + disk listing and reconcile them (as ``scan`` does).

    The returned document has resolved metadata (reel.yaml over folder name), and
    is ``None`` when no ``reel.yaml`` exists yet. The engine's own errors propagate:
    an unparseable document is a :class:`ReelParseError`, an event without a real
    date and title an :class:`EventMetadataError`, an unlistable directory an
    ``OSError``. Each caller maps them — the list to an error row, the detail to
    an :class:`EventReadError`.
    """
    document, seeded = load_event_document(event_dir, order=order)
    require_processable(event_dir, document.metadata, today=DateValue.today())
    persisted = None if seeded else document
    listing = scan_event(event_dir)
    result = reconcile(listing.identities, persisted)
    return persisted, listing, result


def _job_summary(job: Optional[Job]) -> Optional[JobSummaryOut]:
    if job is None:
        return None
    return JobSummaryOut(
        id=job.id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        cancel_requested=job.cancel_requested,
        requeue_count=job.requeue_count,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _title_date_location(
    event_dir: Path, document: Optional[ReelDocument]
) -> tuple[Optional[str], Optional[DateValue], Optional[str]]:
    """Title/date/location: the resolved document's, else the folder name's (the seed)."""
    if document is not None:
        return document.metadata.title, document.metadata.date, document.metadata.location
    parsed = parse_folder_name(event_dir.name)
    return parsed.title, parsed.date, parsed.location


def list_events(
    settings: ApiSettings, job_store: JobStore, runtime: FfmpegRuntime
) -> List[EventRowOut]:
    """``GET /api/v1/events``: every event under the configured root, freshly scanned.

    Each event carries the staleness verdict from the same gate the detail path
    uses, so one request answers "which of these need a render?". The project look
    defaults are resolved **once** here, before the loop, because they are a
    per-request value identical for every row.

    Per-event isolation (Principle I): an event that cannot be read becomes an
    :class:`EventErrorOut` row in place of its summary, and every other event is
    listed as usual. The walk, the job store and the project config are read
    before the loop, so their failures still fail the whole list.
    """
    refs = _list_event_refs(settings)
    latest_jobs = job_store.latest_by_project(str(settings.project_root))
    look_defaults = project_look_defaults(settings)

    rows: List[EventRowOut] = []
    for ref in refs:
        event_id = event_id_for(settings, ref.event_dir)
        try:
            rows.append(
                _event_summary(
                    settings,
                    ref.event_dir,
                    event_id,
                    latest_jobs=latest_jobs,
                    runtime=runtime,
                    look_defaults=look_defaults,
                )
            )
        except (ReelError, OSError) as exc:
            failure = classify_event_failure(exc)
            assert failure is not None  # nosec B101 - both caught types are always classified
            rows.append(_event_error(event_id, failure, exc))
    return rows


def classify_event_failure(exc: BaseException) -> Optional[EventFailure]:
    """The API's kind for a per-event engine failure, or ``None`` when it is not one.

    The one rule both events reads use, so the list's error row and the detail's
    502 can never disagree about why an event cannot be read.
    """
    if isinstance(exc, EventMetadataError):  # before ReelError: it is a subclass
        return EventFailure.UNUSABLE_METADATA
    if isinstance(exc, ReelError):
        return EventFailure.UNPARSEABLE_REEL_YAML
    if isinstance(exc, OSError):
        return EventFailure.UNREADABLE_DISK
    return None


def _event_summary(
    settings: ApiSettings,
    event_dir: Path,
    event_id: str,
    *,
    latest_jobs: Mapping[str, Job],
    runtime: FfmpegRuntime,
    look_defaults: Mapping[str, object],
) -> EventSummaryOut:
    """One event's summary row; the engine's per-event errors propagate to the caller."""
    document, _listing, result = _load_for_reconcile(event_dir, settings.clip_order)
    title, event_date, location = _title_date_location(event_dir, document)
    return EventSummaryOut(
        kind="event",
        event_id=event_id,
        title=title,
        date=event_date,
        location=location,
        clip_count=len(result.classification) - len(result.ignored),
        ignored_count=len(result.ignored),
        new_count=len(result.new),
        missing_count=len(result.missing),
        blocking_missing_count=len(blocking_missing(document, result)),
        latest_job=_job_summary(latest_jobs.get(event_id)),
        staleness=staleness_for(settings, event_dir, document, runtime, look_defaults),
    )


def _event_error(event_id: str, failure: EventFailure, exc: Exception) -> EventErrorOut:
    """The error row for an event the list could not read; ``detail`` is the CLI's text."""
    logger.warning("events scan: %s: %s: %s", event_id, failure.value, exc)
    return EventErrorOut(kind="error", event_id=event_id, failure=failure, detail=str(exc))


def _file_facts(path: Path) -> Tuple[Optional[int], Optional[datetime]]:
    """``(size, mtime UTC)`` for a clip on disk; ``(None, None)`` if it is not there.

    A direct ``stat`` at the point of use rather than the staleness clip signals:
    those drop mtime entirely when hashing is on, which would make the response's
    shape depend on a staleness switch. ``OSError`` yields nulls — a clip can be
    deleted between the scan and this syscall, and null is the honest statement
    that the facts are unavailable, not a fabricated value (Principle I).
    """
    try:
        stat = path.stat()
    except OSError:
        return None, None
    return stat.st_size, datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)


def _is_excluded(document: Optional[ReelDocument], identity: str) -> bool:
    """Whether the document marks ``identity`` ``exclude: true`` (``False`` with no document)."""
    return document is not None and is_excluded(document.clips, identity)


def blocking_missing(document: Optional[ReelDocument], result: ReconcileResult) -> Tuple[str, ...]:
    """The missing clips a render needs: listed, absent from disk, and not excluded.

    The one definition the events reads share (and ``POST /jobs`` can reuse): an
    excluded clip is never probed, so its absence cannot fail a render. In
    ``result.missing`` order; empty when there is no document (nothing is listed, so
    nothing is missing). A read-model projection of two engine facts, never a probe.
    """
    return tuple(i for i in result.missing if not _is_excluded(document, i))


def played_missing_clips(event_dir: Path, document: ReelDocument) -> List[str]:
    """:func:`blocking_missing` for ``document`` against ``event_dir``'s listing, sorted.

    What ``POST /jobs`` refuses an event for: a clip the render would probe that is not
    on disk. A seeded document (no ``reel.yaml``) lists exactly what the listing holds,
    so it can never be missing. The listing's ``OSError`` propagates: an unlistable
    folder is never read as "nothing missing" (Principle I).
    """
    return list(blocking_missing(document, reconcile(scan_event(event_dir).identities, document)))


def _recorded_duration(path: Path, thumbnails: Optional[ThumbnailSettings]) -> Optional[float]:
    """The duration the thumbnail operation recorded for the clip at ``path``, else ``None``.

    Reads the sidecar beside the clip's cached thumbnail (``thumbs.recorded_duration``) and
    nothing else: no ffprobe, no ffmpeg, no cache write. The cache key covers the file's name,
    size and mtime, so a replaced file has no entry until its thumbnail is made again. ``None``
    (unknown, never zero) also covers a clip that cannot be statted for the key and the
    ``thumbnails`` settings being unresolved (``thumbnails`` is ``None``).
    """
    if thumbnails is None:
        return None
    try:
        target = thumbnail_path(path, position=thumbnails.position, cache_dir=thumbnails.cache_dir)
    except OSError:
        return None
    return recorded_duration(target)


def _clip_out(
    event_dir: Path,
    identity: str,
    status: ClipStatus,
    *,
    excluded: bool = False,
    thumbnails: Optional[ThumbnailSettings] = None,
) -> ClipOut:
    """One clip with its file facts and recorded duration; a MISSING clip is not statted."""
    if status is ClipStatus.MISSING:
        return ClipOut(identity=identity, status=status, excluded=excluded)
    # The identity *is* the event-relative POSIX path (the mapping render/ uses),
    # so a clip in a named chapter subdirectory resolves inside that directory.
    path = event_dir / identity
    size, mtime = _file_facts(path)
    return ClipOut(
        identity=identity,
        status=status,
        size=size,
        mtime=mtime,
        duration=_recorded_duration(path, thumbnails),
        excluded=excluded,
    )


def _thumbnail_settings(
    settings: ApiSettings, config: ProjectConfig
) -> Optional[ThumbnailSettings]:
    """The resolved ``thumbnails`` settings, or ``None`` (one warning) when they are unusable.

    The detail's durations are a hint, so a ``thumbnails`` section the thumbnail endpoint
    refuses leaves them unknown instead of failing the response; the endpoint still fails
    loud on the same configuration.
    """
    try:
        return resolve_thumbnail_settings(config, settings.project_root)
    except ConfigError as exc:
        logger.warning("clip durations unknown: %s", exc)
        return None


def _build_chapters(
    document: Optional[ReelDocument],
    listing: DiskListing,
    result: ReconcileResult,
    event_dir: Path,
    order: ClipOrder,
    thumbnails: Optional[ThumbnailSettings] = None,
) -> List[ChapterOut]:
    """Ordered chapters/clips (D-A3): the document's structure when one exists,

    with every disk clip the document does not list (NEW or IGNORED) placed where a
    render adopts it (D-12, :func:`~auto_reel_ng.cli.adoption.place_disk_clips`):
    its folder's chapter when the document names it, else the default chapter, or
    the seed's chapters when the document names none; after the chapter's listed
    clips, in the document's own ``sort`` when it sets one, else the project's sort
    rule ``order``. The disk listing's own grouping when there is no document yet
    (the seeding case). Nothing is adopted or written here.
    Each clip carries the file facts ``_clip_out`` stats and the duration it reads from the
    thumbnail cache's sidecar under ``thumbnails`` — never a probe.
    """
    if document is None:
        return [
            ChapterOut(
                name=name,
                clips=[
                    _clip_out(event_dir, i, ClipStatus.NEW, thumbnails=thumbnails)
                    for i in order_clips(identities, event_dir, order)
                ],
            )
            for name, identities in listing.by_chapter
        ]

    chapters: List[ChapterOut] = []
    seen: set[str] = set()
    for chapter in document.chapters:
        clips = []
        for ref in chapter.clips:
            seen.add(ref.identity)
            status = result.classification.get(ref.identity, ClipStatus.MISSING)
            clips.append(
                _clip_out(
                    event_dir,
                    ref.identity,
                    status,
                    excluded=_is_excluded(document, ref.identity),
                    thumbnails=thumbnails,
                )
            )
        chapters.append(ChapterOut(name=chapter.name, clips=clips))

    by_name = {chapter.name: chapter for chapter in chapters}
    disk_only = [identity for identity in listing.identities if identity not in seen]
    for name, identities in place_disk_clips(
        document, listing, disk_only, event_dir=event_dir, order=order
    ):
        clips = [
            _clip_out(
                event_dir, i, result.classification.get(i, ClipStatus.NEW), thumbnails=thumbnails
            )
            for i in identities
        ]
        if name in by_name:
            by_name[name].clips.extend(clips)
        else:
            new_chapter = ChapterOut(name=name, clips=clips)
            chapters.append(new_chapter)
            by_name[name] = new_chapter
    return chapters


def project_look_defaults(settings: ApiSettings) -> Mapping[str, object]:
    """The resolved project look defaults (D-2) — a **per-request** value.

    Read from disk on every call: no cache, no ``app.state`` copy, because a
    ``config.yaml`` edit must be visible on the next request (D-A3). Callers
    resolve it once per request and pass it to :func:`staleness_for`, so a list
    over N events parses ``config.yaml`` once rather than N times.
    """
    return resolve_look_defaults(load_project_config(settings.project_root))


def staleness_for(
    settings: ApiSettings,
    event_dir: Path,
    document: Optional[ReelDocument],
    runtime: FfmpegRuntime,
    look_defaults: Mapping[str, object],
) -> StalenessOut:
    """The event's staleness verdict (change-detection, §8.14): read-only, never writes.

    Uses ``document`` if it was already loaded, else the folder-seed equivalent
    (never adopted, never persisted — a GET must not write, D-7), with its metadata
    resolved against the folder name exactly as ``render`` resolves it. Public: also
    used by the editorial-write route to echo the post-save verdict inline, where
    the document is the one as authored.

    ``look_defaults`` is the caller's already-resolved per-request value
    (:func:`project_look_defaults`) — a required parameter rather than something
    resolved here, so a per-event loop cannot re-parse ``config.yaml`` per event.
    The clip-set component stays on its default content-free path: the API never
    passes ``use_hash``, so no clip's bytes are read to answer a read request.
    """
    fp_document = with_resolved_metadata(
        document if document is not None else seed_document(event_dir, order=settings.clip_order),
        event_dir,
    )
    fingerprint = compute_fingerprint(
        fp_document,
        event_dir=event_dir,
        look_defaults=look_defaults,
        ffmpeg_version=runtime.version,
    )
    output_path = settings.output_dir / output_relpath(fp_document.metadata)
    verdict = evaluate(event_dir, output_path, fingerprint)
    return StalenessOut(
        stale=verdict.stale,
        reasons=list(verdict.reasons),
        renamed_from=verdict.renamed_from,
        output_name=verdict.output_name,
    )


def get_event(
    settings: ApiSettings, event_id: str, job_store: JobStore, runtime: FfmpegRuntime
) -> EventDetailOut:
    """``GET /api/v1/events/{event_id}``: current detail, parsed fresh from disk.

    The event's own failures are classified by the list's rule
    (:func:`classify_event_failure`) into an :class:`EventReadError`. An unknown ID
    is resolved first, so it stays :class:`EventNotFoundError`; the job store and
    the project config are read outside the catch, as the list reads them before
    its loop, so neither is ever reported as this event's failure.

    ``config.yaml`` is read once per request (D-A3), for the look defaults and for
    the sort rule: the chapters place the clips a render will adopt in the order
    that render uses, and the worker re-reads ``config.yaml`` for every job (D-12),
    so a ``sort`` edit shows on the next request, not after a restart.
    """
    event_dir = resolve_event_dir(settings, event_id)
    config = load_project_config(settings.project_root)
    look_defaults = resolve_look_defaults(config)
    try:
        document, listing, result = _load_for_reconcile(event_dir, config.sort)
        title, event_date, location = _title_date_location(event_dir, document)
        chapters = _build_chapters(
            document, listing, result, event_dir, config.sort, _thumbnail_settings(settings, config)
        )
        staleness = staleness_for(settings, event_dir, document, runtime, look_defaults)
    except (ReelError, OSError) as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc
    latest_jobs = job_store.latest_by_project(str(settings.project_root))

    return EventDetailOut(
        event_id=event_id,
        title=title,
        date=event_date,
        location=location,
        description=document.metadata.description if document is not None else None,
        chapters=chapters,
        missing=list(result.missing),
        blocking_missing=list(blocking_missing(document, result)),
        latest_job=_job_summary(latest_jobs.get(event_id)),
        staleness=staleness,
    )


def get_reel(settings: ApiSettings, event_id: str) -> ReelDocument:
    """``GET /api/v1/events/{event_id}/reel``: the document as authored, parsed fresh.

    An event whose directory resolves but which has no ``reel.yaml`` yet reads as
    the empty document (D-R2), mirroring the write endpoint's own seeding — the
    read must accept exactly the set of events the write accepts. Read-only: no
    file is created and nothing is adopted. A malformed or unreadable document is
    loud (:class:`EventReadError`, classified by :func:`classify_event_failure`),
    never an empty or partial one (Principle I). An event folder that cannot be searched
    is that, too (``unreadable_disk``): only an absent ``reel.yaml`` reads as empty.
    """
    event_dir = resolve_event_dir(settings, event_id)
    reel_path = event_dir / REEL_FILENAME
    try:
        # ``reel_exists`` lets a refusal to answer through (an event folder that cannot
        # be searched), where ``Path.exists()`` reads it as "no reel.yaml" and hands a
        # client an empty document in place of the one it could not look at.
        if not reel_exists(reel_path):
            return ReelDocument()
        return load_document(reel_path)
    except (ReelError, OSError) as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc


def get_analysis(settings: ApiSettings, event_id: str) -> AnalysisOut:
    """``GET /api/v1/events/{event_id}/analysis``: cached sidecar segments only.

    Never triggers analysis. ``analyzed`` is true when at least one clip in the
    event has a valid cache entry for its current on-disk signal.

    Answers only for an id the events list shows (:func:`listed_event_dir`, else
    :class:`EventNotFoundError`), as the thumbnail and media reads do: a year folder,
    an event's ``original/`` or chapter folder and a ``.reelignore``d event are
    not events. An ``OSError`` from the walk, the scan or the signal stat is an
    :class:`EventReadError` with the list's ``unreadable_disk`` kind; an unknown
    layout raises its ``LayoutError``. ``reel.yaml`` is never read: analysis is a
    fact of the sidecar cache and the clip files.
    """
    try:
        event_dir = listed_event_dir(settings, event_id)
        listing = scan_event(event_dir)

        segments: Dict[str, List[SegmentOut]] = {}
        analyzed = (event_dir / CACHE_SUBDIR).is_dir()
        for identity in listing.identities:
            clip_path = event_dir / identity
            if not clip_path.exists():
                continue
            signal = clip_signal(clip_path)
            cached = read_entry(event_dir, identity, signal)
            if cached is not None:
                analyzed = True
                segments[identity] = [
                    SegmentOut(start=s.start, end=s.end, kind=s.kind.value, confidence=s.confidence)
                    for s in cached
                ]
    except OSError as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc
    return AnalysisOut(analyzed=analyzed, segments=segments)


def listed_clip(settings: ApiSettings, event_id: str, clip: str) -> Path:
    """``event_dir / clip`` for a clip discovery lists on disk in an event the list shows.

    The one rule for "a clip of this event" that the per-clip media reads share (the
    thumbnail and the clip media route). In this order, so each outcome has one answer:
    the id must be one the events list shows (:func:`listed_event_dir`, else
    :class:`EventNotFoundError`), and the event is listed with discovery's own rules
    (an ``OSError`` from either walk is an :class:`EventReadError` with the list's
    ``unreadable_disk`` kind); ``clip`` must be exactly one of the listed identities —
    no path or Unicode normalization, so nothing from the request is joined onto a
    path before it matched (:class:`ClipNotFoundError`). ``reel.yaml`` is never read:
    a clip is a fact of the disk, not of the document. An unknown layout raises its
    ``LayoutError``.
    """
    try:
        event_dir = listed_event_dir(settings, event_id)
        listing = scan_event(event_dir)
    except OSError as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc
    if clip not in listing.identities:
        raise ClipNotFoundError(event_id, clip)
    return event_dir / clip


@dataclass(frozen=True)
class ThumbnailSource:
    """A listed clip and where its thumbnail is cached, as the thumbnail route serves it."""

    #: ``event_dir / clip``, for a clip the event's disk listing holds.
    clip_path: Path
    #: ``ThumbnailSettings.position``, resolved on this request.
    position: float
    #: ``ThumbnailSettings.cache_dir``, resolved on this request.
    cache_dir: Path
    #: ``<cache_dir>/<key>.jpg`` as ``thumbs.thumbnail_path`` computes it: nothing generated.
    cache_path: Path

    @property
    def etag(self) -> str:
        """The cache key, quoted: a strong entity-tag of the thumbnail's bytes."""
        return f'"{self.cache_path.stem}"'


def thumbnail_source(settings: ApiSettings, event_id: str, clip: str) -> ThumbnailSource:
    """``GET /api/v1/events/{event_id}/thumbnail``: the clip to serve and its cache entry.

    Read-only, and it never runs ffmpeg or ffprobe. In this order, so each outcome
    has one answer: the clip must be one :func:`listed_clip` finds (an event the list
    shows, else :class:`EventNotFoundError`; a listing that fails, an
    :class:`EventReadError` with the list's ``unreadable_disk`` kind; an identity
    matched exactly, else :class:`ClipNotFoundError`); only then is ``config.yaml``
    read (``ConfigError``) and the cache path computed. ``reel.yaml`` is never read:
    a thumbnail is a fact of the clip file, not of the document.

    Raises:
        ThumbnailError: the listed clip can no longer be statted (it changed after
            the listing), in the wording ``thumbs.thumbnail_for`` gives that case.
    """
    clip_path = listed_clip(settings, event_id, clip)
    thumbnails = resolve_thumbnail_settings(
        load_project_config(settings.project_root), settings.project_root
    )
    try:
        cache_path = thumbnail_path(
            clip_path, position=thumbnails.position, cache_dir=thumbnails.cache_dir
        )
    except OSError as exc:
        raise ThumbnailError(
            str(clip_path), f"cannot stat the clip: {exc.strerror or exc}"
        ) from exc
    return ThumbnailSource(
        clip_path=clip_path,
        position=thumbnails.position,
        cache_dir=thumbnails.cache_dir,
        cache_path=cache_path,
    )


@dataclass(frozen=True)
class OutputCollision:
    """The named event's output path and the other events that claim it."""

    #: Relative to the output directory, as ``render.output_relpath`` gives it.
    output_path: PurePosixPath
    #: The other claimants' event ids (the ids ``GET /api/v1/events`` lists), sorted.
    claimed_by: Tuple[str, ...]


def enqueue_target(
    settings: ApiSettings, event_id: str, *, today: DateValue
) -> Tuple[Path, ReelDocument]:
    """The listed event ``event_id`` names, and its processable document (resolved metadata).

    An enqueue names an event by exactly the id the events list shows
    (:func:`listed_event_dir`), so a job's ``event_dir`` is the one id of its event. The
    document is the one the fingerprint and the output path are computed from, loaded as
    the CLI's ``_checked_document`` loads it and required processable. It does not use the
    engine's ``checked_claim`` because the failure's exception type is needed for
    :func:`classify_event_failure`; the collision check reads the event itself.

    Raises :class:`EventNotFoundError` for an id the list does not show; the lookup's own
    ``OSError`` / ``LayoutError`` when the walk fails (the caller's scan-failure 502, which
    names no event); and :class:`EventReadError` when the event itself cannot be processed,
    carrying the kind :func:`classify_event_failure` gives it (the events list's error row).
    """
    event_dir = listed_event_dir(settings, event_id)
    try:
        document, _seeded = load_event_document(event_dir, order=settings.clip_order)
        require_processable(event_dir, document.metadata, today=today)
    # An EventMetadataError is a ReelError; ValueError is the guard ``checked_claim`` has too.
    except (ReelError, OSError, ValueError) as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc
    return event_dir, document


def output_collision(
    settings: ApiSettings, event_dir: Path, *, today: DateValue
) -> Optional[OutputCollision]:
    """The output collision ``event_dir`` is part of, over every event of the served project.

    The batch commands' rule (D-9), selected by the engine's one function
    (:func:`..render.claims.output_collision`): the claimants are the events the configured
    layout walks from the served root, the events list's rows, and a claimant that fails on
    its own claims nothing. This adapts it to the service: the project's walk root, layout
    and clip order, and the other claimants named by the ids a client links to, sorted.
    ``None`` when nothing else claims the path, or when ``event_dir`` fails on its own.

    ``event_dir`` is the event as its job names it (:func:`named_event_dir`), and every
    claimant is keyed by its own path, never the folder a symlink resolves to. The walk
    collapses symlinked aliases of one folder to a single row, so an alias that was dropped
    claims nothing and the row that was kept is named by its in-root id.

    The walk's own failure (``LayoutError``, ``OSError``) propagates: the caller must not
    enqueue an event whose collision it could not check (Principle I).
    """
    collision = engine_output_collision(
        event_dir,
        walk_root=settings.walk_root,
        layout=settings.layout_name,
        order=settings.clip_order,
        today=today,
    )
    if collision is None:
        return None
    return OutputCollision(
        output_path=collision.output_path,
        claimed_by=tuple(sorted(event_id_for(settings, other) for other in collision.claimed_by)),
    )


__all__ = [
    "EventNotFoundError",
    "EventReadError",
    "ClipNotFoundError",
    "event_id_for",
    "resolve_event_dir",
    "named_event_dir",
    "listed_event_dir",
    "list_events",
    "get_event",
    "get_reel",
    "get_analysis",
    "OutputCollision",
    "enqueue_target",
    "output_collision",
    "blocking_missing",
    "played_missing_clips",
    "listed_clip",
    "ThumbnailSource",
    "thumbnail_source",
    "classify_event_failure",
    "staleness_for",
    "project_look_defaults",
]
