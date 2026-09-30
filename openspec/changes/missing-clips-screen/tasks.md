## 1. Gate

- [ ] 1.1 Confirm that **both** gates are archived on main: `ls openspec/changes/archive/ | grep -E -- '-(event-edit-screen|render-progress-screen)$'` must print two lines. If it does not, stop and report to the supervisor.

  Then re-check the names this change builds on (design, "Context"), and stop and report on any mismatch:
  - `web/src/edit/draft.ts` exports `editableChapters`, `ordersOf`, `buildWriteBody`, `isDirty`, `moveClip`, `movedSet` and `adoptedNewCount`, and imports only with `import type`
  - `web/src/edit/EventEditor.tsx` has `reduce` with the `move` and `reset` actions, `afterEdit`, `summarize`, `submit` and `announce`
  - `web/src/edit/ClipOrderList.tsx` has `RowBody`, `ClipRow`, `IgnoredRow`, the ignored tail (`ignored-caption`, `clip-ignored`), the move-focus layout effect, and the passive effect after it that scrolls
  - `web/src/jobs/RenderControl.tsx` takes `blockedReason?: string`
  - `grep -n "blockedReason" web/src/events/EventDetail.tsx` shows the Edit-mode seam's `editing ? 'Save or leave Edit mode to render' : undefined`
  - `web/src/jobs/LiveJobCell.tsx` shows `RowRender` under `staleness.stale && !active`
  - `web/src/jobs/labels.ts` exists
  - `grep -n "btn-compact\|render-blocked" web/src/jobs/jobs.css` hits both
  - `web/src/ui/Icon.tsx` names `x`, `rotate-ccw` and `alert-triangle`

  If `openspec/changes/archive/` also holds `clip-thumbnails-screen`, write down the props that `IgnoredRow` now passes to `RowBody`: `RemovedRow` must pass the same (design, "Files and parallel changes").

  Re-base the four MODIFIED blocks in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`: for each requirement, take the landed text and carry this change's edits onto it (design, "Research & Decisions"), so no gate's wording is lost.

  Verify: `openspec validate missing-clips-screen --strict` passes and no longer prints "Archive would refuse".

## 2. web/ — the edit model

- [ ] 2.1 In `src/edit/draft.ts`, add `Removals`, `removeClip` and `restoreClip` (which takes the chapter's original order), and give `buildWriteBody` a `removed: ReadonlySet<string>` parameter that leaves those keys out of `clips` (design, "The write body", "The draft: a removal leaves the order"). Keep the file free of runtime imports.

  Verify:
  - `npx tsc --noEmit` passes
  - a scratch script in the session scratchpad (never committed) runs under `node --experimental-strip-types` in the node:22 container. It imports `draft.ts` and asserts the following over detail and `GET …/reel` JSON hand-copied from the agent's library (set up as in 5.1, with design, "Verification fixtures"):
    - **Sommarlov:**
      - `removeClip` of `borttagen.mp4` gives the order `[s1710002.mp4, s1710004.mp4]`
      - the body's chapters are `[{ name: '', clips: [s1710002.mp4, s1710004.mp4] }]`, and its `clips` is `{}`
      - `metadata`, `look` and `ignore` deep-equal the read
    - **Sommarlov, undone:** `restoreClip` gives back the original orders, `isDirty` is false, and the body with an empty `removed` deep-equals the read
    - **Sommarlov, a move between:** remove `borttagen.mp4`, move `s1710004.mp4` up, then `restoreClip`: the order is `[s1710004.mp4, s1710002.mp4, borttagen.mp4]`, and `movedSet` over the full original counts 1
    - **Två saknade:**
      - removing `Kväll/gone-b.mp4` gives a body whose `Kväll` is `[Kväll/s1710003.mp4]`, whose root chapter is the read's own entry, and whose `clips` is `{}`
      - removing `gone-a.mp4` as well gives a root chapter of `[s1710001.mp4]`
    - **two removals in one chapter** (a hand-made order `['a', 'x', 'y']`): removing `x` and then `y` leaves `['a']`, and so does removing `y` and then `x`. From each, undoing in both orders gives back `['a', 'x', 'y']` with `isDirty` false. That is four cases, and the first one (`x`, then `y`, then undo `x`, then `y`) is the one an index-based restore gets wrong, as `['a', 'y', 'x']`.
    - **moves:** `movedSet` over the original without the removed clip, against the order after a removal alone, has size 0

## 3. web/ — the editor

- [ ] 3.1 In `src/edit/EventEditor.tsx`, add the removals to the draft (design, "The draft: a removal leaves the order"):
  - `Ready.removed`, and the `remove` and `restore` actions through `afterEdit`, both refused while a save is in flight. `restore` passes `restoreClip` the chapter's order from `original`.
  - `reset` empties `removed`
  - the handler dispatches `remove` only for a clip whose detail status is `missing`
  - `summarize` gains the removed count ("1 missing clip removed"), after the moves and before the adoption
  - the moved count is taken against each chapter's original order without its removed clips
  - `submit` passes the removed identities to `buildWriteBody`
  - the hint's sentence for an event with a missing clip
  - `ClipOrderList` receives the chapter's removed identities, in original order, plus `onRemove` and `onRestore`

  Verify: `npx tsc --noEmit` and `npm run build` pass, and `git diff --stat web/src/edit/SaveBar.tsx web/src/edit/unsaved.ts` is empty.
- [ ] 3.2 In `src/edit/ClipOrderList.tsx` and `src/edit/edit.css`, add the controls and the tail (design, "How a removed clip is shown", "The Remove and Undo controls", "Focus and announcements"):
  - `RowBody`'s optional `action` slot at the end of `.clip-file`
  - the memoised Remove button in `ClipRow`, for missing rows only
  - `RemovedRow`, mirroring `IgnoredRow`, with its Undo
  - the "Removed from reel.yaml when you save" caption and `<ul className="clip-order clip-removed">` between the `<ol>` and the ignored tail
  - `· N removed on save` in `panel-meta`
  - the `moved` memo over the original without removed clips
  - focus follows the clip: Undo after Remove, Remove after Undo, each with its announcement. The effect finds the row from a ref on the chapter's `<section>`, never `listRef`: the tail is outside the `<ol>`, and the `<ol>` is not rendered once every clip is removed. As for `main`'s move buttons, the layout effect focuses with `preventScroll`, and the passive effect after it scrolls (design, "Focus and announcements").
  - both controls `aria-disabled` while locked, never `disabled`
  - `.removed-caption` sharing `.ignored-caption`'s rule, `.clip-removed .clip-item` sharing the ignored rows' look, and the struck-through `.clip-removed .clip-name`, all in `@layer screens`, with no new grid column and no breakpoint change

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `grep -rn ' disabled=' web/src/edit` prints nothing
  - `git diff web/src/edit/edit.css` changes no `grid-template-columns`, `grid-template-areas` or `@container` line (the breakpoint is `54rem`, or `58rem` if `clip-thumbnails-screen` landed first)

## 4. web/ — the render guard, and docs

- [ ] 4.1 Hold the render back (design, "The render guard"):
  - `src/jobs/labels.ts`: `missingClipsReason` and `MISSING_BLOCKS_ROW`
  - `src/events/EventDetail.tsx`: the seam's `blockedReason` expression falls back to `missingClipsReason(event.missing)`
  - `src/jobs/LiveJobCell.tsx`: a `blockedReason?: string` prop, and the `.row-blocked` note (the `alert-triangle` icon plus the words) in place of `RowRender`
  - `src/events/EventList.tsx`: `EventRow` passes `blockedReason={event.missing_count > 0 ? MISSING_BLOCKS_ROW : undefined}`
  - `src/jobs/jobs.css`: the `.row-blocked` rule in `@layer components`

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff --stat` shows no change to `RenderControl.tsx`, `JobProgress.tsx` or `store.ts`
  - the `EventDetail.tsx` and `EventList.tsx` diffs are 5 lines or fewer each
