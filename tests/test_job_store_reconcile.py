"""Tests for the orphaned-``running`` reconcile query (D-P5): detection only, the
requeue *policy* is 7b's."""

from __future__ import annotations

import datetime as dt

import pytest

from auto_reel_ng.persistence.job_store import JobStore

pytestmark = pytest.mark.requires_db


def test_orphaned_running_job_is_surfaced(job_store: JobStore) -> None:
    job_id = job_store.enqueue("event")
    job_store.claim_next("dead-worker")

    orphaned = job_store.find_orphaned_running(live_workers=["alive-worker"])

    assert [job.id for job in orphaned] == [job_id]


def test_active_running_job_is_not_surfaced(job_store: JobStore) -> None:
    job_store.enqueue("event")
    job_store.claim_next("alive-worker")

    orphaned = job_store.find_orphaned_running(live_workers=["alive-worker"])

    assert orphaned == []


def test_cutoff_surfaces_a_stale_running_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue("event")
    job_store.claim_next("worker")

    future_cutoff = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
    orphaned = job_store.find_orphaned_running(cutoff=future_cutoff)

    assert [job.id for job in orphaned] == [job_id]


def test_cutoff_does_not_surface_a_recent_running_job(job_store: JobStore) -> None:
    job_store.enqueue("event")
    job_store.claim_next("worker")

    past_cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    orphaned = job_store.find_orphaned_running(cutoff=past_cutoff)

    assert orphaned == []


def test_only_running_jobs_are_considered(job_store: JobStore) -> None:
    job_store.enqueue("event")  # stays queued, never claimed

    orphaned = job_store.find_orphaned_running(live_workers=[])

    assert orphaned == []


def test_requires_live_workers_or_cutoff(job_store: JobStore) -> None:
    with pytest.raises(ValueError):
        job_store.find_orphaned_running()
