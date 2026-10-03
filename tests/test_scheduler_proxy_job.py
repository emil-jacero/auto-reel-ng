"""Tests for the ``proxy`` job's handler (proxy-job): what it prepares, its progress, its
failures, its cancel and its CPU token. The preparation of a clip is replaced by a fake and the
store by an in-memory one, so nothing here needs a database or ffmpeg; the real encode is in
``test_scheduler_proxy_job_lifecycle.py``."""

from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest

from auto_reel_ng.accel.profiles import CPUProfile
from auto_reel_ng.config.project import ConfigError
from auto_reel_ng.errors import (
    FfmpegCancelledError,
    FilmstripError,
    ProxyCacheError,
    ProxyError,
    RenderCancelledError,
)
from auto_reel_ng.persistence.models import Job
from auto_reel_ng.proxies import ProxySettings
from auto_reel_ng.scheduler import proxy_job as proxy_job_module
from auto_reel_ng.scheduler.pools import CapacityPools
from auto_reel_ng.scheduler.proxy_job import (
    ProxyJobError,
    ProxyJobHandler,
    load_project_proxy_settings,
)
from auto_reel_ng.scheduler.worker import JobInterrupted

Prepare = Callable[..., Any]


class MemoryStore:
    """The two job-store calls the handler makes, in memory."""

    def __init__(self) -> None:
        self.progress: List[float] = []
        self.cancel_requested = False

    def set_progress(self, job_id: uuid.UUID, fraction: float) -> None:
        del job_id
        self.progress.append(fraction)

    def get(self, job_id: uuid.UUID) -> Any:
        del job_id
        return type("Row", (), {"cancel_requested": self.cancel_requested})()


