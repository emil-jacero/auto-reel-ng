"""Tests for the job-store repository: enqueue, claim-next, transition, progress,
queries, and cancel (real Postgres — D-P1/T3)."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from typing import Callable, TypeVar

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from auto_reel_ng.errors import IllegalJobTransitionError
from auto_reel_ng.persistence.engine import session_scope
from auto_reel_ng.persistence.job_store import CancelOutcome, JobStore, Submission
from auto_reel_ng.persistence.models import Job, JobStatus

pytestmark = pytest.mark.requires_db

_T = TypeVar("_T")

PROJECT_ROOT = "/project"

#: Dev-library event ids (``scripts/make_dev_library.py``) the spec scenarios name.
GRILLNING = "2024/2024-06-27 - Grillning med grannar"
BLANDAT = "2024/Blandat"
TRASIG = "2024/2024-10-05 - Trasig"
BADUTFLYKT = "2024/2024-08-02 - Badutflykt - Varberg"
MIDSOMMAR = "2023/2023-06-23 - Midsommar - Dalarna"

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
    assert job.force is False
    assert job.output_path is None


def test_enqueue_explicit_device_and_output(job_store: JobStore) -> None:
    job_id = job_store.enqueue(
        PROJECT_ROOT, "event", device="renderD128", output_path="/out/event.mp4"
    )
    job = job_store.get(job_id)
    assert job is not None
    assert job.device == "renderD128"
    assert job.output_path == "/out/event.mp4"


def test_enqueue_stamps_force_and_fingerprint(job_store: JobStore) -> None:
    job_id = job_store.enqueue(
        PROJECT_ROOT, "renderD128-event", device="renderD128", force=True, fingerprint="abc123"
    )
    job = job_store.get(job_id)
    assert job is not None
    assert job.device == "renderD128"
    assert job.force is True
    assert job.fingerprint == "abc123"


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
# submit reports whether it created the job (jobs-client-contract 2.1)
# --------------------------------------------------------------------------- #


def test_submit_reports_the_job_it_created(job_store: JobStore) -> None:
    submission = job_store.submit(
        PROJECT_ROOT, GRILLNING, device="renderD128", force=True, fingerprint="abc123"
    )

    assert submission.created is True
    queued = job_store.list_by_status(JobStatus.QUEUED)
    assert [job.id for job in queued] == [submission.job_id]
    job = queued[0]
    assert (job.project_root, job.event_dir) == (PROJECT_ROOT, GRILLNING)
    assert (job.device, job.force, job.fingerprint) == ("renderD128", True, "abc123")


def test_submit_for_an_active_event_reports_the_existing_job_as_not_created(
    job_store: JobStore,
) -> None:
    first = job_store.submit(PROJECT_ROOT, BLANDAT)

    second = job_store.submit(PROJECT_ROOT, BLANDAT)

    assert second == Submission(job_id=first.job_id, created=False)
    assert [job.id for job in job_store.list_by_status(JobStatus.QUEUED)] == [first.job_id]


def test_concurrent_submits_agree_on_one_creation(job_store: JobStore) -> None:
    # Both threads are released together, so the two inserts race on the partial
    # unique index instead of simply running one after the other.
    barrier = threading.Barrier(2)

    def _submit() -> Submission:
        barrier.wait(timeout=10)
        return job_store.submit(PROJECT_ROOT, GRILLNING)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_submit) for _ in range(2)]
        submissions = [f.result() for f in as_completed(futures)]

    assert sorted(submission.created for submission in submissions) == [False, True]
    assert submissions[0].job_id == submissions[1].job_id
    queued = job_store.list_by_status(JobStatus.QUEUED)
    assert [job.id for job in queued] == [submissions[0].job_id]


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
# list_finished_since (jobs-client-contract 2.1)
# --------------------------------------------------------------------------- #


def _finish(job_store: JobStore, event_dir: str, status: JobStatus = JobStatus.DONE) -> uuid.UUID:
    """Enqueue, claim and terminate a job for ``event_dir``; the queue must be empty."""
    job_id = job_store.enqueue(PROJECT_ROOT, event_dir)
    claimed = job_store.claim_next("worker-1")
    assert claimed is not None and claimed.id == job_id
    job_store.transition(
        job_id, status, error="probe failed" if status is JobStatus.FAILED else None
    )
    return job_id


def test_list_finished_since_returns_the_jobs_finished_after_the_instant(
    job_store: JobStore,
) -> None:
    _finish(job_store, MIDSOMMAR)  # finished before the first read: never returned

    first = job_store.list_finished_since(None, overlap=timedelta(0))
    assert first.as_of.tzinfo is not None
    assert first.jobs == []

    trasig = _finish(job_store, TRASIG, JobStatus.FAILED)
    job_store.enqueue(PROJECT_ROOT, BADUTFLYKT)
    job_store.claim_next("worker-2")  # running alongside
    job_store.enqueue(PROJECT_ROOT, GRILLNING)  # queued alongside

    second = job_store.list_finished_since(first.as_of, overlap=timedelta(0))

    assert [(job.id, job.status, job.error) for job in second.jobs] == [
        (trasig, JobStatus.FAILED, "probe failed")
    ]
    assert second.as_of >= first.as_of


def test_list_finished_since_overlap_reaches_back_before_the_instant(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    job_id = _finish(job_store, TRASIG, JobStatus.FAILED)
    as_of = job_store.list_finished_since(None, overlap=timedelta(0)).as_of
    with session_scope(jobs_session_factory) as session:
        job = session.get(Job, job_id)
        assert job is not None
        job.finished_at = as_of - timedelta(seconds=5)

    assert job_store.list_finished_since(as_of, overlap=timedelta(0)).jobs == []
    reached = job_store.list_finished_since(as_of, overlap=timedelta(seconds=30)).jobs
    assert [job.id for job in reached] == [job_id]


def test_list_finished_since_orders_by_finished_at(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    start = job_store.list_finished_since(None, overlap=timedelta(0)).as_of
    earlier_created = _finish(job_store, GRILLNING)
    later_created = _finish(job_store, TRASIG, JobStatus.FAILED)
    with session_scope(jobs_session_factory) as session:
        # Stamp the job created first as the one that finished last.
        for job_id, seconds in ((earlier_created, 10), (later_created, 5)):
            job = session.get(Job, job_id)
            assert job is not None
            job.finished_at = start + timedelta(seconds=seconds)

    finished = job_store.list_finished_since(start, overlap=timedelta(0)).jobs

    assert [job.id for job in finished] == [later_created, earlier_created]


# --------------------------------------------------------------------------- #
# Listings narrowed to one project (jobs-project-guards 2.1)
# --------------------------------------------------------------------------- #

LIBRARY_A = "/dev/a/library"
LIBRARY_B = "/dev/b/library"


def test_list_by_status_narrowed_to_a_project_returns_only_its_jobs(job_store: JobStore) -> None:
    own = job_store.enqueue(LIBRARY_A, BLANDAT)
    foreign = job_store.enqueue(LIBRARY_B, BLANDAT)

    narrowed = job_store.list_by_status(JobStatus.QUEUED, project_root=LIBRARY_A)
    everything = job_store.list_by_status(JobStatus.QUEUED)

    assert [job.id for job in narrowed] == [own]
    assert [job.id for job in everything] == [own, foreign]  # every project, oldest first


def test_a_job_with_no_project_root_is_never_in_a_narrowed_listing(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    with session_scope(jobs_session_factory) as session:
        rootless = Job(project_root=None, event_dir=BLANDAT)
        session.add(rootless)
        session.flush()
        rootless_id = rootless.id

    assert job_store.list_by_status(JobStatus.QUEUED, project_root=LIBRARY_A) == []
    assert [job.id for job in job_store.list_by_status(JobStatus.QUEUED)] == [rootless_id]


def test_list_finished_since_narrowed_to_a_project_returns_only_its_jobs(
    job_store: JobStore,
) -> None:
    as_of = job_store.list_finished_since(None, overlap=timedelta(0)).as_of
    own = job_store.enqueue(LIBRARY_A, TRASIG)
    foreign = job_store.enqueue(LIBRARY_B, TRASIG)
    for job_id in (own, foreign):
        claimed = job_store.claim_next("worker-1")
        assert claimed is not None and claimed.id == job_id
        job_store.transition(job_id, JobStatus.FAILED, error="probe failed")

    narrowed = job_store.list_finished_since(as_of, overlap=timedelta(0), project_root=LIBRARY_A)
    everything = job_store.list_finished_since(as_of, overlap=timedelta(0))

    assert [(job.id, job.status) for job in narrowed.jobs] == [(own, JobStatus.FAILED)]
    assert {job.id for job in everything.jobs} == {own, foreign}
    assert narrowed.as_of >= as_of  # the database time is the read's, narrowed or not


def test_the_queue_stays_shared_while_listings_are_narrowed(job_store: JobStore) -> None:
    """Scoping is a read filter only: a worker still claims any project's job."""
    foreign = job_store.enqueue(LIBRARY_B, BLANDAT)

    claimed = job_store.claim_next("worker-1")

    assert claimed is not None and claimed.id == foreign
    assert job_store.list_by_status(JobStatus.RUNNING, project_root=LIBRARY_A) == []
    assert [job.id for job in job_store.list_by_status(JobStatus.RUNNING)] == [foreign]


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
# cancel: one locked transaction reporting its outcome (jobs-client-contract 2.2)
# --------------------------------------------------------------------------- #


