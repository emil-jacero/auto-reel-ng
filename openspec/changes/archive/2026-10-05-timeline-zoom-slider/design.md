## Context

The Timeline (D-20) is `web/src/timeline/`: a pure model (`model.ts`, `layout.ts`, `cards.ts`, …) tested with
`node:test`, and React components (`TimelineSection.tsx` → `Timeline.tsx` → `Track.tsx`). Its zoom today
(research `scratchpad/research/trim/zoom-perf.md` §1, path:line on `main` e5d3041):

- state `{pps, fitted}` in `Timeline.tsx`; `fit = fitPps(totalMs, range.width)`; effective
  `pps = fitted ? fit : min(MAX_PPS, max(fit, zoom.pps))`; bounds `MIN_PPS 4`, `MAX_PPS 240`, `DEFAULT_PPS 40`
  (`model.ts`);
- `zoomBy(factor)` anchors on the playhead when it is in view, else on the view's centre, through the pure
  `zoomAt(view, factor, anchorX, totalMs)`, and parks the new `scrollLeft` in `pendingScroll`, applied by a
  `useLayoutEffect([pps])` after the commit that widened the canvas; `fitAll()` sets `fitted: true`, scroll 0;
- keys `+ = - _ 0` on `.tl-viewport` (`Track.tsx` → `onTrackKey`); the playhead's `keys.ts` returns null for them;
- no wheel handler, no persistence, no slider.

The track is windowed (`useVisibleRange`, one view width of overscan), so DOM size does not grow with zoom; the canvas
is `inlineSize: totalPx` with `min-inline-size: 100%`. The playhead's grip is centred on its line
(`.tl-grip`: 1.5rem wide at `-0.75rem`; 2.75rem at `-1.375rem` under a coarse pointer); card blocks are at least
`MIN_BLOCK_PX = 24` wide, drawn over neighbours.

`TimelineSection.tsx` serves both views: in the read view (`editing === null`) a closed section with Open/Close and a
words-only card inspector slot; in Edit mode (since `edit-mode-declutter`) open, no button. `EventDetail.tsx`
`ReadyView` mounts the read-view section; `EventEditor.tsx` mounts Edit mode's with `read={NOT_READ}`.

## Goals / Non-Goals

