## ADDED Requirements

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
