"""Tests asserting the D-7 "derived, rebuildable from disk" boundary (D-P6): the
persistence layer never mutates editorial state on disk, and a dropped/recreated
database costs at most re-enqueuing work — never a lost editorial decision."""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_reel_ng.persistence.engine import make_engine, make_session_factory
from auto_reel_ng.persistence.job_store import JobStore
from auto_reel_ng.persistence.models import Base, JobStatus

pytestmark = pytest.mark.requires_db


def _reel_yaml_fixtures(root: Path) -> dict[Path, bytes]:
    """Write two on-disk ``reel.yaml`` fixtures and return their original bytes."""
    reel_a = root / "2026-01-01 - Party" / "reel.yaml"
    reel_b = root / "2026-02-02 - Trip" / "reel.yaml"
    for path in (reel_a, reel_b):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"version: 0\nmetadata:\n  title: Party\n")
    return {path: path.read_bytes() for path in (reel_a, reel_b)}


def test_store_operations_never_touch_reel_yaml(job_store: JobStore, tmp_path: Path) -> None:
    before = _reel_yaml_fixtures(tmp_path)

    job_id = job_store.enqueue(str(tmp_path / "2026-01-01 - Party"))
    job_store.claim_next("worker")
    job_store.set_progress(job_id, 0.5)
    job_store.transition(job_id, JobStatus.DONE)
    other_id = job_store.enqueue(str(tmp_path / "2026-02-02 - Trip"))
    job_store.cancel_queued(other_id)
    job_store.get(job_id)
    job_store.list_by_status(JobStatus.DONE)
    job_store.find_orphaned_running(live_workers=["worker"])

    after = {path: path.read_bytes() for path in before}
    assert after == before
    # Nothing new was created under tmp_path beyond the two fixtures above.
    assert sorted(p for p in tmp_path.rglob("*") if p.is_file()) == sorted(before)


def test_database_drop_and_recreate_leaves_reel_yaml_untouched(
    fresh_database_url: str, tmp_path: Path
) -> None:
    before = _reel_yaml_fixtures(tmp_path)

    engine = make_engine(fresh_database_url)
    try:
        Base.metadata.create_all(engine)
        store = JobStore(make_session_factory(engine))
        store.enqueue(str(tmp_path / "2026-01-01 - Party"))
        store.enqueue(str(tmp_path / "2026-02-02 - Trip"))

        # Drop and recreate the database: the transient work ledger is lost, but
        # nothing on disk is touched (D-7).
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        after = {path: path.read_bytes() for path in before}
        assert after == before
        assert store.list_by_status(JobStatus.QUEUED) == []
    finally:
        engine.dispose()
