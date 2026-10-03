## ADDED Requirements

### Requirement: The Timeline pauses, and is paused, like every other player

The Timeline's video SHALL take part in the page's one rule that a video that starts pauses every other playing video
("The event page plays one video at a time"), as one player among the others and with no rule of its own for any other
player. Pressing Play on the Timeline while the Movie section's player or a clip's player plays SHALL pause that
player where it is; a video of the page that starts while the Timeline plays SHALL pause the Timeline.

A Timeline paused that way SHALL stay open, keep its playhead where it stopped, keep every handle and mark usable, and
play on from the playhead when its own Play is pressed. Being paused by another player SHALL NOT be taken for the
operator's Pause in any way that changes the Timeline: it SHALL NOT edit, select or move anything, SHALL NOT announce
anything, and SHALL NOT start the Timeline again by itself. A change of the Timeline's file at a clip boundary SHALL be
the Timeline continuing, not a start of another video: but when another video has started while the file was changing,
the Timeline SHALL NOT take playback back, and SHALL stay paused at the boundary.

#### Scenario: The Timeline starts while a clip plays
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the operator presses Play on the Timeline
- **THEN** the clip's player is paused at `0:03.2` and stays open, and the Timeline plays from its playhead

#### Scenario: A clip starts while the Timeline plays
- **WHEN** the Timeline plays across `s1710001.mp4` and the operator presses "Play s1710002.mp4" on that clip's
  thumbnail
- **THEN** the Timeline is paused with its playhead at the place it stopped, it is still open, no handle or mark
  has moved, nothing was announced, and the clip plays
- **WHEN** the operator then presses the Timeline's Play
- **THEN** the Timeline plays on from its playhead and the clip is paused

#### Scenario: A start during a clip boundary is kept
- **WHEN** the Timeline plays and, within the moment its file changes at the boundary between two clips, the
  operator presses the Movie section's play
- **THEN** the movie plays, the Timeline stays paused at the boundary and does not start again by itself

#### Scenario: The movie and the Timeline in either order
- **WHEN** the movie plays and the operator presses Play on the Timeline, and then presses the movie's play
- **THEN** each start pauses the other, and neither player has closed or moved
