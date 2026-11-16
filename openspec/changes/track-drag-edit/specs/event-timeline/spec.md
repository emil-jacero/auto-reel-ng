## ADDED Requirements

### Requirement: A clip is reordered by dragging it on the track

In Edit mode a press with a mouse or a pen on a clip block's body that moves more than 3 px SHALL start a drag: the block follows the
pointer, the other clips make room live, and a line with words shows the drop place. Release SHALL make one draft edit
(reorder, or move into another chapter when the place is in another chapter's span or on its band). Escape or a
release outside the track SHALL cancel with no edit, and Escape during a drag SHALL only cancel the drag: the clip stays selected. With touch, a swipe on a clip block SHALL still scroll the track and start no drag; a finger reorders through the bin or the Alt keys ("A selected clip is moved by keyboard"), not by dragging on the track.

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
from the track onto the bin SHALL ignore it. Each SHALL be one draft edit, the draft ignore/include edit. Ignoring and including SHALL be draft edits of the clip's ignore state: counted by the top bar,
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

## MODIFIED Requirements

### Requirement: The playhead scrubs one video

The Timeline SHALL hold exactly one `<video>`, created when the track opens, showing the proxy of the clip the playhead is in, at the playhead's time in that clip. The playhead SHALL be a slider over the whole timeline: it SHALL have the role `slider`, a name ("Playhead"), `aria-valuemin`, `aria-valuemax` and `aria-valuenow` in the timeline's seconds, and a value text that names the clip, the time in it and the time in the whole timeline, each said by its noun ("Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12", the times in the Cuts panel's time format, not padded). Dragging on the ruler SHALL move the playhead; so SHALL dragging on the track's empty lane or a black card's span with a mouse or a pen, and so SHALL dragging the playhead's own grip. With touch, the ruler SHALL scrub and a swipe on the track body, clip blocks included, SHALL scroll it. A press on the ruler SHALL move the playhead there, and so SHALL a press on the track's empty lane. A single press on a clip's block (its body, not its edge tools or handles) SHALL select the clip and SHALL NOT move the playhead, and in Edit mode a press with a mouse or a pen on it that moves more than 3 px SHALL start a reorder drag, not a scrub ("A clip is reordered by dragging it on the track"), and a reorder drag SHALL NOT move the playhead nor pause or resume play; a press on a cut's span or a video card's span inside the block selects that cut or card on press, and is not dragged (only the rest of the block's body starts a reorder); a double press on it SHALL place the playhead there ("A clip is selected on the track or in the bin"). A press in a black card's span still puts the playhead in the card.

Moving the playhead into another clip SHALL load that clip's proxy into the same `<video>` and seek it, so the picture is the clip's frame at that time; a short flash between two clips is accepted. While the pointer is moving, the Timeline SHALL keep at most one seek in flight and SHALL seek to the latest pointer position when it completes, so that a scrub across many clips never queues a seek per pointer move. The video SHALL be paused while scrubbing. The picture and the playhead SHALL end where the pointer ended.

Below the video the Timeline SHALL show the clip's name, the playhead's time in the clip and in the whole timeline, each pair labelled in words ("Clip 0:00.96 of 0:39.84 · Event 1:02.40 of 2:29.76"), in words readable by assistive technology. The readout SHALL be written, kept to a constant width, with the clip's name cut by an ellipsis, as "Running times are written to a fixed width and say what they are" requires, so that it does not change width as the clip plays or as the playhead passes from one clip into another. The end of a scrub, a key step and a click SHALL be announced once through a polite status region ("Playhead at Harbour, 0:12.40"); the movement of a drag SHALL NOT be announced per update.

A proxy whose playing fails SHALL be said by cause, as the clip preview says it: asking once for the file's first byte tells a proxy that is gone (404, "prepare proxies again") from one the service cannot read, from a file the browser cannot decode, from no answer at all. The Timeline SHALL keep the track and the playhead and offer the Prepare state's button for a gone proxy.

#### Scenario: A scrub shows the right frame
- **WHEN** the operator drags the playhead on the ruler to 16.00 s of the second clip's span
- **THEN** the single video shows that clip's proxy, `currentTime` is that time within the clip, and the slider's value text names the clip and the time

#### Scenario: The grip is dragged
- **WHEN** the operator presses on the playhead's grip and drags it along the ruler
- **THEN** the playhead follows the pointer exactly as when the drag starts on the ruler

#### Scenario: A scrub across a boundary
- **WHEN** the operator drags the playhead from the first clip into the third clip within one second
- **THEN** the video ends on the third clip's proxy at the playhead's time, and the page never held more than one video for the Timeline nor more than one seek in flight

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

### Requirement: A clip is selected on the track or in the bin

A press on a clip block's body (not its edge tools or handles) and a press on its bin row SHALL select the clip. The
block SHALL be outlined with trim handles and the row highlighted; each SHALL be scrolled into view in its pane
without moving keyboard focus there. A press on empty track SHALL select nothing. A press with a mouse or a pen on a clip block's body that moves more than 3 px SHALL start a reorder drag instead ("A clip is reordered by dragging it on the track"), and the dragged clip SHALL be the selected one when the drag ends, whether or not it made an edit; Escape during that drag cancels only the drag and keeps the selection.

#### Scenario: Bin to track
- **WHEN** the track shows 0–20 s and the operator presses the bin row of a clip drawn at 31 s
- **THEN** the clip is selected, the track scrolls so the clip is in view, and focus stays on the bin row

#### Scenario: Bin press again
- **WHEN** a clip is selected, the track is scrolled away from it, and the operator presses its bin row again
- **THEN** the track scrolls back to the clip

#### Scenario: Empty track
- **WHEN** the operator presses the track below the last lane
- **THEN** nothing is selected and the inspector shows the Event tab

#### Scenario: A press that moves 3 px or less only selects
- **WHEN** the operator presses a clip block's body and moves 2 px, then releases
- **THEN** the clip is selected and nothing was dragged
