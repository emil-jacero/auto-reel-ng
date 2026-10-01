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
- **The save bar's side of the toast contract.** Toast placement belongs to `ui-a11y-polish`, which landed
  first. It registers the bar with `keepToastsClearOf(bar)`, using two lines in this change's bar effect.
  Its region places itself above the stuck bar or below the resting one, and publishes the height of the
  toasts that rise with the bar for the scroll padding. This change keeps those two lines and keeps
  publishing `--toast-inset-bottom` as the bar's height (supervisor decision; the live band this proposal
  first planned is dropped).
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
- **Supervisor additions:**
  - **The "Saved" toast names the event** by its title and date, as the render toasts of `jobs-live-polish`
    do, or by its folder name when the saved event has no known title.
  - **Edit mode names clips as the event page's table does** (`clipNames` / `ClipName` from
    `event-page-polish`): a chapter that lists a clip from another folder names its clips by their paths, in
    the rows, the frames, the control labels and the announcements.
  - **A save with no answer** says the service is not reachable without the browser's own error text. An
    error in the page itself is no longer reported as an unreachable service.
- **Docs:** `web/README.md`: the Edit-mode paragraph.

## Non-goals

- **Nothing outside Edit mode.** Other polish changes own these:
  - `event-page-polish`: the event page's table, header, status column, thumbnail size and clip names
  - `event-list-polish`: date and time formats, and the failure kinds
  - `ui-a11y-polish`: the toast region, where toasts sit (and its spec requirement that notifications
    never cover the save bar), toast focus and live regions, and dialog descriptions
  - `jobs-live-polish`: render toasts

  Where one of those changes needs a call site in this change's files, or this change needs one in theirs,
  the design names it.
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

- `web-app`: four ADDED requirements, all Edit mode's own, and, after the supervisor's review, once every
  sibling change had landed, two MODIFIED ones whose "file name" became "the clip's name, as the event
  page's table names it". The toast rule is `ui-a11y-polish`'s requirement ("Notifications never cover the
  save bar"), and it is not restated here.
  - `Requirement: Edit mode's save bar stays compact and fits the window`
  - `Requirement: Edit mode keeps keyboard focus in view and never drops it`
  - `Requirement: Edit mode lines up with the event page and fits a phone`
  - `Requirement: Edit mode names clips and the saved event as the other screens do`
  - MODIFIED `Requirement: The event page reorders clips within a chapter`
  - MODIFIED `Requirement: Edit mode removes a missing clip from reel.yaml on request`

## Impact

- **Packages:** `web/` only, plus one documentation file.
  - `src/edit/`:
    - `SaveBar.tsx`: the primary action, the conflict copy, the no-answer alert's detail
    - `EventEditor.tsx`: the Try again focus, the heading ref, the "Saved" toast's name, the failure an
      error in the page gets
    - `ClipOrderList.tsx`: the drop scroll, the row action slot, the heading counts and captions, the clip
      names
    - `edit.css`: the save bar, the row grid, and the field edges
  - `src/events/EventDetail.tsx`: the Edit and Stop editing toggle's class, one line. The brief assigns
    that toggle to this change.
  - `src/events/labels.ts`: `notReachableHint(control)` beside `NOT_REACHABLE_HINT`, for Try again's
    wording (after review; the list's and the page's wording is unchanged).
  - `web/README.md`.
- **CLI vs API (Principle V):** untouched. No behaviour moves into `api/`.
- **Rendered output:** unchanged. No `RENDER_GRAPH_VERSION` bump, and the fingerprint inputs are unchanged.
- **Schemas:** no `reel.yaml`, `config.yaml` or API change, no Alembic migration and no rescan.
  `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gates:** none beyond main at bca64f2. Implemented on main at eb86e8b, where `event-page-polish` and
    `ui-a11y-polish` have landed. Coordination with the parallel changes, listed in the design under "Files
    and parallel changes":
    - with `event-page-polish`: its column properties `--clip-col-pos`, `--clip-thumb-w`,
      `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime`, which this grid reads with today's
      widths as fallbacks
    - with `event-page-polish`: its `clipNames` and `ClipName`, which Edit mode's rows adopt
    - with `ui-a11y-polish`: the toast contract, meaning its two registration lines in the bar effect, and
      its coarse-pointer tap areas, which the compact bar and the row action keep clear of each other
    - with `jobs-live-polish`: its `eventName` formatter, which the "Saved" toast imports
    - with `event-list-polish`: its call sites in `EventEditor.tsx`, `SaveBar.tsx` and
      `ClipOrderList.tsx` (failure kinds and the clip time)
  - **New runtime dependencies:** none. D-8's budget is unchanged.
- **Size (Principle VIII):** one package, one capability delta and 11 tasks.
