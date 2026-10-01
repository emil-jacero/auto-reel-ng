"""``serve``'s uvicorn server does not raise a stop signal again (serve-clean-exit 2.2).

``uvicorn.Server.capture_signals`` installs its handlers only on the main thread, which is
pytest's, and after the block it raises every signal it caught once more for the handlers
it restores. A recording handler for SIGINT and SIGTERM stands in for those, so a signal
raised again lands in a list instead of in pytest's own handler (an aborted run) or in
SIGTERM's default (a killed one). No server runs and no database is needed.
"""

from __future__ import annotations

import signal
from types import FrameType
from typing import Iterator, Optional

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
    delete ``ServiceServer`` (``serve`` can build ``uvicorn.Server`` again) and this test.
    """
    server = uvicorn.Server(_config())
    with server.capture_signals():
        signal.raise_signal(signal.SIGTERM)
    assert recorded == [signal.SIGTERM]
