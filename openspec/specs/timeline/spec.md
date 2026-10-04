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
decorator is not `title`, anchored chapters SHALL be `off` (the model says `unset` when the document has no decorators at all, `off` when it lists some without `title`). A card's duration SHALL be taken in whole
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
