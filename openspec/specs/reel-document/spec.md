# reel-document Specification

## Purpose

Establish `reel.yaml` as the authoritative, durable, GUI-editable record of every editorial decision for an event: define a versioned (`version: 0`) document with `metadata`, `look`, `chapters` (structure as ordered clip references), `clips` (a flat map of per-clip properties keyed by identity), and `ignore`. Provide a fail-loud parse → typed model → round-trip write that preserves comments and key order, keeps editorial structure separate from per-clip properties, identifies clips by their event-relative path, treats trims as ordered cut ranges, and imports the legacy auto-reel format into v0.

## Requirements

### Requirement: Versioned reel.yaml v0 schema

A `reel.yaml` document SHALL carry a `version` field, and this change SHALL define version `0`. A v0 document
SHALL support:

- `metadata` (title, date, location, description)
- `look` (render/title-card settings)
- `chapters` (ordered structure)
- `clips` (per-clip property map)
- `ignore` (dismissed file paths)
- an optional `sort` rule for its event

A loaded document with no `version` key SHALL be treated as the auto-reel legacy format and routed to import
(see the `reel-document` import requirement), and every document the writer produces SHALL include
`version: 0`.

`sort` SHALL be a mapping with:

- an optional `method`: `datetime`, `filename` or `custom`
- an optional boolean `reverse`
- for `custom`, a `custom_order` mapping from clip file names to integer positions

A `sort` with an unknown method, a wrong-typed field, or a `custom_order` given without `custom` SHALL fail
loud, naming the field.

#### Scenario: Document declares version 0
- **WHEN** the writer serializes a document
- **THEN** the output contains `version: 0`

#### Scenario: Missing version routes to legacy import
- **WHEN** a `reel.yaml` is loaded that has no `version` key
- **THEN** it is handled as the auto-reel legacy format rather than parsed as v0

#### Scenario: A document carries its event's sort rule
- **WHEN** a v0 document sets `sort: {method: filename, reverse: true}`
- **THEN** it loads with that rule, and writing it back preserves the `sort` block

#### Scenario: A malformed sort fails loud
- **WHEN** a v0 document sets `sort: {method: shuffle}` or `sort: {custom_order: {a.mp4: 1}}` without
  `method: custom`
- **THEN** loading raises a parse error naming the `sort` field

### Requirement: `look` is carried opaquely in v0

The v0 loader SHALL parse, preserve, and round-trip the `look` section as an opaque map without validating or
interpreting its internal fields. The structured `look`/title-card schema is defined by a later change; v0
SHALL NOT reject a `look` map on the basis of the names or values of its inner keys.

The one constraint on `look` is the type of its keys: every mapping key anywhere inside it, at any depth and
including a mapping inside a list, SHALL be a string. A non-string key (an unquoted `2024-01-01`, which YAML
reads as a date, or `1`) cannot be hashed or serialized, so such a `look` SHALL fail loud with the parse
error, naming the location of the key (`look.<path>`) and its type. A `look` imported from a legacy
`title_card` is held to the same rule.

#### Scenario: Unknown look fields are preserved, not rejected
- **WHEN** a document's `look` contains fields v0 does not model
- **THEN** loading succeeds and the writer round-trips the `look` map unchanged

#### Scenario: A date used as a look key is rejected
- **WHEN** a v0 document sets `look:` with the unquoted key `2024-01-01: x`
- **THEN** loading fails with the parse error naming `look` and the key `2024-01-01` as a date rather than
  a string, and no other kind of error is raised

#### Scenario: A mixed-type key set is rejected
- **WHEN** a v0 document sets `look: {1: a, b: c}`
- **THEN** loading fails with the parse error naming `look` and the key `1` as an integer

#### Scenario: A non-string key nested in a list is rejected
- **WHEN** a v0 document sets `look: {layers: [{1: x}]}`
- **THEN** loading fails with the parse error naming `look.layers[0]` and the key `1`

#### Scenario: A quoted key is a string
- **WHEN** a v0 document sets `look: {'2024-01-01': x}` in quotes
- **THEN** it loads and the writer round-trips the `look` map unchanged

