## ADDED Requirements

### Requirement: Edit mode undoes and redoes draft edits

The workspace SHALL offer Undo and Redo in its top bar and by Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z and Ctrl+Y. Each draft edit
SHALL be one step; typing in one field SHALL be one step until the field loses focus or 1 s passes. Reset SHALL be a
step. Save SHALL clear the history. Each button SHALL name the step it undoes or redoes, and be unavailable when there
is none.

#### Scenario: Undo a move
- **WHEN** the operator moves `s1710002.mp4` above `s1710001.mp4` and presses Ctrl+Z
- **THEN** `s1710001.mp4` is first again on the track and in the bin, and Redo says "Redo move of s1710002.mp4"

#### Scenario: Undo Reset
- **WHEN** the operator adds a cut, presses Reset, then Undo
- **THEN** the cut is back in the draft and the top bar says "1 cut added"

#### Scenario: After Save
- **WHEN** the operator saves
- **THEN** Undo and Redo are unavailable

### Requirement: Undo keys leave text fields alone

While focus is in a text field, select or editable text, Ctrl/Cmd+Z and the redo keys SHALL act on that field's own
text and SHALL NOT change the draft's history. During a drag they SHALL do nothing.

#### Scenario: Typing the title
- **WHEN** the operator types "Två" in Title and presses Ctrl+Z with focus still in Title
- **THEN** the browser's own undo changes the field's text, and the draft's Undo still lists the step
