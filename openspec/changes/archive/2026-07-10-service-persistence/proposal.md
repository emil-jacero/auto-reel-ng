## Why

Phase #6 (`project-cli`) delivered the **left half of phase #7** — a headless driver that runs
scan→render synchronously and in-process. The **right half** needs durable, queryable state: renders
today are a transient `render_batch` for-loop that dies with the process, so nothing survives a restart,
nothing can be scheduled or observed by a second process, and there is no place for a future API/GUI to
read job state. Per **D-7**, the service uses **Postgres** for derived state. This change lays the
persistence foundation — connection/config/migrations plus a **durable job store** — that the scheduler
(7b) and FastAPI service (7c) build on. It ships nothing user-facing on its own; it is the schema and
data-access layer, split out so the scheduler and API land against a stable, migrated, tested store.

## What Changes

- Add a **persistence layer** (`auto_reel_ng/persistence/`): a SQLAlchemy engine/session factory, a
  `DATABASE_URL` config resolution (env → project `config.yaml` → default), and an **Alembic** migration
  harness. Uphold the **D-7 invariant**: everything here is *derived* and **rebuildable from disk** —
  `reel.yaml` on disk remains the editorial source of truth; the DB never becomes the sole home of
  authoritative editorial state.
- Add a **durable job store** (the `jobs` table + a repository API) sized for the T2 decision (a
  separate worker process reads this table). Schema carries everything 7b/7c need so no migration churn
  later: lifecycle `status` (`queued`/`running`/`done`/`failed`/`canceled`), `device` selector
  (`auto` | a render-node id, per §4.8 multi-GPU-ready), FIFO `created_at` + a reserved (unused)
  `priority`, `progress` (0.0–1.0, fed by the engine's existing `on_progress`), `error`, timestamps, and
  a nullable `fingerprint` column reserved for the deferred change-detection gate (§8.14).
- Provide store operations as behavioral requirements: `enqueue`, atomic **claim-next** (a worker
  transitions exactly one `queued`→`running` without racing other workers), `transition`
  (running→done/failed/canceled), `progress` update, list/get queries, and a **reconcile query** that
  finds orphaned `running` jobs (the input to 7b's requeue-on-restart policy — see design).
- Add a **containerized Postgres test fixture** (podman, per T3) so tests exercise the real dialect
  (JSONB, `LISTEN/NOTIFY`, `SELECT … FOR UPDATE SKIP LOCKED`) rather than a SQLite stand-in.
- Add deps to `pyproject.toml`: `sqlalchemy`, `alembic`, `psycopg[binary]` (binary wheel — no native
  build, unlike pycairo/PyGObject). Ship a dev containerized PG in the compose/deploy story (D-7).

## Capabilities

### New Capabilities
- `persistence`: The SQLAlchemy engine/session lifecycle, `DATABASE_URL` config resolution, the Alembic
  migration harness, the podman Postgres test fixture, and the D-7 "derived, rebuildable from disk"
  invariant that bounds what the DB is allowed to own.
- `job-store`: The `jobs` table schema (lifecycle states, `device`, FIFO+reserved `priority`, `progress`,
  `error`, reserved `fingerprint`) and its repository operations — `enqueue`, race-free claim-next,
  `transition`, `progress`, queries, and the orphaned-`running` reconcile query.

### Modified Capabilities
<!-- None. This change adds a new persistence layer beside the engine; no existing engine capability's
     requirements change. The scheduler that *drives* render_movie from the store lands in 7b. -->

## Impact

- **New modules**: `auto_reel_ng/persistence/` (engine/session/config, SQLAlchemy models, Alembic
  `env.py` + versions, the job-store repository).
- **`pyproject.toml`**: add `sqlalchemy`, `alembic`, `psycopg[binary]`; add an `alembic` config +
  migrations dir. New optional test dependency wiring for the podman PG fixture.
- **`config.yaml`**: an optional `database.url` key (env `DATABASE_URL` wins) resolved through the
  existing D-2 layering; absent config falls back to a documented dev default (containerized PG).
- **Reuses unchanged**: the engine (`render_movie`/`render_batch`/`RenderJob`/`RenderOptions`,
  `on_progress`, `_selected_render_node`) — this change stores state *about* jobs but does not yet drive
  them; wiring the store to execution is 7b.
- **Test loop**: introduces a container dependency (podman Postgres) to the suite — the first external
  service in a previously service-free `pytest` run (accepted per T3).

## Non-goals

- **No scheduler / no execution.** This change does not run jobs, own a worker loop, enforce capacity
  pools, or implement the restart **requeue** policy — it only provides the store and the reconcile
  *query*. All of that is **7b `job-scheduler`**.
- **No API / no WebSocket.** FastAPI CRUD and the WS progress channel are **7c `api-service`**.
- **No event index.** Per D-7 the DB will also hold a derived event/clip index, but it has no consumer
  until the GUI (phase 8) / change-detection (§8.14) — deferred to its first real user to keep this
  slice minimal.
- **No change-detection.** The `fingerprint` column is reserved but unused; `_staleness_filter` stays a
  no-op (T1, parked, §8.14).
- **No analysis-cache / ingest-layout persistence.** Those D-7 tables land with their own consumers.
