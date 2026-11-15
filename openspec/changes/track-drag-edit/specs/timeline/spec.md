## ADDED Requirements

### Requirement: The model gives the drop place of a clip dragged on the track

For a dragged clip and a place on the track, the model SHALL give the drop slot: the chapter and the index the clip
would take, the clip it would go before (or none at a chapter's end), and words naming it. The slot SHALL be the clip
boundary nearest the centre of the dragged block. Applying a slot SHALL give the new order; a slot at the clip's own
place SHALL give no change.

#### Scenario: Reorder inside a chapter
- **WHEN** `s1710002.mp4` (second in "Main") is dropped with its centre nearest the boundary before `s1710001.mp4`
- **THEN** the slot is "Main", index 0, before `s1710001.mp4`, and the order becomes `s1710002.mp4`, `s1710001.mp4`

#### Scenario: Across chapters
- **WHEN** `s1710004.mp4` is dropped nearest the boundary after the last clip of "Main"
- **THEN** the slot is "Main" at its end, and `s1710004.mp4` leaves "Kvällen"

#### Scenario: Own place
- **WHEN** a clip is dropped nearest its own boundaries
- **THEN** the slot is its own place and applying it changes nothing
