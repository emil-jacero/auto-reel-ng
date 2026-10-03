## Why

The operator's feedback on Edit mode (2026-10-03, with screenshots): "In the chapter editor I want to add a feature
to start marking the top right corner of the clips I want to move, then I just click and drag any of them and the
whole marked group is moved together."

Today a clip moves one at a time. A drag takes one clip (D-13, `cross-chapter-drag`, requirement "Edit mode drags
clips between chapters": "a drop into another chapter SHALL be one edit", singular), and the only way to move several
at once is a chapter's **Move clips** dialog, which can only append them to the *end* of one other chapter, takes
clips from one chapter at a time, and has no notion of position (requirement "Edit mode moves clips to another
chapter"). Re-ordering a run of clips, or pulling a scatter of clips from two chapters into one place, costs one drag
per clip. The dialog is a different surface from the drag the operator already uses.

What exists to build on, read from `origin/main` (143f0fc): dnd-kit's `DndContext` already wraps every chapter
(`edit/ChapterDrag.tsx`) with a pointer and a keyboard sensor, a drop already resolves to a *slot* (a chapter and an
index; `edit/dragSlots.ts`), a drop into another chapter already shows a line and moves nothing to make room, and the
draft already has the pure edit `moveClipTo` and the counting rule `movedSet` (`edit/draft.ts`). dnd-kit has exactly
one active draggable at a time, so a group cannot be several draggables: it is one lifted clip that stands for a set.
No new dependency is needed.

HLD: §4.10 (GUI v2, "chapter and clip editing" in Edit mode), §6 phase 9 (GUI v2), D-13 (chapters are edited in the
GUI) and D-12 (a chapter's name decides where later clips go). The research (`research/v2/synthesis.md`) is about
proxies and the timeline and has nothing on marking; the evidence for this change is the code reading above and the
operator's words. This change is the gate of `chapter-inline-rename`, which reworks the same chapter header.

## What Changes

- **A mark on each movable clip.** In Edit mode every clip a chapter plays that is on disk gets a checkbox in the
  top-right corner of its thumbnail, named "Mark <clip>", with a check icon when marked (not colour alone) and a
  44 × 44 px tap area under a coarse pointer. Missing and ignored clips (and removed ones) have none, as Move clips
  does not offer them. A line above the chapters says how marking works and, once any clip is marked, shows the count
  ("3 clips marked") and a **Clear marks** button. Marking is not an edit: it never shows the save bar and never
  asks before leaving.
- **Dragging a marked clip moves the whole group.** With two or more clips marked, lifting any marked clip by its
  handle (pointer, touch or keyboard, exactly as today) lifts all of them. A drop is one edit: the group, in page
  order (chapters as listed, then play order), lands together at the drop position, in the same chapter or another,
  from one chapter or several. Dragging an unmarked clip moves just that clip, and one marked clip alone drags as a
  single clip.
- **A group drag shows a line everywhere.** Because other rows cannot make room for a set, a group drag marks the
  drop with a line in every chapter, its own too, and the copy that follows the pointer says how many clips go where.
  The marked rows are dimmed while they are held.
- **One draft edit.** A group drop is one reducer action, counted and saved like Move clips (moved counts, "from"
  badges, Reset, Save, the unsaved-changes question, conflicts, announcements). Marks end for the clips a move took,
  and for everything on Save, Reset and a re-read.
- **Move clips may take the marks.** The dialog gets a **Pick marked** button that picks the marked clips of the
  chapter it was opened on.
- **Docs.** HLD D-13 and §4.10/§6 phase 9 note the group; `web/README.md` describes the marks and the group drag
  (Edit mode paragraph, `edit/` tree).

### Non-goals

- Marking by clicking a row, Shift/Ctrl-click ranges, select-all, lasso. Marking is the checkbox only.
- Dragging by the thumbnail or the row: a drag still starts only from the handle (requirement "The event page reorders
  clips within a chapter": a coarse-pointer scroll must keep working). The operator's "click and drag any of them"
  is any *marked clip's handle*.
- Marking missing or ignored clips; moving a group *between* events; copying.
- Keeping marks beyond Edit mode or a Save: they are page state and end there (see the design).
- A per-move Undo: the editor has none for Move clips or drags either; Reset is the undo.
- The Timeline, the proxies, the player, and the rename rework (`chapter-inline-rename`, a separate change).

### Effect on the rest of the system

- Rendered output unchanged for identical inputs: **no `RENDER_GRAPH_VERSION` bump**, no staleness-fingerprint input
  change. `reel.yaml` and `config.yaml` schemas unchanged; the save writes the same body shape (`chapters` order)
  as Move clips. No Alembic migration, no rescan. No CLI or API change (Principle V: the write API already takes any
  order). Packages: **`web/` only**. No new runtime dependency (dnd-kit stays; Principle VII).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`: ADDED requirements for marking clips and for dragging a marked group; MODIFIED "Edit mode moves clips to
  another chapter" (the dialog's Pick marked).

## Impact

- `web/src/edit/`: `draft.ts` (`moveGroup`, `groupOf`, `groupPlace`, pure), `marks.ts` (new, pure), `dragSlots.ts` (gap mode), `ChapterDrag.tsx` (group
  lift, copy, announcements), `ClipOrderList.tsx` (mark control, dimming, line, sortable strategy),
  `EventEditor.tsx` (marks state and actions, marks bar), `ChapterDialogs.tsx` (Pick marked), `edit.css`/`drag.css`,
  with `node:test` files beside the pure modules. No Python, no API schema, no dependency.
- Docs: `docs/high-level-design.md`, `web/README.md`.
