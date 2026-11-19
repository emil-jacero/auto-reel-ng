## Why

On 2026-11-18 the operator asked for a plain clip list in place of today's bin: "I don't see the point of this sidebar
when I can just drag to move clips in the timeline." In the same session the operator decided that edits of several
clips move to Ctrl/Shift+click selection on the track and in the list, replacing the marks, "Move marked to…" and
"Rotate marked", and that the right-click menu acts on that selection.

Today the workspace holds one selection of at most one clip (`editor-selection`, HLD D-28 "One selection",
`edit/workspace/selection.ts`). The only way to act on several clips is the bin's marks: a checkbox on each row's
thumbnail and the marks line above the chapters. Those exist only in the bin that the plain list replaces. So the
selection has to grow first, while the old bin still stands, and every group edit needs a home outside the bin:
- on the track, by dragging;
- in the inspector, by a button;
- in the clip menu (`clip-context-menu`), which today acts on the one clip it was opened on.

This is the first of four changes that together build the plain clip list, the third of the four follow-ups agreed on
2026-11-18 (HLD §6 item 10, GUI v3; `docs/editor-workspace.md`). Principle VIII splits it:
1. `clip-multi-select` (this change);
2. `chapters-in-inspector`;
3. `clip-tab-and-player`;
4. `plain-clip-bin`.

## What Changes

- **Several clips can be selected.**
  - On the track, Ctrl+click (Cmd+click on macOS) adds a clip block to the selection or takes it out.
  - Shift+click selects every clip drawn from the last clip pressed (the anchor) to the clicked one.
  - The same keys work on the rows of today's bin, in the bin's order.
  - From the keyboard, on a focused block, Ctrl/Cmd+Enter adds or removes and Shift+Enter selects the range. Enter
    alone still selects one clip.
  - A plain click still selects one clip alone, and Escape clears the whole selection.
  - Each selected block is outlined and shown as pressed, and "3 clips selected." is announced once.
- **Dragging a selected block drags them all.** When two or more clips are selected, a drag on any of them moves all of
  them, in play order, as one run to the drop place. Released over the bin, it ignores them all. While the group is
  held, the other blocks do not make room: a line and words show where the run lands, as the bin's group drag does
  today. Dragging a clip that is not selected moves that clip alone, as today.
- **The Clip tab acts on several clips.** With two or more clips selected, the Clip tab shows how many, and their
  names, and offers:
  - Rotate left and Rotate right, which turn each clip a quarter from its own turn, in one step;
  - **Move to…**, a chapter picker and a Move button that put the clips at the end of that chapter, in play order;
  - **Ignore clips**.

  With one clip selected, the Clip tab gains the same Move to…. Each of these is one Undo step ("Undo move of 3
  clips").
- **The clip menu acts on the selection.** Opened on a selected clip, the menu acts on every selected clip and is
  headed "3 clips". Cut at playhead and Use frame as poster then say "Select one clip to …". Opened on a clip that is
  not selected, it selects that clip alone first, as today.
- **Alt+Left and Alt+Right** with several clips selected move nothing, and say that they move one clip and that
  Move to… moves several.
- **The marks stay for now.** The bin keeps its marks, Move marked to… and Rotate marked until `plain-clip-bin`
  removes the old bin. The selection and the marks are separate. Either one's Move puts the move in the pending state
  that the specs call "a move of marked clips", and every control that waits for that move also waits for this one.

## Non-goals

- Removing the marks, Move marked to… or Rotate marked (`plain-clip-bin`).
- Selecting several clips by touch. Ctrl and Shift do not exist on touch, and the marks stay touch's way to move
  several clips until `plain-clip-bin`.
- Select all (Ctrl+A), and a selection of several cuts, title cards or suggestions.
- Clips making room live while a group is dragged on the track. The group drag shows a line, as the bin's does.
- Moving several clips with Alt and the arrows. A run of clips that is not contiguous has no "one place left".
- Trimming several clips at once.
- The keyboard model of the plain list (`plain-clip-bin`).
- Using one clip several times (dropped on 2026-11-18).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `event-timeline`:
  - MODIFIED "One selection in the workspace", which may now hold several clips.
  - MODIFIED "A clip is selected on the track or in the bin", which gains Ctrl/Cmd and Shift.
  - MODIFIED "A selected clip is moved by keyboard, and moving is inert while a save is pending": with several clips
    selected, Alt+arrows say why they move nothing.
  - MODIFIED "A clip block opens the clip's menu" (from `clip-context-menu`), which keeps a selection of several.
  - ADDED "Dragging one of several selected clips moves them all".
- `web-app`:
  - MODIFIED "The inspector follows the selection" and "The Clip tab edits the selected clip" (Move to… for one clip).
  - MODIFIED "Edit mode offers a clip's edits in a menu" (from `clip-context-menu`), which acts on the selection.
  - MODIFIED "An unavailable item in the clip menu says why" (from `clip-context-menu`): its lock words say "the move
    of several clips", which stays true once the marks are gone.
  - ADDED "The Clip tab acts on several selected clips".

## Impact

- **Web only.**
  - `edit/workspace/selection.ts`: a selection of several clips, with its press rules (pure, `node:test`).
  - `edit/EventEditor.tsx`: actions that move or ignore a given list of clips (`selection-move`, `selection-drop`,
    `ignore-many`), beside the marks' own actions, with Undo labels.
  - `timeline/Track.tsx`, `timeline/ClipDrag.tsx`, `timeline/clipDrag.ts`: modifier presses and the group drag.
  - `edit/ClipOrderList.tsx`: modifier presses on today's bin rows.
  - `timeline/ClipTab.tsx`: Move to…, and the tab for several clips.
  - `timeline/clipMenu.ts`: the menu's items for several clips.
- **Unchanged:**
  - No API, engine, `reel.yaml` or `config.yaml` schema change, no Alembic migration and no rescan.
  - No change to rendered output, the staleness fingerprint or `RENDER_GRAPH_VERSION`.
  - The CLI is untouched. Selection is a browser interaction, with no engine capability for the CLI to reach
    (Principle V).
  - No new dependency.
- **Depends on** `clip-context-menu`, which must be archived first. This change widens its menu and two of its
  requirements.
- **Size:** about two days.
