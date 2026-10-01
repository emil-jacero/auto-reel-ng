## Context

See proposal.md, "Why". This change works on main at `6656ebc`. Its code is `web/src/edit/` only: two new
files (`dragSlots.ts`, `ChapterDrag.tsx` with `drag.css`) and edits to `ClipOrderList.tsx`,
`ChapterTools.tsx`, `EventEditor.tsx`, `draft.ts` and `edit.css`. The docs are `web/README.md` and
`docs/high-level-design.md`.

**Edit mode today** (all re-read on `6656ebc`):

- `edit/ClipOrderList.tsx` is one chapter, with its own `DndContext` (`id={`chapter-${chapterKey}`}`,
  775-821).
  - **The drag.** A `PointerSensor` with a 6 px activation distance and a `KeyboardSensor` with
    `sortableKeyboardCoordinates` (621-628). The `withinChapter` modifier (90-97) clamps the dragged row to its
    own `<ol>`. Without the clamp, `closestCenter` would pick the chapter's nearest clip while the pointer is
    over another chapter.
  - **Words and the drop.** The announcements (630-648) and `onDragEnd` (650-663) are per chapter. A drop
    calls `onMove(chapterKey, from, to)`, and the editor's `move` action applies it (`EventEditor.tsx`
    272-281).
  - **Scroll.** After a drop, `dropped` (589) and the layout and passive effects (700-738) scroll the row into
    view.
  - **The rows.** `ClipRow` (252-422) is `memo` with constant icon elements. Its `RowBody`, `MoveButtons` and
    the Cuts control are memoised children, "so a drag step re-renders neither" (196-204).
  - **An empty chapter.** A chapter that plays no clip shows `NO_CLIPS` or `NO_CLIPS_PLAYED` (500-504,
    761-774): "Move clips here with another chapter's Move clips."
- `edit/EventEditor.tsx`:
  - **Rendering.** It renders the chapters in one `map` (1723-1764): `DeletedChapter` for a deleted chapter,
    `ClipOrderList` otherwise.
  - **Moves.** A Move clips move is the `clips-move` action (325-332) over `moveClips` (`draft.ts` 717-749),
    applied in a transition while `movingFrom` locks every list (950-953, 1477-1500).
  - **Locks.** `listsLocked` is "a save in flight or a Move clips pending" (953). `idle()` (1201-1202) is
    the same test for handlers built once.
  - **Cuts.** The Cuts panel store is keyed by identity (`cutPanels`, 1140-1149), so a row mounted anew in
    another chapter opens as it was (G2).
  - **The hint** is at 1692-1714: "Clips stay in their chapter; use a chapter's Move clips to move them to
    another."
- `edit/draft.ts`:
  - `moveClips` (717-749) appends the moved clips to the end of the target. A clip returning to its home
    chapter goes back after its original predecessors (`restoreClip`).
  - `keptOriginal` (620-623) and `movedSet` (807-815) count a clip moved in once and the clips left behind as
    unmoved.
  - `writtenFromView` (256-281) writes every chapter whose order changed from the view.
- `edit/ChapterTools.tsx`: `DeletedChapter` (214-262) is a `<section className="panel edit-chapter"
  data-deleted>` with an Undo.
- `.panel` has `container-type: inline-size` (`styles/components.css` 161-166). That is layout containment,
  so every chapter panel is its own stacking context. Its header is sticky at `z-index: 2`, the app header is
  at 20, the save bar at 6 and the toasts at 30.

**dnd-kit facts** from the installed packages (`web/node_modules/@dnd-kit/core/dist/core.esm.js` 6.3.1 and
`sortable/dist/sortable.esm.js` 10.0.0), each confirmed by the spike below:

