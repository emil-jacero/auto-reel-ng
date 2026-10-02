## Context

See proposal.md for the motivation. The code facts, checked on `main` `99224ab`:

- `api/ws.py` `_push_frames(websocket, hub, queue)` is the per-connection push loop:
  `while (message := await queue.get()) is not _CLOSE: await websocket.send_text(message)`. The queue is
  fed by `JobsHub.subscribe()` (the snapshot) and `_broadcast()` (deltas, only when a tick found some). A
  quiet service therefore sends nothing between the snapshot and the next change.
- `api/schemas.py` `WsMessageType` is `SNAPSHOT | DELTA`; `WsMessage.jobs` is required. `publish_ws_schema`
  puts both into the OpenAPI components, `web/openapi.json` and `web/src/api/schema.d.ts` are generated
  from them, and `tests/test_api_openapi.py` asserts the enum is exactly `["snapshot", "delta"]`.
- `web/src/jobs/store.ts` holds the tab's one socket. `connect()` registers `message`, `close` and `error`
  handlers; `close` (for the current socket only) sets `reconnecting` and schedules a full-jitter retry;
  `FRAME_TYPES: Record<WsMessageType, true>` and the `switch` in `onFrame` are exhaustive over the
  generated type, so a new type fails `tsc` until handled. `live` is set only by a snapshot
  (`applySnapshot`), so a heartbeat can never be what makes the header read live.
- The existing keepalive is uvicorn's WebSocket ping (20 s interval, 20 s timeout). It protects the
  server's resources and is answered by the browser's network stack, never visible to page JavaScript.

**Ordering with `jobshub-stop-and-db-timeouts`.** That change also edited `api/ws.py` (`JobsHub.stop()`
takes a stopping flag, cancels the poller before the lock and shuts the executor down without waiting) and
`tests/test_api_ws_lifecycle.py`, and is now on `main` (`99224ab`). Neither this change's server code nor its
tests depend on those internals: the heartbeat lives in `_push_frames` and a module constant, and does not
touch `JobsHub`. The only shared surface is that `stop()` still ends a connection by putting `_CLOSE` on its
queue, which this design relies on (a heartbeat wait is cancelled the moment `_CLOSE` arrives).

## Goals / Non-Goals

**Goals:**

- A client can tell an idle healthy connection from a dead one within a bounded time, using only what page
  JavaScript can observe.
- A dead connection takes the existing reconnect path, with the header reading "reconnecting".
- No new store reads, no new queue pressure, no change to the hub.

**Non-Goals:** as in proposal.md. Additionally: no heartbeat payload (no timestamp, no sequence number): the
frame's arrival is the whole signal, and the client trusts no content of it.

## Decisions

### A heartbeat is a frame, not a WebSocket ping

**Context**: The browser WebSocket API exposes no ping or pong, so the server's keepalive proves nothing to
the client. The client needs a signal it can observe.

