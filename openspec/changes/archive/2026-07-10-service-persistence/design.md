## Context

After phase #6, the engine runs synchronously: `render_batch(jobs)` is an in-process for-loop over
`render_movie`, driven by the `auto-reel` CLI. There is no durable state — a render that is interrupted
leaves no record, a second process cannot observe progress, and there is nowhere for the coming API/GUI
to read job state. **D-7** locks Postgres as the store for *derived* state (index, jobs, analysis cache,
ingest-layout defs), explicitly **rebuildable from disk** with `reel.yaml` remaining the editorial source
of truth.

This change is scoped to the **persistence foundation only**: connection/config/migrations plus the
**durable `jobs` store**. It deliberately excludes the scheduler (7b) and API (7c) so those land against
a stable, migrated schema. The engine already exposes the seams the later slices need — `on_progress`
(a 0.0–1.0 callback via `FfmpegRuntime.run_with_progress` parsing `-progress pipe:1`), `render_node`
device selection, and the `_staleness_filter` no-op — so nothing here changes engine behavior.

## Goals / Non-Goals

**Goals:**
- A SQLAlchemy engine/session factory with `DATABASE_URL` resolution (env → `config.yaml` → dev default)
  and an Alembic migration harness.
- A `jobs` table whose columns are complete for 7b/7c so no schema churn later: lifecycle status, device
  selector, FIFO+reserved priority, progress, error, timestamps, reserved `fingerprint`.
- A job-store repository whose operations are **safe for the T2 model** — a *separate worker process*
  claiming work concurrently — most importantly a **race-free claim-next**.
- A **reconcile query** that surfaces orphaned `running` jobs, the input to 7b's requeue policy.
- Tests against a **real containerized Postgres** (podman), not a SQLite stand-in.
- Uphold the **D-7 rebuildable-from-disk invariant** as an explicit boundary.

**Non-Goals:**
- No worker loop, no capacity pools, no requeue *policy*, no execution of `render_movie` (all 7b).
- No FastAPI, no WebSocket (7c).
- No event index, analysis-cache, or ingest-layout tables (land with their consumers).
- No change-detection; `fingerprint` is reserved-unused (T1, parked, §8.14).

## Decisions

### D-P1 — Postgres from the start, real PG in tests (T3), not SQLite
D-7 already locks Postgres. Rather than an ORM-portable SQLite-for-tests / PG-for-prod split, tests run
against a **containerized Postgres via podman** so they exercise the exact dialect features 7b relies on:
`SELECT … FOR UPDATE SKIP LOCKED` (claim-next), `LISTEN/NOTIFY` (worker wakeups), and JSONB.
*Alternative rejected:* SQLite in-memory for speed — it silently lacks `SKIP LOCKED` and `NOTIFY`, so the
concurrency-critical code path would be **untested** exactly where it matters. The host is the immutable
Bazzite box (see venv memo): SQLAlchemy/Alembic/`psycopg[binary]` are pip/wheel installs with **no native
build**, unlike pycairo/PyGObject, so this adds no `--system-site-packages` pain.

### D-P2 — Durable jobs table is the queue (T2 = separate worker process)
The queue *is* the `jobs` table; there is no in-memory queue and no external broker (Redis/arq). A worker
process (7b) selects `queued` rows. This is why claim-next must be race-free at the DB level rather than
in application code. *Alternatives rejected:* in-process asyncio queue (dies on API restart — violates the
durability requirement that chose T2=B); external broker (an extra service and moving part for a
single-host, single-operator deployment where Postgres is already mandated).

### D-P3 — Race-free claim-next via `FOR UPDATE SKIP LOCKED`
`claim_next(worker_id, device_filter)` runs, in one transaction:
`SELECT id FROM jobs WHERE status='queued' AND (<device eligible>) ORDER BY priority DESC, created_at ASC
FOR UPDATE SKIP LOCKED LIMIT 1`, then updates that row to `running`, stamping `worker_id`/`started_at`.
`SKIP LOCKED` guarantees two workers never claim the same row without table-locking the queue. Ordering is
**FIFO within priority** (priority reserved, default 0 → pure FIFO for v1). *Alternative rejected:*
advisory locks / application-level "SELECT then UPDATE if unchanged" retry loop — correct but reinvents
what `SKIP LOCKED` does natively and adds retry latency.

