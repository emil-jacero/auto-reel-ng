## 1. Pure edit

- [ ] 1.1 In `web/src/edit/draft.ts` add `moveMarkedToEnd(draft, listed, marked, to)` returning
  `{ draft, moved }` (the page-order group moved by the existing `groupOf` + `moveGroup` at gap = the target's length;
  `moved` empty and the same `draft` object when nothing changes). Verify with `node:test` in `groupMove.test.ts`: marks
  from two chapters land last in the target in page order; a marked clip already in the target joins the run; unmarked
  clips keep order and chapter; the group already last is a no-op (same draft); a stale mark or an unlisted target is
  ignored; a chapter that loses all its clips plays none; moving to the original chapter does not restore the old
  position.
- [ ] 1.2 Delete `pickMarked` and `markedAmong` from `marks.ts`, the draft's `moveClips` and `movedSet` users that only
  the dialog needed, if nothing else calls them (grep first), and their tests. Add words helpers in `marks.ts`
  (`movedWords(count, chapter)` = "3 clips moved to “Dag 2”.", "Nothing moved.", the three reasons) with `node:test`
  that pins the exact strings and the singular.

## 2. Control

- [ ] 2.1 In `EventEditor.tsx` add the **Move marked to…** group beside Rotate marked: the native `select` named
  "Chapter to move the marked clips to" (chapters as listed, deleted ones aside; first option "Choose a chapter"; reset
  when the chosen chapter is deleted) and **Move** (`aria-disabled`, reason in words via `aria-describedby`, press
  inert while a save or a move is pending); on press apply 1.1 through the existing pending state, `afterMove` on the
  marks, announce through the polite region, keep focus on Move and the choice. Not offered with one chapter. Style in
  `edit.css` (own line, wraps at 320, 44 px coarse targets, height stable, focus ring in forced colors). Verify with
  `npm test` (a render-free model test of the reason and option derivation), `tsc --noEmit` and `npm run build`.
- [ ] 2.2 Remove the Move clips button and its busy/aria wiring from `ChapterTools.tsx` and `ClipOrderList.tsx`
  (`ChapterToolsModel.moveClips`), the Move dialog, Pick all, Pick marked and its state from `ChapterDialogs.tsx` and
  `EventEditor.tsx` (`confirmMove`, dialog kind), and their CSS. Update `MARK_HINT`, the drag hint and
  `emptyChapterWords` ("move them here with Move marked to…") and the tests that pin them (`emptyChapter.test.ts`,
  `marks.test.ts`, `saveShortcut.test.ts` wording). Verify with `npm test`, `tsc`, and
  `grep -rn "Move clips\|Pick marked" web/src` returning only comments that name the old behaviour (none preferred).

## 3. Browser proof

- [ ] 3.1 Playwright, Chrome and Firefox, from the scratchpad against a dev library (routing only the write globs):
  mark two clips from different chapters, choose `Test`, Move: both last in `Test` in page order, the announcement, the
  save bar, Save writes `reel.yaml` as intercepted; a keyboard-only run (Space, Tab, arrow keys, Enter); the
  disabled reasons; the picker resets when its chapter is deleted; no "Move clips" text anywhere in the page.
- [ ] 3.2 Same harness: light and dark at 1280 and 390 (and 320 wrap), screenshots read by eye, no horizontal scroll,
  the group's line keeps its height when the first clip is marked, 44 px targets on a coarse pointer.

## 4. Documentation

- [ ] 4.1 Update `docs/high-level-design.md`: §4.10 and the D-13 mentions of "Move clips" (lines naming it in the v1
  scope, the phase table row D and the history paragraph) to say that the per-chapter Move clips was replaced by Move
  marked to… in the marks line (`move-marked-to`); state in §6 that GUI v2 includes it. No new D-number.
- [ ] 4.2 Run `openspec validate move-marked-to --strict` and the full `npm test`; the spec lines for `web-app` and
  `event-timeline` are the contract the tests above pin.
