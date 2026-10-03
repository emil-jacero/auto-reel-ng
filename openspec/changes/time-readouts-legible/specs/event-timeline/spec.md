## MODIFIED Requirements

### Requirement: The playhead scrubs one video

The Timeline SHALL hold exactly one `<video>`, created when the track opens, showing the proxy of the clip the playhead is in, at the playhead's time in that clip. The playhead SHALL be a slider over the whole timeline: it SHALL have the role `slider`, a name ("Playhead"), `aria-valuemin`, `aria-valuemax` and `aria-valuenow` in the timeline's seconds, and a value text that names the clip, the time in it and the time in the whole timeline, each said by its noun ("Harbour, clip 0:12.4 of 0:24.96; event 1:12 of 3:12", the times in the Cuts panel's time format, not padded). Dragging on the ruler SHALL move the playhead; so SHALL dragging on the track body with a mouse or a pen, and so SHALL dragging the playhead's own grip. With touch, the ruler SHALL scrub and a swipe on the track body SHALL scroll it. A press on the ruler or the track SHALL move the playhead there.

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

