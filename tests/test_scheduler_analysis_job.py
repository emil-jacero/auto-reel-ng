"""Tests for the ``analysis`` job's handler (analysis-job): what it analyzes, its failure
markers, its progress, its yield to renders and proxy jobs, its cancel and its CPU token.

Detection is replaced by a fake ``analyze`` and the store by an in-memory one, so nothing here
needs a database or ffmpeg; the real job end to end is ``test_scheduler_analysis_e2e.py``.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest

from auto_reel_ng.analysis import cache as cache_module
from auto_reel_ng.analysis.cache import cache_dir, read_entry, read_failure, write_entry
from auto_reel_ng.analysis.models import Segment, SegmentKind
from auto_reel_ng.errors import AnalysisError, FfmpegCancelledError, RenderCancelledError
from auto_reel_ng.persistence.job_store import Submission
from auto_reel_ng.persistence.models import Job, JobKind, JobStatus
from auto_reel_ng.scheduler import analysis_job as analysis_job_module
from auto_reel_ng.scheduler.analysis_job import (
    AnalysisJobError,
    AnalysisJobHandler,
    submit_analysis,
)
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.worker import JobInterrupted

BLACK = [Segment(start=0.0, end=3.0, kind=SegmentKind.BLACK, confidence=1.0)]
OnClip = Callable[[Path, Callable[[float], None], Callable[[], bool]], List[Segment]]


class MemoryStore:
    """The job-store calls the handler makes, in memory."""

    def __init__(self) -> None:
        self.progress: List[float] = []
        self.cancel_requested = False
        self.running: Dict[str, int] = {JobKind.RENDER: 0, JobKind.PROXY: 0}
        self.listings: List[Any] = []
        self.submitted: List[Dict[str, Any]] = []

    def list_by_status(self, status: Any, *, kind: Any = None) -> List[Any]:
        self.listings.append((status, kind))
        return [object()] * self.running.get(kind, 0)

    def set_progress(self, job_id: uuid.UUID, fraction: float) -> None:
        del job_id
        self.progress.append(fraction)

    def get(self, job_id: uuid.UUID) -> Any:
        del job_id
        return type("Row", (), {"cancel_requested": self.cancel_requested})()

    def submit(self, project_root: str, event_dir: str, **kwargs: Any) -> Submission:
        for row in self.submitted:
            if row["event_dir"] == event_dir:
                return Submission(job_id=row["id"], created=False)
        row = {"project_root": project_root, "event_dir": event_dir, "id": uuid.uuid4(), **kwargs}
        self.submitted.append(row)
        return Submission(job_id=row["id"], created=True)


class Harness:  # pylint: disable=too-many-instance-attributes
    """One project with one event and a fake ``analyze`` that records its calls."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "project"
        self.event = self.root / "2024" / "2024-06-21 - Midsommar"
        self.event.mkdir(parents=True)
        self.store = MemoryStore()
        self.pools = CapacityPools(gpu_caps={}, cpu_cap=1)
        self.stop = threading.Event()
        self.analyzed: List[str] = []
        self.on_clip: Optional[OnClip] = None

    def clip(self, name: str, size: int = 10) -> Path:
        path = self.event / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\0" * size)
        return path

    def analyze(self, clip: Path, **kwargs: Any) -> List[Segment]:
        assert set(kwargs) == {"runtime", "on_progress", "should_cancel"}
        self.analyzed.append(clip.relative_to(self.event).as_posix())
        if self.on_clip is not None:
            return self.on_clip(clip, kwargs["on_progress"], kwargs["should_cancel"])
        kwargs["on_progress"](0.5)
        kwargs["on_progress"](1.0)
        return list(BLACK)

    def handler(self) -> AnalysisJobHandler:
        return AnalysisJobHandler(
            store=self.store,  # type: ignore[arg-type]
            pools=self.pools,
            runtime=None,  # type: ignore[arg-type]
            stop_event=self.stop,
            analyze=self.analyze,
        )

    def job(self, *, force: bool = False) -> Job:
        return Job(
            id=uuid.uuid4(),
            project_root=str(self.root),
            event_dir=self.event.relative_to(self.root).as_posix(),
            kind="analysis",
            force=force,
            cancel_requested=False,
        )

    def run(self, *, force: bool = False) -> None:
        self.handler()(self.job(force=force))

    def signal(self, name: str) -> Dict[str, object]:
        return cache_module.clip_signal(self.event / name)

    def entry(self, name: str) -> Optional[List[Segment]]:
        return read_entry(self.event, name, self.signal(name))

    def failure(self, name: str) -> Optional[str]:
        return read_failure(self.event, name, self.signal(name))

    def cpu_token_is_free(self) -> bool:
        token = self.pools.cpu_token()
        if token.acquire(blocking=False):
            token.release()
            return True
        return False


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def tree(root: Path) -> Dict[str, Any]:
    """Every file under ``root`` with its mtime and size: a snapshot to compare."""
    return {
        str(p.relative_to(root)): (p.stat().st_mtime_ns, p.stat().st_size)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def failing(name: str, message: str = "Cannot analyze undecodable clip") -> OnClip:
    """An ``on_clip`` that fails ``name`` with an AnalysisError and detects the others."""

    def run(
        clip: Path, on_progress: Callable[[float], None], should_cancel: Callable[[], bool]
    ) -> List[Segment]:
        del should_cancel
        if clip.name == name:
            raise AnalysisError(f"{message} {clip}: ffprobe could not read the file")
        on_progress(1.0)
        return list(BLACK)

    return run


# --------------------------------------------------------------------------- #
# what is analyzed
# --------------------------------------------------------------------------- #


def test_every_listed_clip_is_analyzed_in_listing_order_and_gets_an_entry(
    harness: Harness,
) -> None:
    for name in ("b.mp4", "ch/c.mp4", "a.mp4"):
        harness.clip(name)

    harness.run()

    assert harness.analyzed == ["a.mp4", "b.mp4", "ch/c.mp4"]
    assert all(harness.entry(n) == BLACK for n in ("a.mp4", "b.mp4", "ch/c.mp4"))


def test_only_changed_and_new_clips_are_analyzed(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name)
    write_entry(harness.event, "a.mp4", harness.signal("a.mp4"), [])
    write_entry(harness.event, "b.mp4", harness.signal("b.mp4"), [])
    harness.clip("b.mp4", size=20)  # re-copied: its size changed

    harness.run()

    assert harness.analyzed == ["b.mp4", "c.mp4"]
    assert harness.entry("a.mp4") == [] and harness.entry("b.mp4") == BLACK
    assert harness.entry("c.mp4") == BLACK


def test_a_fully_analyzed_event_completes_without_work(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)
        write_entry(harness.event, name, harness.signal(name), [])

    harness.run()

    assert harness.analyzed == []
    assert harness.store.progress[-1] == 1.0


def test_a_forced_job_analyzes_everything_again(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)
        write_entry(harness.event, name, harness.signal(name), [])

    harness.run(force=True)

    assert harness.analyzed == ["a.mp4", "b.mp4"]
    assert harness.entry("a.mp4") == BLACK and harness.entry("b.mp4") == BLACK


def test_editorial_state_does_not_choose_the_clips_and_only_the_cache_is_written(
    harness: Harness,
) -> None:
    harness.clip("a.mp4")
    harness.clip("b.mp4")
    reel = harness.event / "reel.yaml"
    reel.write_text(
        "version: 0\nmetadata:\n  title: M\n  date: 2024-06-21\nchapters:\n  - name: ''\n"
        "    clips:\n      - a.mp4\n      - gone.mp4\n    ignored:\n      - b.mp4\n",
        encoding="utf-8",
    )
    before = tree(harness.root)
    reel_bytes = reel.read_bytes()

    harness.run()

    assert harness.analyzed == ["a.mp4", "b.mp4"]  # b ignored in reel.yaml; gone.mp4 never asked
    assert reel.read_bytes() == reel_bytes
    after = tree(harness.root)
    changed = {k for k in after if before.get(k) != after[k]}
    cache_prefix = str((harness.event / ".auto-reel").relative_to(harness.root))
    assert changed and all(k.startswith(cache_prefix) for k in changed)


def test_a_leftover_temporary_file_is_harmless(harness: Harness) -> None:
    harness.clip("a.mp4")
    cache = cache_dir(harness.event)
    cache.mkdir(parents=True)
    (cache / "0123456789abcdef.json.part-1-dead").write_text("{", encoding="utf-8")

    harness.run()

    assert harness.analyzed == ["a.mp4"] and harness.entry("a.mp4") == BLACK


# --------------------------------------------------------------------------- #
# failures and markers
# --------------------------------------------------------------------------- #


def test_one_failing_clip_is_marked_and_the_others_still_get_entries(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name)
    harness.on_clip = failing("b.mp4")

    with pytest.raises(AnalysisJobError) as excinfo:
        harness.run()

    message = str(excinfo.value)
    assert message.startswith("1 of 3 clips failed: b.mp4: ")
    assert "Cannot analyze undecodable clip" in message
    assert str(harness.event) not in message  # no server path in the job's error
    assert harness.analyzed == ["a.mp4", "b.mp4", "c.mp4"]
    assert harness.entry("a.mp4") == BLACK and harness.entry("c.mp4") == BLACK
    assert harness.entry("b.mp4") is None
    cause = harness.failure("b.mp4")
    assert cause is not None and "Cannot analyze undecodable clip" in cause


def test_a_marked_clip_is_not_retried_without_force(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name)
    harness.on_clip = failing("b.mp4")
    with pytest.raises(AnalysisJobError):
        harness.run()
    cause = harness.failure("b.mp4")
    harness.analyzed.clear()
    harness.on_clip = None  # the clip would succeed now, if it were tried

    with pytest.raises(AnalysisJobError) as excinfo:
        harness.run()

    assert harness.analyzed == []  # no ffmpeg or ffprobe for any clip
    assert str(excinfo.value).startswith(f"1 of 3 clips failed: b.mp4: {cause}")
    assert "earlier" in str(excinfo.value)


def test_force_retries_a_marked_clip_and_a_success_replaces_the_marker(
    harness: Harness,
) -> None:
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)
    harness.on_clip = failing("b.mp4")
    with pytest.raises(AnalysisJobError):
        harness.run()
    harness.analyzed.clear()
    harness.on_clip = None

    harness.run(force=True)

    assert harness.analyzed == ["a.mp4", "b.mp4"]
    assert harness.entry("b.mp4") == BLACK and harness.failure("b.mp4") is None


