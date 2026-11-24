## Why

The operator asked (2026-11-23): "The Left, Right and Bottom panes, all should be resizable by hovering over their
line and dragging." Reviewing the first plan, which kept a 20rem middle row and so left the Timeline unresizable below
660 px of window height, the operator added: "I want all the panes to be resizable and hide if i resize them to min."

Today the workspace's panes are fixed (`docs/editor-workspace.md` row 1.4; HLD D-28 "The panes"):
- the bin is `clamp(240px, 22vw, 320px)` (282 px at 1280, 317 px at 1440);
- the inspector is 340 px;
- the Timeline is `minmax(280px, 38vh)` tall;
- the viewer takes the rest.

These widths are a compromise. A long event wants a taller Timeline or a wider bin. Close picture work wants a larger
viewer, or no bin and no inspector at all. Editing title cards wants a wider inspector. An editor modelled on iMovie
(D-28) lets the operator move the lines between panes and put a pane away, as VS Code's sashes do. Nothing in the
workspace needs fixed panes. The Timeline spans all three columns, so a moved or hidden side pane never changes its
width or its Fit zoom.

The pane lines are 1 px borders today (`.ws-binbox` `border-inline-end`, `.ws-insp` `border-inline-start`, `.ws-tl`
`border-block-start` in `web/src/edit/workspace/workspace.css`). No archived change or doc has discussed resizing.
This change reverses row 1.4's "fixed".

## What Changes

- **Three pane borders can be dragged at every window size of the side-by-side layout** (from 960 CSS pixels wide,
  any height). These are the bin's right edge, the inspector's left edge and the Timeline's top edge.
  - Hovering a border shows a resize cursor and highlights the line. Dragging resizes that pane and the viewer takes
    up the difference.
  - A double-click on the border of a shown pane puts it back to today's size.
  - Escape during a drag puts the size back and keeps the selection.
  - Pressing a border does not move keyboard focus, so after a drag Left and Right still step the playhead.
