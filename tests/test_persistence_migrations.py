"""Tests for the Alembic migration harness: upgrade-from-empty and model drift (D-P7).

Alembic owns the schema (D-P7); ``metadata.create_all`` is used only by the
job-store test fixture. These tests exercise the migration path itself against a
freshly created, isolated database on the shared podman container.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from auto_reel_ng.persistence.engine import make_engine
from auto_reel_ng.persistence.models import Base

pytestmark = pytest.mark.requires_db

_REPO_ROOT = Path(__file__).resolve().parents[1]

_EXPECTED_COLUMNS = {
    "id",
    "event_dir",
    "project_root",
    "output_path",
    "status",
    "device",
    "priority",
    "progress",
    "cancel_requested",
    "requeue_count",
    "force",
    "error",
    "fingerprint",
    "worker_id",
    "created_at",
    "started_at",
    "finished_at",
}


def _alembic_config() -> AlembicConfig:
    cfg = AlembicConfig(str(_REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    return cfg


@pytest.fixture
def migrated_url(fresh_database_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """``fresh_database_url`` with Alembic's ``upgrade head`` already applied."""
    monkeypatch.setenv("DATABASE_URL", fresh_database_url)
    command.upgrade(_alembic_config(), "head")
    return fresh_database_url


def test_upgrade_head_builds_full_schema_from_empty(migrated_url: str) -> None:
    engine = make_engine(migrated_url)
    try:
        inspector = inspect(engine)
        assert "jobs" in inspector.get_table_names()

        columns = {c["name"] for c in inspector.get_columns("jobs")}
        assert columns == _EXPECTED_COLUMNS

        index_names = {i["name"] for i in inspector.get_indexes("jobs")}
        assert {
            "ix_jobs_status",
            "ix_jobs_claim_next",
            "ux_jobs_active_identity",
        } <= index_names

        enum_names = {e["name"] for e in inspector.get_enums()}
        assert "job_status" in enum_names
    finally:
        engine.dispose()


def test_status_rejects_out_of_range_value(migrated_url: str) -> None:
    """The ``job_status`` Postgres enum, not application code, enforces this."""
    engine = make_engine(migrated_url)
    try:
        with pytest.raises(DBAPIError):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO jobs (id, event_dir, status, device, priority, progress) "
                        "VALUES (:id, 'event', 'bogus', 'auto', 0, 0.0)"
                    ),
                    {"id": uuid.uuid4()},
                )
    finally:
        engine.dispose()


def test_migrations_match_models(migrated_url: str) -> None:
    """Drift test: the migrated schema must equal what the models declare."""
    engine = make_engine(migrated_url)
    try:
        with engine.connect() as conn:
            migration_context = MigrationContext.configure(conn)
            diff = compare_metadata(migration_context, Base.metadata)
        assert diff == []
    finally:
        engine.dispose()
