## Context

When this change starts, the three before it are built (see proposal.md, Why):
- **The selection** holds several clips. `pressClip(sel, id, press, order)` takes any order, and the group edits
  ship their clips (`selection-move`, `selection-drop`, `ignore-many`).
- **The Event tab's Chapters list** holds every chapter tool. The bin's chapter headings are plain.
- **`BinPlayer`** sits at the top of the bin and shows the selection's last clip.
- **`ClipInspector`** is the Clip tab for any selected clip. It offers Move earlier/later, Move to…, Rotate,
  Ignore/Include and Remove/Undo, plus the Timeline's `ClipTrackPart` when the track draws the clip.

What is left of the old bin:
- `ChapterDrag` (`@dnd-kit` drag between chapters, group drag of marks, keyboard lift);
- `ClipOrderList` (rows with handle, mark, Watch thumbnail, Move up/down, Rotate, Include, Remove/Undo, and the Cuts
  control with its `CutsPanel`);
- `IgnoredBin` and `wideBin.ts` (ignored clips after the chapters from 960 px);
- the marks line (`marks.ts`, Rotate marked, Move marked to…) and the Clips help.

Two more facts shape the design:
- **What the client knows of a clip.** `ClipOut` has identity, status, size, mtime, duration (nullable) and
  `excluded`. `ProxyOut.facts` (`ProxyFactsOut`, ready proxies only) has:
  - the source's probed duration, and its frame rate as a fraction plus `vfr`;
  - the proxy's displayed width and height (540 on the short side, rotation applied);
  - the source's display rotation, and its audio codec (null when it has no sound).

  There is no source resolution, video codec, bitrate or capture time anywhere in the client.
- **Dependencies.** `timeline/model.test.ts` asserts that the client's dependencies are React, React DOM and the
  three `@dnd-kit` packages. `@dnd-kit` is imported by `ChapterDrag.tsx`, `ClipOrderList.tsx` and
  `ChapterTools.tsx`.

## Goals / Non-Goals

**Goals:**
- A bin that is a list, a player and an information panel, with every edit reached elsewhere.
- No edit, word or announcement lost: each removed control's edit has a named home (proposal table).

**Non-Goals:**
- New draft edits, apart from `include-many`, the mirror of `ignore-many`.
- Any change to the track.

## Decisions

### D1. The rows (`edit/binList.ts`, pure)
```ts
export type BinRow = {
  identity: string
  name: string                      // as the page names it ("Edit mode names clips …")
  group: 'listed' | 'ignored' | 'removed'
  place: string | null              // "Kvällen · 2 of 3", or null for ignored and removed rows
  moved: string | null              // "was 4" | "from Main" (the fewest-moves rule, as the bin counts today)
  status: ClipStatusWords           // New, Missing, Excluded, Included, Ignored
  keptMs: number | null             // null when the length is unknown
  typed: boolean                    // a typed cut waits ("Edit mode lists, adds and removes a clip's cuts")
  onDisk: boolean
}
export function binRows(draft: Draft, baseline: Baseline, detail: EventDetail, typed: ReadonlySet<string>,
                        lastMoved?: string | null): BinRow[]   // lastMoved breaks the fewest-moves ties, as the top bar does
export function binOrder(rows: readonly BinRow[]): readonly string[]  // the order Shift+press ranges over
```
- **Groups.** `listed` covers every listed chapter's play order, with missing and excluded clips in their places.
  `ignored` follows the chapters' order and each chapter's listing. `removed` holds the missing clips removed in this
  Edit mode.
