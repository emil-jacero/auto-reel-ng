"""Tests for the ``serve`` subcommand (task 1.4, D-A7; jobs-ws-lifecycle 3.1)."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

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


def test_serve_keeps_uvicorns_websocket_keepalive(
    tmp_path: Path, postgres_container: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A silent peer is released within 40 s: a ping every 20 s, answered within 20 s.

    ``serve`` sets no keepalive of its own, so that window is uvicorn's default: an
    upstream change of the default fails here instead of moving the spec's bound.
    """
    monkeypatch.setenv("DATABASE_URL", postgres_container)
    captured: dict[str, object] = {}

    class _FakeServer:
        def __init__(self, config: object) -> None:
            captured["ws_ping_interval"] = config.ws_ping_interval  # type: ignore[attr-defined]
            captured["ws_ping_timeout"] = config.ws_ping_timeout  # type: ignore[attr-defined]

        def run(self) -> None:
            return None

    monkeypatch.setattr(commands.uvicorn, "Server", _FakeServer)
    assert main(["serve", str(tmp_path)]) == 0
    assert captured == {"ws_ping_interval": 20.0, "ws_ping_timeout": 20.0}


def _wait_for_healthz(process: subprocess.Popen[str], port: int) -> None:
    """Return once ``serve`` answers ``GET /healthz``; fail if it exits or 15 s pass first."""
    deadline = time.monotonic() + 15
    while process.poll() is None:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1).status_code == 200:
                return
        except httpx.TransportError:
            pass
        assert time.monotonic() < deadline, "serve did not answer /healthz within 15 s"
        time.sleep(0.05)
    pytest.fail(f"serve exited with {process.returncode} before answering /healthz")


@pytest.mark.usefixtures("jobs_schema_engine")  # the snapshot reads the jobs table
@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT], ids=["SIGTERM", "SIGINT"])
def test_one_signal_stops_serve_with_a_websocket_open(
    signum: signal.Signals, tmp_path: Path, postgres_container: str
) -> None:
    """``serve`` in a process of its own: only a main thread gets uvicorn's signal handlers.

    The return code is not asserted. After its orderly shutdown uvicorn re-raises the
    signal it caught, so the process ends by that signal, with or without a socket open.
    """
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "auto_reel_ng.cli.main",
            "serve",
            str(tmp_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env={**os.environ, "DATABASE_URL": postgres_container},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_healthz(process, port)
        with connect(f"ws://127.0.0.1:{port}/api/v1/ws/jobs") as client:
            assert json.loads(client.recv(timeout=5))["type"] == "snapshot"
            process.send_signal(signum)
            signalled = time.monotonic()
            with pytest.raises(ConnectionClosed) as closed:
                while True:
                    client.recv(timeout=5)
        assert closed.value.rcvd is not None and closed.value.rcvd.code == 1012
        # One signal is all it gets: a hang fails on this timeout, never the whole suite.
        process.wait(timeout=max(0.0, signalled + 5 - time.monotonic()))
    finally:
        if process.poll() is None:
            process.kill()
        output = process.communicate()[0]
        print(output)  # serve's log, shown when the test fails
    assert "Application shutdown complete" in output
    assert "Waiting for background tasks to complete" not in output
