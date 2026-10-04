## Why

The operator asked on 2026-10-04 for Premiere's zoom: "To improve usability the zoom in and out should have a slider as
well. just like in Adobe premiere" (part of the clip-edge trim request, whose trim half is `timeline-ripple-layout` and
`clip-edge-trim`). The Timeline's zoom on `main` (e5d3041) is three buttons and three keys stepping by 1.5x
(`web/src/timeline/Timeline.tsx` `ZOOM_STEP`, `zoomBy`), so getting from Fit to a frame-accurate view of one edge takes
up to ten presses and there is no pointer zoom at all (research `trim/zoom-perf.md` §1: no wheel handler, `\` unbound).

Two toolbar bugs, reported the same day, in the operator's words:

- (a) "Even to i have clicked Fit to zoom out max there is a scroll bar at the bottom of the timeline, i don't want
  that." Fit sets the scale so the track's width equals the view's (`fitPps`), but things drawn at the track's end
  extend past it: the playhead's grip is centred on the line (`.tl-grip`, 24 px, 44 px under a coarse pointer), so at
  the end it reaches 12 to 22 px past the canvas, and a fractional width can round one pixel over.
- (b) "Another visual bug when seeking in the timeline." While a seek's frame loads, "The picture is still loading."
  (`edit/poster.ts` `WHY_NO_FRAME`) is written inline beside **Use as poster** and squeezes the clip's name and the
  Clip / Event readouts onto two lines; when the frame arrives they jump back. `time-readouts-legible` (D-20, D-16)
  already promised that the readouts never move; the poster reason breaks that promise from the side.

And a decision about where the Timeline lives: "Alos, i want you to remove the timeline viewer when NOT in edit mode. I
only want it in edit mode." Since `edit-mode-declutter` (#136) Edit mode opens with the Timeline open; the read view
still carries a closed Timeline section with **Open timeline** and, when a card is selected on it, a "Title card for
the opening, 4.0 s, over video" slot. The read view's job is to show the event (the clip list with its ▶ overlays, the
movie, the poster); the Timeline is an editing tool.

HLD §6 phase 8 (GUI v2), D-20 (the timeline is built in the repo, on a pure model): this change amends D-20's zoom and
where the Timeline is shown. It depends on no unresolved §8 item.

## What Changes

- **Zoom slider.** A native range input labelled **Zoom** in the Timeline's zoom group, beside Zoom out, Zoom in and
  Fit: its left end is Fit, its right end the maximum (240 px per second), logarithmic between, with `aria-valuetext`
  "Fit" or "40 px per second". Dragging it zooms continuously, at most once per animation frame, anchored on the
  playhead while the playhead is in view, else on the view's centre. Zoom in / Zoom out keep their 1.5x steps and move
  the slider.
- **Keys and pointer.** `=` / `+` and `-` keep zooming; `0` keeps fitting; **`\`** toggles between Fit and the zoom
  before it (Premiere). **Ctrl+wheel** (Cmd+wheel on macOS, and a trackpad pinch, which browsers deliver as a
  Ctrl+wheel) zooms about the pointer. A plain wheel still scrolls.
- **Zoom remembered per event for the tab's session** (`sessionStorage`, best effort): a Save, a Refresh and leaving
  and re-entering Edit mode keep the zoom; a new tab starts at Fit.
- **Bug (a): Fit never scrolls.** At Fit the track's box has no horizontal scroll bar, with the playhead at the start
  or the end, with card blocks at their 24 px minimum, at 1280 and 390 px, fine or coarse pointer.
- **Bug (b): a toolbar that holds still.** The toolbar's controls keep their boxes while the Timeline is idle, seeks,
  loads a frame, plays, or has its playhead in a card: the clip's name in a fixed slot, ellipsized; the readouts at
  their clock widths; the zoom controls and slider; Use as poster with its reason as a tooltip and description only,
  shown and announced when the disabled button is pressed, never as inline text. Narrower, the toolbar may take
  more rows (at 390 px three rows of controls and the movie stat), the same rows in every state.
- **The read view has no Timeline.** The read view's Timeline section, its **Open timeline / Close timeline** button
  and its card inspector slot are removed with their code, strings, CSS and tests; the Timeline is shown only in Edit
  mode, open, as `edit-mode-declutter` made it. The read view keeps its clip list (▶ overlays, cut summaries, turns),
  the Movie section, the poster and everything else it shows today.
- **MAX_PPS stays 240** (numbers in design.md): no frame-level zoom in this change.

## Non-goals

- No frame-level zoom (no MAX_PPS above 240, no finer ruler ticks, no denser filmstrip sprite): see design.md.
- No touch-screen pinch zoom of the track (a two-finger pinch on a phone stays the browser's page zoom); no zoom
  scrollbar handles (Premiere's zoom-by-dragging-the-scrollbar's ends).
- No trim of a clip's start or end (`clip-edge-trim`) and no ripple layout (`timeline-ripple-layout`).
- No Timeline anywhere outside Edit mode: no read-only Timeline, no "Open in Edit mode" shortcut from the read view.
- No change to the movie player, the clip players, the Cuts panels or the poster's model.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `event-timeline`: the zoom requirement gains the slider, `\`, Ctrl+wheel, the session memory and the Fit-has-no-scroll
  rule; a new requirement holds the toolbar still; the read view's Timeline is removed (the section requirement
  becomes Edit-mode only) and the requirements that described read-view behaviour (track layout, approval,
  dismissal, turn, card block, card selection) lose it.
- `web-app`: Use as poster gives its reason as a tooltip / description and on press, never inline; a conflict's
  "Reload latest" no longer speaks of the read view's Timeline.

## Impact

- **Package:** `web/` only (`web/src/timeline/`, `web/src/events/EventDetail.tsx`, `web/src/edit/poster.ts` caller,
  timeline CSS) and `docs/high-level-design.md`. No engine, CLI or API change (Principle V: nothing new the API
  offers).
- **Rendered output:** unchanged for identical inputs; no `RENDER_GRAPH_VERSION` bump; staleness fingerprint inputs
  unchanged.
- **Schema:** no `reel.yaml` or project `config.yaml` change; no Alembic migration; no rescan.
- **Dependencies:** none added (D-20: React + plain CSS, no timeline library). Tests stay on the existing `node:test`
  runner (`npm test`) plus Playwright from the scratchpad in Chrome 154 and Firefox ≥ 155.
- **Complexity:** the zoom slider adds two pure functions (position ↔ scale) and one `zoomTo` beside the existing
  `zoomAt`; the read-view removal deletes more than it adds.
- **Overlaps in flight:** `help-text-declutter` (MODIFIES the track-layout and card-selection requirements too, and
  reworks the Timeline's notes / stat line), `timeline-ripple-layout` and `clip-edge-trim` (touch `Timeline.tsx`,
  `Track.tsx`, `layout.ts`). Whichever lands later re-copies the current text of a shared requirement and keeps the
  other's behaviour.
