"""Real-ffmpeg lifecycle tests of the ``proxy`` job (proxy-job): cancel inside a clip's encode,
a graceful stop, a killed worker's leftovers and a re-enqueue after a cancel, on three
synthesized clips through the real worker and the real handler (real Postgres).

The middle clip is long enough that its encode is still running when the test acts on it.
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, List, Optional

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import JobKind, JobStatus
from auto_reel_ng.proxies import ProxySettings, lookup_filmstrip, lookup_proxy, prepare_clip
from auto_reel_ng.proxies.spec import proxy_key
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.proxy_job import ProxyJobHandler
from auto_reel_ng.scheduler.worker import Worker

pytestmark = [pytest.mark.requires_db, pytest.mark.has_ffmpeg]

EVENT = "2024/2024-06-21 - Midsommar"


class CountingRuntime:
    """Delegates to a real runtime and records every ffmpeg and ffprobe invocation."""

    def __init__(self, inner: FfmpegRuntime, calls: List[str]) -> None:
        self._inner = inner
        self.calls = calls

    def with_timeout(self, seconds: float) -> "CountingRuntime":
        return CountingRuntime(self._inner.with_timeout(seconds), self.calls)

    def run_ffprobe(self, args: Any, *a: Any, **kw: Any) -> Any:
        self.calls.append(" ".join(map(str, args)))
        return self._inner.run_ffprobe(args, *a, **kw)

    def run_with_progress(self, args: Any, **kw: Any) -> Any:
        self.calls.append(" ".join(map(str, args)))
        return self._inner.run_with_progress(args, **kw)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class Rig:
    """A project of one event with a short, a long and a short clip."""

    def __init__(self, runtime: FfmpegRuntime, job_store: JobStore, tmp_path: Path) -> None:
        self.runtime = runtime
        self.store = job_store
        self.root = tmp_path / "proj"
        self.event = self.root / EVENT
        self.event.mkdir(parents=True)
        self.cache = tmp_path / "cache"
        (self.root / "config.yaml").write_text(
            f"proxies:\n  cache_dir: {self.cache}\n", encoding="utf-8"
        )
        self.settings = ProxySettings(self.cache)
        self.calls: List[str] = []
        self.stop = threading.Event()
        for name, seconds in (("a.mp4", 2), ("b.mp4", 90), ("c.mp4", 2)):
            self.synthesize(name, seconds)

    def synthesize(self, name: str, seconds: int) -> None:
        subprocess.run(
            [
                self.runtime.ffmpeg_path, "-y", "-v", "error",
                "-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate=50:duration={seconds}",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-shortest", str(self.event / name),
            ],
            check=True,
            capture_output=True,
        )  # fmt: skip

    def clip(self, name: str) -> Path:
        return self.event / name

    def worker(self, worker_id: str = "w1") -> Worker:
        pools = CapacityPools(gpu_caps={}, cpu_cap=1)
        handler = ProxyJobHandler(
            store=self.store,
            pools=pools,
            runtime=CountingRuntime(self.runtime, self.calls),  # type: ignore[arg-type]
            profile=CPUProfile(),
            stop_event=self.stop,
        )
        return Worker(
            self.store,
            worker_id=worker_id,
            pools=pools,
            poll_interval=0.02,
            build_job=lambda job: (_ for _ in ()).throw(AssertionError("a render was built")),
            kind_handlers={JobKind.PROXY.value: handler},
            stop_event=self.stop,
        )

    def enqueue(self) -> Any:
        return self.store.enqueue(str(self.root), EVENT, kind=JobKind.PROXY)

    def parts(self) -> List[Path]:
        return sorted(self.cache.glob(".*")) if self.cache.exists() else []

    def has_entry(self, name: str) -> bool:
        return lookup_proxy(self.clip(name), settings=self.settings) is not None

    def status(self, job_id: Any) -> JobStatus:
        job = self.store.get(job_id)
        assert job is not None
        return job.status

    def calls_for(self, name: str) -> List[str]:
        return [call for call in self.calls if name in call]

    def start(self, worker: Worker) -> threading.Thread:
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()
        return thread


def wait_until(condition: Callable[[], bool], *, timeout: float = 120.0, what: str = "") -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what or 'the condition'}")


@pytest.fixture
def rig(runtime: FfmpegRuntime, job_store: JobStore, tmp_path: Path) -> Rig:
    return Rig(runtime, job_store, tmp_path)


def encoding_second_clip(rig: Rig) -> bool:
    """The first clip is done and the second one's build directory exists."""
    return rig.has_entry("a.mp4") and bool(rig.parts())


