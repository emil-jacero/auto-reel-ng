"""Tests for the worker with an ``analysis`` handler (analysis-job): claim order render > proxy >
analysis, ``worker.analysis_slots``, the render in-flight bound, the CPU token and the yield
(real Postgres; detection and proxy preparation are replaced by fakes)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

import pytest
from test_scheduler_worker import _cpu_render_job, _failed_error, _gpu_render_job, _write_event

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.analysis.models import Segment
from auto_reel_ng.errors import AnalysisError, FfmpegCancelledError
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobKind, JobStatus
from auto_reel_ng.proxies import ProxySettings
from auto_reel_ng.render import RenderJob, RenderResult
from auto_reel_ng.scheduler.analysis_job import AnalysisJobHandler
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.proxy_job import ProxyJobHandler
from auto_reel_ng.scheduler.worker import Worker

pytestmark = pytest.mark.requires_db

NODE = "/dev/dri/renderD128"


def wait_until(condition: Callable[[], bool], *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("timed out waiting for the condition")


class Fixture:  # pylint: disable=too-many-instance-attributes
    """A project, an ``analysis`` and a ``proxy`` handler on fakes, and a worker."""

    def __init__(self, job_store: JobStore, tmp_path: Path, *, cpu_cap: int = 1) -> None:
        self.store = job_store
        self.root = tmp_path / "proj"
        self.tmp_path = tmp_path
        self.pools = CapacityPools(gpu_caps={NODE: 1}, cpu_cap=cpu_cap)
        self.stop = threading.Event()
        self.analyzed: List[str] = []
        self.prepared: List[str] = []
        self.renders: List[str] = []
        self.gate: Optional[threading.Event] = None  # when set, a clip waits for it
        self.started = threading.Semaphore(0)
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()
        self.fail: set[str] = set()

    def event(self, name: str, clips: tuple[str, ...] = ("a.mp4",)) -> str:
        rel = f"2024/{name}"
        _write_event(self.root, rel, title=f"Title {name}", clips=clips)
        return rel

    def analyze(self, clip: Path, **kwargs: Any) -> List[Segment]:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        self.analyzed.append(f"{clip.parent.name}/{clip.name}")
        self.started.release()
        try:
            if clip.parent.name in self.fail:
                raise AnalysisError(f"Cannot analyze undecodable clip {clip}: bad")
            while self.gate is not None and not self.gate.is_set():
                if kwargs["should_cancel"]():
                    raise FfmpegCancelledError("canceled")
                time.sleep(0.01)
            kwargs["on_progress"](1.0)
            return []
        finally:
            with self.lock:
                self.active -= 1

    def prepare(self, clip: Path, **kwargs: Any) -> Any:
        self.prepared.append(f"{clip.parent.name}/{clip.name}")
        kwargs["on_progress"](1.0)
        return object()

    def worker(
        self,
        *,
        analysis_slots: int = 1,
        cpu_events: tuple[str, ...] = (),
        render_fn: Optional[Callable[[RenderJob], RenderResult]] = None,
    ) -> Worker:
        def build(job: Job) -> RenderJob:
            if job.event_dir in cpu_events:
                return _cpu_render_job(self.tmp_path, title=job.event_dir)
            return _gpu_render_job(self.tmp_path, title=job.event_dir)

        def run_render(render_job: RenderJob) -> RenderResult:
            self.renders.append(render_job.plan.metadata.title or "")
            return RenderResult(output_path=self.tmp_path / "o.mp4")

        analysis = AnalysisJobHandler(
            store=self.store,
            pools=self.pools,
            runtime=None,  # type: ignore[arg-type]
            stop_event=self.stop,
            analyze=self.analyze,
        )
        proxy = ProxyJobHandler(
            store=self.store,
            pools=self.pools,
            runtime=None,  # type: ignore[arg-type]
            profile=CPUProfile(),
            stop_event=self.stop,
            prepare=self.prepare,
            load_settings=lambda root: ProxySettings(self.tmp_path / "cache"),
        )
        return Worker(
            self.store,
            worker_id="w1",
            pools=self.pools,
            poll_interval=0.01,
            build_job=build,
            render=render_fn or run_render,
            kind_handlers={JobKind.ANALYSIS.value: analysis, JobKind.PROXY.value: proxy},
            analysis_slots=analysis_slots,
            stop_event=self.stop,
        )

    def analysis(self, rel: str) -> Any:
        return self.store.enqueue(str(self.root), rel, kind=JobKind.ANALYSIS)

    def proxy(self, rel: str) -> Any:
        return self.store.enqueue(str(self.root), rel, kind=JobKind.PROXY)

    def render(self, rel: str) -> Any:
        return self.store.enqueue(str(self.root), rel)

    def status(self, job_id: Any) -> JobStatus:
        job = self.store.get(job_id)
        assert job is not None
        return job.status

    def start(self, worker: Worker) -> threading.Thread:
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()
        return thread

    def finish(self, thread: threading.Thread) -> None:
        if self.gate is not None:
            self.gate.set()
        self.stop.set()
        thread.join(timeout=10)


@pytest.fixture
def fx(job_store: JobStore, tmp_path: Path) -> Fixture:
    return Fixture(job_store, tmp_path)


# --------------------------------------------------------------------------- #
# outcomes through the worker
# --------------------------------------------------------------------------- #


def test_an_analysis_job_ends_done_with_progress_one(fx: Fixture) -> None:
    job_id = fx.analysis(fx.event("a", clips=("a.mp4", "b.mp4")))

    assert fx.worker().process_next() is True

    job = fx.store.get(job_id)
    assert job is not None and (job.status, job.progress) == (JobStatus.DONE, 1.0)
    assert fx.analyzed == ["a/a.mp4", "a/b.mp4"]


def test_a_failed_analysis_job_releases_the_token_and_a_cpu_render_starts_at_once(
    fx: Fixture,
) -> None:
    fx.fail = {"a"}
    analysis_id = fx.analysis(fx.event("a"))
    worker = fx.worker(cpu_events=("2024/c",))
    assert worker.process_next() is True
    render_id = fx.render(fx.event("c"))

    assert worker.process_next() is True

    assert _failed_error(fx.store, analysis_id).startswith("1 of 1 clips failed: a.mp4: ")
    assert fx.status(render_id) == JobStatus.DONE
    assert fx.renders == ["2024/c"]


# --------------------------------------------------------------------------- #
# claim order and slots
# --------------------------------------------------------------------------- #


def test_a_newer_render_and_a_newer_proxy_job_go_first(fx: Fixture) -> None:
    analysis_id = fx.analysis(fx.event("an"))  # oldest
    proxy_id = fx.proxy(fx.event("px"))
    render_id = fx.render(fx.event("rd"))  # newest
    worker = fx.worker()
    order: List[str] = []

    for _ in range(3):
        assert worker.process_next() is True
        order.append(
            next(
                name
                for name, job_id in (
                    ("render", render_id),
                    ("proxy", proxy_id),
                    ("analysis", analysis_id),
                )
                if fx.status(job_id) == JobStatus.DONE and name not in order
            )
        )

    assert order == ["render", "proxy", "analysis"]


def test_a_higher_priority_does_not_put_an_analysis_job_before_a_proxy_job(
    fx: Fixture,
) -> None:
    analysis_id = fx.analysis(fx.event("an"))
    proxy_id = fx.proxy(fx.event("px"))
    _bump(fx.store, analysis_id)
    worker = fx.worker()

    assert worker.process_next() is True

    assert (fx.status(proxy_id), fx.status(analysis_id)) == (JobStatus.DONE, JobStatus.QUEUED)


def _bump(store: JobStore, job_id: Any) -> None:
    """Raise a job's ``priority`` straight in the table (no store API sets it)."""
    from auto_reel_ng.persistence.engine import (  # pylint: disable=import-outside-toplevel
        session_scope,
    )

    with session_scope(store._session_factory) as session:  # pylint: disable=protected-access
        job = session.get(Job, job_id)
        assert job is not None
        job.priority = 100


