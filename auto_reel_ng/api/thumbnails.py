"""The thumbnail route's extraction bound (D-11): at most two at once, one per cache key.

An event page asks for one thumbnail per clip, so a cold cache turns one page view
into dozens of ffmpeg processes reading the archive's USB drive. :class:`ThumbnailGate`
bounds that per service process and makes concurrent requests for the same cache
key share one extraction. Waiting costs no thread: requests wait on ``asyncio``
primitives, and only a running extraction holds a threadpool worker, so the rest of
the API keeps answering while thumbnails are made.

The limit is a property of serving, not of extracting: the engine operation is
unbounded, and the CLI bounds itself with ``auto-reel thumbs --jobs N``.
"""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
from typing import Callable, Dict

from starlette.concurrency import run_in_threadpool

#: Extractions one service process runs at once; further requests wait for a slot.
MAX_CONCURRENT_EXTRACTIONS = 2


class ThumbnailGate:
    """At most ``limit`` extractions at once; one shared extraction per cache key.

    Built once per app (``app.state.thumbnail_gate``). The in-flight map is keyed by
    the engine's own cache key, so "the same thumbnail" means exactly what the cache
    means by it: symlinked clips in several events share one extraction.
    """

    def __init__(self, limit: int = MAX_CONCURRENT_EXTRACTIONS) -> None:
        self._slots = asyncio.Semaphore(limit)
        self._in_flight: Dict[str, asyncio.Task[Path]] = {}

    async def produce(self, key: str, extract: Callable[[], Path]) -> Path:
        """Run ``extract`` in the threadpool under a slot, or join the one running for ``key``.

        Every waiter gets the shared extraction's result or its exception. A failed
        extraction leaves the map, so the next request for ``key`` tries again in the gate
        (``thumbnail_for`` may still answer the clip's recorded failure marker, for 60 s).
        """
        task = self._in_flight.get(key)
        if task is None:
            task = asyncio.create_task(self._run(extract))
            self._in_flight[key] = task
            task.add_done_callback(partial(self._settled, key))
        # asyncio.wait never cancels what it waits on: a cancelled waiter leaves the
        # shared extraction running for the others. Not asyncio.shield: a shielded
        # waiter cancelled early reports the extraction's later exception through the
        # loop's exception handler, one ERROR traceback per abandoned request.
        await asyncio.wait((task,))
        return task.result()

    async def _run(self, extract: Callable[[], Path]) -> Path:
        async with self._slots:
            return await run_in_threadpool(extract)

    def _settled(self, key: str, task: asyncio.Task[Path]) -> None:
        if self._in_flight.get(key) is task:
            del self._in_flight[key]
        if not task.cancelled():
            # Mark it retrieved: no "exception was never retrieved" when every waiter left.
            task.exception()


__all__ = ["MAX_CONCURRENT_EXTRACTIONS", "ThumbnailGate"]
