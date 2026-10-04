# timeline Specification

## Purpose
Own the pure model behind the GUI timeline (`web/src/timeline/model.ts`, D-20): time and pixel conversion in
whole milliseconds on a clip's own frame grid, clip layout and zoom, windowing, a clip's cut spans and
rectangles, trim limits and snapping. The model takes a clip's duration and frame rate as arguments, never
defaults them, and adds no dependency; the views that draw it are other capabilities.

## Requirements

### Requirement: The timeline model works in whole milliseconds on the clip's own frame grid

The timeline's model SHALL take and return every time as a whole number of milliseconds, so that a time it
returns is one the Cuts panel writes and reads back unchanged. It SHALL place a time on a clip's frame grid by
rounding to the nearest frame of the clip's own rate, the time of frame *n* being *n* / rate seconds rounded to
the millisecond. It SHALL NOT use a default frame rate or a default duration: a clip's duration and rate
SHALL be given, and a value that is not a finite number above zero SHALL be refused with an error that names
it, never replaced.

#### Scenario: A 29.97 fps clip is rounded to its own frames
- **WHEN** a time of 1,015 ms is placed on the grid of a 29.97 fps clip
- **THEN** the result is 1,001 ms (frame 30), a whole number of milliseconds

#### Scenario: A 25 fps clip is not assumed
- **WHEN** the same 1,015 ms is placed on the grid of a 50 fps clip
- **THEN** the result is 1,020 ms (frame 51), not 1,000 or 1,040 ms from a 25 fps grid

#### Scenario: A clip without facts is refused
- **WHEN** a clip is described with a duration of 0, a negative duration, `NaN`, or a frame rate of 0
- **THEN** the model raises an error naming the field, and builds no clip

### Requirement: Clips are laid out end to end from their durations and found by time

The model SHALL lay a list of clips end to end, in order, each as long as its own duration, and SHALL report
each clip's start and the total length in milliseconds. It SHALL map a time to the clip that holds it: a time
before zero to the first clip, a time at or past the total to the last clip, and a time that is exactly a
boundary to the later clip. An empty list SHALL have a total length of zero and no clip at any time. It SHALL
convert between time and pixels at a given scale, rounding a pixel position back to a whole millisecond, and
SHALL NOT clamp a position to the timeline on its own.

#### Scenario: Mixed durations
- **WHEN** three clips of 24.96 s, 6.08 s and 0.48 s are laid out
- **THEN** their starts are 0, 24,960 and 31,040 ms and the total is 31,520 ms

#### Scenario: A time on a boundary
- **WHEN** the time 24,960 ms is looked up in that layout
- **THEN** the second clip holds it, and 24,959 ms is held by the first

#### Scenario: Past the end
- **WHEN** a time of 40,000 ms is looked up in that layout
- **THEN** the last clip holds it

#### Scenario: Pixels round back to a millisecond
- **WHEN** 137 px at 40 px per second is converted to a time
- **THEN** the result is 3,425 ms

### Requirement: Zoom is bounded and keeps the moment under the pointer

The model SHALL keep the scale between 4 and 240 pixels per second. A zoom about a point on screen SHALL
leave the time under that point where it is, to the nearest pixel, and SHALL keep the scroll position between
zero and the end of the timeline. A fit SHALL choose the scale at which the whole timeline fills the width,
within the same bounds, and a timeline of zero length SHALL fit at the default scale of 40. The ruler's tick
spacing SHALL be the first of 0.5, 1, 2, 5, 10, 30, 60, 300 and 600 seconds that is at least 70 pixels wide at
the scale, and 600 seconds when none is.

#### Scenario: Zooming in about the pointer
- **WHEN** an 800 px view of a 120 s timeline at 40 px per second, scrolled 400 px, is zoomed by 2 about x = 300
- **THEN** the scale is 80, the time that was under x = 300 (17.5 s) is still under it, and the scroll is 1,100 px

#### Scenario: The bounds hold
- **WHEN** a view at 200 px per second is zoomed by 10, and a view at 5 px per second by 0.1
- **THEN** the scales are 240 and 4

#### Scenario: The end of the timeline stops the scroll
- **WHEN** a zoom out would scroll past the end of a timeline that is narrower than the view
- **THEN** the scroll is 0

#### Scenario: Fit
- **WHEN** a 60 s timeline is fitted to a 1,200 px view
- **THEN** the scale is 20; a 3 s timeline in the same view fits at 240, not 400

