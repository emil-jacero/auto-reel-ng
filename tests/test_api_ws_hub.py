"""Unit tests for :class:`JobsHub` (tasks 4.1-4.3) against a stubbed, in-memory store.

No database: ``asyncio_mode = "auto"`` (pyproject) makes these plain ``async def``
tests run directly. The end-to-end test against a real store/poller is
``test_api_ws_e2e.py`` (task 4.4, podman PG).
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from pydantic import ValidationError

from auto_reel_ng.api.schemas import WsMessage, WsMessageType
from auto_reel_ng.api.ws import JobsHub
from auto_reel_ng.persistence.job_store import FinishedJobs
from auto_reel_ng.persistence.models import JobStatus

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)

#: Dev-library event ids (``scripts/make_dev_library.py``) the spec scenarios name.
TRASIG = "2024/2024-10-05 - Trasig"
BADUTFLYKT = "2024/2024-08-02 - Badutflykt - Varberg"
BLANDAT = "2024/Blandat"


@dataclass
class FakeJob:
    """A duck-typed stand-in for :class:`~auto_reel_ng.persistence.models.Job`."""

    id: uuid.UUID
    status: JobStatus
    event_dir: str = "2024/event"
    project_root: Optional[str] = "/proj"
    device: str = "auto"
    progress: float = 0.0
    worker_id: Optional[str] = None
    cancel_requested: bool = False
    requeue_count: int = 0
    force: bool = False
    fingerprint: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: _NOW)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class FakeStore:
    """A minimal store stand-in exposing only the hub's surface.

    ``now`` is the fake database clock: the time ``list_finished_since`` reports, and
    the instant it reads from when given none. It stands still unless a test moves it.
    """

    def __init__(self) -> None:
        self.jobs: dict[uuid.UUID, FakeJob] = {}
        self.now = _NOW
        self.list_by_status_calls = 0
        self.get_calls = 0
        self.list_finished_since_calls = 0

    def list_by_status(self, status: JobStatus) -> list[FakeJob]:
        self.list_by_status_calls += 1
        return [job for job in self.jobs.values() if job.status == status]

    def get(self, job_id: uuid.UUID) -> Optional[FakeJob]:
        self.get_calls += 1
        return self.jobs.get(job_id)

    def list_finished_since(self, since: Optional[datetime], *, overlap: timedelta) -> FinishedJobs:
        self.list_finished_since_calls += 1
        start = (since if since is not None else self.now) - overlap
        finished = [
            job
            for job in sorted(self.jobs.values(), key=lambda job: job.finished_at or start)
            if job.finished_at is not None and job.finished_at >= start
        ]
        return FinishedJobs(as_of=self.now, jobs=finished)


async def _drain(queue: asyncio.Queue, *, timeout: float = 1.0) -> dict:
    message = await asyncio.wait_for(queue.get(), timeout=timeout)
    return json.loads(message)


async def _await_ticks(store: FakeStore, count: int, *, timeout: float = 2.0) -> None:
    """Return once the poller has run ``count`` more complete ticks.

    Every tick starts with one finished read and ends with its broadcast, so
    ``count + 1`` further reads mean ``count`` ticks have run to their end.
    """
    target = store.list_finished_since_calls + count + 1
    async with asyncio.timeout(timeout):
        while store.list_finished_since_calls < target:
            await asyncio.sleep(0.005)


# --------------------------------------------------------------------------- #
# The frame shape (jobs-client-contract 3.3)
# --------------------------------------------------------------------------- #


def test_the_frame_is_a_closed_shape() -> None:
    assert WsMessage(type="snapshot", jobs=[]).type is WsMessageType.SNAPSHOT
    with pytest.raises(ValidationError):
        WsMessage(type="other", jobs=[])
    with pytest.raises(ValidationError):
        WsMessage(type="delta")  # type: ignore[call-arg]


# --------------------------------------------------------------------------- #
# 4.1: poller lifecycle
# --------------------------------------------------------------------------- #


async def test_no_subscribers_means_no_store_queries() -> None:
    store = FakeStore()
    hub = JobsHub(store, poll_interval=0.02)
    assert hub.is_polling is False
    await asyncio.sleep(0.1)
    assert store.list_by_status_calls == 0
    assert store.get_calls == 0
    assert store.list_finished_since_calls == 0


async def test_poller_starts_on_first_subscribe_stops_on_last_unsubscribe() -> None:
    store = FakeStore()
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    assert hub.is_polling is True
    assert store.list_by_status_calls >= 2  # QUEUED + RUNNING, the initial snapshot fetch

    await hub.unsubscribe(queue)
    assert hub.is_polling is False
    calls_after_stop = store.list_by_status_calls
    await asyncio.sleep(0.1)
    assert store.list_by_status_calls == calls_after_stop  # no further polling


class _Unreachable(Exception):
    """Stands in for a database error during the first subscriber's reads."""


