## ADDED Requirements

### Requirement: Load a project config.yaml of shared defaults

The system SHALL load a project-level `config.yaml` that may declare shared defaults: a `look` map
(codec/resolution/title styling), the ingest layout name, and default input/output paths. A
missing or partial `config.yaml` SHALL be tolerated — every field is optional and absent fields
fall back to built-in defaults.

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
