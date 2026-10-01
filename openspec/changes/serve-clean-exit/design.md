## Context

See proposal.md, "Why", for the finding. The code on `main` at `bca64f2`:

- `cli/commands.py` `cmd_serve` builds `uvicorn.Server(uvicorn.Config(app, host, port))` and calls
  `server.run()`. It catches only `SystemExit` (uvicorn's `sys.exit(1)` on a bind failure) and returns 0 after
  `run()` returns. Its docstring says uvicorn "installs its own SIGINT/SIGTERM handlers for a graceful
  shutdown".
- `uvicorn.Server.run()` is `asyncio.run(self.serve())`, and `serve()` is
  `with self.capture_signals(): await self._serve()`. `capture_signals()` (uvicorn/server.py, identical in
  0.51.0 and 0.54.0 apart from imports):
  1. on the main thread only, installs `self.handle_exit` for SIGINT and SIGTERM with `signal.signal`,
     keeping the handlers it replaced
  2. yields for the whole serve: startup, main loop and shutdown
  3. restores the replaced handlers
  4. calls `signal.raise_signal(s)` for each signal `handle_exit` recorded in `self._captured_signals`,
     newest first
- `handle_exit` records the signal. The first one sets `should_exit`. A SIGINT that arrives when
  `should_exit` is already set sets `force_exit`: the shutdown's wait loops for connections and handler tasks
  end, and the application (lifespan) shutdown is skipped if it has not started. uvicorn still awaits
  `asyncio.Server.wait_closed()` afterwards (Research, "Force-quit still waits for open connections"). A
  second SIGTERM only sets `should_exit` again.
- The handlers step 3 restores are:
  - **SIGINT:** `asyncio.Runner` installs its own `_on_sigint` when it finds `signal.default_int_handler`,
    which is what an interactive Python process has. The re-raised SIGINT makes it cancel the main task, and
    `Runner.run` turns that cancel into `KeyboardInterrupt` (asyncio/runners.py:133). The exception leaves
    `main()` uncaught, Python prints the traceback and ends the process by SIGINT.
  - **SIGTERM:** `SIG_DFL`, so the re-raise kills the process.
  - **SIGINT ignored at start** (a background job in a non-interactive shell): Python keeps `SIG_IGN`, asyncio
    installs nothing, and the re-raise is dropped. This is why an earlier `serve` looked clean.
- `tests/test_cli_serve.py`:
  - `test_one_signal_stops_serve_with_a_websocket_open` runs `python -m auto_reel_ng.cli.main serve` as a
    subprocess and deliberately does not assert the return code.
  - Three tests replace the server class by monkeypatching `commands.uvicorn.Server`: two with a `_FakeServer`
    whose `run()` returns at once, and one with a capturing subclass.
- The headless-cli spec already promises "exit zero". The api-service spec's WebSocket requirement covers
  what one signal does to connections (1012, "within a few seconds") and is not changed.

## Goals / Non-Goals

**Goals:**
- An orderly stop exits 0 without a traceback, for SIGINT and SIGTERM, in a terminal and under a supervisor.
- A forced stop exits 130 without a `KeyboardInterrupt` traceback, whichever signal came first.
- uvicorn's own signal handling (which signals, force-quit) and the shutdown sequence stay exactly as they are.
- A test that fails on today's code wherever pytest runs, including from a background shell.

**Non-Goals:**
- Making force-quit end a shutdown that waits on an open client connection (Risks; proposed follow-up).
- Any change to `api/`, the lifespan, the WebSocket handler or its close codes.
- Any change to what a Ctrl-C does before `server.run()` starts, or to `worker`.
- An exit-status check of the application shutdown (Research, "A failed application shutdown").

## Research & Decisions

### Reproduction

**Context**: The brief requires each finding to be reproduced before it is fixed. The live read-only server on
:8114 (`wt-final-e2e`, uvicorn 0.54.0, SIGINT and SIGTERM caught, SIGHUP ignored per `/proc/<pid>/status`)
belongs to the final pass and must not be signalled, so it was only read (`/healthz` 200).

**Explored**: A throwaway `serve` on port 8120 against its own `postgres:16-alpine` container (schema by
`create_all`) and an empty project root, run with the repo's venv (uvicorn 0.51.0, Python 3.14). A launcher
script resets SIGINT to `default_int_handler` (as a terminal leaves it) and runs `main()`. In `fix` mode it
also swaps in the prototype below. Probe scripts and logs are in the session scratchpad
`polish-spec/serve-clean-exit/` (`probe.py`, `probe_force*.py`, `run_serve.py`, `logs/`). The final pass's
own matrix on 0.54.0 is `verify/final/sigint-matrix/*.log`.

| Case (one signal unless noted) | `main` today | Prototype |
|---|---|---|
| SIGINT, WebSocket open | killed by SIGINT (rc −2), `KeyboardInterrupt` traceback, client got 1012 | rc 0, no traceback, 1012 |
| SIGTERM, WebSocket open | killed by SIGTERM (rc −15), 1012 | rc 0, 1012 |
| SIGINT / SIGTERM, no client | −2 with traceback / −15 | 0 / 0 |
| SIGINT ignored at start, WebSocket open | 0 | 0 |
| Real pty, Ctrl-C typed, WebSocket open | killed by signal 2 after 0.29 s, colored traceback | exit 0 after 0.27 s, log ends at "Finished server process" |
| Forced: a handler still running after its client left, SIGINT then SIGINT | −2, traceback, no "Application shutdown complete" | 130, no `KeyboardInterrupt`, no "Application shutdown complete" |
| Forced: same, SIGTERM then SIGINT | −15 (the newest-first re-raise: SIGINT cancels, then SIGTERM kills) | 130 |
| Bind failure (port held) | rc 1, `error: could not bind 127.0.0.1:8120` | same |

In every orderly case the shutdown itself was unchanged: "Application shutdown complete" was logged and the
process ended 0.21–0.36 s after the signal. In the forced cases uvicorn logs "Exception in ASGI application"
with a `CancelledError` for the handler it cut, with or without the change. That log line is truthful, and the
spec allows it.

**Decision**: The finding reproduces on both uvicorn versions and for both signals, with or without a
WebSocket client. The WebSocket plays no part. Nothing is dropped.

**Rationale**: The same `capture_signals` code in 0.51.0 and 0.54.0 explains both sets of logs, and the
prototype removes the symptom in every row without changing the shutdown log.

### Where to stop the re-raise

**Context**: The signal must not reach the pre-uvicorn handlers after an orderly shutdown. The fix must also
keep the bind-failure path, uvicorn's force-quit, and the in-thread use in
`test_serve_starts_and_answers_healthz`, where no signal handler can be installed.

**Explored**:
- **Catch `KeyboardInterrupt` around `server.run()`**, as `uvicorn.run()` does (uvicorn/main.py:622). SIGTERM
  still kills the process, because `SIG_DFL` runs no Python code. It also cannot tell an orderly stop from a
  forced one.
- **Install our own handlers before `server.run()`** (for example `server.handle_exit`) so that the re-raise
  lands on them. This relies only on public names, but:
  - `cmd_serve` would need its own main-thread check and its own handler restore
  - the tests' `_FakeServer` would need a `handle_exit`
  - a SIGINT no longer reaches asyncio's handler before uvicorn's are up, which changes the startup window
- **Override `capture_signals` completely** (install, yield, restore, no re-raise). This copies about ten lines
  of uvicorn, and it would silently drop anything uvicorn later adds there.
- **Run uvicorn on a worker thread**, where `capture_signals` does nothing, and handle signals on the main
  thread. That re-implements uvicorn's signal handling. Rejected.
- **Subclass, and empty the captured list inside uvicorn's own context manager.** uvicorn still installs,
  records and restores. Only its final re-raise finds nothing to raise. Prototyped:
  - strict mypy clean with `@typing.override` (Python ≥ 3.12, and the project requires ≥ 3.13)
  - pylint 10.00, because `self._captured_signals` in a subclass is not `protected-access`
  - black clean
  - a copy with `capture_signals` and `_captured_signals` renamed fails mypy twice ("marked as an override, but
    no base method was found", "has no attribute"), so an upstream rename fails the type gate instead of
    silently bringing the traceback back

**Decision**: Add to `auto_reel_ng/cli/commands.py`, next to `cmd_serve`:

```python
class ServiceServer(uvicorn.Server):
    """uvicorn's server for ``serve``: a stop signal it has obeyed is not raised again.

    After its orderly shutdown ``uvicorn.Server`` raises each signal it caught once more,
    for the handler installed before it: asyncio's SIGINT handler turns that into a
    ``KeyboardInterrupt`` traceback, and SIGTERM's default handler kills the process.
    ``serve`` has nothing left for the signal to do. It returns, and its exit status
    reports the stop (headless-cli, "`serve` runs the API service").
    """

    @override
    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        with super().capture_signals():
            yield
            # The shutdown the captured signals asked for has completed.
            self._captured_signals.clear()
```

`cmd_serve` builds `ServiceServer(uvicorn_config)` instead of `uvicorn.Server(uvicorn_config)`. After
`run()` returns:

```python
    try:
        server.run()
    except SystemExit:
        print(f"error: could not bind {settings.host}:{settings.port}", file=sys.stderr)
        return 1
    # A SIGINT during the shutdown made uvicorn skip the rest of it (its force-quit):
    # 130 = 128 + SIGINT, a shell's status for an interrupted command.
    return 130 if server.force_exit else 0
```

Imports: `contextlib`, and `Iterator` and `override` from `typing` (the module already imports from
`typing`). The `cmd_serve` docstring replaces "uvicorn installs its own SIGINT/SIGTERM handlers for a
graceful shutdown" with: uvicorn handles SIGINT/SIGTERM, and `serve` exits 0 after the orderly shutdown and
130 after a forced one. The class is public so that the tests can replace it
(`monkeypatch.setattr(commands, "ServiceServer", …)`).

**Rationale**:
- It is the smallest change that covers both signals.
- It leaves every uvicorn behavior except the one being removed.
- It works unchanged off the main thread: `super().capture_signals()` yields without installing anything, and
  the list stays empty.
- If the body raises (the bind failure's `SystemExit`, or a server shutdown that raises), the `clear()` is
  skipped and the exception propagates exactly as today. A failed *application* shutdown does not raise
  here; see "A failed application shutdown".

### Exit status of a forced stop

**Context**: The brief requires 0 after an orderly shutdown, and says "a second signal may still
force-quit". It does not say what a forced stop exits with.

**Explored**:
- **0 as well.** This is the simplest, but it reports success for a stop that skipped the application shutdown
  (the WebSocket hub not stopped, the engine not disposed) and may have cut a request.
- **Keep uvicorn's re-raise when `force_exit` is set.** That brings back today's forced outcome: a
  `KeyboardInterrupt` traceback, or death by SIGTERM when SIGTERM came first. The status then depends on the
  order of the signals.
- **Return 130.** This is deterministic and needs no traceback. 130 is what a shell shows for an interrupted
  command, and force is only ever triggered by a SIGINT.

**Decision**: 130, from `cmd_serve` reading `server.force_exit`. The subclass clears the list in both cases,
so the forced path never re-raises either.

**Rationale**: An exit status is the service's only report to a supervisor or script (Principle I: never
report a failure as success). The cost is one expression and one unit test. A second SIGINT that lands after
the orderly shutdown had already finished also reads 130. The operator did interrupt, so that is accurate
enough.

### A test that means the same wherever pytest runs

**Context**: Signal dispositions are inherited. When pytest is started as a background job from a
non-interactive shell (a CI step, an agent's shell), its children start with SIGINT ignored. uvicorn then
restores `SIG_IGN`, the re-raised SIGINT is dropped, and the SIGINT case passes on today's code. The final
pass's first `serve` looked clean for exactly this reason. An inherited ignored SIGTERM (rarer: a wrapper
that ignores it) hides the SIGTERM case the same way.

**Explored**:
- `preexec_fn` resetting the signals in the child. It is not safe when the parent has threads.
- Asserting the child's disposition. That turns a real failure into a skip.
- Launching the child through `python -c` code that sets `signal.default_int_handler` and `SIG_DFL` itself
  and then runs `main()`. That is the state an interactive Python process starts in.
- Measured in review, on today's `cmd_serve` with the new assertions, pytest started with SIGINT and
  SIGTERM both ignored: the test as it stands (`python -m`) passes both cases (2 passed); with the
  launcher both fail, SIGINT with −2 and SIGTERM with −15. From a foreground shell both fail either way.

**Decision**: `tests/test_cli_serve.py` gets a module constant:

```python
#: ``serve`` as a terminal starts it: SIGINT at Python's default and SIGTERM at the system's, even when
#: pytest itself runs with them ignored (a background job), which a child would otherwise inherit and
#: which hides a re-raised signal.
_SERVE_AS_FROM_A_TERMINAL = (
    "import signal, sys\n"
    "signal.signal(signal.SIGINT, signal.default_int_handler)\n"
    "signal.signal(signal.SIGTERM, signal.SIG_DFL)\n"
    "from auto_reel_ng.cli.main import main\n"
    "sys.exit(main(sys.argv[1:]))\n"
)
```

The signal test runs `[sys.executable, "-c", _SERVE_AS_FROM_A_TERMINAL, "serve", <tmp root>, "--host",
"127.0.0.1", "--port", <free>]` and asserts `process.returncode == 0` and `"Traceback" not in output`, in
addition to its current assertions (1012, "Application shutdown complete", no "Waiting for background tasks to
complete", exit within 5 s).

**Rationale**: The test then fails on today's code in every environment (rc −2 with a traceback, or −15), and
passes only when `serve` itself exits 0.

### In-process tests of the subclass, without risking pytest

**Context**: `capture_signals` only installs handlers on the main thread, which is pytest's. A regression
would re-raise SIGINT into pytest's own handler, which aborts the run, or SIGTERM into `SIG_DFL`, which kills
pytest.

**Decision**: a new module `tests/test_cli_serve_signals.py` with no database and no marker. It has a fixture
that installs a recording handler for SIGINT and SIGTERM and restores the previous ones in its `finally`, so
these become the handlers uvicorn restores and re-raises into. Its tests:
- **not raised again**, parametrized over SIGINT and SIGTERM: inside
  `commands.ServiceServer(uvicorn.Config(<dummy app>, log_config=None)).capture_signals()` (no logging
  reconfiguration inside pytest), `signal.raise_signal(sig)` sets
  `should_exit` and not `force_exit`. After the block nothing was recorded, and `signal.getsignal(sig)` is the
  recorder again.
- **a second SIGINT still forces:** two `raise_signal(SIGINT)` calls inside the block set `force_exit`, and
  nothing is recorded afterwards
- **canary:** the same sequence on plain `uvicorn.Server` with SIGTERM records `[SIGTERM]`. Its docstring says
  that when this fails, uvicorn has stopped re-raising, and `ServiceServer` and this test are to be deleted.

Prototyped: 4 passed in 0.03 s. The canary recorded the re-raise, and pytest was unaffected. Rebuilt in
review from this text alone: 4 passed in 0.04 s, also with pytest started with SIGINT and SIGTERM ignored.
With the `clear()` line disabled, the three `ServiceServer` cases fail on `[2]`, `[15]` and `[2, 2]`, the
canary passes, and the run completes.

### Force-quit still waits for open connections

**Context**: This came up while designing the forced-stop scenario. It is pre-existing and is not the finding.

**Explored**: One client held `GET` open on a route that never answers. Then SIGINT was sent three times, one
second apart. The process stayed up through all three, on today's code and with the prototype, and exited
0.16–0.21 s after the client closed its socket. The cause is in uvicorn's shutdown: after `force_exit` it
still awaits `asyncio.Server.wait_closed()`, and since Python 3.12.1 that waits until every connection is
detached (asyncio/base_events.py `wait_closed` docstring). By the same code path, the vanished WebSocket peer
that the api-service spec and README say a "second Ctrl+C forces" would also hold the process until TCP gives
up. That case was not reproduced here.

**Decision**: Out of scope. The spec's forced scenario uses the case force does end (a handler outliving its
client), which was measured. The follow-up is reported to the supervisor: abort the remaining transports on
force, and correct the api-service and README sentence about the vanished peer.

**Rationale**: The fix means cutting in-flight requests on purpose and verifying the vanished-peer case. That
is a separate decision in `api/`'s territory, and it would double this change.

### A failed application shutdown

**Context**: Found in review. The exit status is meant to be 0 only after a *completed* orderly shutdown.
uvicorn handles a lifespan shutdown that raises on its own: Starlette sends `lifespan.shutdown.failed` with
the traceback, uvicorn logs it and "Application shutdown failed. Exiting.", and `Server.serve()` returns
normally (uvicorn/lifespan/on.py `shutdown()`; no exception reaches `run()`). Today the re-raised signal
happens to make that exit non-zero. With `ServiceServer` it would be 0.

**Explored**:
- **Measured with a scratch FastAPI app** whose lifespan re-raises a dead background task at shutdown, as
  `JobsHub.stop()` would re-raise a dead poller: plain `uvicorn.Server` ends −2 (SIGINT) or −15 (SIGTERM),
  `ServiceServer` with this design ends **0** for both, each time after logging "Application shutdown
  failed" and the traceback.
- **Is it reachable in `serve` today?** The app's lifespan shutdown is `await jobs_hub.stop()` then
  `engine.dispose()`.
  - `stop()` can raise only by awaiting a poller that died with an error, which needs a subscriber still
    registered. But uvicorn ends every connection before it sends the lifespan shutdown, and each WebSocket
    handler unsubscribes in its `finally`, so the last one has already dropped the poller.
  - A forced stop skips the lifespan shutdown altogether.
  - `dispose()` does not raise for a database that has gone away.
  - Measured: a real `serve` (port 8120, own Postgres) with a GUI-style WebSocket client. The database
    container was stopped mid-run (`/healthz` then answered 503) and left down for six poll intervals, then
    one SIGTERM was sent. Both the design's prototype and the watch variant below logged "Application shutdown
    complete", sent 1012 and exited 0.
- **An ASGI lifespan watch in `cli/`**: `cmd_serve` wraps the app in a small class whose `__call__` passes
  every scope through and, for the lifespan scope, notes a `lifespan.shutdown.failed` message on its way to
  uvicorn. `cmd_serve` returns 1 when it saw one. It uses only the ASGI lifespan protocol, no uvicorn
  internals. Prototyped in review: about 20 lines with `starlette.types`, strict mypy clean, pylint 10.00,
  and three tests with no database. The dead-task app then exits 1 for both signals, and the serve suites
  stay green.
- **`server.lifespan.should_exit`**: one line, but an untyped uvicorn internal whose meaning is not
  documented.

**Decision**: No watch in this change. The design states the gap instead of claiming that a failed shutdown
stays non-zero, and the supervisor decides (Open Questions).

**Rationale**: No path in today's lifespan can raise when the lifespan shutdown runs (measured above).
Code for an unreachable failure is the "for later" path Principle VII rules out. The cost of being wrong is
an exit 0 with "Application shutdown failed" and its traceback still in the log: loud in the log, wrong in
the status. If the lifespan gains a step that can raise, the watch above is the fix. Spec: the requirement
promises 0 only when "its orderly shutdown has completed", so it does not claim this case either way.

### Changed during review

The adversarial review rebuilt the change from its own text in a scratch copy of `main` at `bca64f2` and
ran it. The fix holds: the e2e test fails first (SIGINT −2 with a `KeyboardInterrupt` traceback, SIGTERM
−15), and with `ServiceServer` and the re-pointed fakes the serve suites pass (11 passed). mypy is clean
and pylint scores 10.00. A scratch ASGI app gave the same results as the matrix above: orderly SIGINT or
SIGTERM 0; handler outlives its client, then two signals, 130 without `KeyboardInterrupt`; a client holding
its request open kept the process up through three SIGINTs. uvicorn 0.51.0 and 0.54.0 have identical
`capture_signals`, `handle_exit` and `shutdown` code. Changes:

1. **The test launcher also resets SIGTERM** to `SIG_DFL`. Without that, an inherited ignored SIGTERM lets
   the SIGTERM case pass on today's code (measured; "A test that means the same wherever pytest runs").
2. **The spec's force-quit sentence was narrowed.** "Stops waiting for work still in progress" was false
   for a client that keeps its request open. It now says what force does (no more waiting for running
   handlers, application shutdown skipped if not yet started) and requires 130 "when the command then
   ends".
3. **A failed application shutdown is no longer claimed to exit non-zero.** It would exit 0. The gap and
   its options are recorded above, and the decision is the supervisor's.
4. **README wording** (task 3.1) places the exit statuses so that "The one exception" still refers to the
   few-seconds promise. The forced-exit sentence is conditional ("When a second Ctrl+C forces the exit…"),
   so it claims nothing about what force waits for.

## Failure behavior and idempotency

- **Bind failure:** uvicorn's `sys.exit(1)` raises through the subclass (no `clear()`) and `run()`.
  `cmd_serve` prints `error: could not bind <host>:<port>` and returns 1, as today.
- **A server shutdown that raises** (for example 0.51's `InvalidState` for a vanished peer,
  `jobs-ws-lifecycle` Risks) propagates as today: out of `run()` and `main()` as a traceback, exit 1.
- **An application (lifespan) shutdown that raises** is caught by uvicorn, which logs "Application shutdown
  failed" with the traceback and returns normally, so `serve` would exit **0**. No step in today's lifespan
  can raise at that point (Research, "A failed application shutdown"). Known gap; see Open Questions.
- **Forced stop:** 130. uvicorn may log the handler it cut as "Exception in ASGI application".
- **Idempotency:** `serve` keeps no state across runs, and this change writes no file and no row. A restart
  behaves the same, and neither rendered output nor the job store is involved.
- **No decision outlives the change** beyond the headless-cli requirement itself. The spec is its durable home,
  so there is no new HLD D-n entry. D-A7 still holds: uvicorn's graceful shutdown is unchanged.

## Ownership (polish round)

P6 owns the `serve` command in `auto_reel_ng/cli/commands.py` (the new class, `cmd_serve` and its imports),
`tests/test_cli_serve.py`, the new `tests/test_cli_serve_signals.py`, and README's `serve` stop paragraph. No
web file and no other change's file is touched.

## Risks / Trade-offs

- **[uvicorn internals]** The subclass relies on `capture_signals` being what `serve()` wraps itself in, and
  on the name `_captured_signals`. → Strict mypy fails on a rename of either. The canary test fails if uvicorn
  stops re-raising, and the e2e return-code assertion fails if `serve()` stops calling `capture_signals`.
- **[Shell scripts and Ctrl-C]** By the "wait and cooperative exit" convention, a program stopped by Ctrl-C
  dies by SIGINT, so a calling shell script aborts too. With exit 0, a script that runs `serve` followed by
  other commands continues after Ctrl-C. → Accepted. The spec has promised exit zero since phase 7, `serve` is
  a long-running foreground service that is normally the last command, and supervisors (systemd, podman) read
  0 as a clean stop.
- **[A signal in the last instructions]** A signal that arrives after `clear()` but before uvicorn restores
  the handlers is recorded and re-raised, as today. → This is a new Ctrl-C at the moment the process exits,
  and it ends as today's traceback. Accepted.
- **[Force-quit waits for open connections]** Pre-existing and unchanged (Research, "Force-quit still waits
  for open connections"). → Follow-up.
- **[A failed application shutdown exits 0]** Today the signal re-raise makes it non-zero by accident; after
  this change it is 0, with the failure in the log only. → Unreachable with today's lifespan (measured).
  The ASGI lifespan watch is prototyped if the supervisor wants it closed now (Open Questions).

## Migration Plan

None. The next `serve` start uses the new exit behavior. Rollback is reverting the commit.

## Open Questions

1. **Forced stop: 130 or 0?** This design returns 130 so that a stop that skipped the application shutdown
   is not reported as success ("Exit status of a forced stop"). The brief fixed only the orderly case, at 0.
   Supervisors (systemd, podman) send SIGTERM, which never forces, so only an operator's second Ctrl-C can
   produce 130.
2. **A failed application shutdown exits 0.** Accept it while today's lifespan cannot raise at that point,
   or add the prototyped ASGI lifespan watch (about 20 lines in `cli/commands.py`, three tests with no
   database, exit 1) in this change? Review recommends accepting it for now (Principle VII). The watch
   becomes the fix if the lifespan gains a step that can raise ("A failed application shutdown").
3. **Force-quit does not end a shutdown that waits on an open client connection.** This is pre-existing and
   out of scope. The likely follow-up in `api/`/`cli/`: abort the remaining transports on force, and correct
   the api-service spec and README sentence saying a second Ctrl+C forces the exit for a vanished peer
   ("Force-quit still waits for open connections").
