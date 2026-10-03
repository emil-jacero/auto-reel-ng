"""``POST /api/v1/events/{event_id}/proxies`` and the job kind (change ``proxy-enqueue-endpoint``).

The route inserts one job row and nothing else: the proxy cache is only read (hand-built
entries, ``proxy_cache_trees``), no ffmpeg or ffprobe starts, and the worker is not running.
Every test builds its own project and cache under ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from proxy_cache_trees import sony_facts, tree, write_entry, write_marker
from sqlalchemy.exc import OperationalError

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import JobKind, JobStatus

pytestmark = pytest.mark.requires_db

GRILLNING = "2024/2024-06-27 - Grillning med grannar"
BLANDAT = "2024/2024-05-01 - Blandat"
TRASIG = "2024/2024-10-06 - Trasig reel"
UTAN_TITEL = "2024/2024-10-07"
TOM = "2024/2024-10-08 - Tom"

#: The clips of the events below, by event: identity -> file content (distinct, so distinct keys).
CLIPS: Dict[str, List[str]] = {
    GRILLNING: ["00100.mp4", "00200.mp4", "chapter/00300.mp4"],
    BLANDAT: ["a.mp4", "b.mp4"],
    TRASIG: ["x.mp4"],
    UTAN_TITEL: ["y.mp4"],
}


def _event_url(event_id: str, suffix: str = "proxies") -> str:
    return f"/api/v1/events/{quote(event_id, safe='/')}/{suffix}"


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
def cache(tmp_path: Path, project: Path) -> Path:
    path = tmp_path / "pcache"
    path.mkdir()
    (project / "config.yaml").write_text(json.dumps({"proxies": {"cache_dir": str(path)}}))
    return path


@pytest.fixture
def store(jobs_session_factory) -> JobStore:  # type: ignore[no-untyped-def]
    return JobStore(jobs_session_factory)


@pytest.fixture
def client(
    project: Path, cache: Path, postgres_container: str, store: JobStore
) -> Iterator[TestClient]:
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


def _prepare(project: Path, cache: Path, event_id: str, *identities: str) -> None:
    """Hand-build a ready cache entry for each named clip of the event (all when none named)."""
    for identity in identities or CLIPS[event_id]:
        write_entry(cache, project / event_id / identity, facts=sony_facts())


def _proxy_rows(store: JobStore, event_id: Optional[str] = None) -> list:
    rows = [
        job
        for status in JobStatus
        for job in store.list_by_status(status, kind=JobKind.PROXY)
        if event_id is None or job.event_dir == event_id
    ]
    return sorted(rows, key=lambda job: job.created_at)


# --------------------------------------------------------------------------- #
# 201: the enqueue
# --------------------------------------------------------------------------- #


def test_an_unprepared_event_enqueues_a_queued_proxy_job_and_does_nothing_else(
    client: TestClient, store: JobStore, cache: Path, no_processes: None
) -> None:
    before = tree(cache)

    response = client.post(_event_url(GRILLNING))

    assert response.status_code == 201
    job = response.json()
    assert job["kind"] == "proxy" and job["status"] == "queued"
    assert job["event_dir"] == GRILLNING  # the events list's id, for a nested id
    assert job["force"] is False and job["fingerprint"] is None
    (row,) = _proxy_rows(store)
    assert str(row.id) == job["id"] and row.kind == "proxy"
    assert tree(cache) == before  # nothing written to the proxy cache
    assert [r.event_dir for r in store.list_by_status(JobStatus.QUEUED, kind=None)] == [GRILLNING]


def test_the_job_carries_the_id_the_events_list_shows(client: TestClient) -> None:
    ids = {row["event_id"] for row in client.get("/api/v1/events").json()}
    assert GRILLNING in ids

    job = client.post(_event_url(GRILLNING)).json()

    assert job["event_dir"] in ids


def test_a_second_request_is_a_conflict_naming_the_first_job(
    client: TestClient, store: JobStore
) -> None:
    first = client.post(_event_url(BLANDAT))

    second = client.post(_event_url(BLANDAT))

    assert second.status_code == 409
    problem = second.json()
    assert problem["conflict"] == "active_job" and problem["job_id"] == first.json()["id"]
    assert len(_proxy_rows(store)) == 1


def test_an_enqueue_that_loses_the_race_is_a_conflict_with_the_winning_jobs_id(
    client: TestClient, store: JobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = client.post(_event_url(BLANDAT))
    assert first.status_code == 201
    # Stands in for a concurrent request that inserts after this one's pre-check found nothing.
    monkeypatch.setattr(client.app.state.job_store, "active_job", lambda *_, **__: None)

    second = client.post(_event_url(BLANDAT))

    assert second.status_code == 409
    assert second.json()["job_id"] == first.json()["id"]
    assert second.json()["conflict"] == "active_job"
    assert len(_proxy_rows(store)) == 1


def test_a_finished_job_does_not_block_the_next_request(
    client: TestClient, store: JobStore
) -> None:
    first = client.post(_event_url(BLANDAT)).json()
    store.cancel_queued(uuid.UUID(first["id"]))

    again = client.post(_event_url(BLANDAT))

    assert again.status_code == 201 and again.json()["id"] != first["id"]


# --------------------------------------------------------------------------- #
# 200: fresh
# --------------------------------------------------------------------------- #


def test_a_prepared_event_is_fresh_and_no_job_is_made(
    client: TestClient, store: JobStore, project: Path, cache: Path, no_processes: None
) -> None:
    _prepare(project, cache, GRILLNING)
    before = tree(cache)

    response = client.post(_event_url(GRILLNING))

    assert response.status_code == 200
    assert response.json() == {"event_id": GRILLNING, "status": "fresh", "clip_count": 3}
    assert _proxy_rows(store) == []
    assert tree(cache) == before


@pytest.mark.parametrize("damage", ["stale", "failed", "absent"])
def test_one_stale_failed_or_absent_clip_makes_the_event_enqueue(
    client: TestClient, store: JobStore, project: Path, cache: Path, damage: str
) -> None:
    _prepare(project, cache, GRILLNING, "00100.mp4", "00200.mp4")
    third = project / GRILLNING / "chapter/00300.mp4"
    if damage == "stale":
        write_entry(cache, third, facts_text="not json")
    elif damage == "failed":
        write_marker(cache, third, {"reason": "moov atom not found"})

    response = client.post(_event_url(GRILLNING))

    assert response.status_code == 201
    assert response.json()["status"] == "queued"
    assert len(_proxy_rows(store)) == 1


def test_a_clip_only_reel_yaml_lists_is_not_a_reason_to_refuse_or_to_enqueue(
    client: TestClient, store: JobStore, project: Path, cache: Path
) -> None:
    (project / BLANDAT / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Blandat\nchapters:\n- name: Main\n  clips: [a.mp4, b.mp4, gone.mp4]\n"
    )
    _prepare(project, cache, BLANDAT)

    fresh = client.post(_event_url(BLANDAT))
    assert (fresh.status_code, fresh.json()["clip_count"]) == (200, 2)

    cache_entries = sorted(cache.iterdir())
    for entry in cache_entries:  # one of the clips on disk loses its proxy
        if entry.is_dir():
            (entry / "filmstrip.jpg").unlink()
            break
    assert client.post(_event_url(BLANDAT)).status_code == 201


def test_ignored_and_excluded_clips_are_prepared_with_the_others(
    client: TestClient, store: JobStore, project: Path, cache: Path
) -> None:
    (project / BLANDAT / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Blandat\nchapters:\n- name: Main\n  clips: [a.mp4]\n"
        "clips:\n  a.mp4:\n    exclude: true\nignore: [b.mp4]\n"
    )
    _prepare(project, cache, BLANDAT, "a.mp4")  # b.mp4 (ignored) has none

    assert client.post(_event_url(BLANDAT)).status_code == 201

    _prepare(project, cache, BLANDAT, "b.mp4")
    for job in _proxy_rows(store):
        store.cancel_queued(job.id)
    fresh = client.post(_event_url(BLANDAT))
    assert (fresh.status_code, fresh.json()["clip_count"]) == (200, 2)


def test_an_event_with_no_clips_is_fresh_with_a_count_of_zero(
    client: TestClient, store: JobStore
) -> None:
    response = client.post(_event_url(TOM))

    assert response.status_code == 200
    assert response.json() == {"event_id": TOM, "status": "fresh", "clip_count": 0}
    assert _proxy_rows(store) == []


def test_an_active_job_is_answered_before_freshness(
    client: TestClient, store: JobStore, project: Path, cache: Path
) -> None:
    job = client.post(_event_url(BLANDAT)).json()
    _prepare(project, cache, BLANDAT)

    response = client.post(_event_url(BLANDAT))

    assert response.status_code == 409 and response.json()["job_id"] == job["id"]


# --------------------------------------------------------------------------- #
# 404 / 502 / 503
# --------------------------------------------------------------------------- #


def test_an_unknown_event_is_a_404_naming_it(client: TestClient, store: JobStore) -> None:
    event_id = "2024/2024-12-24 - Finns inte"

    response = client.post(_event_url(event_id))

    assert response.status_code == 404
    assert response.json()["event_id"] == event_id
    assert _proxy_rows(store) == []


def test_a_directory_the_list_does_not_show_is_a_404(client: TestClient) -> None:
    assert client.post(_event_url("2024")).status_code == 404  # a year folder
    assert client.post(_event_url(f"{GRILLNING}/chapter")).status_code == 404  # a chapter folder


def test_an_unparseable_reel_yaml_and_an_event_without_a_title_still_get_proxies(
    client: TestClient, store: JobStore
) -> None:
    broken = client.post(_event_url(TRASIG))
    untitled = client.post(_event_url(UTAN_TITEL))

    assert (broken.status_code, untitled.status_code) == (201, 201)
    assert {job.event_dir for job in _proxy_rows(store)} == {TRASIG, UTAN_TITEL}


def test_an_event_folder_that_cannot_be_listed_is_a_502_with_the_lists_kind(
    client: TestClient, store: JobStore, project: Path
) -> None:
    folder = project / GRILLNING
    folder.chmod(0o000)
    try:
        response = client.post(_event_url(GRILLNING))
    finally:
        folder.chmod(0o755)

    assert response.status_code == 502
    problem = response.json()
    assert problem["event_id"] == GRILLNING and problem["failure"] == "unreadable_disk"
    assert _proxy_rows(store) == []


def test_a_cache_that_cannot_be_listed_is_a_502_without_a_kind_and_no_row(
    client: TestClient, store: JobStore, cache: Path
) -> None:
    cache.chmod(0o000)
    try:
        response = client.post(_event_url(BLANDAT))
    finally:
        cache.chmod(0o755)

    assert response.status_code == 502
    assert "failure" not in response.json()
    assert _proxy_rows(store) == []


def test_unusable_proxies_settings_are_a_502_and_no_row(
    client: TestClient, store: JobStore, project: Path
) -> None:
    (project / "config.yaml").write_text(json.dumps({"proxies": {"cache_dir": "relative/path"}}))

    response = client.post(_event_url(BLANDAT))

    assert response.status_code == 502 and "failure" not in response.json()
    assert _proxy_rows(store) == []


def test_a_store_that_fails_at_insertion_is_a_503_naming_the_database(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(*_: Any, **__: Any) -> None:
        raise OperationalError("insert", {}, Exception("connection refused"))

    monkeypatch.setattr(client.app.state.job_store, "submit", down)

    response = client.post(_event_url(BLANDAT))

    assert response.status_code == 503 and response.json()["check"] == "database"


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #


def test_an_event_id_with_slashes_reaches_the_route_and_the_detail_is_still_reachable(
    client: TestClient,
) -> None:
    assert client.post(_event_url(GRILLNING)).status_code == 201
    detail = client.get(f"/api/v1/events/{quote(GRILLNING, safe='/')}")
    assert detail.status_code == 200 and detail.json()["event_id"] == GRILLNING


def test_the_detail_and_the_route_agree_on_what_ready_is(
    client: TestClient, project: Path, cache: Path
) -> None:
    _prepare(project, cache, BLANDAT)
    detail = client.get(f"/api/v1/events/{quote(BLANDAT, safe='/')}").json()
    states = {clip["proxy"]["state"] for chapter in detail["chapters"] for clip in chapter["clips"]}
    assert states == {"ready"} and client.post(_event_url(BLANDAT)).status_code == 200

    (
        cache / next(entry.name for entry in cache.iterdir() if entry.is_dir()) / "facts.json"
    ).write_text("not json")
    detail = client.get(f"/api/v1/events/{quote(BLANDAT, safe='/')}").json()
    states = {clip["proxy"]["state"] for chapter in detail["chapters"] for clip in chapter["clips"]}
    assert states == {"ready", "stale"} and client.post(_event_url(BLANDAT)).status_code == 201


# --------------------------------------------------------------------------- #
# a proxy job and a render job of one event do not block each other
# --------------------------------------------------------------------------- #


def _render(client: TestClient, event_id: str) -> Any:
    return client.post("/api/v1/jobs", json={"event_id": event_id})


def test_a_running_proxy_job_does_not_block_a_render_enqueue(
    client: TestClient, store: JobStore
) -> None:
    proxy = store.submit(str(client.app.state.settings.project_root), GRILLNING, kind=JobKind.PROXY)
    store.claim_next("w")  # the proxy job is running
    assert store.get(proxy.job_id).status == JobStatus.RUNNING  # type: ignore[union-attr]

    response = _render(client, GRILLNING)

    assert response.status_code == 201
    assert response.json()["kind"] == "render" and response.json()["status"] == "queued"
    still = store.get(proxy.job_id)
    assert still is not None and still.status == JobStatus.RUNNING and still.kind == "proxy"


def test_a_queued_render_does_not_block_a_proxy_enqueue(
    client: TestClient, store: JobStore
) -> None:
    render = _render(client, GRILLNING).json()

    response = client.post(_event_url(GRILLNING))

    assert response.status_code == 201 and response.json()["kind"] == "proxy"
    row = store.get(uuid.UUID(render["id"]))
    assert row is not None and row.status == JobStatus.QUEUED


def test_with_both_kinds_queued_each_conflict_names_the_job_of_its_own_kind(
    client: TestClient,
) -> None:
    render = _render(client, GRILLNING).json()
    proxy = client.post(_event_url(GRILLNING)).json()

    render_again = _render(client, GRILLNING)
    proxy_again = client.post(_event_url(GRILLNING))

    assert render_again.status_code == 409 and render_again.json()["job_id"] == render["id"]
    assert proxy_again.status_code == 409 and proxy_again.json()["job_id"] == proxy["id"]


def test_cancelling_a_running_proxy_job_flags_it_and_leaves_the_renders_alone(
    client: TestClient, store: JobStore
) -> None:
    root = str(client.app.state.settings.project_root)
    proxy = store.submit(root, BLANDAT, kind=JobKind.PROXY).job_id
    store.claim_next("w")
    render = store.submit(root, BLANDAT, kind=JobKind.RENDER).job_id

    response = client.post(f"/api/v1/jobs/{proxy}/cancel")

    assert response.status_code == 200
    assert response.json()["outcome"] == "flagged-running"
    assert response.json()["status"] == "running"
    flagged, untouched = store.get(proxy), store.get(render)
    assert flagged is not None and flagged.cancel_requested and flagged.status == JobStatus.RUNNING
    assert untouched is not None and not untouched.cancel_requested
    assert untouched.status == JobStatus.QUEUED


def test_cancelling_a_queued_proxy_job_cancels_it(client: TestClient, store: JobStore) -> None:
    proxy = client.post(_event_url(BLANDAT)).json()

    response = client.post(f"/api/v1/jobs/{proxy['id']}/cancel")

    assert response.json()["outcome"] == "canceled-queued"
    assert response.json()["status"] == "canceled"


# --------------------------------------------------------------------------- #
# the job's kind on every read; latest_job is the latest render
# --------------------------------------------------------------------------- #


def test_a_render_job_reads_kind_render_on_every_read(client: TestClient) -> None:
    created = _render(client, GRILLNING).json()

    detail = client.get(f"/api/v1/jobs/{created['id']}").json()
    listed = next(job for job in client.get("/api/v1/jobs").json() if job["id"] == created["id"])
    row = next(r for r in client.get("/api/v1/events").json() if r["event_id"] == GRILLNING)
    event = client.get(f"/api/v1/events/{quote(GRILLNING, safe='/')}").json()

    assert created["kind"] == detail["kind"] == listed["kind"] == "render"
    assert row["latest_job"]["kind"] == event["latest_job"]["kind"] == "render"


def test_the_jobs_list_and_detail_include_proxy_jobs_marked(
    client: TestClient, store: JobStore
) -> None:
    proxy = client.post(_event_url(BLANDAT)).json()
    render = _render(client, GRILLNING).json()

    listed = {job["id"]: job["kind"] for job in client.get("/api/v1/jobs").json()}
    queued = {job["id"] for job in client.get("/api/v1/jobs?status=queued").json()}
    detail = client.get(f"/api/v1/jobs/{proxy['id']}").json()

    assert listed == {proxy["id"]: "proxy", render["id"]: "render"}
    assert queued == {proxy["id"], render["id"]}
    assert (detail["kind"], detail["event_dir"], detail["status"]) == ("proxy", BLANDAT, "queued")


def _latest(client: TestClient, event_id: str) -> Optional[dict]:
    row = next(r for r in client.get("/api/v1/events").json() if r["event_id"] == event_id)
    detail = client.get(f"/api/v1/events/{quote(event_id, safe='/')}").json()
    assert row["latest_job"] == detail["latest_job"]  # the list and the detail agree
    return row["latest_job"]  # type: ignore[no-any-return]


def test_a_newer_proxy_job_does_not_replace_the_latest_render(
    client: TestClient, store: JobStore
) -> None:
    root = str(client.app.state.settings.project_root)
    render = store.submit(root, GRILLNING).job_id
    store.claim_next("w")
    store.transition(render, JobStatus.DONE)
    store.submit(root, GRILLNING, kind=JobKind.PROXY)
    store.claim_next("w")  # the proxy job runs, newer than the render

    latest = _latest(client, GRILLNING)

    assert latest is not None
    assert (latest["id"], latest["kind"], latest["status"]) == (str(render), "render", "done")


def test_an_event_with_only_a_proxy_job_has_no_latest_job(
    client: TestClient, store: JobStore
) -> None:
    job = client.post(_event_url(BLANDAT)).json()
    store.claim_next("w")
    store.transition(uuid.UUID(job["id"]), JobStatus.DONE)

    assert _latest(client, BLANDAT) is None


def test_a_finished_proxy_job_does_not_make_a_failed_render_look_done(
    client: TestClient, store: JobStore
) -> None:
    root = str(client.app.state.settings.project_root)
    render = store.submit(root, BLANDAT).job_id
    store.claim_next("w")
    store.transition(render, JobStatus.FAILED, error="ffprobe: invalid data")
    proxy = store.submit(root, BLANDAT, kind=JobKind.PROXY).job_id
    store.claim_next("w")
    store.transition(proxy, JobStatus.DONE)

    latest = _latest(client, BLANDAT)

    assert latest is not None
    assert (latest["id"], latest["kind"], latest["status"]) == (str(render), "render", "failed")
