## Why

The user saw "Not analyzed" on the Timeline and asked "What does not analyse mean?" and then "Why can i not trigger
that from the web?" (2026-10-05); offered automatic analysis, a button, or both plus "Analyze all", they answered
"3 both". Today black/white/freeze analysis (HLD §4.5) runs only as `auto-reel analyze` in a terminal, and the
one read the web has, `GET /api/v1/events/{id}/analysis`, cannot say what the state is: its `analyzed` flag is true
whenever `.auto-reel/cache/` exists, and that folder also exists when a render wrote its manifest, so the web
distrusts it and collapses "never analyzed", "clip changed since", "analysis running" and "analysis failed" into
one "Not analyzed" note (research `analysis/findings.md` §2: `api/events_read.py:757`, `schemas.py:582`,
`web/src/timeline/overlays/suggestions.ts:435-470`).

The gate `analysis-job` makes analysis a job of kind `analysis` that the worker runs (cancellable, per-clip
failure markers, atomic sidecar writes, `auto-reel analyze <root> --enqueue [--force]`). HLD §4.8 already says
"Renders and analysis are jobs", and §4.9 lets the API own the job lifecycle of work the CLI can reach (Principle
V). Nothing yet lets a client enqueue that job, follow it, or read an honest state. This change is that API half,
in GUI v2 (HLD §6 phase 9, §4.10, D-20 "Analysis overlays"); `analysis-web-controls` builds the buttons on it and
`analysis-auto-sweep` the automatic part.

## What Changes

- **`POST /api/v1/events/{event_id}/analysis`**, optional body `{force?: bool}`, enqueues the event's analysis
  job with the enqueue semantics the render and proxy enqueues share: **201** with the `kind: analysis` job;
  **200 "fresh"** (`clip_count`, `failed_count`) when no clip needs analysis and `force` is false; **409
  `active_job`** with the job's id while one is queued or running (found before or at insertion; a forced request
  first gives a `queued` unforced job `force`, as `analyze --enqueue --force` does); 404 / 502 / 503
  as the proxy enqueue answers them. `force: true` is **Re-analyze**: it always enqueues (unless one is active),
  and the forced job ignores cache entries and failure markers (the gate's `jobs.force` handling).
- **`POST /api/v1/analysis`** is **Analyze all**: one request that enqueues every event the events list shows
  whose analysis is `never` or `stale`, skipping events with an active analysis job, and answers 200 with counts
  (`queued`, `fresh`, `active`) and the events it could not read. No body, no force.
- **An honest analysis state.** `AnalysisOut` gains, additively, `state` for the event and `clips` with a
  `state` per clip, from the closed published vocabulary `never | stale | current | analyzing | failed`, plus
  `job` (the active analysis job, with its `progress`) while analyzing. The state is read by `stat` and JSON only
  (no probe, no decode), from the clip's signal, the sidecar entry, the gate's failure marker and the active job.
  `analyzed` stays with its current value and is documented as legacy.
- **One selection rule, one enqueue.** Which clips (and so which events) need analysis is decided by one engine
  function in `analysis/` that both endpoints and later the auto-sweep use; both endpoints enqueue through the
  gate's `submit_analysis`, the function `auto-reel analyze --enqueue` calls (which keeps queuing every selected
  event, as the gate specified; a job over a fresh event analyzes nothing).
- **The job kind vocabulary publishes `analysis`** (`render | proxy | analysis`) in `JobOut`, the jobs list and
  every WebSocket frame, so a client can count analysis jobs; `latest_job` stays the latest render.
- `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated; the web compiles, its tests pass, and its
  screens are unchanged (no button here).
- **No change to rendered output** (no `RENDER_GRAPH_VERSION` bump), no staleness fingerprint input, no
  `reel.yaml` or `config.yaml` schema change, no Alembic migration (`jobs.kind` is free text and `jobs.force`
  exists), no rescan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: MODIFIED "Analysis results are exposed read-only" (state, per-clip states, the active job, a
  declared 503) and "Job kind is a closed, published vocabulary" (adds `analysis`); ADDED "An event's analysis is
  enqueued by a job the service enqueues", "Every event that needs analysis is enqueued in one request", "Analysis
  state is a closed, published vocabulary", and "An analysis job and the jobs of other kinds of one event do not
  block each other".
- `analysis-cache`: ADDED "A clip's analysis state is read from the disk without decoding" (the per-clip and
  per-event rule, and that the CLI's `--enqueue` and the service select with it). The gate's MODIFIED "explicit
  pass" requirement is not touched here.

## Impact

- **Packages (two):** `auto_reel_ng/api` (`routes/events.py`, a new `api/analysis_read.py` beside
  `proxy_read.py` because `events_read.py` sits at pylint's module-size limit, `schemas.py`, `serialize.py`, the
  generated `web/openapi.json` and `web/src/api/schema.d.ts`) and `auto_reel_ng/analysis` (the state function,
  `analysis/state.py`, over a new `inspect_entry` in `analysis/cache.py` that keeps the sidecar format private),
  plus a typed `AnalysisStateError` in `errors.py`. No `cli/` change. `web/src/jobs/kinds.test.ts` gains a guard
  test only, and `web/src/api/analysis.ts` adds the read's new 503 to the problem statuses it mirrors (a contract
  mirror, not a screen change).
- **CLI vs API (Principle V):** the work is the gate's (`auto-reel analyze`, the `analysis` job); the endpoints
  are job lifecycle; they enqueue through the engine function the CLI's `--enqueue` uses (`submit_analysis`), and
  the selection is an engine function in `analysis/`, not code in `api/` (design D6).
- **Gate:** `analysis-job` merged first (JobKind `analysis`, the handler, failure markers, `--enqueue`,
  `submit_analysis`); task 1.1 checked its real names (design "Gate").
- **Evidence:** research `analysis/findings.md` §2 (read path and the misleading flag), §3 (free-text kind, the
  generic one-active index, `submit`/`active_job`), §5 Q6/Q7 (endpoints and states), A2 split.

## Non-goals

- **No web controls.** The badge, Re-analyze and Analyze all buttons, the header count of analysis jobs and the
  refetch on job end are `analysis-web-controls`.
- **No automatic analysis.** The worker's sweep is `analysis-auto-sweep`; it will reuse the selection here.
- **No analysis state on the events list rows or the event detail.** The web shows the badge on the event page,
  which reads `GET …/analysis`; adding a whole-library sidecar read to the list has no consumer yet (Principle VII).
- **No force on Analyze all**, and no per-sweep cap there: it is an explicit user action, each event one row at the
  lowest claim rank (the gate's claim order keeps renders and proxies first).
- **No change to the analysis work** (filters, thresholds, progress, cancel, markers): all the gate's.
