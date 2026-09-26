## Context

See proposal.md — Why. The state `web/` starts from:

- `src/App.tsx` is the scaffold's wiring check. It fetches `GET /api/v1/events`, types the response
  through `paths['/api/v1/events']['get']['responses'][200]`, and renders a count.
- `src/api/schema.d.ts` is generated. Once `events-list-job-status-contract` is applied it types:
  - `StalenessOut.reasons` as a union of the six reasons
  - `JobSummaryOut.status` as the `JobStatus` union
  - the list's 502 and 503 responses as `ProblemOut` (`title`, `status`, `detail`, optional `check` and
    `event_id`)
- The dependency budget (D-8, `web-app` spec) allows React, `fetch`, and CSS that Vite imports natively.
  Nothing else.
- The dev library (`scripts/make_dev_library.py`) serves 9 events: 3 fresh; 6 stale with reasons
  `editorial`+`output`, `clip_set`, and `no_manifest` (×4); one NEW clip in each of three events; one
  MISSING clip; one undated event; latest jobs `done` ×5, `failed`, `queued`, none ×2.

## Goals / Non-Goals

**Goals:**

- One screen that answers "what needs rendering, and why" for a library of hundreds of events.
- Every fact on screen traceable to a field of the response. The only derived facts are grouping,
  ordering and counts.
- The vocabularies' words defined once, with the compiler enforcing completeness.

**Non-Goals:**

- Navigation, selection, or any interactive row (slice C).
- Live progress (slice E) and any write (slices D and E).
- Visual polish beyond readable, theme-aware plain CSS. A look and feel pass belongs with the v2 look
  editor.

## Research & Decisions

### Module layout

**Context**: The budget forbids a state or data-fetching library, so the fetch, the view state and the
derivations are hand-written. They should stay small and separately readable.

**Decision**: Five files under `web/src/`:

| File | Holds |
|---|---|
| `api/events.ts` | `fetchEvents(signal): Promise<EventsResult>`, the typed fetch and problem parsing |
| `events/labels.ts` | `REASON_LABEL`, `JOB_STATUS_LABEL`: exhaustive maps over the generated unions |
| `events/grouping.ts` | `groupByYear(events)`, `needsRender(event)`: pure and typed |
| `events/EventList.tsx` | the screen: load/refresh state, summary, filter, groups, rows |
| `app.css` | layout and light/dark theme tokens |

`App.tsx` becomes `<EventList />`. Type aliases for the response pieces (`EventSummary`, `Staleness`,
`JobSummary`, `Problem`) are derived in `api/events.ts` from `components['schemas'][...]`. They are
aliases, never re-declared shapes.

**Rationale**: Each file has one reason to change. The fetch module is the only place that knows URLs
and status codes, so slice C adds `fetchEvent` beside it.

### How a failed read becomes a cause

**Context**: The spec requires distinguishing a database failure, a scan failure (with its event), and no
answer at all, taken from the problem body rather than its prose.

**Decision**: `fetchEvents` returns a discriminated union and never throws for an expected failure:

```ts
export type EventsResult =
  | { kind: 'ok'; events: EventSummary[] }
  | { kind: 'problem'; problem: Problem }      // 502/503 from the published ProblemOut shape
  | { kind: 'unreachable'; message: string }   // fetch rejected, or a non-JSON / undeclared status
```

The screen then maps `problem.check === 'database'` → "The service can't reach its database", and
`problem.event_id` → "Event <id> could not be scanned". Any other problem shows its `title` and `detail`.
An abort (unmount or superseding refresh) is not a failure: `fetchEvents` rethrows `AbortError`, and the
screen ignores it.

