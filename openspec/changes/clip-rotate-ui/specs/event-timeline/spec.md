## ADDED Requirements

### Requirement: The Timeline shows a clip's turn

The Timeline SHALL show a clip turned by the clip's `rotate` (the draft's in Edit mode, the saved one in the read view),
as "Every picture of a clip shows its turn" requires: its one video, while the playhead is in the clip, and each tile of
the clip's filmstrip. The turn SHALL be a transform of the proxy's picture and of the sprite's tiles; the proxy and the
sprite SHALL NOT be requested again because of a turn. The track's geometry SHALL NOT depend on a turn: a clip's lane
width SHALL stay its proxy's length, its tiles SHALL keep the lane height, and a turned tile SHALL be fitted inside its
tile box, uncropped. The playhead, the chapters, the cuts, the trim handles and the suggestions SHALL keep their places
and times. A change of a turn in the draft SHALL show on the video and the tiles at once. At the swap between clips the
video SHALL be turned by the next clip's turn before it is shown.

#### Scenario: Filmstrip tiles are turned and fitted
- **WHEN** a landscape clip with `rotate: 90` is on the Timeline
- **THEN** each of its tiles shows the frame turned a quarter clockwise, whole inside the tile, and the lane is as wide as before

#### Scenario: The video follows the clip it is in
- **WHEN** play passes from an unturned clip to one turned 90 degrees
- **THEN** the video is shown turned for the second clip, and unturned again after the next unturned clip

#### Scenario: Turning in Edit mode shows at once
- **WHEN** the operator presses Rotate right on a clip while the Timeline is open
- **THEN** its tiles and, when the playhead is in it, the video show the new turn with no request for a sprite or a proxy
