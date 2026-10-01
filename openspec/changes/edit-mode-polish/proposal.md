## Why

GUI v1 (HLD **§6 phase 8**, §4.10) is feature-complete. Its visual system (**D-10**) promises a modern,
quiet app that works by keyboard and at phone width, inside D-8's budget. The final end-to-end pass on
main (bca64f2) and four critics found that Edit mode (slice D, `event-edit-screen`, extended by
`missing-clips-screen` and `clip-thumbnails-screen`) breaks that promise in eight places. Each one was
reproduced read-only on `serve` :8114 before this proposal (design, "Findings, reproduced"):

- **The save bar crowds out the editor on a phone.** At 390 × 844, a conflict turns the sticky bar into
  378 px, 45 % of the window. A failed write whose detail names a real library path takes 380 px. Both the
  conflict's "Reload latest" and the blocked Save are accent-filled primaries. At 320 and 340 px the
  conflict alert widens the page to 357 px, so the page scrolls sideways.
- **Toasts cover the save bar.** The toast offset is the bar's height, which is right only while the bar is
  stuck to the bottom of the window. At the end of the page, where Tab to Save takes you, and on the short
  fix form, a toast lands on Save. An error toast stays there until it is dismissed, and blocks a pointer
  click on Save.
- **Keyboard focus is lost or hidden.** The first keyboard drop leaves the focused handle under the save bar
  it brought in: 5 of 5 sample points are covered at 1280. Try again after a failed `reel.yaml` read drops
  focus to `<body>`.
- **Layout.** A chapter heading with moved, removed and ignored counts scrolls a 390 px page sideways
  (399 px). A missing clip's row breaks over four lines. Entering Edit mode shifts every column sideways,
  for example Status from x 739 to 651 at 1280. "Stop editing" is drawn as a ghost button, so it looks
  unavailable. Text fields have 1.5:1 edges, and WCAG 1.4.11 asks for 3:1.

The contract these break is already written. The web-app spec says a focused control is never hidden behind
anything that stays in place, a busy control keeps focus, and no page scrolls sideways at phone width. The
design-system design says a toast never covers Save. This change fixes the Edit-mode side. It is the
`edit-mode-polish` slice of the v1 polish round, and runs in parallel with `jobs-live-polish`,
`event-list-polish`, `event-page-polish`, `ui-a11y-polish` and `serve-clean-exit`.

## What Changes

