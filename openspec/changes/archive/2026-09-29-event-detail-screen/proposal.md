## Why

GUI v1 (HLD **§6 phase 8**, §4.10, stack **D-8**) is four features. Slice B, the event list, answers "which
events need a render, and why". Slice **C** answers the next question: **what is in this event?** It covers
the chapters and clips, in the order they will play, and which clips are new, missing or ignored. Legacy
auto-reel gave no view of this at all: the operator opened the folder and read `reel.yaml` by hand (HLD §2,
problem 8).

The API side is complete. The last two gaps closed in `event-detail-client-contract`:

- `GET /api/v1/events/{event_id}` returns chapters and clips in play order, with NEW clips placed as adoption
  would place them, IGNORED clips flagged, and the MISSING list
- each clip carries its size and mtime, with a typed `ClipStatus`
- the response carries the staleness verdict and the latest job
- a per-event failure has the same `failure` kind the list's error row carries

This change is therefore a pure `web/` change, per the precedent that screens do not carry backend edits
(Principle VIII). The real archive shaped its scope (read-only survey, 2026-09-26):

- a typical event has 14 clips, and a renderable one at most about 380 (`2020-02-23 - Spanien`)
- 21 events use chapter subfolders, some per-day
- folder names run to 76 characters

The list screen links to nothing today. This change makes each event row open the event's page.

## What Changes

- **Each event opens on its own page.** An event row's title links to `#/event/<event id>`. A hand-written
  hash route, with no router dependency (D-8 budget), shows the event page. Back and Forward work, and a
  reload or a bookmark reopens the same event. Returning to the list keeps its filter and scroll position
  and does not re-scan the library.
- **The event page shows the event's structure, read-only:**
  - the title (or the folder name), date, location and description
  - "Up to date" or "Needs render" with the reasons in words
  - the latest job
  - counts: clips, total size, and new, missing and ignored clips
  - one table per chapter, in document order, listing clips in play order: position, file name, status in
    words, size and modification time
  - a warning naming any clip `reel.yaml` lists that is missing from disk
  - a Refresh button
- **The event page reports failures by cause:**
  - an unknown event (a stale link) says so, with a way back to the list
  - an event that cannot be read shows the same failure words and detail the list's "Needs attention" row
    shows
  - the database being down, and the service being unreachable, are reported as on the list
- **Clip statuses get words through an exhaustive label map**, like reasons, job statuses and failure kinds.
- **The dev library gains a two-chapter event** (`scripts/make_dev_library.py`) with an IGNORED clip and a
  NEW clip in a named chapter, so every clip state and the chapter layout can be checked in the browser.

## Non-goals

- **No editing.** Reordering clips, editing metadata, and any write belong to slice D. The page is
  read-only.
- **No render button and no live progress** (slice E).
- **No media facts** (duration, resolution, thumbnails): the events reads are probe-free (§4.9). These
  belong to the analysis cache and GUI v2.
- **No output path or look on the page.** No endpoint exposes the resolved look (§4.10 defers it to v2), and
  the output path is not in the detail response.
- **No links from "Needs attention" rows.** Their page would repeat exactly what the row already shows. A
  bookmarked link to an event that later breaks still gets the failure state.
- **No new dependency.** Routing is about 30 lines over `hashchange`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`:
  - new `Requirement: Each event opens on its own page`
  - new `Requirement: The event page shows the event's chapters and clips`
  - new `Requirement: The event page reports failures by cause`
  - `Requirement: Screen labels are exhaustive over the generated vocabularies` gains clip statuses

## Impact

- **Packages:** `web/` only.
  - `src/App.tsx`: the route switch.
  - New files:
    - `src/route.ts`: hash parse, format, and a `useRoute` hook
    - `src/api/event.ts`: `fetchEvent`, and the detail type aliases
    - `src/events/EventDetail.tsx`: the page
    - `src/events/common.tsx`: `JobCell`, `folderName`, `plural` and `formatBytes`, moved out of
      `EventList.tsx` so both screens share them
  - `src/events/EventList.tsx`: title links.
  - `src/events/labels.ts`: `CLIP_STATUS_LABEL`.
  - `src/app.css`: styles for the page.
  - `scripts/make_dev_library.py`, and the dev-library bullets in `web/README.md`.
- **CLI vs API (Principle V):** untouched. The page shows what `GET /api/v1/events/{id}` already returns.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, **no Alembic migration**, no rescan.
- **Dependencies (Principle VII):** none added.
- **Size (Principle VIII):** one read-only screen and a route, in one package.
