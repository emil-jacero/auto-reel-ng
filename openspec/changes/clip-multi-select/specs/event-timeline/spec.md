## ADDED Requirements

### Requirement: Dragging one of several selected clips moves them all

While two or more clips are selected, a drag of any selected block SHALL move every selected clip on the track, in
play order, as one run at the drop place, in one draft edit. The other blocks SHALL NOT make room: a line with words
("3 clips · Before s1710001.mp4") SHALL show the place, and the held blocks SHALL be dimmed. A release over the bin
SHALL ignore them all. The clips SHALL stay selected.

#### Scenario: Two clips of Kvällen dragged into Main
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator selects `Kvällen/s1710002.mp4`, Ctrl+clicks
  `Kvällen/s1710003.mp4`, drags `s1710003.mp4` left until the line says "2 clips · Before s1710001.mp4", and releases
- **THEN**
  - "Main" draws `s1710002.mp4`, `s1710003.mp4` and then `s1710001.mp4`
  - no block moved while the group was held
  - both clips are still selected
  - the top bar says "2 clips moved", and Undo says "Undo move of 2 clips"

#### Scenario: A group released over the bin
- **WHEN** `s1710001.mp4` and `s1710003.mp4` of `2024-06-27 - Grillning med grannar` are selected and the operator
  drags one of them onto the bin and releases
- **THEN** neither is drawn, the bin lists both as ignored, the top bar says "2 clips ignored", and one Undo brings
  both back

#### Scenario: A drop beside the group changes nothing
- **WHEN** `s1710002.mp4` and `s1710003.mp4` are selected and the operator drops them on the line between them
- **THEN** the draft is unchanged, nothing is counted, and "2 clips dropped, unchanged." is announced

#### Scenario: An unselected clip drags alone
- **WHEN** `s1710001.mp4` and `s1710002.mp4` are selected and the operator drags `s1710004.mp4`
- **THEN** only `s1710004.mp4` moves, the other clips make room live as for any one clip, and when the drag ends
  `s1710004.mp4` alone is selected

#### Scenario: Fifty clips are dropped in time
- **WHEN** in a Chromium window 1280 × 900, on an event whose first chapter draws 400 clips and whose second draws 3,
  the operator selects 50 clips of the first chapter with Shift+click and drags them into the second, five times in a
  fresh Edit mode each
- **THEN** the median time from the release to the next painted frame is at most 150 ms longer than that of dragging
  one clip from the first chapter into the second

## MODIFIED Requirements

### Requirement: One selection in the workspace

The workspace SHALL hold one selection: nothing, one or more clips, a cut, a title card or a suggestion. Selecting one
SHALL end any other, except that a clip MAY be added to or taken out of a selection of clips ("A clip is selected on
the track or in the bin"). Escape SHALL clear it, the whole of a selection of clips included. It SHALL survive a
Refresh and a save while its target is still in the event, and end when its target is gone; a selection of clips
SHALL keep the clips the event still lists, and end when it lists none of them. A cut is named by its place in its
clip's list, so a cut selection SHALL end when a new read numbers the cuts again. It SHALL be shown selected in more
than colour.

A selection of two or more clips SHALL be announced once as the count ("3 clips selected."). Adding a clip to it or
taking one out SHALL be announced with the clip's name and the new count ("s1710003.mp4 added. 3 clips selected.",
"s1710003.mp4 taken out. 2 clips selected."). The clip pressed last is the selection's **last clip**; the anchor of
a Shift press is the clip pressed last without Shift.

#### Scenario: Card ends clip
- **WHEN** `s1710003.mp4` is selected and the operator presses the "Kvällen" card block
- **THEN** the card is selected, the clip is no longer outlined, and the inspector shows the Title card tab

#### Scenario: Card ends a selection of clips
- **WHEN** three clips are selected and the operator presses the "Kvällen" card block
- **THEN** only the card is selected and no clip is outlined

#### Scenario: Cut selection ends with the read
- **WHEN** the second cut of a clip is selected, the first is removed and the operator saves
- **THEN** nothing is selected, and the cut that now stands second is not outlined

