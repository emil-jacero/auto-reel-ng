"""Tests for the jobs lifecycle routes (tasks 3.1-3.3)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import JobStatus

pytestmark = pytest.mark.requires_db


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
    job = store.get(uuid.UUID(body["id"]))
    assert job is not None
    assert job.status == JobStatus.QUEUED


def test_duplicate_enqueue_is_a_visible_conflict(client: TestClient, store: JobStore) -> None:
    first = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    second = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    assert second.status_code == 409
    assert second.json()["id"] == first.json()["id"]
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
    response = client.post("/api/v1/jobs", json={"event_id": "2024/does-not-exist"})
    assert response.status_code == 404


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
    from auto_reel_ng.render import output_filename
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event_dir = project / event_id
    event = prepare_event(event_dir, adopt=True)
    persist(event)
    runtime = FfmpegRuntime()
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(project)),
        ffmpeg_version=runtime.version,
    )
    output_path = project / "output" / output_filename(event.document.metadata)
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
    assert body["fingerprint"]
    assert store.list_by_status(JobStatus.QUEUED) == []


def test_force_enqueues_a_fresh_event(client: TestClient, store: JobStore, project: Path) -> None:
    _adopt_and_write_manifest(project, "2024/2024-06-21 - A")

    response = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A", "force": True})

    assert response.status_code == 201
    body = response.json()
    assert body["force"] is True
    assert len(store.list_by_status(JobStatus.QUEUED)) == 1


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
    response = client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


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


def test_cancel_terminal_job_is_a_no_op(client: TestClient, store: JobStore) -> None:
    created = client.post("/api/v1/jobs", json={"event_id": "2024/2024-06-21 - A"})
    job_id = uuid.UUID(created.json()["id"])
    store.claim_next("worker-1")
    store.transition(job_id, JobStatus.DONE)

    response = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "no-op-terminal"
    assert body["status"] == "done"


def test_cancel_unknown_job_is_404(client: TestClient) -> None:
    response = client.post(f"/api/v1/jobs/{uuid.uuid4()}/cancel")
    assert response.status_code == 404
