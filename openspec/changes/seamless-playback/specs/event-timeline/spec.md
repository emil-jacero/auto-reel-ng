## ADDED Requirements

### Requirement: Play crosses a clip boundary without a pause

While the Timeline plays, the next clip SHALL be loaded and started one measured play start-up latency before the
playing clip ends, sought to its first kept frame less a learned pre-roll of at most 40 ms. The picture SHALL go from
one clip to within a few frames of the first kept frame of the next with no blank picture; if the next clip is not
ready, the last frame SHALL stay on screen until it is. A black title card keeps the card's hand-over.

#### Scenario: A plain boundary
- **WHEN** on `2024-06-27 - Grillning med grannar` the Timeline plays from 0:04.00 of `s1710001.mp4` into
  `s1710002.mp4`
- **THEN** every sample of the stage across the boundary shows a frame of one of the two clips, never the stage's
  background; the first presented frame of `s1710002.mp4` is within 5 frames (0.10 s, 50 fps proxy) of its first kept frame, so
  up to a few frames at its start can be skipped; the playhead and the readout move into
  `s1710002.mp4`; and the request for `s1710002.mp4`'s proxy was made before `s1710001.mp4` ended

#### Scenario: The boundary gate
- **WHEN** a script plays at least 20 plain boundaries per browser between 50 fps proxies, each next clip having had
  at least 1 s of play to load, in headed Chrome 157 or newer and in headed Firefox 155 or newer, with the browser's
  sound on and routed to an audio output that accepts the stream but reaches no speaker (a null sink), the page
  visible throughout, counting only boundaries whose steady play keeps its cadence (in the second before the boundary
  no frame is held longer than three refresh intervals of the display plus 2 ms, 52 ms at 60 Hz)
- **THEN** the numbers are those measured and accepted by the operator on 2026-11-23 (research §6.10). Definitions are
  design D7's; lost and hold are in milliseconds, each clip's position taken from its presented frames (frame callback
  time minus media time), not from `currentTime`.
  - **Plain boundaries into a clip's start (IN = 0), per browser:** the play time lost at a boundary is at most one
    frame interval (20 ms) at the 90th percentile; the hold at the 90th percentile is at most the median of the steady
    play's longest hold plus 40 ms in Firefox (two intervals of the 20 ms proxy frame; 90 ms at a steady median of
    50 ms) and plus 67 ms in Chrome (two intervals of its reported 33.5 ms cadence; about 100 ms at a steady median of
    33.5 ms); no boundary holds a frame longer than
    150 ms or skips more than 60 ms of the incoming clip.
  - **Relative to the single-element hand-over** (the same script, run in the same session against the hand-over this
    change replaces): lost at the 90th percentile is at most half of the single element's, in both browsers. Hold at
    the 90th percentile is at most half of it in Firefox (83 against 255.5 ms); in Chrome it is lower but not half
    (50.1 against 83.4 ms), so the Chrome hold is met by the absolute bound above only.
  - **Leading-cut boundaries (the incoming clip entered at IN above 0), a known limitation:** lost at the 90th
    percentile is at most half of the single element's in both browsers (Firefox 29.8 against 237.2 ms, Chrome 20.5
    against 153.8 ms), and the absolute bounds above are not all met: lost p90 is over 20 ms in both browsers (Firefox 29.8 ms,
    Chrome 20.5 ms) and Firefox hold p90 117 ms is over 90 ms (the other terms are met: Firefox max 134 ms, Chrome hold
    p90 83.5 ms and max 116.7 ms). All of these figures fail the first gate (70 / 54 / 100). The hold at the 90th percentile is below the single element's in
    Firefox (117 against 226.8 ms) and equal to it in Chrome (83.5 ms). No bound is claimed for them.
  - **Not claimed:** a floor on negative lost time. The incoming clip's start is typically skipped by about two frames, at most about three
    (p10 lost -41.5 ms in Firefox, -39.4 ms in Chrome; max skip 56.0 / 59.5 ms; IN = 0).

#### Scenario: Pause during the lead
- **WHEN** the Timeline plays the last 0.2 s of `s1710001.mp4` with `s1710002.mp4` in its standby and the operator
  presses Pause just after the standby has started
- **THEN** the Timeline is paused on `s1710001.mp4`, the standby is paused at its pre-sought position (its first kept frame less the pre-roll), no frame
  of `s1710002.mp4` was shown, and Play then crosses the boundary as before

