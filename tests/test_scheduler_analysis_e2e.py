"""A real ``analysis`` job end to end (analysis-job 4.1): a real worker, the real handler, real
ffmpeg on generated clips, and Postgres. Covers the outcome (entries, a marker, ``failed`` naming
the bad clip), progress as stored, a forced re-run after the clip is fixed, and a worker stopped
mid-clip whose requeued job does not analyze its finished clip again."""

from __future__ import annotations

import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Sequence

import pytest

from auto_reel_ng.analysis.cache import clip_signal, read_entry, read_failure
from auto_reel_ng.analysis.models import SegmentKind
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobKind, JobStatus
from auto_reel_ng.render import RenderJob
from auto_reel_ng.scheduler.analysis_job import AnalysisJobHandler
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.worker import Worker

pytestmark = [pytest.mark.has_ffmpeg, pytest.mark.requires_db]


class CountingRuntime(FfmpegRuntime):
    """The real runtime, counting each hooked ffmpeg pass by the clip it decodes."""

    def __init__(self) -> None:
        super().__init__()
        self.passes: List[str] = []
        self.in_pass = threading.Event()

    def run_with_progress(self, args: Sequence[str], **kwargs: Any) -> str:
        clip = Path(list(args)[list(args).index("-i") + 1]).name
        self.passes.append(clip)
        self.in_pass.set()
        try:
            return super().run_with_progress(args, **kwargs)
        finally:
            self.in_pass.clear()


class RecordingStore(JobStore):
    """The real store, keeping every progress value written, in order."""

    def __init__(self, session_factory: Any) -> None:
        super().__init__(session_factory)
        self.written: List[float] = []

    def set_progress(self, job_id: uuid.UUID, fraction: float) -> None:
        self.written.append(fraction)
        super().set_progress(job_id, fraction)


def _ffmpeg(runtime: FfmpegRuntime, *args: str) -> None:
    subprocess.run(
        [runtime.ffmpeg_path, "-y", "-loglevel", "error", *args], check=True, capture_output=True
    )


def _black_then_motion(runtime: FfmpegRuntime, out: Path) -> None:
    _ffmpeg(
        runtime,
        *("-f", "lavfi", "-i", "color=black:s=320x240:r=25:d=3"),
        *("-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=3"),
        *("-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]"),
        *("-pix_fmt", "yuv420p", str(out)),
    )


