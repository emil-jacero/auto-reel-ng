"""``serve``'s stop signals: not raised again, forcing, and the end of the process.

In process (serve-clean-exit 2.2): ``uvicorn.Server.capture_signals`` installs its handlers only
on the main thread, which is pytest's, and after the block it raises every signal it caught once
more for the handlers it restores. A recording handler for SIGINT and SIGTERM stands in for those,
so a signal raised again lands in a list instead of in pytest's own handler (an aborted run) or in
SIGTERM's default (a killed one). No server runs.

In a process of their own (review of the change): ``serve`` started as a terminal starts it, with
its database URL pointing at a local listener that accepts a connection and never answers, a
stalled database. Nothing connects to it but the ``GET /healthz`` that is meant to stall, so these
tests need no database either.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import FrameType
from typing import Any, Iterator, Optional

import httpx
import pytest
import uvicorn

from auto_reel_ng.cli import commands
from auto_reel_ng.cli.serving import LifespanWatch


async def _app(scope: object, receive: object, send: object) -> None:
    """An ASGI app that is never called: only the signal handling is under test."""


def _config() -> uvicorn.Config:
    # No log_config: building the server must not reconfigure logging inside pytest.
    return uvicorn.Config(_app, log_config=None)


@pytest.fixture(name="recorded")
def _recorded() -> Iterator[list[int]]:
    """Record SIGINT and SIGTERM as the handlers in place before uvicorn installs its own."""
    received: list[int] = []

    def _record(signum: int, frame: Optional[FrameType]) -> None:
        received.append(signum)

    previous = {sig: signal.signal(sig, _record) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield received
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
def test_a_handled_signal_is_not_raised_again(signum: signal.Signals, recorded: list[int]) -> None:
    server = commands.ServiceServer(_config())
    recorder = signal.getsignal(signum)
    with server.capture_signals():
        signal.raise_signal(signum)
        assert server.should_exit
        assert not server.force_exit
    assert recorded == []
    assert signal.getsignal(signum) is recorder


@pytest.mark.parametrize(
    ("signals", "forced"),
    [
        ([signal.SIGINT, signal.SIGINT], True),
        ([signal.SIGTERM, signal.SIGINT], True),
        ([signal.SIGINT, signal.SIGTERM], False),
        ([signal.SIGTERM, signal.SIGTERM], False),
    ],
    ids=["SIGINT,SIGINT", "SIGTERM,SIGINT", "SIGINT,SIGTERM", "SIGTERM,SIGTERM"],
)
def test_only_a_later_sigint_forces(
    signals: list[signal.Signals], forced: bool, recorded: list[int]
) -> None:
    """A SIGINT during the shutdown forces whichever signal started it; a SIGTERM never does.

    Both outcomes are uvicorn's ``handle_exit``: a change there that let any second signal
    force would turn a repeated ``kill`` or ``systemctl stop`` into exit 130, and one that
    dropped the SIGTERM-first force would report a forced stop as 0.
    """
    server = commands.ServiceServer(_config())
    with server.capture_signals():
        for signum in signals:
            signal.raise_signal(signum)
        assert server.should_exit
        assert server.force_exit is forced
    assert recorded == []


def test_plain_uvicorn_still_raises_a_handled_signal_again(recorded: list[int]) -> None:
    """Canary: the re-raise that ``ServiceServer`` exists to stop is still uvicorn's.

    When this fails, uvicorn no longer raises a caught signal again after its shutdown:
    delete ``ServiceServer.capture_signals`` and this test.
    """
    server = uvicorn.Server(_config())
    with server.capture_signals():
        signal.raise_signal(signal.SIGTERM)
    assert recorded == [signal.SIGTERM]


# --------------------------------------------------------------------------- #
# LifespanWatch and the exit status it decides
# --------------------------------------------------------------------------- #

_Message = dict[str, Any]


def _drive(app: Any, scope_type: str) -> tuple[LifespanWatch, list[_Message]]:
    """Run ``app`` wrapped in a watch for one scope; return the watch and what reached ``send``."""
    sent: list[_Message] = []

    async def receive() -> _Message:
        return {"type": "lifespan.startup"}

    async def send(message: _Message) -> None:
        sent.append(message)

    watch = LifespanWatch(app)
    asyncio.run(watch({"type": scope_type}, receive, send))  # type: ignore[arg-type]
    return watch, sent


def test_a_watch_hands_other_scopes_to_the_app_untouched() -> None:
    seen: list[Any] = []

    async def app(scope: Any, receive: Any, send: Any) -> None:
        seen.extend([scope, receive, send])

    async def receive() -> _Message:
        return {}

    async def send(message: _Message) -> None:
        raise AssertionError("the app sent nothing")

    scope = {"type": "http"}
    watch = LifespanWatch(app)
    asyncio.run(watch(scope, receive, send))  # type: ignore[arg-type]
    assert seen == [scope, receive, send]
    assert not watch.failed


@pytest.mark.parametrize("event", ["startup", "shutdown"])
def test_a_completed_lifespan_is_not_a_failure(event: str) -> None:
    async def app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": f"lifespan.{event}.complete"})

    watch, sent = _drive(app, "lifespan")
    assert not watch.failed
    assert sent == [{"type": f"lifespan.{event}.complete"}]


@pytest.mark.parametrize("event", ["startup", "shutdown"])
def test_a_failed_lifespan_is_noted_and_still_forwarded(event: str) -> None:
    message = {"type": f"lifespan.{event}.failed", "message": "boom"}

    async def app(scope: Any, receive: Any, send: Any) -> None:
        await send(message)

    watch, sent = _drive(app, "lifespan")
    assert watch.failed
    assert sent == [message]


def _serve_with(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, lifespan_message: str, force: bool
) -> int:
    """``cmd_serve`` on a server that runs the app's lifespan as uvicorn does, then stops."""

    async def app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": lifespan_message})

    class _Server:
        force_exit = False

        def __init__(self, config: uvicorn.Config) -> None:
            self.config = config

        def run(self) -> None:
            self.force_exit = force

            async def send(message: _Message) -> None:
                pass

            async def receive() -> _Message:
                return {}

            watched: Any = self.config.app
            asyncio.run(watched({"type": "lifespan"}, receive, send))

    monkeypatch.setattr(commands, "create_app", lambda settings: app)
    monkeypatch.setattr(commands, "ServiceServer", _Server)
    status: int = commands.cmd_serve(
        argparse.Namespace(root=tmp_path, host="127.0.0.1", port=_free_port(), poll_interval=None)
    )
    return status