#### Scenario: Play again while the standby is returning
- **WHEN** the operator pauses during the lead and presses Play again before the standby has finished seeking back
- **THEN** the boundary does not hand over to the standby until its seek has landed, and no frame of the wrong
  position is shown

#### Scenario: Into a leading cut
- **WHEN** the clip after the playing one has a cut from 0 to 1.50 s
- **THEN** the first frame of it on screen is its frame at 1.50 s, no frame inside the cut is shown, and the boundary
  has no added pause

#### Scenario: Over a clip that is cut whole
- **WHEN** the clip after the playing one is cut from its start to its end
- **THEN** play goes on into the clip after that one, as the render skips the cut clip, with no added pause

#### Scenario: The next clip is not ready in time
- **WHEN** the next clip's proxy answers so slowly that it is not ready when the playing clip ends
- **THEN** the playing clip's last frame stays on screen, never the stage's background, until the next clip is
  ready, and play goes on from the next clip's first kept frame

#### Scenario: The order changes while playing
- **WHEN** the Timeline plays `s1710001.mp4` and the operator moves `s1710003.mp4` to directly after it
- **THEN** at the end of `s1710001.mp4` play goes on into `s1710003.mp4`, not into the clip that was next before

#### Scenario: Into a black card
- **WHEN** the next chapter opens with a black title card
- **THEN** the card plays and hands over to its clip as "The Timeline plays the title cards as the movie will" says

### Requirement: The Timeline's standby video is never seen or counted as a player, and heard only as the incoming clip

The Timeline SHALL load a standby `<video>` only once it plays, with the clip play goes on into (design D3). The standby SHALL be
invisible, hidden from assistive technology, out of the Tab order, and muted and not counted as playing until its early
start, then play unmuted until it takes over. A pause, scrub, seek, Previous or Next clip, yield or reload SHALL put a
started standby back at its pre-sought position; Play within the end slack SHALL hand over to it. A preview and closing release it.

#### Scenario: Play within the end slack hands over to the standby
- **WHEN** the operator pauses during the lead 50 ms before a clip's end, and presses Play
- **THEN** play goes on from the standby that holds the next clip's first kept frame, and the shown video is not loaded with that clip, so no blank frame is shown

#### Scenario: Nothing loads ahead while paused
- **WHEN** Edit mode opens on an event and the operator moves the playhead without pressing Play
- **THEN** only the proxies of the clips the playhead was put in are requested, and no standby loads

#### Scenario: The standby is not seen, and heard only in the lead
- **WHEN** the Timeline plays `s1710001.mp4` with `s1710002.mp4` loaded in its standby
- **THEN** the standby is muted, fully transparent, hidden from assistive technology and not focusable, and a
  screenshot of the stage shows only `s1710001.mp4`'s frame; and in the last lead before the boundary the standby
  plays unmuted and is still fully transparent, with the screenshot showing only `s1710001.mp4`

#### Scenario: Another player starts before the boundary
- **WHEN** the Timeline plays the last second of `s1710001.mp4` and the operator presses Play on the event's movie
- **THEN** the Timeline pauses, its standby does not start (or, if it had started, is paused and put back at its
  first kept frame), and the movie keeps playing

#### Scenario: Use as poster after a hand-over
- **WHEN** play has gone on into `s1710002.mp4`, the operator pauses at 0:01.00 of it and presses Use as poster
- **THEN** the draft's poster is `s1710002.mp4` at 1.000 s and the poster area shows that clip's frame

## MODIFIED Requirements

### Requirement: The playhead scrubs one video

The Timeline SHALL show exactly one loaded `<video>` (its shown video), created when the track opens, showing the proxy of the clip the playhead is in, at the playhead's time in that clip. Its second `<video>` element (the standby slot) has no source until the Timeline plays, MAY hold one while it plays and after a pause, which is never shown before it takes over ("The Timeline's standby video is never seen or counted as a player, and heard only as the incoming clip"). The playhead SHALL be a slider over the whole timeline: it SHALL have the role `slider`, a name ("Playhead"), `aria-valuemin`, `aria-valuemax` and `aria-valuenow` in the timeline's seconds, and a value text that names the clip, the time in it and the time in the whole timeline, each said by its noun ("Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12", the times in the Cuts panel's time format, not padded). Dragging on the ruler SHALL move the playhead; so SHALL dragging on the track's empty lane or a black card's span with a mouse or a pen, and so SHALL dragging the playhead's own grip. With touch, the ruler SHALL scrub and a swipe on the track body, clip blocks included, SHALL scroll it. A press on the ruler SHALL move the playhead there, and so SHALL a press on the track's empty lane. A single press on a clip's block (its body, not its edge tools or handles) SHALL select the clip and SHALL NOT move the playhead, and in Edit mode a press with a mouse or a pen on it that moves more than 3 px SHALL start a reorder drag, not a scrub ("A clip is reordered by dragging it on the track"), and a reorder drag SHALL NOT move the playhead nor pause or resume play; a press on a cut's span or a video card's span inside the block selects that cut or card on press, and is not dragged (only the rest of the block's body starts a reorder); a double press on it SHALL place the playhead there ("A clip is selected on the track or in the bin"). A press in a black card's span still puts the playhead in the card.

