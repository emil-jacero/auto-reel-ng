## Context

- **The preview today.**
  - `preview/ClipPreview.tsx` (about 1100 lines) is rendered by `cuts/CutsPanel.tsx` under a bin row. It opens with
    the panel's Watch control, or the row thumbnail's Watch button.
  - `preview/previews.ts` (`ClipPreviews`) is the store that keeps one preview open and remembers each clip's read
    length (`useClipLength`).
  - Opening a preview releases the Timeline's `<video>`, and a playhead move closes the preview. Both go through
    `playback/coordinator.ts` and `useTimelineVideo`.
  - Set From and Set To write the panel's typed fields through the editor's cut-panel store (`CutPanels`, typed text
    per clip identity). That store keeps text while a panel is hidden.
- **The Clip tab today.**
  - `timeline/ClipTab.tsx` takes a `TrackClip`. The Timeline renders it into the inspector's clip slot by portal
    (`Timeline.tsx`, `clipPanel`), with `ClipHeader` and `clipPlace` computed from the drawn clips.
  - With no track (Prepare), or for a clip the track does not draw, nothing renders.
  - `clip-multi-select` adds `ClipGroupTab` and Move to…, in the same place.
- **The edits the rows offer** (`EventEditor.tsx`):
  - `onMove`: `move` within a chapter, the rows' Move up and Move down;
  - `onMoveClip`: `clip-drop` into another chapter;
  - `onIncludeClip`: `ignore` with `include: true`, at the end of the chapter;
  - `onRemove` and `onRestore`: a missing clip;
  - `onRotate`.

  Each is guarded by `idle()` and announced.

## Goals / Non-Goals

**Goals:**
- One preview, docked in the bin, following the selection, with no media loaded until Play.
- A Clip tab that is a full home for a clip's edits whatever the track's state, so `plain-clip-bin` can strip the rows.

**Non-Goals:**
- Changing `ClipPreview`'s playback, error or copy logic. It moves, it is not rewritten.
- Moving the Cuts panel (`plain-clip-bin`).

## Decisions

### D1. The shown clip (`edit/binPlayer.ts`, pure)
```ts
export function shownClip(sel: Selection, was: string | null, listed: ReadonlySet<string>,
                          onDisk: (id: string) => boolean): string | null
```
- **Rule.** `lastClip(sel)`, or a cut's clip, when it is on disk. Otherwise `was` while the selection is a card, a
  suggestion or nothing. Otherwise `null`. `was` is dropped once it is no longer listed or no longer on disk.
- **Tests.** `binPlayer.test.ts` covers each selection kind, a missing or ignored last clip (ignored clips are on
  disk, so they play), and `was` falling away.

### D2. `BinPlayer` (`edit/BinPlayer.tsx`)
- **Placement.** The bin pane becomes a column: `BinPlayer` (not scrolling), then the existing scroll box with the
  marks toolbar and the lists.
- **Content.** `BinPlayer` renders `ClipPreview` for the shown clip with `open = previews.isOpen(id)`. Closed, the
  preview draws the thumbnail in its 16:9 box with Play enabled and the playhead, Set From and Set To
  `aria-disabled`. Play calls `previews.open(id)` and then plays, which is today's open-then-play path.
- **Close becomes Hide player.** `ClipPreview`'s Close is replaced by Hide player. Escape in the player calls
  `previews.close(id)`, keeps focus on Play, and stops propagation, so `useSelection` does not clear the selection.
- **A new shown clip** calls `previews.close(was)` first. That is the existing one-at-a-time rule.
- **Empty.** With no shown clip the player is an inert placeholder of the closed player's height: a dashed box over
  the space of the closed player's picture and rows, holding "Select a clip to watch it.", with Hide player as its
  only control. The rows below the picture are the closed preview's own markup with `visibility: hidden`, `aria-hidden`
  and `inert`: they keep the closed player's size by construction (same classes, same grid) and are neither shown,
  focusable nor in the accessibility tree. So the first selection changes no bin row's size or place, and the empty
  player has exactly one focusable control. The hidden state is unchanged.
