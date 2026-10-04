## Why

Operator feedback (2026-10-04, Edit mode scrolled to chapter "Test"): selecting a title card opens its inspector
below the Timeline's track, far from the chapter list, so editing a card means scrolling back up and then down again.
The editor belongs where the operator is: over the page, in a dialog, opened by the card they pressed.

## What Changes

- The card inspector (title, subtitle, background, font, sizes, colour, position, per-field "Use event style", live
  preview, "Undo changes to this card") opens in a modal dialog (the existing `ui/Dialog`) when a card row in the chapter
  list or a card block on the Timeline is activated in Edit mode. The inline inspector slot under the track is removed for
  Edit mode (the read view keeps its words-only slot).
- Dialog behaviour: named "Title card for <chapter>" / "Opening title card"; preview above the fields at <= 600 px and
  beside them when wider; focus into the first field and back to the opener; Escape, Close and Done close it; edits go
  into the page draft (no Save inside); full-screen sheet at <= 600 px; the page behind does not scroll.
- Selection highlight on the row and block stays while open and after close; pressing the selected card reopens the dialog.
- A press on a block's duration handle still only selects (a modal opening under a drag would end it).
- Out of scope: the event-wide "Card style for this event" panel stays where it is; `timeline-plays-cards` (parallel)
  owns Timeline block playback, this change only makes activating a block open the dialog.
- HLD: record the placement change (tasks 5.2).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`: "A selected title card opens its inspector in Edit mode" now opens a modal dialog instead of an inline panel.
- `event-timeline`: the card selection requirement opens the dialog in Edit mode; the handle press selects without opening it.

## Impact

`web/` only: `web/src/edit/card/Inspector.tsx` (panel becomes dialog content), `web/src/timeline/TimelineSection.tsx`
(slot removed in Edit mode), `web/src/edit/CardRow.tsx`, the Timeline card block, `useCardSelection.ts` (open state),
`web/src/styles/components.css` / `card.css`. No API, engine, schema or staleness change; no `RENDER_GRAPH_VERSION` bump.
