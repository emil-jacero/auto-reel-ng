## Why

On 2026-11-18 the operator asked: "I want to be able to right click on a clip and get a dropdown of options I can
perform on the clip. Like ignoring it, rotating, etc."

Today every per-clip edit is a button in the inspector's Clip tab. To turn a clip on the track, the operator presses
it, crosses the window to the inspector and finds Rotate. Each edit is a round trip. D-28 modelled Edit mode on
iMovie, where a right-click (Control-click) on a clip lists what can be done to it, right where the clip is. Every edit
such a menu needs already exists as a guarded, undoable draft edit (`edit/EventEditor.tsx`). What is missing is a
menu.

This reverses part of a recorded decision. The archived `compact-bin-tools` proposal listed "Clip selection, a
context menu or a menu button" as a non-goal ("The tools stay direct buttons"). Clip selection came with
`editor-selection`, and the context menu comes now. The other half still holds: every tool stays a direct button,
and the menu is a second route to it, never the only one.

This is slice 7 of the editor workspace (HLD §6 item 10, GUI v3; `docs/editor-workspace.md`). It is the second of the
four follow-ups agreed on 2026-11-18: shortcuts, a clip context menu, a plain clip list, and seamless playback.

## What Changes

- **A clip's menu on the track.** In Edit mode, one gesture opens a menu for a clip:
  - a right-click anywhere on the clip's block (its body, its edge tools or a cut's handles);
  - Shift+F10 or the Menu key on a focused clip block.

  The menu opens at the pointer, or under the block when opened by a key. Opening it selects the clip, so the Clip tab
  shows it, unless the clip or one of its cuts is already selected. The playhead does not move.
- **Items**, headed by the clip's name, in four groups:
  - Rotate left, Rotate right
  - Cut at playhead, Use frame as poster
  - Move to «chapter», one item per other chapter the Timeline draws. It moves the clip to the end of that chapter, as
    a drop on that chapter's band does. There is no such item when only one chapter is drawn.
  - Ignore clip

  Each item makes the same draft edit as its Clip tab control, with the same announcement and one Undo step ("Undo
  rotation of s1710002.mp4").
- **Unavailable items stay listed**, marked unavailable, with the reason in words under the item. The words are the
  Clip tab's: with the playhead in another clip, Cut at playhead says "Move the playhead into s1710002.mp4 to cut
  there." While a save is pending, every item is unavailable under one line that says so. Choosing an unavailable item
  says why and leaves the menu open.
- **Keyboard and focus.**
  - The menu is an ARIA menu. Up and Down move (wrapping), Home and End go to the ends, Enter and Space choose, and
    Escape, Tab and Shift+Tab close it.
  - While it has focus it keeps every key except Ctrl/Cmd chords, so no workspace shortcut (Space, Q/W/S, arrows) or
    track key acts behind it.
  - Escape closes only the menu, and the selection stays.
  - When the menu closes, focus goes back to the clip's block. After Ignore clip it goes to the next clip's block.
- **Gestures.** A right-button press never starts a drag. A right-click during a drag cancels the drag and opens no
  menu. Elsewhere on the track (empty ground, the ruler, card blocks, suggestion marks) the browser keeps its own menu.
- **Touch.** A long press opens the menu where the browser reports it as a context-menu request. Under a coarse
  pointer each item is at least 44 px tall.
- **Keyboard shortcuts list** (`editor-shortcuts`) gains two rows from its table:
  - "Shift+F10 or Menu key on a clip: Open its menu" (Editing)
  - "Right-click a clip: Open its menu" (Mouse)
- **One reusable menu.** The Timeline owns one clip menu and one way to open it. `plain-clip-bin` will open the same
  menu from its rows. The menu acts on the one clip it was opened on.

## Non-goals

- **Today's bin rows.** The chapter-list bin is about to be replaced by `plain-clip-bin`, which wires its own rows to
  this menu. The menu items an ignored or a missing clip would need (Include, Remove from reel.yaml) come with those
  rows, because no track block shows such a clip.
- **Acting on several clips.** Multi-select comes with `clip-multi-select` (the next change), which makes the menu act
  on the selection.
- **Submenus, type-ahead, checkable items,** and menus for cuts, title cards or suggestions.
- **Acting at the pointer's time.** A right-click does not move the playhead, and there is no "Cut here". Cut at
  playhead and Use frame as poster work at the playhead, as in the Clip tab.
- **Trimming from the menu.** The edge tools and the typed Trim In and Trim Out stay the way to trim.
- **A long-press timer of our own.** Safari on iOS sends no context-menu request on a long press, so there the Clip
  tab remains the way to every item.
- **Out of scope here:** Split, Duplicate and using one clip several times (dropped on 2026-11-18). The read view,
  which has no Timeline.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`: ADDED
  - "Edit mode offers a clip's edits in a menu"
  - "An unavailable item in the clip menu says why"
  - "The clip menu is operated by keyboard and keeps its keys"
  - "The clip menu gives focus back and closes when it is done"
  - "The clip menu fits the window and is large enough to touch"
- `event-timeline`:
  - ADDED "A clip block opens the clip's menu" and "A right-click never drags a clip, and cancels a drag".
  - MODIFIED "A clip is selected on the track or in the bin" and "A clip is reordered by dragging it on the track".
    The only change is the wording "primary-button press", so that the new right-click rules do not contradict them.

## Impact

- **Web only.**
  - New pure modules, tested with `node:test`:
    - `web/src/timeline/clipMenu.ts`: the items, their reasons, the selection rule and where focus goes after.
    - `web/src/ui/menu.ts`: placement and keys.
  - New component `web/src/ui/Menu.tsx`, a menu in a `popover="manual"`.
  - `timeline/Timeline.tsx` / `useTimeline` owns the one clip menu and wires its items to the existing edits.
  - `timeline/ClipTab.tsx`: its "+ Cut at playhead" code is lifted out so that the menu shares it.
  - `timeline/Track.tsx` opens the menu, and `timeline/ClipDrag.tsx` cancels a drag on a right-click.
  - `edit/workspace/shortcuts.ts` gets two rows.
- **Unchanged:**
  - No API, engine, `reel.yaml` or `config.yaml` schema change, no Alembic migration and no rescan.
  - No change to rendered output, the staleness fingerprint or `RENDER_GRAPH_VERSION`.
  - The CLI is untouched. This is a browser interaction, with no engine capability for the CLI to reach
    (Principle V).
  - No new reducer action. Move to is the existing `clip-drop` edit at the end of the chapter, the edit a drop on the
    chapter's band already makes.
  - No new dependency. The menu uses the browser's Popover API, as the toasts do, and a small placement function. A
    menu library (Radix, Floating UI) would be a first runtime dependency for about 150 lines of code (Principle VII).
- **Depends on** `editor-shortcuts`, which must be archived first. This change uses its key layer, its last-input
  record (`modality.ts`) and its `SHORTCUTS` table.
- **Size:** about one day.
