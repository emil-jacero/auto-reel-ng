## Why

GUI v1 slice **E** (HLD **§6 phase 8**, §4.10: "schedule a render and watch live progress") keeps a
`WS /api/v1/ws/jobs` socket open in every tab (`render-progress-screen`, C5: one WebSocket hook per tab that
reconnects after any close). The hub's contract rests on two api-service decisions that the handler does not
keep today:

- **D-A4:** the central poller runs "only while ≥1 subscriber is connected".
- **D-A7:** "SIGINT/SIGTERM → uvicorn's graceful shutdown; the hub poller is cancelled cleanly".

The handler (`api/ws.py:328-355` on `main`, unchanged since `jobs-project-guards` merged) is a send loop
only. It waits in `queue.get()` on the hub's queue and never reads from the client; its docstring records
that a concurrent reader "proved racy under test-harness teardown". Three consequences, each reproduced
against the installed uvicorn 0.51.0 and websockets 16.1 (design "Research & Decisions"):

1. **A closed tab keeps the poller running.** A client that closes stays subscribed until a broadcast fails
   on its dead socket. With no job activity no broadcast happens, so the poller keeps querying Postgres every
   `api.poll_interval` with nobody connected. The reproduction, over a fake store, counted 28 store reads in
   1 s at a 0.1 s interval, and task 5.1 checks it on Postgres through `pg_stat_activity`. A later
   subscriber then joins that poller and gets its cached snapshot, up to one poll interval old, instead of
   a fresh read.
2. **One signal does not stop `auto-reel serve` while a socket is open.** uvicorn's shutdown sends the client
   close code 1012 and puts a disconnect on the connection's receive queue, then waits, with no timeout, for
   every connection task to finish ("Waiting for background tasks to complete"). The handler never reads that
   queue, and the only thing that would wake it (`JobsHub.stop()`, from the app's lifespan) runs *after* that
   wait. So:
   - SIGTERM never stops it: uvicorn forces an exit only on a *second SIGINT*, and a second SIGTERM does
     nothing. A `systemctl stop` or `podman stop` ends in SIGKILL.
   - SIGINT needs a second press, and the forced exit skips the lifespan's orderly shutdown.

   With C5 a socket is open whenever a tab is, so this becomes the normal case.
3. **A vanished peer is noticed only by accident.** uvicorn's keepalive (a ping every 20 s, answered within
   20 s) closes the transport of a peer that stopped answering, but the handler never sees it. It stays
   subscribed exactly like case 1.

All three have the same cause: the handler does not watch the client side of its connection. This change
fixes that in `api/`, before C5 makes open sockets routine (Principle VIII).

## What Changes

- **The handler watches the client side for the life of the connection.** It reads the connection until the
  disconnect arrives and ignores anything a client sends. It pushes frames from a child task. The end of the
  connection releases the subscription at once, whatever ends it:
  - a client close
  - a lost connection, including uvicorn's keepalive timeout
  - the server's own shutdown close

  The last subscriber's release stops the poller, as the hub already does on unsubscribe. The push task
  also releases the subscription when it ends on its own, because the hub let it go or a send failed.
  This covers the one ending uvicorn reports late: a peer that vanished while frames were backed up for
  it (design, Risks).
- **One SIGINT or SIGTERM stops `auto-reel serve` with sockets open.** Each client receives close code 1012
  from uvicorn. The handlers end at once, and the lifespan's `hub.stop()` and `engine.dispose()` run. In the
  reproduction the process exited 0.16–0.31 s after one signal, against never (SIGTERM) or only after a
  second SIGINT today.
- **A subscriber the hub lets go is told so.** When the hub drops a slow consumer (or stops), the handler
  closes the socket with **1013** (try again later) instead of dropping the transport without a close frame,
  which clients saw as 1006. An unexpected error in the push task closes with **1011** and is still raised,
  so uvicorn logs it. The client's recovery is unchanged: reconnect and read a fresh snapshot.
- **The keepalive is a contract.** The spec states the 20 s ping / 20 s answer window, and a test pins
  uvicorn's defaults in `serve`'s server config, so an upstream change of the defaults fails loudly. No
  setting and no flag is added.
- **"WebSocket live job updates" states the connection lifecycle:**
  - a closed or lost connection is released within one second
  - a silent peer is released within the keepalive window
  - client messages are ignored
  - one signal closes every socket with 1012 and ends the process within a few seconds
  - a dropped subscriber gets 1013
  - the one exception to the keepalive and one-signal bounds: a peer that vanished behind backed-up frames

