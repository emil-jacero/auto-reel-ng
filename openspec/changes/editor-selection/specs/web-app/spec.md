## ADDED Requirements

### Requirement: The inspector follows the selection

The inspector SHALL show the tab for what is selected: Clip for a clip or a cut, Title card for a card, Suggestion for
a suggestion, and Event when nothing is selected. The operator MAY still pick another tab by hand; the next selection
SHALL pick the tab again. Each tab's controls SHALL edit the one draft, as every Edit-mode change does.

#### Scenario: Clip selected
- **WHEN** the operator presses the body of `s1710003.mp4`'s block on the track
- **THEN** the inspector shows the Clip tab with `s1710003.mp4`, "Kvällen · clip 1 of 2", its Trim In/Out fields,
  rotate buttons and its cuts

#### Scenario: Nothing selected
- **WHEN** the operator presses Escape with a clip selected
- **THEN** nothing is selected and the inspector shows the Event tab with the Details form

### Requirement: The Clip tab edits the selected clip

The Clip tab SHALL show the clip's name, chapter and position, and its length in the movie, and SHALL offer Trim In
and Trim Out as typed times, Rotate left and right, the clip's cuts with remove and "+ Cut at playhead", Use frame as
poster and Ignore clip. A typed trim SHALL be the same draft edit as the track's edge tools.

#### Scenario: Typed Trim In
- **WHEN** the operator types 0:01.50 into Trim In for `s1710001.mp4`
- **THEN** the clip's leading cut is 0 to 1.5 s in the draft, the block shortens and the clips after it move left

### Requirement: The title card editor is docked in the inspector

Selecting a title card, on the track or from its chapter in the bin, SHALL show its editor in the inspector's Title
card tab: the tabs "This title card" and "All title cards in this event", the fields, and one live preview above them.
No modal dialog SHALL open. Edits SHALL go into the one draft; the top bar counts a changed card.

#### Scenario: Card from the track
- **WHEN** the operator presses the "Kvällen" card block
- **THEN** the inspector shows "Title card for Kvällen" with its preview and fields, the track and the picture stay
  visible, and no dialog is open

## REMOVED Requirements

### Requirement: A selected title card opens its inspector in Edit mode
**Reason**: The card editor no longer opens in a modal dialog; it is docked in the workspace's inspector.
**Migration**: "The title card editor is docked in the inspector".
