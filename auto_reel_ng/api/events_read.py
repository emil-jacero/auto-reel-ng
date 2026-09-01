"""Scan-on-request events/analysis read model (decision D-A3, tasks 2.2-2.4).

Reuses the CLI's own building blocks unchanged: the ingest layout walk, disk
scan + reconcile, ``load_document``, and the analysis sidecar cache reader. No
new semantics — this module only shapes the same data ``scan``/``analyze``
already compute into the API's pydantic schemas.
"""

from __future__ import annotations

import logging
from datetime import date as DateValue
from pathlib import Path
from typing import Dict, List, Optional

from ..analysis.cache import CACHE_SUBDIR, clip_signal, read_entry
from ..cli.adoption import REEL_FILENAME
from ..config.project import load_project_config, resolve_look_defaults
from ..errors import ReelParseError
from ..event.discovery import DiskListing, parse_folder_name, scan_event, seed_document
from ..event.reconcile import ClipStatus, ReconcileResult, reconcile
from ..ffmpeg.runtime import FfmpegRuntime
from ..ingest import EventRef, get_layout
from ..persistence.job_store import JobStore
from ..persistence.models import Job
from ..reel import ReelDocument, load_document
from ..render import output_filename
from ..staleness.fingerprint import compute_fingerprint
from ..staleness.gate import evaluate
from .schemas import (
    AnalysisOut,
    ChapterOut,
    ClipOut,
    EventDetailOut,
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
    """An event's ``reel.yaml`` could not be parsed (D-A6: loud, never fabricated)."""

    def __init__(self, event_id: str, detail: str) -> None:
        super().__init__(detail)
        self.event_id = event_id
        self.detail = detail


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
    event_id: str, event_dir: Path
) -> tuple[Optional[ReelDocument], DiskListing, ReconcileResult]:
    """Load the document (if any) + disk listing and reconcile them (as ``scan`` does)."""
    reel_path = event_dir / REEL_FILENAME
    document: Optional[ReelDocument] = None
    if reel_path.exists():
        try:
            document = load_document(reel_path)
        except ReelParseError as exc:
            raise EventReadError(event_id, str(exc)) from exc
    listing = scan_event(event_dir)
    result = reconcile(listing.identities, document)
    return document, listing, result


def _job_summary(job: Optional[Job]) -> Optional[JobSummaryOut]:
    if job is None:
        return None
    return JobSummaryOut(
        id=job.id, status=job.status.value, progress=job.progress, created_at=job.created_at
    )


def _title_date_location(
    event_dir: Path, document: Optional[ReelDocument]
) -> tuple[Optional[str], Optional[DateValue], Optional[str]]:
    """Title/date/location: the document's, else the folder-name hint (as ``scan`` shows)."""
    if document is not None and (
        document.metadata.title or document.metadata.date or document.metadata.location
    ):
        return document.metadata.title, document.metadata.date, document.metadata.location
    parsed = parse_folder_name(event_dir.name)
    if parsed is not None:
        event_date, title, location = parsed
        return title, event_date, location
    return None, None, None


def list_events(settings: ApiSettings, job_store: JobStore) -> List[EventSummaryOut]:
    """``GET /api/v1/events``: every event under the configured root, freshly scanned."""
    refs = _list_event_refs(settings)
    latest_jobs = job_store.latest_by_project(str(settings.project_root))

    summaries: List[EventSummaryOut] = []
    for ref in refs:
        event_id = event_id_for(settings, ref.event_dir)
        document, _listing, result = _load_for_reconcile(event_id, ref.event_dir)
        title, event_date, location = _title_date_location(ref.event_dir, document)
        summaries.append(
            EventSummaryOut(
                event_id=event_id,
                title=title,
                date=event_date,
                location=location,
                clip_count=len(result.classification),
                new_count=len(result.new),
                missing_count=len(result.missing),
                latest_job=_job_summary(latest_jobs.get(event_id)),
            )
        )
    return summaries


def _build_chapters(
    document: Optional[ReelDocument], listing: DiskListing, result: ReconcileResult
) -> List[ChapterOut]:
    """Ordered chapters/clips (D-A3): the document's structure when one exists,

    with disk-only NEW clips appended to their disk chapter; the disk listing's
    own grouping when there is no document yet (the seeding case).
    """
    if document is None:
        return [
            ChapterOut(
                name=name,
                clips=[ClipOut(identity=i, status=ClipStatus.NEW.value) for i in identities],
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
            clips.append(ClipOut(identity=ref.identity, status=status.value))
        chapters.append(ChapterOut(name=chapter.name, clips=clips))

    by_name = {chapter.name: chapter for chapter in chapters}
    for name, identities in listing.by_chapter:
        for identity in identities:
            if identity in seen:
                continue
            status = result.classification.get(identity, ClipStatus.NEW)
            clip = ClipOut(identity=identity, status=status.value)
            if name in by_name:
                by_name[name].clips.append(clip)
            else:
                new_chapter = ChapterOut(name=name, clips=[clip])
                chapters.append(new_chapter)
                by_name[name] = new_chapter
    return chapters


def staleness_for(
    settings: ApiSettings, event_dir: Path, document: Optional[ReelDocument], runtime: FfmpegRuntime
) -> StalenessOut:
    """The event's staleness verdict (change-detection, §8.14): read-only, never writes.

    Uses ``document`` if it was already loaded, else the folder-seed equivalent
    (never adopted, never persisted — a GET must not write, D-7). Public: also
    used by the editorial-write route to echo the post-save verdict inline.
    """
    fp_document = document if document is not None else seed_document(event_dir)
    look_defaults = resolve_look_defaults(load_project_config(settings.project_root))
    fingerprint = compute_fingerprint(
        fp_document,
        event_dir=event_dir,
        look_defaults=look_defaults,
        ffmpeg_version=runtime.version,
    )
    output_path = settings.output_dir / output_filename(fp_document.metadata)
    verdict = evaluate(event_dir, output_path, fingerprint)
    return StalenessOut(stale=verdict.stale, reasons=list(verdict.reasons))


def get_event(
    settings: ApiSettings, event_id: str, job_store: JobStore, runtime: FfmpegRuntime
) -> EventDetailOut:
    """``GET /api/v1/events/{event_id}``: current detail, parsed fresh from disk."""
    event_dir = resolve_event_dir(settings, event_id)
    document, listing, result = _load_for_reconcile(event_id, event_dir)
    title, event_date, location = _title_date_location(event_dir, document)
    latest_jobs = job_store.latest_by_project(str(settings.project_root))

    return EventDetailOut(
        event_id=event_id,
        title=title,
        date=event_date,
        location=location,
        description=document.metadata.description if document is not None else None,
        chapters=_build_chapters(document, listing, result),
        missing=list(result.missing),
        latest_job=_job_summary(latest_jobs.get(event_id)),
        staleness=staleness_for(settings, event_dir, document, runtime),
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
    "staleness_for",
]
