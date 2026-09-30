## 1. Gate

- [ ] 1.1 Gate: none. This change runs in parallel with `web-design-system`, and `jobs-project-guards` (C3) and `render-progress-screen` (C5) wait for it. Confirm the baseline this change was written against (`541c44c`) instead. Verify: `git diff 541c44c -- auto_reel_ng/api/routes/jobs.py auto_reel_ng/api/schemas.py auto_reel_ng/api/ws.py auto_reel_ng/api/app.py auto_reel_ng/persistence/job_store.py openspec/specs/api-service/spec.md openspec/specs/job-store/spec.md` prints nothing.
  - If a file differs, re-read it against the design's "Context" first.
  - If a spec differs, re-base this change's MODIFIED blocks on the current text of those requirements before implementing.
  - Also confirm that no client code reads a problem's `id`: `grep -rnE --include=*.ts --include=*.tsx --exclude=schema.d.ts "problem\??\.(id|job_id)\b" web/src` prints nothing.

## 2. persistence/ — the store reports what it did

- [ ] 2.1 Add `Submission` and `JobStore.submit(...)` (today's `enqueue` body, returning `Submission(job_id, created)`), and reduce `enqueue` to `return self.submit(...).job_id` (design "Result-bearing store verbs, old verbs kept as wrappers"). Add `FinishedJobs` and `JobStore.list_finished_since(since, *, overlap)`: one session, `as_of` from `select(func.now())`, then the jobs with `finished_at >= (since or as_of) - overlap` by `finished_at` ascending (design "Jobs whose whole active life falls between two polls"). Verify with `requires_db` tests in `tests/test_job_store.py`:
  - `submit` for `2024/2024-06-27 - Grillning med grannar` with no active job returns `created=True` and the id of the one new row
  - a second `submit` while that job is `queued` returns `created=False` with the same id, and the table still has one row
  - two `submit`s run concurrently from a `ThreadPoolExecutor` (the pattern of `test_claim_next_never_double_claims`) yield exactly one `created=True` and one `created=False`, both naming the same id
  - every existing `enqueue` test passes unchanged
  - `list_finished_since(None, overlap=timedelta(0))` returns an aware `as_of` and no jobs. After a job for `2024/2024-10-05 - Trasig` is claimed and transitioned to `failed`, `list_finished_since(as_of, overlap=timedelta(0))` returns exactly that job with status `failed`, and no `queued` or `running` job created alongside it
  - a job whose `finished_at` is set (by a direct session update) to `as_of - 5 s` is absent with `overlap=timedelta(0)` and present with `overlap=timedelta(seconds=30)`
- [ ] 2.2 Add `CancelOutcome` (`StrEnum`: `flagged-running`, `canceled-queued`, `no-op-terminal`, in that order), `Cancellation` and `JobStore.cancel(job_id)`, which reads with `session.get(Job, job_id, with_for_update=True)`, then reduce `request_cancel` to the wrapper (design "One locked transaction for the cancel"). Write the lock test first, against `request_cancel`, and run it before changing the store. It fails, with the committed row `canceled` and the claim's `worker_id` set: this is the lost update the design's Context describes. Verify with `requires_db` tests in `tests/test_job_store.py`:
  - a running job gives `FLAGGED_RUNNING`, status `running` and `cancel_requested` true
  - a queued job gives `CANCELED_QUEUED` and status `canceled`, and a later `claim_next` returns nothing
  - a `failed` job gives `NO_OP_TERMINAL`, with the row unchanged
  - an unknown id gives `None`
  - the lock case: a separate session locks the queued row `FOR UPDATE`, sets it `running` with a `worker_id`, and holds the transaction. `cancel` is started on a thread, and the thread is confirmed still blocked after ~0.5 s. The session commits. The thread's result is `FLAGGED_RUNNING`, and the committed row is `running`, with the claim's `worker_id` and `cancel_requested` true.
  - the same lock case through `request_cancel` now returns the flagged `running` job
  - the existing `request_cancel` tests, `tests/test_cli_jobs.py` and `tests/test_scheduler_worker.py` pass unchanged

## 3. api/ — the jobs contract

- [ ] 3.1 Add the typed problem field and the `event_dir` description (design "`job_id` as the typed problem field", "Publishing the responses"):
  - `api/schemas.py`:
    - add `ProblemOut.job_id: Optional[uuid.UUID] = None` with its `#:` comment
    - update the `ProblemOut` docstring, which cites the 409's `id`
    - add the `Field(description=…)` to `JobOut.event_dir`
  - `api/problem.py`: update the `problem_response` docstring, which cites `.id`
  - `api/routes/jobs.py`: the active-job 409 and both unknown-id 404s pass `job_id=` instead of `id=`

  Verify with `tests/test_api_jobs.py`:
  - the duplicate test asserts `second.json()["job_id"] == first.json()["id"]` and that `"id"` is absent from the problem
  - the two unknown-id 404s carry `job_id` equal to the requested id
  - the enqueue 404 for an unknown event carries `event_id`
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
- [ ] 3.2 Rework `api/routes/jobs.py` as the design's "The route: the store's facts, mapped" shows, together with the schema types it needs:
  - make `FreshResult.status` `Literal["fresh"]` with no default, and pass `status="fresh"` in `create_job`
  - type `CancelResult.outcome` as `CancelOutcome`
  - `create_job` calls `submit` and answers 409 with `job_id` when it did not create
  - `cancel_job` makes the single `store.cancel` call and derives nothing itself
  - the module docstring names `submit` and `cancel`

  Verify with `tests/test_api_jobs.py`:
  - a race test monkeypatches the app's `store.active_job` to return `None` while a job is queued. POST answers 409 with that job's `job_id`, and the table holds one row.
  - a stale-read test: create a job and keep `store.get(id)` (a `queued` copy), then claim it, then monkeypatch the app's `store.get` to return that copy. The cancel answers `flagged-running` with status `running`. Before this task it answers `canceled-queued` with `running`, which is the mislabel.
  - the fresh test asserts `body["status"] == "fresh"`
  - the three existing outcome tests pass
  - `.venv/bin/python -m mypy auto_reel_ng` is clean
- [ ] 3.3 In `api/schemas.py` and `api/ws.py`, give the frame its closed type, push cancel requests, and send terminal jobs no frame carried (design "Publishing the WebSocket frame without inventing a route", "`cancel_requested` as a delta trigger", "Jobs whose whole active life falls between two polls"):
  - add `WsMessageType`, type `WsMessage.type` with it, and make `WsMessage.jobs` required (no default)
  - type `_encode`'s argument as `WsMessageType`, and pass its members at both call sites
  - make `_tick` emit a row whose `cancel_requested` changed
  - add `_FINISHED_OVERLAP`, the watermark and `_terminal_sent`: seeded at poller start by a finished read made before the active snapshot, then each tick a finished read before the active read, terminal rows from both paths merged by id and de-duplicated against `_terminal_sent`, the watermark advanced to `as_of`, and old entries pruned

  Verify in `tests/test_api_ws_hub.py`. First give `FakeStore` a settable `now` and `list_finished_since(since, *, overlap)` (filtering its jobs on `finished_at`, counted like the other calls):
  - `WsMessage(type="snapshot", jobs=[])` validates, while `type="other"` or a missing `jobs` raises `ValidationError`
  - with the fake store, flipping only `cancel_requested` on a running job produces one `delta` frame whose row has `cancel_requested: true` and an unchanged `progress`
  - the gap: after the snapshot, a `failed` job with an `error` and `finished_at = store.now` is inserted between two ticks, never having been `queued` or `running` in the store. Exactly one `delta` carries it, with status `failed` and its error, and no further frame arrives over the next five ticks, although each tick's window still includes it
  - a job already `done` with `finished_at` inside the overlap before the first subscribe is never sent
  - in the existing terminal-transition test, the replacing `done` job also gets `finished_at = store.now`, and the test asserts that no second delta for it arrives over five ticks (both paths see it)
  - `test_no_subscribers_means_no_store_queries` also asserts zero finished reads
  - the existing hub tests and `tests/test_api_ws_e2e.py` pass, and mypy is clean
- [ ] 3.4 Declare `responses=` on the three routes (design "Publishing the responses"), add `publish_ws_schema` to `api/ws.py`, and wrap `app.openapi` in `create_app` (design "Publishing the WebSocket frame without inventing a route"). Regenerate `web/openapi.json` and `web/src/api/schema.d.ts` with the `web/README.md` commands, running `npm ci` in the node:22 container first if `web/node_modules` is absent. Verify with new cases in `tests/test_api_openapi.py`:
  - responses:
    - `POST /api/v1/jobs` declares exactly `200` (`FreshResult`), `404` and `409` (`ProblemOut`) besides `201` and `422`
    - `GET /api/v1/jobs/{job_id}` and `POST /api/v1/jobs/{job_id}/cancel` declare exactly `404` (`ProblemOut`) besides `200` and `422`
  - models:
    - `FreshResult.status` has `const: "fresh"` and is in `required`
    - `CancelResult.outcome` references `CancelOutcome`, whose `enum` equals `[o.value for o in CancelOutcome]`
    - `WsMessage.type` references `WsMessageType` (`["snapshot", "delta"]`), `WsMessage.jobs.items` references `JobOut`, and `required` holds both `type` and `jobs`
    - no path names `/api/v1/ws/jobs`
    - `ProblemOut.properties` has `job_id`
    - `JobOut.properties.event_dir.description` names the event id
    - `EXPECTED_MODELS` gains `FreshResult`, `CancelOutcome`, `WsMessage` and `WsMessageType`
    - a second `app.openapi()` call on the same app returns an equal schema with the same component names, because the merge is idempotent
  - the drift test passes after regeneration
  - with the regenerated files, `npx tsc --noEmit` passes in the node:22 container with no client change, and `grep` finds `WsMessage`, `WsMessageType`, `CancelOutcome`, `"flagged-running"` and `status: "fresh"` in `web/src/api/schema.d.ts`

## 4. Docs

- [ ] 4.1 Update `README.md`'s API service section and add one sentence to HLD §4.10. Do not add a new D-n entry. Verify by rereading both against the specs.
  - the jobs bullet:
    - the 409 and the jobs 404s carry `job_id`, and the `id` extra is gone
    - a race answers 409
    - the cancel outcome values, decided by the store under a row lock
    - `event_dir` is the event id
  - the WebSocket bullet: frames are `{type: "snapshot" | "delta", jobs: [...]}`, a cancel request is pushed, and a connected client receives every terminal transition exactly once, even for a job that lived and ended between two polls (a job that ended while it was disconnected is not replayed)
  - the HLD §4.10 closed-vocabulary paragraph: a model sent only over the WebSocket is published into the schema's components by the application's schema hook, never through a fake HTTP route

## 5. Validation

- [ ] 5.1 Smoke the contract against the agent's own dev library (dev-env runbook §9, `SLUG=jobs-client-contract`, `N=2`, port 8102). Run no worker, and use `curl`:
  - `POST /api/v1/jobs {"event_id": "2024/Blandat"}` answers 409 with `job_id`
  - `{"event_id": "2023/2023-06-23 - Midsommar - Dalarna"}` answers 200 with `"status": "fresh"`
  - the gap, live: a WebSocket client from the venv (below) is connected and has read its snapshot. One Python script then POSTs `{"event_id": "2024/2024-06-27 - Grillning med grannar"}` and cancels the returned job immediately (`urllib`, no pause). The POST answers 201 with `event_dir` equal to that id, and the cancel answers `canceled-queued`. Over the next 5 s the client receives exactly one row for that job with status `canceled`; a `queued` row for it may precede it
  - cancelling that job again answers `no-op-terminal`
  - `GET /api/v1/jobs/00000000-0000-0000-0000-000000000000` answers 404 with that `job_id`
  - `GET /openapi.json` from the running service equals `web/openapi.json` when both are parsed as JSON. The served body is compact, so do not compare the bytes.
  - the WebSocket client (`websockets.sync.client.connect("ws://127.0.0.1:8102/api/v1/ws/jobs")`) received a first frame with `type` `snapshot` and a `jobs` array holding `2024/Blandat`'s queued job

  Never touch `../auto-reel-dev`, `auto-reel-media/` or port 8080.
- [ ] 5.2 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full `.venv/bin/python -m pytest`, including `requires_db`. Then run `npx tsc --noEmit` and `npm run build` in the node:22 container. Verify all are clean or green, apart from the known cairo `no-member` noise.
