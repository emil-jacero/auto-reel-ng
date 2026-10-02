## MODIFIED Requirements

### Requirement: Trims are ordered cut ranges

A clip's `trims` SHALL be an ordered list of cut spans, each with `in` and `out` times (seconds) and an
optional `reason`. Trims denote spans to REMOVE; all footage outside the spans is kept. A clip MAY have
multiple spans, and spans MAY overlap or touch: the document SHALL accept them, SHALL keep every span as
written and in the order written, and SHALL NOT reject, merge, reorder or drop any. Overlapping or touching
spans denote ONE joined removal of everything they cover together; the footage kept is what lies outside the
union of all the spans. An editor MAY refuse to add a new span that overlaps another, but that is an editing
aid and not a rule of the document.

#### Scenario: Two cut spans on one clip
- **WHEN** a clip has trims `[{in: 0, out: 3.2, reason: black}, {in: 58.1, out: 60.0, reason: freeze}]`
- **THEN** the document parses both spans in order as removals, keeping the footage between them

#### Scenario: Overlapping cut spans are accepted as written
- **WHEN** a clip has trims `[{in: 1, out: 3}, {in: 2, out: 5}]`
- **THEN** the document parses without error and holds both spans, in that order and with those times,
  and they denote one removal from 1 s to 5 s

#### Scenario: Touching cut spans are one removal
- **WHEN** a clip has trims `[{in: 1, out: 3}, {in: 3, out: 5}]`
- **THEN** the document parses without error and holds both spans, and they denote one removal from 1 s to 5 s

#### Scenario: An invalid span is still rejected beside an overlap
- **WHEN** a clip has trims `[{in: 1, out: 3}, {in: 2, out: 2}]`
- **THEN** parsing fails with an error that names the second span, because its `out` is not greater than its `in`
