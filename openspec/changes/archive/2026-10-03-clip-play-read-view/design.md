## Context

See proposal.md, "Why". Code on main `ac4f356`, before the gate `clip-preview-proxy` (in review, not merged):

- **The player** is `web/src/preview/ClipPreview.tsx`: one component, one `<video>` whose source is set in a layout
  effect, whose open/closed state is `web/src/preview/previews.ts` (a module store: `show`, `hide`, `open`, `opener`,
  `takeFocus`, `keepPlayhead`, `length`), whose words and pure rules are `playback.ts`. `CutsPanel.tsx` mounts it
  inside Edit mode's Cuts panel with `cuts` (the panel's `ListedCut[]`), `typed`, `locked`, `onSet`, `onClose` and
  `onAnnounce`. `useClipLength` and `usePreviewOpen` are `useSyncExternalStore` hooks over the store.
- **The read view** is `ReadyView` and `ChapterPanel` in `events/EventDetail.tsx`: a `<table role="table">` per chapter
  whose rows (`tr.clip-row`) are `display: grid` below a 50rem container (`detail.css`), with a file cell that holds
  `ClipName` and `ReadCuts` (`cuts/ReadCuts.tsx`). `useReadCuts(eventId, event)` reads `GET …/reel` after every event
  read (a quiet one too) and yields `ClipCuts` (identity → `Trim[]`, only clips with cuts) or a failure the page
  already notes. The page re-reads in two ways: the operator's Refresh and the first load replace the content with
  placeholders (so `ReadyView` unmounts), and a re-read the page starts itself (a job ended) is quiet and keeps the
  content, with a new `event` object.
- **The Movie section** (`movie/MoviePanel.tsx`, D-15) sits above the chapters, outside `ReadyView`, with its own
  `<video>`; Edit mode shows none, which is why a clip's player and a `<video>` playing elsewhere on the page never
  coexisted in v1.
- **Edit mode has the reorder, the editor's announcer and a keyed store per editor** (`EventEditor` creates
  `createClipPreviews()` and calls `hideAll()` on unmount); the read view has none of these.
- **No component test runner exists.** Pure modules run under `node --test` (`npm test`, `tsconfig.test.json`); the
  rest is `tsc`, the production build and Playwright from the scratchpad, never the repo.

**What the gate adds, as designed** (its `design.md`; task 1.1 re-checks every name on main):

| Name used here | From | Meaning |
|---|---|---|
| `previewSource(proxy)`, `source.ts` | `clip-preview-proxy` | which file plays, from the detail alone |
| `proxy` prop of `ClipPreview` (beside `clip: Pick<Clip, 'identity' \| 'mtime'>`) | `clip-preview-proxy` | `ClipProxy \| null`, the detail's proxy state; the open snapshot below holds the `proxy` too |
| Play original / Play preview copy, `previews.original / setOriginal` | `clip-preview-proxy` | the operator's file override, per open preview |
| `probeProxy`, `entityVersion` | `clip-preview-proxy` | the copy's address with `v` |
| the copy's failure titles | `clip-preview-proxy` | by cause; some carry the "stop editing" advice |

The client follows what is on main. The specs of this change name no field and no function.

## Goals / Non-Goals

**Goals:**
- Every clip on disk can be watched from the read view in one press, in the player Edit mode has, with the same file
  choice and the same sound in Firefox.
- The player in the read view cannot edit anything and does not pretend to: no dead controls.
- The 400-clip event stays cheap: no video element, no request, no per-row work that grows with an open player.
- Edit mode behaves as it did.

**Non-Goals:**
- A thumbnail button, a keyboard shortcut for the next clip, a playlist, anything the timeline does.
- Refactoring Edit mode, `CutsPanel` or `EventEditor`.

## Research & Decisions

### The row's control is "Watch", not "Play"

