"""Tests for the ``enqueue``, ``worker``, and ``jobs`` subcommands (D-S8).

Real Postgres (podman fixture); ``worker`` runs against real ffmpeg via a tiny
CPU-rendered fixture project so the whole enqueue -> worker -> done path is
exercised end-to-end (task 6.2's smoke test).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from auto_reel_ng.cli.main import main
from auto_reel_ng.persistence.engine import make_engine, make_session_factory
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import JobStatus

pytestmark = pytest.mark.requires_db


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _project(tmp_path: Path, *event_names: str) -> Path:
    root = tmp_path / "proj"
    for name in event_names:
        _touch(root / "2024" / name / "00400.mp4")
    return root


@pytest.fixture
def db_env(postgres_container: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Point ``DATABASE_URL`` at the shared podman container for CLI subcommands."""
    monkeypatch.setenv("DATABASE_URL", postgres_container)
    return postgres_container


@pytest.fixture
def store(db_env: str) -> JobStore:
    engine = make_engine(db_env)
    from auto_reel_ng.persistence.models import Base  # local import: test-only convenience

    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    with engine.begin() as conn:
        from auto_reel_ng.persistence.models import Job

        conn.execute(Job.__table__.delete())
    return JobStore(session_factory)


# --------------------------------------------------------------------------- #
# enqueue
# --------------------------------------------------------------------------- #


def test_enqueue_inserts_one_queued_job_per_event(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A", "2024-06-22 - B")

    assert main(["enqueue", str(root)]) == 0

    queued = store.list_by_status(JobStatus.QUEUED)
    assert len(queued) == 2
    assert {job.project_root for job in queued} == {str(root)}
    out = capsys.readouterr().out
    assert "2/2 event(s) newly queued" in out


def test_enqueue_never_renders_or_writes_output(tmp_path: Path, store: JobStore) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    assert main(["enqueue", str(root)]) == 0
    assert not (root / "output").exists()


def test_enqueue_twice_reports_existing_and_inserts_no_duplicates(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    assert main(["enqueue", str(root)]) == 0
    capsys.readouterr()
    assert main(["enqueue", str(root)]) == 0

    out = capsys.readouterr().out
    assert "0/1 event(s) newly queued" in out
    assert "already queued" in out
    assert len(store.list_by_status(JobStatus.QUEUED)) == 1


# --------------------------------------------------------------------------- #
# worker (6.2 smoke test: enqueue -> worker -> done, output exists)
# --------------------------------------------------------------------------- #


def test_worker_processes_the_queue_end_to_end(
    tmp_path: Path, store: JobStore, runtime, make_clip, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "proj"
    event_dir = root / "2024" / "2024-06-21 - A"
    event_dir.mkdir(parents=True)
    make_clip("proj/2024/2024-06-21 - A/00400.mp4", width=320, height=240, duration=1.0)

    assert main(["enqueue", str(root)]) == 0
    job_id = store.list_by_status(JobStatus.QUEUED)[0].id

    from auto_reel_ng.cli import commands

    # A short-lived worker: stop it after its first empty poll following the one
    # real job, so the CLI test does not hang waiting for SIGINT/SIGTERM.
    real_worker_cls = commands.Worker

    class _OneShotWorker(real_worker_cls):  # type: ignore[misc]
        def run(self, *, max_polls: int = 1) -> None:  # noqa: D102
            super().run(max_polls=max_polls)

    monkeypatch.setattr(commands, "Worker", _OneShotWorker)
    assert main(["worker", str(root), "--device", "cpu"]) == 0

    job = store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.DONE
    assert job.progress == 1.0
    assert list((root / "output").glob("*.mp4"))


# --------------------------------------------------------------------------- #
# jobs list / show / cancel
# --------------------------------------------------------------------------- #


def test_jobs_list_filters_by_status(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A", "2024-06-22 - B")
    assert main(["enqueue", str(root)]) == 0
    queued = store.list_by_status(JobStatus.QUEUED)
    store.claim_next("worker-1")
    capsys.readouterr()

    assert main(["jobs", "list", str(root), "--status", "queued"]) == 0
    out = capsys.readouterr().out
    running_id = next(j.id for j in store.list_by_status(JobStatus.RUNNING))
    assert str(running_id) not in out
    assert any(str(j.id) in out for j in queued)


def test_jobs_show_prints_detail(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    assert main(["enqueue", str(root)]) == 0
    job_id = store.list_by_status(JobStatus.QUEUED)[0].id

    assert main(["jobs", "show", str(root), str(job_id)]) == 0
    out = capsys.readouterr().out
    assert str(job_id) in out
    assert "status:" in out
    assert "queued" in out


def test_jobs_show_unknown_id_exits_nonzero(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path)
    assert main(["jobs", "show", str(root), str(uuid.uuid4())]) == 1


def test_jobs_show_malformed_id_exits_nonzero(tmp_path: Path, store: JobStore) -> None:
    root = _project(tmp_path)
    assert main(["jobs", "show", str(root), "not-a-uuid"]) == 1


def test_jobs_cancel_sets_the_flag_on_a_running_job(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    assert main(["enqueue", str(root)]) == 0
    job_id = store.list_by_status(JobStatus.QUEUED)[0].id
    store.claim_next("worker-1")

    assert main(["jobs", "cancel", str(root), str(job_id)]) == 0
    job = store.get(job_id)
    assert job is not None
    assert job.cancel_requested is True
    assert job.status == JobStatus.RUNNING


def test_jobs_cancel_a_queued_job_cancels_immediately(tmp_path: Path, store: JobStore) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    assert main(["enqueue", str(root)]) == 0
    job_id = store.list_by_status(JobStatus.QUEUED)[0].id

    assert main(["jobs", "cancel", str(root), str(job_id)]) == 0
    job = store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.CANCELED