Moving the playhead into another clip (a scrub, a press, a key, Previous or Next clip) SHALL load that clip's proxy into the shown `<video>` and seek it, so the picture is the clip's frame at that time; a short flash between two clips is accepted for such a move, and not when Play goes on into the next clip ("Play crosses a clip boundary without a pause"). While the pointer is moving, the Timeline SHALL keep at most one seek in flight and SHALL seek to the latest pointer position when it completes, so that a scrub across many clips never queues a seek per pointer move. The video SHALL be paused while scrubbing. The picture and the playhead SHALL end where the pointer ended.

Below the video the Timeline SHALL show the clip's name, the playhead's time in the clip and in the whole timeline, each pair labelled in words ("Clip 0:00.96 of 0:39.84 · Event 1:02.40 of 2:29.76"), in words readable by assistive technology. The readout SHALL be written, kept to a constant width, with the clip's name cut by an ellipsis, as "Running times are written to a fixed width and say what they are" requires, so that it does not change width as the clip plays or as the playhead passes from one clip into another. The end of a scrub, a key step and a click SHALL be announced once through a polite status region ("Playhead at Harbour, 0:12.40"); the movement of a drag SHALL NOT be announced per update.

A proxy whose playing fails SHALL be said by cause, as the clip preview says it: asking once for the file's first byte tells a proxy that is gone (404, "prepare proxies again") from one the service cannot read, from a file the browser cannot decode, from no answer at all. The Timeline SHALL keep the track and the playhead and offer the Prepare state's button for a gone proxy.

#### Scenario: A scrub shows the right frame
- **WHEN** the operator drags the playhead on the ruler to 16.00 s of the second clip's span
- **THEN** the shown video shows that clip's proxy, `currentTime` is that time within the clip, and the slider's value text names the clip and the time

#### Scenario: The grip is dragged
- **WHEN** the operator presses on the playhead's grip and drags it along the ruler
- **THEN** the playhead follows the pointer exactly as when the drag starts on the ruler

#### Scenario: A scrub across a boundary
- **WHEN** the operator drags the playhead from the first clip into the third clip within one second
- **THEN** the video ends on the third clip's proxy at the playhead's time, the page never showed more than one video for the Timeline, the scrub loaded and sought only the shown video, and never more than one seek was in flight

#### Scenario: The speed of a scrub
- **WHEN** a scripted drag sweeps the playhead across one clip of each of the event's proxies in Chrome 154 and in Firefox 155 or newer
- **THEN** the median number of distinct frames presented per second is at least 30 in each

#### Scenario: The clips shrink under the playhead
- **WHEN** the page reads the event again, quietly, and the clip the playhead is on is no longer shown (it is missing, excluded or ignored now)
- **THEN** the Timeline stays on the page with the clips that remain, the playhead goes to the start, and nothing is blank or thrown

#### Scenario: The proxy is gone
- **WHEN** a proxy file is removed from the cache after the page read the event, and the playhead moves into that clip
- **THEN** the Timeline says that this clip's proxy is no longer there and offers "Prepare proxies", while the track and the other clips keep working

#### Scenario: The readout says what each number is and holds still
- **WHEN** the Timeline of an event whose clips are 9.00 s, 40.00 s and 6.02 s is played from the start, in Chrome 154
  and in Firefox 155 or newer, light and dark, at 1280 and at 390 pixels wide
