# project-config Specification

## Purpose

Load a project-level `config.yaml` of shared, all-optional defaults — a `look` map, the ingest layout name, default input/output paths, the clip `sort` rule, and the `database`, `worker`, `api` and `thumbnails` maps of the components that read their own settings from it — tolerating missing or partial files while failing loud on malformed ones. Resolve effective settings through a defined layered order (folder/layout seed → project `config.yaml` → event `reel.yaml` → command-line overrides) so each later layer overrides the earlier, passing the resolved `look` map to `resolve()` as `look_defaults`.

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

### Requirement: A config.yaml that cannot be loaded or used fails loud as a configuration error

Every way a project `config.yaml` can fail to load SHALL surface as the typed configuration error naming
the file, never as a builtin exception. This includes YAML the parser rejects, a well-formed value its tag
cannot hold (an unquoted date that does not exist, such as `2024-02-30`, an unknown `!!bool` value), a
document nested too deeply to construct, and any other error raised while constructing the document.

After a successful load and before any field is read, the system SHALL validate the content and raise the
configuration error, naming the key path, for each of the following:

- a string, as a key or a value anywhere in the file, that cannot be encoded as UTF-8 (a lone surrogate);
- an integer too large to be printed, as a value or as a mapping key (the explicit `? 0x...` key syntax);
- under `look`, a mapping key that is not a string (a date, a number, a boolean), at any depth;
- a mapping or list that contains itself through an alias.

Values under `look`, `worker`, `api` and `thumbnails` SHALL otherwise stay uninterpreted.

#### Scenario: An impossible date is a configuration error

- **WHEN** `config.yaml` contains `look: {a: 2024-02-30}`
- **THEN** loading raises the configuration error whose message names the file and says the YAML is
  malformed, and no `ValueError` escapes

#### Scenario: Other builtin errors from the YAML load are configuration errors

- **WHEN** `config.yaml` contains `a: !!bool maybe`, or a flow sequence nested a hundred thousand levels deep
- **THEN** loading raises the configuration error, not `KeyError` or `RecursionError`

#### Scenario: A non-string look key is refused with its path

- **WHEN** `config.yaml` contains `look: {2024-01-01: x}`, or `look: {1: a, b: c}`, or a non-string key at
  depth, as in `look: {title: {1: x}}`
- **THEN** loading raises the configuration error naming `look` (or `look.title`) and the offending key,
  before any fingerprint is computed

#### Scenario: String keys and non-string keys outside look are accepted

- **WHEN** `config.yaml` has only string keys under `look`, or an integer key under `worker`
- **THEN** it loads exactly as before

#### Scenario: A lone surrogate is refused wherever it appears

- **WHEN** `config.yaml` contains `layout: "x\ud800"`, or the same escape in a `look` value, a `look` key or
  a `database.url`
- **THEN** loading raises the configuration error naming the key path and stating the text contains a lone
  surrogate that cannot be encoded as UTF-8, and no `UnicodeEncodeError` can occur later when the value is printed, logged, hashed or
  sent as JSON

#### Scenario: A huge hexadecimal integer is refused

- **WHEN** `config.yaml` contains `look: {a: 0x` followed by five thousand `f` digits `}`
- **THEN** loading raises the configuration error naming `look.a`, the same refusal a `reel.yaml` gets

#### Scenario: A self-referencing alias is refused

- **WHEN** `config.yaml` contains `look: &a {x: *a}`
- **THEN** loading raises the configuration error stating the structure refers to itself, and does not
  recurse without bound

#### Scenario: A valid file is unaffected

- **WHEN** `config.yaml` has a string-keyed `look`, a `layout`, `sort`, and non-ASCII text such as `Café`
  and `日本語`
- **THEN** it loads to the same `ProjectConfig` as before
