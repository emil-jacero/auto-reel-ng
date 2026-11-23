## MODIFIED Requirements

### Requirement: The event page plays one video at a time

Whenever a video of the page starts to play while another video of the page is playing, the other SHALL be paused where
it is. This SHALL hold between any two of the page's players, in either order: the Movie section's player, a clip's
player in the read view, a clip's preview in Edit mode and the Timeline's video (Edit mode only; its shown and its standby `<video>` are one player), however the video was started (its
own controls, a keyboard key, a chapter jump in the Movie section's chapter list, a thumbnail's play control, the
Timeline's Play, or a player's Play after a thumbnail's control opened it). The rule SHALL be one rule for every video, held in
one place, and not a rule per pair of players: a player added to the page SHALL be covered by it without being named
in it. Neither video SHALL be closed, replaced, restarted or seeked by it, no word SHALL be announced for it, and
pausing SHALL be the only thing the page does: the video that was paused SHALL stay available and play on from its
position when its own Play is pressed. A video that Skip cuts seeks, that plays on after a seek or after a change of
its file at a clip boundary, or the Timeline's standby that takes over from its shown video at a clip boundary, SHALL
NOT count as starting, and a paused standby SHALL NOT count as playing. A video that is paused or ended SHALL NOT be touched.

#### Scenario: A clip started while the movie plays
- **WHEN** the Movie section's player plays at `1:12` and the operator presses Play in the open player of
  `s1710001.mp4`
- **THEN** the movie is paused at `1:12`, the clip plays, and the Movie section's player is still there

#### Scenario: A clip started from its thumbnail while the movie plays
- **WHEN** the Movie section's player plays at `1:12`, the operator presses "Play s1710001.mp4" on that clip's
  thumbnail, whose player opens paused, and then presses the player's Play
- **THEN** the movie is paused at `1:12` and stays there, the clip plays, and nothing has been closed

#### Scenario: The movie started while a clip plays
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the operator presses play in the Movie section's
  player
- **THEN** the clip's player is paused at `0:03.2`, stays open, and plays on from `0:03.2` when its Play is pressed,
  which pauses the movie

#### Scenario: A chapter jump starts the movie while a clip plays
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the operator presses the second chapter in the Movie
  section's chapter list
- **THEN** the movie plays from that chapter, the clip's player is paused at `0:03.2` and stays open

#### Scenario: Two clips never play together
- **WHEN** the player of `s1710001.mp4` plays and the operator presses "Play s1710002.mp4" on its thumbnail, and then the
  second player's Play
- **THEN** the first player has closed, as one player is open at a time, and only the second clip plays

#### Scenario: The Timeline and a clip's player
- **WHEN** in the read view the operator presses "Play s1710001.mp4" on a thumbnail and then the player's Play
- **THEN** the clip plays and no Timeline video exists to pause: the read view has no Timeline (`event-timeline`, "The
  Timeline is shown only in Edit mode, open from the start"); in Edit mode a clip's preview and the Timeline follow the
  next scenario

#### Scenario: Edit mode's preview and the Timeline
- **WHEN** in Edit mode a clip's preview plays in the bin's player and the operator presses Play on the Timeline
- **THEN** the preview closes as "Edit mode holds one video at a time" says, the player shows the clip's
  thumbnail, and only the Timeline plays

#### Scenario: The Timeline's hand-over is not a start
- **WHEN** in Edit mode the Timeline plays across the boundary from `s1710001.mp4` into `s1710002.mp4`, its standby
  taking over
- **THEN** the Timeline still plays and its button says "Pause", no other video of the page is paused, and nothing is
  announced
