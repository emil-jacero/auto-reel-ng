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
  second SIGTERM only sets `should_exit` again. (Corrected in review: what force skips is uvicorn's
  lifespan shutdown *step*; the app's own cleanup still runs when `asyncio.run` cancels the lifespan task.
  "Changed during review of the pull request", item 2.)
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
  what one signal does to connections (1012, "within a few seconds"). Only its sentence on a vanished peer's
  stall changes (Supervisor decisions; "Force-quit still waits for open connections").

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

### Supervisor decisions (before implementation)

- **A forced stop (a second Ctrl-C) exits 130.** Accepted as designed ("Exit status of a forced stop"; Open
  Question 1).
- **An application (lifespan) shutdown that raises exits 0, with its traceback in the log.** Accepted under
  Principle VII: no step of today's lifespan can raise at that point, so the prototyped ASGI lifespan watch
  is not added. The gap stays recorded ("A failed application shutdown", Failure behavior, Risks; Open
  Question 2).
- **The sentences that say a second Ctrl+C forces the exit past a vanished peer are corrected in this
  change**, in README's `serve` stop paragraph and in the api-service requirement "WebSocket live job
  updates", to say what really happens ("Force-quit still waits for open connections"). This reverses the
  earlier plan to leave them to the follow-up, and adds the api-service delta (two capability deltas, within
  Principle VIII's limit). The headless-cli delta states the same limit for a forced stop. Aborting the
  remaining transports on force, so that a second Ctrl+C really ends that wait, stays a follow-up (Open
  Question 3).

### Supervisor decisions (after implementation)

- **No unverified figure for a vanished peer's stall.** README no longer says "about 15 minutes": the
  figure comes from `tcp_retries2` and the `jobs-ws-lifecycle` estimate, and was not reproduced. README says
  the shutdown waits until the operating system gives up on that connection, which can take many minutes,
  and that a second Ctrl+C does not shorten that wait today. The api-service delta says the same in the
  spec's own terms ("until the host's TCP stack abandons the connection, which can take many minutes"; "does
  not shorten that stall"), matching the wording of the requirement's keepalive bullet. Follow-up unchanged:
  abort the remaining connections on force.
- **The api-service MODIFIED block is re-based on the current `openspec/specs/api-service/spec.md` at
  archive time**, since it replaces the whole "WebSocket live job updates" requirement.

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
with a `CancelledError` for the handler it cut, with or without the change. It also logs, as an `ERROR`
traceback, the `CancelledError` of the application lifespan task whose shutdown the force skipped (seen at
implementation, and in the design-phase logs of both modes). Both are truthful, neither is a
`KeyboardInterrupt`, and the spec allows them.

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
- **0 as well.** This is the simplest, but it reports success for a stop that skipped uvicorn's application
  shutdown step and may have cut a request. (Corrected in review: an earlier text said the WebSocket hub
  was not stopped and the engine not disposed. Both still happen, when `asyncio.run` cancels the lifespan
  task; "Changed during review of the pull request", item 2.)
- **Keep uvicorn's re-raise when `force_exit` is set.** That brings back today's forced outcome: a
  `KeyboardInterrupt` traceback, or death by SIGTERM when SIGTERM came first. The status then depends on the
  order of the signals.
- **Return 130.** This is deterministic and needs no traceback. 130 is what a shell shows for an interrupted
  command, and force is only ever triggered by a SIGINT.

**Decision**: 130, from `cmd_serve` reading `server.force_exit`. The subclass clears the list in both cases,
so the forced path never re-raises either. Extended in review: on the main thread `ServiceServer.run()`
ends a forced stop itself with `os._exit(130)`, so that no worker thread is joined, and sets both signals
to `SIG_IGN` once uvicorn has returned ("Changed during review of the pull request", items 1 and 3).

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
up. That case was not reproduced at design time.

Measured at implementation, with the implemented `serve` on port 8120 (scratch launcher and probe routes in
the session scratchpad, `verify/serve-clean-exit/`). A probe WebSocket route sent 64 frames of 256 KiB to a
raw peer (receive buffer 4 KiB) that read the handshake and nothing else, then waited, as a feed that goes
quiet. uvicorn's `shutdown()` writes the 1012 close frame and calls `transport.close()`, and asyncio's
`close()` with a non-empty buffer waits for it to drain before the connection is dropped:

| Signals, 1.5 s apart | uvicorn 0.54 | uvicorn 0.51 |
|---|---|---|
| SIGINT, SIGINT | up 1.5 s after each and 5 s later, "Waiting for connections to close"; exit 130 0.21 s after the peer closed; no "Application shutdown complete" | same; exit 130 after 0.16 s |
| SIGTERM, SIGINT, SIGINT | same; exit 130 after 0.21 s | not run |
| SIGINT | up 6.5 s; exit 0 0.26–0.36 s after the peer closed, after "Application shutdown complete" | same |
| SIGTERM, SIGTERM | up 8 s; exit 0 0.31 s after the peer closed, after "Application shutdown complete", no traceback: a further SIGTERM changes nothing | not run |

The peer here was alive and stopped reading, so its socket's close (with unread data, a reset) ended the
connection. A peer that vanished sends nothing, so the connection ends only when the host's TCP stack
abandons it. `net.ipv4.tcp_retries2` is 15 on this host, which the `jobs-ws-lifecycle` design (Risks)
estimates at about 15 minutes. That figure was not reproduced here (a truly vanished peer needs dropped
packets), so README and the spec give no figure: the wait lasts until the operating system gives up on the
connection, which can take many minutes (Supervisor decisions, after implementation). On 0.51 the shutdown can instead fail, when the keepalive has already started closing that connection
(`InvalidState`, same Risks entry). Both are what the corrected sentences say.

A first probe that sent frames for ever never yielded on 0.51, which has no write back-pressure: it starved
the event loop, so no signal was handled. That is the probe's loop, not `serve`'s behavior (the real feed
sends one small delta per poll), and it was replaced by the bounded backlog above.

**Decision**: The behavior stays out of scope: the spec's forced scenario uses the case force does end (a
handler outliving its client). The sentences that claimed otherwise are corrected in this change
(Supervisor decisions): README's `serve` stop paragraph and the api-service requirement "WebSocket live job
updates" now say that the stall lasts until the host's TCP stack abandons the connection and that a second
SIGINT does not end it. The headless-cli delta says that a forced stop still waits for its client
connections. The follow-up stays: abort the remaining transports on force.

