## Why

`auto-reel serve` has two exit-path gaps, both recorded by the archived `serve-clean-exit` change and
re-checked against `main` (ac30bc2, uvicorn 0.51.0):

- **A second Ctrl+C does not force the exit while a client connection is open.** A client that sent the
  headers of a `POST /api/v1/jobs` and part of its body, then went quiet, keeps `serve` running through
  any number of SIGINTs: the log ends at "Waiting for connections to close. (CTRL+C to force quit)" and
  the process was still up 8 s later (triage repro; re-run for this change with a scratch ASGI server, see
  design). Same for a peer that stopped reading with frames backed up (measured: 5 s later still
  waiting). The README and two specs currently document this as expected; it is a defect in what "force"
  means, not a limit to document.
- **A failed application shutdown makes `serve` exit 0.** uvicorn logs "Application shutdown failed.
  Exiting." and returns normally. Before `ServiceServer` swallowed the re-raised signal the exit happened
  to be non-zero; now it is 0. The path is latent (today's lifespan cannot raise at shutdown) and was
  accepted as a gap at the time, but the status is the only thing a supervisor sees and the fix is about
  20 lines of ASGI-protocol code.

## What Changes

- `serve`'s forced stop (a SIGINT during the shutdown) drops every client connection still open, so
  uvicorn's connection wait ends and the existing `os._exit(130)` path runs within a few seconds,
  whatever the clients do.
- `serve` watches the ASGI lifespan messages and exits 1 when the application's lifespan startup or
  shutdown failed (a forced stop keeps 130).
- The serve machinery (`ServiceServer`, the forced-stop exit, the new lifespan watch) moves to a new
  `cli/serving.py` so `commands.py`, at 969 of pylint's 1000 lines, has room. `commands.ServiceServer`
  stays importable (tests patch it there).
- README's `serve` stop paragraph and the two requirements that said a forced stop still waits for
  connections are corrected.
- No render-affecting change: `RENDER_GRAPH_VERSION` is not bumped.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `headless-cli`: "`serve` runs the API service" - a forced stop also ends open client connections and
  exits 130 within a few seconds; a failed lifespan startup or shutdown exits 1; four new scenarios.
- `api-service`: "WebSocket live job updates" - a second SIGINT now ends the stall behind a vanished
  peer instead of leaving it; one new scenario.

## Impact

- `auto_reel_ng/cli/serving.py` (new), `auto_reel_ng/cli/commands.py` (serve code moved out, `cmd_serve`
  wraps the app and reads the watch), `README.md`.
- Tests: `tests/test_cli_serve_signals.py` (new child-process cases and unit cases for the watch),
  `tests/test_cli_serve.py` (`cmd_serve` exit-status cases).
- Builds on `cli-batch-isolation-and-claims` and `cli-project-context-module` (both on `main`, they edited
  `commands.py` elsewhere). No overlap in the `serve` section.
