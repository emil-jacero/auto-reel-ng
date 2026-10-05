Conventions for every task below:

- Python runs from the worktree root with `.venv/bin/python -m pytest` (never `.venv/bin/pytest`), with `TMPDIR`
  exported to this change's own tmp directory (`/tmp` has a small quota). Node runs only in
  `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 ...`.
- A running service or browser check uses only this change's port, database, dev library and scratch directory;
  never the shared dev library, `auto-reel-media/`, or another change's resources; never remove a container this
  change did not create (`auto-reel-ng-test-pg-*` belong to pytest).
- Run the validation gates (task 5.2) after each task, not only at the end.

## 1. Gate

- [x] 1.1 Confirm the archived `analysis-job` change is on `main` (stop and report if not). Check every row of design
  "Gate" against its code and write the real names into the design: `JobKind.ANALYSIS`, the failure-marker reader
  and its message field, the handler's per-clip selection and where `analyze --enqueue` decides it, how `force` is
  stored and honoured, and whether `web/openapi.json` already lists `analysis`. Re-read the archived text of the two
  MODIFIED `api-service` requirements and replace the copied text in `specs/api-service/spec.md` if the gate changed
  it (behaviour of this change kept). Verify: each row holds or the design is corrected, and
  `openspec validate analysis-enqueue-api --strict` passes.

## 2. analysis/ - the state rule

- [x] 2.1 Add `analysis/state.py` (design D1): `ClipAnalysisState`, `ClipAnalysis`, `clip_analysis_states(event_dir)`
  over `scan_event(event_dir).identities`, `event_disk_state(clips)` and `needs_analysis(clips)`, reading each entry
  through a new `analysis/cache.py inspect_entry` that tells a missing file from an unreadable one (typed
  `AnalysisStateError` in `errors.py`). No `cli/` edit (design D6). Verify in `tests/test_analysis_state.py` (no
  database): valid entry → `current`; marker for the current signal → `failed` with its message; entry or marker for
  an older signal → `stale`; truncated JSON and an entry of another version → `stale`; nothing → `never`; an entry
  file with mode 000 and a clip that cannot be statted raise; ignored and chapter-folder clips are included; the
  event precedence table (no clips, all current, all never, mixed never/current, current+failed); a
  `subprocess.Popen`/`run` monkeypatch that fails the test is never reached and the folder's mtimes and listing are
  unchanged; `needs_analysis` over `never`, `stale`, `current` and current+`failed` events is true for exactly the
  first two; `inspect_entry` in `tests/test_analysis_cache.py` (absent, result, failure, other signal, bad version,
  truncated, unreadable).

## 3. api/ - the read, the two enqueues, the kind

- [x] 3.1 In a new `api/analysis_read.py` and `api/schemas.py` (design D4): `AnalysisState`, `ClipAnalysisOut`, and
  `AnalysisOut` gaining required `state`, `clips` and nullable `job`; the read overlays `analyzing` from
  `active_job(kind=ANALYSIS)` (forced job: `failed` clips read `analyzing`, `current` stay); `analyzed` and
  `segments` keep their values (docstring marks `analyzed` legacy). `GET …/analysis` moves its body here, maps the
  state error to a 502 without a kind and gains `job_store_unreachable` (503). Verify in
  `tests/test_api_analysis_state.py` (`requires_db`) one test per scenario of the MODIFIED "Analysis results are
  exposed read-only": render manifest only → `never`; replaced clip → `stale` with no segments for it; new clip →
  `never` in a `stale` event; marker → `failed` with `detail`; running job at 0.4 → `analyzing`, `job.progress` 0.4,
  current clips stay `current`; forced queued job over all-current clips; unreadable entry → 502 no kind;
  `OperationalError` → 503 `check` `database`; no process started; and every existing analysis-read test in
  `tests/test_api_events.py` passes without edits to its assertions.

- [x] 3.2 Add `POST /api/v1/events/{event_id:path}/analysis` in `routes/events.py` before the greedy detail route, with
  `AnalysisEnqueueRequest` (optional body) and `AnalysisFreshResult` (design D2; check order 404/502 → 409 → 502 →
  200 → 201/409). Verify in `tests/test_api_analysis_enqueue.py` (`requires_db`, each test builds its own event):
  never → 201 `kind` `analysis`, `force` false, `fingerprint` null, one row, no file written, no process; all current
  → 200 `fresh` `clip_count` 4 `failed_count` 0, no row; current+failed without body → 200 `failed_count` 1; the same
  with `{"force": true}` → 201 `force` true and the marker file still present; stale → 201; repeat with and without
  force → 409 with the first id; a forced request over a queued unforced job → 409 and the job now `force`, over a
  running one → 409 and `force` stays false; race (patched `active_job` → `None`) → one 201, one 409 with its id; forced empty
  event → 200 `clip_count` 0; unknown id → 404; unlistable folder → 502 `unreadable_disk`; broken `reel.yaml` → 201;
  `submit` raising `OperationalError` → 503; an id containing `/` reaches the route and `GET /events/{id}` still
  reaches the detail.

