"""The ``proxy`` job (D-21, ``proxy-job``): prepare every clip of one event for the timeline.

A claimed ``proxy`` job lists its event folder with :func:`~auto_reel_ng.event.scan_event`
(every clip on disk, IGNORED ones too; ``reel.yaml`` is never read, so editorial state can
neither add work nor invalidate any) and, in listing order, makes each distinct cache entry's
proxy and then its filmstrip (:func:`~auto_reel_ng.proxies.prepare_clip`). It writes only into
the proxy cache of the job's own project: no render checks apply, no fingerprint is recorded.

The job holds one CPU token while it prepares clips and no GPU token (its libx264 encode is CPU
work even on the hybrid path), so a GPU render runs beside it. The handler owns the token (the
worker takes none for a non-render kind). Progress is weighted by source size, which is a
``stat`` rather than a probe, with the clip in flight contributing its own fraction.

The job yields to renders: it does not start a clip while a ``render`` job is running (experiment
007 measured a render beside a proxy job at 1.3 to 1.6 times its solo time). A clip already
encoding finishes. While it waits it gives its CPU token back, because a running render may be
waiting for that very token.

Failures: a clip that cannot be prepared is recorded and the others still are; the job then
fails naming every failed clip. A fault of the cache directory ends the job at once. A cancel,
or the worker being stopped, ends the encode at ffmpeg's next poll and leaves nothing in the cache.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..accel.profiles import AccelProfile
from ..config.project import load_project_config
from ..errors import (
    EngineError,
    FfmpegCancelledError,
    FilmstripError,
    ProxyError,
    RenderCancelledError,
)
from ..event import scan_event
from ..ffmpeg.runtime import FfmpegRuntime
from ..persistence.job_store import JobStore
from ..persistence.models import Job, JobKind, JobStatus
from ..proxies import PreparedClip, ProxySettings, prepare_clip, proxy_key, resolve_proxy_settings
from ..thumbs import one_line_cause
from .pools import CapacityPools
from .progress import ThrottledProgress
from .worker import JobInterrupted

logger = logging.getLogger(__name__)

#: Seconds between looks at the cancel flag while the job waits for its CPU token.
TOKEN_POLL_S = 0.5
#: Seconds between looks at the running renders while the job yields to them.
YIELD_POLL_S = 1.0
#: How many failed clips an error message spells out before it says "and N more".
MAX_NAMED_FAILURES = 3
#: What the progress of a job with a failed clip is capped at: ``1.0`` means "done".
FAILED_PROGRESS_CAP = 0.99

#: ``prepare_clip``'s signature, so a test can stand in for the real preparation.
PrepareClip = Callable[..., PreparedClip]
#: Loads the settings of a project root (the project's own ``config.yaml``).
LoadSettings = Callable[[Path], ProxySettings]


class ProxyJobError(EngineError):
    """A ``proxy`` job ended with failed clips; the message counts and names them."""


class _Hold:
    """The job's CPU token and whether this job holds it now."""

    def __init__(self, token: threading.BoundedSemaphore) -> None:
        self.token = token
        self.held = False

    def release(self) -> None:
        """Give the token back if held; safe to call twice."""
        if self.held:
            self.held = False
            self.token.release()


@dataclass(frozen=True)
class _Work:
    """One distinct cache entry of the event: the clip that stands for it and its weight."""

    clip: Path
    identities: tuple[str, ...]
    weight: int


def load_project_proxy_settings(project_root: Path) -> ProxySettings:
    """The ``proxies.*`` settings of the project at ``project_root`` (D-2).

    Raises:
        EngineError: ``config.yaml`` does not load, or the cache directory is refused.
    """
    config = load_project_config(project_root)
    return resolve_proxy_settings(config, project_root)


