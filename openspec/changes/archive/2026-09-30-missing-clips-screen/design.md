## Context

See proposal.md, "Why". This change starts from `main` once both of its gates are archived there.

- **`event-edit-screen` is on `main`.** It is archived as `2026-09-30-event-edit-screen`, and its review fixes
  landed with it: `c8bc64b`, and `1995185`, which moves the move-focus scroll into a passive effect. The editor
  below is cited from `main` at `1995185`.
- **`render-progress-screen` is on `main` too** (`2026-09-30-render-progress-screen`, at `ac8154a`). It
  wired the Edit-mode seam (its task 7.1). The render region below was first cited from its pre-rebase
  working tree; task 1.1 re-checked it on `main` at `ac8154a`, where the seam sits in `EventFacts`
  (`EventDetail.tsx:358`), as described.

Task 1.1 re-checks every name on `main`.

**The editor** (`event-edit-screen`, `web/src/edit/`)

- **`draft.ts`** holds the model as pure functions. It has only `import type` imports, so a scratch script can
  run it under Node's type stripping.
  - `editableChapters(detail)` (`:40`): a chapter's movable identities are all its clips except IGNORED ones,
    so MISSING clips are movable. `detailMatchesDocument` (`:66`, with `LISTED` at `:57`) requires each
    document chapter's listed clips, ACTIVE or MISSING, to come first.
  - `buildWriteBody(read, original, next, metadata)` (`:153`) sends `look`, `ignore` and `clips` back as read
    (`clips` is the per-clip properties, verbatim, `:188`). Through `writtenFromView` (`:133`), a chapter
    whose order differs from the original is written from the view, which adopts its NEW clips
    (`adoptedNewCount`, `:194`).
  - `isDirty` (`:208`), `moveClip` (`:218`) and `movedSet(original, next, lastMoved)` (`:281`). `movedSet`
    uses `keptInPlace`, a maximum-weight increasing run that prefers clips at their original index, and then
    the run without `lastMoved`.
- **`EventEditor.tsx`**:
  - a reducer (`reduce`, `:131`) over `Ready` (`:79`: `read, etag, original, orders, lastMoved, metadata,
    dateIncomplete, resets, pressed, problem, refusal, answers`), with the actions `move`, `field`,
    `date-validity`, `reset` (`:184`), `save-start` and `save-failed`
  - `afterEdit` (`:123`), which retires a failure once the draft is back to what was read
  - `edited` (`:470`), which is `isDirty(…)`
  - `summarize(changed, dateIncomplete, moved, adopted)` (`:331`), which writes the save bar's summary
  - `submit` (`:529`), which builds the body (`:536`)
  - `announce` (`:519`), which sets the one status region: cleared, then set a frame later
  - one `ClipOrderList` per chapter (`:688`)
- **`ClipOrderList.tsx`**:
  - `RowBody` (`:118`, memoised): the position; the file cell `.clip-file`, holding the name and the
    "was N" or "moved" badge; then `ClipFacts`
  - `ClipRow` (`:206`): `useSortable`, the handle, `RowBody` and `MoveButtons`
  - `IgnoredRow` (`:274`): a `drag-slot`, `RowBody` with no position, and an empty moves cell
  - `ClipOrderList` (`:286`): `movedSet` over `original` (`:324`); one `DndContext` with an
    `<ol className="clip-order">` (`:448`); then the ignored tail, an `ignored-caption` followed by
    `<ul className="clip-order clip-ignored">` (`:471-482`)
  - A move by button records `focusAfterMove`. A layout effect keyed on `order` (`:385`) finds the row in
    `listRef` (the `<ol>`) and focuses its button with `preventScroll`. A passive effect after it (`:404`)
    scrolls the button into view, once the save bar's height is published.
- **`edit.css`** (`@layer screens`):
  - each `.clip-item` is a seven-column grid: handle, position, file, status, size, time, moves
  - `.clip-file` is a wrapping flex cell
  - `.ignored-caption` and `.clip-ignored .clip-item` style the ignored tail
  - below 54rem (an `@container` query), a row takes two lines

**The render region** (`render-progress-screen`)

- **`jobs/RenderControl.tsx`** takes `blockedReason?: string` (`:111`). It sets
  `canRender = !active && blockedReason === undefined` (`:273`) and shows the reason as `.render-blocked`
  inside the region's `role="status"` paragraph (`:286`). Progress, Cancel and notices do not depend on it.
- **`events/EventDetail.tsx`**: `EventFacts` mounts `RenderControl`. On `main`, `EventFacts` already takes
  `{ event, editing }` from `event-edit-screen`. The Edit-mode seam is wired by `render-progress-screen`, which
  archives second (its task 7.1). It passes `blockedReason={editing ? 'Save or leave Edit mode to render' :
  undefined}`.
