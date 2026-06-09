## ADDED Requirements

### Requirement: `auto-reel` entry point with subcommands

The system SHALL install a `console_scripts` entry point named `auto-reel` exposing the
subcommands `render`, `scan` (alias `list`), `analyze`, and `import`. Invalid arguments or an
unknown subcommand SHALL produce a non-zero exit and a usage message.

#### Scenario: Entry point is installed

- **WHEN** the package is installed and `auto-reel --help` is run
- **THEN** the four subcommands are listed and the command exits zero

#### Scenario: Unknown subcommand fails

- **WHEN** `auto-reel frobnicate` is run
- **THEN** the command exits non-zero with a usage message

### Requirement: `render` drives the engine end to end

The `render` subcommand SHALL scan the project with the resolved layout, reconcile and resolve each
selected event, probe its clips, select an acceleration profile, and render via `render_batch`,
writing one output per event to the output directory. It SHALL accept `--years`, `--dry-run`,
`--overwrite`, and `--device`. Per-event failures SHALL be isolated (via `BatchOutcome`): one bad
event is reported and does not abort the rest.

#### Scenario: End-to-end render of selected events

- **WHEN** `render` runs over a project with two valid events
- **THEN** two output files are produced and the command reports success per event

#### Scenario: Dry run prints commands without writing

- **WHEN** `render --dry-run` runs
- **THEN** the ffmpeg commands are printed, no output file is written, and the command exits zero

#### Scenario: One bad event does not abort the batch

- **WHEN** one event fails to render and another succeeds
- **THEN** the failure is reported with its cause, the other event still renders, and the exit code
  reflects that a failure occurred

#### Scenario: Device override selects the profile

- **WHEN** `render --device <id>` is passed
- **THEN** the selected acceleration profile targets that device rather than the auto-picked default

### Requirement: `scan`/`list` reports inventory without rendering

The `scan` subcommand SHALL report, per selected event, its clips and their reconcile
classification (`NEW`/`ACTIVE`/`IGNORED`/`MISSING`) without running any render or ffmpeg encode.

#### Scenario: Scan lists events and clip status

- **WHEN** `scan` runs over a project
- **THEN** it prints each event with its clips classified, and writes no output files

#### Scenario: Missing referenced clip is surfaced

- **WHEN** an event's `reel.yaml` references a clip absent from disk
- **THEN** `scan` reports that clip as `MISSING`

### Requirement: NEW-clip adoption policy

When an event directory has no `reel.yaml`, the system SHALL seed one from disk structure. When an
event has a `reel.yaml` and disk contains `NEW` clips, `render` SHALL adopt `NEW` clips into the
default chapter (configurable) so an added clip is not silently dropped, while `MISSING` clips
SHALL be reported loudly and never silently removed from the document.

#### Scenario: First scan seeds a document

- **WHEN** `render` runs on an event with no `reel.yaml`
- **THEN** a document is seeded from folder structure and the event renders

#### Scenario: Newly added clip is adopted, not dropped

- **WHEN** an event already has a `reel.yaml` and a new clip file appears on disk
- **THEN** `render` adopts the `NEW` clip into the default chapter and includes it in the output

#### Scenario: Missing clip is reported, not silently removed

- **WHEN** a `reel.yaml` references a clip that no longer exists on disk
- **THEN** the system reports the `MISSING` clip and does not remove it from the document

### Requirement: `analyze` runs detection and reports suggestions

The `analyze` subcommand SHALL run the analysis pass over selected events, print the suggested
black/white/freeze segments, and cache them. It SHALL NOT modify `reel.yaml` (consistent with the
analysis change's suggestion-only scope).

#### Scenario: Analyze prints and caches suggestions

- **WHEN** `analyze` runs on an event
- **THEN** detected segments are printed, cached to the analysis sidecar, and `reel.yaml` is unchanged

### Requirement: `import` adopts auto-reel legacy metadata

The `import` subcommand SHALL read an auto-reel legacy `reel.yaml`/`metadata.yaml` via
`import_legacy` and produce a v2 `reel.yaml`, reporting what was imported.

#### Scenario: Legacy metadata imported to v2

- **WHEN** `import` runs against a legacy event
- **THEN** a v2 `reel.yaml` is produced carrying the legacy metadata/title/sort fields
