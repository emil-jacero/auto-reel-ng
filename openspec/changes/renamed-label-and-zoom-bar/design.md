## Context

See proposal.md, "Why". This change works on main 93721b3 once `output-renamed-reason` (Z2) has archived. Its
code is `web/src/events/labels.ts` with its two call sites, and `web/src/edit/`.

- **Reasons in words.** `REASON_LABEL: Record<StalenessReason, string>` (`labels.ts:11-18`) is the only
  place a reason gets words. `StalenessCell` (`common.tsx:82-97`) shows the verdict pill and the reasons,
  comma-joined, in `.reasons`. Both screens use it: the list row (`EventList.tsx:176`) and the page's
  `RenderPanel` (`EventDetail.tsx:413`, which wraps it in `.render-panel`, `detail.css:119`). `.verdict` is
  `inline-flex; flex-wrap: wrap` and `.reasons` is muted small text (`components.css:654-664`).
  `StalenessReason` is generated (`schema.d.ts:784`). An exhaustive `Record` over it makes a new member a
  `tsc` error at `labels.ts:11`.
- **The save bar** (`SaveBar.tsx`, `edit.css:533-550`). `.save-bar` is `position: sticky;
  inset-block-end: 0; z-index: 6`, transparent and click-through, with `--s-4` padding below its card. It is
  the last child of `.event-editor`, after the last chapter (`EventEditor.tsx:903`).
- **Publishing the bar** (`EventEditor.tsx:564-586`). A layout effect keyed on `showBar` does three things:
  - it writes `bar.offsetHeight` to `--toast-inset-bottom` on `<html>`, and keeps it current with a
    `ResizeObserver` on the bar
  - it registers the bar with `keepToastsClearOf(bar)` (`ui/toast.ts:144`)
  - on cleanup, it releases the registration and removes the property

  Two consumers read the property. `html`'s `scroll-padding-bottom` (`shell/shell.css:11-14`) adds it to
  `--toast-region-h`, `--toast-rise-h` and `--s-4`. The toast region uses it only when no bar is registered
  (`components.css:734`).
- **Placing the toasts** (`ToastRegion.tsx:229-275`). With a bar registered, the region sits at the window's
  bottom when the room under the bar fits it. Otherwise it sits just above the bar's top
  (`viewport − box.top`), and it publishes `--toast-rise-h`. It works on the bar's rectangle, so it never
  asks whether the bar is sticky.
- **After a save's answer** (`EventEditor.tsx:588-612`). A passive effect keyed on `answers` checks the
  focused control. When the control is not fully inside the window, it calls
  `scrollIntoView({ block: 'nearest' })`. This is edit-mode-polish's fix for a short window held at its top.

## Supervisor decisions (2026-10-01)

Recorded before implementation. Where they differ from a section below, they win, and that section says so.

- **Context.** The brief is `plan/brief-decisions.md` (Z3). The operator agreed to words for the renamed
  reason and to a save bar that stops being sticky above about 40 % of the window.
