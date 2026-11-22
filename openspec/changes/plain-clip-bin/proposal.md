## Why

On 2026-11-18 the operator looked at the bin, with its chapter groups, drag handles, Move up/down arrows, rotate
buttons, mark checkboxes, "Choose a chapter → Move" and the Ignored clips section, and asked:

> "I don't see the point of this sidebar when I can just drag to move clips in the timeline. The left list should
> show all clips with a small player at the top (that can be minimized). The list should be plain. Right-clicking on
> the clip in this list also gives me the same options. The bottom part of the list should show clip information,
> like metadata and any cuts in the clip."

The bin is today's chapter lists in compact form. HLD D-28's "No List view" kept it that way so that keyboard and
screen-reader reordering needed no second screen (`docs/editor-workspace.md` 1.3). Three changes have since given
each of its jobs another home:
- `clip-multi-select`: groups are the selection;
- `chapters-in-inspector`: chapter tools are in the Event tab;
- `clip-tab-and-player`: the player sits at the top of the bin, and the Clip tab edits every clip, with Move earlier
  and Move later for keyboard, touch and screen readers.

The track's drag and Alt+arrows cover pointer and keyboard reordering. What is left in the bin duplicates them. This
change makes the bin the plain list the operator asked for. It reverses D-28's "No List view" for the bin's shape,
but not its reason: the non-pointer reorder path now lives in the Clip tab. It is close to the workspace mock's first
idea: an "On timeline" list and a "Not on timeline" section (`editor-workspace.md` 3.1, 3.3).

This is the last of four changes that together build the plain clip list, the third of the four follow-ups agreed on
2026-11-18 (HLD §6 item 10, GUI v3).

## What Changes

- **One plain list of every clip**, between the player and the information. It lists the clips the chapters list,
  in play order (new and missing ones in their places), then "Ignored · N clips, not played", then "Removed from
  reel.yaml when you save · N clips". A row shows:
  - the frame;
  - the name, as the page names it;
  - "Kvällen · 2 of 3" (with "· was 4" or "· from Main" after a move);
  - the kept length;
  - the status icon, and "typed" when a typed cut waits.

  A row holds no control.
- **Selecting in the list works as on the track** (`clip-multi-select`).
  - **Pointer:** a click, Ctrl/Cmd+click and Shift+click.
  - **Keyboard:** the list is one stop. Up, Down, Home and End move, Enter selects, Ctrl/Cmd+Enter adds and
    Shift+Enter selects a range.
  - A press on a row's frame also moves focus to the player's Play.
- **Right-click, Shift+F10 or the Menu key on a row** opens the clip menu (`clip-context-menu`), acting on the
  selection. For clips the track does not draw it offers:
  - **Include clip** (or "Include N clips") for an ignored clip;
  - **Remove from reel.yaml** or **Undo remove** for a missing clip;
  - Cut at playhead and Use frame as poster unavailable, saying why.

  The Clip tab's group view gains Include clips too.
- **Dragging.** An ignored clip's row still drags onto the track to include it, and a clip dragged off the track onto
  the bin is still ignored. No other row drags.
- **Clip information under the list.** It covers the player's clip:
  - from the event read: status, chapter and position, file size, modification time, and length and kept length;
  - from its ready proxy's facts: frame rate (and whether it varies), picture orientation and aspect ratio, the
    container's rotation and the sound's codec;
  - its cuts, read only.

  It makes no request, and says plainly what waits for a proxy. Hide information collapses it, and the choice is kept
  in the browser.
- **The Cuts panel moves into the Clip tab**, with its typed start and end, Remove and Undo and the "typed" rule. It
  is there with or without the track, and while the track draws the clip it also has "+ Cut at playhead" and each
  cut's Edit (today's Clip tab cut list, merged). Set From and Set To in the player fill it.