#### Scenario: A legacy title_card with a non-string key is rejected
- **WHEN** a legacy document's `title_card` holds `{1: a}`
- **THEN** import fails with the same parse error rather than producing a document that cannot be hashed

### Requirement: Structure and properties are normalized apart

The schema SHALL keep editorial structure separate from per-clip properties. `chapters` SHALL be an ordered
list of chapters, each with a name and an ordered list of clip references (identities only). `clips` SHALL be
a map keyed by clip identity whose values hold per-clip properties (`trims`, `title`, `rotate`, `exclude`). A
clip reference in `chapters` and its property entry in `clips` SHALL share the same identity key.

#### Scenario: Chapter holds references, not properties
- **WHEN** a chapter lists a clip
- **THEN** the chapter entry is the clip's identity reference and any trims/title/exclude for that clip live in the `clips` map under the same identity

#### Scenario: Properties survive a reorder
- **WHEN** a clip's position is changed within or across chapters but its `clips` entry is untouched
- **THEN** its trims and other properties remain associated with it unchanged

### Requirement: Clip identity is the event-relative path

A clip SHALL be identified by its path relative to the event root (e.g. `Reception/00400.mp4`). Identities
SHALL be unique within an event document, and the schema SHALL reject a document in which two clip references
resolve to the same identity in a way that is ambiguous.

#### Scenario: Same basename in different subdirs are distinct
- **WHEN** `Reception/00400.mp4` and `Speeches/00400.mp4` both appear
- **THEN** they are treated as two distinct clip identities

### Requirement: Trims are ordered cut ranges

A clip's `trims` SHALL be an ordered list of cut spans, each with `in` and `out` times (seconds) and an
optional `reason`. Trims denote spans to REMOVE; all footage outside the spans is kept. A clip MAY have
multiple spans, and spans MAY overlap or touch: the document SHALL accept them, SHALL keep every span as
written and in the order written, and SHALL NOT reject, merge, reorder or drop a valid span because it
overlaps or touches another. Overlapping or touching spans denote ONE joined removal of everything they
cover together; the footage kept is what lies outside the union of all the spans. An editor MAY refuse to
add a new span that overlaps another, but that is an editing aid and not a rule of the document.

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

### Requirement: Fail-loud parse and validation

Parsing SHALL fail loudly with a clear error on malformed or invalid content and SHALL NOT fabricate or
silently drop data. Validation SHALL reject (at least) an unknown `version`, a trim with `out <= in`, a
negative or non-finite time, and a `chapters` clip reference whose identity is absent from required
structure. Errors SHALL identify the offending location.

`version` SHALL be the integer `0`. A value that merely compares equal to it (the boolean `false`, the float
`0.0`) is an unknown version, as are the string `'0'` and a missing value (`version:` with nothing after it),
and each fails with the unsupported-version error. A trim time SHALL be a finite number: `.nan`, `.inf` and
`-inf` are rejected, naming the span's `in` or `out`.

The reference-integrity checks are **disk-independent** — a referenced clip merely absent from disk is a
*reconcile* MISSING (see `event-reconcile`), not a parse error. Internally the validator SHALL reject: a clip
identity referenced more than once across all chapters (a duplicate/ambiguous reference); a `clips` property
entry keyed by an identity no chapter references (a dangling property record with nothing to attach to); an
`ignore` entry whose identity is also referenced in a chapter (a structure/ignore contradiction); and an
`ignore` list that names the same identity more than once (a duplicate, which has no meaning and is judged
by the identity after normalization, so `./x.mp4` repeats `x.mp4`), by the same rule as a duplicate chapter
reference.

