## MODIFIED Requirements

### Requirement: Load a project config.yaml of shared defaults

The system SHALL load a project-level `config.yaml` that may declare shared defaults: a `look` map
(codec/resolution/title styling), the ingest layout name, default input/output paths, and a clip `sort`
rule. A missing or partial `config.yaml` SHALL be tolerated — every field is optional and absent fields
fall back to built-in defaults.

The `sort` rule SHALL be a mapping with an optional `method`, either `datetime` or `filename`, and an
optional boolean `reverse`. Absent, the rule SHALL be `datetime`, not reversed, which is auto-reel's own
default. Any other method, or a wrong-typed value, SHALL fail loud like any other malformed field.

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
