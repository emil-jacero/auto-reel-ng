## MODIFIED Requirements

### Requirement: Segment list from the render plan

The engine SHALL flatten a `RenderPlan` into a deterministic, fully-ordered list of segments. Each included
`ResolvedClip` SHALL produce one segment when it has no trims, and one segment per **kept span** when it has
`cut_spans` (the footage between/around the removed spans), in source-time order. Cut spans that overlap or
touch SHALL be joined as one removal before the kept spans are taken, whatever order they are listed in, so the
kept spans are disjoint and no footage appears in two segments. The flattening SHALL follow the plan's
chapter and clip order exactly and SHALL NOT consult folder structure. Each segment SHALL record which chapter
it belongs to so chapter boundaries are recoverable after flattening.

#### Scenario: Untrimmed clip yields one segment
- **WHEN** a resolved clip has no cut spans
- **THEN** the segment list contains exactly one segment referencing that clip's full duration

#### Scenario: Trimmed clip yields one segment per kept span
- **WHEN** a resolved clip has a single cut span in the middle of the clip
- **THEN** the segment list contains two segments — the footage before the cut and the footage after it — in source-time order

#### Scenario: Overlapping cut spans are one removal
- **WHEN** a 10 s clip has cut spans 1 s to 3 s and 2 s to 5 s
- **THEN** the segment list contains two segments for it, 0 s to 1 s and 5 s to 10 s, and no footage between 1 s
  and 5 s appears in any segment

#### Scenario: Touching cut spans are one removal
- **WHEN** a 10 s clip has cut spans 1 s to 3 s and 3 s to 5 s
- **THEN** the segment list contains two segments for it, 0 s to 1 s and 5 s to 10 s, and no zero-length segment

#### Scenario: A cut span inside another adds nothing
- **WHEN** a 10 s clip has cut spans 1 s to 9 s and 2 s to 3 s
- **THEN** the segment list contains two segments for it, 0 s to 1 s and 9 s to 10 s

#### Scenario: The order cut spans are listed in does not matter
- **WHEN** a 10 s clip has cut spans 5 s to 8 s, 1 s to 3 s and 2 s to 6 s, in that order
- **THEN** the segment list contains the same two segments as for the sorted list, 0 s to 1 s and 8 s to 10 s

#### Scenario: Chapter membership is preserved
- **WHEN** a plan with two chapters is flattened
- **THEN** every segment records its source chapter, and the original chapter order and per-chapter clip order are preserved in the segment list