def test_one_analysis_job_at_a_time_by_default(fx: Fixture) -> None:
    first = fx.analysis(fx.event("a"))
    second = fx.analysis(fx.event("b"))
    fx.gate = threading.Event()
    thread = fx.start(fx.worker())
    assert fx.started.acquire(timeout=10)

    time.sleep(0.3)  # many polls
    assert (fx.status(first), fx.status(second)) == (JobStatus.RUNNING, JobStatus.QUEUED)
    fx.gate.set()
    wait_until(lambda: fx.status(second) == JobStatus.DONE)
    assert fx.max_active == 1
    fx.finish(thread)


def test_a_waiting_analysis_job_does_not_block_a_gpu_render(fx: Fixture) -> None:
    first = fx.analysis(fx.event("a"))
    fx.gate = threading.Event()
    thread = fx.start(fx.worker())
    assert fx.started.acquire(timeout=10)
    second = fx.analysis(fx.event("b"))
    render_id = fx.render(fx.event("g"))

    wait_until(lambda: fx.status(render_id) == JobStatus.DONE)

    assert fx.status(first) == JobStatus.RUNNING  # never interrupted for another job
    assert fx.status(second) == JobStatus.QUEUED
    fx.finish(thread)


def test_analysis_jobs_in_flight_do_not_use_up_the_render_bound(fx: Fixture) -> None:
    """Two analysis jobs in flight (one working, one waiting for the CPU token) on a worker
    whose render bound is two (one GPU, one CPU slot) still leave room for a GPU render."""
    ids = [fx.analysis(fx.event(name)) for name in ("a", "b")]
    fx.gate = threading.Event()
    thread = fx.start(fx.worker(analysis_slots=2))
    assert fx.started.acquire(timeout=10)
    wait_until(lambda: all(fx.status(i) == JobStatus.RUNNING for i in ids))
    render_id = fx.render(fx.event("g"))

    wait_until(lambda: fx.status(render_id) == JobStatus.DONE)

    assert fx.max_active == 1  # the second analysis job waits for the one CPU token
    fx.finish(thread)