- **`jobs/LiveJobCell.tsx`** renders the row's job cell: `{staleness.stale && !active && <RowRender …/>}`
  (`:146`). When a focused Render leaves, it hands focus to the row's link.
- **`jobs/labels.ts`** holds the sentences the page and the rows share: `NOT_QUEUED`, `SCAN_FAILED` and
  `COLLISION_FIX`.
- **`jobs/jobs.css`** (`@layer components`) is loaded on every page through the shell's `JobsIndicator`. It
  defines `.render-blocked` (`:220`), `.live-job` (`:251`) and `.btn-compact` (`:309`).
- **`events/EventList.tsx`**: `EventRow` shows the `N missing` badge in the clips cell (`:72-77`) and mounts
  `LiveJobCell` in the job cell (`:82`).

**The service** (`main`, which this change does not touch)

- `EventDetailOut.missing` lists the missing identities, sorted, and `EventSummaryOut.missing_count` counts
  them (`api/schemas.py`). `ClipOut` carries no per-clip properties, so neither read says whether a missing
  clip is excluded.
- `PUT …/reel` calls `event/editorial.py` `apply_editorial_write`:
  - `_apply_chapters` calls `_rewrite_identity_list`. That leaves an unchanged chapter untouched. In a changed
    chapter it keeps each remaining entry's comments and writes none for a removed entry.
  - `_apply_clips` rebuilds the `clips` map from the body and drops the section when it is empty.
  - `build_document` calls `reel/schema.py` `_validate_cross_references`, which refuses a `clips` entry that no
    chapter references ("dangling clip properties"). The service answers 400.
- A render probes every referenced clip that is not excluded (`cli/build.py` `_probe_clips`):
  - a missing clip raises `ProbeError("File does not exist: …")` (`probe/media.py:65`)
  - an excluded one is not probed

## Goals / Non-Goals

**Goals:**

- Let the operator take a MISSING entry out of `reel.yaml` from Edit mode. The removal goes through the same
  draft, Undo and Reset, save bar, `If-Match` save and unsaved guard as every other edit.
- Make neither screen offer a render that must fail because of a missing clip, and have each say why in
  words.
- Keep every mechanism of the two gates as it is, and add to them rather than rework them: the positions,
  `movedSet`, the dnd-kit list, the busy lock and the Edit-mode seam.

**Non-Goals:**

- The proposal's non-goals, plus three design-level ones:
  - no change to `detailMatchesDocument`, or to the conflict and overwrite paths
  - no change to `SaveBar.tsx`, which shows the summary string it is given
  - no change to `RenderControl.tsx`, whose `blockedReason` already does what the page needs

## Research & Decisions

### What the service does with a removed entry

**Context**: No API change is allowed here. If a `PUT` could not remove a MISSING entry, this change would
have to stop, so the real API was checked before designing.

**Explored**: On 2026-09-30 the check ran against `auto-reel serve` on port 8113, over this session's own
dev-library copy (`scripts/make_dev_library.py`, with its own database). A scratch script, not committed,
did the following: GET `…/reel`, then PUT the document back under `If-Match` with one identity left out of its
chapter, then read the detail and the list. The results:

- **`2024-09-01 - Sommarlov`**, leaving out `borttagen.mp4`: **200**.
  - `diff` shows exactly one line gone from `reel.yaml`, `- borttagen.mp4  # MISSING`.
  - The detail answered `missing: []` and the list `missing_count: 0`, both with `stale: no_manifest`.
  - A worker (`--device cpu`) then rendered the event: `done`, and it now reads as fresh.
