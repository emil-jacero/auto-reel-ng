## 1. Dependencies and test harness

- [x] 1.1 Add `sqlalchemy`, `alembic`, `psycopg[binary]` to `pyproject.toml` (pin versions) and verify a
  clean install in the `--system-site-packages` venv; update the venv rebuild notes.
- [x] 1.2 Add a session-scoped **podman Postgres** pytest fixture (starts a throwaway container, yields a
  `DATABASE_URL`, tears it down) gated behind a `requires_db` marker; add a smoke test proving the
  container comes up and a non-DB test runs without it.

## 2. Connection and configuration

- [x] 2.1 Create `auto_reel_ng/persistence/config.py` resolving the URL `DATABASE_URL` → `config.yaml`
  `database.url` → documented dev default; fail loud naming the attempted sources. Test all three
  precedence branches + the fail-loud path.
- [x] 2.2 Create `auto_reel_ng/persistence/engine.py` with the SQLAlchemy engine + a session-factory
  context manager (commit on success, rollback on exception, always close). Test commit/rollback/close
  behavior against the podman PG.

## 3. Schema, models, and migrations

- [x] 3.1 Define the `Job` SQLAlchemy model in `auto_reel_ng/persistence/models.py`: id (uuid), event_dir,
  output_path, status enum (queued/running/done/failed/canceled), device, priority (default 0), progress
  (default 0.0), error, fingerprint, worker_id, created_at/started_at/finished_at (server-side timestamps).
- [x] 3.2 Scaffold Alembic (`alembic.ini` + `alembic/env.py` reading the resolved `DATABASE_URL`) and write
  the initial migration creating `jobs`, the status enum, and indexes on `status` and
  `(status, priority, created_at)` for claim-next.
- [x] 3.3 Test `upgrade head` from empty builds the full schema; add a **drift test** asserting the models'
  `create_all` schema equals the migrated schema.

## 4. Job-store repository

- [x] 4.1 `enqueue(event_dir, *, device="auto", output_path=None) -> id` inserting a `queued` row; test the
  defaults (status/priority/device/progress/timestamps) land correctly.
- [x] 4.2 `claim_next(worker_id, device_filter) -> Job | None` using `FOR UPDATE SKIP LOCKED`, ordered
  `priority DESC, created_at ASC`, stamping `running`/`worker_id`/`started_at`. Test: concurrent claims
  never double-claim, FIFO-within-priority order, and device-filter exclusion.
- [x] 4.3 `transition(job_id, terminal_status, *, error=None)` running→done/failed/canceled stamping
  `finished_at`; reject transitions from non-`running`. Test success, failure-with-error, and the illegal
  transition rejection.
- [x] 4.4 `set_progress(job_id, fraction)` clamped to `[0,1]`, running-only. Test it persists for a running
  job and is ignored for non-running jobs.
- [x] 4.5 `get(job_id)` and `list_by_status(status)` (ordered by `created_at`). Test fetch-by-id (present
  + absent) and status-filtered listing order.
- [x] 4.6 `cancel_queued(job_id)` moving queued→canceled + `finished_at`; test a canceled job is never
  returned by `claim_next`.

## 5. Reconcile query

- [x] 5.1 `find_orphaned_running(live_workers | cutoff) -> list[Job]` returning `running` jobs whose worker
  is not live / older than the cutoff. Test an orphaned running row is surfaced and an active one is not.

## 6. Invariant and docs

- [x] 6.1 Add a test asserting the D-7 boundary: exercising every store operation creates/modifies **no**
  `reel.yaml`, and a drop+recreate of the DB leaves on-disk `reel.yaml` fixtures byte-identical.
- [x] 6.2 Document the persistence layer in the module docstring + a short note in the venv/test memo:
  running the suite now needs podman; the dev default DB URL; `alembic upgrade head` to provision.
