"""The event poster endpoint (event-poster-gui, api-service "Event poster endpoint").

Real ffmpeg over two small synthetic clips, on an app whose database URL points at a closed port:
the route never needs it. A counting wrapper over the runtime tells "no process" from "a process".
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Dict, List
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.cli.adoption import persist, prepare_event
from auto_reel_ng.config import default_output_dir
from auto_reel_ng.config.project import load_project_config, resolve_look_defaults
from auto_reel_ng.event import DEFAULT_CLIP_ORDER
from auto_reel_ng.ffmpeg.runtime import FfmpegRuntime
from auto_reel_ng.render import output_relpath
from auto_reel_ng.render.poster import poster_path
from auto_reel_ng.staleness.fingerprint import compute_fingerprint, engine_identity
from auto_reel_ng.staleness.manifest import write_manifest

UNREACHABLE_DATABASE_URL = "postgresql+psycopg://poster:poster@127.0.0.1:1/poster"
EVENT = "2024/2024-07-04 - Barbecue"
SIDECAR_BYTES = b"\xff\xd8\xff\xe0the rendered poster\xff\xd9"


def _reel(poster: str = "") -> str:
    return (
        "version: 0\nmetadata:\n  title: Barbecue\n  date: 2024-07-04\n"
        f"{poster}chapters:\n  - name: ''\n    clips:\n      - a.mp4\n      - b.mp4\n"
    )


@pytest.fixture
def project(tmp_path: Path, make_clip: Callable[..., Path]) -> Path:
    root = tmp_path / "proj"
    event_dir = root / EVENT
    event_dir.mkdir(parents=True)
    for name in ("a.mp4", "b.mp4"):
        clip = make_clip(name, duration=2.0, width=160, height=90, audio=False)
        (event_dir / name).symlink_to(clip)
    (event_dir / "reel.yaml").write_text(_reel("poster:\n  clip: b.mp4\n  at: 1.5\n"))
    (root / "config.yaml").write_text(
        json.dumps({"thumbnails": {"cache_dir": str(tmp_path / "cache")}}), encoding="utf-8"
    )
    return root


@pytest.fixture
def processes(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    """Every ffmpeg or ffprobe run after this fixture, by kind."""
    seen: List[str] = []
    run, probe = FfmpegRuntime.run, FfmpegRuntime.run_ffprobe

    def counted_run(self: FfmpegRuntime, *args: object, **kwargs: object):
        seen.append("ffmpeg")
        return run(self, *args, **kwargs)  # type: ignore[arg-type]

    def counted_probe(self: FfmpegRuntime, *args: object, **kwargs: object):
        seen.append("ffprobe")
        return probe(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(FfmpegRuntime, "run", counted_run)
    monkeypatch.setattr(FfmpegRuntime, "run_ffprobe", counted_probe)
    return seen


@pytest.fixture
def client(project: Path, processes: List[str]):
    app = create_app(resolve_api_settings(project, env={"DATABASE_URL": UNREACHABLE_DATABASE_URL}))
    with TestClient(app) as test_client:
        processes.clear()
        yield test_client


def _url(event: str = EVENT) -> str:
    return f"/api/v1/events/{quote(event, safe='/')}/poster.jpg"


def _set_poster(project: Path, poster: str) -> None:
    (project / EVENT / "reel.yaml").write_text(_reel(poster), encoding="utf-8")


def _tree(root: Path) -> Dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() or p.is_symlink()
    }


def _render_record(project: Path, *, with_sidecar: bool = True) -> Path:
    """Make the event fresh: its movie, manifest and (optionally) the claimed sidecar."""
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
    movie = default_output_dir(project) / output_relpath(event.document.metadata)
    movie.parent.mkdir(parents=True, exist_ok=True)
    movie.write_bytes(b"the movie")
    sidecar = poster_path(movie)
    if with_sidecar:
        sidecar.write_bytes(SIDECAR_BYTES)
    write_manifest(
        event_dir,
        fingerprint,
        output=movie.name,
        engine_identity=engine_identity(runtime.version),
        poster=sidecar.name if with_sidecar else None,
    )
    return sidecar


def test_a_fresh_events_sidecar_is_served_as_it_is_with_no_process(
    client: TestClient, project: Path, processes: List[str]
) -> None:
    sidecar = _render_record(project)
    response = client.get(_url())
    assert response.status_code == 200, response.text
    assert response.content == SIDECAR_BYTES
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, no-cache"
    assert response.headers["etag"].startswith('"sidecar-')
    assert processes == []
    assert sidecar.read_bytes() == SIDECAR_BYTES


def test_a_sidecar_the_manifest_does_not_claim_is_not_served(
    client: TestClient, project: Path
) -> None:
    sidecar = _render_record(project, with_sidecar=False)
    sidecar.write_bytes(SIDECAR_BYTES)
    assert client.get(_url()).content != SIDECAR_BYTES


def test_a_stale_event_draws_the_chosen_frame_and_a_repeat_starts_no_process(
    client: TestClient, project: Path, processes: List[str]
) -> None:
    sidecar = _render_record(project)
    _set_poster(project, "poster:\n  clip: b.mp4\n  at: 0.5\n")  # now stale
    before = _tree(project)
    first = client.get(_url())
    assert first.status_code == 200, first.text
    assert first.content[:3] == b"\xff\xd8\xff" and first.content != SIDECAR_BYTES
    assert "ffmpeg" in processes
    processes.clear()
    again = client.get(_url())
    assert again.content == first.content and again.headers["etag"] == first.headers["etag"]
    assert processes == []
    assert _tree(project) == before  # nothing was written into the library
    assert sidecar.read_bytes() == SIDECAR_BYTES


def test_a_chosen_frame_differs_from_another_frame_and_from_the_default(
    client: TestClient, project: Path
) -> None:
    late = client.get(_url())
    _set_poster(project, "poster:\n  clip: b.mp4\n  at: 0.2\n")
    early = client.get(_url())
    _set_poster(project, "")
    default = client.get(_url())
    tags = {late.headers["etag"], early.headers["etag"], default.headers["etag"]}
    assert len(tags) == 3
    assert len({late.content, early.content, default.content}) == 3


def test_the_default_is_the_first_played_clips_thumbnail(
    client: TestClient, project: Path, tmp_path: Path
) -> None:
    _set_poster(project, "")
    response = client.get(_url())
    assert response.status_code == 200, response.text
    thumbnails = list((tmp_path / "cache").glob("*.jpg"))
    assert [p.read_bytes() for p in thumbnails] == [response.content]
    assert response.headers["etag"] == f'"{thumbnails[0].stem}"'


def test_a_matching_if_none_match_is_a_304_with_a_cold_cache_and_no_extraction(
    client: TestClient, project: Path, processes: List[str], tmp_path: Path
) -> None:
    tag = client.get(_url()).headers["etag"]
    for cached in (tmp_path / "cache").glob("*"):
        cached.unlink()
    processes.clear()
    response = client.get(_url(), headers={"If-None-Match": tag})
    assert response.status_code == 304
    assert (
        response.headers["etag"] == tag and response.headers["cache-control"] == "private, no-cache"
    )
    assert processes == []
    assert list((tmp_path / "cache").glob("*.jpg")) == []


def test_an_event_with_no_playable_clip_is_404_with_no_process(
    client: TestClient, project: Path, processes: List[str]
) -> None:
    (project / EVENT / "reel.yaml").write_text(
        "version: 0\nmetadata:\n  title: Barbecue\n  date: 2024-07-04\n"
        "chapters:\n  - name: ''\n    clips: []\nignore:\n  - a.mp4\n  - b.mp4\n"
    )
    response = client.get(_url())
    assert response.status_code == 404
    assert EVENT in response.json()["event_id"]
    assert "Cache-Control" not in response.headers and processes == []


def test_an_unknown_event_is_404(client: TestClient) -> None:
    assert client.get(_url("2024/no such event")).status_code == 404


def test_a_time_past_the_end_is_a_named_502_remembered_for_a_minute(
    client: TestClient, project: Path, processes: List[str]
) -> None:
    _set_poster(project, "poster:\n  clip: b.mp4\n  at: 99\n")
    response = client.get(_url())
    assert response.status_code == 502
    body = response.json()
    assert body["thumbnail_failure"] == "thumbnail_failed"
    assert body["detail"].startswith("b.mp4: ")
    assert str(project) not in body["detail"]
    processes.clear()
    assert client.get(_url()).status_code == 502
    assert processes == []


def test_a_poster_whose_clip_is_unplayed_falls_back_to_the_default(
    client: TestClient, project: Path
) -> None:
    _set_poster(project, "poster:\n  clip: gone.mp4\n  at: 1\n")
    default = client.get(_url())
    _set_poster(project, "")
    assert default.status_code == 200
    assert client.get(_url()).content == default.content


def test_a_clip_turned_in_the_reel_is_drawn_turned(client: TestClient, project: Path) -> None:
    plain = client.get(_url())
    reel = (project / EVENT / "reel.yaml").read_text(encoding="utf-8")
    (project / EVENT / "reel.yaml").write_text(
        reel + "clips:\n  b.mp4:\n    rotate: 90\n", encoding="utf-8"
    )
    turned = client.get(_url())
    assert turned.status_code == 200, turned.text
    assert turned.content != plain.content and turned.headers["etag"] != plain.headers["etag"]