- **`2024-09-02 - Två saknade`** (ad hoc, see "Verification fixtures"):
  - Leaving `Kväll/gone-b.mp4` out of its chapter but keeping its `clips` entry (a trim): **400**, "dangling
    clip properties for 'Kväll/gone-b.mp4'; no chapter references this identity". Nothing was written.
  - Leaving out both: **200**.
    - the `clips:` section is gone, since it held only that entry
    - `Kväll` lists `Kväll/s1710003.mp4`
    - the root chapter, including `gone-a.mp4   # moved to the NAS`, is byte-identical
  - A second PUT leaving out `gone-a.mp4` then gave `missing: []`.
  - Before the removals, the event's job failed with `File does not exist: …/2024-09-02 - Två
    saknade/gone-a.mp4`.

**Decision**: Build on the existing write. A removal is a complete-state PUT in which the chapter no longer
lists the clip and the `clips` map no longer holds that clip's entry. No API change.

**Rationale**:
- This is exactly the write contract of `editorial-write-api` (D-E1, D-E2): the body is the complete desired
  state.
- Every other entry keeps its comments, through the `editorial-chapter-roundtrip` fix.

### The write body

**Context**: `buildWriteBody` sends `read.clips` back verbatim. After a removal, that would leave a
properties entry for a clip no chapter lists, which the service refuses.

**Explored**: Three options:
- keep `clips` verbatim, which is refused with a 400 (measured above)
- send `clips` empty, which would also drop every other clip's trims
- leave out only the removed clips' entries

**Decision**: `buildWriteBody(read, original, next, metadata, removed: ReadonlySet<string>)`:

- **Chapters**: the logic is unchanged. A removal takes the identity out of `next` (see "The draft"), so the
  chapter's order differs from `original`. `writtenFromView` therefore writes that chapter from the view, and
  the clip is not in it. The chapter's other MISSING clips and its NEW clips are written where they stand, as
  for a reorder. The save bar already says "adds N new clips to reel.yaml" through `adoptedNewCount`.
- **`clips`**: it MUST be `read.clips` without the keys in `removed`, and every other entry MUST go back as read:

  ```ts
  clips: Object.fromEntries(Object.entries(read.clips).filter(([identity]) => !removed.has(identity))),
  ```

- **`metadata`, `look`, `ignore`**: unchanged.

**Rationale**:
- The removed clip's properties describe a clip that `reel.yaml` would no longer list, and the engine refuses
  to keep them (as measured).
- Dropping them is not a silent loss. They go with the entry the operator explicitly removed, and the spec
  says so.
- Leaving out the properties of removed clips only keeps "everything else as read".

### The draft: a removal leaves the order

**Context**: Where a removed clip lives in the draft decides how much of `event-edit-screen` must change.
Everything in its list works on `orders`, a chapter's movable identities: the positions, the "N of M"
announcements, the `movedSet` badges, dnd-kit's `SortableContext` items, and Move up and Move down.

**Explored**: Two options:

- **(a) Keep the removed identity in `orders`**, and hold a `removed` set that every consumer filters by.
  This has several costs:
  - moves must map indexes between the filtered view and the full order
  - Move up and Move down must skip removed rows
  - dnd-kit would sort over rows that are not played, so an arrow step over a removed row would change
    nothing that is saved
- **(b) Take the identity out of `orders`**, and work out where it goes back on Undo.

For (b), where Undo puts the clip back was a second question. Two rules were run over `draft.ts` in a
scratch script under Node's type stripping:

- **The index it had when removed**, or the end of the chapter when that is shorter. It fails when two
  removals from one chapter are undone in the order they were made. From `[a, x, y]`, removing `x` (index 1)
  and then `y` (index 1), then undoing `x` and then `y`, gives `[a, y, x]`. That is dirty, with 1 clip counted
  as moved, although the operator moved nothing. The spec's "an undone removal leaves no change to save" would
  then be false.
- **The original order:** put the clip right after whichever of the clips that came before it when Edit mode
  opened comes last in the chapter's order now, or first when none of them is left. Without moves, the order
  is always a subsequence of the original, so this is exactly the original place, and removals undone in any
  order give back `[a, x, y]`. After a move, every clip that came before it and is still listed comes before
  it again. On Sommarlov, removing `borttagen.mp4`, moving `s1710004.mp4` up and undoing gives
  `[s1710004.mp4, s1710002.mp4, borttagen.mp4]`, with `borttagen.mp4` at position 3 again.

  *Review refinement.* The rule as first written ("right after as many clips as came before it … and are still
  in the chapter's order") placed the clip by a count. The review found it wrong once another clip moved: from
  `[a, x, y, b]`, removing `x`, moving `b` to the front (`[b, a, y]`) and undoing gave `[b, x, a, y]`. That
  counted 2 clips as moved and badged `a`, which nobody touched. Placing the clip after its last original
  predecessor gives `[b, a, x, y]` with 1 clip moved, and changes nothing when no clip moved. The model script
  checks both cases; the count rule fails them.

**Decision**: Option (b), with the original-order rule. `draft.ts` gains:

```ts
/** The missing clips the operator removed: identity → its chapter's name. */
export type Removals = ReadonlyMap<string, string>

/** `orders` with `identity` taken out of `chapter`; null when the chapter does not list it. */
export function removeClip(orders: Orders, chapter: string, identity: string): Orders | null

/**
 * `orders` with `identity` put back in `chapter`, right after whichever of the clips that came before it
 * in `original` (the chapter's order when Edit mode opened) comes last in the chapter's order now;
 * first when none of them is left.
 */
