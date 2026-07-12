"""Tests for the events + analysis read routes (tasks 2.2-2.4)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings

pytestmark = pytest.mark.requires_db


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    _touch(root / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö" / "00400.mp4")
    _touch(root / "2024" / "2024-07-04 - Barbecue" / "00500.mp4")
    _touch(root / "2024" / "2024-07-04 - Barbecue" / "clips" / "00600.mp4")
    return root


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_list_events_matches_scan(client: TestClient) -> None:
    response = client.get("/api/v1/events")
    assert response.status_code == 200
    body = response.json()
    ids = {event["event_id"] for event in body}
    assert ids == {
        "2024/2024-06-21 - Midsommar i Dalarna Åäö",
        "2024/2024-07-04 - Barbecue",
    }
    barbecue = next(e for e in body if e["event_id"] == "2024/2024-07-04 - Barbecue")
    assert barbecue["clip_count"] == 2
    assert barbecue["new_count"] == 2
    assert barbecue["missing_count"] == 0


def test_disk_edit_is_visible_on_next_request(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    (event_dir / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Original Title\n", encoding="utf-8"
    )
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")

    first = client.get(f"/api/v1/events/{event_id}")
    assert first.json()["title"] == "Original Title"

    (event_dir / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Updated Title\n", encoding="utf-8"
    )
    second = client.get(f"/api/v1/events/{event_id}")
    assert second.json()["title"] == "Updated Title"


def test_event_identity_round_trips_with_spaces_and_unicode(client: TestClient) -> None:
    listed = client.get("/api/v1/events").json()
    raw_id = next(e["event_id"] for e in listed if "Midsommar" in e["event_id"])
    assert raw_id == "2024/2024-06-21 - Midsommar i Dalarna Åäö"

    encoded = quote(raw_id, safe="/")
    detail = client.get(f"/api/v1/events/{encoded}")
    assert detail.status_code == 200
    assert detail.json()["event_id"] == raw_id


def test_unknown_event_yields_404(client: TestClient) -> None:
    response = client.get("/api/v1/events/2024/does-not-exist")
    assert response.status_code == 404
    assert "title" in response.json()


def test_path_traversal_is_rejected_as_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/events/..%2F..%2Fetc")
    assert response.status_code == 404


def test_unparseable_reel_yaml_is_a_loud_error(client: TestClient, project: Path) -> None:
    event_dir = project / "2024" / "2024-07-04 - Barbecue"
    (event_dir / "reel.yaml").write_text(
        "version: 0\nchapters: [this is not valid: :\n", encoding="utf-8"
    )
    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")

    response = client.get(f"/api/v1/events/{event_id}")
    assert response.status_code == 502
    body = response.json()
    assert "2024/2024-07-04 - Barbecue" in body["detail"]


def test_event_detail_chapters_from_disk_listing_without_document(client: TestClient) -> None:
    event_id = quote("2024/2024-07-04 - Barbecue", safe="/")
    response = client.get(f"/api/v1/events/{event_id}")
    assert response.status_code == 200
    body = response.json()
    chapter_names = {c["name"] for c in body["chapters"]}
    assert chapter_names == {"", "clips"}
    for chapter in body["chapters"]:
        for clip in chapter["clips"]:
            assert clip["status"] == "new"


def test_analysis_absent_is_not_an_empty_result(client: TestClient) -> None:
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")
    response = client.get(f"/api/v1/events/{event_id}/analysis")
    assert response.status_code == 200
    body = response.json()
    assert body["analyzed"] is False
    assert body["segments"] == {}


def test_analysis_populated_returns_segments(client: TestClient, project: Path) -> None:
    from auto_reel_ng.analysis.cache import clip_signal, write_entry
    from auto_reel_ng.analysis.models import Segment, SegmentKind

    event_dir = project / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    clip_path = event_dir / "00400.mp4"
    signal = clip_signal(clip_path)
    write_entry(
        event_dir,
        "00400.mp4",
        signal,
        [Segment(start=0.0, end=1.0, kind=SegmentKind.BLACK, confidence=0.9)],
    )

    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")
    response = client.get(f"/api/v1/events/{event_id}/analysis")
    assert response.status_code == 200
    body = response.json()
    assert body["analyzed"] is True
    assert body["segments"]["00400.mp4"][0]["kind"] == "black"


def test_unknown_event_analysis_yields_404(client: TestClient) -> None:
    response = client.get("/api/v1/events/2024/does-not-exist/analysis")
    assert response.status_code == 404
