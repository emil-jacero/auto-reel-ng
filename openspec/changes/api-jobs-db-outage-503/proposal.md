## Why

An unreachable database reads as a bare 500 on every jobs route, and the client words it wrongly.

The events reads were taught to fail loud in the shared problem shape: an unreachable job store answers
**503 with `check: "database"`**, the same predicate `/healthz` uses (api-service, "Events reads fail loud
with a problem body"; D-A6). The jobs routes were not. Against a database URL pointing at a closed port,
on `main` at `6a7fe16`:

| Request | Answer today | Where it comes from |
|---|---|---|
| `GET /api/v1/events`, `GET /api/v1/events/{id}` | 503 problem JSON, `check: "database"` | `routes/events.py` `_job_store_unavailable` |
| `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, `POST /api/v1/jobs/{id}/cancel`, `POST /api/v1/jobs` | **bare 500 "Internal Server Error"** | `routes/jobs.py` has no `SQLAlchemyError` handling; `app.py` registers no exception handler, and none of the four `responses=` lists a 503 |

The 503 is then missing from the published OpenAPI schema too (`web/openapi.json` declares 503 only on the
events reads and `/healthz`), so the generated client types cannot name it. The client follows: the enqueue
helper (`web/src/api/jobs.ts`) publishes only 404, 409 and 502 for `POST /api/v1/jobs`, so a 503 falls to
`unpublished` and the operator reads "The render was not queued. POST /api/v1/jobs answered 503 Service
Unavailable" instead of the sentence the event screens already use for the same cause, "The service can't
reach its database." (`DATABASE_CAUSE`, `events/common.tsx`). A failed cancel reads the same way. Principle I
asks that a failure name its real cause, and "one predicate for cannot reach the database" is the stated
reason the events reads share a shape with `/healthz`.

This is bug-round item `jobs-routes-publish-no-503-database`. HLD §6 phase 8 (GUI v1 polish); no §8 research
item is open for it.

## What Changes

- **API:** the four jobs routes answer an unreachable job store with the **503 problem body**, `check:
  "database"`, the same shape the events reads and `/healthz` return, instead of a bare 500. A local
  decorator in `routes/jobs.py` catches `SQLAlchemyError` around each route body, logs a warning and returns
  `service_unavailable(...)`. Nothing is softened: no partial list, no job reported absent (Principle I).
- **Schema:** each of the four routes declares `503: ProblemOut` in `responses=`. `web/openapi.json` and
  `web/src/api/schema.d.ts` are regenerated; the drift test keeps them honest.
- **Client:** `web/src/api/jobs.ts` recognises a 503 whose problem body names the database as its own kind
  (`database`) on the enqueue, the job read and the cancel, so every caller handles it (an unhandled kind is
  a `tsc --noEmit` error). A 503 without `check: "database"` stays an unpublished answer. The screens say
  "The render was not queued. The service can't reach its database." for an enqueue (event page and list row)
  and "The cancel was not confirmed. The service can't reach its database." for a cancel, with the service's
  detail. The job store (`jobs/store.ts`) keeps its last known copy on a 503 read, as it does for any
  unanswered read.
- **Specs:** api-service gains one requirement for the jobs routes' failure; web-app modifies the render
  requirement's list of handled answers and adds one requirement for the cancel and the list row.

## Non-goals

- **No app-wide `SQLAlchemyError` handler** and no change to `app.py`: the media and editorial-write routes
  do not consult the job store today, and a blanket handler would also relabel a non-outage database error
  anywhere. Moving `_job_store_unavailable` into `problem.py` so the events reads and the jobs routes share
  one helper is a possible follow-up; `routes/events.py` is untouched here.
- **No new request validation on `POST /api/v1/jobs`.** That is `api-jobs-create-validation`, which also
  edits `routes/jobs.py` and is sequenced after this change.
- **No retry, no backoff, no queueing of a request while the database is down.** The operator presses Render
  again.
- **No change to the WebSocket poller** or to `GET /healthz`.
- **No change to what the screens say for other failures** (404, 409, 502, 500 without a problem body).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: new requirement "Jobs routes fail loud when the job store is unreachable" (503 problem body
  with `check: "database"` on all four routes, published in the OpenAPI schema).
- `web-app`: `Requirement: An event's page schedules its render` gains the database answer in its list of
  handled answers (the row inherits it); new requirement "A cancel or a job read that meets a database outage
  says so".

## Impact

- **Baseline:** written against `main` at `6a7fe16`.
- **Packages:** `auto_reel_ng/api` (`routes/jobs.py`, plus the regenerated schema dump) and `web/`
  (`src/api/jobs.ts`, `src/jobs/labels.ts`, `RenderControl.tsx`, `LiveJobCell.tsx`, `store.ts`,
  `openapi.json`, `src/api/schema.d.ts`). Tests: `tests/test_api_jobs.py`.
- **CLI vs API (Principle V):** API only. The CLI talks to the store directly and already raises on a database
  error; there is no behavior here the CLI lacks.
- **Complexity (Principle VII):** one ~12-line decorator, used four times. No new dependency, no config key.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Staleness fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. The OpenAPI
  schema gains four 503 responses.
- **Size (Principle VIII):** two capability deltas, two packages, 8 tasks.
