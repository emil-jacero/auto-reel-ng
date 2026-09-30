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

The hub reports one project, the one the service serves (D-A1): both reads are
narrowed to its root, so no frame carries another project's job, and a change to
one never causes a delta (jobs-project-guards). Only the report is scoped: the
worker queue stays shared by every project in the database.

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
from starlette.status import WS_1011_INTERNAL_ERROR, WS_1013_TRY_AGAIN_LATER
from starlette.websockets import WebSocketState

from ..persistence.job_store import FinishedJobs, JobStore
from ..persistence.models import TERMINAL_STATUSES, Job, JobStatus
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


class JobsHub:
    """Subscriber-gated central poller + fanout for live job updates."""

    def __init__(
        self,
        job_store: JobStore,
        *,
        project_root: str,
        poll_interval: float,
        queue_maxsize: int = _QUEUE_MAXSIZE,
    ) -> None:
        self._store = job_store
        # Required, with no default: a forgotten argument must not silently widen the
        # feed to every project in the database.
        self._project_root = project_root
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
        as any later delta. The queue is registered only once the first
        subscriber's reads have succeeded: a start that fails (a database blip) or
        is cancelled leaves the hub as it was, so the next subscriber is the first
        one again and starts the poller, rather than joining one that never ran.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        async with self._lock:
            if not self._subscribers:
                await self._start_polling()
            self._subscribers.add(queue)
        queue.put_nowait(self._encode(WsMessageType.SNAPSHOT, self._snapshot.values()))
        return queue

    async def _start_polling(self) -> None:
        """Seed the poller's state and start it: the first subscriber's work.

        The finished read comes before the active snapshot: a job finishing between
        the two is then in neither, and the first tick sends it. In the other order
        it would be seeded as sent while no frame carried its terminal row. If either
        read raises, or the caller is cancelled, the finished-jobs state is reset
        and the error propagates with no poller started.
        """
        try:
            await self._seed_finished()
            self._snapshot = await self._fetch_active_snapshot()
        except BaseException:
            self._finished_as_of = None
            self._terminal_sent = {}
            raise
        self._poller_task = asyncio.create_task(self._poll_loop())

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
            if record.status in TERMINAL_STATUSES:
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
        active: list[Job] = []
        for status in (JobStatus.QUEUED, JobStatus.RUNNING):
            read = functools.partial(
                self._store.list_by_status, status, project_root=self._project_root
            )
            active.extend(await loop.run_in_executor(self._executor, read))
        return {job.id: job_to_out(job) for job in active}

    async def _fetch_one(self, job_id: uuid.UUID) -> Optional[JobOut]:
        # Only ever asked for a job the scoped snapshot held: it needs no scope check.
        loop = asyncio.get_running_loop()
        job = await loop.run_in_executor(self._executor, self._store.get, job_id)
        return job_to_out(job) if job is not None else None

    async def _fetch_finished(self, since: Optional[datetime]) -> FinishedJobs:
        loop = asyncio.get_running_loop()
        read = functools.partial(
            self._store.list_finished_since,
            since,
            overlap=_FINISHED_OVERLAP,
            project_root=self._project_root,
        )
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


async def _push_frames(websocket: WebSocket, hub: JobsHub, queue: asyncio.Queue) -> None:
    """Send the hub's frames until it lets this subscriber go (close 1013) or a send fails.

    However the push side ends (the hub let go, a send failed, or the handler cancelled
    it), it releases the subscription itself. One ending reaches it long before the
    handler's receive loop: once uvicorn's keepalive has failed a connection whose frames
    are backed up, it has sent its own close, so the next send raises and the 1011 close
    is refused, and the disconnect waits until the write buffer drains.
    """
    try:
        while (message := await queue.get()) is not _CLOSE:
            await websocket.send_text(message)
        await _close(websocket, WS_1013_TRY_AGAIN_LATER)  # dropped (slow consumer) or hub stopped
    except WebSocketDisconnect:
        pass  # the connection is gone; the receive loop sees it too
    except Exception:
        await _close(websocket, WS_1011_INTERNAL_ERROR)
        raise
    finally:
        await hub.unsubscribe(queue)  # a no-op when the handler released it first


async def _close(websocket: WebSocket, code: int) -> None:
    """Close the connection with ``code`` unless it has already ended."""
    if websocket.application_state is WebSocketState.CONNECTED:
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await websocket.close(code)


@router.websocket("/api/v1/ws/jobs")
async def ws_jobs(websocket: WebSocket) -> None:
    """``WS /api/v1/ws/jobs`` (task 4.2-4.3): snapshot on connect, then deltas.

    The channel is push-only, yet the handler reads the connection until it ends and
    drops whatever a client sends. The receive loop is where the server reports every
    end of a connection: a client close, a peer lost to uvicorn's keepalive (a ping every
    20 s, answered within 20 s) and the server's own shutdown, which closes every
    connection with 1012 (service restart). Each releases the subscription at once, so
    the last one out stops the poller (D-A4), and at shutdown the handlers end before
    the lifespan's ``hub.stop()`` (D-A7).

    Frames go out from a push task the handler owns. When the hub lets the subscriber go
    (a slow consumer, or the hub stopping), it closes with 1013 (try again later: a
    reconnect gets a fresh snapshot). An unexpected send error closes with 1011
    (internal error) and is re-raised here once the connection has ended, so uvicorn
    logs it. The server reports either close back to the receive loop as a disconnect.

    Only the push task is ever cancelled, never ``receive()``: it waits on the hub's
    queue or on a send, and cancelling either is safe. It also releases the subscription
    itself, for the one ending the receive loop learns of late (:func:`_push_frames`).
    The handler's own release comes first in its cleanup, before anything can suspend:
    a test harness (Starlette's ``TestClient``) cancels the handler right after it
    delivers the disconnect, and a cancel landing on an earlier await would skip it.
    """
    hub: JobsHub = websocket.app.state.jobs_hub
    await websocket.accept()
    queue: Optional[asyncio.Queue] = None
    pusher: Optional[asyncio.Task[None]] = None
    try:
        # Inside the try, so whatever ends this handler, a subscriber it
        # registered is unsubscribed (a failed subscribe registers none).
        queue = await hub.subscribe()
        pusher = asyncio.create_task(_push_frames(websocket, hub, queue))
        # Push-only: what a client sends is read and dropped until the connection ends.
        while (await websocket.receive())["type"] != "websocket.disconnect":
            pass
    finally:
        # Release before anything here can suspend: a cancel landing on the wait below
        # must find the subscription already gone.
        if pusher is not None:
            pusher.cancel()
        if queue is not None:
            await hub.unsubscribe(queue)
        if pusher is not None:
            await asyncio.wait({pusher})  # never raises; the outcome is read below
    if pusher is not None and not pusher.cancelled():
        pusher.result()  # re-raise an unexpected push error for uvicorn to log


__all__ = ["JobsHub", "publish_ws_schema", "router"]
