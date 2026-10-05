## Context

See proposal.md "Why". Current web state (research `analysis/findings.md` §2, paths under `web/src/`):

- `api/analysis.ts fetchAnalysis` is the only analysis call (GET, `cache: 'no-store'`, 404/502 problems).
- `timeline/overlays/useAnalysis.ts` reads once when the Timeline's track mounts; `useSuggestions.tsx:401` turns
  it into the lane's badge via `suggestions.ts eventNote()` / `clipNotAnalyzed()`, which distrust `analyzed` and
  guess from which clips have segments. `TimelineSection.tsx:190` prints `ANALYZE_COMMAND` in the help.
- The Timeline is mounted only in Edit mode (`overlays/control.ts` header comment; `edit/EventEditor.tsx:2722`)
  and only shows its track once every clip's proxy is ready (`timeline/Prepare.tsx`).
- The jobs store holds every kind the socket carries (`jobs/store.ts`); `jobs/kinds.ts` has `isRender`/`isProxy`
  and per-event "newest" selectors; `useJob.ts useProxyJob` is the precedent for a non-render job hook (live only,
  no read fallback); `JobsIndicator.tsx` counts renders only (`countRenders`).
- `api/proxies.ts enqueueProxies` is the precedent for an enqueue call: one result kind per published answer,
  503 is `database` only when the problem names the database, never abortable.

What the gate `analysis-enqueue-api` publishes (from its plan entry and its draft design, D2–D4; task 1.1
confirms against the merged code before anything else):

| Needed | Expected | If different |
|---|---|---|
| `POST /api/v1/events/{id}/analysis`, body `{force?: bool}` | 201 `JobOut` (kind `analysis`); 200 `AnalysisFreshResult`; 409 `active_job` with the job id; 404/502/503 | map each published answer to one result kind, as `enqueueProxies` does; the plan's "202" became 201 in the gate's design |
| `POST /api/v1/analysis` | 200 `AnalyzeAllResult{queued, fresh, active, unreadable[]}`; 502; 503 | the list line uses the published counts by name |
| `AnalysisOut.state`, `clips{identity: {state, detail}}`, `job: JobOut \| null` | closed `AnalysisState` `never \| stale \| current \| analyzing \| failed`; GET also declares 503 | the words mapping is keyed by the generated union, so a rename fails `tsc` |
| `JobKind` includes `analysis` in `JobOut` and every WS frame | yes | `isAnalysis` follows the generated value |