### Requirement: Only the clips and ticks near the view are asked for

The model SHALL answer which clips and which ruler ticks lie within the visible range plus a margin, as a
range of positions, found without visiting every clip. The answer for a view SHALL not depend on how many
clips lie outside it, so that an event of hundreds of clips costs what an event of a few does. A clip that
touches the range by any width SHALL be included, including one wider than the view; a view past the end of
the timeline SHALL give no clip.

#### Scenario: A long event shows a few clips
- **WHEN** 5,000 clips of 25 s are laid out at 40 px per second and the view is 800 px wide, scrolled to 600,000 px, with a margin of 200 px
- **THEN** the range holds the clips that touch the view and its margin (clips 599 and 600; clip 601, which
  starts exactly at the margin's edge, is not), and it is found without an operation per clip

#### Scenario: One clip wider than the view
- **WHEN** one clip of 600 s at 240 px per second is scrolled so that the view lies inside it
- **THEN** that clip is the whole range

#### Scenario: Beyond the end
- **WHEN** the view starts after the total length of the timeline
- **THEN** no clip is in range

### Requirement: A clip's cuts are drawn and counted as the render joins them

The model SHALL derive a clip's cut spans as the render does: cuts that are not removed, clamped to the clip,
empty ones dropped, sorted, and overlapping or touching ones merged. The movie length SHALL be the clips'
durations less the time their spans cover, once. Each listed cut that is not removed SHALL have a rectangle,
for its own span clamped to the clip, keyed by its position in the clip's list; a cut that runs past the end
SHALL be drawn up to the end, and a cut wholly past the end or empty SHALL have none. A cut's number
SHALL be its position in the clip's list plus one, as the Cuts panel and the spoken playhead ("in cut 2")
number it, never a rank by start: the model SHALL give the timeline no second numbering, so a handle named
"cut 3 start" is row 3 of the panel. The model SHALL refuse a clip duration that is not a finite number above
zero in every function that takes one, and a time that is not finite in `clipAt`.

#### Scenario: Overlapping cuts read from reel.yaml
- **WHEN** a 10 s clip lists cuts 1 to 3 s and 2 to 4 s
- **THEN** its spans are one span of 1 to 4 s and it contributes 7 s to the movie length, but it has two rectangles

#### Scenario: A cut past the end
- **WHEN** a 6.08 s clip lists a cut of 5 to 7 s
- **THEN** its rectangle runs from 5 s to 6.08 s

#### Scenario: Two cuts do not share a name
- **WHEN** a clip lists cuts at 14 to 17.2 s and 0 to 2.4 s, in that order in the file
- **THEN** their rectangles carry list places 0 and 1, so they are cut 1 and cut 2 as in the panel, and a removed
  cut among them keeps its row's number

#### Scenario: A bad duration is refused, not drawn as nothing
- **WHEN** `cutRects`, `cutSpans` or `movieLengthMs` is given a duration that is `NaN`, zero, negative or not finite
- **THEN** it throws a `ModelError` naming the duration

### Requirement: A trim handle moves within limits that always hold its current place

For a cut's start or end, the model SHALL give the lowest and highest time it may take. The neighbours SHALL
be the clip's other cuts that are not removed and do not overlap this cut (touching is not overlap). The start
SHALL be no earlier than the end of the nearest neighbour before it (else the clip's start), and the end no
later than the start of the nearest neighbour after it (else the clip's end). A cut SHALL stay at least three
frames long, the span being measured from the opposite edge; where that edge is on a frame, the limit SHALL be
on a frame too. The range SHALL always contain the edge's current value: a cut already shorter than three
frames, or overlapping a neighbour as read from `reel.yaml`, SHALL keep its edge where it is, and the range
SHALL never be inverted. A clip shorter than three frames SHALL give a range of the current value only.

#### Scenario: Home and End reach a time the clip can show
- **WHEN** the cut 0 to 2.4 s has its end taken to its lowest limit, at 25 fps and at 29.97 fps
- **THEN** the limits are 120 ms and 100 ms, each three frames after the start and each a frame time; a limit
  of 100 ms at 25 fps (2.5 frames) is never produced

#### Scenario: A neighbour limits the edge
- **WHEN** a 25 s clip has cuts 0 to 2.4 s and 14 to 17.2 s
- **THEN** the second cut's start may move between 2.4 s and 17.08 s, and its end between 14.12 s and 24.96 s

#### Scenario: Overlapping cuts from disk
- **WHEN** a 24.96 s clip at 25 fps lists cuts 1 to 3 s and 2 to 4 s and the first cut's end is asked for its limits
- **THEN** the second cut is not a neighbour, the range is 1.12 s to 24.96 s and contains 3 s, and the first
  cut's start range contains 1 s

#### Scenario: A short typed cut is not widened
- **WHEN** a clip lists a cut of 5.000 to 5.050 s and its end is asked for its limits
- **THEN** the range contains 5,050 ms, and moving the end to 5,050 ms returns 5,050 ms

#### Scenario: A clip too short to cut
- **WHEN** a clip of 0.08 s at 25 fps lists a cut of 0 to 0.08 s
- **THEN** each edge's range is its current value alone

### Requirement: A trim snaps to nearby places within 8 pixels

When a trim edge is moved, the model SHALL snap it to the nearest candidate within 8 screen pixels at the
current scale, and otherwise place it on the clip's frame grid. The candidates SHALL be the clip's start and
end, every other cut's start and end, the playhead when it lies in this clip, and any extra points the caller
gives. Two candidates equally near SHALL resolve to the earlier time, whatever the order they were given in.
The result SHALL then be held to the trim limits, and a limit reached SHALL be returned exactly, not moved
to the frame grid. The model SHALL report the place snapped to only when the result is that place, so a
snap line is never shown where the handle did not arrive. Moving an edge to the place it already holds SHALL
return that place.

#### Scenario: Snapping to a neighbour's edge
- **WHEN** at 40 px per second a start is dragged to 7,900 ms with a candidate at 8,000 ms
- **THEN** the result is 8,000 ms, snapped to 8,000 (4 px away)

#### Scenario: Out of range
- **WHEN** the same drag is made at 10 px per second (8 px is 800 ms) with the candidate at 8,000 ms and a
  highest limit of 7,800 ms
- **THEN** the result is 7,800 ms and no snap is reported

#### Scenario: No candidate within reach
- **WHEN** at 40 px per second an end is dragged to 5,317 ms with the nearest candidate 400 ms away
- **THEN** at 25 fps the result is 5,320 ms (the nearest frame) and no snap is reported

#### Scenario: A tie
- **WHEN** candidates 8,000 and 8,100 ms are given, in either order, for 8,050 ms at 80 px per second
- **THEN** the result is 8,000 ms

### Requirement: The model is pure and adds no dependency

The model SHALL be a module of pure functions of its arguments, with no DOM, React, network or file access and
no import beyond the repository's own pure modules. Its tests SHALL run under the existing `npm test`
(Node's built-in runner) and be type-checked by `tsconfig.test.json`, with no test runner or other package
added. The project's `dependencies` SHALL remain React, React DOM and the three dnd-kit packages. Until a
component imports it, the model SHALL NOT change the production bundle.

#### Scenario: The suite runs without a browser
- **WHEN** `npm test` runs in the project's Node container
- **THEN** the model's tests run and pass, with no DOM and no browser

#### Scenario: The dependency list is unchanged
- **WHEN** `web/package.json` is read after the change
- **THEN** `dependencies` holds `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`, `react` and
  `react-dom` and nothing else, and `devDependencies` gains no entry

#### Scenario: The bundle is measured
- **WHEN** the production build is run before and after the change
- **THEN** the gzip size of the built JavaScript and CSS is recorded for both, and an unwired model adds none

### Requirement: The model places each chapter's card as the render does

The model SHALL compute, for each chapter, whether and where its title card is drawn, from the chapter's shown
clips, their cut spans, the resolved card and whether `look.decorators` includes `title`. A chapter SHALL be
`anchored` when it has a shown clip with footage left after the cuts, the anchor being the chapter's first shown
clip, or the next shown clip with footage when every part of the first is cut; the anchor's start SHALL be the
end of a cut span that begins at zero of the anchor clip, else zero. Otherwise it SHALL be `no-footage`. When the
decorator is not `title`, anchored chapters SHALL be `off`. A card's duration SHALL be taken in whole
milliseconds from seconds, and a value that is not a finite number above zero SHALL be refused with a
`ModelError` naming the card, never replaced. A **video** card's width SHALL be the lesser of its duration and
the anchor's first kept span, and the model SHALL report that it was clamped; a **black** card's width SHALL be
its duration. The model SHALL read no media and use no frame rate.

#### Scenario: Plain chapters
- **WHEN** two chapters each have one 20 s clip without cuts and `look.decorators` is `["title"]`
- **THEN** both are anchored at their first clip with a start of 0

#### Scenario: A wholly cut first clip moves the anchor
- **WHEN** a chapter's first clip is cut from 0 to its end and its second clip is 8 s
- **THEN** the anchor is the second clip

#### Scenario: A leading cut
- **WHEN** the anchor clip has a cut from 0 to 3,000 ms
- **THEN** the anchor's start is 3,000 ms and a video card of 7,000 ms on a first kept span of 3,000 ms is
  3,000 ms wide and clamped

#### Scenario: No footage, and off
- **WHEN** every clip of a chapter is wholly cut, and in another event the decorators are absent
- **THEN** the first chapter is `no-footage`, and the second event's anchored chapters are `off`

#### Scenario: A bad duration is refused
- **WHEN** a card has duration 0, -1 or `NaN`
- **THEN** the model throws a `ModelError` naming the card's duration and places nothing for it

### Requirement: Black cards shift the track by a map that keeps clip time

The model SHALL map a clip time to a track time by adding the lengths of every black card anchored at or before
it, and SHALL map a track time back to a clip time, or to the black card whose span holds it, with no clip time.
A black card at a clip's start SHALL come before the clip's time zero, and video and `off` cards SHALL add
nothing. Positions inside a black card SHALL not map to a clip time. The two maps SHALL be inverses on every
clip time. The movie's length SHALL be the footage less the cut spans plus the black cards' lengths, each once.
Windowing SHALL find the cards in range as it finds clips, without visiting every card.

#### Scenario: Two black cards
- **WHEN** black cards of 3,000 and 4,000 ms anchor at the starts of clips of 20,000 and 20,000 ms
- **THEN** the first clip starts on the track at 3,000 ms, the second at 27,000 ms (20,000 + 3,000 + 4,000), and the total is 47,000 ms

#### Scenario: Inside a card
- **WHEN** a track time of 1,500 ms is mapped back with a 3,000 ms black card first
- **THEN** the result is "in card 0" with no clip time

#### Scenario: Round trip
- **WHEN** every clip time of the 40 s above is mapped to the track and back
- **THEN** each returns itself

#### Scenario: A video card moves nothing
- **WHEN** a video card of 4,000 ms is anchored on the first clip
- **THEN** the track times equal the clip times

#### Scenario: A long event
- **WHEN** 2,000 chapters each have a black card and the view shows a few
- **THEN** the cards in range are found without visiting the rest

### Requirement: The model words a card and holds one card selection

The model SHALL word a card as "Title card for <chapter>, <length>, over video" or "on black" (with "not enabled" when the
decorator is off and "<kept> of <duration>" when clamped), the default chapter being "the opening", with the
length in seconds to one decimal. It SHALL hold the card selection as a pure reducer over `select(chapter)`,
`clear`, `chapters(list)` (ends a selection whose chapter is absent) and `selectCut` (ends a card selection),
returning the same object when nothing changes. The model SHALL import no DOM, React, network or file module and
add no dependency.

#### Scenario: Words
- **WHEN** a 4,000 ms video card on "Dag 2" and the default chapter's 3,000 ms black card are worded
- **THEN** they read "Title card for Dag 2, 4.0 s, over video" and "Title card for the opening, 3.0 s, on black"

#### Scenario: The selection ends with its chapter
- **WHEN** "Dag 2" is selected and the chapter list no longer holds it
- **THEN** the reducer returns no selection, and returns the same state when it still does

#### Scenario: Cut and card exclude each other
- **WHEN** a card is selected and `selectCut` is applied
- **THEN** no card is selected

### Requirement: A title card's duration has limits that always hold its current place

The model SHALL give, for a title card, the lowest and highest duration its handle can take, in tenths of a second.
The lowest SHALL be 0.5 s and the highest 60 s, the engine's own bounds, mirrored as two constants that a test
compares with the engine's source. For a card over video (adding no time) the highest SHALL also be no more than the
length of the first span of its chapter's anchor clip that the render keeps (the footage the card is attached to,
`title-card`'s "Segment shorter than the card"), from the cuts it is given, cut to a whole tenth downward. The range SHALL always include the card's current value, so a limit never moves a value that was already
set. When the highest is below the lowest (the first kept span is shorter than half a second, or the chapter has no
footage), the card SHALL be reported as not adjustable, with the reason, and no value SHALL be offered. Every
function SHALL refuse a non-finite or negative input by name, and SHALL never return a value the engine would refuse.

#### Scenario: A black card
- **WHEN** limits are asked for a black card with 4.0 s
- **THEN** they are 0.5 s to 60 s

#### Scenario: A video card is bounded by its first kept span
- **WHEN** limits are asked for a video card with 3.0 s over a first kept span of 2.45 s
- **THEN** the footage allows 2.4 s, and because the current 3.0 s must stay inside the range, the range is 0.5 s to 3.0 s

#### Scenario: A clip too short to carry a card
- **WHEN** the first kept span is 0.4 s long
- **THEN** the card is reported as not adjustable, naming the footage's length, and no range is given

#### Scenario: A chapter with no footage
- **WHEN** limits are asked for a video card of a chapter with no footage (no clip, or every clip cut away)
- **THEN** the card is reported as not adjustable, saying the chapter has no footage

#### Scenario: The constants match the engine
- **WHEN** the engine's minimum or maximum card duration is changed and the web suite runs
- **THEN** the comparison test fails, naming both numbers

### Requirement: A card's length is set in tenths and snaps to whole seconds within 8 pixels

The model SHALL map an edge position to a card duration in whole tenths of a second, the nearest to the position
within the limits. It SHALL take the nearest whole second instead when that second lies within 8 screen pixels of the
position at the current zoom and within the limits; of two equally near whole seconds, the earlier. It SHALL report
whether it snapped. A result SHALL be an exact multiple of 0.1 s, written with one decimal, so no value with a float
error is ever produced. Key steps SHALL be 0.1 s, and with Shift 1 s to the nearest whole second in the direction of
the key; the lowest and highest SHALL be Home and End; a step past a limit SHALL stop at the limit, and a step at the
limit SHALL change nothing.

#### Scenario: A pointer between tenths
- **WHEN** at 40 px per second the position is 4.04 s
- **THEN** the duration is 4.0 s, and it counts as snapped to the whole second

#### Scenario: A zoomed-out view
- **WHEN** at 4 px per second the position is 4.9 s (8 px is 2 s)
- **THEN** the nearest whole second, 5 s, is within 8 px, and is taken

#### Scenario: No snap away from a whole second
- **WHEN** at 240 px per second the position is 4.46 s
- **THEN** the duration is 4.5 s, not snapped (the nearest whole second is 26 px away)

#### Scenario: A snap the limits refuse
- **WHEN** at 20 px per second the highest is 2.4 s and the position is 2.6 s (3 s is 8 px away)
- **THEN** the duration is 2.4 s and it is not reported as snapped

#### Scenario: No float error
- **WHEN** 0.1 s is added to 0.7 s, and 1 s steps run from 4.3 s
- **THEN** the results are 0.8 s exactly, and 5.0 s, then 6.0 s

#### Scenario: Keys at a limit
- **WHEN** the value is 0.5 s and a step down is asked for, then Home
- **THEN** both change nothing; End gives the highest

### Requirement: A black card's length shifts everything after it

The model SHALL give, for the title cards of an event with one card's duration changed, the timeline layout in which
every span after a black card (which adds time) starts later or earlier by the change in its duration, the total
length changed by the same, and every span before it unchanged. A video card, which adds no time, SHALL shift
nothing. A position inside content after the card keeps its clip and its time in the clip, so it SHALL be the same
moment of that content in the changed layout.

#### Scenario: A longer black card
- **WHEN** a black card of 4.0 s at the head of a three-chapter timeline is made 6.0 s
- **THEN** every span after it starts 2.0 s later, the total is 2.0 s longer, and the card's own start is unchanged

#### Scenario: A video card shifts nothing
- **WHEN** a video card is made longer (within its footage)
- **THEN** the layout is the same as before

#### Scenario: A shorter card never overlaps
- **WHEN** a black card of 6.0 s is made 0.5 s
- **THEN** the next span starts exactly where the card ends

#### Scenario: A moment keeps its content
- **WHEN** the playhead is 3.0 s into the second chapter's first clip and the card before that chapter grows by 2.0 s
- **THEN** the same moment of that clip is 2.0 s later on the timeline

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
