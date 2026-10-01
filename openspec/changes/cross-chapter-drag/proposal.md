## Why

auto-reel's chapters were folders (HLD §2, "chapter-from-subdirectory convention") and never reached the
container (§2, learning 3). auto-reel-ng made them real chapters in `reel.yaml` (D-E, D-2), and **D-13**
(`chapter-management-screen`) pulled chapter editing into GUI v1: add, rename, reorder, delete, and a
per-chapter **Move clips** dialog. D-13 kept "dragging across chapters" in v3 (§4.10), because one
`DndContext` across chapters looked expensive on a 400-clip chapter.

The operator has now used both G1 (`chapter-management-screen`) and G2 (`clip-cuts-screen`) and asked for
more: "Ok, it works. However, i would like for the editing of clips in chapters (moving them around) to be
drag and drop ALSO, we can still keep the button and multiple choice menu." Inside a chapter a clip is
already dragged. Between chapters it takes a dialog, a checkbox and a radio button, and the clip lands at the
end of the other chapter. One more drag then puts it in place.

A spike against the installed `@dnd-kit/core` 6.3.1 and `@dnd-kit/sortable` 10.0.0 (design, "Research &
Decisions") settled D-13's cost question. With one `DndContext` and one `SortableContext` per chapter, a step
to a new target costs what a step inside a 400-clip chapter costs today. The other chapters' rows add only
their sortable shells: none of their row bodies, no list and not the editor re-render. D-8's single drag-and-drop library
already covers it, so no dependency is added. This is HLD **§6 phase 8** (GUI v1), slice D. It depends on no
open §8 research item.

The same round also asked for a fix (follow-up #1 of G1's review): on a one-chapter event the operator did not
find chapter support. Edit mode's hint must say that chapters can be added and that clips can be dragged
between them.

## What Changes

- **Drag a clip into another chapter** (Edit mode, the event page; no new screen or route):
  - by **pointer** (mouse, pen or touch) from the clip's handle, as within a chapter today. While the clip
    is held near the window's top or bottom edge, the page scrolls by itself, so a chapter out of view can
    be reached.
  - by **keyboard** on the handle. Past a chapter's last position, Down takes the clip to the first position
    of the next chapter. Past its first position, Up takes it to after the last clip of the chapter before.
    A deleted chapter's placeholder is passed over, and Escape cancels.
  - **to any position**, before any clip of the other chapter or after its last one, or **into an empty
    chapter**. A chapter that plays no clip shows a visible drop area in Edit mode.
- **Where the drop lands, shown without moving anything.** In the target chapter a line marks the gap the clip
  goes into, or the empty chapter's area is highlighted. A compact copy of the dragged row follows the pointer
  and names the target chapter and position. Rows of the target chapter do not shift, so nothing on the page
  changes size or place. Within the clip's own chapter the drag looks and works as today: the rows make room.
- **The same edit as Move clips, at a chosen position.** A drop is one edit that takes the clip out of its
  chapter and puts it at the dropped position (a new pure `moveClipTo` in `draft.ts`). It works like a Move
  clips move for:
  - the "from <chapter>" badge, the moved counts in the heading and the save bar, and the D-12 notes
  - the save body (both chapters written from the view, NEW-clip adoption counted)
  - Reset, the unsaved guard, a conflict and Overwrite

  The clip keeps its cuts and its Cuts panel state, shown or hidden and with any time typed but not added
  (G2's store keyed by identity). A clip dragged back to where it was when Edit mode opened leaves nothing to
  save.
- **What cannot cross.** A **missing** clip's drag still stops at its own chapter's edge, from the keyboard
  too, as Move clips never offers it, and its lift says so. Ignored and removed clips still have no handle. A
  release over a **deleted chapter's placeholder** moves nothing. While a **save is in flight** or a **Move
  clips is being applied**, no clip can be lifted and a drop moves nothing.
- **Announcements and focus.** Every target in another chapter is announced with that chapter's name and the
  position out of the clips it would then play. The drop and a cancel are announced too. Within a chapter
  the existing words stay unchanged. After a drop into another chapter, by pointer or keyboard, keyboard
  focus is on the moved clip's handle in its new chapter, in view above the save bar.
- **Move clips and Move up / Move down stay exactly as they are.** The dialog is unchanged, and Move up and
  Move down never leave the chapter.
- **The hint** (follow-up #1): with one chapter, it says that a chapter can be added (Add chapter, below
  the chapters) and that clips can then be dragged between chapters. With several, it says that a clip can be
  dragged into another chapter, or several moved with a chapter's Move clips. The empty-chapter words say
  that clips can be dragged there.
- **Docs.** `web/README.md` (the Edit-mode paragraph, the `edit/` tree) and `docs/high-level-design.md`. In
  D-13, "Dragging across chapters stays v3." is replaced by a sentence saying that dragging across chapters
  followed in `cross-chapter-drag`. In §4.10, the v3 line loses "drag across chapters" and slice row D gains
  one clause.

## Non-goals

- **Changing Move clips, Move up or Move down.** The operator asked to keep them. They stay as they are.
- **Dragging several clips at once**, range selection, or a drag that splits a chapter. Move clips covers
  batches.
- **Dragging chapters themselves.** Chapters keep their Move up / Move down.
- **Jump keys during a keyboard drag** (Page Up / Page Down to the next chapter, Home / End). Crossing a
  400-clip chapter by arrow is 400 presses. Move clips is the keyboard path for long distances, and a jump key
  is a follow-up if the operator asks.
- **Dropping a missing clip into another chapter.** Move clips refuses it, and so does the drag (proposal and
  design of `chapter-management-screen`).
- **Virtualising the clip lists**, or a different drag-and-drop library. The spike shows the budgets hold
  without either (design, "Render budget").
- **Engine, API, schema or render changes.**

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-app`. All of the following are in the one capability.
  - One ADDED requirement: `Requirement: Edit mode drags clips between chapters`.
  - Three MODIFIED requirements, each re-based on the current `openspec/specs/web-app/spec.md`:
    - `Requirement: The event page reorders clips within a chapter`. A drag no longer stops at the chapter's
      edge, except a missing clip's, and Move up and Move down still never leave it. The scenario "A clip
      cannot leave its chapter" now checks Move up at the chapter's edge, and a new scenario "A missing clip
      cannot leave its chapter" checks the drag.
    - `Requirement: Edit mode moves clips to another chapter`. Its closing sentence ("Dragging a clip … still
      never take it into another chapter") now says that a drag can take a clip into another chapter and
      that Move up and Move down still never do.
    - `Requirement: Edit mode adds, renames, reorders and deletes chapters`. A chapter that plays no clip says
      that clips can be dragged into it, or moved there with another chapter's Move clips.

## Impact

- **Packages:** `web/` only, plus two documentation files.
  - `web/src/edit/`:
    - new `dragSlots.ts`: pure slot math, keyboard order, pointer targets and words, with type-only imports
    - new `ChapterDrag.tsx` and `drag.css`: the one `DndContext`, sensors, collision detection, keyboard
      coordinate getter, `DragOverlay` preview, announcements, and focus after a drop
    - `ClipOrderList.tsx`: the per-chapter `DndContext` becomes a `SortableContext` with an id. It also gains
      the chapter drop target, the drop area, the row's drop line and the empty-chapter words.
    - `ChapterTools.tsx`: the deleted placeholder refuses drops
    - `draft.ts`: `moveClipTo`
    - `EventEditor.tsx`: the `clip-drop` action, the wiring and the hint
    - `edit.css`: the lifted row becomes the placeholder
  - `web/README.md` and `docs/high-level-design.md` (D-13, §4.10).
- **CLI vs API (Principle V):** neither is touched. A drop is a draft edit, and Save is the existing
  `PUT …/reel` that every client reaches through `apply_editorial_write`.
- **Rendered output:** unchanged for identical inputs. There is no `RENDER_GRAPH_VERSION` bump, and the
  fingerprint's inputs are unchanged. A saved drag moves the editorial component, as any edit does.
- **Schemas:** no change to `reel.yaml` or `config.yaml`, and no API change. There is no Alembic migration and
  no rescan. `web/openapi.json` and `schema.d.ts` are untouched.
- **Dependencies:**
  - **Gate:** none. The change starts from main at `6656ebc` or later.
  - **New runtime dependencies:** none. `DragOverlay`, `useDroppable` and the custom collision detection and
    keyboard coordinate getter are all in the installed `@dnd-kit/core` 6.3.1 and `@dnd-kit/sortable` 10.0.0
    (D-8). `web/package.json` and the lockfile stay byte-identical.
- **Size (Principle VIII):** one package plus docs, one capability delta (1 added, 3 modified), and 9 tasks.
