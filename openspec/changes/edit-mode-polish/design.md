## Context

See proposal.md, "Why". This change works on main at bca64f2. Its own code is `web/src/edit/` and the
Edit / Stop editing toggle in `EventDetail.tsx`.

- **The save bar** (`SaveBar.tsx`, `edit.css` 441-513):
  - `.save-bar` is `position: sticky; inset-block-end: 0`, transparent, and lets clicks through. It holds
    `.save-bar-card`, a one-column grid.
  - Inside the card, the alert of a failed save sits above a flex row: the status text (`flex: 1 1 18rem`),
    then Reset and Save.
  - The alert is `ui/Alert`. Its buttons are `.btn`, which is `white-space: nowrap; flex: none`
    (`components.css`).
  - During a conflict the alert's "Reload latest (discard my changes)" is `btn-primary`. Save is also
    `btn-primary`, and it is `aria-disabled`.
- **Publishing the bar** (`EventEditor.tsx` 517-535): a layout effect writes `bar.offsetHeight` to
  `--toast-inset-bottom` on `<html>`. A `ResizeObserver` keeps it current.
  - `.toast-region` (`components.css`, the toast rules of `ui-a11y-polish`) and
    `html { scroll-padding-bottom }` (`shell.css`) both read it.
  - `.page`'s bottom padding is `--s-7 + --toast-region-h`.
- **The edit list** (`ClipOrderList.tsx`):
  - Every `li.clip-item` is its own grid, with tracks
    `2rem 2rem 5rem minmax(0,1fr) 12rem 5.5rem 10.5rem 4.25rem`.
  - Below a 58rem panel the grid switches to two lines. Below 30rem the file name takes the thumbnail's
    column on line 1.
  - `RowBody` puts a missing clip's Remove, or a removed clip's Undo, at the end of `.clip-file`.
  - Moves by button set `focusAfter`/`scrollAfter`. A layout effect refocuses the row, and a passive effect
    runs `scrollIntoView({ block: 'nearest' })`, after the editor has published the bar's height.
  - `onDragEnd` only calls `onMove`.
- **The read view's table** (`detail.css`, `event-page-polish`'s file) has these columns: `col-pos`
  3.5rem, `col-thumb` 5rem, file (the rest), `col-status` 12.5rem, `col-size` 6.5rem and `col-mtime`
  11.5rem. Cells have `--s-3` padding, and the first and last cells have `--s-4` on the outside. The table is
  laid out at panels of 50rem and wider.
- **The read failure** (`EventEditor.tsx` 444-448, 648-680): `readReel` dispatches `reading`, which
  replaces the failed Alert, and its Try again with it, by the loading placeholder.

## Supervisor decisions (2026-10-01)

Recorded before implementation. Where they differ from a section below, they win, and that section says
so.

- **Polish round.** The brief is `plan/brief-polish.md`, including its file ownership. Six sibling changes
  run in parallel: edit-mode-polish (P1, this one), jobs-live-polish (P2), event-list-polish (P3),
  event-page-polish (P4), ui-a11y-polish (P5) and serve-clean-exit (P6). This change stays in its own
  files. In `web/README.md`, whichever change lands second rebases and keeps every side.
- **Column properties are final:** `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`,
  `--clip-col-size` and `--clip-col-mtime`. event-page-polish defines them, and has landed.
- **The toast contract with ui-a11y-polish**, which landed first: keep publishing `--toast-inset-bottom` as
  the bar's height, and keep its two registration lines. The live `clientHeight − bar.top` band and the
  "before P5" fallback are dropped ("Toasts and the bar", Decisions 1 and 5, are withdrawn).
- **The save bar's bounds are accepted:** at most a third of a 390 × 844 window with a conflict, and at
  most two fifths with a failure's detail.
- **ALSO: the "Saved" toast names the event** by its title plus its date, as jobs-live-polish names its
  render toasts.
- **ALSO: Edit mode adopts `clipNames` / `ClipName`** from event-page-polish in `ClipOrderList.tsx`: the
  rows, the handle, Move, Remove and Undo labels, and the announcements. Edit mode then tells cross-folder
  look-alike clips apart, as the read view does.
- **ALSO: a save with no answer** shows the "not reachable" wording without the browser's raw text
  (`TypeError: Failed to fetch`). The `.catch` around `send()` in `EventEditor` no longer labels an
  exception in the page itself "not reachable".
- **Keep the hooks of the quiet "Included" rule.** event-page-polish styles Edit rows through
  `li.clip-item[data-status='active'] .pill`, so `clip-item`, `data-status` and the status `Pill` stay.
- **Follow-ups, not here:** Reset focusing an off-screen heading; Save sitting 56 Tab stops after Title;
  the verdict going stale in Edit mode after a live render.

### What landed on main (eb86e8b), re-checked

Both gates are archived (`2026-10-01-event-page-polish`, `2026-10-01-ui-a11y-polish`). Every name task 1.1
lists matched. What landed, and what it changes here:

- **The columns** (`detail.css` 10-27): the five properties exactly, with 5rem frames and 8rem from a 64rem
  panel. The 8rem is set on `.event-detail .panel > *`, so Edit mode's `.clip-order-head` and `.clip-order`,
  both children of the chapter panel, inherit it. The table's cell padding (`--s-3`, `--s-4` at the outer
  ends) and its 50rem card breakpoint are as "One grid with the table" assumes. The quiet rule is
  `:is(.clip-row, .clip-item)[data-status='active'] .pill` with `padding-inline: 0`, so the status words
  start at the cell's padding in both views.
- **Clip names** (`events/common.tsx`): `clipNames(chapter, identities)` returns the naming function for a
  chapter, and `ClipName({ name })` mutes the folder part (`.clip-dir`, `detail.css`). The table also passes
  the name to `ClipThumb` (`name`), for its "Frame from …" text.
- **Toasts** (`ui/toast.ts`, `ui/ToastRegion.tsx`): `keepToastsClearOf(bar)` and its `release()` already
  sit in this change's bar effect (`EventEditor.tsx` 529 and 534). While a bar is registered, the region
  places itself from the bar's rectangle on every scroll and resize (`--toast-offset`: above the held bar,
  below the resting one). It also publishes `--toast-rise-h`, which `shell.css` adds to
  `scroll-padding-bottom`. That closes the gap the live band was for. `--toast-inset-bottom` is now read only
  as the scroll padding's base and as the region's offset when no bar is registered.
- **Dialogs** (`ui/Dialog.tsx`): the description is automatic. Every child but the `.dialog-actions` row
  becomes `aria-describedby`, and there is no `description` prop. The editor's two dialogs need no change.