@pytest.mark.parametrize(
    ("message", "force", "status"),
    [
        ("lifespan.shutdown.complete", False, 0),
        ("lifespan.shutdown.failed", False, 1),
        ("lifespan.startup.failed", False, 1),
        ("lifespan.shutdown.failed", True, 130),
    ],
    ids=["clean", "shutdown failed", "startup failed", "forced wins"],
)
def test_serve_reports_a_failed_lifespan_in_its_status(
    message: str, force: bool, status: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _serve_with(monkeypatch, tmp_path, lifespan_message=message, force=force) == status


# --------------------------------------------------------------------------- #
# serve in a process of its own
# --------------------------------------------------------------------------- #

#: ``serve`` as a terminal starts it: SIGINT at Python's default handler and SIGTERM at the
#: system's (tests/test_cli_serve.py, ``_SERVE_AS_FROM_A_TERMINAL``, says why both are reset).
_AS_FROM_A_TERMINAL = (
    "import signal, sys\n"
    "signal.signal(signal.SIGINT, signal.default_int_handler)\n"
    "signal.signal(signal.SIGTERM, signal.SIG_DFL)\n"
    "from auto_reel_ng.cli.main import main\n"
    "status = main(sys.argv[1:])\n"
)
_SERVE = _AS_FROM_A_TERMINAL + "sys.exit(status)\n"
#: The same, then a SIGINT and a SIGTERM at itself once ``main()`` has returned: stop signals
#: that land while the process exits, after uvicorn and asyncio have put back the handlers
#: they replaced (at a terminal, a second Ctrl-C a quarter second after the first).
_SERVE_THEN_LATE_SIGNALS = _AS_FROM_A_TERMINAL + (
    "signal.raise_signal(signal.SIGINT)\n"
    "signal.raise_signal(signal.SIGTERM)\n"
    "sys.exit(status)\n"
)


@pytest.fixture(name="stalled_database_url")
def _stalled_database_url() -> Iterator[str]:
    """A Postgres URL whose server accepts a connection and never answers.

    The listener never calls ``accept()``: the kernel completes the connection, and the
    client's first message waits for a reply that never comes.
    """
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    try:
        yield f"postgresql+psycopg://stalled@127.0.0.1:{listener.getsockname()[1]}/stalled"
    finally:
        listener.close()


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    sock.close()
    return port


def _wait_for_log(process: subprocess.Popen[bytes], log: Path, text: str) -> None:
    """Return once ``text`` is in ``serve``'s log; fail if it exits or 15 s pass first."""
    deadline = time.monotonic() + 15
    while text not in log.read_text(encoding="utf-8", errors="replace"):
        if process.poll() is not None:
            pytest.fail(f"serve exited with {process.returncode} before logging {text!r}")
        assert time.monotonic() < deadline, f"serve did not log {text!r} within 15 s"
        time.sleep(0.02)


def _start_serve(
    launcher: str,
    tmp_path: Path,
    database_url: str,
    *,
    listening: bool = True,
) -> tuple[subprocess.Popen[bytes], int, Path]:
    """Start ``serve`` on an empty root and a free port; return once uvicorn is listening.

    ``listening=False`` returns at once, for an app whose startup is meant to fail.
    """
    root = tmp_path / "root"
    root.mkdir()
    port = _free_port()
    log = tmp_path / "serve.log"
    with log.open("wb") as out:
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                launcher,
                "serve",
                str(root),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env={**os.environ, "DATABASE_URL": database_url},
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    if listening:
        _wait_for_log(process, log, "Uvicorn running on")
    return process, port, log


def _end(process: subprocess.Popen[bytes], log: Path) -> str:
    """Kill ``serve`` if it is still up, and return its log (printed, for a failing test)."""
    if process.poll() is None:
        process.kill()
        process.wait()
    output = log.read_text(encoding="utf-8", errors="replace")
    print(output)
    return output


def test_a_forced_stop_does_not_wait_for_a_handler_in_a_worker_thread(
    tmp_path: Path, stalled_database_url: str
) -> None:
    """A second Ctrl-C ends ``serve`` with 130 while a sync handler is still blocked.

    ``GET /healthz`` is a sync route, so it runs in a worker thread, which stays blocked on
    the stalled database after its client gave up. uvicorn's force stops waiting for the
    request's task, but the interpreter joins that thread at exit: the command hung there,
    and a third Ctrl-C ended it in a ``KeyboardInterrupt`` traceback.
    """
    process, port, log = _start_serve(_SERVE, tmp_path, stalled_database_url)
    try:
        with pytest.raises(httpx.ReadTimeout):
            httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1)
        process.send_signal(signal.SIGINT)
        _wait_for_log(process, log, "Waiting for background tasks to complete")
        process.send_signal(signal.SIGINT)
        forced = time.monotonic()
        time.sleep(0.05)
        process.send_signal(signal.SIGINT)  # the operator's third, as the second seems slow
        # A hang fails on this timeout, never the whole suite.
        process.wait(timeout=max(0.0, forced + 5 - time.monotonic()))
    finally:
        output = _end(process, log)
    assert process.returncode == 130
    assert "KeyboardInterrupt" not in output
    assert "Application shutdown complete" not in output


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
def test_a_late_signal_does_not_change_the_exit_status(
    signum: signal.Signals, tmp_path: Path, stalled_database_url: str
) -> None:
    """Once ``serve`` has stopped, a further SIGINT or SIGTERM changes nothing.

    Without ``ServiceServer.run`` ignoring them, the late SIGINT would end the process in a
    ``KeyboardInterrupt`` traceback (killed by SIGINT) and the late SIGTERM would kill it.
    """
    process, _, log = _start_serve(_SERVE_THEN_LATE_SIGNALS, tmp_path, stalled_database_url)
    try:
        process.send_signal(signum)
        process.wait(timeout=5)
    finally:
        output = _end(process, log)
    assert "Application shutdown complete" in output
    assert process.returncode == 0
    assert "Traceback" not in output


