## Context

The track is windowed and absolutely positioned on a pure model in whole milliseconds (D-20); its handles are built in
the repo with a `dragStore` that allows one drag at a time and a live `ShiftFrom` transform. The lists reorder with
`@dnd-kit` and the reducer actions in `EventEditor.tsx` (reorder, move to chapter). There is no draft edit for
ignoring or including a clip: `draft.ts`'s `buildWriteBody` sends `ignore` back as read. This change builds it (D5).

## Decisions

### D1. Pure drop model
```ts
// timeline/reorder.ts
export type DropSlot = { chapter: ChapterKey; index: number; beforeIdentity: string | null; words: string }
export function dropSlot(lay: Lay, chapters: DrawnChapter[], trackMs: Ms, dragged: string): DropSlot
export function applyDrop(orders: Orders, from: { identity: string; chapter: ChapterKey }, slot: DropSlot): Orders
```
The slot is the clip boundary nearest the pointer's centre of the dragged block (snapping is to boundaries only). A
drop at its own place is no edit.

### D2. Built in the repo, not dnd-kit
The track drag uses `dragStore` (one-drag claim shared with trim, edge and card drags) and pointer capture, with a
3 px slop so a press still selects (`editor-selection` D2). `@dnd-kit` stays in the bin; the bin→track and track→bin
drags hand over through a small adapter that reads the pointer's pane.

### D3. Same reducer actions as the lists
A release of a reorder or a move dispatches the existing action, so the top bar summary ("1 clip moved"), Reset and the
save body are unchanged.

### D4. Keyboard
Alt+Left/Right on a selected clip computes `applyDrop` with the neighbouring slot; announcements through Edit mode's
live region.

## Research & Decisions

### dnd-kit on the track
**Context**: D-20 kept `@dnd-kit` for reordering.
**Explored**: the track's windowing and absolute layout; the existing `dragStore` and edge tools (`clip-edge-trim`).
**Decision**: build the track drag in the repo.
**Rationale**: dnd-kit's sortable strategies assume laid-out DOM siblings; the track's blocks are windowed and placed
from the model, which the repo's handles already drive.

## Risks / Trade-offs

- **Press vs. drag conflicts** with selection and handles → slop and the existing nearest-wins hit test decide.
- **Drag smoothness** on 80+ clips → live shift uses the existing transform path; measured as `clip-edge-trim` was.

## Failure behaviour
Display and draft only; Save writes the order as the lists do.

### D5. The draft ignore/include edit
A draft field holds the clips the operator ignores or includes (the set difference against the read `ignore`);
`buildWriteBody` writes `ignore` from it, and `isDirty`, Reset and the top bar's and save bar's counts include it. The
bin↔track drags and the Clip tab's "Ignore clip" button dispatch the one new reducer action, so each is one draft
edit. `editor-selection` leaves the button out for want of this edit.
