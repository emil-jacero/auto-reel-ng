## Why

With `track-draft-order` the track draws the draft order, and with `editor-selection` a clip can be selected on it,
but the order is still edited only in the bin. The goal (`docs/editor-workspace.md` §6.4, §6.8, §3.4; mock board
**Event page: Edit mode (editor workspace)**) is the iMovie feel: drag a clip along the track to reorder it, drop it on
a chapter band to move it, drag a clip from the bin onto the track to include it and off the track to ignore it.
Slice 3 of the workspace (HLD §6 item 10, GUI v3; D-20, which built the timeline in the repo and kept `@dnd-kit` for
the lists).

## What Changes

- **Reorder on the track**: press and drag a clip block's body sideways; the other clips make room live; on release
  the draft's order changes (one draft edit per release). Escape or a drop outside the track cancels.
- **Move between chapters on the track**: dropping into another chapter's span, or onto its band, moves the clip into
  that chapter at the drop place.
- **Bin ↔ track**: dragging a New or Ignored clip from the bin onto the video track includes it at the drop place;
  dragging a clip from the track onto the bin ignores it (through the new draft ignore edit).
- **Keyboard alternative** (WCAG 2.5.7): with a clip selected, Alt+Left / Alt+Right moves it one place (across a
  chapter boundary into the neighbour chapter), announced politely.
- **A draft ignore/include edit** (none exists yet: the draft sends `ignore` back as read): ignoring and including a
  clip become draft edits counted by the top bar, Reset and Save, which the track↔bin drags use, and an
  "Ignore clip" button in the inspector's Clip tab (moved here from `editor-selection`).
- Snapping of the drop place to clip boundaries; the drop slot is drawn as a line with words ("Before s1710003.mp4").
- Inert while a save or a Move marked… is pending, as the other track tools.

## Non-goals

- Dragging several clips at once on the track (the bin's marks stay the way).
- Undo (`editor-undo`); Split (`clip-split`).
- Card length dragging already exists ("A card block's end edge is dragged to set the card's length").

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `timeline`: ADDED the pure model of a track drop: the drop slot for a pointer place, the resulting order and
  chapter, and snapping.
- `web-app`: MODIFIED the reorder requirement (an ignored clip can be included by dragging) and the save requirement (Save writes `ignore` from the draft's ignore/include edit).
- `event-timeline`: ADDED reorder and chapter move by dragging, bin↔track include/ignore, keyboard moves, inert rules.

## Impact

- Web only: new `timeline/reorder.ts` (pure, `node:test`), `timeline/ClipDrag.tsx`, `timeline/dragStore.ts` (a clip
  drag sharing the one-drag claim), `timeline/Track.tsx`, `edit/EventEditor.tsx` (the same reorder/move reducer
  actions the lists use, and a new ignore/include action), `edit/draft.ts` (the draft's ignore field, `buildWriteBody`'s
  `ignore`, `isDirty`, Reset and the save counts), the Clip tab's "Ignore clip" button, bin drag source/target.
- No API, engine, schema, fingerprint or `RENDER_GRAPH_VERSION` change; CLI untouched; no new dependency (the track
  drag is built in the repo like the trim handles, D-20).
- Depends on `editor-selection` (and through it on `track-draft-order`). `clip-split` depends on this change.
