## 1. Gate

- [x] 1.1 Confirm the base. This change has no gate, but it starts from main at `bca64f2` or later. It runs in parallel with `jobs-live-polish`, `event-list-polish`, `event-page-polish`, `ui-a11y-polish` and `serve-clean-exit`.

  Re-check the names the design cites, and stop and report to the supervisor on any mismatch:
  - `web/src/edit/SaveBar.tsx`: `controlState`, `CONFLICT_DETAIL`, Save as `btn btn-primary`, and the conflict's "Reload latest (discard my changes)" as `btn-primary`
  - `web/src/edit/EventEditor.tsx`:
    - the bar's `useLayoutEffect` writes `bar.offsetHeight` to `--toast-inset-bottom`
    - `readReel` dispatches `reading`
    - the failed `Alert` holds Try again
  - `web/src/edit/ClipOrderList.tsx`:
    - `onDragEnd`, `focusAfter` and `scrollAfter`
    - the focus layout effect and the scrolling passive effect
    - `ClipFacts`, and `RowBody`'s `action` inside `.clip-file`
    - `· N removed on save` in `panel-meta`
  - `web/src/edit/edit.css`: the track list `2rem 2rem 5rem minmax(0, 1fr) 12rem 5.5rem 10.5rem 4.25rem`, and the `58rem` and `30rem` container queries
  - `web/src/events/EventDetail.tsx`: `className={editing ? 'btn btn-ghost' : 'btn btn-secondary'}`

  Write down which parallel changes are already on main (`ls openspec/changes/archive/ | grep -E -- '-(event-page-polish|ui-a11y-polish|event-list-polish|jobs-live-polish)$'`). For each one present, record what it landed (design, "Files and parallel changes"):
  - `event-page-polish`: `grep -n -- '--clip-col-\|--clip-thumb-w' web/src/events/detail.css`, which must show `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime`. Stop and report any other name, because the grid's fallbacks would hide it.
  - `ui-a11y-polish`: `grep -n 'keepToastsClearOf' web/src/ui/toast.ts web/src/edit/EventEditor.tsx`
  - `event-list-polish`: its lines in `SaveBar.tsx`, `EventEditor.tsx` and `ClipOrderList.tsx`. They stay as landed.

  Confirm that `openspec/specs/web-app/spec.md` has no requirement named like this change's three.

  Verify: `openspec validate edit-mode-polish --strict` passes.

## 2. web/ — the save bar

