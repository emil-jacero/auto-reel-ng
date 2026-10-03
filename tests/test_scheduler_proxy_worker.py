"""Tests for the worker with a ``proxy`` handler (proxy-job): the outcome mapping, the CPU token,
render-before-proxy admission, ``worker.proxy_slots`` and a graceful stop (real Postgres; the
preparation of a clip is replaced by a fake)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

import pytest
from test_scheduler_worker import (
    _cpu_render_job,
    _failed_error,
    _gpu_render_job,
    _solo_pools,
    _write_event,
)

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.errors import FfmpegCancelledError, ProxyError
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobKind, JobStatus
from auto_reel_ng.proxies import ProxySettings
from auto_reel_ng.render import RenderJob, RenderResult
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


class Fixture:
    """A project with events, a proxy handler on a fake ``prepare_clip``, and a worker."""

    def __init__(self, job_store: JobStore, tmp_path: Path, *, cpu_cap: int = 1) -> None:
        self.store = job_store
        self.root = tmp_path / "proj"
        self.cache = tmp_path / "cache"
        self.pools = CapacityPools(gpu_caps={NODE: 1}, cpu_cap=cpu_cap)
        self.stop = threading.Event()
        self.prepared: List[str] = []
        self.gate: Optional[threading.Event] = None  # when set, a clip waits for it
        self.started = threading.Semaphore(0)
        self.cleaned: List[str] = []
        self.cleanup_seconds = 0.0  # how long a clip takes to clean up after itself
        self.renders: List[str] = []
        self.tmp_path = tmp_path

    def event(self, name: str, clips: tuple[str, ...] = ("a.mp4",), title: str = "") -> str:
        rel = f"2024/{name}"
        _write_event(self.root, rel, title=title or f"Title {name}", clips=clips)
        return rel

    def prepare(self, clip: Path, **kwargs: Any) -> Any:
        self.prepared.append(f"{clip.parent.name}/{clip.name}")
        self.started.release()
        try:
            while self.gate is not None and not self.gate.is_set():
                if kwargs["should_cancel"]():
                    raise FfmpegCancelledError("canceled")
                time.sleep(0.01)
            kwargs["on_progress"](1.0)
        finally:
            time.sleep(self.cleanup_seconds)
            self.cleaned.append(clip.name)
        return object()

    def handler(self, prepare: Optional[Callable[..., Any]] = None) -> ProxyJobHandler:
        return ProxyJobHandler(
            store=self.store,
            pools=self.pools,
            runtime=None,  # type: ignore[arg-type]
            profile=CPUProfile(),
            stop_event=self.stop,
            prepare=prepare or self.prepare,
            load_settings=lambda root: ProxySettings(self.cache),
        )

    def worker(
        self,
        *,
        proxy_slots: int = 1,
        render: str = "gpu",
        cpu_events: tuple[str, ...] = (),
        prepare: Optional[Callable[..., Any]] = None,
        render_fn: Optional[Callable[[RenderJob], RenderResult]] = None,
    ) -> Worker:
        def build(job: Job) -> RenderJob:
            if render == "gpu" and job.event_dir not in cpu_events:
                return _gpu_render_job(self.tmp_path, title=job.event_dir)
            return _cpu_render_job(self.tmp_path, title=job.event_dir)

        def run_render(render_job: RenderJob) -> RenderResult:
            self.renders.append(render_job.plan.metadata.title or "")
            return RenderResult(output_path=self.tmp_path / "o.mp4")

        return Worker(
            self.store,
            worker_id="w1",
            pools=self.pools,
            poll_interval=0.01,
            build_job=build,
            render=render_fn or run_render,
            kind_handlers={JobKind.PROXY.value: self.handler(prepare)},
            proxy_slots=proxy_slots,
            stop_event=self.stop,
        )

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


@pytest.fixture
def fx(job_store: JobStore, tmp_path: Path) -> Fixture:
    return Fixture(job_store, tmp_path)


# --------------------------------------------------------------------------- #
# outcomes
# --------------------------------------------------------------------------- #


def test_a_proxy_job_prepares_its_event_and_ends_done_with_progress_one(fx: Fixture) -> None:
    rel = fx.event("a", clips=("a.mp4", "b.mp4"))
    job_id = fx.proxy(rel)

    assert fx.worker().process_next() is True

    job = fx.store.get(job_id)
    assert job is not None and (job.status, job.progress) == (JobStatus.DONE, 1.0)
    assert fx.prepared == ["a/a.mp4", "a/b.mp4"]


def test_a_failed_clip_fails_the_job_with_the_count_and_releases_the_token(fx: Fixture) -> None:
    rel = fx.event("a", clips=("a.mp4", "b.mp4", "c.mp4"))
    job_id = fx.proxy(rel)

    def prepare(clip: Path, **kwargs: Any) -> Any:
        if clip.name == "b.mp4":
            raise ProxyError(str(clip), "ffmpeg failed on the cpu path")
        kwargs["on_progress"](1.0)
        return object()

    worker = fx.worker(prepare=prepare)
    assert worker.process_next() is True

    assert _failed_error(fx.store, job_id).startswith("1 of 3 clips failed: b.mp4: ffmpeg failed")
    assert fx.pools.cpu_token().acquire(blocking=False)  # the token is free again
    fx.pools.cpu_token().release()


def test_an_unexpected_error_fails_the_job_with_its_type_and_the_worker_keeps_claiming(
    fx: Fixture,
) -> None:
    first = fx.proxy(fx.event("a"))
    second = fx.proxy(fx.event("b"))
    calls: List[str] = []

    def prepare(clip: Path, **kwargs: Any) -> Any:
        calls.append(clip.parent.name)
        if clip.parent.name == "a":
            raise TypeError("boom")
        kwargs["on_progress"](1.0)
        return object()

    worker = fx.worker(prepare=prepare)

    assert worker.process_next() and worker.process_next()

    assert _failed_error(fx.store, first) == "TypeError: boom"
    assert fx.status(second) == JobStatus.DONE
    assert fx.pools.cpu_token().acquire(blocking=False)
    fx.pools.cpu_token().release()


def test_a_cancel_requested_during_a_clip_ends_the_job_canceled(fx: Fixture) -> None:
    job_id = fx.proxy(fx.event("a", clips=("a.mp4", "b.mp4")))
    fx.gate = threading.Event()  # the first clip never finishes on its own
    thread = fx.start(fx.worker())

    assert fx.started.acquire(timeout=10)
    fx.store.request_cancel(job_id)
    wait_until(lambda: fx.status(job_id) == JobStatus.CANCELED)

    fx.stop.set()
    thread.join(timeout=5)
    assert fx.prepared == ["a/a.mp4"]  # the second clip never started


def test_a_proxy_job_of_a_colliding_event_is_not_refused(fx: Fixture) -> None:
    """Two events claim one output path; the render-only collision check does not apply."""
    a = fx.event("a", title="Midsommar")
    b = fx.event("b", title="Midsommar")
    ids = [fx.proxy(a), fx.proxy(b)]
    worker = fx.worker()

    assert worker.process_next() and worker.process_next()

    assert [fx.status(i) for i in ids] == [JobStatus.DONE, JobStatus.DONE]
    assert sorted(fx.prepared) == ["a/a.mp4", "b/a.mp4"]


# --------------------------------------------------------------------------- #
# capacity and priority
# --------------------------------------------------------------------------- #


def test_a_gpu_render_starts_while_a_proxy_job_holds_the_cpu_token(fx: Fixture) -> None:
    proxy_id = fx.proxy(fx.event("a"))
    fx.gate = threading.Event()
    thread = fx.start(fx.worker())
    assert fx.started.acquire(timeout=10)
    render_id = fx.render(fx.event("b"))

    wait_until(lambda: fx.status(render_id) == JobStatus.DONE)

    assert fx.status(proxy_id) == JobStatus.RUNNING  # the proxy job is still working
    assert fx.renders == ["2024/b"]
    fx.gate.set()
    wait_until(lambda: fx.status(proxy_id) == JobStatus.DONE)
    fx.stop.set()
    thread.join(timeout=5)


def test_a_queued_render_is_claimed_before_an_older_proxy_job(fx: Fixture) -> None:
    proxy_id = fx.proxy(fx.event("a"))
    render_id = fx.render(fx.event("b"))
    worker = fx.worker()

    assert worker.process_next() is True
    assert (fx.status(render_id), fx.status(proxy_id)) == (JobStatus.DONE, JobStatus.QUEUED)
    assert worker.process_next() is True
    assert fx.status(proxy_id) == JobStatus.DONE


def test_a_waiting_proxy_job_is_not_claimed_and_does_not_block_a_render(fx: Fixture) -> None:
    first = fx.proxy(fx.event("a"))
    fx.gate = threading.Event()
    thread = fx.start(fx.worker())
    assert fx.started.acquire(timeout=10)
    second = fx.proxy(fx.event("b"))
    render_id = fx.render(fx.event("c"))

    wait_until(lambda: fx.status(render_id) == JobStatus.DONE)

    assert fx.status(first) == JobStatus.RUNNING  # not interrupted by the render
    assert fx.status(second) == JobStatus.QUEUED  # not claimed: proxy_slots is full
    fx.gate.set()
    wait_until(lambda: fx.status(second) == JobStatus.DONE)
    assert fx.status(first) == JobStatus.DONE
    fx.stop.set()
    thread.join(timeout=5)


def test_a_cpu_render_waiting_behind_a_proxy_job_does_not_hold_back_a_gpu_render(
    fx: Fixture,
) -> None:
    """The proxy job's in-flight slot is not counted against the claim bound (review finding)."""
    proxy_id = fx.proxy(fx.event("p", clips=("a.mp4", "b.mp4")))
    fx.gate = threading.Event()
    thread = fx.start(fx.worker(cpu_events=("2024/c",)))
    assert fx.started.acquire(timeout=10)  # the proxy job holds the one CPU token, in clip a
    cpu_id = fx.render(fx.event("c"))  # claimed, then waits for that token
    wait_until(lambda: fx.status(cpu_id) == JobStatus.RUNNING)
    gpu_id = fx.render(fx.event("g"))

    wait_until(lambda: fx.status(gpu_id) == JobStatus.DONE)  # not stuck behind the CPU render

    assert fx.renders == ["2024/g"]
    assert fx.status(cpu_id) == JobStatus.RUNNING
    fx.gate.set()  # clip a ends; the proxy job gives the token to the CPU render before clip b
    wait_until(lambda: fx.status(cpu_id) == JobStatus.DONE)
    wait_until(lambda: fx.status(proxy_id) == JobStatus.DONE)
    assert fx.renders == ["2024/g", "2024/c"]
    assert fx.prepared == ["p/a.mp4", "p/b.mp4"]
    fx.stop.set()
    thread.join(timeout=5)


