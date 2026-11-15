## ADDED Requirements

### Requirement: Edit mode is a full-window workspace

Pressing Edit SHALL replace the event page with a workspace that fills the window: no app header, no page width
limit. It SHALL have a top bar and four panes: the clip bin (left), the viewer (centre), the inspector (right) and the
Timeline (along the bottom). Done SHALL leave it through the same flow as leaving Edit mode today, unsaved guard
included, and the event page SHALL show again with the app header.

#### Scenario: Edit opens the workspace
- **WHEN** the operator presses Edit on `2024-08-20 - Två kapitel - Tjörn` in a 1440×900 window
- **THEN** the app header is gone, the top bar, bin, viewer, inspector and Timeline are all visible, and the page
  does not scroll

#### Scenario: Done with unsaved edits
- **WHEN** the operator has moved a clip and presses Done
- **THEN** the same unsaved-edits question as today is asked, and choosing to stay keeps the workspace and the draft

### Requirement: The workspace's top bar holds the event and the save controls

The top bar SHALL show a control back to the event list (which leaves Edit mode as Done does), the event's title with
its date and location, the unsaved summary in the save bar's words, Reset, Save and Done, and the theme switch. It
SHALL present one primary action as the save bar does today (Save, Reload latest or Back to the event list), and
Ctrl+S / Cmd+S SHALL save as today.

#### Scenario: The summary follows the draft
- **WHEN** the operator adds a cut and moves a clip
- **THEN** the top bar says "Unsaved" with "1 cut added · 1 clip moved", and Save is the primary action

#### Scenario: A conflict
- **WHEN** a save answers 412
- **THEN** the top bar's primary action is Reload latest, and the explanation opens under the top bar without covering
  the Timeline

### Requirement: The clip bin holds the chapters' clip lists

The bin SHALL list every chapter with its clips in compact rows (thumbnail, name, kept length, status) and SHALL keep
every action the chapter lists have: reorder and move between chapters by pointer and by keyboard, marks and Move
marked to…, Add/rename/delete chapter, and the New, Ignored and Missing clips with their actions.

#### Scenario: Keyboard reorder in the bin
- **WHEN** the operator focuses `s1710002.mp4`'s drag handle, presses Space, ArrowUp, Space
- **THEN** `s1710002.mp4` is first in its chapter, the move is announced, and the Timeline draws it first

#### Scenario: 400 clips
- **WHEN** the event has 400 clips
- **THEN** the bin scrolls on its own, the rest of the workspace does not move, and the drag-smoothness gate holds

### Requirement: The viewer and the inspector take the parts of the page they replace

The viewer SHALL show the Timeline's picture with play, previous clip, next clip, the time readout and Use as poster.
The inspector SHALL have an Event tab (Details form, Poster, Title cards On/Off, card style) and a Cut tab (the
selected cut's fields and the selected suggestion's decision). Choosing a cut or a suggestion on the track SHALL show
the Cut tab.

#### Scenario: Next clip
- **WHEN** the playhead is in `s1710002.mp4` and the operator presses Next clip
- **THEN** the playhead moves to the first kept frame of the next drawn clip

#### Scenario: Selecting a cut
- **WHEN** the operator presses a cut's handle on the track
- **THEN** the inspector shows the Cut tab with that cut's start and end fields

### Requirement: The workspace follows the theme and fits narrower windows

The workspace SHALL follow the operator's light or dark theme and its switch SHALL change the same setting as the app
header's. At 1280×720 the page SHALL NOT scroll; the panes scroll within themselves. Below 960 CSS pixels wide the
panes SHALL stack in one column (viewer, Timeline, inspector, bin) with no horizontal page scroll.

#### Scenario: Theme switch
- **WHEN** the operator switches to light in the top bar and leaves Edit mode
- **THEN** the event page is light, and `auto-reel:theme` holds `light`

#### Scenario: Phone width
- **WHEN** the window is 390 CSS pixels wide
- **THEN** the panes are stacked, every control is reachable, and the page does not scroll sideways

## REMOVED Requirements

### Requirement: Edit mode lines up with the event page and fits a phone
**Reason**: Edit mode no longer reuses the event page's table layout; it is a workspace.
**Migration**: "Edit mode is a full-window workspace" and "The workspace follows the theme and fits narrower windows".

### Requirement: Edit mode's save bar rests in the page when it would hide the editor
**Reason**: There is no bottom save bar; the save controls are in the top bar.
**Migration**: "The workspace's top bar holds the event and the save controls".