- **A coarse pointer** (`components.css` 829-878, the `pointer: coarse` block at 841): every `.btn` takes a 44 × 44 tap area through an
  invisible `::after`. Two adjacent `.btn-icon`s grow theirs away from each other, so Move up's grows 11 px
  toward its start. `.alert-action` and `.dialog-actions` keep `row-gap: var(--s-4)`, so stacked buttons'
  areas never meet. Two consequences here, in "The save bar" and "One grid with the table":
  - The compact alert sets only the column gap of `.alert-action`. A `gap` in the `screens` layer would undo
    the coarse row gap. Its buttons keep the 2rem height, so two stacked areas still leave 4 px between
    them.
  - In the one-line layout, a missing row's Remove ends 1rem before Move up, not 0.5rem. Move up's grown area
    then stays clear of it.

## Goals / Non-Goals

**Goals:**

- Fix each of the eight reproduced findings inside `web/src/edit/` plus one class on the toggle, with no
  new dependency, token or component. The toast finding is fixed by `ui-a11y-polish`, which landed first
  and places the toasts from the bar this change registers; this change keeps publishing the bar's height.
- Carry out the supervisor's three additions: the "Saved" toast's name, clip names in Edit mode, and a save
  with no answer worded without the browser's text.
- State every point where this change meets a parallel one as a named class, attribute or custom property,
  never as a shared line.

**Non-Goals:**

- Toast placement, toast focus and toast announcements, which are `ui-a11y-polish`'s.
- The read view's table and its widths, clip names, the status look and date formats, which are
  `event-page-polish`'s and `event-list-polish`'s.
- A roving tabindex, a Save shortcut, focus after Reset, and the "Saved" toast's wording (Open Questions).

## Research & Decisions

### Findings, reproduced

**Context**: The brief asks that every finding be reproduced before it is fixed. The critics' minor
findings were not adversarially verified.

**Explored**: The probes ran read-only against `http://127.0.0.1:8114/` (main bca64f2).

- **Browser**: Playwright 1.49 in `mcr.microsoft.com/playwright/python:v1.49.0-noble` with
  `--network host`, using the Noto `fonts.conf` of the final verification.
- **No writes reached the service**:
  - every `PUT …/reel` was fulfilled in the browser with a mocked 412 or 502
  - every `POST /jobs` got a mocked 409 `output_collision`
  - every other non-GET was aborted

  The log lists only the intercepted requests.
- **Patched reads**: the browser patched the GET detail and GET reel of `Två kapitel` and `Sommarlov` to
  add a missing clip, because the live library lost Sommarlov's `borttagen.mp4` during the e2e run.
- **Files**: scripts `repro.py` and `plib.py`, logs in `logs/` and shots in `shots/`, all under
  `/tmp/claude-1000/-var-home-emil-dev-larnet-auto-reel-project/72ded660-4d8e-435c-8a06-07bf9520945a/scratchpad/polish-spec/edit-mode-polish/`.
- **Prototypes**: the proposed CSS and markup were injected into the live page in the browser only.
  - `proto_bar.py`: the save bar
  - `proto_cols.py`: the columns
  - `proto_toast.py`: the toast inset

**Decision**: All eight findings reproduce. None is dropped.

| Finding | Measured |
|---|---|
| Save bar at phone width | Grillning, location edited, Save answered 412. At 390×844: card 467-828 (362 px, 43 %). Primaries: "Reload latest (discard my changes)" and Save (aria-disabled). A 502 with a short mocked path and a `failure` pill gives 325 px (38 %). The real answer (review, below) is longer and has no pill: 380 px of bar (45 %). At 320×700: conflict 362 px (52 %), write failure 415 px (59 %). |
| Conflict overflow at 320/340 | `scrollWidth` 357 at 320 and at 340, fine from 360. The overflowing chain is `div.save-bar-alert`, `div.alert`, `button.btn.btn-primary` and `div.save-bar-row`. The cause: a `nowrap`, `flex: none` button sets the min-content width of the card's one `auto` grid column. |
| Toast on the save bar | An error toast is held (row Render of `2024-07-14 - kalas`, mocked 409), then Edit on Grillning, a title change, and focus on Save, which scrolls to the end. At 1280, bar 671-739 and toast 702-799: 3 of Save's 5 sample points hit the toast. On the fix form (`Omöjligt datum`) at 1280, Save's centre hits the toast even at scroll 0, because the page is only 17 px taller than the window. With the bar stuck (scroll 0 on Grillning), nothing overlaps. |
| First keyboard drop | Grillning, Edit, Space / ArrowDown / Space on a handle. Covered sample points: `s1710004.mp4` at 1280, 5 of 5 (handle 837-869, bar 816-884); `s1710001.mp4` at 1280, 3 of 5; `s1710001.mp4` at 390, 3 of 5. Row 1 at 390 is not covered (0 of 5). |
| Chapter heading at 390 | Två kapitel, with a missing `gammal.mp4` patched into Main: Remove, then Move down. The heading reads "Main · 1 clip moved · 2 clips · 1 removed on save · 1 ignored". `span.panel-meta` spans x 167-399 and `scrollWidth` is 399, at 390, 360 and 320 alike. |
| Missing clip row at 390 | Sommarlov, `borttagen.mp4` patched back in. The name is on line 1 (1194-1215) and Remove on line 2 (1219-1245). The empty box and "Missing from disk —" are on line 3 (1248-1293), and the mtime "—" alone on line 4 (1273-1294). The row is 116 px against 98 px for the others. |
| Try again → `<body>` | GET /reel mocked 502 `unparseable_reel_yaml`, then Edit, focus on Try again, Enter. `activeElement` is BODY whether the second read fails or succeeds. |
| Columns shift, "Stop editing" | Grillning at 1280, read view → Edit mode: thumbnail x 121 → 161, file text 213 → 253, status 739 → 651, size 927 → 855, time 1031 → 955. The toggle goes from `btn btn-secondary` to `btn btn-ghost`, which at rest has a transparent border and `--fg-muted` text. |
| Field edges | `.field-input` border `--border-strong` on a `--surface` field in a `--surface` panel: 1.53:1 in light and 1.62:1 in dark. `--fg-subtle` measures 3.62:1 and 3.94:1. |

The e2e run reordered `:8114`'s Grillning to `s1710004, s1710002, s1710001, s1710003`. The fixture
(`scripts/make_dev_library.py`) lists `s1710001` to `s1710004`. The drop rows above are rows 1 and 3, so the
spec and task 3.1 name them by position: `s1710001.mp4` and `s1710003.mp4` on the implementer's library.

Parts of the critics' text that are not adopted:

- "The page title row also loses the date line, so the whole page jumps." The web-app spec has the fields
  take the place of the facts and the description, so this is specified, not a defect. Only the sideways
  shift is fixed.
- Three of the critics' suggested fixes are not used. "Hide Save during a conflict" breaks the focus rule.
  "Render the alert in flow" and "cap the card and scroll inside it" are covered under "The save bar"
  below.

**Rationale**: Each finding reproduced on current main by the critic's own mechanism.

### The save bar: compact in place, one primary action

