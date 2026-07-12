"""Tests for the app factory (task 1.3): ``/healthz``, the auth seam."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings

pytestmark = pytest.mark.requires_db


@pytest.fixture
def settings(tmp_path: Path, postgres_container: str):
    return resolve_api_settings(tmp_path, env={"DATABASE_URL": postgres_container})


def test_healthz_ok_when_db_reachable(settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_healthz_reports_db_outage(tmp_path: Path) -> None:
    bad_settings = resolve_api_settings(
        tmp_path, env={"DATABASE_URL": "postgresql+psycopg://nobody:nobody@127.0.0.1:1/nope"}
    )
    app = create_app(bad_settings)
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == 503
    assert body.get("check") == "database"


def test_default_auth_checker_allows_every_request(settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200


def test_registered_token_checker_rejects_untokened_requests(settings) -> None:
    def _checker(request):
        if request.headers.get("authorization") != "Bearer secret":
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return None

    app = create_app(settings, auth_checker=_checker)
    with TestClient(app) as client:
        rejected = client.get("/healthz")
        allowed = client.get("/healthz", headers={"authorization": "Bearer secret"})

    assert rejected.status_code == 401
    assert allowed.status_code == 200
