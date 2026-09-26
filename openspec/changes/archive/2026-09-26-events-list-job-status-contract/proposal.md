## Why

GUI v1 slice B, the event list screen (HLD **§6 phase 8**, §4.10, stack **D-8**), is next. Speccing it
against the shipped API found two places where the generated client types say less than the screen must
know. The screen would have to work around both by hand, which is exactly what D-8's
schema → types pipeline exists to prevent.

1. **Job status is published as a bare string.** `EventSummaryOut.latest_job.status` (`JobSummaryOut`) is
   `str`, so `openapi-typescript` generates `string`. The list shows each event's latest job, so the
   screen must switch on its status: `queued`, `running`, `done`, `failed` or `canceled`. The vocabulary
   is closed and already owned by `persistence/` as `JobStatus`, and the schema even publishes that enum
   for `GET /api/v1/jobs?status=`. Only the response fields drop it. §4.10's rule, written by
   `events-list-client-contract`, is explicit: a closed set published as `str` means every client
   restates it in a hand-maintained map, and a renamed status leaves every check green while the UI
   degrades. The same hole sits in `JobOut.status` (jobs routes and the WS frames slice E will read) and
   `CancelResult.status`.
2. **The events reads' error bodies are not in the schema.** `events-list-client-contract` gave both
   events reads distinct problem bodies, a 503 naming the database and a 502 naming the scan, so a screen
   can say *why* it failed. But the routes return them as untyped `JSONResponse`s. The OpenAPI schema
   declares only `200`, and no problem model exists. A client that reads `title`, `detail` or `check`
   must declare that shape by hand, which the `web-app` spec forbids ("no equivalent shape is declared by
   hand").

Both belong to `api/`. As with `events-list-client-contract`, fixing them here keeps slice B a pure
`web/` change (Principle VIII).

## What Changes

- **Job status fields are typed with `JobStatus`.** This covers `JobSummaryOut.status`, `JobOut.status`
  and `CancelResult.status`. The schema then publishes the enumeration, and the generated TypeScript
  becomes a union. **Wire values do not change.** `JobStatus` is a `str` enum with the same five values
  already sent.
- **A `ProblemOut` model describes the shared problem body.** It has `title`, `status` and `detail`, plus
  the optional fields the events reads send: `check` on a database failure, and `event_id` on a
  per-event failure. Further route-specific fields are still allowed.
- **Both events reads declare their problem responses in the schema.** The list declares `502` and
  `503`. The detail declares `404`, `502` and `503`. Runtime behavior is unchanged: the routes already
  return exactly these bodies. Only the schema learns about them.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.**

## Non-goals

- **No screen.** Slice B (`event-list-screen`) is the next change.
- **No change to any response body, status code or wire value.** This change types what is already sent.
- **No problem declarations beyond the two events reads.** The jobs routes (409 on a duplicate enqueue,
  404), the editorial routes and `/healthz` keep undeclared problem responses. Slice E, which drives
  `POST /api/v1/jobs`, declares the ones it reads.
- **`ClipOut.status` stays `str`.** The clip reconcile vocabulary (`new`/`active`/`missing`/`ignored`) is
  another closed set with the same flaw, but it appears only on the detail response. Slice C reads it,
  and its prerequisite types it.
- **No output-collision surface.** Neither the list nor the jobs API reports colliding output paths yet
  (see `output-path-year-folder`, Non-goals). That lands before slice E.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - new `Requirement: Job status is a closed, published vocabulary`
  - `Requirement: Events reads fail loud with a problem body` now also requires both reads to publish
    their problem responses (status codes and body shape) in the OpenAPI schema

## Impact

- **Packages:** `api/` only.
  - `schemas.py`: three field annotations and one new model.
  - `routes/events.py`: `responses=` on two decorators.
  - `persistence/models.py` (`JobStatus`) is imported, not changed. `api/` → `persistence/` is a
    downward import (Principle VI).
- **CLI vs API (Principle V):** no CLI change. `jobs list`/`show` already print the same status strings.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.**
- **Staleness fingerprint inputs:** unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan.
- **Generated artifacts:** `web/openapi.json` and `web/src/api/schema.d.ts` move.
  `tests/test_api_openapi.py` fails until both are regenerated. The pipeline is working as designed.
- **Dependencies (Principle VII):** none.
- **Size (Principle VIII):** one package, three annotations, one model, two decorators, two regenerated
  artifacts.
