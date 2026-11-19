## ADDED Requirements

### Requirement: A clip block opens the clip's menu

In Edit mode these SHALL open the clip's menu ("Edit mode offers a clip's edits in a menu", `web-app`) in place of
the browser's: a right-click on a clip's block (its body, edge tools or a cut's handles), and Shift+F10 or the Menu
key on a focused block. Opening SHALL select the clip unless it or one of its cuts is selected, and SHALL NOT move the
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

### Requirement: A right-click never drags a clip, and cancels a drag

A right-button press on a clip's block SHALL NOT start a reorder drag or an edge trim, however far the pointer moves
before release. A right-click during a clip drag SHALL cancel the drag as Escape does, with no edit, and SHALL open
no menu. During any other drag on the track (an edge, a cut's handle, a card's end) a right-click SHALL open no menu.

#### Scenario: A right-button press that moves does not drag
- **WHEN** the operator presses the right mouse button on the body of `s1710002.mp4`, moves 20 px and releases
- **THEN** nothing was dragged, the clip is selected, and its menu is open

#### Scenario: A right-click during a drag
- **WHEN** during a drag of `s1710002.mp4` the operator clicks the right mouse button
- **THEN** every clip returns to its place, the draft is unchanged, and no menu opens

#### Scenario: A right-click during a trim
- **WHEN** the operator drags the Trim In tool of `s1710002.mp4` and clicks the right mouse button before releasing it
- **THEN** no menu opens and the browser's own menu is not shown

## MODIFIED Requirements

### Requirement: A clip is selected on the track or in the bin

A primary-button press on a clip block's body (not its edge tools or handles) and a press on its bin row SHALL select the
clip. The block SHALL be outlined with trim handles and the row highlighted; each SHALL be scrolled into view in its pane
without moving keyboard focus there. A press on empty track SHALL select nothing. A primary-button press with a mouse or a pen on a clip block's body that moves more than 3 px SHALL start a reorder drag instead ("A clip is reordered by dragging it on the track"), and the dragged clip SHALL be the selected one when the drag ends, whether or not it made an edit; Escape during that drag cancels only the drag and keeps the selection.

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

### Requirement: A clip is reordered by dragging it on the track

In Edit mode a primary-button press with a mouse or a pen on a clip block's body that moves more than 3 px SHALL start a drag: the block follows the
pointer, the other clips make room live, and a line with words shows the drop place. Release SHALL make one draft edit
(reorder, or move into another chapter when the place is in another chapter's span or on its band). Escape or a
release outside the track SHALL cancel with no edit, and Escape SHALL only cancel the drag. Touch SHALL NOT start it.

#### Scenario: Drag to reorder
- **WHEN** the operator drags `s1710002.mp4` left until the line says "Before s1710001.mp4" and releases
- **THEN** the track and the bin show `s1710002.mp4` first, the top bar says "1 clip moved", nothing is written

#### Scenario: Drop on a chapter band
- **WHEN** the operator drags `s1710003.mp4` onto the band "Main" and releases
- **THEN** `s1710003.mp4` is the last clip of "Main" in the draft

#### Scenario: Touch does not drag
- **WHEN** with touch the operator swipes on a clip block
- **THEN** the track scrolls and no drag starts; a finger reorders through the bin or the Alt keys

#### Scenario: Escape
- **WHEN** during a drag the operator presses Escape
- **THEN** every clip returns to its place and the draft is unchanged
