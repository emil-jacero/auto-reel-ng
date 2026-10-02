## 1. Base

- [x] 1.1 Confirm the base and re-read the code this change edits.
  - `jobshub-stop-and-db-timeouts` is on `main` (`JobsHub.stop()` takes a stopping flag and shuts the
    executor down without waiting).
  - `_push_frames` still reads `queue.get()` and `_CLOSE`, and `store.ts` `connect()` still has the
    `close` handler this change turns into `lost()`; the shapes in design, "Context" hold.
  - Re-base each MODIFIED block in `specs/` on the current text of its requirement in
    `openspec/specs/`, keeping any edit another change made, then
    `openspec validate api-ws-heartbeat --strict` passes.

## 2. api/

- [x] 2.1 In `api/schemas.py`, add `WsMessageType.HEARTBEAT = "heartbeat"` with a comment (an empty-jobs
  frame sent after 15 s of silence on a connection) and update `WsMessage`'s docstring. Regenerate
  `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and
  `web/src/api/schema.d.ts` (`generate:types` in the `node:22` container).
  Tests: `tests/test_api_openapi.py` expects the enum `["snapshot", "delta", "heartbeat"]` (and the
  committed-schema comparison passes); `tests/test_api_ws_hub.py::test_the_frame_is_a_closed_shape` also
  accepts `WsMessage(type="heartbeat", jobs=[])` and still rejects an unknown type.
- [x] 2.2 In `api/ws.py`, add `_HEARTBEAT_INTERVAL_S = 15.0`, the pre-encoded `_HEARTBEAT` string and
  `_next_message()` per design, and use it in `_push_frames`; update the `ws_jobs` and module docstrings
  (the channel is push-only, a heartbeat is per connection and never touches the hub).
  Tests, in `tests/test_api_ws_lifecycle.py` with the interval patched to about 0.1 s through
  `monkeypatch.setattr` on the module (extend `_serving` with an optional poll interval for the third):
  - an idle client gets its snapshot first, then at least two frames equal to
    `{"type": "heartbeat", "jobs": []}`, and the connection stays open
  - with a long poll interval, several heartbeats add no store read beyond the connect-time ones, and the
    subscriber's queue stays empty
  - a client whose job advances more often than the interval receives the deltas and no heartbeat
  - a delta landing as a heartbeat falls due is delivered exactly once, in order, across a run of many
    intervals (progress values received are strictly increasing, none repeated or missing)
  - a hub `stop()` and a slow-consumer drop during a heartbeat wait still close with 1012 and 1013 within
    the existing time bounds (one of the existing tests re-run with the interval patched small)
  - one `requires_db` test in `tests/test_api_ws_e2e.py`: through `create_app` and a real store, an idle
    connection receives snapshot, then a heartbeat.

## 3. web/

- [x] 3.1 In `src/jobs/store.ts`, add `heartbeat: true` to `FRAME_TYPES` and `case 'heartbeat': break` to
  `onFrame` (after `attempt = 0` and the re-arm; no `commit`, no `notify`). Add `SILENCE_MS = 40_000`,
  `armWatchdog()` and `lost()` per design: arm in `connect()` and after each valid frame, clear in `lost()`
  and `stop()`, move the `close` handler body into `lost()`. Update the file's header comment (the
  reconnect bullet gains the silence rule).
  Verify: `tsc --noEmit` and `npm run build` pass in `node:22` after `npm ci`, and
  `grep -n "setTimeout" web/src/jobs/store.ts` lists only the retry, release and watchdog timers.
  A `node:test` file, `src/jobs/store.test.ts` (stub `WebSocket`, `mock.timers`), covers: 40 s of silence
  reconnects once and closes the socket, a heartbeat re-arms the window and commits no state, and a close
  after the store dropped the socket schedules no second reconnect.
- [x] 3.2 Verify in a real browser with an ad hoc Playwright script kept outside the repo
  (`<scratch>/check_heartbeat.py`, the `playwright/python` image, `page.clock` for time, the jobs socket
  mocked with `route_web_socket`, scoped to `**/api/v1/ws/jobs`), against a served build:
  - a mocked server that sends a snapshot and then only heartbeats every 15 s: after `clock` advances 5
    minutes the header still reads live and exactly one socket was opened
  - a mocked server that sends a snapshot and then goes silent without closing: just before 40 s the header
    reads live, just after it reads reconnecting without counts, a second socket is opened after the
    backoff, and after its snapshot the header reads live again with no reload
  - frames arriving every 30 s for 5 minutes (deltas for Grillning's running job) keep the socket
  - a mocked server that closes the socket with 1012 still reconnects as before (no double reconnect from
    the watchdog)
  - with no mock, against `auto-reel serve` on the change's dev port, a real frame log
    (`page.on("websocket")`) shows a `heartbeat` frame about 15 s after the snapshot on an idle service and
    the header stays live
  - screenshots of the header live and reconnecting, light and dark, at 1280 and 390: look at them.

## 4. Docs

- [x] 4.1 Update the three places that describe the frame: `README.md` (the `WS /api/v1/ws/jobs` bullet:
  the type set, and one sentence on the 15 s heartbeat and the client's 40 s silence rule),
  `web/README.md` (the `store.ts` line and the live-job paragraph), and `docs/high-level-design.md` §4.10
  "Live progress needs no library" (the heartbeat and watchdog as part of the reconnect contract).
  Verify: `grep -rn '"snapshot" | "delta"' README.md web docs` finds no stale two-value set.

## 5. Gates

- [x] 5.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` (only the known cairo
  `no-member` noise) and the full `.venv/bin/python -m pytest` (podman for the `requires_db` tests) pass.
- [x] 5.2 `openspec validate api-ws-heartbeat --strict` passes, and `npm ci`, `npx tsc --noEmit` and
  `npm run build` pass in `node:22`.
