"""Throttled progress reporting into the job store (job-scheduler, task 3.5).

``render_movie``'s ``on_progress`` fires on every ffmpeg ``-progress`` line —
far more often than the job row needs updating. :class:`ThrottledProgress` wraps
it into a rate-limited writer so ``set_progress`` is called at most once per
``min_interval_s`` or ``min_delta`` of fractional advance, while still
guaranteeing the terminal ``1.0`` is never dropped by the throttle.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable, Optional

from ..persistence.job_store import JobStore

Clock = Callable[[], float]


class ThrottledProgress:
    """A ``(fraction: float) -> None`` callable that throttles writes to the store."""

    def __init__(
        self,
        store: JobStore,
        job_id: uuid.UUID,
        *,
        min_delta: float = 0.01,
        min_interval_s: float = 1.0,
        clock: Clock = time.monotonic,
    ) -> None:
        self._store = store
        self._job_id = job_id
        self._min_delta = min_delta
        self._min_interval_s = min_interval_s
        self._clock = clock
        self._last_written: Optional[float] = None
        self._last_written_at: Optional[float] = None

    def __call__(self, fraction: float) -> None:
        """Write ``fraction`` if due (first call, delta, interval, or terminal)."""
        now = self._clock()
        due_to_delta = (
            self._last_written is None or (fraction - self._last_written) >= self._min_delta
        )
        due_to_interval = (
            self._last_written_at is None or (now - self._last_written_at) >= self._min_interval_s
        )
        if fraction >= 1.0 or due_to_delta or due_to_interval:
            self._store.set_progress(self._job_id, fraction)
            self._last_written = fraction
            self._last_written_at = now


__all__ = ["ThrottledProgress"]
