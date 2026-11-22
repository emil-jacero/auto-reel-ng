## Why

The operator asked on 2026-11-18 for "a small player at the top (that can be minimized)" of the clip list. The plain
rows of that list keep no buttons. Today each bin row holds a clip's own edits:
- Watch, which opens the clip's preview inside the row's Cuts panel;
- Move up and Move down, Rotate, Include (an ignored clip) and Remove or Undo (a missing clip);
- the Cuts panel.

The inspector's Clip tab already edits the selected clip (HLD D-28, "The inspector follows it"). But the Timeline draws
the tab, for a clip the track draws, so it is empty in three cases:
- while the track is not open (Prepare, "The Timeline asks for the clips' proxies when they are missing");
- for an ignored clip;
- for a missing clip.

These are exactly the clips whose edits live only in the bin rows. The Clip tab must hold them before the rows lose
their buttons. Otherwise an event with one failed proxy could no longer be reordered at all, and a touch or
screen-reader user would lose the bin's Move up and Move down. Those are the reorder path that D-28's "No List view"
kept the bin for.

This is the third of four changes that together build the plain clip list, the third of the four follow-ups agreed on
2026-11-18 (HLD §6 item 10, GUI v3; `docs/editor-workspace.md`).

## What Changes

- **The player at the top of the bin.**
  - **What it shows.** The clip preview leaves the Cuts panel and docks above the bin's lists, where it shows the
    selected clip: the clip pressed last of several, or a selected cut's clip. It keeps that clip while a card, a
    suggestion or nothing is selected.
  - **When it loads.** Until its Play is pressed it shows the clip's thumbnail and loads nothing, so selecting clips
    stays free.
  - **One video.** Play releases the Timeline's video, as opening a preview does today. Moving the Timeline's
    playhead closes the preview again, and only one video exists at a time ("Edit mode holds one video at a time").
  - **Hide player** removes it, leaving a Show player button in the bin toolbar's first row beside the Clips help, and
    the choice is kept in the browser.
  - **Its controls are today's**: Play, the playhead, Skip cuts, Set From, Set To, and Play original or preview copy.
    Hide player replaces Close. Set From and Set To write into the shown clip's Cuts panel, shown or hidden.
- **A row's thumbnail ("Watch <name>")** selects the clip and moves focus to the player's Play. The Cuts panel has no
  Watch control of its own any more.
- **The Clip tab edits every selected clip, on the track or not.**
  - **Always shown:** the clip's name, chapter and position, and status in words, also in Prepare.
  - **For any clip a chapter plays:**
    - **Move earlier** and **Move later**: one place in the chapter, as the bin's Move up and Move down, and into the
      neighbouring chapter at an edge, as Alt and an arrow. A missing clip stops at its own chapter's edge, as its
      drag does.
    - Move to… (`clip-multi-select`) and Rotate.
  - **By status:** Include clip for an ignored clip, Ignore clip for a played one, and Remove from reel.yaml or Undo
    for a missing one.
  - **Only while the track draws the clip:** Trim In and Out, the cuts with "+ Cut at playhead", and Use frame as
    poster, as today.
- **The bin rows keep their buttons** for one more change. The Clip tab is a second route until `plain-clip-bin`
  makes the rows plain.

## Non-goals

- Making the rows plain, or moving the Cuts panel into the Clip tab (`plain-clip-bin`).
- Including or removing several clips at once from the Clip tab.
- A second video, or seamless playback (`seamless-playback`, a later change).
- Autoplay on selection. Selecting a clip never loads media.
- A player in the read view, which keeps its own "Watch" players.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-app`:
  - ADDED "The Clip tab offers a clip's edits whether or not the track draws it".
  - MODIFIED "Edit mode previews a clip on request": the preview is the bin's player, showing the selected clip.
  - MODIFIED "A clip's preview sets cut times at the playhead and plays the clip as the movie will": Set From and Set
    To write into the shown clip's Cuts panel.
  - MODIFIED "A clip's preview plays its preview copy when one is ready" (two scenarios: the player stays with a moved
    clip, and Hide player replaces Close).
  - MODIFIED "The event page plays one video at a time" (the Edit-mode scenario).
  - MODIFIED "The Clip tab edits the selected clip": Move earlier and Move later.
  - MODIFIED "The clip bin holds the chapters' clip lists": the player sits above the lists. The rows-in-view target
    is measured with the player hidden.
  - MODIFIED "The marks line is one aligned unit": while the player is hidden, its Show player sits in the toolbar's
    first row beside the Clips help; the toolbar keeps its two rows and its height.
  - MODIFIED "Workspace shortcuts never act in fields, dialogs, a clip preview or a drag" (from `editor-shortcuts`):
    the whole player counts as a clip preview, so Space on its Play presses Play after a click.
- `event-timeline`:
  - MODIFIED "Edit mode holds one video at a time": the preview is the player's, and selecting a clip does not release
    the Timeline's video.
  - MODIFIED "A clip is reordered by dragging it on the track": a finger reorders with Move earlier and Move later.
  - MODIFIED "The Edit-mode Timeline draws the draft's order and chapters": its reorder scenario uses the Clip tab, not
    a chapter's list in the bin.

## Impact

- **Web only.**
  - `preview/ClipPreview.tsx` renders in a new `edit/BinPlayer.tsx` at the top of the bin, and no longer in
    `cuts/CutsPanel.tsx`.
  - `preview/previews.ts` follows the shown clip.
  - The Clip tab's content is built by `EventEditor` for any selected clip. The Timeline adds its track-only parts
    (trims, cuts, poster) through a slot.
  - `edit/ClipOrderList.tsx`: the thumbnail's Watch selects the clip and focuses the player.
- **Unchanged:**
  - No API, engine, `reel.yaml` or `config.yaml` schema change, no Alembic migration and no rescan.
  - No change to rendered output, the staleness fingerprint or `RENDER_GRAPH_VERSION`.
  - The CLI is untouched. These are browser controls over existing draft edits (Principle V).
  - No new dependency, and no new draft action. Move earlier and Move later dispatch the existing `move` or
    `clip-drop`, and Include, Remove and Undo are today's `ignore`, `remove` and `restore`.
- **Depends on** `chapters-in-inspector`, which must be archived first.
- **Size:** about two days.
