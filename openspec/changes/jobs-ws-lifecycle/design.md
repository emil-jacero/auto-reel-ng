## Context

See proposal.md, "Why". Line numbers refer to `main` at `47e46f4`, after `jobs-project-guards` (C3), which
this change is gated on, was archived (`ed71d57`); `api/ws.py` there is byte-identical to the C3 branch's.
The code facts that shape the approach:

- **`ws_jobs`** (`api/ws.py:328-355`) does:
  1. `accept()`
  2. `queue = await hub.subscribe()`, inside a `try`
  3. a loop of `await queue.get()`: it `break`s on `_CLOSE` and otherwise calls `send_text`
  4. it catches `WebSocketDisconnect`, and its `finally` calls `hub.unsubscribe(queue)`

  It never calls `websocket.receive()`. Its docstring rejects "a concurrent 'detect disconnect promptly'
  reader task": that pattern (two tasks, and cancel the other when the first completes) "proved racy under
  test-harness teardown".
- **`JobsHub`** (`api/ws.py:58-303`):
  - `subscribe` starts the poller for the first subscriber (C2's `_start_polling`, safe against failure and
    cancellation).
  - `unsubscribe(queue, notify_close=False)` discards the queue. When no subscriber is left, it cancels the
    poller and drops the finished-jobs state. It is idempotent: `discard`, and a `None` check on the poller.
  - `stop()` puts `_CLOSE` on every queue, clears them, awaits the cancelled poller and shuts the executor
    down with `wait=True`.
  - A slow consumer is dropped by `_broadcast` → `unsubscribe(queue, notify_close=True)`, which puts `_CLOSE`
    on its queue.
- **The app's lifespan** (`api/app.py:77-82`) runs `await jobs_hub.stop()` and then `engine.dispose()` in its
  `finally`, when uvicorn sends the lifespan shutdown event.
- **`cmd_serve`** (`cli/commands.py:824-852`) builds `uvicorn.Config(app, host=..., port=...)`, so every
  other setting is uvicorn's default, and calls `server.run()`. uvicorn installs its own SIGINT and SIGTERM
  handlers.
- **Installed versions** (`auto-reel-ng/.venv`): uvicorn 0.51.0, websockets 16.1, starlette 1.3.1, FastAPI
  0.139.0; wsproto is not installed. A fresh `pip install -e ".[dev]"` resolves uvicorn 0.54.0, websockets
  17.1, starlette 1.7.0 and FastAPI 0.142.2 (`pip install --dry-run --report`, 2026-09-30).
- **The tests:**
  - `tests/test_api_ws_hub.py` drives the hub directly with a `FakeStore`.
  - `tests/test_api_ws_e2e.py` (`requires_db`) uses Starlette's `TestClient`.
  - `tests/test_cli_serve.py` (`requires_db`) runs `main(["serve", ...])` in a thread, where uvicorn
    installs no signal handlers, and stops it with `should_exit`.
  - No test runs the handler under a real server.

## Goals / Non-Goals

**Goals:**

- The end of a connection releases its subscription promptly, whichever side ends it or however it breaks.
- One SIGINT or SIGTERM ends `serve` through its orderly shutdown, with any number of sockets open.
- No change to the hub, the frame or the CLI's code.

**Non-Goals:**

- A graceful-shutdown timeout, a quieter signal exit from `serve`, or keepalive settings (proposal,
  Non-goals).

## Research & Decisions

### What uvicorn does with a WebSocket at shutdown and on a lost peer

**Context**: Whether the fix belongs in the handler, the lifespan or `serve` depends on the order in which
uvicorn does things.

**Explored**: read `uvicorn/server.py` and `uvicorn/protocols/websockets/` for 0.51.0 (installed) and 0.54.0
(downloaded, `pip download`). Then a scratch reproduction ran the branch's `JobsHub` over a fake store
behind (a) today's `ws_jobs` and (b) the handler below, served by `uvicorn.Server(Config(app, ...)).run()`
exactly as `cmd_serve` runs it, in a subprocess, driven by a `websockets` client (session scratchpad
`c7/serve_app.py`, `c7/driver.py`; poll interval 0.1 s).

- `ws="auto"` picks `WebSocketsSansIOProtocol` whenever `websockets` is importable, in both versions. It is a
  declared dependency.
