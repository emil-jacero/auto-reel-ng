## ADDED Requirements

### Requirement: A clip is reordered by dragging it on the track

In Edit mode a press on a clip block's body that moves more than 3 px SHALL start a drag: the block follows the
pointer, the other clips make room live, and a line with words shows the drop place. Release SHALL make one draft edit
(reorder, or move into another chapter when the place is in another chapter's span or on its band). Escape or a
release outside the track SHALL cancel with no edit.

#### Scenario: Drag to reorder
- **WHEN** the operator drags `s1710002.mp4` left until the line says "Before s1710001.mp4" and releases
- **THEN** the track and the bin show `s1710002.mp4` first, the top bar says "1 clip moved", nothing is written

#### Scenario: Drop on a chapter band
- **WHEN** the operator drags `s1710003.mp4` onto the band "Main" and releases
- **THEN** `s1710003.mp4` is the last clip of "Main" in the draft

#### Scenario: Escape
- **WHEN** during a drag the operator presses Escape
- **THEN** every clip returns to its place and the draft is unchanged

### Requirement: Clips are included and ignored by dragging between bin and track

Dragging a New or Ignored clip from the bin onto the video track SHALL include it at the drop place. Dragging a clip
from the track onto the bin SHALL ignore it. Each SHALL be one draft edit, the same as the bin's own include and
ignore actions. Ignoring and including SHALL be draft edits of the clip's ignore state: counted by the top bar,
undone by Reset, and written by Save in the document's `ignore`. The inspector's Clip tab SHALL offer "Ignore clip" for
the selected clip, the same edit.

#### Scenario: Ignore clip button
- **WHEN** the operator selects `s1710001.mp4` and presses "Ignore clip" in the Clip tab
- **THEN** it is no longer drawn, it is listed as Ignored, the top bar counts "1 clip ignored" and nothing is written

#### Scenario: Include a new clip
- **WHEN** the operator drags `s1710006.mp4` (New) from the bin to before `s1710004.mp4`
- **THEN** it is drawn there, listed in that chapter in the bin, and the top bar counts it

#### Scenario: Ignore by dragging off
- **WHEN** the operator drags `s1710001.mp4` from the track onto the bin
- **THEN** it is no longer drawn and is listed as Ignored

### Requirement: A selected clip is moved by keyboard, and moving is inert while a save is pending

With a clip selected, Alt+Left and Alt+Right SHALL move it one place, into the neighbouring chapter at a chapter's
edge, announced politely. While a save or a Move marked… is pending, dragging and the keys SHALL do nothing and say
why.

#### Scenario: Alt+Right at a chapter's end
- **WHEN** the last clip of "Main" is selected and the operator presses Alt+Right
- **THEN** it becomes the first clip of "Kvällen" and the move is announced

#### Scenario: During a save
- **WHEN** a save is pending and the operator drags a clip
- **THEN** nothing moves and the words say that moving waits for the save