- **Wording: confirmed.** The list says `movie name changed` (landed with `output-renamed-reason`, see "The
  gate as landed" below). The event page adds, on a line of its own: "The next render saves the movie under its
  new name. The movie under its old name stays on disk."
- **A focused bar control follows a bar that goes from held to resting: confirmed.** edit-mode-polish's focus
  rules require it ("A focused control follows a bar that starts to rest").
- **The two-fifths threshold and its consequences: accepted.** At 400 % zoom even the plain bar rests, and a
  failed save's bar rests at 844 × 340 and 683 × 330. This amends `ui-a11y-polish`'s ruling "the save bar stays
  sticky, no `position: fixed`" for short windows only: wherever the bar takes two fifths of the window or less
  it stays sticky, and nothing uses `position: fixed`.
- **One notification over the row above a resting bar: option (a).** This change also MODIFIES web-app's
  "Notifications never cover the save bar": its focus sentence ("A control that receives keyboard focus SHALL NOT
  be left under a notification…") is scoped to a bar that is not resting for its height, and to no bar. While
  the bar rests because it would take more than two fifths of the window, a notification may cover a control
  just above the bar; it still never overlaps the bar. Option (b), room kept above a resting bar and a
  `ToastRegion` that places itself again when the bar moves, is a follow-up (`web/src/ui/`). This supersedes
  "The toast contract in both states" where it says the change leaves that sentence as it is, the matching Open
  Question, and task 3.2's "report as a known violation": the stops are now reported as the case the narrowed
  sentence leaves out, with their visible shares.
- **The web-app scenario "A stale event names every reason" is owned here.** No other change in this round
  modifies "The event list shows every event with its render state".
- **The gate as landed** (task 1.1, main `d77745d`):
  - `openspec/changes/archive/2026-10-01-output-renamed-reason` exists; `StalenessReason` is
    `"no_manifest" | "output" | "output_renamed" | …` (`schema.d.ts:795`).
  - Z2 landed the final list words, `output_renamed: 'movie name changed'` (`labels.ts:14`), not the provisional
    ones (Z2's own supervisor decision). Task 2.1's `REASON_LABEL` edit is therefore a no-op; `REASON_NOTE` is
    still added. `npx tsc --noEmit` passes at the gate.
  - The published description of `output_renamed` says the next render writes under the new name and leaves the
    old file where it is, and that "only a render of another event that now has the old name replaces that
    file" (an exception documented in change-detection, HLD D-9 and the root `README.md`). The page's note speaks
    for this event's next render, which never touches the old file, so it stays true; it names no exception and
    no file, as decided.
  - `web/README.md`'s dev-library bullet ("stale for `editorial`, `output`, `clip_set` and `no_manifest`") was
    left to this change; task 4.1 updates it.
  - The MODIFIED list requirement re-based on the current `openspec/specs/web-app/spec.md` with no other
    difference than this change's two scenarios.
- **Implementation notes** (recorded during apply):
  - The threshold also rests a failed save's bar in other short portrait windows that edit-mode-polish's
    short-window check uses: a conflict at 320 × 700 (46 %), 340 × 700 (43 %) and 375 × 667 (44 %), and a write
    failure there (49–52 %). Its check (after the answer, Save and the whole card are inside the window) passes
    in all of them. 390 × 844 keeps the held bar (26 % / 31–36 %). *Supervisor review: accepted as is.*
  - At 320 × 230 (recorded, not gated) the moved row is 134 px tall and the band between the sticky chapter
    heading and the window's bottom is 129 px, so the row cannot be wholly visible whatever the bar does; the
    focused Move down is. *Supervisor review: accepted as recorded.*
  - With an error toast and a resting bar at 320 × 256, the toast sits above the window at 21 of 124 scroll
    positions (main: 88), for example right after the answer, while the bar's top is above the window: the
    unchanged `ToastRegion` places it just above the bar's top. It shows again below the bar at the page's end.
    *Supervisor review: accepted for now; part of follow-up (b).*
  - Task 2.1's grep `renders under the new name` finds nothing: the note says "saves the movie under its new
    name", and Z2's provisional words never landed.
- **Follow-up (b)** (`web/src/ui/`, not this change): keep room between the last chapter and a resting bar (for
  example a margin of `--toast-rise-h`), and have `ToastRegion` place itself again when the bar moves without a
  scroll, so that (1) a toast never covers the controls just above a resting bar (5 Shift+Tab stops at
  320 × 256 and 4 at 320 × 568 today, `Remove borttagen.mp4` fully covered), and (2) a toast never sits above
  the window while the bar's top is above it (21 of 124 positions at 320 × 256). Then the focus sentence of
  "Notifications never cover the save bar" can be widened again to a resting bar.

## Goals / Non-Goals

**Goals:**

- Give the gate's new reason words that say what will happen: short words on the list, the full sentence
  on the page. Keep every vocabulary map exhaustive, including the new note map.
- Make the bar stop covering the editor wherever it is taller than two fifths of the window, without
  changing it where it already fits: 390 × 844, 1280 × 900, and the plain "Unsaved changes" bar of a
  320-wide window (117 px) in any window taller than about 292 px.
- Keep both halves of the toast contract working in both states, and measure them.
- Never let the bar's change of state take the control that has keyboard focus out of the window.

**Non-Goals:**

- Anything in `web/src/ui/` (toast placement), `web/src/api/`, `web/openapi.json` or the engine.
- Collapsing or scrolling the alert inside the bar. edit-mode-polish rejected a scroller in a sticky
  element, and nothing here needs one.
- The sticky page header and chapter headings. They stay sticky. The probe found no focus stop under them
  once the bar rests.

## Research & Decisions

### Findings, reproduced

**Context**: The brief asks that both problems be reproduced first, with file:line evidence.

**Explored**:

- **Environment**, all under the session scratchpad
  `…/scratchpad/decisions-spec/renamed-label-and-zoom-bar/`:
  - a dev library built by `scripts/make_dev_library.py` against the database
    `arel_spec_renamed_label_and_zoom_bar`
  - the client built from `git archive HEAD web` in a `node:22` container
  - `serve` on :8124, through main's venv with `web_dist_dir` pointed at the scratch build (`serve.py`)
- **Browser**: Playwright 1.49 in `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `--network host`
  and the Noto `fonts.conf` of the final verification.
- **Writes**: every `PUT …/reel` was fulfilled in the browser with a mocked 412, or with a 502 whose detail is
  a real-length temporary path. Every other non-GET was aborted. The one exception was the toast probe's
  real `POST /jobs` for `2024-07-14 - kalas`, which the collision answers with 409 and which creates no job.
- **Files**: scripts `pw/repro.py`, `pw/fix.py`, `pw/labels2.py` and `pw/resize.py`; logs in `pw/logs/`;
  shots in `pw/shots/`.

**Decision**: Both reproduce. The conflict's card is the brief's 306 px. The failure's card is 289 px
with this probe's longer detail (the critic's shorter detail gave 274 px).

**The renamed event** (`repro.py labels`):

- `make_dev_library.py` renders Grillning, then sets its title to "Grillkväll med grannarna". Its
  `render-manifest.json` records `"output": "2024-06-27 - Grillning med Grannar.mp4"`, and
  `library-output/2024/` holds that file.
- `GET /api/v1/events` gives `["editorial", "output"]`.
- The list row and the page both read "Needs render · edited since last render, movie file missing", in
  both schemes, at 1280 and 390. The list's verdict cell is 218 px wide and three lines (61 px) at 1280.

**The bar at short windows** (`fix.py sizes` on main's build, Sommarlov, Move down on the first clip, then
Save). "Bar" is `.save-bar`'s `offsetHeight` (the card plus its 16 px foot). That is the value published as
`--toast-inset-bottom`, and the value the rule below compares.

| Window | Plain bar | Conflict | Write failure | Shift+Tab from Save (18 stops) |
|---|---|---|---|---|
| 320 × 230 | 117 px, 50.9 % | 322 px, 140 % | 305 px, 133 % | 16 fully hidden, both kinds |
| 320 × 256 | 117 px, 45.7 % | 322 px, 125.8 % (card top −66) | 305 px, 119 % (card top −48) | 15 / 16 fully hidden |
| 320 × 568 | 117 px, 20.6 % | 322 px, 56.7 % | 305 px, 53.7 % | 0 hidden |
| 844 × 340 | 77 px, 22.6 % | 163 px, 47.9 % | 206 px, 60.6 % | 0 hidden |
| 390 × 844 | 77 px, 9.1 % | 223 px, 26.4 % | 265 px, 31.4 % | 0 hidden |
| 1280 × 900 | 77 px, 8.6 % | 163 px, 18.1 % | 187 px, 20.8 % | 0 hidden |

The plain bar is also too tall at 400 %. After the first Move at 320 × 256, the focused Move button is 80 %
visible and its row 28 %. At 320 × 230, the button is 0 % visible and its row 21 %. That already breaks
edit-mode-polish's "fully visible together with its whole row".

The verifier's 101 px for the plain bar measured the card. With its foot the bar is 117 px.

### The reason's words: short on the list, full on the page

**Context**: The gate publishes a reason meaning "the movie's name changed since the last render, and the
movie under the old name is still on disk". The user decided that the old file is kept. The brief asks for
words "decided with the design system's tone", short on the list and full on the page.

**Explored**:

- **The existing words**: lower-case phrases, comma-joined: "never rendered", "movie file missing",
  "edited since last render", "project defaults changed", "clips changed", "render engine updated".
- **"renamed"** alone is ambiguous. It could mean the folder, the event or the file.
- **Z2's provisional words**, the brief's example `'renamed — renders under the new name; the old movie
  stays'` (Z2 task 4.1), were measured in the same probe. Grillning's verdict cell grows to four lines (81 px)
  at 1280 and 320, and three (61 px) at 390. A clause with a dash and a semicolon also reads badly inside a
  comma-joined list.
- **The critic's "movie will be renamed"** is wrong: nothing is renamed. A new movie is written and the old
  one stays.
- **Space on the list**: "movie name changed" is exactly as long as "movie file missing" (18 characters).
  Grillning's row keeps its height at 1280 (three lines, 61 px) and at 390 (42 px). `labels2.py` measured only
  the provisional words. The review measured these words on a build with the design's `labels.ts`, with
  Grillning's reasons rewritten in the browser to `["editorial", "output_renamed"]` (`review/pw/labels.py`):
  61 px at 1280, 42 px at 390 and 61 px at 320, in both schemes, with no `.reason-note` on the list.
- **The page**: the render panel has a full line under the verdict. A sentence inside the comma-joined
  reasons would read badly, because it would be a clause with its own full stop inside a list.

**Decision**:

- `REASON_LABEL.output_renamed = 'movie name changed'`, on both screens. It replaces Z2's provisional
  words.
- The page adds, on a line of its own under the reasons: **"The next render saves the movie under its new
  name. The movie under its old name stays on disk."** It says what the render does and what it leaves
  alone. It gives no instruction to delete anything, because the user chose to keep the old movie.
- No file is named. The response carries only the reason (Principle I). Building D-9's name in the client
  would duplicate the engine's rule (Principle V).

**Rationale**: The short words parallel the reason they replace for this case, and fit the list's cell as
before. The note answers the question the critic raised: "is my movie gone?"

### Where the note lives

**Context**: `StalenessCell` is shared by both screens. Only the page shows the note.

**Explored**:

- **(a)** a second exhaustive map plus an opt-in prop on `StalenessCell`
- **(b)** a second, full label map for every reason, chosen by the page
- **(c)** a separate `ReasonNotes` component, mounted by `RenderPanel` beside the cell

**Decision**: (a).

```ts
// labels.ts
/**
 * What the event page adds, on a line of its own, for a reason whose words alone
 * do not say what the next render does; null for the others. Exhaustive like the
 * labels, so a new reason is a decision here too.
 */
export const REASON_NOTE: Record<StalenessReason, string | null> = {
  no_manifest: null,
  output: null,
  output_renamed:
    'The next render saves the movie under its new name. The movie under its old name stays on disk.',
  editorial: null,
  defaults: null,
  clip_set: null,
  engine: null,
}
```

```tsx
// common.tsx
export function StalenessCell({
  staleness,
  explain = false,
}: {
  staleness: Staleness
  /** The event page: each cited reason's note, when it has one, on a line of its own. */
  explain?: boolean
}) {
  // …pill and .reasons unchanged; then, when explain && staleness.stale:
  //   each REASON_NOTE[reason] that is not null → <span className="reason-note">{note}</span>
}
```

`RenderPanel` changes one line: `<StalenessCell staleness={event.staleness} explain />`. In `detail.css`
(`@layer screens`), after the `.render-panel` rule, so that rule keeps its comment:

```css
/* A reason's note (labels.ts REASON_NOTE): a line of its own under the verdict's reasons. */
.render-panel .reason-note {
  flex-basis: 100%;
  color: var(--fg-muted);
  font-size: var(--text-sm);
}
```

**Rationale**:

- (b) would write six sentences nobody asked for.
- (c) would split one verdict across two components that must agree on `stale`.
- (a) keeps the list's markup byte-for-byte, and keeps the page's verdict and its note in one `.verdict`
  wrap.

A `<span>` is used because `.verdict` is a `<span>` (phrasing content), and `flex-basis: 100%` gives it its
own line. In the prototype (`labels2.py`, Grillning's response rewritten to `["editorial", "renamed"]`,
the brief's example name, before Z2 chose `output_renamed`), the note was one line at 1280, two at 390 and
three at 320. It is 13 px `--fg-muted` in both schemes, with no horizontal scroll. The list showed no note.
The review repeated this with `output_renamed` and found the same. It also moved the movie of
`2024-06-21 - Midsommar - Dalarna` aside: its reasons were `["output"]`, both screens read "movie file
missing", and the page showed no note. `2023-06-23 - Midsommar - Dalarna` read "Up to date" with no note.

### The bar rests above two fifths of the window

**Context**: The user agreed that a bar taller than "~40 %" of the window stops being sticky and sits in flow
after the editor. The supervisor's earlier ruling for `ui-a11y-polish`, "the save bar stays sticky, no
`position: fixed`" (that design, line 70), was about where a toast goes. This change keeps the bar sticky
wherever it fits.

**Explored**:

- **A CSS media query** (`@media (height < 30rem)`): it would un-stick the plain bar at 844 × 340 and
  683 × 330, where it is fine (verifier). It also cannot see a bar that grows with its content.
- **Capping the card and scrolling inside it**: edit-mode-polish rejected a focusable scroller in a sticky
  element.
- **A share of the window, measured on the bar itself**. The bar's height does not depend on where it sits:
  the same containing block gives the same width. Measured: 117, 305 and 322 px in both states. So the rule
  cannot oscillate.

**Decision**:

- **Rule**: the bar rests when `bar.offsetHeight > document.documentElement.clientHeight × 0.4`, and is held
  otherwise. `clientHeight` is the viewport height `ToastRegion` already uses.
- **Why two fifths**: it is edit-mode-polish's own ceiling for a held bar at 390 × 844 (failure ≤ 2/5,
  conflict ≤ 1/3). Every bar that requirement allows therefore stays held. Even a bar of exactly two fifths
  leaves the editor only `3/5 × H − header − chapter heading`, which is 62 px at 320 × 256.
- **Expected results**, from the table above:
  - 320 × 256 and 320 × 230: every state rests, the plain bar included (46 % and 51 %)
  - 320 × 568, 844 × 340 and 683 × 330: the plain bar stays held, a conflict or a failure rests
    (48 % to 62 %)
  - 390 × 844 and 1280 × 900: everything stays held

```ts
// EventEditor.tsx, module scope
/** Above this share of the window's height the save bar rests in the page instead of being held. */
const HELD_BAR_MAX_SHARE = 0.4

/**
 * Hold the bar at the window's bottom while it takes at most two fifths of the
 * window; taller (a failed save in a short window, any bar at 400 % zoom) it would
 * hide the editor, so it rests in the page after it (`data-rests`). Only a held bar
 * takes room at the window's bottom: `--toast-inset-bottom` is its height then, and
 * absent while it rests. A held bar that starts to rest takes its focused control
 * to the page's end, so the page follows it there.
 */
function placeBar(bar: HTMLElement): void {
  const root = document.documentElement
  const rested = bar.hasAttribute('data-rests')
  const rests = bar.offsetHeight > root.clientHeight * HELD_BAR_MAX_SHARE
  bar.toggleAttribute('data-rests', rests)
  if (rests) {
    root.style.removeProperty('--toast-inset-bottom')
  } else {
    root.style.setProperty('--toast-inset-bottom', `${bar.offsetHeight}px`)
  }
  const focused = document.activeElement
  if (rests && !rested && focused instanceof HTMLElement && bar.contains(focused)) {
    focused.scrollIntoView({ block: 'nearest' })
  }
}
```

```css
/* edit.css, @layer screens, after .save-bar: taller than two fifths of the window, it rests in the page. */
.save-bar[data-rests] {
  position: static;
}
```

**Rationale**:

- **One measured rule, in the one place that already measures the bar.** The attribute is set on the DOM
  node, not held in React state, so no extra render follows. React never reconciles `data-rests` because no
  JSX sets it.
- **`position: static`.** It drops the stuck offset. `z-index: 6` then has no effect, and nothing needs to
  overlap.
- **Same order as before.** The bar is already the editor's last child, so "in flow, after the editor" needs
  no DOM move.

### When the bar decides

**Context**: The decision has to be made before the answer's focus scroll runs. If not, the scroll measures
Save at its sticky place, finds it inside the window, and does nothing. Then the bar drops to the page's end
and takes Save out of view.

**Decision**: `placeBar` runs from four places.

1. **The existing `[showBar]` layout effect**, in place of today's `publish`. It runs on mount. The
   `ResizeObserver` already watches the bar. A new `window` `resize` listener is added, because zoom and a
   window resize change `clientHeight` without resizing the bar. The cleanup removes the listener, as it
   already releases the registration and removes the property.
2. **The `ResizeObserver`**, for later changes to the bar's own size, such as wrapping.
3. **The `resize` listener**.
4. **A new layout effect with no dependency list**, right after it:
   `if (showBar && barRef.current !== null) placeBar(barRef.current)`. It runs in every commit that can
   change what the bar shows: an answer, a summary or a pressed state. It runs before paint, and before the
   passive `answers` effect, which then sees the final layout. Its cost is one `offsetHeight` read per
   commit while the bar shows.

The `answers` effect is unchanged. It already scrolls a focused control that is outside the window into
view, which is how "the page scrolls to the bar" happens after an answer. A held bar that starts to rest for
any other reason (a resize or a zoom) has no answer behind it, so `placeBar` itself follows a focused control
of the bar (next section).

**Explored**: The prototype (`fix.py sizes`, same matrix, both schemes) reached Edit, Move down and Save by
keyboard. The full keyboard-only path (Tab to Edit, Tab to the first Move down, Tab to Save) was checked with
`resize.py`. Results:

- **320 × 256 and 320 × 230**:
  - After the first Move, the bar rests, and the focused Move and its row are fully visible.
  - After a conflict or a failure, the bar rests, `--toast-inset-bottom` is absent, and Save is 99 %
    sampled visible (edge sampling). Its alert sits above it.
  - A Shift+Tab walk of 18 stops and a Tab walk of 20 stops found 0 fully hidden and 0 under 95 % visible.
- **320 × 568**:
  - The plain bar is held.
  - The conflict and the failure rest. After the answer, Save is in view and the whole card is inside the
    window. This is the edit-mode-polish scenario, still true.
  - 0 hidden stops.
- **844 × 340**: the plain bar is held. The conflict and the failure rest, with 0 hidden stops.
- **390 × 844 and 1280 × 900**: held as before, with `--toast-inset-bottom` equal to the bar's height and
  unchanged numbers.
- **Resize**: 320 × 256 (rests) → 390 × 844 (held, inset 223 px) → 320 × 256 (rests again). With the
  first prototype, Save still had focus back at 320 × 256 but its card sat at y = 693–999 in a 256 px
  window (`resize.py`, `logs/resize-main.log`). The next section fixes that.

### A focused control follows a bar that starts to rest

**Context**: Added in review. The likely way into a short window is a zoom: an operator sees a failed save
at 100 % and zooms in to read it. The bar is held while Save has focus, the zoom makes it rest, and it moves
from the window's bottom to the page's end. No answer is pending, so the `answers` effect does not run. The
page does not scroll with the bar, and Save leaves the window while it keeps focus.

**Explored**: The review rebuilt the scratch environment (main + Z2's `output_renamed` member in
`schema.d.ts` + the first prototype) under `…/renamed-label-and-zoom-bar/review/` and ran `pw/zoomin.py`:
Sommarlov, keyboard Move down and Save, a mocked 412 or 502, then `set_viewport_size`.

| From → to | First prototype: Save visible | With the follow below |
|---|---|---|
| 1280 × 900 → 320 × 256 | 0 %, card top y = 1124 | 99 %, card top y = −56 (conflict), −39 (failure) |
| 390 × 844 → 320 × 256 | 0 %, card top y = 840 | 99 % |
| 390 × 844 → 320 × 568 | 0 % | 99 %, card top y = 256 / 273 |
| 1280 × 900 → 844 × 340 | 0 % | 99 %, card top y = 191 / 148 |

Each row was run for a conflict and for a write failure, with the same result for both.

**Decision**: `placeBar` remembers whether the bar rested before it decides. When the bar goes from held to
resting and the focused element is inside the bar, it calls `focused.scrollIntoView({ block: 'nearest' })`.

- **After an answer** that makes the bar rest (320 × 568, 844 × 340), this scroll runs in the layout effect.
  The `answers` effect then finds Save inside the window and does nothing more. When the answer moved focus
  out of the bar (to a field's message), this scroll does not run, and the `answers` effect handles that
  control as before.
- **A bar that rests from its first commit** (the plain bar at 320 × 256) has no "held before", so nothing
  scrolls. Focus is on the moved clip's control, and edit-mode-polish's scroll keeps it in view.
- **Focus outside the bar** is never scrolled by `placeBar`. A held bar that a zoom-out brings back can cover
  a focused row, as any resize can on main. This change does not alter that.

**Rationale**: It is the case the resting rule creates. Before the change, a held bar never moved its own
controls out of the window. The follow is the same scroll the `answers` effect already uses, in the one
function that knows the bar just changed state.

### The toast contract in both states

**Context**: The brief asks that `--toast-inset-bottom` stay correct in both states. Two contracts read the
bar:

- the scroll padding, which focus scrolls use
- the toasts' placement (`ui-a11y-polish`'s "Notifications never cover the save bar")

**Explored**: `fix.py toasts` holds one error toast from the row Render of `2024-07-14 - kalas` (the real
409), saves Sommarlov with a mocked conflict, then:

- scans every 16 px from the top of the page to its end for any overlap between `.toast` and `.save-bar-card`
- walks Shift+Tab from Save, recording focus stops that a toast covers in part (the visible share)

| Build, window | Overlap positions | Toast outside the window | Focus stops under the toast |
|---|---|---|---|
| main, 320 × 256 | 0 / 124 | 88 / 124 | 0 (but 15 stops hidden under the bar) |
| main, 320 × 568 | 0 / 124 | 1 / 124 | 15, `Remove borttagen.mp4` at 0 % |
| **A**, 320 × 256 | 0 / 124 | 21 / 124 | 5, `Remove borttagen.mp4` at 0 %, the others 43–50 % |
| **A**, 320 × 568 | 0 / 124 | 1 / 124 | 4, `Remove borttagen.mp4` at 0 %, the others 74 % |
| B, 320 × 256 | 27 / 124 | 0 / 124 | 15, at 73–84 % |
| B, 320 × 568 | 26 / 124 | 0 / 124 | 0 |
| A and B, 390 × 844 | 0 / 107 | 0 / 107 | 0 |

- **A** (the decision): a resting bar removes `--toast-inset-bottom` and stays registered with
  `keepToastsClearOf`.
- **B**: a resting bar also releases the registration, so toasts stay at the window's bottom.
- **Keeping the inset while resting** was ruled out by arithmetic. The bar's 322 px plus the toasts' region,
  their rise and the 16 px gap come to more than 400 px of `scroll-padding-bottom` in a 256 px window.

**Decision**: A. While held, the property is the bar's height, as today. While resting, the property is
absent. `keepToastsClearOf(bar)` stays registered in both states, and `ToastRegion` is unchanged.

**Rationale**:

- A keeps `ui-a11y-polish`'s requirement that no notification overlaps the bar, at every scroll position.
  B breaks it at about a fifth of the positions.
- A is better than main overall, though not in every cell. At 320 × 256, the stops hidden under the bar
  fall from 15 to 0, but 5 stops now sit partly under the toast, one of them fully. At 320 × 568, the stops
  under the toast fall from 15 to 4. A toast is outside the window at 21 positions rather than 88.
- The remaining case is the last clip row directly above a resting bar. It exists on main at 320 × 568, at
  the same 0 %. Its geometry (review): while the bar's top is in the window and the toast does not fit below
  the bar, `ToastRegion` places the toast just above the bar's top, which is where that row ends. A focus
  scroll reserves the toast's height at the window's bottom, so it lifts the row, and the bar's top comes
  into the window behind it. The toast follows the bar's top. No scroll position shows that row clear of
  both the toast and the bar, so nothing in `web/src/edit/` alone can fix it. A fix needs room kept between
  the last chapter and a resting bar (for example a margin of `--toast-rise-h`), and a `ToastRegion` that
  places itself again when the bar moves without a scroll. That is a `web/src/ui/` change and a follow-up.
- **This is not a recorded limit.** `ui-a11y-polish` scoped its focus sentence to what it measured clean
  ("one toast, or two in a window at least 844 px tall"). This case is one toast, so it is inside that
  sentence's scope, and the sentence is false here, on main (320 × 568) and with A (320 × 568 and
  320 × 256). The change does not edit that requirement. Whether to narrow it or to fix `ToastRegion` is the
  user's call (Open Questions). Until then, task 3.2 reports these stops as a known violation, never as a
  pass.
- **Superseded (Supervisor decisions, option (a)).** The change MODIFIES "Notifications never cover the save
  bar": the focus sentence holds for a bar that is not resting for its height, and with no bar. A resting bar
  may have a notification over the control just above it, never over the bar. Task 3.2 reports the stops as
  that case. Option (b) is the follow-up.

### Coordination with output-renamed-reason

**Context**: Z2 adds a member to `StalenessReason` and regenerates `schema.d.ts`. With only that change,
`tsc --noEmit` (and `npm run build`) fails. This was reproduced on the scratch copy, with the member then
named `renamed`: `src/events/labels.ts(11,14): error TS2741: Property 'renamed' is missing in type
'{ no_manifest: string; … }' but required in type 'Record<"no_manifest" | "output" | "renamed" | …, string>'`.
Z2 reproduced the same with its own name. Z2's proposal, written in parallel with this one, settles three
things:

- the member is `output_renamed`, declared right after `output`
- its task 4.1 adds `output_renamed: 'renamed — renders under the new name; the old movie stays'` to
  `REASON_LABEL`, to keep the build green
- it leaves the wording, and the web-app scenario "A stale event names every reason", to this change

Z2 makes no web-app spec change.

**Decision**: Task 1.1 re-checks the member's name and the words Z2 landed. Task 2.1 replaces those words
with `'movie name changed'` and adds `REASON_NOTE`. If Z2 lands another name after all, every
`output_renamed` in this change's code means that name. The spec's wording does not depend on the name.

The MODIFIED list requirement is re-based on the spec text current after Z2's archive, following the master
brief's rule for MODIFIED blocks. Z2 plans no edit there, so the re-base is expected to be a no-op.

### Files and parallel changes

| File | This change | Others |
|---|---|---|
| `web/src/events/labels.ts` | `REASON_LABEL`'s entry, `REASON_NOTE` | Z2: the provisional `output_renamed` entry (its task 4.1) |
| `web/src/events/common.tsx` | `StalenessCell`'s `explain` | — |
| `web/src/events/EventDetail.tsx` | one line in `RenderPanel` | — |
| `web/src/events/detail.css` | `.render-panel .reason-note` | — |
| `web/src/edit/EventEditor.tsx` | `HELD_BAR_MAX_SHARE`, `placeBar`, the bar effect and its comment, one layout effect | — |
| `web/src/edit/edit.css` | `.save-bar[data-rests]`, the bar's comment | — |
| `web/src/edit/SaveBar.tsx` | its header comment ("sticky at the bottom…") | — |
| `web/README.md` | Edit mode, Toasts, the dev library's stale kinds | none (Z2 edits the root `README.md` and `make_dev_library.py`'s comment) |
| `web/src/api/schema.d.ts`, `web/openapi.json` | untouched | Z2 regenerates |
| `web/src/ui/*` | untouched (`keepToastsClearOf`'s comment still holds for a bar at rest) | — |

Z1 (`adopt-into-folder-chapter`) is engine and CLI only, and shares no file.

### Verification fixtures

The runbook's scheme:

| Item | Value |
|---|---|
| `SLUG` | `renamed-label-and-zoom-bar` |
| Port | 8124 |
| Database | `arel_renamed_label_and_zoom_bar` |
| Library | `../dev-renamed-label-and-zoom-bar` |
| Worker | none |

The Playwright scripts live in `<scratchpad>/verify/renamed-label-and-zoom-bar/`, with the Noto
`fonts.conf`, and locators scoped to `main:not([hidden])`. Never use port 8080 or 5173, the default
database, `../auto-reel-dev` or `auto-reel-media/`.

- **Renamed**: `2024-06-27 - Grillning med grannar`, as `make_dev_library.py` leaves it. After the gate,
  its reasons are `["editorial", "output_renamed"]`.
- **Missing movie**: `2024-06-21 - Midsommar - Dalarna`, after deleting
  `library-output/2024/2024-06-21 - Midsommar - Dalarna.mp4` in the agent's own library. Its reasons are
  `["output"]`.
- **Bar**: `2024-09-01 - Sommarlov` (three rows, one of them the missing `borttagen.mp4`).
  - Conflicts: a `PUT …/reel` fulfilled with 412 in the browser, plus one real 412 made by a hand edit of its
    `reel.yaml` title after the page read.
  - Write failure: a real `chmod a-w` on the folder (restored afterwards), or a 502 fulfilled in the browser
    with the real detail's length.
- **Toast**: the row Render of `2024-07-14 - kalas` (real 409).

## Failure behavior & idempotency

- **No writes.** Neither part sends a request or touches disk. A save's failure handling is unchanged.
- **Fail loud, never fabricate**:
  - The note appears only for a reason the response cites. It names no file, and it never infers a rename
    from a title change.
  - A reason the client has no words for cannot pass `tsc`. A client built before the gate and served
    against a newer service is the existing build-skew case (`web/README.md`: rebuild `dist`), and is not
    new here.
- **Idempotent placement.** `placeBar` reads two heights and writes one attribute and one property. The same
  inputs give the same state. The bar's height does not depend on its state, so the rule cannot oscillate.
  It scrolls only on a change from held to resting with focus in the bar, so a repeated call with the same
  state never scrolls again.
  The cleanup removes the listener, the observer, the registration and the property, as today. The attribute
  goes away with the bar's node.
- **Re-run, `--force`, worker restart**: not applicable to a client-only change. Rendered output and the
  fingerprint are unchanged.

## Risks / Trade-offs

- **[At 400 % zoom the plain "Unsaved changes" bar rests, so it is out of view until the page's end]** →
  Held, it left the moved row 28 % visible at 320 × 256, and the focused control 0 % visible at 320 × 230.
  The chapter heading's "N clips moved", the unsaved-changes guard and Tab order (Save is last) still lead
  to it. The 117 px plain bar of a 320-wide window stays held in any window taller than about 292 px (117 / 0.4).
- **[A landscape phone (844 × 340) or a 200 % laptop (683 × 330) now rests a failed save's bar
  (48–62 %)]** → Measured: 47.9 % and 60.6 % at 844 × 340, and 49.4 % and 62.4 % at 683 × 330 (review,
  `extra.py`). The plain bar stays held in both (23 %). The verifier found the sticky bar acceptable there.
  Resting is also correct there: Save is focused and scrolled into view, the editor is uncovered, and the
  Shift+Tab walk hides no stop. It follows from the agreed threshold, and is
  listed for confirmation (Open Questions).
- **[A wrapped summary can tip the bar across the line while the operator types, for example at 320 × 300]**
  → The bar moves from the window's bottom to the page's end. Focus stays in the field. The bar's height
  does not depend on its state, so it cannot flicker.
- **[A toast and a resting bar in a short window can still cover the last clip row's controls]** → On main
  this happens at 320 × 568 (15 stops). The change cuts it to 4 there, but adds it at 320 × 256 (5 stops,
  `Remove borttagen.mp4` fully covered), where main hid 15 stops under the bar instead. Either way it breaks
  the focus sentence of `ui-a11y-polish`'s requirement "Notifications never cover the save bar", within its
  one-toast scope ("The toast contract in both states"). The operator can dismiss the toast. A fix needs
  `web/src/ui/` and is a follow-up. Narrowing the sentence instead is the user's call (Open Questions).
  *Resolved (Supervisor decisions):* the sentence is narrowed in this change, option (a); the fix, option (b),
  is the follow-up.
- **[A scroll the operator did not start]** → `placeBar` scrolls only when the bar's own focused control
  would otherwise leave the window with the bar. It never scrolls for focus outside the bar.
- **[Z2 lands other words, or another slug]** → Task 1.1 records both, and task 2.1 overwrites the words. The
  spec does not depend on the slug.
- **[`keepToastsClearOf`'s comment says "held at the viewport's bottom edge"]** → The region already handles
  a bar at rest (that is the sticky bar's resting case). The comment is left as it is, because `ui/` is not
  this change's.

## Migration Plan

The change is client-only. `npm run build` produces `web/dist`, and `serve` serves it. There is no data or
API migration. To roll back, revert the commits. The engine's reason keeps working with the gate's words.

## Open Questions

- **Should Z2 land `'movie name changed'` instead of its provisional words?** Z2's task 4.1 currently adds
  `'renamed — renders under the new name; the old movie stays'`. Using the short words would keep the list's
  rows at today's height between the two merges, and make task 2.1's `REASON_LABEL` edit a no-op. It is a
  supervisor call for Z2's tasks, and does not change this design. *Resolved:* Z2 landed `'movie name changed'`.
- **The landscape and 200 % laptop windows** now rest a failed save's bar. They are an accepted consequence
  of the agreed threshold, unless the supervisor wants the rule scoped to the narrowest windows. *Resolved:*
  accepted.
- **One toast and a resting bar break an existing focus rule. Narrow the rule, or fix the toasts?** With one
  error toast shown, the clip row just above a resting bar sits under the toast: 5 stops at 320 × 256
  (`Remove borttagen.mp4` at 0 %) and 4 at 320 × 568. Main has 15 at 320 × 568. web-app's "Notifications
  never cover the save bar" says a focused control is never under one toast, so the archived spec stays false
  in that corner. The options are:
  - (a) this change also MODIFIES that requirement, scoping its focus sentence to a held bar or no bar;
  - (b) a follow-up change in `web/src/ui/` keeps room between the last chapter and a resting bar, and has
    `ToastRegion` follow it ("The toast contract in both states");
  - (c) both.

  The design assumes (b) and leaves the spec sentence as it is.

  *Resolved (Supervisor decisions):* (a) in this change, (b) as a follow-up.
- **If Z2 publishes the previously recorded output's file name**, should the note name it? This design names
  no file, because the brief's Z2 scope is a reason only.
