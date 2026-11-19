## ADDED Requirements

### Requirement: The workspace answers the Timeline's keys wherever focus is

In Edit mode's workspace, with single-key shortcuts on, these keys SHALL do what they do on the focused playhead or
track, wherever keyboard focus is in the workspace: Space (Play or Pause), Left and Right (a frame), Shift+Left and
Shift+Right (a second), `+` `=` `-` `_` `0` `\` (zoom), Q, W, S (the edge tools) and Alt+Left and Alt+Right (move the
selected clip). Each press SHALL act once.

#### Scenario: Space after a click on a clip
- **WHEN** the operator clicks the block of `s1710002.mp4` on the track and presses Space
- **THEN** the clip is selected, the Timeline plays, and a second Space pauses it

#### Scenario: Space after a click on the video
- **WHEN** the operator clicks the picture in the viewer and presses Space
- **THEN** the Timeline plays

#### Scenario: Zoom and a frame step from the inspector
- **WHEN** the operator clicks the Clip tab's Rotate right with the mouse, then presses `+` and Right
- **THEN** the track zooms in by a factor of 1.5, the playhead moves one frame, and the clip is turned once

### Requirement: Workspace shortcuts never act in fields, dialogs, a clip preview or a drag

A workspace shortcut SHALL NOT act, and SHALL leave the key to the browser, in any of these cases:
- focus is in a text field, a select or editable text;
- a dialog is open, or focus is inside an open clip preview;
- a drag on the track or in the bin is in progress, or an input-method composition is in progress;
- the focused control took the key itself;
- an arrow is pressed on a focused widget that takes arrows (a slider, a radio group, a tab list, a list box, a menu
  or a spin button).

#### Scenario: Typing a title with a space
- **WHEN** focus is in Title and the operator types "Två kvällar"
- **THEN** the field reads "Två kvällar" and the Timeline does not play

#### Scenario: Arrows on the Zoom slider
- **WHEN** the Zoom slider has focus and the operator presses Right
- **THEN** the slider zooms one step and the playhead does not move

#### Scenario: Space during a trim drag
- **WHEN** the operator drags a trim handle and presses Space before releasing it
- **THEN** the Timeline does not start or stop playing

### Requirement: Space presses a control reached by keyboard and plays after a click

When focus is on a button, a checkbox, a radio button, a switch or a clip block, Space SHALL act on that control if the
operator last pressed Tab (Arrow keys do not count: a click on a control, then an arrow, then Space is still Play). It SHALL be Play or Pause, and SHALL NOT also act on the control, if the
operator last pressed a pointer. Enter SHALL act on the control in both cases. A held Space SHALL NOT repeat Play or
Pause.

#### Scenario: Tab to a button, then Space
- **WHEN** the operator tabs to Rotate right in the Clip tab and presses Space
- **THEN** the clip is turned once and the Timeline does not play

#### Scenario: Click a button, then Space
- **WHEN** the operator clicks Rotate right with the mouse and then presses Space
- **THEN** the Timeline plays and the clip has been turned once, not twice

#### Scenario: Enter on a clicked clip
- **WHEN** the operator clicks a clip block with the mouse and presses Enter
- **THEN** the clip stays selected and the Timeline does not play

### Requirement: The workspace lists its keyboard shortcuts

The top bar SHALL hold a "Keyboard shortcuts" button at its right, and `?` SHALL open the list wherever a workspace
shortcut acts. The list SHALL name, in words, every key the workspace layer answers, and the keys of the playhead, the track and the clip handles that share its keys (grouped Playback, Zoom, Editing and
Mouse) and SHALL be built from the keys the workspace handles. It SHALL NOT be modal. Escape, the button or a click
outside SHALL close it, and Escape SHALL then leave the selection as it is.

#### Scenario: Opening the list
- **WHEN** the operator presses `?` with focus on the track
- **THEN** the list opens and shows "Space: Play or pause", "Q: Trim the clip's start to the playhead" and
  "Ctrl+wheel over the Timeline: zoom"

#### Scenario: Escape closes only the list
- **WHEN** a clip is selected, the list is open, and the operator presses Escape
- **THEN** the list closes and the clip stays selected

#### Scenario: Keys work with the list open
- **WHEN** the list is open and the operator presses Space with focus on the playhead
- **THEN** the Timeline plays and the list stays open

### Requirement: Single-key shortcuts can be turned off

The Keyboard shortcuts list SHALL hold a switch "Single-key shortcuts", on by default and kept in the browser for later
visits (on when the browser keeps nothing). Off, no workspace shortcut SHALL act. Keys handled by a focused playhead,
track, trim handle, card handle or suggestion mark, and Ctrl/Cmd chords, SHALL work as before.

#### Scenario: Off, Space on the video does nothing
- **WHEN** the switch is off, the operator clicks the picture in the viewer and presses Space
- **THEN** the Timeline does not play

#### Scenario: Off, the playhead keeps its keys
- **WHEN** the switch is off and the operator clicks the ruler and presses Space
- **THEN** the Timeline plays

#### Scenario: The choice is kept
- **WHEN** the operator turns the switch off, leaves Edit mode and opens Edit mode again in the same browser
- **THEN** the switch is off
