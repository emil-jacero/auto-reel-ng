"""The ``analysis`` job (``analysis-job``): detect black/white/freeze spans in one event's clips.

A claimed ``analysis`` job lists its event folder with :func:`~auto_reel_ng.event.scan_event`
(every clip on disk, IGNORED ones too; ``reel.yaml`` is never read) and, in listing order,
analyzes each **original** clip whose analysis sidecar holds no entry for the clip's current
content-change signal (:func:`~auto_reel_ng.analysis.analyze_clip`, the same two passes and
thresholds as ``auto-reel analyze``). A clip with a current entry costs a ``stat`` and a small
JSON read. A job enqueued with ``force`` (Re-analyze) analyzes every clip whatever the sidecar
holds. It writes only into the event's ``.auto-reel/cache/``, atomically; no render checks
apply, no fingerprint is recorded, and staleness is not touched (analysis is a suggestion).

Failures: a clip that cannot be statted, probed or decoded is recorded, gets a **failure
marker** keyed by its current signal (a clip that cannot be statted has no signal and gets
none), and the others are still analyzed; the job then fails naming the failed clips. A job
that is not forced does not run ffmpeg for a clip whose marker matches its current signal: it
counts it failed again with the recorded cause, so nothing retries it in a loop. A fault of the
sidecar itself (the cache directory cannot be created or written) ends the job at once.

The job holds one CPU token while it analyzes a clip (software decode) and no GPU token, and
it **yields** (``turns``): it starts no clip while a ``render`` or a ``proxy`` job is running,
giving its token back while it waits, so renders and the Timeline's proxies come first at run
time and not only at claim time. A cancel, or the worker being stopped, ends the running ffmpeg
within about a second and leaves no entry or marker for that clip.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from ..analysis.cache import (
    cache_dir,
    clip_signal,
    read_entry,
    read_failure,
    write_entry,
    write_failure,
)
from ..analysis.models import Segment
from ..analysis.runner import analyze_clip
from ..errors import AnalysisError, EngineError, FfmpegCancelledError, RenderCancelledError
from ..event import scan_event
from ..ffmpeg.runtime import FfmpegRuntime
from ..persistence.job_store import JobStore
from ..persistence.models import Job, JobKind
from ..thumbs import one_line_cause
from .pools import CapacityPools
from .progress import ThrottledProgress
from .turns import Hold, Turns

logger = logging.getLogger(__name__)

#: Seconds between looks at the cancel flag while the job waits for its CPU token.
TOKEN_POLL_S = 0.5
#: Seconds between looks at the running renders and proxy jobs while the job yields to them.
YIELD_POLL_S = 1.0
#: How many failed clips an error message spells out before it says "and N more".
MAX_NAMED_FAILURES = 3
#: What the progress of a job with a failed clip is capped at: ``1.0`` means "done".
FAILED_PROGRESS_CAP = 0.99
#: The kinds an analysis job yields to, in claim order.
YIELDS_TO = (JobKind.RENDER, JobKind.PROXY)

#: ``analyze_clip``'s signature, so a test can stand in for the real detection.
AnalyzeClip = Callable[..., List[Segment]]


class AnalysisJobError(EngineError):
    """An ``analysis`` job ended with failed clips, or its sidecar could not be written."""


@dataclass(frozen=True)
class AnalysisSubmission:
    """What :func:`submit_analysis` did for one event."""

    event_dir: str  # project-root-relative, posix
    job_id: uuid.UUID
    created: bool
    #: Whether the job will run forced. A forced submit that meets a ``queued`` unforced job
    #: forces it; one that meets a ``running`` unforced job cannot, and reports ``False``.
    forced: bool


def submit_analysis(
    store: JobStore, project_root: Path, event_dirs: Iterable[Path], *, force: bool
) -> List[AnalysisSubmission]:
    """Queue one ``analysis`` job per event through the store's idempotent submit.

    The one place an analysis job is enqueued (Principle V): the CLI's ``analyze --enqueue``
    and the API both call it. It runs no ffprobe or ffmpeg and writes no file. An event that
    already has an active analysis job reports that job with ``created=False``.

    With ``force``, an active job that is still ``queued`` without ``force`` is forced, so a
    Re-analyze that meets an unforced job (``analyze --enqueue``, the auto-sweep) is not lost;
    a ``running`` unforced job cannot be, and its submission reports ``forced=False``.
    """
    submissions: List[AnalysisSubmission] = []
    for event_dir in event_dirs:
        relative = Path(event_dir).relative_to(project_root).as_posix()
        submission = store.submit(str(project_root), relative, kind=JobKind.ANALYSIS, force=force)
        forced = force
        if force and not submission.created:
            forced = store.force_queued(submission.job_id)
        submissions.append(
            AnalysisSubmission(relative, submission.job_id, submission.created, forced)
        )
    return submissions


@dataclass(frozen=True)
class _Clip:
    """One clip the event's folder lists: its identity, path and progress weight."""

    identity: str
    path: Path
    weight: int


