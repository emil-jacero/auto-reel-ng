## Why

Two read-model gaps leave the GUI saying less than the engine knows, found in the bug triage of `main` at `6a7fe16`; the spec was re-checked against `main` at `ad08dbf`, with both gates merged.

**1. The latest job hides a requeue and a cancel request.** `JobSummaryOut` (the `latest_job` of the events list and
detail) carries `id`, `status`, `progress`, `created_at`, `started_at` and `finished_at`. `JobOut` also carries
`cancel_requested` and `requeue_count`, but `_job_summary` in `api/events_read.py` copies only the six. The client
(`web/src/jobs/useJob.ts`, `choose`) merges a read over the store's copy of a running job, while the jobs connection
is down, only when `isFurther` finds the read further along (running beyond queued, a later start, more progress). A
requeue (`JobStore.requeue`: back to `queued`, `started_at` and `progress` cleared, `requeue_count + 1`) is the
opposite of further along, so the read loses and the page keeps showing the last known running state with its
progress, for a job that is waiting in the queue. The same gap hides a cancel pending: a screen that knows a job
only from a read cannot say "Cancelling…" and offers Cancel again.

**2. A stale verdict says `output_renamed` and names neither file.** The reason says the movie's name changed and the
old movie is still on disk, but neither the API's `StalenessOut` nor the event page says which two files are meant.
The gate computes both (the manifest's recorded name and the expected output name) and drops them. The page's note
("the next render saves the movie under its new name; the movie under its old name stays on disk") makes the
reader open the Movie section to learn the old name, and nothing shows the new one. The engine and the CLI half is
`output-renamed-names-files`, which gives the gate's `Verdict` the names and makes `scan` print them. This change is
the API and GUI half, as that change's summary says.

## What Changes

- **`JobSummaryOut` gains `cancel_requested` and `requeue_count`**, required and with no defaults, exactly as `JobOut`
  declares them. `_job_summary` fills them from the job row. The list and the detail carry the same values as
  `GET /api/v1/jobs/{id}`.
- **`useJob.choose` treats a read with a higher `requeue_count` as authoritative while the connection is not live.** It
  brings the read's status, progress, times and flags forward over the held copy, so a requeued job shows as waiting.
  A read's `cancel_requested` is shown too: "Cancelling…" and no Cancel, also for a job known only from a read.
- **`StalenessOut` gains `renamed_from` and `output_name`**, optional nullable strings, always present, both set exactly
  when `output_renamed` is cited. They flow to the events list, the detail and an editorial write's echoed verdict
  through the one function that builds the verdict. **BREAKING for exact-equality clients only**: a verdict object
  has two more keys. Every existing key keeps its name, type and value.
- **The event page's `output_renamed` note names both files**: "The next render saves the movie as *new*. The movie
  *old* stays on disk." The list keeps its short words and names no file. A verdict without names (null) falls back
  to the sentence without file names, never to an invented one.
- `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: MODIFIED `Staleness reasons are a closed, published vocabulary` (the verdict names the two movie
  files behind `output_renamed`, in every response that carries a verdict); ADDED `An event's latest job reports its
  cancel request and requeue count`.
- `web-app`: MODIFIED `The event page says what a render does when the movie's name changed` (the note names both
  files; the earlier text forbade the verdict from naming any); ADDED `A shown job follows a requeue and a cancel
  request that a read reports`.

## Impact

- **Packages (two, Principle VIII):**
  - `api/`: `schemas.py` (two fields on `JobSummaryOut`, two on `StalenessOut`), `events_read.py` (`_job_summary`,
    `staleness_for`), regenerated `web/openapi.json`
  - `web/`: regenerated `src/api/schema.d.ts`, `src/jobs/useJob.ts`, `src/jobs/shownJob.ts` (new), `src/jobs/JobProgress.tsx`,
    `src/jobs/RenderControl.tsx`, `src/events/labels.ts`, `src/events/common.tsx`, `src/events/detail.css`
- **Tests:** `tests/test_api_events.py` (`requires_db`), `tests/test_api_openapi.py`, and the exact-equality verdict
  assertions in `tests/test_api_editorial_write.py` and `tests/test_editorial_write_e2e.py`. The web's Node runner (`npm test`)
  gets `src/jobs/shownJob.test.ts` (the choice rule, moved out of `useJob.ts` into the pure module `shownJob.ts`) and
  `src/events/labels.test.ts` (the note); the screens are also checked with Playwright from the scratchpad.
- **CLI vs API (Principle V):** nothing here is beyond the CLI's reach. `auto-reel jobs show` already prints
  `cancel_requested` and `requeue_count`. `scan` prints the two file names in `output-renamed-names-files`. The API
  only shapes facts the engine and the job store already hold.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump**; the fingerprint inputs and the gate's decision
  are unchanged, only what it reports.
- **Schemas:** no `reel.yaml` or `config.yaml` change, no Alembic migration, no rescan.
- **Wire:** additive. `latest_job` gains two required keys, the verdict two always-present nullable keys.
- **Dependencies (gates, merged before this change is implemented):** `output-renamed-names-files` (the `Verdict` carries
  the old name) and `api-excluded-clips-read-model` (edits `schemas.py`, `events_read.py` and `EventDetail.tsx`
  around, not in, the models and functions this change touches). Task 1.1 checks both.
