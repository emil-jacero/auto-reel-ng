## Why

The operator reported that "Spacebar or any other shortcut is not working in the editor". A probe of the running app
(2026-11-18, Chromium) confirms it. Every Timeline key belongs to one element and works only while that element has
focus: Space and the arrows belong to the playhead, and `+ - 0 \`, Q, W and S to the track. Some examples:

- After a click on a clip, focus is on the clip's block, which takes Space for "select", so nothing plays.
- After a click on the video or on any button, Space does nothing.
- Only a click on the ruler (which focuses the playhead) makes Space play.

Ctrl+wheel zoom works only with the pointer over the track itself. Over the Timeline's tool row or the viewer it zooms
the whole page instead. Nothing on screen lists the keys: the list exists only as hidden text for screen readers.

D-28 modelled Edit mode on iMovie, and editors like it answer Space and the other edit keys wherever focus is in the
window. This is slice 6 of the editor workspace (HLD §6 item 10, GUI v3; `docs/editor-workspace.md`). It comes first of
the four follow-ups the operator agreed on 2026-11-18: shortcuts, a clip context menu, a plain clip list, and seamless
playback.

## What Changes

- **Workspace shortcuts.** In Edit mode's workspace the Timeline's keys work wherever focus is, not only on the
  playhead or the track:
  - Space plays or pauses.
  - Left and Right step a frame, and Shift with either steps a second.
  - `+` / `=`, `-`, `0` and `\` zoom.
  - Q, W and S are the edge tools.
  - Alt+Left and Alt+Right move the selected clip.
- **Where they are left alone.** The keys never act in a text field, a select or editable text, in an open dialog,
  inside an open clip preview, or during a drag. A control the operator reached by keyboard (Tab) keeps its own Space,
  so a keyboard user still presses a button with Space. A control that was clicked gives Space to Play. A widget that
  owns the arrows (a slider, a radio group, the trim handles, the suggestion marks) keeps them.
- **A clip block clicked with the mouse no longer takes Space.** Enter still selects the clip, and so does Space when
  the block was reached by keyboard.
- **Keyboard shortcuts list.** A "Keyboard shortcuts" button at the right of the top bar, and the `?` key, open a list
  of every key in the workspace, grouped:
  - playback
  - zoom
  - editing (including Ctrl/Cmd+S, Z and Y, A and R on a suggestion, and Escape)
  - mouse (Ctrl+wheel zoom, double-click to place the playhead)

  The list is drawn from the same table the keys are handled from, so the two cannot disagree.
- **A switch for single-key shortcuts** (WCAG 2.1.4, Character Key Shortcuts) in that list, on by default and kept in
  the browser. Off, the workspace answers no single-key shortcut. The keys of a focused playhead, track, handle or mark
  stay, as today.
- **Ctrl+wheel zoom** (Cmd+wheel, trackpad pinch) works over the whole bottom Timeline pane: the tool row, the lanes
  and the track. It zooms about the pointer over the track, and about the playhead elsewhere. Over the viewer, the bin
  and the inspector, Ctrl+wheel stays the browser's page zoom.

## Non-goals

- J/K/L shuttle. The proxy cannot be played backwards in the browser, and "faster" is not asked for.
- Remapping keys to other keys. The switch is the 2.1.4 mechanism.
- Keys for previous or next clip, Delete, or Split.
- The clip context menu (the next change, `clip-context-menu`).
- The read view: it has no Timeline.
- Plain-wheel and Shift+wheel scrolling stay as they are.
- Seamless playback across clips (`seamless-playback`, a later change).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`: ADDED workspace shortcuts that work wherever focus is, with the cases where they are left alone. ADDED the
  Keyboard shortcuts list and the single-key switch.
- `event-timeline`: MODIFIED "The playhead is operable by keyboard, a frame at a time". Its keys also work as workspace
  shortcuts, so "handled only when the playhead has focus" no longer holds in Edit mode. MODIFIED "The track zooms, and
  draws only what is in view". The zoom keys also work as workspace shortcuts, and Ctrl+wheel works over the Timeline's
  pane, not only the track.

## Impact

- **Web only.**
  - New pure modules in `web/src/edit/workspace/`: the key table and decision rules (`shortcuts.ts`) and the
    last-input tracker (`modality.ts`), tested with `node:test`.
  - `timeline/Timeline.tsx` / `useTimeline` gets the document listener and the wider wheel listener.
  - `timeline/Track.tsx` changes the clip block's Space.
  - `edit/workspace/TopBar.tsx` gets the button and the list.
  - `timeline/labels.ts` takes the key words from the table.
- **Unchanged:**
  - No API, engine, `reel.yaml` or `config.yaml` schema, Alembic migration or rescan.
  - No change to rendered output, the staleness fingerprint or `RENDER_GRAPH_VERSION`.
  - The CLI is untouched: this is a browser interaction, with no engine capability for the CLI to reach (Principle V).
  - No new dependency. The list uses the browser's own popover (`popover="auto"`), as the toasts already use
    `popover="manual"`.
- **Depends on** `editor-undo` (archived 2026-11-18): the top bar's Undo/Redo and the undo keys' guards are reused.
- **Size:** about one day.