- [ ] 4.2 Update the docs:
  - `web/README.md`:
    - the Edit-mode paragraph: a missing clip's Remove, the "removed on save" list with Undo, and that only `reel.yaml` changes
    - the render paragraph: a missing clip holds Render back on the page and on the row, and says why
  - `docs/high-level-design.md` §4.10: append one sentence to the slice table's row D saying that `missing-clips-screen` adds the explicit removal of a MISSING clip's entry (never automatic) and holds Render back while an event lists one

  Verify:
  - `grep -n "missing-clips-screen" docs/high-level-design.md` hits row D
  - `git diff docs/high-level-design.md` touches that row only
  - `grep -n "Removed from reel.yaml\|missing clip" web/README.md` hits

## 5. Verification against the dev library

- [ ] 5.1 Set up the agent's own environment per the dev-env runbook §9, with `SLUG=missing-clips-screen` and `N=13`:
  - database `arel_missing_clips_screen`, library `../dev-missing-clips-screen`
  - `auto-reel serve <library> --port 8113` over a fresh `npm run build`
  - no worker until a step starts one
  - never port 8080, `../auto-reel-dev` or `auto-reel-media/`, and never another agent's database, library or port
  - in that library copy only, add `2024/2024-09-02 - Två saknade` and `2024/2024-09-03 - Utesluten` exactly as in design, "Verification fixtures", then save a copy of each fixture's `reel.yaml` and of Sommarlov's

  Drive the built client at `http://127.0.0.1:8113/` with a Playwright script kept in `<scratchpad>/verify/missing-clips-screen/`, never committed:
  - container `mcr.microsoft.com/playwright/python:v1.49.0-noble`, with `--network host`
  - locators scoped to `main:not([hidden])`
  - every `PUT` body captured
  - host-side file checks done with `cat` and `diff`

  Check each item, in this order:
  - **List (worker off):**
    - the `2024-09-01 - Sommarlov` row shows "1 missing", its verdict, no button named "Render 2024-09-01 - Sommarlov", and the words "Blocked by missing clips" beside an icon
    - the `2024-09-02 - Två saknade` row shows "2 missing" and the same words
    - `2024-06-27 - Grillning med grannar` still offers its Render
  - **Guard copy:**
    - Sommarlov's page offers neither Render nor Render anyway, and its render region reads "borttagen.mp4 is missing from disk. Restore it, or remove it in Edit mode."
    - Två saknade's reads "2 clips are missing from disk. Restore them, or remove them in Edit mode."
    - Utesluten's names `borta.mp4` and offers neither Render nor Render anyway, and its row shows "Blocked by missing clips" (it was never rendered, so it is stale). Record this as the accepted limitation (design, "Excluded missing clips").
  - **Precedence:** on Sommarlov, Edit replaces the reason with "Save or leave Edit mode to render". Stop editing with no change restores the missing-clip reason.
  - **Only missing clips offer removal:**
    - in Edit mode, Sommarlov has exactly one button whose name starts with "Remove " (named "Remove borttagen.mp4 from reel.yaml")
    - `2024-08-20 - Två kapitel - Tjörn` has none
  - **Keyboard only, on Sommarlov:** Tab to Remove and press Enter. Then:
    - the `<ol>` lists `s1710002.mp4` and `s1710004.mp4`, numbered 1 and 2
    - the "Removed from reel.yaml when you save" list holds `borttagen.mp4` with its "Missing" status
    - `document.activeElement` is "Undo removing borttagen.mp4"
    - the editor's status region reads the removal
    - the save bar says "1 missing clip removed"

    Enter on Undo: `borttagen.mp4` is at position 3 again, focus is on its Remove, the region reads "borttagen.mp4 is back at position 3 of 3.", and no save bar is shown.

    Remove again, press Move up on `s1710004.mp4`, then Undo: the order is `s1710004.mp4`, `s1710002.mp4`, `borttagen.mp4`, and the save bar says "1 clip moved" and nothing about a removal.

    Remove again, then Reset: the order is as read, there is no tail, and the save bar is gone.

    Every focused control shows a focus ring.
  - **Guarded:** with a removal pending, Back asks "Discard unsaved changes?" with Keep editing focused. Escape keeps the removal.
  - **Locked:** with a removal pending and the `PUT` held by `page.route`, press Enter on Save. Undo is `aria-disabled` and has no `disabled` attribute, and clicking it changes nothing. Abort the route, which keeps the draft.
  - **Save, Sommarlov:**
    - remove `borttagen.mp4` and save
    - the captured body has chapters `[{name: '', clips: [s1710002.mp4, s1710004.mp4]}]` and `clips: {}`, and its `metadata`, `look` and `ignore` equal the `GET …/reel` body
    - `diff` of `reel.yaml` against the saved copy shows exactly one line removed, `- borttagen.mp4  # MISSING`
    - the page shows "Saved", leaves Edit mode, shows no missing-clip warning, and offers Render
    - the list, on return, no longer shows "1 missing" or the note for Sommarlov, and offers its Render
  - **Render succeeds:** start `auto-reel worker <library> --device cpu` and press Render on Sommarlov. The page shows Rendered and then Up to date, and `<library>-output/2024/2024-09-01 - Sommarlov.mp4` exists. Stop the worker with SIGINT.
  - **Save, Två saknade:**
    - remove `Kväll/gone-b.mp4` and save
    - the captured body has no `Kväll/gone-b.mp4` key in `clips`, its `Kväll` chapter is `[Kväll/s1710003.mp4]`, and its root chapter equals the read's
    - `reel.yaml` has no `clips:` section, and its `gone-a.mp4   # moved to the NAS` line is byte-identical
    - the page now reads "gone-a.mp4 is missing from disk. Restore it, or remove it in Edit mode."
  - **Active job:** with no worker, `curl -X POST` a job for Två saknade. Its page shows "Waiting for a worker", Cancel, and the missing-clip reason, with no Render. Its row shows the queued job and no note. Cancel it: queued, so there is no dialog.
  - **Layout:** at 1280, 768 and 390 px, in light and dark (the theme control), take screenshots to `<scratchpad>/verify/missing-clips-screen/` of:
    - Sommarlov's page with the guard
    - Sommarlov in Edit mode with the removed list and the save bar
    - the list with the Sommarlov note

    At each size, check:
    - `document.documentElement.scrollWidth <= clientWidth`
    - the removed row shows its file name, "Missing" and Undo, and Remove's bounding box is inside the viewport
    - at 390 px, the Sommarlov card still shows "1 missing" and the note

    Look at every screenshot.
  - **Contrast and axe:**
    - the row note's text and the removed row's text measure at least 4.5:1 in both themes (C1's method: axe-core injected ad hoc, or computed ratios)
    - an axe-core run in Edit mode with a removed clip reports no serious or critical violations

## 6. Validation

- [ ] 6.1 Run the gates. Verify all pass:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `web-design-system`'s motion grep gate (its design, "Tokens and the support floor", the "motion grep gate" bullet), its three commands verbatim, over `web/src/edit` and `web/src/jobs`. This change adds no animation.
  - `grep -rn 'autoFocus' web/src/edit web/src/jobs` prints nothing
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, then `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, with the web-mount and OpenAPI drift tests green
  - `git diff --stat main -- auto_reel_ng tests scripts web/openapi.json web/src/api/schema.d.ts web/package.json web/package-lock.json` is empty
  - `openspec validate missing-clips-screen --strict` passes
  - no Playwright script, screenshot or `.playwright` directory is in the worktree