async def _assert_a_new_subscriber_gets_deltas(hub: JobsHub, store: FakeStore) -> None:
    """The next subscriber is the first one again: it starts the poller and sees changes."""
    (job_id,) = store.jobs
    queue = await hub.subscribe()
    try:
        snapshot = await _drain(queue)
        assert [job["id"] for job in snapshot["jobs"]] == [str(job_id)]
        assert (hub.subscriber_count, hub.is_polling) == (1, True)
        store.jobs[job_id].progress = 0.5
        delta = await _drain(queue)
        assert (delta["type"], delta["jobs"][0]["progress"]) == ("delta", 0.5)
    finally:
        await hub.unsubscribe(queue)


@pytest.mark.parametrize("failing_read", ["list_finished_since", "list_by_status"])
async def test_a_failed_first_subscribe_leaves_the_hub_recoverable(failing_read: str) -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, progress=0.1)
    read = getattr(store, failing_read)
    failures = [_Unreachable("database unreachable")]

    def flaky_read(*args: object, **kwargs: object) -> object:
        if failures:
            raise failures.pop()
        return read(*args, **kwargs)

    setattr(store, failing_read, flaky_read)
    hub = JobsHub(store, poll_interval=0.02)

    with pytest.raises(_Unreachable):
        await hub.subscribe()

    # Nothing registered and no half-seeded state: the failed start left no trace.
    assert (hub.subscriber_count, hub.is_polling) == (0, False)
    assert (hub._finished_as_of, hub._terminal_sent) == (None, {})  # pylint: disable=W0212
    await _assert_a_new_subscriber_gets_deltas(hub, store)


async def test_a_cancelled_first_subscribe_leaves_the_hub_recoverable() -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, progress=0.1)
    read = store.list_finished_since
    release = threading.Event()

    def held_read(*args: object, **kwargs: object) -> object:
        release.wait(timeout=5)  # the seed read hangs until the test lets it go
        return read(*args, **kwargs)

    store.list_finished_since = held_read  # type: ignore[method-assign]
    hub = JobsHub(store, poll_interval=0.02)

    first = asyncio.create_task(hub.subscribe())
    await asyncio.sleep(0.05)  # the seed read is now in flight on the hub's executor
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert (hub.subscriber_count, hub.is_polling) == (0, False)

    store.list_finished_since = read  # type: ignore[method-assign]
    release.set()
    await _assert_a_new_subscriber_gets_deltas(hub, store)


# --------------------------------------------------------------------------- #
# 4.2: snapshot + delta
# --------------------------------------------------------------------------- #


async def test_snapshot_on_connect_contains_active_jobs() -> None:
    store = FakeStore()
    running_id, queued_id = uuid.uuid4(), uuid.uuid4()
    store.jobs[running_id] = FakeJob(
        id=running_id, status=JobStatus.RUNNING, event_dir=BADUTFLYKT, progress=0.1
    )
    store.jobs[queued_id] = FakeJob(id=queued_id, status=JobStatus.QUEUED, event_dir=BLANDAT)
    hub = JobsHub(store, poll_interval=0.05)

    queue = await hub.subscribe()
    try:
        snapshot = await _drain(queue)
        assert snapshot["type"] == "snapshot"
        assert {job["id"]: (job["status"], job["progress"]) for job in snapshot["jobs"]} == {
            str(running_id): ("running", 0.1),
            str(queued_id): ("queued", 0.0),
        }
    finally:
        await hub.unsubscribe(queue)


async def test_progress_delta_is_pushed() -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, progress=0.1)
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    try:
        await _drain(queue)  # the initial snapshot
        store.jobs[job_id].progress = 0.5
        delta = await _drain(queue, timeout=1.0)
        assert delta["type"] == "delta"
        assert delta["jobs"][0]["progress"] == 0.5
    finally:
        await hub.unsubscribe(queue)


@pytest.mark.parametrize("stamped", [True, False], ids=["finished_at", "no-finished_at"])
async def test_terminal_transition_between_ticks_is_pushed(stamped: bool) -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, progress=0.5)
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    try:
        await _drain(queue)  # the initial snapshot
        # The job finishes between ticks: it leaves the active (queued/running) set.
        # A real terminal transition stamps finished_at; a row without one is seen
        # by the vanished path only, and must still go out exactly once.
        store.jobs[job_id] = FakeJob(
            id=job_id,
            status=JobStatus.DONE,
            progress=1.0,
            finished_at=store.now if stamped else None,
        )
        delta = await _drain(queue, timeout=1.0)
        assert delta["type"] == "delta"
        assert [job["id"] for job in delta["jobs"]] == [str(job_id)]
        assert delta["jobs"][0]["status"] == "done"
        assert delta["jobs"][0]["progress"] == 1.0
        # Both the vanished path and every later finished read see the job (the
        # fake clock stands still, so each window still holds it): it goes out once.
        await _await_ticks(store, 5)
        assert queue.empty()
    finally:
        await hub.unsubscribe(queue)


# --------------------------------------------------------------------------- #
# Cancel requests and jobs finished between polls (jobs-client-contract 3.3)
# --------------------------------------------------------------------------- #


