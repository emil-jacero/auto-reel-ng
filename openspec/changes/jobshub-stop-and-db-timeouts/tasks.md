## 1. api/ — `JobsHub.stop()` never waits on the database

- [ ] 1.1 Red first, in `tests/test_api_ws_lifecycle.py`: add a `_BlockingStore(FakeStore)` whose
  `list_by_status` (and so the seed and the poll) can be switched to block on a `threading.Event` after
  setting an `entered` event; every test releases it in a `finally` so no thread outlives the test. Hub-level
  cases, each with a loop-liveness probe (a task sleeping 50 ms and recording the largest gap):
  - poll stalled: subscribe, switch blocking on, wait for `entered`, `await asyncio.wait_for(hub.stop(), 1)`;
    the probe's largest gap stays under 0.5 s (today `shutdown(wait=True)` freezes the loop for the full
    block)
  - first subscribe stalled: block from the start, run `hub.subscribe()` as a task, wait for `entered`,
    `await asyncio.wait_for(hub.stop(), 1)`; the subscribe task resolves to a queue whose only item is the
    close sentinel, and the hub has no subscriber and is not polling (today `stop()` never returns)
  - a subscribe after `stop()` resolves to a close-only queue and issues no store call; `stop()` twice is
    harmless
  - a subscriber cancelled mid-seed (no stop) leaves the hub as it was: after the release, a new subscribe
    gets a snapshot and starts the poller

  Verify the first two fail on unchanged code (the first on elapsed/gap, the second on the timeout) and that
  every existing test in the file still passes.
- [ ] 1.2 Implement the design's "Stop signals first, then takes the lock" and "The executor is released, not
  joined" in `auto_reel_ng/api/ws.py`: `_stopping`, `_start_task`, the cancellable seed task in
  `_start_polling`, the close-only queue from `subscribe()` once stopping, and `stop()` ending in
  `shutdown(wait=False, cancel_futures=True)`. Rewrite `stop()`'s docstring (the `wait=True` rationale is
  replaced by the abandon-and-detach one) and the module docstring's executor paragraph. Verify: 1.1's tests
  pass, plus `.venv/bin/python -m pytest tests/test_api_ws_hub.py tests/test_api_ws_lifecycle.py`.

## 2. api/ — the handler watches the connection during the first subscribe

- [ ] 2.1 Red first, in `tests/test_api_ws_lifecycle.py` through the real `uvicorn.Server` harness
  (`_serving`) with `_BlockingStore` (the client connects and waits; the handler has accepted but sent no
  frame):
  - client closes during the stalled seed: within 1 s the hub lock is free and no subscriber is registered
    (today the handler is parked until the store answers); after releasing the store, a new client gets a
    normal snapshot
  - server shutdown during the stalled seed: with one client connected and `entered` set, set
    `served.server.should_exit = True`; the client sees close code 1012 and `served.task` completes within
    2 s with the lifespan's `hub.stop()` having run (today it completes only after the store is released)
  - a message the client sends during the stalled seed is dropped and the snapshot still arrives after the
    release

  Verify the first two fail on unchanged code.
- [ ] 2.2 Implement the design's "The handler watches the connection while its first subscribe is stalled" in
  `ws_jobs`: subscribe as a task raced against the connection's next message; a disconnect cancels and awaits
  the subscribe and ends the handler; an ordinary message is dropped and the wait continues; a finished
  subscribe continues as today, with the pending receive task as the loop's first read. Keep the cleanup
  order (release before the first suspension) and update the docstring's teardown paragraph. Verify: 2.1
  passes and the whole existing lifecycle module stays green, including
  `test_a_testclient_session_exit_leaves_the_hub_empty_and_idle` (200 cycles) and the 1012-shutdown, keepalive
  and slow-consumer tests, run three times in a row for flakiness.

## 3. persistence/ — connect timeout

- [ ] 3.1 Red first, in a new DB-free `tests/test_persistence_engine_timeout.py` (the existing
  `tests/test_persistence_engine.py` is `requires_db` module-wide, so it stays as it is; these tests carry no
  marker):
  - with `sqlalchemy.create_engine` replaced in the module by a recorder: a `postgresql+psycopg://` URL gets
    `connect_args == {"connect_timeout": 5}`; a URL ending `?connect_timeout=30` gets no `connect_timeout` in
    `connect_args` (the URL's value wins); a `sqlite://` URL gets no `connect_args`
  - a listening socket that never accepts (backlog 1): with `CONNECT_TIMEOUT_SECONDS` monkeypatched to 2 (libpq
    treats anything under 2 as 2), `make_engine("postgresql+psycopg://u:p@127.0.0.1:<port>/db").connect()`
    raises `sqlalchemy.exc.OperationalError` after between 1.5 s and 6 s, not the test's 30 s cap
  - `GET /healthz` of an app built over that URL (reuse the fixtures in `tests/test_api_app.py`) answers 503
    with `check: "database"` within the same bound

  Verify the recorder and socket cases fail on unchanged code.
- [ ] 3.2 Implement the design's "Connect timeout" in `auto_reel_ng/persistence/engine.py`:
  `CONNECT_TIMEOUT_SECONDS = 5`, `make_engine` as in the design (parse the URL, add `connect_timeout` only for
  the `postgresql` backend and when the URL does not set it), docstring updated. Verify: 3.1 passes, and
  `.venv/bin/python -m pytest tests/test_persistence_engine.py tests/test_job_store.py` (podman) stays green,
  proving a healthy database is unaffected.

## 4. Docs

- [ ] 4.1 In `README.md`'s `serve` stop paragraph ("One SIGINT (Ctrl+C) or SIGTERM …"), add a sentence after
  the "request still being handled" exception: a database that has stopped answering does not hold the stop
  of the live feed (the WebSocket hub is abandoned from its stalled read), and connecting gives up after 5 s
  (`?connect_timeout=N` in `DATABASE_URL` changes it), but a query already running on an established
  connection is not interrupted and the process exits only after it ends. Verify by rereading it against both
  spec deltas: no claim that the process exits within seconds regardless of the database, and the 5 s bound
  is for connecting only.

## 5. Validation

- [ ] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full
  `.venv/bin/python -m pytest` including `requires_db` (podman). Then `openspec validate
  jobshub-stop-and-db-timeouts --strict`. Verify all are clean or green, apart from the known cairo
  `no-member` noise and the five font-dependent skips.
