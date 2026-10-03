"""The job-scheduler worker: claim/execute loop, capacity, reconcile, cancel (7b).

A long-running process that polls :meth:`~auto_reel_ng.persistence.job_store.JobStore.claim_next`,
rebuilds the render plan from disk at claim time (D-S1), classifies the job by its
resolved encoder to acquire the matching capacity token (D-S3), and drives the
existing engine unchanged. Each claimed job runs on its own thread so a job
blocked waiting for a busy pool token never stalls the claim loop (D-S3); startup
reconciliation requeues orphaned ``running`` rows before the first claim (D-S5);
graceful shutdown stops claiming and requeues in-flight work (D-S8).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, NamedTuple, Optional

from ..accel.profiles.base import AccelProfile
from ..cli.build import build_render_job_from_event, prepare_and_persist
from ..config.project import (
    ProjectConfig,
    default_output_dir,
    load_project_config,
    resolve_look_defaults,
)
from ..errors import (
    ClaimedMovieError,
    EngineError,
    IllegalJobTransitionError,
    OutputCollisionError,
    RenderCancelledError,
)
from ..event.claims import checked_claim
from ..event.metadata import load_event_document, require_processable
from ..ffmpeg.runtime import FfmpegRuntime
from ..ingest import DEFAULT_LAYOUT, get_layout
from ..persistence.job_store import JobStore
from ..persistence.models import Job, JobKind, JobStatus
from ..reel import Metadata
from ..render import (
    RenderJob,
    RenderResult,
    find_output_collisions,
    output_relpath,
    render_movie,
    resolve_target,
)
from ..render.claims import (
    claimed_movie,
    claimed_movie_message,
    output_collision,
    output_collision_message,
)
from ..staleness.fingerprint import compute_fingerprint
from ..staleness.gate import evaluate
from .pools import CapacityPools
from .progress import ThrottledProgress

logger = logging.getLogger(__name__)

BuildJob = Callable[[Job], RenderJob]
RunRender = Callable[[RenderJob], RenderResult]
#: Runs a claimed job of a non-render kind: returns normally for ``done``, raises
#: :class:`~auto_reel_ng.errors.RenderCancelledError` for ``canceled`` or an
#: :class:`~auto_reel_ng.errors.EngineError` for ``failed``. The handler owns its own
#: capacity token (job-kind): the worker takes none for it.
KindHandler = Callable[[Job], None]


def _render_job(render_job: RenderJob) -> RenderResult:
    """Adapt :func:`~auto_reel_ng.render.render_movie`'s 3-arg signature to ``RunRender``."""
    return render_movie(render_job.plan, render_job.profile, render_job.options)


def default_build_job(
    job: Job,
    *,
    runtime: FfmpegRuntime,
    profile: AccelProfile,
    render_node: Optional[str],
) -> RenderJob:
    """Resolve ``project_root``/``event_dir`` (D-S7) and rebuild the plan (D-S1).

    Loads the *claimed job's own project* ``config.yaml`` for its ``look``/output
    defaults, rather than any config the worker process itself was started near —
    a job row's ``project_root`` is authoritative for where it lives on disk. The
    render fingerprint (change-detection, §8.14) is computed post-persist (D-C5)
    and carried on the built job's options; ``overwrite`` is set unconditionally
    (D-C4) — whether to render at all is :meth:`Worker._process`'s claim-time
    recheck, using this same fingerprint.
    """
    project_root = Path(job.project_root) if job.project_root else Path.cwd()
    event_dir = project_root / job.event_dir
    config = load_project_config(project_root)
    look_defaults = resolve_look_defaults(config)
    output_dir = (
        project_root / config.output_dir if config.output_dir else default_output_dir(project_root)
    )

    # The same processable-event rule as the CLI: a failure fails the job with the reason.
    document = load_event_document(event_dir, order=config.sort)[0]
    require_processable(event_dir, document.metadata, today=date.today())
    # D-9: no other event of the project may claim this output path. Checked before
    # ``prepare_and_persist`` so a refused job writes nothing (not even an adopted clip);
    # ``force`` never reads here, as it does not for the CLI and the API.
    _refuse_disk_collision(project_root, event_dir, config)
    if not job.force:
        _refuse_claimed_movie(project_root, event_dir, config, document.metadata, output_dir)
    event = prepare_and_persist(event_dir, order=config.sort)
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=look_defaults,
        ffmpeg_version=runtime.version,
    )
    return build_render_job_from_event(
        event,
        output_dir=output_dir,
        runtime=runtime,
        profile=profile,
        render_node=render_node,
        look_defaults=look_defaults,
        overwrite=True,
        fingerprint=fingerprint,
    )


