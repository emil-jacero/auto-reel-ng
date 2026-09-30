## 1. Gate

- [ ] 1.1 Confirm the gate is archived on `main`: `ls openspec/changes/archive/ | grep -- '-render-progress-screen$'` must print one directory. Stop and report to the supervisor if it does not. Then confirm what this change builds on (design "Context"), each with the command given:
  - `grep -n "function stateTime(shown: ShownJob)" web/src/jobs/JobProgress.tsx` and `grep -n "shown.source === 'live'" web/src/jobs/JobProgress.tsx` each hit
  - `grep -n "export type ShownJob" web/src/jobs/useJob.ts` hits, and the union's two members are `{ source: 'live'; job: JobOut }` and `{ source: 'read'; job: JobSummary }`
  - `grep -n "load(failedReadId)" web/src/jobs/RenderControl.tsx` hits. This is the failed-job read that the page scenario for Trasig relies on.
  - `grep -n "_job_summary(" auto_reel_ng/api/events_read.py` prints three lines: the definition, and the calls in `_event_summary` and `get_event`. The definition still passes only `id`, `status`, `progress` and `created_at`.
  - `grep -n "Requirement: A render's progress is shown live" openspec/specs/web-app/spec.md` hits
  - `grep -rn "latest job reports when it started\|dated by the time that matches its state" openspec/specs/` prints nothing

  Verify: every command above gives the stated result, and `openspec validate job-summary-times --strict` passes. If only a name differs (for example `stateTime` renamed or moved), use the landed name and list the difference in the final report. Do not edit `render-progress-screen`'s other files.

## 2. api/ — the latest job carries its times

- [ ] 2.1 Add `started_at: Optional[datetime] = None` and `finished_at: Optional[datetime] = None` to `JobSummaryOut` in `api/schemas.py`. Give it the docstring the design shows: the list and the detail, a projection of `JobOut`, null until stamped, with the existing `status` paragraph kept. Then pass `started_at=job.started_at` and `finished_at=job.finished_at` in `api/events_read.py` `_job_summary` (design "Declaring the two fields exactly as `JobOut` does", "Filling them where the summary is built"). Verify with new `requires_db` tests in `tests/test_api_events.py`. They use the module's `client` and `project` fixtures and `tests/conftest.py`'s `job_store`, and each compares the list row's and the detail's `latest_job` with `GET /api/v1/jobs/{id}` for `2024/2024-07-04 - Barbecue`:
  - enqueued, claimed and transitioned to `done`: the `created_at`, `started_at` and `finished_at` strings of both reads each equal the job detail's, and `created_at <= started_at <= finished_at` when parsed
  - transitioned to `failed`: the same equality on both reads, with both times non-null
  - only enqueued: both reads have the keys `started_at` and `finished_at`, both `None`
  - enqueued, then cancelled with `POST /api/v1/jobs/{id}/cancel` (outcome `canceled-queued`): status `canceled`, `started_at` is `None`, and `finished_at` is not `None` and equals the job detail's
  - claimed: status `running`, `started_at` equals the job detail's, and `finished_at` is `None`. Then `job_store.requeue(id)`, the call a graceful stop and the startup reconcile make (`tests/test_scheduler_worker.py` covers those paths): status `queued`, and both times `None`.
  - `test_a_completed_job_is_not_freshness` and the rest of the module pass unchanged

  Run `.venv/bin/python -m pytest tests/test_api_events.py tests/test_api_events_failures.py` and `.venv/bin/python -m mypy auto_reel_ng`. `test_committed_schema_is_not_stale` fails from here until 2.2, naming `components.schemas[JobSummaryOut] changed`.
- [ ] 2.2 Regenerate both artifacts from the repository root with the `web/README.md` commands:
  - `.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`
  - `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm run generate:types`
  - first run `npm ci` in the same container if `web/node_modules` is absent

  Add a case to `tests/test_api_openapi.py`: every property of `JobSummaryOut` equals `JobOut`'s same-named property (all six, `started_at` and `finished_at` included), and `JobSummaryOut.required == ["id", "status", "progress", "created_at"]`. Verify:
  - `.venv/bin/python -m pytest tests/test_api_openapi.py` passes, the new case and `test_committed_schema_is_not_stale` included
  - `git diff web/src/api/schema.d.ts` changes only `JobSummaryOut`: its rewritten `@description` block, plus `/** Started At */ started_at?: string | null;` and `/** Finished At */ finished_at?: string | null;`
  - `podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npx tsc --noEmit` passes before any client change

