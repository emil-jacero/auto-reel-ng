## Context

7a/7b left a complete headless pipeline: durable jobs (`JobStore`), a worker with capacity pools and
requeue, and CLI surfaces (`enqueue`/`worker`/`jobs`). Progress lives in Postgres, ≥1 s/≥1 % throttled by
the worker's `ThrottledProgress`. The 2026-07-12 explore session settled 7c's five forks (memory:
`auto-reel-ng-phase7-decisions`): scan-on-request reads, central poller hub, no editorial writes, single
project root, no auth. §4.9's constraint frames everything: the API is a thin layer with no business
logic the CLI can't also reach.

## Goals / Non-Goals

**Goals:**
- REST: events/clips read model (from disk), analysis read model (from sidecar cache), jobs lifecycle
  (enqueue/list/get/cancel) over the existing store.
- WS: live job status+progress pushed to subscribers within ~1 s of a store write.
- `auto-reel serve` runs it; config via `api.*` keys + flags (D-2).
- Every endpoint's behavior identical to its CLI counterpart (same scan, same idempotent enqueue, same
  cancel semantics).

**Non-Goals:** editorial writes, event index, NOTIFY, auth, multi-project, GUI, engine/store/migration
changes (see proposal).

## Decisions

### D-A1 — App factory + settings object; no import-time globals
`create_app(settings)` builds the FastAPI app from an `ApiSettings` (project root, layout, host/port, DB
URL via `resolve_database_url`, poll interval). *Why:* TestClient tests construct apps against fixture
roots/containers without env juggling; `serve` resolves settings through the same D-2 layering as
`worker`. *Alternative rejected:* module-level app + env reads at import (untestable, hides config).

### D-A2 — Event identity in URLs = the root-relative event dir, URL-encoded
`GET /events/{event_id}` uses the same root-relative `event_dir` string the job store already uses as
identity (e.g. `2024/2024-06-21 - Midsummer`). *Why:* one identity everywhere — job rows, CLI output, and
API URLs agree; no new id scheme, no index table to mint surrogate keys. Path-encoding is handled by
routing (`:path` param). *Alternative rejected:* hash/surrogate ids — require a lookup table (the index we
deferred) or recomputation, and diverge from what `jobs` rows display.

### D-A3 — Scan-on-request with per-request freshness, no caching
Every events read walks the layout and parses `reel.yaml` now. *Why:* family-archive scale (dozens of
events) costs milliseconds; zero staleness; D-7 trivially holds. Deliberately **no** response cache until
measured need — a cache is the first step back toward the index/staleness problem §8.14 parks.
The read model returns what `scan`/`show` print: metadata, chapters/clips with order, NEW/MISSING
reconcile state — plus job summary (latest active/terminal job per event, one indexed store query) so the
GUI's main screen is one GET.

### D-A4 — WS hub: subscriber-gated central poller, diff-push, snapshot-on-connect
One asyncio task polls active jobs (`queued`+`running`, plus jobs that changed status since the last tick)
at `api.poll_interval` (default 1 s) **only while ≥1 subscriber is connected**; it diffs against its last
snapshot and broadcasts JSON deltas. A new subscriber immediately receives a full snapshot, then deltas.
Slow consumers get best-effort delivery: per-connection bounded queues; a full queue drops the connection
(the client reconnects and resyncs via snapshot) rather than back-pressuring the hub. *Why snapshot+delta:*
reconnect/resync is free (the failure path is the connect path); the GUI never needs to merge REST+WS
state. *Alternatives rejected:* per-connection pollers (N× queries); NOTIFY (standing decision — contains
this poller anyway as its resync path).

### D-A5 — Sync store under async FastAPI: sync endpoints, threadpool
REST endpoints are sync `def` (FastAPI runs them in its threadpool); the WS poller calls the store via
`run_in_executor`/`to_thread`. *Why:* the 7a store is sync SQLAlchemy and proven; an async-ORM migration
buys nothing at this scale. The session-per-request pattern reuses `session_scope`. *Alternative rejected:*
SQLAlchemy async engine — new dialect (`psycopg` async), new fixture semantics, zero user-visible gain.

### D-A6 — Errors: RFC-ish problem JSON, engine errors mapped, fail-loud preserved
404 for unknown event/job; 409 surfaced explicitly when enqueue hits an existing active job (body carries
the existing job id — mirrors the store's idempotent-return, but the API makes the "already queued" case
visible rather than silently 200); 422 pydantic validation; scan/probe `EngineError` → 502-style problem
body naming the failing event (never a fabricated empty result — the no-fake-metadata rule extends to the
API). *Why 409-with-id over silent 200:* a GUI needs to distinguish "created" from "already pending" to
message the user; both carry the id so clients can treat them uniformly when they don't care.

### D-A7 — `serve` subcommand; uvicorn as the only server path
`auto-reel serve [--host] [--port]` resolves `ApiSettings` (D-2: `api.host`/`api.port`/`api.poll_interval`
config keys, flags override, default `127.0.0.1:8080`) and runs uvicorn programmatically. SIGINT/SIGTERM →
uvicorn's graceful shutdown; the hub poller is cancelled cleanly. *Why a subcommand:* one operator surface
(`worker` precedent); the app-factory still supports bare `uvicorn --factory` for development.

### D-A8 — Auth seam, not auth
A single middleware hook point (no-op in v1) where a static-bearer-token check can be registered; default
bind localhost; widening documented as an explicit operator action. *Why:* keeps v1 honest (LAN,
Istio/Tailscale-fronted if ever exposed) while making the future token a config key, not a refactor.

## Risks / Trade-offs

- **[Scan cost grows with library size]** → Accepted at current scale; if a GET ever feels slow the answer
  is the phase-8/9 index, not an API cache (decided). Log scan duration per request for early signal.
- **[Poller misses short-lived states]** → A job that goes queued→running→done inside one tick shows only
  the final state. Accepted: deltas carry the latest row, terminal states always emitted (diff includes
  status transitions since last snapshot, keyed by job id).
- **[WS + threadpool starvation]** → Heavy concurrent scans could exhaust the default threadpool and
  starve the poller's executor calls. Mitigation: poller uses its own single-thread executor; scan
  endpoints are the only heavy sync work and stay bounded by request concurrency.
- **[Unbounded WS fanout]** → Single-operator reality makes this theoretical; bounded per-connection
  queues + drop-and-resync keep the hub O(subscribers) with no slow-consumer memory growth.
- **[`event_id` path params with spaces/unicode]** → Event dirs contain spaces and Swedish characters;
  tests must cover encoded round-trips (URL ↔ `event_dir` ↔ disk path).
- **[Port collision / bind failures]** → `serve` fails loud with the attempted host:port, exits non-zero.

## Migration Plan

1. Deps + `api/` skeleton (settings, factory, health route) + `serve` subcommand — deployable no-op.
2. Events read endpoints, then jobs endpoints (each independently testable against fixtures/podman PG).
3. WS hub last (depends on jobs read model for its snapshot shape).
4. **Rollback:** fully additive — remove the module/subcommand/deps; nothing below the web tier changed.

## Open Questions

- **Analysis endpoint shape:** expose the raw sidecar segments as-is (lean — it's a read-only cache dump)
  or normalized per-clip? Settle when writing the route; keep the sidecar schema as the contract.
- **Health/readiness:** `/healthz` checking DB reachability (lean: yes, trivial and the deploy story wants
  it) — confirm during implementation.
- **OpenAPI surface freeze:** FastAPI autogenerates `/docs`; decide whether the schema is a committed
  artifact (snapshot-tested) now or after the GUI stabilizes it (lean: after — phase 8 will churn it).
