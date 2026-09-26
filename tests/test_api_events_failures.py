"""Tests for how the two events reads fail (events-list-client-contract).

An unreachable job store and a failed scan are distinct conditions, both reported
in the shared problem shape (D-A6): 503 naming ``check="database"`` exactly as
``/healthz`` does, and 502 for the scan. Neither read ever degrades into a partial
or a substituted answer (Principle I).

The 503 tests need no container — the engine connects lazily, so an app pointed at
a closed port fails at the job-store read itself.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api import events_read
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.schemas import ProblemOut
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.errors import ReelError

#: A reachable-looking URL whose port is closed: any query raises SQLAlchemyError.
UNREACHABLE_DATABASE_URL = "postgresql+psycopg://nobody:nobody@127.0.0.1:1/nothing"

EVENT_ID = "2024/2024-07-04 - Barbecue"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - Midsommar" / "00400.mp4")
    _touch(root / "2024" / "2024-07-04 - Barbecue" / "00500.mp4")
    return root


@pytest.fixture
def offline_client(project: Path):
    """A client whose database is pointed at nothing; the scan itself is healthy."""
    settings = resolve_api_settings(project, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def _assert_database_problem(response, expected_status: int = 503) -> dict:
    body = response.json()
    assert response.status_code == expected_status
    assert isinstance(body, dict)
    assert body["status"] == expected_status
    assert body["title"] == "Service Unavailable"
    assert body["check"] == "database"
    assert body["detail"]
    return body


def test_list_reports_an_unreachable_job_store_as_a_database_problem(offline_client) -> None:
    _assert_database_problem(offline_client.get("/api/v1/events"))


def test_detail_reports_an_unreachable_job_store_as_a_database_problem(offline_client) -> None:
    body = _assert_database_problem(offline_client.get(f"/api/v1/events/{quote(EVENT_ID)}"))
    assert body["event_id"] == EVENT_ID


def test_both_reads_and_healthz_agree_on_the_database_predicate(offline_client) -> None:
    """One predicate for "cannot reach the database" across all three, not three."""
    health = offline_client.get("/healthz")
    listing = offline_client.get("/api/v1/events")
    detail = offline_client.get(f"/api/v1/events/{quote(EVENT_ID)}")

    assert {r.status_code for r in (health, listing, detail)} == {503}
    assert {r.json()["check"] for r in (health, listing, detail)} == {"database"}


def test_a_failed_list_is_never_partial_and_never_fabricates_an_absent_job(
    offline_client,
) -> None:
    """No list, no rows, no ``latest_job: null`` — absence is reported, not invented."""
    response = offline_client.get("/api/v1/events")

    assert response.status_code == 503
    assert not isinstance(response.json(), list)
    assert "latest_job" not in response.text
    assert "Barbecue" not in response.text


@pytest.mark.requires_db
def test_unparseable_reel_yaml_on_the_list_is_a_scan_problem(client, project: Path) -> None:
    """Distinguishable from the database failure: 502, and no ``check`` field."""
    (project / "2024" / "2024-07-04 - Barbecue" / "reel.yaml").write_text(
        "metadata: [not, a, mapping\n", encoding="utf-8"
    )

    response = client.get("/api/v1/events")
    body = response.json()

    assert response.status_code == 502
    assert body["title"] == "Bad Gateway"
    assert body["status"] == 502
    assert "check" not in body
    assert body["event_id"] == EVENT_ID
    assert not isinstance(body, list)


@pytest.mark.requires_db
def test_the_detail_routes_404_and_502_are_unchanged(client, project: Path) -> None:
    unknown = client.get("/api/v1/events/2024/nope")
    assert unknown.status_code == 404
    assert unknown.json()["title"] == "Not Found"

    (project / "2024" / "2024-07-04 - Barbecue" / "reel.yaml").write_text(
        "metadata: [not, a, mapping\n", encoding="utf-8"
    )
    unreadable = client.get(f"/api/v1/events/{quote(EVENT_ID)}")
    assert unreadable.status_code == 502
    assert unreadable.json()["title"] == "Bad Gateway"


@pytest.mark.requires_db
def test_a_healthy_read_is_unaffected(client) -> None:
    listing = client.get("/api/v1/events")
    assert listing.status_code == 200
    assert len(listing.json()) == 2

    detail = client.get(f"/api/v1/events/{quote(EVENT_ID)}")
    assert detail.status_code == 200
    assert detail.json()["event_id"] == EVENT_ID


# --- The returned bodies conform to the published ``ProblemOut`` shape ---------------


def _validated_problem(response, expected_status: int) -> ProblemOut:
    assert response.status_code == expected_status
    problem = ProblemOut.model_validate(response.json())
    assert problem.status == expected_status
    return problem


def test_database_problem_bodies_match_the_published_shape(offline_client) -> None:
    listing = _validated_problem(offline_client.get("/api/v1/events"), 503)
    assert listing.check == "database"

    detail = _validated_problem(offline_client.get(f"/api/v1/events/{quote(EVENT_ID)}"), 503)
    assert detail.check == "database"
    assert detail.event_id == EVENT_ID


def test_a_whole_scan_problem_body_matches_the_published_shape(
    offline_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The list's non-per-event scan 502 (a bare ``ReelError``) carries no ``event_id``."""

    def failing_scan(*_args: object) -> None:
        raise ReelError("walk root unreadable")

    monkeypatch.setattr(events_read, "list_events", failing_scan)
    problem = _validated_problem(offline_client.get("/api/v1/events"), 502)
    assert problem.check is None
    assert problem.event_id is None


@pytest.mark.requires_db
def test_per_event_and_unknown_event_bodies_match_the_published_shape(
    client, project: Path
) -> None:
    unknown = _validated_problem(client.get("/api/v1/events/2024/nope"), 404)
    assert unknown.event_id == "2024/nope"

    (project / "2024" / "2024-07-04 - Barbecue" / "reel.yaml").write_text(
        "metadata: [not, a, mapping\n", encoding="utf-8"
    )
    listing = _validated_problem(client.get("/api/v1/events"), 502)
    assert listing.event_id == EVENT_ID
    assert listing.check is None

    detail = _validated_problem(client.get(f"/api/v1/events/{quote(EVENT_ID)}"), 502)
    assert detail.event_id == EVENT_ID
