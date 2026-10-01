## 1. Gate

- [x] 1.1 This change has no gate: it starts from main at `d0bc1d5` or later (`git merge-base --is-ancestor d0bc1d5 HEAD`). Re-check the names it builds on (design, "Context"), and stop and report to the supervisor on any mismatch:
  - `web/src/edit/draft.ts` exports `EditableChapter`, `Orders`, `Removals`, `editableChapters`, `ordersOf`, `detailMatchesDocument`, `buildWriteBody`, `adoptedNewCount`, `isDirty`, `moveClip`, `removeClip`, `restoreClip` and `movedSet`, and imports only with `import type`
  - `web/src/edit/EventEditor.tsx` has `reduce` with the `move`, `remove`, `restore` and `reset` actions, `afterEdit`, `summarize`, `chapterHeading`, `submit` and `announce`, and renders `ClipOrderList` keyed by `chapter.name`
  - `web/src/edit/ClipOrderList.tsx` has `withinChapter`, `RowBody` (with `was`), `RemovedRow`, `IgnoredRow`, `DndContext id={`chapter-${index}`}`, and `nameOf = clipNames(chapter, [...original, ...ignored])`
  - `web/src/ui/Dialog.tsx` has `isActionsRow`, and `web/src/ui/Icon.tsx`'s `IconName` has neither `plus` nor `arrow-right`
  - `ls openspec/changes/` shows no other change touching `web/src/edit/` (`clip-cuts-screen` is gated on this one)

  Re-base the three MODIFIED blocks in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`: for each requirement, take the landed text and carry this change's edits onto it, so no later wording is lost.

  Verify: `openspec validate chapter-management-screen --strict` passes, and for each MODIFIED requirement a `diff` of its main text against the change's text shows only this change's edits (as listed in proposal.md, "Modified Capabilities").

## 2. web/ — the model (pure)

- [x] 2.1 In `src/edit/draft.ts`, add the chapter model (design, "The draft model", "Where moved clips land", "What a save writes"): `ChapterKey`, `DraftChapter`, `Draft`, `Baseline`, `ChapterChanges`; `EditableChapter.key` (`r0`, `r1`…); `Orders` and `Removals` keyed by chapter key; `draftChapters`, `chapterChanges`, `isStructural`, `originOf`, `keptOriginal`, `addChapter`, `renameChapter`, `moveChapter`, `deleteChapter`, `restoreChapter`, `moveClips`; one `writtenFromView(baseline, draft)` used by `buildWriteBody(baseline, draft)`, `adoptedNewCount` and `isDirty`, holding every "written from the view" trigger in that one function (G2's extension point: design, "Files and the G2 seam"); no caller re-derives a trigger. Keep `detailMatchesDocument`, `movedSet`, `moveClip`, `removeClip` and `restoreClip` as they are, re-keyed. Keep the file free of runtime imports.

  Verify:
  - `npx tsc --noEmit` passes in the node:22 container once 3.1 has adapted the callers (until then only `EventEditor.tsx` and `ClipOrderList.tsx` may report errors)
  - a scratch script in `<scratchpad>/verify/chapter-management-screen/`, never committed, runs under `node --experimental-strip-types` in `docker.io/library/node:22`, imports `draft.ts`, and asserts over detail and `GET …/reel` JSON hand-copied from the agent's library (task 4.1's setup) for `2024-08-20 - Två kapitel - Tjörn` (`r0` = `''`, `r1` = `Kvällen`):
    - **untouched**: `buildWriteBody` deep-equals the read document, `isDirty` is false
    - **move between**: `moveClips` of `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4` to `r0` gives `r0` = `[s1710001.mp4, Kvällen/s1710002.mp4, Kvällen/s1710003.mp4]`, `r1` = `[Kvällen/s1710004.mp4]`; the body's chapters are `[{'' : those 3}, {Kvällen: [Kvällen/s1710004.mp4]}]`, `ignore` and `clips` as read; `adoptedNewCount` is 1; `movedSet` per chapter sums to 2
    - **and back**: moving both back to `r1` gives `r1` = `[Kvällen/s1710002.mp4, Kvällen/s1710003.mp4, Kvällen/s1710004.mp4]` and `isDirty` false; the same after moving them back one at a time, in either order
    - **rename**: `renameChapter(r1, 'Kväll')` gives chapters `[{'': [s1710001.mp4]}, {Kväll: [Kvällen/s1710002.mp4, Kvällen/s1710003.mp4, Kvällen/s1710004.mp4]}]`, `chapterChanges` `{renamed: 1}`, `adoptedNewCount` 1; renaming back to `Kvällen` gives `isDirty` false
    - **add**: `addChapter(a1, 'Morgon')` gives both read chapters from the view plus `{Morgon: []}` last; adding and then deleting `a1` gives `isDirty` false
    - **reorder**: `moveChapter(r1, -1)` gives `[Kvällen…, '']` with `reordered: true`; moving it back gives `isDirty` false
    - **delete**: after moving all three `Kvällen` clips to `r0`, `deleteChapter(r1)` gives chapters `[{'': [s1710001.mp4, Kvällen/s1710002.mp4, Kvällen/s1710003.mp4, Kvällen/s1710004.mp4]}]`; `restoreChapter(r1)` brings `{Kvällen: []}` back in place
    - **a moved clip keeps its properties**: with `clips: {Kvällen/s1710002.mp4: {trims: [{in: 0, out: 1.5}], exclude: false}}` in the read, moving that clip to `r0` keeps the entry in the body
    - **no chapters**: for `2024/Blandat` (read `chapters: []`), a title-only change gives `chapters: []`; `addChapter('Morgon')` gives `[{'': [s1710003.mp4]}, {Morgon: []}]`
    - **removal in a deleted chapter**: for `2024-09-01 - Sommarlov` plus an added `Morgon`, moving `s1710002.mp4` and `s1710004.mp4` to `Morgon`, removing `borttagen.mp4` and deleting `r0` gives chapters `[{Morgon: [s1710002.mp4, s1710004.mp4]}]` and no `clips` entry for `borttagen.mp4`
    - **moved out, counted**: after the move between above, `movedSet(keptOriginal(original r1, order r1), order r1, null)` is empty and does not throw (on `d0bc1d5`, `movedSet` over the unfiltered original throws a `TypeError`: design, "Context"); the same for `r1` emptied by moving all three out
    - **chapter moves skip a deleted one**: with `Morgon` added, `r1` emptied and deleted, `moveChapter(a1, -1)` puts `a1` before `r0` in one press, and `r1` keeps its index
    - **repeat submit**: calling `moveClips` twice with the same arguments gives the same draft as once
    - every body above passes a hand-written check of the engine's rules: no duplicate name, no identity twice, every `clips` key listed, no ignored identity listed
- [x] 2.2 Add `src/edit/chapterNames.ts` (design, "Name checks and D-12 notes"): `checkName`, `diskFolders`, `laterClipNotes`, `nameDialogNote`, and the refusal and note copy as exported constants. Type-only imports.

  Verify: the scratch script of 2.1 also asserts, on `Två kapitel`:
  - `checkName` refuses `'kvällen'` (`taken`, clash `Kvällen`), `'   '` (`empty`), `'main'` (`reserved`, also after `r0` is deleted), and, after `deleteChapter(r1)`, `'KVÄLLEN'` (`taken-deleted`); it accepts `' Kväll på stranden '` as `'Kväll på stranden'`, and `'kvällen'` for `r1` itself
  - `diskFolders` is `{'', 'Kvällen'}` (and leaves out a folder that only a missing clip names)
  - renaming `r1` to `Kväll` gives `r1` the note "No chapter will be named after the folder “Kvällen”, so clips added to it later will join Main."; then adding `Kvällen` gives the new chapter "Clips added to the folder “Kvällen” later will join this chapter. Clips from it that other chapters list stay where they are."
  - renaming `r1` to `kvällen` gives the first note too
  - with `Kvällen/s1710004.mp4` ignored under `r1`, renaming or deleting `r1` adds "Its 1 ignored clip will be listed under Main."

## 3. web/ — the editor

- [x] 3.1 In `src/edit/EventEditor.tsx`, move the editor onto the model (design, "The draft model", "Keyboard model and focus", "Counts, badges, the save bar and the hint"):
  - `Ready` holds `baseline` and `draft`; actions `chapter-add`, `chapter-rename`, `chapter-move`, `chapter-delete`, `chapter-restore` and `clips-move` go through `afterEdit` and are refused while a save is in flight; `reset` restores the baseline's chapters; added keys come from a counter in the state
  - the delete guard (plays a clip; the event's own chapter with an ignored clip; the only chapter left) lives in the reducer's caller and answers with the refusal copy; `restore` into a deleted chapter is refused
  - the moved count (`movedCount`) and `ClipOrderList`'s `kept` both use `keptOriginal` (design, "Counts, badges")
  - `summarize` gains the chapter parts before the moves; the hint's sentences change as designed; headings come from the draft
  - focus: a `focusAfter` ref (`{ key, target }`) and the layout + passive effect pair of the design's table, except Add chapter's heading focus, which is a passive effect so `Dialog`'s return to its opener does not undo it (design, "Keyboard model and focus"); when `leaveQuestion` opens, an open chapter dialog closes first
  - every announcement of the design's table goes through `announce`

  Verify: `npx tsc --noEmit` and `npm run build` pass; `git diff --stat web/src/edit/SaveBar.tsx web/src/edit/unsaved.ts web/src/edit/MetadataForm.tsx` is empty; `grep -rn ' disabled=' web/src/edit` prints nothing.
- [x] 3.2 Add `src/edit/ChapterTools.tsx` (tools row, `DeletedChapter`, `AddChapter`) and `src/edit/chapters.css`, adapt `src/edit/ClipOrderList.tsx` (keyed and `DndContext`-identified by `chapterKey`; the tools slot between header and column strip; the empty state; the "from …" badge; `nameOf` over original, order, ignored and removed), add `plus` and `arrow-right` to `src/ui/Icon.tsx`, and give the read view its empty chapter (`ChapterPanel` in `src/events/EventDetail.tsx`, the `.chapter-empty` rule in `src/events/detail.css`) (design, "The chapter tools row", "The read view's empty chapter", "Performance").

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff web/src/edit/edit.css` changes no `grid-template-columns`, `grid-template-areas` or `@container` line, and `chapters.css` declares only `@layer screens`
  - the `EventDetail.tsx` diff is 12 lines or fewer (an early return; design, "The read view's empty chapter"), and touches only `ChapterPanel`
  - the tools row is not inside `.panel-header` (`grep -n "chapter-tools" web/src/edit/ClipOrderList.tsx` shows it after `</header>`)
