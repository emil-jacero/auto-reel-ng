## Context

State of `origin/main` (143f0fc, with `timeline-view`, `timeline-trim`, `timeline-overlays`,
`timeline-overlay-decisions` and `clip-play-read-view` merged), read from the code:

- **One drag context, one active draggable.** `edit/ChapterDrag.tsx` wraps every chapter in one dnd-kit
  `DndContext` (pointer sensor with a 6 px activation distance, keyboard sensor with the custom `coordinateGetter`).
  Each played clip's row is a `useSortable` (`ClipOrderList.tsx` `ClipRow`), the activator is its handle button. dnd-kit
  supports exactly one active draggable, so "the group" cannot be several draggables; it is **one lifted clip that
  stands for a set**.
- **Targets are slots** (`edit/dragSlots.ts`): `{chapter, index}`. In the clip's *own* chapter the index is sortable's
  (the position it takes once the others close up, so a chapter of n clips offers n slots); in *another* chapter it is a
  gap (m + 1 slots). The pointer picks the target by height (`pointerTarget`), the keyboard steps (`stepSlot`,
  `stepChapter`), and `slotOf`/`overIdOf` translate between a slot and a droppable id (`<identity>` or
  `/chapter/<key>` for "after the last").
- **The line and the copy.** In another chapter nothing moves: `ClipRow` draws `data-drop-before` on the row under the
  pointer when the active clip's sortable container differs (`dropBefore`), `ChapterDrop` draws the line after the last
  clip, and the `DragOverlay` copy names the chapter and position (`DragPreview`, `targetOf`). In the own chapter the
  rows make room (sortable's `verticalListSortingStrategy`) and the position numbers renumber while sorting
  (`position={isSorting ? newIndex + 1 : position}`).
- **The draft edits are pure** (`edit/draft.ts`): `moveClip` (reorder), `moveClips` (Move clips: picked clips to the end
  of one chapter, returning clips restored after their original predecessors), `moveClipTo` (a drop at a gap). The
  count of moved clips is `movedSet(keptOriginal(original, order), order, lastMoved)`, per chapter, a longest-increasing-run
  rule (O(n log n)), so a group move needs no new counting.
- **The editor's reducer** (`edit/EventEditor.tsx`) refuses every edit while `pressed !== null` (a save in flight) and
  `idle()` additionally holds while a Move clips applies (`moving`). `clip-drop` and `clips-move` are single reducer
  actions that go through `afterEdit` (the "retire the last save's refusal" rule). `onLift` holds Save while a clip is
  lifted. A save sends the whole order (`buildWriteBody` → `ReelWriteBody`), so *no write-API or engine change* is needed.
- **The thumbnail in Edit mode** is a grid item in area `thumb`; for a clip with a Cuts control it is a `<button
  class="clip-thumb-watch">` ("Watch <name>", `preview/preview.css`) that fills the cell. A sibling change
  (`clip-play-overlay-one-player`, parallel) reworks the *read view's* Watch into an overlaid Play; Edit mode's thumbnail
  stays a Watch button. This change must not nest a control inside that button.
- **Touch rule** (requirement "Every control is large enough to touch"): a 44 × 44 area around each button, none
  reaching into another control. The thumbnail is 80 × 45 px in narrow tables and cards (128 × 72 at ≥ 1024 px panel).

## Research & Decisions

### Marks live in the editor state, outside the draft
**Context**: marks must survive moves and a Cuts panel opening, must not make the page "dirty" (the unsaved-changes
question, the save bar, Reset's enablement), and must be cleared by Save, Reset and a re-read.
**Explored**: `Ready` already holds non-draft session state beside `draft`: `typed` (cut text not added), `lastMoved`,
`resets`, `nextCut`. `isDirty(baseline, draft)` reads only `draft`, so state outside it cannot make the page dirty.
**Decision**: `Ready.marked: ReadonlySet<string>` (identities), default a shared empty set. Actions `mark` `{identity,
on}`, `marks-clear`; `group-drop` and `clips-move` return `marked` less the clips they moved; `reset`, `read` and
`saved` return the empty set. The pure rules (toggle, prune to the clips a listed chapter plays and that are on disk,
less the moved, the words) live in `edit/marks.ts` so `npm test` can cover them (the reducer is in a `.tsx`).
**Rationale**: no draft field means no change to `isDirty`, `buildWriteBody`, `layoutChanged` or the save bar; a
stale identity (the event was re-read) is dropped by `read`, and `groupOf` defensively keeps only clips a listed chapter
plays, so a stale mark can never move a clip that is not there.

### A group is the marked set, taken in page order, gathered at a gap
**Context**: "the whole marked group is moved together ... keeping the group's relative order and dropping it at the
drop position". Marks can span chapters and be scattered inside one.
**Explored**: three definitions of the landing: (a) *anchor on the lifted clip* — every other member keeps its offset
from it (a "ghost layout" the operator cannot see before the drop, and undefined at chapter edges); (b) *like Move
clips* — append to the end, ignoring position (no better than the dialog that exists); (c) *gather at a gap* — remove
the group, then insert it as one run at the gap, before the first non-member clip at or after the gap.
**Decision**: (c). `groupOf(orders, listed, marked)` is the marked clips in page order (chapters as listed, each
chapter's play order), restricted to clips a listed chapter plays. `moveGroup(draft, group, to, gap)` (pure, `draft.ts`):

```ts
// gap: 0..order(to).length over the chapter's order *as it is now* (the group included)
const before = order(to).slice(0, gap).filter((id) => !group.has(id)).length  // unmarked clips above the line
// every chapter loses the group; `to` gets the run at index `before` of what is left
// returns the same `draft` object when no chapter's order changes (a no-op drop)
```

e.g. `A=[a1 a2 a3 a4]`, `B=[b1 b2]`, group `{a2 a4 b1}`: dropped between `b1` and `b2` (gap 1 of B) gives
`A=[a1 a3]`, `B=[a2 a4 b1 b2]`; dropped at the end of `A` (gap 4) gives `A=[a1 a3 a2 a4]`, `B=[b2]`.
**Rationale**: the result depends only on the group and the visible line, the same rule for the own chapter and any
other (no sortable-index special case), idempotent, and a no-op is detectable by reference equality, so "dropped,
unchanged" and "leaves nothing to save" need no extra logic. `lastMoved` is the lifted clip (the tie-break `movedSet`
already has). **Moved clips are not restored after their original predecessors** (as `moveClipTo`, unlike `moveClips`):
a drop is where the operator put it, and a group dragged back to its original contiguous place restores the original
order, which the "dragged back" scenario pins.

### Group drag: gap mode for every chapter, no rows making room
**Context**: in the own chapter sortable displaces the *other* rows around the single dragged row; with a group, the
other marked rows would be displaced as if unrelated, and the position numbers renumber (`isSorting`) by a single-clip
rule that is wrong for a set.
**Decision**: lifting a clip when `groupOf` has two or more members and the clip is a member starts a **group drag**
(`ChapterDrag` computes it once in `onDragStart` and keeps it in the `lift` ref; marks cannot change mid-drag, see
"Risks"). During it the drag model has `gaps: true`:
- `dragSlots.ts`: `slotCount` = length + 1 for *every* chapter (the own chapter's `chapterOf.get(identity) === key`
  special case is skipped), `overIdOf` returns `/chapter/<key>` for index = length in every chapter, `slotOf` maps a
  row to the gap before it and `/chapter/<key>` to the gap after the last, `pointerTarget` uses its "another chapter"
  branch (the first row whose centre lies below the pointer) for the own chapter too. `stepSlot`/`stepChapter` work
  unchanged over `slotCount`. The lift starts the keyboard at the gap before the lifted clip.
- `ChapterDrag.coordinateGetter`: the own-chapter branch (row top/bottom, sortable's rule) is taken only when
  `!gaps`; the line branch serves every chapter. A pure `groupPlace(orders, group, to, gap)` → `{position, total}` gives
  the copy and the announcements their numbers (total = non-members of `to` + group size).
- `ClipOrderList`: a small context from `ChapterDrag` (value changes only at lift and drop) tells the lists a group is
  held, so (a) `SortableContext` gets `strategy={() => null}` (no row shifts), (b) `ClipRow` draws `dropBefore` on any
  `isOver` row, (c) position numbers are not renumbered while sorting, (d) every marked row gets `data-held` (dimmed;
  the words "held" are in the row's accessible description). The dragged row keeps `data-dragging`.
**Rationale**: reuses the cross-chapter machinery (which is already "nothing moves, a line shows") instead of a second
visual language; the diff to `dragSlots.ts` is a flag on a few comparisons, and its existing tests stay as they are.
Single-clip drags never set the flag, so their behavior is byte-for-byte what it was.

### Drop is one reducer action
**Decision**: `{type: 'group-drop', dragged, to, gap}` → `moveGroup(state.draft, groupOf(...state.marked), to, gap)`,
`lastMoved: dragged`, `marked` less the group, through `afterEdit`; refused (state unchanged) when `to` is not listed
or the result is the same draft. `ChapterDrag` gets `onDropGroup(dragged, to, gap): boolean` (false = refused, as
`onDropInto`: the drop is then announced as unchanged) next to `onDropInto`/`onReorder`. The group is computed in the
reducer from `state.marked`, not shipped from the drag, so a drag can never move a clip the state does not hold marked.
Focus and scroll after the drop reuse `Dropped {identity, to, across: true}` (the lifted clip's handle in its new row,
`firstLineIntoView`).
**Rationale**: one dispatch is one render, one undoable-by-Reset edit, one announcement; the existing `listsLocked`
gates (`idle()`, `pressed`) apply unchanged.

### The mark control: a checkbox in the thumbnail's corner, a sibling of the Watch button
**Context**: the thumbnail is a button in Edit mode (cannot contain a checkbox), 80 × 45 px on a phone, and the touch
rule wants 44 × 44.
**Explored**: (a) a 44 px visible box (hides 55 % of an 80 px frame); (b) a box outside the thumbnail (leaves the
corner the operator named); (c) a 24 px visible box in the corner whose hit area is larger under `pointer: coarse`.
**Decision**: (c). `RowBody` renders `<span class="clip-mark"><input type="checkbox" aria-label="Mark <name>"
checked={…} aria-disabled={locked || undefined}/><span class="clip-mark-box" aria-hidden><Icon name="check"/></span></span>`
as a grid item in area `thumb` (`justify-self: end; align-self: start`, later in source order so it paints over the
Watch button), only for rows with `cuttable` (active/new, not excluded). The native input is visually hidden over the
box (so Space, `checked` and the focus ring `:has(input:focus-visible)` are native); the icon, not the colour, tells the
state; `forced-colors` gets a `CanvasText` border. Under `@media (pointer: coarse)` a `::before` enlarges the hit area
to 44 × 44 centred on the box (the box is inset 2 px, so the area reaches 8 px above the thumbnail, within the row's
8 px padding, and never above the row), and it wins over the Watch button where they overlap (z-order); the remaining
thumbnail still opens the preview. This is the one place the touch rule's "no area reaches into another control"
yields, to a smaller target of the same row; the spec says so.
**Rationale**: no nesting of interactive content, native semantics, no layout change (the thumbnail's size and place are
untouched, which "Every clip row shows a frame from its clip" requires). The risk that the grid-area overlay does not sit
exactly on the thumbnail's corner in the two-line and card layouts is covered by a geometry check (task 2.1) that
measures the mark's box against the thumbnail's.

### The marks line
**Decision**: the hint paragraph above the chapters ("Above the chapters, Edit mode SHALL say how clips are moved")
stays untouched; a new line directly under it holds the marking sentence on the left and, on the right, a count and
**Clear marks** inside a slot that always has the button's height (`min-block-size`, content `visibility`-hidden via the
`hidden` attribute on its children, not on the slot), so the first mark moves no row. Clear marks keeps focus by moving
it to the line (`tabIndex={-1}`), because the button leaves with the count.
**Alternatives rejected**: a sticky bar (collides with the carefully tuned scroll padding for the sticky header, the
chapter headings and the save bar that `firstLineIntoView` and the Page-key scrolling depend on); a count in each
chapter's tools row (that row is being reworked by `chapter-inline-rename`, which is gated on this change).
**Known limit**: in a 400-clip chapter Clear marks is a scroll away. Marks end on every move and on Save, the count is
announced on each change, and unmarking is one press on the mark itself, so this is judged enough for v2.

### When a mark ends
**Decision** (also in the spec): a clip's mark ends when a drop or Move clips *moves it*; all marks end on a successful
Save, Reset, leaving Edit mode, and a re-read; a no-op drop and a cancel leave marks; Move up/Down, a single unmarked
drag, chapter edits and cut edits leave them.
**Rationale**: the operator's flow is mark → move → done. Keeping the *remaining* marks after a Move clips from the
dialog (which can move only one chapter's clips) serves "mark across two chapters, move one chapter's part now". Marks
that survive a plain reorder serve "mark a few, nudge one, then move them".

### Move clips takes the marked set by a button
**Decision**: `MoveClipsDialog` gets a `marked: ReadonlySet<string>` prop and a **Pick marked** button next to Pick all
that adds the offered clips that are marked; with none it says so (`aria-disabled`, a line of words, no close). It
does not auto-pick on open (surprising for an operator who marked clips for a different purpose).
**Rationale**: the dialog is the one place a keyboard-only or screen-reader operator can move a set to another chapter
without a drag, and picking the marks there is the smallest bridge; a "Move marked…" with a chapter chooser would be a
second dialog and exceeds this change.

### Announcements
The editor's one live region carries mark changes (`announce`); dnd-kit's own region carries the drag, with new
strings for a group (`edit/marks.ts` `groupWords`, tested): lift, over (with and without a chapter name), drop,
unchanged, cancel. dnd-kit keeps only the last words of a batch, so as for a single clip the over-itself first target
after a lift says nothing (`lifting` ref). The keyboard instructions (`screenReaderInstructions`) gain one sentence
while two or more clips are marked; marks cannot change during a drag, so the context's accessibility does not change
while a clip is lifted.

### Performance
**Context**: a 400-row chapter re-renders slowly enough that the timer starved in the existing edge-scroll tuning
(`AUTO_SCROLL` comment), and "the first edit costs no more than the next" is a spec'd budget.
**Decision**: `ClipOrderList` receives its chapter's marked identities as a memoised `ReadonlySet` that keeps its
identity while the chapter's own marks are unchanged (the editor derives it per chapter), and `ClipRow` receives a
boolean `marked`, so a mark toggles re-render one row of one list; a group drop re-renders only the lists whose order
changed, as `clip-drop` does. The group is computed once per drop, O(total clips). The budgets in the spec are
**relative to the existing single-clip operation on the same fixture** (mark ≤ 100 ms to paint; group of 50 ≤ the
single-clip drop + 150 ms); task 3.1 measures the existing single-clip numbers first and reports both.

## Failure behavior and idempotency

- **Nothing here fails loud on the server**: no request is made for a mark, and a group drop is a draft edit like any
  other; the write is the existing save (If-Match, 412 and 409 paths unchanged).
- A drop for a chapter that is no longer listed, an identity no listed chapter plays, or a no-op returns the same
  state (the editor then speaks "dropped, unchanged"), never a partial move. A stale mark is dropped, never moved.
- **Repeating** `moveGroup` with the same arguments is a no-op (the group is already a run at that gap), and Save,
  `--force`, worker restarts and rendering are untouched: the write body is the same shape as after Move clips.
- **Locked states**: a save in flight or a pending Move clips refuses lifts (`useSortable disabled`), drops
  (`idle()`), marking (`aria-disabled`) and Pick marked.

## Risks

- **Mid-drag mark changes.** A pointer holds the drag and the keyboard drag is modal, but a script or a second input
  device could press a mark. `mark` is ignored while `ChapterDrag` reports a lift (`onLift`, the same flag that holds
  Save), so the group a drag lifted is the group it drops.
- **dnd-kit with a different strategy per drag.** Switching `SortableContext`'s `strategy` at lift is supported (it is a
  prop read on render), but the `onDragStart` render and the first `over` must agree; the Playwright run in Chrome
  and Firefox checks that no row transforms during a group drag.
- **A 24 px box over 80 px of frame.** If the operator finds it hides the frame it can be moved outside the corner
  without touching the logic; the geometry check pins today's position.
- **`chapter-inline-rename`** (gated on this change) edits the chapter header and `ChapterTools`; this change touches
  neither (marks line, rows, drag, dialog only), so the two merge cleanly.

## HLD updates (task 4.1)

D-13 gains a sentence ("a drag of a marked clip takes every marked clip, to the drop position"), §4.10 the v2 bullet for
Edit mode, and §6 phase 9 a line "`clip-group-select-drag` follows: marks and the group drag, web-only, no render,
fingerprint, schema or job change." No D-20/D-21 change: nothing here touches the timeline or the proxy contract.
