"""Tests for the worker's dispatch by job kind (job-kind): a render takes its own path, a
registered handler runs any other kind, and an unhandled kind fails loud (real Postgres,
stubbed engine)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest
from sqlalchemy.orm import sessionmaker
from test_scheduler_worker import (
    _cpu_render_job,
    _failed_error,
    _guard_worker,
    _solo_pools,
    _write_event,
)

from auto_reel_ng.errors import EngineError, RenderCancelledError
from auto_reel_ng.persistence.engine import session_scope
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobKind, JobStatus
from auto_reel_ng.render import RenderJob, RenderResult
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.worker import KindHandler, Worker

pytestmark = pytest.mark.requires_db

PROJECT_ROOT = "/project"
MIDSOMMAR = "2024/2024-06-21 - Midsommar"


class _NoTokenPools(CapacityPools):
    """Pools whose token would raise: a job that reaches them took a capacity token."""

    def token_for(self, **_kwargs: Any) -> Any:
        raise AssertionError("a capacity token was requested")


def _unreachable_build(job: Job) -> RenderJob:
    raise AssertionError(f"the plan was rebuilt for {job.event_dir}")


def _worker(
    job_store: JobStore,
    *,
    handlers: dict[str, KindHandler] | None = None,
    build: Callable[[Job], RenderJob] = _unreachable_build,
    render: Callable[[RenderJob], RenderResult] | None = None,
    pools: CapacityPools | None = None,
) -> Worker:
    kwargs: dict[str, Any] = {"render": render} if render is not None else {}
    return Worker(
        job_store,
        worker_id="w1",
        pools=pools or _solo_pools(),
        poll_interval=0.01,
        build_job=build,
        kind_handlers=handlers,
        **kwargs,
    )


def _insert_job(factory: sessionmaker, event_dir: str, *, kind: str) -> None:
    with session_scope(factory) as session:
        session.add(Job(project_root=PROJECT_ROOT, event_dir=event_dir, kind=kind))


def test_a_render_job_is_processed_as_before(job_store: JobStore, tmp_path: Path) -> None:
    called: list[str] = []
    job_id = job_store.enqueue(PROJECT_ROOT, MIDSOMMAR)
    renders: list[int] = []

    def render(_rj: RenderJob) -> RenderResult:
        renders.append(1)
        return RenderResult(output_path=tmp_path / "o.mp4")

    worker = _worker(
        job_store,
        handlers={"proxy": lambda job: called.append(job.event_dir)},
        build=lambda job: _cpu_render_job(tmp_path),
        render=render,
    )

    assert worker.process_next() is True

    job = job_store.get(job_id)
    assert job is not None and (job.status, job.progress) == (JobStatus.DONE, 1.0)
    assert renders == [1] and called == []


def test_a_job_of_a_handled_kind_runs_its_handler(job_store: JobStore) -> None:
    seen: list[Job] = []
    job_id = job_store.enqueue(PROJECT_ROOT, MIDSOMMAR, kind=JobKind.PROXY)
    worker = _worker(
        job_store, handlers={"proxy": seen.append}, pools=_NoTokenPools(gpu_caps={}, cpu_cap=1)
    )

    assert worker.process_next() is True

    assert [job.id for job in seen] == [job_id] and seen[0].kind == "proxy"
    job = job_store.get(job_id)
    assert job is not None and (job.status, job.progress) == (JobStatus.DONE, 1.0)
    assert job.error is None


def test_a_known_kind_with_no_handler_fails_loud_and_the_worker_goes_on(
    job_store: JobStore, tmp_path: Path
) -> None:
    event = tmp_path / "2024" / "x"
    event.mkdir(parents=True)
    (event / "a.mp4").write_bytes(b"clip")
    before = sorted(p.name for p in event.iterdir())
    proxy_id = job_store.enqueue(str(tmp_path), "2024/x", kind=JobKind.PROXY)
    render_id = job_store.enqueue(str(tmp_path), "2024/y")
    builds: list[str] = []

    def build(job: Job) -> RenderJob:
        builds.append(job.event_dir)
        return _cpu_render_job(tmp_path)

    worker = _worker(
        job_store, build=build, render=lambda rj: RenderResult(output_path=tmp_path / "o.mp4")
    )

    assert worker.process_next() is True  # the render goes first, whatever the older job's kind
    render = job_store.get(render_id)
    assert render is not None and render.status == JobStatus.DONE and builds == ["2024/y"]
    assert worker.process_next() is True

    failed = job_store.get(proxy_id)
    assert failed is not None and failed.status == JobStatus.FAILED
    assert failed.error is not None and "proxy" in failed.error
    assert builds == ["2024/y"] and sorted(p.name for p in event.iterdir()) == before


def test_a_known_kind_with_no_handler_takes_no_capacity_token(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, MIDSOMMAR, kind=JobKind.PROXY)
    worker = _worker(job_store, pools=_NoTokenPools(gpu_caps={}, cpu_cap=1))

    assert worker.process_next() is True

    error = _failed_error(job_store, job_id)  # an AssertionError from the pools would read so
    assert "AssertionError" not in error and "proxy" in error


def test_a_job_of_an_unknown_kind_fails_loud_without_blocking_a_render(
    job_store: JobStore, jobs_session_factory: sessionmaker, tmp_path: Path
) -> None:
    _insert_job(jobs_session_factory, "2024/x", kind="thumbnails")
    render_id = job_store.enqueue(PROJECT_ROOT, "2024/y")
    worker = _worker(
        job_store,
        build=lambda job: _cpu_render_job(tmp_path),
        render=lambda rj: RenderResult(output_path=tmp_path / "o.mp4"),
    )

    assert worker.process_next() is True  # the render is claimed before a kind of any other name
    render = job_store.get(render_id)
    assert render is not None and render.status == JobStatus.DONE
    assert worker.process_next() is True

    failed = job_store.list_by_status(JobStatus.FAILED, kind="thumbnails")
    assert len(failed) == 1
    assert failed[0].error is not None and "thumbnails" in failed[0].error
    assert failed[0].requeue_count == 0
    assert job_store.list_by_status(JobStatus.QUEUED, kind=None) == []


def test_a_handlers_failure_is_isolated_and_typed(job_store: JobStore) -> None:
    first = job_store.enqueue(PROJECT_ROOT, "2024/a", kind=JobKind.PROXY)
    second = job_store.enqueue(PROJECT_ROOT, "2024/b", kind=JobKind.PROXY)
    third = job_store.enqueue(PROJECT_ROOT, "2024/c", kind=JobKind.PROXY)

    def handler(job: Job) -> None:
        if job.event_dir == "2024/a":
            raise EngineError("no audio stream")
        if job.event_dir == "2024/b":
            raise TypeError("boom")

    worker = _worker(job_store, handlers={"proxy": handler})

    for _ in range(3):
        assert worker.process_next() is True

    assert _failed_error(job_store, first) == "no audio stream"
    assert _failed_error(job_store, second) == "TypeError: boom"
    last = job_store.get(third)
    assert last is not None and last.status == JobStatus.DONE


def test_a_handlers_cancellation_ends_the_job_canceled(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, MIDSOMMAR, kind=JobKind.PROXY)

    def handler(_job: Job) -> None:
        raise RenderCancelledError("canceled")

    worker = _worker(job_store, handlers={"proxy": handler})

    assert worker.process_next() is True

    job = job_store.get(job_id)
    assert job is not None and job.status == JobStatus.CANCELED and job.error is None


def test_a_handler_cannot_take_over_the_render_path(job_store: JobStore) -> None:
    with pytest.raises(ValueError, match="render"):
        _worker(job_store, handlers={"render": lambda job: None})


def test_a_requeued_proxy_job_is_dispatched_again(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, MIDSOMMAR, kind=JobKind.PROXY)
    assert job_store.claim_next("dead-worker") is not None  # running when its worker died
    seen: list[str] = []
    worker = _worker(job_store, handlers={"proxy": lambda job: seen.append(job.kind)})

    assert worker.reconcile() == [job_id]
    assert worker.process_next() is True

    assert seen == ["proxy"]
    job = job_store.get(job_id)
    assert job is not None and job.status == JobStatus.DONE and job.requeue_count == 1


def test_a_running_proxy_job_does_not_hold_the_events_output(
    job_store: JobStore, runtime, make_clip, tmp_path: Path
) -> None:
    root = tmp_path / "proj"
    (root / "2024" / "x").mkdir(parents=True)
    make_clip("proj/2024/x/a.mp4", width=320, height=240, duration=1.0)
    _write_event(root, "2024/x", title="Midsommar")
    proxy_id = job_store.enqueue(str(root), "2024/x", kind=JobKind.PROXY)
    claimed = job_store.claim_next("other-worker")  # the proxy job is running elsewhere
    assert claimed is not None and claimed.id == proxy_id
    render_id = job_store.enqueue(str(root), "2024/x")
    worker, renders, _builds = _guard_worker(job_store, runtime=runtime)

    assert worker.process_next() is True

    render = job_store.get(render_id)
    assert render is not None and render.status == JobStatus.DONE, render and render.error
    assert renders == [1]