**Explored**: (a) server pings: invisible to JS. (b) A client-to-server ping with a reply: needs a request
handler on a channel that is deliberately push-only ("anything a client sends is ignored"), and a reply
path. (c) Polling a REST endpoint on a timer: forbidden by the web-app spec ("SHALL NOT poll any jobs or
events endpoint on a timer"). (d) A data frame the server sends unprompted.

**Decision**: (d): `WsMessageType.HEARTBEAT = "heartbeat"`, sent as `{"type": "heartbeat", "jobs": []}`.

**Rationale**: It reuses the one frame shape (`jobs` stays required, empty), keeps the channel push-only,
and the type set is a closed generated enumeration, so the client is forced by `tsc` to handle it.

### One per-connection timer in `_push_frames`; the poller is untouched

**Context**: Heartbeats are about a connection, not about jobs. Sending them through the hub's `_broadcast`
would put them on the bounded subscriber queues, where a slow consumer's heartbeats would count towards its
drop, and would tie them to the poller, which runs only while subscribed (it is, but the coupling buys
nothing).

**Decision**: The push loop waits for the next queued message for at most the heartbeat interval and sends a
heartbeat when none came:

```python
#: Silence after which a connection is sent a heartbeat frame (seconds); a module constant (VII).
_HEARTBEAT_INTERVAL_S = 15.0
_HEARTBEAT = WsMessage(type=WsMessageType.HEARTBEAT, jobs=[]).model_dump_json()

async def _next_message(queue: asyncio.Queue) -> object:
    try:
        return await asyncio.wait_for(queue.get(), _HEARTBEAT_INTERVAL_S)
    except TimeoutError:
        return _HEARTBEAT
```

and `_push_frames` becomes `while (message := await _next_message(queue)) is not _CLOSE:`. The interval is
read at each wait, so a test patches `ws._HEARTBEAT_INTERVAL_S`.

**Rationale**:

- *Idle-based, not fixed-rate.* The timer restarts after every message, so a connection with frames at
  least every 15 s sends no heartbeat. The client resets its window on every frame, so the window is the
  same either way.
- *No lost frame.* Cancelling `queue.get()` on timeout leaves the item in the queue (a getter dequeues only
  after it wakes), so a delta racing the timeout is delivered by the next iteration, once, in order.
- *`_CLOSE` is prompt.* A hub stop or slow-consumer drop puts `_CLOSE` on the queue, which wakes the wait
  immediately; the 1012/1013 close paths and `finally: hub.unsubscribe` are unchanged.
- *No new work for the hub.* The heartbeat string is encoded once at import; sending it is one
  `send_text`. It never touches `subscribe`, `_tick`, the executor or the store.
- *First frame.* The snapshot is already on the queue when the loop starts, so a heartbeat can precede
  nothing: it is never the first frame.

**Failure behaviour**: a heartbeat send is an ordinary send. `WebSocketDisconnect` ends the push quietly and
the receive loop releases the subscription; any other error closes 1011 and is re-raised, exactly as for a
delta (spec: "A push error closes with 1011" is existing behaviour, not restated).

### The client drops a silent socket itself

**Context**: `WebSocket.close()` on a connection whose peer is gone starts a closing handshake that the peer
never answers; the `close` event fires only when the browser gives up, which is browser-dependent and can be
long. Relying on it would make the watchdog detect in 40 s and then wait on top of that.

**Decision**: In `store.ts`, move the body of the `close` handler into a function `lost(opened)` and call it
from both the handler and the watchdog:

```ts
// Frames must arrive within this window (the service sends one at least every 15 s).
const SILENCE_MS = 40_000
let watchdog: number | undefined

function armWatchdog(opened: WebSocket): void {
  window.clearTimeout(watchdog)
  watchdog = window.setTimeout(() => {
    if (opened === socket) {
      console.warn('jobs WebSocket: silent; reconnecting')
      lost(opened)
      opened.close() // best effort; its close event is dropped by the identity guard
    }
  }, SILENCE_MS)
}

function lost(opened: WebSocket): void {   // was the 'close' handler body
  window.clearTimeout(watchdog)
  socket = null
  setConnection('reconnecting')
  /* full-jitter retry exactly as today */
}
```

- `connect()` calls `armWatchdog(opened)` right after creating the socket, so a connection that never
  completes (a black-holed SYN) is also bounded; `onFrame` calls it after a frame has validated, for every
  type. A malformed frame still closes the socket and does not re-arm.
- `socket = null` happens before `opened.close()`, so the guard `opened !== socket` in the `close` and
  `message` handlers drops everything the dying socket does afterwards: no second reconnect, no stale frame
  applied.
- `stop()` clears the watchdog together with `retryTimer`. The `close` handler path for the current socket
  calls `lost`, which clears it.
- `onFrame` gains `case 'heartbeat': break`. It still sets `attempt = 0` (a valid frame arrived) and takes no
  other action: it calls neither `commit` nor `notify`, so no subscribed screen re-renders.
- `FRAME_TYPES` gains `heartbeat: true`.

**Rationale**: The reconnect machinery (backoff, `online`, snapshot reconcile of jobs that ended meanwhile)
is untouched; the watchdog only adds a second way into it. Because `attempt` is reset by every valid frame,
a socket that delivered frames and then went silent reconnects after at most 500 ms of jitter, while one
that never delivered any backs off as before.

### Intervals: 15 s and 40 s, constants

15 s is well under uvicorn's 20 s ping and any common NAT idle timeout (30-60 s). 40 s is more than two
intervals: it tolerates one lost or late heartbeat plus scheduling jitter before declaring the connection
lost, and a false positive costs only a reconnect and a fresh snapshot. Neither is configurable: there is
no real use for a different value (Principle VII). The two constants are named in each other's comments, and
the web-app spec states both numbers.

## Risks / Trade-offs

- [A tab throttled in the background fires its timer late, possibly before queued frames are delivered, and
  drops a healthy socket] → the cost is one reconnect with a fresh snapshot, which the store already
  reconciles; detection only ever gets later when throttled, never wrongly skipped.
- [An older web bundle, cached in a tab across the upgrade, treats `heartbeat` as a malformed frame and
  reconnects] → the valid snapshot resets that bundle's backoff, so the stale tab loops: snapshot, a
  malformed heartbeat 15 s later, a reconnect within 500 ms, and the header flaps Live/Reconnecting about
  every 15 s until the tab is reloaded. The service serves its own bundle, so a reload fixes it; a
  malformed-frame reconnect is the existing, loud failure for an unknown type, and the exhaustive `Record`
  is what keeps a new bundle from ever missing one.
- [A heartbeat says the connection is alive, not that the hub is polling successfully] → out of scope
  (proposal Non-goals); a wedged poller shows as no progress, as it does today.
- [A busy connection sends no heartbeats, so its liveness rests on delta frames] → intended: any frame
  resets the window, and a busy connection has them.
- [The 40 s detection time is not instant] → a dead connection reads "Live" for at most 40 s instead of
  indefinitely.

## Migration Plan

No data migration. Server and bundle ship together (the service serves its bundle); rollback is reverting
both. A server older than the bundle never sends a heartbeat and a client newer than it would reconnect
every 40 s on an idle connection, so the two must not be mixed; the packaged image and the local build
always carry both.

## Open Questions

None.
