## Context

`web/src/edit/workspace/Workspace.tsx` renders Edit mode's workspace as one grid. Its children, in DOM and Tab order:

| Element | Grid area | Pane |
|---|---|---|
| `.ws-top` | `top` | the top bar |
| `section.ws-binbox` "Clips" | `bin` | LEFT: player, `.ws-pane.ws-bin[data-ws-scroll]`, ClipInfo |
| `section.ws-pane.ws-view` "Viewer" | `view` | centre: the portal target `.ws-view-slot` |
| `section.ws-pane.ws-insp` "Inspector" | `insp` | RIGHT: the Event, Clip, Title card and Suggestion tabs |
| `section.ws-pane.ws-tl` "Timeline" | `tl` | BOTTOM: the track and its tool row |

The Timeline's picture and transport, and its cut panel, are moved into the viewer and the inspector through
`TimelinePanesContext` (`web/src/timeline/panes.ts`), so the whole workspace stays one React tree with one state. The
single `<video>` is rendered by the Timeline but its DOM lives in the viewer's `.ws-view-slot`; the inspector's Clip,
Title card and Suggestion tabs hold portal targets (`clipSlot`, `cardPane`, `suggestionPane`).

`workspace.css`:
- `html[data-workspace]` sets `--ws-bin-w: clamp(240px, 22vw, 320px)` and `--ws-insp-w: 340px`. They are on `<html>`
  so that the notification region, which is outside `.ws`, can read them. It does so in
  `inset-inline: calc(var(--ws-bin-w) + var(--s-3)) calc(var(--ws-insp-w) + var(--s-3))`.
- `.ws` is
  `grid-template: 'top top top' auto / 'bin view insp' minmax(0, 1fr) / 'tl tl tl' minmax(280px, 38vh) / var(--ws-bin-w) minmax(0, 1fr) var(--ws-insp-w)`,
  with `block-size: 100dvh` and no `overflow` rule.
- Below 960 px wide (`@media (width < 960px)`) `.ws` becomes a flex column ordered viewer, Timeline, inspector, bin,
  and the page scrolls. Pane sizes do not apply there.
- The z-indexes in use: the inspector's sticky tabs (3), the top bar (6) and the wide alert panel (7).

**What reads pane sizes or rects:**
1. **The save explanation's cap.** Workspace.tsx's layout effect computes `--ws-alert-max` in the wide frame from the
   Timeline's top edge (`.ws-tl`'s `getBoundingClientRect().top`). It runs on a top-bar or alert resize (a
   `ResizeObserver`) and on window `resize`. A Timeline that changes height without a window resize would leave the
   cap stale.
2. **The notification region** reads `--ws-bin-w` and `--ws-insp-w` (above).
3. **`overBin`** (`EventEditor.tsx`): a track drag asks whether a client point is inside `.ws-binbox`'s
   `getBoundingClientRect()`.
4. **The Timeline's width.** `useVisibleRange.ts`, Fit and `zoomTo` read the scroller's `clientWidth`
   (`Timeline.tsx` returns early on `clientWidth === 0`). The Timeline spans all three columns, so a side border
   never changes it.
5. **The viewer's stage.** In the wide frame it is `block-size: 100%`, `aspect-ratio: 16 / 9`,
   `max-inline-size: 100%`, and the video uses `object-fit: contain`. A tall, narrow viewer letterboxes. This already
   happens at 960 px.
6. **The viewer's transport.** It follows container queries on `tl`: one row from 31rem, three rows under 28rem.
7. **The bin.**
   - `.ws-binbox` is an inline-size container, a flex column with `min-block-size: 0` and no `overflow`: a player
     taller than the row paints over the Timeline. (Before this change; now `overflow-y: auto`, D5.)
   - The compact player is guaranteed only from a 240 px bin (`binPlayerCss.test.ts`, "least side pane 240 px").
   - ClipInfo is capped at 30 % of the bin's height.
   - `binPlayerPref.ts`'s `SHORT_WINDOW_QUERY` assumes today's Timeline height when it picks the player's default.
   - `BinPlayer.tsx` closes the open preview when the player is hidden (`!wanted`).
8. **The inspector.** The card editor is one column under 22rem, and the four tabs need about 320 px.
   `EventEditor.tsx` shows the Event tab and focuses a save's refusal at the Details fields.

**The idioms reused:**
- **Stored preferences:** `binPlayerPref.ts` / `binInfoPref.ts`. Each is a module store read with
  `useSyncExternalStore`, uses an `auto-reel:<name>` key, guards every storage access with an in-memory fallback, takes
  an injected `PrefStorage` and has a reset seam.
- **Value parsing:** `zoomMemory.ts`'s `parseZoom`, which validates and returns null rather than guess.
- **Pointer drags:** `TrimHandle.tsx` and `EdgeHandles.tsx`. Their `onPointerDown` takes the primary button only,
  calls `preventDefault` and `setPointerCapture`, keeps the drag in an `active` ref, handles move, up and cancel, and
  cancels on lost capture. Two parts of that idiom are **not** copied:
  - they move focus *to* the handle on a press (`target.focus({ preventScroll: true })`, TrimHandle 448–449,
    EdgeHandles 303–304), because a handle's keys are the point of pressing it. A separator must leave focus where it
    was (D4);
  - their `bareMouseDown` (TrimHandle 135–150, EdgeHandles 411) exists only for "a mouse press that came without
    pointer events (Firefox under touch emulation)". Under the Pointer Events spec a cancelled `pointerdown`
    suppresses the compatibility `mousedown`, so a `mousedown` guard never runs after a `pointerdown` that called
    `preventDefault`.
- **Escape during a drag:** `ClipBin.tsx`'s window capture listener.
- **Invisible but laid out:** `BinPlayer.tsx`'s `preview-ghost` rows (`visibility: hidden`, `aria-hidden`, `inert`).

## Decisions

### D1. Sizes and hidden panes are preferences laid over today's rules (`edit/workspace/paneSizes.ts`, pure)

```ts
export type PaneId = 'bin' | 'insp' | 'tl'
/** What is stored: the chosen sizes in CSS px (a missing entry means "today's rule") and the hidden panes. */
export type PanePrefs = { sizes: Partial<Record<PaneId, number>>; hidden: readonly PaneId[] }
/** The sizes laid out, in whole CSS px; 0 means hidden. */
export type Drawn = Record<PaneId, number>
export type Frame = { width: number; height: number; rem: number; top: number } // clientWidth/Height, root font px, top bar's drawn height

export const MIN_BIN_PX = 240           // the compact player's least side pane (binPlayerCss.test.ts)
export const MIN_INSP_PX = 320          // the four inspector tabs (measured in task 3.1: "Title card" wraps at 300 in both; it fits from 310 in Chromium and from 320 in Firefox)
export const MIN_TL_PX = 200            // tool row + ruler + video lane + scrollbar (measured in task 3.1)
export const MIN_VIEW_REM = 20          // the viewer's least width
export const MIN_MIDDLE_REM = 20        // the middle row's least height while the bin is shown (derived below)
export const MIN_MIDDLE_BARE_REM = 14   // the middle row's least height while the bin is hidden (measured in task 3.1)
export const SNAP_FRACTION = 0.5        // a pane dragged under this share of its minimum hides (D4)
export const DRAG_SLOP_PX = 3           // movement below this is a click, not a drag (D4)
export const KEY_STEP_PX = 16
export const KEY_BIG_STEP_PX = 64

export type Limits = { min: number; max: number }
export type Mods = { shift: boolean; ctrl: boolean; alt: boolean; meta: boolean; repeat: boolean } // repeat: KeyboardEvent.repeat
export type PaneProperty = '--ws-bin-w' | '--ws-insp-w' | '--ws-tl-h'
/** What a gesture or a key asks of a pane. */
export type PaneAction = { kind: 'size'; px: number } | { kind: 'hide' } | { kind: 'show' } | { kind: 'reset' }
/** The three panes, in a fixed order (the stored `hidden` list keeps it). */
export const PANES: readonly PaneId[] = ['bin', 'insp', 'tl']

/** Today's rules as whole px: bin clamp(240, 0.22·width, 320), inspector 340, Timeline max(280, 0.38·height). */
export function defaultSizes(frame: Frame): Drawn
/** The middle row's least height in px: MIN_MIDDLE_REM with the bin shown, MIN_MIDDLE_BARE_REM without. */
export function middleMin(binShown: boolean, frame: Frame): number
/** The least and largest shown size of `pane` while the other panes stay as `drawn` (0 = hidden). */
export function limits(pane: PaneId, drawn: Drawn, frame: Frame): Limits
/** The layout: shown panes at their preference or default, shrunk to the frame (below); hidden panes 0. */
export function effectiveSizes(prefs: PanePrefs, frame: Frame): Drawn
/** A drag from a hidden pane starts at the press's distance from the window's edge on the pane's side, in px
 *  (`x`, `y` the press, `width`, `height` the window), so the pane appears under the pointer, not at the edge. */
export function edgeDistance(pane: PaneId, x: number, y: number, width: number, height: number): number
/** A drag from `start` (0 when the pane was hidden): hide under SNAP_FRACTION·min, else the size clamped to `lim`. */
export function dragAction(pane: PaneId, start: number, dx: number, dy: number, lim: Limits): PaneAction
/** A key on a focused separator, or null when the key is not the pane's, Ctrl, Alt or Meta is held, or an
 *  auto-repeat would hide or show the pane (below). */
export function keyAction(pane: PaneId, key: string, mods: Mods, current: number, lim: Limits): PaneAction | null
/** Whether `key` is one of the pane's separator keys (its two arrows, Home, End, Enter), whatever the modifiers. */
export function isPaneKey(pane: PaneId, key: string): boolean
/** What a commit stores (see "Committing"). */
export function commitPanes(pane: PaneId, action: PaneAction, prefs: PanePrefs, drawn: Drawn, frame: Frame): PanePrefs
/** Whether `pane` is hidden as laid out: never while stacked (`stacked` from `isStacked()`/`useStacked()`, D2). */
export function paneHidden(pane: PaneId, prefs: PanePrefs, stacked: boolean): boolean
/** The custom properties to write on <html>: each drawn size as a px string ("0px" hidden), null for all three when `stacked`. */
export function paneProperties(drawn: Drawn, stacked: boolean): Record<PaneProperty, string | null>
/** Whether two frames have the same four numbers (D3's bail-out). */
export function sameFrame(a: Frame, b: Frame): boolean
/** Stored JSON → prefs; null on anything but an object of finite, positive sizes under known keys and an optional
 *  `hidden` array of distinct known panes. */
export function parsePanes(raw: string | null): PanePrefs | null
/** Prefs → stored JSON, or null (remove the key) when there is no size and no hidden pane. */
export function serializePanes(prefs: PanePrefs): string | null
/** "Clip bin 282 pixels wide", "Inspector 340 pixels wide", "Timeline 342 pixels tall"; "Clip bin hidden" at 0. */
export function valueText(pane: PaneId, px: number): string
```