### D-P4 — Job schema is complete for 7b/7c now (no churn later)
Columns: `id` (uuid), `event_dir` (text, the event identity), `output_path` (text, nullable until known),
`status` (enum: queued/running/done/failed/canceled), `device` (text: `auto` or a render-node id, per
§4.8 — modeled per-device now though v1 has one node), `priority` (int, default 0, **reserved-unused**,
FIFO tiebreak `created_at`), `progress` (float 0.0–1.0, default 0.0), `error` (text, nullable),
`fingerprint` (text, nullable, **reserved** for §8.14), `worker_id` (text, nullable), and timestamps
`created_at` / `started_at` / `finished_at`. `status` and `device` semantics come straight from the T4
capacity decisions so 7b adds a scheduler, not a migration.

### D-P5 — Reconcile query here, requeue policy in 7b (respect the slice boundary)
On worker startup a `running` job whose worker died is *orphaned*. This change provides only the **query**
— `find_orphaned_running(before | not-in-live-workers)` — as a store operation. The **policy** decided in
T4 (requeue: if the output file exists and verifies → `done`, else reset to `queued`) needs the engine's
output-verification and lives in 7b. Keeping the query here lets 7b's policy be a thin, testable consumer.
*Alternative rejected:* implement the full requeue here — it would pull `render/verify.py` and worker
identity into a persistence slice that has no worker.

### D-P6 — D-7 rebuildable-from-disk is an enforced boundary, not a slogan
The store holds *job bookkeeping* (a transient work ledger) and, later, a *derived index*. It never holds
editorial state (order/trims/metadata/look) — that stays in `reel.yaml`. Concretely: nothing in this
layer writes back to `reel.yaml`, and a dropped-and-recreated database must cost at most re-enqueuing
work, never lost editorial decisions. This is asserted in the `persistence` spec and guards future tables.

### D-P7 — Alembic owns the schema; `create_all` only in the test fixture
Production/dev schema changes go through Alembic migrations (one initial migration creating `jobs`). The
SQLAlchemy `metadata.create_all` path is used **only** by the podman test fixture for a fast clean schema,
kept in sync by a test that asserts "migrations produce the same schema as the models."

## Risks / Trade-offs

- **[Container dependency in the test loop]** → podman Postgres is now required for `pytest`; a previously
  service-free suite gains an external service (accepted, T3). *Mitigation:* a session-scoped fixture
  starts one throwaway container, gated by a marker so pure-unit tests still run without it; document the
  one-liner in the venv/test notes.
- **[`psycopg[binary]` wheel on the immutable host]** → relies on a manylinux wheel. *Mitigation:* it is a
  pure binary wheel (no local compilation), unlike pycairo/PyGObject; pin a version and verify install in
  the venv rebuild recipe.
- **[Schema guessed ahead of 7b/7c needs]** → columns reserved for the scheduler/API might not fit exactly.
  *Mitigation:* every reserved column traces to an explicit T4 decision; a wrong guess is one additive
  Alembic migration, not a redesign.
- **[Reconcile without a worker is untestable end-to-end here]** → the requeue policy can't be exercised in
  this slice. *Mitigation:* test the *query* directly (seed an orphaned `running` row → assert it is
  returned); 7b tests the policy on top.
- **[Clock source]** → timestamps must come from the DB (`now()` / server default), not app wall-clock, to
  stay consistent across the worker and API processes.

## Migration Plan

1. Add deps (`sqlalchemy`, `alembic`, `psycopg[binary]`) and an `alembic/` tree with `env.py` reading the
   resolved `DATABASE_URL`.
2. One initial migration creates `jobs` (+ the status enum, indexes on `status` and `(status, priority,
   created_at)` for claim-next).
3. Ship a documented dev default (containerized PG) and the podman test fixture.
4. **Rollback:** the layer is additive and has no consumer yet (no scheduler/API); reverting is dropping
   the new modules/deps and the `jobs` table. No data migration risk because nothing authoritative lives
   here (D-P6).

## Open Questions

- **Running-cancel (rides into 7b):** whether the operator can cancel a *running* job (worker SIGTERMs the
  live ffmpeg) or only a `queued` one. The `canceled` state exists here regardless; the behavior is a 7b
  decision. *Current lean: include running-cancel.*
- **`event_dir` identity:** store the absolute path, or a project-root-relative key? Leaning
  root-relative so the DB survives a project move (consistent with rebuildable-from-disk). Settle when 7b
  wires enqueue from the CLI's `EventRef`.
- **Multiple projects in one DB:** does `jobs` need a `project_id`/root column now? Leaning yes as a
  nullable column (cheap, avoids a churn migration) — confirm against the 7c API's project model.