- **Height budget (fine pointer, side pane).** About 200 px in all, with the preview closed, open or with a ready
  copy: 1px border, 4px padding above and below, the picture's box (at most 136 px, as wide as the pane, 16:9 below
  the cap, the picture whole inside it), a 2px gap, Play with the playhead (24px), a 2px gap, and Skip cuts, Set From
  and Set To (24px): 197 px measured at a 282 px pane (1280 wide), 194 px at 240. What else the preview says is laid
  on the picture's box, in its one grid cell: the readout and Hide player along its top (light badges, as the status
  badge), the legend under the readout, and the source line and Play original along its foot, so a ready copy adds no
  row. The clip's name is the region's heading for assistive technology only; the selected row and the Clip tab name
  it on screen. A coarse pointer or a stacked page (under 960 px) keeps the larger rows (`@media (width >= 960px) and
  (not (pointer: coarse))` gates the compact layout; a headless browser reports no fine pointer, so "not coarse" is
  the test the workspace already uses).
- **Unavailable looks unavailable without color.** Set From, Set To and the playhead, when they say they are
  unavailable, have a dashed edge in addition to the dimmed color (`preview.css`).
- **Hidden.** The player renders nothing of its own and closes any open preview: no bar, no heading. Its Show player
  button goes through a portal into a slot in the first row of the marks toolbar (`EventEditor`'s `.mark-lead`), next
  to the Clips help, so the toolbar's two fixed rows, its 88 px and the place of the count and Clear marks do not
  change ("The marks line is one aligned unit"). The button is named `Show player, <name>` for the shown clip
  (`Show player` with none). In the workspace's bin it is an icon alone, 32 px square, like the help toggle; and
  while hidden, a bin narrower than 19rem (a container query on `.ws-binbox`) shows Clear marks as its icon alone,
  because the help, Show player, the count and Clear marks would not fit a 240 px pane's row. Hide player leaves
  focus on Show player; Show player leaves it on Hide player; a row's Watch shows the player
  and focuses Play.
- **Workspace keys.** The whole player region counts as "inside a clip preview" for `editor-shortcuts`' rules
  (`focusFacts.inPreview`), open or closed. So Space on its Play presses Play even after a pointer press on a row's
  frame, and the arrows on its playhead stay the playhead's.

### D3. Hide player is remembered (`edit/binPlayerPref.ts`)
- **Storage.** `auto-reel:bin-player` = `hidden` in `localStorage`, absent meaning shown. Every access is in
  try/catch, and when the browser keeps nothing it falls back to shown.
- **Sharing.** A small module store read through `useSyncExternalStore`, the pattern `editor-shortcuts` D5 uses for its
  switch.

### D4. Set From and Set To target the shown clip's panel
- **Writing.** `ClipPreview`'s `onSet(field, ms)` writes through `CutPanels.setTyped(identity, field, text)`, which
  works with the panel hidden. The `cut-typed` action then marks the clip "typed", as today, so the row's Cuts control
  says "typed" and the save bar holds Save.
- **Not shown.** Set From and Set To do not open the panel, scroll the bin or move focus.
- **Only a clip with a Cuts panel.** The player plays any clip on disk, but offers Set From and Set To only for a
  clip that can be cut: not excluded, and active or new (`cuttable`, the rule that gives a row its Cuts control). For
  an ignored or excluded clip the preview is read-only (no Set buttons), so a typed time can never be held where the
  operator has no field to clear it. Include clip makes it cuttable.

### D5. The Clip tab is built by the editor (`edit/ClipInspector.tsx`)
- **Two parts.**
  - `EventEditor` renders `ClipInspector` into the inspector's clip slot for any clip or clips selection.
  - The Timeline no longer portals the whole tab. It portals only `ClipTrackPart` (Trim In/Out, the cuts with Edit,
    Remove and "+ Cut at playhead", Use frame as poster, `CutFields`) into a slot inside `ClipInspector`, and only
    when it draws the clip.
- **`ClipInspector` for one clip**, built from the draft and the detail, so it is there in Prepare:
  - the header: name, chapter and position from the draft's orders (`clipPlace` gains a draft-order variant), and the
    status words;
  - Move earlier and Move later (D6), Move to… and Rotate, for a clip a chapter lists that is on disk (a missing clip:
    Move earlier and Move later only);
  - Ignore clip or Include clip, by status;
  - Remove from reel.yaml, or Undo for a removed clip.
- **`ClipGroupTab`** (`clip-multi-select`) moves here unchanged. Its edits are all draft edits.
- **Focus** stays on the pressed control. After Include, the clip is drawn and the tab's controls re-render in place.
  After Remove, focus goes to Undo, as the row's control does.

### D6. Move earlier and Move later (`edit/stepMove.ts`, pure)
```ts
export function stepMove(chapters: readonly { key: ChapterKey; identities: readonly string[] }[],
                         identity: string, way: -1 | 1, onDisk: (identity: string) => boolean):
  | { kind: 'move'; chapter: ChapterKey; from: number; to: number }
  | { kind: 'clip-drop'; from: ChapterKey; to: ChapterKey; at: number; before: string | null }
  | { kind: 'edge'; words: string }
```
- **Order.** Steps go over the chapter's listed clips, missing ones included and ignored ones not: the bin's play
  order. That is Move up and Move down.
- **Edges.** At a chapter's edge the clip goes where Alt and an arrow put it (`stepSlot`, `applyDrop`): after the
  previous listed chapter's last clip on disk, or before the next one's first clip on disk (`before` names it for the
  announcement, null at a chapter's end), so Move later is Alt+Right. A missing clip returns `edge` with the reason in
  words; so does the first or last clip of the event, with Alt and an arrow's "<name> is already the first/last
  clip."; the button is `aria-disabled`. One difference remains inside a chapter: Move earlier and Move later step
  over missing clips (the bin's play order), where Alt and an arrow skip them.
- **Announcements** reuse the Move up/down words in a chapter and the Alt-arrow words across one.
- **Tests.** `stepMove.test.ts`.

### D7. The row's Watch button
`ClipOrderList`'s thumbnail button calls `onWatch(identity)`. That selects the clip alone (`pressClip(…, 'alone')`),
turns the player's preference to shown, and focuses the player's Play after the commit, in a layout effect. The Cuts
panel loses its own Watch control and its embedded preview.

## Research & Decisions

### Where the player lives
**Context**: the operator asked for a small, collapsible player at the top of the clip list.
**Explored**:
- keep the preview in the Cuts panel;
- the inspector's Clip tab;
- the top of the bin.

**Decision**: the top of the bin (D2).
**Rationale**: the operator asked for it there. It sits next to the list it plays from, and the inspector stays the
place for edits.

### What the player shows
**Explored**: (a) the clip a Watch press names; (b) the selection's last clip, kept while nothing else is a clip.
**Decision**: (b) (D1).
**Rationale**: the selection already drives the inspector and the track's scroll, so one rule for the player keeps
them in step. Keeping the last clip means that selecting a card to rename it does not blank the player.

### Load on selection, or on Play
**Decision**: on Play only.
**Rationale**: selecting clips with arrows, or Shift+click over 400 clips, must stay free. "Nothing loads before it
is asked for" already demanded that, and the one-video rule ("Edit mode holds one video at a time") would otherwise
take the Timeline's video away on every selection.

### The Clip tab: drawn by the Timeline or by the editor
**Context**: the Timeline needs proxies, and the edits a missing, ignored or Prepare-state clip needs are draft edits.
**Decision**: the editor draws the tab, and the Timeline adds its track-only part (D5).
**Rationale**: the tab is then there in every state, and the Timeline keeps the parts that do need the track, the
playhead and the proxies' facts.

## Risks / Trade-offs

- [At 1280×720 the bin is 391 px tall, and the player took 323 px of it with its controls in rows] → The player is
  compact in the side pane (D2): 197 px measured, in both Firefox 132 and Chrome. With it shown the bin's scroll box is
  194 px at 1280×720 and 312 px at 1440×900, and it holds the 88 px toolbar, a 36 px chapter heading and 68 px rows:
  1 whole played row at 1280×720 and 1 to 2 at 1440×900 (2 where the event has one chapter; `2024-08-20 - Två kapitel`
  has two headings), against 3 and 4 to 5 with the player hidden. The operator's targets of 2 and 4 are out of reach
  for a player near 200 px: 2 rows with their headings need the player under about 95 px, or 131 px for one chapter.
  Hide player gives the room back, and the choice is remembered. In a window under about 46rem tall the bin's
  scroll padding goes, so that a row selected on the track still sits under its chapter heading (the box then holds
  192 of its 194 px).
- [Two routes to the same edit (row buttons and Clip tab) for one change] → They dispatch the same actions and use the
  same words. `plain-clip-bin` removes the row buttons next.
- [Set From while the panel is hidden is invisible] → The row's Cuts control says "typed", the save bar names the
  clip, and the value is announced.
- [Moving `ClipTab` out of the Timeline breaks the portal's focus handling] → `ClipTrackPart` keeps its own focus
  code. The Clip tab's scenarios (`editor-selection`) are re-run in task 3.1.

## Failure behaviour

Display and draft edits only. The player's failures are `ClipPreview`'s, shown in the player by cause, as before. A
failed preference write keeps the player as the operator left it for the visit.