- **`Server.shutdown()`**:
  1. closes the listeners
  2. calls `connection.shutdown()` on every connection. For an accepted WebSocket that puts
     `{"type": "websocket.disconnect", "code": 1012}` on the connection's **receive** queue, sends a close
     frame with 1012 and closes the transport.
  3. waits for every connection task to finish, under `timeout_graceful_shutdown`, which defaults to `None`,
     so the wait has no limit
  4. only then sends the lifespan shutdown event

  So `hub.stop()` cannot wake a handler in time. Closing live sockets from the lifespan would come too late
  for the same reason.
- **`handle_exit`** sets `force_exit` only for a *second SIGINT*; a repeated SIGTERM just sets `should_exit`
  again. `force_exit` skips the wait and the lifespan shutdown event.
- **The keepalive** defaults to `ws_ping_interval=20.0` and `ws_ping_timeout=20.0`. A ping left unanswered
  fails the connection (uvicorn sends 1011 and sets `close_sent`) and closes the transport. The timeout
  queues nothing itself: `connection_lost` puts the disconnect on the receive queue, and asyncio calls it
  only once the transport's write buffer is empty (`_SelectorTransport.close`). While frames are backed up
  for a peer that stopped acknowledging, that disconnect waits (see Risks).
- **An app-sent `websocket.close`** also puts a disconnect on the app's receive queue (0.51 and 0.54),
  unless uvicorn has already sent a close itself (keepalive failure): then the send raises `RuntimeError`
  ("after sending 'websocket.close'") and nothing is queued.
- **0.54 vs 0.51**: identical in all of the above. 0.54 adds two things:
  - write back-pressure: `pause_writing` clears `writable`, so a `send` to a peer that stops reading waits,
    and `connection_lost` sets it again. 0.51 has no `pause_writing`: its sends never wait, and a slow
    reader's frames pile up in the transport's buffer.
  - a closing handshake after an app close: the transport stays open for up to 10 s for the peer's echo.
    The disconnect is still queued at once. `shutdown()` only closes the transport of a connection that has
    already sent its close, where 0.51 raises `InvalidState` (see Risks).
- **starlette 1.7.0 vs 1.3.1**: the invalid-state errors become `WebSocketDisconnected(RuntimeError)`, and the
  test client's session is otherwise identical. The handler below guards on state and relies on neither
  error type.

The reproduction's results:

| Case | Today's handler | Handler below |
|---|---|---|
| Client closes, no job activity | still subscribed, poller running; 28 store reads in the next 1 s | released at once; 0 reads |
| One SIGINT, socket open | hangs at "Waiting for background tasks to complete"; the client got 1012; a second SIGINT force-exits with a `KeyboardInterrupt`/`CancelledError` traceback | exits in 0.31 s; "Application shutdown complete" |
| One SIGTERM, socket open | hangs (never exits by itself; SIGINT needed) | exits in 0.16 s |
| Silent peer (handshake, then never reads), ping 0.3 s / 0.3 s | still subscribed and polling after 2.8 s | released within 1.8 s; poller stopped |
| Hub drops the subscriber | transport closed with no close frame (client sees no code, 1006) | close frame 1013 |
| Peer stops reading while large frames back up (ping 0.2 s / 0.2 s; review probe `c7-review/tests/test_backlog_probe.py`) | 0.51: released, because its next send fails; 0.54: not released (send parked on the paused transport) | 0.51: released by the push task's own unsubscribe (without it: not released); 0.54: as today. Either way the connection stays open (Risks) |

**Decision**: the handler has to read the connection. That is the only place uvicorn reports every one of
these endings, a client close, a lost peer and its own shutdown, and it is not reported anywhere else in
time. The one ending that does not reach it in time is a lost peer behind backed-up frames. Its subscription is
released on 0.51 by the push task's own release (below) and on 0.54 by the hub's slow-consumer drop
(Risks). `serve` needs no change.

### The handler: a receive loop, with a push task it owns

**Context**: The handler has to wait on two things: the hub's queue (frames to push) and the connection
(its end). The rejected pattern cancelled whichever wait lost.