**Context**: the request says "play"; the plan summary says "each clip row gets a Play control".
**Explored**: (a) the row's control named "Play <name>": the open player's own Play button is named
`playName(name, playing)` = "Play <name>" / "Pause <name>" (`playback.ts`), so two controls in one region of the page
would share an accessible name, and every locator and every screen-reader list would be ambiguous; (b) a control with the
visible word "Play" and the name "Watch <name>": a visible label not contained in the name fails WCAG 2.5.3 (Label in
Name); (c) Edit mode's own words, "Watch" and "Hide player" (`WATCH`, `HIDE_PLAYER`, `watchName`, `hideName`).
**Decision**: (c). The control is what Edit mode's panel shows, with the play icon, in the same words and names.
**Rationale**: one vocabulary in both views; no collision; the operator's "play feature" is this control plus the
player it opens. The spec calls it Watch, and the result of this change says so, since the plan summary says Play.

### The player opens in a row of its own under the clip's row

**Context**: the player needs 640 px at most and a fixed 16:9 box; the file cell is a narrow column, and below 50rem
each clip row is a grid.
**Explored**: (a) inside the file cell: far too narrow, and it would stretch the row's grid; (b) a modal or a side
panel: a second kind of surface for one video, focus trapping to build, and the clip's row out of sight; (c) a second
`<tr>` directly after the clip's row, spanning the table, as the Cuts panel sits under the row in Edit mode.
**Decision**: (c). `ChapterPanel` renders, for each clip, a `Fragment` of the clip's `tr` and a `PlayerRow` that returns
`null` until the clip's preview is open. The player row is `<tr role="row" class="clip-preview-row"><td role="cell"
colSpan={6}>`; in the grid layouts (`@container (width < 50rem)`) the row is `display: block` and the cell is the whole
width. It carries no position, is counted nowhere (`Counts`, the panel heading read the clips, not the DOM), and exists
only while open.
**Rationale**: the table's reading order stays (clip, then its player); a closed row costs nothing; no clip row is
refactored into a component.
**Cost**: a table row that is not a clip. Mitigation: the region inside it is named "Player for <name>".

### One component: read-only is the absence of `onSet`

**Context**: "Reuse the existing preview component — do not fork it."
**Explored**: (a) a `mode: 'edit' | 'read'` prop beside `onSet`: two sources of one fact; (b) a wrapper that hides the
Set buttons with CSS: dead controls in the tab order and the accessibility tree; (c) `onSet`, `locked` and `typed`
become optional, and `readOnly = onSet === undefined` is derived once inside the component.
**Decision**: (c). In `ClipPreview.tsx`: the Set From / Set To buttons are not rendered when read-only; Skip cuts is
rendered when `offersSkip(readOnly, cuts)` (Edit mode: always, as today; read-only: the clip has a cut on its bar);
`failureOf`, and the gate's copy failures, take the advice from `staleAdvice(readOnly)`: Edit mode's `STOP_EDITING`
unchanged, and here "Press Refresh to read the event again, then watch the clip anew." Everything else (file choice,
probe, notes, keys, announcements, Escape, focus-on-open) is not touched.
`CutsPanel.tsx` is not touched at all: it passes `onSet`, so its player is exactly as before.
**Rationale**: the fork would copy 870 lines and the gate's changes to it; this is a handful of conditionals and one
pure function, and a read-only player cannot have a disabled control by construction.

### Which clips offer it, and what they get as cuts

**Decision**: `canWatch(clip)` is `status !== 'missing'` (a pure function in `events/watch.ts`). The service serves an
ignored clip like any other (`clip_media`'s docstring), and an excluded clip is on disk, so both can be watched; a
missing clip has no file, so no control and no cell content. The cuts handed to the player are
`clip.excluded ? [] : (read.cuts?.get(identity) ?? NO_CUTS)`: exactly the expression `ReadCuts` uses for the cuts
indicator beside it, so the bar and the indicator never disagree. `NO_CUTS` is one module-level array, and `Trim[]`
from `ClipCuts` is stable until the next read, because `ClipPreview` is a `memo` component and a fresh array per render
would defeat it. A `Trim` is a `ListedCut` (`in`, `out`, no `removed`).
**Rationale**: the page already reads these cuts once per event read; the player asks for nothing more. A failed cuts
read leaves `read.cuts` null: no spans and no Skip cuts, and the page's existing note stays the only word.

### The store, one per mounted read view, and a re-read

**Context**: Edit mode creates `createClipPreviews()` per editor. `ReadyView` mounts and unmounts with the content: a
Refresh or the first load replaces it with placeholders, and Edit mode replaces it with the editor.
**Decision**: `ReadyView` holds `const previews = useState(createClipPreviews)[0]` and an effect that calls
`previews.hideAll()` on unmount. So Refresh, entering Edit mode and leaving the page close the player without further
code, which is what the spec says. A quiet re-read (a new `event`, same mounted view) changes the rows only:
- `watchedAfterRead(open, clips)` (pure) is `open` when the clip is still listed and on disk, else `null`. A layout
  effect in `ReadyView` on `event` calls it and, on `null`, calls `previews.hide(open)`; when keyboard focus had been
  in the player (a ref set by focus and blur on the player cell) it focuses the clip's row (`tabIndex={-1}`, programmatic
  only) when the clip is still listed, else the page's heading, through a callback `EventDetailBody` already has
  (`focusHeading`).
- The player row is keyed by the clip's media address (`clipMediaUrl`: it contains `v` = `mtime`) and holds a snapshot
  of the clip as it was at the open (`useState(() => clip)`). A changed file is a new key: the old element's cleanup
  keeps the playhead (the machinery that serves "a clip moved to another chapter" in Edit mode), the new one restores
  it, paused. A re-read that changes only the clip's proxy state (a proxy job finished meanwhile) is the same key and
  the same snapshot, so the player does not change file under the operator's thumb; the next open uses the new state.
**Rationale**: the gate decides the file from the detail "when the preview opens" and its component derives it from the
prop each render; in Edit mode the detail never changes while the preview is open, in the read view it can, so the
snapshot is what keeps the gate's rule true here.

### Opening one preview re-renders no list

**Decision**: each row's `WatchButton` and `PlayerRow` subscribe with `usePreviewOpen(previews, identity)`
(`useSyncExternalStore` over a boolean per clip); `ChapterPanel`, `ReadyView` and the 400 other rows do not re-render
when a preview opens. This is G1's rule for Edit mode (`previews.ts`' header) held here.
**Cost**: 400 subscribers on a notify; each snapshot is one comparison. Measured in task 4.2 on the 400-clip event.

### Focus and ids without extracting a row component

**Decision**: `ChapterPanel` already has `headingId`; the row ids are `${headingId}-w${index}` (the Watch button) and
`${headingId}-p${index}` (the player region, the button's `aria-controls`). Close and Escape call
`previews.hide(identity)` and then `document.getElementById(watchId)?.focus()`: the button is not unmounted by the
close, so focus is placed at once. Open: `previews.show(identity, 'toggle')`, and the gate's/`v1`'s `takeFocus` puts
focus on Play. The `opener` is always `'toggle'` in the read view.
**Rationale**: no hook-in-a-loop, no extraction of the existing row JSX.

### The read view's live region

**Decision**: `ReadyView` renders one `<p role="status" class="visually-hidden">` and an `announce(message)` that clears
the text and sets it a frame later (the same four lines as `EventEditor`'s, whose region is Edit mode's only), passed
to the player as `onAnnounce`, stable (`useCallback`). `EventEditor` is not refactored to share it (Principle VIII).

### One video at a time: a capturing `play` listener

**Context**: the Movie player and a clip's player can now both exist, and a `<video>`'s `play` event does not bubble.
**Explored**: (a) closing the clip's player when the movie plays: loses the operator's place and takes focus; (b) a
shared store between `MoviePanel` and the read view: couples two components that do not know each other;
(c) one listener on `document`, capturing, for `play`: when a `video` starts, every other `video` in the document that
is not paused is paused.
**Decision**: (c), `events/onePlayer.ts`: `keepOneVideoPlaying(root)` adds the listener and returns its remover;
`pauseOthers(started, videos)` is the pure part. `EventDetailBody` installs it in an effect for the page's life (the
Movie section sits outside `ReadyView`). Seeks, `load()` and Skip cuts' jumps fire `seeking`/`seeked`, never `play`,
so Skip cuts is not interrupted; the paused video's `pause` event is handled as any pause (the player's Play shows
"Play" again; the Movie panel has no state on pause).
**Rationale**: ten lines, no knowledge of either component, correct for any future `<video>` on the page.

### Where each part is tested

Pure logic in modules `npm test` runs: `events/watch.ts` (`canWatch`, `watchedAfterRead`), `events/onePlayer.ts`
(`pauseOthers`, and the listener against a stand-in root), `preview/playback.ts` (`staleAdvice`, `offersSkip`, and the
two stale-words functions). The wiring is verified by `tsc`, the production build and Playwright in Chrome 154 and
Firefox >= 155 from the scratchpad (task 4), including decoded sound for the Sony clips.

### Found on main (task 1.1) and while implementing

- **Names.** The gate gave `ClipPreview` a separate `proxy` prop (`ClipProxy | null`) beside `clip: Pick<Clip,
  'identity' | 'mtime'>`; `source.ts`, `probeProxy`, `previews.original / setOriginal` and Play original are as
  designed, and Play original is the last control. `grep` finds the "stop editing" advice only in `playback.ts`
  (`STOP_EDITING`, through `goneWords` and `changedWords`): the gate's copy-failure titles carry none, so
  `staleAdvice` is routed there alone. Nothing but the `onAnnounce` prop assumes the editor's live region.
- **The bare `<video>` is not a tab stop.** Firefox (unlike Chrome) makes a `<video>` without `controls` a tab stop,
  so the keyboard order the Edit-mode requirement fixes (Close, Play, playhead, ...) had a stray first stop there,
  found by the Firefox run. `ClipPreview` gives the element `tabIndex={-1}`; its controls are the house's own and a
  press on the picture still plays or pauses. This changes Edit mode only by removing that stop.
- **A sentence of its own.** The service's "no longer on disk" detail has no full stop; the read view's advice
  ends it as one (`goneWords(…, readOnly)`), Edit mode's string stays byte for byte as it was.
- **The player row is empty-free.** A read-only player of a clip with no cuts and no ready copy has nothing in its
  actions row, so the row is not rendered (an empty grid row would still take a gap).
- **Scrolling once the clip is read.** A read-only player that opens comes into view whole; reading the clip adds
  the cuts' legend and grows the region, so it scrolls once more then. That second scroll happens only when the
  first load succeeds and the page is still where the first scroll left it (an operator who has scrolled away is not
  pulled back), and it is the read-only player's alone: Edit mode's preview is as it was.

## Risks / Trade-offs

- **A gate's names differ from the plan** → task 1.1 reads main first and stops and reports on a mismatch that changes
  the specs; the specs name no function. In particular it greps every use of the "stop editing" advice, which the
  gate's copy-failure titles may add, and routes each through `staleAdvice`.
- **`ClipPreview`'s `onSet`-optional change touches a 870-line component the gate also touches** → the edit is a
  handful of lines (the Set buttons, one condition, the advice); the gate merges first, so this change is written
  on its result, and `git diff web/src/cuts/CutsPanel.tsx` stays empty.
- **A table row that is not a clip** (the player row) → `role="row"` with one `role="cell"`, `colSpan` 6; the region
  inside is named; screen readers announce the row count of the table, which includes it while open. Accepted.
- **Narrow layouts**: the clip rows are grids below 50rem; the player row must be `display: block` at each container
  query or its cell collapses into the first grid track. Task 4.2 looks at 320, 390, 800 and 1280, both schemes.
- **A started movie pauses a clip the operator meant to keep playing** (a video-in-video situation): the page has one
  audio output; pausing the older is what every player does. The paused one stays and resumes from its position.
- **Focus after a vanished clip** is a rare path (a re-read while the player has focus and the clip went). It has a
  rule so that focus never lands on `<body>`, and it is covered by the pure function's test and by Playwright where a
  worker can be run (task 4.1).

## Migration Plan

None: a client change over routes that exist. Edit mode is unchanged. Rolling back is reverting the web change; no data
is written.
