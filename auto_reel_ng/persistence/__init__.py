"""The persistence layer: connection config, engine/session, models, and the job store.

Holds only *derived* state — the transient jobs work ledger today, an event index
later — never editorial state. ``reel.yaml`` on disk remains the sole authoritative
source of editorial decisions (order/trims/metadata/look); dropping and recreating
the database costs at most re-enqueuing work (D-7/D-P6).

- :mod:`auto_reel_ng.persistence.config` resolves ``DATABASE_URL`` (env ->
  project ``config.yaml`` -> a documented dev default pointing at a local
  containerized Postgres).
- :mod:`auto_reel_ng.persistence.engine` builds the SQLAlchemy engine and a
  commit/rollback/close session-factory context manager.
- :mod:`auto_reel_ng.persistence.models` defines the ``jobs`` table (``Job``,
  ``JobStatus``).
- :mod:`auto_reel_ng.persistence.job_store` is the repository over it:
  ``enqueue``, race-free ``claim_next`` (``FOR UPDATE SKIP LOCKED``, D-P3),
  ``transition``, ``set_progress``, queries, ``cancel_queued``, and the orphaned-
  ``running`` reconcile query consumed by the scheduler (7b).

Schema changes go through **Alembic** (``alembic/``, repo root) — run
``alembic upgrade head`` to provision a database; ``Base.metadata.create_all`` is
used only by the test suite for a fast clean schema (D-P7), never in production.
The test suite's ``requires_db``-marked tests start a throwaway **podman**
Postgres container (see ``tests/conftest.py``); tests without that marker never
touch it.
"""

from __future__ import annotations

from .config import DEFAULT_DATABASE_URL, resolve_database_url
from .engine import make_engine, make_session_factory, session_scope
from .job_store import JobStore
from .models import Base, Job, JobKind, JobStatus

__all__ = [
    "DEFAULT_DATABASE_URL",
    "resolve_database_url",
    "make_engine",
    "make_session_factory",
    "session_scope",
    "Base",
    "Job",
    "JobKind",
    "JobStatus",
    "JobStore",
]
