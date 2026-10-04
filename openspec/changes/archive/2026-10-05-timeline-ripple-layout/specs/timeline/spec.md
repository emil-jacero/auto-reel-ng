## MODIFIED Requirements

### Requirement: Clips are laid out end to end from their durations and found by time

The model SHALL lay a list of clips end to end, in order, each as long as its **kept extent** ("A clip's edge cuts
set its kept extent"), which is its own duration when it has no leading and no trailing cut, and SHALL report each
clip's start and the total length in milliseconds. A clip whose kept extent is empty SHALL take no length: the clip
after it starts where the clip before it ends. It SHALL map a time to the clip that holds it: a time before zero to
the first clip, a time at or past the total to the last clip, and a time that is exactly a boundary to the later
clip, never to a clip of no length. An empty list SHALL have a total length of zero and no clip at any time. It SHALL
convert between time and pixels at a given scale, rounding a pixel position back to a whole millisecond, and SHALL
NOT clamp a position to the timeline on its own.

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

#### Scenario: Edge cuts shorten the layout
- **WHEN** clips of 10,000 ms (a cut from 0 to 2,000 ms), 8,000 ms (a cut from 6,000 to 8,000 ms) and 5,000 ms (a cut
  from 1,000 to 2,000 ms) are laid out
- **THEN** their starts are 0, 8,000 and 14,000 ms and the total is 19,000 ms

#### Scenario: A wholly cut clip takes no length
- **WHEN** three clips of 4,000 ms are laid out and the second has a cut from 0 to 4,000 ms
- **THEN** the starts are 0, 4,000 and 4,000 ms, the total is 8,000 ms, and the time 4,000 ms is held by the third clip

## ADDED Requirements

### Requirement: A clip's edge cuts set its kept extent

The model SHALL derive each clip's **kept extent**, a range `[in, out)` of the clip's own time in whole
milliseconds, from its cut spans as the render joins them (not removed, clamped to the clip, sorted, overlapping or
touching ones merged): `in` SHALL be the end of the joined span that starts at the clip's beginning (a **leading
cut**), else 0; `out` SHALL be the start of the joined span that runs to the clip's end or ends less than 100 ms
before it (a **trailing cut**, the 0.1 s by which Play ends a clip at a cut), else the clip's duration. A span that
is both SHALL leave the extent empty. The other spans are **interior cuts**; the model SHALL give the view only
those to draw, each relative to `in`, and SHALL say which of a clip's listed cuts lie within a leading or trailing
cut (they have no handle).

A time in a clip SHALL map to the layout as the clip's start plus the time less `in`, and a layout time back to a
clip and a time in it as the inverse; the two SHALL be inverses on every kept time. A layout time mapped to a
playhead position SHALL be the nearest frame of the clip's own rate held to its kept frames: the **first kept
frame** is the first frame at or after `in`, the **last kept frame** the last frame before `out`. A clip whose extent
holds no frame SHALL have no position: a lookup and a frame step pass over it to the next clip that has one. A frame
step SHALL move between kept frames and cross a boundary from one clip's last kept frame to the next clip's first,
skipping none. A position whose time is no longer kept SHALL be held to the nearest kept frame of its clip. The
filmstrip tile at `x` pixels into a clip's block SHALL be the sprite's tile for the clip's time `in + x / scale`. A
title card SHALL anchor at the anchor clip's first kept time, which is the left edge of its block on the track; the
black cards' map SHALL take the layout's times so that a card adds its length before that edge.

#### Scenario: Extents from edge cuts
- **WHEN** a 10,000 ms clip has cuts from 0 to 2,000 ms and from 1,500 to 3,000 ms, and another 10,000 ms clip has a
  cut from 9,950 to 10,000 ms and one from 4,000 to 5,000 ms
- **THEN** the first clip's extent is 3,000 to 10,000 ms with no interior cut and both its listed cuts within its
  leading cut; the second's is 0 to 9,950 ms with one interior cut, drawn from 4,000 to 5,000 ms of the clip

#### Scenario: A cut ending just short of the end is a trailing cut
- **WHEN** a 6,020 ms clip has a cut from 5,000 to 5,950 ms, and another 6,020 ms clip a cut from 5,000 to 7,000 ms
- **THEN** both extents are 0 to 5,000 ms

#### Scenario: Round trip through the extent
- **WHEN** the clips of "Edge cuts shorten the layout" are laid out and every kept time of each clip is mapped to the
  layout and back
- **THEN** each returns itself, and the first clip's time 5,000 ms is the layout time 3,000 ms

#### Scenario: Positions are held to kept frames
- **WHEN** in that layout at 25 fps the layout times -5, 13,975 and 19,500 ms are mapped to positions
- **THEN** they are the first clip at 2,000 ms, the second clip at 5,960 ms and the third clip at 4,960 ms

#### Scenario: Steps cross the edges
- **WHEN** a position at the second clip's 5,960 ms is stepped by +1 frame, and one at its 0 ms by -1 frame
- **THEN** the results are the third clip at 0 ms and the first clip at 9,960 ms

#### Scenario: A few frames kept
- **WHEN** a 10,000 ms, 25 fps clip has cuts from 0 to 4,000 ms and from 4,120 to 10,000 ms
- **THEN** its extent is 120 ms long, and its kept frames are 4,000, 4,040 and 4,080 ms

#### Scenario: A clip with no kept frame is passed over
- **WHEN** of three 25 fps clips the second has an extent from 1,001 to 1,030 ms, which holds no frame
- **THEN** a frame step from the first clip's last kept frame lands on the third clip's first kept frame

#### Scenario: The filmstrip starts at the kept start
- **WHEN** a clip with a sprite of one tile a second and an extent from 2,000 ms is drawn at 40 px per second with
  96 px places
- **THEN** the place at 0 px shows tile 2 and the place at 96 px tile 4

#### Scenario: A card at a trimmed clip
- **WHEN** a black card of 3,000 ms anchors at a clip whose extent starts at 2,000 ms and that clip starts at layout
  time 8,000 ms
- **THEN** the card spans track times 8,000 to 11,000 ms, the clip's block starts at 11,000 ms, and the clip's time
  2,000 ms is track time 11,000 ms
