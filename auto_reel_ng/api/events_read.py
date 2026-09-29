"""Scan-on-request events/analysis read model (decision D-A3, tasks 2.2-2.4).

Reuses the CLI's own building blocks unchanged: the ingest layout walk, disk
scan + reconcile, the resolving loader (reel.yaml over folder name) plus the
processable-event rule, and the analysis sidecar cache reader. No
new semantics — this module only shapes the same data ``scan``/``analyze``
already compute into the API's pydantic schemas.
"""

from __future__ import annotations

import logging
from datetime import date as DateValue
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from ..analysis.cache import CACHE_SUBDIR, clip_signal, read_entry
from ..cli.adoption import REEL_FILENAME
from ..config.project import load_project_config, resolve_look_defaults
from ..errors import EventMetadataError, ReelError, ReelParseError
from ..event.discovery import (
    ClipOrder,
    DiskListing,
    order_clips,
    parse_folder_name,
    scan_event,
    seed_document,
)
from ..event.metadata import load_event_document, require_processable, with_resolved_metadata
from ..event.reconcile import ClipStatus, ReconcileResult, reconcile
from ..ffmpeg.runtime import FfmpegRuntime
from ..ingest import EventRef, get_layout
from ..persistence.job_store import JobStore
from ..persistence.models import Job
from ..reel import ReelDocument, load_document
from ..render import output_relpath
from ..staleness.fingerprint import compute_fingerprint
from ..staleness.gate import evaluate
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
    detail read so its 502 names the same kind the list's error row would; the
    editorial read raises without one. (D-A6: loud, never fabricated.)
    """

    def __init__(self, event_id: str, detail: str, failure: Optional[EventFailure] = None) -> None:
        super().__init__(detail)
        self.event_id = event_id
        self.detail = detail
        self.failure = failure


def event_id_for(settings: ApiSettings, event_dir: Path) -> str:
    """The root-relative, URL-safe identity for ``event_dir`` (D-A2)."""
    return event_dir.relative_to(settings.project_root).as_posix()


def resolve_event_dir(settings: ApiSettings, event_id: str) -> Path:
    """Root-relative ``event_id`` -> an existing directory under the project root.

    Rejects any id that escapes ``project_root`` (``..`` traversal) the same way
    an unknown directory is rejected: :class:`EventNotFoundError`.
    """
    root = settings.project_root.resolve()
    candidate = (root / event_id).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise EventNotFoundError(event_id) from None
    if not candidate.is_dir():
        raise EventNotFoundError(event_id)
    return candidate


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
        id=job.id, status=job.status, progress=job.progress, created_at=job.created_at
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
        clip_count=len(result.classification),
        new_count=len(result.new),
        missing_count=len(result.missing),
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


def _clip_out(event_dir: Path, identity: str, status: ClipStatus) -> ClipOut:
    """One clip with its file facts; a MISSING clip has no file, so it is not statted."""
    if status is ClipStatus.MISSING:
        return ClipOut(identity=identity, status=status)
    # The identity *is* the event-relative POSIX path (the mapping render/ uses),
    # so a clip in a named chapter subdirectory resolves inside that directory.
    size, mtime = _file_facts(event_dir / identity)
    return ClipOut(identity=identity, status=status, size=size, mtime=mtime)


def _build_chapters(
    document: Optional[ReelDocument],
    listing: DiskListing,
    result: ReconcileResult,
    event_dir: Path,
    order: ClipOrder,
) -> List[ChapterOut]:
    """Ordered chapters/clips (D-A3): the document's structure when one exists,

    with disk-only NEW clips appended to their disk chapter; the disk listing's
    own grouping when there is no document yet (the seeding case). Disk clips are
    placed as seeding and adoption place them: in the document's own ``sort`` when
    it sets one, else the project's sort rule ``order``.
    Each clip carries the file facts ``_clip_out`` stats — never a probe.
    """
    if document is None:
        return [
            ChapterOut(
                name=name,
                clips=[
                    _clip_out(event_dir, i, ClipStatus.NEW)
                    for i in order_clips(identities, event_dir, order)
                ],
            )
            for name, identities in listing.by_chapter
        ]

    order = document.sort or order
    chapters: List[ChapterOut] = []
    seen: set[str] = set()
    for chapter in document.chapters:
        clips = []
        for ref in chapter.clips:
            seen.add(ref.identity)
            status = result.classification.get(ref.identity, ClipStatus.MISSING)
            clips.append(_clip_out(event_dir, ref.identity, status))
        chapters.append(ChapterOut(name=chapter.name, clips=clips))

    by_name = {chapter.name: chapter for chapter in chapters}
    for name, identities in listing.by_chapter:
        for identity in order_clips(identities, event_dir, order):
            if identity in seen:
                continue
            status = result.classification.get(identity, ClipStatus.NEW)
            clip = _clip_out(event_dir, identity, status)
            if name in by_name:
                by_name[name].clips.append(clip)
            else:
                new_chapter = ChapterOut(name=name, clips=[clip])
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
    return StalenessOut(stale=verdict.stale, reasons=list(verdict.reasons))


def get_event(
    settings: ApiSettings, event_id: str, job_store: JobStore, runtime: FfmpegRuntime
) -> EventDetailOut:
    """``GET /api/v1/events/{event_id}``: current detail, parsed fresh from disk.

    The event's own failures are classified by the list's rule
    (:func:`classify_event_failure`) into an :class:`EventReadError`. An unknown ID
    is resolved first, so it stays :class:`EventNotFoundError`; the job store and
    the project config are read outside the catch, as the list reads them before
    its loop, so neither is ever reported as this event's failure.
    """
    event_dir = resolve_event_dir(settings, event_id)
    look_defaults = project_look_defaults(settings)
    try:
        document, listing, result = _load_for_reconcile(event_dir, settings.clip_order)
        title, event_date, location = _title_date_location(event_dir, document)
        chapters = _build_chapters(document, listing, result, event_dir, settings.clip_order)
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
        latest_job=_job_summary(latest_jobs.get(event_id)),
        staleness=staleness,
    )


def get_reel(settings: ApiSettings, event_id: str) -> ReelDocument:
    """``GET /api/v1/events/{event_id}/reel``: the document as authored, parsed fresh.

    An event whose directory resolves but which has no ``reel.yaml`` yet reads as
    the empty document (D-R2), mirroring the write endpoint's own seeding — the
    read must accept exactly the set of events the write accepts. Read-only: no
    file is created and nothing is adopted. A malformed document is loud
    (:class:`EventReadError`), never an empty or partial one (Principle I).
    """
    event_dir = resolve_event_dir(settings, event_id)
    reel_path = event_dir / REEL_FILENAME
    if not reel_path.exists():
        return ReelDocument()
    try:
        return load_document(reel_path)
    except ReelParseError as exc:
        raise EventReadError(event_id, str(exc)) from exc


def get_analysis(settings: ApiSettings, event_id: str) -> AnalysisOut:
    """``GET /api/v1/events/{event_id}/analysis``: cached sidecar segments only.

    Never triggers analysis. ``analyzed`` is true when at least one clip in the
    event has a valid cache entry for its current on-disk signal.
    """
    event_dir = resolve_event_dir(settings, event_id)
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
    return AnalysisOut(analyzed=analyzed, segments=segments)


__all__ = [
    "EventNotFoundError",
    "EventReadError",
    "event_id_for",
    "resolve_event_dir",
    "list_events",
    "get_event",
    "get_reel",
    "get_analysis",
    "classify_event_failure",
    "staleness_for",
    "project_look_defaults",
]
