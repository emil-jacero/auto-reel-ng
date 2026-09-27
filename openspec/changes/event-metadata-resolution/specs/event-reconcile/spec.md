## MODIFIED Requirements

### Requirement: Discovery seeds a complete document from folder structure

On first discovery of an event directory, the engine SHALL seed a complete v0 document using folder structure
only as a hint: subdirectories become chapters, root-level clips become the default chapter, and folder-name
metadata seeds `metadata`. After seeding, structure SHALL live in the document and folder layout SHALL NOT be
consulted again to determine structure.

A folder name SHALL be read as `[<date> - ]<title>[ - <location>]`. The leading token is the date. The title
and location SHALL be extracted from the remainder whether or not the date part is usable. The date SHALL be
set only when the token is a real calendar date in `YYYY-MM-DD` form. Otherwise the date SHALL be left unset,
and the parse SHALL state a problem naming why:

- the token is well-formed but not a real date, such as `2019-04-31`
- the token is a year only, such as `2004`
- the name carries no date

A remainder with no title SHALL leave the title unset, with a problem stating that. Seeding SHALL NOT raise
because of a folder name's problem, and it SHALL NOT fabricate a value: no placeholder title and no guessed
date.

#### Scenario: Subdirectories seed chapters
- **WHEN** an event directory with a `Reception/` subdir and root-level clips is first discovered
- **THEN** the seeded document has a default chapter for the root clips and a `Reception` chapter for the subdir clips

#### Scenario: Folder name seeds metadata
- **WHEN** an event directory named `2024-06-21 - Midsummer - Dalarna` is seeded
- **THEN** the document's metadata has title `Midsummer`, date `2024-06-21`, and location `Dalarna`

#### Scenario: An impossible date keeps the title and states the problem
- **WHEN** an event directory named `2019-04-31 - Golfträning med Emil - Tjörn` is seeded
- **THEN** the document's metadata has title `Golfträning med Emil` and location `Tjörn` and no date, and the
  parse states that `2019-04-31` is not a real date

#### Scenario: A year-only name keeps the title and states the problem
- **WHEN** an event directory named `2004 - Yngve berättar om skövde` is seeded
- **THEN** the document's metadata has title `Yngve Berättar om Skövde` and no date, and the parse states that
  the name has a year only

#### Scenario: A name without a date is a title
- **WHEN** an event directory named `Blandat` is seeded
- **THEN** the document's metadata has title `Blandat` and no date, and the parse states that the name has no
  date

#### Scenario: Nothing is fabricated
- **WHEN** any folder name is seeded, however malformed
- **THEN** the seeded metadata contains only values read from the name, and never a placeholder title such as
  `Untitled`

## ADDED Requirements

### Requirement: Event metadata resolves field by field, reel.yaml over folder name

Whenever the engine processes an event, it SHALL resolve the event's metadata one field at a time. Date,
title and location SHALL each take the value from the event's `reel.yaml` when that field is set there,
otherwise the value parsed from the event's folder name. The folder layer is the lowest one (D-2). An empty
or whitespace-only value in `reel.yaml` SHALL count as unset.

Resolution SHALL apply to a legacy `reel.yaml` as well as a v0 one. It SHALL be what every consumer that
processes the event reads:

- output naming
- the title card
- the staleness fingerprint's editorial component
- scanning and rendering
- the worker
- the service's events list and detail

Resolution SHALL NOT be written back to disk. The editorial read and write endpoints SHALL continue to read
and write `reel.yaml` exactly as authored. A folder-name problem SHALL NOT affect a field that `reel.yaml`
supplies.

#### Scenario: A reel.yaml without a date takes the folder's date
- **WHEN** event folder `2025-01-13 - Resa till Gran Canaria` holds a `reel.yaml` with a title but no date
- **THEN** the event resolves to date `2025-01-13` and the title from `reel.yaml`

#### Scenario: reel.yaml wins over the folder name
- **WHEN** event folder `2019-04-31 - Golfträning med Emil - Tjörn` holds a `reel.yaml` with date `2019-04-30`
- **THEN** the event resolves to date `2019-04-30`, and the impossible folder date has no effect

#### Scenario: A folder rename changes only fields reel.yaml leaves unset
- **WHEN** a `reel.yaml` sets title and date but no location, and the folder is renamed to add ` - Tjörn`
- **THEN** the resolved location becomes `Tjörn`, and the title and date are unchanged

#### Scenario: Resolution is never persisted
- **WHEN** an event with a date-less `reel.yaml` is scanned, rendered and read through the editorial read
  endpoint
- **THEN** its `reel.yaml` still has no date, and the editorial read returns the document without one