**Confirmed against `origin/main` (task 1.1, `web/src/api/schema.d.ts` and `auto_reel_ng/api/schemas.py` after
`36624908`):** every row holds as written. Real names: `AnalysisEnqueueRequest{force: boolean = false}` (body
optional); 201 `JobOut`; 200 `AnalysisFreshResult{event_id, status: "fresh", clip_count, failed_count}`; 409
`ProblemOut` with `conflict: "active_job"`, `job_id` and **`forced`** (new to this table: `false` when a forced
request met a `running` unforced job, which keeps running unforced — "ask again once it ends"); 404 / 502 / 503
`ProblemOut` (503 with `check: "database"`). `POST /api/v1/analysis` → 200
`AnalyzeAllResult{queued, fresh, active, unreadable: AnalyzeAllUnreadable{event_id, detail, failure?}[]}`, 502, 503.
`AnalysisOut{analyzed (legacy), segments, state: AnalysisState, clips: {[identity]: ClipAnalysisOut{state,
detail?}}, job?: JobOut | null}`; `AnalysisState = "never" | "stale" | "current" | "analyzing" | "failed"`;
`JobKind = "render" | "proxy" | "analysis"`. `fetchAnalysis` already accepted the 503 (the gate's own change).
The one adaptation: an `active` answer with `forced: false` to a Re-analyze says the running analysis is not a
re-analysis ("Re-analyze again once it ends"), in the status region, not as a failure.

## Goals / Non-Goals

**Goals:** honest badge everywhere it appears, Re-analyze, Analyze all, the header count, suggestions that follow
a finished job without a reload.

**Non-Goals:** a Jobs page; an analysis pill per event-list row (the gate publishes no state on the list, and
reading every event's sidecar for the list has no consumer yet — Principle VII); cancelling an analysis job from
the web (the generic `POST /jobs/{id}/cancel` exists, but nobody asked; a running analysis yields to renders);
"3 of 9 clips" (proposal: needs an `api` field).

## Decisions

### D1. One analysis read per event page, lifted out of the Timeline

`useEventAnalysis(eventId)` (new, `web/src/analysis/useEventAnalysis.ts`, grown from `useAnalysis.ts`) lives in
`EventDetailBody` and is passed down to the header badge, the read view's Re-analyze, and through `EventEditor` →
`TimelineSection` → `AnalysisControl` to the lane. It reads on mount and on `reload()` (Refresh calls it), keeps
the old answer shown while a re-read runs (`{status: 'ok', analysis, rereading: true}`), and aborts on unmount.

*Why one read, not two:* the header and the lane must never disagree, and the header needs the state before any
proxy exists. *Cost:* one extra cheap GET per page open for pages whose Timeline is never opened — the GET is
stat + small JSON per clip (gate D1), no probe. *Alternative:* keep the Timeline's own read and add a second in
the header — rejected: two answers at different times give two badges that disagree after a job ends.

### D2. The badge is a pure function of (read, live job)

`analysis/badge.ts` (pure, `node:test`): `badgeOf(read, liveJob, connectionLive) → {state, words, glyph, tone,
progress?, failedNames?} | null`. Rules, first that holds:

1. a live job of the event (queued/running) while the connection is live → analyzing (queued: indeterminate,
   "Waiting to analyze"; running: "Analyzing N clips…" + `floor(min(progress, .99) * 100)`%, N = clips whose read
   state is `analyzing`, "Analyzing…" when 0);
2. a failed read → "Analysis state unknown";
3. the read's `state` via `ANALYSIS_STATE_WORDS: Record<AnalysisState, …>` (exhaustive; an unknown runtime value
   → "Analysis state unknown"); `current` → null.

`clipNoteOf(read, identity)` replaces `clipNotAnalyzed()` from `clips[identity].state`. `eventNote()`'s "nothing
found" stays, now gated on `state === 'current'`. The 99% hold copies the render bar's rule (spec "A render's
progress is shown live").

### D3. Refetch on job end follows the store, the way `useEventJob` reconciles

`useAnalysisJob(eventId)` (in `jobs/useJob.ts`, like `useProxyJob`) returns the newest `analysis` job the store
holds for the event. `useEventAnalysis` watches it: on an observed transition active → ended it calls `reload()`
once and asks the page's status region to announce ("Analysis finished." or "Analysis failed for N clips." from
the new read); a reconciled end (the store's `load(…, {knownActive})` after a reconnect) reloads without the
announcement. When the read says `analyzing` but the live connection holds no active analysis job for the event,
it reloads once per read (a guard flag, so a stale service answer cannot loop). No timer, no polling (spec "one
connection").

*Alternative:* re-read on every delta frame — rejected, one GET per progress tick.

### D4. Enqueue calls mirror `enqueueProxies`

`api/analysis.ts` gains `enqueueAnalysis(eventId, {force})` and `analyzeAll()`, each returning one result kind
per published answer (`enqueued | fresh | active | problem | database | unreachable | unpublished`; for all:
`counted | database | problem | unreachable | unpublished`). Writes are not abortable. On `enqueued` and
`active`, the job is put into the store (`load(jobId, {knownActive: true})` for `active`; the 201 body for
`enqueued`), so the badge shows it before the next socket frame. Unit tests with a stubbed `fetch` per status, as
`proxies.test.ts` does.

### D5. Where the controls go

- Read view: Re-analyze is a third `page-actions` button after Refresh and Edit (secondary style, `scan` glyph);
  the badge goes on the `page-meta` facts line. Edit mode: the header badge stays; Re-analyze sits in the
  Timeline's suggestion strip (`sg-strip`) beside the lane's badge. With no proxies in Edit mode the Timeline is in
  Prepare and offers no Re-analyze; the header badge still shows the state (Stop editing to re-analyze).
- Event list: Analyze all between the Needs render filter and Refresh; its result line in `page-meta` and its
  polite status region beside the list's existing one.
- `aria-disabled` + `aria-describedby` reason while analyzing, busy while in flight (the project's pattern: focus
  is kept, `Refresh` does the same).

### D6. The header's analysis count

`countAnalysis(jobs)` in `jobs/kinds.ts` counts events with a queued or running `analysis` job (the store may
hold several ended rows per event; only active ones count; one active per event is the service's invariant).
`JobsIndicator` renders it after the render counts as its own `Count` with a new `scan` glyph and the words "to
analyze". One number, not "analyzing"/"queued" pairs, because at 390 px only glyph + number show and two analysis
numbers with one glyph would be ambiguous; with the worker's `analysis_slots=1` the running count is 0 or 1 and
says little. The visually hidden prefix "Render jobs:" becomes "Jobs:".

## Risks / Trade-offs

- [Gate names differ from its draft] → task 1.1 reads the merged schema first and records the real names here
  before any code; the badge mapping is keyed by the generated union so `tsc` finds every miss.
- [Analyze all on the 13-year archive queues hundreds of jobs] → each is one row at the lowest claim rank behind
  renders and proxies (gate `analysis-job`); the header count makes the backlog visible; no confirmation by the
  user's choice of an explicit button. Cancelling the backlog is not offered (non-goal), noted for the user.
- [An extra GET on every event page open] → cheap read (stat + JSON); aborted on leave; no poll.
- [The lane refreshes under a pressed mark or open detail] → keep the selected mark by its dismissal key
  (`dismissalKey`, clip + span + kind); when the new read lacks it, the detail closes and focus moves to the lane
  group. Tested in `suggestions.test.ts`.
- [Dismissals keyed by span] → a re-analysis that finds the same span keeps it dismissed for the visit; one with a
  different span shows it pending: the honest outcome, stated in the help.

## Migration Plan

Web-only, additive; reverting the change restores the Timeline's own read and the terminal-command note. The gate
must be merged first (types).

## Research & Decisions

- **Why the badge must leave `analyzed`**: `findings.md` §2 (`analyzed` true whenever `.auto-reel/cache` exists;
  three states collapse). → D2 reads the published state only.
- **Why the header, not only the Timeline**: §2 "Timeline only mounts when proxies are ready … the badge is only
  visible after proxies exist". → D1, D5.
- **Why refetch on job end**: §2 "`useAnalysis.ts` reads ONCE"; §3 WS hub carries every kind with `kind` on each
  frame. → D3.
- **No Jobs page exists**: §2 "only the header `jobs/JobsIndicator.tsx` (counts renders only)". → D6, the count
  in the header is the whole "Jobs" surface.
- **Progress is size-weighted** (§3 "Progress: … Weighted by size in proxy job"; gate `analysis-job` copies it) →
  no clips-done count on the wire → proposal's flagged deviation.
