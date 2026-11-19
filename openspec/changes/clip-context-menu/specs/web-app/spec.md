## ADDED Requirements

### Requirement: Edit mode offers a clip's edits in a menu

In Edit mode a clip's menu SHALL be headed by the clip's name and list four groups: Rotate left and Rotate right;
Cut at playhead and Use frame as poster; Move to «chapter» for each other chapter the Timeline draws; Ignore clip.
Each item SHALL make the draft edit its Clip tab control makes (Move to: a drop on that chapter's band, at its end),
announced as there and undone in one step. The Clip tab SHALL keep all of these controls.

#### Scenario: The menu of a clip in Kvällen
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator opens the menu of `s1710002.mp4`, drawn in `Kvällen`
- **THEN** it is headed "s1710002.mp4" and lists Rotate left, Rotate right, Cut at playhead, Use frame as poster,
  Move to Main and Ignore clip, in that order, with a separator between the groups

#### Scenario: Rotate right from the menu
- **WHEN** the operator chooses Rotate right in the menu of `s1710002.mp4`
- **THEN** the clip is turned a quarter right on the track and in the picture, the turn is announced once, nothing
  is written, and Undo says "Undo rotation of s1710002.mp4"

#### Scenario: Move to another chapter
- **WHEN** the operator chooses Move to Main in the menu of `s1710003.mp4`
- **THEN** `s1710003.mp4` is drawn as the last clip of Main, after `s1710001.mp4`, "Moved s1710003.mp4. At the end of
  Main." is announced, the top bar says "1 clip moved", and Undo says "Undo move of s1710003.mp4"

#### Scenario: Cut at the playhead
- **WHEN** the playhead is at 0:02.00 of `s1710002.mp4`, which has no cuts, and the operator chooses Cut at playhead
  in its menu
- **THEN** the draft has a cut of that clip from 2.0 to 3.0 s, the cut "+ Cut at playhead" in the Clip tab makes,
  and the top bar says "1 cut added"

#### Scenario: Ignore from the menu
- **WHEN** the operator chooses Ignore clip in the menu of `s1710002.mp4`
- **THEN** it is no longer drawn, the bin lists it as ignored, and the top bar says "1 clip ignored"

#### Scenario: One chapter, no Move to
- **WHEN** the Timeline draws a single chapter and the operator opens a clip's menu
- **THEN** the menu has no Move to item

### Requirement: An unavailable item in the clip menu says why

An item that cannot act SHALL stay listed, shown as unavailable in more than colour and to assistive technology, with
its reason in words under it, as the Clip tab words it. While a save or a Move marked… is pending, every item SHALL be
unavailable under one line that says so. Choosing an unavailable item SHALL say its reason once through the polite
status, change nothing, and keep the menu open.

#### Scenario: The playhead is in another clip
- **WHEN** the playhead is in `s1710001.mp4` and the operator opens the menu of `s1710002.mp4`
- **THEN** Cut at playhead is unavailable under "Move the playhead into s1710002.mp4 to cut there.", Use frame as
  poster is unavailable under "Move the playhead into s1710002.mp4 to use a frame as poster.", and the other items
  are available

#### Scenario: During a save
- **WHEN** a save is pending, the operator opens a clip's menu and presses Enter on Rotate right
- **THEN** every item is unavailable under "Clip edits wait for the save or the move of marked clips to finish.",
  those words are announced, the clip is not turned, and the menu stays open

### Requirement: The clip menu is operated by keyboard and keeps its keys

The clip menu SHALL be a menu of menu items, and opening it SHALL focus its first item. Up and Down SHALL move between
items, wrapping; Home and End SHALL go to the first and the last; Enter and Space SHALL choose; Escape, Tab and
Shift+Tab SHALL close it. While it has focus, no other key SHALL act, except Ctrl or Cmd chords. That means no
workspace shortcut, no track key, and no Escape that clears the selection.

#### Scenario: Keyboard only
- **WHEN** the operator tabs to the block of `s1710002.mp4`, presses Shift+F10, then Down and Enter
- **THEN** the menu opened under the block with Rotate left focused, the clip is turned right once, the menu is
  closed, and focus is on the clip's block

#### Scenario: Keys stay in the menu
- **WHEN** the playhead is in `s1710002.mp4`, the operator opens its menu with a right-click, and presses W, Right,
  then Space on Rotate left
- **THEN** the clip's end is not trimmed, the playhead has not moved, the Timeline does not play, and the clip is
  turned left once

#### Scenario: Escape keeps the selection
- **WHEN** `s1710002.mp4` is selected, its menu is open, and the operator presses Escape
- **THEN** the menu closes, focus is on the clip's block, and `s1710002.mp4` is still selected; a second Escape
  clears the selection

### Requirement: The clip menu gives focus back and closes when it is done

When the menu is closed by Escape, Tab or a choice, focus SHALL go to the clip's block. When the choice took the clip
off the track, focus SHALL go to the block of the clip drawn after it, else the one before it, else the track. A
press outside the menu SHALL close it and act as it would. Focus SHALL never fall to the page's body. The menu SHALL
also close when the window is resized, when the track or a pane scrolls, and when its clip is no longer drawn.

#### Scenario: Ignore moves focus to the next clip
- **WHEN** the operator opens the menu of `s1710002.mp4` with Shift+F10 and chooses Ignore clip
- **THEN** focus is on the block of `s1710003.mp4`

#### Scenario: A press outside
- **WHEN** the menu is open and the operator clicks the picture in the viewer
- **THEN** the menu closes, the draft is unchanged, and focus is not on the page's body

#### Scenario: Scrolling the track closes it
- **WHEN** the menu is open and the operator turns the wheel over the track
- **THEN** the track scrolls and the menu is closed

#### Scenario: Undo takes its clip away
- **WHEN** the operator drags the ignored `s1710004.mp4` of Main from the bin onto the track, opens its menu and
  presses Ctrl+Z
- **THEN** the include is undone, `s1710004.mp4` is no longer drawn, and the menu is closed

### Requirement: The clip menu fits the window and is large enough to touch

A menu opened by pointer SHALL open at the pointer. A menu opened by a key SHALL open under the clip's block, or above
it when it does not fit under and there is more room above. It SHALL lie wholly inside the window, 8 px from its edges, at any width from
320 px, and scroll within itself when it is taller. Each item SHALL be at least 24 px tall, and 44 px under a coarse
pointer, and the menu SHALL follow the light or dark theme.

#### Scenario: Near the window's corner
- **WHEN** in a 1280×720 window the operator right-clicks a clip block 20 px from the window's right edge
- **THEN** the menu opens to the left of the pointer, wholly inside the window

#### Scenario: Phone width with a coarse pointer
- **WHEN** in a 390×844 window with a coarse pointer the menu of `s1710002.mp4` is opened
- **THEN** it is wholly inside the window, each item takes a tap in an area at least 44 px tall, and the page does
  not scroll sideways