**Rationale**: The fix means cutting in-flight requests on purpose and verifying the vanished-peer case. That
is a separate decision in `api/`'s territory, and it would double this change. A spec and a README that
promise what a second Ctrl+C cannot do are wrong today, and correcting them costs no code.

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
  - A forced stop skips uvicorn's lifespan shutdown step. The lifespan's cleanup then runs in the cancelled
    lifespan task, and the exit is 130 whatever it logs.
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
stays non-zero. The supervisor accepted the gap (Supervisor decisions).

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
   so it claims nothing about what force waits for. Superseded at implementation: the paragraph now says
   that force does not end the wait for a connection that has not ended ("Changed during implementation").

### Changed during implementation

1. **The vanished-peer sentences are corrected here** (Supervisor decisions): README's `serve` stop
   paragraph, a new api-service delta that changes one sentence of "WebSocket live job updates", and one
   sentence in the headless-cli delta. Task 3.1 and the proposal say so, and 4.1 gains the backed-up peer
   check ("Force-quit still waits for open connections").
2. **The forced stop's logged tracebacks.** Besides the cut handler's "Exception in ASGI application", uvicorn
   logs the lifespan task's `CancelledError` when the force skips its shutdown. The headless-cli delta names
   both as allowed error logs; neither is a `KeyboardInterrupt` traceback of the command's own.
3. **Task 4.1 ran on the worktree's own database** on the shared dev Postgres container (the polish round's
   per-worktree arrangement) instead of a throwaway container, with new probes run by the worktree's venv
   (uvicorn 0.54.0). The design-phase probes use the main checkout's venv, which imports the main checkout's
   code, so they could not run the implemented code. The 0.51 comparison ran the main checkout's venv with
   `PYTHONPATH` set to the worktree, reading that venv only.

