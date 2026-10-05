"""Tests for job kinds in the job store (job-kind): the per-kind active-job guarantee,
per-kind enqueue and lookup, and the kind scope of the read surfaces (real Postgres)."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from auto_reel_ng.persistence.engine import session_scope
from auto_reel_ng.persistence.job_store import JobStore, Submission
from auto_reel_ng.persistence.models import Job, JobKind, JobStatus

pytestmark = pytest.mark.requires_db

LIBRARY_A = "/dev/a/library"
GRILLNING = "2024/2024-06-27 - Grillning med grannar"
BLANDAT = "2024/Blandat"
TRASIG = "2024/2024-10-05 - Trasig"

_T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _insert(
    factory: sessionmaker,
    event_dir: str,
    *,
    kind: str | None = None,
    status: JobStatus = JobStatus.QUEUED,
    minutes: int = 0,
    priority: int = 0,
) -> uuid.UUID:
    """Insert a job with an explicit ``created_at``; ``kind=None`` leaves the column default."""
    job = Job(
        project_root=LIBRARY_A,
        event_dir=event_dir,
        status=status,
        priority=priority,
        created_at=_T0 + timedelta(minutes=minutes),
    )
    if kind is not None:
        job.kind = kind
    with session_scope(factory) as session:
        session.add(job)
        session.flush()
        return job.id


# --------------------------------------------------------------------------- #
# 1.1 schema: the kind column and the per-kind unique-active index
# --------------------------------------------------------------------------- #


def test_a_new_job_is_a_render(job_store: JobStore) -> None:
    job = job_store.get(job_store.enqueue(LIBRARY_A, BLANDAT))
    assert job is not None
    assert job.kind == "render" == JobKind.RENDER


def test_a_row_without_a_kind_defaults_to_render(jobs_session_factory: sessionmaker) -> None:
    job_id = _insert(jobs_session_factory, BLANDAT)
    with session_scope(jobs_session_factory) as session:
        assert session.get(Job, job_id).kind == "render"  # type: ignore[union-attr]


def test_a_render_and_a_proxy_job_for_one_event_are_active_together(
    jobs_session_factory: sessionmaker,
) -> None:
    _insert(jobs_session_factory, GRILLNING, kind="render", status=JobStatus.RUNNING)
    proxy = _insert(jobs_session_factory, GRILLNING, kind="proxy", status=JobStatus.QUEUED)

    assert proxy is not None
    for kind, status in (("proxy", JobStatus.QUEUED), ("render", JobStatus.QUEUED)):
        with pytest.raises(IntegrityError):
            _insert(jobs_session_factory, GRILLNING, kind=kind, status=status)


def test_a_finished_job_does_not_block_a_new_one_of_its_kind(
    jobs_session_factory: sessionmaker,
) -> None:
    _insert(jobs_session_factory, GRILLNING, kind="proxy", status=JobStatus.DONE)
    _insert(jobs_session_factory, GRILLNING, kind="proxy", status=JobStatus.QUEUED)


def test_the_database_accepts_a_kind_this_build_does_not_know(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    job_id = _insert(jobs_session_factory, BLANDAT, kind="thumbnails")
    job = job_store.get(job_id)
    assert job is not None
    assert job.kind == "thumbnails"


# --------------------------------------------------------------------------- #
# 1.3 enqueue and the active-job lookup are per kind
# --------------------------------------------------------------------------- #


def test_enqueue_is_idempotent_per_kind(job_store: JobStore) -> None:
    render = job_store.submit(LIBRARY_A, BLANDAT)

    first = job_store.submit(LIBRARY_A, BLANDAT, kind=JobKind.PROXY)
    second = job_store.submit(LIBRARY_A, BLANDAT, kind=JobKind.PROXY)

    assert first.created is True and first.job_id != render.job_id
    assert second == Submission(job_id=first.job_id, created=False)
    stored = job_store.get(first.job_id)
    assert stored is not None and stored.kind == "proxy"
    untouched = job_store.get(render.job_id)
    assert untouched is not None
    assert (untouched.kind, untouched.status) == ("render", JobStatus.QUEUED)
    assert job_store.enqueue(LIBRARY_A, BLANDAT) == render.job_id


def test_the_active_job_lookup_is_per_kind(job_store: JobStore) -> None:
    proxy_id = job_store.enqueue(LIBRARY_A, BLANDAT, kind=JobKind.PROXY)

    assert job_store.active_job(LIBRARY_A, BLANDAT) is None
    found = job_store.active_job(LIBRARY_A, BLANDAT, JobKind.PROXY)
    assert found is not None and found.id == proxy_id

    render_id = job_store.enqueue(LIBRARY_A, BLANDAT)
    default = job_store.active_job(LIBRARY_A, BLANDAT)
    assert default is not None and default.id == render_id


def test_concurrent_proxy_enqueues_agree_on_one_creation(job_store: JobStore) -> None:
    job_store.enqueue(LIBRARY_A, GRILLNING)  # an active render must not matter
    barrier = threading.Barrier(2)

    def _submit() -> Submission:
        barrier.wait(timeout=10)
        return job_store.submit(LIBRARY_A, GRILLNING, kind=JobKind.PROXY)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_submit) for _ in range(2)]
        submissions = [f.result() for f in as_completed(futures)]

    assert sorted(s.created for s in submissions) == [False, True]
    assert submissions[0].job_id == submissions[1].job_id
    proxies = job_store.list_by_status(JobStatus.QUEUED, kind=JobKind.PROXY)
    assert [job.id for job in proxies] == [submissions[0].job_id]


# --------------------------------------------------------------------------- #
# 1.4 reads are scoped to a kind, defaulting to render
# --------------------------------------------------------------------------- #


def test_list_by_status_defaults_to_render_jobs(job_store: JobStore) -> None:
    render = job_store.enqueue(LIBRARY_A, BLANDAT)
    proxy = job_store.enqueue(LIBRARY_A, BLANDAT, kind=JobKind.PROXY)

    assert [j.id for j in job_store.list_by_status(JobStatus.QUEUED)] == [render]
    assert [j.id for j in job_store.list_by_status(JobStatus.QUEUED, kind="proxy")] == [proxy]
    both = job_store.list_by_status(JobStatus.QUEUED, kind=None)
    assert [j.id for j in both] == [render, proxy]
    narrowed = job_store.list_by_status(JobStatus.QUEUED, project_root="/elsewhere", kind=None)
    assert narrowed == []


def test_a_finished_proxy_job_is_not_a_finished_render(job_store: JobStore) -> None:
    as_of = job_store.list_finished_since(None, overlap=timedelta(0)).as_of
    proxy_id = job_store.enqueue(LIBRARY_A, TRASIG, kind=JobKind.PROXY)
    claimed = job_store.claim_next("worker")
    assert claimed is not None and claimed.id == proxy_id
    job_store.transition(proxy_id, JobStatus.DONE)

    assert job_store.list_finished_since(as_of, overlap=timedelta(0)).jobs == []
    every = job_store.list_finished_since(as_of, overlap=timedelta(0), kind=None)
    assert [j.id for j in every.jobs] == [proxy_id]
    only = job_store.list_finished_since(as_of, overlap=timedelta(0), kind="proxy")
    assert [j.id for j in only.jobs] == [proxy_id]


def test_a_job_is_fetched_by_id_whatever_its_kind(job_store: JobStore) -> None:
    proxy_id = job_store.enqueue(LIBRARY_A, BLANDAT, kind=JobKind.PROXY)
    job = job_store.get(proxy_id)
    assert job is not None and job.kind == "proxy"


def test_a_newer_proxy_job_does_not_displace_the_latest_render(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    render = _insert(jobs_session_factory, BLANDAT, kind="render", status=JobStatus.DONE, minutes=1)
    proxy = _insert(jobs_session_factory, BLANDAT, kind="proxy", status=JobStatus.QUEUED, minutes=2)

    assert job_store.latest_by_project(LIBRARY_A)[BLANDAT].id == render
    assert job_store.latest_by_project(LIBRARY_A, kind="proxy")[BLANDAT].id == proxy
    assert job_store.latest_by_project(LIBRARY_A, kind=None)[BLANDAT].id == proxy


def test_an_event_with_only_proxy_jobs_has_no_latest_render(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    _insert(jobs_session_factory, BLANDAT, kind="proxy")

    assert job_store.latest_by_project(LIBRARY_A) == {}
    assert set(job_store.latest_by_project(LIBRARY_A, kind=None)) == {BLANDAT}


# --------------------------------------------------------------------------- #
# claim_next: a render before any other kind (proxy-job)
# --------------------------------------------------------------------------- #


def test_claim_next_claims_a_newer_render_before_an_older_proxy_job(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    proxy = _insert(jobs_session_factory, GRILLNING, kind="proxy", minutes=0)
    render = _insert(jobs_session_factory, BLANDAT, kind="render", minutes=60)

    first = job_store.claim_next("worker")
    second = job_store.claim_next("worker")

    assert first is not None and second is not None
    assert (first.id, second.id) == (render, proxy)


def test_claim_next_claims_a_render_before_a_proxy_job_of_higher_priority(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    _insert(jobs_session_factory, GRILLNING, kind="proxy", minutes=0, priority=9)
    render = _insert(jobs_session_factory, BLANDAT, kind="render", minutes=1)

    claimed = job_store.claim_next("worker")

    assert claimed is not None and claimed.id == render


def test_claim_next_keeps_priority_then_age_within_a_kind(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    old = _insert(jobs_session_factory, "2024/a", kind="render", minutes=0)
    urgent = _insert(jobs_session_factory, "2024/b", kind="render", minutes=5, priority=3)
    new = _insert(jobs_session_factory, "2024/c", kind="render", minutes=9)

    order = [job_store.claim_next("worker") for _ in range(3)]

    assert [job.id for job in order if job is not None] == [urgent, old, new]


def test_claim_next_takes_proxy_jobs_oldest_first(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    first = _insert(jobs_session_factory, "2024/a", kind="proxy", minutes=0)
    second = _insert(jobs_session_factory, "2024/b", kind="proxy", minutes=1)
    third = _insert(jobs_session_factory, "2024/c", kind="proxy", minutes=2)

    order = [job_store.claim_next("worker") for _ in range(3)]

    assert [job.id for job in order if job is not None] == [first, second, third]


def test_claim_next_leaves_an_excluded_kind_queued_and_takes_the_render(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    proxy = _insert(jobs_session_factory, GRILLNING, kind="proxy", minutes=0)
    render = _insert(jobs_session_factory, BLANDAT, kind="render", minutes=5)

    claimed = job_store.claim_next("worker", exclude_kinds=["proxy"])

    assert claimed is not None and claimed.id == render
    assert job_store.claim_next("worker", exclude_kinds=["proxy"]) is None
    queued = job_store.get(proxy)
    assert queued is not None and queued.status == JobStatus.QUEUED


def test_claim_next_without_exclusions_still_claims_a_kind_it_has_never_heard_of(
    job_store: JobStore, jobs_session_factory: sessionmaker
) -> None:
    thumbnails = _insert(jobs_session_factory, GRILLNING, kind="thumbnails", minutes=0)

    claimed = job_store.claim_next("worker", exclude_kinds=["proxy"])

    assert claimed is not None and claimed.id == thumbnails


# --------------------------------------------------------------------------- #
# force_queued: a forced submit meeting an active job (analysis-job)
# --------------------------------------------------------------------------- #


def test_force_queued_forces_a_queued_job_and_leaves_a_running_one(job_store: JobStore) -> None:
    running = job_store.enqueue(LIBRARY_A, GRILLNING, kind=JobKind.ANALYSIS)
    queued = job_store.enqueue(LIBRARY_A, BLANDAT, kind=JobKind.ANALYSIS)
    claimed = job_store.claim_next("w1")
    assert claimed is not None and claimed.id == running  # oldest first within the kind

    assert job_store.force_queued(queued) is True
    assert job_store.force_queued(running) is False  # it started without force
    assert job_store.force_queued(uuid.uuid4()) is False  # missing
    job = job_store.get(queued)
    assert job is not None and job.force is True and job.status == JobStatus.QUEUED
    job = job_store.get(running)
    assert job is not None and job.force is False and job.status == JobStatus.RUNNING


def test_force_queued_is_false_for_a_terminal_job(job_store: JobStore) -> None:
    job_id = job_store.enqueue(LIBRARY_A, GRILLNING, kind=JobKind.ANALYSIS)
    job_store.cancel_queued(job_id)

    assert job_store.force_queued(job_id) is False
    job = job_store.get(job_id)
    assert job is not None and job.force is False