Every string in a document, a key or a value at any depth and in `look` as in the rest, SHALL be text that
can be encoded as UTF-8. A string holding a lone surrogate (the double-quoted escape `"\ud800"` yields one)
SHALL fail loud, in a v0 document and in a legacy one, with the parse error naming the location of the
string (`metadata.title`, `look.font`, or the key's own path). The message SHALL show the string only
escaped, so reporting it does not itself fail. A document that a writer builds is checked the same way
before it is written, so no write produces a `reel.yaml` this requirement would refuse to load.

Content that cannot be read as YAML text SHALL fail the same way. This covers:

- **An impossible typed value.** YAML reads an unquoted scalar such as `2024-02-30`, `2024-13-45` or
  `2024-02-29T25:00:00` as a date or a timestamp, and that date or time does not exist. The same holds for a
  value whose explicit tag it cannot satisfy, such as `!!int abc`, `!!bool maybe`, or `!!int` with no value.
  This SHALL fail in a v0 document and in a legacy one, wherever in the document the value appears, `look`
  included. The error SHALL name the file, the value as written, and its line. It SHALL call the value
  invalid and SHALL NOT call the YAML malformed: the text is well-formed.
- **Any other text the YAML reader cannot load.** An example is a double-quoted escape that names no
  Unicode character (`"\UFFFFFFFF"`). When the reader reports no position, the error SHALL name the file
  and the reader's reason.
- **Bytes that are not UTF-8 text.** The error SHALL name the file, state that it is not UTF-8 text, and give
  the offset of the first byte that cannot be decoded.

Every failure to load or validate a document's content, and every failure to read its file, SHALL be raised
as the single parse error this requirement defines, never as another kind of error. Every caller that reports
an unparseable `reel.yaml` for one event therefore reports these the same way:

- the CLI's `ERROR <event>: <reason>` line
- the events list's error row with the unparseable-`reel.yaml` failure kind
- the event detail's 502 problem body

A value is never coerced, clamped or dropped to make a document load.

Whether a document exists at all SHALL be answered by the disk, not guessed. A `reel.yaml` is absent only
when the disk says there is no such file, including when the event path is not a directory. When the disk
cannot say, because the event folder denies the search permission needed to look the file up, the document
is neither absent nor present. That failure SHALL be raised as the operating-system error for the folder (a
permission error). It SHALL NOT be read as "no document", so no caller seeds a document from the folder name
or reports the event's clips as new over a `reel.yaml` it was not allowed to look for. It SHALL NOT be the
single parse error either: that error is for a file that exists and cannot be loaded or read, and the events
list reports the two differently (`unreadable_disk` for the folder, `unparseable_reel_yaml` for the file).

#### Scenario: Invalid trim is rejected
- **WHEN** a document contains a trim with `out` less than or equal to `in`
- **THEN** loading fails with an error naming the clip and the invalid span

#### Scenario: Unknown version is rejected
- **WHEN** a document declares a `version` this engine does not support
- **THEN** loading fails with a clear unsupported-version error rather than a best-effort parse

#### Scenario: Dangling clip property entry is rejected
- **WHEN** the `clips` map holds a property entry keyed by an identity that no chapter references
- **THEN** loading fails with an error naming the dangling identity rather than silently keeping an orphaned record

#### Scenario: Duplicate clip reference is rejected
- **WHEN** the same clip identity is referenced more than once across the document's chapters
- **THEN** loading fails with an error naming the duplicated identity

#### Scenario: An impossible date is a parse error naming the value and its line
- **WHEN** the `reel.yaml` of `2024/2024-07-04 - Barbecue` reads `version: 0`, then `metadata:`, then
  `title: Barbecue`, then `date: 2024-02-30` on line 4
- **THEN** loading fails with the parse error, whose message names that `reel.yaml`, the value `2024-02-30`
  and line 4 as an invalid value rather than as malformed YAML, and no other kind of error is raised

#### Scenario: An impossible date in a legacy document fails the same way
- **WHEN** a `reel.yaml` with no `version` key has `metadata:` with `date: 2024-13-45`
- **THEN** loading fails with the same parse error naming `2024-13-45` and its line, before any legacy import
  is attempted

#### Scenario: An impossible timestamp inside look fails loud
- **WHEN** a v0 document's opaque `look` map holds `generated: 2024-02-29T25:00:00`
- **THEN** loading fails with the parse error naming that value and its line, although `look` is otherwise
  not validated

#### Scenario: A value its explicit tag cannot hold fails loud
- **WHEN** a v0 document's `look` map holds `shadow: !!bool maybe`, or `size: !!int` with no value
- **THEN** loading fails with the parse error naming the file, the value as written (`maybe`, or the empty
  value), and its line, and no other kind of error is raised

#### Scenario: An escape that names no character is a parse error
- **WHEN** a v0 document sets `title: "Fest \UFFFFFFFF"`, a double-quoted escape beyond the last Unicode
  code point
- **THEN** loading fails with the parse error naming the file and the reader's reason, and no other kind
  of error is raised

#### Scenario: A real leap day and a quoted impossible date behave as before
- **WHEN** a v0 document sets `date: 2024-02-29`, or sets `date: '2024-02-30'` in quotes
- **THEN** the first loads with the date 29 February 2024, and the second fails with the existing error
  naming `metadata.date` as an invalid date

#### Scenario: A reel.yaml saved as Latin-1 is a parse error
- **WHEN** an event's `reel.yaml` holds the title `Kräftskiva` encoded as Latin-1, so its bytes are not
  valid UTF-8
- **THEN** loading fails with the parse error, whose message names that `reel.yaml`, says it is not UTF-8
  text, and gives the offset of the first bad byte

#### Scenario: One impossible date costs one event
- **WHEN** a project holds `2024-06-21 - Midsommar`, `2024-07-04 - Barbecue` and `2024-08-01 - Kräftskiva`,
  and only Barbecue's `reel.yaml` sets `date: 2024-02-30`
- **THEN** `auto-reel scan` prints one `ERROR  2024-07-04 - Barbecue:` line naming `2024-02-30`, lists the
  other two events and exits non-zero. The events list answers 200 with two summaries and one error row for
  Barbecue, whose failure kind is `unparseable_reel_yaml`.

#### Scenario: A non-finite trim time is rejected
- **WHEN** a clip's trims hold `{in: .nan, out: 5}`, `{in: 1, out: .inf}` or `{in: 0, out: .nan}`
- **THEN** loading fails with the parse error naming the clip and the span's `in` or `out` as not finite,
  rather than loading a span that no comparison can order

#### Scenario: A version that only equals zero is rejected
- **WHEN** a document sets `version: false`, `version: 0.0`, `version: '0'` or `version:` with no value
- **THEN** loading fails with the unsupported-version error, and `version: 0` still loads

#### Scenario: A duplicate ignore entry is rejected
- **WHEN** a document sets `ignore: [x.mp4, y.mp4, x.mp4]`, or `ignore: [x.mp4, ./x.mp4]`
- **THEN** loading fails with the parse error naming the duplicated identity `x.mp4` and the position of its
  second appearance

#### Scenario: An editorial write that duplicates an ignore entry writes nothing
- **WHEN** an editorial write submits the `ignore` list `[x.mp4, x.mp4]` for an event whose `reel.yaml`
  ignores `x.mp4` once
- **THEN** the write fails with the parse error and the file on disk is unchanged

#### Scenario: A lone surrogate in a value is rejected
- **WHEN** a v0 document sets `title: "Fest \ud800"`
- **THEN** loading fails with the parse error naming `metadata.title`, and the message can itself be printed
  and encoded as UTF-8

#### Scenario: A lone surrogate in look is rejected
- **WHEN** a v0 document's `look` holds the value `"x\ud800"` under `font`, or a key `"a\ud800"`
- **THEN** loading fails with the parse error naming `look.font`, or the location of that key

#### Scenario: A lone surrogate in a legacy document is rejected
- **WHEN** a legacy document with no `version` key sets `title: "x\ud800"`
- **THEN** loading fails with the same parse error, before any import is attempted

#### Scenario: An editorial write of a lone surrogate writes nothing
- **WHEN** an editorial write submits the title `"Fest \ud800"`
- **THEN** the write fails with the parse error and the file on disk is unchanged

#### Scenario: A character beyond U+FFFF still loads
- **WHEN** a v0 document sets `title: "Fest \U0001F386"`
- **THEN** it loads, because a character beyond U+FFFF is a real character and not a lone surrogate

#### Scenario: A reel.yaml in a folder that cannot be searched is not absent
- **WHEN** event folder `2024-06-21 - Fest` has mode `0600` (listable, not searchable) and holds a `reel.yaml`
  titled `Real` and a clip, and its document is loaded
- **THEN** loading raises a permission error naming the path, and it neither returns a document seeded
  with the title `Fest` nor ignores the `reel.yaml`

#### Scenario: A reel.yaml that exists but cannot be read stays a parse error
- **WHEN** event folder `2024-06-21 - Fest` is searchable and holds a `reel.yaml` with mode `0000`
- **THEN** loading fails with the parse error naming that `reel.yaml` as unreadable, not with a permission
  error for the folder

#### Scenario: A missing reel.yaml is still absent
- **WHEN** event folder `2024-06-21 - Fest` is searchable and holds clips but no `reel.yaml`
- **THEN** loading seeds a document from the folder, and no error is raised

### Requirement: Round-trip preserving writer

The writer SHALL serialize a document such that loading and re-writing an unmodified document preserves its
comments and key order (round-trip stable). Machine writes SHALL NOT reorder keys or strip comments on
otherwise-unchanged content.

The byte-stable guarantee holds for documents written in the engine's canonical block style (2-space mappings,
4-space sequences, offset 2); the underlying round-trip YAML library cannot reproduce arbitrary foreign
indentation, so the schema is constrained to that style (see the design's Risks). Comment/key-order
preservation also extends to documents mutated by reconcile apply-operations — only the changed lines differ.

#### Scenario: Unchanged document round-trips byte-stable
- **WHEN** a hand-authored `reel.yaml` with comments is loaded and written back without edits
- **THEN** the output is byte-for-byte equivalent, including comments and key order

### Requirement: Import of auto-reel legacy format

The engine SHALL import an auto-reel-format document (`metadata`, top-level `title`/`description`, `sort`,
`title_card`) into a v0 document. Mappable fields SHALL be translated:

- `metadata` → `metadata`
- `title_card` → `look`
- `sort` (`method`, `reverse`, `custom_order`) → the v0 `sort`, so it takes effect when the event's clips
  first enter the document

Anything that cannot be faithfully mapped SHALL be reported, not silently discarded; import SHALL never
produce a partial document without surfacing what was dropped.

A legacy top-level `title` is auto-reel's full movie-name stem. When it has the form `YYYY-MM-DD - <rest>`
with a real date, and the legacy document either gives no date or gives that same date, the import SHALL
set `metadata.title` to `<rest>`. When no date was given, it SHALL set `metadata.date` from the prefix. Any
other title SHALL be imported verbatim.

#### Scenario: Legacy metadata and title_card are mapped
- **WHEN** a legacy document with `metadata` and `title_card` is imported
- **THEN** the result is a `version: 0` document whose `metadata` and `look` carry the translated values

#### Scenario: Unmappable field is reported
- **WHEN** a legacy field cannot be represented in v0
- **THEN** the importer reports it explicitly rather than dropping it silently

#### Scenario: A dated legacy title does not double the date
- **WHEN** a legacy document with `title: "2025-01-13 - Resa till Gran Canaria"` and no `metadata.date` is
  imported
- **THEN** the result has title `Resa till Gran Canaria` and date `2025-01-13`, so its output name is
  `2025/2025-01-13 - Resa till Gran Canaria.mp4`

#### Scenario: A title whose date disagrees is kept as written
- **WHEN** a legacy document has `title: "2025-01-13 - Resa"` and `metadata.date: 2025-01-14`
- **THEN** the title is imported verbatim, and the date is `2025-01-14`

#### Scenario: Legacy sort is carried
- **WHEN** a legacy document has `sort: {method: custom, custom_order: {b.mp4: 1, a.mp4: 2}, reverse: false}`
- **THEN** the v0 document's `sort` is that rule, and nothing about `sort` is reported as unmapped

#### Scenario: An unknown legacy sort method is reported
- **WHEN** a legacy document has `sort: {method: random}`
- **THEN** the import reports `sort.method` as unmapped, and the v0 document carries no `sort`

### Requirement: Load errors name the real source and how far reading got

Every message the parse error carries for a document that cannot be loaded SHALL name the source it was read
from (the `reel.yaml` path, or the caller's stated source for text not read from a file). It SHALL NOT name
the YAML reader's internal stand-in for a string stream (`<unicode string>`): where the reader's excerpt
says which stream a line and column belong to (`in "...", line 2, column 8`), that name SHALL be the
document's own source. The excerpt's line, column and reason are otherwise unchanged. This holds for every
YAML syntax or structure error the reader reports with a position, including a repeated key.

A failure the reader reports with no position of its own SHALL, when the reader had already produced
tokens before it failed, also state the line it got as far as: a line number that is a lower bound on where
the failure is, not a claim of the exact line. When the failure happens after the whole text was read
(a document nested deeper than the engine can load), there is no such line and the message SHALL name the
source and the reason only. A document nested too deeply to load SHALL be reported as such, with the
underlying reason kept, and SHALL NOT be reported only as the bare recursion-limit message.

None of this changes which documents load or which kind of error is raised: it remains the single parse
error, and a message is never made to look as if it located something it did not.

#### Scenario: A syntax error names the document, not the stand-in
- **WHEN** the `reel.yaml` of `2024/2024-07-04 - Barbecue` reads `version: 0`, then `title: "\x"` on line 2
- **THEN** loading fails with the parse error whose message holds that `reel.yaml`'s path in the reader's
  excerpt for line 2 (in place of `<unicode string>`), still shows line 2 and the reader's reason, and does
  not contain `<unicode string>`

#### Scenario: A structure error with a position is renamed the same way
- **WHEN** a v0 document defines the same top-level key twice, or has a tab starting a line, or an unclosed
  flow sequence
- **THEN** loading fails with the parse error whose message does not contain `<unicode string>` and names
  the source in each of the reader's line-and-column excerpts

#### Scenario: A source given by the caller is used as given
- **WHEN** text is loaded with the stated source `draft-reel` and holds `title: "\x"`
- **THEN** the message names `draft-reel` in the excerpt and does not contain `<unicode string>`

#### Scenario: A position-less failure says how far reading got
- **WHEN** a v0 document's line 4 reads `  x: "\U00110000"`, a double-quoted escape past the last Unicode
  code point, and lines 1 to 3 are valid
- **THEN** loading fails with the parse error naming the file and the reader's reason, and stating that
  reading got as far as line 4

#### Scenario: A document nested too deeply is named as such
- **WHEN** a v0 document sets `title` to a flow sequence nested 250 levels deep
- **THEN** loading fails with the parse error naming the file, saying the document is nested too deeply to
  load and keeping the reader's reason, and states no line number

#### Scenario: A valid document is unaffected
- **WHEN** a v0 document with no syntax error is loaded
- **THEN** it loads exactly as before, with no re-reading and no change to its fingerprint or output

### Requirement: Chapter names are unpadded, non-blank and unique ignoring case

A chapter's `name` SHALL be a string. The empty string is the name of the default chapter and is always
valid. Any other name SHALL be non-blank (not empty after `str.strip()`) and SHALL equal its own
`str.strip()`, so it has no leading or trailing whitespace. Two chapters SHALL NOT have names that are equal
under `str.casefold()`; the document is judged by that comparison alone, with no Unicode normalization, so
a name differing only in case from another is a duplicate and a name differing in any other character is
not. Loading a document that breaks any of these SHALL fail with the single parse error of "Fail-loud parse
and validation", naming the offending `chapters[i]` and, for a duplicate, both chapters and both names as
written. A name SHALL NOT be trimmed, case-folded or otherwise rewritten to make a document load.

A document that a writer is asked to write SHALL be checked by the same rules before anything is written,
so no write produces a `reel.yaml` that this requirement would refuse to load. A refused write leaves the
previous `reel.yaml`, if any, as it was.

#### Scenario: A whitespace-only chapter name is refused

- **WHEN** a `reel.yaml` lists chapters named `""` and `"  "`
- **THEN** loading fails with the parse error naming `chapters[1]`, saying the name is blank

#### Scenario: A padded chapter name is refused

- **WHEN** a `reel.yaml` lists a chapter named `" Party"` or `"Party "`
- **THEN** loading fails with the parse error naming that chapter and the name as written, and the
  document is not trimmed to load

#### Scenario: Names equal ignoring case are duplicates

- **WHEN** a `reel.yaml` lists chapters `Party` and `party`
- **THEN** loading fails with the parse error naming `chapters[1]` and `chapters[0]` and both names, saying
  they are the same ignoring case

#### Scenario: Case folding follows str.casefold

- **WHEN** a `reel.yaml` lists chapters `Straße` and `STRASSE`
- **THEN** loading fails with a duplicate chapter name error, because `str.casefold()` folds the sharp s

#### Scenario: Exact duplicates are still refused

- **WHEN** a `reel.yaml` lists two chapters both named `Reception`
- **THEN** loading fails with a duplicate chapter name error naming both

#### Scenario: The default chapter and ordinary names load

- **WHEN** a `reel.yaml` lists chapters `""`, `Reception` and `Dag 2`
- **THEN** it loads, and `""` is the default chapter

#### Scenario: Seeding folders that differ only by case writes nothing

- **WHEN** an event holds subfolders `Party/` and `party/`, each with a clip, and no `reel.yaml`, and the
  seeded document is written
- **THEN** the write fails with the duplicate chapter name error and no `reel.yaml` exists afterwards

#### Scenario: A writer refuses a padded name and keeps the old file

- **WHEN** an existing `reel.yaml` is replaced by a document with a chapter named `"Party "`
- **THEN** the write fails with the parse error and the `reel.yaml` on disk is unchanged

### Requirement: A clip's `rotate` is an extra clockwise turn

A clip's `rotate` property (`clips.<identity>.rotate` in `reel.yaml`) SHALL mean "turn this clip this many
degrees **clockwise** from how it plays now", where "how it plays now" is the picture a player shows after
applying the container's own display rotation. It SHALL be an extra turn **on top of** the display rotation and
SHALL NOT replace it: a clip that a player shows sideways is fixed by the turn that makes the player's picture
upright, whatever the clip's container says. An absent `rotate` and `rotate: 0` SHALL both mean no extra turn.
The value is the editorial decision and SHALL be remembered in the event's `reel.yaml`, which stays the only
home of it.

A document SHALL accept for `rotate` an integer that is a multiple of 90 (so 0, 90, 180 and 270, and also -90
and 360, which mean 270 and 0). Any other value, a boolean, a float and a string included, SHALL fail the load
with a parse error that names the clip identity and the key `rotate`; the same rule SHALL apply to a document
built by an editorial write. The value SHALL be written back as it was written, with the document's comments and
key order kept by the round-trip writer.

Where another requirement or spec calls `rotate` an "orientation override", this requirement governs.

#### Scenario: A turn is read as written
- **WHEN** a document sets `clips: {Reception/00400.mp4: {rotate: 90}}`
- **THEN** the clip's property `rotate` is 90, and resolving the document puts 90 on the clip in the plan

#### Scenario: No turn
- **WHEN** a clip has no `rotate`, or `rotate: 0`
- **THEN** the plan applies no extra turn to it, and the clip is fixed only by its display rotation

#### Scenario: A turn that is not a quarter turn is refused at load
- **WHEN** a document sets `rotate: 45` on `Reception/00400.mp4`
- **THEN** loading fails with a parse error naming `Reception/00400.mp4` and `rotate`, and no render is queued
  from that document

#### Scenario: A float, a string and a boolean are refused
- **WHEN** a document sets `rotate: 90.0`, `rotate: "90"` or `rotate: true`
- **THEN** loading fails with a parse error naming the clip and `rotate`

#### Scenario: An editorial write of a bad turn leaves the file alone
- **WHEN** an editorial write sets `rotate: 100` on a clip
- **THEN** the write fails loudly and the existing `reel.yaml` is unchanged

#### Scenario: A turn survives a round trip
- **WHEN** a document with `rotate: 270` and a comment beside it is read and written back with no edit
- **THEN** the file's bytes are unchanged
