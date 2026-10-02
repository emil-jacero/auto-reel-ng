## ADDED Requirements

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
