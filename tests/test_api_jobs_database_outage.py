"""Tests for how the jobs routes fail when the job store cannot be reached.

Covers api-jobs-db-outage-503. The four jobs routes answer an unreachable job store
in the shared problem shape (D-A6): 503 naming ``check="database"``, exactly as the
events reads and ``/healthz`` do — never a bare 500, never a softened answer
(Principle I).

These tests need no container: the engine connects lazily, so an app pointed at a
closed port fails at the first store query itself. They live apart from
``test_api_jobs.py`` because that module is marked ``requires_db`` as a whole.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.openapi import build_openapi_schema
from auto_reel_ng.api.schemas import ProblemOut
from auto_reel_ng.api.settings import resolve_api_settings

#: A reachable-looking URL whose port is closed: any query raises SQLAlchemyError.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nobody:nobody@127.0.0.1:1/nothing"

EVENT_ID = "2024/2024-06-27 - Grillning med grannar"
UNKNOWN_EVENT_ID = "2024/2024-12-24 - Finns inte"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-27 - Grillning med grannar" / "00400.mp4")
    _touch(root / "2024" / "2024-07-14 - Kalas" / "00400.mp4")
    _touch(root / "2024" / "2024-07-14 - kalas" / "00400.mp4")
    return root


@pytest.fixture
def offline_client(project: Path):
    """A client whose database is pointed at nothing; the disk side is healthy."""
    settings = resolve_api_settings(project, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL})
    app = create_app(settings)
    # An unhandled error answers its 500 instead of re-raising into the test, so a
    # missing handler fails as "got 500", the way a client would see it.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _assert_database_problem(response) -> dict:
    assert response.status_code == 503
    body = response.json()
    assert isinstance(body, dict)
    problem = ProblemOut.model_validate(body)
    assert problem.status == 503
    assert problem.title == "Service Unavailable"
    assert problem.check == "database"
    assert problem.detail
    return body


def test_list_reports_an_unreachable_job_store_as_a_database_problem(offline_client) -> None:
    body = _assert_database_problem(offline_client.get("/api/v1/jobs"))
    assert not isinstance(body, list)


def test_detail_reports_an_unreachable_job_store_as_a_database_problem(offline_client) -> None:
    """Not the 404 an unknown id gets: the job could not be read, not shown absent."""
    _assert_database_problem(offline_client.get(f"/api/v1/jobs/{uuid.uuid4()}"))


def test_cancel_reports_an_unreachable_job_store_as_a_database_problem(offline_client) -> None:
    body = _assert_database_problem(offline_client.post(f"/api/v1/jobs/{uuid.uuid4()}/cancel"))
    assert "outcome" not in body


def test_enqueue_reports_an_unreachable_job_store_as_a_database_problem(offline_client) -> None:
    response = offline_client.post("/api/v1/jobs", json={"event_id": EVENT_ID})
    _assert_database_problem(response)


def test_enqueue_forced_reports_an_unreachable_job_store_too(offline_client) -> None:
    response = offline_client.post("/api/v1/jobs", json={"event_id": EVENT_ID, "force": True})
    _assert_database_problem(response)


def test_an_enqueues_disk_checks_still_answer_first(offline_client) -> None:
    """A fact true without the database is not hidden behind the outage."""
    missing = offline_client.post("/api/v1/jobs", json={"event_id": UNKNOWN_EVENT_ID})
    assert missing.status_code == 404
    assert missing.json()["event_id"] == UNKNOWN_EVENT_ID

    collision = offline_client.post("/api/v1/jobs", json={"event_id": "2024/2024-07-14 - kalas"})
    assert collision.status_code == 409
    assert collision.json()["conflict"] == "output_collision"


def test_jobs_and_events_agree_on_the_database_predicate(offline_client) -> None:
    """One predicate for "cannot reach the database" across the surface, not two."""
    events = offline_client.get("/api/v1/events")
    detail = offline_client.get(f"/api/v1/events/{quote(EVENT_ID)}")
    jobs = offline_client.get("/api/v1/jobs")

    responses = (events, detail, jobs)
    assert {r.status_code for r in responses} == {503}
    assert {r.json()["title"] for r in responses} == {"Service Unavailable"}
    assert {r.json()["check"] for r in responses} == {"database"}


def test_the_503_is_logged(offline_client, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        offline_client.get("/api/v1/jobs")
    assert any("job store unreachable" in record.getMessage() for record in caplog.records)


def test_a_non_database_error_is_not_relabelled(project: Path) -> None:
    """Only a SQLAlchemyError is the outage; anything else stays the server's own 500."""
    settings = resolve_api_settings(project, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL})
    app = create_app(settings)

    class _Broken:
        def list_by_status(self, *args: object, **kwargs: object) -> list:
            raise RuntimeError("not a database error")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        app.state.job_store = _Broken()
        response = test_client.get("/api/v1/jobs")
    assert response.status_code == 500


def test_wrapped_routes_keep_their_parameters() -> None:
    """The decorator must not hide ``job_id``, ``status`` or the body from FastAPI."""
    paths = build_openapi_schema()["paths"]
    for path in ("/api/v1/jobs/{job_id}", "/api/v1/jobs/{job_id}/cancel"):
        operation = next(iter(paths[path].values()))
        assert [p["name"] for p in operation["parameters"]] == ["job_id"]
    assert [p["name"] for p in paths["/api/v1/jobs"]["get"]["parameters"]] == ["status"]
    assert "requestBody" in paths["/api/v1/jobs"]["post"]
