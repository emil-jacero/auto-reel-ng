"""What the analysis routes read: an event's analysis state, and the events Analyze all queues.

Split from :mod:`events_read` (which is at its size limit), like :mod:`proxy_read`. The disk
half is the engine's rule (:mod:`auto_reel_ng.analysis.state`: ``stat`` and JSON, no process,
no write, ``reel.yaml`` never read); this module overlays ``analyzing`` from the job store and
enqueues through :func:`~auto_reel_ng.scheduler.submit_analysis`, the function
``auto-reel analyze --enqueue`` uses (Principle V). Nothing here writes anything but job rows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ..analysis.cache import CACHE_SUBDIR
from ..analysis.state import (
    ClipAnalysis,
    ClipAnalysisState,
    clip_analysis_states,
    event_disk_state,
    needs_analysis,
)
from ..errors import AnalysisStateError
from ..ingest import get_layout
from ..persistence.job_store import JobStore
from ..persistence.models import Job, JobKind, JobStatus
from ..scheduler import submit_analysis
from .events_read import EventReadError, classify_event_failure, event_id_for, listed_event_dir
from .schemas import (
    AnalysisOut,
    AnalysisState,
    AnalyzeAllResult,
    AnalyzeAllUnreadable,
    ClipAnalysisOut,
    SegmentOut,
)
from .serialize import job_to_out
from .settings import ApiSettings

logger = logging.getLogger(__name__)

_ACTIVE = (JobStatus.QUEUED, JobStatus.RUNNING)


@dataclass(frozen=True)
class EventAnalysis:
    """An event's folder and its clips' disk states, as the enqueue judges them."""

    event_dir: Path
    clips: List[ClipAnalysis]


def read_event_clips(settings: ApiSettings, event_id: str) -> EventAnalysis:
    """The listed event's folder and its clips' analysis states.

    Raises:
        EventNotFoundError: the events list does not show ``event_id``.
        LayoutError: the configured layout cannot be resolved.
        EventReadError: the walk or the event folder cannot be listed (with the list's kind).
        AnalysisStateError: a clip cannot be statted or its cache entry cannot be read.
    """
    try:
        event_dir = listed_event_dir(settings, event_id)
        return EventAnalysis(event_dir, clip_analysis_states(event_dir))
    except OSError as exc:
        raise EventReadError(event_id, str(exc), classify_event_failure(exc)) from exc


def _clip_state(clip: ClipAnalysis, job: Optional[Job]) -> AnalysisState:
    """The clip's state with the active job overlaid: what the job will analyze is ``analyzing``.

    An unforced job analyzes ``never`` and ``stale`` clips; a forced one also retries a
    ``failed`` clip. A ``current`` clip stays ``current`` either way: its suggestions hold
    until they are replaced.
    """
    if job is not None:
        if clip.state in (ClipAnalysisState.NEVER, ClipAnalysisState.STALE):
            return AnalysisState.ANALYZING
        if clip.state is ClipAnalysisState.FAILED and job.force:
            return AnalysisState.ANALYZING
    return AnalysisState(clip.state.value)


def get_analysis(settings: ApiSettings, event_id: str, store: JobStore) -> AnalysisOut:
    """``GET /api/v1/events/{event_id}/analysis``: cached segments and the analysis state.

    Never triggers analysis. ``analyzed`` keeps its legacy value (the cache folder exists).

    Raises:
        EventNotFoundError, LayoutError, EventReadError, AnalysisStateError: as
            :func:`read_event_clips`.
        SQLAlchemyError: the job store cannot be reached (``analyzing`` cannot be known).
    """
    read = read_event_clips(settings, event_id)
    job = store.active_job(str(settings.project_root), event_id, kind=JobKind.ANALYSIS)
    segments: Dict[str, List[SegmentOut]] = {
        clip.identity: [
            SegmentOut(start=s.start, end=s.end, kind=s.kind.value, confidence=s.confidence)
            for s in clip.segments
        ]
        for clip in read.clips
        if clip.state is ClipAnalysisState.CURRENT
    }
    state = (
        AnalysisState.ANALYZING
        if job is not None
        else AnalysisState(event_disk_state(read.clips).value)
    )
    return AnalysisOut(
        analyzed=(read.event_dir / CACHE_SUBDIR).is_dir(),
        segments=segments,
        state=state,
        clips={
            clip.identity: ClipAnalysisOut(state=_clip_state(clip, job), detail=clip.detail)
            for clip in read.clips
        },
        job=job_to_out(job) if job is not None else None,
    )


def failed_count(clips: Sequence[ClipAnalysis]) -> int:
    """How many clips read ``failed``."""
    return sum(1 for clip in clips if clip.state is ClipAnalysisState.FAILED)


def analyze_all(settings: ApiSettings, store: JobStore) -> AnalyzeAllResult:
    """``POST /api/v1/analysis``: queue an unforced analysis job for every event that needs one.

    Walks the events the events list shows, in its order. Per event: an active analysis job
    (one read of the latest analysis job per event, before the walk) counts ``active``; a
    folder, clip or entry that cannot be read is one ``unreadable`` item and the walk goes on
    (Principle I's per-event isolation); no ``never`` or ``stale`` clip counts ``fresh``;
    otherwise :func:`~auto_reel_ng.scheduler.submit_analysis` inserts the job, ``queued`` (or
    ``active`` when a concurrent insert won). ``reel.yaml`` is never read.

    Raises:
        LayoutError / OSError: the project walk failed; nothing was queued.
        SQLAlchemyError: the job store cannot be reached; rows inserted before stay queued.
    """
    project_root = settings.project_root
    refs = list(get_layout(settings.layout_name)(settings.walk_root))
    latest = store.latest_by_project(str(project_root), kind=JobKind.ANALYSIS)
    result = AnalyzeAllResult(queued=0, fresh=0, active=0, unreadable=[])
    for ref in refs:
        event_id = event_id_for(settings, ref.event_dir)
        held = latest.get(event_id)
        if held is not None and held.status in _ACTIVE:
            result.active += 1
            continue
        try:
            clips = clip_analysis_states(ref.event_dir)
        except AnalysisStateError as exc:
            result.unreadable.append(AnalyzeAllUnreadable(event_id=event_id, detail=str(exc)))
            continue
        except OSError as exc:
            failure = classify_event_failure(exc)
            result.unreadable.append(
                AnalyzeAllUnreadable(event_id=event_id, detail=str(exc), failure=failure)
            )
            continue
        if not needs_analysis(clips):
            result.fresh += 1
            continue
        submission = submit_analysis(store, project_root, [ref.event_dir], force=False)[0]
        if submission.created:
            result.queued += 1
        else:
            result.active += 1
    for item in result.unreadable:
        logger.warning("analyze all: %s: %s", item.event_id, item.detail)
    return result


__all__ = ["EventAnalysis", "analyze_all", "failed_count", "get_analysis", "read_event_clips"]
