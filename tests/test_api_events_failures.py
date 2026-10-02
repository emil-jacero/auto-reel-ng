"""Tests for how the two events reads fail.

Covers events-list-client-contract, events-list-error-rows and event-detail-client-contract.
An unreachable job store and a failed scan are distinct conditions, both reported
in the shared problem shape (D-A6): 503 naming ``check="database"`` exactly as
``/healthz`` does, and 502 for the scan. Neither read ever degrades into a partial
or a substituted answer (Principle I). On the list, one unreadable event is an
error row in place of its summary, never a failed request (per-event isolation);
on the detail, the same event is a 502 carrying the same failure kind and detail.

The 503 tests need no container — the engine connects lazily, so an app pointed at
a closed port fails at the job-store read itself.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, ContextManager, Iterator
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api import events_read
from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.schemas import ProblemOut
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.errors import ReelError
from auto_reel_ng.ingest import LayoutError

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


def _rows_by_kind(response) -> tuple[list[dict], list[dict]]:
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    summaries = [row for row in rows if row["kind"] == "event"]
    errors = [row for row in rows if row["kind"] == "error"]
    assert len(summaries) + len(errors) == len(rows)
    return summaries, errors


@pytest.mark.requires_db
def test_unparseable_reel_yaml_on_the_list_is_an_error_row(client, project: Path) -> None:
    """One bad event among three costs one row: two summaries and one error row."""
    _touch(project / "2024" / "2024-08-01 - Kräftskiva" / "00600.mp4")
    (project / "2024" / "2024-07-04 - Barbecue" / "reel.yaml").write_text(
        "metadata: [not, a, mapping\n", encoding="utf-8"
    )

    summaries, errors = _rows_by_kind(client.get("/api/v1/events"))

    assert len(summaries) == 2
    assert EVENT_ID not in {row["event_id"] for row in summaries}
    assert len(errors) == 1
    (error,) = errors
    assert error["event_id"] == EVENT_ID
    assert error["failure"] == "unparseable_reel_yaml"
    assert error["detail"]
    # No fact that could not be read is carried, not even as null.
    assert set(error) == {"kind", "event_id", "failure", "detail"}


@pytest.mark.requires_db
@pytest.mark.parametrize(
    ("content", "named"),
    [
        pytest.param(
            b"version: 0\nmetadata:\n  title: Barbecue\n  date: 2024-02-30\n",
            "'2024-02-30'",
            id="impossible-date",
        ),
        pytest.param(
            "version: 0\nmetadata:\n  title: Grillkväll\n".encode("latin-1"),
            "not UTF-8 text",
            id="latin-1",
        ),
    ],
)
def test_an_impossible_reel_yaml_date_is_an_error_row_not_a_500(
    client, project: Path, content: bytes, named: str
) -> None:
    """A value or a byte the YAML reader cannot load was a 500 for the whole list."""
    _touch(project / "2024" / "2024-08-01 - Kräftskiva" / "00600.mp4")
    (project / EVENT_ID / "reel.yaml").write_bytes(content)

    summaries, errors = _rows_by_kind(client.get("/api/v1/events"))

    assert len(summaries) == 2
    (error,) = errors
    assert error["event_id"] == EVENT_ID
    assert error["failure"] == "unparseable_reel_yaml"
    assert named in error["detail"]

    # The event's own reads are the classified 502, the document read included.
    for path in (f"/api/v1/events/{quote(EVENT_ID)}", f"/api/v1/events/{quote(EVENT_ID)}/reel"):
        problem = _validated_problem(client.get(path), 502)
        assert problem.event_id == EVENT_ID
        assert problem.failure == "unparseable_reel_yaml"
        assert named in problem.detail


@pytest.mark.requires_db
def test_a_year_only_event_on_the_list_is_an_unusable_metadata_row(client, project: Path) -> None:
    _touch(project / "2004" / "2004 - Yngve berättar om skövde" / "00100.mp4")

    summaries, errors = _rows_by_kind(client.get("/api/v1/events"))

    assert len(summaries) == 2
    (error,) = errors
    assert error["event_id"] == "2004/2004 - Yngve berättar om skövde"
    assert error["failure"] == "unusable_metadata"
    assert "year only" in error["detail"]
    assert "metadata.date" in error["detail"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
@pytest.mark.requires_db
def test_an_unreadable_event_directory_is_an_unreadable_disk_row(client, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    event_dir.chmod(0o000)
    try:
        response = client.get("/api/v1/events")
    finally:
        event_dir.chmod(0o755)

    summaries, errors = _rows_by_kind(response)
    assert len(summaries) == 1
    (error,) = errors
    assert error["event_id"] == EVENT_ID
    assert error["failure"] == "unreadable_disk"
    assert error["detail"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
@pytest.mark.requires_db
def test_an_unsearchable_event_directory_is_an_error_row_not_an_empty_summary(
    client, project: Path
) -> None:
    with _unsearchable_event_dir(project):
        response = client.get("/api/v1/events")

    summaries, errors = _rows_by_kind(response)
    assert len(summaries) == 1
    assert summaries[0]["event_id"] != EVENT_ID
    (error,) = errors
    assert error["event_id"] == EVENT_ID
    assert error["failure"] == "unreadable_disk"
    assert error["detail"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unreadable_walk_root_is_a_scan_problem(offline_client, project: Path) -> None:
    """The walk failing accounts for no event: a whole-list 502, never an unshaped 500.

    No database is needed: the walk runs before the job store is consulted.
    """
    year_dir = project / "2024"
    year_dir.chmod(0o000)
    try:
        response = offline_client.get("/api/v1/events")
    finally:
        year_dir.chmod(0o755)

    problem = _validated_problem(response, 502)
    assert problem.title == "Bad Gateway"
    assert "event scan failed" in problem.detail
    assert problem.check is None
    assert problem.event_id is None


@pytest.mark.parametrize("error", [LayoutError("bad layout"), OSError(13, "Permission denied")])
def test_a_walk_failure_is_a_scan_problem(
    offline_client, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def failing_walk(*_args: object) -> None:
        raise error

    monkeypatch.setattr(events_read, "_list_event_refs", failing_walk)
    problem = _validated_problem(offline_client.get("/api/v1/events"), 502)
    assert "event scan failed" in problem.detail


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
    assert {row["kind"] for row in listing.json()} == {"event"}

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
    detail = _validated_problem(client.get(f"/api/v1/events/{quote(EVENT_ID)}"), 502)
    assert detail.event_id == EVENT_ID


# --- The detail classifies per-event failures by the list's rule --------------------

GOLF_ID = "2019/2019-04-31 - Golfträning med Emil - Tjörn"


@contextmanager
def _unparseable_reel_yaml(project: Path) -> Iterator[str]:
    (project / EVENT_ID / "reel.yaml").write_text("metadata: [not, a, mapping\n", encoding="utf-8")
    yield EVENT_ID


@contextmanager
def _impossible_folder_date(project: Path) -> Iterator[str]:
    _touch(project / GOLF_ID / "00100.mp4")
    yield GOLF_ID


@contextmanager
def _unreadable_event_dir(project: Path) -> Iterator[str]:
    event_dir = project / EVENT_ID
    event_dir.chmod(0o000)
    try:
        yield EVENT_ID
    finally:
        event_dir.chmod(0o755)


@contextmanager
def _unsearchable_event_dir(project: Path) -> Iterator[str]:
    """Listable but not searchable (``0600``), holding a reel.yaml: once read as an empty event."""
    event_dir = project / EVENT_ID
    (event_dir / "reel.yaml").write_text("version: 0\nmetadata:\n  title: Real\n", encoding="utf-8")
    event_dir.chmod(0o600)
    try:
        yield EVENT_ID
    finally:
        event_dir.chmod(0o755)


BrokenEvent = Callable[[Path], ContextManager[str]]

#: One broken event per failure kind, with the kind both reads must report for it.
BROKEN_EVENTS = [
    pytest.param(_unparseable_reel_yaml, "unparseable_reel_yaml", id="unparseable_reel_yaml"),
    pytest.param(_impossible_folder_date, "unusable_metadata", id="unusable_metadata"),
    pytest.param(
        _unreadable_event_dir,
        "unreadable_disk",
        id="unreadable_disk",
        marks=pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions"),
    ),
    pytest.param(
        _unsearchable_event_dir,
        "unreadable_disk",
        id="unsearchable_dir",
        marks=pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions"),
    ),
]


@pytest.mark.requires_db
@pytest.mark.parametrize(("broken", "failure"), BROKEN_EVENTS)
def test_a_broken_event_detail_is_a_classified_scan_problem(
    client, project: Path, broken: BrokenEvent, failure: str
) -> None:
    """A 502 naming the event and its kind; an unreadable directory was a bare 500."""
    with broken(project) as event_id:
        response = client.get(f"/api/v1/events/{quote(event_id)}")

    problem = _validated_problem(response, 502)
    assert problem.title == "Bad Gateway"
    assert problem.event_id == event_id
    assert problem.failure == failure
    assert problem.check is None
    assert problem.detail


@pytest.mark.requires_db
def test_an_impossible_folder_date_detail_names_the_fix(client, project: Path) -> None:
    with _impossible_folder_date(project) as event_id:
        problem = _validated_problem(client.get(f"/api/v1/events/{quote(event_id)}"), 502)

    assert "2019-04-31 is not a real date" in problem.detail
    # Unprefixed: the engine's own text, exactly as the list's error row carries it.
    assert not problem.detail.startswith("event ")


@pytest.mark.requires_db
@pytest.mark.parametrize(("broken", "failure"), BROKEN_EVENTS)
def test_list_and_detail_agree_on_why_an_event_cannot_be_read(
    client, project: Path, broken: BrokenEvent, failure: str
) -> None:
    """Agreement by construction: the same kind and the same detail on both reads."""
    with broken(project) as event_id:
        listing = client.get("/api/v1/events")
        detail = client.get(f"/api/v1/events/{quote(event_id)}")

    _summaries, errors = _rows_by_kind(listing)
    (row,) = [error for error in errors if error["event_id"] == event_id]
    problem = _validated_problem(detail, 502)
    assert row["failure"] == problem.failure == failure
    assert row["detail"] == problem.detail
