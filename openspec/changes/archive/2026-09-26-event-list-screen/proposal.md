## Why

GUI v1 (HLD **§6 phase 8**, §4.10, stack **D-8**) opens on the scan/ingest view, and its first question
is the one legacy auto-reel never answered: **which events need a render, and why?** (HLD §2, problem 8:
the operator tracked it in their head.) Slices 0 and A plus two API contract changes built everything
this screen reads:

- the events list carries each event's staleness verdict (`events-list-staleness`)
- the verdict's reasons are a closed, typed vocabulary (`events-list-client-contract`)
- the latest job's status is typed and the list's failures are published problem shapes
  (`events-list-job-status-contract`, the prerequisite of this change)
- `web/` builds against generated types (`web-app-scaffold`)

`App.tsx` is still the scaffold's wiring check: it shows an event count. This change replaces it with
the first real screen, slice **B** of the §4.10 plan. It is built against the 9-event dev library
(`scripts/make_dev_library.py`), which holds every state the screen must show.

## What Changes

- **The event list screen replaces the wiring check.** It shows every event under the project root,
  grouped by the year of the event's date, newest first, with undated events in their own group. Each
  row shows the date, title (the folder name when untitled), location, clip count, NEW and MISSING
  counts, whether the event needs a render and every reason in words, and the latest job's status.
- **A summary and a filter answer the first question directly.** "N of M events need rendering", and a
  toggle to show only those.
- **Refresh re-reads disk.** The list is scanned per request (D-A3), so a refresh button re-fetches it.
  There is no polling and no client cache. A failed refresh replaces the list with the error, rather
  than presenting the old list as current (Principle I).
- **Failures are reported by cause.** Using the published problem shape, the screen says "the service
  can't reach its database" (503, `check: database`), "an event could not be scanned" with the event
  named (502), or "the service is not reachable" (no response).
- **Labels are exhaustive over the generated vocabularies.** Staleness reasons and job statuses map to
  words through maps typed over the generated unions. A new or renamed reason or status is a
  `tsc --noEmit` error, not a raw slug on screen.

## Non-goals

- **No event detail, no clicking a row.** Slice C. Rows are read-only text.
- **No writes of any kind.** No render button, no enqueue, no editorial save. Slices D and E.
- **No live job progress.** The latest job is shown as of the last fetch. The WebSocket hook is slice E.
- **No collision flag.** The API does not report output-path collisions yet
  (`output-path-year-folder`, Non-goals). Colliding events show as ordinary rows until the API change
  that precedes slice E.
- **No new dependency.** It uses React, the generated types, `fetch` and one plain CSS file. There is no
  router, state library, data-fetching library, component library or CSS framework (the `web-app`
  dependency budget, D-8).
- **No test runner.** `tsc --noEmit` stays the frontend gate (`web-app` spec). The grouping and sorting
  are small, typed pure functions. A later slice with logic that needs unit tests proposes a runner with
  its justification.
- **No backend change.** Every field and problem shape it reads is published by
  `events-list-job-status-contract`, which MUST be applied first.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: new requirements for the event list screen:
  - what it shows and how it orders it
  - that it answers "what needs rendering" and refreshes from disk
  - that it reports failures by cause
  - that its labels are exhaustive over the generated vocabularies

## Impact

- **Packages:** `web/` only.
  - `src/App.tsx` is replaced.
  - New modules: the events fetch, the label maps, grouping/sorting, the screen component, and one CSS
    file.
  - `web/README.md` no longer says there is no screen.
- **CLI vs API (Principle V):** neither is touched. The screen shows what `auto-reel scan` already
  prints: events, clip classification counts and staleness with reasons.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** The fingerprint inputs are
  unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan, and no API
  schema change.
- **Dependencies (Principle VII):** none added.
- **Size (Principle VIII):** one screen, read-only, in one package.
