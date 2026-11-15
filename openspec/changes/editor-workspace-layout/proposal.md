## Why

The user set the editor workspace as the next GUI goal on 2026-11-14 (`docs/editor-workspace.md`; mock board
**Event page: Edit mode (editor workspace)**): "I click Edit and it resembles something like the simple iMovie".
Today Edit mode is a long page of stacked panels inside the 72rem event page (Details, Poster, Timeline, marks,
chapter lists, save bar), so the picture, the track and the clip lists are never on screen together, and every
edit means scrolling. This change is slice 1 of the workspace (HLD §6 item 10, GUI v3; D-20 for the Timeline).

## What Changes

- **Edit opens a full-window workspace** instead of the stacked page: no app header, no page width limit, the
  window's full height; Done (and the top bar's back control) leaves it through today's leave flow.
- **Top bar**: back to Events, event title with date and location, the unsaved summary (today's save-bar words),
  Reset, Save (Ctrl/Cmd+S), Done, and the theme switch (the same `auto-reel:theme` setting as the app header).
- **Four panes**: clip **bin** (left), **viewer** (centre), **inspector** (right), **Timeline** (bottom).
  - Bin: today's chapter lists in compact rows (thumbnail, name, kept length), with every existing list action:
    drag and keyboard reorder, moves between chapters, marks and Move marked to…, Add chapter, and the New,
    Ignored and Missing clips.
  - Viewer: the Timeline's picture and transport (play, previous / next clip, time readout, Use as poster).
  - Inspector: tabs picked by hand — **Event** (Details form, Poster, Title cards On/Off, card style) and **Cut**
    (the selected cut's fields and the selected suggestion's decision, as today below the track).
  - Timeline: tool row (Trim In/Out, Snap, zoom, Fit, movie stats) and the lanes, as today.
- **Light and dark** both, following the operator's theme.
- Target window 1280×720 with no page scroll; narrower windows stack the panes in one column (not critical).
- The card editor stays a dialog in this change; `editor-selection` docks it.

## Non-goals

- Inspector that follows the selection, the Clip tab, a docked card editor, bin↔track selection (`editor-selection`).
- Dragging on the track (`track-drag-edit`), Undo/Redo (`editor-undo`), Split (`clip-split`).
- Any API, engine, `reel.yaml` change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`: ADDED the workspace frame, top bar, bin, viewer, inspector and narrow-window rules; REMOVED "Edit mode
  lines up with the event page and fits a phone" and "Edit mode's save bar rests in the page when it would hide the
  editor" (there is no stacked page and no bottom save bar any more).
- `event-timeline`: MODIFIED "The Timeline is shown only in Edit mode and draws the draft" (its place is the bottom
  pane, the picture is in the viewer).

## Impact

- Web only (`web/`): new `edit/workspace/` (frame, top bar, panes, CSS), `edit/EventEditor.tsx` (renders into panes
  instead of a stack), `events/EventDetail.tsx` (Edit renders the workspace in place of the page), `timeline/Timeline.tsx`
  split into viewer and track parts sharing one state, `edit/SaveBar.tsx` (top-bar form), `shell/` (theme switch reused).
- No API, engine, schema, fingerprint or `RENDER_GRAPH_VERSION` change; CLI untouched. No new dependency.
- Size: the largest slice (about 2–3 days). Principle VIII: if the tasks grow past the list below, split the bin
  into its own change.
- Depends on `track-draft-order` (the bin and the track must show the same order). `editor-selection` and
  `editor-undo` depend on this change.
