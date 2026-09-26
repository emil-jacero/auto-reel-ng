# headless-cli Specification

## Purpose

Provide a headless `auto-reel` command-line entry point that drives the engine end to end. The CLI exposes `render`, `scan` (alias `list`), `analyze`, `import`, and `serve` subcommands, isolating per-event failures, reporting inventory without rendering, seeding and adopting clips through a defined NEW-clip policy, surfacing analysis suggestions without mutating `reel.yaml`, importing legacy auto-reel metadata into the v2 document format, and running the API service.

## Requirements

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

### Requirement: `serve` runs the API service
`auto-reel serve` SHALL resolve API settings through the D-2 layering (`api.host` / `api.port` /
`api.poll_interval` from `config.yaml`, CLI flags override, defaults `127.0.0.1:8080`, 1 s) and run the
API service under uvicorn until SIGINT/SIGTERM triggers a graceful shutdown (WebSocket poller stopped,
connections closed, exit zero). A failure to bind SHALL exit non-zero naming the attempted host and port.

#### Scenario: Serve starts and answers
- **WHEN** `auto-reel serve` runs against a project root and a reachable database
- **THEN** `GET /healthz` on the configured host/port returns success

#### Scenario: Flags override config
- **WHEN** `config.yaml` sets `api.port: 8080` and `auto-reel serve --port 9000` is run
- **THEN** the service binds port 9000

#### Scenario: Bind failure is loud
- **WHEN** the configured port is already in use
- **THEN** the command exits non-zero naming the attempted host:port

### Requirement: Batch commands refuse colliding output paths

Before acting, `render`, `enqueue` and `adopt-renders` SHALL check the events they selected: every event,
fresh or stale, forced or not, whether or not it is a dry run. Any two or more events that resolve to the
same output path SHALL be treated as a **collision**. Paths SHALL be compared case-insensitively, so a
collision that a case-insensitive archive filesystem would create is caught even on a case-sensitive host.

Every event in a collision SHALL be reported as an error. The report SHALL name the shared output path and
the other events that claim it. For these events the command MUST NOT render, enqueue, adopt, or overwrite
anything; an output file that already exists at the shared path SHALL be left untouched. Events outside
any collision SHALL proceed normally (per-event isolation). A command that reported at least one
collision SHALL exit non-zero. A collision SHALL NOT be resolved automatically by renaming, suffixing or
skipping one side. The operator resolves it by changing an event's `title` or `location` in `reel.yaml`.

The check covers only the events the command selected (for example, only the years named by `--years`).
Events outside the selection are not examined.

#### Scenario: Two same-titled events in one year collide
- **WHEN** `render` runs over events `2024/2024-06-21 - Midsommar` and `2024/2024-06-22 - Midsommar`,
  both with title `Midsommar` and no location, plus a third, uniquely named 2024 event
- **THEN** both Midsommar events are reported as errors naming `2024/Midsommar.mp4` and each other, neither
  is rendered, the third event renders normally, and the command exits non-zero

#### Scenario: A fresh event's output is protected from a new same-named event
- **WHEN** a fresh event already owns `<output>/2024/Midsommar.mp4` and a newly added 2024 event also
  resolves to `Midsommar`
- **THEN** `render` reports both as colliding, the existing `Midsommar.mp4` is byte-for-byte unchanged, and
  no manifest is written for either event

#### Scenario: Collision differing only in letter case
- **WHEN** two 2024 events resolve to `2024/Midsommar.mp4` and `2024/midsommar.mp4`
- **THEN** they are reported as a collision

#### Scenario: Same title in different years is not a collision
- **WHEN** events dated 2023 and 2024 both have title `Midsommar`
- **THEN** no collision is reported and both render to their own year folder

#### Scenario: Force does not override a collision
- **WHEN** `render --force` runs over two colliding events
- **THEN** both are reported as colliding and neither is rendered

#### Scenario: Dry run reports the collision
- **WHEN** `render --dry-run` runs over two colliding events
- **THEN** both are reported as colliding, no commands are printed for them, and the command exits
  non-zero

#### Scenario: Enqueue refuses colliding events
- **WHEN** `enqueue` runs over two colliding stale events
- **THEN** both are reported as colliding, no job row is inserted for either, other events are enqueued,
  and the command exits non-zero

#### Scenario: Adoption refuses a shared output
- **WHEN** `adopt-renders` runs over two colliding events and the shared output file exists
- **THEN** no manifest is written for either event (one file cannot be adopted as both movies), both are
  reported as colliding, and the command exits non-zero

### Requirement: Default output directory sits outside the project root

When neither `-o/--output` nor `config.yaml`'s `output` is set, the output directory SHALL default to
the sibling folder `<parent>/<root-name>-output` of the project root (for example, project root
`/mnt/MOL/videos/sorted` → `/mnt/MOL/videos/sorted-output`). It MUST NOT default to a path inside the
project root: the ingest layouts walk the project root's subfolders, so rendered movies filed into year
folders there would be scanned back in as events. `render`, `scan`, `enqueue`, `adopt-renders`, the worker
and the API service SHALL all resolve the same default. An explicitly configured output directory is used
as given, even when it lies inside the project root.

#### Scenario: Default output is a sibling of the project root
- **WHEN** `render /data/videos/sorted` runs with no `-o` and no `output` in `config.yaml`
- **THEN** movies are written under `/data/videos/sorted-output/`, and nothing is created inside
  `/data/videos/sorted/` except event sidecars

#### Scenario: Rendered year folders are never scanned as events
- **WHEN** `render` has written `sorted-output/2024/Midsommar.mp4` using the default output directory and
  `scan` then runs over the same project root
- **THEN** no event named `2024` or containing `Midsommar.mp4` is reported

#### Scenario: Explicit output is honored
- **WHEN** `render <root> -o <root>/out` runs
- **THEN** movies are written under `<root>/out/` as given
