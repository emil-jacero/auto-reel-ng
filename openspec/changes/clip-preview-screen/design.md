## Supervisor decisions (2026-10-01)

- **The 0.1 s end slack** (`END_SLACK_MS`) is accepted, and so is the wording "no frame that lies wholly inside a
  cut" for Skip cuts.
- **One press from the row.** Besides the **Watch** control in the Cuts panel, the clip's thumbnail in Edit mode
  is a button "Watch <name>" that opens the same player. It is not the drag handle, which stays separate. It
  keeps the thumbnail's size, with no layout shift, and a failed thumbnail's "No preview" box opens the player
  too (decision "The thumbnail opens the player", and the spec's MODIFIED "Every clip row shows a frame from its
  clip").
- **One video in Edit mode.** Only one video element exists in Edit mode at a time. The movie player
  (`movie-player-screen`) is not shown in Edit mode.
- **Verification** uses the Chrome-channel Playwright image `localhost/playback-research:chrome` (its
  Containerfile is in R0's research folder and in `docs/research/browser-playback.md`) or Firefox. Playwright's
  stock Chromium is never used for playback.
- **The control's words** are "Watch" / "Watch <name>", the region "Player for <name>", and Close "Close the player
  of <name>". This keeps "preview" away from the thumbnails' "No preview" / "No preview for <name>" on the same row.

## Context

See proposal.md, "Why". This change starts from main **after** both `media-endpoints` and `cross-chapter-drag`
are archived. Line numbers below are on main at `cb9e85f`, where both gates have landed (re-checked before this
change was proposed). Task 1.1 re-checks every name this design uses.

**What the media route gives** (`openspec/changes/archive/2026-10-01-media-endpoints/`, its design section "What
the screens can rely on", and `web/src/api/schema.d.ts`):
- `GET /api/v1/events/{event_id}/media?clip=<identity>[&v=]` streams the clip's bytes unchanged.
  - It answers 200, 206 for a range, 416 past the end (a zero-byte file answers 416 to `bytes=0-`), 404 for an
    identity that is not a listed clip, and 502 for an unreadable folder or file.
  - It also publishes 304 (an `If-None-Match` naming the current file) and 400 (a malformed `Range`). The
    one-byte check below sends neither an `If-None-Match` (`cache: 'no-store'`) nor a malformed `Range`, so
    neither can answer it; were one to, it reads as an answer the check does not expect (no answer).
  - It sends `Cache-Control: private, no-cache` and a strong `ETag`.
- No database, no probe. Each range request passes the one auth hook, as `<img src>` does.
- Its types come from the regenerated `schema.d.ts`, as `paths['/api/v1/events/{event_id}/media']`.
- To a `<video>`, a 404, a 502 and a zero-byte clip all look the same: `MediaError` 4.

**Edit mode today** (main at `cb9e85f`, `cross-chapter-drag` merged):
- **The Cuts panel.** `cuts/CutsPanel.tsx` is `CutsPanel` (182-449), `memo`, mounted by `ClipRow`
  (`edit/ClipOrderList.tsx` 365-377) once shown, and then only hidden (`hidden={!open}`, 330).
  - It keeps its two fields as local state, seeded from and written back to the editor's panel store
    (`CutPanels`, 44-47) through `setFields` (223-236). `setFields` calls `onTyped` when "has text" flips: that
    is G2's typed-cut mark and the save bar's hold.
  - Focus after an edit is a request (`focusAfter`), applied in a layout effect with no deps (298-317). A
    passive effect then scrolls it into view (322-326).
  - `locked` (a save in flight or a Move clips pending, `listsLocked`, `EventEditor.tsx` 967) makes its
    fields `readOnly` and its buttons `aria-disabled`.
- **The panel store.** `EventEditor.tsx` 1152-1163 creates the store once, `{ panels, clear }`, and passes it
  to every list. Reset calls `cutPanels.clear()` before it dispatches `reset` (1860-1865). `ClipRow` also
  hides its panel on Reset (its `resets` prop) and keys `CutsPanel` by it, so every panel remounts empty. Rows are keyed by
  identity, and the store too, because Move clips (G1) and, after `cross-chapter-drag`, a drop into another
  chapter mount the row anew in another `ClipOrderList`.
- **`cross-chapter-drag`** (`edit/ChapterDrag.tsx`). One `DndContext` wraps every chapter, and each row is a `useSortable` shell.
  - On every new drag target, every row's shell re-runs. Its memoised children (`RowBody`, `CutsToggle`,
    `CutsPanel`) do not.
  - The drag's activator is the handle only, so a key or a pointer inside the panel never lifts a row.
  - A cross-chapter drop focuses the moved row's handle (its `ChapterDrag` layout effect, 555-575). Its passive
    effect (579-591) brings the row's first line into view (`firstLineIntoView`, 124-142: the handle, `.clip-name`
    and the Cuts control), not the whole `li`, so a row taller than the space is scrolled so its first line is.
  - While a pointer holds a clip, a transparent layer (`.clip-drag-shield`) takes the pointer, and within its own
    chapter a clip stays put while the pointer is over its own row, however tall (the review fixes). Neither
    concerns a preview: the layer exists only during a pointer drag, and the dragged copy (`DragPreview`) shows
    the clip's name only, never its panel or a video.
- **Times.** `cuts/times.ts` is pure, with type-only imports:
  - `parseTime` reads a time to whole milliseconds, and `formatTime` (71-75) writes `m:ss` or `h:mm:ss` with up
    to three decimals and no trailing zero
  - `checkCut(listed, typedIn, typedOut)` (158-183) refuses empty, unreadable or too-precise times, a wrong order
    and overlaps
  - `CUT_HINT` (287-290) says the page does not know the clip's length
- **Thumbnails.** `api/thumbnail.ts` 20-28 builds `thumbnailUrl(eventId, clip)` with `v` = `mtime`. The address
  is already in the browser's cache once the row has shown it (`private, max-age=86400`). The spec keeps the
  thumbnail not focusable (`web-app` spec, "Every clip row shows a frame from its clip"); this change modifies
  that for Edit mode. `RowBody` (`edit/ClipOrderList.tsx` 83-139, `memo`) renders `ClipThumb`
  (`events/ClipThumb.tsx`) as the row grid's `thumb` item (`edit/edit.css` 277-279).
- **Strict mode.** `main.tsx` renders in `StrictMode`, so effects mount, unmount and mount again in development.
- **Edit mode replaces the read view** (`events/EventDetail.tsx` 365-386: `editing ? <EventEditor> :
  <ReadyView>`). The event's movie player (`movie-player-screen`, D-15) lives in `ReadyView`, so it is never on
  the page beside a preview. One preview at a time therefore means one video on the page.
- **The render's cut rule.** `render/segments.py` `kept_spans` (131-159) clamps each cut to `[0, duration]`,
  sorts the cuts and merges overlapping **or touching** ones (`start <= merged[-1][1]`). `times.ts`
  `cutOutSeconds` merges the same way.

**R0** (`docs/research/browser-playback.md`, landed by `media-endpoints`):
- **What plays.** H.264 with AAC plays in Chrome 154, Firefox 132 and WebKit.
- **PCM audio.** The Sony XAVC clips carry PCM audio, 52 % of the archive. Their sound plays in Chrome and is
  silent in Firefox (`mozHasAudio === false`, no error).
- **No picture.** HEVC and MPEG-4 Part 2 give `videoWidth === 0` in Chrome with no error, and HEVC gives
  `MediaError` 4 in Firefox.
- **Rotation** is honoured.
- **`preload`.** `preload="none"` makes no request, and `"metadata"` makes 3 to 4 range requests per file.
- **The stock browser.** Playwright's bundled Chromium cannot decode H.264, so every check uses Chrome
  (channel `chrome`) or Firefox.

## Goals / Non-Goals

**Goals:**

- See a clip, find a moment, and turn it into a cut's From or To in one press, without leaving Edit mode or the
  panel the cut is typed in.
- Play the clip as the movie will (Skip cuts), and refuse a cut past the clip's end with a length read from the
  file itself.
- Say what the browser cannot do, by cause. Never load media before it is asked for. Never re-render a list
  while a clip plays.

**Non-Goals:**

- No engine, API, schema or dependency change. No change to `ClipOrderList`'s rows beyond two props to
  `CutsPanel` and the thumbnail's Watch button, and none to the drag, to Move clips, or to the save bar's
  mechanics.
- No editing on the bar: it shows cuts and moves the playhead (proposal, "Non-goals").

## Research & Decisions

### The spike: player facts this design rests on

**Context**: R0 established what plays. The preview also depends on how exactly a browser reports a length,
reads a seek back, and lets a page skip footage while it plays.

**Explored**: a scratch spike (session scratchpad `g-spec/clip-preview-screen/`: `srv.py`, `probe.py`,
`probe2.py`, never committed). A Starlette `FileResponse` server on port 8194 served:
- two dev-library-style clips, cut by `make_dev_library.py`'s own recipe (`ffmpeg -t 6 -map 0 -c copy` from the
  fixture's Grillning clips: 1080p50, AAC, 6.020 s by ffprobe)
- symlinks to five R0 samples
- a zero-byte file, and a name that does not exist

It was driven by Playwright in `localhost/playback-research:chrome` (the image R0 built `FROM
mcr.microsoft.com/playwright/python:v1.49.0-noble`, plus `RUN pip install -q playwright==1.49.0 && python -m
playwright install chrome`), with Chrome 154 (channel
`chrome`) and Firefox 132. WebKit hung in `play()` under headless and was dropped. It is not a target browser,
and R0 covered its codecs.

| Fact | Chrome 154 | Firefox 132 |
|---|---|---|
| `duration` at `loadedmetadata` vs ffprobe's format duration (dev clip 6.020; 1080p50 24.960; portrait 14.651995; rotate 18.401667) | equal (6.02; 24.96; 14.651995; 18.401667) | longer (6.08; 25.002666; 14.675011; 18.459863) |
| `duration` after playing towards the end of the dev clip | 6.04 (a `durationchange`, also seen before the end was reached, while Chrome buffered ahead) | 6.08 |
| `currentTime` read back after `currentTime = 1.234`, `2.5`, `0.001`, `3.2033333` and `seeked` | the value set, to the microsecond (`3.2033333` reads `3.203333`) | the value set |
| `currentTime = duration` fires `ended` | dev clip: no; Sony clip: yes | yes |
| `requestVideoFrameCallback` | yes | yes |
| `mozHasAudio`: Sony PCM / AAC clips | absent | `false` / `true` |
| HEVC `.mov` | metadata, `videoWidth` 0 | `MediaError` 4; a `Range: bytes=0-0` fetch answers 206 |
| zero-byte file / unknown name | `MediaError` 4; the fetch answers 416 / 404 | same |

Skipping a cut from 1 to 2 s while playing from 0.5 s. A fresh element per strategy. A frame counts as shown
when a `requestVideoFrameCallback` observer recorded its `mediaTime` in [1, 2):

| Strategy | dev clip, 50 fps (Chrome / Firefox) | Sony clip, 25 fps (Chrome / Firefox) |
|---|---|---|
| on `timeupdate`, jump when inside the cut | 11 / 5 frames shown | 7 / 4 |
| on each presented frame, jump when the frame is inside the cut | 1 / 1 | 1 / 1 |
| on each presented frame, jump when the **next** frame would be inside (frame step from the last two frames) | **0 / 0** | **0 / 0** |

The spike's "cut to the end" row (Chrome and Firefox "looping at the last frame", `ended` never firing) was an
artifact of its own loop: it re-seeked on **every** presented frame while the frame was before the cut's end
(`jumps: 98` and `105`), and the clip's last frame (5.98) lies inside a cut from 5 to 6.02. The review re-ran
the end and the skip cases (`g-spec/clip-preview-screen/review/probe3.py` to `probe8.py`, same image, same
two clips, port 8195, stopped afterwards):

| Fact (review spike) | Chrome 154 | Firefox 132 |
|---|---|---|
| One jump to 6.02 (ffprobe's end) at a cut from 5 to 6.02, playing from 4.5 | ends (`ended` at 6.04), after showing frames 5.98 and 6.04: both inside the cut | ends at 6.08, after showing 6.02 and 6.04 |
| At that cut, pause and seek to 5 instead | paused at 5, no frame after 5 (dev clip and Sony clip) | the same |
| The design's first loop rule (`from <= at + step && at < to`), cut from 1 to **2.01** or **2.03** (between two frames) | **stalls**: 52 to 65 seeks in 4 s, playback never passes the cut, the frame at 2.00 (2.02) shown again and again, on both clips | passes (Firefox shows the seek target's own time, 2.01) |
| The rule kept below (`from <= at + step < to`, times in whole ms), cuts 1–2 (×3), 1–2.01, 1–2.03 | one jump each, playback passes 3 s; 0 frames inside 1–2; for 1–2.01 only the frame 2.00, which straddles the cut's end | one jump each; 0 frames inside |
| The same rule with times not rounded to whole ms | the 25 fps Sony clip showed the frame at 1.0 in 6 of 6 runs (`0.96 + 0.04` < 1 in floating point) | the same |

**Decision**: The decisions below use these numbers. The skip runs per presented frame, in whole milliseconds,
and jumps while the **next** frame would start inside a cut. A cut that ends within 0.1 s of the browser's
length pauses at its start. It never relies on `ended`. The length is the browser's `duration`, updated on
`durationchange`.

**Rationale**: Every behaviour the spec states was observed. The one cross-browser difference that matters,
Firefox reading lengths 20 to 60 ms longer (and Chrome raising 6.02 to 6.04 during playback), errs on the side
of accepting a cut, and the render then clamps it, as D-14 says. It also means a cut that ends where the render
ends the clip does not reach the browser's end, which is why "runs to the end" has a 0.1 s slack.

### Where the preview lives: inside the clip's Cuts panel

**Context**: The brief asks for a preview opened "from its row / Cuts panel", one at a time, whose Set From and
Set To fill the cut fields. Those fields are `CutsPanel`'s local state.

**Explored**:
- **A modal `Dialog`** per clip. The panel's fields behind it are inert, so the dialog would need its own
  copy of the cut form. A typed cut would then live in two places, and "typed but not added" (G2) would become
  a dialog-close question. It also hides the row and its cuts.
- **One docked player** for the editor (a sticky panel). Set From would write into a panel that may be hidden
  or unmounted, so every panel would need a subscription to its fields. A row moved under it would also
  separate the player from its clip's cuts.
- **The row's thumbnail as a button**, alone. The spec kept the thumbnail not focusable, and a focusable
  thumbnail adds a tab stop per row (400 on `Stor dag`). As the only way in, it would also leave the player
  without a control inside the panel that holds it.
- **Inline, at the top of the clip's Cuts panel.** The row's Cuts control opens the panel, as today, and its
  Watch control opens the player there.

**Decision**: Inline. `CutsPanel` gains a **Watch** toggle as its first control, and a `ClipPreview` region
under it while open, above the cut list and form. Set From and Set To call the panel's own `setFields`. In
addition, the supervisor chose one press from the row (2026-10-01): in Edit mode the clip's thumbnail is a
**Watch** button that shows the panel and opens the same player there (next decision). The row's grid and its
sizes do not change; its cost is one tab stop per row (Risks).

**Rationale**:
- The player, the cuts it shows and the fields it fills are one panel.
- G2's mechanics hold unchanged: typed text, the "typed" mark, the save bar hold, the lock, focus requests and
  the panel store.
- The panel already moves with its row and is remounted on a move, which the store below survives.
- The row's grid, sizes and drag rules stay as G2 and `cross-chapter-drag` measured them. The thumbnail rule
  changes for Edit mode only (spec, MODIFIED "Every clip row shows a frame from its clip").

### The thumbnail opens the player: one press from the row

**Context**: Supervisor decision (2026-10-01). The panel's Watch takes two presses from the row (Cuts, then
Watch). The operator asked for one.