- [x] 2.1 Make the save bar compact, with one primary action (design, "The save bar: compact in place, one primary action").

  In `src/edit/SaveBar.tsx`:
  - Save's class follows `savePrimary`
  - the `gone` alert's link becomes `btn btn-primary`
  - `CONFLICT_DETAIL` is deleted, and the conflict's action slot ends with `<span className="alert-note">Your edits are kept.</span>`

  In `src/edit/edit.css` (`@layer screens`), add the save-bar rules from the design:
  - the card's `minmax(0, 1fr)` column, its gap and its padding
  - the `.save-bar-text` basis of `9rem`
  - `.save-bar .btn` wrapping
  - the compact `.save-bar-alert` rules

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the node:22 container
  - `grep -rn 'CONFLICT_DETAIL' web/src/edit` prints nothing
  - Playwright against the agent's own `serve` on :8115 (design, "Verification fixtures"). Edit the location of Grillning, hand-edit its `reel.yaml` title, then press Save. At 390×844:
    - with the page at its top (the bar stuck), `.save-bar`'s `offsetHeight` is at most 281 px (a third; the review measured 215)
    - `.save-bar-card .btn-primary` matches exactly one element, "Reload latest (discard my changes)"
    - Save has `btn-secondary` and `aria-disabled="true"`
    - `document.activeElement` is Save, and its `aria-describedby` is the alert's id
  - In `src/edit/EventEditor.tsx` (supervisor, after review): after every save answer, the focused control is scrolled into view (`block: 'nearest'`) when it is not fully inside the window. With the page held at its top and Save pressed, at 320×568, 320×700, 340×700 and 375×667, with a conflict and with a write failure, the focused Save and the `.save-bar-card` are inside the window.
  - With the same conflict at 320, 340 and 360 wide, `document.documentElement.scrollWidth <= clientWidth`, and every element inside `.save-bar-card` has `getBoundingClientRect().right <= innerWidth`
  - At 390×844, with Sommarlov's folder `chmod a-w`, saving a reorder shows "reel.yaml could not be saved.", the service's whole detail with the real library path and temporary file name (its text equals the answer's `detail`), and Retry. With the page at its top, `.save-bar`'s `offsetHeight` is at most 337 px (two fifths; the review measured 300), the page does not scroll sideways, and the card's one `.btn-primary` is Save. Restore the folder's permissions afterwards.
- [x] 2.2 Keep the toast contract as it landed, name the saved event, and word a save with no answer (design, "Supervisor decisions", "Toasts and the bar", "The "Saved" toast names the event", "A save with no answer, and an error in the page"):
  - `src/edit/EventEditor.tsx`: the bar effect keeps publishing `bar.offsetHeight` as `--toast-inset-bottom`, with `keepToastsClearOf(bar)` and its `release()`; only its comment changes. The success toast says `Saved <name>`, with jobs-live-polish's `eventName` format and the saved title and date (never a value the service resolves). The `.catch` after `send()` makes a `disk`-kind problem titled "The save stopped on an error in this page.", logs the error, and keeps Retry.
  - `src/edit/SaveBar.tsx`: the `unreachable` alert shows no detail; a comment above the `disk` kind says what it covers.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `grep -n 'keepToastsClearOf\|release()\|offsetHeight' web/src/edit/EventEditor.tsx` shows all three inside the bar effect
  - Playwright, on Grillning with a title edit, at 1280×900 and at 390×844: `--toast-inset-bottom` equals `.save-bar`'s `offsetHeight`, and after Reset the property is absent
  - Saving a location change on Grillning shows a success toast whose text is `Saved “Grillkväll med grannarna” · 2024-06-27` (with its no-break spaces and word joiners); restore its `reel.yaml` afterwards
  - At 390×844, a reorder of Badutflykt whose `PUT …/reel` is aborted by `page.route`: the bar says "The service is not reachable.", its text has no "Failed to fetch" or "TypeError", Retry is there, focus stays on Save, and `.save-bar`'s `offsetHeight` is at most 281 px
  - The same save with an init script that resolves a `PUT` `fetch` to `null`: the bar says "The save stopped on an error in this page.", not "not reachable", and offers Retry

## 3. web/ — keyboard focus

- [x] 3.1 Scroll a dropped row clear of the save bar (design, "The first drop keeps its row in view"). In `src/edit/ClipOrderList.tsx`:
  - `onDragEnd` records `dropped`, for a drop that changed the order
  - the layout effect turns it into `scrollAfter` before its `focusAfter` early return
  - the passive effect is unchanged

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - Playwright. Sample the focused element at its centre and its four corners with `elementFromPoint`, the critics' method. On Grillning in Edit mode with no other edit, drop from the keyboard (Space, ArrowDown, Space) the first clip, `s1710001.mp4`, and then the third, `s1710003.mp4`. Run each from a fresh Edit mode, so that the drop is the edit that brings the bar in. On main these rows' handles had 3-5 of 5 points under the bar (design, "Findings, reproduced"). Do this at 1280×900, 768×1024 and 390×844, and once more at 1280 with `reduced_motion='reduce'`.
    - Each time, focus is on the dropped clip's handle, and none of the 5 points hits `.save-bar-card`, `.app-header` or a `.panel-header`.
    - Move down on `s1710002.mp4`, and Remove and Undo on Sommarlov's `borttagen.mp4`, still leave 0 points covered.
    - The spec's "Dragging a clip to the front" scenario still holds with a pointer drag.
- [x] 3.2 Keep focus on Try again (design, "Try again keeps focus"). In `src/edit/EventEditor.tsx`:
  - the `retrying` flag and action, and `readReel(retry)`
  - Try again `aria-disabled` and `aria-busy` while retrying, and its click ignored meanwhile
  - "Reading reel.yaml…" in the status region while retrying
  - the layout effect after the answer (`useLayoutEffect`, so no frame paints with focus on `<body>`): on a failure, `announce(cause)`; on a read, focus the details `<h2>` (a ref, `tabIndex={-1}`); on a change on disk, focus "Read again" (a ref)

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - Playwright, with Grillning's `reel.yaml` made unparseable after the page read: Edit, then focus Try again. Hold `GET …/reel` for 1.5 s with `page.route` and press Enter. While it is held:
    - `document.activeElement` is Try again, with `aria-busy="true"` and `aria-disabled="true"`
    - the failure is still shown
    - the status region reads "Reading reel.yaml…"
  - After the failed answer, focus is still on Try again, and the status region holds the failure's cause
  - Restore the file and press Enter. The fields show, and `document.activeElement` is the "Details" `h2`.
  - The fix form of `2024-02-30 - Omöjligt datum`, with its first `GET …/reel` answered 502 by `page.route` and the next one passed through, behaves the same, and focus lands on "Fix the date or title"
  - `activeElement` is never `BODY` at any step

## 4. web/ — rows and headings

- [x] 4.1 Build Edit mode's grid from the table's tracks, and move the row action after the facts (design, "One grid with the table", "A missing clip's row: its action after its facts").

  In `src/edit/edit.css`:
  - the one-line track list and areas, reading `--clip-col-pos`, `--clip-thumb-w`, `--clip-col-status`, `--clip-col-size` and `--clip-col-mtime` with today's widths as fallbacks
  - the items' areas and cell padding, the action's end margin, and the 1.5rem handle
  - the header strip's areas
  - the `< 58rem` block restoring its own gap, padding, 2rem handle, 5rem thumbnail, zero item padding and zero action margin, with the same selectors as the base rules it undoes

  The new base rules go before the `(width < 58rem)` and `(width < 30rem)` blocks, so the narrow areas win by source order (design, "Cascade order matters").

  In `src/edit/ClipOrderList.tsx`, `RowBody` passes `action` to `ClipFacts`, which renders it after `.clip-mtime`, in a `.clip-action` wrapper. This covers `ClipRow`'s Remove and `RemovedRow`'s Undo. Under a coarse pointer, from a 28rem panel to the one-line layout, a Remove takes a facts line of its own (design, "A missing clip's row", changed at implementation).

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass, and `grep -rn ' disabled=' web/src/edit` prints nothing
  - Playwright, on Grillning, Sommarlov and Två kapitel at 1280 and 1024 (both schemes at 1280). If `event-page-polish` is on main, the frames at 1280 are 128 px wide in both views. For every row, in the read view and then in Edit mode, these each start within 1 px of each other: `.clip-thumb`, the file name's text (a `Range` over it), the status pill, and the size and time text. The header strip's "Status", "Size" and "Modified" start within 1 px of the table's headers.
  - At 390, Sommarlov's `borttagen.mp4` row is at most 8 px taller than `s1710002.mp4`'s, and its Remove's left edge is at or right of its box's right edge
  - Sweep from 320 to 1440 px, in steps of 40, over Sommarlov with `borttagen.mp4` removed, and over Två kapitel: `scrollWidth <= clientWidth` throughout
  - The pointer-drag and keyboard-reorder scenarios of the spec still hold
- [x] 4.2 Finish the headings, the toggle and the fields (design, "Chapter headings stay one line", "Stop editing, and field edges"):
  - in `src/edit/ClipOrderList.tsx`: `panel-meta` holds only the count, and both captions carry their counts
  - in `src/edit/edit.css`: `.edit-chapter > .panel-header > h2` gets `min-inline-size: 0; overflow-wrap: anywhere`; `.field-input` gets a `--fg-subtle` edge and a `--fg-muted` hover
  - in `src/events/EventDetail.tsx`: the toggle's `className="btn btn-secondary"`, the one line

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff main -- web/src/events/EventDetail.tsx` shows one changed line
  - Playwright:
    - **Sommarlov at 320**, after removing `borttagen.mp4` and moving `s1710004.mp4` up: no horizontal scroll; `.edit-chapter .panel-header` is at most 44.5 px tall and reads "Clips", "1 clip moved" and "2 clips"; the caption reads "1 clip removed from reel.yaml when you save"
    - **Två kapitel at 390**: Main's heading reads "Main" and "1 clip", and its caption reads "1 ignored clip, not played"
    - **Två kapitel with `gammal.mp4` patched into Main** by `page.route`, after Remove and Move down, at 390 and at 320: no horizontal scroll, and the heading is at most 44.5 px tall
    - **The toggle**: it has `btn btn-secondary` as Edit and as Stop editing, and focus stays on it when Edit mode starts
    - **The fields**: the edges of the empty Location and Description measure at least 3:1 against their panel in light and in dark (the canvas method of the design's "Findings, reproduced")

- [x] 4.3 Name clips as the table does (design, "Clip names, as the table names them"). In `src/edit/ClipOrderList.tsx`, one `clipNames(chapter, [...original, ...ignored])` per chapter names every row (`ClipName`), its frame (`ClipThumb`'s `name`), the handle's, Move's, Remove's and Undo's labels, and the drag and button announcements. `fileName` is no longer used there.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass, and `grep -n 'fileName' web/src/edit/ClipOrderList.tsx` prints nothing
  - Playwright, with `Två kapitel`'s `reel.yaml` listing `Kvällen/s1710004.mp4` after `s1710001.mp4` in its default chapter (restored afterwards): in the read view and in Edit mode, `Main`'s rows read `s1710001.mp4`, `Kvällen/s1710004.mp4` and the ignored `s1710004.mp4`; the second's handle is named "Reorder Kvällen/s1710004.mp4"; its Move up announces "Kvällen/s1710004.mp4 moved to position 1 of 2."; and after the move the names are unchanged
  - On Grillning (one folder) every Edit row's name equals its file name, as before

## 5. Docs

- [x] 5.1 Update `web/README.md`, the Edit-mode paragraph:
  - the save bar's one primary action
  - its compact failure at phone width
  - the rows sharing the table's columns, and naming clips as the table does
  - the headings' clip count, and the counts on the removed and ignored lists. The quoted caption "Removed from reel.yaml when you save" becomes the counted one, for example "1 clip removed from reel.yaml when you save"
  - Try again keeping focus

  The "Toasts" bullet, as `ui-a11y-polish` rewrote it, already says that the page sets `--toast-inset-bottom` to the bar's height, which stays true (supervisor decision), so it is left as it is.

  Verify:
  - `grep -n "toast-inset-bottom" web/README.md` still shows the Toasts bullet's sentence, unchanged
  - `grep -n "primary" web/README.md` hits the Edit-mode paragraph
  - `grep -n '"Removed from reel.yaml when you save"' web/README.md` prints nothing
  - `git diff --stat main -- docs` is empty

## 6. Verification against the dev library

- [x] 6.1 Run the whole pass in the agent's own environment (design, "Verification fixtures"): `SLUG=edit-mode-polish`, `N=15`, database `arel_edit_mode_polish`, library `../dev-edit-mode-polish`, `serve` on 8115, and no worker. Never use port 8080 or 5173, the default database, `../auto-reel-dev`, `auto-reel-media/`, or another agent's database, library or port.

  The Playwright scripts live in `<scratchpad>/verify/edit-mode-polish/` and are never committed. Run them in `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `--network host`, with locators scoped to `main:not([hidden])`.

  - **Screenshots**, light and dark, at 1280, 768, 390 and 320 px:
    - Grillning in Edit mode: clean, then dirty with the bar
    - the conflict bar
    - Sommarlov's write failure
    - Sommarlov's missing row, and its removed list
    - Två kapitel in Edit mode
    - the Try again failure

    Look at every one.
  - **axe-core**, injected ad hoc: no serious or critical violation in Edit mode with the conflict shown, and with Sommarlov's missing row, in both schemes
  - **The tasks' checks**: run once more the checks of 2.1, 2.2, 3.1, 3.2, 4.1, 4.2 and 4.3 on the final build
  - **`ui-a11y-polish` is on main**, so two integration checks. Hold an error toast, from the row Render of `2024-07-14 - kalas` (the real 409):
    - From the top of Grillning's Edit mode at 1280×900 and at 390×844, a Tab walk to Save finds no focused control with any of its 5 sample points under `.toast`, `.save-bar-card` or `.app-header`.
    - On Grillning and on the Omöjligt datum fix form, at 1280, 390 and 320, at scroll 0, 50, 90, 97 and 100 %, no `.toast` rect intersects `.save-bar-card`.
  - **Touch**: `ui-a11y-polish`'s touch probe (every point of each control's 44 × 44 area reaches that control), under a coarse pointer, over Grillning's, Sommarlov's and Två kapitel's Edit mode at 1280, 768, 390 and 320, and over the conflict bar at 390 and 320
  - **`event-page-polish` is on main**: at 1280, both views show 128 px frames, and the alignment check of 4.1 holds

## 7. Validation

- [x] 7.1 Run the gates. Verify all pass:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - the motion grep gate (web/README.md, "Motion") over `web/src/edit`. This change adds no animation.
  - `grep -rn 'autoFocus' web/src/edit` prints nothing
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, then `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, with the web-mount and OpenAPI drift tests green
  - `git diff --stat main -- auto_reel_ng tests scripts docs web/openapi.json web/src/api web/package.json web/package-lock.json web/src/jobs web/src/ui web/src/shell web/src/styles` is empty
  - `openspec validate edit-mode-polish --strict` passes
  - no Playwright script, screenshot or `.playwright` directory is in the worktree