**Goals:**
- A Premiere-like continuous zoom (slider, `\`, Ctrl/Cmd+wheel about the pointer), anchored like today's buttons.
- Fit never shows a horizontal scroll bar in the track's box.
- The toolbar's control boxes never move between idle, seeking, loading, playing and card states.
- The Timeline exists only in Edit mode; the read-view-only code goes.

**Non-Goals:**
- Raising MAX_PPS / frame-level zoom, finer ticks, denser sprites; touch pinch; scrollbar-end zoom handles.
- Any change to trim, ripple, cards' model, the poster model, the engine or the API.

## Decisions

### D1 — The slider maps logarithmically from Fit to MAX_PPS, and never stores its own position

Two pure functions in `model.ts`, beside `clampPps` / `fitPps`:

```ts
/** Slider position (0..SLIDER_STEPS) for a scale; 0 is Fit. Fit ≥ max → 0. */
export function ppsToSlider(pps: number, fit: number, max: number = MAX_PPS): number
/** The scale at a slider position; 0 → fit exactly, SLIDER_STEPS → max exactly; clamped. */
export function sliderToPps(position: number, fit: number, max: number = MAX_PPS): number
export const SLIDER_STEPS = 200
```

`pps = fit · (max/fit)^(s/SLIDER_STEPS)`, inverse `s = SLIDER_STEPS · ln(pps/fit) / ln(max/fit)`, rounded for
display. 200 integer steps: one step is at most (240/4)^(1/200) ≈ 2.07 % (the widest range, a long event fitted at 4);
Arrow keys move one step, PageUp/PageDown the browser's larger step, Home = Fit, End = max — the native range input's
own keyboard, no handler of ours. The position is derived from `pps` on every render (never stored), so buttons, keys,
wheel, Fit-follows-resize and the slider cannot disagree. Position 0 sets `fitted: true` (so Fit keeps following a
resized view), any other position `fitted: false`. When `fit ≥ MAX_PPS` (a short event) the slider is `disabled`
(nothing to zoom), as Zoom in is already `aria-disabled`.

`aria-valuetext` is "Fit" at position 0, else "<n> px per second" with `n` rounded to an integer (`labels.ts`:
`zoomValueText(pps, fitted)`). The input is labelled "Zoom" (`aria-label`), inside the existing `role="group"
aria-label="Zoom"`, between Zoom out and Zoom in.

### D2 — `zoomTo(target, anchorX?)` is the one zoom path; slider input is coalesced per animation frame

`zoomBy(factor)` becomes `zoomTo(pps * factor)`. `zoomTo(target, anchorX?)` clamps to `[fit, MAX_PPS]`, builds the
`View` from the live `el.scrollLeft` / `clientWidth` and the **requested** scale (`ppsRef`, updated synchronously when a
zoom is requested, not only at render — otherwise two requests in one frame anchor on a stale scale and the playhead
drifts; research §3 "Anchoring" caveat), picks the anchor (given `anchorX`, else playhead if `0 ≤ x ≤ width`, else
`width / 2`), calls `zoomAt`, parks `pendingScroll` and `setZoom`. The slider's `input` events store the latest
position in a ref and schedule one `requestAnimationFrame`; the frame calls `zoomTo(sliderToPps(latest, fit))`
(latest wins). Rationale: every `pps` change re-renders Timeline → Track (research §3 "Re-render cost"); one render per
frame is the pattern `useVisibleRange` and the drag store already use. The existing `useLayoutEffect([pps])` applies the
scroll unchanged.

Review (2026-10-05) made each zoom frame cheaper: `zoomTo` also sets the visible range it is about to scroll to
(`useVisibleRange`'s `expect`, a sub-pixel `scrollLeft` rounding reads as no change), so a zoom renders the Timeline
once, not twice; while the slider is dragged the track draws a quarter view of margin on each side instead of a whole
view (`LIVE_OVERSCAN`, back to one view 200 ms after the slider's last zoom); the readout and the card layer are
memoised. A preview of the drag (the drawn layers scaled with `scale`/`translate`, the zoom drawn on a pause and on
release) was tried and dropped: it stretched the text and pictures and did not measurably lower the frame times,
because most of a zoom frame's cost on the 400-clip fixture is the Edit page around the Timeline (see Risks).

A pure helper `anchorFor(playheadX, width, pointerX?)` returns the anchor so the rule is unit-tested; `zoomAt` is
reused as is.

### D3 — Keys, wheel and pinch

- `\` joins `+ = - _ 0` in `Track.tsx`'s viewport key list and `onTrackKey`; `keys.ts` returns null for it (test).
  A pure `trackZoomKey` (`keys.ts`) decides which keydown is a zoom key: never with Cmd, never with Ctrl alone (the
  browser's zoom); a key typed with AltGr (Linux reports AltGraph, Windows Ctrl+Alt together) is the character typed,
  and `\` also takes Alt alone, because macOS types it with Option on Swedish and German layouts.
  `\` at Fit with a remembered previous zoom restores it (anchored like D2); otherwise it remembers the current scale and
  fits. The remembered scale lives in a ref (`beforeFit`), cleared by any other zoom. `TRACK_KEYS` reads
  "+ and - zoom, 0 fits, \ toggles Fit."
- Ctrl+wheel / Meta+wheel on `.tl-viewport`: a **non-passive** `wheel` listener added with `addEventListener(…,
  {passive: false})` (React's `onWheel` is passive and cannot stop the browser's page zoom). Only when
  `ctrlKey || metaKey`: `preventDefault()`, normalise `deltaY` to pixels (`deltaMode` 1 → ×16, 2 → ×view height),
  factor `1.5^(−Δ/100)` clamped to `[1/1.5, 1.5]` per event, `zoomTo(pps·factor, pointerX − viewportLeft)`, coalesced
  per frame like the slider (factors multiply within a frame). Chrome and Firefox deliver a trackpad pinch as
  `wheel` with `ctrlKey: true`, so pinch is the same path. A plain or Shift wheel is left to the browser (scroll).

### D4 — The zoom is remembered per event in `sessionStorage`, best effort

Key `auto-reel:timeline-zoom:<eventId>`, value `{"fitted": bool, "pps": number}`, written (try/catch) when a zoom
settles (the frame that applies it). Read once on mount (try/catch; a missing, unparsable or non-finite value → Fit);
`pps` is re-clamped to `[fit, MAX_PPS]` once the view is measured; scroll starts at 0 with the playhead at the start,
as today. A module-level `Map` mirrors it so a browser that throws on storage still keeps it for the page's life.
`sessionStorage` matches "for the session": it survives a reload in the same tab and Edit mode's remounts (Refresh,
Save, leaving and re-entering), and is gone in a new tab. It is a per-viewer convenience, never read by Claude or the
service.

### D5 — Fit fits the canvas *including* what is drawn at its end

Measure first (task 2.1): at Fit, record `viewport.scrollWidth − clientWidth` with the playhead at the start and at the
end, fine and coarse pointer, an event with black cards at their 24 px minimum, 1280 and 390 px. The known suspects:
(1) the grip's half-width past the canvas end (12 px fine, 22 px coarse); (2) `timeToPx(totalMs, fit)` landing a
fraction above `clientWidth`; (3) a 24 px minimum block or a ruler label extending past the end.

Fix: an **end gutter** equal to the grip's half-width, read from a CSS custom property (`--tl-end-gutter`, 0.75rem /
1.375rem coarse) via `getComputedStyle` once per resize: Fit computes `fitPps(totalMs, clientWidth − gutter)`, the
canvas is `totalPx + gutter` wide (floored to whole pixels), so the grip at the last moment is inside the canvas and
the canvas is never wider than the view at Fit. Anything else the measurement finds overflowing the end (a label, a
block) is kept inside the canvas the same way (positioned from the end, or clamped), not hidden.

Rejected: `overflow-x: clip` on the canvas. It hides the overflow but also cuts the outward half of a coarse-pointer
trim area at the last clip's end (the trim spec requires the area to extend outward from the cut) and the grip's half at
the end.

### D6 — The toolbar is a grid of fixed slots; the poster reason is a tooltip, a description and a press-time tip

`.tl-controls` becomes a CSS grid in the Timeline's size container (one row from 64rem; two from 31rem: Play + readouts
/ zoom + poster; three below: Play + readouts / zoom / poster; the movie stat on a row of its own) whose rows and
columns do not depend on state:

- Play (its width fixed to the wider of Play / Pause);
- the readout: the clip's name in a slot with `min-inline-size: 0`, `overflow: hidden`, `text-overflow: ellipsis`,
  `white-space: nowrap`, full name as `title`; the Clip / Event clocks at their existing fixed widths (`clock.ts`,
  tabular figures) — unchanged behaviour from `time-readouts-legible`, now unbreakable by a sibling;
- the zoom group: −, slider (`inline-size` fixed, e.g. 8rem; 44 px hit area under a coarse pointer), +, Fit;
- Use as poster: the `.tl-poster-why` inline span is deleted. The button keeps `aria-disabled`, gets the reason as
  `title` and as `aria-describedby` → a visually hidden element (always present, text changes). Pressing it while it
  cannot act shows the reason in a tip positioned absolutely under the button (it takes no layout space; dismissed on
  blur, Escape, or when the reason ends) and says it once in the Timeline's polite live region.

The readout and Play are already one component each; only CSS and the poster markup change. The narrow rows are
always present (same height whether or not the poster reason exists); at 390 px the Timeline is about 20rem wide, so
the zoom group and Use as poster each take a row (both on one row would squeeze the slider below its hit area).

### D7 — The read view loses the Timeline; `editing` becomes required

- `EventDetail.tsx` `ReadyView` no longer mounts `TimelineSection`; its `dismissals`, `cards` and (if then unused)
  `onFinished` props go. The page keeps `useDismissals` / `useCardSelection` for Edit mode (the selection and
  dismissals still outlive Edit mode's remounts).
- `TimelineSection`: `editing: EditBinding` and `cardEditing: CardEditing` become required; `toggled`,
  `sectionOpen`, the Open/Close button, `aria-expanded`/`aria-controls`, the `hidden` body and the `read` prop go
  (Edit mode passes `NOT_READ`; the cuts are the draft's). `CardInspector` keeps only its polite status region
  (Edit mode announces a selection once); the words slot, `.tl-inspector*` CSS and `.tl-toggle` go.
- `Timeline.tsx` / `Track.tsx` / `overlays/control.ts`: `editing` is required; every `editing === null` branch that
  TypeScript then flags is deleted (31 sites today across these four files), with the tests that covered only the read
  view (`sectionOpen` in `layout.test.ts`, the read branch of `analysisOf`).
- `sectionState` keeps `none | prepare | track` (no `closed`).

Strings deleted: "Open timeline", "Close timeline", the read-view approval absence note if any. Specs: the section
requirement becomes Edit-mode only; requirements that stated read-view Timeline behaviour drop it, and "The Timeline
pauses, and is paused, like every other player" is removed (its partners, the Movie section's player and the read
view's clip players, are never on the page with the Timeline any more). Requirements whose wording still mentions a
closed section or opening the Timeline without stating read-view behaviour (the analysis read, Prepare, card images)
are left as written: their statements stay true in Edit mode, and copying them in full to reword them would add
archive conflicts with the changes in flight for no change in behaviour.

## Research & Decisions

### MAX_PPS stays 240
**Context**: The request asks for Premiere's slider; the brief allows raising MAX_PPS only if frame-level zoom is
needed and the track-width cap allows it.
**Explored**: `research/trim/zoom-perf.md` §2: at 240 px/s a 25 fps frame is 9.6 px (8 px at 30 fps, 4 px at 60);
frame-level (≈40 px per frame) needs ≈1,000 px/s; a 3 h event is 2.59 M px at 240 and 10.8 M px at 1,000 (inside
Chrome's ≈33.5 M and Firefox's ≈17.9 M), but 21.6 M px at 2,000 breaks Firefox. The filmstrip sprite has one tile per
second (96 px places), so above 96 px/s tiles already repeat and at frame level the picture does not change per frame;
the ruler's tick list (a SHALL in the `timeline` spec) stops at 0.5 s. No perf numbers exist above 240 px/s.
**Decision**: keep 240.
**Rationale**: raising it needs a width cap derived from the event's length, finer ticks (a third capability delta:
`timeline`), a denser sprite (backend, `filmstrip-sprites`) and a new perf run against the scrub gates; frame accuracy
is already reachable by keyboard (frame steps on the playhead and the trim handles). A later change can raise it with
those pieces.

### Anchor rule
**Context**: what stays still while zooming.
**Explored**: `zoom-perf.md` §3; `premiere-ux.md` §2 (verified there: Premiere's `\` fits and a second press returns to
the previous zoom; Resolve's slider and its wheel zoom at the pointer. From memory, unverified there: Premiere anchoring
keyboard zoom on the playhead, and Premiere's Alt+wheel); the existing spec "A zoom SHALL keep the playhead where it was
in the track's view".
**Decision**: slider, buttons, keys → playhead if visible, else centre; Ctrl/Cmd+wheel and pinch → pointer. The wheel
modifier is Ctrl/Cmd, not Premiere's Alt: browsers deliver a trackpad pinch as Ctrl+wheel, and Ctrl+wheel is the page
zoom the operator would otherwise trigger by accident over the track.
**Rationale**: matches the existing requirement and the editors' common model; one pure helper and one `zoomAt`.

### Session persistence
**Context**: "Persist the zoom per event only for the session."
**Explored**: in-memory module map (lost on reload) vs `sessionStorage` (per tab) vs `localStorage` (forever).
**Decision**: `sessionStorage` with an in-memory mirror; every access in try/catch.
**Rationale**: "the session" is the tab; a reload during editing keeps the zoom, a new day starts at Fit.

### Fit gutter vs clipping
See D5.

### Removing the read view's Timeline
**Context**: the operator's decision (verbatim in proposal.md); `edit-mode-declutter` already opens it in Edit mode.
**Explored**: hide the section vs remove the code paths.
**Decision**: remove; make `editing` required so TypeScript finds every read-view branch.
**Rationale**: Principle VII — no second code path kept "for later"; the read view's ▶ overlays, movie and poster do not
depend on the Timeline (`ReadyView` passes it only `read`, `dismissals`, `cards`, `onFinished`).

## Failure behaviour

- Storage unavailable / corrupt → Fit, no error shown (a convenience).
- A zoom request with no measured view (width 0) → ignored, as `zoomBy` does today.
- Wheel without Ctrl/Meta → untouched; with them → always `preventDefault` inside the track box, even at a bound (so
  the page does not zoom instead).
- No writes: zooming, the slider and the read-view removal send no request (verified by Playwright with write routes
  intercepted).

## Idempotency

Pure UI: re-running a zoom to the same scale is a no-op (`|target − pps| < 1e-9` returns early, as today); a remount
restores the stored zoom; no job, no file, no DB row is touched.

## Risks / Trade-offs

- [Per-frame re-render while dragging the slider on a large event] → rAF coalescing; Playwright measures the drag on
  the 400-clip fixture with 4x CPU throttling and must keep the existing gates (≤ 2 % of frames over 25 ms, as the trim
  drag; scrub ≥ 30 fps). Not met in Chrome at 4x (tasks 3.1 status): the thumb alone costs 1.4-2.1 %, a
  zoom 30-34 %, and 7.4-7.9 % with the Edit page's clip list under `content-visibility: auto` — the page around the
  Timeline is most of the cost. Options for the supervisor: that page-level change (a separate change: it touches the
  clip list, its focus rings and dnd-kit's measuring), or a gate measured against the page's own floor.
- [Non-passive wheel listener costs scroll performance] → it returns immediately without Ctrl/Meta; it is on the track
  box only.
- [Shared requirements with in-flight changes] → `help-text-declutter` MODIFIES "The track lays the clips out…" and
  "A card is selected…"; `timeline-ripple-layout` / `clip-edge-trim` change the track. Whichever lands later re-copies
  the merged text and keeps both behaviours (task 1.1 checks this before code).
- [The read view loses a way to watch the event as one track] → the operator asked for exactly that; the movie player
  plays the rendered event and the clip ▶ overlays play each clip.
