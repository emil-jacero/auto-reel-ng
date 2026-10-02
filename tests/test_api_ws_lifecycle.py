"""The jobs WebSocket's connection lifecycle under a real server (jobs-ws-lifecycle 2.1-2.3).

Starlette's ``TestClient`` cannot show how the end of a connection reaches the hub: it
has no transport, no keepalive and no server shutdown, and its session exit cancels
the handler. These tests serve the app in-process with ``uvicorn.Server``, the base class
of ``ServiceServer``, the server ``auto-reel serve`` runs, on the test's own event loop and
over the in-memory ``FakeStore`` of ``test_api_ws_hub.py``, so they need no database. The
clients are ``websockets`` clients; the silent peer is a raw socket that completes the
opening handshake and then never reads again.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Optional

import pytest
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from test_api_ws_hub import BLANDAT, PROJ, FakeJob, FakeStore
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from auto_reel_ng.api import ws as ws_module
from auto_reel_ng.api.ws import _CLOSE, JobsHub, _next_message, router
from auto_reel_ng.persistence.models import JobStatus

#: The hub's poll interval: five polls without a store query take a quarter second.
POLL = 0.05

#: A dev-library event id (``scripts/make_dev_library.py``) the spec scenarios name.
GRILLNING = "2024/2024-06-27 - Grillning med grannar"

WS_PATH = "/api/v1/ws/jobs"


def _app(hub: JobsHub) -> FastAPI:
    """The WebSocket route over ``hub``, whose lifespan ends with ``hub.stop()`` like the app's."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await hub.stop()

    app = FastAPI(lifespan=lifespan)
    app.state.jobs_hub = hub
    app.include_router(router)
    return app


@dataclass
class _Served:
    """An app under a running ``uvicorn.Server``: what a test drives and inspects."""

    hub: JobsHub
    store: FakeStore
    server: uvicorn.Server
    task: asyncio.Task[None]
    port: int

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}{WS_PATH}"


@asynccontextmanager
async def _serving(
    store: Optional[FakeStore] = None,
    *,
    queue_maxsize: Optional[int] = None,
    poll_interval: float = POLL,
    **config: Any,
) -> AsyncIterator[_Served]:
    """Serve a hub over ``store`` with ``uvicorn.Server`` on this loop until the block ends.

    ``poll_interval`` is the hub's; ``config`` overrides uvicorn settings (the keepalive).
    ``log_config=None`` leaves the process's logging as it is: uvicorn's default config would
    stop the ``uvicorn`` logger's propagation mid-test, and ``caplog`` would miss that test's
    uvicorn records.
    Port 0 lets the kernel pick a free port.
    Leaving the block stops the server the way a signal does (``should_exit``) and waits
    for its shutdown, lifespan included.
    """
    store = store if store is not None else FakeStore()
    sizing = {} if queue_maxsize is None else {"queue_maxsize": queue_maxsize}
    hub = JobsHub(store, project_root=PROJ, poll_interval=poll_interval, **sizing)
    server = uvicorn.Server(
        uvicorn.Config(
            _app(hub), host="127.0.0.1", port=0, log_level="warning", log_config=None, **config
        )
    )
    task = asyncio.create_task(server.serve())
    await _until(lambda: server.started, timeout=5.0)
    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield _Served(hub, store, server, task, port)
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 5.0)


async def _until(predicate: Callable[[], bool], *, timeout: float = 1.0) -> None:
    """Return once ``predicate()`` holds; raise ``TimeoutError`` after ``timeout`` seconds."""
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)


async def _frame(client: ClientConnection) -> Any:
    """The next frame ``client`` receives, decoded; fails when none arrives within a second."""
    return json.loads(await asyncio.wait_for(client.recv(), 1.0))


async def _close_code(client: ClientConnection, *, timeout: float = 2.0) -> Optional[int]:
    """Read ``client`` until its connection ends: the code of the close frame it received.

    A frame still in flight ahead of the close (a delta) is read and dropped. ``None``
    means the connection ended without a close frame, which a client reports as 1006.
    """
    try:
        async with asyncio.timeout(timeout):
            while True:
                await client.recv()
    except ConnectionClosed as closed:
        return closed.rcvd.code if closed.rcvd is not None else None


def _store_reads(store: FakeStore) -> tuple[int, int, int]:
    """Every read the hub has made of ``store``, counted by kind."""
    return (store.list_by_status_calls, store.get_calls, store.list_finished_since_calls)