| Task 4.1 case (uvicorn 0.54) | Result |
|---|---|
| Real pty, WebSocket open, `\x03` typed | exit 0 after 0.27 s; output after `^C` ends at "Finished server process"; no traceback; 1012 |
| `kill -TERM`, WebSocket open | exit 0 after 0.31 s; no traceback; "Application shutdown complete"; 1012 |
| Handler outlives its client; SIGINT, SIGINT | 130, 0.26 s after the second; no `KeyboardInterrupt`; no "Application shutdown complete" |
| Same; SIGTERM, SIGINT | 130, 0.26 s after the second; same |
| Backed-up peer | see "Force-quit still waits for open connections" |
| Port held | exit 1; `error: could not bind 127.0.0.1:8120`; no traceback |

The same orderly and forced cases on uvicorn 0.51: `kill -TERM` exit 0 with 1012; both forced cases 130
without `KeyboardInterrupt`.

### Changed during review of the pull request

A supervisor review of `pr/serve-clean-exit` (two Opus lenses, each finding then checked by a skeptic)
found one major and four minor defects. The major and the first minor are the same defect, found by both
lenses. All five were fixed on the pr branch, in new commits. Each fix was reproduced first with the
review's own scratch probes (`verify/serve-clean-exit/review_probe.py` and `review_pty.py`, port 8120, a
local listener that accepts and never answers as the database, an empty root), then rerun on the fix.

1. **A forced stop waited for a sync handler's worker thread, and a third Ctrl-C ended in a
   `KeyboardInterrupt` traceback** (major). The spec and README said the force ends the wait for request
   handlers still running. That held only for async handlers, the only kind the design's probes used
   (`await asyncio.sleep(3600)`). Ten of the twelve API routes are sync `def` endpoints, which FastAPI
   runs in anyio worker threads, and the thumbnail route runs its extraction in one too. Those threads are
   not daemons. uvicorn's force stops waiting for the request's task, and `asyncio.run` cancels that task,
   but the thread keeps running, and the interpreter joins it after `cmd_serve` has returned 130.
   Measured before the fix, with `GET /healthz` blocked on the stalled database after its client gave up:
   - `kill -INT` twice: "Finished server process", then the process was still up 6 s later. A third
     SIGINT ended it with 130 and `Exception ignored while joining a thread in _thread._shutdown():
     ... KeyboardInterrupt`.
   - The real `auto-reel` console script in a pty, Ctrl-C typed twice: still up 8 s later.
   - One SIGTERM: still up after 5 s (the orderly stop waits for the handler, as it should).

   **Fix:** `ServiceServer.run()` now ends a forced stop itself, on the main thread: it flushes the log
   and the standard streams and calls `os._exit(130)`, so no worker thread is joined. The app's cleanup
   has already run by then (item 2). Off the main thread (`test_serve_starts_and_answers_healthz`) it
   returns as uvicorn's does, and `cmd_serve` still maps `force_exit` to 130 for that path and for the
   tests' fakes. After the fix: two or three SIGINTs give 130 0.03–0.11 s after the last one, with no
   `KeyboardInterrupt`, for `kill -INT` and for a typed Ctrl-C in a pty. The spec now says that the
   orderly shutdown waits for running handlers and that the force abandons one blocked in a worker thread,
   with a new scenario for it. README's "one exception" became two: a request still being handled holds
   the orderly shutdown until it returns. The api-service sentence gains the same remark. The
   alternative, narrowing the text to async handlers, would have documented a hang that a second Ctrl-C
   is meant to end.
   New test `test_a_forced_stop_does_not_wait_for_a_handler_in_a_worker_thread` (no database): the
   stalled `GET /healthz`, then SIGINT, SIGINT and SIGINT, must end with 130 within 5 s and no
   `KeyboardInterrupt`. On the unfixed code it timed out.
