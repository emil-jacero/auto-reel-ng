"""The event poster in the editorial body (event-poster-gui, api-service "editorial document")."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
import yaml
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.event import DEFAULT_CLIP_ORDER

pytestmark = pytest.mark.requires_db

EVENT = "2024/2024-07-04 - Barbecue"
REEL_YAML = """\
# my notes
version: 0
metadata:
  title: Barbecue
  date: 2024-07-04
poster:
  clip: 00600.mp4  # the toast
  at: 3.5
chapters:
  - name: ""
    clips:
      - 00500.mp4
      - 00600.mp4
"""
NO_POSTER_YAML = REEL_YAML.replace("poster:\n  clip: 00600.mp4  # the toast\n  at: 3.5\n", "")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    event_dir = root / EVENT
    event_dir.mkdir(parents=True)
    for name in ("00500.mp4", "00600.mp4"):
        (event_dir / name).write_bytes(b"")
    (event_dir / "reel.yaml").write_text(REEL_YAML, encoding="utf-8")
    return root


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):
    app = create_app(resolve_api_settings(project, env={"DATABASE_URL": postgres_container}))
    with TestClient(app) as test_client:
        yield test_client


def _url(suffix: str = "/reel") -> str:
    return f"/api/v1/events/{quote(EVENT, safe='/')}{suffix}"


def _reel(project: Path) -> str:
    return (project / EVENT / "reel.yaml").read_text(encoding="utf-8")


def _without_poster(body: dict) -> dict:
    return {key: value for key, value in body.items() if key != "poster"}


def test_the_poster_is_read_and_echoed(client: TestClient) -> None:
    body = client.get(_url()).json()
    assert body["poster"] == {"clip": "00600.mp4", "at": 3.5}
    assert client.put(_url(), json=body).json()["document"]["poster"] == body["poster"]


def test_a_poster_is_set(client: TestClient, project: Path) -> None:
    (project / EVENT / "reel.yaml").write_text(NO_POSTER_YAML, encoding="utf-8")
    body = client.get(_url()).json()
    assert body["poster"] is None
    response = client.put(_url(), json={**body, "poster": {"clip": "00500.mp4", "at": 12.5}})
    assert response.status_code == 200, response.text
    assert response.json()["document"]["poster"] == {"clip": "00500.mp4", "at": 12.5}
    assert yaml.safe_load(_reel(project))["poster"] == {"clip": "00500.mp4", "at": 12.5}
    assert client.get(_url()).json()["poster"] == {"clip": "00500.mp4", "at": 12.5}


def test_a_body_without_poster_keeps_it(client: TestClient, project: Path) -> None:
    body = _without_poster(client.get(_url()).json())
    assert "poster" not in body
    response = client.put(_url(), json=body)
    assert response.status_code == 200, response.text
    assert response.json()["document"]["poster"] == {"clip": "00600.mp4", "at": 3.5}
    assert _reel(project) == REEL_YAML


def test_null_removes_the_poster(client: TestClient, project: Path) -> None:
    body = client.get(_url()).json()
    response = client.put(_url(), json={**body, "poster": None})
    assert response.status_code == 200, response.text
    assert response.json()["document"]["poster"] is None
    assert "poster" not in yaml.safe_load(_reel(project))
    assert client.get(_url()).json()["poster"] is None


def test_an_unmodified_echo_is_byte_identical(client: TestClient, project: Path) -> None:
    assert client.put(_url(), json=client.get(_url()).json()).status_code == 200
    assert _reel(project) == REEL_YAML


def test_changing_only_at_keeps_the_comment(client: TestClient, project: Path) -> None:
    body = client.get(_url()).json()
    client.put(_url(), json={**body, "poster": {"clip": "00600.mp4", "at": 4.25}})
    assert _reel(project) == REEL_YAML.replace("at: 3.5", "at: 4.25")


@pytest.mark.parametrize("at", [-2, -0.001])
def test_a_refused_time_is_a_400_naming_the_field(
    client: TestClient, project: Path, at: float
) -> None:
    body = client.get(_url()).json()
    response = client.put(_url(), json={**body, "poster": {"clip": "00500.mp4", "at": at}})
    assert response.status_code in (400, 422), response.text
    if response.status_code == 400:
        assert "poster.at" in response.json()["detail"]
    assert _reel(project) == REEL_YAML


def test_an_unknown_poster_key_and_wrong_types_are_rejected(client: TestClient) -> None:
    body = client.get(_url()).json()
    for poster in (
        {"clip": "a.mp4", "at": 1, "frame": 3},
        {"clip": 3, "at": "x"},
        {"clip": "a.mp4"},
    ):
        response = client.put(_url(), json={**body, "poster": poster})
        assert response.status_code == 422, (poster, response.text)


def test_a_clip_the_movie_does_not_play_is_accepted(client: TestClient, project: Path) -> None:
    body = client.get(_url()).json()
    response = client.put(_url(), json={**body, "poster": {"clip": "nope.mp4", "at": 1}})
    assert response.status_code == 200, response.text
    assert yaml.safe_load(_reel(project))["poster"]["clip"] == "nope.mp4"


def test_a_poster_edit_makes_a_fresh_event_stale_and_enqueues_nothing(
    client: TestClient, project: Path
) -> None:
    from auto_reel_ng.cli.adoption import persist, prepare_event
    from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
    from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
    from auto_reel_ng.render import output_relpath
    from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
    from auto_reel_ng.staleness.manifest import write_manifest

    event_dir = project / EVENT
    event = prepare_event(event_dir, order=DEFAULT_CLIP_ORDER, adopt=True)
    persist(event)
    runtime = FfmpegRuntime()
    fingerprint = compute_fingerprint(
        event.document,
        event_dir=event_dir,
        look_defaults=resolve_look_defaults(load_project_config(project)),
        ffmpeg_version=runtime.version,
    )
    output = default_output_dir(project) / output_relpath(event.document.metadata)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"already-rendered")
    write_manifest(
        event_dir, fingerprint, output=output.name, engine_identity=engine_identity(runtime.version)
    )
    assert client.get(_url("")).json()["staleness"]["stale"] is False

    body = client.get(_url()).json()
    response = client.put(_url(), json={**body, "poster": {"clip": "00600.mp4", "at": 9.0}})
    assert response.status_code == 200, response.text
    staleness = response.json()["staleness"]
    assert staleness["stale"] is True
    assert "editorial" in staleness["reasons"]
    assert client.get("/api/v1/jobs").json() == []