def _refuse_disk_collision(project_root: Path, event_dir: Path, config: ProjectConfig) -> None:
    """Raise :class:`OutputCollisionError` when another event of the project claims the output.

    The disk rule (D-9): the event's own project is walked with the project's layout and
    sort, so the answer is the one the API gives at enqueue. ``force`` never bypasses it.
    """
    walk_root = project_root / config.input_dir if config.input_dir else project_root
    collision = output_collision(
        event_dir,
        walk_root=walk_root,
        layout=config.layout or DEFAULT_LAYOUT,
        order=config.sort,
        today=date.today(),
    )
    if collision is not None:
        raise OutputCollisionError(
            output_collision_message(
                collision.output_path,
                [_claimant_name(path, project_root) for path in collision.claimed_by],
            )
        )


def _refuse_claimed_movie(
    project_root: Path,
    event_dir: Path,
    config: ProjectConfig,
    metadata: Metadata,
    output_dir: Path,
) -> None:
    """Raise :class:`ClaimedMovieError` when the job would replace a movie another event records.

    The kept, old-named movie of a renamed event is recorded in that event's render manifest
    (D-9); an unforced render must not silently replace it. Read-only, and decided before
    ``prepare_and_persist`` so a refused job adopts and writes nothing. The project is walked
    with its layout, as the collision rule does, and a walk failure propagates: a job must not
    render when the check could not be made (Principle I).
    """
    relpath = output_relpath(metadata)
    walk_root = project_root / config.input_dir if config.input_dir else project_root
    events = [ref.event_dir for ref in get_layout(config.layout or DEFAULT_LAYOUT)(walk_root)]
    claimed = claimed_movie(event_dir, output_dir / relpath, events=events)
    if claimed is not None:
        raise ClaimedMovieError(
            claimed_movie_message(
                relpath, [_claimant_name(path, project_root) for path in claimed.recorded_by]
            )
        )


def _claimant_name(event_dir: Path, project_root: Path) -> str:
    """A claimant as the project spells it (``2024/a``), or the full path outside the root."""
    try:
        return event_dir.relative_to(project_root).as_posix()
    except ValueError:
        return str(event_dir)


class _JobOutput(NamedTuple):
    """Where a job writes: its output directory and the file the event's metadata names."""

    output_dir: Path
    relpath: PurePosixPath

    @property
    def path(self) -> PurePosixPath:
        """The absolute output path, as the collision rule compares it."""
        return PurePosixPath(self.output_dir / self.relpath)


def _job_output(job: Job, *, today: date) -> Optional[_JobOutput]:
    """The output ``job`` writes, or ``None`` when its project or event claims nothing.

    Read-only, from disk (``Job.output_path`` is never recorded). A project config that
    will not load, or an event that is not processable, claims no path: the job's own
    build reports that reason.
    """
    project_root = Path(job.project_root) if job.project_root else Path.cwd()
    try:
        config = load_project_config(project_root)
    except (EngineError, OSError):
        return None
    document, _reason = checked_claim(project_root / job.event_dir, order=config.sort, today=today)
    if document is None:
        return None
    output_dir = (
        project_root / config.output_dir if config.output_dir else default_output_dir(project_root)
    )
    return _JobOutput(output_dir, output_relpath(document.metadata))


