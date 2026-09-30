## Why

GUI v1 slice **E** (HLD **§6 phase 8**, §4.10, change `render-progress-screen`) shows every job with the time
that matches its state: "finished …" for a job that ended, "started …" for a running one, "queued …" for a
queued one. A job reaches a screen from two places:

- the jobs connection or a job read, which carry the full `JobOut`, with `started_at` and `finished_at`
- the events reads, whose `latest_job` is a `JobSummaryOut` carrying only `id`, `status`, `progress` and
  `created_at` (`auto_reel_ng/api/schemas.py`, `class JobSummaryOut`; filled by `_job_summary` in
  `auto_reel_ng/api/events_read.py`)

Most jobs a screen shows come from the second place. Opening the list or an event's page shows the latest
job of every event from the read, and the connection only adds jobs that are active or that this tab
followed. So a rendered row, and the page's "Last job", read **"Rendered · queued Sep 30, 6:25 PM"**. That
is the time the job was *queued*, shown under a pill that says it *rendered*. The client does not lie: it
labels the time "queued", because C5 refused to present a queued time as a finish time. That rule is
Principle I, the rule behind the legacy tool's silent fake-metadata fallback (HLD §2, problem 5). But the
page answers "when was this rendered?" with a different fact, and on the MOL archive a queue time can be
hours before the finish.

A failed job shows the same defect in a second way. An event's page reads a failed job once, for its
error text, and that read is a full `JobOut`. So `2024-10-05 - Trasig`'s page first says
"Last job · Failed · queued …", then switches to "finished …" when the job read answers. That text is in
the page's `role="status"` region, so a screen reader announces the switch although the job's state did
not change. C5's own rule is that only state changes are announced. (This was measured with Playwright
against C5's build, with the job read held.)

The fix belongs in the read model, not the client. The client's types come only from the schema (D-8), so
it cannot show a time the schema does not publish. The job store already records both times
(`persistence/models.py`, `Job.started_at`, `Job.finished_at`). `JobStore.latest_by_project` already
loads whole rows. `JobOut` already publishes both times. Only the summary drops them.

Measured on a dev library built with `scripts/make_dev_library.py` and served on port 8112:

- `GET /api/v1/events` gives `2024-10-05 - Trasig` a `latest_job` of `{id, status: "failed", progress: 0.0,
  created_at: …14.361887Z}`
- `GET /api/v1/jobs` gives the same job `started_at …22.833079Z` and `finished_at …22.838420Z`
- a job for `2024-08-02 - Badutflykt - Varberg`, cancelled while queued, reads `started_at: null` and
  `finished_at …17.264670Z` from `GET /api/v1/jobs/{id}`, while the list's summary has neither

## What Changes

- **`JobSummaryOut` gains `started_at` and `finished_at`.** Both are optional date-times, declared as
  `JobOut` declares them. The events list rows and the event detail carry them in `latest_job`, with the
  same values and meaning as `GET /api/v1/jobs/{id}` for the same job:
  - `started_at` is when a worker claimed the job. It is null while the job is queued, again after a
    requeue, and for a job cancelled before any worker claimed it.
  - `finished_at` is when the job reached `done`, `failed` or `canceled`, and null until then.
  - A time the store did not record is null. It is never replaced with `created_at` or the current time.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.** The staleness test in
  `tests/test_api_openapi.py` fails until they are.
- **The screens date a job known only from a read by its state.** `stateTime` in
  `web/src/jobs/JobProgress.tsx` stops restricting "finished" and "started" to jobs from the connection. It
  reads the two times from whichever job it is given. A list row or a page's "Last job" then says
  "Rendered · finished …", "Failed · finished …" or "Canceled · finished …". "Queued …" stays for queued
  jobs, and for a job whose matching time is absent, still labelled "queued". A failed event's page shows
  its finish time as soon as the event is read, so the status region's words stay the same when the job
  read for the error text answers.

## Non-goals

- **No further summary fields.** `error`, `cancel_requested`, `event_dir`, `device` and the rest stay on
  `JobOut`. C5 deliberately keeps a list read from carrying or fetching a failed job's error text, and
  "Cancelling…" comes from the connection only. The summary grows by exactly the two times.
- **No change to the job store, its queries or its timestamps.** No new column, no Alembic migration, and
  `latest_by_project` stays one `DISTINCT ON` query.
- **No new time format or wording.** C5's short "Sep 30, 6:25 PM" format and its "finished / started /
  queued" labels stay. Only the input changes.
- **No `JobCell` clean-up.** `render-progress-screen` already removed it (from `web/src/events/common.tsx`)
  before it was archived, so there is nothing left to remove (design, "Supervisor decisions").
- **No change to the WebSocket, the jobs routes, or `JobOut`.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: ADDED `Requirement: An event's latest job reports when it started and finished`. The
  events reads' `latest_job` carries `started_at` and `finished_at` with the job detail's values, published
  in the schema as the job detail publishes them.
- `web-app`: ADDED `Requirement: A shown job is dated by the time that matches its state`. The same
  labelled time is shown whether the job came from the connection, a job read or a screen's events read.
  No requirement is MODIFIED, so neither `render-progress-screen`'s nor a parallel change's text is
  rewritten.

## Impact

- **Packages (two, Principle VIII):**
  - `api/`:
    - `schemas.py`: two fields on `JobSummaryOut`, and its docstring
    - `events_read.py`: `_job_summary` passes the two times
    - regenerated `web/openapi.json`
  - `web/`:
    - regenerated `src/api/schema.d.ts`
    - `src/jobs/JobProgress.tsx`: `stateTime` and its comment
- **Tests:** `tests/test_api_events.py` (`requires_db`) and `tests/test_api_openapi.py`. The web has no
  test runner (D-8: `tsc --noEmit` is its gate), so the screens are checked with Playwright from the
  scratchpad (task 5.1).
- **Docs:** the `README.md` API service section, one sentence in `web/README.md`, and one sentence in HLD
  §4.10 (no new D-n).
- **CLI vs API (Principle V):** API only. The CLI already reports both times, in
  `auto-reel jobs show` (`cli/commands.py`, `cmd_jobs_show`). No behavior is added that the CLI cannot
  reach, and the new fields are read-model shaping of a stored fact.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan.
- **Wire:** additive only. `latest_job` gains two keys, always present (a value or `null`). Every existing
  key keeps its name, type and value. A client that ignores unknown keys is unaffected.
- **Dependencies (gate):** `render-progress-screen` must be archived on `main` first
  (`openspec/changes/archive/*-render-progress-screen`). The web half edits that change's `stateTime`, and
  the ADDED web requirement builds on its "A render's progress is shown live". Task 1.1 checks the gate.
- **Runtime dependencies:** none new (Principle VII).
- **Size (Principle VIII):** two schema fields, two serializer arguments, one client function, and two
  ADDED requirements. Seven tasks, one of them the gate.