- [x] 3.3 Add `src/edit/ChapterDialogs.tsx` (`NameDialog`, `MoveClipsDialog`) and the `.dialog-fields` split in `src/ui/Dialog.tsx` (design, "The name dialog", "The Move clips dialog", "Dialog descriptions"). Field markup reuses `.field`, `.field-label`, `.field-input`, `.field-error`, `.field-hint`; the choice rows and the dialog width go in `chapters.css`.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass; `grep -rn 'autoFocus' web/src/edit web/src/ui` prints nothing
  - `git diff web/src/ui/Dialog.tsx` changes only the child split (no new prop)
  - every label shown comes from a label map or the copy constants, never a status slug (`grep -n "'new'\|'active'" web/src/edit/ChapterDialogs.tsx` shows comparisons only)

## 4. Verification against the dev library

- [x] 4.1 Set up the agent's own environment per the dev-env runbook §9 with `SLUG=chapter-management-screen`, `N=26`: database `arel_chapter_management_screen`, library `../dev-chapter-management-screen`, `auto-reel serve <library> --port 8126` over a fresh `npm run build`, no worker. Never port 8080 or 5173, `../auto-reel-dev`, `auto-reel-media/`, the default database, or another agent's database, library or port. In that library copy only, add the fixtures of design, "Verification fixtures" (`Stor dag` by the `archive/2026-09-30-event-edit-screen/design.md` recipe plus the three `Kväll/` files, no `reel.yaml`), and copy every `reel.yaml` before touching it. `make_dev_library.py` dumps `Två kapitel` and `Grillning` with ruamel's default indentation, and the engine's writer (`reel/writer.py` 28-35) re-indents every list on its first real write. So first normalise each `reel.yaml` a check will `diff` (these two in particular): load it and dump it again with `YAML()` and `indent(mapping=2, sequence=4, offset=2)`. Then take its copy.

  Drive `http://127.0.0.1:8126/` with a Playwright script in `<scratchpad>/verify/chapter-management-screen/` (container `mcr.microsoft.com/playwright/python:v1.49.0-noble`, `--network host`), locators scoped to `main:not([hidden])`, every `PUT …/reel` body captured, file checks host-side with `cat` and `diff`. **Keyboard only** (Tab, Shift+Tab, Enter, Space, arrows, Escape; no clicks) for every item below except where it says pointer, asserting `document.activeElement` and the editor's `role="status"` text after each step:
  - every scenario of the four ADDED requirements, on the named events, in order; each save's body matches design, "What a save writes", and each `reel.yaml` `diff` shows only the lines the scenario names. Specifically:
    - **Rename + save** (`Kvällen` → `Kväll`): `reel.yaml` lists `Kväll` with the three `Kvällen/…` clips, no `Kvällen`, `ignore` unchanged; the page then shows `Kväll` with those three, none "New", and names them by path
    - **Move two + save**: `reel.yaml`'s default chapter lists `s1710001.mp4`, `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4`, each keeping any end-of-line comment it had in the copy, and `Kvällen` lists `Kvällen/s1710004.mp4` alone; the save bar said "adds 1 new clip to reel.yaml"
    - **Delete + save**: one chapter, headed `Clips` after the save
    - **Add + save on Grillning**: the read view shows `Kvällen vid grillen` with "0 clips", the empty-chapter sentence and no `<table>`
    - **Blandat**: add `Morgon` + save gives `[{'': [s1710003.mp4]}, {Morgon: []}]`, and `s1710003.mp4` is no longer "New"
  - the MODIFIED scenarios this change adds ("Moving clips writes the two chapters", "A moved clip keeps its cut", "A renamed chapter keeps its new clip", "A chapter added to a document without chapters", "A clip moved in from another folder is named by its path", "A renamed chapter names its clips by their paths"), and the unchanged ones of "The event page reorders clips within a chapter" still pass (drag by pointer included)
  - **dialog semantics**: the name dialog's and the Move clips dialog's `aria-describedby` text is their one-sentence explanation only (no clip names), and "Overwrite the other change?" and "Discard unsaved changes?" are described exactly as before
  - **focus after Add**: after Add chapter → `Morgon` → Enter, `document.activeElement` is `Morgon`'s `h2`, checked after two animation frames (not Add chapter)
  - **Enter in Move clips**: Space on the first box, Enter: exactly one move is announced and the clip is in the target once (no second submit)
  - **locked**: with a rename pending and the `PUT` held by `page.route`, Enter on Save; Add chapter and each of `Kvällen`'s controls are `aria-disabled` with no `disabled` attribute, a press changes nothing, and focus stays on Save; abort the route: the rename is kept
  - **conflict**: on `Två kapitel`, rename `Kvällen`, change the title in its `reel.yaml` host-side, then Save: the conflict alert shows; Overwrite with mine, confirmed: the captured body carries the rename and every chapter from the view, and the hand-edited title is replaced
  - **guard**: with only a chapter added, Back asks "Discard unsaved changes?"; Keep editing keeps it; with the Move clips dialog open, Back closes it and asks
  - **scale**: on `2024-09-15 - Stor dag`, open Move clips on the 400-clip chapter (focus on its first box), press Space, then Enter: the first clip is last in `Kväll`. The time from Enter to the dialog's close, and from a row's Move up press to its announcement, are each under 200 ms. Typing 10 characters in Title takes under 50 ms per keystroke, as on Grillning (lists do not re-render on typing; design, "Performance")
  - restore every touched `reel.yaml` from its copy afterwards and `diff` to confirm
