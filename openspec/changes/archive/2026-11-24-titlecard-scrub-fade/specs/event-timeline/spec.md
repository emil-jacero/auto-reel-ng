## MODIFIED Requirements

### Requirement: The Timeline plays the title cards as the movie will

When the Timeline plays into a **black** card's span, the player area SHALL show that card's image in place of the
video, fitted inside the same box as the video (letterboxed, uncropped), with the card's fade-in and fade-out as its
opacity over the card's length. The playhead SHALL advance in real time for the card's whole `duration`, without any
video playing, and then playback SHALL go on into the chapter's first clip at that clip's first kept frame. The
Timeline SHALL load and seek that clip's proxy during the card, so that the hand-over shows the clip's frame with no
gap of black or of a stale picture; the card's image SHALL be removed only when that frame is ready to be shown, and
if it is not ready when the card ends the card SHALL stay on its last frame until it is. A **video** card's image
(text on transparency) SHALL be laid over the playing video for the card's window, from the start of the first kept
span to its clamped end, drawn above the video at the same size and position, with the fades as opacity; it SHALL
add no time and SHALL not touch the video. The card's fades SHALL be the project's default fades (2 s in, 2 s out)
scaled so that their sum does not exceed the card's length, as the render clamps them, because the event detail does
not carry them; the Timeline SHALL say once, in the Timeline's help, that a fade set by the event's or
the project's `look.title_card` is not shown here.

Pause and Play, Space on the playhead, and a seek SHALL work inside a card: Pause stops the card's clock where it is,
and Play goes on from there. Pause SHALL leave the card's image at the opacity it had when the clock stopped, in a
black card's span and in a video card's window; it SHALL NOT jump to full opacity. A video that starts elsewhere on
the page ("The Timeline pauses, and is paused, like every
other player") SHALL pause the Timeline during a card too, with the playhead where it stopped and no announcement; the
card's clock SHALL NOT go on by itself afterwards. A card's span in a cut-skipping play SHALL be played whole. The
sound of a card is silence; the Timeline SHALL not start an audio element for it.

The card clock SHALL be the browser's frame clock, and SHALL be driven by elapsed time, not by a count of frames, so a
slow frame does not stretch the card. A page that is hidden SHALL pause the clock as it pauses a video.

#### Scenario: Play from zero through the opening card
- **WHEN** an event whose opening card is black and 7.0 s is played from 0:00 on Chrome 154 and on Firefox 155 or
  newer
- **THEN** the card's image is shown, the playhead moves from 0 to 7.0 s over about 7 s, and then the first clip's
  video plays from its first frame with the card gone, and the sampled playhead never goes backwards

#### Scenario: The hand-over has no gap
- **WHEN** the card ends and the clip's proxy was loaded and sought during the card
- **THEN** no sampled frame between the card's last frame and the clip's first shows the page's background, and the
  video's `currentTime` is the clip's first kept time when the card goes

#### Scenario: A video card over the video
- **WHEN** the Timeline plays a chapter whose card is video and 4.0 s over its first clip
- **THEN** the card's image is above the video for 4.0 s of the clip's time, the video keeps playing under it, the
  card's opacity rises over its fade-in and falls over its fade-out, and the image is gone after the window

#### Scenario: Pause and Play inside a card
- **WHEN** the operator presses Pause 1.2 s into a 7.0 s black card and then Play
- **THEN** the playhead stops at 1.2 s of the card, the image stays at opacity 0.6 (1.2 s into its 2 s fade-in), the
  button says "Play", and Play goes on from 1.2 s and ends the card 5.8 s later

#### Scenario: Pause during a video card's fade-out
- **WHEN** the Timeline plays a 4.0 s video card's window and the operator presses Pause 3.0 s into it
- **THEN** the video stops, and the card's image stays over it at opacity 0.5 (1.0 s before the window's end, in its
  2 s fade-out), not at full opacity

#### Scenario: Another player starts during a card
- **WHEN** the Timeline is inside a black card and the operator presses Play on the event's movie
- **THEN** the Timeline is paused with its playhead where it was, the movie plays, nothing is announced, and the card
  does not go on

#### Scenario: A slow frame does not stretch the card
- **WHEN** the browser presents no frame for 500 ms during a 7.0 s card
- **THEN** the card still ends 7.0 s after it began, within one frame

### Requirement: The playhead can be put in a card, and the readouts count card time

Pressing or dragging the playhead, on the ruler or on the track, into a black card's span SHALL put the playhead in
that card at that point and show that card's image there (opacity from its fades at that time), with no video change
beyond what the clip after the card needs for "The Timeline plays the title cards as the movie will". The playhead
SHALL be at the pointer in the card; the time it names SHALL count the card. The Event readout SHALL count the cards'
time: with the playhead 1.0 s into the opening card it reads "Event 0:01.00 of 2:43.76", the length being the movie's length with its
black cards, as the readout's scale is chosen from it. Inside a card the Clip readout SHALL read "Card 0:01.20 of
0:07.00" (the time in the card and the card's length, written to one scale so that the readout's width does not
change), and the clip's name cell SHALL name the card ("Title card for the opening"). The playhead slider's value text
SHALL say "title card for <chapter>, 1.2 s of 7.0 s; event 0:01.20 of 2:43.76" in a card, and `aria-valuenow` SHALL be
the position on the whole timeline including cards.