#### Scenario: Target deleted
- **WHEN** the selected card's chapter is deleted
- **THEN** nothing is selected and the inspector shows the Event tab

#### Scenario: A selected clip leaves the event
- **WHEN** `s1710001.mp4`, `s1710002.mp4` and `s1710004.mp4` are selected and a proxy job's read no longer lists
  `s1710004.mp4`
- **THEN** `s1710001.mp4` and `s1710002.mp4` are still selected

#### Scenario: Escape clears them all
- **WHEN** three clips are selected and the operator presses Escape with focus on the track
- **THEN** nothing is selected and the inspector shows the Event tab

### Requirement: A clip is selected on the track or in the bin

A primary-button press on a clip block's body (not its edge tools or handles) and a press on its bin row SHALL select
the clip. The block SHALL be outlined with trim handles and the row highlighted; each SHALL be scrolled into view in its
pane without moving keyboard focus there. A press on empty track SHALL select nothing.

With Ctrl held (Cmd on macOS), the press SHALL add the clip to the selection, or take it out when it was selected. With
Shift held, it SHALL select every clip from the anchor to the pressed one, in the order of the surface pressed: the
drawn order on the track, the bin's order in the bin. On a focused clip block, Enter SHALL select the clip alone,
Ctrl/Cmd+Enter SHALL add or take it out, and Shift+Enter SHALL select the range. While two or more clips are selected,
every one of their blocks SHALL be outlined and pressed, and every one of their rows highlighted. A press without Ctrl,
Cmd or Shift on a block that is one of several selected SHALL keep the selection while the press may still become a
drag, and SHALL select that clip alone when it is released without one.

A primary-button press with a mouse or a pen on a clip block's body that moves more than 3 px SHALL start a reorder drag
instead ("A clip is reordered by dragging it on the track", or "Dragging one of several selected clips moves them all"
when the block is one of several selected). The dragged clip, or the dragged clips, SHALL be the selection when the drag
ends, whether or not it made an edit; Escape during that drag cancels only the drag and keeps the selection.

#### Scenario: Bin to track
- **WHEN** the track shows 0–20 s and the operator presses the bin row of a clip drawn at 31 s
- **THEN** the clip is selected, the track scrolls so the clip is in view, and focus stays on the bin row

#### Scenario: Bin press again
- **WHEN** a clip is selected, the track is scrolled away from it, and the operator presses its bin row again
- **THEN** the track scrolls back to the clip

#### Scenario: Empty track
- **WHEN** the operator presses the track below the last lane
- **THEN** nothing is selected and the inspector shows the Event tab

#### Scenario: A press that moves 3 px or less only selects
- **WHEN** the operator presses a clip block's body and moves 2 px, then releases
- **THEN** the clip is selected and nothing was dragged

#### Scenario: Ctrl+click adds and takes out
- **WHEN** `s1710001.mp4` is selected and the operator Ctrl+clicks `s1710003.mp4`, then Ctrl+clicks `s1710001.mp4`
- **THEN** after the first click both blocks are outlined and pressed and "s1710003.mp4 added. 2 clips selected." is
  announced; after the second only `s1710003.mp4` is selected

#### Scenario: Shift+click selects a range across a chapter's edge
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator clicks `s1710001.mp4` (Main) and Shift+clicks
  `Kvällen/s1710003.mp4`
- **THEN** `s1710001.mp4`, `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4` are selected and "3 clips selected." is
  announced once

#### Scenario: Shift+click in the bin follows the bin's order
- **WHEN** the operator presses the bin row of `s1710002.mp4` and Shift+presses the row of `s1710004.mp4`
- **THEN** `s1710002.mp4`, `s1710003.mp4` and `s1710004.mp4` are selected, and their blocks on the track are outlined

#### Scenario: Keyboard only
- **WHEN** the operator tabs to the block of `s1710001.mp4` and presses Enter, tabs to `s1710003.mp4` and presses
  Ctrl+Enter
- **THEN** both clips are selected, and keyboard focus is on the block of `s1710003.mp4`