def test_a_forced_stop_does_not_wait_for_a_client_that_holds_its_request_open(
    tmp_path: Path, stalled_database_url: str
) -> None:
    """A second Ctrl-C ends ``serve`` with 130 while a half-sent request is still open.

    uvicorn's force skips its two wait loops, then awaits ``wait_closed()`` on its listening
    servers, which since Python 3.12.1 returns only once every accepted connection is gone:
    a client that sent part of a request and went quiet held ``serve`` through any number of
    Ctrl-C (``ServiceServer._wait_tasks_to_complete``).
    """
    process, port, log = _start_serve(_SERVE, tmp_path, stalled_database_url)
    client = socket.create_connection(("127.0.0.1", port))
    try:
        client.sendall(
            b"POST /api/v1/jobs HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
            b"Content-Length: 100\r\n\r\n" + b'{"even'
        )
        time.sleep(0.2)  # let the server accept it and read what was sent
        process.send_signal(signal.SIGINT)
        _wait_for_log(process, log, "Waiting for connections to close")
        process.send_signal(signal.SIGINT)
        # The client still holds its connection open here, so this return is the evidence; a
        # hang fails on the timeout, never the whole suite.
        process.wait(timeout=5)
    finally:
        client.close()
        output = _end(process, log)
    assert process.returncode == 130
    assert "KeyboardInterrupt" not in output
    assert "Application shutdown complete" not in output


