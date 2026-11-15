## Why

In the workspace (`editor-workspace-layout`) the inspector's tabs are picked by hand and three selections live in
three places: the cut (`Track`), the suggestion (`useSuggestions`) and the card (`EventDetail`). There is no selected
**clip** at all. The goal (`docs/editor-workspace.md` §5, mock board **Event page: Edit mode (editor workspace)**,
`selection` tweak) is an iMovie-like inspector that shows what you clicked: a clip, a title card, a suggestion, or the
event when nothing is selected. Slice 2 of the workspace (HLD §6 item 10, GUI v3; D-20).

## What Changes

- **One selection for the workspace**: nothing · clip · cut · title card · suggestion. Selecting one ends the other;
  Escape clears it; it survives a Refresh and a save while its target still exists.
- **New: selecting a clip** — a press on a clip block (outside its edge and cut handles), or on its bin row; the block
  is outlined and the row highlighted, in more than colour.
- **Bin and track share it**: selecting in one shows it in the other and scrolls it into view.
- **The inspector follows it** with tabs Clip · Title card · Suggestion · Event (Cut fields live in the Clip tab):
  - Clip: name, chapter and position, length in the movie, Trim In/Out as typed fields, rotate, its cuts with "+ Cut at
    playhead", Use frame as poster. ("Ignore clip" comes with `track-drag-edit`, which builds the draft ignore edit.)
  - Title card: the card editor **docked** in the inspector (tabs, fields, live preview) instead of a modal dialog.
  - Suggestion: kind, clip and range, preview, Approve as cut (A) / Dismiss (R).
  - Event: Details, Poster, and a button "All title cards in this event" (with whether title cards are on, in
    words) that shows the docked editor's "All title cards in this event" tab, which holds the card style and the
    Title cards switch. Deferred: the chapter list with Add chapter stays in the bin, where it is today; it does not
    move into the Event tab.
- A press on empty track selects nothing, so the inspector shows Event.

## Non-goals

- Multi-selection on the track (bin marks stay the way to act on several clips).
- Dragging on the track (`track-drag-edit`), Undo (`editor-undo`).
- Any API, engine or `reel.yaml` change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`: ADDED the inspector-follows-selection and the docked card editor; REMOVED "A selected title card opens
  its inspector in Edit mode" (the modal dialog).
- `event-timeline`: ADDED "One selection in the workspace" and clip selection; REMOVED "A card is selected from the
  Timeline or the list, as one selection" (folded into the one selection).

## Impact

- Web only: new `edit/workspace/selection.ts` (pure model + `node:test`), `edit/workspace/Inspector.tsx`,
  `edit/card/Inspector.tsx` (docked variant, dialog removed), `timeline/Track.tsx` (clip press), `edit/EventEditor.tsx`,
  `events/EventDetail.tsx` (card selection moves into the one selection), `timeline/overlays/useSuggestions.tsx`.
- No API, engine, schema, fingerprint or `RENDER_GRAPH_VERSION` change; CLI untouched; no new dependency.
- Depends on `editor-workspace-layout`. `track-drag-edit` depends on this change.
