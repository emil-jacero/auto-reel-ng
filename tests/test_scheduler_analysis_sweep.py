"""Tests for the worker's automatic analysis sweep (analysis-auto-sweep).

The store is an in-memory stand-in for the calls the sweep makes and the projects are tmp trees
of fake clip files with hand-written sidecar entries, so nothing here needs a database or
ffmpeg; the real store, worker and handler end to end is ``test_scheduler_analysis_sweep_db.py``.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import pytest
from sqlalchemy.exc import OperationalError

from auto_reel_ng.analysis import cache as cache_module
from auto_reel_ng.analysis.cache import clip_signal, write_entry, write_failure
from auto_reel_ng.config.project import ProjectConfig
from auto_reel_ng.persistence.job_store import Submission
from auto_reel_ng.persistence.models import JobKind, JobStatus
from auto_reel_ng.scheduler.analysis_sweep import AnalysisSweep, SweepReport, start_analysis_sweep

ACTIVE = (JobStatus.QUEUED, JobStatus.RUNNING)


@dataclass
class Row:  # pylint: disable=too-many-instance-attributes
    """The job attributes the sweep reads."""

    project_root: str
    event_dir: str
    kind: str
    status: JobStatus = JobStatus.QUEUED
    force: bool = False
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None


class MemoryStore:
    """The job-store calls the sweep makes, in memory, with the one-active-per-kind rule."""

    def __init__(self) -> None:
        self.rows: List[Row] = []
        self.calls: List[str] = []

    def add(self, root: Path, event: Path, kind: str, status: JobStatus, **kwargs: Any) -> Row:
        row = Row(str(root), event.relative_to(root).as_posix(), str(kind), status, **kwargs)
        self.rows.append(row)
        return row

    def list_by_status(
        self, status: JobStatus, *, project_root: Optional[str] = None, kind: Any = "render"
    ) -> List[Row]:
        self.calls.append(f"list_by_status:{status.value}:{kind}")
        return [
            row
            for row in self.rows
            if row.status == status
            and (kind is None or row.kind == str(kind))
            and (project_root is None or row.project_root == project_root)
        ]

    def latest_by_project(self, project_root: str, *, kind: Any = "render") -> Dict[str, Row]:
        self.calls.append(f"latest_by_project:{kind}")
        latest: Dict[str, Row] = {}
        for row in self.rows:
            if row.project_root != project_root or (kind is not None and row.kind != str(kind)):
                continue
            if row.event_dir not in latest or row.created_at >= latest[row.event_dir].created_at:
                latest[row.event_dir] = row
        return latest

    def submit(
        self, project_root: str, event_dir: str, *, kind: Any = "render", **kwargs: Any
    ) -> Submission:
        self.calls.append(f"submit:{event_dir}")
        for row in self.rows:
            if (row.project_root, row.event_dir, row.kind) == (
                project_root,
                event_dir,
                str(kind),
            ) and row.status in ACTIVE:
                return Submission(job_id=row.id, created=False)
        row = Row(project_root, event_dir, str(kind), JobStatus.QUEUED, **kwargs)
        self.rows.append(row)
        return Submission(job_id=row.id, created=True)

    def force_queued(self, job_id: uuid.UUID) -> bool:
        raise AssertionError(f"the sweep never forces a job ({job_id})")

    def analysis_jobs(self) -> List[str]:
        return [row.event_dir for row in self.rows if row.kind == JobKind.ANALYSIS]


class Project:
    """A ``year-event`` project of fake clips whose sidecars the test writes by hand."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def event(self, name: str, *clips: str, year: str = "2024") -> Path:
        event = self.root / year / name
        event.mkdir(parents=True, exist_ok=True)
        for clip in clips:
            (event / clip).write_bytes(f"{name}/{clip}".encode())
        return event

    def rel(self, event: Path) -> str:
        return event.relative_to(self.root).as_posix()

    @staticmethod
    def analyzed(event: Path, *clips: str) -> None:
        for clip in clips:
            write_entry(event, clip, clip_signal(event / clip), [])

    @staticmethod
    def failed(event: Path, clip: str) -> None:
        write_failure(event, clip, clip_signal(event / clip), "moov atom not found")