def test_renders_are_never_starved_by_ten_queued_analysis_jobs(fx: Fixture) -> None:
    ids = [fx.analysis(fx.event(f"an{n}")) for n in range(10)]
    thread = fx.start(fx.worker())
    claimed_after: List[float] = []

    for n in range(3):
        render_id = fx.render(fx.event(f"rd{n}"))
        queued_at = time.monotonic()
        wait_until(lambda render_id=render_id: fx.status(render_id) == JobStatus.DONE)
        claimed_after.append(time.monotonic() - queued_at)

    wait_until(lambda: all(fx.status(i) == JobStatus.DONE for i in ids), timeout=20)
    fx.finish(thread)

    assert fx.max_active == 1
    assert max(claimed_after) < 2.0, claimed_after
    assert fx.renders == ["2024/rd0", "2024/rd1", "2024/rd2"]


def test_an_analysis_job_starts_no_clip_while_a_proxy_job_runs(
    fx: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from auto_reel_ng.scheduler import analysis_job as analysis_job_module  # pylint: disable=import-outside-toplevel

    monkeypatch.setattr(analysis_job_module, "YIELD_POLL_S", 0.02)
    proxy_id = fx.proxy(fx.event("px"))
    assert fx.store.claim_next("other-worker") is not None  # the proxy job runs elsewhere
    analysis_id = fx.analysis(fx.event("an"))
    worker = fx.worker()
    # process_next, not run: run's startup reconcile would requeue the other worker's job.
    thread = threading.Thread(target=worker.process_next, daemon=True)
    thread.start()

    wait_until(lambda: fx.status(analysis_id) == JobStatus.RUNNING)
    time.sleep(0.3)
    assert fx.analyzed == []  # claimed, but it yields to the running proxy job
    fx.store.transition(proxy_id, JobStatus.DONE)
    thread.join(timeout=10)
    assert fx.status(analysis_id) == JobStatus.DONE
    assert fx.analyzed == ["an/a.mp4"]


def test_the_worker_refuses_an_analysis_slots_below_one(fx: Fixture) -> None:
    with pytest.raises(ValueError, match="analysis_slots"):
        fx.worker(analysis_slots=0)
