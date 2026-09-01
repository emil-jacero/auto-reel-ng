"""Tests for the editorial read route and the write's ``If-Match`` precondition.

``GET /api/v1/events/{id}/reel`` is the exact inverse of the PUT: the same model,
built by the same serializer, so a GUI can submit what it read. These tests pin
that round-trip, the two edge cases of D-R2, the ETag's canonicity (D-R1) and the
conditional write of D-R3.
"""

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


REEL_YAML = """\
version: 0
metadata:
  title: Original Title
  date: 2024-07-04
  location: Somewhere
look:
  resolution: 1080p
  fps: 30
chapters:
  - name: ""
    clips:
      - 00500.mp4
      - clips/00600.mp4
clips:
  00500.mp4:
    trims:
      - {in: 0.0, out: 1.5, reason: black}
    rotate: 90
ignore:
  - clips/00700.mp4
"""

BARE_YAML = """\
version: 0
metadata:
  title: Bare
chapters:
  - name: ""
    clips:
      - 00800.mp4
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Three events: one fully authored, one with clips but no document, one broken."""
    root = tmp_path / "proj"

    event_dir = root / "2024" / "2024-07-04 - Barbecue"
    _touch(event_dir / "00500.mp4")
    _touch(event_dir / "clips" / "00600.mp4")
    _touch(event_dir / "clips" / "00700.mp4")  # listed in ``ignore``
    _touch(event_dir / "clips" / "00800.mp4")  # on disk, unknown to the document -> NEW
    (event_dir / "reel.yaml").write_text(REEL_YAML, encoding="utf-8")

    unsaved = root / "2024" / "2024-08-01 - Unsaved"
    _touch(unsaved / "00900.mp4")

    broken = root / "2024" / "2024-09-01 - Broken"
    _touch(broken / "01000.mp4")
    (broken / "reel.yaml").write_text("version: 0\nchapters: not-a-list\n", encoding="utf-8")

    return root


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):
    settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def _event_id(name: str = "2024/2024-07-04 - Barbecue") -> str:
    return quote(name, safe="/")


def _event_dir(project: Path, name: str = "2024/2024-07-04 - Barbecue") -> Path:
    return project / name


# --- task 2.1: the read itself ----------------------------------------------


def test_read_returns_the_full_editorial_state(client: TestClient) -> None:
    """Trims, ``ignore`` and ``look`` all come back — none appear in the detail view."""
    response = client.get(f"/api/v1/events/{_event_id()}/reel")
    assert response.status_code == 200
    body = response.json()

    assert body["metadata"] == {
        "title": "Original Title",
        "date": "2024-07-04",
        "location": "Somewhere",
        "description": None,
    }
    assert body["look"] == {"resolution": "1080p", "fps": 30}
    assert body["chapters"] == [{"name": "", "clips": ["00500.mp4", "clips/00600.mp4"]}]
    assert body["clips"]["00500.mp4"]["trims"] == [{"in": 0.0, "out": 1.5, "reason": "black"}]
    assert body["clips"]["00500.mp4"]["rotate"] == 90
    assert body["ignore"] == ["clips/00700.mp4"]

    detail = client.get(f"/api/v1/events/{_event_id()}").json()
    assert "look" not in detail
    assert "ignore" not in detail
    assert "clips" not in detail


def test_read_of_unknown_event_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/events/2024/nope/reel")
    assert response.status_code == 404
    assert response.json()["title"] == "Not Found"


# --- task 2.2: the two edge cases (D-R2) ------------------------------------


def test_event_without_reel_yaml_reads_as_the_empty_document(
    client: TestClient, project: Path
) -> None:
    """Mirrors the write's own seeding: 200 with the empty document, and no file created."""
    event_id = _event_id("2024/2024-08-01 - Unsaved")
    response = client.get(f"/api/v1/events/{event_id}/reel")
    assert response.status_code == 200
    body = response.json()
    assert body["chapters"] == []
    assert body["clips"] == {}
    assert body["ignore"] == []
    assert body["look"] == {}
    assert body["metadata"]["title"] is None

    assert not (_event_dir(project, "2024/2024-08-01 - Unsaved") / "reel.yaml").exists()


def test_unparseable_document_is_loud(client: TestClient) -> None:
    """Never an empty or partial document (Principle I) — a problem body naming the event."""
    event_id = _event_id("2024/2024-09-01 - Broken")
    response = client.get(f"/api/v1/events/{event_id}/reel")
    assert response.status_code == 502
    body = response.json()
    assert body["event_id"] == "2024/2024-09-01 - Broken"
    assert "chapters" in body["detail"]


# --- task 2.3: the ETag -----------------------------------------------------


def test_etag_ignores_comments_but_tracks_editorial_change(
    client: TestClient, project: Path
) -> None:
    reel_path = _event_dir(project) / "reel.yaml"
    original = client.get(f"/api/v1/events/{_event_id()}/reel").headers["ETag"]
    assert original.startswith('"')

    reel_path.write_text(
        "# a hand-written note\n" + REEL_YAML.replace("chapters:", "\nchapters:  # order matters"),
        encoding="utf-8",
    )
    assert client.get(f"/api/v1/events/{_event_id()}/reel").headers["ETag"] == original

    reel_path.write_text(REEL_YAML.replace("Original Title", "Renamed"), encoding="utf-8")
    assert client.get(f"/api/v1/events/{_event_id()}/reel").headers["ETag"] != original