@pytest.fixture(autouse=True)
def _sweep_logger_enabled() -> Iterator[None]:
    """Re-enable the sweep's logger for ``caplog``: a test that runs Alembic's ``fileConfig``
    earlier in the session disables every logger that existed then."""
    sweep_logger = logging.getLogger("auto_reel_ng.scheduler.analysis_sweep")
    was = sweep_logger.disabled
    sweep_logger.disabled = False
    yield
    sweep_logger.disabled = was


@pytest.fixture
def project(tmp_path: Path) -> Project:
    return Project(tmp_path / "proj")


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


def _sweep(
    store: MemoryStore,
    project: Project,
    *,
    max_events: int = 2,
    config: Optional[ProjectConfig] = None,
) -> AnalysisSweep:
    return AnalysisSweep(
        store,  # type: ignore[arg-type]
        project.root,
        config if config is not None else ProjectConfig(),
        max_events=max_events,
    )


# --------------------------------------------------------------------------- #
# 2.1 what a sweep enqueues
# --------------------------------------------------------------------------- #


def test_only_never_analyzed_and_stale_events_are_enqueued(
    store: MemoryStore, project: Project
) -> None:
    never = project.event("2024-01-01 - Never", "a.mp4")
    stale = project.event("2024-02-01 - Stale", "a.mp4", "b.mp4")
    project.analyzed(stale, "a.mp4", "b.mp4")
    (stale / "b.mp4").write_bytes(b"re-copied, longer than before")
    current = project.event("2024-03-01 - Current", "a.mp4")
    project.analyzed(current, "a.mp4")

    report = _sweep(store, project, max_events=10).sweep_once()

    assert sorted(store.analysis_jobs()) == sorted([project.rel(never), project.rel(stale)])
    assert sorted(report.enqueued) == sorted(store.analysis_jobs())
    assert all(not row.force for row in store.rows)


def test_a_new_clip_makes_an_analyzed_event_due(store: MemoryStore, project: Project) -> None:
    event = project.event("2024-01-01 - Party", "a.mp4")
    project.analyzed(event, "a.mp4")
    assert _sweep(store, project).sweep_once().enqueued == ()
    (event / "b.mp4").write_bytes(b"new clip")
    assert _sweep(store, project).sweep_once().enqueued == (project.rel(event),)


def test_the_cap_holds_and_the_newest_events_go_first(store: MemoryStore, project: Project) -> None:
    names = [f"2024-0{month}-01 - E{month}" for month in range(1, 6)]
    events = [project.event(name, "a.mp4") for name in names]
    project.event("2025-01-01 - Newest", "a.mp4", year="2025")

    report = _sweep(store, project, max_events=2).sweep_once()

    assert report.enqueued == ("2025/2025-01-01 - Newest", project.rel(events[-1]))
    assert len(store.analysis_jobs()) == 2


def test_an_event_whose_only_due_clip_is_failure_marked_is_not_enqueued(
    store: MemoryStore, project: Project
) -> None:
    event = project.event("2024-01-01 - Broken", "a.mp4", "bad.mp4")
    project.analyzed(event, "a.mp4")
    project.failed(event, "bad.mp4")
    for _ in range(3):
        assert _sweep(store, project).sweep_once().enqueued == ()
    (event / "bad.mp4").write_bytes(b"a good copy now")  # the clip changed: due again
    assert _sweep(store, project).sweep_once().enqueued == (project.rel(event),)