**The middle row's minimum.** With collapse available, the minimums only have to keep each *shown* pane whole; when
there is not room for everything, the operator hides a pane. The middle row's least height is therefore the bin
column's need while the bin is shown, and the viewer's while it is hidden.
- **Bin shown: 20rem** (320 px at a 16 px root), the bin column with the player shown, ClipInfo **closed** and a
  fine pointer (an explicit Show wins over `SHORT_WINDOW_QUERY`, so the player can be shown at any height):
  - the player, `flex: none`, about 197 px (`binPlayer.css`, "height budget of about 200 CSS pixels");
  - the bin's sticky heading, `--panel-head-h` 2.75rem (44 px);
  - one whole list row, `--bin-row-h` 2.5rem (40 px);
  - ClipInfo's heading and toggle, 34 px at their content plus the 1 px border (35 px).

  That is about 316 px. It also leaves the viewer room for its three-row transport plus a picture, and room for a
  toast at the viewer's top that does not reach the transport.

  **What the 20rem does not cover, and the bin column's shrink order (decided by the lead 2026-11-24).** ClipInfo is
  open by default (`binInfoPref.ts` reads closed only when stored), and in the wide frame its body takes up to 30 % of
  the bin's height. A coarse pointer's player is taller (no compact rows, `binPlayer.css`) and may not fit whole next
  to a list row. When the bin column is too short, it gives way in this order, **wide layout only (>= 960 px); the
  stacked layout is today's behaviour, byte for byte**:
  1. **The clip list (`.ws-bin`) shrinks first**, to a least height of its heading plus one row
     (`min-block-size: calc(var(--bin-head-h) + var(--bin-row-h))`), and it takes all the spare height
     (`flex: 1 1 0`).
  2. **ClipInfo's body shrinks next**: `.bin-info` is `flex: 0 1 auto` with `min-block-size: 35px` (its real heading,
     34 px, plus the 1 px border; the heading and the "Hide information" toggle never shrink away) and keeps its 30 % cap.
     The body already scrolls inside itself. `.bin-info` has `overflow-y: clip` (not `overflow-block`, which Chrome < 135 lacks) (wide only): the body's 8 px bottom
     padding keeps the body's border box at 8 px or more, which would otherwise spill past the box's least height and make
     the bin's box scroll before step 3 (measured: 322 in 320 at the middle row's minimum, fine pointer, player shown).
  3. **Only if the player, the list's least and ClipInfo's heading still exceed the bin's height does the bin's box
     scroll** (`.ws-binbox { overflow-y: auto; overflow-x: clip }`, D5). The bin never clips a reachable control, and
     nothing is drawn over the Timeline.

  **Accepted limitation, the focus ring of the scrolling bin.** Firefox makes a scroll container a Tab stop, and its focus
  ring on `.ws-binbox` and `.ws-bin` is partly covered by their own positioned parts (the sticky "Clips" heading, the list
  pane, ClipInfo). That is the browser's behaviour for a scroll container, present before this change wherever one
  scrolls, and it is accepted as is (decided by the lead 2026-11-24): no `tabindex` on either box (it would make a click
  on empty list space take focus and change the stacked layout), and no CSS written for that ring. `.bin-info-body`,
  a scroller with nothing over it, keeps its ring inside (`outline-offset: -2px`, wide only).

  **Acceptance (relaxed by the user 2026-11-24).** Fine pointer: at an untouched 1280x720 with ClipInfo open the bin
  has no scrollbar, with the player shown or hidden, and at the middle row's minimum with the player shown (list 80, ClipInfo 43,
  box 320 in 320) it has none either. **Coarse pointer with the bin player shown: the bin may scroll at 1280x720.** The coarse player
  alone is 383 px of a 391 px bin, and no shrink of the list and ClipInfo can fit the rest; the box scrolls by step 3 and the
  toggle is reachable by that scroll. Before this change the content was drawn over the Timeline there instead. A compact
  coarse side-pane player is not done (it would change the touch-sized rows `preview.css` keeps on purpose).

  **Measured** (final code; Chromium and Firefox, real scrollbars, Tjörn; logs `final/last/rv9_bin.chromium.log` 55 of 55 and
  `final/last/rv9_bin.firefox.log` 29 of 29, `DATA` lines): untouched 1280x720, fine, player shown: box 391 in 391, player 197,
  list 132 (2 whole rows), ClipInfo 63 (heading 34), toggle visible and clickable; player hidden: no scrollbar. Middle-row
  minimum (End on the Timeline's border), fine, player shown: box 320 in 320, list 80 (1 row), ClipInfo 43, no scrollbar, toggle
  inside and hit-testable. 960x500, fine, player shown: list 80, ClipInfo 35 (its least), box 296 in 251 (it scrolls only
  after both are at their least), toggle reachable by that scroll. Coarse, 1280x720, player shown: player 383, list 96 (its
  least), ClipInfo 35, box 526 in 391, toggle reachable by scrolling and clickable; coarse with the player hidden: no scrollbar.
  The bin's bottom is at or above the Timeline's top in every case. **Not chosen:** budgeting ClipInfo's 30 % share into the
  middle row's minimum (it needs about 25rem and moves the "looks as today" threshold from 648 px to about 728 px tall);
  leaving the bin's content out of the minimum.
- **Bin hidden: 14rem**, the viewer's three-row transport (it is under 28rem wide at its least width) plus a picture
  and the viewer's padding. Provisional: task 3.1 measures it.
- **Measured (task 3.1, Chromium and Firefox, Tjörn, 16 px root, a 49 px top bar, so an untouched 1280×600 Timeline is 231
  and a hidden-bin one 327, one pixel under the 232 and 328 above):**
  - *Bin shown, 20rem, fine pointer, End on the Timeline's border at 1280×720:* the middle row is 320; the player is 197 and
    whole; with ClipInfo **closed** the list is 88 px with 1 whole row; with ClipInfo **open** the list was **27 px** (superseded by the shrink order above: 80 px, one row), no whole
    row. Nothing in the bin is drawn over the Timeline (the bin ends where the Timeline starts), and every control of the
    bin and the viewer is hit-testable at its centre in both cases.
  - *Viewer at 20rem wide together with it:* the three-row transport is 139 px and whole, the stage 259×146.
  - *Bin hidden, 14rem (224 px), viewer at 20rem wide:* the transport is whole and hit-testable and the picture is 88×50
    ("some picture shows"); the constant stays 14. At the viewer's ordinary width the one-row transport leaves a 277×156
    picture.
  - *Coarse pointer at 1280×720 (Chromium, `is_mobile`):* with the player shown (383 px) the fixed parts (player and
    ClipInfo's heading, 418 px) are close to the bin's 391 px, so the list is at its least (96 px, one row, by the shrink order
    above), ClipInfo is at its 35 px and the bin's box scrolls (scrollHeight 526 including the 12 px coarse end padding,
    clientHeight 391; `final/last/rv9_bin.chromium.log`). This is the accepted relaxation above. With the bin scrolled to its
    end ClipInfo's toggle is inside the bin and hit-testable (the coarse Timeline strip reaches 12 px up into the bin, so a
    coarse pointer adds 12 px of end padding and scroll padding, D5). The 27 px / 0 px / 80 px list figures taken earlier,
    before ClipInfo's body could shrink, are superseded.
  - *Inspector:* "Title card" wraps to two lines at 300 px in Chromium and fits from 310 there and from 320 in Firefox, whose
    tabs are 6 px wider; `MIN_INSP_PX` is therefore 320 (a whole 20rem; 240 + 320 + 320 = 880 still fits 960).
  - *Timeline at 200 px:* the tool row and the ruler are whole; the track's lanes scroll in the pane.
