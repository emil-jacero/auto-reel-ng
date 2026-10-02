# project-config Specification

## Purpose

Load a project-level `config.yaml` of shared, all-optional defaults — a `look` map, the ingest layout name, default input/output paths, and the clip `sort` rule — tolerating missing or partial files while failing loud on malformed ones. Resolve effective settings through a defined layered order (folder/layout seed → project `config.yaml` → event `reel.yaml` → command-line overrides) so each later layer overrides the earlier, passing the resolved `look` map to `resolve()` as `look_defaults`.

## Requirements

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

### Requirement: Layered configuration resolution (D-2)

The system SHALL resolve effective settings in the order folder/layout seed → project
`config.yaml` → event `reel.yaml` → command-line overrides, with each later layer overriding the
earlier. The resolved `look` map SHALL be passed to `resolve()` as `look_defaults`, which already
treats it opaquely.

#### Scenario: reel.yaml overrides config.yaml

- **WHEN** `config.yaml` sets a default resolution and an event's `reel.yaml` sets a different one
- **THEN** the event renders at the `reel.yaml` resolution

#### Scenario: CLI flag overrides config.yaml

- **WHEN** `config.yaml` sets a default and the matching CLI flag is passed
- **THEN** the CLI flag value wins for that run

#### Scenario: Config default applies when nothing overrides

- **WHEN** `config.yaml` sets a default that no `reel.yaml` or CLI flag overrides
- **THEN** that default is used

### Requirement: The output directory never lies inside the walked root

The effective output directory SHALL NOT equal the directory the ingest layout walks, and SHALL NOT lie
inside it. The walked directory is the project root, or `<root>/<input>` when `config.yaml` sets `input`.
This SHALL hold whichever layer chose the output: `-o/--output`, `config.yaml`'s `output`, or the default.
The comparison SHALL be made on resolved paths, so a relative path, `..` or a symlink into the walked root
is caught and a symlink out of it is not. The check SHALL be made once for every consumer of these
settings, the CLI commands that walk a project and the API service, with the same outcome. A violation
SHALL fail loud with a typed configuration error that names the output directory and the walked root and
suggests a folder outside it, before the layout walks anything and before anything is written, rendered or
bound (the service does not start). An output directory that contains the walked root, or lies beside it
or inside the project root but outside a distinct `input` directory, SHALL NOT be refused.

#### Scenario: Config output inside the project root is refused
- **WHEN** `config.yaml` sets `output: out` with no `input`, and a CLI command or the API service resolves
  the project
- **THEN** it raises the configuration error naming `<root>/out` and `<root>`, and no event is enumerated

#### Scenario: The service refuses to start
- **WHEN** `auto-reel serve <root>` runs with `config.yaml` `output: out`
- **THEN** it exits 1 with the same error before binding a port

#### Scenario: A nested output is refused
- **WHEN** `-o <root>/out/renders` is given
- **THEN** it is refused, because the output is inside the walked root at any depth

#### Scenario: A symlink into the walked root is refused
- **WHEN** `-o ../shortcut` is given where `shortcut` is a symlink to `<root>/out`
- **THEN** it is refused, because its resolved path is inside the walked root

#### Scenario: The sibling default is allowed
- **WHEN** neither `-o` nor `output` is set
- **THEN** the output is `<parent>/<root-name>-output`, no error is raised, and nothing changes from
  before

#### Scenario: A sibling folder is allowed
- **WHEN** `config.yaml` sets `output: ../renders`
- **THEN** the output is accepted

#### Scenario: Output beside a distinct input directory is allowed
- **WHEN** `config.yaml` sets `input: media` and `output: out`
- **THEN** the walked root is `<root>/media`, the output `<root>/out` is outside it, and it is accepted

#### Scenario: An output containing the walked root is allowed
- **WHEN** `config.yaml` sets `input: media` and `output: .`
- **THEN** the output `<root>` contains the walked root `<root>/media`, movies are filed under
  `<root>/<YYYY>/`, and it is accepted