## 3. web/ — a read job is dated by its state

- [ ] 3.1 In `web/src/jobs/JobProgress.tsx`, make `stateTime` take `{ job }: ShownJob`, drop the `shown.source === 'live'` guard, keep the "queued" fallback, and rewrite its doc comment (design "The client: one source-independent `stateTime`"). No other client file changes. Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the node:22 container (the 2.2 `podman run` form)
  - `git diff --stat web/src` lists only `api/schema.d.ts` and `jobs/JobProgress.tsx`
  - the behavior is checked in 5.1

## 4. Docs

- [ ] 4.1 Update the docs, then verify by rereading each against the specs:
  - `README.md`'s API service section, in the "Events are scanned on request" bullet: each event's `latest_job` (list and detail) carries `id`, `status`, `progress`, `created_at`, `started_at` and `finished_at`, with the values `GET /api/v1/jobs/{id}` returns for that job, and a time not yet recorded is `null`
  - `web/README.md`'s "Rendering" paragraph: every job shown is dated by its state (finished, started or queued), whether it came from the connection or a read
  - `docs/high-level-design.md` §4.10: one sentence after the one naming `jobs-project-guards`, naming `job-summary-times` as slice E's follow-up (the events reads' latest job carries its start and finish times, so a screen dates a job it knows only from a read by its state). No new D-n (design "HLD: one sentence, no D-n").

## 5. Validation

- [ ] 5.1 Verify against the agent's own dev library (dev-env runbook §9, `SLUG=job-summary-times`, port 8112), freshly built. Serve the worktree's built `web/dist` with no worker running until the worker step below. Never touch `../auto-reel-dev`, `auto-reel-media/`, another agent's database, or port 8080.
  - **API, with `curl`:**
    - for `2024/2024-06-27 - Grillning med grannar` (`done`), `2024/2024-10-05 - Trasig` (`failed`) and `2024/Blandat` (`queued`), each `latest_job` from `GET /api/v1/events` and from `GET /api/v1/events/{id}` has `created_at`, `started_at` and `finished_at` equal to `GET /api/v1/jobs/{id}`'s. Blandat's two times are `null`.
    - `POST /api/v1/jobs` for `2024/2024-08-02 - Badutflykt - Varberg` answers 201, and its cancel answers `canceled-queued`. The list's `latest_job` for it then has that job's id, `started_at: null`, and the `finished_at` that `GET /api/v1/jobs/{id}` reports.
    - `GET /openapi.json` equals `web/openapi.json` when both are parsed as JSON
  - **Playwright** (container `mcr.microsoft.com/playwright/python:v1.49.0-noble`, `--network host`, `pip install -q playwright==1.49.0` first; script and screenshots in `<scratchpad>/verify/job-summary-times/`; locators scoped to `main:not([hidden])`; rows found by their event link's `href`, since a row shows the event's title, not its folder name):
    - in a fresh page, the list rows of Grillning, Trasig and Badutflykt each show "finished". Each row's `.job-when time` has a `datetime` equal to that job's `finished_at` from `GET /api/v1/jobs/{id}`.
    - Blandat's row shows "queued", and no row whose `.job-state` has an ended `data-status` shows "queued"
    - in a fresh page, Grillning's page shows "Last job", Rendered and "finished", with that `datetime`
    - in a fresh page, with `**/api/v1/jobs/*` held by `page.route`, Trasig's page `.render-status` already shows "Last job", Failed and "finished", with the job's `finished_at` as `datetime`. Record its text, then release the route. "Why the render failed" appears with the error text, and the `.render-status` text equals the recorded text.
    - screenshots of the list and of Trasig's page in light and dark, at 1280 px and 390 px, with no horizontal page scroll at 390 px. Take these before the worker starts, while Blandat is still queued.
    - then start `auto-reel worker <library> --device cpu` against the same database. It claims Blandat's queued job first. On `2024-08-20 - Två kapitel - Tjörn`'s page (stale for `clip_set` in a fresh library), press Render. Wait until the page's job has gone through `queued` or `running` to `done` (Rendered), and record the "finished" `datetime`. Reload the tab: the same `datetime` is shown, and it equals `GET /api/v1/events/{id}`'s `latest_job.finished_at`.
- [ ] 5.2 Run the gates: `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full `.venv/bin/python -m pytest`, including `requires_db`. Then run `npx tsc --noEmit` and `npm run build` in the node:22 container. Verify all are clean or green, apart from the known cairo `no-member` noise.