At every position of the playhead in a black card's span or in a video card's window, the card SHALL be shown at the
opacity of its fades at that time, the same opacity that play shows there, however the playhead got there: the
Timeline's opening position, Play, a press, a drag, a frame or seconds step, Home, Previous/Next clip, Move to, a
suggestion, or a re-placing after a read or an edit. Whether the Timeline is playing SHALL NOT change the opacity, and
a paused position SHALL NOT be shown at full opacity unless its fades give full opacity there. At a card's first
instant that opacity is 0, as in the movie: a black card's span then shows black, and a video card's window shows the
video alone. The same holds at a black card's end, which the playhead reaches only when an edit shortens the card
below the playhead's place in it and the playhead is held to the new end.

A press in a black card's block on the track SHALL put the playhead at the pressed point of the card. Activating the
block from the keyboard (a press with no pointer position, as Enter gives) SHALL put the playhead at the end of the
card's fade-in, where the card is first shown at full opacity.

A frame step (Left, Right) and Shift/Page steps SHALL be taken on the timeline including cards: a step by seconds
(Shift, Page Up, Page Down) that lands in a card stops there; a frame step into the card from the clip before it SHALL
land on the card's first instant, and from the card on the clip's first frame; Home SHALL be the start of the opening
card when the opening card is black and End the last frame of the last clip. Within a card, Left and Right SHALL move by
one frame of the movie's output rate if the Timeline knows it, else by 0.1 s; the Timeline SHALL not claim frame
accuracy in a card. The end of a scrub, a key step and a click that end in a card SHALL be announced once ("Playhead at
title card for the opening, 1.20").

#### Scenario: A press into a mid card
- **WHEN** the event has a 4.0 s black card between two chapters and the operator presses the track 1.0 s into the
  card's span
- **THEN** the card's image is shown at opacity 0.5 (1.0 s into its 2 s fade-in), the playhead is 1.0 s into the card,
  the Clip readout reads "Card 0:01.00 of 0:04.00", and the Event readout reads the clip time before the card plus
  1.0 s

#### Scenario: A drag across a card
- **WHEN** the operator drags the playhead from the end of the clip before a card, through the card, to the start of the
  next chapter's clip
- **THEN** the card's image shows while the pointer is in its span, at its fades' opacity at the pointer's time: rising
  over the fade-in, full between the fades and falling over the fade-out, as play shows it at those times; the video
  returns after it, never more than one `<video>` for the Timeline and one seek in flight

#### Scenario: A drag shows the same fade whether it began paused or playing
- **WHEN** the operator drags the playhead to 1.0 s into a 7.0 s black card, once starting the drag while the Timeline
  is paused and once while it plays
- **THEN** both drags show the card's image at opacity 0.5 at that point

#### Scenario: A short card's clamped fades while paused
- **WHEN** the Timeline is paused and the operator presses 1.0 s into a 3.0 s black card
- **THEN** the card's image is shown at opacity 2/3 (its fades are clamped to 1.5 s each, as the render clamps them)

#### Scenario: Home onto the opening card shows its first instant
- **WHEN** the Timeline is paused, the opening card is black, and the operator presses Home
- **THEN** the playhead is at the card's start, the stage is black with the card's image at opacity 0 (the movie's
  first frame), the Clip readout reads "Card 0:00.00 of" the card's length, and one more Right shows the image at the
  fade-in's opacity 0.1 s in

#### Scenario: The Edit page opens on an opening black card
- **WHEN** the operator opens an event in Edit mode, the Timeline open, and the event's opening card is black and 7.0 s
- **THEN** the playhead is at the card's start, the stage is black with neither the card's image nor its title
  visible (opacity 0, the movie's first frame), the Clip readout reads "Card 0:00.00 of 0:07.00", and one Right shows
  the card at opacity 0.05

#### Scenario: Next clip into a chapter with a video card
- **WHEN** the Timeline is paused in a chapter and the operator presses Next clip, and the next chapter's card is
  video, 4.0 s, over its first clip
- **THEN** the playhead is on that clip's first kept frame, at the start of the card's window, and the card's image is
  over the video at opacity 0 (at most one frame of its 2 s fade-in), not at full opacity

#### Scenario: A step back from a clip into its card
- **WHEN** the Timeline is paused on the first frame of a chapter's clip after a 4.0 s black card and the operator
  presses Left
- **THEN** the playhead is 3.9 s into the card and the card is shown at opacity 0.05 (0.1 s before its end, in its
  2 s fade-out)

#### Scenario: A keyboard activation of a black card block
- **WHEN** the Timeline is paused and the operator moves focus to a 4.0 s black card's block with Tab and presses
  Enter
- **THEN** the card is selected as a press selects it, the playhead is 2.0 s into the card (the end of its fade-in),
  and the card's image is shown at full opacity

#### Scenario: A frame step into a card
- **WHEN** the Timeline is paused on the last frame of the clip before a 4.0 s black card and the operator presses
  Right
- **THEN** the playhead is on the card's first instant and the card is shown at opacity 0; a Shift+Right then shows it
  at opacity 0.5, 1.0 s in

#### Scenario: A paused position in a video card's window
- **WHEN** the Timeline is paused and the operator presses the track 1.0 s into a 4.0 s video card's window, and then
  presses before the window and after it
- **THEN** the card's image is over the video at opacity 0.5 at 1.0 s in, and no card layer is shown before the window
  or from its end on

#### Scenario: The Event readout counts card time
- **WHEN** the playhead is 3.00 s into the opening card of an event whose movie is 2:43.76 long
- **THEN** the Event readout reads "Event 0:03.00 of 2:43.76" and the Clip readout reads "Card 0:03.00 of" the card's length

#### Scenario: The slider says it is in a card
- **WHEN** a screen reader reads the playhead 1.2 s into the opening card of 7.0 s
- **THEN** its value text names the title card, 1.2 s of 7.0 s, and the event time including cards
