"""The analysis enqueues (``analysis-enqueue-api``): one event, and Analyze all.

``POST /api/v1/events/{event_id}/analysis`` and ``POST /api/v1/analysis`` insert job rows and
nothing else: sidecars are hand-built (``analysis_trees``), no worker runs, and any process a
request starts fails the test. Every test builds its own project under ``tmp_path``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import quote

import pytest
from analysis_trees import analyze, fail, replace, snapshot
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from auto_reel_ng.analysis.cache import _entry_path
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobKind, JobStatus

pytestmark = pytest.mark.requires_db

GRILLNING = "2024/2024-06-27 - Grillning med grannar"
BLANDAT = "2024/Blandat"
MIDSOMMAR = "2023/2023-06-23 - Midsommar - Dalarna"
TRASIG = "2024/2024-10-06 - Trasig reel"
TOM = "2024/2024-10-08 - Tom"

CLIPS: Dict[str, List[str]] = {
    GRILLNING: ["00100.mp4", "00200.mp4", "chapter/00300.mp4"],
    BLANDAT: ["a.mp4", "b.mp4", "broken.mp4"],
    MIDSOMMAR: ["C0001.MP4", "C0002.MP4", "C0003.MP4", "C0004.MP4"],
    TRASIG: ["x.mp4"],
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for event_id, identities in CLIPS.items():
        for identity in identities:
            clip = root / event_id / identity
            clip.parent.mkdir(parents=True, exist_ok=True)
            clip.write_bytes(f"clip {event_id} {identity}".encode())
    (root / TRASIG / "reel.yaml").write_text("version: 0\nmetadata: [unterminated\n")
    (root / TOM).mkdir(parents=True)
    (root / TOM / "notes.txt").write_text("no clips here")
    return root


@pytest.fixture
def store(jobs_session_factory) -> JobStore:  # type: ignore[no-untyped-def]
    return JobStore(jobs_session_factory)


@pytest.fixture
def client(project: Path, postgres_container: str, store: JobStore) -> Iterator[TestClient]:
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def no_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any process the request starts fails the test (ffmpeg, ffprobe, anything)."""

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(f"the request started a process: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)


def _url(event_id: str, suffix: str = "analysis") -> str:
    return f"/api/v1/events/{quote(event_id, safe='/')}/{suffix}"


def _rows(store: JobStore, kind: Optional[str] = JobKind.ANALYSIS) -> List[Job]:
    rows = [job for status in JobStatus for job in store.list_by_status(status, kind=kind)]
    return sorted(rows, key=lambda job: job.created_at)


def _analyzed(project: Path, event_id: str) -> None:
    analyze(project / event_id, *CLIPS[event_id])


def _blandat_with_a_failure(project: Path) -> None:
    analyze(project / BLANDAT, "a.mp4", "b.mp4")
    fail(project / BLANDAT, "broken.mp4")


# --------------------------------------------------------------------------- #
# POST /api/v1/events/{event_id}/analysis: 201
# --------------------------------------------------------------------------- #


def test_a_never_analyzed_event_enqueues_a_queued_analysis_job_and_nothing_else(
    client: TestClient, store: JobStore, project: Path, no_processes: None
) -> None:
    before = snapshot(project)

    response = client.post(_url(GRILLNING))

    assert response.status_code == 201, response.text
    job = response.json()
    assert (job["kind"], job["status"], job["event_dir"]) == ("analysis", "queued", GRILLNING)
    assert job["force"] is False and job["fingerprint"] is None
    (row,) = _rows(store)
    assert str(row.id) == job["id"] and row.force is False
    assert [r.id for r in _rows(store, kind=None)] == [row.id]
    assert snapshot(project) == before  # nothing written


def test_a_stale_clip_makes_the_event_enqueue(
    client: TestClient, store: JobStore, project: Path
) -> None:
    _analyzed(project, GRILLNING)
    replace(project / GRILLNING / "00200.mp4")

    response = client.post(_url(GRILLNING))

    assert response.status_code == 201 and response.json()["force"] is False


def test_an_unusable_reel_yaml_does_not_block_analysis(client: TestClient) -> None:
    response = client.post(_url(TRASIG))

    assert response.status_code == 201, response.text


def test_a_running_render_and_a_proxy_job_do_not_block_analysis(
    client: TestClient, store: JobStore, project: Path
) -> None:
    render = store.submit(str(project), GRILLNING, kind=JobKind.RENDER).job_id
    store.claim_next("worker-1")
    store.submit(str(project), GRILLNING, kind=JobKind.PROXY)

    response = client.post(_url(GRILLNING))

    assert response.status_code == 201 and response.json()["kind"] == "analysis"
    held = store.get(render)
    assert held is not None and held.status is JobStatus.RUNNING


# --------------------------------------------------------------------------- #
# 200 fresh
# --------------------------------------------------------------------------- #


def test_an_analyzed_event_is_fresh(client: TestClient, store: JobStore, project: Path) -> None:
    _analyzed(project, MIDSOMMAR)

    response = client.post(_url(MIDSOMMAR))

    assert response.status_code == 200
    assert response.json() == {
        "event_id": MIDSOMMAR,
        "status": "fresh",
        "clip_count": 4,
        "failed_count": 0,
    }
    assert _rows(store) == []


def test_a_failed_clip_alone_does_not_re_enqueue(
    client: TestClient, store: JobStore, project: Path
) -> None:
    _blandat_with_a_failure(project)

    response = client.post(_url(BLANDAT))

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["clip_count"], body["failed_count"]) == ("fresh", 3, 1)
    assert _rows(store) == []


