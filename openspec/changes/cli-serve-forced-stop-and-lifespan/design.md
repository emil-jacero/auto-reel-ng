## Context

`serve` runs `ServiceServer` (a `uvicorn.Server` subclass in `cli/commands.py`). Its `run()` ends the
process with `os._exit(130)` after uvicorn returns when `force_exit` is set, and `cmd_serve` returns
`130 if server.force_exit else 0` (off the main thread, in-process tests). See the archived
`serve-clean-exit` design ("Force-quit still waits for open connections" and "A failed application
shutdown") for the measurements that recorded both gaps as accepted follow-ups.

Re-checked against `main` ac30bc2 with uvicorn 0.51.0 (`.venv`; the shutdown code is identical in 0.54.0
per the archived review):

- `Server.shutdown()` closes the listening servers, calls `connection.shutdown()` on each connection, and
  awaits `_wait_tasks_to_complete()`. That method's two wait loops honour `force_exit`, but it ends with
  `for server in self.servers: await server.wait_closed()` unconditionally. Since Python 3.12.1
  `wait_closed()` returns only when every connection the server accepted has been detached. A connection
  whose client is idle (half-sent request, peer not reading) never is. So a second SIGINT sets
  `force_exit`, skips the loops and then blocks here; `ServiceServer.run` is never reached.
- `handle_exit` only sets flags (`should_exit`, `force_exit`) and appends to `_captured_signals`.
- On a shutdown that raises, Starlette sends `lifespan.shutdown.failed`; uvicorn's `LifespanOn` logs
  "Application shutdown failed. Exiting." and `Server.serve()` returns normally. `lifespan.startup.failed`
  likewise sets `should_exit` and returns normally. `cmd_serve` sees neither.
- `cli/commands.py` is 969 lines against pylint's 1000-line cap. Adding ~45 lines of serve code there does
  not fit.

Prototype in the session scratchpad (`verify/bugs/cli-serve-forced-stop-and-lifespan/proto.py`, a
`uvicorn.Server` subclass with the same `capture_signals` override as `ServiceServer`, a scratch ASGI app,
SIGINT twice, 5 s budget):

| Client | Today | With `abort_clients()` in the wait |
|---|---|---|
| `POST` headers + 6 of 100 body bytes, held open | still up at 5 s ("Waiting for connections to close") | exit 130 |
| `GET` of 16 MiB, receive buffer 4 KiB, never read | still up at 5 s | exit 130; log shows the cut handler's `CancelledError` traceback (already permitted by the spec) |
| app lifespan sends `lifespan.shutdown.failed`, one SIGINT | exit 0 after "Application shutdown failed. Exiting." | watch records it; exit 1 |

## Goals / Non-Goals

**Goals:**
- A second Ctrl+C always ends `serve` (status 130) within a few seconds, whatever the clients do.
- A failed application lifespan, startup or shutdown, is a non-zero exit status.
- Both behaviours are tested through `serve` in a process of its own, so a uvicorn rename fails loudly.

**Non-Goals:**
- A single SIGINT/SIGTERM still waits for running handlers and open connections. Only the forced stop
  changes. No graceful-shutdown timeout is added.
- No change to what the lifespan does. Making `JobsHub.stop` log-and-continue (the triage's alternative)
  would hide a real failure; the watch makes it visible instead.
- A request handler running in a worker thread is still abandoned by `_end_forced_stop`, not stopped.
- Chapter and render behaviour; `RENDER_GRAPH_VERSION` is untouched (no rendered output changes).

## Decisions

### D1. Abort the clients from inside uvicorn's wait, once forced

`ServiceServer` overrides `_wait_tasks_to_complete`. It starts `super()._wait_tasks_to_complete()` as a
task and loops: while the task is not done, if `force_exit` is set, call `abort_clients()` on every server
in `self.servers`, then wait up to 0.1 s for the task. Once the connections are detached, `wait_closed()`
returns, `shutdown()` skips the lifespan step (already the case when forced), `run()` sees
`force_exit` and calls `_end_forced_stop()`, unchanged.

- `asyncio.Server.abort_clients()` (Python 3.13, the project's floor) is public API and aborts exactly the
  connections that `wait_closed()` waits on. It drops any pending write buffer, which is what a peer that
  stopped reading needs; `close_clients()` would wait for the buffer to drain and not help.
- Polling every 0.1 s, not a one-shot abort, covers a connection accepted between the force and the
  listener closing, and a force that arrives before the wait starts. uvicorn's own loops poll at 0.1 s.
- Alternatives rejected:
  - **Abort in `handle_exit`.** It runs as a signal handler between bytecodes of the event loop; touching
    transports there is unsafe, and it needs `call_soon_threadsafe` and a loop reference to be safe. It
    also misses connections that appear later.
  - **Abort every `server_state.connections` transport by hand** (the triage sketch). Works, but reaches
    into uvicorn's protocol objects (`.transport`) where `abort_clients()` is public.
  - **Skip `wait_closed()`** by overriding `shutdown`: duplicates uvicorn's shutdown body and leaves the
    connections open when the loop is torn down.
  - **Cut connections at the first signal / a graceful timeout.** Changes the one-signal contract the
    clean-exit change fixed; out of scope.
- The override is of a private uvicorn method. The new child-process tests are the guard: if uvicorn
  renames it, the override stops being called and the half-sent-request test hangs and fails on its own
  5 s budget (never the whole suite). The existing `capture_signals` override takes the same trade.

### D2. A lifespan watch, outside uvicorn internals

A small ASGI wrapper class, `LifespanWatch(app)`, with an async `__call__` that forwards every scope
unchanged. For the `lifespan` scope it hands the app a `send` that notes `lifespan.startup.failed` and
`lifespan.shutdown.failed` and then forwards the message. `failed` is a plain attribute. `cmd_serve` wraps
the app it builds, passes the wrapper to `uvicorn.Config`, and returns `130 if server.force_exit else 1 if
watch.failed else 0`.

- Uses only the ASGI lifespan protocol. Alternative `server.lifespan.shutdown_failed` is an untyped uvicorn
  internal (the archived design rejected it for the same reason).
- Startup failure is covered by the same hook because it has the same outcome (uvicorn returns normally
  and the command would exit 0), costs one more message type, and keeps the requirement symmetric. It is
  not reachable from today's lifespan either; both are tested with a failing scratch app.
- Precedence: a forced stop skips the application shutdown, so the two rarely meet. When they do,
  130 wins, and on the main thread the process has already ended with it.
- `uvicorn.Config.load()` decides the ASGI interface from the app's callable; an instance with an async
  `__call__` is ASGI3 (checked in the prototype).

### D3. The serve code moves to `cli/serving.py`

`ServiceServer`, `_end_forced_stop` and `LifespanWatch` live in `cli/serving.py`; `commands.py` imports
`ServiceServer` and `LifespanWatch` (so `commands.ServiceServer` stays the patch point the tests use) and
keeps `cmd_serve`. This is a move, not a rewrite, and lands as its own task first so the diff of the
behaviour change is readable. `cli/` is the only package touched.

### D4. Test shape

Real `serve` child processes started as a terminal starts them (the existing `_AS_FROM_A_TERMINAL`
launcher), on a free port, with the stalled-database URL so no Postgres is needed:
- half-sent `POST /api/v1/jobs` held open on a raw socket; SIGINT, wait for "Waiting for connections to
  close", SIGINT; `wait(timeout=5)` gives 130, and the client socket is still open.
- a launcher variant that swaps `commands.create_app` for a scratch ASGI app: one route streaming 16 MiB
  to a raw client with a 4 KiB receive buffer that never reads (the peer-stopped-reading scenario), and a
  second app whose lifespan raises at shutdown (SIGTERM and SIGINT: rc 1, "Application shutdown failed" in
  the log) or at startup (rc 1, no signal needed).
- unit tests for `LifespanWatch` itself (non-lifespan scopes pass through untouched, `complete` messages
  are not failures, the message is forwarded to uvicorn).

## Risks / Trade-offs

- **In-flight requests are cut on a forced stop** → That is what a force-quit is; the spec already allows
  the cut handler's traceback in the log. A sync handler already running in a worker thread is abandoned
  as before.
- **Private-method override** → See D1; guarded by e2e tests, mirrors `capture_signals`.
- **uvicorn versions** → `pyproject` pins `uvicorn>=0.51.0`; behaviour verified on 0.51.0, the archived
  review verified the shutdown code is the same on 0.54.0. The implementation re-runs the child tests on
  whichever versions are installed.
- **`abort_clients()` is 3.13+** → The project requires Python >= 3.13.
- **Rebase surface** → both prerequisite changes are already on `main`; the `serve` block is cut out
  wholesale, so a conflict with later `commands.py` edits is limited to the imports block.