def _running_job(store: FakeStore, **fields: Any) -> uuid.UUID:
    """Add a running job to ``store``; its id."""
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, **fields)
    return job_id


def _upgrade_request(port: int) -> bytes:
    """A WebSocket opening handshake for the jobs route, as sent on the wire."""
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    return (
        f"GET {WS_PATH} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ).encode("ascii")


def _logged_asgi_error(caplog: pytest.LogCaptureFixture, error: type[BaseException]) -> bool:
    """Whether uvicorn logged "Exception in ASGI application" for an ``error``."""
    return any(
        record.name == "uvicorn.error"
        and "Exception in ASGI application" in record.getMessage()
        and record.exc_info is not None
        and isinstance(record.exc_info[1], error)
        for record in caplog.records
    )


#: The longest a blocked store call waits for its release. A test releases it in a ``finally``;
#: this bound only keeps a regression (a ``stop()`` that joins the stalled thread, so the
#: loop cannot even time out) a failing test instead of a hung one.
_MAX_BLOCK = 3.0


class _BlockingStore(FakeStore):
    """A ``FakeStore`` whose ``list_by_status`` can be made to block, like a stalled database.

    ``entered`` is set when a call starts blocking. The block is a ``threading.Event`` wait
    on the hub's executor thread, so releasing it ends the thread; no test leaves one behind.
    """

    def __init__(self, *, blocked: bool = False) -> None:
        super().__init__()
        self.entered = threading.Event()
        self._open = threading.Event()
        if not blocked:
            self._open.set()

    def block(self) -> None:
        self._open.clear()

    def release(self) -> None:
        self._open.set()

    def list_by_status(
        self, status: JobStatus, *, project_root: Optional[str] = None
    ) -> list[FakeJob]:
        if not self._open.is_set():
            self.entered.set()
            self._open.wait(_MAX_BLOCK)
        return super().list_by_status(status, project_root=project_root)


class _LoopProbe:
    """A task that sleeps 50 ms in a loop and records the largest gap between its wake-ups."""

    def __init__(self) -> None:
        self.max_gap = 0.0
        self._task: Optional[asyncio.Task[None]] = None

    async def _run(self) -> None:
        last = time.monotonic()
        while True:
            await asyncio.sleep(0.05)
            now = time.monotonic()
            self.max_gap = max(self.max_gap, now - last)
            last = now

    async def __aenter__(self) -> "_LoopProbe":
        self._task = asyncio.create_task(self._run())
        await asyncio.sleep(0.12)  # let it tick a few times
        return self

    async def __aexit__(self, *_exc: object) -> None:
        assert self._task is not None
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task


# --------------------------------------------------------------------------- #
# 2.1: the end of a connection releases its subscription
# --------------------------------------------------------------------------- #


async def test_closing_each_tab_releases_it_and_the_last_close_stops_the_poller() -> None:
    async with _serving() as served:
        first, second = await connect(served.url), await connect(served.url)
        for client in (first, second):
            assert (await _frame(client))["type"] == "snapshot"

        await first.close()
        await _until(lambda: served.hub.subscriber_count == 1)
        assert served.hub.is_polling  # the other tab is still subscribed

        await second.close()
        await _until(lambda: (served.hub.subscriber_count, served.hub.is_polling) == (0, False))
        reads = _store_reads(served.store)
        await asyncio.sleep(POLL * 5)
        assert _store_reads(served.store) == reads  # although no job changed


async def test_closing_one_of_two_tabs_keeps_the_other_live() -> None:
    store = FakeStore()
    job_id = _running_job(store, event_dir=GRILLNING, progress=0.2)
    async with _serving(store) as served:
        async with connect(served.url) as staying:
            leaving = await connect(served.url)
            for client in (leaving, staying):
                assert (await _frame(client))["type"] == "snapshot"

            await leaving.close()
            await _until(lambda: served.hub.subscriber_count == 1)

            store.jobs[job_id].progress = 0.6
            delta = await _frame(staying)
            assert delta["type"] == "delta"
            assert [(job["event_dir"], job["progress"]) for job in delta["jobs"]] == [
                (GRILLNING, 0.6)
            ]


async def test_the_first_client_after_the_last_close_gets_a_fresh_snapshot() -> None:
    async with _serving() as served:
        async with connect(served.url) as client:
            assert (await _frame(client))["jobs"] == []
        await _until(lambda: (served.hub.subscriber_count, served.hub.is_polling) == (0, False))

        job_id = uuid.uuid4()
        served.store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.QUEUED, event_dir=BLANDAT)
        seed_reads = served.store.list_finished_since_calls
        async with connect(served.url) as client:
            snapshot = await _frame(client)

        assert snapshot["type"] == "snapshot"
        assert [job["id"] for job in snapshot["jobs"]] == [str(job_id)]
        # Read at this connect, by the poller it started: nothing polled while nobody was.
        assert served.store.list_finished_since_calls > seed_reads


