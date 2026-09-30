## 1. Gate

- [x] 1.1 Gate: `jobs-project-guards` (C3) must be archived on `main`: `ls openspec/changes/archive/ | grep -E -- '-jobs-project-guards$'` prints one directory. It did at `ed71d57`, and `47e46f4` is the baseline this change was written against. If it prints nothing, stop and report to the supervisor. Then confirm the baseline:
  - `git diff 47e46f4 -- auto_reel_ng/api/ws.py auto_reel_ng/api/app.py auto_reel_ng/cli/commands.py tests/conftest.py tests/test_api_ws_hub.py tests/test_cli_serve.py openspec/specs/api-service/spec.md` prints nothing. If a file differs, re-read it against the design's "Context" first. If the spec differs in "WebSocket live job updates", re-base this change's MODIFIED block on the current text of that requirement and re-run `openspec validate jobs-ws-lifecycle --strict`.
  - `grep -n "A single send loop only" auto_reel_ng/api/ws.py` hits: `ws_jobs` is still the send loop the design's Context describes
  - `.venv/bin/python -c "import uvicorn, websockets; print(uvicorn.__version__, websockets.__version__)"`. If uvicorn is neither 0.51.x nor 0.54.x, re-read the following against the design's "What uvicorn does" before implementing:
    - `uvicorn/server.py`: `shutdown`
    - `protocols/websockets/websockets_sansio_impl.py`: `shutdown`, `connection_lost`, `keepalive_timeout`, and the app-close branch of `send`

  Verify: every check above holds, or the difference is recorded in the final report.

## 2. api/ — the handler watches the client side

- [x] 2.1 Write `tests/test_api_ws_lifecycle.py` first. Then replace `ws_jobs` in `api/ws.py` with the receive loop and the `_push_frames(websocket, hub, queue)` task (design "The handler: a receive loop, with a push task it owns"), and rewrite its docstring.
  - The push task releases the subscription in its own `finally`.
  - The handler's cleanup follows the order in "Teardown order".
  - The close codes are imported by name (design, the bullets under the snippet).

  The test module (no database, no marker):
  - has the async context manager that runs the app in-process under `uvicorn.Server` with `log_config=None` (design "Tests"), and imports `FakeStore`/`FakeJob` from `test_api_ws_hub`
  - uses a poll interval of 0.05 s

  Before changing the handler, run the module against the current one and record the result:
  - **close releases**, **the other tab stays live** (its first assertion) and **fresh snapshot** fail, with the hub still at one subscriber and polling
  - **messages ignored** fails at the fixture's teardown. The server's shutdown hangs on the stuck handler (proposal item 2) until the fixture's wait times out.
  - the **`TestClient`** cycles pass. They guard that at least one release happens before the harness's cancel lands, the handler's early unsubscribe or the push task's own, not the order itself. Measured in the implementation: with the cleanup reversed (wait, then unsubscribe) and the push task's release kept, they passed 5 of 5 runs on uvicorn 0.54 and on 0.51; with both removed, they failed within 200 cycles in 2 of 3 runs. The handler keeps the design's order because it does not depend on when the push task runs.

  Verify after the change:
  - **close releases:** two `websockets` clients connect and read their snapshots. Closing the first leaves `subscriber_count == 1` within 1 s, with `is_polling` true. Closing the second gives `subscriber_count == 0` and `is_polling` false within 1 s, and the `FakeStore`'s read counters do not change over the next five poll intervals.
  - **the other tab stays live:** in the same setup, after the first client closes, a `FakeJob` running for `2024/2024-06-27 - Grillning med grannar` advances its progress, and the remaining client receives that delta
  - **fresh snapshot:** after the last client closed and `is_polling` is false, a job is added to the `FakeStore`. A new client's snapshot contains it, and the `FakeStore`'s finished-read counter shows the new poller's seed read at that connect.
  - **messages ignored:** a client sends `"hello"`; after three poll intervals it is still subscribed, and a later progress change still reaches it
  - **teardown under `TestClient`:** 200 cycles of `TestClient` connect → read the snapshot → exit, over an app built the same way. After each cycle `subscriber_count == 0` and `is_polling` is false.
  - `tests/test_api_ws_hub.py` and `tests/test_api_ws_e2e.py` pass unchanged
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
- [x] 2.2 Cover the closes the handler sends (design "Close codes"), in `tests/test_api_ws_lifecycle.py`. Verify:
  - **hub lets go:** a connected client reads its snapshot, then the test awaits `hub.stop()`. The client's next receive raises `ConnectionClosed` with `rcvd.code == 1013`, and `subscriber_count == 0`.
  - **slow consumer:** use a hub built with `queue_maxsize=1` and a `FakeJob` running. The hub test's recipe (never drain) does not work over a real server, because the push task drains the queue (design "Tests"). Instead:
    - `WebSocket.send_text` is monkeypatched so that its second call waits on an `asyncio.Event` before sending
    - the job's progress advances once every 1.5 poll intervals until `subscriber_count == 0` (the drop through `_broadcast`), within 1 s
    - the test then sets the event, and the client's connection ends with `rcvd.code == 1013` (the parked delta may arrive first)
    - with the real `send_text` restored, a reconnect's first frame is a `snapshot`
  - **push error:** `WebSocket.send_text` is monkeypatched to raise `ValueError` on its second call (the first delta). Then:
    - the client is closed with 1011
    - `subscriber_count` returns to 0
    - uvicorn's error log (`caplog`, logger `uvicorn.error`) records "Exception in ASGI application" with the `ValueError` as its `exc_info`
  - **the push side releases on its own:** `WebSocket.send_text` raises `RuntimeError` on its second call, and `WebSocket.close` raises `RuntimeError`. This is what uvicorn does once its keepalive has sent a close (design "The push side releases too"). With the client still connected:
    - `subscriber_count == 0` and `is_polling` is false within 1 s
    - after the client closes, uvicorn logs "Exception in ASGI application"
    - against the design's snippet without the push task's `finally` release, this case times out (checked in the review)
  - mypy is clean