- [x] 4.2 Layout, touch and accessibility, on `Två kapitel` in Edit mode with `Kvällen` renamed to `Kväll`, `Morgon` added and the Move clips dialog open in turn, and on Grillning's read view with an empty chapter saved:
  - **sizes**: 320×700, 390×844, 768×1024 and 1280×900, in the light and the dark theme (the theme control); screenshots of each state to `<scratchpad>/verify/chapter-management-screen/`; look at every one. At each size `document.documentElement.scrollWidth <= clientWidth`; each chapter's header is one line (its height equals `--panel-head-h` computed); the tools row's buttons are inside the panel's box; at 1280 the clip columns start within 1 px of where the read view's table started them
  - **coarse pointer**: a context with `has_touch` and `is_mobile` at 320×700 and 390×844: for Add chapter, Undo, and each of `Kväll`'s Rename, Move clips, Move up, Move down and Delete, `ui-a11y-polish`'s touch probe (`elementFromPoint` at a 7 × 7 grid across the designed area: the border box grown to 44 px each way, and for the Move up / Move down pair anchored away from the other) returns that control or a descendant, each control scrolled to the window's centre first; in the Move clips dialog each `.choice` row is at least 44 px tall and rows do not overlap
  - **fine pointer**: at 1280 and 390 with a mouse, the existing controls (Edit, Save, the clip rows' handle and moves) keep their size and place (bounding boxes equal to a run on main's build, taken first)
  - **contrast**: the chapter notes, the refusal, the "from Kvällen" badge and the "Deleted when you save" badge measure at least 4.5:1 in both themes
  - **axe-core**, injected ad hoc: no serious or critical violation in Edit mode with each dialog open and closed, and on the read view with the empty chapter, in both themes
  - **busy focus**: as in 4.1's locked check, `document.activeElement` stays on Save through the held request
  - no Playwright script, screenshot or `.playwright` directory is in the worktree

## 5. Docs and validation

- [x] 5.1 Update `web/README.md` (the Edit-mode paragraph: the chapter tools, Move clips, Delete only when empty, the D-12 notes; the `edit/` file tree with `chapterNames.ts`, `ChapterTools.tsx`, `ChapterDialogs.tsx`, `chapters.css`) and `docs/high-level-design.md` (D-13 as in design, "HLD"; §4.10's v1 bullet gains "chapter edits and Move clips (**D-13**)", its v3 line and slice row D change). Then run the gates:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `web-design-system`'s motion grep gate, its three commands verbatim, over `web/src/edit` (this change adds no animation)
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full `.venv/bin/python -m pytest` (the web-mount and OpenAPI drift tests green)
  - `git diff --stat main -- auto_reel_ng tests scripts web/openapi.json web/src/api web/package.json web/package-lock.json` is empty
  - `openspec validate chapter-management-screen --strict` passes

  Verify: all of the above pass; `grep -n "D-13" docs/high-level-design.md` hits §7 and §4.10; `grep -n "Move clips" web/README.md` hits.