export function restoreClip(
  orders: Orders,
  chapter: string,
  identity: string,
  original: readonly string[],
): Orders
```

The rule has one trade-off. Suppose a missing clip is moved, then removed, then restored. It returns right
after the last of the clips it followed when Edit mode opened, not to where it had been moved. The operator's
latest act on that clip was to remove it, and missing clips are rare, so this is accepted. Keeping that move
would take a second, shadow order that holds removed clips, which is option (a) again.

In `EventEditor`:

- **State.** `Ready` gains `removed: Removals`, empty when the document is read.
- **Actions.** The reducer gains `{ type: 'remove'; chapter; identity }` and `{ type: 'restore'; identity }`.
  - `remove` records `identity → chapter` in `removed`. It returns the state unchanged when `removeClip`
    answers null.
  - `restore` looks up the chapter in `removed`, calls `restoreClip` with `state.original.get(chapter)`, and
    deletes the entry. It returns the state unchanged for an identity that was not removed.
  - Both go through `afterEdit`, as `move` does.
  - Both MUST be refused while a save is in flight. The reducer's existing `pressed` check already does this.
  - `reset` also empties `removed`.
- **Save.** `submit` passes `new Set(removed.keys())` to `buildWriteBody`.
- **Dirty.** `isDirty` needs no change. A removal changes the chapter's order. With no move in between,
  removals undone in any order restore it exactly, so they leave nothing dirty (the spec: an undone removal
  "leaves no change to save").
- **Who can be removed.** Only a clip the page read as MISSING. `EventEditor`'s handler MUST check
  `clips.get(identity)?.status === 'missing'` before dispatching, because `draft.ts` knows no statuses. The
  status is the detail's as of the moment Edit mode opened, the same snapshot the editor already shows.

The counts:

- **The summary.** The save bar's summary gains a part, placed after the moves and before the adoption part:
  `removed > 0 && \`${plural(removed, 'missing clip', 'missing clips')} removed\``. `summarize` takes the
  `removed` count as a new argument.
- **Moves.** The moved count and the "was N" badges compare each chapter's order with its original order
  **without the removed clips** (`original.filter((identity) => !removed.has(identity))`). This applies both to
  `EventEditor`'s count and to `ClipOrderList`'s `moved` memo. So a removal on its own never counts as a move,
  never causes one, and `keptInPlace`'s "at its original index" preference compares like with like.
- **The badge.** Its old position stays the position from when Edit mode opened, as the spec requires ("its
  position from when Edit mode opened").

**Rationale**: With option (b), `orders` means exactly what a save writes. Every mechanism of
`event-edit-screen` then keeps working unchanged:
- positions and "N of M" (removed clips are not counted, as the spec requires)
- dnd-kit, and Move up and Move down
- `movedSet`, `writtenFromView` and `isDirty`

### How a removed clip is shown: a "removed on save" list with Undo

**Context**: The plan left two options open: the row leaves the list and an Undo control is offered, or the
row stays in place in a "will be removed" state.

**Explored**:

- **In place**: the row is struck through, and its Remove turns into Undo. Focus never moves, and the clip is
  seen where it was. But a row that stays in the play-order list while not being played is option (a) of the
  previous topic, with all its costs:
  - positions that skip a row
  - a sortable item that cannot move, but that others move past
  - Move up and Move down that must jump over it
  - announcements over a row with no position

  It would also make the numbered list disagree with what Save writes.
- **A tail list per chapter**, like the ignored clips that the editor already lists after the play order.

**Decision**: The tail. `ClipOrderList` renders it after the `<ol>` and before the ignored tail:

```tsx
<p className="removed-caption" id={removedId}>Removed from reel.yaml when you save</p>
<ul className="clip-order clip-removed" aria-labelledby={removedId}>
  {removed.map((identity) => <RemovedRow key={identity} … />)}
</ul>
```

- **`RemovedRow`** mirrors `IgnoredRow`:
  - `<li className="clip-item" data-status="missing" data-identity={identity} data-removed>`
  - a `drag-slot`, `RowBody` with no position and no badge, and an empty `clip-moves` cell
  - it passes `RowBody` whatever `IgnoredRow` passes (see "Files and parallel changes")
  - its file cell holds the **Undo** button
- **Order.** The tail lists its clips in their original order: `original`, filtered to the chapter's
  removals.
- **Header.** The chapter's `panel-meta` gains `· N removed on save`, next to the ignored count.
- **`edit.css`**:
  - `.removed-caption` shares the rule of `.ignored-caption`
  - `.clip-removed .clip-item` shares the dimmed look of `.clip-ignored .clip-item`
  - `.clip-removed .clip-name` is struck through (`text-decoration: line-through`)

  The caption's words, not the strike-through, say what happens.
- **Every clip removed.** Such a chapter keeps its panel. It has no `<ol>`, as for an empty order today, and
  then the tail.

**Rationale**:
- The numbered list stays exactly what Save writes, and nothing in the existing list changes.
- The tail reuses the one pattern the editor already has for "listed but not played".
- Undo stays next to the clip until Save or Reset, and the save bar counts the removal.

### The Remove and Undo controls

**Context**: The plan asks for an explicit, keyboard-reachable control on each MISSING row whose name gives
the file. The row grid and the button styles already exist.

**Explored**:
- **Placement:**
  - a third icon button in the moves column, which would widen that column for every row
  - an eighth grid column, which would collide with `clip-thumbnails-screen`'s grid edits
  - the end of the file cell
- **Form:**
  - an icon-only button, where the icon set has no trash can, and `x` alone reads as "close"
  - icon plus text

**Decision**:

- **Remove** MUST be rendered by `ClipRow` only for a row whose `clip.status === 'missing'`:

  ```tsx
  <button className="btn btn-ghost btn-compact clip-remove" aria-label={`Remove ${name} from reel.yaml`}>
    <Icon name="x" />
    Remove
  </button>
  ```

  It sits at the end of the row's file cell (`.clip-file`). `RowBody` gains an optional `action?: ReactNode`,
  rendered there. `ClipRow` memoises the element (by identity, `locked` and handler), so the rows'
  memoisation is unchanged, and only missing rows carry one.
- **Undo** sits in `RemovedRow`:

  ```tsx
  <button className="btn btn-secondary btn-compact clip-undo" aria-label={`Undo removing ${name}`}>
    <Icon name="rotate-ccw" />
    Undo
  </button>
  ```

- **Names.** Each accessible name begins with the visible words (WCAG 2.5.3, label in name). `name` is the
  identity's last segment, as in every other row label (`Reorder …`, `Move … up`).
- **During a save.** Both buttons MUST be `aria-disabled="true"` while a save is in flight, and their handlers
  return early, like the handles and move buttons of a locked editor. They MUST NOT get `disabled`, so
  `grep -rn ' disabled=' web/src/edit` keeps finding none.
- **Classes and icons.** `.btn-compact` is `render-progress-screen`'s row-sized button class, and both icons
  exist (`x`, `rotate-ccw`). No new icon and no new component class is added.
- **Hint.** When the event lists a missing clip, the editor's hint (the `edit-hint` paragraph in
  `EventEditor`) adds one sentence: "A missing clip is not on disk: restore the file, or remove it from
  reel.yaml."

