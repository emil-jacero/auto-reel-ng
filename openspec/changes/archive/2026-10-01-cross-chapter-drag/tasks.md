## 1. Gate

- [x] 1.1 This change has no gate. It starts from main at `6656ebc` or later (`git merge-base --is-ancestor 6656ebc HEAD`). Re-check the names it builds on (design, "Context"), and stop and report to the supervisor on any mismatch:
  - `web/src/edit/ClipOrderList.tsx` has `withinChapter`, `useReducedMotion`, `dropped`, `NO_CLIPS`, `NO_CLIPS_PLAYED`, `ClipRow` with `useSortable({ id: clip.identity, disabled: locked, transition })`, and one `DndContext` with `id={`chapter-${chapterKey}`}`
  - `web/src/edit/EventEditor.tsx` has `reduce` with the `move` and `clips-move` actions, `isListed`, `afterEdit`, `idle`, `listsLocked`, `onDisk`, `nameNow`, `headingIn`, and the hint sentence "Clips stay in their chapter"
  - `web/src/edit/draft.ts` exports `moveClip`, `moveClips`, `restoreClip`, `keptOriginal`, `movedSet`, `writtenFromView` and `addChapter`, and imports only with `import type`
  - `web/src/edit/ChapterTools.tsx`'s `DeletedChapter` renders a `section.edit-chapter[data-deleted]`
  - `web/package-lock.json` resolves `@dnd-kit/core` 6.3.1 and `@dnd-kit/sortable` 10.0.0, and `DragOverlay` and `useDroppable` are exported by the installed core
  - `ls openspec/changes/` shows no other change that touches `web/src/edit/`

  Re-base the four MODIFIED blocks in `specs/web-app/spec.md` on the current `openspec/specs/web-app/spec.md`: for each requirement, take the landed text and carry this change's edits onto it, so no later wording is lost.

  Verify: `openspec validate cross-chapter-drag --strict` passes. For each MODIFIED requirement, a `diff` of its main text against the change's text shows only this change's edits (proposal, "Modified Capabilities"):
  - **reorder**: the sentences on Move up / Move down and on how a clip changes chapter; the "A clip cannot leave its chapter" scenario, now about Move up; and the added "A missing clip cannot leave its chapter"
  - **Move clips**: its closing paragraph
  - **chapters**: the empty-chapter sentence and the first scenario's THEN
  - **focus in view**: the drop-into-another-chapter exception in its first paragraph, and the added scenario "A tall row dropped into another chapter"

## 2. web/ — the model (pure)

