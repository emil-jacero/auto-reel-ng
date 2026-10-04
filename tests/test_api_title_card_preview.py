"""``POST /api/v1/events/{id}/title-card/preview``: one draft card as a PNG.

Against the real engine: the expected image is always the renderer's own output for the
card the draft resolves to. No database: the preview reads none, so the app is built on the
schema-dump settings' unreachable one.
"""

from __future__ import annotations

import io
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.preview_gate import PreviewGate
from auto_reel_ng.api.routes import title_cards
from auto_reel_ng.api.settings import ApiSettings, resolve_api_settings
from auto_reel_ng.errors import TitleCardBackendError
from auto_reel_ng.render.title import (
    TitleCardContent,
    parse_title_card_config,
    registered_families,
)
from auto_reel_ng.render.title import render as card_render
from auto_reel_ng.render.title import render_card_png

pytestmark = pytest.mark.has_fonts

EVENT = "2024/2024-07-04 - Barbecue"

REEL = """\
version: 0
metadata:
  title: Barbecue
  date: 2024-07-04
look:
  title_card:
    text_color: "#FFFFFF"
chapters:
  - name: ""
    clips: [00500.mp4]
"""


@pytest.fixture
def event_dir(tmp_path: Path) -> Path:
    path = tmp_path / "proj" / "2024" / "2024-07-04 - Barbecue"
    path.mkdir(parents=True)
    (path / "00500.mp4").write_bytes(b"")
    (path / "reel.yaml").write_text(REEL, encoding="utf-8")
    return path


@pytest.fixture
def client(event_dir: Path, has_fonts: None):
    settings: ApiSettings = resolve_api_settings(
        event_dir.parents[1], env={"DATABASE_URL": "postgresql+psycopg://x:x@127.0.0.1:1/x"}
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _url(event: str = EVENT) -> str:
    return f"/api/v1/events/{quote(event, safe='/')}/title-card/preview"


def _decode(data: bytes) -> tuple[int, int, bytes, int]:
    import cairo

    surface = cairo.ImageSurface.create_from_png(io.BytesIO(data))
    return (
        surface.get_width(),
        surface.get_height(),
        bytes(surface.get_data()),
        surface.get_stride(),
    )


def _format(data: bytes) -> str:
    import cairo

    surface = cairo.ImageSurface.create_from_png(io.BytesIO(data))
    return {cairo.FORMAT_ARGB32: "ARGB32", cairo.FORMAT_RGB24: "RGB24"}[surface.get_format()]


def _alpha(data: bytes, x: int, y: int) -> int:
    _w, _h, pixels, stride = _decode(data)
    return pixels[y * stride + x * 4 + 3]


def _expected(
    heading: str, subtitle: str = "", *, size: tuple[int, int] = (1920, 1080), **look: Any
):
    config = parse_title_card_config({"text_color": "#FFFFFF", **look})
    return render_card_png(config, TitleCardContent(heading, subtitle), *size)


def test_a_black_card_is_the_renderers_image_at_the_target_resolution(client: TestClient) -> None:
    response = client.post(
        _url(), json={"chapter": "", "card": {"title": "Sommaren", "subtitle": "2024"}}
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert _decode(response.content)[:2] == (1920, 1080)
    assert response.content == _expected("Sommaren", "2024")


def test_the_event_target_resolution_decides_the_size(client: TestClient, event_dir: Path) -> None:
    (event_dir / "reel.yaml").write_text(
        REEL.replace("look:\n", "look:\n  target_resolution: [1280, 720]\n"), encoding="utf-8"
    )
    response = client.post(_url(), json={"card": {"title": "Hej"}})
    assert response.status_code == 200
    assert _decode(response.content)[:2] == (1280, 720)
    assert response.content == _expected("Hej", size=(1280, 720))


def test_a_video_card_is_text_on_transparency(client: TestClient) -> None:
    response = client.post(_url(), json={"card": {"title": "OVER VIDEO", "background": "video"}})
    assert response.status_code == 200
    assert _alpha(response.content, 2, 2) == 0
    assert max(_alpha(response.content, x, 540) for x in range(1920)) == 255  # opaque text
    black = client.post(_url(), json={"card": {"title": "OVER VIDEO"}})
    assert black.content != response.content
    assert _format(response.content) == "ARGB32"  # a transparent card keeps its alpha channel
    assert _format(black.content) == "RGB24"  # cairo stores a fully opaque card without one


def test_a_draft_is_drawn_without_saving_it(client: TestClient, event_dir: Path) -> None:
    before = (event_dir / "reel.yaml").read_bytes()
    saved = client.post(_url(), json={}).content
    draft = client.post(_url(), json={"card": {"title": "Not saved"}})
    assert draft.content == _expected("Not saved") != saved
    assert saved == _expected("Barbecue")
    assert (event_dir / "reel.yaml").read_bytes() == before


def test_the_draft_style_wins_over_the_saved_one_and_is_absent_otherwise(
    client: TestClient,
) -> None:
    red = client.post(_url(), json={"card": {"title": "Hej"}, "style": {"text_color": "#FF0000"}})
    assert red.content == _expected("Hej", text_color="#FF0000")
    saved = client.post(_url(), json={"card": {"title": "Hej"}})
    assert saved.content == _expected("Hej")
    assert saved.content != red.content


def test_the_opening_card_defaults_to_the_draft_event_title(client: TestClient) -> None:
    drafted = client.post(_url(), json={"chapter": "", "event_title": "Nytt namn"})
    assert drafted.content == _expected("Nytt namn")
    assert client.post(_url(), json={"chapter": ""}).content == _expected("Barbecue")
    named = client.post(_url(), json={"chapter": "Dag 2", "event_title": "Nytt namn"})
    assert named.content == _expected("Dag 2")  # a named chapter does not use the event title


def test_each_registry_family_renders_a_distinct_image(client: TestClient) -> None:
    images = {}
    for family in registered_families():
        response = client.post(
            _url(), json={"card": {"title": "Hamburgefonts", "font_family": family}}
        )
        assert response.status_code == 200, (family, response.text)
        images[family] = response.content
    assert len(set(images.values())) == len(images)


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ({"card": {"title_font_size": 0}}, "card.title_font_size"),
        ({"card": {"font_family": "Comic Sans"}}, "font_family"),
        ({"card": {"duration": 900}}, "card.duration"),
        ({"style": {"title_font_size": "big"}}, "look.title_card.title_font_size"),
        ({"card": {"title": " "}}, "card.title"),
    ],
)
def test_an_invalid_draft_is_a_400_naming_the_field(
    client: TestClient, body: dict, needle: str
) -> None:
    response = client.post(_url(), json=body)
    assert response.status_code == 400, response.text
    assert needle in response.json()["detail"]
    assert response.headers["content-type"].startswith("application/json")