| Fact | Where |
|---|---|
| `sortableKeyboardCoordinates` already crosses `SortableContext`s: it picks the nearest enabled droppable in the key's direction with `closestCorners` over **all** containers | sortable 657-747 |
| A sortable item is displaced only while `active` and `over` are in the **same** `SortableContext` (`displaceItem`); in a target context without the active item, `disableTransforms` is set. Without a `DragOverlay` the dragged row therefore loses its transform, and snaps back to its place, while it is over another chapter | sortable 314, 506-507 |
| `InternalContext`'s value includes `over`, and every `useDraggable` / `useDroppable` reads it. Every `useSortable` row re-renders when the target changes. The pointer's transform is read through `ActiveDraggableContext` by the dragged item only | core 3337-3352, 3403-3410, 3476 |
| `RestoreFocus` puts focus back on the activator after a **keyboard** drag only; a pointer drop that unmounts the focused handle leaves focus on `<body>` | core 2689-2740 |
| `DragOverlay` takes `className`, `style` (spread last, so `width`/`height: auto` win), `zIndex` and `dropAnimation`. `draggingNodeRect` (collisions, the keyboard's current coordinates) is the overlay's measured rect once it is mounted | core 2947-2948, 3640-3676, 3895-3965 |
| Droppable rects are `Rect`s that follow the scroll of their scrollable ancestors. `pointerCoordinates` are viewport coordinates, `null` for a keyboard drag | core 970-1004, 2977 |
| The keyboard sensor scrolls a scroll container itself when the new coordinates leave the middle half of the window (arrow codes only), and ends a drag on Tab | core 1175-1306 |

**Spike** (session scratchpad, `g-spec/cross-chapter-drag/spike/`, never committed). It is a Vite app on the
installed packages with one `DndContext`, one `SortableContext` per chapter, a `DragOverlay`, the collision
detection and the keyboard getter designed below, and `memo` rows with render counters. It has the shape of
`Stor dag` plus a deleted placeholder: `Main` (4 clips, one missing), `Stor` (400), `Kväll` (3), a deleted
chapter and an empty added one. It was driven with Playwright (`probe.py`, `p7.py`–`p12.py`), as a production
build and under the StrictMode dev server.

| Check | Result |
|---|---|
| keyboard: last clip of `Main`, Down, drop | over `Stor` position 1 of 401; dropped there; focus on its handle in `Stor` (`RestoreFocus`) |
| keyboard: last clip of `Kväll`, Down | the deleted chapter is passed over; over the empty chapter, "position 1 of 1"; dropped there |
| keyboard: missing clip, Down at its chapter's end | stays; drop keeps it last in `Main` |
| keyboard from `c0400` across into `Kväll` at 390 × 844 | the sensor scrolls the page; the line and the overlay stay in the window at each step |
| pointer: `Main` → between `c0001` and `c0002` | line above `c0002`; dropped at index 1; **focus fell to `<body>`** (see "Focus and scroll after a drop") |
| pointer: onto the empty chapter's area, onto the deleted placeholder, missing clip into `Stor` | dropped first / nothing moved / clamped to `Main`, last |
| pointer held at the bottom edge from `Main` to `Kväll` (≈ 18 000 px) | auto-scroll reached `Kväll` in ≈ 14 s; drop correct; no long task |
| touch (CDP `Input.dispatchTouchEvent`), 390 × 844, coarse | `Kväll` clip dropped into the empty chapter |
| StrictMode dev server | every check above gave the same result |
| renders, keyboard step (408 rows) | 408 row shells, **0 row bodies, 0 lists**, 15–38 ms (the spike's rows show no position number) |
| renders, 10 pointer moves with no new target | 1 row (the dragged one) per move |
| renders, lift / drop | 1 629 row shells (4 passes) in 56–94 ms / 2 lists, 29 ms |
| commit-hook counts vs in-app counters | equal for lift, step, move and new target (method in "Render budget") |

One thing the spike first got wrong decided a detail: a child's `useLayoutEffect` runs before its parent
element's ref is attached. A droppable attached to the parent `<section>` from a child component must
therefore attach in `useEffect` (see "Droppables").

## Goals / Non-Goals

**Goals:**

- Drag a clip into any position of another chapter, or into an empty one, by pointer and by keyboard, as
  one edit with Move clips' semantics. Move clips stays as it is.
- Within a chapter, today's behaviour: the rows make room, with the same announcements, focus and scroll.
  Only the lifted row's look moves to the floating copy ("The visuals").
- Drag costs stay within today's budgets on the 403-clip fixture, and nothing moves or changes size while the
  pointer is over another chapter.

**Non-Goals:**

- No engine, API, schema or dependency change. No change to Move clips, Move up / Move down, Remove / Undo,
  the Cuts panel or the save bar's mechanics.
- No new drop semantics for a clip that returns to its home chapter: unlike Move clips, a drag puts the clip
  where it was dropped (see "A drop is one edit").

## Research & Decisions

### One `DndContext`, a `SortableContext` per chapter, and a `DragOverlay`

**Context**: A clip must travel from one chapter's list to another's, by pointer and by keyboard, and land
at a chosen position.

**Explored** (spike; dnd-kit facts above):
- **Keep a `DndContext` per chapter.** Separate contexts cannot see each other's droppables, so this cannot
  work.
- **One `DndContext`, rows transformed as today, no overlay.** Over another chapter, `useSortable` drops the
  dragged row's transform (`displaceItem`), so the row snaps back home. Even with its own transform it would
  sit inside its panel's stacking context (`container-type`). It would pass under the next panel and under
  every sticky chapter header.
- **One `DndContext` with a `DragOverlay`** in a portal to `<body>`, as dnd-kit's multi-container examples
  use. The row stays in its list as a placeholder, and a copy follows the pointer above every panel.

**Decision**: One `DndContext` (`id="edit-chapters"`) in a new `ChapterDrag` component that wraps the
chapter sections in `EventEditor` and renders no element of its own. Each `ClipOrderList` keeps a
`SortableContext`, now with `id={chapterKey}`, and loses its `DndContext`, sensors, modifier, announcements
and `onDragEnd`. The copy is a `DragOverlay`, portalled to `document.body`, with these settings:

- `className="clip-drag-overlay"`
- `style={{ height: 'auto' }}`: the copy is the row's first line, compact, never the height of an open Cuts
  panel. The wrapper keeps dnd-kit's own `width` (the row's), so the preview inside it can be sized against
  the row ("The visuals")
- `zIndex={25}`: above the app header (20) and the save bar (6), under the toasts (30)
- `dropAnimation={null}`

**Rationale**: The overlay is the only shape that can leave the panel. Within the clip's own chapter,
sortable still displaces the rows, so the placeholder moves to the drop position and the rows make room, as
today. `ChapterDrag` receives the lists as `children`. Its own state changes (the active clip) and every
`DndContext` update therefore leave the list elements identical, and React re-renders only context
consumers ("Render budget").

### Over another chapter: show the target, move nothing

**Context**: dnd-kit's multi-container pattern moves the item into the target container during the drag
(`onDragOver` updates the state).

**Explored**:
- **Move during the drag.** Every crossing writes state. Two 400-row lists re-render and re-measure, the
  source row unmounts while it is the active node, and a cancel must undo it. The page changes height under
  the pointer, which is a layout shift, and dnd-kit's example needs a guard against collision loops.
- **Target only.** The target is shown and nothing moves: a line between two rows, the empty chapter's area
  marked, and the copy's badge naming the chapter and position. The drop applies one draft edit.

**Decision**: Target only. Over another chapter no row moves and nothing changes size. The line is a
pseudo-element of the row it precedes, or an absolutely placed element at the list's end, and an empty
chapter's area exists before the drag starts. Within the own chapter, sortable's displacement stays as today.

**Rationale**: There is no state change during a drag, so a cancel needs no undo. Rects measured at the lift
stay valid, nothing is re-measured, and nothing shifts. It is also the cheapest variant. The spike measured
29 ms for the one drop commit.

### Droppables and their ids

**Decision**: Three kinds of droppable:

| Droppable | id | Registered by | Rect |
|---|---|---|---|
| a played clip's row | its identity (as today) | `ClipRow`'s `useSortable` | the row |
| a listed chapter | `/chapter/<key>` | `ChapterDrop`, a child of `ClipOrderList`, `useDroppable` attached to the chapter's `<section>` in a `useEffect` | the whole section |
| a deleted chapter's placeholder | `/deleted/<key>` | `DeletedChapter`, `ref={setNodeRef}` on its `<section>` | the placeholder |

An identity is a path relative to the event folder and never starts with `/`, so neither prefix can collide
with a clip. `dragSlots.ts` exports both prefixes. `ChapterDrop` attaches in `useEffect` (spike: in
`useLayoutEffect` the parent's ref is still `null`). `ClipOrderList` does not call `useDroppable` itself:
that would make it a context consumer, and its 400-row map would run on every new target.

### Collision detection

**Context**: `closestCenter` over every row of every chapter would pick rows across chapter boundaries by
their centres. It would also ignore the deleted placeholder and let a missing clip escape.

**Decision**: A custom `CollisionDetection` in `ChapterDrag`, a thin adapter over the pure `pointerTarget` in
`dragSlots.ts`:

- **Keyboard** (`pointerCoordinates === null`): return the droppable of the slot the coordinate getter last
  chose (`overIdOf`, kept in a ref). `onDragStart` empties the ref at every lift, so a slot from an earlier
  drag is never reused. Before the first key, return the active clip itself, as `closestCenter` does today.
- **Pointer**, at the pointer's height `y`:
  1. If `y` is inside a `/deleted/…` rect, return no collision: over `null`.
  2. Choose the chapter: the `/chapter/…` rect that contains `y`, else the one nearest to `y`. A missing clip
     always gets its own chapter.
  3. In the clip's **own** chapter, pick the row whose centre is nearest to `y`: sortable's index semantics,
     as `closestCenter` gives today with the row under the pointer.
  4. In **another** chapter, pick the first row, in play order, whose centre is below `y` ("before that
     row"). If there is none, pick `/chapter/<key>` ("after its last clip"). For a chapter that plays no
     clip that is its area.

```ts
/** The droppable a pointer at height `y` targets, or null (a deleted chapter's placeholder). */
export function pointerTarget(
  model: DragModel,
  identity: string,
  staysHome: boolean,
  y: number,
  chapterSpan: (key: ChapterKey) => Span | undefined,
  deletedSpans: readonly Span[],
  rowSpan: (identity: string) => Span | undefined,
): string | null
```

**Rationale**: The pointer, not the copy's rect, decides. The copy is grabbed at its handle and is shorter
than a row with an open Cuts panel, so its centre would drift. A pointer in the gap between two panels, or over a
chapter's header or ignored list, still lands in an obvious place: the nearest chapter, at its start or end.
Each call is one pass over the target chapter's rows (≤ 400).

### Keyboard model and the coordinate getter

**Context**: `sortableKeyboardCoordinates` crosses containers geometrically (closest corners in the key's
direction). That lands on whichever droppable is nearest: a chapter's section rect, a row of a chapter two
panels away. It cannot express "after the last clip".

**Decision**: A custom `KeyboardCoordinateGetter` over a linear **slot** sequence (`dragSlots.ts`):

```ts
/** Where a drop puts the clip: an index into a listed chapter's play order. */
export type Slot = { chapter: ChapterKey; index: number }

/**
 * Every slot `identity` can be dropped at, in page order: its own chapter's n positions
 * (sortable's index semantics), and, unless it stays home (a missing clip), each other
 * listed chapter's m + 1 gaps (before each of its m clips, then after the last).
 */
export function slotsOf(model: DragModel, identity: string, staysHome: boolean): Slot[]
/** The slot one step up (-1) or down (1) from `from`; null at either end. */
export function stepSlot(model: DragModel, identity: string, staysHome: boolean, from: Slot, delta: -1 | 1): Slot | null
/** The droppable a slot stands for: a row's identity, or `/chapter/<key>` after the last clip. */
export function overIdOf(model: DragModel, identity: string, slot: Slot): string
/** The slot an `over` id stands for; null for none or a deleted placeholder. */
export function slotOf(model: DragModel, identity: string, overId: string | null): Slot | null
```

- **Down / Up** move one slot. From the own chapter's last position, Down goes to the next listed chapter's
  first gap. From a chapter's first gap, Up goes to the previous listed chapter's last gap, or, when that is
  the own chapter, to its last position. Deleted chapters are not listed, so they are passed over. At either
  end of the sequence the getter returns `undefined` and nothing happens, as at a list's end today.
- **Every other key** returns `undefined`. Space and Enter drop, Escape cancels and Tab drops (the sensor's
  own codes, unchanged).
- **Coordinates.** The getter stores the slot, then returns coordinates that put the copy where the drop
  will be:
  - own chapter: the target row's top, or its bottom when moving down past the clip (sortable's rule)
  - another chapter: centred on the gap's line (the row's top, or the last row's bottom, minus half the copy's
    height)
  - an empty chapter: centred on its area

  The sensor then scrolls the page as it does today (middle-half rule, `scrollBehavior` `smooth`, or `auto`
  under reduced motion).

**Rationale**: The sequence is the page's reading order, so "Down past the last clip" means "into the next
chapter" with no geometry to tune. The spike crossed 400 rows into `Kväll` and back with the line and the
copy in the window at each step. Jump keys (Page Up / Page Down) are a non-goal (proposal): the sensor scrolls
only for arrow codes, so a jump would also need its own scroll.

### A drop is one edit: `moveClipTo`

**Context**: Move clips appends to the target's end, or returns a home-coming clip after its original
predecessors (`moveClips`). A drag names its position.

**Decision**: A position-aware variant, pure, in `draft.ts`:

```ts
/**
 * `draft` with `identity` taken out of chapter `from` and put at index `at` of chapter
 * `to` (clamped to its length): a drop into another chapter. Only a clip `from` plays
 * moves, so a repeated call moves nothing; `from === to` is a reorder (`moveClip`), not
 * this, and returns `draft` unchanged.
 */
export function moveClipTo(
  draft: Draft,
  from: ChapterKey,
  to: ChapterKey,
  identity: string,
  at: number,
): Draft
```

and one reducer action in `EventEditor.tsx`:

```ts
| { type: 'clip-drop'; from: ChapterKey; to: ChapterKey; identity: string; at: number }
```

- Both chapters must be listed (`isListed`), and the action is refused while a save is in flight (the
  reducer's existing guard).
- It goes through `afterEdit` and sets `lastMoved: identity`, as `move` does. When `moveClipTo` returns the
  same `Draft`, the action returns `state` itself, with `lastMoved` unchanged, as `withDraft` does.
- `EventEditor` dispatches it only when `idle()` holds and the clip is on disk (`onDisk`). It is dispatched
  synchronously, not in a transition: the copy disappears in the same commit, and a transition would show the
  old order for a frame.

A drop within the own chapter stays `onMove(chapter, from, to)` (the `move` action), as today.

Nothing else in the model changes. Every rule that already holds for a Move clips move holds as it is:

- the counts and the "from" badge: `keptOriginal` + `movedSet` per chapter, `origins`
- the save body: `writtenFromView` sees both orders changed, and `adoptedNewCount` counts the NEW clips
- the D-12 notes: they depend on chapter names, not orders
- `isDirty`, Reset, the unsaved guard, Overwrite and the conflict

A clip dragged back to its home chapter at its original index restores that order exactly, so `isDirty`
is false with no special case. Dropped elsewhere at home, it is an ordinary reorder.

**Rationale**: The operator chose the position, so `restoreClip`'s placement would move the clip away from
where it was dropped. A separate small function keeps `moveClips` (and its scenarios) untouched.

### What cannot cross, and the locks

**Decision**:

- **A missing clip.** `staysHome(identity)` is true: `slotsOf` lists only its own chapter,
  `pointerTarget` forces its own chapter, and a modifier clamps its copy to its own `<ol>`. That is today's
  `withinChapter`, now applied to the overlay and only to a missing clip. `containerNodeRect` is still the
  active row's parent. On an event with more than one listed chapter, its lift announcement adds
  " It is missing, so it stays in “<heading>”."
- **Ignored and removed clips** have no handle (unchanged), and they are not droppables.
- **A deleted chapter's placeholder**: over `null` (collision step 1), and the keyboard sequence never lists
  it. A release there is `onDragEnd` with `over === null`: nothing moves, and the drop is announced with
  today's "unchanged" words.
- **Locks.** Rows keep `useSortable({ disabled: locked })` with `locked = listsLocked`. While a save is in
  flight or a Move clips is pending, no drag starts: the handle has no listeners and says `aria-disabled`.
  At the drop, `ChapterDrag` checks `locked` again, `onDropInto` checks `idle()`, and the reducer refuses
  `clip-drop` while `pressed` is set. A drop that a lock refuses moves nothing.
- **Modifiers.** `[vertical, homeClamp]`. `vertical` sets `x: 0` for every copy, so the copy stays in its
  column at every width. `homeClamp` is the clamp above.

### The visuals

**Decision** (all in `@layer screens`, tokens only, no new colour):

- **The placeholder** (`.clip-item[data-dragging]`, `edit.css`). Today's lifted look moves to the copy. The
  row gets `background: var(--accent-soft)` and `outline: 1px dashed var(--accent)` with
  `outline-offset: -1px`. Its text keeps its colours, with no opacity, so contrast holds during a drag
  (axe runs then; tasks 4.2). It keeps its size.
- **The copy** (`drag.css`, `.clip-drag-overlay` > `.clip-drag-preview`). It holds the grip icon, the clip's
  name as its row names it (monospace, one line, ellipsis) and, over another chapter, an info badge
  `to “<heading>”, position <p> of <m + 1>` with an `arrow-right` icon.
  - Look: `--surface-raised` with `--shadow-lg` and the accent ring that `[data-dragging]` has today.
  - Size: `inline-size: fit-content`, `max-inline-size: min(24rem, calc(100% - 3rem))` (100 % is the
    wrapper, which is the row's width), `min-block-size: 2.75rem`, flex-wrap, so the badge wraps under the
    name at 320 px. The copy therefore always ends at least 3rem before the row's inline end, and the line
    under it stays visible there with its dot (spike: a full-width copy hid it). A cap against the viewport
    (`100vw - 2 * --page-gutter`) would not do this: at 320 px the name and the badge reach that cap, and
    the copy would be exactly as wide as the row.
  - The copy is `aria-hidden="true"`; the live region speaks.
- **The line before a row** (`.clip-item[data-drop-before]`). A `::before` 2 px tall,
  `background: var(--accent)`, inset `var(--s-2)` on both sides and centred on the row's top edge, plus an
  8 px accent dot at its inline end (`::after`). Both have `pointer-events: none`. `ClipRow` sets the
  attribute when `isOver` is true and the active clip's `sortable.containerId` differs from its own. It
  already re-renders on every new target.
- **The line after the last row** (`.chapter-drop-end`). `ChapterDrop` renders an `aria-hidden` element
  while `/chapter/<key>` is the target and the chapter plays clips. It is placed absolutely at the `<ol>`'s
  `offsetTop + offsetHeight`; `.edit-chapter` becomes `position: relative`. It is rendered **before** the
  `<ol>`, so `.edit-chapter > .clip-order:last-child` still matches and the last row's border never flips
  during a drag.
- **The empty chapter's area** (`.chapter-drop`, replacing `.chapter-empty` in Edit mode). `ChapterDrop`
  renders it whenever the chapter plays no clip, drag or not, with the words of "The hint and the words".
  It has `border: 1px dashed var(--fg-subtle)` (3.6:1 on `--surface` in light, 4.0:1 in dark),
  `border-radius: var(--r-md)` and `margin: var(--s-3) var(--s-4)`. While it is the target
  (`[data-over]`) the border is solid `--accent` on `--accent-soft`, with `--fg` text. The same width, so the
  box does not move.
- **Motion.** The sortable row transition keeps `reducedMotion ? null : undefined`, and the copy has
  `dropAnimation={null}`. The one CSS transition, on the area's border and background colours, takes
  `--dur-fast` / `--ease-out` inside the file's `@media (prefers-reduced-motion: no-preference)` block. The
  motion grep gate covers `web/src/edit`.
- **Coarse pointer.** Unchanged: the handle keeps `touch-action: none` and its 44 px touch area
  (`components.css`). A touch elsewhere scrolls, and auto-scroll works for touch drags (spike).

### Announcements and instructions

**Decision**: dnd-kit's one live region (`container: document.body`) speaks every drag. `name` is the
clip's name as its row named it at the lift (`nameOf`, the editor's `nameNow`). `p`/`n` are within the own
chapter, as today. `T` is the target chapter's heading (`headingIn`). `m` is the number of clips `T` plays.

| Moment | Own chapter (unchanged words) | Another chapter |
|---|---|---|
| lift | `Picked up {name}, position {p} of {n}.` (+ ` It is missing, so it stays in “{own}”.` for a missing clip while more than one chapter is listed) | — |
| new target | `{name} is over position {p} of {n}.` | `{name} is over “{T}”, position {k} of {m + 1}.` |
| over a deleted placeholder | — (over `null`: silent, as today) | — |
| drop | `{name} moved to position {p} of {n}.` / `{name} dropped at position {p} of {n}, unchanged.` | `{name} moved to “{T}”, position {k} of {m + 1}.` |
| drop over nothing, or refused by a lock | `{name} dropped at position {p} of {n}, unchanged.` | same |
| cancel | `Move cancelled. {name} is back at position {p} of {n}.` | same |

The instructions are today's, plus one sentence while more than one chapter is listed: "Press Space or Enter
to pick up a clip, the Up and Down arrows to move it, Space or Enter to drop it, Escape to cancel. Past a
chapter's first or last clip, the arrows move it into the chapter before or after."

**Rationale**: The words within a chapter are spec-fixed ("The event page reorders clips within a
chapter"). "Of m + 1" counts the clip that joins, as the Move clips announcement counts the target after the
move. Naming the clip as it was lifted keeps one name through the drag; the row may take a path name in its
new chapter (`clipNames`), which its row then shows.

### Focus and scroll after a drop

**Context**: A cross-chapter drop unmounts the row, and its focused handle, in the source list and mounts a
new one in the target. dnd-kit restores focus only after a keyboard drag. The spike's pointer drops left
focus on `<body>`, which "Edit mode keeps keyboard focus in view and never drops it" forbids.

**Decision**: `ChapterDrag` owns the drop's follow-up for every drop. The rows' button moves keep
`ClipOrderList`'s own effects. `onDragEnd` records `{ identity, to, across }` before it dispatches. Then:

- A **layout effect** keyed on the orders finds the row in `[data-chapter-key="<to>"]` by `dataset.identity`.
  For a drop into another chapter it focuses the row's `.drag-handle` with `preventScroll`. Focus moved by
  script after a pointer interaction does not match `:focus-visible`, so no ring flashes. A keyboard drop
  then gets dnd-kit's own `RestoreFocus` on the same handle a frame later, which is harmless. The effect notes
  the row.
- A **passive effect** scrolls that row `scrollIntoView({ block: 'nearest' })` after the editor's layout
  effect has published the save bar's height. That is today's "first drop" path (edit-mode-polish, "The
  first drop keeps its row in view"), moved up one component.

`ClipOrderList`'s `dropped` ref and its use in the two effects are removed.

### The Cuts panel follows the clip

**Decision**: Nothing new. The row mounts anew in its target `ClipOrderList` and reads `panels.get(identity)`
for `open` and the typed fields (G2's store keyed by identity, built for Move clips). Its cuts are
`cutsOf(baseCuts, cuts, identity)`, keyed by identity. `typed` is keyed by identity, so the save bar keeps
naming the clip (`nameNow`, by its new chapter). The copy never shows the panel.

### The hint and the words

**Decision**: the hint (`EventEditor.tsx`, while there is a detail):

- one listed chapter: "Drag a clip by its handle, or use its arrows. To split the event into chapters, use
  Add chapter below the chapters; clips can then be dragged between them."
- more than one: "Drag a clip by its handle, or use its arrows, to reorder it. Drag it into another chapter
  to move it there; a chapter's Move clips moves several clips at once." The arrows (Move up / Move down)
  never leave the chapter, so the hint does not offer them for a move between chapters.
- a missing clip present: "A missing clip is not on disk and stays in its chapter: restore the file, or
  remove it from reel.yaml." The ignored and NEW sentences are unchanged.

The empty chapter's area (`ClipOrderList`):

- `NO_CLIPS`: "No clips. Drag clips here, or move them here with another chapter's Move clips. A chapter
  without clips is left out of the movie."
- `NO_CLIPS_PLAYED`: the same, starting "It plays no clip."

**Rationale**: Follow-up #1: the one-chapter case is where the operator could not find chapters. Add chapter
is below the last chapter, so the hint says where it is.

### Render budget: what one `DndContext` re-renders

**Context**: The brief asks that drag start, a new target and a drop stay within today's budgets on the
400-clip fixture, and that "one DndContext must not re-render every row on each drag-over".

**Explored** (spike, numbers above):

- **Per pointer move with no new target**, only the dragged row (it reads the transform), the copy, and the
  `SortableContext` providers re-render. The providers' children are unchanged elements. No other row
  re-renders.
- **Per new target**, every row's sortable shell (`ClipRow`'s function body) re-runs. That covers a keyboard
  step and a pointer crossing a row's midpoint. dnd-kit 6 publishes `over` through `InternalContext`, which
  every `useDraggable` / `useDroppable` reads. No `memo` boundary can stop that short of not using
  `useSortable` per row. The work stays in the shells:
  - `MoveButtons`, `CutsToggle`, `CutsPanel` and `ClipThumb` do not re-render, and neither does
    `RowBody`, except for a row whose shown position changes (within the own chapter, as today)
  - no `ClipOrderList` re-renders, and neither does `EventEditor`
  - the measured cost is 15–38 ms for 408 rows

  Today a step inside a 400-clip chapter re-runs the same 400 shells. What is new is that a drag in the
  3-clip `Kväll` now also re-runs the other chapter's 400.
- **Avoiding it** would take one of two things. One is rows without `useSortable` (a hand-rolled drag), which
  gives up the keyboard sensor and sortable's displacement that the spec relies on. The other is a different
  library, which D-8 and the plan rule out.

**Decision**: Accept the shells and hold everything else. The budgets, measured in tasks 4.3 on `Stor dag`
(403 rows):

| Moment | Budget | Today's reference |
|---|---|---|
| lift (Space → "Picked up …" in the live region) | < 200 ms | spike 56–94 ms |
| keyboard step, within the 400 and across into `Kväll` | median < 100 ms over 10 steps | C4's budget; spike 15–38 ms |
| pointer move, no new target | ≤ 1 `ClipRow`, 0 `RowBody`, 0 `ClipOrderList`, 0 `EventEditor` per commit | spike 1 / 0 / 0 |
| new target | `RowBody` only for rows whose shown position changes (≤ 2 per keyboard step inside the own chapter, 0 for a target in another chapter), 0 `ClipOrderList`, 0 `EventEditor` (`ClipRow` = every row, recorded) | spike 408 / 0 / 0 (its rows show no position) |
| drop (release → announcement and the new order shown) | < 200 ms; `ClipOrderList` renders exactly the 2 chapters involved (`Stor dag` has only those two; see below) | spike 29 ms |
| pointer drag over 20 rows after the lift | no long task ≥ 100 ms | spike none |
| typing in Title | < 50 ms per keystroke (lists do not re-render) | G1 / G2 |

The counts come from a commit hook installed ad hoc by Playwright (`add_init_script`) before React loads,
never committed. It is a minimal `__REACT_DEVTOOLS_GLOBAL_HOOK__` with `supportsFiber`, `inject` and
`onCommitFiberRoot`.

- On each commit it walks the fibers that rendered, skipping a subtree whose `child` is its alternate's
  `child` (React bailed out of it).
- It counts function fibers with `flags & 1` (PerformedWork) by their **direct** host child:
  - `li.clip-item` is a `ClipRow`
  - `span.clip-pos` is a `RowBody`
  - `section.edit-chapter:not([data-deleted])` is a `ClipOrderList`
  - `div.event-editor` is the `EventEditor`

The editor passes `lastMoved` to every `ClipOrderList` (main today), and a drop sets it, as a reorder does.
On an event with a third chapter, that chapter's list therefore also re-renders at a drop: its map runs, but
none of its rows does (`memo`). This is the same as a reorder today, and this change keeps it. The drop budget
is measured on `Stor dag`, which has only the two chapters involved.

In the spike this method matched in-app counters exactly. When a budget is exceeded, the implementer stops
and reports. They do not add virtualisation, a `memo` that changes behaviour, or a dependency.

**Rationale**: The brief's intent, no full re-render per drag-over, holds for everything that costs: no
list map, no row body and no editor. The literal reading, no row shell either, is not reachable with the one
drag-and-drop library and its sortable preset. The proposal states this, and it is an open question for the
supervisor below.

### Files

| File | Change |
|---|---|
| `edit/dragSlots.ts` (new, pure, `import type` only) | `Slot`, `DragModel`, `dragModel`, `slotsOf`, `stepSlot`, `overIdOf`, `slotOf`, `pointerTarget`, `CHAPTER_DROP` (`'/chapter/'`), `DELETED_DROP` (`'/deleted/'`) |
| `edit/ChapterDrag.tsx` (new) | `ChapterDrag`: the `DndContext`, sensors, collision adapter, keyboard getter, modifiers, announcements and instructions, `DragOverlay` + `DragPreview`, drop dispatch, focus and scroll after a drop; `useReducedMotion` moves here from `ClipOrderList.tsx` and is exported |
| `edit/drag.css` (new) | the copy, the line before a row and after the last, the empty chapter's area |
| `edit/ClipOrderList.tsx` | no `DndContext`, sensors, modifier, announcements, `onDragEnd` or `dropped`; `SortableContext id={chapterKey}`; `ChapterDrop`; `data-drop-before` on `ClipRow`; the empty-chapter words |
| `edit/ChapterTools.tsx` | `DeletedChapter` registers `/deleted/<key>` (`ref={setNodeRef}`) |
| `edit/EventEditor.tsx` | `clip-drop` action; `ChapterDrag` around the chapter sections with its props; `onDropInto`; the hint |
| `edit/draft.ts` | `moveClipTo` |
| `edit/edit.css` | `.clip-item[data-dragging]` becomes the placeholder; `.edit-chapter { position: relative }` |
| `web/README.md`, `docs/high-level-design.md` | docs |

`ChapterDrag`'s props, all stable across a metadata keystroke except `children`:

```ts
export function ChapterDrag(props: {
  /** The draft's orders, and the listed (not deleted) chapters in the order shown. */
  orders: Orders
  listed: readonly ChapterKey[]
  /** A clip not on disk (missing): it stays in its chapter. */
  staysHome: (identity: string) => boolean
  /** The clip's name as its row names it now (`nameNow`), and a chapter's heading (`headingIn`). */
  nameOf: (identity: string) => string
  headingOf: (key: ChapterKey) => string
  /** `listsLocked`: a save in flight or a Move clips pending. */
  locked: boolean
  onReorder: MoveHandler
  onDropInto: (identity: string, from: ChapterKey, to: ChapterKey, at: number) => void
  /** The editor's root, where the moved row is found after a drop. */
  rootRef: RefObject<HTMLElement | null>
  children: ReactNode
}): ReactNode
```

### HLD

D-13 keeps its date and change. Its sentence "Dragging across chapters stays v3." is **replaced**, not left
beside the new one, which would contradict it. The new sentence is: "Dragging a clip into another chapter
followed in `cross-chapter-drag` (2026-10-01), at the operator's request, beside Move clips: any position, an
empty chapter too, by pointer and keyboard. A missing clip stays in its chapter." §4.10's v1 bullet reads
"**chapter edits, Move clips and dragging clips between chapters** (**D-13**)". The v3 line drops "drag across
chapters". Slice row D gains "`cross-chapter-drag` lets a clip be dragged into another chapter (D-13)".
No new D-n: the decision is D-13's, carried further.

### Verification fixtures

The implementing agent's own environment (dev-env runbook §9): `SLUG=cross-chapter-drag`, `N=28`, database
`arel_cross_chapter_drag`, library `../dev-cross-chapter-drag`, `serve` on port **8128**, no worker. In that
library copy only:

- `2024/2024-09-15 - Stor dag`, by the recipe of `archive/2026-09-30-event-edit-screen/design.md`
  ("Verification fixtures"): 400 symlinks `c0001.mp4`…`c0400.mp4` to one cut clip, plus `Kväll/k001.mp4`,
  `Kväll/k002.mp4`, `Kväll/k003.mp4`, and no `reel.yaml`. The page seeds two chapters, the event's own
  (400) and `Kväll` (3).
- Normalise before copying (G1's rule): load each `reel.yaml` a check will `diff` (`Två kapitel`,
  `Grillning` in particular), dump it with `YAML()` and `indent(mapping=2, sequence=4, offset=2)`, then take
  the copy. Each `reel.yaml` touched is restored from its copy afterwards and compared with `diff`.

Two containers that share a mount (the node build and Playwright) use `:z`, not `:Z`. In the spike, `:Z`
relabelled the directory for the second container and stopped the first.

## Failure behavior & idempotency

- Nothing renders, enqueues or probes. A drop changes the draft only, and Save is the existing single `PUT`
  with `If-Match`. Every failure path (400, 404, 412 with Reload or Overwrite, 502, no answer, an error in the
  page) keeps the draft, drops included, as today.
- `moveClipTo` is idempotent: a repeated call finds the clip no longer in `from` and returns `draft`. The
  reducer refuses `clip-drop` between unlisted chapters, within one chapter, and while a save is in flight.
  The editor refuses it while a Move clips is pending and for a clip not on disk. Each refusal moves nothing,
  and the drop is announced as unchanged.
- The engine still refuses what the GUI never sends: a clip in two chapters, or an ignored clip listed.
  `moveClipTo` removes before it inserts, so a clip cannot be in two chapters. Ignored clips are never
  draggable.
- A drag in progress when the window is resized or hidden is cancelled by dnd-kit, and nothing moves. The
  unsaved-changes question opening mid-drag (the browser's Back) does not cancel a pointer drag: a release
  afterwards is an ordinary edit, which Discard then discards.
- Re-running a save of the same draft is a no-op on disk (unchanged).

## Risks / Trade-offs

- **[Every row's shell re-runs on a new target, on every chapter]** → It is the same work a step inside a
  400-clip chapter does today, and it is bounded and measured (tasks 4.3). No body, list or editor re-renders.
  If a budget fails, the implementer stops and reports.
- **[Auto-scroll across 400 rows is slow (≈ 14 s at 1280 × 900 in the spike)]** → dnd-kit's default speed is
  kept. Move clips is the fast path for long distances, and the hint names it. Tuning `autoScroll`
  acceleration is a follow-up if the operator asks.
- **[A missing clip's lift words may be cut short]** → dnd-kit's live region is atomic, and the first "is
  over position …" follows the lift at once (today too). The stays-home note is also in the hint, and the
  keyboard sequence never offers another chapter.
- **[The copy is narrower than the row]** → On purpose: it ends at least 3rem before the row's end at every
  width, so the line stays visible there and its dot marks it. At 320 px the badge wraps under the name,
  and the copy is two lines tall.
- **[A target row under a sticky chapter heading]** → When the target chapter is scrolled so its heading
  sticks over its first rows, the line of a gap there can sit under the heading. The copy's badge still
  names the chapter and position, and the announcement says it.
- **[Pointer in the gap between panels picks the nearest chapter]** → The line or area shows the target before
  the release, and a deleted placeholder is never a target.
- **[`ChapterDrop` attaches its droppable in a passive effect]** → A drag cannot start before the first paint,
  so the rect exists when measuring starts (spike, StrictMode included).
- **[Legacy dnd-kit has had no release since 2024-12]** → Unchanged from D-8. Everything used here is public
  API of the installed versions.

## Migration Plan

- None: no dependency, no schema. Rebuild `web/dist` with the `web/README.md` container command, and `serve`
  mounts it as before.
- Rollback: revert the web change. Files saved meanwhile are ordinary editorial writes.

## Open Questions

- **Re-render reading of the brief.** "one DndContext must not re-render every row on each drag-over" is met
  for row bodies, lists and the editor, but not for the rows' sortable shells (see "Render budget"). The
  design proceeds on that reading. If the supervisor wants the literal one, the alternative is a hand-rolled
  pointer and keyboard drag without `useSortable` rows, and that would be its own change.