class Worker:
    """Polls the job store, rebuilds each claimed job's plan, and renders it.

    ``build_job``/``render`` are injectable seams (default: :func:`default_build_job`
    wired to a real engine, and :func:`~auto_reel_ng.render.render_movie`) so tests
    can stub the engine, mirroring the CLI's own patched-engine tests.

    A claimed job is dispatched by its ``kind`` (job-kind): ``render`` is the worker's own
    path and cannot be overridden; any other kind runs the handler registered for it in
    ``kind_handlers``, and a kind with no handler fails the job loud.
    """

    def __init__(
        self,
        job_store: JobStore,
        *,
        worker_id: str,
        pools: CapacityPools,
        poll_interval: float,
        build_job: BuildJob,
        render: RunRender = _render_job,
        device_filter: Optional[str] = None,
        kind_handlers: Optional[Mapping[str, KindHandler]] = None,
    ) -> None:
        handlers = dict(kind_handlers or {})
        if JobKind.RENDER in handlers:
            raise ValueError("the render kind is the worker's own path and cannot have a handler")
        self._store = job_store
        self._worker_id = worker_id
        self._pools = pools
        self._poll_interval = poll_interval
        self._build_job = build_job
        self._render = render
        self._device_filter = device_filter
        self._kind_handlers = handlers
        self._stopping = threading.Event()
        self._lock = threading.Lock()
        self._inflight: dict[uuid.UUID, threading.Thread] = {}

    @property
    def worker_id(self) -> str:
        """This worker instance's unique identity (``host:pid:nonce``, D-S5)."""
        return self._worker_id

    def stop(self) -> None:
        """Signal the loop to stop claiming new work (called from a signal handler)."""
        self._stopping.set()

    def reconcile(self) -> list[uuid.UUID]:
        """Startup reconcile (D-S5): requeue every ``running`` row this worker doesn't own.

        Must run once before the first claim. Sound unconditionally because output
        finalization is atomic (D-S2): a genuinely finished orphan re-runs, hits
        the engine's skip-if-exists check, and completes as ``done`` in
        milliseconds rather than re-rendering.
        """
        orphaned = self._store.find_orphaned_running(live_workers=[self._worker_id])
        for job in orphaned:
            self._store.requeue(job.id)
        return [job.id for job in orphaned]

    def run(self, *, max_polls: Optional[int] = None) -> None:
        """Run the claim/execute loop until :meth:`stop`, or until idle for ``max_polls``
        consecutive polls (a "drain and stop" seam for tests/bounded runs).

        Each claimed job is dispatched to its own thread immediately, so a job
        blocked on a busy capacity token never stalls the claim loop for other
        eligible jobs. Claiming itself is bounded to ``pools.total_capacity``
        concurrently in-flight jobs (D-S3): once that many are claimed-and-spawned,
        the loop stops claiming further work until one finishes, so a burst of
        queued jobs never spawns more waiting threads than there is eventual token
        capacity to run them. ``max_polls`` only counts polls that are *both* empty
        (no claim, at or under capacity) and have no in-flight work, so a bounded
        run waits for spawned jobs to finish rather than requeuing them out from
        under themselves. On exit (stop requested or idle-``max_polls`` reached),
        any still-in-flight jobs are requeued before returning (graceful shutdown).
        """
        self.reconcile()
        idle_polls = 0
        total_capacity = self._pools.total_capacity
        while not self._stopping.is_set():
            with self._lock:
                at_capacity = len(self._inflight) >= total_capacity
            if not at_capacity:
                job = self._store.claim_next(self._worker_id, device_filter=self._device_filter)
                if job is not None:
                    idle_polls = 0
                    self._spawn(job)
                    continue
            with self._lock:
                has_inflight = bool(self._inflight)
            if has_inflight:
                idle_polls = 0
            else:
                idle_polls += 1
                if max_polls is not None and idle_polls >= max_polls:
                    break
            time.sleep(self._poll_interval)
        self._requeue_inflight()

    def process_next(self) -> bool:
        """Claim and process one job synchronously in the calling thread; no spawn.

        Returns ``False`` without touching anything when the queue is empty.
        Useful for tests and for single-threaded/deterministic operation; the
        concurrent, capacity-aware path is :meth:`run`.
        """
        job = self._store.claim_next(self._worker_id, device_filter=self._device_filter)
        if job is None:
            return False
        self._process(job)
        return True

    def _spawn(self, job: Job) -> None:
        thread = threading.Thread(target=self._run_and_untrack, args=(job,), daemon=True)
        with self._lock:
            self._inflight[job.id] = thread
        thread.start()

    def _run_and_untrack(self, job: Job) -> None:
        try:
            self._process(job)
        finally:
            with self._lock:
                self._inflight.pop(job.id, None)

    def _requeue_inflight(self) -> None:
        """Requeue whatever is still in-flight at shutdown (D-S8, graceful shutdown)."""
        with self._lock:
            job_ids = list(self._inflight.keys())
        for job_id in job_ids:
            try:
                self._store.requeue(job_id)
            except IllegalJobTransitionError:
                pass  # it reached a terminal state between the snapshot and this call

    def _process(self, job: Job) -> None:
        """Process one claimed job; no exception except ``BaseException`` leaves this method.

        The typed handlers inside :meth:`_process_job` keep their own messages and the
        cancel semantics; anything they let through fails the job here rather than
        killing the thread and leaving the row ``running``.
        """
        try:
            self._process_job(job)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._fail_unexpected(job, exc)

    def _fail_unexpected(self, job: Job, exc: Exception) -> None:
        """Record an unexpected exception as the job's failure; never raise."""
        logger.exception("job %s failed unexpectedly", job.id)
        message = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        try:
            self._safe_transition(job.id, JobStatus.FAILED, error=message)
        except Exception:  # pylint: disable=broad-exception-caught
            # Usually the database itself; the row is left for the next startup reconcile.
            logger.exception("job %s: could not record failure", job.id)

    def _process_job(self, job: Job) -> None:
        """Dispatch a claimed job by its kind (job-kind)."""
        if job.kind == JobKind.RENDER:
            self._process_render(job)
            return
        handler = self._kind_handlers.get(job.kind)
        if handler is None:
            # Before any token, build or probe: nothing about the event is touched, and the
            # job is failed rather than requeued (a requeue would spin on the same claim).
            known = job.kind in {kind.value for kind in JobKind}
            reason = (
                f"no handler for job kind {job.kind!r}"
                if known
                else f"unknown job kind {job.kind!r}"
            )
            logger.error("job %s failed: %s", job.id, reason)
            self._safe_transition(job.id, JobStatus.FAILED, error=reason)
            return
        self._run_handler(job, handler)

    def _run_handler(self, job: Job, handler: KindHandler) -> None:
        """Run a non-render kind's handler and record its outcome."""
        try:
            handler(job)
        except RenderCancelledError:
            logger.info("job %s canceled", job.id)
            self._safe_transition(job.id, JobStatus.CANCELED)
            return
        except EngineError as exc:
            logger.error("job %s failed: %s", job.id, exc)
            self._safe_transition(job.id, JobStatus.FAILED, error=str(exc))
            return
        self._store.set_progress(job.id, 1.0)
        self._safe_transition(job.id, JobStatus.DONE)

    def _process_render(self, job: Job) -> None:
        try:
            self._refuse_running_output(job)
            render_job = self._build_job(job)
        except EngineError as exc:
            logger.error("job %s failed to build: %s", job.id, exc)
            self._safe_transition(job.id, JobStatus.FAILED, error=str(exc))
            return

        if not job.force and self._is_fresh(render_job):
            logger.info("job %s: event fresh at claim time; completing without render", job.id)
            self._store.set_progress(job.id, 1.0)
            self._safe_transition(job.id, JobStatus.DONE)
            return

        try:
            target = resolve_target(
                render_job.plan, render_job.profile, render_job.options.clip_facts
            )
        except EngineError as exc:
            logger.error("job %s failed to classify: %s", job.id, exc)
            self._safe_transition(job.id, JobStatus.FAILED, error=str(exc))
            return

        render_job.options.on_progress = ThrottledProgress(self._store, job.id)
        render_job.options.should_cancel = lambda: self._cancel_requested(job.id)

        token = self._pools.token_for(
            video_encoder=target.video_encoder, render_node=render_job.options.render_node
        )
        token.acquire()
        try:
            self._render_and_finish(job, render_job)
        finally:
            token.release()

    def _refuse_running_output(self, job: Job) -> None:
        """Raise when another ``running`` job writes the output ``job`` would (D-9).

        Before the plan is rebuilt, so a refusal has adopted, probed and written nothing.
        The job's own row is ``running`` too and is skipped. This sees what the disk rule
        of :func:`default_build_job` cannot: another project with the same output
        directory, or an event the layout walk does not reach. Two jobs claimed together
        may both be refused; at most one renders.
        """
        today = date.today()
        own = _job_output(job, today=today)
        if own is None:
            return
        running = {
            other.id: other
            for other in self._store.list_by_status(JobStatus.RUNNING, kind=JobKind.RENDER)
            if other.id != job.id
        }
        claims = {job.id: own.path}
        for other in running.values():
            other_output = _job_output(other, today=today)
            if other_output is not None:
                claims[other.id] = other_output.path
        rivals = find_output_collisions(claims).get(job.id, ())
        if not rivals:
            return
        # A rival that is itself claimed on disk is not writing: the disk rule names the
        # real reason (and the shared sentence), so it is decided first.
        project_root = Path(job.project_root) if job.project_root else Path.cwd()
        _refuse_disk_collision(
            project_root, project_root / job.event_dir, load_project_config(project_root)
        )
        rival = running[rivals[0]]
        where = (
            f" of project {rival.project_root}" if rival.project_root != job.project_root else ""
        )
        raise OutputCollisionError(
            f"output path {own.relpath} is also being written by the running job for "
            f"{rival.event_dir}{where}; enqueue this event again once that job has ended"
        )

    @staticmethod
    def _is_fresh(render_job: RenderJob) -> bool:
        """The claim-time staleness recheck (§8.14, D-C3 site 3): re-evaluate the gate.

        Catches both disk changes made while the job was queued and reverts (an
        event back at its last-rendered state completes as skipped-``done`` rather
        than re-rendering); absorbs a requeued already-finished orphan by manifest
        verification rather than bare output existence. A job built without a
        fingerprint (a caller not wired for change-detection) is never fresh.
        """
        fingerprint = render_job.options.fingerprint
        if fingerprint is None:
            return False
        output_path = render_job.options.output_dir / output_relpath(render_job.plan.metadata)
        verdict = evaluate(render_job.options.event_dir, output_path, fingerprint)
        return not verdict.stale

    def _cancel_requested(self, job_id: uuid.UUID) -> bool:
        current = self._store.get(job_id)
        return current is not None and current.cancel_requested

    def _render_and_finish(self, job: Job, render_job: RenderJob) -> None:
        try:
            self._render(render_job)
        except RenderCancelledError:
            logger.info("job %s canceled", job.id)
            self._safe_transition(job.id, JobStatus.CANCELED)
            return
        except EngineError as exc:
            logger.error("job %s failed to render: %s", job.id, exc)
            self._safe_transition(job.id, JobStatus.FAILED, error=str(exc))
            return
        # Guarantee progress reaches 1.0 no later than the terminal transition,
        # even if the engine's on_progress never fired (e.g. the skip-if-exists path).
        self._store.set_progress(job.id, 1.0)
        self._safe_transition(job.id, JobStatus.DONE)

    def _safe_transition(
        self, job_id: uuid.UUID, status: JobStatus, *, error: Optional[str] = None
    ) -> None:
        """Transition, tolerating a race where the row left ``running`` under us.

        A graceful shutdown can requeue this job's row (D-S8) while this thread is
        still finishing up (it already returned from a possibly-slow render call);
        the row is no longer this thread's to write, so the write is skipped
        rather than raising.
        """
        try:
            self._store.transition(job_id, status, error=error)
        except IllegalJobTransitionError:
            logger.warning(
                "job %s: skipped %s transition; row already left running", job_id, status.value
            )


__all__ = ["Worker", "BuildJob", "KindHandler", "RunRender", "default_build_job"]