# --- task 2.4: the conditional write (D-R3) ---------------------------------


def test_matching_if_match_writes(client: TestClient) -> None:
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    body = read.json()
    body["metadata"]["title"] = "Renamed Barbecue"

    response = client.put(
        f"/api/v1/events/{_event_id()}/reel", json=body, headers={"If-Match": read.headers["ETag"]}
    )
    assert response.status_code == 200
    assert response.json()["document"]["metadata"]["title"] == "Renamed Barbecue"


def test_star_if_match_writes(client: TestClient) -> None:
    body = client.get(f"/api/v1/events/{_event_id()}/reel").json()
    body["metadata"]["title"] = "Starred"
    response = client.put(
        f"/api/v1/events/{_event_id()}/reel", json=body, headers={"If-Match": "*"}
    )
    assert response.status_code == 200


def test_stale_if_match_is_412_and_leaves_the_file_untouched(
    client: TestClient, project: Path
) -> None:
    """The concurrent-writer case: another writer's trims survive the refused write."""
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    held_etag = read.headers["ETag"]
    body = read.json()
    body["metadata"]["title"] = "Client Edit"

    reel_path = _event_dir(project) / "reel.yaml"
    reel_path.write_text(
        REEL_YAML.replace("out: 1.5", "out: 2.5").replace("rotate: 90", "rotate: 180"),
        encoding="utf-8",
    )
    before = reel_path.read_bytes()

    response = client.put(
        f"/api/v1/events/{_event_id()}/reel", json=body, headers={"If-Match": held_etag}
    )
    assert response.status_code == 412
    assert response.json()["title"] == "Precondition Failed"
    assert reel_path.read_bytes() == before

    fresh = client.get(f"/api/v1/events/{_event_id()}/reel")
    assert fresh.json()["clips"]["00500.mp4"]["trims"][0]["out"] == 2.5

    retry = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json={**fresh.json(), "metadata": {**fresh.json()["metadata"], "title": "Client Edit"}},
        headers={"If-Match": fresh.headers["ETag"]},
    )
    assert retry.status_code == 200
    assert retry.json()["document"]["clips"]["00500.mp4"]["trims"][0]["out"] == 2.5


def test_absent_if_match_stays_unconditional(client: TestClient, project: Path) -> None:
    body = client.get(f"/api/v1/events/{_event_id()}/reel").json()
    body["metadata"]["title"] = "Unconditional"

    (_event_dir(project) / "reel.yaml").write_text(
        REEL_YAML.replace("Original Title", "Someone Else"), encoding="utf-8"
    )

    response = client.put(f"/api/v1/events/{_event_id()}/reel", json=body)
    assert response.status_code == 200
    assert response.json()["document"]["metadata"]["title"] == "Unconditional"


def test_comment_only_edit_does_not_invalidate_a_held_etag(
    client: TestClient, project: Path
) -> None:
    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    body = read.json()
    body["metadata"]["title"] = "After A Comment"

    reel_path = _event_dir(project) / "reel.yaml"
    reel_path.write_text("# added by hand\n" + REEL_YAML, encoding="utf-8")

    response = client.put(
        f"/api/v1/events/{_event_id()}/reel", json=body, headers={"If-Match": read.headers["ETag"]}
    )
    assert response.status_code == 200


# --- task 2.5: the two guarantees a GUI depends on --------------------------


def test_read_response_round_trips_byte_for_byte(client: TestClient, project: Path) -> None:
    """The read body submitted verbatim changes neither the file nor the verdict."""
    reel_path = _event_dir(project) / "reel.yaml"
    before_bytes = reel_path.read_bytes()
    before_verdict = client.get(f"/api/v1/events/{_event_id()}").json()["staleness"]

    read = client.get(f"/api/v1/events/{_event_id()}/reel")
    response = client.put(
        f"/api/v1/events/{_event_id()}/reel",
        json=read.json(),
        headers={"If-Match": read.headers["ETag"]},
    )
    assert response.status_code == 200
    assert reel_path.read_bytes() == before_bytes
    assert response.json()["staleness"] == before_verdict
    assert client.get(f"/api/v1/events/{_event_id()}/reel").headers["ETag"] == read.headers["ETag"]


def test_detail_view_is_not_an_editorial_write_body(client: TestClient) -> None:
    """A disk clip absent from ``reel.yaml`` is NEW in the detail view and absent here."""
    detail = client.get(f"/api/v1/events/{_event_id()}").json()
    detail_clips = {
        clip["identity"]: clip["status"] for ch in detail["chapters"] for clip in ch["clips"]
    }
    assert detail_clips["clips/00800.mp4"] == "new"
    assert detail_clips["clips/00700.mp4"] == "ignored"

    editorial = client.get(f"/api/v1/events/{_event_id()}/reel").json()
    referenced = {identity for ch in editorial["chapters"] for identity in ch["clips"]}
    assert "clips/00800.mp4" not in referenced
    assert "clips/00700.mp4" not in referenced
    assert editorial["ignore"] == ["clips/00700.mp4"]  # the exclusion survives a round trip

    rejected = client.put(f"/api/v1/events/{_event_id()}/reel", json=detail)
    assert rejected.status_code == 422
    offending = {
        tuple(error["loc"])[-1] for error in rejected.json()["detail"] if error["loc"][0] == "body"
    }
    assert {"event_id", "staleness"} <= offending