**Decision**:
- **Markup.** `RowBody` gains an optional `onWatch`. When it is given, the thumbnail is wrapped in a button, and
  `ClipThumb` itself is unchanged:

  ```tsx
  <button type="button" className="clip-thumb-watch" aria-label={`Watch ${name}`} onClick={onWatch}>
    <ClipThumb eventId={eventId} clip={clip} name={name} />
  </button>
  ```

  The button's name stands in for the image's "Frame from <name>" and for a failed box's "No preview for
  <name>", which sit inside it. It has no `aria-expanded`: it opens, and never closes.
- **Which rows.** `ClipRow` passes `onWatch` only when `cuttable` (an active or new clip). Missing, removed and
  ignored rows pass none and keep the plain, unfocusable thumbnail.
- **What it does.** `onWatch` is a `useCallback` over `identity` and `panels`, so it is stable and `RowBody`'s
  `memo` still holds on every drag step. It:
  1. shows the Cuts panel when it is hidden, exactly as the Cuts control does (`panels.set(…, { open: true, … })`,
     `setOpen(true)`)
  2. calls `panels.previews.show(identity, 'thumb')`, which closes any other preview and asks for focus on Play
- **Focus.** `show` records who opened the preview (`'toggle'` or `'thumb'`) and a one-shot focus request.
  `ClipPreview`'s layout effect takes the request (`takeFocus`) and focuses Play, on its mount and on every later
  `show` of the same clip. So a press while the preview is open moves focus to Play, and a remount after a move
  finds no request and takes no focus. Close and Escape return focus to the opener: `'toggle'` → the panel's
  `focusAfter` request `preview-toggle`; `'thumb'` → the row's `.clip-thumb-watch`, found from the panel's root
  with `closest('.clip-item')`. A row remounted by a move has its own thumbnail button, so the opener is always
  in the page.
