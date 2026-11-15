## Why

Split at the playhead is the one feature in the goal (`docs/editor-workspace.md` §6.12; mock board **Event page: Edit
mode (editor workspace)**, the dashed Split button) that may need a `reel.yaml` change. iMovie's split turns one clip
into two that can be moved apart. `reel.yaml` lists each clip once per chapter, keyed by identity, so "one clip in two
places" may not be expressible. This change decides the model **before** building it (explore session 2026-11-15).
Slice 5 of the workspace (HLD §6 item 10, GUI v3; D-2 for `reel.yaml` as the source of truth).

## What Changes

Decided in task 0.3 (explore), then one of:

- **A. Split = a boundary inside the clip, no move apart**: Split at the playhead marks a boundary that the track
  draws as two blocks of the same clip; the halves cannot be reordered apart. Web only, if the boundary can be stored
  without a schema change (task 0.2).
- **B. Split = one clip used twice**: `reel.yaml` gains clip *uses* (the same identity twice, each with its own
  trims), so the halves can move apart, into different chapters. Touches `reel/` schema, `editorial-write`, the
  fingerprint's editorial input, the API body and the web draft; it becomes its own plan of several changes.
- **C. Drop Split**: "cut a span" already removes the middle of a clip.

Until 0.3 decides, everything below is provisional.

## Non-goals

- Splitting a title card.
- Splitting several clips at once.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `event-timeline` (options A and B): ADDED Split at the playhead.
- Option B only, to be listed after 0.3: `reel-document`, `editorial-write`, `change-detection`.

## Impact

- Option A: web only (`timeline/`, `edit/`); no API, engine, schema, fingerprint or `RENDER_GRAPH_VERSION` change.
- Option B: engine + API + web; `reel.yaml` schema change; fingerprint input change (Principle IV) and possibly a
  `RENDER_GRAPH_VERSION` bump; per Principle VIII it MUST be split into several changes after 0.3.
- Depends on `track-drag-edit` (a split only matters once halves can be dragged) and on the decision in 0.3.
