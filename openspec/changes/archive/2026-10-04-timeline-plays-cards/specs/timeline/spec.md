## ADDED Requirements

### Requirement: The model plays a movie of clips and cards on one clock

The model SHALL give the movie's play order as a list of **stages** in track time, from the card map and the layout:
a clip stage per shown clip, and a card stage (with its chapter, length and background) before the clip it anchors for
each black card, so that stage times add up to the track's total. A **position on the track** SHALL be a stage and a
time in it, and the model SHALL map between it and a track time in whole milliseconds, a boundary being the later
stage's start, a time before zero the first instant and a time past the end the last frame. The playhead's clip
position SHALL stay the clip time it is today: a position in a card SHALL hold the card's anchor clip and the card's
elapsed time, so that every consumer of clip time (cuts, handles, marks) is unchanged and is told a card is not a clip
by a single field.

The model SHALL compute **what is shown** at a position: for a black card, the card and its opacity at the elapsed time
from its fades; for a clip, the clip and the video card, if any, whose window holds the clip time, with its opacity. The
fades SHALL be taken as the default 2.0 s in and 2.0 s out, scaled down together so that their sum does not exceed the
card's length, and the opacity SHALL be 0 at the start of the fade-in, 1 from its end to the start of the fade-out,
and 0 at the end of the card; a card whose length is not a finite number above zero SHALL be refused with a
`ModelError` and not played. The model SHALL compute the **hand-over**: what follows a card is the anchor clip at its
first kept time, which is the end of a cut span that begins at zero, else zero; and what follows a clip is the next
clip's card if it has a black one, else the next clip, else the end. The model SHALL give the time a card clock has
reached from an elapsed real time since it started, held to the card's length, and SHALL read no clock itself: the
clock is passed in. The model SHALL import no DOM, React, network or file module and add no dependency.

#### Scenario: Stages add up
- **WHEN** a 3,000 ms black card and a 4,000 ms black card anchor at the starts of clips of 20,000 ms and 20,000 ms
- **THEN** the stages are card, clip, card, clip with starts at 0, 3,000, 23,000 and 27,000 ms, and the total is 47,000 ms

#### Scenario: A position in a card
- **WHEN** the track time 1,500 ms is mapped to a position with a 3,000 ms black card first
- **THEN** it is in the card stage at 1,500 ms elapsed, with the anchor clip index and clip time 0, and mapped back it
  is 1,500 ms

#### Scenario: Round trip
- **WHEN** every whole second of the track above is mapped to a position and back
- **THEN** each returns itself

#### Scenario: Opacity follows the fades
- **WHEN** a 7,000 ms card with fades of 2,000 ms is asked for its opacity at 0, 1,000, 2,000, 3,500, 5,000, 6,000 and
  7,000 ms
- **THEN** the answers are 0, 0.5, 1, 1, 1, 0.5 and 0

#### Scenario: The fades are clamped together
- **WHEN** a 2,000 ms card is asked for its opacity at 500 and 1,000 ms
- **THEN** the fades are 1,000 ms each, so it is 0.5 and 1 (at the point where the fade-out begins)

#### Scenario: Hand-over after a card with a leading cut
- **WHEN** the card's anchor clip has a cut from 0 to 3,000 ms
- **THEN** the hand-over is that clip at 3,000 ms

#### Scenario: A video card's window
- **WHEN** a video card of 4,000 ms is anchored on a clip whose first kept span starts at 3,000 ms and lasts 10,000 ms
- **THEN** the overlay is shown for clip times 3,000 to 7,000 ms, with its opacity from the fades, and not at 2,999 or
  at 7,000 ms

#### Scenario: A card's clock is held to its length
- **WHEN** 9,000 ms of real time have passed since a 7,000 ms card began
- **THEN** the time reached is 7,000 ms and the hand-over is due

#### Scenario: A bad length is refused
- **WHEN** a card of length 0 or `NaN` is to be played
- **THEN** the model throws a `ModelError` naming the card, and plays nothing for it