def test_a_changed_clip_retries_a_marked_clip(harness: Harness) -> None:
    harness.clip("a.mp4")
    harness.clip("b.mp4")
    harness.on_clip = failing("b.mp4")
    with pytest.raises(AnalysisJobError):
        harness.run()
    harness.analyzed.clear()
    harness.on_clip = None
    harness.clip("b.mp4", size=99)  # replaced by a good copy

    harness.run()

    assert harness.analyzed == ["b.mp4"]
    assert harness.entry("b.mp4") == BLACK


def test_a_clip_that_cannot_be_statted_fails_without_a_marker(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.clip("a.mp4")
    harness.clip("vanished.mp4")
    real_signal = analysis_job_module.clip_signal

    def signal(path: Path) -> Dict[str, object]:
        if Path(path).name == "vanished.mp4":
            raise FileNotFoundError(2, "No such file or directory")
        return real_signal(path)

    monkeypatch.setattr(analysis_job_module, "clip_signal", signal)

    with pytest.raises(AnalysisJobError) as excinfo:
        harness.run()

    assert harness.analyzed == ["a.mp4"]
    assert "1 of 2 clips failed: vanished.mp4: cannot stat" in str(excinfo.value)
    assert len(list(cache_dir(harness.event).glob("*.json"))) == 1


def test_a_long_failure_list_names_the_first_three(harness: Harness) -> None:
    names = [f"{c}.mp4" for c in "abcde"]
    for name in names:
        harness.clip(name)

    def run(clip: Path, *_: Any) -> List[Segment]:
        raise AnalysisError(f"ffmpeg white detection pass failed for {clip}: boom")

    harness.on_clip = run

    with pytest.raises(AnalysisJobError) as excinfo:
        harness.run()

    message = str(excinfo.value)
    assert message.startswith("5 of 5 clips failed: a.mp4: ")
    assert "c.mp4" in message and "d.mp4" not in message and message.endswith("; and 2 more")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the read-only mode")
def test_an_unwritable_event_folder_ends_the_job_at_once(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name)
    harness.event.chmod(0o555)
    try:
        with pytest.raises(AnalysisJobError) as excinfo:
            harness.run()
    finally:
        harness.event.chmod(0o755)

    assert harness.analyzed == ["a.mp4"]  # detection of the first clip, then the cache fault
    assert ".auto-reel/cache" in str(excinfo.value)
    assert "clips failed" not in str(excinfo.value)
    assert not cache_dir(harness.event).exists()
    assert harness.cpu_token_is_free()


def test_an_unexpected_exception_propagates_and_releases_the_token(harness: Harness) -> None:
    harness.clip("a.mp4")

    def run(*_: Any) -> List[Segment]:
        raise TypeError("boom")

    harness.on_clip = run

    with pytest.raises(TypeError):
        harness.run()

    assert harness.cpu_token_is_free()
    assert harness.failure("a.mp4") is None


# --------------------------------------------------------------------------- #
# progress
# --------------------------------------------------------------------------- #


def test_progress_is_weighted_by_size(harness: Harness) -> None:
    harness.clip("a.mp4", size=900)
    harness.clip("b.mp4", size=100)
    seen_at_b: List[float] = []

    def run(
        clip: Path, on_progress: Callable[[float], None], should_cancel: Callable[[], bool]
    ) -> List[Segment]:
        del should_cancel
        if clip.name == "b.mp4":
            seen_at_b.append(harness.store.progress[-1])
        on_progress(1.0)
        return []

    harness.on_clip = run
    harness.run()

    assert seen_at_b == [pytest.approx(0.9)]
    assert harness.store.progress == sorted(harness.store.progress)
    assert harness.store.progress[-1] == 1.0


def test_progress_moves_inside_a_clip(harness: Harness) -> None:
    harness.clip("a.mp4")

    def run(
        clip: Path, on_progress: Callable[[float], None], should_cancel: Callable[[], bool]
    ) -> List[Segment]:
        del clip, should_cancel
        on_progress(0.25)
        on_progress(0.75)  # inside the second pass
        on_progress(1.0)
        return []

    harness.on_clip = run
    harness.run()

    assert harness.store.progress[:3] == [0.25, 0.75, 1.0]
    assert 0.5 < harness.store.progress[1] < 1.0


def test_progress_stays_below_one_for_good_once_a_clip_failed(harness: Harness) -> None:
    harness.clip("a.mp4")
    harness.clip("b.mp4")
    harness.on_clip = failing("a.mp4")

    with pytest.raises(AnalysisJobError):
        harness.run()

    assert harness.store.progress == sorted(harness.store.progress)
    assert max(harness.store.progress) < 1.0


# --------------------------------------------------------------------------- #
# the CPU token
# --------------------------------------------------------------------------- #


def test_the_job_holds_one_cpu_token_while_it_works_and_releases_it_after(
    harness: Harness,
) -> None:
    harness.clip("a.mp4")
    free_during: List[bool] = []

    def run(*_: Any) -> List[Segment]:
        free_during.append(harness.cpu_token_is_free())
        return []

    harness.on_clip = run
    harness.run()

    assert free_during == [False]
    assert harness.cpu_token_is_free()


def test_the_token_is_released_when_the_job_fails(harness: Harness) -> None:
    harness.clip("a.mp4")
    harness.on_clip = failing("a.mp4")

    with pytest.raises(AnalysisJobError):
        harness.run()

    assert harness.cpu_token_is_free()


# --------------------------------------------------------------------------- #
# yielding to renders and proxy jobs
# --------------------------------------------------------------------------- #


@pytest.fixture
def quick_yield(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analysis_job_module, "YIELD_POLL_S", 0.01)
    monkeypatch.setattr(analysis_job_module, "TOKEN_POLL_S", 0.01)


def run_in_thread(harness: Harness) -> tuple[threading.Thread, List[BaseException]]:
    errors: List[BaseException] = []

    def target() -> None:
        try:
            harness.run()
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread, errors


def wait_for(condition: Callable[[], bool], timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


@pytest.mark.parametrize("kind", [JobKind.RENDER, JobKind.PROXY])
def test_no_clip_starts_while_a_render_or_proxy_job_runs_and_the_token_is_given_back(
    harness: Harness, quick_yield: None, kind: JobKind
) -> None:
    del quick_yield
    harness.clip("a.mp4")
    harness.store.running[kind] = 1

    thread, errors = run_in_thread(harness)
    assert wait_for(lambda: len(harness.store.listings) >= 4)  # it is looking, not working

    assert harness.analyzed == []
    assert harness.cpu_token_is_free()  # a job waiting for the CPU token is not blocked by it
    assert kind in {k for _, k in harness.store.listings}
    assert all(status == JobStatus.RUNNING for status, _ in harness.store.listings)
    progress_while_waiting = list(harness.store.progress)
    harness.store.running[kind] = 0
    thread.join(timeout=5)

    assert not thread.is_alive() and errors == []
    assert progress_while_waiting == []
    assert harness.analyzed == ["a.mp4"]
    assert harness.cpu_token_is_free()


def test_a_proxy_job_waiting_for_the_token_gets_it_after_the_clip_in_flight(
    harness: Harness, quick_yield: None
) -> None:
    del quick_yield
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)
    proxy_got_token = threading.Event()

    def proxy_job() -> None:
        token = harness.pools.cpu_token()
        token.acquire()
        proxy_got_token.set()
        time.sleep(0.05)
        harness.store.running[JobKind.PROXY] = 0
        token.release()

    def run(clip: Path, *_: Any) -> List[Segment]:
        if clip.name == "a.mp4":
            harness.store.running[JobKind.PROXY] = 1  # claimed; it waits for the CPU token
            threading.Thread(target=proxy_job, daemon=True).start()
            time.sleep(0.05)
            assert not proxy_got_token.is_set()  # the clip in flight finishes first
        else:
            assert proxy_got_token.is_set()
        return []

    harness.on_clip = run
    harness.run()

    assert proxy_got_token.is_set()
    assert harness.analyzed == ["a.mp4", "b.mp4"]


def test_a_render_that_starts_during_a_clip_holds_back_the_next_clip_only(
    harness: Harness, quick_yield: None
) -> None:
    del quick_yield
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)

    def run(clip: Path, *_: Any) -> List[Segment]:
        if clip.name == "a.mp4":
            harness.store.running[JobKind.RENDER] = 1
        return []

    harness.on_clip = run
    thread, errors = run_in_thread(harness)

    assert wait_for(lambda: harness.analyzed == ["a.mp4"] and harness.cpu_token_is_free())
    time.sleep(0.1)
    assert harness.analyzed == ["a.mp4"]
    harness.store.running[JobKind.RENDER] = 0
    thread.join(timeout=5)

    assert errors == []
    assert harness.analyzed == ["a.mp4", "b.mp4"]