## Non-goals

- **No `timeout_graceful_shutdown` on `serve`.** With the handler fixed, shutdown with sockets open took
  0.16–0.31 s. A graceful timeout would also cut in-flight REST requests, which is a separate decision for
  every endpoint, not a WebSocket fix. Consequences, each ended by a second SIGINT as before:
  - A handler still inside its first subscribe (the first subscriber's two store reads) while the database
    hangs delays shutdown until those reads return.
  - A connection to a peer that vanished while frames were backed up for it cannot be closed by uvicorn
    until the host's TCP stack abandons it. uvicorn 0.54 waits for it at shutdown, and 0.51's shutdown
    fails with an error before the orderly lifespan shutdown. This is uvicorn behavior, the same with
    today's handler (design, Risks), and the spec names it as the exception.
- **No change to how `serve` reports a signal.** After a graceful shutdown uvicorn re-raises the captured
  signal, so a SIGINT still ends with a `KeyboardInterrupt` traceback and the process ends by the signal (rc
  −2 or −15). This happens with no socket open too; it is pre-existing and unchanged. It is a candidate
  follow-up for `cli/`.
- **No new configuration key or `serve` flag** for the keepalive (Principle VII). No server-initiated ping of
  our own, no application-level heartbeat frame, and no new frame type.
- **No hub change.** `JobsHub` (`subscribe`, `unsubscribe`, `stop`, the poller and the finished-jobs
  watermark from C2/C3) is used as it is. The snapshot a *second* subscriber gets while the poller runs is
  still the poller's latest (D-A4). Only a subscriber that restarts the poller gets a fresh read, which is
  now every subscriber after the last one left.
- **No web client change.** C5's socket hook already reconnects after any close, 1012 and 1013 included.
  C5's risk "[A half-open connection still reads Live]" is on the client side and stays open. uvicorn's
  ping lets the server notice a dead client, not the browser a dead server. The heartbeat frame C5 names
  for it remains a follow-up.
- **No change to `GET /jobs`, cancel, or project scoping** (C2, C3).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - `Requirement: WebSocket live job updates`: the connection lifecycle, which covers:
    - prompt release on a client close or a lost connection, which stops an idle poller
    - release of a silent peer within the keepalive window
    - client messages ignored
    - one-signal shutdown with close code 1012
    - close code 1013 for a subscriber the hub drops

## Impact

- **Dependencies (gates):** gate: jobs-project-guards archived on main. It was archived at `ed71d57`, and
  this change is written against `main` at `47e46f4`. Its `api/ws.py` has C2's `_start_polling`,
  `list_finished_since`, `TERMINAL_STATUSES` and C3's project scoping. C3 does not modify "WebSocket live
  job updates", so this change's MODIFIED block is based on the text C2 archived. `render-progress-screen`
  (C5) does not wait for it, but C5's live feed relies on its lifecycle, so it should archive first.
- **Packages:**
  - `api/`: `ws.py` only. The `ws_jobs` handler becomes a receive loop plus a push task, with its docstring
    rewritten. There is no `JobsHub` change.
  - `cli/`: no code change. `tests/test_cli_serve.py` gains the signal end-to-end test and the keepalive pin.
  - Tests: new `tests/test_api_ws_lifecycle.py` (in-process uvicorn server over a fake store, no database).
  - Docs: `README.md`'s WebSocket bullet and one clause in HLD §4.10's live-progress bullet.
- **CLI vs API (Principle V):** the WebSocket is the API's fan-out, which the thin-API rule allows. No engine
  behavior moves; the CLI's `serve` gains its one-signal stop without a code change.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. The OpenAPI schema
  and `web/openapi.json` are unchanged (close codes are not part of the frame).
- **Wire:**
  - a hub-dropped subscriber now receives close code 1013 where it saw an abnormal close (1006)
  - a client's close ends its subscription at once
  - every frame's shape and timing is unchanged
- **Runtime dependencies:** none added. `uvicorn>=0.51.0` and `websockets>=13.0` stay as declared. A fresh
  `pip install -e ".[dev]"` resolves uvicorn 0.54.0, websockets 17.1, starlette 1.7.0 and FastAPI 0.142.2.
  The shutdown, keepalive and app-close behavior the handler relies on is the same there. The planned
  lifecycle tests passed on uvicorn 0.54.0 with starlette 1.7.0. 0.54 adds write back-pressure and a
  closing handshake (design).
- **Size (Principle VIII):** one capability delta, one package's code (`api/ws.py`), 8 tasks (one of them the
  gate, two of them validation).