**Explored**:
- **`asyncio.wait({queue.get(), websocket.receive()}, FIRST_COMPLETED)` per frame, cancelling the loser.**
  It cancels a pending `receive()`, which is the pattern the docstring records as racy under the test
  harness. It also re-creates two tasks per frame.
- **A reader task that unsubscribes on disconnect, with the send loop kept in the handler.** When the hub
  ends the send loop first, the reader is still blocked in `receive()` and must be cancelled. That is the
  same hazard.
- **A serve-level `timeout_graceful_shutdown`.** It only bounds item 2, to the timeout, on *every* shutdown
  with a tab open. It fixes neither item 1 nor item 3, and it cancels in-flight REST requests too.
- **The receive loop in the handler, with pushing in a child task.** `receive()` is never cancelled by our
  code. The push task only ever waits on the hub's own queue or on a send, and cancelling either is safe.

**Decision**: in `api/ws.py`:

```python
async def _push_frames(websocket: WebSocket, hub: JobsHub, queue: asyncio.Queue) -> None:
    """Send the hub's frames until it lets this subscriber go (close 1013) or a send fails."""
    try:
        while (message := await queue.get()) is not _CLOSE:
            await websocket.send_text(message)
        await _close(websocket, WS_1013_TRY_AGAIN_LATER)    # dropped (slow consumer) or hub stopped
    except WebSocketDisconnect:
        pass                                            # the connection is gone; the receive loop sees it too
    except Exception:
        await _close(websocket, WS_1011_INTERNAL_ERROR)
        raise
    finally:
        await hub.unsubscribe(queue)                    # the push side's own end releases too (idempotent)


async def _close(websocket: WebSocket, code: int) -> None:
    if websocket.application_state is WebSocketState.CONNECTED:
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await websocket.close(code)


@router.websocket("/api/v1/ws/jobs")
async def ws_jobs(websocket: WebSocket) -> None:
    hub: JobsHub = websocket.app.state.jobs_hub
    await websocket.accept()
    queue: Optional[asyncio.Queue] = None
    pusher: Optional[asyncio.Task[None]] = None
    try:
        queue = await hub.subscribe()
        pusher = asyncio.create_task(_push_frames(websocket, hub, queue))
        # Push-only channel: what a client sends is read and ignored. The loop exists to see the end
        # of the connection: a client close, a lost peer (keepalive), the server's shutdown close (1012),
        # or our own close, which the server also reports as a disconnect.
        while (await websocket.receive())["type"] != "websocket.disconnect":
            pass
    finally:
        # Release first: nothing may suspend before the unsubscribe (see "Teardown order").
        if pusher is not None:
            pusher.cancel()
        if queue is not None:
            await hub.unsubscribe(queue)
        if pusher is not None:
            await asyncio.wait({pusher})            # never raises; the outcome is read below
    if pusher is not None and not pusher.cancelled():
        pusher.result()                             # re-raise an unexpected push error for uvicorn to log
```

- Imports: `from starlette.status import WS_1011_INTERNAL_ERROR, WS_1013_TRY_AGAIN_LATER` and
  `from starlette.websockets import WebSocketState`. Import the codes by name, not a bare `status` module:
  `_fetch_active_snapshot` has a `status` loop variable, which pylint flags as W0621 (checked).
- There is no `except asyncio.CancelledError: raise` clause. `CancelledError` is not an `Exception`, so the
  clause would be dead, and pylint flags it as W0706 (checked). A cancelled push task still runs its
  `finally`.
- The handler's docstring is rewritten. It names the receive loop and why it exists, the three close codes
  (uvicorn's 1012, and the handler's 1013 and 1011), why the push task, not `receive()`, is the one that
  gets cancelled, and why the push task releases the subscription itself.
- Both calls use `unsubscribe(queue)` without `notify_close`, as today. The push task is cancelled rather
  than woken with `_CLOSE`. `notify_close` stays for `_broadcast`.
- Once black-formatted, the snippet passes strict mypy and pylint (10.00) in the review's scratch copy of
  `main`.

**Rationale**:
- **Every ending reaches the loop.**
  - A client close, a keepalive timeout and a lost transport each put a disconnect on the receive queue,
    and so does uvicorn's shutdown (1012). The loop returns at once, and the subscription is released
    within uvicorn's own 0.1 s pause, before its task wait starts.
  - When the hub lets go (`_CLOSE`), the push task closes with 1013. uvicorn answers that close with a
    disconnect on the same receive queue, which ends the loop.
  - An unexpected push error closes with 1011 and ends the loop the same way.