**Context**: The failure must be seen where the operator pressed Save, and focus must stay on the pressed
control, which the alert describes (`aria-describedby`). The spec says the bar keeps visible what changed,
Reset and Save.

**Explored**:

- **The alert in flow above the bar's resting place.** This frees the bar, but the alert is off-screen
  whenever the page is not at its end. That is the usual case on a long event, so the failure would go
  unseen, or the page would have to jump.
- **Cap the card (`max-block-size: 40dvh`) and scroll inside it.** Save, at the card's end, would sit
  scrolled out of sight while it holds focus, inside a scroll container on a sticky element.
- **Hide Save during a conflict.** Focus would drop to `<body>`.
- **Compact in place, prototyped by injection (`proto_bar.py`).** The changes:
  - a `minmax(0, 1fr)` column, so the card cannot widen the page
  - bar buttons that may wrap their words
  - a compact Alert
  - a 9rem basis for the status text
  - the conflict's paragraph replaced by a note

  The card's height, before → after. The write failure here is the short mocked detail. The review's
  measurement with the real one follows the decision.

  | Window | No failure | Conflict | Write failure (mocked) |
  |---|---|---|---|
  | 390×844 | 113 → 61 px | 362 → 199 px (24 %) | 325 → 230 px (27 %) |
  | 320×700 | 113 → 101 px | 362 → 302 px | 415 → 289 px |
  | 1280×900 | 69 → 61 px | 194 → 143 px | 194 → 167 px |

  At 320, 340, 360, 390, 768 and 1280 there was no horizontal scroll. Screenshots:
  `shots/proto-conflict-390-9rem.png`, `-320-9rem` and `-1280-9rem`, and `proto-disk-390-9rem.png`.

**Decision**: Keep the alert in the card and make it compact.

`edit.css`, `@layer screens`, replacing and extending the save-bar rules:

```css
.save-bar-card {
  grid-template-columns: minmax(0, 1fr); /* nothing the card holds widens the page */
  gap: var(--s-2);
  padding: var(--s-2) var(--s-2) var(--s-2) var(--s-3);
}
.save-bar-row { gap: var(--s-2) var(--s-3); }
.save-bar-text { flex: 1 1 9rem; } /* one row with Reset and Save from about 360 px */

/* The bar's buttons wrap their words rather than widen the bar (a 320 px conflict). */
.save-bar .btn {
  flex: 0 1 auto;
  min-inline-size: 0;
  padding-block: 0.3125rem;
  line-height: var(--lh-tight);
  white-space: normal;
  text-align: center;
}

/* A failed save's alert, compact: a 16 px icon, small type, tighter padding. */
.save-bar-alert > .alert {
  gap: var(--s-2);
  padding: var(--s-2) var(--s-3);
  font-size: var(--text-sm);

  & > svg { inline-size: 1rem; block-size: 1rem; margin-block-start: 0.125rem; }
}
.save-bar-alert .alert-action { column-gap: var(--s-2); }
.save-bar-alert .alert-action .btn { font-size: var(--text-sm); }
```

Changed at implementation, against the coarse-pointer rule that landed with ui-a11y-polish ("What landed
on main"). The review's CSS set `gap` and `min-block-size: 1.75rem` here. Only the column gap is set now, so
`.alert-action`'s own row gap, which is 1rem under a coarse pointer, stays. The alert's buttons keep `.btn`'s
2rem height, so two stacked buttons' 44 px areas still leave 4 px between them. A stacked conflict at 390
gets 4 to 8 px taller from this. The bounds below leave room for that.

`SaveBar.tsx`:

- **One primary.** `const savePrimary = problem?.kind !== 'conflict' && problem?.kind !== 'gone'`, and
  Save's class is `savePrimary ? 'btn btn-primary' : 'btn btn-secondary'`. Its `controlState`,
  `aria-describedby` and click guard are unchanged.
  - The `gone` alert's "Back to the event list" becomes `btn btn-primary`.
  - The conflict's "Reload latest (discard my changes)" stays `btn-primary`, and "Overwrite with mine" stays
    `btn-danger`.
- **Conflict copy.** The title stays "This event was changed elsewhere since you started editing.".
  `CONFLICT_DETAIL` is deleted. After "Overwrite with mine" the action slot gets
  `<span className="alert-note">Your edits are kept.</span>`, as the write-failure alert already has. The
  button labels already say what each choice does, and the bar's own row still says "Unsaved changes" and
  what changed.

**The spec's bounds, re-measured by review.** The review used the CSS above exactly, without the
prototype's extra `container-type` on the card, which no width needed. It measured `.save-bar`'s
`offsetHeight` (card plus its `--s-4` foot, the band the page loses while the bar is stuck) at 390×844
(`review/rv_bar.py`, `review/logs/rv_bar.log`).

- **Conflict:** 378 → 215 px (25 %).
- **Write failure:** 380 → 300 px (36 %). This is the real answer: a 502 with no `failure` (`routes/events.py:480`) and the detail "reel.yaml could not be saved: [Errno 13] Permission denied: '/var/home/…/dev-edit-mode-polish/2024/2024-09-01 - Sommarlov/.reel.yaml.<32 hex>.tmp'". The writer's temporary name (`reel/writer.py`) and the dev library's path wrap to six lines of detail.
- **No horizontal scroll** at 320, 340, 360, 768 and 1280, with every element of the card inside the window.

So the spec bounds the bar at a third with a conflict, whose copy is the client's. With a failure, it is
bounded at two fifths, because the service's detail is free text the client must show in full: the
phone-width requirement drops no fact. Clamping the detail to a few lines would need a disclosure. Scrolling
it inside the bar would need a keyboard-focusable scroller in a sticky element. Either is more machinery
than this polish round warrants. The detail's title repeating its first words ("reel.yaml could not be
saved") is the service's prose, and is left alone here.

**Rationale**: The failure stays where the operator's focus is, and the bar stays the one place that says
what to do next. The fix is CSS plus two class expressions and one copy change, and needs no new
component.

### Toasts and the bar: the contract with `ui-a11y-polish`

**Context**: The brief gives toast placement to the region (P5) and "what EventEditor publishes" to this
change. P5's design ("Where toasts sit relative to the save bar") was read while this one was written:

- `ui/toast.ts` gains `keepToastsClearOf(bar)`.
- `ToastRegion` places itself live:
  - **above** the bar while it is stuck
  - **below** it when it rests in flow with room under it, in `.page`'s bottom padding
- P5 adds two lines to this change's bar effect (`const release = keepToastsClearOf(bar)`, and `release()`
  in its cleanup).
- `--toast-inset-bottom` stays this change's, and still feeds `scroll-padding-bottom`.

**Explored**:

- **Follow the bar's top** (`proto_toast.py`): `--toast-inset-bottom = clientHeight - bar.top`, plus room
  above the resting bar (`margin-block-start: var(--toast-region-h)`). It measured 0 overlaps of the card
  and 0 rows under a toast at the end. It cases Grillning, the fix form and Lång kväll at 1280, 390 and
  320, at 5 scroll positions each. It is a second mechanism next to P5's, though, and it moves the bar when
  a toast comes or goes, so it is not adopted.
- **P5's rule with today's `offsetHeight` publish.** There is a gap. On its way to rest, the bar rises by
  `L` (up to the region's height plus a gap) before the toasts switch below it. Meanwhile the toasts ride
  `L` px higher than `scroll-padding-bottom` (`offsetHeight + region + gap`) accounts for. A control that
  Tab scrolls into that band can sit under a toast.

**Decision (supervisor, 2026-10-01, which supersedes the review's decision below)**: P5 landed first, and
its region closes the gap itself: it places itself from the registered bar's rectangle on every scroll, and
publishes `--toast-rise-h`, which `scroll-padding-bottom` adds ("What landed on main"). So this change keeps
today's publish unchanged: `--toast-inset-bottom` is the bar's `offsetHeight`, written synchronously when
the bar shows and kept current by a `ResizeObserver` on the bar, and removed when the bar leaves. P5's two
lines, `const release = keepToastsClearOf(bar)` and `release()` in the cleanup, stay in that effect. Only
the effect's comment changes, to say who reads the property now. Points 2 to 4 below still hold. Point 1, the
live band, and point 5, the interim before P5, are withdrawn.

**The review's decision, withdrawn in part**: Toast placement is P5's alone. This change's side:

1. **A live band (withdrawn).** `--toast-inset-bottom` = `max(0, ceil(documentElement.clientHeight − bar.top))`,
   written only when the value changes.
   - It is published synchronously in the commit that shows the bar. The passive scroll after a move or a
     drop depends on that.
   - After that, a `ResizeObserver` on the bar and on `<html>` re-measures directly in its callback. This is
     after layout and before paint, as today's observer does, so a bar that grows (its summary wraps)
     is re-published in the same frame. The `<html>` observation catches content above the bar that moves
     it without resizing it. Window `scroll` (passive) and `resize` re-measure at most once per animation
     frame.
   - While stuck, the value equals `offsetHeight`, which is today's value. On the way to rest it grows with
     the bar's rise, so `scroll-padding-bottom` covers the toasts riding above it. At rest it over-reserves,
     which is harmless: the content is all above the bar, and the page cannot scroll further.

   ```ts
   useLayoutEffect(() => {
     const bar = barRef.current
     if (!showBar || bar === null) return
     const root = document.documentElement
     let frame = 0
     let last = -1
     const publish = () => {
       const band = Math.max(0, Math.ceil(root.clientHeight - bar.getBoundingClientRect().top))
       if (band !== last) {
         last = band
         root.style.setProperty('--toast-inset-bottom', `${band}px`)
       }
     }
     const onFrame = () => {
       frame = 0
       publish()
     }
     const schedule = () => { if (frame === 0) frame = window.requestAnimationFrame(onFrame) }
     publish()
     // P5's two lines go here: const release = keepToastsClearOf(bar)
     const observer = new ResizeObserver(publish)
     observer.observe(bar)
     observer.observe(root)
     window.addEventListener('scroll', schedule, { passive: true })
     window.addEventListener('resize', schedule)
     return () => {
       window.cancelAnimationFrame(frame)
       observer.disconnect()
       window.removeEventListener('scroll', schedule)
       window.removeEventListener('resize', schedule)
       root.style.removeProperty('--toast-inset-bottom') // and P5's release()
     }
   }, [showBar])
   ```

   The write happens only on a change, because an inherited custom property on `<html>` invalidates the
   whole tree's style. While the bar is stuck, which is most of a scroll, nothing is written.
2. **The registration.** If `ui-a11y-polish` is on main when this is implemented, its two lines stay in
   this effect. Task 2.2 checks for them. If it is not, P5's rebase re-applies them, as its design says.
3. **No placement of toasts here**: no margin above the bar, and no region rule.
4. **No spec sentence on toasts here.** P5's ADDED requirement ("Notifications never cover the save bar")
   is the contract. Restating it would be a second source.
5. **If this change lands before P5 (moot: P5 landed first)**, the region still reads `--toast-inset-bottom` as its offset, so the
   live band places toasts at the bar's top edge. That is P5's "follow" rule (its design, "F"). Toasts then
   never cover the bar, which fixes the brief's finding. At the page end, though, they can sit on the
   last rows' controls until P5's switch lands: P5 measured 4 Move buttons covered at 1280. Today they
   cover Save instead. Task 6.1 records which state it verified.

| | `ui-a11y-polish` (P5) | `edit-mode-polish` (P1) |
|---|---|---|
| Where toasts sit | the region's live offset (`--toast-offset`) while a bar is registered, and `--toast-inset-bottom` otherwise | nothing |
| `--toast-inset-bottom` | read as the fallback only | published as the bar's height, as before |
| `scroll-padding-bottom` (`shell.css`) | adds `--toast-region-h` and `--toast-rise-h` | its base, the bar's height |
| Registration | its two lines in P1's effect | keeps them |
| Spec | "Notifications never cover the save bar" | not restated |

**Rationale**: One owner for where toasts sit, and one for what the bar says about itself. P5's
`--toast-rise-h` covers the toasts that rise with the bar, which the live band was for, so a second
mechanism would only add a scroll listener.

### The first drop keeps its row in view

**Context**: dnd-kit's `RestoreFocus` calls `.focus()` on the handle in a `requestAnimationFrame` after a
drop. That is before the save bar is measured, and `.focus()` does not scroll an element that is already in
the viewport.

**Decision**: In `ClipOrderList.tsx`:

- `onDragEnd` records `dropped.current = String(active.id)` before calling `onMove`, only for a drop that
  changes the order. It records it for keyboard and pointer drops alike.
- The existing layout effect turns it into `scrollAfter.current = <that row>`, looked up in `sectionRef` by
  `data-identity`, as for a button move. It does this before its own `focusAfter` early return, which the
  restructure moves.
- The existing passive effect then runs `scrollIntoView({ block: 'nearest' })`. Because it is passive, it
  runs after the editor published the bar's height in its layout effect, and `html`'s scroll padding already
  holds the new bar.

**Rationale**: This is the same path the Move, Remove and Undo buttons already take (commit 4b7b701). A
pointer drop gets the same "nearest" nudge, the least scroll that clears the bar.

### Try again keeps focus

**Context**: The busy-control rule says a control that waits keeps focus and is never removed. The spec
says a busy control "SHALL keep keyboard focus, and SHALL NOT be removed from the tab order".

**Explored**:

- Focus the page `h1` after the read. The operator would lose their place, and a failed retry would land
  far from the failure.
- Keep the Alert mounted with Try again busy, the pattern every other retry in the app uses.

**Decision**: In `EventEditor.tsx`:

- **State.** `State`'s `failed` gains `retrying?: true`, and a `retrying` action sets it on a failed state.
  `readReel(retry)` dispatches `retrying` instead of `reading` when retrying. The first read and Reload
  still dispatch `reading`.
- **The button.** Try again gets `aria-disabled` and `aria-busy` while `retrying`. Its click is ignored
  then, and it sets `retried.current = true`. The Alert is not keyed, so the same button element stays
  mounted.
- **The status region.** It reads "Reading reel.yaml…" while `loading` or `retrying`.
- **When the answer arrives**, a `useLayoutEffect` on `state` acts if `retried.current` is set. It is a
  layout effect, not a passive one: a read that succeeds unmounts the Alert, and with it the focused Try
  again. A passive effect would run only after a paint with focus on `<body>`, and assistive technology
  could announce the document in between. Then:
  - `failed`: focus is still on Try again. Call `announce(state.cause)`, because `role="alert"` does not
    re-announce unchanged text.
  - `ready`: focus the details `<h2>`, which gets a ref and `tabIndex={-1}`. Its default `:focus-visible`
    ring stays, so a sighted keyboard user sees where focus went.
  - `changed`: focus the "Read again" button, which gets a ref.

Two details were added at implementation:

- The re-announcement says the failure's kind as well, as the alert's title does: "This event could not be
  read. reel.yaml can't be read".
- After a read, the live region is cleared, so it no longer holds the failure that has gone.

**Rationale**: This is the app's own busy pattern. Focus lands on the first heading of what replaced the
failure, and never on `<body>`.

### One grid with the table

**Context**: `event-page-polish` publishes these custom properties on `.event-detail` from `detail.css`
(its design, "Thumbnails"):

- `--clip-col-pos` 3.5rem
- `--clip-thumb-w`: 5rem, and 8rem where `.event-detail .panel > *` sits in a panel of 64rem or more
- `--clip-col-status` 12.5rem
- `--clip-col-size` 6.5rem
- `--clip-col-mtime` 11.5rem

Its `.clip-table` columns read them, and its open question asks whether Edit mode's grid will too.

**Explored**:

- **Reserve empty handle and moves gutters in the read table.** That would be `event-page-polish`'s table,
  and it wastes about 100 px of the read view. Not adopted.
- **Literal widths in `edit.css`.** They drift the moment the table changes, which it does in this round:
  8rem thumbnails at 1280. Not adopted.
- **The table's tracks with zero column gap and cell-like padding** (`proto_cols.py`):
  - the handle (1.5rem) and the position number share the table's position column
  - the move buttons, and a missing clip's Remove, take an `auto` track at the end of the file column
  - status, size and time keep the table's widths, measured from the right

  Measured at 1280 and 1024 on Grillning and on Sommarlov with its missing row: the thumbnail, file text,
  status pill, size and time start exactly where the read view puts them, and nothing overflows. At 960 the
  read panel is 55rem, so the read view is a table while Edit mode is already two-line. The layouts differ
  there by design.

  The review re-ran it as specified below (`review/rv_cols.py`, `review/logs/rv_cols*.log`): the 9-track
  grid with the `action` area, the Remove moved after the facts, and P4's own rules injected (its
  properties, its 8rem frames at 64rem, its `.clip-table` columns, its quiet status).
  - **Alignment:** 0 mismatches over 1 px on every row of Grillning, Sommarlov (with its missing row and its
    Remove in the `action` track) and Två kapitel, at 1280 (128 px frames) and 1024. The header strip's
    Status, Size and Modified start exactly at the table's.
  - **With mismatched names** (P1 reading `--clip-thumb-w` while P4's first draft published
    `--clip-col-thumb`), the fallback hid the mismatch. Edit mode kept 80 px frames against the table's
    128 px, and every file name sat 48 px off at 1280. The spike was run both ways and only matching names
    align. P4's design now publishes `--clip-thumb-w`, so the names agree (Review fixes).

**Decision**: `edit.css`. The base rules are the one-line grid, as today, and are overridden below 58rem:

```css
.clip-order-head,
.clip-item {
  grid-template-columns:
    1.5rem calc(var(--clip-col-pos, 3.5rem) - 1.5rem) var(--clip-thumb-w, 5rem)
    minmax(0, 1fr) auto auto
    var(--clip-col-status, 12.5rem) var(--clip-col-size, 6.5rem) var(--clip-col-mtime, 11.5rem);
  grid-template-areas: 'handle pos thumb file action moves status size mtime';
  column-gap: 0;
  padding-inline: 0;
}
```

The items are placed by area, with the table's cell padding (`--s-3`, and `--s-4` at the outer end):

| Item | Area | Inline spacing |
|---|---|---|
| handle (`inline-size: 1.5rem` in this layout, 24 × 32 px, at least WCAG 2.5.8's 24) and `.drag-slot` | `handle` | — |
| `.clip-pos` (text-align end) | `pos` | end `--s-2` |
| `> .clip-thumb` | `thumb` | — |
| `.clip-file` | `file` | `--s-3` |
| the row action (below) | `action` | margin end `--s-4` (a margin: padding would widen the button). The review had `--s-2`. Under a coarse pointer Move up's tap area grows 11 px toward its start, and with `--s-2` it would reach 3 px into Remove ("What landed on main"). |
| `.clip-moves` | `moves` | end `--s-3` |
| `.clip-status`, `.clip-size` | `status`, `size` | `--s-3` |
| `.clip-mtime` | `mtime` | `--s-3` start, `--s-4` end |

- `.clip-facts` stays `display: contents` here, so its children take their own areas.
- The header strip's eight spans map to `handle pos thumb file status size mtime moves`, by `nth-child` or a
  class per span.
- The `< 58rem` block restores the two-line layout's own `column-gap: var(--s-2)`, its
  `padding-inline: var(--s-2) var(--s-3)`, the 2rem handle, a literal `5rem` thumbnail (a narrow panel is
  under 64rem), zero item padding and a zero action margin. Its grid areas are unchanged.
- **Cascade order matters.** The new base rules go before the `@container (width < 58rem)` and
  `(width < 30rem)` blocks, where today's base rules are. Those blocks override them by source order
  (same layer, same specificity). Each override uses the same selector as the base rule it undoes, for
  example `.clip-item > .drag-handle` and `.clip-item .clip-status`. The review's first spike put the
  base rules after the blocks: the base areas then won at 390, the missing row's file column collapsed,
  and the page scrolled sideways at 320.
- The 58rem breakpoint stays. With the moves track (about 80 px) taken from the file column, 58rem still
  leaves an 18-character camera name its line in an ordinary row. A missing or removed row also gives its
  action about 102 px with the `--s-4` margin (94 px in the review's measurement with `--s-2`). There
  `borttagen.mp4` keeps its line from a 58.5rem panel (`review/logs/rv_wide.log`), but an 18-character
  missing name breaks inside the word between 58 and about 61rem (Risks).

If `event-page-polish` has not landed, the fallbacks equal today's table, so the alignment already holds.
If it has, the grid follows its widths, including the 8rem frames at 1280. Task 4.1 checks the alignment
against whatever the table shows when the task runs.

**Rationale**: One set of properties, declared by the table's owner, is the whole contract. Only the
position number moves (24 px right) to make room for the grip. That is the one shift a handle must cause.

### A missing clip's row: its action after its facts

**Context**: At 390 the file area is 188 px. "borttagen.mp4" (101 px) plus the 86 px Remove does not fit, so
Remove wraps under the name and pushes the box down. The facts area is 176 px.

**Explored**:

- **Remove in the moves area on line 1.** This squeezes the name to 98 px at 390, which breaks it in the
  middle, and overflows at 320.
- **Icon-only Remove.** The missing-clips requirement says the control "SHALL say that it removes the
  clip".
- **A third grid line for the action.** That makes 123 px, no better than today.
- **The action as the last item of the facts**, which wrap beside the box: "Missing from disk —" on one
  line, then "— Remove". That is 51 px beside a 45 px box, and the row is about 101 px against 98 px.

**Decision**: `RowBody` passes `action` to `ClipFacts`, which renders it after `.clip-mtime`. `.clip-file`
then holds only the name and the moved badge. The same applies to `RemovedRow`'s Undo.

- **Wide layout**: the button takes the `action` area, a direct grid item through `display: contents`.
- **Narrow layout**: it is the facts flex line's last item.
- **Tab order** in a row stays handle → Remove → Move up → Move down, since `.clip-facts` precedes
  `.clip-moves`.
- **Focus targets** (`.clip-remove`, `.clip-undo`) are found by class inside the row, so the
  `focusAfter` effect is unchanged.

**Changed at implementation, for a coarse pointer.** ui-a11y-polish's touch probe (task 6.1) found Remove's
44 px area meeting Move up's and Move down's in windows 510 to 590 px wide, panels of about 29.3 to 33.9rem.
There the facts' first line also holds Remove, right under the move buttons' line: 2 px apart, against the
15 px their two areas need. In narrower panels Remove already wraps to the facts' second line, 28 px down.
In wider ones it ends clear of Move up's area. So:

- `ClipFacts` wraps the action in `<span className="clip-action">`. The wrapper takes the `action` area and
  its margin in the one-line layout.
- Under `(pointer: coarse)`, from a 28rem panel to the 58rem one-line layout, a wrapper that holds a
  Remove takes `flex-basis: 100%`, so Remove starts a line of its own at the facts' start. Undo has no move
  buttons above it and keeps its place.
- The cost: on a touch screen, a missing row in those panels is 103 px tall against 76 px for the others.
  A fine pointer, and every phone width up to 28rem, keep the layout above, so the 390 px bound is
  unchanged. After the change the probe passes over Sommarlov at 430 to 640 px, every 10 px, and at 1280,
  768, 390 and 320.

**Rationale**: The remedy sits beside the status that explains it. The row keeps the two-line rhythm of
the others, and the change is one prop moved.

### Chapter headings stay one line

**Context**: The heading is sticky (`top: var(--header-h)`), and `html`'s `scroll-padding-top` assumes it is
`--panel-head-h` (2.75rem) tall. A heading that wraps to two lines (about 58 px) would let a row scrolled
"nearest" sit up to 14 px under it. `.panel-meta` is `nowrap`.

**Explored**:

- **Let the heading wrap.** This breaks the scroll-padding assumption above.
- **Shorter words.** "2 clips · 1 removed · 1 ignored" is still 220 px against 183 px free at 390, and fails
  outright for long chapter names.
- **Counts into the lists they count.** The removed and ignored lists already have captions right above
  their rows.

**Decision**: In `ClipOrderList.tsx`:

- **The heading.** `panel-meta` says `plural(order.length, 'clip', 'clips')` only, the clips it plays.
- **The captions** gain their counts:
  - "`{plural(removed.length, 'clip', 'clips')}` removed from reel.yaml when you save"
  - "`{plural(ignored.length, 'ignored clip', 'ignored clips')}`, not played"
- **Long names.** `.edit-chapter > .panel-header > h2` gets `min-inline-size: 0; overflow-wrap: anywhere`,
  so a long chapter name wraps inside the heading instead of pushing the count out. The badge and the count
  stay `nowrap`.

The save bar still counts the removals. The heading of h2, the moved badge and "N clips" is about 200 px at
320. The review swept 320 to 1440 px in steps of 40, with the new texts injected, over Sommarlov after its
removal and a move, and over Två kapitel with `gammal.mp4` patched into `Main`, removed, and a move. No
width scrolled sideways, and every chapter heading was 44 px tall (`review/logs/rv_cols_narrow.log`).

The read view's heading, as `event-page-polish` MODIFIES its requirement, counts "N clips · N ignored".
Edit mode's heading keeps only "N clips", next to its moved badge, and its ignored list's caption carries
the ignored count. The two headings differ by that count on purpose. With the badge, "· 1 ignored" would not
fit at 320.

**Rationale**: A sticky heading has to keep one line. The counts stay on screen, next to the rows they count.

### Stop editing, and field edges

**Decision**:

- **The toggle.** In `EventDetail.tsx` its class becomes `"btn btn-secondary"` in both states (the one line
  the brief gives this change). The label and the `x` / `pencil` icon still change. There is no
  `aria-pressed`, because a toggle whose label changes must not also be pressed (ARIA APG).
- **The field edges.** In `edit.css`, `.field-input`'s border becomes `1px solid var(--fg-subtle)` (3.62:1
  and 3.94:1, against the 3:1 that WCAG 1.4.11 asks). Its hover becomes `--fg-muted`, and focus, invalid and
  locked are unchanged.
  - D-10's token note allows `--fg-subtle` "for icons, borders and placeholders". No token is added.

### Clip names, as the table names them (supervisor, ALSO)

**Context**: event-page-polish names a chapter's clips with `clipNames(chapter.name, identities)`. A chapter
whose clips all lie in its own folder names them by file name. A chapter that lists a clip from another
folder names each clip by its path in the event folder. `ClipName` mutes the folder part. Edit mode still
uses `fileName` everywhere: the row, the frame's text, the labels of the handle, Move, Remove and Undo, and
the announcements of drags and buttons. A chapter that lists `s1710004.mp4` and `Kvällen/s1710004.mp4`
therefore shows two rows that read alike, and two handles both named "Reorder s1710004.mp4".

**Decision**: In `ClipOrderList.tsx`:

- **One naming function per chapter.** `nameOf = clipNames(chapter, [...original, ...ignored])`, memoised on
  those two lists. `original` holds every clip the chapter played when Edit mode opened, removed ones
  included, so neither a removal nor a move renames a row. The read view passes the same identities: the
  clips it plays and the clips it ignores.
- **Every place that names a clip uses it.** `RowBody` takes the name as a prop. `.clip-name` renders
  `<ClipName name={name} />`, and `ClipThumb` gets `name`. The same name goes into "Reorder …",
  "Move … up", "Move … down", "Remove … from reel.yaml", "Undo removing …", dnd-kit's announcements and the
  button announcements.
- **The rows keep their hooks:** `li.clip-item`, `data-status` and the status `Pill`, which event-page-polish's
  quiet "Included" rule reaches.

**Rationale**: One function decides how both views name a clip, so Edit mode cannot drift from the table.

### The "Saved" toast names the event (supervisor, ALSO)

**Context**: jobs-live-polish names render toasts by the event's title followed by its date, or by the
folder name when the event has no title: `“Grillkväll med grannarna” · 2024-06-27`. A no-break space sits on
each side of the "·", and word joiners follow the date's hyphens. That helper, `eventName` in its
`jobs/labels.ts`, is not on main, and neither change edits the other's files. Edit mode's success toast says
only "Saved".

**Decision**: In `EventEditor.tsx`, the toast says `Saved <name>`.

- **The format.** A local `eventName(eventId, title, date)` with P2's signature and output. Whichever of the
  two changes lands second can reduce it to one import (Open Questions).
- **The title and date** are the ones the save leaves the event with, never a guess:
  - a field the save writes with a value: that value
  - a field the document left unset and still leaves unset: the value the page resolved from the folder
    name, which is the detail's
  - a field the operator emptied: left out. The service resolves it from the folder name, and the client
    does not know that value. With no title, the name is the folder name, which starts with the date.
- The needs-attention form has no detail, so an unset field there is left out too.

**Rationale**: The same event reads the same in every toast, and nothing is invented.

### A save with no answer, and an error in the page (supervisor, ALSO)

**Context**: When `fetch` rejects, `saveReel` and the overwrite's `fetchReel` return `unreachable` with
`String(error)`, and the bar shows that text as the detail: "TypeError: Failed to fetch". The browser wrote
it, it says nothing the title does not, and it takes a line of a phone's bar. The `.catch` after `send()` also
turns any exception into the same `unreachable` problem, so an error in the page itself, a bug, reads "The
service is not reachable."

**Decision**:

- **`SaveBar.tsx`:** the `unreachable` alert shows no detail. Its title, Retry and "Your edits are kept."
  stay. The `unpublished` kind that event-list-polish adds keeps its detail, which names the request and
  the status it got.
- **`EventEditor.tsx`:** the `.catch` after `send()` makes a `disk`-kind problem titled "The save stopped on
  an error in this page.", with the error's text as its detail and Retry. It also logs the error with
  `console.error`, for its stack, as `jobs/store.ts` does. The `disk` kind already has this shape (its own
  title, a detail, Retry), so the `SaveProblem` union is not widened. event-list-polish edits the union's
  `unreachable` line, and a new member next to it would be a shared line. A comment above `disk` says what
  it covers. Whether the PUT was sent is unknown at that point, so the title does not claim that nothing was
  saved. A Retry after a write that did land is answered 412, which the conflict path handles.

**Rationale**: "Not reachable" is said only when no answer came, and the bar shows only the service's words
and the client's.

### Files and parallel changes

**Context**: Six polish changes are written in parallel. The brief assigns `web/src/edit/*` and the toggle
to this change.

**Decision**:

| File | This change | Other changes' lines in it |
|---|---|---|
| `edit/SaveBar.tsx` | Save's class, the gone link's class, conflict copy, the `unreachable` alert's detail, a comment above the `disk` kind | `event-list-polish` (not on main yet): the `SaveProblem` kind `unreachable \| unpublished`, `case 'unpublished'`, the title expression and its import. These sit in the failure `switch`, not in the lines this change edits. |
| `edit/EventEditor.tsx` | the bar effect's comment, Try again, the heading and Read again refs, the `.catch` after `send()`, the "Saved" toast's name | `ui-a11y-polish` (landed): two registration lines in the bar effect, kept. `event-list-polish`: `readFailure`, `send()`, the import. |
| `edit/ClipOrderList.tsx` | the drop scroll, `ClipFacts`' action and its `.clip-action` wrapper, the heading count and captions, clip names | `event-list-polish`: `formatInstant(clip.mtime)` (one line, plus the import) |
| `edit/edit.css` | the save bar, the grid, the field edges | none |
| `events/EventDetail.tsx` | the toggle's `className` (one line) | `event-page-polish` (landed) owns the rest, and left that button as it was. |
| `web/README.md` | the Edit-mode paragraph | `ui-a11y-polish` (landed) rewrote the Toasts bullet, whose `--toast-inset-bottom` sentence is still true, so this change leaves it. |

Contracts this change honours:

- **`event-page-polish`**: it reads `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`,
  `--clip-col-size` and `--clip-col-mtime` with today's values as fallbacks. These are the exact names
  that change's design now defines ("Thumbnail size, and the column contract"), and both changes' gate
  tasks stop on any difference. Neither side renames alone: a fallback hides a mismatch. It keeps `li.clip-item`,
  `data-status` and the status `Pill`, which that change's quiet-status rule
  `li.clip-item[data-status='active'] .pill` reaches. It adopts `clipNames` / `ClipName` (supervisor
  decision; "Clip names, as the table names them").
- **`ui-a11y-polish`**: the toast table above.
- **`jobs-live-polish`**: the "Saved" toast follows its `eventName` format through a local copy ("The
  "Saved" toast names the event"). `RenderControl`'s `blockedReason` for Edit mode is `EventDetail.tsx`'s,
  and is unchanged.

**Rationale**: Every dependency is a name, never a line both sides edit for different reasons. The two
shared sentences or lines are listed.

### Verification fixtures

**Decision**: The implementing agent's own environment (dev-env runbook §9, `SLUG=edit-mode-polish`,
`N=15`):

- database `arel_edit_mode_polish`
- library `../dev-edit-mode-polish`
- `auto-reel serve` on port 8115, and no worker. Nothing here renders, and the `kalas` collision answers
  409 without one.

The states are made in that library copy only, and each is restored afterwards:

- **Conflict**: hand-edit Grillning's `reel.yaml` title after Edit mode opens.
- **Write failure**: `chmod a-w` on Sommarlov's folder.
- **Unparseable document**: write `title: [` into Grillning's `reel.yaml` after the page read, and restore
  the saved copy to repair it.
- **A chapter with missing and ignored clips**: `page.route` patches `Två kapitel`'s detail and reel reads,
  as the e2e critics did, against this agent's own server.
- **A chapter that lists a clip from another folder**: `Två kapitel`'s `reel.yaml` lists
  `Kvällen/s1710004.mp4` in its default chapter, beside the ignored `s1710004.mp4`.
- **No answer**: `page.route` aborts the `PUT …/reel`, so `fetch` rejects.
- **An error in the page**: an init script wraps `window.fetch` so that a `PUT` resolves to `null`.
  `saveReel` then throws reading the answer's status, outside its own `try`, which is an exception in the
  page and not a missing answer.

## Failure behavior & idempotency

- **No request is added, and none is removed.** Try again is the same `GET …/reel`. Saves, their
  conditions and their answers are unchanged, and so are the write body and the dirty rules (`draft.ts` is
  untouched).
- **Rendered output, fingerprints, jobs and `reel.yaml` are untouched by this change.** A re-run, a
  `--force` render or a worker restart does not interact with it.
- **A failed retry keeps the failure and the focus**, and announces the failure again. A retry answered
  after Edit mode closed is aborted, as today (`inFlight`).
- **`--toast-inset-bottom` is removed** when the bar leaves, and the registration is released, so the
  region and the scroll padding fall back to 0, as today.
- **A save with no answer, and one that hit an error in the page**, keep the edits and offer Retry, as
  every failed save does. Only their words change.
- **Nothing is invented.** Absent facts still show "—", and the counts come from the order the editor
  already holds.

## Risks / Trade-offs

- [The bar's buttons may now wrap their words, so a two-line "Reload latest (discard my changes)" at 320
  looks heavier] → It happens only below about 340 px. The alternative is horizontal scroll, which WCAG
  1.4.10 forbids.
- [A failure's height depends on the service's detail] → The bar shows the detail in full, so the spec
  bounds a failure at two fifths, not a third. The dev library's path and the writer's temporary name
  measured 300 px (36 %) at 390×844. A much deeper library path could still exceed it. Task 2.1 measures
  the real answer, and a miss there is a finding to report, not a reason to clip the text.
- [A missing or removed row gives about 102 px of its file column to its action in the one-line layout] →
  `borttagen.mp4` keeps its line from a 58.5rem panel. An 18-character missing camera name breaks inside
  the word between 58 and about 61rem (windows of about 990-1040 px). Today the Remove wraps under the name
  there instead. This is a cosmetic trade-off for a rare row.
- [Two copies of the toast's event-name format, until jobs-live-polish lands] → The local helper keeps
  P2's signature and output, so either change can make it one import (Open Questions).
- [A missing row's Remove moves to the facts line, next to the move buttons' line] → Under a coarse pointer
  both take 44 px areas. Task 6.1 runs ui-a11y-polish's touch probe over Edit mode, Sommarlov's missing
  row included, at 1280, 768, 390 and 320.
- [The grid's look depends on `event-page-polish`'s properties] → With the fallbacks, alignment holds
  either way. If that change renames a property, the fallback hides it, so task 4.1 asserts alignment
  against the live table, not against the numbers.
- [Edit mode's numbers move 24 px right] → This is the one shift the grip needs. Everything after the
  number stays.
- [A short window held at its top: the conflict bar can sit partly below it] → Found by task 6.1, and not
  new: on main the bar is taller. A sticky element cannot rise above its containing block,
  `.event-editor`. In a window 320 × 700, 340 × 700 or 375 × 667 scrolled to its very top, the editor
  starts 400 to 480 px down, and a 290 to 320 px conflict bar overhangs the window by 25 to 100 px. Its last
  row, which holds the focused Save, is then out of view until the page scrolls. In the usual flow, where
  editing a field scrolls the page, the bar is whole at every size measured, and at 390 × 844 it is whole
  even at the top. The fix would be structural: the bar's containing block, or scrolling the pressed
  control into view after an answer. It is a follow-up (Open Questions).
- [The drag handle is 24 px wide in the one-line layout] → It is still 32 px tall and meets WCAG 2.2's
  24 px target. Below 58rem, where touch is likely, it stays 32 px.

### Review fixes (2026-10-01)

The adversarial review re-checked each fix against main, P4's and P5's designs, and the fixture. It
changed:

- **The thumbnail property's name, checked.** This review found the names crossed: P1 read
  `--clip-thumb-w`, while P4's first draft published `--clip-col-thumb`, which P1's own prototype had used.
  The spike showed the cost: 80 px frames against 128 px. In parallel, P4's review renamed its property
  to `--clip-thumb-w`, so P1 keeps `--clip-thumb-w` and the two now agree. Task 1.1 still stops on any
  difference, and the supervisor is asked to confirm the final name (Open Questions).
- **The save bar's bound.** A third with a conflict, and two fifths with a failure, whose service detail
  is shown in full. The real write failure measured 36 %, not 27 %. The failed-write scenario no longer
  promises a failure kind, because the save 502 carries none.
- **The drop scenarios and task 3.1** name the fixture's rows (`s1710001.mp4`, `s1710003.mp4`), not
  `:8114`'s reordered ones. On the fixture `s1710004.mp4` is last and cannot move down.
- **Publish timing.** The ResizeObserver re-measures directly, as today, and only scroll and resize go
  through `requestAnimationFrame`.
- **Try again's focus** moves in a layout effect, so no frame paints with focus on `<body>`.
- **Grid details.** The action's spacing is a margin, and the base rules must precede the container
  blocks.
- **Wording.** Save turns secondary only while a conflict or a vanished event holds it back.
- **Recorded:** the interim before P5, and the missing row's narrow band.

The review's scripts, logs and screenshots are in `review/` (`rv_cols.py`, `rv_bar.py`, `rv_wide.py`),
under the scratch directory named in "Findings, reproduced". They ran read-only against `:8114`: every
PUT was fulfilled in the browser and every other non-GET aborted, and none reached the service.

## Migration Plan

None. This is a static client with no schema, setting or data change. Rollback is a revert of the change's
commits.

## Open Questions

Resolved by the supervisor (2026-10-01, "Supervisor decisions"): the five column names are final; the
two-fifths bound is accepted; the "Saved" toast names the event, and Edit mode adopts `clipNames` /
`ClipName`, both in this change.

Open:

- **One `eventName`.** This change keeps a local copy of jobs-live-polish's format for the "Saved" toast,
  because neither change may edit the other's files while both are in flight. Whichever lands second can
  replace one copy with an import of the other (`jobs/labels.ts` or `edit/EventEditor.tsx`), or the helper
  can move to a shared module in a follow-up.
- **The conflict bar on a short window held at its top** (Risks): a follow-up, if wanted. Either the save
  bar moves out of `.event-editor`, to a containing block that starts at the page's top, or the editor
  scrolls the pressed control into view after a failed answer.
- **Follow-ups the critics raised that are not in this round's list:**
  - Reset focuses an off-screen `h1` with `preventScroll`
  - 56 Tab stops from Title to Save on a 16-clip event
  - the verdict stays stale in Edit mode after a live render ends
