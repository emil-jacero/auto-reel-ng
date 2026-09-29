## Context

See proposal.md — Why. The state `web/` starts from:

- **`src/App.tsx`** renders `<EventList />` only. There is no routing of any kind, and the budget forbids a
  router library (D-8, `web-app`: dependency budget).
- **`src/events/EventList.tsx`** (291 lines):
  - owns the list's load state (mount + refresh, with abort), the needs-render filter (`useState`), and the
    "Needs attention" table
  - holds private helpers the event page also needs: `JobCell`, `folderName` and `plural`
  - renders a `<main>`
- **`src/api/events.ts`** holds `fetchEvents` and the list's type aliases, plus two module-private helpers
  (`readJson`, `isProblem`). The detail read needs them too.
- **Generated types** (`src/api/schema.d.ts`):
  - `EventDetailOut`: `event_id`, `title`/`date`/`location`/`description` (nullable), `chapters: ChapterOut[]`,
    `missing: string[]`, `latest_job`, `staleness`
  - `ChapterOut`: `name` (`""` is the default chapter), `clips: ClipOut[]`
  - `ClipOut`: `identity` (event-relative, for example `Kvällen/00401.mp4`), `status: ClipStatus`,
    `size`/`mtime` (nullable)
  - `ProblemOut`: `title`, `status`, `detail`, and optional `check`, `event_id` and `failure`
  - the detail route declares 404, 502 and 503
- **The service** routes `GET /api/v1/events/{event_id:path}`. Event IDs contain `/` (the year folder),
  spaces, commas, `&` and Swedish letters.
- **The dev library** (`scripts/make_dev_library.py`) has no chapter subfolder and no IGNORED clip.

## Goals / Non-Goals

**Goals:**

- A read-only event page reached from the list, with real browser history.
- Returning to the list is instant: no re-scan, with the same filter and scroll.
- Every clip status and failure is put in words through exhaustive maps.

**Non-Goals:**

- Editing (slice D), rendering (slice E), media facts, and look or output information (proposal:
  Non-goals).

## Research & Decisions

### Routing without a router

**Decision**: A new `src/route.ts`:

```ts
export type Route = { page: 'list' } | { page: 'event'; eventId: string }

/** '#/event/<id segments, each encodeURIComponent'd>' -> event; anything else -> list. */
export function parseRoute(hash: string): Route
/** The href for an event page; '/' separators kept, every segment encoded. */
export function eventHref(eventId: string): string
/** The current route, updated on 'hashchange'. */
export function useRoute(): Route
```

- IDs are encoded **per segment** with `encodeURIComponent`. `/` stays a separator, and spaces, `,`, `&`,
  `#`, `?`, `%` and non-ASCII letters are escaped.
- Parsing splits on `/` and decodes each segment. A `URIError` from a malformed escape yields the list route.
- The same segment encoding builds the API path: `'/api/v1/events/' + segments`.

**Rationale**:
- A hash route needs no server configuration: `serve`'s static mount and Vite serve `index.html` for `/`.
- It gives Back, Forward, reload and bookmarks for free, and adds no dependency.
- Per-segment encoding keeps addresses readable (`#/event/2024/2024-06-21%20-%20Midsommar`), and matches how
  the service's `{event_id:path}` route decodes.

**Alternative rejected**: the History API (`pushState` with path URLs). It would need the service to answer
every client path with `index.html`, a server change, for no gain in v1.

### Keeping the list alive

**Decision**:
- `App` mounts `EventList` the first time the route is the list, then keeps it mounted, passing
  `hidden={route.page !== 'list'}` to its `<main>`.
- `EventDetail` mounts per event (`key={eventId}`), only while the route is an event page.
- On leaving the list, `App` saves `window.scrollY`. On returning, a `useLayoutEffect` restores it once the
  list is visible. Opening an event page scrolls to the top.
- `history.scrollRestoration = 'manual'`, so the browser's own restore doesn't race the re-render.

**Rationale**:
- Keeping the component mounted keeps its load state and filter as they were, which is the spec's "no new
  list request" and "same filter".
- A deep link straight to an event page never scans the whole library, because the list mounts only when
  first shown.
- Only one `<main>` is visible at a time, which HTML requires, via the `hidden` attribute.

### Reading one event

**Decision**:
- A new `src/api/event.ts` exports the type aliases `EventDetail`, `Chapter`, `Clip` and `ClipStatus`, plus
  `fetchEvent(eventId, signal)`.
- `fetchEvent` returns `{kind:'ok', event} | {kind:'problem', problem} | {kind:'unreachable', message}`.
  404, 502 and 503 are problem statuses, matching the declared responses.
