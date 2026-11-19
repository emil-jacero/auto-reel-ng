## Context

- **The selection is one target** (`edit/workspace/selection.ts`): `none | clip | cut | card | suggestion`, held beside
  the draft in `EventDetail` and read through `useSelection`. `keptSelection` drops a target the event no longer lists.
  `selectState` replaces it, and pressing the same clip again bumps `again`, so the track scrolls back to it.
- **The marks are a second set**, held in the editor's state (`state.marked`, `edit/marks.ts`). Three actions read
  them from the state rather than from the dispatch:
  - `marked-move` (Move marked to…, through `moveMarkedToEnd`), dispatched in `startTransition`, so `movePending`
    makes `listsLocked` true while it is applied;
  - `group-drop` (the bin's group drag, through `groupOf` and `moveGroup`);
  - `rotate` with `identities[]` (Rotate marked).
- **The track.**
  - A clip block is `.tl-clip-press` (`role=button`, `aria-pressed`): Enter/Space select, a double press places the
    playhead.
  - `ClipDrag` turns a press that moves 3 px into a drag of one clip. Others shift live by the dragged block's width
    (`flatMove`, `shiftOf`). A release over the bin (`overBin`) ignores the clip.
  - Alt+arrows go through `moveSelected(way)` (lifted by `editor-shortcuts`).
- **Today's bin rows** (`ClipOrderList`, `li.clip-item`) select on a click whose target is not a control.
- **The clip menu** (`clip-context-menu`): `clipMenu(facts)` builds the items for one identity. `menuSelects` decides
  whether opening selects. `MENU_LOCKED` is the lock note.
- **The Clip tab** (`timeline/ClipTab.tsx`) is drawn by the Timeline for one `TrackClip`, into the inspector by a
  portal.

## Goals / Non-Goals

**Goals:**
- A selection of several clips that every surface reads the same way.
- Group edits that ship their clips in the action, so the marks' actions stay untouched until `plain-clip-bin`
  deletes them.

**Non-Goals:**
- Changing the marks, their actions or their requirements.
- A selection model for the plain list's keyboard: `plain-clip-bin` adds it on top of D1.

## Decisions

### D1. The selection gains a clips kind (`selection.ts`, pure)
```ts
export type Selection =
  | { kind: 'none' }
  | { kind: 'clip'; identity: string }                  // one clip: every existing reader is unchanged
  | { kind: 'clips'; identities: readonly string[]; anchor: string; last: string } // two or more, in press order
  | { kind: 'cut'; identity: string; key: string }
  | { kind: 'card'; chapter: ChapterKey }
  | { kind: 'suggestion'; id: string }

export type Press = 'alone' | 'toggle' | 'range'
export function pressClip(sel: Selection, identity: string, press: Press, order: readonly string[]): Selection
export function selectedClips(sel: Selection): readonly string[]   // [] | [identity] | identities
export function lastClip(sel: Selection): string | null             // the clip pressed last
export function selectionWords(was: Selection, now: Selection, nameOf: (id: string) => string): string | null
```
- **One clip stays `clip`.** Two or more are `clips`. `pressClip` and `keptSelection` normalise: a set of one becomes
  `clip`, and an empty set becomes `none`. So every reader of `kind === 'clip'` keeps working, and only the readers that
  need a set call `selectedClips`.
- **Anchor.** For `clip` it is the clip itself. `toggle` sets it to the toggled clip, and `range` keeps it. A set that
  a toggle normalises down to one clip (or to none) keeps no anchor beside it: `{a, c}` with `a` taken out is the clip
  `c`, so a following Shift press ranges from `c`, not from `a`. A clip alone is its own anchor, and a deselected clip
  is a poor place to range from, so this is accepted rather than held in extra state.
- **Range.** It runs from the anchor to the pressed clip in `order`: the track passes the drawn order, the bin its
  rows' order. An anchor that is not in `order` (the clip left the track) makes the range the pressed clip alone.
- **Toggling from a cut, card or suggestion** starts a set of the pressed clip alone.
- **Tests.** `selection.test.ts` covers each press from each kind, the normalisation, `keptSelection` on a set, and the
  words of D6.

### D2. Group edits ship their clips (`EventEditor.tsx`)
```ts
| { type: 'selection-move'; identities: readonly string[]; to: ChapterKey }  // Move to…: end of `to`
| { type: 'selection-drop'; identities: readonly string[]; dragged: string; to: ChapterKey; gap: number }
| { type: 'ignore-many'; identities: readonly string[] }
```
- **Reuse.** `selection-move` and `selection-drop` reuse `moveMarkedToEnd` and `moveGroup`, with the shipped set in
  place of `state.marked`. Both drop the identities that a listed chapter does not play (`groupOf`'s rule) and the
  ones that are not on disk, so a stale selection cannot move a clip it should not. A missing clip stays in its
  chapter's order, so the order alone cannot say so: each of the three actions also carries `onDisk(identity)`, built
  by the dispatcher from the clips it knows (as `rotate` takes its predicate), and `ignore-many` applies the existing
  `ignore` step to each clip that passes, in one draft edit. Rotate already takes `identities[]`.
- **The marks.** None of the three touches `state.marked`, except that `afterMove` unmarks a moved clip, as a drag of
  a marked clip does today.
- **Undo labels.** `describeEdit` gains "move of N clips", "ignore of N clips" and "rotation of N clips".
- **Pending.** Move to… with several clips dispatches in `startTransition` like `marked-move`, so the existing
  `movePending` lock covers both. One move of one clip is a plain dispatch.
- **Tests.** `groupMove.test.ts` gains the shipped-set cases. `selectionEdit.test.ts` drives `selectionStep` and
  `selectionLabel` and checks that one `ignore-many` is one history step. `EventEditor.tsx` cannot be imported under
  Node (TSX), so its wiring (`describeEdit`, `afterEdit`) is covered by the Playwright pass of tasks 2.x and 3.1, which
  reads the Undo labels ("Undo ignore of 2 clips", "Undo move of 2 clips").

### D3. Pressing on the track and in the bin
- **Modifiers.** `pressOf(event)` gives `toggle` for Ctrl or Meta, `range` for Shift, and `alone` otherwise. On
  macOS Ctrl+click is a right-click: it opens the menu (`clip-context-menu` D4), and Cmd is the toggle there.
- **Track block.** On a block that is one of several selected, `pointerdown` does not change the selection. The
  release without a drag applies the press. Enter, Ctrl/Cmd+Enter and Shift+Enter map to `alone`, `toggle` and
  `range`. Space keeps `editor-shortcuts`' rule: after keyboard focus it selects the clip alone.
- **Today's bin rows.** `li.clip-item`'s click passes `pressOf(event)` and the rows' page order. A row's own controls
  (handle, mark, Watch, Cuts) keep their clicks.
- **Shown.** `aria-pressed` and the outline follow `selectedClips(sel).includes(identity)`, read from a `Set` built
  once per selection. Scrolling into view follows `lastClip`.

### D4. The group drag (`ClipDrag.tsx`, `clipDrag.ts`)
- **When.** A press past the 3 px slop on a block whose clip is in a `clips` selection drags the group: every selected
  clip that the track draws, in drawn order.
- **No live room.** No block shifts. The held blocks get `data-held` (dimmed) and the tip names the count and the
  slot.
- **The slot.** A new pure `groupSlot(chapters, group, x)` computes the slot over the drawn order without the group.
  The run then goes before the first clip at or after the gap that is not in the group, which is `moveGroup`'s rule.
  Words: "3 clips · Before s1710001.mp4", "3 clips · End of Main".
- **Release.** On the track it dispatches `selection-drop`, or nothing with "N clips dropped, unchanged." when
  `isOwnPlace` holds for the run. Over the bin it dispatches `ignore-many`. Elsewhere, or on Escape or a right-click,
  it cancels.
- **One clip.** A drag of an unselected block is today's drag, and it selects that clip alone.

### D5. The Clip tab for several clips, and Move to… (`ClipTab.tsx`)
- **Which tab.** The Timeline's clip panel renders `ClipGroupTab` when `selectedClips(sel).length > 1`, and `ClipTab`
  otherwise.
- **`ClipGroupTab`:**
  - a heading "N clips selected" and up to five names, then "and N more";
  - `RotateButtons` with the identities on disk and in a chapter (Rotate marked's rule);
  - **Move to…**;
  - **Ignore clips**.
- **Move to…** is one component used by both tabs:
  - a native `select` and a Move button, the Move marked to… pattern with its `aria-disabled` reasons (`moveReason`
    words);
  - for one clip, its own chapter is left out and Move dispatches today's `clip-drop` at the end of the chapter (the
    menu's Move to);
  - for several, all listed chapters are offered and Move dispatches `selection-move`.
- **After.** Focus stays on the pressed control. After Ignore clips the selection is cleared, since its clips are no
  longer on the track.

### D6. Words and announcements
- **One status.** The selection's polite status says "3 clips selected." for a change to a set. A toggle says
  "s1710003.mp4 added. 3 clips selected." or "… taken out. 2 clips selected.", and so does the one that takes a set of
  two down to one clip ("… taken out. 1 clip selected."). Any other change to one clip keeps today's words.
- **Alt+arrows with a set:** "Alt and an arrow move one clip. Move to… in the Clip tab moves the selected clips."
- **The lock words** name no marks, so they stay true when `plain-clip-bin` removes them:
  - `MENU_LOCKED` becomes "Clip edits wait for the save or the move of several clips to finish.";
  - `MOVE_LOCKED` becomes "Moving clips waits for the save or the move of several clips to finish.".
- **`SHORTCUTS`** gains three rows (`editor-shortcuts`):
  - "Ctrl+click or Cmd+click a clip: Add it to the selection, or take it out" (Mouse);
  - "Shift+click a clip: Select the clips from the last one pressed" (Mouse);
  - "Ctrl+Enter or Shift+Enter on a clip: The same from the keyboard" (Editing, `focused`).

### D7. The menu acts on the selection (`clipMenu.ts`)
- **Facts.** `ClipMenuFacts` gains `targets: readonly string[]`: the selection's clips when the opened clip is one of
  them, else the clip alone.
- **Rules.** `menuSelects` returns false for a clip in a `clips` selection.
- **Items for several targets:**
  - the title is "N clips";
  - Rotate goes to `onRotate(targets)`;
  - Move to «chapter» covers every drawn chapter and dispatches `selection-move`;
  - "Ignore N clips" dispatches `ignore-many`;
  - Cut and Poster carry the "Select one clip to …" reasons.
- **Focus after a group ignore** goes to the clip drawn after the last target (`focusAfter` on the run's end).

## Research & Decisions

### A new selection kind vs a list in `clip`
**Context**: many readers test `sel.kind === 'clip'` and read `sel.identity`.
**Explored**: (a) change `clip` to hold a list; (b) add `clips` for two or more, with one clip staying `clip`.
**Decision**: (b).
**Rationale**: every single-clip reader keeps its type, and only the group readers change. A selection of one is the
common case, and its code paths and tests stay as they are.

### The group drag on the track: live room or a line
**Context**: the track's single-clip drag shifts the other blocks live by one width.
**Explored**:
- shift every block by the run's width as the group passes;
- a drop line only, as the bin's group drag and its spec do ("no row SHALL move to make room").

**Decision**: a line only (D4).
**Rationale**: a run of clips that are not contiguous has no single width to open, and collapsing the held blocks
would move the drop targets under the pointer. The bin's group drag was specified this way for the same reason, and
its 150 ms gate is reused.

### Keep the marks until the old bin goes
**Context**: the operator chose the selection to replace the marks.
**Explored**: remove the marks here, or keep them until `plain-clip-bin`.
**Decision**: keep them. The two sets are independent.
**Rationale**:
- Removing them here rewrites four requirements and the bin's toolbar, which `plain-clip-bin` deletes anyway.
- Touch has no Ctrl or Shift, so until the plain list lands the marks stay the only way to move several clips by
  touch.
- Keeping both costs nothing: they share no state.

### Who moves several clips with the keyboard
**Decision**: the Clip tab's Move to… and the menu. Alt+arrows move one clip only.
**Rationale**: "one place left" is undefined for a set that is not contiguous, and silently moving only the last clip
would surprise.

## Risks / Trade-offs

- [Two group mechanisms at once (marks and selection) may confuse] → They look different (a checkbox vs an outline),
  each Move names its own set ("Move marked to…" vs "Move to…"), and the overlap lasts only until `plain-clip-bin`.
- [Ctrl+click on macOS is a right-click] → Cmd is the toggle there. The shortcuts list says "Ctrl+click or Cmd+click".
- [`clip-context-menu`'s text may change before it is archived] → Task 0.2 copies its archived requirements into this
  change's MODIFIED blocks again before any code is written.
- [Shift+click across 400 clips re-renders every block and every bin row] → `aria-pressed` reads a `Set`, and blocks
  are memoised by pressed state. Measured in task 3.1, the bin rows were the cost, not the blocks:
  - a row's own style is costly to recalculate (about 80 µs), so a selection state on the `li` costs 30 ms for 400
    rows: the state sits on leaves (the ground `.clip-sel`, the name), never on the row;
  - only the row of `lastClip` scrolls into view, not every newly selected row;
  - the bin follows the selection in a deferred render (`useDeferredValue`), after the track and the inspector paint.

  The 100 ms gate (task 3.1) checks it.

## Failure behaviour

These are browser edits of the draft. Nothing is written until Save, and Save's failure behaviour is unchanged. A group
edit whose clips are gone (a re-read dropped them) moves what remains, or announces "Nothing moved." and changes
nothing.