2. **"Skips its application shutdown" was inaccurate.** What force skips is uvicorn's lifespan shutdown
   step and its "Application shutdown complete" line. The app's `_lifespan` is `try: yield finally: await
   jobs_hub.stop(); engine.dispose()`. When `asyncio.run` closes the loop it cancels the still-pending
   lifespan task, and that `finally` runs. Measured with an instrumented launcher on the real app, forced
   stop with an async and with a sync handler: `hub.stop` start and end and `engine.dispose` are printed
   after "Finished server process", followed by the lifespan's `CancelledError` traceback. The two spec
   sentences, README, and this design's reason for 130 (Research, "Exit status of a forced stop") no
   longer say the hub is not stopped and the engine not disposed. The spec says that the cleanup still
   runs and that the command waits for it. 130 still holds, because a request may have been cut.
3. **A second signal during the interpreter's finalization killed `serve`.** After `main()` returned,
   the process spent about 0.2 s finalizing (the reviewer's stamps: 0.16–0.28 s). Python resets its own
   handlers to `SIG_DFL` there, so a second signal killed it. Measured before the fix, with stop and second signal 0.25 s or 0.32 s apart:
   `kill -TERM` twice gave −15 in 5 of 5 runs at each gap, and `kill -INT` twice gave −2 in 5 of 5. A
   typed Ctrl-C 0.25 s after the first ended by signal 2 in 3 of 3 runs. The design's risk entry covered
   only the gap between `clear()` and the restore. **Fix:** once uvicorn has returned on the main thread,
   `ServiceServer.run()` sets SIGINT and SIGTERM to `SIG_IGN`, which survives finalization; a
   Python-level handler would not. After the fix, `kill -TERM` twice exits 0 in 15 of 15 runs (gaps of
   0.15, 0.25 and 0.32 s). `kill -INT` twice exits 0 in 10 of 10 at 0.25 and 0.32 s. The pty's typed
   Ctrl-C exits 0 in 3 of 3. At 0.15 s the second SIGINT still lands inside uvicorn's shutdown and
   forces (130, 5 of 5, before and after the fix), as the spec says. The spec now also says that a further SIGINT or SIGTERM while the command
   exits changes nothing, with a scenario. The risk entry is corrected. New test
   `test_a_late_signal_does_not_change_the_exit_status[SIGINT/SIGTERM]` (no database): the launcher
   raises a SIGINT and a SIGTERM at itself after `main()` returns. The status must stay 0, and the test
   fails (−2) on the unfixed code.
4. **Two of the spec's signal-order promises had no test:** SIGTERM then SIGINT forces, and a SIGTERM
   never forces. `test_a_second_sigint_still_forces` became `test_only_a_later_sigint_forces`, which
   checks all four two-signal orders against `force_exit`. It also checks that nothing is raised again.
   Both outcomes come from uvicorn's private `handle_exit`, so an upgrade that changes them now fails a
   test.

Found while fixing, and not changed here (Risks, the last two entries):
- A forced stop's `os._exit` can leave an abandoned thread's hidden temporary file behind.
- `JobsHub.stop()` joins its executor inside the app's cleanup. A poller read stuck on a stalled
  database therefore holds even a forced stop until the read returns. A WebSocket subscriber opened on
  the stalled database showed it: after the second SIGINT, the log had reached `hub.stop` start and the
  process was still up 6 s later. A third SIGINT ended it with 130, and the lifespan logged that
  `KeyboardInterrupt` as an error. The spec's MAY clause names this log.

## Failure behavior and idempotency

- **Bind failure:** uvicorn's `sys.exit(1)` raises through the subclass (no `clear()`) and `run()`.
  `cmd_serve` prints `error: could not bind <host>:<port>` and returns 1, as today.
- **A server shutdown that raises** (for example 0.51's `InvalidState` for a vanished peer,
  `jobs-ws-lifecycle` Risks) propagates as today: out of `run()` and `main()` as a traceback, exit 1.
- **An application (lifespan) shutdown that raises** is caught by uvicorn, which logs "Application shutdown
  failed" with the traceback and returns normally, so `serve` would exit **0**. No step in today's lifespan
  can raise at that point (Research, "A failed application shutdown"). Known gap; see Open Questions.
- **Forced stop:** 130, once every client connection has ended and the app's cleanup has run. A request
  handler still blocked in a worker thread is abandoned: `ServiceServer.run()` ends the process with
  `os._exit(130)` instead of letting the interpreter join that thread. uvicorn may log the handler it cut as
  "Exception in ASGI application", and the lifespan task's `CancelledError` as an error traceback.
- **Idempotency:** `serve` keeps no state across runs, and this change writes no file and no row. A restart
  behaves the same, and neither rendered output nor the job store is involved.
- **No decision outlives the change** beyond the headless-cli requirement itself. The spec is its durable home,
  so there is no new HLD D-n entry. D-A7 still holds: uvicorn's graceful shutdown is unchanged.

## Ownership (polish round)

P6 owns the `serve` command in `auto_reel_ng/cli/commands.py` (the new class, `cmd_serve` and its imports),
`tests/test_cli_serve.py`, the new `tests/test_cli_serve_signals.py`, README's `serve` stop paragraph, and the
api-service requirement "WebSocket live job updates" (one sentence; no other polish change has an
api-service delta). No web file and no other change's file is touched.

## Risks / Trade-offs

- **[uvicorn internals]** The subclass relies on `capture_signals` being what `serve()` wraps itself in, and
  on the name `_captured_signals`. → Strict mypy fails on a rename of either. The canary test fails if uvicorn
  stops re-raising, and the e2e return-code assertion fails if `serve()` stops calling `capture_signals`.
- **[Shell scripts and Ctrl-C]** By the "wait and cooperative exit" convention, a program stopped by Ctrl-C
  dies by SIGINT, so a calling shell script aborts too. With exit 0, a script that runs `serve` followed by
  other commands continues after Ctrl-C. → Accepted. The spec has promised exit zero since phase 7, `serve` is
  a long-running foreground service that is normally the last command, and supervisors (systemd, podman) read
  0 as a clean stop.
- **[A signal in the last instructions]** A signal that arrives after `clear()` but before
  `ServiceServer.run()` sets `SIG_IGN` is recorded and re-raised, or meets the handler uvicorn or asyncio
  restored, as before the change. → This is a new Ctrl-C at the moment the process exits, and it ends as
  today's traceback. Accepted. Corrected in review: the window that mattered was the interpreter's
  finalization after `main()` returned (about 0.2 s, about half of a whole stop), where a second signal
  killed `serve`. `SIG_IGN` now closes it. What remains is the gap from `clear()` to `SIG_IGN`: within
  one millisecond on an orderly stop (the reviewer's stage stamps), and on a forced stop also the app's
  cleanup, which runs in that gap ("Changed during review of the pull request", items 1 and 3).
- **[A forced stop abandons worker threads]** `os._exit(130)` ends a request handler still running in a
  worker thread wherever it is. Its temporary file can stay behind: a thumbnail extraction's
  `.<key>.<uuid>.tmp` in the thumbnail cache, or, in a write that lands in that instant, a `reel.yaml`
  writer's `.reel.yaml.<hex>.tmp` next to the file. Both are written to a hidden temporary name and
  renamed into place, so no thumbnail or `reel.yaml` is ever left half-written, and nothing reads the
  temporary names. → Accepted: the operator asked to stop now, and a killed or third-Ctrl-C'd process left
  the same files before. Nothing sweeps them yet (follow-up).
- **[The hub's stop waits for a store call]** `JobsHub.stop()` shuts its executor down with `wait=True`,
  inside the app's cleanup, which a forced stop also waits for. A poller read stuck on a stalled database
  (for example a subscriber's first read) holds every stop, forced or not, until that call returns
  (psycopg 3.3's default connect timeout is 130 s; a query on a connection whose server went silent has no
  bound). Measured in review: a third Ctrl-C interrupts it, the lifespan logs the `KeyboardInterrupt` as an
  error, and `serve` exits 130. → Pre-existing, in `api/` (`jobs-ws-lifecycle`'s decision to wait); out of
  scope, follow-up.
- **[Force-quit waits for open connections]** Pre-existing and unchanged (Research, "Force-quit still waits
  for open connections"). A second Ctrl+C behind a vanished peer still leaves `serve` running until the host's
  TCP stack abandons the connection. → The spec and README now say so; aborting the transports is the
  follow-up.
- **[A failed application shutdown exits 0]** Today the signal re-raise makes it non-zero by accident; after
  this change it is 0, with the failure in the log only. → Unreachable with today's lifespan (measured).
  The ASGI lifespan watch is prototyped if the supervisor wants it closed now (Open Questions).

## Migration Plan

None. The next `serve` start uses the new exit behavior. Rollback is reverting the commit.

## Open Questions

All three were decided by the supervisor before implementation (Research, "Supervisor decisions"): 130 is
accepted; a failed application shutdown exiting 0 is accepted as a recorded gap; the vanished-peer sentences
are corrected in this change, and aborting the transports stays a follow-up. The questions are kept as asked.

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
