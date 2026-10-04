"""The title-card preview's bound: at most two draws at once, with a wait limit.

A preview is a draft drawn with Cairo/Pango on the server; an editor can send one per
keystroke. :class:`PreviewGate` keeps a burst from filling the threadpool: requests wait on an
``asyncio`` semaphore (no thread held while waiting), only a draw in progress holds a worker,
and a request that cannot start within the wait limit is refused (503) and is never drawn
afterwards. Modelled on :class:`~auto_reel_ng.api.thumbnails.ThumbnailGate`.
"""

from __future__ import annotations

import asyncio
from typing import Callable, TypeVar

from starlette.concurrency import run_in_threadpool

#: Draws one service process runs at once; further requests wait for a slot.
MAX_CONCURRENT_PREVIEWS = 2

#: How long a request waits for a slot before it is answered 503, in seconds.
PREVIEW_WAIT_SECONDS = 10.0

_T = TypeVar("_T")


class PreviewBusyError(Exception):
    """No draw slot became free within the wait limit."""


class PreviewGate:
    """At most ``limit`` draws at once; a waiter gives up after ``wait`` seconds."""

    def __init__(
        self, limit: int = MAX_CONCURRENT_PREVIEWS, wait: float = PREVIEW_WAIT_SECONDS
    ) -> None:
        self._slots = asyncio.Semaphore(limit)
        self.wait = wait

    async def run(self, draw: Callable[[], _T]) -> _T:
        """Run ``draw`` in the threadpool under a slot.

        Raises:
            PreviewBusyError: no slot was free within ``wait`` seconds; ``draw`` was not run.
        """
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=self.wait)
        except asyncio.TimeoutError as exc:
            raise PreviewBusyError(
                f"the title-card preview is busy: no draw slot free within {self.wait:g} s"
            ) from exc
        try:
            return await run_in_threadpool(draw)
        finally:
            self._slots.release()


__all__ = ["MAX_CONCURRENT_PREVIEWS", "PREVIEW_WAIT_SECONDS", "PreviewBusyError", "PreviewGate"]