**Rationale**:
- The file cell already wraps (`flex-wrap`), so the button needs no grid column. The seven-column grid and
  the two-line layout below 54rem stay as they are, so `clip-thumbnails-screen`, which edits that grid, is not
  in the way.
- The label says the scope, "from reel.yaml": nothing on disk is touched. The status "Missing" already
  implies this.

### Focus and announcements

**Context**: The pressed Remove or Undo unmounts with its row, since the row moves between the play order
and the tail.

**Explored**: Two options:
- focus the row that now takes the removed clip's place, which keeps the viewport still but leaves the
  operator far from the Undo control
- let focus follow the clip

**Decision**: Focus follows the clip, as it does for Move up and Move down.

- **Remove.** `ClipOrderList` records `focusAfter = { identity, target: 'undo' }` and calls
  `onRemove(chapter, identity)`. Through the editor's `announce`, it says "`<file>` will be removed from
  reel.yaml when you save."
- **Undo.** `ClipOrderList` records `{ identity, target: 'remove' }` and calls `onRestore(identity)`. After the
  commit, the layout effect announces "`<file>` is back at position N of M.", computed from the new order.
- **The effects.** The existing move-focus layout effect, and the passive scroll effect after it, are now
  keyed on `order` and on the chapter's `removed`.
  - **Where it searches.** It MUST search the whole chapter, not `listRef`, because `listRef` is only the
    `<ol>`. The tail is outside it, and the `<ol>` is not rendered at all once every clip of the chapter is
    removed. So it uses a ref on the chapter's `<section>`, finds the row by `data-identity` (which
    `RemovedRow` also sets), and focuses the target button.
  - **When it scrolls.** As for the move buttons on `main` (`1995185`), the layout effect focuses with
    `preventScroll`, and the passive effect then calls `scrollIntoView({ block: 'nearest' })`. The split
    matters here too. The first removal of a clean draft brings the save bar in the same commit, and the
    scroll MUST clear the bar's published height.

**Rationale**:
- Without a hand-off, the pressed button unmounts with its row and focus drops to `<body>`, which the keyboard
  requirement forbids.
- Following the clip keeps the operator on the control that reverses what they just did.
- In a long chapter the tail can be far below the row. Focusing it scrolls it into view, which shows where the
  clip went (see Risks).

### The render guard

**Context**: While the event lists a missing clip, the page must not offer Render or Render anyway, and the
row must not offer Render. `RenderControl` already has the mechanism for this (`blockedReason`), and the seam
already feeds it while editing.