- **The push side releases too.** One ending does not reach the loop in time. When uvicorn's keepalive
  fails a connection whose frames are backed up, it has already sent its own close, so the push task's
  next send raises `RuntimeError` and its 1011 close is refused. `connection_lost`, and with it the
  disconnect, then waits for the write buffer to drain. The push task's `finally` therefore unsubscribes
  whenever the push side ends: the hub let go, a send failed, or it was cancelled. `unsubscribe` is
  idempotent, so the second of the two releases is a no-op. In the review's probe the design without this
  release kept the subscriber and the poller on 0.51, where today's handler releases them; with it, 0.51
  releases them. The error is still re-raised once the connection ends.
- **No cancellation of `receive()`.** The one task cancelled is ours. It is waiting on `queue.get()` or on a
  send (uvicorn's `writable.wait()`), and cancelling either is safe. That includes a send parked on 0.54's
  paused transport.
- **The hub is untouched.** The last unsubscribe cancels the poller, as today. During shutdown the handlers
  finish first, so `hub.stop()` then finds no subscriber and no poller. It still waits for any in-flight
  store call (`executor.shutdown(wait=True)`) before `engine.dispose()`.

### Teardown order: unsubscribe before any suspension

**Context**: Starlette's `TestClient` ends a session by delivering the disconnect and then *immediately*
cancelling the app's cancel scope (`WebSocketTestSession.__exit__`: `close(1000)`, then `cs.cancel`), so
cancellation lands while the handler is still cleaning up.

**Explored**: the handler above, with its cleanup first written as "cancel the pusher, `await
asyncio.wait({pusher})`, then unsubscribe". It ran 300 `TestClient` connect → read snapshot → exit cycles
over the fake-store hub (`c7/testclient_check.py`), asserting after each that the hub has no subscriber and
no poller. It failed at cycle 48: the scope's cancel landed in `asyncio.wait` and skipped the unsubscribe,
which left a subscriber and a running poller. With the unsubscribe first, 3 × 300 cycles passed, with no
asyncio "exception never retrieved" log record, and a hub-initiated close reached the test client as 1013.
This is very likely the race the current docstring describes.

The review re-ran this as the planned 200-cycle test (task 2.1). With the push task's own release added,
it passed in every run. With the cleanup reversed (wait, then unsubscribe), it failed within 200 cycles in
5 of 5 runs, at cycles 2 to 123.

**Decision**: the `finally` cancels the pusher (synchronous), then unsubscribes, then waits for the pusher.
The push task's own release is a second one, and the handler does not rely on it: a cancelled task runs
its `finally` only when it is next scheduled.
`unsubscribe` suspends only when the hub's lock is held (a concurrent first subscribe or a slow-consumer
drop). A cancellation that lands exactly there can only come from a test harness. uvicorn never cancels a
connection task (`timeout_graceful_shutdown` is `None`), and at loop teardown `hub.stop()` clears every
subscriber anyway.

### Close codes

**Decision**:

| Code | Sent by | When |
|---|---|---|
| **1012** (service restart) | uvicorn | on shutdown; nothing of ours |
| **1013** (try again later) | the handler | when the hub drops the subscriber (slow consumer) or stops |
| **1011** (internal error) | the handler | when the push task fails unexpectedly; the error is re-raised |

A client's own close needs no reply from the handler: uvicorn completes the handshake.

**Rationale**: a close frame is what ends the receive loop when the hub lets go, so *some* code is needed.
1013 says what the client should do: reconnect, which yields a fresh snapshot. C5 reconnects after any close,
so no client change is needed.

### Keepalive: uvicorn's defaults, pinned by a test

**Context**: Item 3 needs a server ping. uvicorn already sends one (20 s / 20 s), and once the handler reads
the connection, the ping's timeout releases the subscription (the reproduction's silent-peer case).

**Explored**: explicit `ws_ping_interval`/`ws_ping_timeout` arguments in `cmd_serve`, or `api.*` config
keys. The first changes `cli/` code only to restate the defaults. The second is a knob no operator needs
(Principle VII).

**Decision**: no code. `tests/test_cli_serve.py` captures `serve`'s `uvicorn.Config` (the existing
`_FakeServer` pattern) and asserts `ws_ping_interval == 20.0` and `ws_ping_timeout == 20.0`, so an upstream
change of the defaults fails the suite rather than silently changing the spec'd 40 s window.

### Tests: a real server in-process, and `serve` in a subprocess for the signal

**Context**: `TestClient` cannot show items 1–3. Its session exit cancels the handler, which also
unsubscribes today's handler, and it has no transport, keepalive or server shutdown.

**Decision**:
- **`tests/test_api_ws_lifecycle.py`**, with no database. An async context manager builds a minimal
  `FastAPI` app with the WS `router`, a `JobsHub` over the `FakeStore` of `tests/test_api_ws_hub.py`, and a
  lifespan calling `hub.stop()`. It runs `uvicorn.Server(Config(app, host="127.0.0.1", port=<free>,
  log_level="warning", log_config=None, **overrides)).serve()` as a task on the test's loop, and ends with
  `should_exit = True`.
  - `log_config=None` matters. uvicorn's default logging config sets the `uvicorn` logger to
    `propagate=False` for the rest of the pytest process, so `caplog` never sees "Exception in ASGI
    application" (checked).
  - Clients use `websockets.asyncio.client.connect`. The silent peer is a raw `asyncio.open_connection`
    that sends the upgrade request, reads the 101 and then nothing.
  - Import `FakeStore`/`FakeJob` from `test_api_ws_hub.py`. `tests/` has no `__init__.py`, so pytest's
    default import mode resolves it (checked).
  - A slow consumer cannot be produced by leaving the client unread. The push task drains the one-slot
    queue into the transport, and 0.51 never makes a send wait. So the test gates `WebSocket.send_text`:
    its second call waits on an `asyncio.Event` until the hub has dropped the subscriber.

  Prototyped as `c7/test_lifecycle_proto.py` (five cases). The review's scratch module
  (`c7-review/tree/tests/test_api_ws_lifecycle.py`) covers every Verify bullet of tasks 2.1–2.3. It passed
  in about 3.2 s on every run on uvicorn 0.51 and 0.54 (starlette 1.3.1 and 1.7.0). Against today's handler,
  every case but the `TestClient` cycles failed.
- **`tests/test_cli_serve.py`**, `requires_db`: `[sys.executable, "-m", "auto_reel_ng.cli.main", "serve",
  <tmp root>, "--host", "127.0.0.1", "--port", <free>]` as a subprocess, with `DATABASE_URL` set to the
  container. Only a main-thread process gets uvicorn's signal handlers, and an in-process `serve()` would
  re-raise the captured signal into pytest. The test is parametrized over SIGTERM and SIGINT.
  - It requests `jobs_schema_engine`: `postgres_container` alone has no `jobs` table, and the snapshot read
    fails without one.
  - Prototyped in the review scratch: SIGTERM exited in 0.12–0.20 s and SIGINT in 0.43–0.51 s (rc −15 and
    −2). Against today's handler both cases failed on the 5 s `communicate` timeout, and the `finally` kill
    left no process behind.

## Failure behavior and idempotency

- **A failed first subscribe** (database down) raises out of the handler as today. C2's `_start_polling`
  leaves the hub as it was, and no push task exists. uvicorn logs the error and closes the connection, and
  the client reconnects.
- **A disconnect while subscribing** is queued by the server and seen by the first `receive()`, so the
  subscriber that was just registered is released at once.
- **An unexpected push error** closes with 1011, and the push task releases the subscription at once. The
  error is re-raised once the connection ends, so uvicorn logs "Exception in ASGI application". Nothing is
  swallowed (Principle I).
- **A double release is harmless.**
  - The push task's `finally` and the handler both unsubscribe. After a slow-consumer drop or `hub.stop()`
    there is a third release. Every release after the first is a no-op: `discard`, with no poller to cancel,
    or, when another subscriber has joined meanwhile, a poller that keeps running.
  - A `_close` after the connection has ended is skipped (the state check) or suppressed.
- **Reconnect** yields a fresh snapshot, as before. After the last subscriber leaves, it is now always a
  fresh read.
- **Worker restart mid-render**: unaffected. The worker does not use the WebSocket.
- **`serve` restart** (one signal): every client sees 1012 and reconnects when the service is back.
- **Nothing here renders or writes files.** No `RENDER_GRAPH_VERSION` bump, and no fingerprint, manifest or
  schema change.

## Risks / Trade-offs

- **[A subscribe stuck on a hung database]** The receive loop starts after `subscribe` returns. A first
  subscriber's two store reads that hang (a database host gone silent, psycopg without a connect timeout)
  delay that handler's release, and so shutdown. → The disconnect is queued and seen as soon as the reads
  return. A second SIGINT still forces the exit, and the reads are milliseconds otherwise. A graceful
  timeout is a named follow-up if this ever shows up.
- **[Test harness cancellation]** The teardown order is load-bearing under `TestClient`. → The docstring says
  so, and the existing `tests/test_api_ws_e2e.py` runs a `TestClient` teardown on every test. Task 2.1 adds a
  repeated connect/exit test that asserts the hub is empty and idle after each cycle.
- **[A vanished peer behind backed-up frames]** When a peer stops acknowledging (a laptop suspended
  mid-render) after the frames sent to it have filled the host's TCP send buffer, asyncio holds them in the
  transport. uvicorn's keepalive close then cannot finish: `connection_lost`, and so the disconnect, waits
  until the buffer drains or the host's TCP stack abandons the connection, which is minutes on Linux
  defaults. The review's probe (a raw peer that stops reading, 20 jobs with 50 kB frames, ping 0.2 s /
  0.2 s) showed:
  - **Subscription.** On 0.51 the push task's next send fails, and its own release frees the subscription
    (above). On 0.54 the send waits on the paused transport, so the subscription stays until the hub drops
    it as a slow consumer. That happens once 64 frames have queued, and a feed that goes quiet never fills
    the queue. Today's handler behaves the same on 0.54.
  - **Shutdown.** The connection itself stays open. On 0.51, `Server.shutdown()` raises `InvalidState`
    ("connection is closing") from that connection's `shutdown()`, so `Server.serve()` fails before the
    lifespan shutdown event is sent: the orderly `hub.stop()` / `engine.dispose()` is skipped. On 0.54,
    shutdown waits at "Waiting for connections to close" until a second SIGINT. Both are uvicorn behavior,
    the same with today's handler, and out of the handler's reach.
  - **Noise.** The failed send takes the 1011 path, so uvicorn logs a `RuntimeError` ("after sending
    'websocket.close'") as "Exception in ASGI application" once the connection ends.

  → Accepted and stated in the spec as the exception to its 40 s and one-signal bounds. Whether a feed fills
  the buffer before the keepalive fires depends on two things:
  - the kernel's send buffer: Linux starts it at 16 KiB (`net.ipv4.tcp_wmem`) and grows it
  - the feed's rate: one running job's delta is about 0.5 kB per poll

  So a suspended laptop during a render can hit this, and a quiet feed cannot. The TCP stack gives up
  after `net.ipv4.tcp_retries2` = 15 retries, about 15 min. A graceful-shutdown timeout would bound 0.54's
  wait but not 0.51's abort, and it stays a follow-up (proposal, Non-goals). The real fix is in uvicorn,
  whose keepalive and shutdown `close()` a transport that `abort()` would drop at once. Reporting it
  upstream is a follow-up outside `api/`.
- **[Clients that send data]** Every message is read and discarded. → uvicorn bounds a message to
  `ws_max_size` (16 MiB) and pauses reading until the app has drained each message. The GUI sends nothing.
- **[A future server swap]** The design relies on the server delivering a disconnect after an app close and
  on shutdown. Both are ASGI WebSocket semantics, and both uvicorn protocol implementations here do it. →
  The in-process tests fail loudly if a server stops doing it.
- **[Pre-existing: signal exit status]** After a graceful shutdown uvicorn re-raises the captured signal.
  `serve` therefore still ends with rc −2 (and a `KeyboardInterrupt` traceback) or −15. → Unchanged and out
  of scope. The e2e test asserts the process ended and the log, not the return code.

## Migration Plan

None. Deploying is restarting `serve`, and during that restart every open tab gets today's 1012 and
reconnects. Rollback is reverting `api/ws.py`.

## Open Questions

None.