- **THEN** every sample of the readout, taken every 100 ms across the first clip's end, reads `Clip <time> of <length>
  · Event <time> of 55.02`, with the same width for each time and the same left edge for each pair, and the slider's
  value text says "clip" and "event" with the same numbers

#### Scenario: A clip press does not move the playhead
- **WHEN** the playhead is at 5.0 s and the operator presses once on the body of a clip's block elsewhere
- **THEN** the clip is selected and the playhead is still at 5.0 s

#### Scenario: A finger swipe on a clip scrolls
- **WHEN** with touch the operator swipes 40 px sideways starting on a clip block's body
- **THEN** the track scrolls, no reorder drag starts and the playhead has not moved

#### Scenario: A clip drag does not scrub
- **WHEN** in Edit mode the operator presses on the body of a clip's block and moves 20 px sideways
- **THEN** a reorder drag starts and the playhead has not moved

#### Scenario: A double press places the playhead
- **WHEN** the operator presses twice on the body of a clip's block
- **THEN** the clip is selected and the playhead is at the press

### Requirement: Edit mode holds one video at a time

Edit mode SHALL never hold more than one player: the Timeline's, whose shown `<video>` exists while its track is open and whose standby `<video>` holds a source only once it plays ("The playhead scrubs one video"), or the preview's in the bin's player. Opening a clip's preview, with the player's Play ("Edit mode previews a clip on request"), SHALL release both of the Timeline's videos, stopping their playback and their loading, and keep the Timeline open with the playhead where it stood and every handle usable. Moving the playhead, or pressing Play, on the Timeline SHALL close the player's preview, which shows its clip's thumbnail again, and create the Timeline's shown video again at the playhead (it loads the proxy of the clip the playhead is in, as when the track opens). Selecting a clip on the track SHALL NOT release the Timeline's video: the player shows the clip's thumbnail until its Play is pressed. Releasing and creating the video SHALL NOT be an edit, SHALL NOT disturb a drag or a typed time, and SHALL NOT move keyboard focus off the control that had it.

#### Scenario: A preview releases the timeline's video
- **WHEN** in Edit mode the Timeline's video has been scrubbed to 1.6 s of `s1710001.mp4`, the operator presses that clip's block and then Play in the bin's player
- **THEN** after the press on the block the page still holds the Timeline's video; after Play it holds one video with a source, the clip's preview, and the Timeline is still open with its playhead at 1.6 s and its handles working

#### Scenario: Scrubbing closes the preview
- **WHEN** a clip's preview is open in the bin's player and the operator moves the Timeline's playhead
- **THEN** the preview closes, the player shows the clip's thumbnail, the Timeline's video shows the playhead's frame, and the page holds one video with a source

#### Scenario: A preview opened while the Timeline plays
- **WHEN** the Timeline plays `s1710001.mp4` with `s1710002.mp4` loaded in its standby, and the operator plays the
  preview of `s1710003.mp4` in the bin's player
- **THEN** the page holds one video, the preview; neither of the Timeline's videos remains, and no Timeline proxy is
  requested until the operator moves the playhead or presses Play
### Requirement: The Timeline shows a clip's turn

The Timeline SHALL show a clip turned by the clip's `rotate` (the draft's),
as "Every picture of a clip shows its turn" requires: its shown video, while the playhead is in the clip, and each tile of
the clip's filmstrip. The turn SHALL be a transform of the proxy's picture and of the sprite's tiles; the proxy and the
sprite SHALL NOT be requested again because of a turn. The track's geometry SHALL NOT depend on a turn: a clip's lane
width SHALL stay its proxy's length, its tiles SHALL keep the lane height, and a turned tile SHALL be fitted inside its
tile box, uncropped. The playhead, the chapters, the cuts, the trim handles and the suggestions SHALL keep their places
and times. A change of a turn in the draft SHALL show on the video and the tiles at once. At the swap between clips the
video that shows the next clip SHALL be turned by that clip's turn before it is shown: a standby carries its clip's
turn from the moment it loads, and takes a turn changed meanwhile at once.

#### Scenario: Filmstrip tiles are turned and fitted
- **WHEN** a landscape clip with `rotate: 90` is on the Timeline
- **THEN** each of its tiles shows the frame turned a quarter clockwise, whole inside the tile, and the lane is as wide as before

#### Scenario: The video follows the clip it is in
- **WHEN** play passes from an unturned clip to one turned 90 degrees
- **THEN** the video is shown turned for the second clip, and unturned again after the next unturned clip

#### Scenario: Turning in Edit mode shows at once
- **WHEN** the operator presses Rotate right on a clip in Edit mode
- **THEN** its tiles and, when the playhead is in it, the video show the new turn with no request for a sprite or a proxy

#### Scenario: The standby is turned before it is shown
- **WHEN** the Timeline plays `s1710001.mp4` (unturned) with `s1710002.mp4` (`rotate: 90`) in its standby, and the
  operator presses Rotate right on `s1710002.mp4` before the boundary
- **THEN** the first frame of `s1710002.mp4` on screen is already turned 180 degrees, and its proxy is not requested
  again