**Explored**:
- **For the row:** show nothing where Render would be, or a short reason there. With nothing, a "Needs
  render" row with no Render looks broken, and a screen reader walking the row learns nothing. The
  "N missing" badge sits in another cell.
- **For the page:** name every missing clip in the reason, or name one and count several. The warning above
  the chapters already names them all.

**Decision**:

- **The words.** `jobs/labels.ts` gains them, next to the other sentences both screens use:

  ```ts
  /** Why the page holds a render back while reel.yaml lists clips missing from disk; none: undefined. */
  export function missingClipsReason(missing: readonly string[]): string | undefined {
    if (missing.length === 0) return undefined
    return missing.length === 1
      ? `${missing[0]} is missing from disk. Restore it, or remove it in Edit mode.`
      : `${missing.length} clips are missing from disk. Restore them, or remove them in Edit mode.`
  }
  /** A row's words in place of Render while its event lists a missing clip. */
  export const MISSING_BLOCKS_ROW = 'Blocked by missing clips'
  ```

- **The page.** In `EventDetail.tsx`, the seam's expression becomes
  `blockedReason={editing ? 'Save or leave Edit mode to render' : missingClipsReason(event.missing)}`.
  - Edit mode's reason MUST win while editing: a render reads the saved file, whatever the draft holds.
  - When a save removes the last missing clip, the page's re-read returns `missing: []`, so Render comes back.
    The event is stale, with the edit as its reason.
- **The row.**
  - `LiveJobCell.tsx` gains `blockedReason?: string`. When `staleness.stale && !active` and no reason is set,
    the cell shows `RowRender`. When a reason is set, it shows this in its place:
    `<span className="row-blocked"><Icon name="alert-triangle" />{blockedReason}</span>`
  - `EventList.tsx`'s `EventRow` passes
    `blockedReason={event.missing_count > 0 ? MISSING_BLOCKS_ROW : undefined}`.
- **The style.** `jobs.css` (`@layer components`) gains `.row-blocked`: inline-flex,
  `gap: var(--s-1)`, `align-items: center`, `color: var(--fg-muted)` and `font-size: var(--text-xs)`. In the
  narrow card layout the cell's items already flow (`.live-job { display: contents }`), so it needs no
  narrow rule.
- **The warning above the chapters** (`ReadyView`) stays as it is. It names every missing clip, so the reason
  gives only the number when there are several.
- **Active jobs.** `RenderControl` and `LiveJobCell` keep their own rules. A queued or running job keeps its
  progress and Cancel. The page still shows the reason beside it (the job will fail at probe); the row shows
  the job, not the note.

**Rationale**:
- The one mechanism `render-progress-screen` built for "a reason instead of Render" is reused. The page needs
  no new prop, and the row needs one.
- The reason names the identity, not only the file name, as the warning above the chapters does:
  `Kväll/gone-b.mp4` says which chapter folder.
- The row's note pairs an icon with words, since "State is never shown by color alone" treats a warning that
  way. It is short enough for the 11rem job column.

### Excluded missing clips

**Context**: A missing clip whose `clips` entry sets `exclude: true` is not probed (`cli/build.py`
`_probe_clips`), so its render succeeds.

**Explored**:
- This was measured on `2024-09-03 - Utesluten` (ad hoc): `s1710002.mp4`, plus a `reel.yaml` that lists
  `borta.mp4` with `exclude: true`. After `POST /jobs`, the worker rendered it (`done`), and afterwards the list
  shows it as fresh with `missing_count: 1`.
- Neither `EventDetailOut` nor `EventSummaryOut` says whether a missing clip is excluded. The page could learn
  it only from `GET …/reel`: one more read per page, and none is possible for the list.

**Decision**: Every missing clip holds the render back, excluded or not.
- **Before any render.** In the verification library Utesluten is never rendered, so it is stale.
  - Its page says "borta.mp4 is missing from disk. …" and offers neither Render nor Render anyway.
  - Its row shows "Blocked by missing clips".
- **After a render started elsewhere** (the CLI, or `POST /jobs` as measured). The event is fresh.
  - Its page still offers no Render anyway.
  - Its row offers no Render, as for any fresh row, and so shows no note.

**Rationale**:
- The guard must use what the reads publish.
- The case needs an `exclude` written by hand on a clip that is gone.
- The block is never a dead end: removing the entry, and its `exclude` with it, lifts it.
- The exact fix is an API field, for example saying which missing clips a render would need. That is
  recorded as a follow-up; with it, the guard narrows without changing the approach.

### Files and parallel changes

**Context**: Two other changes are specified at the same time and may land before or after this one.

