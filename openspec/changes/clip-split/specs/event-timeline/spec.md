## ADDED Requirements

### Requirement: Split divides the clip under the playhead

In Edit mode, Split (the tool row's button, and the key `B`) SHALL divide the clip under the playhead at the playhead
into two blocks, as one draft edit. Split SHALL be unavailable, saying why, when the playhead is in a title card, on a
cut, within three frames of a clip's kept edge, or while a save is pending. (Provisional: what the two blocks may do
afterwards depends on the model decided in task 0.3.)

#### Scenario: Split in the middle
- **WHEN** the playhead is at 5.0 s inside `s1710003.mp4` (10.0 s, no cuts) and the operator presses Split
- **THEN** the track draws two blocks of `s1710003.mp4`, 0–5.0 s and 5.0–10.0 s, and the top bar counts one split

#### Scenario: On a card
- **WHEN** the playhead is in the "Kvällen" card and the operator presses Split
- **THEN** nothing is split and the words say that a title card cannot be split
