"""``GET /api/v1/events/{event_id}/analysis``: the analysis state (``analysis-enqueue-api``).

Sidecars are hand-built (``analysis_trees``); jobs are rows the store inserts and a test
claims, with no worker running. Any process the read starts fails the test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Iterator
from urllib.parse import quote

import pytest
from analysis_trees import analyze, fail, replace, snapshot
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from auto_reel_ng.analysis.cache import _entry_path
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import JobKind
from auto_reel_ng.scheduler import submit_analysis

pytestmark = pytest.mark.requires_db

GRILLNING = "2024/2024-06-27 - Grillning med grannar"
BLANDAT = "2024/Blandat"
MIDSOMMAR = "2023/2023-06-23 - Midsommar - Dalarna"

CLIPS = {
    GRILLNING: ["00100.mp4", "00200.mp4", "chapter/00300.mp4"],
    BLANDAT: ["a.mp4", "b.mp4", "broken.mp4"],
    MIDSOMMAR: ["C0001.MP4", "C0002.MP4", "C0003.MP4", "C0004.MP4", "C0005.MP4"],
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for event_id, identities in CLIPS.items():
        for identity in identities:
            clip = root / event_id / identity
            clip.parent.mkdir(parents=True, exist_ok=True)
            clip.write_bytes(f"clip {event_id} {identity}".encode())
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
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError(f"the request started a process: {args!r}")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)


def _read(client: TestClient, event_id: str) -> Dict[str, Any]:
    response = client.get(f"/api/v1/events/{quote(event_id, safe='/')}/analysis")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def _clip_states(body: Dict[str, Any]) -> Dict[str, str]:
    return {identity: clip["state"] for identity, clip in body["clips"].items()}


def _queue(store: JobStore, project: Path, event_id: str, *, force: bool = False) -> str:
    (submission,) = submit_analysis(store, project, [project / event_id], force=force)
    return str(submission.job_id)


def test_a_never_analyzed_event_reads_never_on_every_clip(client: TestClient) -> None:
    body = _read(client, GRILLNING)

    assert body["state"] == "never" and body["job"] is None
    assert _clip_states(body) == {i: "never" for i in CLIPS[GRILLNING]}
    assert body["segments"] == {} and body["analyzed"] is False


def test_a_render_manifest_does_not_make_an_event_look_analyzed(
    client: TestClient, project: Path
) -> None:
    cache = project / GRILLNING / ".auto-reel" / "cache"
    cache.mkdir(parents=True)
    (cache / "render-manifest.json").write_text("{}")

    body = _read(client, GRILLNING)

    assert body["analyzed"] is True  # legacy: the folder exists
    assert body["state"] == "never"
    assert set(_clip_states(body).values()) == {"never"}


def test_cached_analysis_is_returned_and_current(client: TestClient, project: Path) -> None:
    analyze(project / GRILLNING, *CLIPS[GRILLNING])

    body = _read(client, GRILLNING)

    assert body["state"] == "current"
    assert set(_clip_states(body).values()) == {"current"}
    assert body["segments"]["00100.mp4"][0]["kind"] == "black"
    assert set(body["segments"]) == set(CLIPS[GRILLNING])


def test_a_replaced_clip_is_stale_with_no_segments(client: TestClient, project: Path) -> None:
    analyze(project / GRILLNING, *CLIPS[GRILLNING])
    replace(project / GRILLNING / "00200.mp4")

    body = _read(client, GRILLNING)

    assert body["state"] == "stale"
    assert _clip_states(body) == {
        "00100.mp4": "current",
        "00200.mp4": "stale",
        "chapter/00300.mp4": "current",
    }
    assert "00200.mp4" not in body["segments"] and "00100.mp4" in body["segments"]


def test_a_new_clip_reads_never_in_a_stale_event(client: TestClient, project: Path) -> None:
    analyze(project / GRILLNING, *CLIPS[GRILLNING])
    (project / GRILLNING / "00400.mp4").write_bytes(b"a fourth clip")

    body = _read(client, GRILLNING)

    assert body["state"] == "stale" and body["clips"]["00400.mp4"]["state"] == "never"


def test_a_failed_clip_is_reported_with_its_reason(client: TestClient, project: Path) -> None:
    analyze(project / BLANDAT, "a.mp4", "b.mp4")
    fail(project / BLANDAT, "broken.mp4", "moov atom not found")

    body = _read(client, BLANDAT)

    assert body["state"] == "failed"
    assert body["clips"]["broken.mp4"] == {"state": "failed", "detail": "moov atom not found"}
    assert body["clips"]["a.mp4"] == {"state": "current", "detail": None}


def test_a_running_job_is_reported_with_its_progress(
    client: TestClient, project: Path, store: JobStore
) -> None:
    analyze(project / MIDSOMMAR, "C0001.MP4", "C0002.MP4")
    job_id = _queue(store, project, MIDSOMMAR)
    claimed = store.claim_next("worker-1")
    assert claimed is not None and str(claimed.id) == job_id
    store.set_progress(claimed.id, 0.4)

    body = _read(client, MIDSOMMAR)

    assert body["state"] == "analyzing"
    job = body["job"]
    assert (job["id"], job["kind"], job["status"]) == (job_id, "analysis", "running")
    assert job["progress"] == pytest.approx(0.4)
    assert _clip_states(body) == {
        "C0001.MP4": "current",
        "C0002.MP4": "current",
        "C0003.MP4": "analyzing",
        "C0004.MP4": "analyzing",
        "C0005.MP4": "analyzing",
    }


def test_a_forced_job_leaves_current_clips_current(
    client: TestClient, project: Path, store: JobStore
) -> None:
    analyze(project / GRILLNING, *CLIPS[GRILLNING])
    job_id = _queue(store, project, GRILLNING, force=True)

    body = _read(client, GRILLNING)

    assert body["state"] == "analyzing" and body["job"]["id"] == job_id
    assert body["job"]["force"] is True and body["job"]["status"] == "queued"
    assert set(_clip_states(body).values()) == {"current"}
    assert set(body["segments"]) == set(CLIPS[GRILLNING])


def test_a_failed_clip_reads_analyzing_only_under_a_forced_job(
    client: TestClient, project: Path, store: JobStore
) -> None:
    analyze(project / BLANDAT, "a.mp4", "b.mp4")
    fail(project / BLANDAT, "broken.mp4")
    _queue(store, project, BLANDAT)

    unforced = _read(client, BLANDAT)
    assert unforced["state"] == "analyzing"
    assert unforced["clips"]["broken.mp4"]["state"] == "failed"

    _queue(store, project, BLANDAT, force=True)  # forces the queued job (the gate's rule)
    forced = _read(client, BLANDAT)
    assert forced["clips"]["broken.mp4"]["state"] == "analyzing"
    assert forced["clips"]["a.mp4"]["state"] == "current"


def test_a_finished_job_is_not_reported(client: TestClient, project: Path, store: JobStore) -> None:
    from auto_reel_ng.persistence.models import JobStatus

    _queue(store, project, GRILLNING)
    claimed = store.claim_next("worker-1")
    assert claimed is not None
    store.transition(claimed.id, JobStatus.DONE)

    body = _read(client, GRILLNING)

    assert body["job"] is None and body["state"] == "never"


def test_reading_the_state_starts_nothing_and_writes_nothing(
    client: TestClient, project: Path, store: JobStore, no_processes: None
) -> None:
    analyze(project / GRILLNING, "00100.mp4")
    replace(project / GRILLNING / "00100.mp4")
    before = snapshot(project)

    body = _read(client, GRILLNING)

    assert body["state"] == "stale"
    assert snapshot(project) == before
    assert store.latest_by_project(str(project), kind=JobKind.ANALYSIS) == {}


def test_an_unreadable_cache_entry_is_a_502_without_a_kind(
    client: TestClient, project: Path
) -> None:
    analyze(project / GRILLNING, "00100.mp4")
    entry = _entry_path(project / GRILLNING, "00100.mp4")
    entry.chmod(0)
    try:
        response = client.get(f"/api/v1/events/{quote(GRILLNING, safe='/')}/analysis")
    finally:
        entry.chmod(0o644)

    assert response.status_code == 502
    body = response.json()
    assert body["event_id"] == GRILLNING and body.get("failure") is None
    assert "00100.mp4" in body["detail"]


def test_an_unreachable_job_store_is_a_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(*_: Any, **__: Any) -> None:
        raise OperationalError("select", {}, Exception("connection refused"))

    monkeypatch.setattr(client.app.state.job_store, "active_job", down)

    response = client.get(f"/api/v1/events/{quote(BLANDAT, safe='/')}/analysis")

    assert response.status_code == 503
    body = response.json()
    assert body["check"] == "database" and "state" not in body


def test_an_event_with_no_clips_is_current_with_no_clips(client: TestClient, project: Path) -> None:
    empty = "2024/2024-10-08 - Tom"
    (project / empty).mkdir(parents=True)
    (project / empty / "notes.txt").write_text("no clips here")

    body = _read(client, empty)

    assert body["state"] == "current" and body["clips"] == {}
