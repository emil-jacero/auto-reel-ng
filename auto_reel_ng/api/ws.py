"""The WebSocket live-progress hub (decision D-A4, tasks 4.1-4.4).

A single central poller task queries the store for active (``queued``/``running``)
jobs at ``poll_interval``, diffs against its last snapshot, and fans out JSON
deltas to every subscriber. The poller starts with the first subscriber and stops
with the last, so an idle service issues no store queries. A subscriber that
cannot keep up (a full outbound queue) is disconnected rather than back-pressuring
the hub; its recovery path is reconnect, which gets a fresh snapshot.

Each poll also reads the jobs that finished since the previous one, so a job whose
whole active life fell between two polls — enqueued, claimed and failed at probe
within one interval — still reaches every connected subscriber, exactly once.

Store calls run on a dedicated single-thread executor (D-A5 risk mitigation), so
concurrent REST scan requests (FastAPI's default threadpool) can never starve the
poller.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic.json_schema import models_json_schema

from ..persistence.job_store import FinishedJobs, JobStore
from ..persistence.models import JobStatus
from .schemas import JobOut, WsMessage, WsMessageType
from .serialize import job_to_out

#: Sentinel placed on a subscriber's queue to signal "your connection is being
#: closed" (either a slow-consumer drop, or hub shutdown).
_CLOSE = object()

#: Bounded per-connection queue depth (D-A4): a slow consumer is dropped, never
#: allowed to back-pressure the poller.
_QUEUE_MAXSIZE = 64

#: How far each poll's finished-jobs read reaches back before the previous read's
#: time. ``finished_at`` is the *start* of the terminal write's transaction, which
#: can commit after a read already past it; that write is one read and one update,
#: so 30 s is orders of magnitude of slack, at the cost of re-reading 30 s of
#: finished rows per poll.
_FINISHED_OVERLAP = timedelta(seconds=30)

#: The statuses a job never leaves: a row in one of them is sent at most once.
_TERMINAL = frozenset({JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED})


class JobsHub:
    """Subscriber-gated central poller + fanout for live job updates."""

    def __init__(
        self, job_store: JobStore, *, poll_interval: float, queue_maxsize: int = _QUEUE_MAXSIZE
    ) -> None:
        self._store = job_store
        self._poll_interval = poll_interval
        self._queue_maxsize = queue_maxsize
        self._subscribers: set[asyncio.Queue] = set()
        self._snapshot: dict[uuid.UUID, JobOut] = {}
        # The finished-jobs watermark (database time) and the jobs a frame already
        # carried as terminal, by id, with their ``finished_at``: seeded when the
        # poller starts, dropped when it stops.
        self._finished_as_of: Optional[datetime] = None
        self._terminal_sent: dict[uuid.UUID, datetime] = {}
        self._poller_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        # Single-thread executor (D-A5 risk mitigation): the poller's store calls
        # never compete with REST scan requests for FastAPI's default threadpool.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jobs-hub")

    @property
    def subscriber_count(self) -> int:
        """The number of currently connected subscribers (tests)."""
        return len(self._subscribers)

    @property
    def is_polling(self) -> bool:
        """Whether the central poller task is currently running (tests)."""
        return self._poller_task is not None

    async def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber; starts the poller if this is the first one.

        Returns a queue whose first item is always a full snapshot (D-A4:
        snapshot-on-connect), so the caller's send loop delivers it the same way
        as any later delta.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        async with self._lock:
            first = not self._subscribers
            self._subscribers.add(queue)
            if first:
                # The finished read comes before the active snapshot: a job finishing
                # between the two is then in neither, and the first tick sends it. In
                # the other order it would be seeded as sent while no frame carried
                # its terminal row.
                await self._seed_finished()
                self._snapshot = await self._fetch_active_snapshot()
                self._poller_task = asyncio.create_task(self._poll_loop())
        queue.put_nowait(self._encode(WsMessageType.SNAPSHOT, self._snapshot.values()))
        return queue

    async def unsubscribe(self, queue: asyncio.Queue, *, notify_close: bool = False) -> None:
        """Remove ``queue``; stops the poller if it was the last subscriber."""
        async with self._lock:
            self._subscribers.discard(queue)
            if notify_close:
                self._force_put(queue, _CLOSE)
            if not self._subscribers and self._poller_task is not None:
                self._poller_task.cancel()
                self._poller_task = None
                # A job finishing while nobody is connected is never sent: the next
                # first subscriber seeds both again, and a client reconciles the jobs
                # it tracks after its snapshot.
                self._finished_as_of = None
                self._terminal_sent = {}

    async def stop(self) -> None:
        """Shut the hub down (app shutdown, D-A7): close every subscriber, stop polling.

        Awaits the cancelled poller task and shuts the executor down with
        ``wait=True`` *before* returning: the app's lifespan disposes the engine
        immediately after calling this, and a store call still in flight on the
        executor thread when that happens would race a closing connection pool.
        """
        async with self._lock:
            poller = self._poller_task
            self._poller_task = None
            for queue in list(self._subscribers):
                self._force_put(queue, _CLOSE)
            self._subscribers.clear()
        if poller is not None:
            poller.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller
        self._executor.shutdown(wait=True)

    @staticmethod
    def _force_put(queue: asyncio.Queue, item: object) -> None:
        """Put ``item`` on ``queue``, dropping the oldest entry first if full."""
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - racy, harmless
                pass
            queue.put_nowait(item)

    @staticmethod
    def _encode(message_type: WsMessageType, jobs: Iterable[JobOut]) -> str:
        return WsMessage(type=message_type, jobs=list(jobs)).model_dump_json()

    async def _poll_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._poll_interval)
                await self._tick()
        except asyncio.CancelledError:
            pass

    async def _tick(self) -> None:
        """One poll: diff the fresh active snapshot against the last, broadcast deltas.

        The finished read comes first. A job that leaves the active set by a commit
        landing between the two reads is then sent by this tick's ``vanished`` path,
        and ``_terminal_sent`` keeps the next tick's finished read from resending it.
        """
        finished = await self._fetch_finished(self._finished_as_of)
        new_snapshot = await self._fetch_active_snapshot()

        deltas: list[JobOut] = []
        for job_id, record in new_snapshot.items():
            previous = self._snapshot.get(job_id)
            if (
                previous is None
                or previous.status != record.status
                or previous.progress != record.progress
                # A cancel request on a running job moves neither of the above: the
                # flag is all it writes, so a change of it is a change of its own.
                or previous.cancel_requested != record.cancel_requested
            ):
                deltas.append(record)

        # The rows that left the active set: the final row of every job active last
        # tick but absent now (D-A4 risk: "poller misses short-lived states"), merged
        # by id with every job finished since the last read — which also holds a job
        # whose whole active life fell between two polls, so no snapshot ever had it.
        left = {job.id: job_to_out(job) for job in finished.jobs}
        vanished = set(self._snapshot) - set(new_snapshot)
        for job_id in vanished:
            final = await self._fetch_one(job_id)
            if final is not None:
                left[job_id] = final
        for record in left.values():
            if record.status in _TERMINAL:
                if record.id in self._terminal_sent:
                    continue  # an earlier frame carried it, whichever path found it
                if record.finished_at is not None:  # else no finished read returns it
                    self._terminal_sent[record.id] = record.finished_at
            deltas.append(record)

        self._snapshot = new_snapshot
        self._advance_finished_watermark(finished.as_of)
        if deltas:
            await self._broadcast(self._encode(WsMessageType.DELTA, deltas))

    def _advance_finished_watermark(self, as_of: datetime) -> None:
        """Make ``as_of`` the next finished read's instant, forgetting what it cannot return.

        The next read returns only ``finished_at >= as_of - overlap``, so an older
        entry can never come back to be de-duplicated: ``_terminal_sent`` stays
        bounded by one window's worth of finished jobs.
        """
        self._finished_as_of = as_of
        cutoff = as_of - _FINISHED_OVERLAP
        self._terminal_sent = {
            job_id: finished_at
            for job_id, finished_at in self._terminal_sent.items()
            if finished_at >= cutoff
        }

    async def _broadcast(self, message: str) -> None:
        dead: list[asyncio.Queue] = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(queue)
        for queue in dead:
            # Slow-consumer policy (D-A4): drop rather than back-pressure the hub;
            # the client reconnects and resyncs via a fresh snapshot.
            await self.unsubscribe(queue, notify_close=True)

    async def _fetch_active_snapshot(self) -> dict[uuid.UUID, JobOut]:
        loop = asyncio.get_running_loop()
        queued = await loop.run_in_executor(
            self._executor, self._store.list_by_status, JobStatus.QUEUED
        )
        running = await loop.run_in_executor(
            self._executor, self._store.list_by_status, JobStatus.RUNNING
        )
        return {job.id: job_to_out(job) for job in (*queued, *running)}

    async def _fetch_one(self, job_id: uuid.UUID) -> Optional[JobOut]:
        loop = asyncio.get_running_loop()
        job = await loop.run_in_executor(self._executor, self._store.get, job_id)
        return job_to_out(job) if job is not None else None

    async def _fetch_finished(self, since: Optional[datetime]) -> FinishedJobs:
        loop = asyncio.get_running_loop()
        read = functools.partial(self._store.list_finished_since, since, overlap=_FINISHED_OVERLAP)
        return await loop.run_in_executor(self._executor, read)

    async def _seed_finished(self) -> None:
        """Start the finished-jobs watermark, counting what already finished as sent.

        Those jobs finished before the poller existed: no subscriber saw them active,
        so none is owed their terminal row (a client reconciles the jobs it tracks
        after its snapshot).
        """
        finished = await self._fetch_finished(None)
        self._terminal_sent = {
            job.id: job.finished_at for job in finished.jobs if job.finished_at is not None
        }
        self._finished_as_of = finished.as_of


def publish_ws_schema(schema: dict[str, Any]) -> None:
    """Add the WebSocket frame's models to an OpenAPI ``schema``'s components, in place.

    A WebSocket route contributes nothing to ``app.openapi()``, yet the client parses
    every frame: publishing :class:`WsMessage` and :class:`WsMessageType` as named
    components — never through a fake HTTP route — lets the generated types carry
    the frame (D-8, §4.10). Only absent names are added, so the frame's references
    resolve to the ``JobOut`` and ``JobStatus`` the routes publish (pydantic's own
    ``JobOut`` definition is not byte-identical to FastAPI's), and a repeated call
    adds nothing.
    """
    _, top_level = models_json_schema(
        [(WsMessage, "serialization")], ref_template="#/components/schemas/{model}"
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in top_level.get("$defs", {}).items():
        components.setdefault(name, definition)


router = APIRouter()


@router.websocket("/api/v1/ws/jobs")
async def ws_jobs(websocket: WebSocket) -> None:
    """``WS /api/v1/ws/jobs`` (task 4.2-4.3): snapshot on connect, then deltas.

    A single send loop only — no concurrent "detect disconnect promptly" reader
    task. That pattern (two tasks + cancel-the-other-on-first-completion) proved
    racy under test-harness teardown (a cancelled sibling task's exception
    surfacing through the WS test client's own close handshake); a disconnect is
    still caught here via ``WebSocketDisconnect`` on the next failed send, which
    is standard practice for a push-only channel like this one.
    """
    hub: JobsHub = websocket.app.state.jobs_hub
    await websocket.accept()
    queue = await hub.subscribe()
    try:
        while True:
            message = await queue.get()
            if message is _CLOSE:
                break
            await websocket.send_text(message)
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(queue)


__all__ = ["JobsHub", "publish_ws_schema", "router"]
