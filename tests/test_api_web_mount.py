"""Tests for serving the built web client (tasks 2.2-2.3).

The mount is conditional and registered last. Both halves matter: with no build
present the service is byte-for-byte the service it was, and with a build present
the API, the health endpoint and the WebSocket still reach their handlers rather
than being answered with the client's ``index.html``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from auto_reel_ng.api import app as app_module
from auto_reel_ng.api.app import create_app, web_dist_dir
from auto_reel_ng.api.settings import resolve_api_settings

INDEX_HTML = '<!doctype html><title>auto-reel-ng</title><div id="root"></div>'
ASSET_JS = "export const wired = true;\n"


@pytest.fixture
def built_client(tmp_path: Path) -> Path:
    """A stand-in for ``web/dist``: an entry document and one hashed asset."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "main.js").write_text(ASSET_JS, encoding="utf-8")
    # The file a traversing request would reach if the mount were not confined.
    (tmp_path / "outside.txt").write_text("must not be served", encoding="utf-8")
    return dist


def test_web_dist_dir_points_at_the_checkout() -> None:
    """The resolver names ``<checkout>/web/dist`` — the sibling of the package."""
    dist = web_dist_dir()
    assert dist.name == "dist"
    assert dist.parent.name == "web"
    assert (dist.parent.parent / "auto_reel_ng").is_dir()


def test_root_is_not_served_when_no_build_is_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout that never built the client serves the API and nothing at ``/``."""
    monkeypatch.setattr(app_module, "web_dist_dir", lambda: tmp_path / "never-built")
    settings = resolve_api_settings(tmp_path, env={"DATABASE_URL": "postgresql+psycopg://x@/x"})
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/").status_code == 404


@pytest.mark.requires_db
class TestWithBuiltClient:
    """The built client is present: it is served, and it shadows nothing."""

    @pytest.fixture
    def client(
        self,
        tmp_path: Path,
        built_client: Path,
        postgres_container: str,
        jobs_schema_engine,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(app_module, "web_dist_dir", lambda: built_client)
        project = tmp_path / "project"
        project.mkdir()
        settings = resolve_api_settings(project, env={"DATABASE_URL": postgres_container})
        with TestClient(create_app(settings)) as test_client:
            yield test_client

    def test_root_returns_the_entry_document(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert response.text == INDEX_HTML

    def test_assets_resolve_by_path(self, client: TestClient) -> None:
        response = client.get("/assets/main.js")
        assert response.status_code == 200
        assert response.text == ASSET_JS

    def test_api_routes_win_over_the_mount(self, client: TestClient) -> None:
        response = client.get("/api/v1/events")
        assert response.status_code == 200
        assert response.json() == []

    def test_healthz_wins_over_the_mount(self, client: TestClient) -> None:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_the_websocket_still_reaches_its_handler(self, client: TestClient) -> None:
        with client.websocket_connect("/api/v1/ws/jobs") as websocket:
            snapshot = json.loads(websocket.receive_text())
        assert snapshot["type"] == "snapshot"

    def test_traversal_does_not_escape_the_built_directory(self, client: TestClient) -> None:
        for path in ("/../outside.txt", "/assets/../../outside.txt", "/%2e%2e/outside.txt"):
            response = client.get(path)
            assert response.status_code != 200, path
            assert "must not be served" not in response.text