def test_an_unknown_event_is_404(client: TestClient) -> None:
    response = client.post(_url("2024/2099-01-01 - Nope"), json={})
    assert response.status_code == 404
    assert response.json()["status"] == 404


def test_an_unparseable_reel_yaml_is_the_scan_failure_502(
    client: TestClient, event_dir: Path
) -> None:
    (event_dir / "reel.yaml").write_text("version: 0\nchapters: not-a-list\n", encoding="utf-8")
    response = client.post(_url(), json={})
    assert response.status_code == 502
    assert response.json()["failure"] == "unparseable_reel_yaml"


def test_a_missing_drawing_backend_is_a_503_naming_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken() -> None:
        raise TitleCardBackendError("title-card rendering requires Cairo + Pango; none usable")

    monkeypatch.setattr(card_render, "_load_backend", broken)
    response = client.post(_url(), json={})
    assert response.status_code == 503
    assert "Cairo" in response.json()["detail"]


def test_an_over_long_text_is_a_422_naming_the_field_and_nothing_is_drawn(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_a: object, **_k: object) -> bytes:
        raise AssertionError("must not draw")

    monkeypatch.setattr(title_cards, "render_card_png", forbidden)
    for body, loc in (
        ({"card": {"title": "x" * 201}}, "title"),
        ({"card": {"subtitle": "x" * 401}}, "subtitle"),
        ({"event_title": "x" * 201}, "event_title"),
    ):
        response = client.post(_url(), json=body)
        assert response.status_code == 422
        assert loc in str(response.json()["detail"][0]["loc"])
    ok = {"card": {"title": "x" * 200, "subtitle": "y" * 400}}
    monkeypatch.undo()
    assert client.post(_url(), json=ok).status_code == 200


def test_the_preview_touches_nothing(
    client: TestClient, event_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def tree() -> dict:
        return {
            str(p): (p.stat().st_mtime_ns, p.stat().st_size)
            for p in tmp_path.rglob("*")
            if p.is_file()
        }

    def forbidden(*_a: object, **_k: object) -> None:
        raise AssertionError("the preview must not start a subprocess")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    before = tree()
    assert (
        client.post(_url(), json={"card": {"title": "x", "background": "video"}}).status_code == 200
    )
    assert tree() == before  # no cache, no file, reel.yaml untouched


def test_a_busy_service_answers_503_with_retry_after_while_the_api_keeps_answering(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.app.state.title_card_gate = PreviewGate(limit=1, wait=0.2)  # type: ignore[attr-defined]
    started, release = threading.Event(), threading.Event()
    real = render_card_png

    def held(*args: Any, **kwargs: Any) -> bytes:
        started.set()
        release.wait(10)
        return real(*args, **kwargs)

    monkeypatch.setattr(title_cards, "render_card_png", held)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, _url(), json={"card": {"title": "one"}})
        assert started.wait(5)
        second: Optional[Any] = pool.submit(client.post, _url(), json={"card": {"title": "two"}})
        busy = second.result(timeout=5)
        assert busy.status_code == 503
        assert busy.headers["retry-after"] == "2"
        assert "busy" in busy.json()["detail"]
        assert client.get("/api/v1/fonts").status_code == 200  # the rest of the API answers
        release.set()
        assert first.result(timeout=10).status_code == 200


def test_two_different_drafts_share_no_state(client: TestClient) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(client.post, _url(), json={"card": {"title": "Alpha"}})
        b = pool.submit(client.post, _url(), json={"card": {"title": "Beta"}})
        ra, rb = a.result(timeout=20), b.result(timeout=20)
    assert ra.content == _expected("Alpha")
    assert rb.content == _expected("Beta")
