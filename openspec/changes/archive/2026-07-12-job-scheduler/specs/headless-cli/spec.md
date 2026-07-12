## MODIFIED Requirements

### Requirement: `auto-reel` entry point with subcommands

The system SHALL install a `console_scripts` entry point named `auto-reel` exposing the
subcommands `render`, `scan` (alias `list`), `analyze`, `import`, `enqueue`, `worker`, and `jobs`.
Invalid arguments or an unknown subcommand SHALL produce a non-zero exit and a usage message.

#### Scenario: Entry point is installed

- **WHEN** the package is installed and `auto-reel --help` is run
- **THEN** the seven subcommands are listed and the command exits zero

#### Scenario: Unknown subcommand fails

- **WHEN** `auto-reel frobnicate` is run
- **THEN** the command exits non-zero with a usage message

## ADDED Requirements

### Requirement: `enqueue` records jobs without rendering
`auto-reel enqueue` SHALL scan the project via the configured ingest layout (honoring `--years` and
`--device`) and insert one `queued` job per selected event, storing the root-relative event identity and
the project root. It MUST NOT probe, render, or block on job completion, and it SHALL report per event
whether a job was created or an active job already existed (idempotent enqueue).

#### Scenario: Events become queued jobs
- **WHEN** `auto-reel enqueue --input-dir <root> --years 2024` runs against events with no active jobs
- **THEN** one `queued` job per selected event exists and the command exits zero without rendering

#### Scenario: Re-running enqueue creates no duplicates
- **WHEN** `auto-reel enqueue` runs twice for the same events
- **THEN** the second run inserts no new jobs and reports the existing active jobs

### Requirement: `worker` runs the scheduler loop
`auto-reel worker` SHALL start the job-scheduler worker: startup reconciliation, then the poll/claim/render
loop, until SIGINT/SIGTERM triggers graceful shutdown (in-flight jobs requeued, clean exit). Pool
capacities and the poll interval SHALL be configurable via `config.yaml` with CLI-flag overrides (D-2
layering).

#### Scenario: Worker processes the queue
- **WHEN** jobs are queued and `auto-reel worker` runs
- **THEN** jobs transition queued → running → done and outputs appear at their final paths

#### Scenario: Interrupt exits cleanly
- **WHEN** the worker receives SIGINT while processing
- **THEN** it requeues in-flight work and exits zero without leaving any job `running`

### Requirement: `jobs` reports job state
`auto-reel jobs` SHALL provide a read-only view of the store: listing jobs (filterable by status) and
showing one job's detail (status, progress, device, worker, timestamps, error). It SHALL also expose
cancellation via `request_cancel` (`auto-reel jobs cancel <id>`). It MUST NOT mutate job state other than
through `request_cancel`.

#### Scenario: List queued jobs
- **WHEN** `auto-reel jobs list --status queued` runs
- **THEN** queued jobs print with id, event, and created time, oldest first

#### Scenario: Cancel from the CLI
- **WHEN** `auto-reel jobs cancel <id>` targets a running job
- **THEN** the job's `cancel_requested` flag is set and the command exits zero