def test_cancel_outcomes_are_a_closed_vocabulary() -> None:
    assert [outcome.value for outcome in CancelOutcome] == [
        "flagged-running",
        "canceled-queued",
        "no-op-terminal",
    ]


def test_cancel_flags_a_running_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, BADUTFLYKT)
    job_store.claim_next("worker-1")

    result = job_store.cancel(job_id)

    assert result is not None
    assert result.outcome is CancelOutcome.FLAGGED_RUNNING
    assert (result.job.status, result.job.cancel_requested) == (JobStatus.RUNNING, True)
    job = job_store.get(job_id)
    assert job is not None
    assert (job.status, job.cancel_requested) == (JobStatus.RUNNING, True)


def test_cancel_cancels_a_queued_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, BLANDAT)

    result = job_store.cancel(job_id)

    assert result is not None
    assert result.outcome is CancelOutcome.CANCELED_QUEUED
    assert result.job.status == JobStatus.CANCELED
    assert result.job.finished_at is not None
    assert job_store.claim_next("worker-1") is None


def test_cancel_leaves_a_terminal_job_unchanged(job_store: JobStore) -> None:
    job_id = _finish(job_store, TRASIG, JobStatus.FAILED)
    before = job_store.get(job_id)
    assert before is not None

    result = job_store.cancel(job_id)

    assert result is not None
    assert result.outcome is CancelOutcome.NO_OP_TERMINAL
    assert result.job.status == JobStatus.FAILED
    after = job_store.get(job_id)
    assert after is not None
    assert (after.status, after.cancel_requested, after.finished_at, after.error) == (
        JobStatus.FAILED,
        False,
        before.finished_at,
        before.error,
    )