class AnalysisJobHandler:  # pylint: disable=too-few-public-methods
    """The ``analysis`` kind's :data:`~auto_reel_ng.scheduler.worker.KindHandler`."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        store: JobStore,
        pools: CapacityPools,
        runtime: FfmpegRuntime,
        stop_event: Optional[threading.Event] = None,
        analyze: AnalyzeClip = analyze_clip,
    ) -> None:
        self._store = store
        self._pools = pools
        self._runtime = runtime
        self._stop = stop_event if stop_event is not None else threading.Event()
        self._analyze = analyze
        self._turns = Turns(store, self._stop, label="analysis")

    def __call__(self, job: Job) -> None:
        """Analyze the job's event; return for ``done``, raise for ``failed`` or ``canceled``.

        Raises:
            RenderCancelledError: the job was canceled.
            JobInterrupted: the worker is stopping; the row is left for its requeue.
            AnalysisJobError: one or more clips failed, or the sidecar could not be written.
            AnalysisError: the event folder cannot be listed.
        """
        project_root = Path(job.project_root) if job.project_root else Path.cwd()
        event_dir = project_root / job.event_dir
        clips = _plan(event_dir)
        hold = Hold(self._pools.cpu_token())
        try:
            self._run(job, event_dir, clips, hold)
        finally:
            hold.release()

    def _cancel_check(self, job: Job) -> Callable[[], bool]:
        def should_cancel() -> bool:
            if self._stop.is_set():
                return True
            current = self._store.get(job.id)
            return current is not None and current.cancel_requested

        return should_cancel

    def _take_turn(self, job: Job, hold: Hold) -> None:
        self._turns.take_turn(
            job, hold, yield_to=YIELDS_TO, token_poll_s=TOKEN_POLL_S, yield_poll_s=YIELD_POLL_S
        )

    def _run(  # pylint: disable=too-many-locals
        self, job: Job, event_dir: Path, clips: List[_Clip], hold: Hold
    ) -> None:
        progress = ThrottledProgress(self._store, job.id)
        should_cancel = self._cancel_check(job)
        total = sum(clip.weight for clip in clips) or 1
        finished = 0
        failures: List[str] = []

        def report(value: float) -> None:
            progress(min(value, FAILED_PROGRESS_CAP) if failures else value)

        for clip in clips:
            self._turns.stop_or_cancel(job)
            self._take_turn(job, hold)
            base = finished

            def on_clip(fraction: float, base: int = base, weight: int = clip.weight) -> None:
                report((base + weight * fraction) / total)

            cause = self._analyze_one(job, event_dir, clip, on_clip, should_cancel)
            if cause is not None:
                failures.append(f"{clip.identity}: {cause}")
            finished += clip.weight
            report(finished / total)
        if failures:
            raise AnalysisJobError(_failure_message(failures, len(clips)))

    def _analyze_one(
        self,
        job: Job,
        event_dir: Path,
        clip: _Clip,
        on_clip: Callable[[float], None],
        should_cancel: Callable[[], bool],
    ) -> Optional[str]:
        """Bring one clip's sidecar entry up to date; return its failure's cause, else ``None``.

        Raises:
            AnalysisJobError: the sidecar could not be written (ends the job).
            RenderCancelledError / JobInterrupted: the job was canceled / the worker stops.
        """
        try:
            signal = clip_signal(clip.path)
        except OSError as exc:
            logger.error("job %s: %s: cannot stat: %s", job.id, clip.identity, exc)
            return f"cannot stat the clip: {exc.strerror or exc}"
        if not job.force:
            if read_entry(event_dir, clip.identity, signal) is not None:
                return None
            recorded = read_failure(event_dir, clip.identity, signal)
            if recorded is not None:
                return f"{recorded} (an earlier failure; Re-analyze to retry)"
        try:
            segments = self._analyze(
                clip.path,
                runtime=self._runtime,
                on_progress=on_clip,
                should_cancel=should_cancel,
            )
        except FfmpegCancelledError as exc:
            self._turns.stop_or_cancel(job)  # a stop is not a cancel
            raise RenderCancelledError(f"analysis job {job.id} was canceled") from exc
        except AnalysisError as exc:
            logger.error("job %s: %s: %s", job.id, clip.identity, exc)
            cause = one_line_cause(str(exc).replace(str(clip.path), clip.path.name), clip.path)
            self._write(event_dir, lambda: write_failure(event_dir, clip.identity, signal, cause))
            return cause
        self._write(event_dir, lambda: write_entry(event_dir, clip.identity, signal, segments))
        return None

    @staticmethod
    def _write(event_dir: Path, write: Callable[[], Path]) -> None:
        """Run one sidecar write; a failure of the cache itself ends the job at once."""
        try:
            write()
        except OSError as exc:
            where = cache_dir(event_dir)
            raise AnalysisJobError(
                f"cannot write the analysis cache {where}: {exc.strerror or exc}"
            ) from exc


def _plan(event_dir: Path) -> List[_Clip]:
    """Every clip the event's folder lists, in listing order, with its weight."""
    try:
        identities = scan_event(event_dir).identities
    except OSError as exc:
        raise AnalysisError(f"cannot list the event folder {event_dir}: {exc}") from exc
    return [
        _Clip(identity=identity, path=event_dir / identity, weight=_weight(event_dir / identity))
        for identity in identities
    ]


def _weight(clip: Path) -> int:
    """The clip's weight in the job's progress: its size in bytes, at least one."""
    try:
        return max(1, clip.stat().st_size)
    except OSError:
        return 1


def _failure_message(failures: List[str], clips: int) -> str:
    """``"1 of 3 clips failed: a.mp4: cause; ..."``, shortened to the first few."""
    named = "; ".join(failures[:MAX_NAMED_FAILURES])
    more = len(failures) - MAX_NAMED_FAILURES
    if more > 0:
        named += f"; and {more} more"
    return f"{len(failures)} of {clips} clips failed: {named}"


__all__ = [
    "FAILED_PROGRESS_CAP",
    "MAX_NAMED_FAILURES",
    "YIELD_POLL_S",
    "YIELDS_TO",
    "AnalysisJobError",
    "AnalysisJobHandler",
    "AnalysisSubmission",
    "submit_analysis",
]
