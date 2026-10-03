"""End-to-end WS test over podman PG (task 4.4): a real store, a real poller."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api import ws as ws_module
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.persistence.job_store import CancelOutcome, JobStore
from auto_reel_ng.persistence.models import JobKind, JobStatus

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


def _read_until(
    websocket, job_id: str, matches: Callable[[dict], bool], *, max_reads: int = 8
) -> dict:
    """Read WS frames until one carries a row for ``job_id`` that ``matches``.

    Tolerates an intermediate delta this test doesn't otherwise assert on (e.g. a
    ``queued`` frame that lands between ``enqueue`` and ``claim_next`` if a poll
    tick happens to land between the two calls).
    """
    for _ in range(max_reads):
        message = json.loads(websocket.receive_text())
        for job in message.get("jobs", []):
            if job["id"] == job_id and matches(job):
                return job
    raise AssertionError(f"no matching row for job {job_id} within {max_reads} frames")


def _read_until_status(websocket, job_id: str, target: str, *, max_reads: int = 8) -> dict:
    """Read WS frames until one reports ``job_id`` at ``target`` status."""
    return _read_until(websocket, job_id, lambda job: job["status"] == target, max_reads=max_reads)


def _rows_before_marker(websocket, job_id: str, marker_id: str, *, max_reads: int = 8) -> list:
    """Every row for ``job_id`` in the frames up to the one carrying ``marker_id``.

    A job enqueued as a marker bounds the watch: the hub sends its delta after any
    change committed before it, so a missing row fails here rather than blocking.
    """
    rows: list = []
    for _ in range(max_reads):
        message = json.loads(websocket.receive_text())
        rows += [job for job in message["jobs"] if job["id"] == job_id]
        if any(job["id"] == marker_id for job in message["jobs"]):
            return rows
    raise AssertionError("the marker job's delta never arrived")


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


def test_a_job_that_ends_between_polls_is_pushed_once(
    client: TestClient, store: JobStore, project: Path
) -> None:
    """The real store's finished read and database clock, end to end.

    Enqueue, claim and failure take milliseconds, so a poll rarely sees the job
    active; either way exactly one terminal row may arrive, although every later
    poll's window still holds its ``finished_at``.
    """
    with client.websocket_connect("/api/v1/ws/jobs") as websocket:
        snapshot = json.loads(websocket.receive_text())
        assert snapshot["type"] == "snapshot"

        job_id = store.enqueue(str(project), "2024/2024-10-05 - Trasig")
        store.claim_next("worker-1")
        store.transition(job_id, JobStatus.FAILED, error="ffprobe: invalid data")

        failed = _read_until_status(websocket, str(job_id), "failed")
        assert failed["error"] == "ffprobe: invalid data"

        # Several polls later, an unrelated job's delta marks the end of the watch:
        # no frame before it may carry the failed job again.
        time.sleep(_POLL_INTERVAL_S * 5)
        marker = store.enqueue(str(project), "2024/2024-06-21 - A")
        assert _rows_before_marker(websocket, str(job_id), str(marker)) == []


def test_a_proxy_job_is_followed_on_the_socket_with_its_kind(
    client: TestClient, store: JobStore, project: Path
) -> None:
    """A real store and poller: a client that connects while a proxy job runs gets it in the
    snapshot, then its progress and end as deltas, each marked ``kind: proxy``."""
    job_id = store.enqueue(str(project), "2024/2024-06-21 - A", kind=JobKind.PROXY)
    store.claim_next("worker-1")
    store.set_progress(job_id, 0.4)

    with client.websocket_connect("/api/v1/ws/jobs") as websocket:
        snapshot = json.loads(websocket.receive_text())
        assert snapshot["type"] == "snapshot"
        assert [(job["id"], job["kind"], job["progress"]) for job in snapshot["jobs"]] == [
            (str(job_id), "proxy", 0.4)
        ]

        store.set_progress(job_id, 0.8)
        progressed = _read_until(websocket, str(job_id), lambda job: job["progress"] == 0.8)
        assert progressed["kind"] == "proxy"

        store.transition(job_id, JobStatus.DONE)
        done = _read_until_status(websocket, str(job_id), "done")
        assert done["kind"] == "proxy"

        time.sleep(_POLL_INTERVAL_S * 5)
        marker = store.enqueue(str(project), "2024/2024-06-21 - A")  # a render, as the end mark
        assert _rows_before_marker(websocket, str(job_id), str(marker)) == []


def test_a_cancel_request_is_pushed(client: TestClient, store: JobStore, project: Path) -> None:
    """The flag a running job's cancel sets reaches subscribers with no progress change."""
    with client.websocket_connect("/api/v1/ws/jobs") as websocket:
        json.loads(websocket.receive_text())  # the snapshot

        job_id = store.enqueue(str(project), "2024/2024-08-02 - Badutflykt - Varberg")
        store.claim_next("worker-1")
        store.set_progress(job_id, 0.4)
        running = _read_until(websocket, str(job_id), lambda job: job["progress"] == 0.4)
        assert (running["status"], running["cancel_requested"]) == ("running", False)

        result = store.cancel(job_id)
        assert result is not None and result.outcome is CancelOutcome.FLAGGED_RUNNING

        # The flag's delta is due within about one poll; the marker bounds the wait.
        time.sleep(_POLL_INTERVAL_S * 3)
        marker = store.enqueue(str(project), "2024/2024-06-21 - A")
        rows = _rows_before_marker(websocket, str(job_id), str(marker))
        assert [(job["status"], job["progress"], job["cancel_requested"]) for job in rows] == [
            ("running", 0.4, True)
        ]


def test_an_idle_connection_is_sent_a_heartbeat_after_its_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through ``create_app`` and a real store: snapshot first, then the empty-jobs heartbeat."""
    monkeypatch.setattr(ws_module, "_HEARTBEAT_INTERVAL_S", 0.2)
    with client.websocket_connect("/api/v1/ws/jobs") as websocket:
        assert json.loads(websocket.receive_text())["type"] == "snapshot"
        assert json.loads(websocket.receive_text()) == {"type": "heartbeat", "jobs": []}
