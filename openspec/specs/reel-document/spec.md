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
SHALL NOT reject a `look` map on the basis of its inner keys.

#### Scenario: Unknown look fields are preserved, not rejected
- **WHEN** a document's `look` contains fields v0 does not model
- **THEN** loading succeeds and the writer round-trips the `look` map unchanged

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
multiple non-overlapping spans.

#### Scenario: Two cut spans on one clip
- **WHEN** a clip has trims `[{in: 0, out: 3.2, reason: black}, {in: 58.1, out: 60.0, reason: freeze}]`
- **THEN** the document parses both spans in order as removals, keeping the footage between them

### Requirement: Fail-loud parse and validation

Parsing SHALL fail loudly with a clear error on malformed or invalid content and SHALL NOT fabricate or
silently drop data. Validation SHALL reject (at least) an unknown `version`, a trim with `out <= in`, a
negative time, and a `chapters` clip reference whose identity is absent from required structure. Errors SHALL
identify the offending location.

The reference-integrity checks are **disk-independent** — a referenced clip merely absent from disk is a
*reconcile* MISSING (see `event-reconcile`), not a parse error. Internally the validator SHALL reject: a clip
identity referenced more than once across all chapters (a duplicate/ambiguous reference); a `clips` property
entry keyed by an identity no chapter references (a dangling property record with nothing to attach to); and
an `ignore` entry whose identity is also referenced in a chapter (a structure/ignore contradiction).

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
