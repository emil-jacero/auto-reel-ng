## Why

`POST /api/v1/jobs` queues a render for an event whose `reel.yaml` plays a clip that is gone from disk.
The render cannot succeed: `cli/build.py` probes every referenced, non-excluded clip
(`_probe_clips`), and `probe_media` raises for a path that is not there (Principle I). So the job is
accepted with a 201, waits for a worker, claims a GPU slot, and then fails at probe. The operator sees a
failed job where the request itself could have been refused with the reason.

The page and the list row already hold Render back for missing clips (web-app "An event's page schedules
its render", "The event list shows live job state and offers a render"), but that guard is client-side
only and works from the page's last read. It is stale whenever a clip vanishes after the read (a card
being re-copied, a drive unmounting), and it does not bind any other API caller. Triage item
`excluded-missing-clip-blocks-render-no-api-field` (verified on `6a7fe16`): with a non-excluded absent clip,
`POST /api/v1/jobs` answers 201 with `force` true or false and enqueues a job that fails at probe.

The supervisor decided (bug round, 2026-10-02): the service refuses such an enqueue with a typed 409
`missing_clips` that names the clips, and `force` does not bypass it, because the render would fail
anyway. A missing clip that `reel.yaml` **excludes** is not a reason to refuse: excluded clips never reach
the plan and are never probed (`event/resolution.py`, `cli/build.py`), so that render succeeds.

HLD §6 phase 8 (GUI v1 and editorial write API) is the phase; the enqueue is the jobs surface of
`api-service` (HLD §4.9, D-A6 for the problem body).

## What Changes

- **`POST /api/v1/jobs` refuses an event that plays a missing clip** with **409**, `conflict`
  `missing_clips`, a typed `missing` list of the played clips' identities (sorted), and a detail that names
  them and the fix (restore them, or remove them in `reel.yaml`). Played means referenced in a chapter and
  not excluded. The refusal holds fresh or stale, forced or not, and writes nothing (no job row, no
  manifest, no output file).
- **Order of the checks:** output collision, then active job, then the missing-clip check, then the
  staleness gate. An event that already has an active job is still answered by following that job; the
  refusal is for a request that would create one.
- **The conflict vocabulary gains a third member.** `EnqueueConflict` becomes `active_job`,
  `output_collision`, `missing_clips`; `ProblemOut` gains the `missing` list. `web/openapi.json` and
  `web/src/api/schema.d.ts` are regenerated.
- **The client tells the refusal.** `enqueueJob` returns a new `missingClips` kind (the closed `switch` on
  `conflict` fails `tsc` until it does). The event page shows an error notice naming the clips with the
  restore-or-remove words, and re-reads so its Render control is held back from then on. A list row raises
  an error notification naming the event and the clips, with a link to the page, and re-reads the list.
- **No change to what a render produces.** No `RENDER_GRAPH_VERSION` bump, no fingerprint input change, no
  `reel.yaml` or `config.yaml` schema change, no Alembic migration, no rescan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: a new requirement "Enqueue refuses an event that plays a clip missing from disk"; the
  `conflict` vocabulary in "Enqueue refuses an event whose output path another event claims" and "Jobs
  lifecycle over REST" gains `missing_clips`, and "a forced request always enqueues unless ..." names the
  second refusal.
- `web-app`: a new requirement "A render the service refuses for a missing clip is told, and the screen
  re-reads", covering the event page and the list row (an ADDED requirement rather than an edit of "An
  event's page schedules its render" and "The event list shows live job state and offers a render", which
  the `api-excluded-clips-read-model` change also edits; see design "Spec deltas and the two gates").

## Impact

- **Packages (two):** `auto_reel_ng/api` (`routes/jobs.py`, `schemas.py`, `events_read.py`) and `web`
  (`src/api/jobs.ts`, `src/jobs/RenderControl.tsx`, `src/jobs/LiveJobCell.tsx`, `src/jobs/labels.ts`,
  `openapi.json`, `src/api/schema.d.ts`).
- **CLI vs API (Principle V):** the refusal is the API reaching an engine fact (reconcile plus the
  document's `exclude`). `auto-reel render` already reaches the same outcome for the same event, in the
  engine's way: the missing played clip fails the event at probe and is reported failed, never rendered.
  `auto-reel enqueue` still queues such an event. Making it refuse too is a third package (`cli/`) and is
  left to a follow-up (design "Non-goals").
- **Gates:** `api-jobs-create-validation` (`routes/jobs.py` and `events_read.py`) and
  `api-excluded-clips-read-model` (`schemas.py`, `events_read.py`, the web event screens) merge first; this
  change is implemented on top of them (design "Gate").
- **Tests:** `tests/test_api_jobs.py` (requires_db), `tests/test_api_openapi.py`, and a real-browser
  Playwright run for the two screens.

## Non-goals

- **No change to the page's own blocking.** Which missing clips hold the page's Render back
  (`blocking_missing`) is `api-excluded-clips-read-model`'s. This change only makes the server agree with
  it and tells the client when the server disagrees with a stale read.
- **No CLI refusal in `auto-reel enqueue`** (follow-up, third package).
- **No refresh-until-restored.** Screens still do not poll for a clip coming back.
- **No refusal for a clip that is only NEW or IGNORED**, nor for an unreadable or unlistable event: the
  first are not missing, and the second keep the scan-failure 502 that `api-jobs-create-validation` and the
  collision check already give.
- **No probe in the route.** The check reads the folder listing and `reel.yaml`, as the events reads do. A
  clip that exists but cannot be probed still fails the job at probe, loudly.
