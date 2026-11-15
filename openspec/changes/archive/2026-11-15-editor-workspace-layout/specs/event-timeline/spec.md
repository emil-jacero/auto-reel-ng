## MODIFIED Requirements

### Requirement: The Timeline is shown only in Edit mode and draws the draft

The Timeline SHALL be shown only in Edit mode, as the workspace's bottom pane, with its picture and transport in the
viewer pane. It SHALL be open whenever Edit mode shows, including after a Refresh or a save, and SHALL have no button
that opens or closes it.

#### Scenario: Edit opens the Timeline, leaving closes it
- **WHEN** the operator presses Edit on `2024-06-27 - Grillning med grannar` and later leaves Edit mode
- **THEN** the workspace shows the Timeline along the bottom and its picture in the viewer, with no "Open timeline"
  or "Close timeline" button; after leaving, the read view shows no Timeline section and its clip list, Movie section
  and poster as before
