## Why

`JobsHub.stop()` is the first step of the service's orderly shutdown (D-A7: the app lifespan calls
`await jobs_hub.stop()` and then `engine.dispose()`; HLD §4.10). It was written on the assumption that the
database answers. When it does not, `stop()` and the whole event loop go with it. Re-checked against `main`
at `6a7fe16` with the triage's repro (a fake store whose `list_by_status` blocks 20 s):

1. **A stalled poll tick freezes the loop.** `stop()` cancels the poller task, then calls
   `self._executor.shutdown(wait=True)` (`api/ws.py:169`). That is a synchronous join of the executor
   thread, run on the event loop, so every request, every WebSocket and uvicorn's own shutdown wait until the
   blocked store call returns: an `asyncio.sleep(2)` after `stop()` took 19.7 s.
2. **A stalled first subscribe makes `stop()` never return, and keeps the service from reaching it.**
   `subscribe()` holds `hub._lock` while it awaits the first subscriber's seed reads (`_start_polling`,
   `ws.py:111-113`), and `stop()` begins with `async with self._lock` (`ws.py:159`). Nothing can cancel the
   seed from `stop()`. Worse, in the running service `stop()` is not even reached: the `ws_jobs` handler is
   parked inside `await hub.subscribe()` and reads no frames, so it never sees the client's close or the
   server's own 1012 close, and uvicorn waits for that handler to end before it runs the lifespan shutdown
   (measured on the repo's uvicorn: a WebSocket handler that sleeps 6 s without reading held
   `Server.serve()` and the lifespan shutdown for 5.8 s after `should_exit`). The same park holds a client
   that closes its tab during the stall until the database answers.
3. **No connection ever times out.** `make_engine` is `create_engine(url, future=True)`
   (`persistence/engine.py:20`): no `connect_args`, so libpq has no `connect_timeout` and a database host that
   drops packets is waited on for as long as the operating system's TCP timeouts allow (minutes). This is the
   stall behind 1 and 2 in practice, and it equally stalls `worker`, every REST route that touches the store,
   and the CLI's job commands.

The headless-cli and api-service specs promise that one SIGINT or SIGTERM ends the service "within a few
seconds, however many connections are open" (`jobs-ws-lifecycle`, `serve-clean-exit`). A database outage is
exactly when an operator restarts the service, and today that restart hangs.

HLD §6 phase 7 delivered the service and the hub; this is a phase 8 polish-round fix. It depends on no open
§8 research item.

## What Changes

- **`JobsHub.stop()` never waits on the database.** It signals first (a stopping flag, the in-flight first
  subscribe's seed and the poller cancelled) and only then takes the lock to close subscribers; it releases
  the executor without joining it (`wait=False`, queued work cancelled), so the event loop is never blocked.
  A store call already running on the executor thread is abandoned, not awaited.
- **A subscriber that was waiting on the stalled seed is let go** with the hub's normal "try again later"
  (close 1013), and a subscriber that arrives after `stop()` is refused the same way. Neither hangs nor sees
  an internal error.
- **The `ws_jobs` handler watches the connection while its first subscribe is stalled.** A client close, a
  lost peer or the server's shutdown close during the seed abandons the subscribe at once (releasing the hub
  lock and the seed), so the handler ends and uvicorn reaches the lifespan's `hub.stop()`. Today it ends
  only when the database answers.
- **Postgres connections give up connecting after 5 s.** `make_engine` passes `connect_timeout=5` (module
  constant, no config key) for Postgres URLs, unless the URL itself sets `connect_timeout`. The failure
  surfaces as the driver's `OperationalError` through the existing paths (a 5xx on a REST route, a
  per-poll error in the worker), instead of a minutes-long hang.
- **Tests.** Hub: a store that blocks 20 s must not stop `stop()` or the loop from returning within about one
  second, in both stall positions (a poll tick; the first subscribe). Service (real `uvicorn.Server`): a stop
  or a client close while the first subscribe is stalled completes within about one second. Engine: the 5 s bound is passed, an
  explicit URL value wins, and a peer that accepts but never answers makes `connect` fail at the bound.
- **Spec:** the api-service WebSocket requirement states that the hub's stop does not wait on the database;
  the persistence spec gains the connect-timeout requirement. README's `serve` stop paragraph gains the
  stalled-database sentence.

## Non-goals

- **No bound on a query that has already started.** `connect_timeout` limits connecting only. An
  established connection whose server stops answering mid-query is bounded by TCP only. No `statement_timeout`,
  no TCP keepalive or `tcp_user_timeout`: they would also bound the worker's legitimate queries and need their
  own decision (Principle VII; the triage said "consider"). Consequence, stated in the spec: the *process* still
  waits at interpreter exit for such a thread, because executor threads are joined then; the lifespan, the loop
  and the other connections do not.
- **No config key for the timeout** (a module constant, as for the thumbnail timeout).
- **No heartbeat, reaper or retry** around the store; no change to the poll cadence or frame shapes.
- **No change to `unsubscribe` outside shutdown**, or to the single-thread executor design (D-A5).
- **No change to `worker`, the scheduler or the REST routes.** They gain the connect bound only through
  `make_engine`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: `Requirement: WebSocket live job updates` states that stopping the service does not wait for
  the database: a stalled store read (a poll, or the first subscriber's snapshot) neither blocks the event
  loop nor holds the shutdown, a subscriber waiting on it is closed with 1013, and the only thing left waiting
  on such a read is the process's exit.
- `persistence`: new `Requirement: Postgres connections fail fast`: connecting to Postgres gives up after
  5 s, an explicit `connect_timeout` in the URL wins, and the failure is the driver's error, not a hang.

## Impact

- **Baseline:** written against `main` at `6a7fe16`. No gate change touches `api/ws.py` or `persistence/engine.py`
  first; `api-ws-heartbeat` is gated on this change (it edits `ws.py` after this merges).
- **Packages:** `api/` (`ws.py` only: the hub's `stop()`/`subscribe()` and the `ws_jobs` handler; `app.py` is
  read, and needs no edit because its lifespan already calls `hub.stop()` then `engine.dispose()`) and `persistence/` (`engine.py`). Tests: `tests/test_api_ws_lifecycle.py`,
  `tests/test_persistence_engine.py`.
- **CLI vs API (Principle V):** the engine change is shared by both, since `make_engine` is the one factory
  (`cli/commands.py`, `api/app.py`, `scripts/make_dev_library.py`). The hub is API-only by nature (WebSocket
  fan-out); no engine behavior is added to `api/`.
- **Complexity (Principle VII):** one module constant, a stopping flag and a start-task handle in the hub, and a two-task wait in the handler. No
  dependency.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Staleness fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. OpenAPI schema and
  `web/openapi.json` unchanged.
- **Operators:** a database host that silently drops packets now yields connection errors after 5 s rather
  than a minutes-long hang; a healthy or refusing database behaves as before.
- **Size (Principle VIII):** two capability deltas, two packages, 8 tasks (one validation, one docs).
