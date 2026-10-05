"""The CPU-token turn protocol shared by the low-priority job kinds (``proxy``, ``analysis``).

A low-priority job holds one CPU token while it works on a clip and **yields**: it does not
start a clip while a job of a kind it yields to is ``running`` (a claimed job that waits for
the CPU token is already ``running``), and while it waits it gives its token back, so a job
it yields to that is itself waiting for that token is never blocked by the job yielding to it.
A clip already started finishes. Waiting, it still answers a cancel and a worker stop.

The ``proxy`` job yields to renders; the ``analysis`` job to renders and proxy jobs. The poll
intervals are passed per call, so each handler's own module constants stay its tuning knobs.
"""

from __future__ import annotations

import threading
from typing import Collection

from ..errors import RenderCancelledError
from ..persistence.job_store import JobStore
from ..persistence.models import Job, JobStatus
from .worker import JobInterrupted


class Hold:
    """A job's CPU token and whether the job holds it now."""

    def __init__(self, token: threading.BoundedSemaphore) -> None:
        self.token = token
        self.held = False

    def release(self) -> None:
        """Give the token back if held; safe to call twice."""
        if self.held:
            self.held = False
            self.token.release()


class Turns:
    """One handler's view of the protocol: its store, its stop event and its kind's name."""

    def __init__(self, store: JobStore, stop: threading.Event, *, label: str) -> None:
        self._store = store
        self._stop = stop
        self._label = label

    def stop_or_cancel(self, job: Job) -> None:
        """Raise the right interruption now if the worker is stopping or the job was canceled.

        Raises:
            JobInterrupted: the worker is stopping (the row is left for its requeue).
            RenderCancelledError: the job's ``cancel_requested`` is set.
        """
        if self._stop.is_set():
            raise JobInterrupted(f"job {job.id}: the worker is stopping")
        current = self._store.get(job.id)
        if current is not None and current.cancel_requested:
            raise RenderCancelledError(f"{self._label} job {job.id} was canceled")

    def acquire(self, hold: Hold, job: Job, *, poll_s: float) -> None:
        """Wait for the CPU token, still answering a cancel or a stop while waiting."""
        while not hold.token.acquire(timeout=poll_s):
            self.stop_or_cancel(job)
        hold.held = True
        self.stop_or_cancel(job)

    def running(self, kinds: Collection[str]) -> bool:
        """Whether a job of one of ``kinds`` is ``running`` now."""
        return any(self._store.list_by_status(JobStatus.RUNNING, kind=kind) for kind in kinds)

    def take_turn(  # pylint: disable=too-many-arguments
        self,
        job: Job,
        hold: Hold,
        *,
        yield_to: Collection[str],
        token_poll_s: float,
        yield_poll_s: float,
    ) -> None:
        """Hold the CPU token at a moment when no job of ``yield_to`` is running."""
        while True:
            if not hold.held:
                self.acquire(hold, job, poll_s=token_poll_s)
            if not self.running(yield_to):
                return
            hold.release()
            while self.running(yield_to):
                self.stop_or_cancel(job)
                self._stop.wait(yield_poll_s)


__all__ = ["Hold", "Turns"]