- **Not chosen:** following the bin *player's* Show/Hide too. The Timeline would then jump whenever the player is
  shown, a control in another pane. Hiding the bin is a pane gesture, so a changed middle-row minimum there is
  expected. Task 3.1 measures both figures and raises the constants (and the spec's figures) if content does not fit.

**Limits** (`limits`, for a pane as if shown; the other panes as drawn, 0 when hidden).
- **Bin:** `min = MIN_BIN_PX`, `max = width − drawn.insp − MIN_VIEW_REM·rem`.
- **Inspector:** `min = MIN_INSP_PX`, `max = width − drawn.bin − MIN_VIEW_REM·rem`.
- **Timeline:** `min = MIN_TL_PX`, `max = height − top − middleMin(drawn.bin > 0)`.
- **The coupling this makes.** Because the Timeline's maximum follows `drawn.bin`, hiding or showing the bin can
  lengthen or shorten a Timeline that the middle row holds short. Example at 1280×600 (top bar 48, 16 px root) with a
  kept 340 px Timeline: with the bin shown it is drawn at 552 − 320 = 232; once the bin is hidden (released) it is
  552 − 224 = 328; when the bin is shown again it is 232. The Timeline changes when the bin's hide or show is
  committed, not during the drag (D3: only the dragged pane is written live). This is the one exception to "a commit
  never moves another pane", and the spec states it.
- **Precedence.** If `max < min`, then `max = min`: the pane minimums win over the viewer's and the middle row's.
- **Invariant:** for every pane shown in `effectiveSizes(prefs, frame)`, its drawn size lies within
  `limits(pane, drawn, frame)`. (The earlier draft's special case for a default drawn above its maximum, the 280 px
  Timeline under 660 px tall, is gone: every shown pane, default or chosen, is now clamped by the same rule.)
- **The range in which every minimum holds** at a 16 px root and an about 48 px top bar:
  - in width, from 960 px: 240 + 320 + 320 = 880 ≤ 960, and the defaults 240 + 340 + 320 = 900 ≤ 960;
  - in height, from 568 px with the bin shown (200 + 320 + 48), 472 px with the bin hidden; an untouched Timeline
    keeps its 280 px from 648 px tall.
- Sizes are whole px.

**`effectiveSizes`** (window resize, first paint, every commit). With `want(p) = max(sizes[p] ?? default[p], min(p))`:
- **Hidden panes** are 0. Hiding is the operator's alone: no window size hides a pane.
- **Shown side panes.** `room = width − MIN_VIEW_REM·rem`. When `Σ want ≤ room` over the shown side panes, each is
  drawn at `want`. Otherwise each gives up the same share of its excess over its minimum: the factor
  `(room − Σmin) / Σ(want − min)`, clamped to [0, 1], and each pane is `min + floor((want − min) · factor)`. This is
  deterministic, keeps the ratio the operator chose and starves neither pane. It applies to defaults too, which
  never shrink in practice from 960 px at a 16 px root (900 ≤ 960) but do with a larger root font.
  - When `room < Σmin` (a large root font) the factor is 0 and the panes sit at their minimums, never below: the
    viewer gives way under 20rem. When `Σ(want − min)` is 0 no factor is computed (no division by zero, no NaN).
  - Flooring keeps `bin + insp ≤ room`, so the viewer is never 1 px short of 20rem.
  - Example: at 1100 × 900 with stored bin 600 and inspector 500, room = 780, factor = 220/540, and the panes are
    drawn at 386 and 393 (raw 386.67 and 393.33); the viewer is 321.
  - With one side pane hidden the other is `clamp(want, min, max(room, min))`.
- **The Timeline**, shown: with `H = height − top`, `lower = min(MIN_TL_PX, max(H, 0))` and
  `upper = max(H − middleMin(bin shown), lower)`, it is `clamp(want, lower, upper)`.
- The preference itself is never rewritten by a clamp. A window that grows back brings the chosen size back.
- **The exception: showing a hidden side pane.** The invariant "a resize never pushes the other side pane" holds for
  drags and keys on a *shown* pane. A `show` stores nothing and lets `effectiveSizes` fit both kept sizes to the window,
  so when the room is short the other side pane is drawn narrower (minimums win; the stored size is untouched and
  returns with the room). Example: 1100 × 900, bin kept at 600, inspector hidden (bin drawn 600): showing the inspector
  draws the bin at 448 and the inspector at 331; at 1440 the bin is 600 and the inspector 340 again. Covered by
  `paneSizes.test.ts` ("showing a hidden side pane in a window without room"). Not chosen: pinning the bin at 600
  and refusing the show (the operator asked for the pane) or storing the shrunk bin (it would forget a chosen size).

**A window too small for every shown pane's minimum.** The order in which things give way, with nothing ever hidden
and the page never scrolling:
1. Shown panes shrink toward their minimums (the side panes by the shared factor; the Timeline to `H − middleMin`).
2. Then the viewer gives way below 20rem of width (only with a large root font: 560 px of side minimums always fit
   in 960) and the middle row below its least height (under 568 px tall with the bin shown).
3. Then content is clipped inside the panes: the panes scroll (`.ws-pane`), the bin column scrolls
   (`.ws-binbox { overflow-y: auto }`, D5) so its controls stay reachable and nothing paints over the Timeline, and in a window shorter than
   the top bar plus 200 px the Timeline takes what is left (`lower` above) and scrolls within itself.

`.ws` gets `overflow: clip` in the wide frame (D5), so nothing it lays out can scroll the page. **Not chosen:**
auto-hiding a pane (as some IDEs do): the operator asked for hiding when *they* resize to the minimum, and a pane
that disappears on a window resize loses its content without a gesture to explain it. **Not chosen:** a page
scroll, which the workspace has avoided in the wide frame since `editor-workspace-layout`.

**Committing** (`commitPanes`, used by every pointer, key, double-click and Enter commit). A commit stores what the
operator sees and never moves another pane:
- `size` sets `sizes[pane] = px` and takes `pane` out of `hidden`;
- `hide` adds `pane` to `hidden` and **keeps** `sizes[pane]` and every other kept size, so the pane comes back at its size;
- `reset` deletes `sizes[pane]` (the pane is shown, so it is not in `hidden`).
- **Side panes:** when the window is shrinking the other side pane (it is shown and drawn below its `want`), the
  commit also stores it at its drawn size. Otherwise a commit inside the shrink would change the factor and move both
  panes after release. In the example above, dragging the bin to 380 stores `{bin: 380, insp: 393}` and nothing
  moves; storing `{bin: 380, insp: 500}` would have snapped the bin to 338 and the inspector to 441. A `reset` of a side pane
  whose default does not fit beside the other pane as drawn stores the size that fits, for the same reason. **`hide`
  stores nothing** (it only adds to `hidden`, and is a no-op on a pane already hidden, so a wiggle on a hidden strip
  changes nothing): the other side pane may grow to its kept size in the freed room, and `show` returns both panes to
  exactly the widths they had, so hide/show cycles never lower a kept size.
- **The Timeline:** a commit stores only the Timeline. Showing or hiding the bin changes `middleMin`, so showing the
  bin can shorten a tall Timeline in a short window. Its kept size is not rewritten and comes back with room.
- **Property** (tested): for a `size` within `limits(pane, drawn, frame)` and for `hide`, `effectiveSizes` of the
  result draws `pane` at that size (or 0) and every other pane as in `drawn`, except the Timeline after a bin
  `size`/`hide` as just said. A shown pane coming back from hidden is a `show` (below), which stores no size.

**`show`.** A third action, `{kind: 'show'}`, used by Enter and a double click on a hidden pane's border and by the
refusal path (`showPane`). `commitPanes` only takes the pane out of `hidden`: it writes no size and pins no other pane,
so `effectiveSizes` fits the kept (or default) sizes to the window. A window too small for both kept side sizes shrinks
both proportionally, as for any narrow window; nothing the operator chose is forgotten, and a window large enough again
shows the kept sizes. (An earlier `restoreSize` stored the clamped value, which lost the kept size and moved the other
pane; it is gone.) Arrow, Home, End and a drag out of a hidden pane are explicit sizes and stay `size`.

**Direction and snap.**
- The bin grows with +dx (Right), the inspector with −dx (Left), the Timeline with −dy (Up).
- **`dragAction`**: `raw = start + growth`. Under `SNAP_FRACTION · lim.min` it is `hide`; otherwise
  `size: round(clamp(raw, lim.min, lim.max))`. From a hidden pane (`start = 0`) the pane stays hidden until the
  pointer is half its minimum out, appears at its minimum, then follows the pointer once past it. The threshold is
  the same in both directions, as VS Code's sashes (its `snap` at half the minimum), so a drag that hesitates at the
  threshold flips the same way each time it crosses it.
- **`keyAction`**:
  - with Ctrl, Alt or Meta held, every key is null: Alt+Left and Alt+Right are the browser's Back and Forward and
    the workspace's move-clip chord, and Ctrl and Meta arrows are the browser's;
  - an auto-repeat (`mods.repeat`) never hides or shows a pane: a repeated Enter is null, a repeated shrink key at
    or under `lim.min` is null, and a repeated grow key on a hidden pane is null. Held, a shrink key therefore stops
    at the minimum and a fresh press hides; a held Enter does not flip the pane at the repeat rate (and does not write
    `localStorage` and re-render Workspace at that rate). Repeated steps between the minimum and the maximum still
    act, as on a slider;
  - the grow key (bin `ArrowRight`, inspector `ArrowLeft`, Timeline `ArrowUp`): from hidden, `size: lim.min`;
    otherwise `size: min(current + step, lim.max)`;
  - the shrink key (bin `ArrowLeft`, inspector `ArrowRight`, Timeline `ArrowDown`): from hidden, null; at or under
    `lim.min`, `hide`; otherwise `size: max(current − step, lim.min)` — so one press stops at the minimum and the
    next hides, the keyboard twin of the drag's snap;
  - Shift uses the big step;
  - `Home` gives `size: lim.min` and `End` `size: lim.max`, from hidden too (they show the pane);
  - `Enter` (Shift ignored) gives `hide` on a shown pane and `show` on a hidden one;
  - anything else is null.

  **The kept size after a key collapse.** Every arrow press is a commit, so stepping a 417 px bin down to 240 and
  pressing once more to hide keeps 240, and Enter brings it back at 240: the size it had just before it was hidden,
  which is what the spec promises. A drag past the minimum commits nothing on the way, so it keeps 417. Accepted;
  remembering a pre-collapse size apart from the kept size would be a second stored figure for one pane.

  The arrows move the *line* the way they point, as APG's window splitter does. **Home** is the smallest *shown*
  size, not the hidden state: APG allows either ("may completely collapse"), and a Home that hides would make
  Home/End asymmetric with the drag's minimum. Enter is the collapse key, as APG names it.

### D2. Stored panes (`edit/workspace/paneSizesPref.ts`)
This module copies `binPlayerPref.ts`.
- **The key:** `PANES_KEY = 'auto-reel:workspace-panes'`, holding JSON
  `{"bin":317,"insp":420,"tl":360,"hidden":["tl"]}`, with only the chosen sizes present and `hidden` left out when
  empty. `serializePanes` and `parsePanes` (D1) own the format.
- **Reading and writing:**
  - `readPanes(storage)` returns `parsePanes(getItem)`, or the empty prefs, inside try/catch.
  - `writePanes(prefs, storage)` removes the key when `serializePanes` gives null and otherwise calls `setItem`,
    inside try/catch.
- **The module store:**
  - `panePrefs()` is read once from the browser, then held;
  - `setPanePrefs(next)` stores and notifies (the only writer; callers pass `commitPanes(...)`);
  - `subscribePanePrefs(listener)`;
  - `usePanePrefs()` is `useSyncExternalStore(subscribe, panePrefs, () => EMPTY)`, where `EMPTY` is a frozen
    `{sizes: {}, hidden: []}`, so the snapshot is stable;
  - `resetPanePrefs()` is the test seam.
- **The one source of "stacked".** Today it is a local inside Workspace's `measure`. Beside the prefs:
  - `STACKED_QUERY = '(width < 960px)'`, the same media query as `workspace.css` (a viewport query, scrollbar
    included, so not derived from `clientWidth`);
  - `isStacked()` reads `matchMedia(STACKED_QUERY).matches` (false without `matchMedia`, as in `node:test`);
    `useStacked()` is `useSyncExternalStore` over the query's `change` event;
  - `isPaneHidden(pane)` is `paneHidden(pane, panePrefs(), isStacked())`, read at call time (for `overBin`);
    `usePaneHidden(pane)` is the hook form, `paneHidden(pane, usePanePrefs(), useStacked())`.

  Workspace (its apply effect and `measure`), `BinPlayer`, `EventEditor`'s `overBin` and its refusal path all use
  these. Nothing else computes `stacked`.
- **Showing a pane from outside Workspace.** `EventEditor` renders `Workspace` (it is its parent), so it has no
  `frame` or `drawn` (D3) and must not measure them again. The store holds one resolver slot:
  - `registerPaneShower(fn)` returns an unregister function. Workspace registers in a layout effect a function that
    reads its current prefs, `drawn` and `frame` from refs and, for a pane hidden in the wide frame, calls
    `setPanePrefs(commitPanes(pane, {kind: 'show'}, prefs, drawn, frame))`
    and then `applyPane` for that pane from the result (D3, "Commit applies the pane"). Stacked, or for a shown pane,
    it does nothing.
  - `showPane(pane)` calls the registered function, and does nothing when none is registered (no workspace mounted).

  The inspector's refusal path (D8) calls `showPane('insp')`; nothing outside Workspace calls `commitPanes`.
- **Per browser, for every event.** Sizes and hidden panes are layout, not part of any event. When the browser keeps
  nothing, they last for the page visit.

### D3. Sizes are applied as custom properties, hidden panes as attributes
`Workspace` keeps `frame` in state: `clientWidth`, `clientHeight`, the root font size and the top bar's
`offsetHeight`. The top-bar figure comes from the measure the layout effect already takes. `frame` is updated on
window `resize` and on the existing observer (which, with D7, also fires while the Timeline's border is dragged).

**No re-render from a drag.** `measure` keeps the last frame it set in a `frameRef` and calls `setFrame(next)` only
when `!sameFrame(frameRef.current, next)`. A Timeline drag changes the Timeline's height but none of the four
numbers, so no state update is queued at all and Workspace does not render between pointerdown and pointerup. (A
functional `setFrame(prev => sameFrame(prev, next) ? prev : next)` is not enough: React skips the children of an
unchanged state, but when the fiber still has pending work from an earlier update it may call the component once
before it bails out, which would make the 0-render check of task 3.1 flaky.)

From `usePanePrefs()`, `frame` and `useStacked()` (D2), Workspace computes `drawn = effectiveSizes(prefs, frame)`. One
imperative writer, `applyPane(pane, px)`, sets everything a pane's size decides, together:
- the track property on `document.documentElement.style` (`--ws-bin-w`, `--ws-insp-w`, `--ws-tl-h`), in px, `0px`
  when hidden;
- on the pane's section, `data-hidden` and the `inert` property, when `px` is 0;
- a *live* (mid-drag) write of 0 is transient: it sets `data-collapsing` instead of `data-hidden`, and neither blurs
  nor sets `inert`. The CSS lays `data-collapsing` out like `data-hidden` but never as `visibility: hidden`, because a
  focused element that stops being visible is blurred by Chromium and Firefox (checked in both), which would fire
  `blur` commits (a half-typed trim or cut field). The commit's write of 0 sets `data-hidden`, `inert` and the blur;
- before setting `inert` (commit only), focus inside the section is blurred (`document.activeElement.blur()`), so focus lands on
  the page, where the workspace's keys still act (Space plays, Left steps), rather than on a node the browser fixes
  up in its own way.

A layout effect calls `applyPane` for each pane from `drawn` (wide) or removes the properties and attributes
(stacked); the separators' live writes (D4) call the same function. React does not own `data-hidden` or `inert`, so a
render never undoes a live write, and a cancel re-applies from `drawn`.

**Always written in the wide frame.** The earlier draft removed a pane's property when it had no preference, so the
CSS rule applied. Now every pane's effective px is written: an untouched Timeline is clamped to the window, and a
hidden pane is 0, which the CSS rules cannot express. The CSS rules stay as the fallback for the first paint and for
the stacked layout. A reset still stores nothing, and `defaultSizes(frame)` follows every window resize, so the 22vw
/ 38vh rules are never frozen into the stored px.

**The effect never fights a drag.**
- Its dependencies are primitives only: the three drawn px and `stacked`. A parent re-render (playback, a save) that
  changes none of them does not re-run it.
- While a pane is being dragged (a `draggingRef` in Workspace, set by the first `onLive` and cleared by `onCommit` and
  `onCancel`), the effect skips that pane, so a re-run from another cause (a window resize mid-drag) does not write the
  stored size over the live one.
- `onCancel` re-applies that pane from the current `drawn`, which is the size (or hidden state) drawn when the drag
  began. See D4.

**Commit applies the pane.** `onCommit(action)` computes `next = commitPanes(pane, action, prefs, drawn, frame)`,
calls `setPanePrefs(next)`, clears `draggingRef`, and then calls `applyPane(pane, effectiveSizes(next, frame)[pane])`
itself, as `onCancel` does from `drawn`. The layout effect cannot be relied on for the committed pane: it re-runs only
when one of the three drawn px changes, and a commit whose size equals the pane's drawn size before the drag leaves
the deps unchanged. Concretely, a Timeline at 200 dragged past 100 hides live (0 px, `inert`, `data-hidden`); pulled
back between 100 and 200 it gives `size: 200`, and if the release comes before that frame flushes (every end cancels
the pending frame, D4), the store says shown at 200, the deps go from 200 to 200, and without the explicit apply the
Timeline would stay hidden and inert while React and the separator think it shown. The other panes are left to the
effect: `commitPanes` does not move them, except the Timeline after a bin commit (D1), whose drawn px then changes
and re-runs the effect. `showPane` (D2) goes through the same commit path.

`workspace.css` changes the Timeline row to `'tl tl tl' var(--ws-tl-h, minmax(280px, 38vh))`. `--ws-bin-w` and
`--ws-insp-w` keep their defaults on `html[data-workspace]`, and the inline style on `<html>` overrides them. The
notification region's `inset-inline` then follows the panes with no change: with a side pane hidden its inset is
`0px + var(--s-3)`.

In the stacked layout (`width < 960px`) the properties and attributes are not set, and are removed if present. The
flex column ignores the properties anyway; removing them keeps the toast region's wide rule from reading a stale
width when the window crosses 960 px. Every pane shows there, hidden or not in the store (`paneHidden` is false
while stacked).

### D4. The separator (`edit/workspace/PaneSeparator.tsx`)
```tsx
<PaneSeparator pane="bin" controls={binId} label="Resize the clip bin" size={drawn.bin} limits={lim.bin}
               onLive={live} onCommit={commit} onCancel={cancel} />
```
- **Markup:** `<div role="separator" tabIndex={0} className="ws-sep" data-pane="bin|insp|tl">`, with `data-hidden`
  when its pane is hidden, and:
  - `aria-orientation`: `vertical` for bin and insp, `horizontal` for tl;
  - `aria-controls`: the pane's id (`useId()` ids added to the three sections);
  - `aria-label`;
  - `aria-valuemin="0"` (the hidden state is the range's low end, as APG's collapsible splitter), `aria-valuemax`
    the pane's `lim.max`, and `aria-valuenow` the drawn px (0 when hidden);
  - `aria-valuetext` from `valueText` ("Clip bin hidden" at 0).
- **Labels:** "Resize the clip bin", "Resize the inspector", "Resize the Timeline". The separator is never inside
  its pane, so it stays focusable and named when the pane is inert.
- **DOM order:** `.ws` gets three children. The bin's separator goes right after the bin section, the inspector's right
  before the inspector section, and the Timeline's right before the Timeline section. The Tab order is then: bin,
  bin border, viewer, inspector border, inspector, Timeline border, Timeline; a hidden pane drops out of it and its
  border stays.
- **Focus.** A press must not move focus to the separator (it has `tabIndex=0`, so a browser's default press action
  would focus it, and a focused separator takes Left and Right as an `ARROW_ROLE`). Unlike TrimHandle, which focuses
  its handle on purpose, the separator keeps focus where it was in two ways:
  - `onMouseDown` calls `preventDefault`. This blocks both the focus change and text selection for a mouse press,
    and for a touch tap's compatibility mouse events. It works only because `onPointerDown` does **not** call
    `preventDefault`: a cancelled `pointerdown` suppresses the compatibility `mousedown` (Pointer Events spec), so
    the guard would never run.
  - `onPointerDown` records `document.activeElement`. A `focus` handler on the separator, while a pointer press is in
    progress (the `active` ref), puts focus back on the recorded element with `preventScroll: true`, or blurs the
    separator if nothing was focused or the recorded element is now inside an `inert` pane (it was hidden by this
    drag, D3).
  - **A live hide that does not last gives focus back.** A commit of a hide blurs focus inside the pane (D3); a live hide does not
    (it is only `data-collapsing`). At every end of a drag (release, Escape, `pointercancel`, lost capture), *after*
    `onCommit` or `onCancel` has re-applied the pane, the separator puts focus back on the element recorded at
    `pointerdown` (`focus({ preventScroll: true })`) when all of these hold: the element is still connected, it is not
    inside an `inert` pane, and `document.activeElement` is `<body>` or null. So focus in an inspector field survives
    a drag that hides the inspector live and then drags it back out, or is cancelled by Escape; only a drag that ends
    with the pane hidden leaves focus on the page.

  Touch scrolling and selection during a drag are handled by `touch-action: none` and `html[data-ws-resizing]`'s
  `user-select: none` (D5), not by cancelling `pointerdown`.
- **Pointer** (the TrimHandle drag shape, without its focus move):
  - `onPointerDown` takes the primary button only. It calls `setPointerCapture`, and keeps the drag in an `active`
    ref: the pointer id, the start point, the start size (the drawn px for a shown pane; for a hidden pane the press's `edgeDistance`, below) and the `limits` at the start.
    It sets `data-dragging`, `html[data-ws-resizing="col|row"]`, and a window capture `keydown` listener for Escape.
  - `onPointerMove` does nothing unless `active` holds a drag for that pointer. It computes `dragAction` and writes it
    through `onLive(px)` (0 for `hide`) in a `requestAnimationFrame`, at most once per frame, with no React state
    update. The pending frame's id is kept. The live write is `applyPane` (D3), so the pane hides or reappears while
    the pointer moves, as in VS Code, not only on release.
  - `onPointerUp`: if the pointer moved `DRAG_SLOP_PX` or more on the pane's axis, compute `dragAction` from the
    `pointerup`'s own coordinates and call `onCommit(action)`, which stores `commitPanes(...)` through the store (D1)
    and applies the committed pane (D3, "Commit applies the pane"), so a live frame that was cancelled unflushed
    cannot leave the DOM behind the store. Otherwise call `onCancel()` and save nothing.
  - **Escape** (window capture, `preventDefault`, `stopPropagation`), `pointercancel`, and `lostpointercapture` while
    the drag is still active call `onCancel()`. On Escape the separator also calls `releasePointerCapture` and
    clears `active`. The button is still down, so the moves and the `pointerup` that follow are ignored.
  - **`onCancel` restores the drag's start**, not the stored preference: Workspace re-applies that pane from the
    current `drawn` (D3). A pane hidden live during the drag comes back; a hidden pane dragged partly out hides again.
    In a window that clamps the kept sizes, the stored 600 px bin is not written back over its drawn 386 px.
  - **Every end** (up, Escape, cancel, lost capture, unmount) cancels the pending `requestAnimationFrame`, clears
    `active` and `data-dragging`, removes `data-ws-resizing` and the Escape listener. A frame queued before the end
    can then never write a size after a commit, a cancel or a reset.
- **Double-click** (`onDoubleClick`): on a hidden pane, `onCommit({kind: 'show'})` shows it at its kept size; on a shown pane, `onCommit({kind: 'reset'})` puts it back to today's rule. Its two presses never moved, so
  neither stored anything, and the 22vw / 38vh rule is not frozen into px.
- **Keys** (`onKeyDown`): `keyAction` with the event's Shift, Ctrl, Alt, Meta and `repeat`;
  when it is non-null, call `preventDefault` and `onCommit(action)`. A pane key (the pane's two arrows, Home, End,
  Enter) with no Ctrl, Alt or Meta that `keyAction` turns to null only because it is a repeat (D1) is still
  `preventDefault`ed, so a held key never falls through to a scroll. Space is not taken, and a separator is not a Space control
  (`SPACE_ROLES`), so with single-key shortcuts on it reaches the workspace layer and plays or pauses, whether the
  separator was reached by Tab or by a pointer. With the switch off, Space does nothing there. Enter on a separator
  is the separator's: the workspace layer has no plain-Enter command.
- A hidden pane's Enter and double click are `{kind: 'show'}`; the separator takes no size prop for it. A drag from a
  hidden pane starts at `edgeDistance` (the press's distance from the window's edge), so the pane follows the pointer
  from where it was grabbed. `isPaneKey` is how the separator tells a pane key from any other.
- `aria-valuenow` follows React state, so it updates on commit, on a key and on a window resize, not on every frame of
  a pointer drag. Screen readers do not follow pointer drags.

### D5. Styles (`workspace.css`)
- **Placement.** Each separator is a grid item in its pane's area, aligned to the edge and straddling the 1 px border.
  - `.ws-sep[data-pane="bin"]` has `grid-area: bin; justify-self: end`. Its hit strip is 8 px wide: 2 px inside the bin
    and 6 px into the viewer's 12 px padding, so it does not cover the bin's scrollbar.
  - The inspector's separator mirrors it (`grid-area: insp; justify-self: start`): 6 px into the viewer and 2 px into
    the inspector.
  - The Timeline's separator has `grid-area: tl; align-self: start` and is 8 px tall: 6 px above the line and 2 px
    into the Timeline. It is placed with a negative margin or `translate` so that it does not cover the Timeline's
    sticky tool row.
- **Look.**
  - `position: relative; z-index: 5`: above the inspector's sticky tabs (3) and below the top bar (6) and the alert
    panel (7);
  - `touch-action: none`;
  - the cursor is `col-resize` or `row-resize`;
  - transparent at rest. On `:hover`, `:focus-visible` and `[data-dragging]`, a 2 px line centred on the border in
    `var(--accent)`, with the focus outline in `var(--focus-ring)`. Tokens only.
- **A hidden pane's separator** (`.ws-sep[data-hidden]`). The pane's track is 0, so the separator's area is the
  window's edge: the left edge for the bin, the right for the inspector, the bottom for the Timeline. The part of the
  strip that would lie outside the window is clipped (`.ws`), so the separator is shifted fully inside: an 8 px strip
  from the edge into the viewer's padding (for the Timeline, into the bottom 8 px of the middle row). At rest it draws
  a 3 px line along the edge in `var(--fg-subtle)` with a short centred grip (two 1 px marks), so a hidden pane
  is visible as a handle; on hover, focus and drag it is drawn as any separator. The cursor is the same
  `col-resize` / `row-resize`.
  - **The line's colour.** The line is the only sign that a pane is hidden and the only pointer way back, so it must
    meet WCAG 1.4.11 (3:1 against what lies beside it). `--border-strong` does not: by the tokens' OKLCH lightness
    (relative luminance ≈ L³ for these near-neutrals) it is about 1.5:1 on `--bg` in light (86 % on 98.5 %) and about
    1.7:1 in dark (35 % on 16 %). `--fg-subtle`, the token kept for icons and borders, is about 3.5:1 on `--bg` and
    3.6:1 on `--surface` in light (62 %) and about 4.2:1 on `--bg` in dark (56 %). No new token. Task 3.1 measures it
    from the computed colours; if it falls under 3:1 in either theme, `--fg-muted` is used instead.
  - **The hidden Timeline's strip spans only the viewer's column** (`grid-column: 2` within the `tl` area, both at
    rest and on hover). Across the bin's and the inspector's columns its strip would lie over their last controls:
    ClipInfo's heading is the bin's last 2rem, so its toggle's centre is about 16 px above the window's bottom edge,
    and the inspector's last control sits there when the inspector is scrolled to its end. The viewer's column has its
    12 px padding at the bottom. The line is drawn under the viewer only, which is where the Timeline's top edge is
    met by the pointer coming from the picture.
- **Hidden panes** (`[data-hidden]` on `.ws-binbox`, `.ws-insp`, `.ws-tl`, wide frame only). The section stays
  mounted and laid out, but outside the window and invisible (D8):
  - `visibility: hidden` (no paint, no hit testing; `inert` from D3 takes it out of the Tab order and the
    accessibility tree in every browser);
  - `[data-collapsing]` (the live hide) has the same sizes and translate but no `visibility: hidden`;
  - its own least size, so its content is never laid out at 0: `.ws-binbox[data-hidden] { inline-size: 240px;
    translate: -100% 0 }` (its area is at the left edge, so it is moved out to the left);
    `.ws-insp[data-hidden] { inline-size: 320px }` (its area starts at the right edge, so it lies past it);
    `.ws-tl[data-hidden] { block-size: 200px }` (its area starts at the bottom edge). The figures equal
    `MIN_BIN_PX`, `MIN_INSP_PX` and `MIN_TL_PX`; `workspaceCss.test.ts` pins them against `paneSizes.ts`.
- **Clipping, wide frame only.** `.ws { overflow: clip }`: the hidden panes and any shrink overflow never scroll the
  page. `clip` creates no scroll container, so the sticky headings and tabs inside still stick; the top bar and the
  alert panel lie inside `.ws`, which is the window. `.ws-binbox { overflow-x: clip; overflow-y: auto }`: below the
  middle row's least height the bin's box scrolls instead of clipping a control or painting over the Timeline (in the
  order of D1: the list shrinks first, to its heading and one row; then ClipInfo's body, to its heading; only then the box scrolls). With a coarse pointer it also has `padding-block-end` and `scroll-padding-block-end`
  of 12 px, clear of the Timeline's 24 px strip. Task 3.1 checks for
  clipped focus rings at the bin's edges.
- **Coarse pointer.** `@media (pointer: coarse)` widens the hit strip to 24 px, for WCAG 2.5.8 target size, while the
  drawn line stays 2 px:
  - side borders: centred on the line, 12 px into the viewer's 12 px padding (no control there) and 12 px into the
    pane's edge;
  - the Timeline's border: centred on the line, 12 px above it (the viewer's bottom padding, the bin's and the
    inspector's last 12 px) and 12 px into the Timeline's tool row;
  - a hidden pane's border: 24 px from the window's edge inward (the hidden Timeline's only across the viewer's
    column, above).

  **Exempt from the coarse check: the scrollbar thumbs.** The 12 px overlap into a shown pane covers the centre of a
  classic scrollbar's thumb at the bin's or the inspector's edge (about 7 px from it). A coarse pointer scrolls those
  panes by swiping, not by the thumb, so under coarse emulation the thumbs are not checked; with a fine pointer the
  8 px strip lies only 2 px into the pane and the thumbs are checked.

  **Every other control** near a border must have its centre outside the strip, and task 3.1 checks that under
  coarse emulation. The permitted fix where one does not, decided now because an edge strip cannot move away from
  its edge: that strip's coarse form narrows to 12 px (still clear of the control's centre) and gains a centred grip
  24 px across and 48 px along, part of the separator, as its 24 px target (WCAG 2.5.8; the grip is placed at the
  middle of the edge and must itself clear every control's centre, which 3.1 checks again). Accepting a covered
  control is not a permitted outcome.
- **During a drag.** `html[data-ws-resizing="col"] *` and `[data-ws-resizing="row"] *` set the cursor and
  `user-select: none`.
- **Stacked layout.** `@media (width < 960px) { .ws-sep { display: none } }` takes the separators out of view and out
  of the Tab order. The `[data-hidden]` and `overflow: clip` rules are inside `@media (width >= 960px)`.

### D6. Shortcuts and focus (`edit/workspace/shortcuts.ts`)
- **`'separator'` joins `ARROW_ROLES`.** Arrows on a focused separator then give `null` from `workspaceCommand`, which
  is the rule "an arrow on a widget that takes arrows". This is belt and braces beside the separator's own
  `preventDefault`, which rule 1 already honours through `defaultPrevented`.
- **Home, End, Up, Down and plain Enter** are not workspace keys, so nothing else answers them.
- **During a drag**, `modality.ts`'s `pointerHeld()` already turns the workspace layer off while any primary button is
  down.
- **Modifiers.** `keyAction` returns null with Ctrl, Alt or Meta held, so those chords keep their browser meaning on a
  focused separator; the `ARROW_ROLES` rule then leaves them to the browser too, as on a slider.
- **`SHORTCUTS` gains five rows.** These are `focused` or `mouse` rows, not `workspace` ones, so the
  `workspaceCommand` table tests are unaffected:
  - Editing, `focused`: `[['Left'], ['Right'], ['Up'], ['Down']]`, "On a pane border: move it (Shift: further), past
    its smallest size to hide it";
  - Editing, `focused`: `[['Home'], ['End']]`, "On a pane border: the pane's smallest or largest size";
  - Editing, `focused`: `[['Enter']]`, "On a pane border: hide or show the pane";
  - Mouse: `[['Drag a pane border']]`, "Resize the pane; past half its smallest size it hides";
  - Mouse: `[['Double-click a pane border']]`, "Put the pane back to its first size, or show it again".
- **Pane toggle shortcuts are a follow-up, not scope.** A key that hides or shows a pane from anywhere needs a new
  `Command`, its dispatch in Workspace, a `workspace` row with `presses` and the table tests, and a key: VS Code's
  Ctrl+B and Ctrl+J are the browser's (bookmarks, downloads), and the free single letters are few and would also need
  the single-key switch. That is not a row in the existing table.

### D7. The save explanation follows the Timeline (`Workspace.tsx`)
The layout effect's `ResizeObserver` also observes the `.ws-tl` section, through `top.parentElement`, which is
`.ws`. A changed Timeline height then re-runs `measure`, and the wide panel's `--ws-alert-max` again ends above the
Timeline's new top. During a pointer drag the observer fires per frame. That is acceptable: `measure` reads a few
rectangles and writes two properties, and it already runs per frame during a window resize. Its `setFrame` bails out
on an unchanged frame (D3), so the observer causes no React render during the drag.

**A hidden Timeline.** Its area starts at the window's bottom edge, so `.ws-tl`'s rect top is the window's bottom
(the section is laid out below it, D5): `measure` needs no special case, and the panel's cap is `TOP_MAX_SHARE` of the
window or the room down to the bottom edge, whichever is less. A Timeline drawn at 200 px that hides keeps its
200 px box (now off-screen, D5), so the observer does not see the hide: the section moves but does not resize. So
`applyPane` for the Timeline also calls `measure` (through a ref the layout effect fills) after it writes; it is cheap,
as above.

### D8. A hidden pane stays mounted, out of sight and out of reach
**Considered:**
- **unmount the pane's content.** Rejected: the Timeline renders the single `<video>` and the transport into the
  viewer and the cut panel and card editor into the inspector's tabs; unmounting the Timeline would stop playback and
  drop its state, and unmounting the inspector would drop the portal targets the Timeline writes into. The bin's
  player and ClipInfo would lose their state.
- **`display: none` on the section.** Keeps the React tree, but the browser drops the layout boxes: scroll positions
  (the bin's list, the Timeline's horizontal scroll at a zoom) are lost, every `ResizeObserver` inside reports 0, the
  Timeline's scroller `clientWidth` becomes 0 (Fit and `useVisibleRange` stop), and container queries fall back.
- **A 0-size track with the content laid out at 0.** The same zero-size reports, and container queries and the card
  editor's measurements see a 0-wide pane.
- **Chosen:** the track is 0, and the section keeps a laid-out box at its pane's least size, outside the window,
  with `visibility: hidden` and `inert` (D3, D5). Nothing inside sees a 0 size, scroll positions and state survive,
  the Timeline's width (it spans the columns) never changes, and the content is out of the Tab order, the
  accessibility tree and hit testing.

**What that means for each pane:**
- **The Timeline.** The component stays mounted and keeps playing: its `<video>` and transport are in the viewer,
  which a hidden Timeline does not touch. The workspace's keys still act (Space, the arrows, Q/W) because the
  workspace layer is window-level; only the track's own controls are out of reach. A hidden Timeline keeps its
  follow-scroll during playback, off-screen.
- **The inspector.** The portal targets (`clipSlot`, `cardPane`, `suggestionPane`) stay in the DOM, so the Timeline's
  parts keep rendering into them; a selection made on the track while the inspector is hidden is there when it is
  shown.
- **A save refused at an inspector field shows a hidden inspector.** A refusal the operator cannot see or reach is a
  failure, and a focus into an `inert` pane fails silently. Three refusals land in the inspector: at the Event tab's
  Details fields (the reducer's `refusal`, focused through `refusalRef`), at a title card's field (`cardRefusal`, whose
  effect calls `openCard`) and at the card style's field (`styleRefusal`, shown in the card editor, which this change does not open: a style refusal only shows the inspector). In
  `EventEditor.tsx`:
  - the answers effect, when the answer carries any of the three and `isPaneHidden('insp')` (D2), calls
    `showPane('insp')` first; the `cardRefusal` effect does the same before `openCard`;
  - the Details refusal waits whenever it cannot take focus yet, **independent of the tab**: `refusalWaits` is set
    when the inspector is hidden *or* the refusal is inside `.ws-insp-panel[hidden]` (another tab shown, which also
    calls `setInspectorTab('event')`); the effect then returns without focusing;
  - the waiting focus moves to a layout effect keyed on `inspectorTab` **and** `inspHidden = usePaneHidden('insp')`.
    It focuses only when `refusalWaits` is set, the Event tab is shown and the inspector is not hidden.
    `showPane`'s store change re-renders EventEditor and Workspace in one commit; Workspace is the child, so its apply
    layout effect (and `showPane`'s own `applyPane`) has removed `inert` before EventEditor's layout effect runs. This
    also covers the case the existing code misses: the Event tab already shown, only the inspector hidden, where the
    old code would focus at once into the `inert` pane and nothing would retry.

  Task 2.4 checks every other `.focus()` call in `edit/` and `timeline/` whose target can be inside a hideable pane,
  and either shows the pane or leaves focus alone, named in the task's notes.
- **The bin.** Its state (selection, scroll, the player's shown clip, ClipInfo) survives. Its player's open preview is
  closed when the bin hides, as Hide player does, so no hidden video keeps playing sound. Only the preview-closing
  layout effect in `BinPlayer.tsx` reads the hidden bin: its condition becomes
  `!wanted || binHidden || held !== shown` with `binHidden = usePaneHidden('bin')` in its deps. `wanted` itself is
  not changed: setting it false would swap the player for the Show player button portalled into the bin's toolbar,
  unmounting the player's bar and remounting it on show. Stacked, `usePaneHidden` is false (D2), so a stored
  `hidden: ['bin']` never closes a preview or hides the player in the stacked page. `overBin` returns false while
  `isPaneHidden('bin')` (read when it is called; its rect is outside the window anyway, the check is explicit), so a
  track drag never drops into a hidden bin and every track-to-bin drop still works in the stacked page. A drag from
  the bin needs a visible bin and works as before once it is shown.

**Pointer and rect readers with a hidden pane:**
- `overBin`: false (above).
- The notification region: its inset reads the 0px track, so it spans to `var(--s-3)` from the window's edge.
- The alert cap: D7.
- `useVisibleRange`, Fit, `zoomTo`: unchanged width; the Timeline's 200 px off-screen height is irrelevant to them.
- `ClipBin.tsx`'s scroll test (`pane.scrollHeight > pane.clientHeight`): reads the off-screen 240 px box, harmless.

### D9. Nothing in the Timeline changes
- The Timeline's width does not change with a side border or a hidden side pane, and Fit already follows window
  resizes.
- A taller or shorter Timeline only changes how much of the pane scrolls vertically.
- `binPlayerPref.ts`'s window-height default (`SHORT_WINDOW_QUERY`) is left as it is and documented as an
  approximation once the Timeline height is a preference. It is only a default: an explicit Show or Hide wins.

## Defaults chosen

The operator settled collapsing ("I want all the panes to be resizable and hide if i resize them to min"), so the
earlier open question on collapse is closed (D1, D4, D8). These remain defaults this change adopts; any can be
revisited before task 1.

1. **Minimum sizes.**
   - **Chosen:**
     - bin 240 px minimum (today's least, the compact player's guarantee);
     - inspector 320 px minimum (its four tabs: 3.1 measured that "Title card" wraps at 300 and fits from 310 in Chromium, and 320 in Firefox, whose tabs are wider);
     - Timeline 200 px minimum, below today's 280 px floor so the picture can grow (task 3.1 checks that the tool row,
       the ruler and the video lane stay visible);
     - the viewer at least 20rem wide; the middle row at least 20rem tall with the bin shown and 14rem with it hidden
       (D1; task 3.1 measures both);
     - the pane minimums win over the viewer's and the middle row's where the window cannot hold all of them, and
       then content scrolls inside the panes (the bin's box scrolls, D1; the others' bodies scroll); nothing auto-hides and the page never scrolls (D1);
     - no fixed maximums: the bin's and the inspector's come from the viewer's minimum, and the Timeline's from the
       middle row's.
   - **Not chosen:** forbidding sizes below today's defaults (240 / 340 / 280). Safer for the existing gates but less
     flexible, and moot now that a pane can be hidden.
2. **The snap.** **Chosen:** hide under half the minimum, the same threshold both ways (VS Code). **Not chosen:**
   hiding at the minimum itself (a drag to the minimum would then hide by accident), or a fixed px threshold (the
   Timeline's and the bin's minimums differ).
3. **Where a hidden pane comes back.** **Chosen:** at its kept size by double-click and Enter (today's rule if never
   resized), and by a drag where the pointer leaves it (from the minimum). **Not chosen:** always at the minimum,
   which loses the operator's size for a pane hidden for a moment. A pane collapsed by the arrow keys keeps the last
   size it was stepped to, since every key press is a commit (D1).
4. **Home on a border.** **Chosen:** the smallest shown size; Enter hides (D1).
5. **Persistence.**
   - **Chosen:** per browser, global across events and visits (`localStorage` `auto-reel:workspace-panes`), as the
     bin player is, hidden panes included.
   - **Not chosen:** per event, or per tab session as the Timeline zoom is.
6. **A drag into the viewer's limit.** **Chosen:** the dragged pane stops and the other side pane keeps its width.
   Only a window resize shrinks both, proportionally to their excess over their minimums (D1). A commit made while
   the window shrinks them stores both drawn sizes, so nothing moves on release.
7. **A row in the Keyboard shortcuts list.** **Chosen:** yes. D6 adds three `focused` rows and two `mouse` rows, and
   the delta modifies "The workspace lists its keyboard shortcuts" to name the pane borders.
8. **Shortcuts that toggle panes.** **Chosen:** a follow-up (D6), not scope.

## Research & Decisions

### Where the sizes live
**Considered:**
- React state with an inline `grid-template` on `.ws`;
- new CSS properties on `.ws`;
- the existing `--ws-bin-w` and `--ws-insp-w` on `<html>`.

**Decision:** the existing properties on `<html>`, plus a new `--ws-tl-h` (D3).

**Rationale:** the notification region already reads them from `<html>`, so it follows with no change, a hidden pane
included. CSS keeps the default rule as the `var()` fallback, and a pointer drag writes one property per frame
without a React render.

### A splitter library
**Considered:** `react-resizable-panels` and similar, which also offer collapsible panels.

**Decision:** none.

**Rationale:** the workspace is one CSS grid with a stacked fallback and a portal-based Timeline, and a panel library
would replace that layout and own the panes' mounting. The repo already has its own pointer-drag idiom (TrimHandle,
EdgeHandles). Three separators with pure maths, collapse included, are about 300 lines. Adding a library would also
break the change's no-new-dependency rule.

### Separator vs a plain handle
**Decision:** a focusable `role="separator"` with a value (WAI-ARIA window splitter pattern), Enter to collapse.

**Rationale:** resizing and hiding then work for keyboard and screen-reader users too (WCAG 2.1.1). The arrows conflict
with the workspace layer, which D6 handles with the existing `ARROW_ROLES` rule.

### Saving on pointerup only after movement
**Decision:** save only when the pointer moved at least `DRAG_SLOP_PX` (D4).

**Rationale:** a double-click's two presses would otherwise store the current, window-relative default as px, so the
reset would undo itself.

## Risks / Trade-offs

- **A focused separator fighting the workspace arrows.** If a press left focus on the border, Left and Right would
  resize the pane instead of stepping the playhead. Two things keep focus where it was (D4):
  - `onMouseDown` calls `preventDefault`, which only runs because `onPointerDown` does not cancel;
  - the focus handler puts focus back if a browser focuses the separator on `pointerdown`.

  `separator` in `ARROW_ROLES` and the separator's own `preventDefault` only matter once the border was focused on
  purpose (by Tab). Task 2.3 verifies in Playwright, in Chromium and Firefox, that `document.activeElement` is
  unchanged after a drag and after a press without movement.
- **Focus in a pane that hides.** It is blurred to the page (D3). A keyboard user hiding with Enter keeps focus on
  the separator, so this only affects a pointer hide, where the pointer user did not rely on that focus. Accepted for
  a drag that ends with the pane hidden; a drag that hid the pane only live gives the focus back at its end (D4).
- **Accidental hides.** A fast drag past half the minimum hides a pane. The border stays at the edge, drawn, and
  Escape before release, a drag back, a double-click or Enter brings it back at its size. Accepted, as in VS Code.
- **The apply effect fighting a live drag.** A live write and the layout effect write the same property and
  attributes. D3 keeps them apart: `frame` bails out on unchanged numbers, the effect depends on primitives, it skips
  the dragged pane, and React owns neither `inert` nor `data-hidden`. Task 3.1 drags the Timeline's border slowly,
  with and without playback, and checks that its height follows the pointer monotonically.
- **`overflow: clip` on `.ws`.** Anything that today paints past `.ws` would be cut. `.ws` is the window in the wide
  frame, so only paint past the window is lost; fixed-position menus and the top layer are unaffected. Task 3.1 opens
  the clip menu, the shortcuts list and a toast at the window's edges to check.
- **A hidden pane's off-screen layout cost.** It still lays out on a window resize and, for the Timeline, during
  playback, as today. No new cost.
- **Hit strips over controls.** The strips could cover the bin's scrollbar, ClipInfo's toggle, the inspector's bottom
  content above the Timeline's line, the Timeline's sticky tool row, or, for a hidden pane's edge strip, the
  transport's or the bin's controls nearest the window's edge. The strips are biased into the viewer's padding and
  above the Timeline's line, and a hidden Timeline's strip spans only the viewer's column. Task 3.1 checks
  `elementFromPoint` at every control's centre near each border, hidden panes included; under a coarse pointer the
  scrollbar thumbs are exempt and a failure has one permitted fix (D5).
- **The stale alert cap.** Covered by D7, and verified in 3.1 by a 412 conflict after a drag of the Timeline's border
  and with the Timeline hidden.
- **The alert cap at the moment of a hide or show.** The Timeline's section moves without resizing when it hides at
  200 px or shows from hidden at 200 px, which a `ResizeObserver` does not report; D7's direct `measure` call covers it.
- **A narrow, tall viewer.** It letterboxes the picture inside the 16:9 stage, and a black card paints the whole stage.
  This already happens at 960 px and is now easier to reach. Task 3.1 checks both themes at the viewer's minimum.
- **The toast region.** It must keep reading the same properties on `<html>` (D3). The viewer's 20rem minimum leaves
  it at least `20rem − 2·s-3` wide.
- **The middle row's minimum with ClipInfo open or a coarse pointer.** At 20rem the list can drop under one row
  (ClipInfo open) or the player can fill the bin (coarse pointer); the list shrinks to one row, then ClipInfo's body, then the bin's box scrolls (D1's order), and nothing paints over the Timeline. Accepted rather than a 25rem minimum that would change an untouched 1280×720 workspace.
- **The bin player's height default** is approximate once the Timeline's height is chosen (D9). Accepted and
  documented.
- **Drag cost.** Each frame re-lays the grid, including the bin's list and the inspector. The property is written in
  `requestAnimationFrame` with no React render, and task 3.1 measures the frames on a 400-clip event and checks that
  Workspace renders 0 times between pointerdown and pointerup.
- **Windows under the range.** Under 568 px tall with the bin shown, the middle row gives way and the bin's content
  clips (D1). This is a change from today only below 648 px tall, where an untouched Timeline now shrinks from 280 px
  to keep the middle row 20rem: today the 280 px Timeline wins there and the bin's player is squeezed. The operator
  hides a pane when there is not room for all of them.
- **Crossing 960 px with stored sizes or hidden panes.** The sizes are clamped, never overflowing, and neither sizes
  nor hidden panes apply when stacked. The spec's no-page-scroll guarantees and the stacking below 960 still hold.

## Failure behaviour

Layout and input only: nothing is written to the server and nothing is requested.
- When storage is unavailable, sizes and hidden panes last for the page visit.
- A stored value that does not parse is ignored, as if nothing were stored: every pane shows at today's rule. It is
  not rewritten until the operator resizes, hides or shows a pane.