- [x] 3.3 Add `POST /api/v1/analysis` and `AnalyzeAllResult` (design D3), walking the events list's own event set and
  using one `latest_by_project(kind=ANALYSIS)` read. Verify in `tests/test_api_analysis_enqueue.py` (`requires_db`):
  the four-event project gives `queued` 2 / `fresh` 1 / `active` 1, two unforced rows; the repeat gives 0 / 1 / 3 and
  no row; one unlistable event lands in `unreadable` with `unreadable_disk` while another is queued; a
  `.reelignore`d folder is never counted; an unknown layout is 502 with no row; `submit` failing on the second event
  is 503 and the first row stays; no process is started; every inserted row is unforced.

- [x] 3.4 Pin the kind vocabulary and per-kind independence (design D5; code only where a test fails). Verify in
  `tests/test_api_analysis_enqueue.py` and `tests/test_api_ws_hub.py`: an analysis job reads `kind` `analysis` on
  the detail, the list, the analysis read and a WebSocket delta (with its progress and its terminal row once), and the
  event's `latest_job` stays its render; a running render does not make the analysis enqueue a 409, a queued analysis
  job makes neither the render nor the proxy enqueue a 409; cancel of a queued analysis job is `canceled-queued` and
  leaves render and proxy rows untouched; the existing render, proxy and WS tests pass unedited.

## 4. Generated artifacts and the web

- [x] 4.1 Regenerate `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and
  `web/src/api/schema.d.ts` (`npm run generate:types` in the node:22 container), and add to
  `web/src/jobs/kinds.test.ts` that an `analysis` job is neither a render nor a proxy job and is not counted by
  `countRenders` (no change to `kinds.ts`). Verify in `tests/test_api_openapi.py`: `JobKind` is `render`, `proxy`,
  `analysis`; `AnalysisState` is the five values and both `state` fields reference it; `AnalysisOut` requires `state`
  and `clips`; both new routes declare the bodies and responses of their spec requirements; the 503 on
  `GET …/analysis`; the drift test passes. In the container: `npx tsc --noEmit`, `npm test` and `npm run build` pass
  with no hand edit under `web/src` besides `schema.d.ts` and the tests (the required `state` and `clips` made
  `suggestions.test.ts`'s hand-built `AnalysisOut` fixtures fail `tsc -p tsconfig.test.json`; they go through a
  `legacy()` helper now, no production web file is touched).

- [ ] 4.2 Verify in real browsers (Playwright from the scratch directory only; Chrome via
  `localhost/playback-research:chrome`, Firefox >= 155 via `localhost/pcm-audio-research:pw163` after
  `firefox --version` shows it; locators scoped to `main:not([hidden])`; `page.wait_for_timeout`; route only
  `**/api/v1/jobs` and `**/api/v1/jobs/**`). With a dev library from `scripts/make_dev_library.py` on this change's
  directory, served on this change's port and database with a worker, at 1280 and 390 px in light and dark, look at
  the screenshots: (a) the event list, an event page and its Timeline render as before with no console error;
  (b) from the page, `fetch` `POST …/analysis` on a short event returns 201, the page's socket receives frames with
  `kind: "analysis"` and rising `progress`, `GET …/analysis` reads `analyzing` with `job` during the run and
  `current` after, and a repeat POST then answers 200 `fresh`; (c) `POST /api/v1/analysis` answers counts that match
  the library and the header's render count never includes the analysis jobs; (d) a POST with `{"force": true}`
  while a render runs is 201 and the render is not delayed by it (the gate's claim order).

## 5. Docs and validation

- [x] 5.1 In `docs/high-level-design.md`: under the gate's analysis-job decision (its D-n; if it took none, add the
  next free number, never D-18/D-19/D-20/D-21 nor a reused one) an "Enqueue over REST and state" addendum (the two
  routes, 201 / 200 fresh / 409, the five-state vocabulary, the stat-only rule shared with `--enqueue`, force handled
  by the job); in **D-20** "Analysis overlays", that the lane's note will read `state` instead of `analyzed`
  (`analysis-web-controls`); in **§4.9** one paragraph beside the proxy enqueue (kinds now `render | proxy |
  analysis`, the analysis read needs the store for `analyzing`); in **§4.10** the v2 entry for `analysis-enqueue-api`;
  in **§6** phase 9 its status. Verify with `grep -n "analysis-enqueue-api\|/analysis" docs/high-level-design.md`
  showing each place and no D-number reused.

- [ ] 5.2 Run the validation gates: black + isort, `mypy auto_reel_ng`, `pylint auto_reel_ng` (only the known cairo
  `no-member` noise), the full `pytest` (background, generous timeout, podman for `requires_db`), and `npx tsc
  --noEmit`, `npm test`, `npm run build` in the node:22 container. Verify: all pass; `git diff --stat` shows nothing
  under `render/`, `scheduler/`, `proxies/`, `staleness/` (no `RENDER_GRAPH_VERSION` change) and no Alembic revision;
  `openspec validate analysis-enqueue-api --strict` passes.
