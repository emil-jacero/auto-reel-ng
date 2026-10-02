## ADDED Requirements

### Requirement: An editorial write that changes nothing leaves reel.yaml untouched
When the event already has a `reel.yaml` and the desired state, merged onto it and validated, yields the
same document the file already holds, the operation SHALL return that document without writing. "The same
document" means the document the writer would emit for the merged state is identical, comments and key
order included, to the one it would emit for the loaded file. The file's bytes, its modification time and
its directory entry MUST be left as they were, and no temporary file may be created. This holds whatever
indentation the file was authored in: a file written in a style other than the engine's canonical one
(2-space mappings, 4-space sequences, offset 2) stays exactly as authored when a save changes nothing.

Validation (schema, cross-references, the event rule on date and title) SHALL still run first, so a state
that would be refused is refused whether or not it differs from the file. An event without a `reel.yaml`
SHALL always be written, even for an empty desired state. A save that changes anything SHALL write the
whole document in the canonical style, as it does today; keeping a foreign style through a real change is
not required.

A version-less (auto-reel legacy) `reel.yaml` that a save leaves unchanged SHALL stay as it is; it is
converted to `version: 0` by a save that changes something, or by `auto-reel import`.

The returned document, and the editorial-read `ETag` computed from it, SHALL be the same whether or not a
write happened.

#### Scenario: A foreign-indented file survives an unmodified save
- **WHEN** the event `2024/2024-06-21 - Midsommar` has a hand-authored `reel.yaml` with 4-space mappings, an
  un-indented `-   name: ''` chapter sequence and `title: Midsommar   # keep`, and its current state is
  applied unmodified
- **THEN** `reel.yaml` is byte-for-byte unchanged, its modification time is unchanged, and no hidden
  temporary file was created in the event folder

#### Scenario: PUT of the document just read changes nothing on disk
- **WHEN** a client reads `GET /api/v1/events/{event_id}/reel` for that foreign-indented event and PUTs the
  body back with `If-Match` set to the `ETag` it received
- **THEN** the response is 200 echoing the same document with the same `ETag`, and `reel.yaml` is
  byte-for-byte unchanged

#### Scenario: A real change to a foreign-indented file is written in the canonical style
- **WHEN** the same event receives a desired state that changes only the title
- **THEN** the persisted file carries the new title and is written in the canonical style, with every
  comment and the key order kept

#### Scenario: An invalid unmodified-looking state is still refused
- **WHEN** a desired state equal to the file's content except that a chapter references a clip the document
  does not define is applied
- **THEN** the operation fails loudly naming the problem, as before, and the file is unchanged

#### Scenario: An empty state for an event with no reel.yaml still creates one
- **WHEN** the event `2024/2024-06-21 - Trip`, which has no `reel.yaml`, receives an empty desired state
- **THEN** a `reel.yaml` declaring `version: 0` is written

#### Scenario: An unmodified save leaves a legacy file alone
- **WHEN** an event's `reel.yaml` is in the auto-reel legacy format (no `version` key, a top-level
  `title`) and its current state is applied unmodified
- **THEN** the file is byte-for-byte unchanged, and a later save that changes the title writes it as
  `version: 0`

### Requirement: A changed cut list edits only the spans that differ
When a clip's desired `trims` differ from those on disk, the operation SHALL change only the spans that
differ and leave every other span exactly as authored. Spans are compared by value: `in` and `out` as
numbers (so an integer `0` and a float `0.0` are equal), and `reason`.

- **A span whose value is unchanged SHALL keep its form.** Its flow or block style, the spelling of its
  numbers (`in: 0` stays `in: 0`, never `0.0`), its end-of-line comment at its column, and the own-line
  comments and blank lines directly above it are persisted as they were, wherever the span lands in the
  list.
- **A span that is edited SHALL be edited in place.** A desired span is matched to the existing span of
  equal value, else one with the same `in`, else one with the same `out`, else the next one left, so a
  span with one bound changed is the same span. Only the keys whose value differs are rewritten (a
  key whose value is numerically equal keeps its stored spelling); a `reason` that is added, changed or
  removed changes only that key. The span keeps its style and its comments.
- **A removed span SHALL take only its own comments with it**, and no other span's comment is lost.
- **An added span SHALL carry no comment** and is written with `in`, `out` and, when set, `reason`, in the
  style of the span before it: a flow mapping after a flow-style span, a block mapping after a block one.
- **Comment lines after the last span SHALL stay at the end of the list.**
- **A list that is unchanged by value SHALL be persisted exactly as it was.**

Changing a clip's other properties (`title`, `rotate`, `exclude`) leaves its `trims` untouched. The
operation leaves overlapping or adjacent spans exactly as given: whether cuts overlap is the renderer's
concern, not the writer's, and the engine continues to treat overlapping cuts as their union. A span that
moves takes its comments with it.