def test_a_whole_event_is_prepared_with_a_proxy_and_a_filmstrip_per_clip(rig: Rig) -> None:
    rig.synthesize("b.mp4", 3)  # a short second clip: this test is about the whole job
    job_id = rig.enqueue()

    assert rig.worker().process_next() is True

    job = rig.store.get(job_id)
    assert job is not None and (job.status, job.progress) == (JobStatus.DONE, 1.0)
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        entry = lookup_proxy(rig.clip(name), settings=rig.settings)
        assert entry is not None and lookup_filmstrip(entry) is not None
    assert rig.parts() == []


def test_cancel_inside_the_second_clip_ends_canceled_fast_and_leaves_the_cache_clean(
    rig: Rig,
) -> None:
    job_id = rig.enqueue()
    worker = rig.worker()
    thread = rig.start(worker)
    wait_until(lambda: encoding_second_clip(rig), what="the second clip to start encoding")

    asked = time.monotonic()
    rig.store.request_cancel(job_id)
    wait_until(lambda: rig.status(job_id) == JobStatus.CANCELED, timeout=30, what="canceled")
    took = time.monotonic() - asked

    worker.stop()
    thread.join(timeout=15)
    assert took < 3.0  # a poll of about a second plus the kill
    assert rig.has_entry("a.mp4")  # the clip finished before the cancel stays
    assert not rig.has_entry("b.mp4") and not rig.has_entry("c.mp4")
    assert rig.parts() == []  # no .part and no temporary file
    assert rig.calls_for("c.mp4") == []  # the third clip was never started


def test_a_stop_requeues_the_job_and_leaves_no_build_directory(rig: Rig) -> None:
    job_id = rig.enqueue()
    worker = rig.worker()
    thread = rig.start(worker)
    wait_until(lambda: encoding_second_clip(rig), what="the second clip to start encoding")

    worker.stop()
    thread.join(timeout=30)

    assert not thread.is_alive()
    assert rig.status(job_id) == JobStatus.QUEUED
    assert rig.parts() == []
    assert rig.has_entry("a.mp4") and not rig.has_entry("b.mp4")
    assert rig.calls_for("c.mp4") == []


def test_a_killed_workers_job_is_requeued_and_only_the_missing_clips_are_encoded(
    rig: Rig,
) -> None:
    rig.synthesize("b.mp4", 3)
    prepare_clip(
        rig.clip("a.mp4"), settings=rig.settings, runtime=rig.runtime, profile=CPUProfile()
    )
    # What a SIGKILLed worker leaves: the row still running under its (dead) identity, and
    # the hidden build directory of the clip it was encoding.
    job_id = rig.enqueue()
    claimed = rig.store.claim_next("dead-worker:1:abcd")
    assert claimed is not None and claimed.id == job_id
    leftover = rig.cache / f".{proxy_key(rig.clip('b.mp4'))}.{'0' * 32}.part"
    leftover.mkdir(parents=True)
    (leftover / "proxy.mp4").write_bytes(b"half a proxy")

    worker = rig.worker("w2")
    thread = rig.start(worker)
    wait_until(lambda: rig.status(job_id) == JobStatus.DONE, what="the requeued job to finish")
    worker.stop()
    thread.join(timeout=15)

    assert rig.calls_for("a.mp4") == []  # finished before: costs no process
    assert rig.calls_for("b.mp4") and rig.calls_for("c.mp4")
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        entry = lookup_proxy(rig.clip(name), settings=rig.settings)
        assert entry is not None and entry.proxy_path.stat().st_size > 1000
        assert lookup_filmstrip(entry) is not None
    assert entry.proxy_path.read_bytes() != b"half a proxy"


def test_a_canceled_event_can_be_enqueued_again_and_prepares_only_what_is_missing(
    rig: Rig,
) -> None:
    first = rig.enqueue()
    worker = rig.worker()
    thread = rig.start(worker)
    wait_until(lambda: encoding_second_clip(rig), what="the second clip to start encoding")
    rig.store.request_cancel(first)
    wait_until(lambda: rig.status(first) == JobStatus.CANCELED, timeout=30, what="canceled")
    rig.synthesize("b.mp4", 3)  # keep the rerun quick
    before = len(rig.calls)

    second = rig.enqueue()
    assert second != first
    wait_until(lambda: rig.status(second) == JobStatus.DONE, what="the second job")
    worker.stop()
    thread.join(timeout=15)

    later = rig.calls[before:]
    assert not any("a.mp4" in call for call in later)  # the first clip is cached
    assert any("b.mp4" in call for call in later) and any("c.mp4" in call for call in later)
    assert all(rig.has_entry(name) for name in ("a.mp4", "b.mp4", "c.mp4"))