def test_a_cancel_while_yielding_ends_the_job(harness: Harness, quick_yield: None) -> None:
    del quick_yield
    harness.clip("a.mp4")
    harness.store.running[JobKind.RENDER] = 1
    thread, errors = run_in_thread(harness)
    assert wait_for(lambda: len(harness.store.listings) >= 2)

    harness.store.cancel_requested = True
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert [type(e) for e in errors] == [RenderCancelledError]
    assert harness.analyzed == [] and harness.cpu_token_is_free()


def test_a_stop_while_yielding_interrupts_the_job_at_once(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(analysis_job_module, "YIELD_POLL_S", 30.0)  # only the stop can wake it
    harness.clip("a.mp4")
    harness.store.running[JobKind.PROXY] = 1
    thread, errors = run_in_thread(harness)
    assert wait_for(lambda: len(harness.store.listings) >= 1)

    harness.stop.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert [type(e) for e in errors] == [JobInterrupted]
    assert harness.analyzed == [] and harness.cpu_token_is_free()


# --------------------------------------------------------------------------- #
# cancel and stop inside a clip
# --------------------------------------------------------------------------- #


def cancelled_in(name: str, harness: Harness) -> OnClip:
    """An ``on_clip`` that, in clip ``name``, sets the flag and ends as ffmpeg would."""

    def run(
        clip: Path, on_progress: Callable[[float], None], should_cancel: Callable[[], bool]
    ) -> List[Segment]:
        if clip.name == name:
            harness.store.cancel_requested = True
            assert should_cancel()
            raise FfmpegCancelledError("ffmpeg canceled: fake")
        on_progress(1.0)
        return list(BLACK)

    return run


def test_a_cancel_inside_a_clip_ends_the_job_canceled_and_keeps_finished_clips(
    harness: Harness,
) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name)
    harness.on_clip = cancelled_in("b.mp4", harness)

    with pytest.raises(RenderCancelledError):
        harness.run()

    assert harness.analyzed == ["a.mp4", "b.mp4"]  # c never started
    assert harness.entry("a.mp4") == BLACK
    assert harness.entry("b.mp4") is None and harness.failure("b.mp4") is None
    assert harness.cpu_token_is_free()


