## 1. Baseline

- [x] 1.1 Confirm the code this change was designed against. Report to the supervisor if a check fails in a
  way the design does not cover.
  - `git diff 6a7fe16 -- auto_reel_ng/api/routes/jobs.py auto_reel_ng/api/routes/events.py auto_reel_ng/api/app.py web/src/api/jobs.ts web/src/jobs openspec/specs/api-service/spec.md openspec/specs/web-app/spec.md`
    prints nothing, or the difference is read and the MODIFIED block of `specs/web-app/spec.md` is re-based
    on the current "An event's page schedules its render" text (then re-run
    `openspec validate api-jobs-db-outage-503 --strict`).
  - `grep -n "exception_handler" -r auto_reel_ng` prints nothing (no app-wide handler appeared).
  - `grep -n "503" web/openapi.json` lists only the events reads and `/healthz`.

  Verify: every check holds, or the difference is in the final report.

## 2. api/ — the jobs routes answer 503 `check: database`

- [x] 2.1 Red first. In a new `tests/test_api_jobs_database_outage.py` (not `test_api_jobs.py`, whose module-level `requires_db` mark would pull the offline tests into the container lane) add an `offline_client` fixture (a project with one event on
  disk and `DATABASE_URL` = a closed port, as `tests/test_api_events_failures.py` does; no container, no
  `requires_db`) and tests, each validating the body against `ProblemOut` and asserting `status == 503`,
  `title == "Service Unavailable"`, `check == "database"` and a non-empty `detail`:
  `GET /api/v1/jobs`, `GET /api/v1/jobs/{uuid}`, `POST /api/v1/jobs/{uuid}/cancel`, `POST /api/v1/jobs` for
  an existing event; plus `POST /api/v1/jobs` for an unknown event (404 with `event_id`, database untouched)
  and a test that `GET /api/v1/events` and `GET /api/v1/jobs` agree on `title`, `status` and `check`.
  Run `.venv/bin/python -m pytest tests/test_api_jobs.py tests/test_api_jobs_database_outage.py`:
  the four 503 tests and the agreement test fail (the jobs routes answer 500); the unknown-event 404 test
  already passes and pins that the disk checks keep answering first.

  Verify: the four fail for the stated reason (status 500), not for a fixture error.

- [x] 2.2 In `auto_reel_ng/api/routes/jobs.py` add the `_job_store_unreachable` decorator from the design
  (module `logger`, `functools.wraps`, `ParamSpec` typing that passes strict mypy) and apply it under
  `@router.post`/`@router.get` on `create_job`, `list_jobs`, `get_job` and `cancel_job`. Import
  `service_unavailable` from `..problem` and `SQLAlchemyError` from `sqlalchemy.exc`. Do not touch
  `routes/events.py` or `app.py`.

  Verify: the 2.1 tests pass; the existing `tests/test_api_jobs.py` (with `requires_db`) still passes, which
  shows FastAPI still resolves the wrapped signatures (path `job_id`, query `status`, body `payload`).

- [x] 2.3 Publish the response. Add `503: {"model": ProblemOut}` to the `responses=` of the four routes,
  regenerate with `.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`, and extend `EXPECTED_JOBS_RESPONSES` in
  `tests/test_api_openapi.py` so the four operations must declare a 503 whose schema is `#/components/schemas/ProblemOut`. Update the
  four route docstrings' failure sentence if they list answers.

  Verify: `git diff web/openapi.json` adds only the four 503 entries; `tests/test_api_openapi.py` passes.

## 3. web/ — the screens word the outage

- [x] 3.1 Regenerate `web/src/api/schema.d.ts` (`npm run generate:types`, Node only through podman:
  `podman run --rm -v $WT/web:/app:Z -w /app docker.io/library/node:22 npm ci && npm run generate:types`),
  then in `web/src/api/jobs.ts` add the `isDatabaseDown` predicate and a `{ kind: 'database'; problem:
  Problem }` case to `EnqueueResult`, `JobResult` and `CancelAnswer`, returned by `enqueueJob`, `fetchJob`
  and `cancelJob` before their own problem statuses. A 503 that is not `check === 'database'` stays
  `unpublished`. Update the "problem statuses each route publishes" comment.

  Verify: `npx tsc --noEmit` now fails in exactly the switches that must handle the new kind
  (`RenderControl.tsx`, `LiveJobCell.tsx`, `jobs/store.ts`), nowhere else.

- [x] 3.2 Handle the kind. `RenderControl.tsx`: the `notQueued` and `cancelUnconfirmed` notices carry a cause
  (`unpublished` | `unreachable` | `database`) instead of `answered: boolean`; `database` titles with
  `${NOT_QUEUED} ${DATABASE_CAUSE}` / `${NOT_CONFIRMED} ${DATABASE_CAUSE}` and shows `problem.detail`.
  `LiveJobCell.tsx` `tellRowAnswer`: `toast.error(`${name}: ${NOT_QUEUED} ${DATABASE_CAUSE}`)` with no link.
  `jobs/store.ts` `load`: `database` keeps the last known copy (no `forget`, no toast). Import
  `DATABASE_CAUSE` from `../events/common`. If `jobs/labels.ts` gains a sentence, it is the one in the spec,
  not a new wording.

  Verify: `npx tsc --noEmit` clean; `npm run build` succeeds.

- [x] 3.3 Verify in Chromium (scratchpad script, never in the repo; follow the brief's Playwright rules).
  Serve the build against a dev library and database; route only `**/api/v1/jobs` and `**/api/v1/jobs/**`
  to answer, per case, 503 `{title, status: 503, detail, check: "database"}`, 503 without `check`, and 500
  with no body. Check, in light and dark at 1280 and 390, and look at the screenshots:
  - event page Render: the alert reads "The render was not queued. The service can't reach its database."
    with the detail, and Render is offered again; the 503 without `check` and the 500 read with their status
    and never name the database
  - list row Render: one error toast naming the event, no link; no horizontal scroll at 390
  - Cancel on a queued job: "The cancel was not confirmed. The service can't reach its database.", the job
    still shown as queued
  - a 503 on a job read (`GET .../jobs/{id}`): no toast, the job stays shown
  Also `curl` the four jobs routes of a throwaway `auto-reel serve` (own port, own database name) started
  with an unreachable `DATABASE_URL`: 503 with `check: database` for each.

  Verify: every case behaves as listed, with the screenshots viewed.

## 4. Gates

- [x] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` (only the known cairo
  `no-member` noise), and `.venv/bin/python -m pytest` (full suite with podman; `-m "not requires_db"` and
  say so if podman is unavailable).

- [x] 4.2 Web: `npx tsc --noEmit` and `npm run build` through podman; confirm `web/src/api/schema.d.ts` and
  `web/openapi.json` match a fresh generation (`tests/test_api_openapi.py` passes).