- **A pane dragged past its smallest size hides** (editor-style, as VS Code's sashes).
  - Past the minimum the pane stops at it; dragged on beyond half its minimum it snaps away: its grid track becomes
    0 and the viewer (or, for the Timeline, the middle row) takes the room.
  - A hidden pane leaves its border at the window's edge, drawn as a thin line that shows the resize cursor.
    Dragging it back out shows the pane again: at its minimum once past half of it, then following the pointer.
  - A double-click on a hidden pane's border, or Enter on it, shows the pane at its kept size. Enter on a shown
    pane's border hides it (WAI-ARIA window splitter).
  - A hidden pane stays mounted but is `inert` and invisible: out of the Tab order, the accessibility tree and hit
    testing. A hidden Timeline keeps playing in the viewer; a hidden inspector keeps the Timeline's parts portalled
    into its tabs and is shown by a save refused at one of its fields; a hidden bin keeps its state, closes its
    player's open preview and takes no drops.
  - A pane is never hidden by anything but the operator: a small window shrinks panes, it does not hide them.
- **The borders are keyboard separators** (WAI-ARIA `role="separator"`, focusable, in reading order).
  - Each has a name ("Resize the clip bin") and gives its size in words, or "hidden".
  - Left/Right (on the side borders) or Up/Down (on the Timeline's border) move it 16 px, or 64 px with Shift. A
    press that would shrink a pane already at its minimum hides it; a press that grows a hidden pane shows it at its
    minimum. Home and End take it to the pane's smallest and largest shown size. Enter hides or shows it.
  - A focused border never steps the playhead.
- **Limits keep the workspace usable.**
  - Smallest shown sizes: bin 240 px (the compact player's guaranteed width), inspector 320 px, Timeline 200 px.
  - The viewer keeps at least 20rem of width. The middle row keeps at least 20rem of height while the bin is shown
    (the bin column with its player shown and its information closed needs about that much with a mouse), and about
    14rem (the viewer's transport and a picture; measured in task 3.1) while the bin is hidden. With the bin's
    information open, or a coarse pointer, the bin's list shrinks first (to its heading and one row), then ClipInfo's body, then the bin's box scrolls (no control is
    clipped out of reach) at that height, and nothing is drawn over the Timeline.
  - Dragging one side pane into the viewer's limit stops it there. It does not push the other side pane, and nothing
    moves after release, with two exceptions: showing a hidden side pane in a window without room for both kept sizes
    draws the other side pane narrower (its kept size is unchanged), and a Timeline that the middle row holds short lengthens when the bin is
    hidden and shortens again when it is shown (the middle row's least height follows the bin).
  - **When the window is too small for every shown pane's minimum**, the panes shrink to their minimums and are never
    hidden; then the viewer and the middle row give way; then content is cut or scrolled inside the panes. The page never
    scrolls in the side-by-side layout, at any height.
- **Sizes and hidden panes are kept in the browser.** They are stored for all events and across visits, in
  `auto-reel:workspace-panes` in `localStorage`.
  - A pane the operator never resized follows today's rule, clamped to the window, so a workspace that was never
    touched looks exactly as it does today from 960×648 (16 px root font; 649 with the 49 px top bar drawn). Below that height an untouched Timeline now
    shrinks toward 200 px so that the middle row keeps 20rem; today it stays 280 px and squeezes the bin's player.
  - A narrower window shrinks panes toward their minimums without forgetting the chosen size, and a wider window
    brings it back. Hiding a pane keeps its size for when it is shown again.
- **The Keyboard shortcuts list** gains the pane-border keys and gestures (`focused` and `mouse` rows). Ctrl, Alt
  and Meta arrows on a border stay the browser's; Space on a border plays, as on any non-Space control.
- **The save explanation's cap follows the Timeline.** That cap is `--ws-alert-max`, and the panel ends above the
  Timeline. It is now measured again whenever the Timeline's height changes, not only on a window resize; with the
  Timeline hidden it ends above the window's bottom edge.

## Non-goals

- Shortcuts that toggle a pane from anywhere (as VS Code's Ctrl+B / Ctrl+J). They need a new workspace command, its
  dispatch and free keys (Ctrl+B and Ctrl+J are browser keys; the free single letters are few). Listed as a
  follow-up; the keyboard path in scope is Enter on the focused border.
- A menu or button that hides or shows panes. The border is the one control.
- Resizing or hiding in the stacked layout below 960 px: there the borders are not shown, and the stored sizes and
  hidden panes are not applied (every pane shows, stacked, as today).
- Sizes per event or per tab session. Sizes are per browser.
- A drag that pushes the opposite side pane. Only a window resize shrinks both side panes.
- Resizing within a pane, such as the bin's player against its list or ClipInfo's height.
- Changing the viewer's 16:9 stage. A narrow, tall viewer letterboxes as it already does at 960 px.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`:
  - ADDED "The workspace's pane borders can be dragged".
  - ADDED "Hiding or showing the bin moves a Timeline held short" (the one pane another border changes).
  - ADDED "A pane border shows itself under the pointer" (cursor, highlight, hit strip clear of controls).
  - ADDED "A pane dragged past its least size hides" (the snap at half the minimum).
  - ADDED "A pane hides and comes back while the border is dragged" (live, and Escape).
  - ADDED "A pane hidden only during a drag keeps focus".
  - ADDED "A hidden pane's border stays at the window's edge" (drag back out).
  - ADDED "A double-click or Enter shows a hidden pane" (and Enter hides).
  - ADDED "A hidden pane is out of the way" (not drawn, not in the Tab order or the accessibility tree).
  - ADDED "A hidden Timeline keeps playing".
  - ADDED "A hidden inspector keeps up with the page" (the portals, a save's refusal).
  - ADDED "A hidden bin keeps its state, not its sound or its drops".
  - ADDED "A resized pane keeps the workspace usable" (the minimums, no push).
  - ADDED "Showing a hidden side pane may narrow the other" (both drawn in proportion; the narrower width is not stored).
  - ADDED "The side-by-side workspace never scrolls the page" (from 960 wide, any height).
  - ADDED "The middle row at its least height stays usable" (the bin's player, a list row, the transport).
  - ADDED "A window too small for every least size shrinks panes, never hides them".
  - ADDED "A pane border press changes only the pane" (focus, Escape, double-click).
  - ADDED "Each pane border is a named separator in the Tab order".
  - ADDED "Keys on a pane border move it".
  - ADDED "Keys on a pane border hide and show it".
  - ADDED "Other keys on a pane border keep their meaning" (Ctrl, Alt and Meta arrows; Space).
  - ADDED "Pane sizes and hidden panes are kept in the browser".
  - ADDED "A pane never resized follows its default size" (clamped to the window).
  - ADDED "Kept pane sizes fit the window" (shrink and restore).
  - ADDED "Stacked panes have no borders and no hidden panes".
  - MODIFIED "Workspace shortcuts never act in fields, dialogs, a clip preview or a drag": a focused pane border takes
    the arrows and Enter, and resizing a pane is a drag.
  - MODIFIED "The workspace lists its keyboard shortcuts": the list also names the pane borders' keys and gestures.

## Impact

- **Web only.**
  - New in `web/src/edit/workspace/`:
    - `paneSizes.ts`, with the pure limits, clamping, snap, drag, key, commit and parse maths;
    - `paneSizesPref.ts`, the stored-panes module store, with the one shared "stacked" source and the request that
      shows a pane from outside the workspace;
    - `PaneSeparator.tsx`, the separator;
    - their `node:test` tests, and `workspaceCss.test.ts`.
  - Changed:
    - `Workspace.tsx`: the separators, the custom properties, the hidden panes' `inert` and `data-hidden`, focus
      leaving a pane that hides, and the extra `.ws-tl` observation;
    - `workspace.css`: the Timeline row's `--ws-tl-h`, the separators' styles (at rest, hover, focus, drag, and the
      hidden pane's edge line), the hidden panes' rules, `overflow: clip` on `.ws` and a vertically scrolling `.ws-binbox` in the wide frame;
    - `shortcuts.ts`: `separator` in `ARROW_ROLES`, plus the list rows;
    - `BinPlayer.tsx`: a hidden bin closes the open preview, as Hide player does;
    - `EventEditor.tsx`: `overBin` is false while the bin is hidden; a save refused at an inspector field (Details, a
      title card's or the card style's) shows a hidden inspector first, and the Details refusal takes focus only once
      the inspector is shown.
- **Unchanged:**
  - No API, engine, `reel.yaml` or `config.yaml` schema, Alembic migration or rescan.
  - No change to rendered output, the staleness fingerprint or `RENDER_GRAPH_VERSION`.
  - The CLI is untouched: this is browser layout, with no engine capability for the CLI to reach (Principle V).
  - No new dependency and no new design token.
- **Depends on** nothing in flight. The workspace (`editor-workspace-layout`), the shortcuts layer
  (`editor-shortcuts`) and the plain bin (`plain-clip-bin`) are archived. It is independent of the title-card scrub
  fix proposed alongside it.
- **Docs:** HLD D-28 "The panes" amended and a §6 item 10 line added; `docs/editor-workspace.md` row 1.4 and a new
  change-table row.
- **Size:** about two days.
