"""Tests for the jobs lifecycle routes (tasks 3.1-3.3)."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.persistence.engine import session_scope
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobStatus
from auto_reel_ng.staleness.manifest import manifest_path

pytestmark = pytest.mark.requires_db

#: The dev library's case-only twins (``scripts/make_dev_library.py``).
KALAS = "2024/2024-07-14 - Kalas"
KALAS_LOWER = "2024/2024-07-14 - kalas"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - A" / "00400.mp4")
    _touch(root / "2024" / "2024-06-22 - B" / "00400.mp4")
    return root


@pytest.fixture
def store(jobs_session_factory) -> JobStore:
    """A store bound to the shared schema, table cleared (function-scoped fixture)."""
    return JobStore(jobs_session_factory)


@pytest.fixture
def client(project: Path, postgres_container: str, store: JobStore):
    # Depends on ``store`` so the ``jobs`` table is cleared before either the
    # app's own engine or this fixture's store queries run (both point at the
    # same Postgres database; only the table-clear ordering matters here).
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_enqueue_creates_queued_job(client: TestClient, store: JobStore) -> None:
    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"
    assert body["event_dir"] == "2024/2024-06-21 - A"
    job = store.get(uuid.UUID(body["id"]))
    assert job is not None
    assert job.status == JobStatus.QUEUED


def test_a_job_carries_the_events_routes_id_as_its_event_dir(client: TestClient) -> None:
    """The contract a client matches jobs to event rows by: ``event_dir == event_id``."""
    rows = client.get("/api/v1/events").json()
    event_id = next(row["event_id"] for row in rows if row["event_id"].endswith(" - A"))

    job = client.post("/api/v1/jobs", json={"event_id": event_id}).json()

    assert job["event_dir"] == event_id


def test_an_enqueue_that_loses_the_race_is_a_conflict(
    client: TestClient, store: JobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert first.status_code == 201
    # Stands in for a concurrent request that inserts after this request's
    # pre-check found nothing: the store's insertion must decide, not the pre-check.
    monkeypatch.setattr(client.app.state.job_store, "active_job", lambda *_: None)

    second = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})

    assert second.status_code == 409
    assert second.json()["job_id"] == first.json()["id"]
    assert second.json()["conflict"] == "active_job"  # the same kind as the pre-check's
    assert len(store.list_by_status(JobStatus.QUEUED)) == 1


def test_duplicate_enqueue_is_a_visible_conflict(client: TestClient, store: JobStore) -> None:
    first = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    second = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert second.status_code == 409
    problem = second.json()
    assert problem["job_id"] == first.json()["id"]
    assert problem["conflict"] == "active_job"
    assert "claimed_by" not in problem
    assert "id" not in problem  # the untyped extra the typed ``job_id`` replaced
    assert len(store.list_by_status(JobStatus.QUEUED)) == 1


def test_terminal_job_does_not_block_new_enqueue(client: TestClient, store: JobStore) -> None:
    first = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = uuid.UUID(first.json()["id"])
    store.claim_next("worker-1")
    store.transition(job_id, JobStatus.DONE)

    second = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert second.status_code == 201
    assert second.json()["id"] != str(job_id)


def test_enqueue_unknown_event_is_404(client: TestClient) -> None:
    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-12-24 - Finns inte"})
    assert response.status_code == 404
    assert response.json()["event_id"] == "2024/2024-12-24 - Finns inte"


def test_enqueue_stamps_fingerprint_and_defaults_force_false(
    client: TestClient, store: JobStore
) -> None:
    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    body = response.json()
    assert body["fingerprint"]
    assert body["force"] is False


def _adopt_and_write_manifest(project: Path, event_id: str) -> None:
    from auto_reel_ng.cli.adoption import persist, prepare_event
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event_dir = project / event_id
    event = prepare_event(event_dir, order=DEFAULT_CLIP_ORDER, adopt=True)
    persist(event)
    runtime = FfmpegRuntime()
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(project)),
        ffmpeg_version=runtime.version,
    )
    output_path = default_output_dir(project) / output_relpath(event.document.metadata)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"already-rendered")
    write_manifest(
        event_dir,
        fingerprint,
        output=output_path.name,
        engine_identity=engine_identity(runtime.version),
    )


def test_fresh_event_is_not_enqueued(client: TestClient, store: JobStore, project: Path) -> None:
    _adopt_and_write_manifest(project, "2024/2024-06-21 - A")

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fresh"
    assert body["event_id"] == "2024/2024-06-21 - A"
    assert body["fingerprint"]
    assert body["manifest"].startswith("2024/2024-06-21 - A/")
    assert store.list_by_status(JobStatus.QUEUED) == []


def test_force_enqueues_a_fresh_event(client: TestClient, store: JobStore, project: Path) -> None:
    _adopt_and_write_manifest(project, "2024/2024-06-21 - A")

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A", "force": True})

    assert response.status_code == 201
    body = response.json()
    assert body["force"] is True
    assert len(store.list_by_status(JobStatus.QUEUED)) == 1


# --------------------------------------------------------------------------- #
# Output collisions on enqueue (jobs-project-guards 3.3)
# --------------------------------------------------------------------------- #


def _add_case_only_twins(project: Path) -> None:
    """Add the dev library's two Kalas events to this test's project.

    ``kalas`` authors its title in lower case, so its output path differs from
    ``Kalas``'s only in letter case: the rule compares paths case-insensitively.
    """
    _touch(project / KALAS / "00400.mp4")
    _touch(project / KALAS_LOWER / "00500.mp4")
    (project / KALAS_LOWER / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: kalas\n", encoding="utf-8"
    )


def _all_jobs(store: JobStore) -> list[Job]:
    return [job for status in JobStatus for job in store.list_by_status(status)]


@pytest.mark.parametrize("force", [False, True], ids=["unforced", "forced"])
def test_an_output_collision_is_refused(
    client: TestClient, store: JobStore, project: Path, force: bool
) -> None:
    _add_case_only_twins(project)

    response = client.post("/api/v1/jobs", json={"event_id": KALAS_LOWER, "force": force})

    assert response.status_code == 409
    problem = response.json()
    assert problem["conflict"] == "output_collision"
    assert problem["claimed_by"] == [KALAS]
    assert problem["event_id"] == KALAS_LOWER
    assert "job_id" not in problem
    assert "2024/2024-07-14 - kalas.mp4" in problem["detail"]
    assert f"also claimed by {KALAS};" in problem["detail"]
    assert "set a distinct title or location in reel.yaml" in problem["detail"]
    assert _all_jobs(store) == []


def test_a_fresh_events_movie_is_protected_from_its_twin(
    client: TestClient, store: JobStore, project: Path
) -> None:
    _add_case_only_twins(project)
    _adopt_and_write_manifest(project, KALAS)
    movie = default_output_dir(project) / "2024" / "2024-07-14 - Kalas.mp4"
    manifest = manifest_path(project / KALAS)
    before = (movie.read_bytes(), manifest.read_bytes())

    response = client.post("/api/v1/jobs", json={"event_id": KALAS})

    assert response.status_code == 409  # checked before the gate: not the 200 "fresh"
    assert response.json()["conflict"] == "output_collision"
    assert response.json()["claimed_by"] == [KALAS_LOWER]
    assert (movie.read_bytes(), manifest.read_bytes()) == before
    assert _all_jobs(store) == []
    # Without its twin the same event is simply fresh: the collision took precedence.
    shutil.rmtree(project / KALAS_LOWER)
    assert client.post("/api/v1/jobs", json={"event_id": KALAS}).status_code == 200


def test_a_collision_outranks_an_active_job(
    client: TestClient, store: JobStore, project: Path
) -> None:
    """Checked first: a job queued before its twin appeared is not the answer."""
    _add_case_only_twins(project)
    active = store.enqueue(str(project), KALAS_LOWER)

    response = client.post("/api/v1/jobs", json={"event_id": KALAS_LOWER})

    assert response.status_code == 409
    problem = response.json()
    assert problem["conflict"] == "output_collision"
    assert "job_id" not in problem
    assert [job.id for job in _all_jobs(store)] == [active]  # nothing new


def test_an_event_outside_any_collision_still_enqueues(client: TestClient, project: Path) -> None:
    _add_case_only_twins(project)

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})

    assert response.status_code == 201


def test_events_that_fail_on_their_own_claim_no_path(client: TestClient, project: Path) -> None:
    _touch(project / "2024" / "2024-02-30 - Omöjligt datum" / "00400.mp4")
    unparseable = project / "2024" / "2024-06-21 - a"  # A's twin, if it parsed
    _touch(unparseable / "00400.mp4")
    (unparseable / "reel.yaml").write_text(": [", encoding="utf-8")

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})

    assert response.status_code == 201


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_a_walk_that_fails_refuses_to_enqueue(
    client: TestClient, store: JobStore, project: Path
) -> None:
    year_dir = project / "2023"
    _touch(year_dir / "2023-06-23 - Midsommar - Dalarna" / "00400.mp4")
    year_dir.chmod(0o000)
    try:
        response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    finally:
        year_dir.chmod(0o755)

    assert response.status_code == 502
    problem = response.json()
    assert problem["title"] == "Bad Gateway"
    assert "event scan failed" in problem["detail"]
    assert _all_jobs(store) == []


def test_list_jobs_filters_by_status(client: TestClient, store: JobStore) -> None:
    client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-22 - B"})
    running_id = store.claim_next("worker-1").id

    response = client.get("/api/v1/jobs", params={"status": "queued"})
    assert response.status_code == 200
    ids = {job["id"] for job in response.json()}
    assert str(running_id) not in ids
    assert len(ids) == 1


def test_get_job_detail(client: TestClient, store: JobStore) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = created.json()["id"]

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == job_id
    assert body["requeue_count"] == 0
    assert body["force"] is False
    assert body["fingerprint"]


def test_get_unknown_job_is_404(client: TestClient) -> None:
    job_id = uuid.uuid4()
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 404
    assert response.json()["job_id"] == str(job_id)


def test_cancel_running_job_flags_without_changing_status(
    client: TestClient, store: JobStore
) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = created.json()["id"]
    store.claim_next("worker-1")

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "flagged-running"
    assert body["status"] == "running"

    job = store.get(uuid.UUID(job_id))
    assert job is not None
    assert job.cancel_requested is True
    assert job.status == JobStatus.RUNNING


def test_cancel_queued_job_cancels_immediately(client: TestClient, store: JobStore) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = created.json()["id"]

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "canceled-queued"
    assert body["status"] == "canceled"


def test_cancel_reports_the_outcome_it_applied_not_an_earlier_read(
    client: TestClient, store: JobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = uuid.UUID(created.json()["id"])
    queued_copy = store.get(job_id)  # read while the job is still queued ...
    store.claim_next("worker-1")  # ... before a worker claims it
    monkeypatch.setattr(client.app.state.job_store, "get", lambda _job_id: queued_copy)

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")

    assert response.status_code == 200
    body = response.json()
    assert (body["outcome"], body["status"]) == ("flagged-running", "running")


@pytest.mark.parametrize("terminal", [JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED])
def test_cancel_terminal_job_is_a_no_op(
    client: TestClient, store: JobStore, terminal: JobStatus
) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = uuid.UUID(created.json()["id"])
    store.claim_next("worker-1")
    store.transition(job_id, terminal)

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "no-op-terminal"
    assert body["status"] == terminal.value


def test_cancel_unknown_job_is_404(client: TestClient, store: JobStore) -> None:
    queued = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"}).json()
    job_id = uuid.uuid4()

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")

    assert response.status_code == 404
    assert response.json()["job_id"] == str(job_id)
    job = store.get(uuid.UUID(queued["id"]))
    assert job is not None
    assert (job.status, job.cancel_requested) == (JobStatus.QUEUED, False)  # no row changed


# --------------------------------------------------------------------------- #
# The served project only (jobs-project-guards 4.1)
# --------------------------------------------------------------------------- #

#: Another library in the same database: its job is only a row, no folder exists.
FOREIGN_ROOT = "/elsewhere/library"


def _job_outside_the_project(
    store: JobStore, session_factory: sessionmaker, project_root: Optional[str]
) -> uuid.UUID:
    """A queued ``2024/Blandat`` job of another project, or with no recorded root."""
    if project_root is not None:
        return store.enqueue(project_root, "2024/Blandat")
    with session_scope(session_factory) as session:
        job = Job(project_root=None, event_dir="2024/Blandat")
        session.add(job)
        session.flush()
        return job.id


@pytest.mark.parametrize("project_root", [FOREIGN_ROOT, None], ids=["foreign", "rootless"])
def test_a_job_outside_the_project_is_not_listed(
    client: TestClient,
    store: JobStore,
    jobs_session_factory: sessionmaker,
    project_root: Optional[str],
) -> None:
    own = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"}).json()
    outside = _job_outside_the_project(store, jobs_session_factory, project_root)

    for params in ({}, {"status": "queued"}):
        listed = client.get("/api/v1/jobs", params=params).json()
        assert [job["id"] for job in listed] == [own["id"]], params
    # The store itself still holds both: only the service's view is scoped.
    assert outside in {job.id for job in store.list_by_status(JobStatus.QUEUED)}


@pytest.mark.parametrize("project_root", [FOREIGN_ROOT, None], ids=["foreign", "rootless"])
def test_a_job_outside_the_project_is_an_unknown_id(
    client: TestClient,
    store: JobStore,
    jobs_session_factory: sessionmaker,
    project_root: Optional[str],
) -> None:
    outside = _job_outside_the_project(store, jobs_session_factory, project_root)
    unknown = client.get(f"/api/v1/jobs/{uuid.uuid4()}").json()

    shown = client.get(f"/api/v1/jobs/{outside}")
    canceled = client.post(f"/api/v1/jobs/{outside}/cancel")

    for response in (shown, canceled):
        assert response.status_code == 404
        problem = response.json()
        assert set(problem) == set(unknown)  # the very shape an unknown id gets
        assert (problem["title"], problem["status"]) == (unknown["title"], unknown["status"])
        assert problem["job_id"] == str(outside)
        assert problem["detail"] == f"no job with id {outside}"
    job = store.get(outside)
    assert job is not None
    assert (job.status, job.cancel_requested) == (JobStatus.QUEUED, False)  # untouched


def test_the_projects_own_jobs_are_served_beside_a_foreign_one(
    client: TestClient, store: JobStore
) -> None:
    store.enqueue(FOREIGN_ROOT, "2024/2024-06-21 - A")  # the same event id, another project
    own = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert own.status_code == 201  # the one-active-job rule is per project too
    job_id = own.json()["id"]

    assert client.get(f"/api/v1/jobs/{job_id}").json()["id"] == job_id
    canceled = client.post(f"/api/v1/jobs/{job_id}/cancel").json()
    assert (canceled["outcome"], canceled["status"]) == ("canceled-queued", "canceled")
    assert [job["id"] for job in client.get("/api/v1/jobs").json()] == [job_id]
