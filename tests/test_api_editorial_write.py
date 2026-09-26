"""Tests for the editorial write route (tasks 2.2-2.4): PUT /api/v1/events/{id}/reel."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.config import default_output_dir

pytestmark = pytest.mark.requires_db


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


REEL_YAML = """\
version: 0
metadata:
  title: Original Title
  date: 2024-07-04
  location: Somewhere
chapters:
  - name: ""
    clips:
      - 00500.mp4
      - clips/00600.mp4
"""

UNICODE_REEL_YAML = """\
version: 0
metadata:
  title: Midsommar
chapters:
  - name: ""
    clips:
      - 00400.mp4
"""

BASE_BODY = {
    "metadata": {"title": "Original Title", "date": "2024-07-04", "location": "Somewhere"},
    "chapters": [{"name": "", "clips": ["00500.mp4", "clips/00600.mp4"]}],
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"

    event_dir = root / "2024" / "2024-07-04 - Barbecue"
    _touch(event_dir / "00500.mp4")
    _touch(event_dir / "clips" / "00600.mp4")
    (event_dir / "reel.yaml").write_text(REEL_YAML, encoding="utf-8")

    unicode_dir = root / "2024" / "2024-06-21 - Midsommar i Dalarna Åäö"
    _touch(unicode_dir / "00400.mp4")
    (unicode_dir / "reel.yaml").write_text(UNICODE_REEL_YAML, encoding="utf-8")

    return root


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def _event_id() -> str:
    return quote("2024/2024-07-04 - Barbecue", safe="/")


def _event_dir(project: Path) -> Path:
    return project / "2024" / "2024-07-04 - Barbecue"


def test_save_persists_and_echoes(client: TestClient, project: Path) -> None:
    body = {
        **BASE_BODY,
        "metadata": {**BASE_BODY["metadata"], "title": "Renamed Barbecue"},
        "chapters": [{"name": "", "clips": ["clips/00600.mp4", "00500.mp4"]}],
    }
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert response.status_code == 200
    result = response.json()
    assert result["document"]["metadata"]["title"] == "Renamed Barbecue"
    assert result["document"]["chapters"][0]["clips"] == ["clips/00600.mp4", "00500.mp4"]
    assert result["staleness"]["stale"] is True  # no manifest exists yet

    text = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")
    assert "Renamed Barbecue" in text


def test_save_makes_a_previously_fresh_event_stale(client: TestClient, project: Path) -> None:
    from auto_reel_ng.cli.adoption import persist, prepare_event
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event_dir = _event_dir(project)
    event = prepare_event(event_dir, adopt=True)
    persist(event)
    runtime = FfmpegRuntime()
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(project)),
        ffmpeg_version=runtime.version,
    )
    output_path = default_output_dir(project) / output_relpath(event.document.metadata)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"already-rendered")
    write_manifest(
        event_dir,
        fingerprint,
        output=output_path.name,
        engine_identity=engine_identity(runtime.version),
    )

    fresh_check = client.get(f"/api/v1/events/{_event_id()}")
    assert fresh_check.json()["staleness"]["stale"] is False

    body = {**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Changed"}}
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert response.status_code == 200
    verdict = response.json()["staleness"]
    assert verdict["stale"] is True
    assert "editorial" in verdict["reasons"]

    follow_up = client.get(f"/api/v1/events/{_event_id()}")
    assert follow_up.json()["staleness"]["stale"] is True

    assert client.get("/api/v1/jobs").json() == []  # the write never enqueues


def test_invalid_state_is_rejected_and_file_unchanged(client: TestClient, project: Path) -> None:
    original = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")
    body = {
        **BASE_BODY,
        # Dangling: a clip properties entry with no chapter reference at all.
        "clips": {"nowhere.mp4": {"exclude": False}},
    }
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert response.status_code == 400
    assert "dangling" in response.json()["detail"]
    assert (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8") == original


def test_unknown_event_yields_404(client: TestClient) -> None:
    response = client.put("/api/v1/events/2024/does-not-exist/reel", json=BASE_BODY)
    assert response.status_code == 404
    assert "title" in response.json()


def test_unknown_field_is_rejected_structurally(client: TestClient) -> None:
    response = client.put(f"/api/v1/events/{_event_id()}/reel", json={**BASE_BODY, "bogus": True})
    assert response.status_code == 422


def test_url_round_trip_with_spaces_and_unicode(client: TestClient) -> None:
    event_id = quote("2024/2024-06-21 - Midsommar i Dalarna Åäö", safe="/")
    body = {
        "metadata": {"title": "Midsommar Reviderad"},
        "chapters": [{"name": "", "clips": ["00400.mp4"]}],
    }
    response = client.put(f"/api/v1/events/{event_id}/reel", json=body)
    assert response.status_code == 200
    assert response.json()["document"]["metadata"]["title"] == "Midsommar Reviderad"


def test_put_of_echoed_document_is_a_noop(client: TestClient, project: Path) -> None:
    first = client.put(f"/api/v1/events/{_event_id()}/reel", json=BASE_BODY)
    assert first.status_code == 200
    echoed = first.json()["document"]
    text_after_first = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")

    second = client.put(f"/api/v1/events/{_event_id()}/reel", json=echoed)
    assert second.status_code == 200
    assert second.json()["document"] == echoed
    assert (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8") == text_after_first


def test_write_etag_equals_the_tag_a_read_would_give(client: TestClient) -> None:
    body = {**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Tagged Barbecue"}}
    written = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert written.status_code == 200
    assert written.headers["ETag"]

    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    assert read.headers["ETag"] == written.headers["ETag"]


def test_unmodified_save_returns_the_tag_it_was_given(client: TestClient) -> None:
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    etag = read.headers["ETag"]

    written = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=read.json(),
        headers={"If-Match": etag},
    )
    assert written.status_code == 200
    assert written.headers["ETag"] == etag


def test_consecutive_conditional_writes_need_no_intervening_read(
    client: TestClient, project: Path
) -> None:
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    first = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**BASE_BODY, "chapters": [{"name": "", "clips": ["clips/00600.mp4", "00500.mp4"]}]},
        headers={"If-Match": read.headers["ETag"]},
    )
    assert first.status_code == 200

    # The tag the first write handed back is the only precondition used here: no
    # GET of /reel happens between the two writes.
    second = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**BASE_BODY, "chapters": [{"name": "", "clips": ["00500.mp4", "clips/00600.mp4"]}]},
        headers={"If-Match": first.headers["ETag"]},
    )
    assert second.status_code == 200
    assert second.json()["document"]["chapters"][0]["clips"] == ["00500.mp4", "clips/00600.mp4"]
    assert "00500.mp4" in (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")


def test_refused_write_hands_back_no_precondition(client: TestClient, project: Path) -> None:
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    stale_etag = read.headers["ETag"]

    # Another writer changes the editorial state under the client.
    client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Someone Else"}},
    )
    text_before = (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8")

    refused = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**BASE_BODY, "metadata": {**BASE_BODY["metadata"], "title": "Lost Update"}},
        headers={"If-Match": stale_etag},
    )
    assert refused.status_code == 412
    assert "ETag" not in refused.headers
    assert (_event_dir(project) / "reel.yaml").read_text(encoding="utf-8") == text_before