**Explored**: `openspec/changes/job-summary-times` and `openspec/changes/clip-thumbnails-screen`, read from
their proposals and tasks. Each lists the files it edits.

**Decision**:

- **Owned, and edited here:**
  - `web/src/edit/draft.ts`, `EventEditor.tsx`, `ClipOrderList.tsx` and `edit.css`
  - `web/src/jobs/LiveJobCell.tsx`, `labels.ts` and `jobs.css`
- **Shared, with one localized edit each:**
  - `web/src/events/EventDetail.tsx`: the `blockedReason` expression
  - `web/src/events/EventList.tsx`: one prop on `LiveJobCell`
  - `web/README.md`: the Edit-mode and render paragraphs
  - `docs/high-level-design.md`: §4.10, row D, one sentence
- **Not touched:**
  - in `src/edit/`: `SaveBar.tsx`, `unsaved.ts` and `MetadataForm.tsx`
  - in `src/jobs/`: `RenderControl.tsx`, `JobProgress.tsx` and `store.ts`
  - elsewhere: `route.ts`, `ui/**`, `styles/**`, `api/**` and `package.json`
- **`job-summary-times`** (C9) edits `api/`, `web/openapi.json`, `schema.d.ts` and `jobs/JobProgress.tsx`. The
  two changes share no file.
- **`clip-thumbnails-screen`** (T3) edits:
  - `ClipOrderList.tsx`: it threads `eventId` through `ClipRow` and `IgnoredRow` into `RowBody`, and adds a
    thumbnail cell
  - `edit.css`: a grid column, the narrow areas and the breakpoint
  - `EventEditor.tsx`: it passes `eventId`
  - `EventDetail.tsx`: `ChapterPanel`

  This change adds no grid column and leaves the breakpoint alone. `RemovedRow` passes `RowBody` exactly
  what `IgnoredRow` passes, so whichever change lands second makes `RemovedRow` follow `IgnoredRow`; task 1.1
  checks this. A missing clip shows T3's empty box, whether removed or not.

### Verification fixtures

**Context**: Every spec scenario must be checkable in the browser.

**Explored**: The events that `scripts/make_dev_library.py` builds. Only `2024-09-01 - Sommarlov` lists a
missing clip, and it has no per-clip properties.

**Decision**: The dev library's `2024-09-01 - Sommarlov` covers one missing clip. Two more states are added ad
hoc, only in the implementing agent's own library copy. They never go into `scripts/make_dev_library.py`,
whose counts other changes' checks cite.

- **`2024/2024-09-02 - Två saknade`**: `s1710001.mp4` at the root and `Kväll/s1710003.mp4`, both symlinked to
  `clips/`, and this `reel.yaml`:

  ```yaml
  version: 0
  metadata:
    title: Två saknade
  chapters:
    - name: ''
      clips:
        - s1710001.mp4
        - gone-a.mp4   # moved to the NAS
    - name: Kväll
      clips:
        - Kväll/gone-b.mp4
        - Kväll/s1710003.mp4
  clips:
    Kväll/gone-b.mp4:
      trims:
        - {in: 0, out: 1.5, reason: black}
  ```

  It has two missing clips: one in a named chapter with a per-clip property, and one with an end-of-line
  comment. `reel.yaml` sets no date; the folder name gives 2024-09-02.
- **`2024/2024-09-03 - Utesluten`**: `s1710002.mp4`, symlinked to `clips/`, and this `reel.yaml` (the folder
  name gives the title and the date):

  ```yaml
  version: 0
  chapters:
    - name: ''
      clips:
        - s1710002.mp4
        - borta.mp4
  clips:
    borta.mp4:
      exclude: true
  ```

### Review decisions (supervisor, 2026-09-30)

**Context**: The supervisor reviewed this design before implementation and ruled on its open points.

**Decision**:

- **Undo rule.** The original-order restore (`restoreClip`) is accepted. A missing clip that was moved, then
  removed, then restored returns near its original place (the trade-off under "The draft"). After the
  implementation review, the clip goes right after the last of its original predecessors in the current order,
  not after a count of them ("The draft", *Review refinement*).
- **Fixtures.** No second missing clip in one chapter is added to a browser fixture. The "removals undone in
  any order" scenario is proven by task 2.1's model script only.
- **Excluded missing clips.** The explicit behaviour on `2024-09-03 - Utesluten` is accepted: every missing
  clip holds the render back. Two follow-ups go into the PR body, not into code:
  - an API field saying which missing clips a render needs, or a server-side refusal on `POST /jobs`
  - a restored file is adopted into the default chapter, not its folder's chapter (`cli/adoption.py`
    `adopt_chapter`)
