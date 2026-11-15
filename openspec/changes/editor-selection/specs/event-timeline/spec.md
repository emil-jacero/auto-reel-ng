## ADDED Requirements

### Requirement: One selection in the workspace

The workspace SHALL hold one selection: nothing, a clip, a cut, a title card or a suggestion. Selecting one SHALL end
any other. Escape SHALL clear it. It SHALL survive a Refresh and a save while its target is still in the event, and
end when its target is gone. The selected thing SHALL be shown selected in more than colour.

#### Scenario: Card ends clip
- **WHEN** `s1710003.mp4` is selected and the operator presses the "Kvällen" card block
- **THEN** the card is selected, the clip is no longer outlined, and the inspector shows the Title card tab

#### Scenario: Target deleted
- **WHEN** the selected card's chapter is deleted
- **THEN** nothing is selected and the inspector shows the Event tab

### Requirement: A clip is selected on the track or in the bin

A press on a clip block's body (not its edge tools or handles) and a press on its bin row SHALL select the clip. The
block SHALL be outlined with trim handles and the row highlighted; each SHALL be scrolled into view in its pane
without moving keyboard focus there. A press on empty track SHALL select nothing.

#### Scenario: Bin to track
- **WHEN** the track shows 0–20 s and the operator presses the bin row of a clip drawn at 31 s
- **THEN** the clip is selected, the track scrolls so the clip is in view, and focus stays on the bin row

#### Scenario: Empty track
- **WHEN** the operator presses the track below the last lane
- **THEN** nothing is selected and the inspector shows the Event tab

## REMOVED Requirements

### Requirement: A card is selected from the Timeline or the list, as one selection
**Reason**: The card selection is now part of the workspace's one selection.
**Migration**: "One selection in the workspace".
