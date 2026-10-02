## MODIFIED Requirements

### Requirement: Load a project config.yaml of shared defaults

The system SHALL load a project-level `config.yaml` that may declare shared defaults: a `look` map
(codec/resolution/title styling), the ingest layout name, default input/output paths, a clip `sort`
rule, and the maps of the components that read their own settings from it: `database.url`, `worker`,
`api` and `thumbnails`. A missing or partial `config.yaml` SHALL be tolerated — every field is optional
and absent fields fall back to built-in defaults.

The `sort` rule SHALL be a mapping with an optional `method`, either `datetime` or `filename`, and an
optional boolean `reverse`. Absent, the rule SHALL be `datetime`, not reversed, which is auto-reel's own
default. Any other method, or a wrong-typed value, SHALL fail loud like any other malformed field.

The `database`, `worker`, `api` and `thumbnails` entries SHALL each be a mapping, and any other type
SHALL fail loud naming the key. This capability SHALL carry the inner keys of `worker`, `api` and
`thumbnails` through untouched, like `look`; the component that reads a map validates its keys and the
capability that owns the component states them (`clip-thumbnails` for `thumbnails.position` and
`thumbnails.cache_dir`).

#### Scenario: Config supplies the ingest layout name

- **WHEN** `config.yaml` sets the layout to `flat`
- **THEN** the project scan uses the `flat` layout unless overridden on the command line

#### Scenario: Missing config is tolerated

- **WHEN** no `config.yaml` exists at the project root
- **THEN** scanning and rendering proceed using built-in defaults and the default `year-event` layout

#### Scenario: Malformed config fails loud

- **WHEN** `config.yaml` exists but is not valid YAML or has a wrong-typed field
- **THEN** the system raises a typed configuration error identifying the problem, rather than
  silently ignoring the file

#### Scenario: The sort rule defaults to datetime

- **WHEN** `config.yaml` sets no `sort`
- **THEN** new clips enter documents in `datetime` order, not reversed

#### Scenario: A library chooses filename order

- **WHEN** `config.yaml` sets `sort: {method: filename}`
- **THEN** new clips enter documents in natural, case-insensitive filename order

#### Scenario: An unknown sort method fails loud

- **WHEN** `config.yaml` sets `sort: {method: custom}` or `sort: {reverse: "yes"}`
- **THEN** the system raises a typed configuration error naming `sort.method` or `sort.reverse`

#### Scenario: Config supplies thumbnail settings

- **WHEN** `config.yaml` sets `thumbnails: {position: 0.5, cache_dir: /data/cache/auto-reel/thumbnails}`
- **THEN** the loaded configuration carries both keys as written, for the thumbnail settings to validate

#### Scenario: A config without a thumbnails map is tolerated

- **WHEN** `config.yaml` sets no `thumbnails`
- **THEN** the loaded configuration carries an empty `thumbnails` map, and the thumbnail defaults apply

#### Scenario: A wrong-typed thumbnails map fails loud

- **WHEN** `config.yaml` sets `thumbnails: 3`
- **THEN** the system raises a typed configuration error naming `thumbnails`

#### Scenario: Config supplies worker and API settings

- **WHEN** `config.yaml` sets `worker: {cpu_slots: 4}` and `api: {port: 9000}`
- **THEN** the loaded configuration carries `cpu_slots: 4` in its `worker` map and `port: 9000` in its `api`
  map
