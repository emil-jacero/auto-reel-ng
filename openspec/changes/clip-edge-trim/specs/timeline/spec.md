## ADDED Requirements

### Requirement: A clip's edges are its leading and trailing cuts

The model SHALL treat a clip's **start edge** as the clip's kept in-point: the end of the joined removed span that
starts at the clip's start, or 0 when no such span exists; and its **end edge** as the kept out-point: the start of
the joined removed span that reaches the clip's end (ends less than 100 ms before it, or at or past it: the rule the
track and Play use), or the clip's duration when none does. Spans SHALL be joined as
the render joins them (cuts not removed, clamped to the clip, overlapping or touching ones merged), so the edges are
the same places the track lays the clip's block out by. The **edge cut** of the start edge SHALL be, among the clip's
cuts that are not removed and start at 0, the one that ends latest, the first in list order on a tie; the edge cut of
the end edge SHALL be, among the cuts that are not removed and reach the clip's end in that sense, the one that
starts earliest, the first in list order on a tie. A clip with no such cut SHALL have no edge cut on that edge. The
model SHALL refuse a clip duration that is not a finite number above zero, as its other functions do.

#### Scenario: An untrimmed clip
- **WHEN** `s1710001.mp4` (6.02 s, 50 fps) lists cuts 1.0 to 2.5 s and 4.0 to 5.0 s
- **THEN** its start edge is 0, its end edge is 6.02 s, and neither edge has an edge cut

#### Scenario: A start trim joined with a cut it touches
- **WHEN** the same clip also lists a cut 0 to 1.0 s
- **THEN** its start edge is 2.5 s (the joined span 0 to 2.5 s) and its edge cut is the cut 0 to 1.0 s

#### Scenario: A cut read past the end
- **WHEN** the clip lists a cut 5.5 to 7.0 s
- **THEN** its end edge is 5.5 s and that cut is the end edge's edge cut

#### Scenario: Two cuts at the start
- **WHEN** the clip lists a `black` cut 0 to 1.0 s and a `manual` cut 0 to 0.5 s, in that order
- **THEN** the start edge's edge cut is the `black` cut, which ends later

### Requirement: An edge moves within limits that keep three played frames

For each edge the model SHALL give the lowest and highest place it may take, on the clip's frame grid. The start
edge's lowest place SHALL be the end of the joined span that the clip's other cuts (not its edge cut, not removed)
form from the clip's start, or 0 when they form none; that place of 0 is the **start of the file**. Its highest place
SHALL be the latest frame time at which the clip still plays at least three of its frames: its duration less the
time all its cuts cover, once, with the start trimmed to that place. The end edge SHALL mirror this: its highest place
is the clip's duration (the **end of the file**) or the start of the joined span the other cuts form at the end, and
its lowest place the earliest frame time at which the clip still plays three frames. The range SHALL always hold the
edge's current place, so a clip already playing fewer than three frames keeps its edges where they are and the range
is never inverted.

#### Scenario: The start edge can trim up to three played frames
- **WHEN** `s1710001.mp4` (6.02 s, 50 fps, three frames are 60 ms) lists cuts 1.0 to 2.5 s and 4.0 to 5.0 s
- **THEN** its start edge may take places from 0 to 5.96 s, and at 5.96 s the clip plays 60 ms

#### Scenario: Another cut holds the start
- **WHEN** the clip lists a `black` cut 0 to 1.0 s and a `manual` cut 0 to 3.0 s
- **THEN** the start edge's edge cut is the `manual` cut and its lowest place is 1.0 s, not the start of the file

#### Scenario: The end edge mirrors the start
- **WHEN** the clip lists cuts 1.0 to 2.5 s and 4.0 to 5.0 s
- **THEN** its end edge may take places from 0.06 s to 6.02 s

### Requirement: An edge dragged to a place snaps, joins, and makes one edit

When an edge is moved to a wanted place, the model SHALL snap it to the nearest candidate within 8 screen pixels at
the current scale (the earlier of two equally near), else put it on the nearest frame, and then hold it to the edge's
limits, a limit being returned exactly. The candidates SHALL be the playhead when it lies in the clip, the start and
end of every interior cut of the clip that is not removed, and every whole second of the clip's own time; the caller
SHALL be able to turn snapping off, and then the place is the nearest frame held to the limits. The edge's new place
SHALL be the edge the clip would have with its edge cut set to that place: reaching or passing an interior cut's start
(start edge) or end (end edge) **joins** that cut, and the edge is at the far side of the joined span; the model
SHALL report which cuts were joined, by their number in the clip's list. The model SHALL report the change in the
clip's played length (negative when footage is removed) and the new played length.

The model SHALL give the one edit that a release at that place makes, relative to the cuts listed when the drag
began:

- the place is the start of the file (start edge) or the end of the file (end edge) and the edge has an edge cut:
  **remove** that cut
- the place equals the edge's place when the drag began: **no edit**
- the edge has no edge cut: **add** a cut from 0 to the place (start edge) or from the place to the clip's duration
  (end edge), with the reason `manual`
- otherwise: **trim** the edge cut to run from 0 to the place (start edge) or from the place to its own end as listed
  (end edge), keeping its key, its place in the list and its reason

The joined cuts SHALL NOT be changed by the edit: they stay in the list as they are, and moving the edge back un-joins
them.

#### Scenario: Trimming a start creates a manual cut
- **WHEN** at 40 px per second the start edge of `s1710001.mp4` (cuts 1.0 to 2.5 s and 4.0 to 5.0 s) is moved to
  0.5 s with no candidate within 8 px
- **THEN** the edit adds a cut 0 to 0.5 s with the reason `manual`, the change is −0.5 s and the clip plays 3.02 s

#### Scenario: Extending an approved black cut keeps its reason
- **WHEN** the clip lists a `black` cut 0 to 0.5 s and its start edge is moved to 0.8 s
- **THEN** the edit trims that cut to 0 to 0.8 s, with the reason `black` and the same key

#### Scenario: Back to the start of the file removes the cut
- **WHEN** the start edge is moved from 0.8 s to 0
- **THEN** the edit removes the edge cut, and the clip's start edge is 0

#### Scenario: Reaching an interior cut joins it
- **WHEN** the start edge is moved to 1.2 s, inside the cut 1.0 to 2.5 s (cut 1)
- **THEN** the edit adds a cut 0 to 1.2 s, the start edge is 2.5 s, cut 1 is reported as joined and is unchanged
- **WHEN** the edge is then moved back to 0.9 s
- **THEN** the edge is at 0.9 s and nothing is joined

#### Scenario: The end edge from a cut past the end
- **WHEN** the clip lists a cut 5.5 to 7.0 s and its end edge is moved to 5.0 s
- **THEN** the edit trims that cut to 5.0 to 7.0 s, keeping its end as listed

#### Scenario: A drag past the limit stops there
- **WHEN** the start edge is moved to 6.5 s
- **THEN** the edge is at 5.96 s, the clip plays three frames, and cuts 1 and 2 are reported as joined

#### Scenario: Snapping off
- **WHEN** at 40 px per second the start edge is moved to 2.96 s with the whole second 3.0 s 1.6 px away, snapping on
- **THEN** it is at 3.0 s, snapped to the whole second
- **WHEN** snapping is off
- **THEN** it is at 2.96 s, the nearest frame