**Rationale**:
- A union makes every caller handle all three outcomes, which `tsc` checks.
- Relying on `check` and `event_id` rather than status codes alone matches how
  `events-list-client-contract` defined the contract ("one predicate for the database across `/healthz`
  and both reads").
- A response with an undeclared status (a bare 500) is reported as "unreachable" with its status. That
  is honest: it carries no published shape to read a cause from.

### Grouping and ordering

**Context**: Group by the event date's year, or by the layout's year folder?

**Decision**: By `date` year, the same year D-9 uses for the output folder. Events without a date go in
a trailing "No date" group, ordered by `event_id`. Within a dated group, order by `date` descending, then
`event_id` ascending.

**Rationale**:
- The `flat` layout has no year folder, and `event_id` is layout-specific. The date is the one year
  every layout has when it has one.
- Matching D-9 means a movie on disk and its row sit under the same year.
- Newest first because the operator's current work is the most recent footage.

### Load, refresh and the filter

**Decision**: `EventList` holds the load state as a union: `loading`, `ready` with events and fetch
time, or `failed` with the result. The filter is a separate `useState<boolean>`.
- Load happens once on mount.
- **Refresh** aborts any in-flight request (`AbortController`), sets `loading`, then refetches. Loading
  replaces the previous list, so an in-flight or failed refresh never shows an old list as current.
- The summary counts stale events over the **whole** list, not the filtered view. The filter changes
  only which rows show.
- No polling, no cache, no `localStorage`.

**Rationale**: This is the spec's "never present an earlier list as current" requirement in its
simplest form. Keeping the old list visible and dimmed while loading is friendlier, but it is a second
state to get right, and nothing in v1 needs it.

### Label maps

**Decision**:

```ts
export const REASON_LABEL: Record<StalenessReason, string> = {
  no_manifest: 'never rendered',
  output: 'movie file missing',
  editorial: 'edited since last render',
  defaults: 'project defaults changed',
  clip_set: 'clips changed',
  engine: 'render engine updated',
}
export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  queued: 'Queued', running: 'Rendering', done: 'Rendered', failed: 'Failed', canceled: 'Canceled',
}
```

A `Record` over the union fails `tsc` when the union gains a member (missing key) or loses one (excess
key). This is the spec's exhaustiveness, with no runner needed.

### Rendering the rows

**Decision**:
- One `<table>` per year group, with a `<caption>` for the year. Columns: Date, Event (title with the
  location muted beside it), Clips (count, plus "N new" and "N missing" badges), Render (the "Up to
  date" or "Needs render" pill, followed by the reasons joined with commas), Last job (status label and
  local date-time of `created_at`; `running` adds its progress percent).
- State is always conveyed by text, never by colour alone.
- The date renders as the ISO `YYYY-MM-DD` string the API sends. There is no locale formatting of a
  calendar date, which would risk an off-by-one-day timezone shift.

**Rationale**: A semantic table is accessible without ARIA work, stays readable at hundreds of rows
without virtualization, and needs no component library.

### Theme

**Decision**: CSS custom properties on `:root` for colours, redefined under
`@media (prefers-color-scheme: dark)`. `system-ui` fonts. No web font, no CSS framework.

## Failure behavior and idempotency

- Nothing on this screen writes. A load, a refresh, a failed read, or unmounting mid-request has no
  side effect anywhere.
- A failed read shows its cause and hides the list. It never shows a partial or earlier one.
- A re-run (refresh) re-reads disk, and it is the only way the screen learns of changes.
- No rendered output, fingerprint input, or API schema changes, so there is **no
  `RENDER_GRAPH_VERSION` bump** and no migration.

## Risks / Trade-offs

- **[A library of thousands of events]** One request scans every event (probe-free, D-A3), and a table
  of thousands of rows is slow to paint. → The dev library is 9 events. The real library is likely in
  the hundreds, which is fine for plain rows. `list_events` already logs its scan time. Measure against
  the real library before adding pagination or virtualization.
- **[Refresh hides the list while loading]** There's a flash on every refresh. → This is accepted for
  v1 (see "Load, refresh and the filter").
- **[Colliding events look ordinary]** Two events sharing an output path both show as normal rows. →
  This is a documented non-goal until the API exposes collisions (before slice E).
- **[No automated UI test]** A regression in grouping or sorting would only show on screen. → `tsc`
  covers every shape and vocabulary. The pure functions are small, and the manual checklist in tasks.md
  exercises each dev-library state. A runner is proposed when a slice's logic outgrows this.

## Migration Plan

Deploy is building `web/dist` (the container command in `web/README.md`). `auto-reel serve` mounts it
when present. Rollback means restoring the wiring-check `App.tsx`. No data, schema or config migrates.