class ProxyJobHandler:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """The ``proxy`` kind's :data:`~auto_reel_ng.scheduler.worker.KindHandler`."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        store: JobStore,
        pools: CapacityPools,
        runtime: FfmpegRuntime,
        profile: AccelProfile,
        render_node: Optional[str] = None,
        stop_event: Optional[threading.Event] = None,
        prepare: PrepareClip = prepare_clip,
        load_settings: LoadSettings = load_project_proxy_settings,
    ) -> None:
        self._store = store
        self._pools = pools
        self._runtime = runtime
        self._profile = profile
        self._render_node = render_node
        self._stop = stop_event if stop_event is not None else threading.Event()
        self._prepare = prepare
        self._load_settings = load_settings

    def __call__(self, job: Job) -> None:
        """Prepare the job's event; return for ``done``, raise for ``failed`` or ``canceled``.

        Raises:
            RenderCancelledError: the job was canceled.
            JobInterrupted: the worker is stopping; the row is left for its requeue.
            ProxyJobError: one or more clips could not be prepared.
            ProxyCacheError: the proxy cache directory is unusable.
            EngineError: the project's settings are refused, or the event cannot be listed.
        """
        project_root = Path(job.project_root) if job.project_root else Path.cwd()
        event_dir = project_root / job.event_dir
        settings = self._load_settings(
            project_root
        )  # before the token: a refusal waits for nothing
        work = self._plan(event_dir)
        hold = _Hold(self._pools.cpu_token())
        try:
            self._run(job, settings, work, hold)
        finally:
            hold.release()

    def _cancel_check(self, job: Job) -> Callable[[], bool]:
        def should_cancel() -> bool:
            if self._stop.is_set():
                return True
            current = self._store.get(job.id)
            return current is not None and current.cancel_requested

        return should_cancel

    def _stop_or_cancel(self, job: Job) -> None:
        """Raise the right interruption now if the worker is stopping or the job was canceled."""
        if self._stop.is_set():
            raise JobInterrupted(f"job {job.id}: the worker is stopping")
        current = self._store.get(job.id)
        if current is not None and current.cancel_requested:
            raise RenderCancelledError(f"proxy job {job.id} was canceled")

    def _acquire(self, hold: _Hold, job: Job) -> None:
        """Wait for the CPU token, still answering a cancel or a stop while waiting."""
        while not hold.token.acquire(timeout=TOKEN_POLL_S):
            self._stop_or_cancel(job)
        hold.held = True
        self._stop_or_cancel(job)

    def _render_running(self) -> bool:
        return bool(self._store.list_by_status(JobStatus.RUNNING, kind=JobKind.RENDER))

    def _take_turn(self, job: Job, hold: _Hold) -> None:
        """Hold the CPU token at a moment when no render is running.

        While a render runs the token is given back and the job waits, so a render that is
        itself waiting for the CPU token is never blocked by the job that yields to it.
        """
        while True:
            if not hold.held:
                self._acquire(hold, job)
            if not self._render_running():
                return
            hold.release()
            while self._render_running():
                self._stop_or_cancel(job)
                self._stop.wait(YIELD_POLL_S)

    @staticmethod
    def _plan(event_dir: Path) -> List[_Work]:
        """Every distinct cache entry the event's folder lists, in listing order, with weights."""
        try:
            identities = scan_event(event_dir).identities
        except OSError as exc:
            raise ProxyError(str(event_dir), f"cannot list the event folder: {exc}") from exc
        groups: Dict[str, List[str]] = {}
        for identity in identities:
            try:
                key = proxy_key(event_dir / identity)
            except OSError:
                key = f"unstatted:{identity}"  # the clip vanished; preparing it reports why
            groups.setdefault(key, []).append(identity)
        return [
            _Work(
                clip=event_dir / members[0],
                identities=tuple(members),
                weight=_weight(event_dir / members[0]),
            )
            for members in groups.values()
        ]

    def _run(self, job: Job, settings: ProxySettings, work: List[_Work], hold: _Hold) -> None:
        progress = ThrottledProgress(self._store, job.id)
        should_cancel = self._cancel_check(job)
        total = sum(item.weight for item in work) or 1
        finished = 0
        failures: List[str] = []
        for item in work:
            self._stop_or_cancel(job)
            self._take_turn(job, hold)
            base = finished

            def on_clip(fraction: float, base: int = base, weight: int = item.weight) -> None:
                value = (base + weight * fraction) / total
                progress(min(value, FAILED_PROGRESS_CAP) if failures else value)

            try:
                self._prepare(
                    item.clip,
                    settings=settings,
                    runtime=self._runtime,
                    profile=self._profile,
                    render_node=self._render_node,
                    on_progress=on_clip,
                    should_cancel=should_cancel,
                )
            except FfmpegCancelledError as exc:
                self._stop_or_cancel(job)  # a stop is not a cancel
                raise RenderCancelledError(f"proxy job {job.id} was canceled") from exc
            # A ProxyCacheError is not caught: it is not a clip's fault, so it ends the job at once
            # (every remaining clip would fail the same way).
            except (ProxyError, FilmstripError) as exc:
                reason = one_line_cause(exc.reason, item.clip)
                logger.error("job %s: %s: %s", job.id, item.identities[0], exc.reason)
                failures.extend(f"{identity}: {reason}" for identity in item.identities)
            finished += item.weight
            if not failures:
                progress(finished / total)
        if failures:
            clips = sum(len(item.identities) for item in work)
            raise ProxyJobError(_failure_message(failures, clips))


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
    "ProxyJobError",
    "ProxyJobHandler",
    "load_project_proxy_settings",
]