def test_a_proxy_job_does_not_start_its_next_clip_while_a_render_runs(fx: Fixture) -> None:
    proxy_id = fx.proxy(fx.event("p", clips=("a.mp4", "b.mp4")))
    fx.gate = threading.Event()
    release_render = threading.Event()

    def render(render_job: RenderJob) -> RenderResult:
        fx.renders.append(render_job.plan.metadata.title or "")
        assert release_render.wait(timeout=10)
        return RenderResult(output_path=fx.tmp_path / "o.mp4")

    thread = fx.start(fx.worker(render_fn=render))
    assert fx.started.acquire(timeout=10)  # clip a is encoding
    render_id = fx.render(fx.event("g"))
    wait_until(lambda: fx.status(render_id) == JobStatus.RUNNING)

    fx.gate.set()  # clip a finishes while the render runs
    time.sleep(1.5)  # longer than the poll of the yield

    assert fx.prepared == ["p/a.mp4"]  # clip b waits for the render
    assert fx.status(proxy_id) == JobStatus.RUNNING
    release_render.set()
    wait_until(lambda: fx.status(proxy_id) == JobStatus.DONE, timeout=15)
    assert fx.prepared == ["p/a.mp4", "p/b.mp4"]
    fx.stop.set()
    thread.join(timeout=5)