- **Captions** for the last two groups ("Ignored · 1 clip, not played", "Removed from reel.yaml when you save · 1
  clip") come from the words the bin uses today.
- **Reuse.** The counting (`moved`) reuses the existing moved-clip rule, so the top bar and the rows agree.
- **Tests.** `binList.test.ts` covers Tjörn, Sommarlov before and after a removal, a moved clip within and across
  chapters, a 400-clip event, and names of clips from another folder.

### D2. The list (`edit/ClipBin.tsx`)
```tsx
<section class="bin">              // the bin pane: a column
  <header> Clips · N  <HelpToggle section="Clips"/> <ShowPlayer/> </header>  // Show player only while hidden
  <BinPlayer/>                     // clip-tab-and-player
  <div role="listbox" aria-multiselectable="true" aria-label="Clips" data-ws-scroll>
    <div role="group" aria-label="Clips in play order"> <div role="option" aria-selected …/> … </div>
    <div role="group" aria-labelledby="ignored-caption"> … </div>
    <div role="group" aria-labelledby="removed-caption"> … </div>
  </div>
  <ClipInfo/>
</section>
```
- **Focus.** Roving `tabindex`: one option holds 0. Keys come through the pure `listKey(press) → ListCommand`:
  - Up, Down, Home and End move focus;
  - Enter, and Space reached by keyboard (`modality.ts`), give `select alone`;
  - Ctrl/Cmd+Enter gives `toggle`, and Shift+Enter gives `range`;
  - Shift+F10 and ContextMenu give `menu`.

  Focus moving does not select, the multi-select listbox pattern. So walking the list announces nothing beyond the
  option names, and loads nothing.
- **Pointer.** A click passes `pressOf(event)` (`clip-multi-select` D3) and `binOrder`. A press on the frame of an
  on-disk clip also calls `BinPlayer`'s `watch(identity)` (`clip-tab-and-player` D7).
- **Menu.** A `contextmenu` event on a row, or the `menu` key command, selects by `menuSelects` and opens the menu
  through `openClipMenu` (`clip-context-menu` D1), with the row as the invoker.
- **Drag.** A press past 3 px on an ignored row starts the existing bin-to-track include drag (`track-drag-edit`),
  the one the ignored rows' grip starts today. Other rows start nothing.
- **Windowing.** Each option keeps `content-visibility: auto` with `contain-intrinsic-block-size` (`edit-list-paint-cost`).
- **Sizes.** Rows are 40 px with a fine pointer (a 48 × 27 frame and two text lines) and 48 px with a coarse one.

### D3. The information (`edit/clipInfo.ts` pure, `edit/ClipInfo.tsx`)
```ts
export function clipInfo(clip: Clip, facts: ProxyFacts | null, cuts: readonly DraftCut[],
                         place: string | null, turn?: Turn): InfoLine[]   // clip: the draft's view (withIgnoreStatus)
```
- **Length.** The detail's duration, else the facts' duration. Null is "unknown", never 0. Kept length subtracts the
  union of the cuts, as the movie stat does.
- **Frame rate.** `fps_num/fps_den` rounded to two decimals without trailing zeros ("25 fps", "29.97 fps"). With
  `vfr === true`, "variable, about 29.97 fps".
- **Picture.** From the proxy's displayed width and height: the orientation (landscape, portrait or square) and the
  ratio. The ratio is matched within 1 % to 16:9, 4:3, 3:2, 1:1, 21:9 and their portrait forms, else "about 1.85:1".
  No pixel size is shown: those are the proxy's (Principle I).
- **Rotation.** `rotation` 90, 180 or 270 gives "Turned 90° by its container". The draft's turn is shown with
  `clip-rotation`'s words when it is set.
- **Sound.** The codec in capitals ("AAC"), with any `pcm_*` as "PCM". Null gives "No sound".
- **Size and time** use the page's formats ("Times are written one way on every screen").
- **Cuts** come from the draft, as the Cuts panel lists them (removed ones left out): number, span, length and reason,
  in the Cuts panel's formats.
- **A missing clip** gets its status, place and cuts only: no size, time, length or proxy line (it has no file).
- **Without a ready proxy**, one line says that frame rate, picture and sound are known once its proxy is prepared.
- **Hide information** works as Hide player does (`clip-tab-and-player` D3). The key is `auto-reel:bin-info`, and the
  panel is capped at 30 % of the bin's height, scrolling within itself.
- **Tests.** `clipInfo.test.ts`.

### D4. The Cuts panel in the Clip tab
- **Placement.** `ClipInspector` renders `CutsPanel`, minus its old toggle and Watch, for an on-disk, listed,
  non-excluded clip, with or without the track.
- **Merge.** `ClipTrackPart` stops drawing its own cut list (`ClipCuts`). It hands the panel two extras through
  props: "+ Cut at playhead", and each cut's Edit, which selects the cut on the track.
- **Unchanged.** The `CutPanels` store, its typed text per clip, and the `cut-typed` action stay as they are. The row
  reads `typed` from them (D1).
- **Summary.** The panel's heading is the cut summary (today's Cuts control words, no longer a button).

### D5. The menu and the group view (`clipMenu.ts`, `ClipGroupTab`)
- **The last item follows the status:** Ignore clip, Include clip, Remove from reel.yaml, or Undo remove. They make
  today's `ignore`, `ignore` with `include`, `remove` and `restore` edits.
- **Not on the track.** Rotate, Move to, Cut and Poster carry the reasons the spec gives.
- **Several clips.** "Include N clips" counts the ignored targets and dispatches the new `include-many`, which
  includes each at the end of its chapter in the bin's order, as one step labelled "include of N clips". The group
  view gets Include clips too.
- **Focus after Remove from the menu** goes back to the row, which stays and moves to the removed group.

### D6. What is deleted
- **Components and modules:** `ChapterDrag.tsx`, `ClipOrderList.tsx` (rows, `IgnoredRow`, `IgnoredBin`),
  `wideBin.ts`, `marks.ts`, and `dragSlots.ts` and `listPaint.ts` if nothing else imports them, and the marks line in
  `EventEditor.tsx`.
- **Draft actions:** `mark`, `marks-clear`, `marked-move` and `group-drop`, with their tests. Any test that still
  covers a kept rule moves to the new modules.