None of this changes the editorial state a write persists, so it never moves the event's staleness verdict
or its editorial-read `ETag`.

#### Scenario: Editing one span leaves the others as authored
- **WHEN** a clip `00400.mp4` has `trims:` holding `- {in: 0, out: 3.2, reason: black}  # black start` and
  `- {in: 10, out: 12}  # shake`, and a desired state changes only the second span's `out` to 13
- **THEN** the first span line is persisted byte-for-byte as written, flow style and `# black start`
  included, and the second span keeps its flow style and `# shake` with `out` now 13

#### Scenario: An API float does not respell an unchanged number
- **WHEN** the same clip receives its trims over the API as JSON, so `in` arrives as `0.0` and `10.0`, with
  only the second span's `out` changed
- **THEN** the first span still reads `in: 0` in the persisted file, and the second reads `in: 10`

#### Scenario: Removing a middle span drops only its comment
- **WHEN** a clip has three commented spans `# first`, `# second`, `# third` and a desired state removes the
  second
- **THEN** the persisted list holds the first and third spans, each with its own comment, and `# second` is
  gone

#### Scenario: A moved span takes its comments with it
- **WHEN** a desired state swaps the first and third of three commented spans
- **THEN** each span is persisted with its own end-of-line comment and the own-line comments that were above
  it, at its new position

#### Scenario: Removing one span while editing another edits the right one
- **WHEN** a clip has three commented block-style spans and a desired state removes the second and changes
  the third span's `out`
- **THEN** the first span is persisted as written, the third span carries the new `out` and its own
  comment, and the second span and its comments are gone

#### Scenario: Adding a span leaves the existing ones untouched
- **WHEN** a desired state appends a third span `{in: 20, out: 22, reason: manual}` to a clip with two
  commented flow-style spans
- **THEN** the two existing span lines are persisted unchanged, and the new span is a flow mapping, like
  the spans before it, with no comment

#### Scenario: Changing another property leaves the trims alone
- **WHEN** a desired state changes only a clip's `title` while its flow-style commented trims are
  unchanged
- **THEN** the trims lines are persisted byte-for-byte as written

#### Scenario: A reason added to one span touches only that span
- **WHEN** a desired state adds `reason: manual` to the second of two spans and changes nothing else
- **THEN** only the second span's mapping changes, and the first span's line and comment are unchanged

#### Scenario: Overlapping spans are written as given
- **WHEN** a desired state lists the spans `{in: 5, out: 9}` and `{in: 7, out: 12}` on one clip
- **THEN** both are persisted unchanged and nothing is merged, split or refused at write time

### Requirement: Writing reel.yaml sweeps abandoned temporaries
After `reel.yaml` has been replaced successfully, the writer SHALL remove from the same folder the hidden
temporary files an earlier write left behind: regular files, not symbolic links, named exactly
`.reel.yaml.<32 lowercase hex digits>.tmp`, whose modification time is more than 24 hours old. It MUST
NOT remove a younger one (a concurrent write in progress) or any file with another name, including other
hidden `.reel.yaml.*` files. Removing one is housekeeping: a failure to list, inspect or remove SHALL NOT
fail or undo the write that already succeeded.

A write that fails or is refused SHALL NOT sweep. A save that changes nothing writes nothing and so does
not sweep. The rule applies to every write of a `reel.yaml` through the writer, the API's and the
`auto-reel import` command's alike.

#### Scenario: A day-old temporary left by a killed write is removed
- **WHEN** the event folder holds `.reel.yaml.0123456789abcdef0123456789abcdef.tmp` last modified two days
  ago, and a save that changes the title succeeds
- **THEN** that file is gone afterwards and `reel.yaml` holds the new title

#### Scenario: A young temporary is left alone
- **WHEN** the folder holds `.reel.yaml.fedcba9876543210fedcba9876543210.tmp` modified a minute ago and a
  save succeeds
- **THEN** that file is still there

#### Scenario: Other hidden files are never touched
- **WHEN** the folder holds a three-day-old `.reel.yaml.bak`, `.reel.yaml.1234.tmp` and
  `.other.0123456789abcdef0123456789abcdef.tmp`, and a save succeeds
- **THEN** all three are still there

#### Scenario: A refused write sweeps nothing
- **WHEN** a save on an event whose folder is mounted read-only is refused, and an old temporary sits in it
- **THEN** the operation raises naming the read-only error, and the old temporary is still there

#### Scenario: A sweep that cannot remove a file does not fail the save
- **WHEN** a save succeeds but the old temporary cannot be removed (the folder forbids the removal)
- **THEN** the save is reported successful, and the new `reel.yaml` is in place