- [x] 2.1 In `src/edit/draft.ts`, add `moveClipTo` (design, "A drop is one edit"), and add the new `src/edit/dragSlots.ts` with `Slot`, `DragModel`, `dragModel`, `slotsOf`, `stepSlot`, `overIdOf`, `slotOf`, `pointerTarget`, `CHAPTER_DROP` and `DELETED_DROP` (design, "Droppables and their ids", "Collision detection", "Keyboard model and the coordinate getter"). Both files take type-only imports, and `draft.ts` changes in nothing else.

  Verify:
  - `npx tsc --noEmit` passes in the node:22 container. Until 3.3 lands, only callers may report errors.
  - a scratch script in `<scratchpad>/verify/cross-chapter-drag/`, never committed, runs under `node --experimental-strip-types` in `docker.io/library/node:22`. It imports both files and asserts over detail and `GET …/reel` JSON hand-copied from the agent's library (task 4.1's setup), using `r0` = `''` and `r1` = `Kvällen` for `2024-08-20 - Två kapitel - Tjörn`.
  - `moveClipTo` cases:
    - **into Main at 0**: `moveClipTo(r1 → r0, Kvällen/s1710003.mp4, 0)` gives `r0` = `[Kvällen/s1710003.mp4, s1710001.mp4]` and `r1` = `[Kvällen/s1710002.mp4, Kvällen/s1710004.mp4]`
      - the body's chapters are `[{'': those 2}, {Kvällen: those 2}]`, with `ignore` and `clips` as read
      - `adoptedNewCount` is 1, and `movedSet(keptOriginal(…), …, 'Kvällen/s1710003.mp4')` per chapter sums to 1
    - **and back**: `moveClipTo(r0 → r1, Kvällen/s1710003.mp4, 1)` gives `isDirty` false
    - **clamped**: `at` 99 puts the clip last, and `at` -1 puts it first
    - **idempotent**: a second identical call returns the same `Draft` object (`===`). So does a call with `from === to`, with an unknown chapter, and with a clip `from` does not play.
    - **an empty chapter** on `2024-06-27 - Grillning med grannar`: after `addChapter(a1, 'Kvällen vid grillen')`, `moveClipTo(r0 → a1, s1710004.mp4, 0)` gives chapters `[{'': [s1710001.mp4, s1710002.mp4, s1710003.mp4]}, {'Kvällen vid grillen': [s1710004.mp4]}]`
    - **a cut kept**: after `addCut(Kvällen/s1710002.mp4, {in: 0, out: 1.5})` and `moveClipTo` into `r0`, the body lists the clip under `''` with its trim
  - `dragSlots.ts` cases on `Två kapitel` (listed `[r0, r1]`):
    - `slotsOf(s1710001.mp4)` is `r0:0, r1:0, r1:1, r1:2, r1:3`
    - `slotsOf(Kvällen/s1710002.mp4)` is `r0:0, r0:1, r1:0, r1:1, r1:2`
    - `stepSlot` from `r0:0` down gives `r1:0`; from `r1:0` up gives `r0:0` for `s1710001.mp4`, and `r0:1` for `Kvällen/s1710002.mp4`
    - `stepSlot` returns null past either end
    - `overIdOf`:
      - `s1710001.mp4` at `r1:3` gives `/chapter/r1`, and at `r1:1` gives `Kvällen/s1710003.mp4`
      - own slots give the row at that index
      - `slotOf` round-trips every slot of each sequence
      - `slotOf('/deleted/r1')` and `slotOf(null)` are null
    - **missing**: on `2024-09-01 - Sommarlov` plus an added `a1`, `slotsOf(borttagen.mp4, staysHome)` is `r0:0, r0:1, r0:2`, and `stepSlot(r0:2, 1)` is null
    - **a deleted chapter passed over**: on `Två kapitel`, move all three `Kvällen` clips to `r0` (`moveClips`), `deleteChapter(r1)` and `addChapter(a1, 'Morgon')`. Listed is then `[r0, a1]`, and `stepSlot(Kvällen/s1710004.mp4 at r0:3, 1)` is `a1:0`.
    - `pointerTarget` for `s1710001.mp4` (own chapter `r0`), on hand-made spans: chapters `r0` 100–300 and `r1` 330–600, a deleted span 610–650, and 45 px rows starting 45 px below each chapter's top (`r0`: one row; `r1`: three rows, 375–420, 420–465 and 465–510):
      - in `r0`, the nearest own row
      - in `r1`, y = 430 (upper half of its second row) gives `Kvällen/s1710003.mp4`, and y = 500 (lower half of its last row) gives `/chapter/r1`
      - in the gap between the panels, y = 310 gives `r0`'s nearest own row and y = 322 gives `Kvällen/s1710002.mp4` (nearest chapter `r1`, before its first row)
      - y = 630 gives null
      - with `staysHome`, y = 322 and y = 500 give an own row, and y = 630 still gives null (the deleted placeholder is checked first, design "Collision detection" step 1)
    - both prefixes start with `/`, and no identity in the library's detail JSON does

## 3. web/ — the drag

