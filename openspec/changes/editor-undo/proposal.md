## Why

Edit mode's draft has only Reset: one wrong drag or trim means redoing every other edit since the last save. Every
editor the workspace is modelled on (iMovie, Premiere) has Undo/Redo, and the goal lists it (`docs/editor-workspace.md`
§2.2; mock board **Event page: Edit mode (editor workspace)**, top bar). Slice 4 of the workspace (HLD §6 item 10,
GUI v3).

## What Changes

- **Undo / Redo** buttons in the workspace's top bar, and Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z and Ctrl+Y.
- Every draft edit is one step: a reorder or move, a trim release, a cut added/removed, a suggestion approved, a card
  or style field, a chapter added/renamed/deleted, a rotate, the poster, a metadata field.
- Typing in one field is one step until the field loses focus or 1 s passes without typing.
- In a text field the keys do the field's own undo, not the draft's.
- **Reset** is a step (it can be undone). **Save** clears the history (the saved state is the new start).
- The buttons say what they will undo ("Undo move of s1710002.mp4"); the step is announced politely.

## Non-goals

- History across page visits or after Save.
- Undo of writes to disk.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`: ADDED Undo/Redo of the Edit-mode draft.

## Impact

- Web only: new `edit/history.ts` (pure, `node:test`), `edit/EventEditor.tsx` (reducer wrapped), the workspace top bar.
- No API, engine, schema, fingerprint or `RENDER_GRAPH_VERSION` change; CLI untouched; no new dependency.
- Depends on `editor-workspace-layout` (the top bar). Independent of `editor-selection` and `track-drag-edit`: the
  history wraps the reducer, so actions added later are undoable without further work.