- **The drag.** The button gets no drag listeners. `useSortable`'s activator is the handle only
  (`setActivatorNodeRef`), so a press or a pointer drag on the thumbnail never lifts the row, and the image
  keeps `draggable={false}`.
- **Look.** In `preview/preview.css` (`@layer screens`):

  ```css
  .clip-item > .clip-thumb-watch { grid-area: thumb; display: block; inline-size: 100%; padding: 0; border: 0;
    background: none; border-radius: var(--r-sm); cursor: pointer; }
  .clip-thumb-watch:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
  ```

  The button takes the grid cell the bare `.clip-thumb` took, and `.clip-thumb` fills it (`inline-size: 100%`,
  16:9), so the box keeps its size and place (task 4.2 compares row heights and boxes with main's build). No
  hover animation.
- **Touch.** The box is at least 80 × 45, so the thumbnail's own box is its 44 × 44 tap area. It does not reach
  the handle or the file name.

**Rationale**: One press, without a second player or a second copy of the cut form: the thumbnail opens the
panel's own player. The panel's Watch stays, so the player has a toggle inside the panel that holds it.

### One preview at a time: a store in the editor, not editor state

**Context**: Opening one preview closes the others, across chapters. Editor state would re-render every list
(G1's rule: no list prop derives from such state).

**Decision**: `preview/previews.ts`, pure (no runtime import):

```ts
/** The editor's previews: which clip's is open, and what a remount or a later check needs. */
export type ClipPreviews = {
  /** The identity whose preview is open, or null: one on the page at a time. */
  open(): string | null
  /** Opens `identity`'s preview, closing any other; records the opener and asks once for focus on Play. */
  show(identity: string, from: 'toggle' | 'thumb'): void
  /** Who opened `identity`'s open preview: where Close and Escape return focus. */
  opener(identity: string): 'toggle' | 'thumb' | null
  /** True once after each `show(identity, …)`: `ClipPreview` then focuses Play. A remount finds false. */
  takeFocus(identity: string): boolean
  /** Changes on every `show`, so a mounted `ClipPreview` re-runs its focus effect. */
  showCount(): number
  /** Closes `identity`'s preview if it is the open one, and forgets its kept playhead. */
  hide(identity: string): void
  /** Reset: no preview open, no playhead kept. Lengths stay: they are facts of files, not edits. */
  hideAll(): void
  subscribe(listener: () => void): () => void
  /** Where an open preview's playhead stood when its element unmounted (a move to another chapter). */
  playhead(identity: string): number | undefined
  keepPlayhead(identity: string, seconds: number | undefined): void
  /** A clip's length as this browser read it, by its media address (`v` = mtime: a new file, a new key). */
  length(src: string): number | undefined
  setLength(src: string, seconds: number): void
}
export function createClipPreviews(): ClipPreviews
```

- **Where it lives.** `CutPanels` (`CutsPanel.tsx` 44-47) gains `previews: ClipPreviews`, so it reaches every
  `CutsPanel` with no new prop through `ClipOrderList` and `ClipRow`. `EventEditor` creates it beside the map
  (1152-1163). Its `clear` also calls `previews.hideAll()`, so Reset closes every preview before the panels
  remount.
- **How a panel reads it.** Two `useSyncExternalStore` reads in `CutsPanel`: `previews.open() === identity`
  and `previews.length(src)`. Both are primitives, so a panel re-renders only when its own answer changes.
  `ClipPreview` reads `showCount()` for its focus effect; it re-renders on a `show` only while it is mounted,
  which is one element.
- **Leaving Edit mode** unmounts the editor, and the store goes with it. A length is never sent or saved.
- **`hide` and `hideAll`** also forget the opener and any focus request not yet taken.

### The element: created on open, its source set in an effect

**Decision**: `ClipPreview` renders `<video>` only while open, with these settings:
- `preload="metadata"`
- `poster` = `thumbnailUrl(eventId, clip)`, the row's thumbnail, already cached
- `playsInline`
- no `controls` and no `autoPlay`

A layout effect sets `video.src = clipMediaUrl(eventId, clip)`. Its cleanup:
1. When `previews.open()` is still this identity (the row is being remounted elsewhere), keeps the playhead
   (`keepPlayhead`). Otherwise it forgets it.
2. Pauses, removes `src` and calls `load()`, which aborts the range requests.

On `loadedmetadata`, a kept playhead is applied and forgotten, and the clip stays paused.

Hiding the panel unmounts `ClipPreview` in the same commit in which `CutsPanel`'s layout effect then calls
`hide`. So the cleanup still finds the preview open and keeps the playhead, and `hide` (and `hideAll`) must
forget it. Otherwise the next Watch of that clip would open at an old time instead of at the start.

**Rationale**:
- **`src` in an effect** makes StrictMode's mount, unmount and mount, and a real remount, behave the same.
  The second mount sets the source again. A JSX `src` would leave the cleanup's `removeAttribute` undone in
  development only.
- **`load()` after removing `src`** is the documented way to drop a media element's network activity at
  once, rather than at garbage collection.
- **React runs every unmount cleanup of a commit before its mount effects**, so on a cross-chapter drop the
  old panel keeps the playhead before the new one reads it.
- **`preload="metadata"` with a cached poster** shows a frame at once, and reads the length with the fewest
  requests (R0 §7).

### Custom controls, native elements

**Explored**: `<video controls>`. Its keyboard behaviour and seek step differ per browser, and it shows a
second seek bar beside the cut bar. Chrome adds a download item and a menu. Its time display is not the
panel's format, and it cannot say "in cut 2".

**Decision**: Native `<button>`s with the house classes, plus one custom slider for the playhead. The markup:

```html
<div class="clip-cuts" id="cuts-:r3:" role="group" aria-label="Cuts of s1710001.mp4">
  <button type="button" class="btn btn-secondary btn-compact preview-toggle" aria-expanded="true"
          aria-controls="preview-:r7:" aria-label="Watch s1710001.mp4"><svg play/>Watch</button>
  <section class="clip-preview" id="preview-:r7:" aria-label="Player for s1710001.mp4" data-state="ready">
    <div class="preview-head">
      <span class="preview-time" aria-hidden="true"><span>0:01.234</span> / 0:06.02</span>
      <button type="button" class="btn btn-ghost btn-icon preview-close"
              aria-label="Close the player of s1710001.mp4"><svg x/></button>
    </div>
    <div class="preview-stage">                                  <!-- 16:9, sized before any byte -->
      <video class="preview-video" preload="metadata" playsinline poster="…/thumbnail?clip=…&v=…"></video>
      <span class="preview-status" aria-hidden="true">Loading…</span>   <!-- until loadedmetadata -->
    </div>
    <div class="preview-transport">
      <button type="button" class="btn btn-secondary btn-icon preview-play"
              aria-label="Play s1710001.mp4"><svg play/></button>       <!-- "Pause …" + pause icon -->
      <div class="cut-bar" role="slider" tabindex="0" aria-label="Playhead of s1710001.mp4"
           aria-valuemin="0" aria-valuemax="6.02" aria-valuenow="1.234"
           aria-valuetext="0:01.234 of 0:06.02, in cut 1" aria-describedby="preview-:r7:-keys">
        <span class="cut-bar-track"></span>
        <span class="cut-bar-span" data-kind="cut" style="--from: 0%; --to: 24.9%"></span>
        <span class="cut-bar-span" data-kind="removed" style="…"></span>
        <span class="cut-bar-span" data-kind="typed" style="…"></span>
        <span class="cut-bar-head" style="--at: 20.5%"></span>
      </div>
    </div>
    <p class="visually-hidden" id="preview-:r7:-keys">Arrows move 0.1 seconds, Page Up and Page Down one
      second, Home and End to the start and the end.</p>
    <ul class="preview-legend" aria-hidden="true">                <!-- only the kinds shown -->
      <li><span class="cut-bar-swatch" data-kind="cut"></span>Cut</li>
      <li><span class="cut-bar-swatch" data-kind="removed"></span>Removed when you save</li>
      <li><span class="cut-bar-swatch" data-kind="typed"></span>Typed, not added</li>
    </ul>
    <div class="preview-actions">
      <button type="button" class="btn btn-ghost btn-compact preview-skip" aria-pressed="false"
              aria-label="Skip cuts of s1710001.mp4"><svg skip-forward/>Skip cuts</button>
      <button type="button" class="btn btn-secondary btn-compact preview-set" data-field="start"
              aria-label="Set From at the playhead of s1710001.mp4">Set From</button>
      <button type="button" class="btn btn-secondary btn-compact preview-set" data-field="end"
              aria-label="Set To at the playhead of s1710001.mp4">Set To</button>
    </div>
    <!-- notes, each an Alert role="note": no sound / no picture (+ Download) -->
  </section>
  <div><!-- the cut list, as today --></div>
  <form class="cut-form">…</form>
</div>
```

- **Order and names.** The keyboard order is Close, Play, the playhead, Skip cuts, Set From, Set To, as the
  spec lists them. Every accessible name starts with the visible words (label in name). In the row, the
  thumbnail's Watch comes after the handle and before the row's action, the move buttons, the Cuts control and
  the panel's Watch.
- **`aria-controls`** on the Watch toggle names the region only while it is mounted, as `CutsToggle` does
  with its panel (never an id that is not in the page). Closed, the toggle has `aria-expanded="false"` and no
  `aria-controls`.
- **Visible time.** The time and length use `formatTime`, as the spec's "Times" demands (no trailing zero).
  `tabular-nums` and a `min-inline-size` in `ch` keep the box from jumping. Before the length is read it shows
  `0:00 / —` ("absent shows as absent").
- **The legend** is `aria-hidden`: the slider's value text says the same thing ("in cut 2").
- **A press on the picture** plays or pauses: a pointer convenience for which Play is the keyboard path.
- **Failed** (`data-state="failed"`): the head with Close stays, and an `Alert` (`role="note"`) replaces the
  stage, the transport, the legend and the actions.

### The playhead slider

**Decision** (pure parts in `preview/playback.ts`):

```ts
/** The playhead after a key on the slider, in ms, clamped to [0, length]; null: not its key. */
export function seekKey(key: string, atMs: number, lengthMs: number): number | null
// ArrowLeft/ArrowDown −100, ArrowRight/ArrowUp +100, PageDown −1000, PageUp +1000, Home 0, End lengthMs
/** `0:01.234 of 0:06.02`, plus `, in cut 2` when `atMs` lies inside the 2nd listed, not-removed cut. */
export function playheadWords(atMs: number, lengthMs: number, cuts: readonly ListedCut[]): string
/** A time's place along the bar, 0–100 (%), clamped. */
export function along(ms: number, lengthMs: number): number
```

- **Keys.** A handled key calls `preventDefault`, so the page does not scroll, and sets
  `video.currentTime = ms / 1000`. The spike read every such value back exactly.
- **Pointer.** On `pointerdown`, the slider takes pointer capture and seeks to the time under the pointer.
  Every `pointermove` while captured seeks too, batched to one seek per animation frame. `touch-action: pan-y`
  lets a vertical swipe scroll the page, while a horizontal one seeks.
- **What it says.** `aria-valuenow` and `aria-valuetext` follow every seek, pause and key. While the clip
  plays, they change at most once a second, on the whole second. The visual head follows every frame. A
  focused slider whose value changes 50 times a second would be read out continuously.
- **Unavailable** (`aria-disabled="true"`, keys and pointer ignored) until the length is known: there is no
  range to move in. Set From and Set To follow the same rule.

### Set From / Set To

**Decision**: `ClipPreview` calls `onSet(field, video.currentTime)`. `CutsPanel` handles it:
- while `locked`, it does nothing (the buttons are `aria-disabled`)
- otherwise it calls `setFields(formatTime(seconds), end)` (or `(start, formatTime(seconds))`), clears the
  field's refusal, and announces `From set to 0:01.234.` / `To set to 0:02.5.` through `onAnnounce`

Focus stays on the pressed button.

**Rationale**:
- `formatTime` rounds to whole milliseconds and drops trailing zeros. `parseTime` reads it back exactly, since
  both go through whole milliseconds, so the field and the cut agree with what the panel shows.
- Going through `setFields` is what makes the text "typed" (`onTyped` when "has text" flips). It is also what
  writes it to the panel store, so it survives hiding and a move.
- No new rule is needed for the save bar, the guard or Reset.

**The typed span on the bar** is `typedSpan(start, end)`: the parsed span when both fields parse and the end
is after the start, else null. It is memoised on the two strings, and it is a hint only. Add cut still runs the
full `checkCut`.

### Skip cuts: one frame ahead, the render's merge

**Decision** (`preview/playback.ts`):

```ts
/** A span Skip cuts jumps over, in whole ms. */
export type Skip = { from: number; to: number }
/**
 * The listed, not-removed cuts as the render joins them (`kept_spans`): clamped to
 * [0, length], empty ones dropped, sorted, overlapping or touching ones merged.
 */
export function skipSpans(cuts: readonly ListedCut[], lengthMs: number): Skip[]
/** A span that ends less than this before the browser's length runs to the clip's end. */
export const END_SLACK_MS = 100
/** Whether `span` runs to the clip's end: `lengthMs - span.to < END_SLACK_MS`. */
export function toEnd(span: Skip, lengthMs: number): boolean
/**
 * Where playback goes when the frame at `atMs` is shown and the next comes `stepMs`
 * later (both whole ms): for the first span with `from <= atMs + stepMs < to`,
 * `{stop: from}` when it runs to the end, else `{seek: to}`; null to play on.
 */
export function skipAt(spans: readonly Skip[], atMs: number, stepMs: number, lengthMs: number):
  { seek: number } | { stop: number } | null
/**
 * Where Play starts: `atMs`, a span's end, the first footage from 0 (also when `atMs` is
 * within `END_SLACK_MS` of the end), or null (all cut).
 */
export function playFrom(spans: readonly Skip[], atMs: number, lengthMs: number): number | null
```

- **While playing with Skip cuts on**, a `requestVideoFrameCallback` loop runs on each presented frame.
  `atMs` is `Math.round(metadata.mediaTime * 1000)`, and `stepMs` the difference of the last two `atMs`
  (0 before the second frame, so the first frame itself is tested). It acts on the first span into which the
  **next** frame would start, `from <= atMs + stepMs < to`:
  - when the span does not run to the end (`toEnd` false), it seeks to `to`
  - otherwise it pauses and seeks to `from`: the movie's clip ends there

  The loop runs only while playing, the same callback also sets the frame's time for the head, and it stops on
  `pause` or unmount.
- **Why `< to` on the next frame, not `at < to`.** After a seek to a `to` that falls between two frames
  (any time Set To wrote while playing, such as `0:02.607`), Chrome presents the frame that starts just before
  `to`. A rule on the shown frame's own time would find it inside the cut and seek again, for ever: the review
  spike measured 52 to 65 seeks in 4 s with playback stuck. On the next frame's start, that straddling frame is
  left alone (it is not wholly inside the cut) and playback goes on after one seek.
- **Play**, with Skip cuts on, first applies `playFrom`. When it returns null, nothing plays, and
  `Nothing plays: the cuts cover the whole clip.` is announced. When the playhead sits in or at the start of a
  span that runs to the end, or at the clip's end (where `play()` would restart from 0 and show the first
  frame of a cut there), play starts from the first footage after 0.
- **Seeks are not skipped while paused.** The operator may park the playhead inside a cut to set a time. While
  playing, the next frame leaves the cut.
- **Skip cuts off**: the loop only moves the head.

**Rationale**:
- One frame ahead is the only strategy that showed **no** frame of a cut, in both browsers at 25 and 50 fps
  (spike), once times are in whole milliseconds (review spike).
- `timeupdate` fires about 4 times a second and showed 4 to 11 frames.
- **The 0.1 s slack.** The browser's length runs past the render's by up to 60 ms (Firefox) or 20 ms (Chrome
  after a `durationchange`). A cut that ends where the render ends the clip (an analysis trim, or a To set at
  Chrome's first read) then leaves a few ms before the browser's end, and a jump there shows the clip's last
  frames, which lie inside the cut (review spike: 2 frames in each browser). Pausing at the cut's start shows
  none. The cost: a cut that ends 1 to 99 ms before the browser's end stops the preview at its start, while the
  movie keeps those few frames. 0.1 s is above every overshoot measured (58 ms at most) plus a frame at 50 fps.
- `requestVideoFrameCallback` exists in Chrome and in Firefox from 132 (spike), and in Safari from 15.4 (not
  tested here). There is no second path (Principle VII).

### The clip's length: the browser's read of the file, checked to the millisecond

**Decision**:
- **Where it comes from.** `ClipPreview` calls `previews.setLength(src, video.duration)` on `loadedmetadata`
  and on every `durationchange`, only when `Number.isFinite(duration) && duration > 0`. Nothing else ever sets
  a length: no default, no guess (Principle I).
- **`checkCut` takes it.** `checkCut(listed, typedIn, typedOut, length?: number)`, with the same order as today
  and one new step after `order`:
  - when `length` is known and `outMs > Math.round(length * 1000)`, it refuses with
    `{ kind: 'past-end'; field: inMs >= lengthMs ? 'start' : 'end'; at: seconds; length: seconds }`
  - `refusalWords` gains the case, and `tsc` checks the switch is exhaustive
- **Rounding.** The length is rounded as `formatTime` rounds it, so a To set at the end (`formatTime(duration)`)
  is never refused. That includes a length such as 6.0065 s, shown as `0:06.007`.
- **The hint.** With a length, the hint is `lengthHint(length)`, otherwise `CUT_HINT` unchanged.
- **The badge.** `pastEnd(cut, length)` marks a listed cut whose `out` exceeds the length: a badge
  `Past the clip’s end` (`data-tone="warn"`, `alert-triangle`) in its row.
- **What is not checked.** `checkRestore` is unchanged: an Undo goes back to what was read, and a read cut past
  the end is the render's business.
- **The key** is the media address, which carries `v` = `mtime`, so a replaced file is a new key. Lengths
  survive Reset, closing and moves. They go when the editor unmounts.

**Rationale**:
- **Why the browser's length is safe here.** It is a read of the file being cut, not an invented value. In the
  spike Chrome's equals ffprobe's format duration, the one `probe/media.py` `_parse_duration` gives the
  render. Firefox's is 20 to 60 ms longer. Both err towards accepting, so the check never refuses a cut the
  render keeps in full. In Firefox, a To past ffprobe's end by under 60 ms is accepted, and the render clamps
  it, as D-14 already says.
- **No second source.** No server duration exists, and adding one is an API decision (D-14's open question)
  that this change does not need.

### What the browser cannot do: by cause, with one byte

**Decision**:
- **Codes.** `error` with `MediaError` code 1 (`ABORTED`: our own cleanup) is ignored. Codes 2, 3 and 4 put the
  preview in `checking`, and `checkClipMedia(src, signal)` runs, once (`api/clipMedia.ts`):

  ```ts
  export type MediaCheck =
    | { kind: 'served'; lastModified: string | null } // 206 or 200: the file is served; its `Last-Modified`
    | { kind: 'empty' }                   // 416: no first byte (a zero-byte file)
    | { kind: 'problem'; problem: Problem } // 404 / 502 in the problem shape
    | Unanswered                          // fetch rejected, or a status or body the route does not publish
  /** One `GET` with `Range: bytes=0-0` and `cache: 'no-store'`. Rethrows `AbortError`. */
  export async function checkClipMedia(src: string, signal: AbortSignal): Promise<MediaCheck>
  ```

- **`served` is split by the file's age.** `api/clipMedia.ts` also exports
  `changedSince(mtime: string | null, lastModified: string | null): boolean`. It is true when both are present
  and differ in whole seconds. The detail's `mtime` (`api/events_read.py` 300-312: a UTC `datetime`, `…Z`, with
  microseconds) is read from its first 19 characters plus `Z`, and `Last-Modified` (Starlette's
  `formatdate`, whole seconds) with `Date.parse`. When it is true, the cause is **changed on disk since the
  page was read**. Otherwise it is **a format this browser does not play**. The reason it matters is in
  `docs/research/browser-playback.md` (from `movie-player-screen`'s spike, landed by `media-endpoints`): after a
  file is replaced, Chrome fails a new element at the **same** address with `MediaError` 3, probably because its
  media cache keeps the old file's ranges. Calling that a format problem would send
  the operator to another browser instead of to Refresh. Both stats follow symbolic links (the detail's facts
  and the route's `os.stat`), so a linked clip compares its target's time on both sides.
- **After `loadedmetadata`**, two notes:
  - `videoWidth === 0` → **no picture**
  - `'mozHasAudio' in video && video.mozHasAudio === false` → **no sound**. Firefox only, so there is no
    equivalent elsewhere, and `canPlayType` says nothing about PCM (R0).
- **Announcing.** Each failure or note is announced once, through `onAnnounce`, as `<title>. <detail>`, and is
  shown in an `Alert` with `role="note"`. Never an alert role: a preview's limits are content, not a failure
  of the page (the spec's "announce each change once"). This differs from the movie player (D-15), whose
  playback failures are alerts: Edit mode already speaks every edit through its one polite live region, and an
  assertive alert there would cut those announcements off. D-16 records the difference, so that neither player
  is later "fixed" to match the other.
- **Focus.** When the failure removes the control that held focus, a layout effect moves it to Close.

**Rationale**:
- A media element hides the status (R0, `media-endpoints` design). One-byte reads are cheap, idempotent, and
  answered by the same lookup, so the page can tell the operator what to do: refresh, nothing to play, the
  folder's failure kind, another browser, or retry.
- No retry loop: Try again only for no answer.

### Locks, moves and Reset

**Decision**:
- **`locked`** gives Set From and Set To `aria-disabled` and makes `onSet` a no-op. Play, the slider, Skip cuts
  and Close never lock: they change nothing to save. The `media-endpoints` contract says a save in flight, a
  failed save, a draft or the lock must not close or reload the element.
- **A move within a chapter** moves the `li` with React's `insertBefore`. The element stays in the document, so
  playback goes on.
- **A move into another chapter** (a drop, or Move clips) mounts the panel anew. The store still says open, so
  the new `ClipPreview` reopens, paused, at the kept playhead. It takes no focus (the store's focus request was
  taken at the first open) and scrolls nothing. After a drop, `cross-chapter-drag` focuses the handle and
  scrolls so the handle and the row's first line are visible. With an open preview the row is taller than the
  space between the header or chapter heading and the save bar at 390 × 844 and 320 × 700, so only its first
  line is promised, and the preview under it may lie partly outside the view. After Move clips, focus stays on
  Move clips (G1).
- **Hiding the panel** (`open` false) closes the preview in a layout effect, before the hidden region could
  keep playing sound.
- **Reset** goes through `clear()`, which calls `hideAll()`.
- **A successful save** leaves Edit mode, which unmounts the editor and the preview.
- **No other video to pause.** Edit mode shows no movie player (Context), and one preview is open at a time, so
  Edit mode holds at most one video element, and the preview never has to pause another one (Principle VII: no
  rule for a case that cannot occur).

### Opening, closing and focus

**Decision**:

| Action | Effect | Focus after | Announced |
|---|---|---|---|
| Watch in the panel (closed) | `previews.show(identity, 'toggle')`; another clip's preview closes | the new Play (the store's focus request, taken by `ClipPreview`) | nothing beyond the toggle's state |
| Watch in the panel (open) | `previews.hide(identity)` | stays on Watch | nothing |
| the thumbnail's Watch | shows the panel if hidden; `previews.show(identity, 'thumb')`; another clip's preview closes | Play (also when the preview was already open) | nothing |
| Close, or Escape anywhere in the region | `hide` | the opener: the panel's Watch (request `preview-toggle`) or the row's thumbnail | nothing |
| the Cuts control hides the panel | `hide` (layout effect) | stays on the Cuts control | nothing |
| Play / Pause, keys on the slider, Skip cuts | as named | stays | nothing (state changes are read from the control) |
| Set From / Set To | the field | stays | `From set to 0:01.234.` |
| a failure removes the transport | the Alert | Close, when focus was inside | the failure, once |
| another clip's Watch or thumbnail pressed | this one closes | the other's Play | nothing |
| a move into another chapter | reopens paused at the kept playhead | the handle after a drop, Move clips after Move clips (not the preview's) | as the move announces |

The panel's existing `focusAfter` layout effect gains the `preview-toggle` target; Play's focus is the store's
request, so that the thumbnail can ask for it too. When `ClipPreview` takes that request, a passive effect after
it brings the region into view whole (`block: 'nearest'`), under the page's scroll padding (header, chapter
heading, save bar), as the panel's own scroll does for its targets. A remount after a move takes no request, so
it scrolls nothing and leaves `cross-chapter-drag`'s handle scroll alone. Under reduced motion every
`scrollIntoView` is instant, as today.

### Copy

`<name>` is the clip's name as its row names it. Times are `formatTime`'s.

| Where | Words |
|---|---|
| Watch control (panel) | `Watch`; name `Watch <name>` |
| thumbnail in Edit mode | no words of its own (the frame, or the "No preview" box); name `Watch <name>` |
| region | name `Player for <name>` |
| Close / Play / Pause | names `Close the player of <name>` / `Play <name>` / `Pause <name>` |
| loading (on the picture) | `Loading…` |
| time (visible) | `0:01.234 / 0:06.02`; `0:00 / —` before the length |
| playhead | name `Playhead of <name>`; value `0:01.234 of 0:06.02`, `…, in cut 2` |
| playhead keys (its description) | Arrows move 0.1 seconds, Page Up and Page Down one second, Home and End to the start and the end. |
| Skip cuts | `Skip cuts`; name `Skip cuts of <name>`; pressed or not |
| Set From / Set To | `Set From` / `Set To`; names `Set From at the playhead of <name>` / `Set To at the playhead of <name>` |
| after Set From / Set To (announced) | `From set to 0:01.234.` / `To set to 0:02.5.` |
| legend | `Cut` · `Removed when you save` · `Typed, not added` |
| all cut, Play with Skip cuts (announced) | `Nothing plays: the cuts cover the whole clip.` |
| length hint (known) | `Seconds (75.5), m:ss (1:15.5) or h:mm:ss (1:01:15.5). This clip ends at 0:06.02, as this browser reads it: a cut must end by then, and a cut over the whole clip leaves the clip out of the movie.` |
| length hint (unknown) | `CUT_HINT`, unchanged |
| refused, end | `This cut ends at 0:07, after the clip’s end at 0:06.02. Type an end up to 0:06.02.` |
| refused, start | `This cut starts at 0:07, at or after the clip’s end at 0:06.02. A cut must start before the clip ends.` |
| listed cut past the end (badge) | `Past the clip’s end` |
| no sound (note) | **No sound in this browser.** This browser finds no sound it can play in `<name>`. If a Sony camera recorded it, its sound is PCM, which Firefox does not play and Chrome does; the render keeps it. |
| no picture (note) | **This browser cannot show the picture of `<name>`.** It reads the clip but not its video format. The clip is unchanged on disk. Action: `Download <file name>` |
| 404 | **`<name>` is no longer on disk.** The service's detail, then: Stop editing (save first if you want to keep your edits) to read the event again, then open the player anew. |
| 200 / 206, `Last-Modified` not the page's `mtime` | **`<name>` changed on disk since the page was read.** Stop editing (save first if you want to keep your edits) to read the event again, then open the player anew. |
| 416 | **The file of `<name>` is empty.** There is nothing to play. |
| 502 | **`<name>` could not be read** + the failure kind's pill (`FAILURE_LABEL`) when there is one. The service's detail. |
| 200 / 206, same time | **This browser cannot play `<name>`.** Its format is not one this browser plays. The clip is unchanged on disk. Action: `Download <file name>` |
| no usable answer | `unansweredFailure`'s cause and detail. Action: `Try again` |

The two "Stop editing" rows never say "Refresh": in Edit mode the header's Refresh asks about unsaved changes and
then leaves Edit mode (`EventDetail.tsx` 265), which the words name instead. The note changes nothing itself;
the draft and the typed cuts stay until the operator acts.

`Download` is an `<a class="btn btn-secondary btn-compact" href={src} download={fileName(identity)}>`, with the
`download` icon before its words. The same
origin makes `download` save the file under its own name, whatever the route's `Content-Disposition: inline`.

### Layout, look and motion

`preview/preview.css`, in `@layer screens`, uses tokens only and no new colour. It is imported by
`ClipPreview.tsx`.

```css
.preview-toggle { justify-self: start; }
.clip-preview { display: grid; gap: var(--s-2); max-inline-size: 40rem; }
.preview-head { display: flex; align-items: center; justify-content: space-between; gap: var(--s-2); }
.preview-time { min-inline-size: 15ch; color: var(--fg-muted); font-family: var(--font-mono);
  font-size: var(--text-sm); font-variant-numeric: tabular-nums; white-space: nowrap; }
.preview-stage { position: relative; aspect-ratio: 16 / 9; max-block-size: 22.5rem;
  border-radius: var(--r-md); overflow: hidden; background: var(--media-bg);
  box-shadow: inset 0 0 0 1px var(--border); }
.preview-video { display: block; inline-size: 100%; block-size: 100%; object-fit: contain; }
.preview-status { position: absolute; inset-block-end: var(--s-2); inset-inline-start: var(--s-2);
  padding: 0.125rem var(--s-2); border-radius: var(--r-sm); background: var(--surface-raised);
  color: var(--fg-muted); font-size: var(--text-sm); }
.preview-transport { display: flex; align-items: center; gap: var(--s-2); }
.cut-bar { position: relative; flex: 1; min-inline-size: 0; block-size: 1.75rem; cursor: pointer;
  touch-action: pan-y; border-radius: var(--r-sm); }
.cut-bar:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.cut-bar[aria-disabled='true'] { cursor: default; }
.cut-bar-track { position: absolute; inset-inline: 0; inset-block-start: calc(50% - 0.1875rem);
  block-size: 0.375rem; border-radius: var(--r-full); background: var(--surface);
  box-shadow: inset 0 0 0 1px var(--border-strong); }
.cut-bar-span { position: absolute; inset-block-start: calc(50% - 0.375rem); block-size: 0.75rem;
  inset-inline-start: var(--from); inline-size: max(2px, calc(var(--to) - var(--from))); border-radius: 2px; }
:is(.cut-bar-span, .cut-bar-swatch)[data-kind='cut'] { background: var(--err); }
:is(.cut-bar-span, .cut-bar-swatch)[data-kind='removed'] { border: 1.5px dashed var(--fg-muted); }
:is(.cut-bar-span, .cut-bar-swatch)[data-kind='typed'] { border: 2px solid var(--accent);
  background: var(--accent-soft); }
.cut-bar-head { position: absolute; inset-block: 0.125rem; inset-inline-start: var(--at); inline-size: 2px;
  translate: -1px 0; background: var(--fg); pointer-events: none;
  &::before { content: ''; position: absolute; inset-block-start: -0.125rem; inset-inline-start: -5px;
    inline-size: 0.75rem; block-size: 0.75rem; border-radius: 50%; background: var(--fg);
    box-shadow: 0 0 0 2px var(--surface-2); } }
.preview-legend { display: flex; flex-wrap: wrap; gap: var(--s-1) var(--s-3); list-style: none;
  color: var(--fg-muted); font-size: var(--text-xs); }
.cut-bar-swatch { display: inline-block; inline-size: 1rem; block-size: 0.625rem;
  margin-inline-end: var(--s-1); vertical-align: middle; border-radius: 2px; }
.preview-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); }
/* `.btn` draws from its own custom properties (components.css 26-41). */
.preview-skip[aria-pressed='true'] { --_border: var(--accent); --_bg: var(--accent-soft);
  --_bg-hover: var(--accent-soft); --_fg: var(--info-fg); }
@media (pointer: coarse) {
  .cut-bar { block-size: 2.75rem; }
  .preview-actions { row-gap: var(--s-4); }
}
@media (forced-colors: active) {
  .cut-bar-span[data-kind='cut'], .cut-bar-swatch[data-kind='cut'], .cut-bar-head { background: CanvasText; }
  :is(.cut-bar-span, .cut-bar-swatch)[data-kind='typed'] { border-color: Highlight; }
}
```

- **Sizes.**
  - At 1280 px the panel spans the row from its file column (G2), so the stage is 640 × 360.
  - At 320 px the stage is the panel's width, about 224 px by 126.
  - Its box is set by `aspect-ratio` before any byte arrives, so `loadedmetadata` moves nothing.
  - A portrait or rotated clip is letterboxed inside it (`object-fit: contain`), as thumbnails are.
- **Never colour alone.** A cut is a solid bar, a removed one a dashed outline, a typed one an accent outline
  with a soft fill. The legend names each in words, and the slider's text says "in cut n". Skip cuts shows
  `aria-pressed` with an accent border and fill, not only a colour.
- **Contrast.** Task 4.2 measures these at least 3:1 against the track: `--err` (light about 4:1 on
  `--surface`, dark about 6:1), the dashed `--fg-muted` and the `--accent` outline. It also measures the legend
  and time text at 4.5:1 on `--surface-2`, and the stage against `--media-bg`, black in both schemes: the
  `Loading…` words at 4.5:1 on their badge, and the badge at 3:1 against the black stage.
- **The stage colour** is `--media-bg`, the token `movie-player-screen` specifies:
  `--media-bg: light-dark(oklch(0% 0 0), oklch(0% 0 0));` under Neutrals in `tokens.css`, with the comment
  "behind a video picture: black in both schemes, as every player letterboxes". Whichever of the two changes
  lands first adds it, with exactly that value and comment; the other finds it (task 1.1 notes which). No
  fallback, so the stage is black in both schemes whatever the landing order.
- **Touch.** Under a coarse pointer the slider is 44 px tall across its width. Play's `.btn::after` area reaches
  6 px into the transport's 8 px gap, and the actions wrap with a 1 rem row gap (components.css's rule for
  stacked buttons). Close's area reaches 6 px into the 8 px gap above the stage.
- **Motion.** No `transition` or `animation` in `preview.css`. The head moves with the video's time only.

### Performance

- **Before Watch: no `<video>`.** Rows mount nothing new but the thumbnail's button. `ClipRow` passes `eventId`
  and `clip.mtime` (two strings) to `CutsPanel` and a stable `onWatch` to `RowBody`, so a drag step's row shells
  do the same work as before, and `RowBody` still skips.
- **While playing:**
  - the per-frame time is `ClipPreview`'s own state
  - `CutsPanel` re-renders only when its two store reads change: open and length
  - no `ClipRow`, `ClipOrderList` or `EventEditor` commit follows a frame
  - typing in Title re-renders no list, as G1 and G2 require
- **Measuring.** Task 4.3 measures on `Stor dag` with `cross-chapter-drag`'s commit hook, adding `section.clip-preview`
  (`ClipPreview`) and `div.clip-cuts` (`CutsPanel`) to its host-child table.

### Files and the seams

| File | Change |
|---|---|
| `api/clipMedia.ts` (new) | `clipMediaUrl(eventId, clip)`, checked against the generated `paths` like `thumbnail.ts`; `MediaCheck`, `checkClipMedia`, `changedSince` |
| `preview/previews.ts` (new, pure) | `ClipPreviews`, `createClipPreviews` |
| `preview/playback.ts` (new, pure, type-only imports) | `Skip`, `skipSpans`, `skipAt`, `playFrom`, `seekKey`, `along`, `playheadWords`, `typedSpan`, and the preview's copy |
| `preview/ClipPreview.tsx` (new) | `ClipPreview` (`memo`), `CutBar`, `usePreviewOpen`, `useClipLength` |
| `preview/preview.css` (new) | the rules above, and `.clip-thumb-watch` |
| `cuts/times.ts` | `checkCut`'s `length`, the `past-end` refusal and words, `lengthHint`, `pastEnd`, `PAST_END` |
| `cuts/CutsPanel.tsx` | `CutPanels.previews`; props `eventId`, `mtime`; the Watch toggle; `ClipPreview`; `onSet`; length into `checkCut`, the hint and the badge; the `preview-toggle` focus target and the return to the row's thumbnail |
| `edit/ClipOrderList.tsx` | `ClipRow` passes `eventId` and `clip.mtime` to `CutsPanel`, and a stable `onWatch` to `RowBody` for a cuttable clip; `RowBody` wraps the thumbnail in the Watch button when given `onWatch` |
| `styles/tokens.css` | `--media-bg`, only when `movie-player-screen` has not added it already |
| `edit/EventEditor.tsx` | the store gains `previews` (`createClipPreviews()`), and `clear` calls `hideAll()` |
| `ui/Icon.tsx` | `pause`, `skip-forward`, `download` (Lucide 1.49.0, ISC; all three are Feather-derived, so they join the MIT list) |
| `web/README.md`, `docs/high-level-design.md` | docs |

The Lucide path data (`lucide-static` 1.49.0, `icons/*.svg`):
- `pause`: `<rect x="14" y="3" width="5" height="18" rx="1"/><rect x="5" y="3" width="5" height="18" rx="1"/>`
- `skip-forward`: `<path d="M21 4v16"/><path d="M6.029 4.285A2 2 0 0 0 3 6v12a2 2 0 0 0 3.029 1.715l9.997-5.998a2 2 0 0 0 .003-3.432z"/>`
- `download`: `<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>`

**`movie-player-screen` seam.** Both changes are written in parallel and archive in an order not known in
advance.
- **Files.** This change owns `preview/**` and `api/clipMedia.ts`, and it does not touch the event page's read
  view. `movie-player-screen` owns `movie/**`, `api/movie.ts` and `api/headers.ts`, and adds no icon (its
  proposal, "Impact").
- **Shared.** HLD §7 and §4.10 and `web/README.md` are shared. Whichever change archives second re-reads them on
  main and keeps the other's lines. Task 1.1 still checks `Icon.tsx` for the three icons, in case that plan
  changes.
- **The stage colour.** Whichever change lands first adds `--media-bg` with `movie-player-screen`'s exact value
  and comment ("Layout, look and motion"), and the stage reads plain `var(--media-bg)`. Both players letterbox
  alike in either order, and this change's contrast checks run against black.
- **One-byte checks.** `movie-player-screen` has its own one-byte read of `/movie` (`api/movie.ts`, with
  `api/headers.ts`). Both map the same answers to the same kinds. Whichever change lands second reuses the
  other's status mapping (and `contentRangeSize`) rather than restating it, and the response-to-kind table stays
  identical (task 1.1). The two changes' trouble words stay separate vocabularies.
- **The download icon.** This change adds `download` to `Icon.tsx` and uses it on its Download. If
  `movie-player-screen` lands second, its "Download the movie" uses it too.

### HLD

`docs/high-level-design.md` §7 gains, after D-15 when it is there and after D-14 otherwise:

> **D-16 — A clip is previewed in Edit mode in GUI v1** (2026-10-01, change `clip-preview-screen`).
> - **What.** A clip's Cuts panel plays the clip itself, its file streamed unchanged by the media route
>   (`media-endpoints`, §4.9). Its Watch control, or one press on the clip's thumbnail in Edit mode, opens it.
>   It has a cut bar, Set From and Set To at the playhead (to the millisecond, written as typed times, D-14),
>   and Skip cuts, which plays the clip as the movie will (the render's merge, D-D), showing no frame that lies
>   wholly inside a cut; a cut within 0.1 s of the clip's end stops playback at its start.
> - **Loading.** A `<video>` exists only while a preview is open, one at a time: Edit mode holds at most one
>   video, and shows no movie player (D-15).
> - **Notes, not alerts.** What the browser cannot do is said by cause in a note, announced through Edit mode's
>   one live region (polite) rather than as an alert, unlike D-15's playback failures, because Edit mode already
>   speaks every edit there.
> - **The length.** The length the browser reads from the file refuses a cut that ends past the clip's end,
>   for that clip, while Edit mode stays open. The API still carries no duration, so a clip never previewed
>   keeps D-14's rule. Measured on five files: Chrome's length equals ffprobe's, and Firefox's runs up to 60 ms
>   longer, never shorter, so the check never refused a cut the render keeps in full.
> - **What stays v2.** Firefox plays PCM audio silently (52 % of the archive), and the preview says so. Proxies,
>   the PCM audio path, scrubbing and drag-trim stay the v2 timeline editor's (§4.10, §8.11).

D-14's sentences change too:
- "It cannot refuse a cut past the clip's end, because no probe-free read gives a duration" gains "unless the
  clip was previewed in that Edit mode (D-16)".
- Its "previews" wording, as `media-endpoints` leaves it, becomes "a clip's preview followed in GUI v1 (D-16).
  Scrubbing and drag-trim are the v2 timeline editor's."

§4.10's v1 bullet gains "**a clip's preview with Set From / Set To** (**D-16**)", and slice row D gains a
sentence naming this change. Both are re-read on main first, since `media-endpoints`, `cross-chapter-drag` and
`movie-player-screen` all edit §4.10.

### Verification fixtures

The implementing agent's own environment (dev-env runbook §9):

| Item | Value |
|---|---|
| `SLUG` | `clip-preview-screen` |
| database | `arel_clip_preview_screen` |
| library | `../dev-clip-preview-screen` |
| `serve` | port **8131**, over a fresh `npm run build`, no worker |
| browsers | Chrome (channel `chrome`) in `localhost/playback-research:chrome`, and that image's Firefox 132; never Playwright's stock Chromium for playback |

In that library copy only:
- **`2024/2024-05-19 - Provklipp`**: symbolic links to each of the ten files in `../auto-reel-media/samples/`,
  never copies or moves (the recipe of `media-endpoints` task 6.1).
- **`2024/2024-09-15 - Stor dag`**: `cross-chapter-drag`'s recipe. That is 400 links `c0001.mp4`…`c0400.mp4`
  to one cut clip, plus `Kväll/k001.mp4`…`k003.mp4`, and no `reel.yaml`.
- **`reel.yaml` fixtures, each applied only for the scenarios that state it:**
  - Grillning `s1710003.mp4: {trims: [{in: 0, out: 1.2, reason: black}]}` (G2's)
  - Grillning `s1710002.mp4: {trims: [{in: 3723.125, out: 3725.5}]}` (G2's layout fixture, for the past-end
    badge)
  - Grillning `s1710002.mp4` cuts `[1, 2]` and `[5, 6.02]`, and `s1710001.mp4` `[0, 6.02]`, for the skip
    scenarios, added through the panel rather than by hand where the scenario says "has a cut"
- Every `reel.yaml` a check `diff`s is normalised first (G1's rule: `YAML()` with
  `indent(mapping=2, sequence=4, offset=2)`), copied, and restored afterwards.
- Two containers that share a mount use `:z`.

## Failure behavior & idempotency

- **Nothing renders, enqueues, probes or writes.** A preview's requests are reads of one file. There is no job,
  so a `--force` run and a worker restart do not concern it, and a re-run (reopening a preview) reads the same
  bytes. A cut set at the
  playhead is saved by G2's single `PUT` with `If-Match`, and every save failure keeps the draft and the typed
  text, as today. The preview stays open through a failed save. A successful save leaves Edit mode.
- **The browser cannot play the clip.** One one-byte check, then words by cause. No automatic retry. Try again
  (no answer only) remounts the element.
- **The service goes away mid-play.** The element stalls or raises `MediaError` 2, and the check then answers
  `unreachable` with Try again. No partial state exists to clean up.
- **Opening the same preview twice, a StrictMode remount, or a remount after a move** each set the source once
  more, and the cleanup aborts the earlier one. No two elements play one clip.
- **A clip replaced on disk while Edit mode is open.** The address keeps the `v` the page read, so the
  browser may hold the old file's ranges under it. `movie-player-screen`'s spike (recorded in
  `docs/research/browser-playback.md`) saw Chrome fail such an element with `MediaError` 3. The check then finds
  a `Last-Modified` that is not the page's `mtime` and says that the clip changed on disk, advising to stop
  editing (saving first) and read the event again. The draft is untouched until the operator acts. The next
  read gives a new `mtime`, which gives a new address, and with it a new length key.

## Risks / Trade-offs

- **[Firefox reads lengths up to 60 ms long]** → A To in that tail is accepted, and the render clamps it, as
  D-14 already says. The alternative, a server duration, is an API decision for later.
- **[A length reported as `Infinity` or `NaN`]** (a file the browser cannot index) → No length is kept, and the
  panel keeps D-14's words. Nothing is invented.
- **[One more tab stop per row]** The thumbnail's Watch adds a stop to every cuttable row (400 on `Stor dag`).
  → Accepted by the supervisor for the one-press path. The skip control and the chapter headings still jump
  past long lists, and the row's grid and sizes do not change.
- **[A failed thumbnail's visible words]** Its box shows "No preview" while the button is named "Watch <name>".
  → Accepted: a speech-input user says "Watch", the control's name, and a screen reader hears only the button's
  name, so the two words never reach it as two controls.
- **[The skip shows one frame of a cut in a browser whose frame step changes mid-clip]** (variable frame rate)
  → The step is measured per frame, so a wrong guess shows at most one frame. The archive's clips are constant
  frame rate (R0).
- **[A cut that ends between two frames]** → Chrome shows the one frame that straddles the cut's end, as the
  next frame after the jump. It is not wholly inside the cut, and the rule never seeks for it again (review
  spike: one seek, playback goes on).
- **[A cut that ends 1 to 99 ms before the browser's end]** → The preview stops at the cut's start, while the
  movie keeps those few frames. The slack covers the browsers' longer lengths (up to 58 ms measured). Without
  it, a cut that ends at the render's end shows the cut's last frames.
- **[A slow USB drive]** → The first open of a moov-at-end clip costs a tail read plus data (R0 §7). The poster
  shows at once, and "Loading…" says why the picture waits. Only one preview is ever loading.
- **[An HEVC clip outside `original/`]** → None exist in the archive (R0). If one appears, Chrome says "no
  picture" and Firefox "cannot play", and both offer the file.
- **[Set From while playing lands between frames]** → It is written to the millisecond, and the render cuts at
  that time. The operator pauses first for a frame-exact choice, and the slider's 0.1 s steps make that easy.
- **[A preview playing while its row is dragged]** → The placeholder keeps its panel and the video plays on. A
  cross-chapter drop reopens it paused at the same time.

## Migration Plan

- None: no data, schema or API change. Rebuild `web/dist` with the `web/README.md` container command.
- Rollback: revert the web change. Cuts saved meanwhile are ordinary `reel.yaml` trims.

## Open Questions

None that change the specs, the approach or the tasks. Deferred, by design:
- A server-side clip duration (D-14's open question): it would extend the length check to clips never
  previewed.
- One shared media-failure helper with `movie-player-screen`, beyond reusing the status mapping (task 1.1).