- **Accepted as designed:**
  - removed clips in a tail list with Undo
  - a save that adopts NEW clips in the chapter it writes (`event-edit-screen`'s behaviour)
  - the row's "Blocked by missing clips" note
  - the page's reason naming the full identity
- **`.btn-compact`.** This change uses it outside the jobs screens (Remove and Undo in the editor). So the rule
  moves, unchanged, from `jobs/jobs.css` to the shared `@layer components` in `styles/components.css`, next
  to the other button classes, with no new token. This overrides "Not touched: `styles/**`" under "Files and
  parallel changes" for that one rule.
- **The seam.** Its location is re-checked on current `main` in task 1.1: `EventFacts`, in `EventDetail.tsx`.

## Failure behavior and idempotency

- **Remove, Undo and Reset send nothing.** They change the draft only, and the unsaved guard covers them.
- **A save is the editor's one conditional PUT.**
  - Every failure keeps the draft, removals included, and says why by cause. Retry sends the same body again.
  - The dangling-properties 400 cannot come from a removal, because the properties go with it. Any other 400
    is shown as today.
  - A 412 offers two ways on. Reload latest discards the removals too. Overwrite with mine writes the
    operator's document, removals included, over the other change.
- **Only `reel.yaml` changes on disk**, and only through the atomic write (`reel/writer.py`). No media file is
  created, moved or deleted, since only a clip that is absent from disk can be removed.
- **The file comes back.** Before the save, Undo or Reset keeps the entry. After the save, the next read shows
  the clip as NEW in its folder's chapter, and its removed properties are gone. It rejoins `reel.yaml` in one
  of two ways:
  - a reorder of that chapter in Edit mode writes it where it is shown
  - the next render adopts it (D-CLI3), appended to the default chapter (`cli/adoption.py` `prepare_event`,
    `adopt_chapter`), even when its folder is a named chapter
- **Saving again.** After a successful removal, a new save writes the new state and removes nothing more. A
  save from a draft that is out of date gets a 412.
- **The guard is read-only.** It MUST only withhold controls, and it sends nothing. A job queued elsewhere for such an event
  (from the CLI, from curl or from another tab) still runs and fails loud at probe. The page and the row show
  it like any job, with Cancel.
- **Worker restart and `--force`:** no interaction, because no render path changes. There is no
  `RENDER_GRAPH_VERSION` bump, no API or schema change, and no migration.

## Risks / Trade-offs

- **[An excluded missing clip blocks a render that would succeed]** → This was measured and is accepted (see
  "Excluded missing clips"). Removing the entry lifts the block, and an API field is the follow-up.
- **[A saved removal cannot be undone in the app: the entry and its trims are gone]** → It takes one
  explicit, named control per clip, with Undo and Reset available until Save, and a count in the save bar.
  The file itself is never touched, and a restored file comes back as NEW.
- **[Undo does not keep a move of the removed clip itself]** → A missing clip that was moved, then removed,
  then restored goes back right after the last of the clips it followed when Edit mode opened. This is the
  price of a rule under which removals undone in any order leave nothing to save ("The draft"). The clip can
  be moved again.
- **[Focus jumps to the tail in a long chapter]** → The tail is the clip's new place, and it is scrolled into
  view. Undo there returns focus to the clip's row in the list. Missing clips are rare and few.
- **[The guard trusts the last read]** → A file restored on disk after the page or the list was read still
  shows as missing until Refresh, since screens never poll. The guard only ever withholds a control, and
  Refresh corrects it.
- **[Removing every clip of an event leaves nothing to render]** → Render then comes back, since no clip is
  missing, and the job fails loud ("render plan has no clips to render", `render/orchestrator.py`). The same is
  true today for any empty event. A guard for it is out of scope.
- **[The guard is client-side only]** → The API still accepts the job, and the job fails loud. A server-side
  refusal is a follow-up, and it would also serve the CLI.
- **[Parallel edits with `clip-thumbnails-screen` in the same editor files]** → This change makes no grid
  change, `RemovedRow` mirrors `IgnoredRow`, and the gate task checks which change landed first.
- **[MODIFIED requirements written by two other changes]** → Task 1.1 re-bases each block on the archived text
  at the gate.
  - The two `event-edit-screen` blocks already match `main`'s landed text, plus this change's edits.
  - Until `render-progress-screen` is archived, `openspec validate --strict` reports "Archive would refuse"
    for its two requirements.
  - On a scratch copy of `main`'s `openspec/`, `render-progress-screen`'s delta was archived first. This
    change then validated with no INFO and archived as "+ 1 added, ~ 4 modified".

## Migration Plan

- Rebuild `web/dist` with the container command in `web/README.md`; `serve` mounts it as before.
- No data migration: a removal is an ordinary editorial write.
- Rollback: revert the web change and rebuild. Any `reel.yaml` already saved stays a valid document.
