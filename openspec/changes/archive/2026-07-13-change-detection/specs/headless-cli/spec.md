## MODIFIED Requirements

### Requirement: `auto-reel` entry point with subcommands

The system SHALL install a `console_scripts` entry point named `auto-reel` exposing the
subcommands `render`, `scan` (alias `list`), `analyze`, `import`, `enqueue`, `worker`, `jobs`, `serve`,
and `adopt-renders`. Invalid arguments or an unknown subcommand SHALL produce a non-zero exit and a usage
message.

#### Scenario: Entry point is installed

- **WHEN** the package is installed and `auto-reel --help` is run
- **THEN** the nine subcommands are listed and the command exits zero

#### Scenario: Unknown subcommand fails

- **WHEN** `auto-reel frobnicate` is run
- **THEN** the command exits non-zero with a usage message

### Requirement: `render` drives the engine end to end

The `render` subcommand SHALL scan the project with the resolved layout, apply the staleness gate to the
selected events (rendering only stale ones unless `--force`), reconcile and resolve each event, probe its
clips, select an acceleration profile, and render via `render_batch`, writing one output per event to the
output directory. For an event judged stale, the render SHALL replace any existing output (the gate
verdict, not bare file existence, is what "already done" means). It SHALL accept `--years`, `--dry-run`,
`--force`, and `--device`; the former `--overwrite` flag is removed (**BREAKING** — use `--force`).
Per-event failures SHALL be isolated (via `BatchOutcome`): one bad event is reported and does not abort
the rest.

#### Scenario: End-to-end render of selected events

- **WHEN** `render` runs over a project with two valid stale events
- **THEN** two output files are produced and the command reports success per event

#### Scenario: Unchanged project renders nothing

- **WHEN** `render` runs twice with no disk change between
- **THEN** the second run performs zero renders and reports each event as fresh

#### Scenario: Force bypasses the gate and replaces output

- **WHEN** `render --force` runs over a fresh event with an existing output
- **THEN** the event re-renders and the output is replaced

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

#### Scenario: Removed flag fails loud

- **WHEN** `render --overwrite` is passed
- **THEN** the command exits non-zero with a usage message

### Requirement: `scan`/`list` reports inventory without rendering

The `scan` subcommand SHALL report, per selected event, its clips and their reconcile
classification (`NEW`/`ACTIVE`/`IGNORED`/`MISSING`) and its staleness verdict — fresh, or stale with the
changed components as reasons — without running any render or ffmpeg encode.

#### Scenario: Scan lists events and clip status

- **WHEN** `scan` runs over a project
- **THEN** it prints each event with its clips classified, and writes no output files

#### Scenario: Missing referenced clip is surfaced

- **WHEN** an event's `reel.yaml` references a clip absent from disk
- **THEN** `scan` reports that clip as `MISSING`

#### Scenario: Staleness is reported with reasons

- **WHEN** `scan` runs over one fresh event and one event whose clips changed since its last render
- **THEN** the first is reported fresh and the second stale citing the clip-set component

### Requirement: `enqueue` records jobs without rendering
`auto-reel enqueue` SHALL scan the project via the configured ingest layout (honoring `--years` and
`--device`), apply the staleness gate, and insert one `queued` job per **stale** selected event — storing
the root-relative event identity, the project root, the event's fingerprint, and the force flag. Fresh
events SHALL be reported as fresh and not enqueued unless `--force` is given, which enqueues them all with
`force` set. It MUST NOT probe, render, or block on job completion, and it SHALL report per event whether
a job was created, an active job already existed (idempotent enqueue), or the event was fresh.

#### Scenario: Only stale events become queued jobs
- **WHEN** `auto-reel enqueue` runs against one stale and one fresh event
- **THEN** one `queued` job exists for the stale event and the fresh event is reported fresh with no job

#### Scenario: Force enqueues fresh events
- **WHEN** `auto-reel enqueue --force` runs against fresh events
- **THEN** each gets a `queued` job with its `force` flag set

#### Scenario: Re-running enqueue creates no duplicates
- **WHEN** `auto-reel enqueue` runs twice for the same stale events
- **THEN** the second run inserts no new jobs and reports the existing active jobs

## ADDED Requirements

### Requirement: `adopt-renders` performs explicit manifest adoption
`auto-reel adopt-renders` SHALL run manifest adoption over the selected events (honoring `--years`):
writing a manifest at the current fingerprint for each event whose output file exists, skipping events
without outputs, rendering nothing, and reporting the outcome per event. This is the documented one-time
step when deploying change detection over an already-rendered archive.

#### Scenario: Archive adoption without re-rendering
- **WHEN** `auto-reel adopt-renders` runs over an archive of rendered events with no manifests
- **THEN** each event with an output gains a manifest, no ffmpeg process runs, and a subsequent
  `enqueue`/`render` treats those events as fresh

#### Scenario: Unrendered events are reported and skipped
- **WHEN** an event has no output file
- **THEN** `adopt-renders` reports it as unrendered and writes no manifest