async def test_a_cancel_request_is_pushed() -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(
        id=job_id, status=JobStatus.RUNNING, event_dir=BADUTFLYKT, progress=0.4
    )
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    try:
        await _drain(queue)  # the initial snapshot
        store.jobs[job_id].cancel_requested = True  # neither status nor progress moves
        delta = await _drain(queue)
        assert delta["type"] == "delta"
        assert [
            (job["id"], job["status"], job["progress"], job["cancel_requested"])
            for job in delta["jobs"]
        ] == [(str(job_id), "running", 0.4, True)]
        await _await_ticks(store, 3)
        assert queue.empty()  # one delta for the change, not one per tick
    finally:
        await hub.unsubscribe(queue)


async def test_a_job_that_lived_and_ended_between_two_polls_is_pushed_once() -> None:
    store = FakeStore()
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    try:
        snapshot = await _drain(queue)
        assert snapshot["jobs"] == []
        # Enqueued, claimed and failed at probe between two polls: no active read
        # ever saw it queued or running.
        job_id = uuid.uuid4()
        store.jobs[job_id] = FakeJob(
            id=job_id,
            status=JobStatus.FAILED,
            event_dir=TRASIG,
            error="ffprobe: invalid data",
            finished_at=store.now,
        )
        delta = await _drain(queue)
        assert delta["type"] == "delta"
        assert [(job["id"], job["status"], job["error"]) for job in delta["jobs"]] == [
            (str(job_id), "failed", "ffprobe: invalid data")
        ]
        # Every later window still includes its finished_at: only the hub's memory
        # of what it sent keeps it from going out again.
        await _await_ticks(store, 5)
        assert queue.empty()
    finally:
        await hub.unsubscribe(queue)


async def test_a_job_missed_by_one_active_read_still_gets_its_terminal_row() -> None:
    """A still-active row off the vanished path is sent, but never remembered as final.

    The active snapshot is two reads (queued, then running), so a requeue landing
    between them hides a job from one tick: it "vanishes" while still active. That
    row is current state and goes out, but it must not count as the job's terminal
    row, or the real one would later be suppressed.
    """
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, progress=0.5)
    hidden: set[uuid.UUID] = set()
    list_by_status = store.list_by_status
    store.list_by_status = lambda status: [  # type: ignore[method-assign]
        job for job in list_by_status(status) if job.id not in hidden
    ]
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    try:
        await _drain(queue)  # the initial snapshot
        hidden.add(job_id)  # one tick's active reads miss the requeued job
        store.jobs[job_id].status = JobStatus.QUEUED
        store.jobs[job_id].progress = 0.0
        missed = await _drain(queue)
        assert [(job["id"], job["status"]) for job in missed["jobs"]] == [(str(job_id), "queued")]

        hidden.clear()
        store.jobs[job_id] = FakeJob(
            id=job_id, status=JobStatus.FAILED, error="ffprobe: invalid data", finished_at=store.now
        )
        final = await _drain(queue)
        assert [(job["id"], job["status"]) for job in final["jobs"]] == [(str(job_id), "failed")]
    finally:
        await hub.unsubscribe(queue)


async def test_a_job_finished_before_the_first_subscribe_is_never_sent() -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(
        id=job_id,
        status=JobStatus.DONE,
        progress=1.0,
        finished_at=store.now - timedelta(seconds=10),  # inside the overlap
    )
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    try:
        snapshot = await _drain(queue)
        assert snapshot["jobs"] == []
        await _await_ticks(store, 5)
        assert queue.empty()
    finally:
        await hub.unsubscribe(queue)


async def test_the_sent_memory_forgets_jobs_older_than_the_window() -> None:
    store = FakeStore()
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    try:
        await _drain(queue)  # the initial snapshot
        job_id = uuid.uuid4()
        store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.DONE, finished_at=store.now)
        await _drain(queue)  # its one terminal delta
        store.now += timedelta(seconds=60)  # the clock moves the window past the job

        await _await_ticks(store, 2)

        assert queue.empty()
        assert hub._terminal_sent == {}  # pylint: disable=protected-access
    finally:
        await hub.unsubscribe(queue)


# --------------------------------------------------------------------------- #
# 4.3: slow-consumer policy
# --------------------------------------------------------------------------- #


async def test_slow_consumer_is_dropped_and_can_reconnect() -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, progress=0.0)
    hub = JobsHub(store, poll_interval=0.01, queue_maxsize=1)

    queue = await hub.subscribe()
    await _drain(queue)  # the initial snapshot, freeing the one-slot queue

    # Never drain again: force the queue to fill and overflow across several ticks.
    for step in range(1, 6):
        store.jobs[job_id].progress = step / 10
        await asyncio.sleep(0.03)

    assert hub.subscriber_count == 0  # dropped rather than back-pressuring the hub

    # Recovery path: reconnect gets a fresh snapshot.
    new_queue = await hub.subscribe()
    try:
        snapshot = await _drain(new_queue)
        assert snapshot["type"] == "snapshot"
        assert snapshot["jobs"][0]["id"] == str(job_id)
    finally:
        await hub.unsubscribe(new_queue)