async def test_a_clients_messages_are_ignored() -> None:
    store = FakeStore()
    job_id = _running_job(store, progress=0.1)
    async with _serving(store) as served:
        async with connect(served.url) as client:
            await _frame(client)  # the snapshot
            await client.send("hello")
            await client.send(b"\x00\x01")
            await asyncio.sleep(POLL * 3)
            assert served.hub.subscriber_count == 1

            store.jobs[job_id].progress = 0.7
            delta = await _frame(client)
            assert [(job["id"], job["progress"]) for job in delta["jobs"]] == [(str(job_id), 0.7)]


def test_a_testclient_session_exit_leaves_the_hub_empty_and_idle() -> None:
    """``TestClient`` cancels the handler right after it delivers the disconnect.

    Wherever in the handler's cleanup that cancel lands, the subscription is already
    released: the handler unsubscribes before its first suspension (design, "Teardown
    order"), and the push task releases it too. A handler with neither, waiting for its
    push task before unsubscribing, failed this within 200 cycles.
    """
    hub = JobsHub(FakeStore(), project_root=PROJ, poll_interval=POLL)
    with TestClient(_app(hub)) as client:
        for cycle in range(200):
            with client.websocket_connect(WS_PATH) as websocket:
                assert json.loads(websocket.receive_text())["type"] == "snapshot"
            assert (hub.subscriber_count, hub.is_polling) == (0, False), f"cycle {cycle}"


# --------------------------------------------------------------------------- #
# 2.2: the closes the handler sends
# --------------------------------------------------------------------------- #


async def test_a_hub_that_lets_go_closes_with_1013() -> None:
    async with _serving() as served:
        async with connect(served.url) as client:
            await _frame(client)  # the snapshot
            await served.hub.stop()
            assert await _close_code(client) == 1013
            assert served.hub.subscriber_count == 0


async def test_a_slow_consumer_is_closed_with_1013_and_reconnects_to_a_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hub drops a subscriber whose one-slot queue overflows, and its client is told.

    An unread client cannot fill the queue over a real server, because the push task
    drains it into the transport. So the push task is held inside its second send (the
    first delta) until the hub has dropped the subscriber.
    """
    store = FakeStore()
    job_id = _running_job(store)
    release = asyncio.Event()
    send_text = WebSocket.send_text
    sends = 0

    async def held_send_text(self: WebSocket, data: str) -> None:
        nonlocal sends
        sends += 1
        if sends == 2:
            await release.wait()
        await send_text(self, data)

    monkeypatch.setattr(WebSocket, "send_text", held_send_text)
    async with _serving(store, queue_maxsize=1) as served:
        client = await connect(served.url)
        assert (await _frame(client))["type"] == "snapshot"
        step = 0
        async with asyncio.timeout(1.0):
            while served.hub.subscriber_count:  # dropped by the hub's broadcast
                step += 1
                store.jobs[job_id].progress = step / 100
                await asyncio.sleep(POLL * 1.5)

        release.set()
        assert await _close_code(client) == 1013  # after the held delta, which may get out

        monkeypatch.setattr(WebSocket, "send_text", send_text)
        async with connect(served.url) as again:
            assert (await _frame(again))["type"] == "snapshot"


async def test_a_push_error_closes_with_1011_and_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    store = FakeStore()
    job_id = _running_job(store)
    send_text = WebSocket.send_text
    sends = 0

    async def failing_send_text(self: WebSocket, data: str) -> None:
        nonlocal sends
        sends += 1
        if sends == 2:
            raise ValueError("an unexpected push error")
        await send_text(self, data)

    monkeypatch.setattr(WebSocket, "send_text", failing_send_text)
    caplog.set_level(logging.ERROR, logger="uvicorn.error")
    async with _serving(store) as served:
        client = await connect(served.url)
        await _frame(client)  # the snapshot
        store.jobs[job_id].progress = 0.5  # its delta's send fails

        assert await _close_code(client) == 1011
        await _until(lambda: served.hub.subscriber_count == 0)
        await _until(lambda: _logged_asgi_error(caplog, ValueError))


async def test_the_push_side_releases_the_subscription_on_its_own(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed send whose close the server refuses leaves no disconnect to read.

    That is uvicorn once its keepalive has failed a connection with frames backed up:
    it has sent its own close, so the next send and the handler's close both raise, and
    the disconnect waits until the write buffer drains (design, Risks). The push task's
    own release then frees the subscription and stops the poller.
    """
    store = FakeStore()
    job_id = _running_job(store)
    send_text = WebSocket.send_text
    sends = 0
    after_close = "Unexpected ASGI message '{}', after sending 'websocket.close'."

    async def refused_send_text(self: WebSocket, data: str) -> None:
        nonlocal sends
        sends += 1
        if sends == 2:
            raise RuntimeError(after_close.format("websocket.send"))
        await send_text(self, data)

    async def refused_close(
        self: WebSocket, code: int = 1000, reason: Optional[str] = None
    ) -> None:
        raise RuntimeError(after_close.format("websocket.close"))

    monkeypatch.setattr(WebSocket, "send_text", refused_send_text)
    monkeypatch.setattr(WebSocket, "close", refused_close)
    caplog.set_level(logging.ERROR, logger="uvicorn.error")
    async with _serving(store) as served:
        async with connect(served.url) as client:
            await _frame(client)  # the snapshot
            store.jobs[job_id].progress = 0.5  # its delta's send fails
            await _until(lambda: (served.hub.subscriber_count, served.hub.is_polling) == (0, False))
        # The client's close ends the receive loop, which re-raises the push error.
        await _until(lambda: _logged_asgi_error(caplog, RuntimeError))