def test_proxy_jobs_run_one_at_a_time_oldest_first(fx: Fixture) -> None:
    ids = [fx.proxy(fx.event(name)) for name in ("a", "b", "c")]
    running_at_once: List[int] = []
    active = 0
    lock = threading.Lock()

    def prepare(clip: Path, **kwargs: Any) -> Any:
        nonlocal active
        with lock:
            active += 1
            running_at_once.append(active)
        time.sleep(0.05)
        kwargs["on_progress"](1.0)
        fx.prepared.append(clip.parent.name)
        with lock:
            active -= 1
        return object()

    worker = fx.worker(prepare=prepare)
    thread = fx.start(worker)

    wait_until(lambda: all(fx.status(i) == JobStatus.DONE for i in ids))
    fx.stop.set()
    thread.join(timeout=5)

    assert fx.prepared == ["a", "b", "c"]
    assert max(running_at_once) == 1


def test_two_proxy_slots_run_two_jobs_together(job_store: JobStore, tmp_path: Path) -> None:
    fx = Fixture(job_store, tmp_path, cpu_cap=2)
    ids = [fx.proxy(fx.event(name)) for name in ("a", "b")]
    fx.gate = threading.Event()
    thread = fx.start(fx.worker(proxy_slots=2))

    assert fx.started.acquire(timeout=10) and fx.started.acquire(timeout=10)

    assert [fx.status(i) for i in ids] == [JobStatus.RUNNING, JobStatus.RUNNING]
    fx.gate.set()
    wait_until(lambda: all(fx.status(i) == JobStatus.DONE for i in ids))
    fx.stop.set()
    thread.join(timeout=5)


def test_render_claim_order_is_unchanged_without_proxy_jobs(fx: Fixture) -> None:
    ids = [fx.render(fx.event(name)) for name in ("a", "b", "c")]
    worker = fx.worker()

    for _ in ids:
        assert worker.process_next() is True

    assert fx.renders == ["2024/a", "2024/b", "2024/c"]


# --------------------------------------------------------------------------- #
# graceful stop
# --------------------------------------------------------------------------- #


def test_a_stop_requeues_the_proxy_job_and_its_thread_cleans_up_before_run_returns(
    fx: Fixture,
) -> None:
    job_id = fx.proxy(fx.event("a", clips=("a.mp4", "b.mp4")))
    fx.gate = threading.Event()  # the clip runs until it is told to stop
    fx.cleanup_seconds = 0.5
    worker = fx.worker()
    thread = fx.start(worker)
    assert fx.started.acquire(timeout=10)

    worker.stop()
    thread.join(timeout=15)

    assert not thread.is_alive()
    job = fx.store.get(job_id)
    assert job is not None and job.status == JobStatus.QUEUED
    assert fx.cleaned == ["a.mp4"]  # the clip's cleanup ran before run() returned
    assert fx.prepared == ["a/a.mp4"]
