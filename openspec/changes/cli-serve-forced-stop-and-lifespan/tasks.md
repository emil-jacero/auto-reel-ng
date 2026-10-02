## 1. cli/ - make room, then force the stop

- [x] 1.1 Move `ServiceServer` and `_end_forced_stop` unchanged from `cli/commands.py` into a new
  `cli/serving.py`, and import `ServiceServer` back into `commands.py` (so `commands.ServiceServer` stays the
  name tests patch and `cmd_serve` uses). Update the `os`/`signal`/`socket`/`threading` imports that
  `commands.py` no longer needs. Verify: `.venv/bin/python -m pytest tests/test_cli_serve_signals.py
  tests/test_cli_serve.py -m "not requires_db"` and the same files with the DB tests pass as before, and
  `wc -l auto_reel_ng/cli/commands.py` is under 940.
- [x] 1.2 Red first, in `tests/test_cli_serve_signals.py`: a child-process test holding a half-sent
  `POST /api/v1/jobs` open on a raw socket (headers with `Content-Length: 100`, 6 body bytes), using the stalled
  database URL and the `_SERVE` launcher. Send SIGINT, `_wait_for_log` "Waiting for connections to close",
  send SIGINT again, `process.wait(timeout=5)`; assert `returncode == 130`, the client socket is still open,
  no "KeyboardInterrupt" and no "Application shutdown complete" in the log. Verify: it fails today with the
  5 s timeout (process still up), and the failure is not the whole suite hanging.
- [x] 1.3 In `cli/serving.py`, override `ServiceServer._wait_tasks_to_complete`: run
  `super()._wait_tasks_to_complete()` as a task; while it is not done, once `force_exit` is set call
  `abort_clients()` on each of `self.servers`, then wait up to 0.1 s for the task (design D1). Docstring says
  why (uvicorn awaits `wait_closed()` even when forced). Verify: the 1.2 test passes; the existing
  `test_a_forced_stop_does_not_wait_for_a_handler_in_a_worker_thread` and
  `test_a_late_signal_does_not_change_the_exit_status` still pass.
- [x] 1.4 Add the peer-that-stopped-reading case in the same file: a launcher variant that replaces
  `commands.create_app` with a scratch ASGI app streaming 16 MiB to `GET /big`, a raw client with
  `SO_RCVBUF` 4096 that requests it and never reads, then the SIGINT/SIGINT sequence. Verify:
  `returncode == 130` within 5 s of the second SIGINT with the client socket still open (this test hangs and
  fails on its 5 s timeout when 1.3's override is removed).

## 2. cli/ - a failed lifespan is not exit 0

- [x] 2.1 Red first, in `tests/test_cli_serve_signals.py` (no database): a launcher variant that replaces
  `commands.create_app` with a scratch ASGI app whose lifespan raises at shutdown. Parametrized over SIGTERM
  and SIGINT, one signal: `wait(timeout=5)`; assert `returncode == 1` and "Application shutdown failed" in the
  log. A second case whose lifespan raises at startup: no signal, `returncode == 1` on its own and the output
  names the failed startup, not a bind failure (uvicorn already exits 1 through `SystemExit`, with the wrong
  message). Verify: the shutdown cases fail today with return code 0, the startup case on the message.
- [x] 2.2 Add `LifespanWatch` to `cli/serving.py` (ASGI wrapper: forwards every scope; for `lifespan` wraps
  `send` to set `failed` on `lifespan.startup.failed` / `lifespan.shutdown.failed`, then forwards; typed with
  `starlette.types`). In `cmd_serve`, wrap `create_app(settings)` in it, pass the wrapper to `uvicorn.Config`,
  and return `130 if server.force_exit else 1 if watch.failed else 0` (comment the precedence); the
  `except SystemExit` branch says "application startup failed" when the watch has failed, not "could not bind". Verify: the
  2.1 tests pass; `tests/test_cli_serve.py` cases that patch `commands.ServiceServer` with fakes still pass;
  strict mypy and pylint clean.
- [x] 2.3 Unit tests for `LifespanWatch` in `tests/test_cli_serve_signals.py` (or a new
  `tests/test_cli_serve_lifespan.py` if the file would pass ~350 lines), no server: an `http` scope reaches
  the app with its own `receive`/`send`; `lifespan.startup.complete` and `lifespan.shutdown.complete` leave
  `failed` false and are forwarded; each `*.failed` message sets it and is forwarded with its `message`.
  Verify: `.venv/bin/python -m pytest tests/test_cli_serve_signals.py -k lifespan` passes.

## 3. Docs and gate

- [x] 3.1 README `serve` stop paragraphs (around "One SIGINT (Ctrl+C) or SIGTERM"): replace "The force does
  not end the wait for a connection that has not ended: a second Ctrl+C does not shorten the wait behind such
  a vanished peer today" with the new behaviour (a second Ctrl+C drops open connections and exits 130 within
  a few seconds), keep the one-signal exception about the vanished peer, and add one sentence that a failed
  application startup or shutdown exits 1. Verify: `grep -n "does not shorten" README.md` finds nothing, and
  the README sentences match the two spec deltas.
- [x] 3.2 Run `black`/`isort`, `mypy auto_reel_ng`, `pylint auto_reel_ng` (no new warnings beyond the known
  cairo noise), the full suite in the background, and `openspec validate cli-serve-forced-stop-and-lifespan
  --strict`. Verify: all green; record the uvicorn version(s) the child tests ran against in the PR notes.
