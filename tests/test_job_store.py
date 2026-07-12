"""Tests for the job-store repository: enqueue, claim-next, transition, progress,
queries, and cancel (real Postgres — D-P1/T3)."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy.exc import IntegrityError

from auto_reel_ng.errors import IllegalJobTransitionError
from auto_reel_ng.persistence.engine import session_scope
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Job, JobStatus

pytestmark = pytest.mark.requires_db

PROJECT_ROOT = "/project"

# --------------------------------------------------------------------------- #
# 4.1 enqueue
# --------------------------------------------------------------------------- #


def test_enqueue_defaults(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "2026-01-01 - Party")
    job = job_store.get(job_id)
    assert job is not None
    assert job.project_root == PROJECT_ROOT
    assert job.event_dir == "2026-01-01 - Party"
    assert job.status == JobStatus.QUEUED
    assert job.priority == 0
    assert job.device == "auto"
    assert job.progress == 0.0
    assert job.cancel_requested is False
    assert job.requeue_count == 0
    assert job.created_at is not None
    assert job.started_at is None
    assert job.finished_at is None
    assert job.error is None
    assert job.fingerprint is None
    assert job.output_path is None


def test_enqueue_explicit_device_and_output(job_store: JobStore) -> None:
    job_id = job_store.enqueue(
        PROJECT_ROOT, "event", device="renderD128", output_path="/out/event.mp4"
    )
    job = job_store.get(job_id)
    assert job is not None
    assert job.device == "renderD128"
    assert job.output_path == "/out/event.mp4"


# --------------------------------------------------------------------------- #
# 4.1b idempotent enqueue
# --------------------------------------------------------------------------- #


def test_enqueue_is_idempotent_for_an_active_event(job_store: JobStore) -> None:
    first_id = job_store.enqueue(PROJECT_ROOT, "event")
    second_id = job_store.enqueue(PROJECT_ROOT, "event")
    assert second_id == first_id
    assert len(job_store.list_by_status(JobStatus.QUEUED)) == 1


def test_enqueue_is_idempotent_for_a_running_event(job_store: JobStore) -> None:
    first_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    second_id = job_store.enqueue(PROJECT_ROOT, "event")
    assert second_id == first_id


def test_enqueue_after_terminal_state_creates_a_new_job(job_store: JobStore) -> None:
    first_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.transition(first_id, JobStatus.DONE)
    second_id = job_store.enqueue(PROJECT_ROOT, "event")
    assert second_id != first_id
    assert job_store.get(second_id).status == JobStatus.QUEUED  # type: ignore[union-attr]


def test_enqueue_idempotency_is_scoped_to_project_root(job_store: JobStore) -> None:
    first_id = job_store.enqueue(PROJECT_ROOT, "event")
    second_id = job_store.enqueue("/other-project", "event")
    assert second_id != first_id


def test_database_rejects_a_raw_duplicate_active_job_insert(jobs_session_factory) -> None:
    # Proves the partial unique index itself is the source of truth (job-store
    # spec: "Duplicate active job is rejected by the database") — bypassing
    # JobStore.enqueue's own IntegrityError-catching fallback entirely, so this
    # cannot pass merely because that fallback happens to swallow the conflict.
    with session_scope(jobs_session_factory) as session:
        session.add(Job(project_root=PROJECT_ROOT, event_dir="event"))

    with pytest.raises(IntegrityError):
        with session_scope(jobs_session_factory) as session:
            session.add(Job(project_root=PROJECT_ROOT, event_dir="event"))


def test_database_allows_a_second_row_once_the_first_is_terminal(jobs_session_factory) -> None:
    with session_scope(jobs_session_factory) as session:
        session.add(Job(project_root=PROJECT_ROOT, event_dir="event", status=JobStatus.DONE))

    # A second row for the same identity is fine once the first is terminal.
    with session_scope(jobs_session_factory) as session:
        session.add(Job(project_root=PROJECT_ROOT, event_dir="event"))


def test_active_job_finds_a_queued_or_running_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    assert job_store.active_job(PROJECT_ROOT, "event").id == job_id  # type: ignore[union-attr]
    job_store.claim_next("worker")
    assert job_store.active_job(PROJECT_ROOT, "event").id == job_id  # type: ignore[union-attr]


def test_active_job_is_none_when_absent_or_terminal(job_store: JobStore) -> None:
    assert job_store.active_job(PROJECT_ROOT, "event") is None
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.transition(job_id, JobStatus.DONE)
    assert job_store.active_job(PROJECT_ROOT, "event") is None


# --------------------------------------------------------------------------- #
# 4.2 claim_next
# --------------------------------------------------------------------------- #


def test_claim_next_never_double_claims(job_store: JobStore) -> None:
    ids = {job_store.enqueue(PROJECT_ROOT, f"event-{i}") for i in range(5)}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(job_store.claim_next, f"worker-{i}") for i in range(5)]
        claimed = [f.result() for f in as_completed(futures)]

    claimed_ids = [job.id for job in claimed if job is not None]
    assert len(claimed_ids) == 5
    assert len(set(claimed_ids)) == 5
    assert set(claimed_ids) == ids


def test_claim_next_fifo_within_priority(job_store: JobStore) -> None:
    ids_in_order = [job_store.enqueue(PROJECT_ROOT, f"event-{i}") for i in range(3)]
    claimed_order = [job_store.claim_next("worker").id for _ in range(3)]
    assert claimed_order == ids_in_order


def test_claim_next_device_filter_excludes_ineligible(job_store: JobStore) -> None:
    job_store.enqueue(PROJECT_ROOT, "event-a", device="renderD129")
    assert job_store.claim_next("worker", device_filter="renderD128") is None


def test_claim_next_device_filter_admits_auto(job_store: JobStore) -> None:
    auto_id = job_store.enqueue(PROJECT_ROOT, "event-a", device="auto")
    job = job_store.claim_next("worker", device_filter="renderD128")
    assert job is not None
    assert job.id == auto_id


def test_claim_next_device_filter_admits_exact_match(job_store: JobStore) -> None:
    exact_id = job_store.enqueue(PROJECT_ROOT, "event-a", device="renderD128")
    job = job_store.claim_next("worker", device_filter="renderD128")
    assert job is not None
    assert job.id == exact_id


def test_claim_next_stamps_worker_and_started_at(job_store: JobStore) -> None:
    job_store.enqueue(PROJECT_ROOT, "event")
    job = job_store.claim_next("worker-7")
    assert job is not None
    assert job.status == JobStatus.RUNNING
    assert job.worker_id == "worker-7"
    assert job.started_at is not None


def test_claim_next_returns_none_when_queue_empty(job_store: JobStore) -> None:
    assert job_store.claim_next("worker") is None


# --------------------------------------------------------------------------- #
# 4.3 transition
# --------------------------------------------------------------------------- #


def test_transition_to_done(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    done = job_store.transition(job_id, JobStatus.DONE)
    assert done.status == JobStatus.DONE
    assert done.finished_at is not None
    assert done.error is None


def test_transition_to_failed_records_error(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    failed = job_store.transition(job_id, JobStatus.FAILED, error="ffmpeg exit 1")
    assert failed.status == JobStatus.FAILED
    assert failed.finished_at is not None
    assert failed.error == "ffmpeg exit 1"


def test_transition_rejects_non_running_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")  # still queued

    with pytest.raises(IllegalJobTransitionError):
        job_store.transition(job_id, JobStatus.DONE)

    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.QUEUED
    assert job.finished_at is None


def test_transition_rejects_re_terminating_a_finished_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.transition(job_id, JobStatus.DONE)

    with pytest.raises(IllegalJobTransitionError):
        job_store.transition(job_id, JobStatus.FAILED, error="too late")


# --------------------------------------------------------------------------- #
# 4.4 set_progress
# --------------------------------------------------------------------------- #


def test_set_progress_persists_for_running_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.set_progress(job_id, 0.42)
    job = job_store.get(job_id)
    assert job is not None
    assert job.progress == pytest.approx(0.42)


def test_set_progress_clamps_to_unit_interval(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")

    job_store.set_progress(job_id, 5.0)
    assert job_store.get(job_id).progress == 1.0  # type: ignore[union-attr]

    job_store.set_progress(job_id, -5.0)
    assert job_store.get(job_id).progress == 0.0  # type: ignore[union-attr]


def test_set_progress_ignored_for_queued_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.set_progress(job_id, 0.9)
    job = job_store.get(job_id)
    assert job is not None
    assert job.progress == 0.0


@pytest.mark.parametrize("terminal", [JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED])
def test_set_progress_ignored_for_terminal_job(job_store: JobStore, terminal: JobStatus) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.transition(job_id, terminal)
    job_store.set_progress(job_id, 0.5)
    job = job_store.get(job_id)
    assert job is not None
    assert job.progress == 0.0


# --------------------------------------------------------------------------- #
# 4.5 get / list_by_status
# --------------------------------------------------------------------------- #


def test_get_returns_none_for_absent_job(job_store: JobStore) -> None:
    assert job_store.get(uuid.uuid4()) is None


def test_list_by_status_orders_by_created_at(job_store: JobStore) -> None:
    ids_in_order = [job_store.enqueue(PROJECT_ROOT, f"event-{i}") for i in range(3)]
    listed = job_store.list_by_status(JobStatus.QUEUED)
    assert [job.id for job in listed] == ids_in_order


def test_list_by_status_filters_other_statuses_out(job_store: JobStore) -> None:
    first = job_store.enqueue(PROJECT_ROOT, "a")
    second = job_store.enqueue(PROJECT_ROOT, "b")
    job_store.claim_next("worker")  # claims `first` (FIFO)

    queued = job_store.list_by_status(JobStatus.QUEUED)
    running = job_store.list_by_status(JobStatus.RUNNING)

    assert [job.id for job in queued] == [second]
    assert [job.id for job in running] == [first]


# --------------------------------------------------------------------------- #
# 4.6 cancel_queued
# --------------------------------------------------------------------------- #


def test_cancel_queued_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    canceled = job_store.cancel_queued(job_id)
    assert canceled is not None
    assert canceled.status == JobStatus.CANCELED
    assert canceled.finished_at is not None


def test_canceled_job_is_never_claimed(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.cancel_queued(job_id)
    assert job_store.claim_next("worker") is None


def test_cancel_queued_ignored_for_running_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")

    result = job_store.cancel_queued(job_id)

    assert result is None
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.RUNNING


# --------------------------------------------------------------------------- #
# 4.7 request_cancel
# --------------------------------------------------------------------------- #


def test_request_cancel_flags_a_running_job_without_transitioning(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")

    result = job_store.request_cancel(job_id)

    assert result is not None
    assert result.cancel_requested is True
    assert result.status == JobStatus.RUNNING
    job = job_store.get(job_id)
    assert job is not None
    assert job.cancel_requested is True
    assert job.status == JobStatus.RUNNING


def test_request_cancel_cancels_a_queued_job_directly(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")

    result = job_store.request_cancel(job_id)

    assert result is not None
    assert result.status == JobStatus.CANCELED
    assert job_store.claim_next("worker") is None


@pytest.mark.parametrize("terminal", [JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELED])
def test_request_cancel_is_a_noop_for_a_terminal_job(
    job_store: JobStore, terminal: JobStatus
) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.transition(job_id, terminal)

    result = job_store.request_cancel(job_id)

    assert result is None
    job = job_store.get(job_id)
    assert job is not None
    assert job.status == terminal
    assert job.cancel_requested is False


def test_request_cancel_is_a_noop_for_a_missing_job(job_store: JobStore) -> None:
    assert job_store.request_cancel(uuid.uuid4()) is None


# --------------------------------------------------------------------------- #
# 4.8 requeue
# --------------------------------------------------------------------------- #


def test_requeue_resets_a_running_job_for_a_fresh_claim(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.set_progress(job_id, 0.75)

    requeued = job_store.requeue(job_id)

    assert requeued.status == JobStatus.QUEUED
    assert requeued.worker_id is None
    assert requeued.started_at is None
    assert requeued.progress == 0.0
    assert requeued.requeue_count == 1

    claimed = job_store.claim_next("worker-2")
    assert claimed is not None
    assert claimed.id == job_id


def test_requeue_keeps_cancel_requested(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.request_cancel(job_id)

    requeued = job_store.requeue(job_id)

    assert requeued.cancel_requested is True


def test_requeue_increments_counter_across_repeated_crashes(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker-1")
    job_store.requeue(job_id)
    job_store.claim_next("worker-2")
    requeued = job_store.requeue(job_id)

    assert requeued.requeue_count == 2


def test_requeue_rejects_a_queued_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")  # still queued

    with pytest.raises(IllegalJobTransitionError):
        job_store.requeue(job_id)

    job = job_store.get(job_id)
    assert job is not None
    assert job.status == JobStatus.QUEUED


def test_requeue_rejects_a_terminal_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, "event")
    job_store.claim_next("worker")
    job_store.transition(job_id, JobStatus.DONE)

    with pytest.raises(IllegalJobTransitionError):
        job_store.requeue(job_id)
