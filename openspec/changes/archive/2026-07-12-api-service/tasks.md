## 1. Skeleton: deps, settings, factory, serve

- [x] 1.1 Add `fastapi` + `uvicorn` to `pyproject.toml` (pin versions); verify clean install in the
  `--system-site-packages` venv.
- [x] 1.2 Create `auto_reel_ng/api/settings.py`: `ApiSettings` (project root, layout, host, port,
  poll interval, database URL via `resolve_database_url`) resolved through D-2 layering (`api.*` keys,
  flag/env overrides, defaults `127.0.0.1:8080`, 1 s). Test precedence branches.
- [x] 1.3 Create the app factory (`auto_reel_ng/api/app.py`): `create_app(settings)` with the no-op auth
  middleware hook and `GET /healthz` (DB reachability check). Test: healthy path via TestClient + podman
  PG; DB-down path returns non-success naming the check; a registered token check rejects untokened
  requests with no route changes.
- [x] 1.4 Add `auto-reel serve` (`cli/main.py` + `cli/commands.py`): resolve settings, run uvicorn,
  graceful shutdown on SIGINT/SIGTERM, loud non-zero exit on bind failure. Update the entry-point
  help/usage test to eight subcommands; test flag-over-config port override and bind-failure exit.

## 2. Events read endpoints

- [x] 2.1 Pydantic response schemas (event summary, event detail with ordered chapters/clips + reconcile
  state, problem body) in `auto_reel_ng/api/schemas.py` — mirroring what `scan` prints, no new semantics.
- [x] 2.2 `GET /api/v1/events`: walk the configured layout per request (reuse the CLI's scan path); include
  per-event latest-job summary via one store query. Test against a fixture project: list matches `scan`,
  disk edits visible on next request.
- [x] 2.3 `GET /api/v1/events/{event_id:path}`: root-relative id → event dir; parse current `reel.yaml`
  (folder-name seeding like `scan`); 404 unknown; loud error (never fabricated/partial) on unparseable
  `reel.yaml`. Test detail shape, 404, error path, and URL round-trip with spaces + Swedish characters.
- [x] 2.4 `GET /api/v1/events/{event_id:path}/analysis`: read the sidecar cache; distinguish "never
  analyzed" from "analyzed, empty". Test both plus the populated case.

## 3. Jobs endpoints

- [x] 3.1 `POST /api/v1/jobs` (event id + optional device): store `enqueue` stamping the configured
  project root; 201 with job on create, **409 with existing id** on active duplicate. Test both, and
  that a terminal job doesn't block a new enqueue.
- [x] 3.2 `GET /api/v1/jobs` (status filter, oldest first) and `GET /api/v1/jobs/{id}` (full detail incl.
  requeue count); 404 unknown id. Test list filter + detail against seeded rows.
- [x] 3.3 `POST /api/v1/jobs/{id}/cancel` → `request_cancel`; response distinguishes flagged-running /
  canceled-queued / no-op-terminal. Test all three branches; assert the API never writes `status` itself.

## 4. WebSocket hub

- [x] 4.1 Implement the hub (`auto_reel_ng/api/ws.py`): subscriber registry with bounded per-connection
  queues; central poller task (dedicated single-thread executor for store calls) that starts with the
  first subscriber and stops with the last. Test poller lifecycle: no subscribers → no store queries.
- [x] 4.2 Snapshot-on-connect + diff/delta broadcast (progress changes and all status transitions incl.
  terminal, keyed by job id). Test with a stubbed store: snapshot shape, progress delta, terminal
  delta for a job that finished between ticks.
- [x] 4.3 Slow-consumer policy: full queue → disconnect; reconnect gets a fresh snapshot. Test the drop
  and the resync.
- [x] 4.4 End-to-end WS test over podman PG: seed a running job, advance `set_progress`/`transition`
  out-of-band, assert deltas arrive within ~one poll interval.

## 5. Closeout

- [x] 5.1 Docs: README section for `serve` (config keys, bind/auth posture, the thin-layer rule), module
  docstrings; scan-duration logging per events request (the D-A3 early signal).
- [x] 5.2 Full suite + lint green; dogfood on `auto-reel-media/`: `serve` + `worker` running, enqueue via
  `POST /jobs`, watch progress over WS, confirm output; record the result in the change notes.

  **Dogfood result (2026-07-12):** podman Postgres + `alembic upgrade head`, `auto-reel worker` and
  `auto-reel serve --poll-interval 0.3` against a copy of `auto-reel-media/input`. `GET /api/v1/events`
  matched the sample event exactly. `POST /api/v1/jobs` returned 201; a WS client connected to
  `/api/v1/ws/jobs` received the initial empty snapshot, then live deltas
  `queued -> running -> progress 0.8 -> progress 1.0 -> done`, each within one poll tick (0.3s). The
  rendered `2024-06-27 - Grillning med grannarna.mp4` (150s, ~848MB) exists and probes clean. Re-enqueuing
  the same event after the job reached `done` returned a fresh 201 (terminal jobs don't block). Caught and
  fixed one real gap during this run: bare `uvicorn` has no WebSocket implementation
  (`AutoWebSocketsProtocol` resolves to `None`) — added `websockets` as an explicit dependency; the WS
  route only "worked" before this under `TestClient`, which uses an in-process ASGI transport that doesn't
  need one.

  Also caught (via a ~1-in-6 flake hunting session running the WS tests in a loop, not the dogfood run
  itself) and fixed two shutdown-races: `JobsHub.stop()` called `executor.shutdown(wait=False)` before
  `engine.dispose()`, so a store call still in flight on the executor thread could race a closing
  connection pool — fixed by awaiting the cancelled poller task and shutting the executor down with
  `wait=True` first. The WS route also ran a sender + a "detect disconnect promptly" receiver task
  concurrently via `asyncio.wait(..., FIRST_COMPLETED)` + cancel-the-other; that pairing occasionally
  surfaced a `CancelledError` through the test client's own close handshake. Simplified to a single send
  loop that catches `WebSocketDisconnect` on a failed send — standard practice for a push-only channel,
  and it removed the race. 12/12 clean on a stress-loop re-run after both fixes.