# --------------------------------------------------------------------------- #
# 2.3: the endings uvicorn reports
# --------------------------------------------------------------------------- #


async def test_a_silent_peer_is_released_by_the_keepalive() -> None:
    """A peer that completes the handshake, then neither reads nor answers a ping.

    The keepalive is shortened to a 0.2 s ping and a 0.2 s answer here; ``serve`` keeps
    uvicorn's 20 s and 20 s, which ``test_cli_serve.py`` pins.
    """
    async with _serving(ws_ping_interval=0.2, ws_ping_timeout=0.2) as served:
        reader, writer = await asyncio.open_connection("127.0.0.1", served.port)
        try:
            writer.write(_upgrade_request(served.port))
            head = await reader.readuntil(b"\r\n\r\n")  # the last read
            assert head.startswith(b"HTTP/1.1 101")
            await _until(lambda: served.hub.subscriber_count == 1)

            await _until(
                lambda: (served.hub.subscriber_count, served.hub.is_polling) == (0, False),
                timeout=2.0,
            )
        finally:
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()


async def test_a_server_shutdown_closes_every_client_with_1012_and_completes() -> None:
    async with _serving() as served:
        clients = [await connect(served.url) for _ in range(3)]
        for client in clients:
            await _frame(client)  # the snapshot
        served.server.should_exit = True  # what uvicorn's SIGINT and SIGTERM handlers set

        assert [await _close_code(client) for client in clients] == [1012, 1012, 1012]
        await asyncio.wait_for(asyncio.shield(served.task), 3.0)
        assert (served.hub.subscriber_count, served.hub.is_polling) == (0, False)


# --------------------------------------------------------------------------- #
# jobshub-stop-and-db-timeouts: stop() never waits on the database
# --------------------------------------------------------------------------- #


async def _wait_entered(store: _BlockingStore) -> None:
    """Return once a store call is blocked in ``store`` (the call runs on another thread)."""
    await _until(store.entered.is_set, timeout=2.0)


def _blocking_hub(store: _BlockingStore) -> JobsHub:
    return JobsHub(store, project_root=PROJ, poll_interval=POLL)


async def test_a_stalled_poll_does_not_freeze_the_stop_or_the_loop() -> None:
    store = _BlockingStore()
    hub = _blocking_hub(store)
    try:
        await hub.subscribe()
        store.block()
        await _wait_entered(store)  # the poller's tick is now inside the stalled read

        async with _LoopProbe() as probe:
            started = time.monotonic()
            await asyncio.wait_for(hub.stop(), 1.0)
            elapsed = time.monotonic() - started
            await asyncio.sleep(0.2)
        assert elapsed < 1.0
        assert probe.max_gap < 0.5  # a joined executor thread would freeze the loop for the block
        assert (hub.subscriber_count, hub.is_polling) == (0, False)
    finally:
        store.release()