@pytest.mark.parametrize(
    "kind,status",
    [
        (JobKind.RENDER, JobStatus.QUEUED),
        (JobKind.PROXY, JobStatus.QUEUED),
        (JobKind.ANALYSIS, JobStatus.QUEUED),
        (JobKind.RENDER, JobStatus.RUNNING),
        (JobKind.PROXY, JobStatus.RUNNING),
    ],
)
def test_the_sweep_is_quiet_while_the_queue_is_busy(
    store: MemoryStore, project: Project, kind: JobKind, status: JobStatus
) -> None:
    other = project.event("2023-05-01 - Other", "a.mp4", year="2023")
    project.event("2024-01-01 - Due", "a.mp4")
    store.add(project.root, other, kind, status)

    report = _sweep(store, project).sweep_once()

    assert report.busy and report.enqueued == ()
    assert [row.event_dir for row in store.rows] == [project.rel(other)]
    assert not any(call.startswith("submit") for call in store.calls)


def test_another_projects_queued_job_does_not_quiet_the_sweep(
    store: MemoryStore, project: Project, tmp_path: Path
) -> None:
    project.event("2024-01-01 - Due", "a.mp4")
    elsewhere = Project(tmp_path / "elsewhere")
    store.add(
        elsewhere.root, elsewhere.event("2024-01-01 - X", "a.mp4"), "render", JobStatus.QUEUED
    )
    assert _sweep(store, project).sweep_once().enqueued == ("2024/2024-01-01 - Due",)


def test_a_running_analysis_job_is_skipped_and_does_not_count_toward_the_cap(
    store: MemoryStore, project: Project
) -> None:
    oldest = project.event("2024-01-01 - A", "a.mp4")
    middle = project.event("2024-02-01 - B", "a.mp4")
    newest = project.event("2024-03-01 - C", "a.mp4")
    store.add(project.root, newest, JobKind.ANALYSIS, JobStatus.RUNNING)

    report = _sweep(store, project, max_events=2).sweep_once()

    assert not report.busy
    assert report.enqueued == (project.rel(middle), project.rel(oldest))
    assert "submit:" + project.rel(newest) not in store.calls


def test_reelignored_and_outside_input_dir_events_are_never_enqueued(
    store: MemoryStore, project: Project
) -> None:
    ignored = project.event("2024-01-01 - Ignored", "a.mp4")
    (ignored / ".reelignore").write_text("", encoding="utf-8")
    project.event("2024-02-01 - Outside", "a.mp4")  # under proj/2024, not proj/media
    inside = Project(project.root / "media").event("2024-03-01 - Inside", "a.mp4")

    report = _sweep(
        store, project, max_events=10, config=ProjectConfig(input_dir=Path("media"))
    ).sweep_once()

    assert report.enqueued == (project.rel(inside),)


