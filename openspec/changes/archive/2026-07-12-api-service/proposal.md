## Why

7a/7b delivered durable jobs and a worker, but the only way to observe or drive them is the CLI and raw
SQL — there is no surface a GUI (phase 8, §4.10) can talk to, and no live progress anywhere: the worker
writes throttled progress into Postgres and nothing pushes it out. This change completes phase #7 (§6
slice 7) with the **FastAPI service** (§4.9): REST over events and jobs plus a **WebSocket channel for
live job progress** — a deliberately thin layer where every endpoint maps to an operation the CLI already
reaches (§4.9's constraint), so no business logic moves into the web tier.

## What Changes

- Add a **FastAPI service** (`auto_reel_ng/api/`) serving a **single configured project root** (config/env
  at startup, mirroring the CLI's `--input-dir`; stamps the existing `project_root` job column; no
  `projects` table; unscoped `/api/v1/...` routes).
- **Event read model = scan-on-request**: `GET /api/v1/events` and `/events/{id}` walk the configured
  ingest layout and parse `reel.yaml` from disk per request — disk stays trivially authoritative (D-7);
  **no Postgres event index** (its first real user is phase 8/9 thumbnails/GUI scale). Read-only analysis
  results from the existing sidecar cache ride along (`GET /events/{id}/analysis`).
- **Jobs lifecycle over REST**, thin over the existing `JobStore`: enqueue (`POST /jobs`, idempotent like
  the store), list/get, and cancel (`POST /jobs/{id}/cancel` → `request_cancel`).
- **WebSocket live progress** (`/api/v1/ws/jobs`): a **central poller hub** — one asyncio task, ~1 Hz
  SELECT of active jobs, diffed and fanned out to subscribers; the poller runs only while subscribers
  exist. LISTEN/NOTIFY stays deferred (standing decision: revisit only if the GUI feels laggy — a robust
  NOTIFY needs a poll-resync anyway and 7b progress is already ≥1 s throttled).
- Add an **`auto-reel serve` subcommand** running the service under uvicorn (default bind `127.0.0.1`,
  configurable `api.host`/`api.port` via D-2 layering), keeping one operator surface alongside `worker`.
- **No auth in v1**: default-localhost bind plus a middleware seam so a bearer token is a drop-in later;
  widening the bind is an explicit operator choice.
- New deps: `fastapi`, `uvicorn`, (pydantic transitively) — pure wheels, no native-build pain. The sync
  SQLAlchemy store is used from sync `def` endpoints (FastAPI's threadpool); no async-ORM migration.

## Capabilities

### New Capabilities
- `api-service`: The FastAPI application — project-root configuration, scan-on-request event/analysis read
  endpoints, jobs lifecycle endpoints over the store, the WS progress hub with its subscriber-gated
  poller, bind/auth posture, and the thin-layer constraint (every endpoint CLI-reachable).

### Modified Capabilities
- `headless-cli`: The `auto-reel` entry point gains a `serve` subcommand (eight subcommands total).

## Impact

- **New modules**: `auto_reel_ng/api/` (app factory, routes, pydantic schemas, WS hub/poller, settings).
- **CLI**: `serve` subcommand in `cli/main.py`/`cli/commands.py`.
- **`pyproject.toml`**: add `fastapi`, `uvicorn`, `websockets` (bare `uvicorn` ships no WebSocket
  implementation of its own — `uvicorn[standard]` pulls in far more than needed here); dev-only
  `pytest-asyncio`, `httpx` (FastAPI's `TestClient`).
- **`config.yaml`**: optional `api.host`/`api.port`/`api.poll_interval` keys (D-2 layering; flags override).
- **Reuses unchanged**: ingest layouts + `load_document` (event reads), the analysis sidecar cache reader,
  `JobStore` (`enqueue`/`get`/`list_by_status`/`request_cancel`), `resolve_database_url`. **No engine, no
  migration changes** — `JobStore` gains one additive, read-only method (`latest_by_project`, one indexed
  query, no schema change) backing the events-list job-summary enrichment (D-A3); everything below that
  stays untouched.
- **Tests**: FastAPI TestClient over fixture projects + podman PG; WS hub tests with a stubbed clock/store.

## Non-goals

- **No editorial writes.** Reorder/trim/metadata mutations to `reel.yaml` (and §4.7 GUI⇄yaml sync
  semantics) land with GUI v1 (phase 8), where a real consumer exercises them. 7c events/clips are
  read-only.
- **No Postgres event index** (§4.7) — deferred to its first real user (thumbnails/GUI scale, phase 8/9).
- **No LISTEN/NOTIFY** — standing decision; central poller until the GUI proves laggy.
- **No auth/user model** — localhost-default bind + token seam only.
- **No multi-project model** — one configured root; the `project_root` column keeps multi-project additive
  later.
- **No GUI** (phase 8), **no change detection** (§8.14/T1 still parked), **no scheduler/engine changes**.