async def test_a_stalled_first_subscribe_does_not_hold_the_stop() -> None:
    store = _BlockingStore(blocked=True)
    hub = _blocking_hub(store)
    try:
        subscribing = asyncio.create_task(hub.subscribe())
        await _wait_entered(store)

        async with _LoopProbe() as probe:
            await asyncio.wait_for(hub.stop(), 1.0)
            queue = await asyncio.wait_for(subscribing, 1.0)
        assert probe.max_gap < 0.5
        assert queue.get_nowait() is _CLOSE
        assert queue.empty()
        assert (hub.subscriber_count, hub.is_polling) == (0, False)
    finally:
        store.release()


async def test_a_subscribe_after_the_stop_is_refused_without_a_store_call() -> None:
    store = _BlockingStore()
    hub = _blocking_hub(store)
    await hub.stop()
    await hub.stop()  # a second stop is harmless

    queue = await asyncio.wait_for(hub.subscribe(), 1.0)

    assert queue.get_nowait() is _CLOSE
    assert queue.empty()
    assert _store_reads(store) == (0, 0, 0)
    assert (hub.subscriber_count, hub.is_polling) == (0, False)


async def test_a_subscriber_cancelled_mid_seed_leaves_the_hub_as_it_was() -> None:
    store = _BlockingStore(blocked=True)
    hub = _blocking_hub(store)
    try:
        subscribing = asyncio.create_task(hub.subscribe())
        await _wait_entered(store)
        subscribing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await subscribing
        assert (hub.subscriber_count, hub.is_polling) == (0, False)

        store.release()
        queue = await asyncio.wait_for(hub.subscribe(), 1.0)
        assert json.loads(queue.get_nowait())["type"] == "snapshot"
        assert (hub.subscriber_count, hub.is_polling) == (1, True)
    finally:
        store.release()
        await hub.stop()


# --------------------------------------------------------------------------- #
# jobshub-stop-and-db-timeouts: the handler watches the connection during the seed
# --------------------------------------------------------------------------- #


async def test_a_client_that_closes_during_a_stalled_first_snapshot_is_released_at_once() -> None:
    store = _BlockingStore(blocked=True)
    try:
        async with _serving(store) as served:
            client = await connect(served.url)
            await _wait_entered(store)

            await asyncio.wait_for(client.close(), 2.0)

            # The database has not answered, yet the lock is free and nothing is registered.
            await _until(lambda: not served.hub._lock.locked(), timeout=1.0)
            assert (served.hub.subscriber_count, served.hub.is_polling) == (0, False)

            store.release()
            async with connect(served.url) as later:
                assert (await _frame(later))["type"] == "snapshot"
    finally:
        store.release()


async def test_a_server_shutdown_during_a_stalled_first_snapshot_completes_without_it() -> None:
    store = _BlockingStore(blocked=True)
    try:
        async with _serving(store) as served:
            client = await connect(served.url)
            await _wait_entered(store)

            served.server.should_exit = True

            assert await _close_code(client) == 1012
            await asyncio.wait_for(asyncio.shield(served.task), 2.0)  # the lifespan's stop() ran
            refused = await served.hub.subscribe()
            assert refused.get_nowait() is _CLOSE
    finally:
        store.release()


async def test_a_message_sent_during_a_stalled_first_snapshot_is_dropped() -> None:
    store = _BlockingStore(blocked=True)
    try:
        async with _serving(store) as served:
            async with connect(served.url) as client:
                await _wait_entered(store)
                await client.send("anyone there?")
                await asyncio.sleep(0.2)

                store.release()

                frame = await _frame(client)
                assert frame["type"] == "snapshot"
                assert served.hub.subscriber_count == 1
    finally:
        store.release()


# --------------------------------------------------------------------------- #
# api-ws-heartbeat: an idle connection is sent a heartbeat
# --------------------------------------------------------------------------- #

#: The patched heartbeat interval: a heartbeat every tenth of a second.
BEAT = 0.1
HEARTBEAT_FRAME = {"type": "heartbeat", "jobs": []}