def test_a_stop_inside_a_clip_interrupts_the_job_for_its_requeue(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)

    def run(
        clip: Path, on_progress: Callable[[float], None], should_cancel: Callable[[], bool]
    ) -> List[Segment]:
        del on_progress
        if clip.name == "b.mp4":
            harness.stop.set()
            assert should_cancel()
            raise FfmpegCancelledError("ffmpeg canceled: fake")
        return list(BLACK)

    harness.on_clip = run

    with pytest.raises(JobInterrupted):
        harness.run()

    assert harness.entry("a.mp4") == BLACK
    assert harness.entry("b.mp4") is None and harness.failure("b.mp4") is None
    assert harness.cpu_token_is_free()


# --------------------------------------------------------------------------- #
# submit_analysis (the CLI's and the API's shared enqueue)
# --------------------------------------------------------------------------- #


def test_submit_analysis_queues_one_analysis_job_per_event_idempotently(
    harness: Harness,
) -> None:
    other = harness.root / "2024" / "2024-07-01 - Other"
    other.mkdir()

    first = submit_analysis(
        harness.store, harness.root, [harness.event, other], force=True  # type: ignore[arg-type]
    )
    again = submit_analysis(
        harness.store, harness.root, [harness.event], force=False  # type: ignore[arg-type]
    )

    assert [(s.event_dir, s.created) for s in first] == [
        ("2024/2024-06-21 - Midsommar", True),
        ("2024/2024-07-01 - Other", True),
    ]
    assert [(s.event_dir, s.created, s.job_id) for s in again] == [
        ("2024/2024-06-21 - Midsommar", False, first[0].job_id)
    ]
    assert all(
        row["kind"] == JobKind.ANALYSIS and row["force"] is True for row in harness.store.submitted
    )
    assert harness.store.submitted[0]["project_root"] == str(harness.root)