- [x] 2.3 Cover the endings uvicorn reports (design "What uvicorn does…"), in `tests/test_api_ws_lifecycle.py`. Verify:
  - **silent peer:** with `ws_ping_interval=0.2, ws_ping_timeout=0.2`, a raw `asyncio.open_connection` that sends the upgrade request, reads up to the end of the 101 headers and then reads nothing more, is subscribed and then released within 2 s, and the poller stops
  - **shutdown:** with one client connected and its snapshot read, setting `server.should_exit = True` closes the client with `rcvd.code == 1012`. The server task completes within 3 s, and afterwards `subscriber_count == 0` and `is_polling` is false.
  - the design's reproduction ("What uvicorn does…", table) showed both cases failing under the pre-change handler (the peer stays subscribed; the shutdown never completes), so these tests guard against a regression to it

## 3. cli/ — tests only: one signal stops `serve`

- [x] 3.1 In `tests/test_cli_serve.py` (`requires_db`), add the end-to-end signal test and the keepalive pin (design "Tests", "Keepalive"). No `cli/` code changes. Verify:
  - **one signal (parametrized: SIGTERM, SIGINT):**
    - the test requests `jobs_schema_engine` as well as `postgres_container`, so the `jobs` table the snapshot reads exists
    - `python -m auto_reel_ng.cli.main serve <tmp_path> --host 127.0.0.1 --port <free>` is started with `DATABASE_URL` set to the container, and `stdout`/`stderr` are captured
    - after `GET /healthz` answers 200, a `websockets.sync.client` connects and reads its snapshot (`type` is `snapshot`), and one signal is sent
    - the process ends within 5 s without a second signal
    - the client's connection was closed with 1012
    - the output contains "Application shutdown complete" and does not contain "Waiting for background tasks to complete"
    - the return code is not asserted (design, Risks: uvicorn re-raises the signal)
    - the test kills the process in its `finally` if it is still running, so a regression fails by timeout instead of hanging the suite
  - **keepalive pin:** with the existing `_FakeServer` capture, `serve`'s config has `ws_ping_interval == 20.0` and `ws_ping_timeout == 20.0`
  - the existing `serve` tests pass unchanged

## 4. Docs

- [x] 4.1 Update `README.md` and HLD §4.10. Do not add a new D-n entry. Verify by rereading both against the spec delta:
  - `README.md`'s WebSocket bullet:
    - a closed or lost connection is released at once, and a silent peer within about 40 s (20 s ping, 20 s answer)
    - client messages are ignored
    - a dropped subscriber gets close code 1013, and a server stop gives every client 1012; either way, reconnect for a fresh snapshot
  - `README.md`'s `serve` section: one SIGINT or SIGTERM stops it with sockets open
  - HLD §4.10, the "Live progress needs no library" bullet, gets one clause: the service closes with 1012 on stop and 1013 when it drops a subscriber, and the client reconnects after any close. `render-progress-screen` (C5) adds a sentence to the same bullet: if it has landed, keep it and add the clause next to it.

## 5. Validation

- [x] 5.1 Smoke against the agent's own dev library (dev-env runbook §9, `SLUG=jobs-ws-lifecycle`, `N=7`, port 8107), with no worker running. The WebSocket client is a Python script from the venv (`websockets.sync.client`), run from the session scratchpad and never committed.
  - **idle after close:**
    - with a client connected, `SELECT max(query_start) FROM pg_stat_activity WHERE datname = '<DB>' AND pid <> pg_backend_pid()` advances between two reads 3 s apart (the poller runs)
    - after the client reads its snapshot (it holds `2024/Blandat`'s queued job) and closes, the same query returns the same value twice, 3 s apart
    - a new client's snapshot still holds `2024/Blandat`'s job
  - **one signal:**
    - with a client connected, `kill -TERM <serve pid>`: the process exits within 5 s, the client reports close code 1012, and the log shows "Application shutdown complete" and no "Waiting for background tasks to complete"
    - restart `serve` and repeat with `kill -INT`

  Never touch `../auto-reel-dev`, `auto-reel-media/` or port 8080.
- [x] 5.2 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full `.venv/bin/python -m pytest`, including `requires_db`. Then run `openspec validate jobs-ws-lifecycle --strict`. Verify all are clean or green, apart from the known cairo `no-member` noise.
