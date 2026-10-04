# clip-rotation Specification

## Purpose
Lets an editor turn a clip a quarter turn left or right in Edit mode, keeps the turn in the draft until it is saved to reel.yaml, and shows the turn on every picture of the clip and as a tag in the read view.

## Requirements

### Requirement: A clip's turn is read from reel.yaml and means a clockwise turn from how the clip plays

The system SHALL treat `clips.<identity>.rotate` of the event's `reel.yaml` as the only home of a clip's editorial turn.
The value SHALL mean an extra clockwise turn, in degrees, on top of how the clip plays (the picture after the
container's display rotation), as the render applies it. The client SHALL read it from the reel document the service
returns, and SHALL show the quarter-turn it stands for: 0, 90, 180 or 270, also from -90 and 360. A value that is not a
multiple of 90 SHALL be shown as no turn, and the client SHALL NOT invent one. The client SHALL NOT change the proxies,
the sprites or the thumbnails the service serves, and SHALL NOT ask for different ones because of a turn.

#### Scenario: A clip turned 90 in reel.yaml is shown turned
- **WHEN** `reel.yaml` has `rotate: 90` for a clip and the event page is opened
- **THEN** the clip's thumbnail shows its picture turned a quarter clockwise from the frame the service serves

#### Scenario: Minus 90 is 270
- **WHEN** `reel.yaml` has `rotate: -90` for a clip
- **THEN** it is shown turned 270 degrees clockwise, the same as `rotate: 270`

#### Scenario: A phone clip is turned only by the extra value
- **WHEN** a clip whose container carries a display rotation of 90 and `rotate: 0` is shown, and then `rotate: 90` is set
- **THEN** the first picture is upright and the second is the upright picture turned 90 degrees clockwise, not 180

### Requirement: Edit mode turns a clip left or right, and the turn is part of the draft

In Edit mode, every clip that a chapter plays and that is on disk (active or new) SHALL have two controls: **Rotate
left** and **Rotate right**, named "Rotate <name> left" and "Rotate <name> right", where <name> is the clip's name as its
row names it. Each SHALL show an icon and SHALL be operable by keyboard, with a visible focus. Pressing Rotate right
SHALL add a quarter turn clockwise to the clip's turn in the draft; Rotate left SHALL subtract one. A turn that comes
back to 0 SHALL remove `rotate` from the clip's entry, and SHALL NOT write `rotate: 0`. A missing clip, an ignored clip
and a clip the operator removed SHALL NOT have the controls. When the primary pointer is coarse, each control SHALL take
a tap in an area of at least 44 × 44 CSS pixels, reaching no other control. The controls SHALL NOT change a row's size or
position, SHALL NOT start a drag, and SHALL NOT mark the clip.

A turn SHALL be an edit of the draft like a cut: it SHALL show the save bar, enable Reset and Save, make leaving
Edit mode ask first, and be written by Save as `clips.<identity>.rotate` in the same write as the other changes, with
the clip's other properties unchanged. A draft whose turn equals the saved turn SHALL count as no change. A turn SHALL be stepped back by the
opposite turn; Reset SHALL restore the saved turns. The controls SHALL be unavailable while a save or a move is
pending.

Each press SHALL be announced once to assistive technology with the clip's name and the turn it now has ("s1710002.mp4
turned right, now rotated 90 degrees clockwise.", "s1710002.mp4 no longer rotated.").

#### Scenario: Rotate right twice is 180
- **WHEN** the operator presses Rotate right twice on a clip with no turn
- **THEN** the clip shows turned 180 degrees, the draft holds `rotate: 180`, and Save writes `clips.<identity>.rotate: 180`

#### Scenario: Rotate left from nothing is 270
- **WHEN** the operator presses Rotate left once on a clip with no turn
- **THEN** the clip's turn is 270 and `rotate: 270` is written

#### Scenario: Back to nothing removes the key
- **WHEN** a clip saved with `rotate: 90` is turned left once and saved
- **THEN** its entry in `reel.yaml` has no `rotate` key, and the write has no `rotate: 0`

#### Scenario: Stepping back and Reset
- **WHEN** the operator turns a clip right three times, turns it left once, then presses Reset
- **THEN** after the left turn the clip is turned 180 and after Reset it is as saved, and the page is not dirty

#### Scenario: Turning is not marking and not dragging
- **WHEN** the operator presses Rotate right on a clip
- **THEN** the clip stays unmarked, no drag starts, and no row moves

### Requirement: The save bar says how many clips are turned

The save bar's summary of unsaved changes SHALL count clips whose turn differs from the saved one, in words, with the
other counts: "1 clip rotated", "3 clips rotated". A clip turned and then turned back to its saved value SHALL not be
counted. The count SHALL be in the summary the bar already announces, and SHALL NOT make the bar taller than "Edit
mode's save bar stays compact and fits the window" allows.

#### Scenario: One clip rotated
- **WHEN** one clip is turned and nothing else changed
- **THEN** the save bar says "1 clip rotated"

#### Scenario: Turned back is not a change
- **WHEN** a clip is turned right and then left
- **THEN** the save bar does not mention a rotation

### Requirement: The marked group turns together

The marks line (`Edit mode marks clips to move together`) SHALL offer **Rotate marked left** and **Rotate marked
right**. Each SHALL turn every marked clip that is on disk by a quarter turn from that clip's own current turn in the
draft, in one step, and SHALL announce once how many clips were turned ("3 clips rotated right."). They SHALL be
disabled, and say why to assistive technology, when no clip is marked. Turning the group SHALL NOT clear or change the
marks. The buttons SHALL meet the touch-size rule above and SHALL fit the line at 390 pixels wide without making the page
scroll horizontally.

#### Scenario: Three marked clips with different turns
- **WHEN** three clips with turns 0, 90 and 270 are marked and Rotate marked right is pressed
- **THEN** their turns are 90, 180 and 0 (key removed), they stay marked, and Rotate marked left restores all three

### Requirement: Every picture of a clip shows its turn

Wherever the client shows a picture of a clip, it SHALL show it turned by the clip's turn in the draft in Edit mode, and
by the saved turn elsewhere: the clip's thumbnail (read view and Edit mode), the clip's player (read view Watch and
Edit mode preview, whether it plays the preview copy or the original, and its poster), and the Timeline's video and
filmstrips ("The Timeline shows a clip's turn"). The turn SHALL be made on the client by a transform of the picture the
service serves, and SHALL leave the picture's box its size and place: a 90 or 270 degree turn of a landscape picture
SHALL be shown whole inside its box, fitted, and never cropped, squashed or stretched. A clip with no turn SHALL be
shown exactly as before. Controls laid over a picture (the play control, the mark box, the player's controls) SHALL stay
upright and where they were, and a failed picture's "No preview" box SHALL not be turned. A change of the draft's turn
SHALL show at once, without a request. The Movie player plays the rendered movie, in which the render has turned the
clips, and SHALL NOT be turned.

#### Scenario: A turned landscape thumbnail fits its box
- **WHEN** a landscape clip is turned 90 degrees
- **THEN** its thumbnail box keeps its 16:9 size and place, and the turned frame lies wholly inside it, uncropped

#### Scenario: The play control stays upright
- **WHEN** a clip turned 90 degrees has its play control on the thumbnail
- **THEN** the control is centred on the box and its icon is upright

#### Scenario: Edit shows the draft, the read view the saved
- **WHEN** the operator turns a clip in Edit mode without saving
- **THEN** its Edit thumbnail and preview show the turn at once, and the read view, once Edit mode is left by Reset, shows the saved turn

#### Scenario: The player shows the turn on both files
- **WHEN** a clip turned 90 degrees plays its preview copy, and then Play original is chosen
- **THEN** both are shown turned a quarter clockwise from how they play unturned, and neither is cropped

#### Scenario: A rotated phone clip
- **WHEN** `h264-720p-rotate90-aac.mp4` (display rotation, upright in its proxy and thumbnail) has `rotate: 90`
- **THEN** its thumbnail, player and Timeline all show it on its side, the way the render will, in Chrome and Firefox, light and dark, at 1280 and 390 pixels wide

### Requirement: The read view tags a turned clip in words and an icon

The event page's read view SHALL show, beside the name of each clip that has a turn and that `reel.yaml` does not
exclude, a tag saying "Rotated 90 degrees" (or 180, 270), with an icon, so that the state is not told by colour alone.
A clip with no turn SHALL show nothing more than before. The tag SHALL be read as its words. It SHALL NOT make the page
scroll horizontally from 320 pixels up and SHALL NOT change a row's height at 1280 pixels. The page SHALL take the turn
from the reel read it already makes for cuts, SHALL NOT write anything, and, when that read fails, SHALL show the clips
without a tag, with the note it already shows for the cuts.

#### Scenario: A turned clip is tagged
- **WHEN** a clip has `rotate: 270`
- **THEN** its row shows "Rotated 270 degrees" with an icon

#### Scenario: A clip without a turn
- **WHEN** a clip has no `rotate`
- **THEN** its row is as it was
