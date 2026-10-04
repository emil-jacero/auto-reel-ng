## Why

User feedback on Edit mode (2026-10-04, with a screenshot of the chapters): "It also look like we can remove the old
> Move clips...". Every chapter header carries a **Move clips…** button that opens a dialog to pick clips (Pick all,
Pick marked) and one target chapter. Since `clip-group-select-drag` (#104) the operator marks clips with the box on
each thumbnail and drags the group, so the per-chapter dialog is clutter on every chapter row. It is still the only
way to move clips between chapters without a drag, which keyboard, screen-reader and imprecise-touch operators need,
so it cannot just be deleted.

## What Changes

- Remove the per-chapter **Move clips…** button, its dialog (`ChapterDialogs` Move dialog, Pick all, Pick marked) and
  the code, strings and tests that only they used (`pickMarked`, `markedAmong`, `ChapterToolsModel.moveClips`, the
  draft's `moveClips` if nothing else calls it).
- Add **Move marked to…** to the existing marks line, next to Rotate marked left / right: a native chapter picker and
  a **Move** button, `aria-disabled` with a reason in words when no clip is marked or no chapter is chosen. Move puts
  the marked clips, in page order, at the end of the chosen chapter as one edit, through the existing `groupOf` and
  `moveGroup` of the drag (no second implementation), unmarks them (`afterMove`), announces "3 clips moved to “Dag 2”."
  and counts in the save bar like a drag.
- Keyboard drag of a marked group (#104) is unchanged.
- web-only: no schema, `reel.yaml`, API, job, render or fingerprint change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: REMOVED "Edit mode moves clips to another chapter"; ADDED "Edit mode moves the marked clips to a
  chapter"; MODIFIED the requirements that name Move clips as a control or as a pending state (chapters, drag, marks,
  names, previews, notifications, Ctrl+S, poster, reorder, cuts).
- `event-timeline`: MODIFIED three requirements whose wording names "a Move clips is pending" so that they say a move
  of marked clips.

## Impact

- `web/src/edit/`: `EventEditor.tsx`, `ChapterTools.tsx`, `ChapterDialogs.tsx`, `ClipOrderList.tsx`, `marks.ts`,
  `draft.ts`, `emptyChapter.ts`, `edit.css`/`chapters.css`, and their `node:test` files. Package: `web` only.
- `docs/high-level-design.md`: §4.10 / D-13 wording.

Evidence: the user's feedback above; the code read on main 89079d9 (`web/src/edit/draft.ts` `groupOf`, `moveGroup`;
`marks.ts` `afterMove`; the marks line with Rotate marked in `EventEditor.tsx`); specs `web-app` "Edit mode moves clips
to another chapter", "Edit mode marks clips to move together", "Dragging a marked clip moves the whole marked group";
`clip-rotation` (the marks line offers Rotate marked). No research note applies.
