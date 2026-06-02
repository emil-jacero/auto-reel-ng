## ADDED Requirements

### Requirement: Resolve a document into a fully-explicit render plan

Given a loaded document and its event directory, the engine SHALL produce a render plan in which every chapter
and clip is fully materialized: each chapter carries an ordered, explicit list of included clips with their
resolved properties. The plan SHALL be derived from the document alone (plus clip content facts) and SHALL NOT
re-read folder structure to decide membership or order.

#### Scenario: Plan lists clips explicitly in document order
- **WHEN** a document with two chapters is resolved
- **THEN** the plan contains those chapters in document order, each with its clips in the order the document lists them

### Requirement: Deterministic ordering

Resolution SHALL be deterministic: the same document and event directory SHALL always yield the same chapter
and clip order. Order SHALL follow the explicit lists in the document; any tiebreak SHALL be defined and
total, and resolution SHALL NOT depend on map/dict iteration order.

#### Scenario: Repeated resolution is identical
- **WHEN** the same document is resolved twice
- **THEN** the two plans have identical chapter and clip ordering

### Requirement: Apply per-clip properties

Resolution SHALL apply each clip's properties from the `clips` map: `trims` as cut spans, `rotate` as an
orientation override, and `exclude` to drop a clip from the plan while leaving it in the document. Excluded
clips SHALL NOT appear in the render plan.

#### Scenario: Excluded clip is absent from the plan
- **WHEN** a clip has `exclude: true`
- **THEN** the resolved plan omits that clip but the document still records it

#### Scenario: Cut spans carried into the plan
- **WHEN** a clip has trims
- **THEN** the plan carries those cut spans for that clip so the renderer can remove them

### Requirement: Title baseline with override

Resolution SHALL mark the title clip of each chapter as the first included clip in resolved order, unless a
clip's `title` property overrides it. An explicit `title: true` SHALL designate that clip; an explicit
`title: false` SHALL prevent the baseline from selecting it.

#### Scenario: First clip is the title by default
- **WHEN** no clip in a chapter sets `title`
- **THEN** the first included clip of that chapter is marked as the title clip

#### Scenario: Explicit title override wins
- **WHEN** a non-first clip sets `title: true`
- **THEN** that clip is the chapter's title clip instead of the first

### Requirement: Look merged with server-config defaults

Resolution SHALL produce the plan's `look` by shallow-merging the document's `look` over the server-level
`config.yaml` default `look` at the top level: a top-level key present in the document SHALL win over the same
key in the defaults, and keys present only in the defaults SHALL be carried through (D-2). Both maps SHALL be
treated as opaque (their inner fields are not interpreted in v0). An absent or partial defaults map SHALL be
tolerated.

#### Scenario: Default-only key is carried through
- **WHEN** the server config defines a top-level `look` key the document omits
- **THEN** the resolved plan's `look` includes that key from the defaults

#### Scenario: Document key overrides the default
- **WHEN** both the document and the server config define the same top-level `look` key
- **THEN** the resolved plan uses the document's value for that key

#### Scenario: Absent defaults are tolerated
- **WHEN** no server-config `look` defaults are provided
- **THEN** resolution succeeds using the document's `look` as-is
