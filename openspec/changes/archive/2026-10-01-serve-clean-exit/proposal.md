## Why

`auto-reel serve` is the whole deployment of the service (HLD §4.10, D-8), and its stop is specified twice:
**D-A7** (api-service design: "SIGINT/SIGTERM → uvicorn's graceful shutdown") and the headless-cli requirement
"`serve` runs the API service", which promises a graceful shutdown with **exit zero**. The orderly part works:
since `jobs-ws-lifecycle`, one signal closes every WebSocket with 1012 and the log reaches "Application
shutdown complete". The exit does not. After that shutdown uvicorn raises the signal it caught a second time,
for the handler that was installed before it:

- **SIGINT (Ctrl-C):** that handler is asyncio's, so the operator gets a `KeyboardInterrupt` traceback through
  `cli/commands.py` `server.run()` and the process dies by SIGINT (a shell shows 130).
- **SIGTERM (`kill`, `systemctl stop`, `podman stop`):** that handler is the default, so the process is killed
  by SIGTERM (143) after it has already shut down cleanly.

Reproduced on a throwaway `serve` (port 8120, own Postgres container) with the repo's uvicorn 0.51.0, and by
the final end-to-end pass on 0.54.0; both versions carry the same `capture_signals` code (design, "Research &
Decisions"). The final pass reported it as a failure, and `tests/test_cli_serve.py` deliberately does not
assert the return code (`jobs-ws-lifecycle` design, Risks: "Pre-existing: signal exit status"). A clean stop
that looks like a crash violates HLD §4.11 ("keeps automation/CI working") and Principle I in reverse: the
exit status must tell the truth, so a supervisor, a script or the operator can tell a clean stop from a
failure.

HLD §6 **phase 7** delivered `serve`; this is part of phase 8's v1 polish round (the `jobs-ws-lifecycle`
follow-up it named for `cli/`). It depends on no open §8 research item.

## What Changes

- **One SIGINT or SIGTERM ends `serve` with exit status 0 and no traceback** once the orderly shutdown has
  completed, with or without WebSocket clients, in a terminal or under a supervisor. Nothing about the
  shutdown itself changes: clients still get 1012, the poller stops and the database connections are
  released first.
- **A forced exit is reported as interrupted, not as success.** uvicorn's own force-quit stays: a second
  SIGINT while the shutdown is still waiting ends its wait for running request handlers and skips the
  application shutdown. The command then exits **130** without a `KeyboardInterrupt` traceback, instead of today's traceback, or of a
  death by SIGTERM when the first signal was a SIGTERM. A further SIGTERM still does not force anything.
- **The bind failure is unchanged:** exit 1 with `error: could not bind <host>:<port>`.
- **Tests assert the return code.** The signal end-to-end test starts `serve` with SIGINT and SIGTERM at
  their terminal defaults, so it cannot pass by inheriting an ignored signal from a background shell, and
  asserts exit 0 and no traceback for both signals. New in-process tests pin that a handled signal is not
  raised again, that a second SIGINT still forces, and, as a canary, that plain uvicorn still re-raises.
- **Spec:** "`serve` runs the API service" states the exit status of an orderly and of a forced stop, with
  scenarios for each, and that a forced stop still waits for its client connections to end.
- **A second Ctrl+C is no longer said to end a stall behind a vanished peer** (supervisor decision). The
  api-service requirement "WebSocket live job updates" and README said it forces the exit. It does not:
  with frames backed up to a peer that stopped reading, a second and a third SIGINT left `serve` running
  until that connection ended (measured on uvicorn 0.51 and 0.54). For a vanished peer that is when the
  host's TCP stack abandons the connection, which can take many minutes, and the force only skips the
  application shutdown (design, "Force-quit still waits for open connections"). Both now say so, with no
  figure for the wait: none was reproduced.
- **Docs:** README's `serve` stop paragraph gains the exit statuses and the corrected vanished-peer
  sentence.

## Non-goals

- **No change to what a forced exit waits for.** On Python ≥ 3.12 uvicorn's force-quit still awaits
  `asyncio.Server.wait_closed()`, which waits for every client connection to close. A client that keeps a
  request open therefore holds the process through a second and a third Ctrl-C (measured; design, "Force-quit
  still waits for open connections"). That is pre-existing, is not what the finding reports, and needs its own
  decision on cutting in-flight requests; it is proposed as a follow-up. This change only corrects the
  sentences that said otherwise.
- **No exit-status check of the application shutdown.** uvicorn logs a lifespan shutdown that raises and
  returns normally, so such a failure would exit 0 with the error in the log. Today's lifespan cannot raise
  at that point (measured; design, "A failed application shutdown"), and the supervisor accepted the gap.
- **No `timeout_graceful_shutdown`** and no new flag or config key (Principle VII); `jobs-ws-lifecycle`'s
  reasons stand.
- **No change to a Ctrl-C before the server runs** (while the app is being built): it still ends as an
  ordinary `KeyboardInterrupt`. It is not an orderly shutdown, and the window is short.
- **No change to `worker`**, whose own handlers already exit zero.
- **No change to `api/`** or to the WebSocket lifecycle. The api-service spec changes only its sentence on a
  vanished peer's stall, to what the service already does.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `headless-cli`: `Requirement: \`serve\` runs the API service` states that an orderly stop by one SIGINT or
  SIGTERM exits zero without a traceback, that a further SIGTERM does not change that, and that a forced stop
  (a second SIGINT) exits 130 once its client connections have ended.
- `api-service`: `Requirement: WebSocket live job updates` no longer says that a second SIGINT forces the
  exit past a vanished peer with frames backed up. The stall lasts until the host's TCP stack abandons that
  connection, and a second SIGINT only skips the application shutdown. Text only; no behavior changes.

## Impact

- **Baseline:** written against `main` at `bca64f2`.
- **Packages:** `cli/` only: `commands.py` gains a small `uvicorn.Server` subclass used by `cmd_serve`, and
  `cmd_serve` returns 130 after a forced stop. Tests: `tests/test_cli_serve.py` (fakes re-pointed, return code
  asserted, forced-exit case) and a new `tests/test_cli_serve_signals.py` (no database). Docs: `README.md`.
  The api-service delta is spec text only.
- **CLI vs API (Principle V):** CLI only. The API app, its lifespan and its routes are untouched.
- **Complexity (Principle VII):** a subclass of about ten lines that relies on two uvicorn internals
  (`Server.capture_signals` and its `_captured_signals` list). Both are checked by strict mypy (`@override`
  and the attribute lookup fail if uvicorn renames them) and by a canary test that fails when uvicorn stops
  re-raising, so the subclass is deleted rather than left behind. The alternatives are in the design.
- **Dependencies:** none added; `uvicorn>=0.51.0` stays.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Staleness fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. OpenAPI schema and
  `web/openapi.json` unchanged.
- **Operators:** `serve` under systemd, podman or a shell now reports a clean stop as 0. A shell script that
  runs `serve` and then more commands continues after Ctrl-C instead of stopping (design, Risks).
- **Size (Principle VIII):** two capability deltas (headless-cli; api-service, text only), one package,
  7 tasks (one baseline check, two validation).