@pytest.fixture
def quick_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ws_module, "_HEARTBEAT_INTERVAL_S", BEAT)


@pytest.mark.usefixtures("quick_heartbeat")
async def test_an_idle_connection_is_sent_heartbeats_and_stays_open() -> None:
    async with _serving() as served:
        async with connect(served.url) as client:
            assert (await _frame(client))["type"] == "snapshot"  # never a heartbeat first
            assert await _frame(client) == HEARTBEAT_FRAME
            assert await _frame(client) == HEARTBEAT_FRAME
            assert served.hub.subscriber_count == 1


@pytest.mark.usefixtures("quick_heartbeat")
async def test_heartbeats_cost_the_hub_nothing() -> None:
    """A heartbeat is the connection's own: no store read, nothing on the subscriber's queue."""
    async with _serving(poll_interval=60.0) as served:
        async with connect(served.url) as client:
            await _frame(client)  # the snapshot
            reads = _store_reads(served.store)
            for _ in range(4):
                assert await _frame(client) == HEARTBEAT_FRAME
            assert _store_reads(served.store) == reads
            assert all(
                queue.empty() for queue in served.hub._subscribers
            )  # pylint: disable=protected-access


async def test_a_busy_connection_is_sent_no_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Frames more often than the interval leave the heartbeat timer forever restarting."""
    monkeypatch.setattr(ws_module, "_HEARTBEAT_INTERVAL_S", 2.0)
    store = FakeStore()
    job_id = _running_job(store, event_dir=GRILLNING, progress=0.0)
    async with _serving(store) as served:
        async with connect(served.url) as client:
            await _frame(client)  # the snapshot
            types = []
            for step in range(1, 16):
                store.jobs[job_id].progress = step / 100
                types.append((await _frame(client))["type"])
                await asyncio.sleep(0.1)
            assert types == ["delta"] * 15  # about 2.3 s: past one interval, never idle for one


async def test_a_delta_landing_as_a_heartbeat_falls_due_is_delivered_once_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Poll and heartbeat intervals coincide, so the two race again and again."""
    monkeypatch.setattr(ws_module, "_HEARTBEAT_INTERVAL_S", POLL)
    store = FakeStore()
    job_id = _running_job(store, event_dir=GRILLNING, progress=0.0)
    last = 60
    async with _serving(store) as served:
        async with connect(served.url) as client:
            await _frame(client)  # the snapshot
            seen: list[float] = []

            async def advance() -> None:
                for step in range(1, last + 1):
                    store.jobs[job_id].progress = step / 1000
                    await asyncio.sleep(POLL)

            advancing = asyncio.create_task(advance())
            try:
                async with asyncio.timeout(10.0):
                    while not seen or seen[-1] < last / 1000:
                        frame = await _frame(client)
                        if frame["type"] != "heartbeat":
                            seen += [job["progress"] for job in frame["jobs"]]
            finally:
                await advancing
            assert seen == sorted(set(seen))  # strictly increasing: none repeated, none reordered
            assert seen[-1] == last / 1000  # and the last change was not lost


@pytest.mark.usefixtures("quick_heartbeat")
async def test_a_hub_stop_during_a_heartbeat_wait_still_closes_with_1013() -> None:
    async with _serving() as served:
        async with connect(served.url) as client:
            await _frame(client)  # the snapshot
            assert await _frame(client) == HEARTBEAT_FRAME
            await served.hub.stop()
            assert await _close_code(client) == 1013
            assert served.hub.subscriber_count == 0


async def test_the_heartbeat_wait_neither_loses_a_racing_frame_nor_outlasts_a_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ws_module, "_HEARTBEAT_INTERVAL_S", 0.05)
    queue: asyncio.Queue = asyncio.Queue()
    # nothing came
    assert json.loads(str(await asyncio.wait_for(_next_message(queue), 1.0))) == HEARTBEAT_FRAME

    queue.put_nowait("frame")
    # a queued frame wins over a heartbeat
    assert await asyncio.wait_for(_next_message(queue), 1.0) == "frame"

    monkeypatch.setattr(ws_module, "_HEARTBEAT_INTERVAL_S", 30.0)
    waiting = asyncio.create_task(_next_message(queue))
    await asyncio.sleep(0.05)
    queue.put_nowait(_CLOSE)
    assert await asyncio.wait_for(waiting, 1.0) is _CLOSE  # prompt, not after 30 s
