"""End-to-end WS test over podman PG (task 4.4): a real store, a real poller."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import JobStatus

pytestmark = pytest.mark.requires_db

#: Fast enough that a handful of polls fit comfortably inside the test timeout,
#: slow enough not to flake under load.
_POLL_INTERVAL_S = 0.15


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - A" / "00400.mp4")
    return root


@pytest.fixture
def store(jobs_session_factory) -> JobStore:
    return JobStore(jobs_session_factory)


@pytest.fixture
def client(project: Path, postgres_container: str, store: JobStore):
    settings = resolve_api_settings(
        project, env={"DATABASE_URL": postgres_container}, poll_interval=_POLL_INTERVAL_S
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def _read_until_status(websocket, job_id: str, target: str, *, max_reads: int = 8) -> dict:
    """Read WS frames until one reports ``job_id`` at ``target`` status.

    Tolerates an intermediate delta this test doesn't otherwise assert on (e.g. a
    ``queued`` frame that lands between ``enqueue`` and ``claim_next`` if a poll
    tick happens to land between the two calls).
    """
    for _ in range(max_reads):
        message = json.loads(websocket.receive_text())
        for job in message.get("jobs", []):
            if job["id"] == job_id and job["status"] == target:
                return job
    raise AssertionError(f"status {target!r} for job {job_id} not seen within {max_reads} frames")


def test_deltas_arrive_within_a_poll_interval(
    client: TestClient, store: JobStore, project: Path
) -> None:
    with client.websocket_connect("/api/v1/ws/jobs") as websocket:
        snapshot = json.loads(websocket.receive_text())
        assert snapshot["type"] == "snapshot"
        assert snapshot["jobs"] == []

        job_id = store.enqueue(str(project), "2024/2024-06-21 - A")
        store.claim_next("worker-1")

        running = _read_until_status(websocket, str(job_id), "running")
        assert running["progress"] == 0.0

        store.set_progress(job_id, 0.5)
        progressed = _read_until_status(websocket, str(job_id), "running")
        assert progressed["progress"] == 0.5

        store.transition(job_id, JobStatus.DONE)
        done = _read_until_status(websocket, str(job_id), "done")
        assert done["progress"] == 0.5