- **A compact save bar with one primary action.**
  - The bar's card can no longer widen the page. Its buttons may wrap their words, so the conflict fits a
    320 px window.
  - The failure alert inside the bar takes a compact form: a smaller icon, small text, and tighter padding.
  - The status and the Reset/Save buttons share one row wherever they fit.
  - The conflict alert keeps its title and its two choices. Its separate paragraph becomes the same "Your
    edits are kept." note the write-failure alert already uses.
  - Exactly one primary action at a time:
    - Save, normally
    - "Reload latest" while a conflict holds Save back
    - "Back to the event list" when the event no longer exists

    Save stays in place, keeps focus and stays aria-disabled, but is drawn as secondary while a conflict
    or a vanished event holds it back. An incomplete date leaves it primary and aria-disabled, as today.
  - Targets in a 390 × 844 window:
    - at most a third with a conflict (measured at 215 px, 25 %)
    - at most two fifths with a failed write, whose service detail is shown in full (measured at 300 px,
      36 %, with the dev library's real path and temporary file name)
- **The save bar's side of the toast contract.** Toast placement belongs to `ui-a11y-polish`. That change
  registers the bar with `keepToastsClearOf(bar)`, using two lines in this change's bar effect, and the
  region places itself above the stuck bar or below the resting one. This change owns what the editor
  publishes:
  - `--toast-inset-bottom` becomes the live band from the bar's top edge to the bottom of the window, kept
    current on scroll and resize. Before, it was the bar's height, which is right only while the bar is
    stuck.
  - So `html`'s `scroll-padding-bottom` also covers the toasts that ride above a bar on its way up to rest,
    and a focused control scrolls clear of them.
  - Today's value is unchanged while the bar is stuck.
- **Focus stays in view and is never dropped.**
  - A drop that changes the order, from the keyboard or a pointer, scrolls the dropped row clear of the save
    bar, as the Move, Remove and Undo buttons already do.
  - Try again keeps the failure shown and becomes busy (aria-disabled, aria-busy) while it reads. A failed
    retry keeps focus on it and is announced again. A successful one moves focus to the editor's first
    heading.
- **Rows and headings that fit and line up.**
  - **Shared columns.** In the one-line (wide) layout, the edit rows use the event page table's column
    widths, read from the column custom properties that `event-page-polish` publishes (including its
    8rem frames in a panel of 64rem or more), with today's widths as fallbacks. The position number makes
    room for the handle, and the move buttons (plus a missing clip's Remove or a removed clip's Undo) sit
    at the end of the file column. The thumbnail, file name, status, size and time stay where the table shows them.
  - **Missing clip rows.** A missing clip's Remove, and a removed clip's Undo, move from under the file name
    to after the clip's facts. At 390 the row keeps two lines, like the others.
  - **Chapter headings.** A chapter heading in Edit mode holds its name, the moved badge and the clip count,
    so it stays one line. The removed and ignored counts move into the captions of their own lists: "1 clip
    removed from reel.yaml when you save" and "1 ignored clip, not played".
  - **Stop editing** keeps the same secondary style as Edit.
  - **Field edges** take `--fg-subtle`, which measures 3.62:1 in light and 3.94:1 in dark.
- **Docs:** `web/README.md`: the Edit-mode paragraph, and the toast bullet's sentence on
  `--toast-inset-bottom`.

## Non-goals

- **Nothing outside Edit mode.** Other polish changes own these:
  - `event-page-polish`: the event page's table, header, status column, thumbnail size and clip names
  - `event-list-polish`: date and time formats, and the failure kinds
  - `ui-a11y-polish`: the toast region, where toasts sit (and its spec requirement that notifications
    never cover the save bar), toast focus and live regions, and dialog descriptions
  - `jobs-live-polish`: render toasts

  Where one of those changes needs a call site in this change's files, or this change needs one in theirs,
  the design names it.
- **The "Saved" toast keeps its wording.** `jobs-live-polish` names render toasts by title and leaves
  "Saved" to this file's owner. That is not one of this change's findings, so it is an open question for
  the supervisor (design).
- **Save stays at the end of the tab order.** The critics measured 56 Tab stops from Title to Save on a
  16-clip event. A roving tabindex or a Save shortcut is a separate change.
- **Focus after Reset is unchanged.** Reset still focuses the page heading in place. The critic's point
  that the heading is off-screen is not in this round's list. It is recorded as a follow-up.
- **The date line still leaves when Edit mode opens.** The spec has the fields take the place of the facts
  and the description. Only the sideways shift is fixed.
- **No new dependency, token, API, engine or schema change.** Principle VII: every fix reuses an existing
  token or class.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: three ADDED requirements, all Edit mode's own. No MODIFIED block, so the parallel polish
  changes cannot lose each other's wording at archive. The toast rule is `ui-a11y-polish`'s requirement
  ("Notifications never cover the save bar"), and it is not restated here.
  - `Requirement: Edit mode's save bar stays compact and fits the window`
  - `Requirement: Edit mode keeps keyboard focus in view and never drops it`
  - `Requirement: Edit mode lines up with the event page and fits a phone`

## Impact

- **Packages:** `web/` only, plus one documentation file.
  - `src/edit/`:
    - `SaveBar.tsx`: the primary action, the conflict copy
    - `EventEditor.tsx`: the live toast inset, the Try again focus, the heading ref
    - `ClipOrderList.tsx`: the drop scroll, the row action slot, the heading counts and captions
    - `edit.css`: the save bar, the row grid, and the field edges
  - `src/events/EventDetail.tsx`: the Edit and Stop editing toggle's class, one line. The brief assigns
    that toggle to this change.
  - `web/README.md`.
- **CLI vs API (Principle V):** untouched. No behaviour moves into `api/`.
- **Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump, and the fingerprint inputs are unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, no Alembic migration and no rescan.
  `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gates:** none beyond main at bca64f2. Coordination with the parallel changes, listed in the design
    under "Files and parallel changes":
    - with `event-page-polish`: its column properties `--clip-col-pos`, `--clip-thumb-w`,
      `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime`, which this grid reads with today's
      widths as fallbacks
    - with `ui-a11y-polish`: the toast contract, meaning its two registration lines in the bar effect
    - with `event-list-polish`: its call sites in `EventEditor.tsx`, `SaveBar.tsx` and
      `ClipOrderList.tsx` (failure kinds and the clip time)
  - **New runtime dependencies:** none. D-8's budget is unchanged.
- **Size (Principle VIII):** one package, one capability delta and 10 tasks.
