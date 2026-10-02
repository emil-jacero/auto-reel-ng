## Context

See proposal.md, "Why", for the three findings. The code on `main` at `6a7fe16`:

- `JobsHub` (`api/ws.py`) runs every store call on a private single-thread `ThreadPoolExecutor`
  (`_executor`, D-A5), through `loop.run_in_executor`. `subscribe()` holds `self._lock` while it awaits
  `_start_polling()` (two executor reads, then `create_task(_poll_loop())`) for the first subscriber.
  `unsubscribe()` takes the same lock, cancels the poller when the last subscriber leaves and resets the
  finished-jobs state. `stop()` takes the lock, closes every subscriber, releases it, cancels and awaits the
  poller, then calls `self._executor.shutdown(wait=True)` on the event loop.
- Cancelling a task that awaits `run_in_executor` cancels the awaiting future only. The executor thread keeps
  running the store call until it returns; its result is dropped. So `unsubscribe()` stopping the poller does
  not free the thread, and `shutdown(wait=True)` is what joins it.
- `app.py`'s lifespan: `finally: await jobs_hub.stop(); engine.dispose()`. `Engine.dispose()` closes the
  checked-in connections and only detaches checked-out ones (SQLAlchemy 2.0 docs): a connection an abandoned
  store call still holds is closed when that call returns it. It is not interrupted.
- `ws_jobs` (`api/ws.py`) does `queue = await hub.subscribe()`, then starts a push task and loops on
  `websocket.receive()` until the disconnect. During the `await hub.subscribe()` it reads nothing.
- uvicorn's shutdown (`Server.shutdown`) closes the listeners, asks every connection to close (a WebSocket
  gets 1012), waits for the connections and for the ASGI tasks it started, and only then runs the lifespan
  shutdown. A handler that is not reading does not end on the close. Measured with a handler that sleeps 6 s
  after `accept()`: `serve()` returned 5.8 s after `should_exit`, with the lifespan shutdown at the same
  moment (scratch experiment, not committed). A thread still inside a database call at exit also kept a scratch process alive until released.
- `make_engine` is `create_engine(database_url, future=True)`. Its callers: `api/app.py`, `cli/commands.py`
  (`_job_store`, used by `enqueue`, `jobs`, `worker`) and `scripts/make_dev_library.py`. The driver is
  psycopg 3 (`postgresql+psycopg://`, the dev default); it accepts libpq's `connect_timeout` as a keyword.
  Tests build the engine on `postgresql+psycopg://` URLs (`tests/conftest.py`).
- Executor worker threads are not daemons: `concurrent.futures` joins them at interpreter exit. Whatever
  `stop()` does, a thread still inside a database call keeps the *process* alive until the call returns.

## Goals / Non-Goals

**Goals:**
- `JobsHub.stop()` returns promptly and never blocks the event loop, whatever the database is doing.
- A stalled first-subscriber snapshot read holds neither the client's own close nor the service's shutdown.
- No connect to Postgres waits longer than 5 s unless the operator's URL says otherwise.

**Non-Goals:**
- Interrupting a database call that is already running (proposal, Non-goals). No `statement_timeout`.
- Replacing the executor with daemon threads so that process exit does not wait either. Considered below.
- Any change to frames, close codes other than using the existing 1013, poll cadence, or `unsubscribe` outside
  shutdown.

## Research & Decisions

### Stop signals first, then takes the lock

**Context**: `stop()` takes `_lock` first, so a stalled first subscribe (which holds it) blocks `stop()`
(finding 2). Holding the lock across a database read is the root, but it is what makes the "first subscriber
starts the poller" step atomic against `unsubscribe`.
**Explored**: (a) a timeout on the seed; (b) `wait_for` on `stop()`'s lock; (c) a stopping flag plus a
cancellable seed task.
**Decision**: (c). `JobsHub` gains `_stopping: bool` and `_start_task: Optional[asyncio.Task]`.
`_start_polling` runs the two seed reads as a task it stores in `_start_task` and awaits it. `stop()`:

```python
async def stop(self) -> None:
    self._stopping = True                      # 1. signal: nothing new starts
    if self._start_task is not None:
        self._start_task.cancel()              #    wakes a subscribe parked on the seed
    poller = self._poller_task
    self._poller_task = None
    if poller is not None:
        poller.cancel()
    async with self._lock:                     # 2. now free: the cancelled seed released it
        for queue in list(self._subscribers):
            self._force_put(queue, _CLOSE)
        self._subscribers.clear()
    if poller is not None:                     # 3. a cancelled poller ends at its next await
        with contextlib.suppress(asyncio.CancelledError):
            await poller
    self._executor.shutdown(wait=False, cancel_futures=True)   # 4. never joins
```

`subscribe()` checks `_stopping` before and after taking the lock; when set it returns a queue holding only
`_CLOSE` (not registered), so the handler's push task closes the connection with 1013 like any dropped
subscriber. A seed task cancelled by `stop()` (the awaiting subscriber itself was not cancelled, which
`asyncio.current_task().cancelling()` tells) makes `_start_polling` report "stopped" rather than raise
`CancelledError`; a cancel of the subscriber itself still propagates and resets the finished-jobs state, as
today. `stop()` is idempotent (a second call finds the flag set and `shutdown` is a no-op).
**Rationale**: the signal needs no lock, the lock is then uncontended, and the existing "start that fails or is
cancelled leaves the hub as it was" contract (`_start_polling`'s `except BaseException`) is reused as is.
(a) adds a magic number, shifts a slow-but-working database into a client-visible failure, and still holds
shutdown for its length. (b) leaves the subscriber parked and the lock held.

### The executor is released, not joined

**Context**: `shutdown(wait=True)` on the loop is finding 1. The reason for `wait=True` was that the lifespan
disposes the engine right after `stop()` and an in-flight call would race a closing pool.
**Explored**: `await loop.run_in_executor(None, executor.shutdown)` under `wait_for` (moves the join to the
default executor, whose own `shutdown_default_executor` at the end of `asyncio.run` then waits up to 300 s for
it, so it relocates the stall); `wait=False` alone; `wait=False, cancel_futures=True`.
**Decision**: `shutdown(wait=False, cancel_futures=True)`. Work queued behind the running call is cancelled
(its awaiters are already cancelled, so nothing observes it); the running call is abandoned.
**Rationale**: the race the `wait=True` guarded is benign. `dispose()` never touches a checked-out
connection (Context); the abandoned call finishes on it and returns it to a pool nothing refers to. A call
that raises after `stop()` raises into a future nobody awaits; `concurrent.futures` does not log that.
The stop path never schedules onto the shut-down executor: the flag keeps `subscribe()` out, the poller is
cancelled before the shutdown and `_tick` runs only inside it.

### The handler watches the connection while its first subscribe is stalled

**Context**: without this, finding 2 persists in the running service: `stop()` is reached only after the
handler returns (Context, uvicorn's shutdown), and the handler is parked in `subscribe()`.
**Explored**: (a) rely on `stop()` waking subscribers (unreachable until the handler ends); (b) a seed
timeout (the same objections as above, and the shutdown would still last the timeout); (c) race the subscribe
against the receive loop.
**Decision**: (c). The handler starts `subscribe()` as a task and waits for the first of that task and the
connection's next message:

```python
subscribing = asyncio.create_task(hub.subscribe())
incoming = asyncio.create_task(websocket.receive())
await asyncio.wait({subscribing, incoming}, return_when=asyncio.FIRST_COMPLETED)
```

If `incoming` finished first with `websocket.disconnect` (the client closed, the peer was lost, or the server's
shutdown closed the connection), the handler cancels `subscribing`, awaits it, and ends: the cancelled
subscribe releases the lock and abandons the seed, exactly as a cancelled start does today. If `incoming`
finished first with an ordinary message, the handler drops it, starts a new `receive()` task, and keeps
waiting. If `subscribing` finished first, the handler continues as today (push task, then the receive loop,
reusing the pending `incoming` task as its first read). The old rule "only the push task is ever
cancelled, never `receive()`" is narrowed: while the handler runs normally the `incoming` task is awaited to
the connection's end, and it is cancelled only when the handler ends before the connection does (the
handler's own cancellation, as TestClient's session exit causes, or a first subscribe that fails). Both go
through the same `finally`, which releases the subscription before its first suspension and then cancels the
pending `receive()`; uvicorn's `receive` is cancel-safe.
**Rationale**: a client that closes its tab during a database stall is released at once instead of when the
database answers, and the shutdown reaches `stop()` on the close the server already
sends. Cost: the handler body gains a second task and a wait. Principle V is unaffected: this is WebSocket
connection handling, which only the API has.

