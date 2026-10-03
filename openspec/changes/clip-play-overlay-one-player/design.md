## Context

See proposal.md, "Why". Code on `origin/main` `143f0fc`:

- **The read view's control** is `WatchButton` in `web/src/events/ClipWatch.tsx`: a text button ("Watch" / "Hide player")
  in `td.cell-file`, between `ClipName` and `ReadCuts` (`EventDetail.tsx`, `ChapterPanel`). It subscribes to the preview
  store with `usePreviewOpen(previews, identity)`, opens with `previews.show(identity, 'toggle')`, closes with
  `previews.hide(identity)`. Its id (`watchId`) is where Close and Escape return focus, and its `aria-controls` is the
  player region (`playerId`). `PlayerRow` and `OpenPlayer` are untouched by this change.
- **The thumbnail** is `ClipThumb` (`events/ClipThumb.tsx`): a `span.clip-thumb` box (`events/thumbs.css`: `position:
  relative`, 16:9, `overflow: hidden`, an inset edge in `::after`) whose child is the image or the "No preview" box.
  A missing clip renders an empty hidden box. Its width is the cell's: 128 px at 1280, `--clip-thumb-w` (5rem = 80 px)
  below 1024 and in the card layout, so the box is at least 80 x 45.
- **Edit mode's thumbnail** is already a button around `ClipThumb` (`edit/ClipOrderList.tsx`, `.clip-thumb-watch` in
  `preview/preview.css`), named "Watch <name>". It stays.
- **Two "one video" mechanisms.** `playback/exclusive.ts` is a registry (`claimPlayback` / `releasePlayback`): the Movie
  section's `<video onPlay>` and `useTimelineVideo` call it. `events/onePlayer.ts` (`keepOneVideoPlaying(documentRoot(document))`)
  is a capturing `play` listener that `EventDetailBody` installs in an effect, so it covers every `<video>` below the
  event page, and covers the Timeline and the Movie player twice.
- **The Timeline's video** is one element whose file is swapped at clip boundaries (`useTimelineVideo`: `advance`,
  `swapping`, `afterSettle`, `startVideo`). An external `pause` already stops it cleanly: `onPause` clears `wantPlay`
  and the playing state unless the hook paused it itself, a swap, a scrub or an end.
- **No component test runner exists.** Pure modules run under `node --test` (`npm test`, `tsconfig.test.json`), the rest
  is `tsc`, the production build and Playwright from the scratchpad.

## Goals / Non-Goals

**Goals:**
- A clip is played by pressing its frame, with a control that says so to a mouse, a finger, a keyboard and a screen reader.
- Starting any video of the page pauses every other one, by one rule that names no player.
- The row loses a line and gains nothing; the 400-clip event stays as cheap as it was.

**Non-Goals:**
- Edit mode's thumbnail, the player's controls, a playlist, resuming a paused player, closing one on another's start.

## Research & Decisions

### The control is named "Play <name>", and renames itself while its player is open

**Context**: `clip-play-read-view` chose "Watch" because the open player holds a button named "Play <name>" /
"Pause <name>" (`playName` in `preview/playback.ts`); the operator now asks for "a play button on the clip".
**Explored**: (a) keep "Watch <name>" as the name on a play-looking glyph: the glyph says play and the name says watch,
and the plan and the request both say Play; (b) "Play <name>" at all times: two controls with one name while the
player is open; (c) "Play <name>" while closed, and while open the control is "Hide player of <name>" with the hide icon
(the name it already has when open).
**Decision**: (c). The collision (b) needs both controls to exist, which happens only while the player is open, and then
the control has another name; at no time do two controls share a name. A pure `thumbControlName(name, open)` in
`events/watch.ts` makes that testable: for any name, the open name equals neither `playName(name, false)` nor
`playName(name, true)`.
**Rationale**: the operator's word is used, the earlier reason is kept, and the open state keeps the words the page has
used for it since `clip-play-read-view`.

### The control is inside the thumbnail's box, filling it

**Explored**: (a) a button around `ClipThumb`, as Edit mode does: the button's name replaces the image's alternative
text, the "No preview" box is inside a button, and one more wrapper changes the box; (b) a sibling positioned against
the cell: the cell is wider than the box in some layouts; (c) an `overlay` slot on `ClipThumb`, rendered as the last child
of the box, `position: absolute; inset: 0`.
**Decision**: (c). `ClipThumb` takes `overlay?: ReactNode` and renders it inside `.clip-thumb` for every state but
missing (which the caller does not pass one for). The image keeps "Frame from <name>"; the failed state keeps its
"No preview" box and role; the control is over both. The button is `inline-size/block-size: 100%`, so the box's edge and
the control's are the same, and the 44 x 44 rule is met by the box itself (80 x 45 minimum), with no extra tap area to
engineer and nothing reaching a neighbour.
**Cost**: the box clips (`overflow: hidden`), so the focus ring is drawn inside it (`outline-offset: -3px`, token
`--focus-ring`, 2px). **Rationale**: the thumbnail's size, place and requests stay as the thumbnail requirement says; a
focus ring over a frame needs a contrasting edge, so the glyph's disc and the ring both use a surface-colored ring.

### When the glyph is seen