- **Removed from the bin**, each with its new home:

  | Removed | New home |
  |---|---|
  | chapter sections and headings | the Chapters list |
  | handles, keyboard lift and the bin's drag | the track and the Clip tab |
  | Move up / Move down | Move earlier / Move later |
  | marks, the marks line, Rotate marked, Move marked to… | the selection, and the Clip tab's group view |
  | row Rotate, Include and Remove / Undo buttons | the Clip tab and the menu |
  | per-row Cuts panels | the Clip tab |

  The Clips help is rewritten for the list.
- **BREAKING for habits, not for data.** The marks go; they were never saved. Selecting several clips needs Ctrl,
  Cmd or Shift, so touch users move clips one at a time. A long jump by keyboard is Move to… (end of a chapter), or
  Move earlier and Move later step by step.

## Non-goals

- **Filters or a search box in the list.** The order already groups clips by status.
- **A chapter-grouped view, or a switch between views** (D-28's "no second layout" still holds).
- **Source resolution, video codec, bitrate or capture date in the information.** The client has none of them. The
  proxy facts' width and height are the proxy's (540 on the short side), so the page shows orientation and aspect
  ratio, never "540 × 960". Adding them needs the proxy job to record them (`clip-proxies`) or a probe-backed read: a
  separate change, against the probe-free detail rule (`ClipOut`).
- **Dragging a clip that plays from the list onto the track** to move it. The track moves clips.
- **Selecting several clips by touch.**
- **Using one clip several times** (dropped on 2026-11-18), and seamless playback (`seamless-playback`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`:
  - ADDED:
    - "The clip bin lists every clip of the event as one plain list"
    - "The bin's list selects clips as the track does and opens their menu"
    - "The bin shows what the page knows of the shown clip"
    - "Edit mode opens on the event's editorial document and keeps the operator's edits"
    - "Edit mode moves clips on the track and in the Clip tab, and counts the fewest moves"
  - REMOVED, with Reason and Migration:
    - "The clip bin holds the chapters' clip lists"
    - "The bin's chapter headings and lists say what they hold"
    - "Edit mode drags clips between chapters"
    - "Edit mode marks clips to move together"
    - "Dragging a marked clip moves the whole marked group"
    - "Edit mode moves the marked clips to a chapter"
    - "The marks line is one aligned unit"
    - "The event page reorders clips within a chapter"
  - MODIFIED, every requirement whose words name the old bin's rows, handles, Cuts controls or marks:
    - the Cuts panel, the player, Set From, the Clip tab (one clip, without the track, several clips) and the menu;
    - the chapters, the Help toggles, row windowing, focus in view, touch sizes, clip names and the first-edit save bar;
    - the trim, the save and the read view's chapter tables.

    Most of these edits are a sentence or a scenario. The validator requires a MODIFIED block to keep every scenario
    of the requirement, so the delta is long. The behaviour changed is this change's alone.
- `clip-rotation`: REMOVED "The marked group turns together". Several clips turn as a selection, in the Clip tab and
  the menu.

## Impact

- **Web only.**
  - New pure modules, tested with `node:test`:
    - `edit/binList.ts`: the rows, their order, words and groups;
    - `edit/clipInfo.ts`: the information's words, from `ClipOut`, `ProxyFactsOut` and the draft's cuts.
  - New components: `edit/ClipBin.tsx` (the list) and `edit/ClipInfo.tsx` (the information).
  - `CutsPanel` renders in the Clip tab. `clipMenu.ts` gains Include and Remove. `EventEditor.tsx` gains
    `include-many`.
  - Deleted: `ClipOrderList.tsx`, `ChapterDrag.tsx`, `marks.ts`, `wideBin.ts`, the marks line and the bin's
    `@dnd-kit` use.

    `@dnd-kit` itself stays a dependency only if another surface still uses it. Task 2.5 checks this, and removes it
    from `package.json` otherwise.
- **Unchanged:**
  - No API, engine, `reel.yaml` or `config.yaml` schema change, no Alembic migration and no rescan.
  - No change to rendered output, the staleness fingerprint or `RENDER_GRAPH_VERSION`.
  - The CLI is untouched. This is the browser's layout of edits that already exist (Principle V).
  - No new dependency.
- **Depends on** `clip-tab-and-player`, which must be archived first.
- **Size:** about two days.
