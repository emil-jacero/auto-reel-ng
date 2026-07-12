"""Unit tests for :class:`JobsHub` (tasks 4.1-4.3) against a stubbed, in-memory store.

No database: ``asyncio_mode = "auto"`` (pyproject) makes these plain ``async def``
tests run directly. The end-to-end test against a real store/poller is
``test_api_ws_e2e.py`` (task 4.4, podman PG).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from auto_reel_ng.api.ws import JobsHub
from auto_reel_ng.persistence.models import JobStatus

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


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
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: _NOW)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class FakeStore:
    """A minimal store stand-in exposing only ``list_by_status``/``get`` (hub's surface)."""

    def __init__(self) -> None:
        self.jobs: dict[uuid.UUID, FakeJob] = {}
        self.list_by_status_calls = 0
        self.get_calls = 0

    def list_by_status(self, status: JobStatus) -> list[FakeJob]:
        self.list_by_status_calls += 1
        return [job for job in self.jobs.values() if job.status == status]

    def get(self, job_id: uuid.UUID) -> Optional[FakeJob]:
        self.get_calls += 1
        return self.jobs.get(job_id)


async def _drain(queue: asyncio.Queue, *, timeout: float = 1.0) -> dict:
    message = await asyncio.wait_for(queue.get(), timeout=timeout)
    return json.loads(message)


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


# --------------------------------------------------------------------------- #
# 4.2: snapshot + delta
# --------------------------------------------------------------------------- #


async def test_snapshot_on_connect_contains_active_jobs() -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, progress=0.1)
    hub = JobsHub(store, poll_interval=0.05)

    queue = await hub.subscribe()
    try:
        snapshot = await _drain(queue)
        assert snapshot["type"] == "snapshot"
        assert [j["id"] for j in snapshot["jobs"]] == [str(job_id)]
        assert snapshot["jobs"][0]["status"] == "running"
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


async def test_terminal_transition_between_ticks_is_pushed() -> None:
    store = FakeStore()
    job_id = uuid.uuid4()
    store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.RUNNING, progress=0.5)
    hub = JobsHub(store, poll_interval=0.02)

    queue = await hub.subscribe()
    try:
        await _drain(queue)  # the initial snapshot
        # The job finishes between ticks: it leaves the active (queued/running) set.
        store.jobs[job_id] = FakeJob(id=job_id, status=JobStatus.DONE, progress=1.0)
        delta = await _drain(queue, timeout=1.0)
        assert delta["type"] == "delta"
        assert delta["jobs"][0]["status"] == "done"
        assert delta["jobs"][0]["progress"] == 1.0
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
