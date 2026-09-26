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
from pathlib import Path
from typing import Callable, Optional

from ..accel.profiles.base import AccelProfile
from ..cli.build import build_render_job_from_event, prepare_and_persist
from ..config.project import default_output_dir, load_project_config, resolve_look_defaults
from ..errors import EngineError, IllegalJobTransitionError, RenderCancelledError
from ..ffmpeg.runtime import FfmpegRuntime
from ..persistence.job_store import JobStore
from ..persistence.models import Job, JobStatus
from ..render import RenderJob, RenderResult, output_relpath, render_movie, resolve_target
from ..staleness.fingerprint import compute_fingerprint
from ..staleness.gate import evaluate
from .pools import CapacityPools
from .progress import ThrottledProgress

logger = logging.getLogger(__name__)

BuildJob = Callable[[Job], RenderJob]
RunRender = Callable[[RenderJob], RenderResult]


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

    event = prepare_and_persist(event_dir)
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


class Worker:
    """Polls the job store, rebuilds each claimed job's plan, and renders it.

    ``build_job``/``render`` are injectable seams (default: :func:`default_build_job`
    wired to a real engine, and :func:`~auto_reel_ng.render.render_movie`) so tests
    can stub the engine, mirroring the CLI's own patched-engine tests.
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
    ) -> None:
        self._store = job_store
        self._worker_id = worker_id
        self._pools = pools
        self._poll_interval = poll_interval
        self._build_job = build_job
        self._render = render
        self._device_filter = device_filter
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
        try:
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


__all__ = ["Worker", "BuildJob", "RunRender", "default_build_job"]