# --------------------------------------------------------------------------- #
# staleness: the sidecar shares .auto-reel/cache/ with the render manifest
# --------------------------------------------------------------------------- #


def test_analysis_does_not_make_a_fresh_event_stale(harness: Harness) -> None:
    from auto_reel_ng.cli.adoption import (  # pylint: disable=import-outside-toplevel
        persist,
        prepare_event,
    )
    from auto_reel_ng.config import default_output_dir  # pylint: disable=import-outside-toplevel
    from auto_reel_ng.config.project import (  # pylint: disable=import-outside-toplevel
        ProjectConfig,
        resolve_look_defaults,
    )
    from auto_reel_ng.event import DEFAULT_CLIP_ORDER  # pylint: disable=import-outside-toplevel
    from auto_reel_ng.render import output_relpath  # pylint: disable=import-outside-toplevel
    from auto_reel_ng.staleness.fingerprint import (  # pylint: disable=import-outside-toplevel
        compute_fingerprint,
        engine_identity,
    )
    from auto_reel_ng.staleness.gate import evaluate  # pylint: disable=import-outside-toplevel
    from auto_reel_ng.staleness.manifest import (  # pylint: disable=import-outside-toplevel
        manifest_path,
        write_manifest,
    )

    harness.clip("a.mp4")
    harness.clip("b.mp4")
    event = prepare_event(harness.event, order=DEFAULT_CLIP_ORDER, adopt=True)
    persist(event)
    version = (8, 1)

    def verdict() -> Any:
        fingerprint = compute_fingerprint(
            event.document,
            event_dir=harness.event,
            look_defaults=resolve_look_defaults(ProjectConfig()),
            ffmpeg_version=version,
        )
        output = default_output_dir(harness.root) / output_relpath(event.document.metadata)
        return fingerprint, output, evaluate(harness.event, output, fingerprint)

    fingerprint, output, _ = verdict()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"already-rendered")
    write_manifest(
        harness.event, fingerprint, output=output.name, engine_identity=engine_identity(version)
    )
    assert verdict()[2].stale is False
    manifest = manifest_path(harness.event).read_bytes()

    harness.run()

    assert harness.analyzed == ["a.mp4", "b.mp4"]
    assert verdict()[2].stale is False
    assert manifest_path(harness.event).read_bytes() == manifest
