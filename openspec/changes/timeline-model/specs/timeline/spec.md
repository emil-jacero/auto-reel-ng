## ADDED Requirements

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
SHALL be drawn up to the end, and a cut wholly past the end or empty SHALL have none. Each listed cut that is
not removed SHALL have an ordinal from 1, in order of start (a tie by end, then by position in the list), so
that no two cuts of one clip share an ordinal; a removed cut SHALL have none.

#### Scenario: Overlapping cuts read from reel.yaml
- **WHEN** a 10 s clip lists cuts 1 to 3 s and 2 to 4 s
- **THEN** its spans are one span of 1 to 4 s and it contributes 7 s to the movie length, but it has two rectangles

#### Scenario: A cut past the end
- **WHEN** a 6.08 s clip lists a cut of 5 to 7 s
- **THEN** its rectangle runs from 5 s to 6.08 s

#### Scenario: Two cuts do not share a name
- **WHEN** a clip lists cuts at 14 to 17.2 s and 0 to 2.4 s, in that order in the file
- **THEN** the cut at 0 s has ordinal 1 and the one at 14 s has ordinal 2, and a removed cut among them has none

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