def test_cancel_reports_a_missing_job_as_none(job_store: JobStore) -> None:
    assert job_store.cancel(uuid.uuid4()) is None


def _cancel_during_a_held_claim(
    session_factory: sessionmaker, job_id: uuid.UUID, cancel: Callable[[uuid.UUID], _T]
) -> _T:
    """Run ``cancel(job_id)`` while another transaction holds the queued row mid-claim.

    The claim is ``claim_next``'s own write (``FOR UPDATE SKIP LOCKED``, then
    ``running`` with a worker id), left uncommitted for ~0.5 s after the cancel
    starts: the cancel must wait for the row rather than act on the ``queued``
    version it can still read. Committing the claim releases it.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    claim = session_factory()
    try:
        job = claim.execute(
            select(Job).where(Job.id == job_id).with_for_update(skip_locked=True)
        ).scalar_one()
        job.status = JobStatus.RUNNING
        job.worker_id = "worker-1"
        job.started_at = func.now()  # pylint: disable=not-callable
        claim.flush()
        future = pool.submit(cancel, job_id)
        time.sleep(0.5)
        blocked = not future.done()
        claim.commit()
    finally:
        claim.close()  # rolls an uncommitted claim back, so the cancel thread can finish
        pool.shutdown(wait=True)
    assert blocked, "the cancel did not wait for the transaction holding the row"
    return future.result()


def test_cancel_waits_for_a_claim_holding_the_row(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    job_id = job_store.enqueue(PROJECT_ROOT, BLANDAT)

    result = _cancel_during_a_held_claim(jobs_session_factory, job_id, job_store.cancel)

    assert result is not None
    assert result.outcome is CancelOutcome.FLAGGED_RUNNING
    job = job_store.get(job_id)
    assert job is not None
    assert (job.status, job.worker_id, job.cancel_requested) == (
        JobStatus.RUNNING,
        "worker-1",
        True,
    )
    assert job.finished_at is None


def test_request_cancel_waits_for_a_claim_holding_the_row(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    # The lost update this guards: an unlocked read sees ``queued``, and the write
    # then overwrites the claim's committed ``running`` with ``canceled`` while the
    # worker renders on, unflagged, to a row that says it was canceled.
    job_id = job_store.enqueue(PROJECT_ROOT, BLANDAT)

    result = _cancel_during_a_held_claim(jobs_session_factory, job_id, job_store.request_cancel)

    assert result is not None
    assert (result.status, result.cancel_requested) == (JobStatus.RUNNING, True)
    job = job_store.get(job_id)
    assert job is not None
    assert (job.status, job.worker_id, job.cancel_requested) == (
        JobStatus.RUNNING,
        "worker-1",
        True,
    )


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