def test_a_sweep_reads_metadata_only(
    store: MemoryStore, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    never = project.event("2024-01-01 - Never", "a.mp4")
    stale = project.event("2024-02-01 - Stale", "a.mp4")
    project.analyzed(stale, "a.mp4")
    (stale / "a.mp4").write_bytes(b"changed")
    current = project.event("2024-03-01 - Current", "a.mp4", "reel.yaml")
    project.analyzed(current, "a.mp4")
    before = {
        p: (p.stat().st_mtime_ns, p.read_bytes()) for p in project.root.rglob("*") if p.is_file()
    }

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a process or a content read was started: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(cache_module, "_content_hash", refuse)
    monkeypatch.setattr(cache_module, "analyze_clip", refuse)

    report = _sweep(store, project, max_events=10).sweep_once()

    assert sorted(report.enqueued) == sorted([project.rel(never), project.rel(stale)])
    after = {
        p: (p.stat().st_mtime_ns, p.read_bytes()) for p in project.root.rglob("*") if p.is_file()
    }
    assert after == before  # no file written, touched or added


def test_the_store_is_read_once_per_sweep(store: MemoryStore, project: Project) -> None:
    for month in range(1, 5):
        project.event(f"2024-0{month}-01 - E{month}", "a.mp4")
    _sweep(store, project, max_events=10).sweep_once()
    reads = [call for call in store.calls if not call.startswith("submit")]
    assert sorted(reads) == sorted(
        ["list_by_status:queued:None", "list_by_status:running:None", "latest_by_project:analysis"]
    )


def test_an_empty_project_enqueues_nothing(store: MemoryStore, project: Project) -> None:
    project.event("2024-01-01 - Empty")
    assert _sweep(store, project).sweep_once().enqueued == ()


def test_a_bad_cap_is_refused(store: MemoryStore, project: Project) -> None:
    with pytest.raises(ValueError, match="max_events"):
        _sweep(store, project, max_events=0)


# --------------------------------------------------------------------------- #
# 2.2 back-off after a canceled or failed analysis job
# --------------------------------------------------------------------------- #


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ended(
    store: MemoryStore, project: Project, event: Path, status: JobStatus, *, at: datetime
) -> Row:
    return store.add(
        project.root,
        event,
        JobKind.ANALYSIS,
        status,
        created_at=at - timedelta(seconds=30),
        finished_at=at,
    )


@pytest.mark.parametrize("status", [JobStatus.CANCELED, JobStatus.FAILED])
def test_a_canceled_or_failed_job_is_not_re_enqueued_while_nothing_changes(
    store: MemoryStore, project: Project, status: JobStatus
) -> None:
    event = project.event("2024-01-01 - Party", "a.mp4", "b.mp4")
    project.analyzed(event, "a.mp4")  # b.mp4 still has no entry: it is due
    _ended(store, project, event, status, at=_now() + timedelta(seconds=1))
    for _ in range(3):
        assert _sweep(store, project).sweep_once().enqueued == ()


def test_touching_a_clip_after_the_cancel_makes_the_event_due_again(
    store: MemoryStore, project: Project
) -> None:
    event = project.event("2024-01-01 - Party", "a.mp4", "b.mp4")
    project.analyzed(event, "a.mp4")
    _ended(store, project, event, JobStatus.CANCELED, at=_now())
    time.sleep(0.02)
    os.utime(event / "a.mp4")  # its mtime and ctime move past the job's end
    assert _sweep(store, project).sweep_once().enqueued == (project.rel(event),)


def test_a_clip_copied_in_with_an_old_mtime_still_counts_through_ctime(
    store: MemoryStore, project: Project, tmp_path: Path
) -> None:
    event = project.event("2024-01-01 - Party", "a.mp4")
    camera = tmp_path / "camera.mp4"
    camera.write_bytes(b"straight from the SD card")
    os.utime(camera, (1_000_000_000, 1_000_000_000))  # 2001
    _ended(store, project, event, JobStatus.CANCELED, at=_now())
    time.sleep(0.02)
    shutil.copy2(camera, event / "b.mp4")  # keeps the 2001 mtime; its ctime is now
    assert (event / "b.mp4").stat().st_mtime < 1_000_000_001
    assert _sweep(store, project).sweep_once().enqueued == (project.rel(event),)


def test_a_newer_done_job_lifts_the_back_off(store: MemoryStore, project: Project) -> None:
    event = project.event("2024-01-01 - Party", "a.mp4", "b.mp4")
    project.analyzed(event, "a.mp4")
    later = _now() + timedelta(seconds=60)
    _ended(store, project, event, JobStatus.CANCELED, at=later - timedelta(seconds=10))
    _ended(store, project, event, JobStatus.DONE, at=later)  # b.mp4 was added after it
    assert _sweep(store, project).sweep_once().enqueued == (project.rel(event),)


def test_the_back_off_is_per_event(store: MemoryStore, project: Project) -> None:
    canceled = project.event("2024-02-01 - Canceled", "a.mp4")
    other = project.event("2024-01-01 - Other", "a.mp4")
    _ended(store, project, canceled, JobStatus.CANCELED, at=_now() + timedelta(seconds=1))
    assert _sweep(store, project).sweep_once().enqueued == (project.rel(other),)


def test_a_backed_off_event_does_not_count_toward_the_cap(
    store: MemoryStore, project: Project
) -> None:
    events = [project.event(f"2024-0{m}-01 - E{m}", "a.mp4") for m in (1, 2, 3)]
    _ended(store, project, events[2], JobStatus.FAILED, at=_now() + timedelta(seconds=1))
    report = _sweep(store, project, max_events=2).sweep_once()
    assert report.enqueued == (project.rel(events[1]), project.rel(events[0]))


# --------------------------------------------------------------------------- #
# 2.3 failure isolation and logging
# --------------------------------------------------------------------------- #


class FailingStore(MemoryStore):
    """A store whose ``fail_on`` call raises the driver's connection error."""

    def __init__(self, fail_on: str) -> None:
        super().__init__()
        self.fail_on = fail_on

    def _maybe_fail(self, name: str) -> None:
        if name == self.fail_on:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    def list_by_status(self, status: JobStatus, **kwargs: Any) -> List[Row]:
        self._maybe_fail(f"list_by_status:{status.value}")
        return super().list_by_status(status, **kwargs)

    def latest_by_project(self, project_root: str, **kwargs: Any) -> Dict[str, Row]:
        self._maybe_fail("latest_by_project")
        return super().latest_by_project(project_root, **kwargs)

    def submit(self, project_root: str, event_dir: str, **kwargs: Any) -> Submission:
        self._maybe_fail("submit")
        return super().submit(project_root, event_dir, **kwargs)


@pytest.mark.parametrize(
    "fail_on", ["list_by_status:queued", "list_by_status:running", "latest_by_project", "submit"]
)
def test_a_store_error_ends_the_sweep_with_an_error_log_and_the_next_one_runs(
    project: Project, caplog: pytest.LogCaptureFixture, fail_on: str
) -> None:
    project.event("2024-01-01 - Due", "a.mp4")
    store = FailingStore(fail_on)
    sweep = _sweep(store, project)
    with caplog.at_level("ERROR", logger="auto_reel_ng.scheduler.analysis_sweep"):
        report = sweep.sweep_once()
    assert report.enqueued == () and report.error is not None
    assert "connection refused" in caplog.text
    store.fail_on = ""  # the store is back
    assert sweep.sweep_once().enqueued == ("2024/2024-01-01 - Due",)


def test_a_failing_walk_ends_the_sweep_with_an_error_naming_the_root(
    store: MemoryStore, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    missing = Project(tmp_path / "proj")
    missing.root.rmdir()  # the walk root vanished (an unmounted share)
    with caplog.at_level("ERROR", logger="auto_reel_ng.scheduler.analysis_sweep"):
        report = _sweep(store, missing).sweep_once()
    assert report.enqueued == () and report.error is not None
    assert str(missing.root) in caplog.text
    assert not any(call.startswith("submit") for call in store.calls)


def test_an_unknown_layout_ends_the_sweep_with_an_error(
    store: MemoryStore, project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    project.event("2024-01-01 - Due", "a.mp4")
    with caplog.at_level("ERROR", logger="auto_reel_ng.scheduler.analysis_sweep"):
        report = _sweep(store, project, config=ProjectConfig(layout="nope")).sweep_once()
    assert report.error is not None and "nope" in caplog.text


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 folder")
def test_an_unreadable_event_is_skipped_with_a_warning_and_the_others_still_go(
    store: MemoryStore, project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    good = project.event("2024-01-01 - Good", "a.mp4")
    locked = project.event("2024-02-01 - Locked", "a.mp4")
    locked.chmod(0)
    try:
        with caplog.at_level("WARNING", logger="auto_reel_ng.scheduler.analysis_sweep"):
            report = _sweep(store, project).sweep_once()
    finally:
        locked.chmod(0o755)
    assert report.enqueued == (project.rel(good),) and report.error is None
    assert any(
        record.levelname == "WARNING" and "2024-02-01 - Locked" in record.getMessage()
        for record in caplog.records
    )


def test_a_clip_that_vanishes_mid_sweep_skips_its_event_with_a_warning(
    store: MemoryStore,
    project: Project,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = project.event("2024-01-01 - Good", "a.mp4")
    flaky = project.event("2024-02-01 - Flaky", "a.mp4")
    real_signal = cache_module.clip_signal

    def vanishing(path: Path, **kwargs: Any) -> Dict[str, object]:
        if flaky in Path(path).parents:
            raise FileNotFoundError(2, "No such file or directory", str(path))
        return real_signal(path, **kwargs)

    monkeypatch.setattr(cache_module, "clip_signal", vanishing)
    with caplog.at_level("WARNING", logger="auto_reel_ng.scheduler.analysis_sweep"):
        report = _sweep(store, project).sweep_once()
    assert report.enqueued == (project.rel(good),)
    assert "2024-02-01 - Flaky" in caplog.text


def test_one_info_line_names_what_a_sweep_enqueued(
    store: MemoryStore, project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    project.event("2024-01-01 - A", "a.mp4")
    project.event("2024-02-01 - B", "a.mp4")
    with caplog.at_level("INFO", logger="auto_reel_ng.scheduler.analysis_sweep"):
        report = _sweep(store, project).sweep_once()
    infos = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    assert len(infos) == 1
    assert all(event in infos[0] for event in report.enqueued)
    assert all(str(job_id) in infos[0] for job_id in report.job_ids)
    caplog.clear()
    with caplog.at_level("INFO", logger="auto_reel_ng.scheduler.analysis_sweep"):
        _sweep(store, project).sweep_once()  # busy now: no INFO line
    assert not [r for r in caplog.records if r.levelname == "INFO"]


# --------------------------------------------------------------------------- #
# 2.4 the loop and its thread
# --------------------------------------------------------------------------- #


class CountingSweep(AnalysisSweep):
    """A sweep that counts its runs instead of walking (and can raise on one)."""

    def __init__(self, store: MemoryStore, project: Project, *, raise_on: int = 0) -> None:
        super().__init__(store, project.root, ProjectConfig(), max_events=2)  # type: ignore[arg-type]
        self.sweeps = 0
        self.raise_on = raise_on

    def sweep_once(self) -> SweepReport:
        self.sweeps += 1
        if self.sweeps == self.raise_on:
            raise RuntimeError("an unforeseen bug")
        return SweepReport()


def test_run_sweeps_at_start_then_once_per_interval_until_stopped(
    store: MemoryStore, project: Project
) -> None:
    sweep = CountingSweep(store, project)
    waits: List[float] = []

    def wait(seconds: float) -> bool:
        waits.append(seconds)
        assert sweep.sweeps == len(waits)  # a sweep came before every wait
        return len(waits) == 3  # stopped during the third interval

    sweep.run(threading.Event(), 300.0, wait=wait)
    assert sweep.sweeps == 3 and waits == [300.0, 300.0, 300.0]


def test_run_does_not_sweep_once_stopped(store: MemoryStore, project: Project) -> None:
    sweep = CountingSweep(store, project)
    stop = threading.Event()
    stop.set()
    sweep.run(stop, 300.0)
    assert sweep.sweeps == 0


def test_an_unexpected_error_in_a_sweep_does_not_end_the_loop(
    store: MemoryStore, project: Project, caplog: pytest.LogCaptureFixture
) -> None:
    sweep = CountingSweep(store, project, raise_on=1)
    calls = iter([False, True])
    with caplog.at_level("ERROR", logger="auto_reel_ng.scheduler.analysis_sweep"):
        sweep.run(threading.Event(), 1.0, wait=lambda _s: next(calls))
    assert sweep.sweeps == 2 and "an unforeseen bug" in caplog.text


def test_stopping_during_a_long_interval_is_prompt(store: MemoryStore, project: Project) -> None:
    sweep = CountingSweep(store, project)
    stop = threading.Event()
    thread = start_analysis_sweep(sweep, stop, interval=300.0)
    deadline = time.monotonic() + 5
    while sweep.sweeps == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    started = time.monotonic()
    stop.set()
    thread.join(timeout=5)
    assert not thread.is_alive() and time.monotonic() - started < 1.0
    assert sweep.sweeps == 1 and thread.daemon
