## MODIFIED Requirements

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
