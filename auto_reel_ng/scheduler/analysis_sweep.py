"""The worker's automatic analysis sweep (``analysis-auto-sweep``).

While ``worker.auto_analyze`` is on, the worker runs :meth:`AnalysisSweep.run` on a thread beside
its claim loop: a sweep when it starts, then one every ``worker.auto_analyze_interval`` seconds
until the worker stops. A sweep enqueues an ordinary, non-forced ``analysis`` job (through
:func:`~auto_reel_ng.scheduler.analysis_job.submit_analysis`, the one enqueue path) for each
event that has a clip such a job would analyze, decided by
:func:`~auto_reel_ng.analysis.cache.pending_clips`, the rule the job itself uses; so an event the
job has just brought up to date (failure-marked clips included) is never enqueued again.

A sweep is cheap and polite:

- **Metadata only.** Directory listings, ``stat`` and the small sidecar JSON files; never
  ffprobe, ffmpeg, a content hash or ``reel.yaml``; it writes no file, only job rows.
- **Quiet while the queue is busy.** Nothing is enqueued while any job of the project is
  ``queued``, or a ``render`` or ``proxy`` job of it is ``running``; a running ``analysis`` job
  alone does not stop it. Analysis is claimed after every other kind and yields to running
  renders and proxy jobs (``analysis-job``), so automatic work never delays a user's.
- **Capped, newest first.** Events are visited in reverse layout-walk order (recent footage
  first) and the sweep stops once it created ``max_events`` jobs, so the first sweep over a
  large archive trickles.
- **Backs off** from an event whose latest ``analysis`` job ended ``canceled`` or ``failed``
  until one of its clip files changes after that job finished (``st_mtime`` or ``st_ctime``,
  so a copy that preserved an old mtime still counts): a user's cancel is not undone and a
  job-level fault does not loop.
- **Never stops the worker.** A database error or a failing layout walk ends that sweep with
  an ERROR log; an event that cannot be listed or statted is skipped with a WARNING.

It keeps no state of its own: the store's one-active-job index, the job rows and the on-disk
sidecars carry everything across restarts.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Sequence

from sqlalchemy.exc import SQLAlchemyError

from ..analysis.cache import pending_clips
from ..config.project import ProjectConfig
from ..errors import EngineError
from ..event import scan_event
from ..ingest import DEFAULT_LAYOUT, get_layout
from ..persistence.job_store import JobStore
from ..persistence.models import Job, JobKind, JobStatus
from .analysis_job import submit_analysis

logger = logging.getLogger(__name__)

#: The running kinds that keep a sweep quiet (any ``queued`` job does too).
BUSY_RUNNING_KINDS = frozenset({JobKind.RENDER.value, JobKind.PROXY.value})

#: The terminal statuses of an event's latest ``analysis`` job that make the sweep back off.
BACK_OFF_STATUSES = frozenset({JobStatus.CANCELED, JobStatus.FAILED})

#: ``threading.Event.wait``'s shape, so a test can drive :meth:`AnalysisSweep.run` without sleeping.
Wait = Callable[[float], bool]


@dataclass(frozen=True)
class SweepReport:
    """What one sweep did."""

    #: Project-relative event folders a job was created for, in the order they were enqueued.
    enqueued: tuple[str, ...] = ()
    #: The created jobs' ids, aligned with :attr:`enqueued`.
    job_ids: tuple[uuid.UUID, ...] = ()
    #: The queue was busy, so nothing was considered.
    busy: bool = False
    #: Why the sweep ended early (a database error, a failing walk), else ``None``.
    error: Optional[str] = None


class AnalysisSweep:
    """Enqueue ``analysis`` jobs for one project's events whose analysis is due."""

    def __init__(
        self,
        store: JobStore,
        project_root: Path,
        config: ProjectConfig,
        *,
        max_events: int,
    ) -> None:
        if max_events < 1:
            raise ValueError(f"max_events must be at least 1, got {max_events}")
        self._store = store
        self._root = Path(project_root)
        self._config = config
        self._max_events = max_events

    def sweep_once(self) -> SweepReport:
        """One sweep over the project; never raises for a database or walk failure."""
        project = str(self._root)
        try:
            running = self._running_unless_busy(project)
            if running is None:
                logger.debug("analysis sweep: the queue is busy; nothing enqueued")
                return SweepReport(busy=True)
            active = {job.event_dir for job in running if job.kind == JobKind.ANALYSIS.value}
            latest = self._store.latest_by_project(project, kind=JobKind.ANALYSIS)
            events = self._walk()
            if events is None:
                return SweepReport(error="the layout walk failed")
            return self._enqueue_due(events, active, latest)
        except SQLAlchemyError as exc:
            logger.error("analysis sweep: the job store failed; trying again later: %s", exc)
            return SweepReport(error=f"job store: {exc}")

    # ------------------------------------------------------------------ reads

    def _running_unless_busy(self, project: str) -> Optional[List[Job]]:
        """The project's running jobs, or ``None`` when the queue is busy (the quiet rule)."""
        if self._store.list_by_status(JobStatus.QUEUED, project_root=project, kind=None):
            return None
        running = self._store.list_by_status(JobStatus.RUNNING, project_root=project, kind=None)
        if any(job.kind in BUSY_RUNNING_KINDS for job in running):
            return None
        return running

    def _walk(self) -> Optional[List[Path]]:
        """The project's events, newest first (the reverse of the layout's walk order).

        ``None`` when the walk failed (logged at ERROR naming the walk root): the walk root is
        gone (an unmounted share), unreadable, or the configured layout is unknown.
        """
        walk_root = self._root / self._config.input_dir if self._config.input_dir else self._root
        try:
            layout = get_layout(self._config.layout or DEFAULT_LAYOUT)
            return [ref.event_dir for ref in layout(walk_root)][::-1]
        except (OSError, EngineError) as exc:
            logger.error("analysis sweep: cannot walk %s; trying again later: %s", walk_root, exc)
            return None

    # ------------------------------------------------------------------ enqueue

    def _enqueue_due(
        self, events: Sequence[Path], active: set[str], latest: Mapping[str, Job]
    ) -> SweepReport:
        enqueued: List[str] = []
        job_ids: List[uuid.UUID] = []
        for event_dir in events:
            if len(enqueued) >= self._max_events:
                break
            relative = self._relative(event_dir)
            if relative is None or relative in active:
                continue
            if not self._due(event_dir, latest.get(relative)):
                continue
            (submission,) = submit_analysis(self._store, self._root, [event_dir], force=False)
            if submission.created:
                enqueued.append(submission.event_dir)
                job_ids.append(submission.job_id)
        if enqueued:
            logger.info(
                "analysis sweep: enqueued %d event(s): %s",
                len(enqueued),
                ", ".join(f"{event} ({job_id})" for event, job_id in zip(enqueued, job_ids)),
            )
        else:
            logger.debug("analysis sweep: nothing due")
        return SweepReport(enqueued=tuple(enqueued), job_ids=tuple(job_ids))

    def _relative(self, event_dir: Path) -> Optional[str]:
        try:
            return event_dir.relative_to(self._root).as_posix()
        except ValueError:
            logger.warning("analysis sweep: skipping %s: outside the project root", event_dir)
            return None

    def _due(self, event_dir: Path, latest: Optional[Job]) -> bool:
        """Whether a non-forced ``analysis`` job of ``event_dir`` would analyze a clip, and the
        event's latest analysis job, if it was canceled or failed, does not hold it back."""
        try:
            if not pending_clips(event_dir):
                return False
            if latest is None or latest.status not in BACK_OFF_STATUSES:
                return True
            if _changed_since(event_dir, latest):
                return True
        except OSError as exc:
            logger.warning("analysis sweep: skipping %s: cannot read it: %s", event_dir, exc)
            return False
        logger.debug(
            "analysis sweep: %s: its last analysis job %s ended %s and nothing changed since",
            event_dir,
            latest.id,
            latest.status.value,
        )
        return False


def _changed_since(event_dir: Path, job: Job) -> bool:
    """Whether a clip file of ``event_dir`` changed after ``job`` finished.

    A clip's ``st_mtime`` or ``st_ctime`` later than the job's ``finished_at`` (its
    ``created_at`` should a terminal row lack one) counts: an ingest tool that preserves a
    camera file's old mtime still moves the copy's ctime.

    Raises:
        OSError: the folder cannot be listed or a clip cannot be statted.
    """
    ended = job.finished_at if job.finished_at is not None else job.created_at
    threshold = ended.timestamp()
    for identity in scan_event(event_dir).identities:
        stat = (event_dir / identity).stat()
        if max(stat.st_mtime, stat.st_ctime) > threshold:
            return True
    return False


__all__ = ["AnalysisSweep", "SweepReport", "BUSY_RUNNING_KINDS", "BACK_OFF_STATUSES", "Wait"]
