"""The automatic analysis sweep against the real store, worker and handler (analysis-auto-sweep
3.1): Postgres from the session fixture, real ffmpeg on tiny generated clips (never
auto-reel-media). Covers the job and the sweep agreeing (a swept, analyzed project is not swept
again), a replaced clip, a worker restart with a swept job queued or orphaned, and a queued
render keeping the sweep quiet and being claimed before the analysis job."""

from __future__ import annotations

import subprocess
import threading
import uuid
from pathlib import Path
from typing import List

import pytest

from auto_reel_ng.analysis.cache import clip_signal, read_entry, read_failure
from auto_reel_ng.config.project import ProjectConfig
from auto_reel_ng.errors import EngineError
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobKind, JobStatus
from auto_reel_ng.render import RenderJob
from auto_reel_ng.scheduler.analysis_job import AnalysisJobHandler
from auto_reel_ng.scheduler.analysis_sweep import AnalysisSweep
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.worker import Worker

pytestmark = [pytest.mark.has_ffmpeg, pytest.mark.requires_db]


def _clip(runtime: FfmpegRuntime, out: Path, *, seconds: int = 2) -> None:
    subprocess.run(
        [
            runtime.ffmpeg_path,
            *("-y", "-loglevel", "error", "-f", "lavfi"),
            *("-i", f"testsrc=s=160x120:r=10:d={seconds}"),
            *("-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)),
        ],
        check=True,
        capture_output=True,
    )


def _refuse_render(job: Job) -> RenderJob:
    raise EngineError(f"no render in this test ({job.event_dir})")


class Lab:
    """A scratch project, the real store and a real worker with the real analysis handler."""

    def __init__(self, store: JobStore, root: Path, runtime: FfmpegRuntime) -> None:
        self.store = store
        self.root = root
        self.runtime = runtime
        self.events = {}
        for name in ("2024-01-01 - Old", "2024-06-01 - New"):
            event = root / "2024" / name
            event.mkdir(parents=True)
            _clip(runtime, event / "a.mp4")
            self.events[name.split(" - ")[1]] = event

    def rel(self, name: str) -> str:
        return self.events[name].relative_to(self.root).as_posix()

    def sweep(self) -> AnalysisSweep:
        return AnalysisSweep(self.store, self.root, ProjectConfig(), max_events=2)

    def worker(self, worker_id: str = "") -> Worker:
        pools = CapacityPools(gpu_caps={}, cpu_cap=1)
        handler = AnalysisJobHandler(store=self.store, pools=pools, runtime=self.runtime)
        return Worker(
            self.store,
            worker_id=worker_id or f"w-{uuid.uuid4().hex[:6]}",
            pools=pools,
            poll_interval=0.05,
            build_job=_refuse_render,
            kind_handlers={JobKind.ANALYSIS.value: handler},
        )

    def drain(self) -> None:
        """Process every queued job, in the worker's claim order."""
        worker = self.worker()
        while worker.process_next():
            pass

    def all_jobs(self) -> List[Job]:
        return [
            job
            for status in JobStatus
            for job in self.store.list_by_status(status, project_root=str(self.root), kind=None)
        ]

    def active_analysis(self, name: str) -> List[Job]:
        return [
            job
            for job in self.all_jobs()
            if job.kind == JobKind.ANALYSIS
            and job.event_dir == self.rel(name)
            and job.status in (JobStatus.QUEUED, JobStatus.RUNNING)
        ]


@pytest.fixture
def lab(job_store: JobStore, tmp_path: Path, runtime: FfmpegRuntime) -> Lab:
    return Lab(job_store, tmp_path / "proj", runtime)


def test_swept_events_are_analyzed_and_the_next_sweep_finds_nothing(lab: Lab) -> None:
    report = lab.sweep().sweep_once()
    assert report.enqueued == (lab.rel("New"), lab.rel("Old"))  # newest first

    lab.drain()
    for job in lab.all_jobs():
        assert (job.kind, job.status) == (JobKind.ANALYSIS, JobStatus.DONE), job.error
    for event in lab.events.values():
        assert read_entry(event, "a.mp4", clip_signal(event / "a.mp4")) is not None

    assert lab.sweep().sweep_once().enqueued == ()  # the job and the sweep agree


def test_a_failure_marked_clip_is_not_swept_again(lab: Lab) -> None:
    bad = lab.events["New"] / "b.mp4"
    bad.write_bytes(b"not a video at all, ffprobe cannot read this")
    lab.sweep().sweep_once()
    lab.drain()
    new_job = lab.store.latest_by_project(str(lab.root), kind=JobKind.ANALYSIS)[lab.rel("New")]
    assert new_job.status == JobStatus.FAILED and "b.mp4" in (new_job.error or "")
    assert read_failure(lab.events["New"], "b.mp4", clip_signal(bad)) is not None

    for _ in range(2):
        assert lab.sweep().sweep_once().enqueued == ()


def test_replacing_one_clip_sweeps_only_its_event(lab: Lab) -> None:
    lab.sweep().sweep_once()
    lab.drain()
    _clip(lab.runtime, lab.events["Old"] / "a.mp4", seconds=3)  # re-copied: new size and mtime

    assert lab.sweep().sweep_once().enqueued == (lab.rel("Old"),)
    lab.drain()
    assert lab.sweep().sweep_once().enqueued == ()


def test_a_restart_with_a_swept_job_queued_or_orphaned_keeps_one_active_job(lab: Lab) -> None:
    lab.sweep().sweep_once()  # both events queued
    # A worker claims "New" and dies mid-job: the row stays running under a dead worker id.
    orphan = lab.store.claim_next("dead-worker", exclude_kinds=())
    assert orphan is not None and orphan.event_dir == lab.rel("New")

    # The restart: a new sweep and a new worker's reconcile, in either order.
    assert lab.sweep().sweep_once().busy  # "Old" is still queued: quiet
    requeued = lab.worker().reconcile()
    assert requeued == [orphan.id]
    assert lab.sweep().sweep_once().busy

    assert [job.id for job in lab.active_analysis("New")] == [orphan.id]
    assert len(lab.active_analysis("Old")) == 1


def test_a_queued_render_keeps_the_sweep_quiet_and_is_claimed_first(lab: Lab) -> None:
    lab.sweep().sweep_once()  # both events' analysis queued
    render = lab.store.submit(str(lab.root), lab.rel("Old"), kind=JobKind.RENDER)
    assert render.created

    _clip(lab.runtime, lab.events["New"] / "b.mp4")  # more due work appears
    assert lab.sweep().sweep_once().busy

    worker = lab.worker()
    assert worker.process_next()
    first = lab.store.get(render.job_id)
    assert first is not None and first.status == JobStatus.FAILED  # claimed (and refused) first
    queued = lab.store.list_by_status(JobStatus.QUEUED, project_root=str(lab.root), kind=None)
    assert sorted(job.kind for job in queued) == [JobKind.ANALYSIS, JobKind.ANALYSIS]


def test_the_sweep_thread_stops_with_the_worker(lab: Lab) -> None:
    stop = threading.Event()
    sweep = lab.sweep()
    thread = threading.Thread(target=sweep.run, args=(stop, 300.0), daemon=True)
    thread.start()
    deadline_jobs = 0
    for _ in range(200):
        deadline_jobs = len(lab.all_jobs())
        if deadline_jobs == 2:
            break
        stop.wait(0.05)
    stop.set()
    thread.join(timeout=2)
    assert not thread.is_alive() and deadline_jobs == 2
