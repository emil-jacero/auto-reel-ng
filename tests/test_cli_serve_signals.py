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

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import FrameType
from typing import Iterator, Optional

import httpx
import pytest
import uvicorn

from auto_reel_ng.cli import commands


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
    port = sock.getsockname()[1]
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
    launcher: str, tmp_path: Path, database_url: str
) -> tuple[subprocess.Popen[bytes], int, Path]:
    """Start ``serve`` on an empty root and a free port; return once uvicorn is listening."""
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