def _plain(runtime: FfmpegRuntime, out: Path, *, size: str = "320x240", seconds: int = 4) -> None:
    _ffmpeg(
        runtime,
        *("-f", "lavfi", "-i", f"testsrc2=s={size}:r=25:d={seconds}"),
        *("-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)),
    )


def _truncated(runtime: FfmpegRuntime, out: Path) -> None:
    _plain(runtime, out)
    data = out.read_bytes()
    out.write_bytes(data[: len(data) // 2])  # the moov atom is at the end: unreadable


@pytest.fixture
def recording_store(jobs_session_factory: Any) -> RecordingStore:
    return RecordingStore(jobs_session_factory)


def _unreachable_build(job: Job) -> RenderJob:
    raise AssertionError(f"a render was built for {job.event_dir}")


def _worker(store: JobStore, runtime: CountingRuntime, stop: threading.Event) -> Worker:
    pools = CapacityPools(gpu_caps={}, cpu_cap=1)
    handler = AnalysisJobHandler(store=store, pools=pools, runtime=runtime, stop_event=stop)
    return Worker(
        store,
        worker_id=f"w-{uuid.uuid4().hex[:6]}",
        pools=pools,
        poll_interval=0.05,
        build_job=_unreachable_build,
        kind_handlers={JobKind.ANALYSIS.value: handler},
        stop_event=stop,
    )


def _entries(event: Path, names: Sequence[str]) -> Dict[str, Any]:
    return {name: read_entry(event, name, clip_signal(event / name)) for name in names}


def test_a_real_analysis_job_marks_the_bad_clip_and_a_forced_rerun_after_the_fix_is_done(
    recording_store: RecordingStore, tmp_path: Path
) -> None:
    store = recording_store
    root = tmp_path / "proj"
    event = root / "2024" / "2024-06-21 - Midsommar"
    event.mkdir(parents=True)
    runtime = CountingRuntime()
    _black_then_motion(runtime, event / "a.mp4")
    _plain(runtime, event / "b.mp4")
    _truncated(runtime, event / "c.mp4")
    rel = event.relative_to(root).as_posix()

    job_id = store.enqueue(str(root), rel, kind=JobKind.ANALYSIS)
    assert _worker(store, runtime, threading.Event()).process_next() is True

    job = store.get(job_id)
    assert job is not None and job.status == JobStatus.FAILED
    assert job.error is not None and job.error.startswith("1 of 3 clips failed: c.mp4: ")
    entries = _entries(event, ["a.mp4", "b.mp4", "c.mp4"])
    assert [(s.kind, round(s.start), round(s.end)) for s in entries["a.mp4"]] == [
        (SegmentKind.BLACK, 0, 3)
    ]
    assert entries["b.mp4"] == [] and entries["c.mp4"] is None
    assert read_failure(event, "c.mp4", clip_signal(event / "c.mp4")) is not None
    assert store.written == sorted(store.written) and max(store.written) < 1.0
    assert runtime.passes.count("a.mp4") == 2 and runtime.passes.count("b.mp4") == 2
    assert "c.mp4" not in runtime.passes  # its probe failed: no pass ran

    _plain(runtime, event / "c.mp4", seconds=5)  # replaced by a good copy
    runtime.passes.clear()
    forced = store.submit(str(root), rel, kind=JobKind.ANALYSIS, force=True).job_id
    assert _worker(store, runtime, threading.Event()).process_next() is True

    job = store.get(forced)
    assert job is not None and (job.status, job.progress) == (JobStatus.DONE, 1.0), job.error
    assert sorted(set(runtime.passes)) == ["a.mp4", "b.mp4", "c.mp4"]  # forced: all again
    assert _entries(event, ["c.mp4"])["c.mp4"] == []
    assert read_failure(event, "c.mp4", clip_signal(event / "c.mp4")) is None


def test_a_worker_stopped_mid_clip_requeues_and_the_rerun_skips_the_finished_clip(
    job_store: JobStore, tmp_path: Path
) -> None:
    root = tmp_path / "proj"
    event = root / "2024" / "2024-07-01 - Lång"
    event.mkdir(parents=True)
    runtime = CountingRuntime()
    _plain(runtime, event / "a.mp4")
    _plain(runtime, event / "b.mp4", size="1280x720", seconds=60)  # long enough to stop inside
    rel = event.relative_to(root).as_posix()
    job_id = job_store.enqueue(str(root), rel, kind=JobKind.ANALYSIS)

    stop = threading.Event()
    worker = _worker(job_store, runtime, stop)
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 60
    while not ("b.mp4" in runtime.passes and runtime.in_pass.is_set()):
        assert time.monotonic() < deadline, "clip b never started"
        time.sleep(0.02)
    stopped_at = time.monotonic()
    worker.stop()
    thread.join(timeout=20)

    assert not thread.is_alive() and time.monotonic() - stopped_at < 5
    job = job_store.get(job_id)
    assert job is not None and job.status == JobStatus.QUEUED
    assert _entries(event, ["a.mp4"])["a.mp4"] == []
    assert read_entry(event, "b.mp4", clip_signal(event / "b.mp4")) is None
    assert read_failure(event, "b.mp4", clip_signal(event / "b.mp4")) is None

    runtime.passes.clear()
    assert _worker(job_store, runtime, threading.Event()).process_next() is True

    job = job_store.get(job_id)
    assert job is not None and job.status == JobStatus.DONE, job.error
    assert "a.mp4" not in runtime.passes  # the finished clip cost no ffmpeg process
    assert runtime.passes == ["b.mp4", "b.mp4"]