**Decision**: the control is never `display: none`, `visibility: hidden` or `inert`; only the glyph's `opacity` changes:
`0` under `@media (hover: hover) and (pointer: fine)` and `1` on `:hover`, `:focus-visible`, `[aria-expanded='true']`; `1`
everywhere else (coarse pointers, hover-less ones). No `transition`: the page animates nothing. The disc is
`color-mix(in oklab, var(--surface) 88%, transparent)` with `var(--fg)` icon and a 1px `var(--border)` ring, so it reads
over a white frame and a black one; forced-colors uses `Canvas` / `CanvasText` / `ButtonText` as the page's other
overlays do (`detail.css`, the forced-colors block).
**Alternatives**: always visible (rejected by the plan's summary: 400 clips of discs hide the frames); hover only
(unreachable by keyboard and touch). **Risk**: a mouse operator does not see the control until the pointer is over a
frame. Mitigation: `cursor: pointer` on the frame, the glyph appears at once, and the screenshots of task 4.2 show the
idle state; if it fails the look-check, the idle opacity is a one-line change that the specs permit ("MAY be unseen").

### One coordinator, driven by the `play` event, installed once

**Context**: the page has four players (Movie section, a read-view clip's player, Edit mode's preview, the Timeline's
video) and `exclusive.ts` + `onePlayer.ts` cover them by overlapping rules.
**Explored**: (a) extend `exclusive.ts` so the clip players claim too: every player calls into it, and the next one
forgets; (b) a wrapper for `video.play()`: the Movie section's native controls and a browser's media keys start a video
without calling any wrapper; (c) the `play` event on the document, captured: it fires whenever `paused` becomes false,
however the video was started, does not bubble (so capture), and is not fired by a seek or a `load()`.
**Decision**: (c), the mechanism `onePlayer.ts` already has, moved to `playback/coordinator.ts` and installed once in
`main.tsx` before the first render (a module-level call, not a component effect), so it spans every screen and every
player and outlives every remount. `exclusive.ts`, `onePlayer.ts` and their tests are deleted; the `claimPlayback` call on
the Movie section's `onPlay`, the claim and release calls in `useTimelineVideo`, and the effect in `EventDetailBody` go.
The module keeps `onePlayer.ts`'s structural types (`PausableVideo`, `VideoRoot`) so `npm test` runs it with stand-ins:
`pauseOthers(started, videos)`, `keepOneVideoPlaying(root)`, `documentRoot(document)`, and one new pure function,
`anotherPlays(self, videos)`.
**Rationale**: one rule, one place, no player named; a fifth player is covered by being a `<video>`.
**Cost**: timing. `play()` flips `paused` and queues the event, so the other video plays for one task longer than with
the claim in `startVideo`, before the `play()` call; a task is far below a frame's worth of audible overlap. Measured in
task 4.1 (the other video's time does not advance past the start by more than one frame).

### The Timeline does not take playback back after a swap

**Context**: the Timeline is one `<video>` whose file is swapped at clip boundaries; the browser pauses it on the swap
and the hook calls `play()` again once the new file is ready (`afterSettle` -> `startVideo`). That `play()` fires a `play`
event, a start like any other. If the operator started another video during the swap (the hook ignores the `pause` it
sees while `swapping`), the resume would be the later start and would pause the video the operator just started.
**Decision**: the hook asks `anotherPlays(video, document videos)` before a resume that the operator did not ask for
(an `afterSettle` start after a swap or a settled seek while `wantPlay` was already true): when another video plays,
it clears `wantPlay`, sets the playing state to false and does not call `play()`. The operator's own Play always starts and
always pauses the others. No other player's code changes.
**Alternatives**: ignore it (a rare race that ends with the Timeline playing and the operator's video paused: the
opposite of what the operator did last); keep a per-player flag in the coordinator ("who was started by a person"):
the browser cannot tell a person's `play()` from a script's, so the flag would be per-pair code in disguise.

### Which videos the coordinator touches

**Decision**: every `<video>` of the document that is not `paused` and is not the one that started. A paused or ended video
is never touched (`pause()` on a paused video is harmless, but it is not called, so no `pause` event is raised for a
video that was not playing, which `ClipPreview` and the Timeline would read as an operator's pause). Nothing is closed,
replaced, restarted or seeked; no announcement. A pending `play()` of the paused video rejects with `AbortError`: the
Timeline already ignores it, `ClipPreview` swallows it, the Movie section's native controls are not promise-driven.
**Edit mode** holds one video at a time by releasing the Timeline's video when a preview opens ("Edit mode holds one
video at a time"); the coordinator is the safety net there and decides nothing.

### Where the control's pieces live

`events/watch.ts` (pure) gains `thumbControlName`; `events/ClipWatch.tsx` renames `WatchButton` to `PlayControl`, renders
the glyph and passes through `usePreviewOpen`; `EventDetail.tsx` passes it to `ClipThumb` as `overlay` and drops the
file-cell Watch button; `events/detail.css` loses the `.cell-file > .watch-button` rules and gains the `.clip-play` rules.
Row ids (`watchId`, `playerId`) stay, so Close and Escape return focus with no change; the id is now the overlay's.
`aria-controls` is set only while open, as now.

## Risks / Trade-offs

- **The first press of a hidden glyph by a keyboard user**: the control is in the tab order, and gains its glyph on focus;
  verified in task 4.1.
- **A thumbnail in a dragged row**: the read view has no drag; Edit mode's thumbnails are untouched.
- **Row heights shrink**: the Watch button's line is gone, so rows are shorter by about a line; task 4.2 measures it.
- **The gate**: `time-readouts-legible` may land `preview.css` / `timeline.css` edits; this change touches neither file.