class Harness:
    """One project with one event, a fake ``prepare_clip`` that records its calls."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "project"
        self.event = self.root / "2024" / "2024-06-21 - Midsommar"
        self.event.mkdir(parents=True)
        self.cache = tmp_path / "cache"
        self.store = MemoryStore()
        self.pools = CapacityPools(gpu_caps={}, cpu_cap=1)
        self.stop = threading.Event()
        self.prepared: List[str] = []
        self.settings_seen: List[ProxySettings] = []
        self.settings_loaded_for: List[Path] = []
        self.on_prepare: Optional[Callable[[Path, Callable[[float], None]], None]] = None

    def clip(self, name: str, size: int = 10) -> Path:
        path = self.event / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\0" * size)
        return path

    def prepare(self, clip: Path, **kwargs: Any) -> Any:
        self.prepared.append(
            clip.relative_to(self.event).as_posix()
            if clip.is_relative_to(self.event)
            else str(clip)
        )
        self.settings_seen.append(kwargs["settings"])
        if self.on_prepare is not None:
            self.on_prepare(clip, kwargs["on_progress"])
        else:
            kwargs["on_progress"](0.5)
            kwargs["on_progress"](1.0)
        return object()

    def load(self, project_root: Path) -> ProxySettings:
        self.settings_loaded_for.append(project_root)
        return ProxySettings(self.cache)

    def handler(self, **overrides: Any) -> ProxyJobHandler:
        kwargs: Dict[str, Any] = {
            "store": self.store,
            "pools": self.pools,
            "runtime": None,
            "profile": CPUProfile(),
            "stop_event": self.stop,
            "prepare": self.prepare,
            "load_settings": self.load,
        }
        kwargs.update(overrides)
        return ProxyJobHandler(**kwargs)

    def job(self) -> Job:
        return Job(
            id=uuid.uuid4(),
            project_root=str(self.root),
            event_dir=self.event.relative_to(self.root).as_posix(),
            kind="proxy",
            cancel_requested=False,
        )

    def run(self, **overrides: Any) -> None:
        self.handler(**overrides)(self.job())

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
    """Every path under ``root`` with its mtime and size: a snapshot to compare."""
    return {
        str(p.relative_to(root)): (p.stat().st_mtime_ns, p.stat().st_size)
        for p in sorted(root.rglob("*"))
    }


# --------------------------------------------------------------------------- #
# what is prepared
# --------------------------------------------------------------------------- #


def test_every_listed_clip_is_prepared_in_listing_order(harness: Harness) -> None:
    for name in ("b.mp4", "ch/c.mp4", "a.mp4"):
        harness.clip(name)

    harness.run()

    assert harness.prepared == ["a.mp4", "b.mp4", "ch/c.mp4"]


def test_editorial_state_does_not_choose_the_clips_and_reel_yaml_is_untouched(
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
    before = reel.read_bytes()

    harness.run()

    assert harness.prepared == ["a.mp4", "b.mp4"]  # b is ignored in reel.yaml; gone.mp4 never asked
    assert reel.read_bytes() == before
    assert sorted(p.name for p in harness.event.iterdir()) == ["a.mp4", "b.mp4", "reel.yaml"]


def test_clips_that_resolve_to_one_entry_are_prepared_once(harness: Harness) -> None:
    harness.clip("a.mp4")
    (harness.event / "b.mp4").symlink_to(harness.event / "a.mp4")  # same file, same cache key

    harness.run()

    assert harness.prepared == ["a.mp4"]


def test_a_clip_that_vanishes_after_the_listing_is_a_clip_failure_with_its_cause(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.clip("a.mp4")
    harness.clip("vanished.mp4")
    real_key = proxy_job_module.proxy_key

    def key(path: Path) -> str:
        if path.name == "vanished.mp4":
            raise FileNotFoundError(2, "No such file or directory")
        return real_key(path)

    monkeypatch.setattr(proxy_job_module, "proxy_key", key)

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        if clip.name == "vanished.mp4":
            raise ProxyError(str(clip), "cannot stat the clip: No such file or directory")
        on_progress(1.0)

    harness.on_prepare = run

    with pytest.raises(ProxyJobError, match=r"1 of 2 clips failed: vanished.mp4: cannot stat"):
        harness.run()

    assert harness.prepared == ["a.mp4", "vanished.mp4"]  # the other clip is still prepared


def test_the_library_is_written_nowhere(harness: Harness) -> None:
    harness.clip("a.mp4")
    harness.clip("ch/b.mp4")
    snapshot = tree(harness.root)
    os.chmod(harness.event, 0o555)
    os.chmod(harness.event / "ch", 0o555)
    try:
        harness.run()
    finally:
        os.chmod(harness.event, 0o755)
        os.chmod(harness.event / "ch", 0o755)

    assert tree(harness.root) == snapshot


def test_the_settings_come_from_the_jobs_own_project(harness: Harness, tmp_path: Path) -> None:
    harness.clip("a.mp4")
    other = tmp_path / "other"
    other_event = other / "2024" / "x"
    other_event.mkdir(parents=True)
    (other_event / "z.mp4").write_bytes(b"z")
    caches = {
        harness.root: ProxySettings(tmp_path / "cache-a"),
        other: ProxySettings(tmp_path / "cache-b"),
    }
    handler = harness.handler(load_settings=lambda root: caches[root])

    handler(harness.job())
    handler(Job(id=uuid.uuid4(), project_root=str(other), event_dir="2024/x", kind="proxy"))

    assert [s.cache_dir for s in harness.settings_seen] == [
        tmp_path / "cache-a",
        tmp_path / "cache-b",
    ]


def test_a_refused_cache_directory_fails_before_any_clip_or_token(
    harness: Harness, tmp_path: Path
) -> None:
    harness.clip("a.mp4")
    (harness.root / "config.yaml").write_text(
        f"proxies:\n  cache_dir: {harness.root / 'cache'}\n", encoding="utf-8"
    )
    token = harness.pools.cpu_token()
    token.acquire()  # a taken token: reaching for it would hang the test
    try:
        with pytest.raises(ConfigError, match="proxies.cache_dir"):
            harness.run(load_settings=load_project_proxy_settings)
    finally:
        token.release()

    assert harness.prepared == []


def test_a_project_config_that_does_not_load_fails_the_job(harness: Harness) -> None:
    harness.clip("a.mp4")
    (harness.root / "config.yaml").write_text("proxies: [not, a, map]\n", encoding="utf-8")

    with pytest.raises(ConfigError):
        harness.run(load_settings=load_project_proxy_settings)

    assert harness.prepared == []


def test_two_projects_resolve_two_cache_directories(tmp_path: Path) -> None:
    for name in ("one", "two"):
        root = tmp_path / name
        root.mkdir()
        (root / "config.yaml").write_text(
            f"proxies:\n  cache_dir: {tmp_path / (name + '-cache')}\n", encoding="utf-8"
        )

    assert load_project_proxy_settings(tmp_path / "one").cache_dir == tmp_path / "one-cache"
    assert load_project_proxy_settings(tmp_path / "two").cache_dir == tmp_path / "two-cache"


# --------------------------------------------------------------------------- #
# progress
# --------------------------------------------------------------------------- #


def test_progress_is_weighted_by_source_size(harness: Harness) -> None:
    harness.clip("a.mp4", size=900)
    harness.clip("b.mp4", size=100)
    seen_at_second: List[float] = []

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        if clip.name == "b.mp4":
            seen_at_second.append(harness.store.progress[-1])
        on_progress(1.0)

    harness.on_prepare = run
    harness.run()

    assert seen_at_second == [pytest.approx(0.9)]
    assert harness.store.progress[-1] == 1.0


def test_progress_moves_inside_a_clip(harness: Harness) -> None:
    harness.clip("only.mp4", size=100)

    def half(clip: Path, on_progress: Callable[[float], None]) -> None:
        del clip
        on_progress(0.5)
        assert harness.store.progress[-1] == pytest.approx(0.5)
        on_progress(1.0)

    harness.on_prepare = half
    harness.run()

    assert harness.store.progress[-1] == 1.0


def test_cached_clips_advance_the_bar_without_going_back(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name, size=100)

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        if clip.name != "b.mp4":
            on_progress(1.0)  # a cache hit reports one at once
            return
        for fraction in (0.2, 0.6, 1.0):
            on_progress(fraction)

    harness.on_prepare = run
    harness.run()

    assert harness.store.progress == sorted(harness.store.progress)
    assert harness.store.progress[-1] == 1.0


def test_progress_stays_below_one_until_the_last_clip_is_finished(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name, size=100)
    at_second: List[List[float]] = []

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        if clip.name == "b.mp4":
            at_second.append(list(harness.store.progress))
        on_progress(1.0)

    harness.on_prepare = run
    harness.run()

    assert at_second and all(p < 1.0 for p in at_second[0])


def test_a_zero_size_file_weighs_one_byte(harness: Harness) -> None:
    harness.clip("empty.mp4", size=0)

    harness.run()

    assert harness.store.progress[-1] == 1.0


def test_a_fully_cached_event_reaches_one_and_starts_no_process(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)
    harness.on_prepare = lambda clip, on_progress: on_progress(1.0)

    harness.run()

    assert harness.store.progress[-1] == 1.0  # and the fake is the only thing that ran


# --------------------------------------------------------------------------- #
# failures
# --------------------------------------------------------------------------- #


def test_one_bad_clip_of_three_fails_the_job_after_the_others_are_prepared(
    harness: Harness,
) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name)

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        if clip.name == "b.mp4":
            raise ProxyError(str(clip), "ffmpeg failed on the cpu path")
        on_progress(1.0)

    harness.on_prepare = run

    with pytest.raises(ProxyJobError) as raised:
        harness.run()

    assert str(raised.value).startswith("1 of 3 clips failed: b.mp4: ffmpeg failed")
    assert harness.prepared == ["a.mp4", "b.mp4", "c.mp4"]
    assert max(harness.store.progress) < 1.0  # a job with a failed clip never reads as done


def test_a_failed_filmstrip_is_a_clip_failure_too(harness: Harness) -> None:
    harness.clip("a.mp4")

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        on_progress(0.97)
        raise FilmstripError(str(clip), "ffmpeg could not cut the filmstrip")

    harness.on_prepare = run

    with pytest.raises(ProxyJobError, match="1 of 1 clips failed: a.mp4: ffmpeg could not cut"):
        harness.run()


def test_a_long_list_of_failures_is_shortened_to_the_first_few(harness: Harness) -> None:
    for number in range(6):
        harness.clip(f"{number}.mp4")

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        del on_progress
        raise ProxyError(str(clip), "bad")

    harness.on_prepare = run

    with pytest.raises(ProxyJobError) as raised:
        harness.run()

    message = str(raised.value)
    assert message.startswith("6 of 6 clips failed: 0.mp4: bad; 1.mp4: bad; 2.mp4: bad; and 3 more")
    assert "5.mp4" not in message


def test_a_cache_fault_ends_the_job_at_once(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name)

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        del on_progress
        raise ProxyCacheError(f"{harness.cache}: cannot write proxies: No space left on device")

    harness.on_prepare = run

    with pytest.raises(ProxyCacheError, match="No space left"):
        harness.run()

    assert harness.prepared == ["a.mp4"]
    assert harness.cpu_token_is_free()


def test_an_event_folder_that_cannot_be_listed_is_a_proxy_error(harness: Harness) -> None:
    harness.event.rmdir()

    with pytest.raises(ProxyError, match="cannot list the event folder"):
        harness.run()


# --------------------------------------------------------------------------- #
# cancel, stop and the CPU token
# --------------------------------------------------------------------------- #


def test_cancel_inside_a_clip_ends_the_job_canceled_and_the_next_clip_is_not_started(
    harness: Harness,
) -> None:
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        harness.clip(name)

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        del on_progress
        if clip.name == "b.mp4":
            harness.store.cancel_requested = True
            raise FfmpegCancelledError("canceled")  # what the encode raises once it sees the flag

    harness.on_prepare = run

    with pytest.raises(RenderCancelledError):
        harness.run()

    assert harness.prepared == ["a.mp4", "b.mp4"]
    assert harness.cpu_token_is_free()


def test_the_cancel_check_handed_to_a_clip_reads_the_jobs_flag(harness: Harness) -> None:
    harness.clip("a.mp4")
    answers: List[bool] = []

    def prepare(clip: Path, **kwargs: Any) -> Any:
        del clip
        answers.append(kwargs["should_cancel"]())
        harness.store.cancel_requested = True
        answers.append(kwargs["should_cancel"]())
        raise FfmpegCancelledError("canceled")

    with pytest.raises(RenderCancelledError):
        harness.run(prepare=prepare)

    assert answers == [False, True]


def test_cancel_between_clips_starts_no_further_clip(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        on_progress(1.0)
        harness.store.cancel_requested = True  # set while moving to the next clip

    harness.on_prepare = run

    with pytest.raises(RenderCancelledError):
        harness.run()

    assert harness.prepared == ["a.mp4"]


def test_a_stop_is_an_interruption_not_a_cancel_and_stops_the_encode(harness: Harness) -> None:
    for name in ("a.mp4", "b.mp4"):
        harness.clip(name)
    checks: List[bool] = []

    def prepare(clip: Path, **kwargs: Any) -> Any:
        del clip
        harness.stop.set()
        checks.append(kwargs["should_cancel"]())
        raise FfmpegCancelledError("stopped")

    with pytest.raises(JobInterrupted):
        harness.run(prepare=prepare)

    assert checks == [True]
    assert harness.cpu_token_is_free()


def test_the_job_holds_one_cpu_token_while_it_works_and_releases_it_after(harness: Harness) -> None:
    harness.clip("a.mp4")
    free_during: List[bool] = []

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        del clip
        free_during.append(harness.cpu_token_is_free())
        on_progress(1.0)

    harness.on_prepare = run
    harness.run()

    assert free_during == [False]
    assert harness.cpu_token_is_free()


@pytest.mark.parametrize("error", [ProxyError("a.mp4", "bad"), TypeError("boom")])
def test_the_token_is_released_when_the_job_fails(harness: Harness, error: Exception) -> None:
    harness.clip("a.mp4")

    def run(clip: Path, on_progress: Callable[[float], None]) -> None:
        del clip, on_progress
        raise error

    harness.on_prepare = run

    with pytest.raises((ProxyJobError, TypeError)):
        harness.run()

    assert harness.cpu_token_is_free()


def test_a_cancel_while_waiting_for_the_token_ends_the_job_without_a_clip(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(proxy_job_module, "TOKEN_POLL_S", 0.01)
    harness.clip("a.mp4")
    token = harness.pools.cpu_token()
    token.acquire()  # another job holds the CPU token
    timer = threading.Timer(0.1, lambda: setattr(harness.store, "cancel_requested", True))
    timer.start()
    try:
        with pytest.raises(RenderCancelledError):
            harness.run()
    finally:
        timer.cancel()
        token.release()

    assert harness.prepared == []


def test_a_stop_while_waiting_for_the_token_interrupts_the_job(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(proxy_job_module, "TOKEN_POLL_S", 0.01)
    harness.clip("a.mp4")
    token = harness.pools.cpu_token()
    token.acquire()
    timer = threading.Timer(0.1, harness.stop.set)
    timer.start()
    try:
        with pytest.raises(JobInterrupted):
            harness.run()
    finally:
        timer.cancel()
        token.release()

    assert harness.prepared == []
