Conventions for every task below:

- Python runs from the checkout root with `.venv/bin/python -m pytest` (never `.venv/bin/pytest`), with `TMPDIR`
  exported to the change's own tmp directory (`/tmp` has a small quota). Node runs only in
  `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 ...`.
- A running service or a browser check uses only this change's port, database, dev library and scratch directory.
  Never the shared dev library, `auto-reel-media/`, or another change's resources; never remove a container this
  change did not create (the `auto-reel-ng-test-pg-*` ones belong to pytest).
- Run the validation gates (task 5.2) after each task, not only at the end.

## 1. Gate and persistence

- [ ] 1.1 Confirm that the archived `proxy-job`, `proxy-state-read` and `proxy-media-endpoints` changes (and
  `job-kind`, `proxy-encode`, `filmstrip-sprites` beneath them) exist on `main`. If one does not, stop and
  report. Then check each row of design "Gate" against the code they left and write the real names into the
  design: the job-kind enumeration and where it lives, `submit` / `active_job` and their kind arguments, the
  proxy-state function and the settings resolution, and the clip set `proxy-job` prepares. Re-read the archived
  text of every `api-service` requirement the delta refers to ("Jobs lifecycle over REST", "WebSocket live job
  updates", the two latest-job requirements) and correct cross-references in `specs/api-service/spec.md` (names
  only, never behaviour). Verify: every row of design "Gate" holds or the design and spec are corrected (in
  particular the clip-set row: the 200's set equals the job's set), and
  `openspec validate proxy-enqueue-endpoint --strict` passes.

- [ ] 1.2 `job-kind` already scoped `JobStore.latest_by_project` to one kind (`kind=JobKind.RENDER` default, in the
  ranking subquery's `where`), so make no persistence change and record that in the design (done in 1.1). Keep the
  checks as tests in `tests/test_job_store.py` only if `tests/test_job_store_kind.py` lacks them: a project with
  `2024/Blandat` whose render `done` at T and proxy job created at T+5 s returns the render; an event with only a
  proxy job is absent; `kind=proxy` returns the proxy job.

## 2. api/ - the job's kind, and the proxy clip set

- [ ] 2.1 In `api/events_read.py`, add `proxy_clips(event_dir)` (the identities `scan_event` lists: what `proxy-job`
  prepares; `reel.yaml` is not read) and `proxies_fresh(settings, event_dir)` returning the clip count and whether
  every clip's state, from `proxies.read_proxy_state`, is `ready`. The detail's `_clip_proxy` keeps its "unknown"
  fallback; this calls `read_proxy_state` directly so errors stay errors. No subprocess, no write. Verify in
  `tests/test_api_events.py` (no database): a folder with clips at the root and in a chapter folder, one of which
  `reel.yaml` ignores and one excludes, yields every clip on disk and none that only `reel.yaml` lists; all
  `ready` gives `(count, True)`; one each of `absent`, `stale`, `failed` gives False; no clips gives `(0, True)`;
  an unreadable cache directory (permission denied) raises (never `absent`/`ready`), as does a clip that cannot be
  statted; the same call under a `subprocess.Popen` / `subprocess.run` monkeypatch that fails the test never
  reaches it; the detail's `proxy` field state equals this function's for the same event.

- [ ] 2.2 In `api/schemas.py` and `api/serialize.py`, publish the job-kind enumeration (the persistence enum,
  docstring written for a client) and add required `kind` to `JobOut` and `JobSummaryOut`; `job_to_out` and
  `events_read._job_summary` set it. Both `events_read` latest-job reads name `kind=JobKind.RENDER`. `GET
  /api/v1/jobs` passes `kind=None` to the store's `list_by_status` (a proxy job is listed, marked). Verify: in `tests/test_api_jobs.py` (`requires_db`), a created render job's 201 body, detail, list item
  and the event row's `latest_job` all read `kind` `render`, every other field equal to what the same test
  asserted before (existing assertions unchanged); a proxy job inserted with `store.submit(kind=proxy)` reads
  `kind` `proxy` on detail and list; in `tests/test_api_events.py` (`requires_db`) the three scenarios of "An
  event's latest job is its latest render job" (newer running proxy; proxy-only event is `null`; failed render
  beside a done proxy) on both the list and the detail; the hub tests' stand-in jobs gain `kind` and pass.

