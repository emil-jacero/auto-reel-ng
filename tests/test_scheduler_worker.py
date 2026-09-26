"""Tests for the job-scheduler :class:`Worker`: claim/execute, capacity, reconcile,
shutdown, and cooperative cancellation (real Postgres — D-P1/T3, stubbed engine)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import List, Tuple
from unittest.mock import Mock

import pytest

from auto_reel_ng.accel.models import AcceleratorCapabilities, Device, Vendor
from auto_reel_ng.accel.profiles import CPUProfile, VaapiProfile
from auto_reel_ng.cli.adoption import persist, prepare_event
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.errors import ProbeError, RenderError
from auto_reel_ng.event.plan import RenderPlan, ResolvedChapter, ResolvedClip
from auto_reel_ng.persistence.engine import session_scope
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobStatus
from auto_reel_ng.probe import probe_media
from auto_reel_ng.probe.metadata import ClipMetadata
from auto_reel_ng.reel.document import Metadata
from auto_reel_ng.render import RenderJob, RenderOptions, RenderResult
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.worker import Worker, _render_job, default_build_job

pytestmark = pytest.mark.requires_db

PROJECT_ROOT = "/project"


def _clip(identity: str = "a.mp4", *, is_hdr: bool = False) -> ClipMetadata:
    return ClipMetadata(
        path=Path(identity),
        duration=1.0,
        fps=30.0,
        video_codec="h264",
        profile=None,
        width=320,
        height=240,
        sample_aspect_ratio=None,
        display_aspect_ratio=None,
        pix_fmt="yuv420p",
        video_bitrate=None,
        rotation=None,
        color_transfer="smpte2084" if is_hdr else None,
        is_hdr=is_hdr,
        audio=None,
        creation_time=None,
    )


def _solo_pools(*, gpu_caps=None, cpu_cap: int = 1) -> CapacityPools:
    return CapacityPools(gpu_caps=gpu_caps or {}, cpu_cap=cpu_cap)


def _cpu_render_job(tmp_path: Path, *, title: str = "Movie") -> RenderJob:
    facts = {"a.mp4": _clip()}
    plan = RenderPlan(
        metadata=Metadata(title=title),
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    options = RenderOptions(
        event_dir=tmp_path, output_dir=tmp_path / "out", clip_facts=facts, runtime=Mock()
    )
    return RenderJob(plan=plan, profile=CPUProfile(), options=options)


def _amd_profile() -> VaapiProfile:
    caps = AcceleratorCapabilities(
        vendor=Vendor.AMD,
        usable=True,
        device=Device(
            id="pci-0000:03:00.0",
            vendor=Vendor.AMD,
            name="RX 9070 XT",
            render_node="/dev/dri/renderD128",
        ),
        pad_filter="pad_vaapi",
        can_overlay_hw=False,
        can_tonemap_hw=False,
        usable_encoders={"h264": "h264_vaapi"},
        decode_method="vaapi",
    )
    return VaapiProfile(caps)


def _gpu_render_job(tmp_path: Path, *, title: str = "GPU Movie") -> RenderJob:
    facts = {"a.mp4": _clip()}
    plan = RenderPlan(
        metadata=Metadata(title=title),
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=tmp_path / "out",
        clip_facts=facts,
        runtime=Mock(),
        render_node="/dev/dri/renderD128",
    )
    return RenderJob(plan=plan, profile=_amd_profile(), options=options)


# --------------------------------------------------------------------------- #
# 3.4 claim/execute loop
# --------------------------------------------------------------------------- #


def test_worker_processes_a_job_to_done(job_store: JobStore, tmp_path: Path) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    render_job = _cpu_render_job(tmp_path)

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=lambda job: render_job,
        render=lambda rj: RenderResult(output_path=tmp_path / "out.mp4"),
    )
    assert worker.process_next() is True
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.DONE
    assert job.progress == 1.0


def test_worker_returns_false_when_queue_empty(job_store: JobStore) -> None:
    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=lambda job: (_ for _ in ()).throw(AssertionError("unreachable")),
    )
    assert worker.process_next() is False


def test_idle_worker_keeps_polling_and_claims_promptly(job_store: JobStore, tmp_path: Path) -> None:
    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.05,
        build_job=lambda job: _cpu_render_job(tmp_path),
        render=lambda rj: RenderResult(output_path=tmp_path / "o.mp4"),
    )
    run_thread = threading.Thread(target=worker.run, daemon=True)
    run_thread.start()

    # The queue is empty: let the worker idle-poll a few times without crashing
    # or busy-looping before any job exists.
    time.sleep(0.2)

    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    deadline = time.monotonic() + 2.0
    status = None
    while time.monotonic() < deadline:
        status = job_store.get(job_id).status  # type: ignore[union-attr]
        if status == JobStatus.DONE:
            break
        time.sleep(0.02)

    worker.stop()
    run_thread.join(timeout=2)
    assert status == JobStatus.DONE


def test_worker_marks_job_failed_when_build_fails(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")

    def stub_build(job: Job) -> RenderJob:
        raise ProbeError("clip unreadable")

    worker = Worker(
        job_store, worker_id="w1", pools=_solo_pools(), poll_interval=0.01, build_job=stub_build
    )
    assert worker.process_next() is True
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.FAILED
    assert job.error is not None and "clip unreadable" in job.error


def test_worker_marks_job_failed_when_render_fails(job_store: JobStore, tmp_path: Path) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    render_job = _cpu_render_job(tmp_path)

    def stub_render(rj: RenderJob) -> RenderResult:
        raise RenderError("concat failed")

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=lambda job: render_job,
        render=stub_render,
    )
    assert worker.process_next() is True
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.FAILED
    assert job.error is not None and "concat failed" in job.error


def test_worker_claims_and_processes_jobs_in_fifo_order(
    job_store: JobStore, tmp_path: Path
) -> None:
    ids_in_order = [job_store.enqueue(PROJECT_ROOT, f"event-{i}") for i in range(3)]
    order: List = []

    def stub_build(job: Job) -> RenderJob:
        order.append(job.id)
        return _cpu_render_job(tmp_path)

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=stub_build,
        render=lambda rj: RenderResult(output_path=tmp_path / "o.mp4"),
    )
    while worker.process_next():
        pass
    assert order == ids_in_order


def test_worker_device_filter_never_claims_a_job_pinned_to_a_different_device(
    job_store: JobStore, tmp_path: Path
) -> None:
    # A worker bound to one render_node (device_filter, D-CLI4/4c) must only
    # claim "auto" jobs or ones pinned to its own device — never a job pinned
    # to a different device id. Exercises the CLI/Worker pass-through of the
    # already store-tested claim_next(device_filter=...) primitive end-to-end.
    auto_id = job_store.enqueue(PROJECT_ROOT, "auto-event", device="auto")
    other_id = job_store.enqueue(PROJECT_ROOT, "other-event", device="renderD129")

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=lambda job: _cpu_render_job(tmp_path),
        render=lambda rj: RenderResult(output_path=tmp_path / "o.mp4"),
        device_filter="renderD128",
    )
    assert worker.process_next() is True  # claims the "auto" job
    assert worker.process_next() is False  # the renderD129 job is not eligible here

    auto_job = job_store.get(auto_id)
    other_job = job_store.get(other_id)
    assert auto_job is not None and auto_job.status == JobStatus.DONE
    assert other_job is not None and other_job.status == JobStatus.QUEUED


def test_claimed_job_renders_from_current_disk_state_not_enqueue_time(
    job_store: JobStore, runtime, make_clip, tmp_path: Path
) -> None:
    # D-S1: a job row is an event reference, never a frozen plan. Seed a reel.yaml
    # (the state "at enqueue time"), enqueue, then edit reel.yaml on disk before
    # the worker ever claims it — the render must reflect the edit.
    event_dir = tmp_path / "2024-01-01 - Original Title"
    event_dir.mkdir()
    make_clip("2024-01-01 - Original Title/a.mp4", width=320, height=240, duration=1.0)

    persist(prepare_event(event_dir, adopt=True))
    reel_path = event_dir / "reel.yaml"
    assert "Original Title" in reel_path.read_text(encoding="utf-8")

    job_id = job_store.enqueue(str(tmp_path), event_dir.name, device="auto")

    # The edit happens strictly after enqueue, before the claim below.
    reel_path.write_text(
        reel_path.read_text(encoding="utf-8").replace("Original Title", "Edited Title"),
        encoding="utf-8",
    )

    def build(job: Job) -> RenderJob:
        return default_build_job(job, runtime=runtime, profile=CPUProfile(), render_node=None)

    worker = Worker(
        job_store, worker_id="w1", pools=_solo_pools(), poll_interval=0.01, build_job=build
    )
    assert worker.process_next() is True

    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.DONE
    assert (default_output_dir(tmp_path) / "2024" / "Edited Title.mp4").exists()
    assert not (default_output_dir(tmp_path) / "2024" / "Original Title.mp4").exists()


# --------------------------------------------------------------------------- #
# 3.6 capacity behavior
# --------------------------------------------------------------------------- #


def test_two_gpu_jobs_serialize_while_a_cpu_job_runs_concurrently(
    job_store: JobStore, tmp_path: Path
) -> None:
    gpu_a = job_store.enqueue(PROJECT_ROOT, "gpu-a")
    gpu_b = job_store.enqueue(PROJECT_ROOT, "gpu-b")
    cpu_job = job_store.enqueue(PROJECT_ROOT, "cpu-job")

    jobs_by_event = {
        "gpu-a": _gpu_render_job(tmp_path, title="GPU A"),
        "gpu-b": _gpu_render_job(tmp_path, title="GPU B"),
        "cpu-job": _cpu_render_job(tmp_path, title="CPU"),
    }

    intervals: List[Tuple[str, float, float]] = []
    lock = threading.Lock()

    def stub_build(job: Job) -> RenderJob:
        return jobs_by_event[job.event_dir]

    def stub_render(rj: RenderJob) -> RenderResult:
        label = rj.plan.metadata.title or ""
        start = time.monotonic()
        time.sleep(0.2)
        end = time.monotonic()
        with lock:
            intervals.append((label, start, end))
        return RenderResult(output_path=tmp_path / "o.mp4")

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(gpu_caps={"/dev/dri/renderD128": 1}, cpu_cap=1),
        poll_interval=0.01,
        build_job=stub_build,
        render=stub_render,
    )

    run_thread = threading.Thread(target=worker.run, daemon=True)
    run_thread.start()
    deadline = time.monotonic() + 5.0
    ids = {gpu_a, gpu_b, cpu_job}
    while time.monotonic() < deadline:
        statuses = {job_store.get(i).status for i in ids}  # type: ignore[union-attr]
        if statuses <= {JobStatus.DONE}:
            break
        time.sleep(0.05)
    worker.stop()
    run_thread.join(timeout=2)

    assert all(job_store.get(i).status == JobStatus.DONE for i in ids)  # type: ignore[union-attr]
    assert len(intervals) == 3

    by_label = {label: (start, end) for label, start, end in intervals}
    gpu1, gpu2 = by_label["GPU A"], by_label["GPU B"]

    def _overlaps(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
        return a[0] < b[1] and b[0] < a[1]

    assert not _overlaps(gpu1, gpu2)  # cap-1 GPU pool: the two GPU jobs serialize
    cpu_interval = by_label["CPU"]
    assert _overlaps(cpu_interval, gpu1) or _overlaps(cpu_interval, gpu2)


def test_claim_loop_bounds_inflight_jobs_to_total_capacity(
    job_store: JobStore, tmp_path: Path
) -> None:
    # More jobs are queued than the CPU pool's capacity; the claim loop must
    # never have more concurrently claimed-and-spawned jobs than
    # pools.total_capacity, even though claim_next itself can't know a job's
    # classification (GPU vs CPU) before it is claimed and its plan rebuilt.
    ids = [job_store.enqueue(PROJECT_ROOT, f"event-{i}") for i in range(5)]

    release = threading.Event()
    lock = threading.Lock()
    current = 0
    max_concurrent = 0

    def stub_render(rj: RenderJob) -> RenderResult:
        nonlocal current, max_concurrent
        with lock:
            current += 1
            max_concurrent = max(max_concurrent, current)
        release.wait(timeout=5)
        with lock:
            current -= 1
        return RenderResult(output_path=tmp_path / "o.mp4")

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(cpu_cap=2),
        poll_interval=0.01,
        build_job=lambda job: _cpu_render_job(tmp_path),
        render=stub_render,
    )
    run_thread = threading.Thread(target=worker.run, daemon=True)
    run_thread.start()

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and max_concurrent < 2:
        time.sleep(0.02)
    # Give the loop ample further opportunity to over-claim if the bound were broken.
    time.sleep(0.3)
    assert max_concurrent == 2

    release.set()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        statuses = {job_store.get(i).status for i in ids}  # type: ignore[union-attr]
        if statuses <= {JobStatus.DONE}:
            break
        time.sleep(0.05)
    worker.stop()
    run_thread.join(timeout=2)

    assert max_concurrent == 2  # never exceeded the cpu_cap=2 bound
    assert all(job_store.get(i).status == JobStatus.DONE for i in ids)  # type: ignore[union-attr]


class _SpySemaphore:
    """Wraps a real semaphore, counting acquire/release calls made through it."""

    def __init__(self, real) -> None:
        self._real = real
        self.acquire_calls = 0
        self.release_calls = 0

    def acquire(self, *args, **kwargs):  # noqa: D102
        self.acquire_calls += 1
        return self._real.acquire(*args, **kwargs)

    def release(self, *args, **kwargs) -> None:  # noqa: D102
        self.release_calls += 1
        self._real.release(*args, **kwargs)


def test_worker_holds_exactly_one_token_for_the_whole_job(
    job_store: JobStore, tmp_path: Path
) -> None:
    # D-S3 (4a): even a job whose pipeline mixes CPU filter stages with a
    # hardware encode (the HDR case: CPU tonemap -> VAAPI encode) holds only its
    # GPU token from start to finish — no mid-job handoff. The worker classifies
    # once (by the *resolved final encoder*, independent of what ffmpeg mixes
    # internally) and acquires/releases exactly once around the whole render.
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    render_node = "/dev/dri/renderD128"

    facts = {"a.mp4": _clip(is_hdr=True)}  # forces an internal CPU tonemap fallback
    plan = RenderPlan(
        metadata=Metadata(title="HDR Movie"),
        chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
    )
    options = RenderOptions(
        event_dir=tmp_path,
        output_dir=tmp_path / "out",
        clip_facts=facts,
        runtime=Mock(),
        render_node=render_node,
    )
    render_job = RenderJob(plan=plan, profile=_amd_profile(), options=options)

    real_pools = _solo_pools(gpu_caps={render_node: 1}, cpu_cap=1)
    gpu_semaphore = real_pools.token_for(video_encoder="h264_vaapi", render_node=render_node)
    spy = _SpySemaphore(gpu_semaphore)

    class _SpyPools:
        def token_for(self, *, video_encoder: str, render_node):  # noqa: D102
            token = real_pools.token_for(video_encoder=video_encoder, render_node=render_node)
            assert token is gpu_semaphore  # this job really does classify as GPU
            return spy

    render_calls = []

    def stub_render(rj: RenderJob) -> RenderResult:
        # Simulate the multi-step (CPU + GPU) work happening *while* the single
        # token is held: no acquire/release should occur during this call.
        assert (spy.acquire_calls, spy.release_calls) == (1, 0)
        render_calls.append(1)
        return RenderResult(output_path=tmp_path / "out.mp4")

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_SpyPools(),
        poll_interval=0.01,
        build_job=lambda job: render_job,
        render=stub_render,
    )
    assert worker.process_next() is True

    assert render_calls == [1]
    assert (spy.acquire_calls, spy.release_calls) == (1, 1)
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.DONE


# --------------------------------------------------------------------------- #
# 4.1 startup reconcile
# --------------------------------------------------------------------------- #


def test_reconcile_requeues_an_orphaned_running_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("dead-worker")

    worker = Worker(
        job_store,
        worker_id="alive-worker",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=lambda job: (_ for _ in ()).throw(AssertionError("unreachable")),
    )
    requeued = worker.reconcile()

    assert requeued == [job_id]
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.worker_id is None


def test_reconciled_finished_orphan_completes_without_rerendering(
    job_store: JobStore, tmp_path: Path
) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("dead-worker")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "Movie.mp4").write_bytes(b"already a complete render")

    render_job = RenderJob(
        plan=RenderPlan(
            metadata=Metadata(title="Movie"),
            chapters=(ResolvedChapter(name="", clips=(ResolvedClip(identity="a.mp4"),)),),
        ),
        profile=CPUProfile(),
        options=RenderOptions(
            event_dir=tmp_path, output_dir=out_dir, clip_facts={"a.mp4": _clip()}, runtime=Mock()
        ),
    )

    # No `render` override: the real render_movie must hit its skip-if-exists path
    # (a Mock() runtime would blow up loudly if a real render were attempted).
    worker = Worker(
        job_store,
        worker_id="alive-worker",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=lambda job: render_job,
    )

    worker.reconcile()
    assert worker.process_next() is True
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.DONE
    assert (out_dir / "Movie.mp4").read_bytes() == b"already a complete render"


# --------------------------------------------------------------------------- #
# 4.2 graceful shutdown
# --------------------------------------------------------------------------- #


def test_sigterm_mid_render_requeues_the_in_flight_job(job_store: JobStore, tmp_path: Path) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    started = threading.Event()
    release = threading.Event()

    def stub_render(rj: RenderJob) -> RenderResult:
        started.set()
        release.wait(timeout=5)
        return RenderResult(output_path=tmp_path / "o.mp4")

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.02,
        build_job=lambda job: _cpu_render_job(tmp_path),
        render=stub_render,
    )
    run_thread = threading.Thread(target=worker.run, daemon=True)
    run_thread.start()
    assert started.wait(timeout=2)

    worker.stop()
    run_thread.join(timeout=2)
    assert not run_thread.is_alive()

    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.QUEUED
    release.set()  # let the stubbed render return so the daemon thread exits cleanly


def test_clean_shutdown_with_no_inflight_work_leaves_nothing_running(job_store: JobStore) -> None:
    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=lambda job: (_ for _ in ()).throw(AssertionError("unreachable")),
    )
    run_thread = threading.Thread(target=worker.run, daemon=True)
    run_thread.start()
    time.sleep(0.05)
    worker.stop()
    run_thread.join(timeout=2)
    assert not run_thread.is_alive()


# --------------------------------------------------------------------------- #
# 5.1 cooperative cancellation
# --------------------------------------------------------------------------- #


def test_worker_cancels_a_running_job_between_segments(
    job_store: JobStore, runtime, make_clip, tmp_path: Path
) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    clip_a = make_clip("a.mp4", width=320, height=240, duration=1.0)
    clip_b = make_clip("b.mp4", width=320, height=240, duration=1.0)
    facts = {
        "a.mp4": probe_media(clip_a, runtime=runtime),
        "b.mp4": probe_media(clip_b, runtime=runtime),
    }
    plan = RenderPlan(
        metadata=Metadata(title="Movie"),
        look={"target_resolution": [640, 480]},
        chapters=(
            ResolvedChapter(name="Intro", clips=(ResolvedClip(identity="a.mp4"),)),
            ResolvedChapter(name="Main", clips=(ResolvedClip(identity="b.mp4"),)),
        ),
    )
    out_dir = tmp_path / "out"
    options = RenderOptions(
        event_dir=tmp_path, output_dir=out_dir, clip_facts=facts, runtime=runtime
    )
    render_job = RenderJob(plan=plan, profile=CPUProfile(), options=options)

    def stub_build(job: Job) -> RenderJob:
        # Request cancellation once the job is claimed (running) but before the
        # worker's should_cancel check fires at the first segment boundary.
        job_store.request_cancel(job.id)
        return render_job

    worker = Worker(
        job_store, worker_id="w1", pools=_solo_pools(), poll_interval=0.01, build_job=stub_build
    )
    assert worker.process_next() is True
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.CANCELED
    assert not (out_dir / "Movie.mp4").exists()
    assert not (out_dir / "Movie.mp4.part").exists()


def test_cancel_requested_pre_claim_cancels_promptly_without_the_worker(
    job_store: JobStore,
) -> None:
    # A queued job's request_cancel path (job-store level) needs no worker/engine
    # involvement at all: it cancels directly and is never claimed.
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.request_cancel(job_id)
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.CANCELED
    assert job_store.claim_next("worker") is None


# --------------------------------------------------------------------------- #
# 6.1 claim-time staleness recheck (change-detection, §8.14)
# --------------------------------------------------------------------------- #


def _seed_project(tmp_path: Path, make_clip, *, name: str = "2024-01-01 - Reunion") -> Path:
    event_dir = tmp_path / name
    event_dir.mkdir()
    make_clip(f"{name}/a.mp4", width=320, height=240, duration=1.0)
    persist(prepare_event(event_dir, adopt=True))
    return event_dir


def _counting_render():
    calls: List[int] = []

    def render(rj: RenderJob) -> RenderResult:
        calls.append(1)
        return _render_job(rj)

    return render, calls


def test_reverted_event_skips_at_claim_time_without_ffmpeg(
    job_store: JobStore, runtime, make_clip, tmp_path: Path
) -> None:
    event_dir = _seed_project(tmp_path, make_clip)
    render, calls = _counting_render()

    def build(job: Job) -> RenderJob:
        return default_build_job(job, runtime=runtime, profile=CPUProfile(), render_node=None)

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=build,
        render=render,
    )

    first_id = job_store.enqueue(str(tmp_path), event_dir.name)
    assert worker.process_next() is True  # real render: no manifest yet
    assert job_store.get(first_id).status == JobStatus.DONE  # type: ignore[union-attr]
    assert len(calls) == 1

    # Nothing changed on disk since the last render (equivalent to a revert to
    # exactly the last-rendered state): the second job must complete without
    # any ffmpeg process.
    second_id = job_store.enqueue(str(tmp_path), event_dir.name)
    assert worker.process_next() is True
    assert len(calls) == 1  # unchanged: no second render

    job = job_store.get(second_id)
    assert job is not None
    assert job.status == JobStatus.DONE
    assert job.progress == 1.0


def test_forced_job_never_rechecks_and_always_renders(
    job_store: JobStore, runtime, make_clip, tmp_path: Path
) -> None:
    event_dir = _seed_project(tmp_path, make_clip)
    render, calls = _counting_render()

    def build(job: Job) -> RenderJob:
        return default_build_job(job, runtime=runtime, profile=CPUProfile(), render_node=None)

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=build,
        render=render,
    )

    job_store.enqueue(str(tmp_path), event_dir.name)
    assert worker.process_next() is True
    assert len(calls) == 1

    # Unchanged disk state, but force=True: must render again regardless.
    forced_id = job_store.enqueue(str(tmp_path), event_dir.name, force=True)
    assert worker.process_next() is True
    assert len(calls) == 2

    job = job_store.get(forced_id)
    assert job is not None
    assert job.status == JobStatus.DONE


def test_stale_job_replaces_the_outdated_output(
    job_store: JobStore, runtime, make_clip, tmp_path: Path
) -> None:
    event_dir = _seed_project(tmp_path, make_clip)
    render, calls = _counting_render()

    def build(job: Job) -> RenderJob:
        return default_build_job(job, runtime=runtime, profile=CPUProfile(), render_node=None)

    worker = Worker(
        job_store,
        worker_id="w1",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=build,
        render=render,
    )

    job_store.enqueue(str(tmp_path), event_dir.name)
    assert worker.process_next() is True
    assert len(calls) == 1
    output_path = default_output_dir(tmp_path) / "2024" / "Reunion.mp4"
    assert output_path.exists()
    first_mtime = output_path.stat().st_mtime_ns

    # The clip changes (different duration -> different content signal): the
    # event is stale via clip_set even though an output already exists.
    make_clip(f"{event_dir.name}/a.mp4", width=320, height=240, duration=2.0)
    stale_id = job_store.enqueue(str(tmp_path), event_dir.name)
    assert worker.process_next() is True
    assert len(calls) == 2  # rendered again, replacing (not skipping) the output

    job = job_store.get(stale_id)
    assert job is not None
    assert job.status == JobStatus.DONE
    assert output_path.stat().st_mtime_ns != first_mtime


def test_requeued_finished_orphan_absorbed_by_manifest(
    job_store: JobStore, jobs_session_factory, runtime, make_clip, tmp_path: Path
) -> None:
    event_dir = _seed_project(tmp_path, make_clip)

    def build(job: Job) -> RenderJob:
        return default_build_job(job, runtime=runtime, profile=CPUProfile(), render_node=None)

    worker = Worker(
        job_store, worker_id="w1", pools=_solo_pools(), poll_interval=0.01, build_job=build
    )
    job_id = job_store.enqueue(str(tmp_path), event_dir.name)
    assert worker.process_next() is True  # real render: manifest + output now exist
    assert job_store.get(job_id).status == JobStatus.DONE  # type: ignore[union-attr]

    # Simulate a crash after the render finished (manifest written) but before
    # the DONE transition landed: the row is still "running" under a dead worker.
    with session_scope(jobs_session_factory) as session:
        row = session.get(Job, job_id)
        row.status = JobStatus.RUNNING
        row.worker_id = "dead-worker"

    alive = Worker(
        job_store,
        worker_id="alive-worker",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=build,
    )
    requeued = alive.reconcile()
    assert requeued == [job_id]

    render, calls = _counting_render()
    absorber = Worker(
        job_store,
        worker_id="w2",
        pools=_solo_pools(),
        poll_interval=0.01,
        build_job=build,
        render=render,
    )
    assert absorber.process_next() is True
    assert calls == []  # absorbed by the manifest: no re-render

    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.DONE
    assert job.progress == 1.0
