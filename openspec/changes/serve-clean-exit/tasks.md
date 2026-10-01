## 1. Baseline

- [x] 1.1 Confirm the code this change was designed against. Stop and report to the supervisor if a check
  fails in a way the design does not cover.
  - `git diff bca64f2 -- auto_reel_ng/cli/commands.py tests/test_cli_serve.py openspec/specs/headless-cli/spec.md README.md`
    prints nothing. If the spec's "`serve` runs the API service" differs, re-base this change's MODIFIED block
    on the current text and re-run `openspec validate serve-clean-exit --strict`.
  - `grep -n "server = uvicorn.Server(uvicorn_config)" auto_reel_ng/cli/commands.py` hits `cmd_serve`
  - `.venv/bin/python -c "import uvicorn; print(uvicorn.__version__)"`. Then
    `grep -n "raise_signal\|_captured_signals" .venv/lib64/python3.14/site-packages/uvicorn/server.py` still
    shows the re-raise loop at the end of `capture_signals`. If uvicorn no longer re-raises, the change is
    moot: report it instead of implementing.

  Verify: every check holds, or the difference is in the final report.

## 2. cli/ — `serve` exits by its status, not by the signal

- [x] 2.1 Red first. In `tests/test_cli_serve.py`, change `test_one_signal_stops_serve_with_a_websocket_open`
  as the design describes ("A test that means the same wherever pytest runs"):
  - add the `_SERVE_AS_FROM_A_TERMINAL` launcher constant (it resets SIGINT to `default_int_handler` *and*
    SIGTERM to `SIG_DFL`) and start the child as
    `[sys.executable, "-c", _SERVE_AS_FROM_A_TERMINAL, "serve", …]`
  - add `assert process.returncode == 0` and `assert "Traceback" not in output` after the existing assertions
  - rewrite the docstring: drop the paragraph saying the return code is not asserted, and say why the launcher
    resets both signals

  Run `.venv/bin/python -m pytest tests/test_cli_serve.py -k one_signal` against the unchanged `cmd_serve`.
  Verify:
  - both parameters fail on the return code: SIGINT with −2 (and a traceback in the printed log), SIGTERM with
    −15
  - 1012, "Application shutdown complete" and the 5 s bound still hold in both
  - the same two failures with pytest started with both signals ignored:
    `.venv/bin/python -c "import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN); os.execv(sys.executable, [sys.executable, '-m', 'pytest', 'tests/test_cli_serve.py', '-k', 'one_signal'])"`.
    If either case passes there, the launcher is not in effect. Fix that before going on.
