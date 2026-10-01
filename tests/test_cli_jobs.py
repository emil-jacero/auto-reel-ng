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
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
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


def _adopt_and_write_manifest(root: Path, event_dir: Path) -> None:
    """Adopt ``event_dir`` and write a manifest + output at its current fingerprint,
    so it evaluates fresh without a real render."""
    from auto_reel_ng.cli.adoption import persist, prepare_event
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event = prepare_event(event_dir, order=DEFAULT_CLIP_ORDER, adopt=True)
    persist(event)
    runtime = FfmpegRuntime()
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(root)),
        ffmpeg_version=runtime.version,
    )
    output_path = default_output_dir(root) / output_relpath(event.document.metadata)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"already-rendered")
    write_manifest(
        event_dir,
        fingerprint,
        output=output_path.name,
        engine_identity=engine_identity(runtime.version),
    )


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
    assert not (default_output_dir(root)).exists()


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


def test_enqueue_stamps_fingerprint_on_the_job(tmp_path: Path, store: JobStore) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    assert main(["enqueue", str(root)]) == 0
    job = store.list_by_status(JobStatus.QUEUED)[0]
    assert job.fingerprint
    assert job.force is False


def test_enqueue_skips_a_fresh_event(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    _adopt_and_write_manifest(root, root / "2024" / "2024-06-21 - A")

    assert main(["enqueue", str(root)]) == 0
    out = capsys.readouterr().out
    assert "0/1 event(s) newly queued" in out
    assert "fresh, not enqueued" in out
    assert len(store.list_by_status(JobStatus.QUEUED)) == 0


def test_enqueue_force_enqueues_a_fresh_event(tmp_path: Path, store: JobStore) -> None:
    root = _project(tmp_path, "2024-06-21 - A")
    _adopt_and_write_manifest(root, root / "2024" / "2024-06-21 - A")

    assert main(["enqueue", str(root), "--force"]) == 0
    queued = store.list_by_status(JobStatus.QUEUED)
    assert len(queued) == 1
    assert queued[0].force is True


def test_enqueue_mixed_stale_and_fresh_events(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    # headless-cli spec: "one stale and one fresh event -> one queued job for the
    # stale event and the fresh event is reported fresh with no job."
    root = _project(tmp_path, "2024-06-21 - A", "2024-06-22 - B")
    _adopt_and_write_manifest(root, root / "2024" / "2024-06-21 - A")  # A is fresh

    assert main(["enqueue", str(root)]) == 0
    out = capsys.readouterr().out
    assert "1/2 event(s) newly queued" in out
    assert "2024-06-21 - A: fresh, not enqueued" in out
    assert "2024-06-22 - B: queued" in out

    queued = store.list_by_status(JobStatus.QUEUED)
    assert len(queued) == 1
    assert queued[0].event_dir == "2024/2024-06-22 - B"


@pytest.mark.parametrize(
    ("keep_old_movie", "reason"), [(True, "output_renamed"), (False, "output")]
)
def test_enqueue_queues_a_renamed_event_whatever_its_output_reason(
    tmp_path: Path,
    store: JobStore,
    capsys: pytest.CaptureFixture[str],
    keep_old_movie: bool,
    reason: str,
) -> None:
    """The rename reason never changes the decision: queued exactly as a missing movie is."""
    root = _project(tmp_path, "2024-06-21 - A")
    event_dir = root / "2024" / "2024-06-21 - A"
    _adopt_and_write_manifest(root, event_dir)
    reel = event_dir / "reel.yaml"
    reel.write_text(
        reel.read_text(encoding="utf-8").replace("title: A\n", "title: A Renamed\n"),
        encoding="utf-8",
    )
    old_movie = default_output_dir(root) / "2024" / "2024-06-21 - A.mp4"
    if not keep_old_movie:
        old_movie.unlink()

    assert main(["scan", str(root)]) == 0
    assert f"stale: editorial, {reason}" in capsys.readouterr().out

    assert main(["enqueue", str(root)]) == 0
    out = capsys.readouterr().out
    assert "1/1 event(s) newly queued" in out
    assert "2024-06-21 - A: queued" in out
    queued = store.list_by_status(JobStatus.QUEUED)
    assert [job.event_dir for job in queued] == ["2024/2024-06-21 - A"]
    assert queued[0].force is False
    assert old_movie.exists() is keep_old_movie  # enqueue never touches the old movie


# --------------------------------------------------------------------------- #
# worker (6.2 smoke test: enqueue -> worker -> done, output exists)
# --------------------------------------------------------------------------- #


def test_enqueue_refuses_colliding_events(
    tmp_path: Path, store: JobStore, capsys: pytest.CaptureFixture[str]
) -> None:
    # headless-cli spec: "Enqueue refuses colliding events".
    root = _project(
        tmp_path, "2024-06-21 - Midsommar", "2024-06-21 - midsommar", "2024-08-01 - Kalas"
    )

    assert main(["enqueue", str(root)]) == 1

    out = capsys.readouterr().out
    assert out.count("ERROR") == 2
    queued = store.list_by_status(JobStatus.QUEUED)
    assert [job.event_dir for job in queued] == ["2024/2024-08-01 - Kalas"]


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
    assert list(default_output_dir(root).rglob("*.mp4"))


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