- [x] 3.1 Add `src/edit/ChapterDrag.tsx` and `src/edit/drag.css` (design, "One `DndContext` …", "Collision detection", "Keyboard model and the coordinate getter", "What cannot cross, and the locks", "The visuals", "Announcements and instructions", "Focus and scroll after a drop", "Files"). It holds:
  - `ChapterDrag` with `id="edit-chapters"`
  - the sensors: `PointerSensor` with distance 6, and `KeyboardSensor` with the slot getter and `scrollBehavior` `auto` under reduced motion, `smooth` otherwise
  - the collision adapter over `pointerTarget`, with the slot in a ref that `onDragStart` empties
  - the modifiers `vertical` and `homeClamp`
  - the announcements and the instructions, per the design's table
  - `onDragStart`, `onDragEnd` (within a chapter it calls `onReorder`; into another chapter it calls `onDropInto`, only while not locked) and `onDragCancel`
  - `DragOverlay` portalled to `document.body`, with `className="clip-drag-overlay"`, `style={{ height: 'auto' }}` (the wrapper keeps the row's width), `zIndex={25}` and `dropAnimation={null}`
  - `DragPreview`: `aria-hidden`, holding the grip, the name and the target badge, reading `over` from `useDndContext`; `inline-size: fit-content` and `max-inline-size: min(24rem, calc(100% - 3rem))`
  - the layout and passive effects for focus and scroll after a drop
  - `useReducedMotion`, moved here from `ClipOrderList.tsx` and exported

  The only React state is the lifted clip, `{ identity, name }`.

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass in the node:22 container
  - `grep -rn "<DndContext" web/src` hits `ChapterDrag.tsx` only
  - `drag.css` declares only `@layer screens`, and every `transition` in it sits in a `prefers-reduced-motion: no-preference` block and reads `--dur-*`
  - `grep -rn ' disabled=' web/src/edit` prints nothing
  - `git diff --stat main -- web/package.json web/package-lock.json` is empty
- [x] 3.2 Adapt `src/edit/ClipOrderList.tsx`, `src/edit/ChapterTools.tsx` and `src/edit/edit.css` (design, "Droppables and their ids", "The visuals", "The hint and the words"):
  - `ClipOrderList.tsx`:
    - drop the per-chapter `DndContext`, sensors, `withinChapter`, `INSTRUCTIONS`, announcements, `onDragEnd` and `dropped`
    - `SortableContext` takes `id={chapterKey}`
    - add `ChapterDrop` (its `useDroppable` for `/chapter/<key>` attached to the section in a `useEffect`; the area for a chapter that plays no clip; the end line, rendered before the `<ol>`)
    - `ClipRow` sets `data-drop-before`
    - `NO_CLIPS` and `NO_CLIPS_PLAYED` take the new words
  - `ChapterTools.tsx`: `DeletedChapter` registers `/deleted/<key>` with `ref={setNodeRef}`
  - `edit.css`: the placeholder look for `.clip-item[data-dragging]`, and `.edit-chapter { position: relative }`

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff web/src/edit/edit.css` changes no `grid-template-columns`, `grid-template-areas` or `@container` line
  - `grep -n "useDroppable" web/src/edit/ClipOrderList.tsx` hits inside `ChapterDrop` only
  - the diffs of `RowBody`, `MoveButtons`, `RemovedRow` and `IgnoredRow` are empty
- [x] 3.3 In `src/edit/EventEditor.tsx` (design, "A drop is one edit", "Files", "The hint and the words"):
  - add the `clip-drop` action: `isListed` both, `from !== to`, through `afterEdit`, `lastMoved`; `state` itself when `moveClipTo` returns the same draft
  - add `onDropInto`, which dispatches only when `idle()` holds and `onDisk` is true for the clip, and returns whether it did
  - wrap the chapter sections' `map` in `ChapterDrag`, with `orders`, the listed keys, `staysHome`, `nameOf` (over `nameNow`), `headingOf` (`headingIn`), `locked={listsLocked}`, `onReorder={onMove}`, `onDropInto` and `rootRef={editorRef}`
  - change the hint's sentences

  Verify:
  - `npx tsc --noEmit` and `npm run build` pass
  - `git diff main -- web/src/edit/SaveBar.tsx web/src/edit/unsaved.ts web/src/edit/MetadataForm.tsx web/src/edit/ChapterDialogs.tsx web/src/edit/chapterNames.ts web/src/cuts` is empty
  - `git diff main -- web/src/edit/draft.ts` adds `moveClipTo` and nothing else
  - in `EventEditor.tsx`, the `clips-move` case and `confirmMove` are unchanged

## 4. Verification against the dev library

- [x] 4.1 Set up the agent's own environment per the dev-env runbook §9 with `SLUG=cross-chapter-drag`, `N=28`: database `arel_cross_chapter_drag`, library `../dev-cross-chapter-drag`, and `auto-reel serve <library> --port 8128` over a fresh `npm run build`, with no worker.
  - Never use port 8080 or 5173, `../auto-reel-dev`, `auto-reel-media/`, the default database, or another agent's database, library or port. Never stop or remove a `test-pg` container.
  - In that library copy only, add `Stor dag` (design, "Verification fixtures").
  - Normalise and copy every `reel.yaml` a check will `diff`. Mount shared directories with `:z`.

  Drive `http://127.0.0.1:8128/` with a Playwright script in `<scratchpad>/verify/cross-chapter-drag/` (container `mcr.microsoft.com/playwright/python:v1.49.0-noble`, `--network host`).
  - Scope locators to `main:not([hidden])`, capture every `PUT …/reel` body, and check files host-side with `cat` and `diff`.
  - Record every text of dnd-kit's live region (`[id^="DndLiveRegion"]`, with a `MutationObserver` installed before the lift) and of the editor's `role="status"`.
  - **Pointer drags** use `page.mouse`: down on the handle's centre, 10 px down (past the 6 px activation), then 10 or more steps to the target, 100 ms of hold, then up.
  - **Keyboard drags** use only Tab, Space, Enter, the arrows and Escape. After each, assert `document.activeElement` two animation frames after the drop.

  Check:
  - **Every scenario of the ADDED requirement and of the four MODIFIED ones**, on the named events, in order. Each save's body matches design, "A drop is one edit", and each `reel.yaml` `diff` against its normalised copy shows only the lines the scenario names:
    - **Saving a dragged clip** (`Två kapitel`): the default chapter becomes `- Kvällen/s1710003.mp4` then `- s1710001.mp4`. In `Kvällen`, `- Kvällen/s1710003.mp4` goes and `- Kvällen/s1710004.mp4` is added. Nothing else changes, and `ignore` is untouched.
    - **Dragging a clip into an empty chapter** (`Grillning`): `Kvällen vid grillen` is added with `- s1710004.mp4`, and that line leaves the default chapter
    - **Crossing into the next chapter from the keyboard**, then Save: `Kvällen` lists `Kvällen/s1710002.mp4`, `s1710001.mp4`, `Kvällen/s1710003.mp4` and `Kvällen/s1710004.mp4`, and the default chapter lists none. The page then shows `Main` holding only the ignored `s1710004.mp4`.
    - **Dragging a clip back leaves nothing to save**: Save is gone, and no `PUT` is sent
  - **What each drag shows** while held over another chapter:
    - exactly one `.clip-item[data-drop-before]` (or `.chapter-drop-end`, or `.chapter-drop[data-over]`) in the target chapter, and none elsewhere
    - the copy's badge text matches the announcement
    - the source row has `data-dragging` and keeps its box
  - **Focus**: after each drop into another chapter, by pointer and by keyboard, `document.activeElement` is the `.drag-handle` of the moved row in `[data-chapter-key="<target>"]`. The handle and the row's first line (handle, `.clip-name`, Cuts control) lie inside the window, below the panel's sticky heading and above the save bar's top (bounding boxes). Also with the dragged clip's Cuts panel open, at 1280 × 900 and 390 × 844, and at 390 × 600 with four cuts added (the row is then taller than the room left), by pointer and by keyboard.
  - **Within a chapter, unchanged**: the scenarios "Dragging a clip to the front", "Reordering from the keyboard" and "Escape cancels a keyboard move" pass with the same words as on main, and the first keyboard drop on `Grillning` keeps its row in view at 1280 × 900 and 390 × 844
  - **Locked**: with a dragged clip pending and the `PUT` held by `page.route`, press Enter on Save
    - focus stays on Save, and every handle is `aria-disabled` with no `disabled` attribute
    - then focus the handle of `s1710001.mp4` by script: Space adds no live-region text, a pointer drag from it moves nothing, and no order changes
    - abort the route: the drag is kept
  - **Guard and conflict**:
    - after a drag only, Back asks "Discard unsaved changes?" and Keep editing keeps it
    - after a drag on `Två kapitel`, change the title in its `reel.yaml` host-side and Save. The conflict alert shows. Overwrite with mine, confirmed, sends a body carrying the drag.
  - **Cuts**: the scenario "A dragged clip keeps its cuts and what was typed" passes by pointer and, after Reset, by keyboard (lift, Up, Space)
  - **Move clips unchanged**: every scenario of "Edit mode moves clips to another chapter" still passes with the same words and focus as on main
  - restore every touched `reel.yaml` from its copy afterwards, and `diff` to confirm
- [x] 4.2 Layout, touch, motion and accessibility on `2024-08-20 - Två kapitel - Tjörn`, and on `2024-06-27 - Grillning med grannar` with `Kvällen vid grillen` added:
  - **Sizes**: 320×700, 390×844, 768×1024 and 1280×900, each in the light and the dark theme (the theme control). At each of the 8:
    - **pointer drag**: drag `s1710001.mp4` over `Kvällen`, holding it between `s1710002.mp4` and `s1710003.mp4`. Take a screenshot.
      - no layout shift: every `.clip-item` and `.edit-chapter` keeps its document-relative box (`rect.top + scrollY`, `left`, `width`, `height`) from before the press within 0.5 px, the dragged row included
      - the line is visible: the copy's right edge is at least 16 px left of the row's right edge, and `getComputedStyle(row, '::before').backgroundColor` is the accent
      - `document.documentElement.scrollWidth <= clientWidth`
    - release, and check the order and focus as in 4.1. Take a screenshot, then Reset.
    - **keyboard drag**: lift `Kvällen/s1710002.mp4`, press Up and drop. Check the order, the words and focus, then Reset.
    - on `Grillning`, check the empty chapter's area (screenshot) and, during a drag over it, the `[data-over]` area (screenshot). The area's box does not change.

    Save every screenshot to `<scratchpad>/verify/cross-chapter-drag/` and look at each one.
  - **Coarse pointer**: a context with `has_touch` and `is_mobile` at 320×700 and 390×844
    - a touch drag over CDP `Input.dispatchTouchEvent` (start on the handle of `Kvällen/s1710002.mp4`, 20 moves to above `s1710001.mp4`, end) puts it first in `Main`
    - a touch that starts on its `.clip-name` and moves 200 px up changes `scrollY` and no order
    - `ui-a11y-polish`'s touch probe on the handle still returns the handle
  - **Fine pointer**: at 1280 and 390 with a mouse, the bounding boxes of Edit, Save, the handles, the move buttons, the Cuts controls and the chapter tools equal a run on main's build taken first. The one exception is a chapter that plays no clip, where the area replaces the words.
  - **Reduced motion** (`reduced_motion='reduce'`):
    - after a keyboard drop within a chapter, no `.clip-item` has a non-zero computed `transition-duration`
    - after a drop into another chapter, `.clip-drag-overlay` is gone one animation frame after the release
    - the area's colours change with `transition-duration` `0s`
  - **Contrast**, in both themes:
    - at least 4.5:1: the area's words, idle and `[data-over]`, against their backgrounds; the copy's name and badge text; the placeholder's name and muted facts on `--accent-soft`
    - at least 3:1: the area's dashed border against `--surface`, and the line's accent against `--surface`
  - **axe-core**, injected ad hoc from cdnjs: no serious or critical violation in either theme, in each of these states:
    - Edit mode idle with the area shown (`Grillning` plus the added chapter)
    - a keyboard drag lifted and over `Kvällen` (`Två kapitel`)
    - after a drop
  - no Playwright script, screenshot or `.playwright` directory is in the worktree
- [x] 4.3 Scale and render budget on `2024/2024-09-15 - Stor dag` at 1280 × 900 (design, "Render budget"). Measure the production build, with the commit hook installed by `page.add_init_script` before the first navigation (the design's method; never committed). Record every number in the report.
  - **lift**: Space on the handles of `c0200.mp4` and `Kväll/k002.mp4`. From the key to "Picked up …" in the live region takes under 200 ms each.
  - **keyboard steps**:
    - 10 Down steps from `c0200.mp4`: median under 100 ms from the key to the new live-region text
    - from `c0400.mp4`, Down 3 times into `Kväll` and Up 3 times back: median under 100 ms
    - per step: at most 2 `RowBody` within the 400-clip chapter and 0 for a step into or within `Kväll`, and 0 `ClipOrderList` and 0 `EventEditor` commits (`ClipRow` count recorded)
  - **pointer**: drag `Kväll/k001.mp4` up into the 400-clip chapter
    - over 10 moves that keep one target: at most 1 `ClipRow`, and 0 `RowBody`, `ClipOrderList` and `EventEditor` per commit
    - at each new target: 0 `RowBody`, `ClipOrderList` and `EventEditor`
    - no `longtask` entry of 100 ms or more after the lift (`PerformanceObserver`)
  - **auto-scroll**: holding that drag at the window's top edge (just below the app header) scrolls the page up at least 2 000 px within 3 s, and reaches `c0001.mp4` within 30 s. Released over its upper half, `k001.mp4` is position 1 of 401, and the announcement says so.
  - **drop**: from the release to the drop's announcement takes under 200 ms, with exactly 2 `ClipOrderList` commits, for the drop above, and for a keyboard drop of `c0400.mp4` into `Kväll`
  - **unchanged budgets**:
    - typing 10 characters in Title: under 50 ms per keystroke, and 0 `ClipOrderList` commits
    - Move up on the 200th clip: under 200 ms to its announcement
    - Move clips of the first clip to `Kväll`: under 200 ms from Enter to the dialog's close
  - when a budget fails, stop and report the numbers. Do not add virtualisation, a behaviour-changing `memo`, or a dependency.

## 5. Docs and validation

- [x] 5.1 Update `web/README.md` and `docs/high-level-design.md`:
  - `web/README.md`: in the Edit-mode paragraph, dragging into another chapter by pointer and keyboard, the empty chapter's area, missing clips staying, and Move clips kept; "A drag or a Move up / Move down never takes a clip into another chapter" becomes the Move up / Move down rule only. In the `edit/` tree, add `ChapterDrag.tsx`, `dragSlots.ts` and `drag.css`, and update `ClipOrderList.tsx`'s line.
  - `docs/high-level-design.md`: D-13's "Dragging across chapters stays v3." replaced by the new sentence, §4.10's v1 bullet and v3 line, and slice row D, as in design, "HLD". Re-read §4.10 on main first: if `media-endpoints` has landed, the v3 line already reads "nothing planned for the GUI"; keep it, and edit only the v1 bullet, slice row D and D-13

  Then run the gates:
  - `npx tsc --noEmit` and `npm run build` in the node:22 container
  - `web-design-system`'s motion grep gate, its three commands verbatim, over `web/src/edit`
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full `.venv/bin/python -m pytest` (with the web-mount and OpenAPI drift tests green)
  - `git diff --stat main -- auto_reel_ng tests scripts web/openapi.json web/src/api web/package.json web/package-lock.json` is empty
  - `openspec validate cross-chapter-drag --strict` passes

  Verify that all of the above pass, that each of these hits:
  - `grep -n "cross-chapter-drag" docs/high-level-design.md` (D-13 and §4.10)
  - `grep -n "ChapterDrag" web/README.md`

  and that §4.10's v3 line no longer names dragging across chapters, and `grep -n "Dragging across chapters stays v3" docs/high-level-design.md` prints nothing.
