"""The event detail's ``poster`` and ``poster_note`` (event-poster-gui, api-service)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime

pytestmark = pytest.mark.requires_db

EVENT = "2024/2024-07-04 - Barbecue"


def _reel(*, poster: str = "", ignore: str = "", extra: str = "") -> str:
    return (
        "version: 0\nmetadata:\n  title: Barbecue\n  date: 2024-07-04\n"
        f"{poster}chapters:\n  - name: ''\n    clips:\n      - a.mp4\n      - b.mp4\n      - c.mp4\n"
        f"{extra}{ignore}"
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / EVENT).mkdir(parents=True)
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        (root / EVENT / name).write_bytes(b"")
    return root


@pytest.fixture
def client(project: Path, postgres_container: str, jobs_schema_engine):
    app = create_app(resolve_api_settings(project, env={"DATABASE_URL": postgres_container}))
    with TestClient(app) as test_client:
        yield test_client


def _detail(client: TestClient) -> dict:
    response = client.get(f"/api/v1/events/{quote(EVENT, safe='/')}")
    assert response.status_code == 200, response.text
    return response.json()


def _write(project: Path, text: str) -> None:
    (project / EVENT / "reel.yaml").write_text(text, encoding="utf-8")


def test_a_chosen_frame(client: TestClient, project: Path) -> None:
    _write(project, _reel(poster="poster:\n  clip: b.mp4\n  at: 12.5\n"))
    detail = _detail(client)
    assert detail["poster"] == {"clip": "b.mp4", "at": 12.5, "source": "event"}
    assert detail["poster_note"] is None


def test_no_poster_is_the_first_played_clip_with_no_time(client: TestClient, project: Path) -> None:
    _write(project, _reel(ignore="ignore:\n  - a.mp4\n").replace("      - a.mp4\n", ""))
    detail = _detail(client)
    assert detail["poster"] == {"clip": "b.mp4", "at": None, "source": "default"}
    assert detail["poster_note"] is None


def test_an_event_without_a_reel_yaml_uses_the_first_clip(client: TestClient) -> None:
    assert _detail(client)["poster"] == {"clip": "a.mp4", "at": None, "source": "default"}


@pytest.mark.parametrize(
    ("variant", "reason"),
    [
        ("ignored", "ignored"),
        ("excluded", "excluded"),
        ("missing", "missing"),
    ],
)
def test_a_chosen_clip_that_does_not_play_falls_back_with_a_note(
    client: TestClient, project: Path, variant: str, reason: str
) -> None:
    clip = "zz.mp4" if variant == "missing" else "c.mp4"
    text = _reel(poster=f"poster:\n  clip: {clip}\n  at: 1\n")
    if variant == "ignored":
        text = text.replace("      - c.mp4\n", "") + "ignore:\n  - c.mp4\n"
    if variant == "excluded":
        text += "clips:\n  c.mp4:\n    exclude: true\n"
    _write(project, text)
    detail = _detail(client)
    assert detail["poster"] == {"clip": "a.mp4", "at": None, "source": "default"}
    assert detail["poster_note"] == (
        f"poster clip {clip!r} is {reason}; using the first played clip's frame"
    )


def test_an_event_with_no_playable_clip_has_no_poster(client: TestClient, project: Path) -> None:
    _write(
        project,
        "version: 0\nmetadata:\n  title: Barbecue\n  date: 2024-07-04\n"
        "chapters:\n  - name: ''\n    clips: []\nignore:\n  - a.mp4\n  - b.mp4\n  - c.mp4\n",
    )
    detail = _detail(client)
    assert detail["poster"] is None
    assert detail["poster_note"] is None


def test_a_bad_poster_is_the_events_failure_naming_the_field(
    client: TestClient, project: Path
) -> None:
    _write(project, _reel(poster='poster:\n  clip: 3\n  at: "x"\n'))
    response = client.get(f"/api/v1/events/{quote(EVENT, safe='/')}")
    assert response.status_code == 502
    assert "poster" in response.json()["detail"]


def test_the_read_starts_no_process_and_writes_nothing(
    client: TestClient, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(project, _reel(poster="poster:\n  clip: b.mp4\n  at: 2\n"))
    before = sorted(p.name for p in (project / EVENT).iterdir())

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the detail started a process")

    monkeypatch.setattr(FfmpegRuntime, "run", refuse)
    monkeypatch.setattr(FfmpegRuntime, "run_ffprobe", refuse)
    assert _detail(client)["poster"]["clip"] == "b.mp4"
    assert sorted(p.name for p in (project / EVENT).iterdir()) == before