# --------------------------------------------------------------------------- #
# serve with a scratch application
# --------------------------------------------------------------------------- #

#: ``serve`` as above, with ``commands.create_app`` replaced by a scratch Starlette app, so the
#: exit paths the real app cannot reach are driven through real ``serve``: ``GET /big`` streams
#: 16 MiB, and ``SCRATCH_LIFESPAN_FAILS`` (``startup`` or ``shutdown``) makes the lifespan raise
#: there, which Starlette reports to uvicorn as ``lifespan.*.failed``.
_SERVE_SCRATCH_APP = (
    "import contextlib, os\n"
    "from starlette.applications import Starlette\n"
    "from starlette.responses import StreamingResponse\n"
    "from starlette.routing import Route\n"
    "from auto_reel_ng.cli import commands\n"
    "fails = os.environ.get('SCRATCH_LIFESPAN_FAILS')\n"
    "@contextlib.asynccontextmanager\n"
    "async def lifespan(app):\n"
    "    if fails == 'startup':\n"
    "        raise RuntimeError('scratch startup failure')\n"
    "    yield\n"
    "    if fails == 'shutdown':\n"
    "        raise RuntimeError('scratch shutdown failure')\n"
    "async def big(request):\n"
    "    async def chunks():\n"
    "        for _ in range(256):\n"
    "            yield b'x' * 65536\n"
    "    return StreamingResponse(chunks())\n"
    "scratch = Starlette(routes=[Route('/big', big)], lifespan=lifespan)\n"
    "commands.create_app = lambda settings: scratch\n"
) + _SERVE


def _scratch_env(monkeypatch: pytest.MonkeyPatch, lifespan_fails: Optional[str] = None) -> None:
    """Pass the scratch app's switch to the child (it inherits the test's environment)."""
    if lifespan_fails is None:
        monkeypatch.delenv("SCRATCH_LIFESPAN_FAILS", raising=False)
    else:
        monkeypatch.setenv("SCRATCH_LIFESPAN_FAILS", lifespan_fails)


def test_a_forced_stop_does_not_wait_for_a_peer_that_stopped_reading(
    tmp_path: Path, stalled_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second Ctrl-C ends ``serve`` with 130 behind a peer with unsent output backed up.

    The connection's write buffer cannot drain, so neither the first signal's wait nor
    ``wait_closed()`` ever ends: only dropping the connection does (``abort_clients``, not
    ``close_clients``, which waits for the buffer).
    """
    _scratch_env(monkeypatch)
    process, port, log = _start_serve(_SERVE_SCRATCH_APP, tmp_path, stalled_database_url)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    try:
        client.connect(("127.0.0.1", port))
        client.sendall(b"GET /big HTTP/1.1\r\nHost: x\r\n\r\n")  # and never read
        time.sleep(0.5)  # the server fills the socket buffers and stalls
        process.send_signal(signal.SIGINT)
        _wait_for_log(process, log, "Waiting for connections to close")
        process.send_signal(signal.SIGINT)
        process.wait(timeout=5)  # the client never reads or closes: the exit is the evidence
    finally:
        client.close()
        output = _end(process, log)
    assert process.returncode == 130
    assert "KeyboardInterrupt" not in output


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM], ids=["SIGINT", "SIGTERM"])
def test_a_failed_application_shutdown_does_not_exit_zero(
    signum: signal.Signals,
    tmp_path: Path,
    stalled_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """uvicorn logs a failed lifespan shutdown and returns normally: ``serve`` still says 1."""
    _scratch_env(monkeypatch, "shutdown")
    process, _, log = _start_serve(_SERVE_SCRATCH_APP, tmp_path, stalled_database_url)
    try:
        process.send_signal(signum)
        process.wait(timeout=5)
    finally:
        output = _end(process, log)
    assert "Application shutdown failed" in output
    assert "scratch shutdown failure" in output
    assert process.returncode == 1


def test_a_failed_application_startup_does_not_exit_zero(
    tmp_path: Path, stalled_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scratch_env(monkeypatch, "startup")
    process, _, log = _start_serve(
        _SERVE_SCRATCH_APP, tmp_path, stalled_database_url, listening=False
    )
    try:
        process.wait(timeout=10)
    finally:
        output = _end(process, log)
    assert "Application startup failed" in output
    assert "could not bind" not in output  # uvicorn exits through SystemExit for this too
    assert "error: application startup failed" in output
    assert process.returncode == 1
