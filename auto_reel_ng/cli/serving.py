"""``serve``'s uvicorn server: how a stop signal ends the process and what it reports.

Split from :mod:`.commands` (which keeps ``cmd_serve`` and imports :class:`ServiceServer` back,
the name tests patch there) so the subcommand module stays under pylint's line cap.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import socket
import sys
import threading
from typing import Iterator, List, NoReturn, Optional, override

import uvicorn


class ServiceServer(uvicorn.Server):
    """uvicorn's server for ``serve``: a stop signal it has obeyed is not raised again.

    After its orderly shutdown ``uvicorn.Server`` raises each signal it caught once more,
    for the handler installed before it: asyncio's SIGINT handler turns that into a
    ``KeyboardInterrupt`` traceback, and SIGTERM's default handler kills the process.
    ``serve`` has nothing left for the signal to do. It returns, and its exit status
    reports the stop (headless-cli, "`serve` runs the API service"), which :meth:`run`
    makes final.
    """

    @override
    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        with super().capture_signals():
            yield
            # The shutdown the captured signals asked for has completed.
            self._captured_signals.clear()

    @override
    def run(self, sockets: Optional[List[socket.socket]] = None) -> None:
        """Serve until stopped; on the main thread, then make the stop final.

        Once uvicorn returns, the outcome is decided (:func:`.commands.cmd_serve`). A further SIGINT
        or SIGTERM is ignored from here on: the interpreter resets Python-level handlers
        while it finalizes, so only ``SIG_IGN`` keeps a late signal from killing the
        exiting process or ending it in a ``KeyboardInterrupt``. A forced stop ends the
        process here: a request handler still running in a worker thread (a sync route
        blocked on a stalled database or a slow drive) would otherwise hold the exit, as
        uvicorn's force stops waiting for its task but the interpreter joins the thread.
        Off the main thread (in-process tests) uvicorn handled no signal: this returns.
        """
        super().run(sockets)
        if threading.current_thread() is not threading.main_thread():
            return
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, signal.SIG_IGN)
        if self.force_exit:
            _end_forced_stop()


def _end_forced_stop() -> NoReturn:
    """End the process at once with status 130, without joining any worker thread.

    The log and the standard streams are flushed first. The app's lifespan cleanup
    has already run, when ``asyncio.run`` cancelled the lifespan task.
    """
    logging.shutdown()
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            with contextlib.suppress(OSError, ValueError):
                stream.flush()
    os._exit(130)