#### Scenario: A click on one of several selects it alone
- **WHEN** three clips are selected and the operator clicks one of them without moving the pointer
- **THEN** that clip alone is selected

#### Scenario: Selecting many clips paints in time
- **WHEN** in a Chromium window 1280 × 900, on an event whose one chapter draws 400 clips, the operator clicks the first
  clip and Shift+clicks the 400th, five times, each in a fresh Edit mode
- **THEN** the median time from the second press to the next painted frame is at most 100 ms

### Requirement: A selected clip is moved by keyboard, and moving is inert while a save is pending

With one clip selected, Alt+Left and Alt+Right SHALL move it one place, into the neighbouring chapter at a chapter's
edge, announced politely. With two or more clips selected, they SHALL move nothing and SHALL say, politely, that Alt
and an arrow move one clip and that Move to… in the Clip tab moves the selected clips. While a save is pending, or a
move of several clips (Move marked… or the Clip tab's Move to…) is being applied, dragging and the keys SHALL do
nothing and say why.

#### Scenario: Alt+Right at a chapter's end
- **WHEN** the last clip of "Main" is selected and the operator presses Alt+Right
- **THEN** it becomes the first clip of "Kvällen" and the move is announced

#### Scenario: During a save
- **WHEN** a save is pending and the operator drags a clip
- **THEN** nothing moves and the words say that moving waits for the save

#### Scenario: Several clips selected
- **WHEN** `s1710001.mp4` and `s1710003.mp4` are selected and the operator presses Alt+Right
- **THEN** no clip moves, the draft is unchanged, and the polite status says that Alt and an arrow move one clip and
  that Move to… moves the selected clips

### Requirement: A clip block opens the clip's menu

In Edit mode these SHALL open the clip's menu ("Edit mode offers a clip's edits in a menu", `web-app`) in place of
the browser's: a right-click on a clip's block (its body, edge tools or a cut's handles), and Shift+F10 or the Menu
key on a focused block. Opening SHALL select the clip alone unless it is selected (alone or as one of several) or one
of its cuts is selected; a selection of several clips that holds it SHALL stay as it is. Opening SHALL NOT move the
playhead. A long press SHALL open it where the browser reports one as a context-menu request. Elsewhere on the track
the browser's menu SHALL stay.

#### Scenario: A right-click selects the clip and opens its menu
- **WHEN** nothing is selected and the operator right-clicks the body of `s1710003.mp4`
- **THEN** the clip is selected and the inspector shows its Clip tab, its menu is open at the pointer, the browser's
  own menu is not shown, and the playhead has not moved

#### Scenario: A right-click on an edge tool
- **WHEN** the operator right-clicks the Trim Out tool at the end of `s1710001.mp4`
- **THEN** the menu of `s1710001.mp4` opens and no trim starts

#### Scenario: A selected cut stays selected
- **WHEN** the second cut of `s1710002.mp4` is selected and the operator right-clicks that clip's block
- **THEN** the cut stays selected and the open menu is the menu of `s1710002.mp4`

#### Scenario: A right-click on one of several selected clips
- **WHEN** `s1710001.mp4` and `s1710003.mp4` are selected and the operator right-clicks `s1710003.mp4`
- **THEN** both clips stay selected and the menu headed "2 clips" opens

#### Scenario: A right-click outside the selection
- **WHEN** `s1710001.mp4` and `s1710003.mp4` are selected and the operator right-clicks `s1710002.mp4`
- **THEN** `s1710002.mp4` alone is selected and its own menu opens

#### Scenario: Not on a card or the empty track
- **WHEN** the operator right-clicks the "Kvällen" card block, and then the empty track below the last lane
- **THEN** no clip menu opens, and the browser's own menu is left to show each time

#### Scenario: A long press
- **WHEN** on a touch screen whose browser reports a long press as a context-menu request, the operator holds a
  finger still on `s1710002.mp4`
- **THEN** its menu opens and no drag starts

#### Scenario: The keys are listed
- **WHEN** the operator opens the Keyboard shortcuts list
- **THEN** it reads "Shift+F10 or Menu key on a clip: Open its menu" under Editing and "Right-click a clip: Open its
  menu" under Mouse
