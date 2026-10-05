## Why

The user saw "Not analyzed" on the Timeline and asked "What does not analyse mean?", then "Why can i not trigger
that from the web?"; offered automatic analysis with a Re-analyze button, a button only, or both plus "Analyze
all" on the event list, they answered "3 both" (2026-10-05). Today the web can only print a terminal command
(`ANALYZE_COMMAND`, `web/src/timeline/TimelineSection.tsx:190`), it collapses "never analysed", "clip changed
since", "running" and "failed" into one "Not analyzed" note (`timeline/overlays/suggestions.ts:435-470`), the
badge is only visible once proxies exist (the Timeline mounts behind Prepare), and the suggestions are read once
on mount (`timeline/overlays/useAnalysis.ts`), so a finished analysis needs a reload (research
`analysis/findings.md` §2).

The gates give the web what it lacks: `analysis-job` makes analysis a worker job of kind `analysis`, and
`analysis-enqueue-api` adds `POST /api/v1/events/{id}/analysis {force?}`, `POST /api/v1/analysis`, an honest
`state` per event and per clip on `GET …/analysis`, and `analysis` in the published job-kind vocabulary. This
change is the web half (HLD §4.10, D-20 "Analysis overlays"); `analysis-auto-sweep` is the automatic half.

## What Changes

- **One analysis read per event page**, made on opening, on Refresh and when the event's `analysis` job ends
  (live over the existing jobs WebSocket); the header and the Timeline both show it. The Timeline no longer reads
  the analysis itself.
- **A state badge** from the published `state`, in the event page header (read view and Edit mode, so it shows
  before any proxy exists) and in the Timeline's lane: "Not analyzed", "Analysis out of date", "Waiting to
  analyze" / "Analyzing N clips… 42%" (live from the job), "Analysis failed for N clips" (names in the header,
  names and failure text in the Timeline help), nothing when current. Per-clip notes from `clips[].state`.
- **Re-analyze** ("Analyze" when never analysed) in the read view's header actions and beside the Timeline badge
  in Edit mode: `POST …/analysis {force: true}`, no confirmation, unavailable with a reason while analyzing.
- **Analyze all** on the event list header: `POST /api/v1/analysis`, the answer as "Queued 12 events. 1 already
  queued." in a status line.
- **The header counts analysis jobs** as its own "N to analyze" count with its own glyph; render counts unchanged.
- **The terminal command** leaves every visible sentence; the Timeline help keeps it as an aside.
- **Deviation from the plan's wording, flagged:** the plan asked for "Analyzing… 3 of 9 clips". The jobs channel
  carries only a size-weighted progress fraction (`JobOut.progress`, research §3 "Progress"), not a clips-done
  count, and the page must not poll. The badge shows "Analyzing 9 clips… 42%" (N from the read's per-clip
  `analyzing` states, the percentage live). A true "3 of 9" needs a published clips-done field on the job: an
  `api` change, out of this web-only change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: ADDED "The event page shows the event's analysis state", "The operator re-analyzes an event from
  its page", "The event list analyzes every event that needs it"; MODIFIED "The client follows render jobs live
  over one connection" (the header's analysis count).
- `event-timeline`: MODIFIED "The timeline shows the event's analysis suggestions beside its clips" (the page's
  one read instead of the Timeline's own, the published states for the badge and the clip rows, refresh on job
  end, Re-analyze in Edit mode, the help).

## Impact

- **Package (one): `web`.** `web/src/api/analysis.ts` (enqueue calls beside the read), a new
  `web/src/analysis/` (pure state-to-badge model, words, the page-level read hook, the badge and the
  Re-analyze control), `web/src/jobs/kinds.ts` + `useJob.ts` (analysis job selectors, the count),
  `jobs/JobsIndicator.tsx`, `events/EventDetail.tsx`, `events/EventList.tsx`, `edit/EventEditor.tsx` (pass the
  read through), `timeline/TimelineSection.tsx`, `timeline/overlays/` (`suggestions.ts`, `useSuggestions.tsx`;
  `useAnalysis.ts` moves up), `ui/Icon.tsx` (one glyph). HLD §4.10 / §6 / D-20 note.
- **No API, engine, DB, dependency or staleness change**; no `RENDER_GRAPH_VERSION` bump. The schema types come
  from `analysis-enqueue-api`'s regeneration; this change only consumes them.
- **Gates:** `analysis-enqueue-api` (and through it `analysis-job`) merged first; task 1.1 checks the real names.
