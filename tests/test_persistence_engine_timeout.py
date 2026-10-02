"""Postgres connections fail fast (persistence, jobshub-stop-and-db-timeouts 3.1).

DB-free: the engine is built over a URL and either inspected (a recording
``create_engine``) or pointed at a listening socket that never answers, which stands in
for a database host that has stopped responding.
"""

from __future__ import annotations

import socket
import time
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from auto_reel_ng.api.app import create_app
from auto_reel_ng.api.settings import resolve_api_settings
from auto_reel_ng.persistence import engine as engine_module
from auto_reel_ng.persistence.engine import CONNECT_TIMEOUT_SECONDS, make_engine

#: libpq treats a ``connect_timeout`` under 2 s as 2 s, so the socket tests use 2.
_TEST_TIMEOUT = 2


@pytest.fixture
def created(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every ``create_engine`` call ``make_engine`` makes: its keyword arguments."""
    calls: list[dict[str, Any]] = []

    def _record(url: Any, **kwargs: Any) -> object:
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(engine_module, "create_engine", _record)
    return calls


@pytest.fixture
def silent_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A URL for a listener that never accepts: a connect reaches the kernel, then waits."""
    monkeypatch.setattr(engine_module, "CONNECT_TIMEOUT_SECONDS", _TEST_TIMEOUT)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        yield f"postgresql+psycopg://u:p@127.0.0.1:{port}/db"


def test_the_bound_is_five_seconds() -> None:
    assert CONNECT_TIMEOUT_SECONDS == 5


def test_a_postgres_url_gets_the_connect_timeout(created: list[dict[str, Any]]) -> None:
    make_engine("postgresql+psycopg://u:p@db.example/arel")

    assert created[0]["connect_args"] == {"connect_timeout": CONNECT_TIMEOUT_SECONDS}


def test_a_connect_timeout_in_the_url_wins(created: list[dict[str, Any]]) -> None:
    make_engine("postgresql+psycopg://u:p@db.example/arel?connect_timeout=30")

    assert "connect_timeout" not in created[0].get("connect_args", {})


def test_another_backend_gets_no_connect_args(created: list[dict[str, Any]]) -> None:
    make_engine("sqlite://")

    assert not created[0].get("connect_args")


def test_connecting_to_a_database_that_never_answers_gives_up_at_the_bound(
    silent_database: str,
) -> None:
    engine = make_engine(silent_database)
    started = time.monotonic()
    try:
        with pytest.raises(OperationalError):
            engine.connect()
    finally:
        engine.dispose()

    assert 1.5 <= time.monotonic() - started <= 6.0


def test_healthz_answers_503_at_the_bound_when_the_database_never_answers(
    tmp_path: Path, silent_database: str
) -> None:
    settings = resolve_api_settings(tmp_path, env={"DATABASE_URL": silent_database})
    with TestClient(create_app(settings)) as client:
        started = time.monotonic()
        response = client.get("/healthz")
        elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert response.json().get("check") == "database"
    assert elapsed <= 6.0