def test_re_analyze_forces_a_job_and_leaves_the_failure_on_disk(
    client: TestClient, store: JobStore, project: Path, no_processes: None
) -> None:
    _blandat_with_a_failure(project)
    marker = _entry_path(project / BLANDAT, "broken.mp4")
    before = marker.read_text()

    response = client.post(_url(BLANDAT), json={"force": True})

    assert response.status_code == 201, response.text
    assert response.json()["force"] is True and response.json()["kind"] == "analysis"
    (row,) = _rows(store)
    assert row.force is True
    assert marker.read_text() == before  # the job overrides it when it runs, not the request


def test_an_empty_body_and_force_false_are_the_default(client: TestClient, project: Path) -> None:
    _analyzed(project, MIDSOMMAR)

    assert client.post(_url(MIDSOMMAR), json={}).status_code == 200
    assert client.post(_url(MIDSOMMAR), json={"force": False}).status_code == 200


def test_forcing_an_event_with_no_clips_creates_nothing(
    client: TestClient, store: JobStore
) -> None:
    response = client.post(_url(TOM), json={"force": True})

    assert response.status_code == 200
    assert response.json() == {
        "event_id": TOM,
        "status": "fresh",
        "clip_count": 0,
        "failed_count": 0,
    }
    assert _rows(store) == []


# --------------------------------------------------------------------------- #
# 409
# --------------------------------------------------------------------------- #


def test_a_repeated_request_is_a_conflict_naming_the_first_job(
    client: TestClient, store: JobStore
) -> None:
    first = client.post(_url(GRILLNING)).json()["id"]

    for body in (None, {"force": False}):
        response = client.post(_url(GRILLNING), json=body)
        assert response.status_code == 409
        problem = response.json()
        assert problem["conflict"] == "active_job" and problem["job_id"] == first

    assert [str(row.id) for row in _rows(store)] == [first]


def test_re_analyze_meets_a_queued_unforced_job_and_forces_it(
    client: TestClient, store: JobStore
) -> None:
    first = client.post(_url(GRILLNING)).json()["id"]

    response = client.post(_url(GRILLNING), json={"force": True})

    assert response.status_code == 409 and response.json()["job_id"] == first
    (row,) = _rows(store)
    assert row.force is True and row.status is JobStatus.QUEUED


def test_re_analyze_meets_a_running_unforced_job_and_leaves_it(
    client: TestClient, store: JobStore
) -> None:
    first = client.post(_url(GRILLNING)).json()["id"]
    claimed = store.claim_next("worker-1")
    assert claimed is not None and str(claimed.id) == first

    response = client.post(_url(GRILLNING), json={"force": True})

    assert response.status_code == 409 and response.json()["job_id"] == first
    (row,) = _rows(store)
    assert row.force is False and row.status is JobStatus.RUNNING


def test_an_enqueue_that_loses_a_race_is_a_conflict(
    client: TestClient, store: JobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Both requests pass the active-job check before either inserts.
    monkeypatch.setattr(client.app.state.job_store, "active_job", lambda *a, **k: None)

    first = client.post(_url(BLANDAT))
    second = client.post(_url(BLANDAT))

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["conflict"] == "active_job"
    assert second.json()["job_id"] == first.json()["id"]
    assert len(_rows(store)) == 1


# --------------------------------------------------------------------------- #
# 404 / 502 / 503
# --------------------------------------------------------------------------- #


def test_an_unknown_event_is_a_404(client: TestClient, store: JobStore) -> None:
    response = client.post(_url("2024/2024-12-24 - Finns inte"))

    assert response.status_code == 404
    assert response.json()["event_id"] == "2024/2024-12-24 - Finns inte"
    assert _rows(store) == []


def test_a_year_folder_is_not_an_event(client: TestClient, store: JobStore) -> None:
    response = client.post(_url("2024"))

    assert response.status_code == 404 and _rows(store) == []


def test_an_event_folder_that_cannot_be_listed_is_a_502(
    client: TestClient, store: JobStore, project: Path
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    event_dir = project / GRILLNING
    event_dir.chmod(0)
    try:
        response = client.post(_url(GRILLNING))
    finally:
        event_dir.chmod(0o755)

    assert response.status_code == 502
    body = response.json()
    assert body["event_id"] == GRILLNING and body["failure"] == "unreadable_disk"
    assert _rows(store) == []


def test_a_cache_entry_that_cannot_be_read_is_a_502_without_a_kind(
    client: TestClient, store: JobStore, project: Path
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root ignores file permissions")
    analyze(project / GRILLNING, "00100.mp4")
    entry = _entry_path(project / GRILLNING, "00100.mp4")
    entry.chmod(0)
    try:
        response = client.post(_url(GRILLNING))
    finally:
        entry.chmod(0o644)

    assert response.status_code == 502
    assert response.json().get("failure") is None and response.json()["event_id"] == GRILLNING
    assert _rows(store) == []


def test_an_unreachable_job_store_is_a_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(*_: Any, **__: Any) -> None:
        raise OperationalError("insert", {}, Exception("connection refused"))

    monkeypatch.setattr(client.app.state.job_store, "submit", down)

    response = client.post(_url(BLANDAT))

    assert response.status_code == 503 and response.json()["check"] == "database"


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #


def test_an_id_with_a_slash_reaches_the_route_and_the_detail_still_answers(
    client: TestClient,
) -> None:
    assert client.post(_url(GRILLNING)).status_code == 201
    detail = client.get(f"/api/v1/events/{quote(GRILLNING, safe='/')}")
    assert detail.status_code == 200 and detail.json()["event_id"] == GRILLNING