- **Words:** the Clips help is rewritten:
  - "Press a clip to select it; Ctrl or Cmd adds one, Shift selects a range."
  - "Right-click a clip, or press Shift+F10, for its menu."
  - "Move clips on the Timeline, or with Move earlier, Move later and Move to… in the Clip tab."
  - "Ignored clips are not played; drag one onto the Timeline to include it."
  - The event's own chapter, missing and new clip sentences stay.
- **`@dnd-kit`.** Once nothing imports it, the three packages leave `package.json`, and the dependency test in
  `timeline/model.test.ts` says "React and React DOM".

## Research & Decisions

### A listbox, buttons, or a grid
**Context**: the list must select several clips by keyboard and pointer, open a menu, and stay light at 400 rows.
**Explored**:
- a `listbox` with `aria-multiselectable` (WAI-ARIA multi-select listbox, focus not following selection);
- a list of `role=button` rows, as the track's blocks are, which makes 400 Tab stops;
- a `grid` with per-cell controls.

**Decision**: the listbox (D2).
**Rationale**:
- It is one Tab stop with arrow keys, and screen readers announce selected states natively.
- A plain row holds no control, which a listbox requires anyway.
- The rows' modifier keys match the track's (Enter, Ctrl/Cmd+Enter, Shift+Enter).

### One list, or grouped by chapter
**Decision**: one list in play order, with each row naming its chapter, and only the ignored and removed clips
captioned apart.
**Rationale**: the operator asked for "plain". The chapters have the Chapters list, and the track's bands show them
along time. A grouped list would bring back the headings this change removes.

### What the information shows without a new endpoint
**Context**: the operator asked for "metadata". The useful source facts (resolution, codec, bitrate, capture time)
are not in the client.
**Explored**:
- (a) a probe-backed read per clip;
- (b) have the proxy job record more of the probe it already runs (`clip-proxies`, "The facts about the clip are
  written beside the proxy");
- (c) show what the client has.

**Decision**: (c) now, and (b) as a possible follow-up.
**Rationale**:
- (a) breaks the probe-free detail (`ClipOut`) and adds an endpoint, which the thin API (Principle V) would also need
  in the CLI.
- (b) is an engine change with a cache-format bump, so it is its own change.
- (c) needs nothing new, and states only facts (Principle I): orientation and ratio, never the proxy's pixel size.

### Keep typed cuts in the Clip tab
**Context**: the Clip tab already had "+ Cut at playhead" and the selected cut's typed fields. The bin's panel added
typed new cuts, removed-cut Undo, and the "typed" hold on Save.
**Decision**: move the whole Cuts panel into the Clip tab (D4).
**Rationale**:
- Without it, a clip whose proxy is not ready could not be cut at all.
- The player's Set From and Set To need fields to fill.
- Many requirements refer to "the clip's Cuts panel", so keeping the term keeps them true.

### A long delta for a two-day change
**Context**: the old bin is named in about 30 requirements.
**Decision**: one change. Each requirement is MODIFIED once here, keeping its scenarios as the validator requires, or
REMOVED with its migration.
**Rationale**: the code is one swap (a list in, the old bin out). Splitting the spec edits from the code would leave
`main` with specs that describe a bin that is gone, or one that is not yet built.

## Risks / Trade-offs

- [The keyboard path for a long jump is slower than the old lift] → Move to… puts a clip at the end of any chapter in
  one press. Move earlier and Move later step it. Alt+arrows on the track step it too.
- [Touch users cannot select several clips] → Each clip has the full Clip tab and menu. A touch path for groups
  (a selection mode) can come later if asked for.
- [The selection is announced by the polite status and by the listbox] → Focus moving does not select, so only an
  explicit Enter or click changes the selection, and it is announced once, as "One selection in the workspace" says.
- [The bin is short. At 1280×720 it is about 390 px tall, and the player (about 230–300 px with its controls) plus the
  information (up to 30 %) leave no whole row. At 1440×900 they leave about one] → Hide player and Hide information
  give the room back, and the choices are kept. The player already starts hidden, while no choice is stored, in a
  side pane shorter than 70.125rem (`clip-tab-and-player`, "Edit mode previews a clip on request"), so at 1280×720
  and 1440×900 the list gets the player's room by default; this change keeps that rule. The spec states the hidden
  case (all 5 rows of Tjörn at 1280×720) and 1 row with both shown at 1440×900. Task 3.1 measures and reports both.
  Hiding the information by default in short windows is still an open choice for the operator.
- [Removing `@dnd-kit` breaks a surface that still uses it] → D6 removes it only when nothing imports it, and the
  build gate catches a missed import.

## Failure behaviour

Display and draft edits only: no new request and no write. A clip read without facts shows what the read gives, and
says what waits for its proxy. A failed preference write keeps the visit's choice.