### Connect timeout is a Postgres connect argument with a module constant

**Context**: finding 3. The triage suggested "config-overridable".
**Decision**: in `persistence/engine.py`, `CONNECT_TIMEOUT_SECONDS = 5` and

```python
def make_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, object] = {}
    if (
        url.get_backend_name() == "postgresql"
        and "connect_timeout" not in url.query
        and "PGCONNECT_TIMEOUT" not in os.environ
    ):
        connect_args["connect_timeout"] = CONNECT_TIMEOUT_SECONDS
    return create_engine(url, future=True, connect_args=connect_args)
```

**Rationale**: a key in `config.yaml` has no use no one has asked for (Principle VII), and `DATABASE_URL`
already is the operator's override: `?connect_timeout=30` in the URL wins (psycopg would otherwise let the
keyword override the conninfo, so the guard matters). libpq's `PGCONNECT_TIMEOUT` environment variable is honoured the same way: when it is set, no keyword is passed (the keyword would silently beat it). Only Postgres gets the argument: other drivers reject it.
`make_url(...)` is passed to `create_engine` as given, so the password is not re-rendered or logged. 5 s covers
a cold container and a LAN and is short enough to sit inside the "few seconds" of the stop contract.
**Failure behavior** (Principle I): the connect raises the driver's `OperationalError` with its libpq text
("connection timeout expired"), which every existing path already handles: a REST route's 5xx, `/healthz`'s 503
with the message, the worker's per-poll error, the CLI's non-zero exit. Nothing is swallowed or retried here.

### Idempotency

`stop()` twice is a no-op the second time. A `subscribe()` after `stop()` gets a closed queue, never an error.
A restart of the service builds a fresh hub, engine and executor. `make_engine` is stateless. Nothing is
persisted and no job state changes, so there is no re-run or `--force` interaction.

### Not doing: daemon threads for the executor

The executor could be a hand-rolled daemon thread so process exit would not wait for an abandoned call. It
would replace D-A5's executor with bespoke code to cover only a stall in an established connection, which
the connect bound does not address and which needs the `statement_timeout`/keepalive decision first. Left as
a follow-up if an outage of that shape is ever observed; the spec says plainly what waits.

## Risks / Trade-offs

- [An abandoned store call keeps running after `stop()`] -> it holds one checked-out connection and, at
  interpreter exit, the process. For a connect stall that is at most 5 s plus the OS; for a mid-query stall it
  is TCP's own timeout. Stated in the spec and README rather than hidden.
- [The handler's two-task wait changes a delicate piece of lifecycle code (`jobs-ws-lifecycle`)] -> the
  existing lifecycle tests stay unchanged and green (200-cycle TestClient teardown, keepalive, slow consumer,
  1012 shutdown), and new tests cover the stalled-seed paths through a real `uvicorn.Server`.
- [A 5 s connect bound could fail a connect to a database that needs longer, e.g. a cold start] -> the URL's
  `connect_timeout` overrides it, `worker` retries on its next loop, and `/healthz` reports it.
- [`current_task().cancelling()` distinguishes a stop-cancelled seed from a cancelled subscriber] -> Python
  >= 3.13 is required by the project, so the API exists; a test cancels the subscriber mid-seed and asserts the
  hub is as it was.
- [Tests that block a store need releasing, or they leak a thread past the test] -> the fake store blocks on a
  `threading.Event` the test sets in a `finally`, rather than sleeping 20 s.