- `readJson` and `isProblem` move from `src/api/events.ts` into a shared `src/api/http.ts`, used by both
  reads.

The page describes a problem as follows:
- `404`: "No event … under the project root", with a link to the list.
- `502` with `failure`: `FAILURE_LABEL[failure]` plus `detail`, the same words as the list's row.
- `502` without `failure`: "This event could not be read", plus `detail`.
- `503` with `check === 'database'`: the list's database sentence.
- Unreachable: the list's unreachable sentence.

### The page

**Decision**: `src/events/EventDetail.tsx` holds the same load, refresh and abort pattern as the list (a
`LoadState` union, where a failed or loading read replaces the content). It renders:

- a header: a link back to the list, the title or folder name, "date · location", the description, and a
  Refresh button
- a status line: the "Up to date" or "Needs render" pill with `REASON_LABEL` words, and `JobCell`
- counts: `N clips · <total size> · k new · m missing · i ignored`, with zero counts omitted. The total sums
  known sizes only.
- a warning when `missing` is non-empty: "reel.yaml lists clips that are not on disk: a.mp4, b.mp4"
- per chapter, a `<table>` with `<caption>`:
  - the caption is the chapter name, or `Main` for `""` when named chapters exist
  - there is no caption when `""` is the only chapter
  - columns: `#` (1-based), **File** (the identity's last segment), **Status** (`CLIP_STATUS_LABEL`),
    **Size** (`formatBytes`, or `—` when null), **Modified** (`toLocaleString()`, or `—` when null)

`document.title` becomes `<title> — auto-reel` on the page and `Events — auto-reel` on the list.

Shared helpers move to `src/events/common.tsx`: `JobCell`, `folderName`, `plural`, and a new
`formatBytes(n)` (1024-based: B, KiB, MiB, GiB, TiB, with one decimal at or above KiB).

**Rationale**:
- The page shows only what the response carries. Null sizes and times render as absent (Principle I, as
  the spec states).
- A plain table per chapter handles a 380-clip chapter without virtualization.

### Labels

**Decision**: `labels.ts` gains `CLIP_STATUS_LABEL: Record<ClipStatus, string>`:
- `new`: "New, not yet in reel.yaml"
- `active`: "Included"
- `missing`: "Missing from disk"
- `ignored`: "Ignored"

**Rationale**: A `Record` over the generated union fails `tsc` on any added, removed or renamed status, as
the existing maps do.

### The dev library event

**Decision**: `scripts/make_dev_library.py` adds `2024/2024-08-20 - Två kapitel - Tjörn`.

- **Phase 1**, rendered through the queue: `s1710001.mp4` at the root, plus `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`. The worker seeds the chapters `""` and `Kvällen`, and persists them.
- **Phase 2**:
  - link `s1710004.mp4` at the root, and add `ignore: [s1710004.mp4]` to its `reel.yaml` (round-trip edit),
    making it IGNORED
  - link `Kvällen/s1710004.mp4`, making it NEW in a named chapter
  - the event is then stale (`clip_set`)

The library becomes 11 events: 10 listed, plus 1 needing attention, with **7 of 10** needing a render.

**Rationale**: It covers the only states the page shows that the library lacks (a named chapter, IGNORED, and
NEW inside a chapter), with real footage.

## Failure behavior and idempotency

- **The page never writes.** Every request is a GET.
- **A failed read or refresh** replaces the content with its cause.
- **Navigating away** aborts an in-flight read, as the list does.
- **Reopening a page** re-reads the event, and Refresh re-reads it too.
- **The list is read once**, when first shown, and then only on Refresh.
- **No `RENDER_GRAPH_VERSION` bump**, and no API or schema change.

## Risks / Trade-offs

- **[The list is not re-read after returning]** Disk changes made elsewhere while an event page was open show
  only after Refresh. → The spec states this, and the list's existing Refresh covers it. Slice D, which
  writes, will re-read after a save.
- **[A hidden list stays in memory]** It is a few hundred rows. → That's negligible.
- **[Encoded addresses look noisy]** (`%20`, `%C3%A5`) → They are correct and round-trip. The page title
  shows the readable name.
- **[No automated test of `parseRoute`/`formatBytes`]** `tsc` is the frontend gate (`web-app`: no runner in
  v1). → The helpers are tiny. The manual checklist exercises spaces, `/`, `å`, a malformed escape, and null
  sizes.

## Migration Plan

Rebuild `web/dist` (the `web/README.md` container command). `serve` mounts it as before. Rebuild the dev
library to get the new event. Rollback means restoring `App.tsx` to render only the list.