- [x] 2.2 Add `ServiceServer` to `auto_reel_ng/cli/commands.py` exactly as in the design ("Where to stop the
  re-raise"): `@override` plus `@contextlib.contextmanager`, clearing `self._captured_signals` inside
  `super().capture_signals()`, with its docstring. Add `import contextlib` and `Iterator` and `override` to
  the `typing` import. Add `tests/test_cli_serve_signals.py` (no marker) with the recording fixture and the
  four cases from the design ("In-process tests of the subclass"): not raised again for SIGINT and for
  SIGTERM, a second SIGINT still forces, and the plain-uvicorn canary. Verify:
  - `.venv/bin/python -m pytest tests/test_cli_serve_signals.py` passes in well under a second
  - with the `clear()` line commented out, the two "not raised again" cases and the force case fail on a
    non-empty recording, the canary still passes, and the pytest run itself completes (nothing reaches
    pytest's own handlers). Restore the line afterwards.
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
  - `.venv/bin/python -m pylint auto_reel_ng/cli/commands.py` reports no `protected-access` and nothing new
- [x] 2.3 Wire it into `cmd_serve`: build `ServiceServer(uvicorn_config)`, return
  `130 if server.force_exit else 0` after `run()` with the design's comment, keep the `SystemExit` branch as
  it is, and rewrite the docstring's signal sentence (design, "Where to stop the re-raise"). In
  `tests/test_cli_serve.py`, re-point the replacements *before running anything*. A test still patching
  `commands.uvicorn.Server` would start a real server that never stops.
  - `test_flags_override_config_port` and `test_serve_keeps_uvicorns_websocket_keepalive`: their `_FakeServer`
    gains `force_exit = False` and is set with `monkeypatch.setattr(commands, "ServiceServer", _FakeServer)`
  - `test_serve_starts_and_answers_healthz`: `_CapturingServer` subclasses `commands.ServiceServer` and
    replaces `commands.ServiceServer`
  - new `test_forced_stop_exits_130`: a fake whose `run()` sets `self.force_exit = True` (as uvicorn does when a
    SIGINT lands during its shutdown). `main(["serve", str(tmp_path)])` returns 130.

  Verify with `.venv/bin/python -m pytest tests/test_cli_serve.py tests/test_cli_serve_signals.py`:
  - all pass
  - 2.1's end-to-end test now passes for SIGINT and SIGTERM with return code 0 and no traceback
  - the bind-failure test still returns 1 with `127.0.0.1:<port>` on stderr
  - the in-thread healthz test still returns 0
  - `grep -n "uvicorn.Server" tests/test_cli_serve.py` prints nothing (the in-process server tests in
    `tests/test_api_ws_lifecycle.py` keep their own `uvicorn.Server` and are not affected)

## 3. Docs

- [x] 3.1 In `README.md`'s `serve` stop paragraph ("One SIGINT (Ctrl+C) or SIGTERM …"), end the first
  sentence with "…released) within a few seconds, and `serve` exits with status 0." so that "The one
  exception" still follows the few-seconds promise. Correct the vanished-peer sentence (supervisor
  decision; design, "Force-quit still waits for open connections"): the shutdown can fail before its
  orderly part, or wait until the operating system gives up on that connection, which can take many
  minutes (no figure: none was reproduced; design, "Supervisor decisions (after implementation)"). Then
  add "When a second Ctrl+C forces the exit, the application shutdown is skipped and `serve` exits with
  status 130.", and say that the force ends the wait for running request handlers, not the wait for a
  connection that has not ended, so a second Ctrl+C does not shorten the wait behind a vanished peer today.
  Verify by rereading the paragraph against both spec deltas: orderly 0 for Ctrl+C and SIGTERM, forced
  130, no claim that a second Ctrl+C ends the vanished peer's stall, bind failure unchanged, and no claim
  that a failed shutdown exits non-zero.

## 4. Validation

- [x] 4.1 Manual check from the session scratchpad, never committed, with a throwaway `serve` on port **8120**
  run by the worktree's own venv against the worktree's own database, and an empty scratch project root.
  A scratch launcher starts `serve` as a terminal does (SIGINT at `default_int_handler`, SIGTERM at
  `SIG_DFL`) and can wrap `create_app` with two probe routes. Verify:
  - a real pty (`pty.fork`), a WebSocket client connected, `\x03` typed: the child exits with status 0, the
    output after `^C` ends at "Finished server process" with no traceback, and the client got 1012
  - `kill -TERM`: exit 0, 1012
  - forced: a handler that outlives its client (a probe HTTP route that never answers), then SIGINT and
    SIGINT: exit 130, no `KeyboardInterrupt`, no "Application shutdown complete". Repeat with SIGTERM then
    SIGINT: 130.
  - backed-up peer (supervisor decision): a probe WebSocket route backs 16 MiB of frames up to a raw peer
    that stops reading. SIGINT then SIGINT, and SIGTERM then SIGINT then SIGINT: the process stays up until
    the peer's connection ends, then exits 130 without "Application shutdown complete". One SIGINT: it
    exits 0 after "Application shutdown complete" once the connection ends.

  Never use port 8080, 8114 or 5173, the default database `auto_reel_ng`, or `auto-reel-media/`. Leave no
  `serve` process behind.
- [x] 4.2 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full
  `.venv/bin/python -m pytest`, including `requires_db` (podman). Then run
  `openspec validate serve-clean-exit --strict`. Verify all are clean or green, apart from the known cairo
  `no-member` noise and the five font-dependent skips.
