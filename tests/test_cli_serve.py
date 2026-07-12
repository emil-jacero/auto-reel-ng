"""Tests for the ``serve`` subcommand (task 1.4, D-A7)."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import httpx
import pytest

from auto_reel_ng.cli import commands
from auto_reel_ng.cli.main import main

pytestmark = pytest.mark.requires_db


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_flags_override_config_port(
    tmp_path: Path, postgres_container: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.yaml").write_text("api:\n  port: 8080\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", postgres_container)

    captured: dict[str, object] = {}

    class _FakeServer:
        def __init__(self, config: object) -> None:
            captured["host"] = config.host  # type: ignore[attr-defined]
            captured["port"] = config.port  # type: ignore[attr-defined]

        def run(self) -> None:
            return None

    monkeypatch.setattr(commands.uvicorn, "Server", _FakeServer)
    assert main(["serve", str(tmp_path), "--port", "9000"]) == 0
    assert captured["port"] == 9000


def test_bind_failure_exits_nonzero_naming_host_port(
    tmp_path: Path,
    postgres_container: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DATABASE_URL", postgres_container)
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    port = holder.getsockname()[1]
    try:
        assert main(["serve", str(tmp_path), "--host", "127.0.0.1", "--port", str(port)]) == 1
    finally:
        holder.close()
    err = capsys.readouterr().err
    assert f"127.0.0.1:{port}" in err


def test_serve_starts_and_answers_healthz(
    tmp_path: Path, postgres_container: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", postgres_container)
    port = _free_port()

    servers: list = []
    real_server_cls = commands.uvicorn.Server

    class _CapturingServer(real_server_cls):  # type: ignore[misc,valid-type]
        def __init__(self, config: object) -> None:
            super().__init__(config)  # type: ignore[arg-type]
            servers.append(self)

    monkeypatch.setattr(commands.uvicorn, "Server", _CapturingServer)

    result: dict[str, int] = {}

    def _run() -> None:
        result["code"] = main(["serve", str(tmp_path), "--host", "127.0.0.1", "--port", str(port)])

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        response = None
        while time.monotonic() < deadline:
            if servers and servers[0].started:
                try:
                    response = httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1)
                    break
                except httpx.TransportError:
                    pass
            time.sleep(0.05)
        assert response is not None
        assert response.status_code == 200
    finally:
        if servers:
            servers[0].should_exit = True
        thread.join(timeout=10)
    assert result.get("code") == 0