## 3. api/ - the endpoint

- [ ] 3.1 Add `POST /api/v1/events/{event_id:path}/proxies` in `routes/events.py`, registered before the greedy
  detail route, and `ProxiesFreshResult` in `schemas.py` (design "Decisions"). Order: `listed_event_dir` (404),
  `scan_event` with `OSError` mapped to `EventReadError` (502 with `failure` `unreadable_disk`), the `proxies`
  settings and cache (502 without a kind), `active_job(kind=proxy)` (409 `active_job`), `proxies_fresh` (200), then
  `submit(kind=proxy)` (201, or the race's 409). Move `_job_store_unreachable` to a module both route files
  import and apply it here (503). The enumeration docstring of `EnqueueConflict` is generalised. Verify in
  `tests/test_api_jobs.py` (`requires_db`; each test builds its own event): 201 with a `queued` proxy row,
  `event_dir` equal to the list's id for a nested id, `force` false, `fingerprint` null, no file in the proxy cache
  and no process (monkeypatched `subprocess`); a second request is 409 `active_job` with the first job's id and one
  row; two requests racing past the pre-check (patch `active_job` to return `None`) give one 201 and one 409 with
  the 201's id; all-`ready` event is 200 with `clip_count`, status `fresh` and no row; one `stale` and one
  `failed` clip each give 201; a clip only `reel.yaml` lists, absent from disk, with the others `ready` is 200, and
  with one `absent` is 201; an ignored `absent` clip gives 201; an event with no clips is 200 `clip_count` 0; an
  active job with every clip `ready` is 409; unknown id is 404 with `event_id`; an event folder that cannot be
  listed is 502 with `failure` `unreadable_disk` and `event_id`; an unparseable `reel.yaml` and an event with no
  title are 201, not errors; a cache directory that cannot be listed is 502 with no `failure` and no row;
  `JobStore.submit` raising `OperationalError` is 503 with `check` `database`; a route-order test shows an event
  id containing `/` reaches the new route and `GET /events/{id}` still reaches the detail.

- [ ] 3.2 Pin the per-kind rule from the render side, and the WebSocket. Verify in `tests/test_api_jobs.py` (`requires_db`): a
  `running` proxy job for `2024/2024-06-27 - Grillning med grannar` does not make `POST /api/v1/jobs` a 409 (201,
  a `queued` render, the proxy row unchanged); a `queued` render does not make the proxy enqueue a 409; with
  both queued, `POST /api/v1/jobs` is 409 `active_job` whose `job_id` is the render's; `POST /jobs/{id}/cancel`
  on a `running` proxy job is `flagged-running` / `running` and on a `queued` one `canceled-queued`, and the
  event's render rows are untouched; every existing render enqueue, fresh, force, collision, missing-clip and
  cancel test passes without edits (the render's behaviour is unchanged).

  And the socket, with the same fixtures: extend the frame and lifecycle tests with proxy jobs; `api/ws.py` reads with `kind=None` (design "The jobs
  WebSocket"; the tests below fail without it). Verify in `tests/test_api_ws_hub.py`: a snapshot
  with a `running` proxy job and a `queued` render holds both with their `kind`; a proxy job's `queued` ->
  `running` (progress 0.4) -> `done` arrives as deltas in order with the terminal row exactly once; a proxy job
  created, claimed and finished between two polls is delivered once; another project's proxy job is never sent.
  In `tests/test_api_ws_lifecycle.py` (and `tests/test_api_ws_e2e.py` for one real socket): the existing
  lifecycle cases (last close stops the poller, slow consumer 1013, shutdown 1012) pass with a proxy job active,
  and a client connected while a proxy job runs gets the snapshot first; a frame holding only render jobs equals
  the pre-change frame plus `kind: "render"` per job.

## 4. Generated artifacts and the web

- [ ] 4.1 Regenerate `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and
  `web/src/api/schema.d.ts` (`npm run generate:types` in the node:22 container). Verify in
  `tests/test_api_openapi.py`: the job kind is the closed enumeration `render`, `proxy`, in `required` of both
  the job detail and the latest-job model with identical definitions; the proxy enqueue declares its 201 `JobOut`,
  its 200 `ProxiesFreshResult` (required constant `status` `fresh`, `clip_count`), and 404 / 409 / 502 / 503 shared
  problem bodies, no request body; no duplicate operation id warning; the drift tests pass. In the node:22
  container: `grep` finds `ProxiesFreshResult` and `JobKind` in `schema.d.ts`; `npx tsc --noEmit`, `npm test`
  and `npm run build` pass with no hand edit under `web/src` (the existing screens compile and pass because they
  read `kind` nowhere; if `tsc` fails in a closed `switch`, that is a finding to report, not a reason to widen
  scope).

- [ ] 4.2 Verify in real browsers (Playwright from the scratch directory only; Chrome via
  `localhost/playback-research:chrome`, Firefox >= 155 via `localhost/pcm-audio-research:pw163` after
  `firefox --version` shows it; locators scoped to `main:not([hidden])`; `page.wait_for_timeout`, never
  `time.sleep`; route only `**/api/v1/jobs` and `**/api/v1/jobs/**`). Build a dev library with
  `scripts/make_dev_library.py` on this change's directory, serve it on this change's port and database with a
  worker (proxies cache under this change's `XDG_CACHE_HOME`), and, at 1280 and 390 px in light and dark,
  look at the screenshots: (a) the event list and an event page render and show a render's live progress exactly
  as before, with `kind: "render"` on the socket frames (read in the page with a `WebSocket` listener) and no
  console error; (b) from the page context `fetch('POST .../proxies')` for the event returns 201, the page's own
  socket then receives a frame whose job has `kind: "proxy"` and a rising `progress`, a second POST answers 409
  with that job's id, and after the job is `done` the same POST answers 200 `fresh` with the clip count and
  `GET .../proxy?clip=` for a clip answers 200 (the gate's endpoint, as the proof the enqueued job produced
  something); (c) a render enqueued while the proxy job runs is 201 and finishes; (d) cancelling the proxy job
  mid-run through `POST /api/v1/jobs/{id}/cancel` leaves no `.part` in the cache. Record in the result, not in
  the repo, that the header's "rendering" count includes the proxy job (design "Risks"); that is the known
  interim limitation, not a failure of this task.

## 5. Docs and validation

- [ ] 5.1 In `docs/high-level-design.md`: add to **D-21** (proxy contract, written by `proxy-encode`) a
  bullet that proxy preparation is a job of kind `proxy` enqueued by `POST /api/v1/events/{event_id}/proxies`
  (201 / 200 fresh / 409, no body, freshness from the clips' `proxy` state, not a staleness input), and that a
  job reports its `kind` while `latest_job` stays the latest render; to **D-20** (timeline), that the Prepare
  state calls this endpoint and follows the job on the socket; in **§4.9**, one paragraph beside the jobs
  description saying the jobs shapes carry `kind`, that the proxy enqueue is a job-lifecycle route (Principle V:
  the work is `auto-reel proxies`'s) and that proxy jobs share the WebSocket; in **§4.10** the v2 change list
  entry for `proxy-enqueue-endpoint`; in **§6** phase 9, the status of the proxy enqueue. Verify with `grep -n
  "proxy-enqueue-endpoint\|/proxies" docs/high-level-design.md` showing each place, and that no D-n number is
  reused or renumbered (D-18 and D-19 stay the bug round's).

- [ ] 5.2 Run the validation gates:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng` (only the known cairo `no-member` noise)
  - `.venv/bin/python -m pytest` (full, in the background with a generous timeout; podman for `requires_db`)
  - `npx tsc --noEmit`, `npm test` and `npm run build` in the node:22 container

  Verify: all pass; `git diff --stat` shows nothing under `render/`, `scheduler/`, `proxies/` or
  `staleness/fingerprint.py` (`RENDER_GRAPH_VERSION` is untouched, as the proposal says), no Alembic revision,
  and no hand-edited file under `web/src` besides the generated `schema.d.ts`; and
  `openspec validate proxy-enqueue-endpoint --strict` still passes.
