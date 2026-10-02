# headless-cli Specification

## Purpose

Provide a headless `auto-reel` command-line entry point that drives the engine end to end. The CLI exposes `render`, `scan` (alias `list`), `analyze`, `import`, and `serve` subcommands, isolating per-event failures, reporting inventory without rendering, seeding and adopting clips through a defined NEW-clip policy, surfacing analysis suggestions without mutating `reel.yaml`, importing legacy auto-reel metadata into the v2 document format, and running the API service.

## Requirements

### Requirement: `auto-reel` entry point with subcommands

The system SHALL install a `console_scripts` entry point named `auto-reel` exposing the
subcommands `render`, `scan` (alias `list`), `analyze`, `import`, `enqueue`, `worker`, `jobs`, `serve`,
`adopt-renders`, and `thumbs`. Invalid arguments or an unknown subcommand SHALL produce a non-zero exit and
a usage message.

#### Scenario: Entry point is installed

- **WHEN** the package is installed and `auto-reel --help` is run
- **THEN** the ten subcommands are listed and the command exits zero

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
changed components as reasons — without running any render or ffmpeg encode. When the verdict cites `output_renamed`, the `stale:` line SHALL follow that reason with the movie file it found and the movie file the next render writes, each quoted: ``output_renamed (was '<previous movie>', now '<expected output>')``. The file names are those the verdict carries, without folder parts, and the whole `stale:` line stays on one line. A stale verdict that does not cite `output_renamed` prints its reasons exactly as before, and a fresh one prints `fresh`.

An event whose folder or
`reel.yaml` cannot be read for lack of permission SHALL be reported as an `ERROR` for that event, naming
the folder and the permission failure. It MUST NOT be listed as an empty or folder-seeded event, and it
MUST NOT end the command: the remaining
events are still listed and the command exits non-zero. Whether a `reel.yaml` exists SHALL be decided by the disk
answering, never by a lookup the disk refused.

#### Scenario: Scan lists events and clip status

- **WHEN** `scan` runs over a project
- **THEN** it prints each event with its clips classified, and writes no output files

#### Scenario: Missing referenced clip is surfaced

- **WHEN** an event's `reel.yaml` references a clip absent from disk
- **THEN** `scan` reports that clip as `MISSING`

#### Scenario: Staleness is reported with reasons

- **WHEN** `scan` runs over one fresh event and one event whose clips changed since its last render
- **THEN** the first is reported fresh and the second stale citing the clip-set component

#### Scenario: A renamed event's old and new movie files are named
- **WHEN** `scan` runs over `2024-06-27 - Grillning med grannar`, rendered as
  `2024-06-27 - Grillning med Grannar.mp4` and then retitled `Grillkväll med grannarna`
- **THEN** it prints `stale: editorial, output_renamed (was '2024-06-27 - Grillning med Grannar.mp4', now
  '2024-06-27 - Grillkväll med grannarna.mp4')` for that event
- **AND** it renders nothing and writes no file

#### Scenario: A deleted movie is not reported as renamed
- **WHEN** `scan` runs over an otherwise fresh event whose rendered movie was deleted with no edit
- **THEN** it prints `stale: output`, with no file names

#### Scenario: An event folder that cannot be searched is an error row
- **WHEN** `scan` runs over three events and one is a folder with mode `0600` (names listable, nothing
  inside it can be looked up) holding a `reel.yaml` titled `Real` and `a.mp4`
- **THEN** that event is reported as `ERROR` naming the permission failure, it is not listed with the
  folder-name title or as an event with no clips, the other two are listed, and the command exits non-zero

#### Scenario: An event folder that cannot be listed is an error row
- **WHEN** `scan` runs over a project and one event folder has mode `0300` and holds a `reel.yaml`
- **THEN** that event is reported as `ERROR` naming the permission failure rather than ending the command
  with a traceback, the other events are listed, and the command exits non-zero

### Requirement: NEW-clip adoption policy

When an event directory has no `reel.yaml`, the system SHALL seed one from disk structure. When an
event has a `reel.yaml` and disk contains `NEW` clips, `render` SHALL adopt every `NEW` clip so an added
clip is not silently dropped, while `MISSING` clips SHALL be reported loudly and never silently removed
from the document. A render that the job-scheduler worker runs, such as the one the GUI's Render starts,
SHALL adopt exactly as `render` does.

Each `NEW` clip SHALL be adopted into the chapter named after the folder it was found in. A clip in the
event folder itself goes into the default chapter. A clip in a chapter subfolder goes into the chapter with
that subfolder's name. When `reel.yaml` names no chapter of that name, the clip SHALL be adopted into the
default chapter instead. When `reel.yaml` does not name the default chapter and a clip enters it, the
default chapter SHALL be added after the chapters `reel.yaml` names.

A `reel.yaml` that names no chapters at all SHALL be adopted into as first discovery seeds a new event.
Each `NEW` clip SHALL enter the chapter named after its folder, the default chapter for the event folder's
clips. Those chapters SHALL be added in seeding order: the default chapter first, then the subfolders'
chapters by name. The result SHALL be the chapters and clip order that seeding the same event would write
under the same sort rule.

Apart from these, adoption SHALL NOT create any chapter. It SHALL NOT move, remove or re-order a clip that
`reel.yaml` already lists, wherever an earlier adoption or a hand edit put it. The adoption target is set by
this rule alone and is not configurable.

The clips entering one chapter SHALL be appended after the clips that chapter already lists. Among
themselves they SHALL be in the sort rule's order (event-reconcile, "Clips enter a document in the
configured sort order"), whichever folders they came from.

#### Scenario: First scan seeds a document

- **WHEN** `render` runs on an event with no `reel.yaml`
- **THEN** a document is seeded from folder structure and the event renders

#### Scenario: Newly added clip is adopted, not dropped

- **WHEN** an event's `reel.yaml` lists `s1710001.mp4` in its default chapter, and `s1710002.mp4` appears in
  the event folder
- **THEN** `render` appends `s1710002.mp4` to the default chapter and includes it in the output

#### Scenario: A new clip joins its folder's chapter

- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `s1710001.mp4` in its default chapter
  and `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` in `Kvällen`, and `Kvällen/s1710004.mp4` appears on
  disk
- **THEN** after `render`, `reel.yaml` lists `Kvällen` as `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4`,
  `Kvällen/s1710004.mp4` and the default chapter as `s1710001.mp4` alone, and the movie's `Kvällen` chapter
  plays the three clips

#### Scenario: A folder without a chapter falls back to the default chapter

- **WHEN** an event's `reel.yaml` names only the default chapter, listing `s1710001.mp4`, and
  `Dag 2/s1710002.mp4` and `Dag 2/s1710003.mp4` appear on disk
- **THEN** `render` appends both to the default chapter after `s1710001.mp4`, in the sort rule's order, and
  `reel.yaml` names no `Dag 2` chapter

#### Scenario: Clips from two folders entering one chapter are ordered together

- **WHEN** the sort rule is `datetime`, and an event's `reel.yaml` names only `Kvällen`, listing
  `Kvällen/a.mp4`. Then `b.mp4` (modified 12:00) appears in the event folder and `Dag 2/c.mp4` (modified
  11:00) in a folder with no chapter.
- **THEN** `render` adds the default chapter after `Kvällen`, listing `Dag 2/c.mp4` then `b.mp4`, and leaves
  `Kvällen` as `Kvällen/a.mp4` alone

#### Scenario: A document that names no chapters is seeded like a new event

- **WHEN** an event's `reel.yaml` holds only `metadata`, as `import` writes a legacy document or as a
  metadata-only first save from the GUI writes it, and the event holds `s1710001.mp4` in its folder and
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4` in a subfolder
- **THEN** `render` writes the default chapter listing `s1710001.mp4`, then a `Kvällen` chapter listing
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4` in the sort rule's order, which are the chapters a first
  render of the event without a `reel.yaml` seeds, and the movie has both chapters
- **AND** `reel.yaml` keeps its `metadata` as written

#### Scenario: A clip adopted earlier stays where it is

- **WHEN** an event's `reel.yaml` lists `Kvällen/s1710004.mp4` in its default chapter, as an earlier
  render's adoption left it, while its `Kvällen` chapter lists `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, and no clip is NEW
- **THEN** `render` adopts nothing and does not rewrite `reel.yaml`, and `Kvällen/s1710004.mp4` still plays in
  the default chapter

#### Scenario: A GUI render adopts as the CLI does

- **WHEN** the operator presses Render on `2024-08-20 - Två kapitel - Tjörn` while `Kvällen/s1710004.mp4` is
  NEW, and the worker runs the job
- **THEN** the worker writes the `reel.yaml` that `render` would write, with `Kvällen/s1710004.mp4` third in
  `Kvällen`

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

`import` SHALL isolate failures per event. An event whose legacy file (or whose `reel.yaml`, when it is the
legacy source or must be checked for a `version` key) cannot be read, is not valid UTF-8, is not valid YAML,
is not a mapping, cannot be imported by `import_legacy`, or whose `reel.yaml` cannot be written, SHALL be
reported as `ERROR <event>: <reason>`. `import` SHALL then continue with the remaining events. A failed
event keeps whatever `reel.yaml` it had (the write is atomic). `import` SHALL print its final count line
even when events failed, stating how many failed, and SHALL exit non-zero when any event failed. Skipping an
event (no legacy source, or a v2 `reel.yaml` without `--overwrite`) is not a failure. Whether an event's
`metadata.yaml` or `reel.yaml` exists SHALL be decided by the disk answering: a lookup the disk refused is
that event's `ERROR`, not "no such file". The `ERROR` reason SHALL be one line naming the file.

#### Scenario: Legacy metadata imported to v2

- **WHEN** `import` runs against a legacy event
- **THEN** a v2 `reel.yaml` is produced carrying the legacy metadata/title/sort fields

#### Scenario: A non-UTF-8 metadata file fails only its event
- **WHEN** `import` runs over three legacy events and the middle one's `metadata.yaml` is not valid UTF-8
- **THEN** the first and third get a v2 `reel.yaml` and print `OK`, the middle one prints `ERROR` naming the
  decode failure and gets no `reel.yaml`, the count line reports two imported and one failed, and the
  command exits non-zero

#### Scenario: Malformed YAML and a non-mapping file fail only their events
- **WHEN** `import` runs over a legacy event with malformed YAML, one whose `metadata.yaml` is a list, and a
  valid one, in that order
- **THEN** the first two are each reported as `ERROR` with their own reason, the valid one is imported, and
  the command exits non-zero

#### Scenario: A malformed reel.yaml is that event's error
- **WHEN** an event has no `metadata.yaml` and a `reel.yaml` that is malformed YAML, and `import` runs
- **THEN** the event is reported as `ERROR` naming the parse failure, nothing is written for it, and the
  events after it are still imported

#### Scenario: An empty or non-mapping reel.yaml beside a metadata.yaml is not an error

- **WHEN** an event has a valid `metadata.yaml` and a `reel.yaml` that is empty or whose root is not a
  mapping, and `import` runs with or without `--overwrite`
- **THEN** the `reel.yaml` is treated as having no `version` key, the event is imported from
  `metadata.yaml`, and the command exits zero

#### Scenario: A skipped event does not fail the command
- **WHEN** `import` runs over one legacy event and one event with a v2 `reel.yaml` and no `--overwrite`
- **THEN** the second prints `SKIP`, the first is imported, and the command exits zero

### Requirement: `enqueue` records jobs without rendering

`auto-reel enqueue` SHALL scan the project via the configured ingest layout (honoring `--years` and
`--device`), apply the staleness gate, and insert one `queued` job per **stale** selected event — storing
the root-relative event identity, the project root, the event's fingerprint, and the force flag. Fresh
events SHALL be reported as fresh and not enqueued unless `--force` is given, which enqueues them all with
`force` set. It MUST NOT probe, render, or block on job completion, and it SHALL report per event whether
a job was created, an active job already existed (idempotent enqueue), or the event was fresh. Whether a job
was created SHALL be the insertion's own outcome as the job store reports it, never a lookup made before the
insert, and the count of newly queued jobs SHALL be the number of events whose insertion created a row.

#### Scenario: Only stale events become queued jobs
- **WHEN** `auto-reel enqueue` runs against one stale and one fresh event
- **THEN** one `queued` job exists for the stale event and the fresh event is reported fresh with no job

#### Scenario: Force enqueues fresh events
- **WHEN** `auto-reel enqueue --force` runs against fresh events
- **THEN** each gets a `queued` job with its `force` flag set

#### Scenario: Re-running enqueue creates no duplicates
- **WHEN** `auto-reel enqueue` runs twice for the same stale events
- **THEN** the second run inserts no new jobs and reports the existing active jobs

#### Scenario: The report follows the insertion, not an earlier read
- **WHEN** an event is stale, no active job is visible when `enqueue` starts, and the insert finds that an
  active job for the event already exists (a concurrent `enqueue` won the race)
- **THEN** the event is reported as already queued/running with that job's id, it is not counted as newly
  queued, and no second row exists

#### Scenario: A job created is reported and counted as created
- **WHEN** `enqueue` inserts a job for a stale event
- **THEN** the event is reported as queued with the new job's id and counted once in the newly queued total

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

When one SIGINT or one SIGTERM has stopped the service and its orderly shutdown has completed, the command
SHALL exit with status 0 and SHALL NOT end with a traceback. This SHALL hold whichever of the two signals
stopped it, with or without WebSocket clients connected, and whether it runs in a terminal (Ctrl-C) or under
a supervisor that sends SIGTERM. A further SIGTERM while the shutdown is still running SHALL NOT change the
outcome. Once the service has finished its shutdown, a further SIGINT or SIGTERM that arrives while the
command exits SHALL NOT change it either.

The orderly shutdown waits for the request handlers that are still running. A SIGINT that arrives while the
shutdown is still running, whichever signal started it, is the operator's force-quit: the service stops
waiting for those handlers, including one blocked in a worker thread (any synchronous route, for example on
a stalled database), which the command abandons when it exits instead of waiting for it to return. uvicorn's
application shutdown step is skipped if it has not started yet, so the log has no "Application shutdown
complete". The application's own cleanup (the WebSocket poller stopped, the database connections released)
still runs, when its lifespan is cancelled as the service exits, and the command waits for it. The force
also ends the service's client connections: every connection still open is dropped at once, without waiting
for it to close, so none holds the command running, including one whose client sent only part of a request
and one whose peer stopped reading with frames backed up for it (api-service, "WebSocket live job
updates"). The command SHALL then exit with status 130, never 0, so that a forced stop is not reported as a
clean one, within a few seconds of the force, and it SHALL NOT end with a `KeyboardInterrupt` traceback of its
own, however many further SIGINTs arrived. A request handler that the forced stop cancels, and the application
lifespan, cancelled at exit or interrupted by a further SIGINT while its cleanup still waits, MAY still be
logged as errors with their tracebacks.

When the application's lifespan fails, the command SHALL NOT exit with status 0 and SHALL NOT report the
failure only in its log: an application shutdown that failed after one SIGINT or SIGTERM, or an application
startup that failed, makes the command exit with status 1. uvicorn logs the failure, the traceback and
"Application shutdown failed. Exiting." or "Application startup failed. Exiting."; after a failed shutdown it
returns normally, after a failed startup it exits through `SystemExit`, and neither is allowed to decide the
status. A forced stop skips the application shutdown and keeps status 130.

#### Scenario: Serve starts and answers
- **WHEN** `auto-reel serve` runs against a project root and a reachable database
- **THEN** `GET /healthz` on the configured host/port returns success

#### Scenario: Flags override config
- **WHEN** `config.yaml` sets `api.port: 8080` and `auto-reel serve --port 9000` is run
- **THEN** the service binds port 9000

#### Scenario: Bind failure is loud
- **WHEN** the configured port is already in use
- **THEN** the command exits non-zero naming the attempted host:port

#### Scenario: One Ctrl-C stops serve with exit zero
- **WHEN** `auto-reel serve` runs in a terminal, a GUI tab showing the event list holds its jobs WebSocket
  open, and the operator presses Ctrl-C once
- **THEN** the tab's connection is closed with code 1012 and the service logs "Application shutdown complete"
- **AND** the command exits with status 0, and its output holds no traceback

#### Scenario: One SIGTERM stops serve with exit zero
- **WHEN** `podman stop` sends one SIGTERM to a running `auto-reel serve` with a WebSocket client connected
- **THEN** the client's connection is closed with code 1012, the service completes its orderly shutdown, and
  the command exits with status 0 without a traceback

#### Scenario: A second Ctrl-C forces the exit and reports it
- **WHEN** one Ctrl-C has started the shutdown of `auto-reel serve`, the shutdown is still waiting for a
  request handler that keeps running after its client left, and the operator presses Ctrl-C again
- **THEN** the service stops waiting without uvicorn's application shutdown step, so its log has no
  "Application shutdown complete"
- **AND** the command exits with status 130 and does not end with a `KeyboardInterrupt` traceback

#### Scenario: A forced stop does not wait for a handler blocked in a worker thread
- **WHEN** a `GET /healthz` is blocked in a worker thread on a database that accepts the connection and
  never answers, its client has given up, one Ctrl-C has started the shutdown of `auto-reel serve`, and
  the operator presses Ctrl-C twice more
- **THEN** the command exits with status 130 within a few seconds of the second Ctrl-C, while that handler
  is still blocked
- **AND** its output holds no `KeyboardInterrupt` traceback

#### Scenario: A forced stop does not wait for a client that holds its request open
- **WHEN** a client has sent the headers of a `POST /api/v1/jobs` announcing a body and only part of it, and
  keeps the connection open, one Ctrl-C has started the shutdown of `auto-reel serve` (which logs "Waiting for
  connections to close"), and the operator presses Ctrl-C again
- **THEN** the command exits with status 130 within a few seconds of the second Ctrl-C, while the client
  still holds the connection open
- **AND** its output holds no `KeyboardInterrupt` traceback and no "Application shutdown complete"

#### Scenario: A forced stop does not wait for a peer that stopped reading
- **WHEN** a client has requested a response larger than the host's socket buffers and reads none of it, one
  Ctrl-C has started the shutdown of `auto-reel serve`, and the operator presses Ctrl-C again
- **THEN** the command exits with status 130 within a few seconds of the second Ctrl-C, while the client has
  not closed the connection

#### Scenario: A failed application shutdown does not exit zero
- **WHEN** the application's lifespan raises while `auto-reel serve` shuts down after one SIGTERM, or, in a
  second run, one SIGINT
- **THEN** the log holds "Application shutdown failed" and the traceback
- **AND** the command exits with status 1, not 0

#### Scenario: A failed application startup does not exit zero
- **WHEN** the application's lifespan raises while `auto-reel serve` starts
- **THEN** the command exits with status 1, not 0
- **AND** it names the failed application startup, not a failure to bind the port

#### Scenario: A late signal does not change the exit status
- **WHEN** one SIGTERM or one Ctrl-C has stopped `auto-reel serve` and its orderly shutdown has completed,
  and a further SIGINT or SIGTERM arrives while the command exits
- **THEN** the command still exits with status 0, and its output holds no traceback

### Requirement: Batch commands refuse colliding output paths

Before acting, `render`, `enqueue` and `adopt-renders` SHALL check the events they selected: every event,
fresh or stale, forced or not, whether or not it is a dry run. Any two or more events that resolve to the
same output path SHALL be treated as a **collision**. Paths SHALL be compared case-insensitively, so a
collision that a case-insensitive archive filesystem would create is caught even on a case-sensitive host.
Because a dated event's file name begins with its date, a collision needs two events with the same date,
title and location. An event without a real date never reaches the check: it fails on its own first and
cannot claim a path.

Which events claim a path SHALL be decided by one rule, whichever surface checks. An event claims the output
path its resolved metadata gives it only when it can be loaded and is processable ("An event without a real
date and title fails on its own"). An event that fails in any other way, such as an unparseable `reel.yaml` or
a folder or file the process is not permitted to list or read, SHALL claim no path and SHALL fail on its own
with its reason. Such a failure MUST NOT abort the command and MUST NOT stop the collision check of any other
event. The same rule SHALL apply to the other surfaces that check for collisions: `POST /api/v1/jobs` and the
worker's claim-time recheck.

Every event in a collision SHALL be reported as an error. The report SHALL name the shared output path and
the other events that claim it. For these events the command MUST NOT render, enqueue, adopt, or overwrite
anything; an output file that already exists at the shared path SHALL be left untouched. Events outside
any collision SHALL proceed normally (per-event isolation). A command that reported at least one
collision SHALL exit non-zero. A collision SHALL NOT be resolved automatically by renaming, suffixing or
skipping one side. The operator resolves it by changing an event's `title` or `location` in `reel.yaml`.

The check covers only the events the command selected (for example, only the years named by `--years`).
Events outside the selection are not examined.

#### Scenario: Two same-titled events in one year collide
- **WHEN** `render` runs over events `2024/2024-06-21 - Midsommar` and `2024/2024-06-21 - midsommar`, both
  dated `2024-06-21` with title `Midsommar` and no location, plus a third, uniquely named 2024 event
- **THEN** both Midsommar events are reported as errors naming `2024/2024-06-21 - Midsommar.mp4` and each
  other, neither is rendered, the third event renders normally, and the command exits non-zero

#### Scenario: A fresh event's output is protected from a new same-named event
- **WHEN** a fresh event already owns `<output>/2024/2024-06-21 - Midsommar.mp4`, and a newly added event
  also resolves to date `2024-06-21` and title `Midsommar`
- **THEN** `render` reports both as colliding, the existing movie is byte-for-byte unchanged, and no
  manifest is written for either event

#### Scenario: Collision differing only in letter case
- **WHEN** two events resolve to `2024/2024-06-21 - Midsommar.mp4` and `2024/2024-06-21 - midsommar.mp4`
- **THEN** they are reported as a collision

#### Scenario: Same title in different years is not a collision
- **WHEN** events dated 2023 and 2024 both have title `Midsommar`
- **THEN** no collision is reported and both render to their own year folder

#### Scenario: Same title on different dates is not a collision
- **WHEN** events dated `2024-06-21` and `2024-06-22` both have title `Midsommar` and no location
- **THEN** no collision is reported and both render, each under its own date-prefixed name

#### Scenario: Two reel.yaml events with the same date and title collide
- **WHEN** event folders `2024/a` and `2024/b` each hold a `reel.yaml` with title `Blandat`, date
  `2024-11-02` and no location
- **THEN** both are reported as colliding on `2024/2024-11-02 - Blandat.mp4`

#### Scenario: Two undated events with the same title collide
- **WHEN** two events with folder name `Blandat` and no `reel.yaml` date are selected
- **THEN** no collision is reported: each fails on its own as an error for having no date, and neither
  claims an output path

#### Scenario: An unreadable sibling claims nothing and does not stop the check
- **WHEN** `render` runs over `2024/2024-06-21 - Midsommar`, `2024/2024-06-21 - midsommar` and
  `2024/2024-06-21 - Fest`, where the `Fest` folder has no `reel.yaml` and its permissions are `000`
- **THEN** `2024-06-21 - Fest` is reported as `ERROR` with the operating system's reason (permission denied)
  and no traceback, it claims no path, and the two Midsommar events are still reported as colliding with each
  other
- **AND** the command exits non-zero

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
and the API service SHALL all resolve the same default. An explicitly configured output directory (`-o/--output` or
`config.yaml`'s `output`) is used as given, unless it equals or lies inside the directory the layout walks, which every
command that walks a project, and `serve`, refuses (capability `project-config`, requirement "The output directory never lies inside the
walked root"): the command prints `error: output directory <output> is inside the walked root <root>;
choose a folder outside it, for example <root>-output`, exits non-zero, and walks, renders and writes
nothing. An output that lies inside the project root but outside a distinct `input` directory is
honoured.

#### Scenario: Default output is a sibling of the project root
- **WHEN** `render /data/videos/sorted` runs with no `-o` and no `output` in `config.yaml`
- **THEN** movies are written under `/data/videos/sorted-output/`, and nothing is created inside
  `/data/videos/sorted/` except event sidecars

#### Scenario: Rendered year folders are never scanned as events
- **WHEN** `render` has written `sorted-output/2024/Midsommar.mp4` using the default output directory and
  `scan` then runs over the same project root
- **THEN** no event named `2024` or containing `Midsommar.mp4` is reported

#### Scenario: Explicit output is honored
- **WHEN** `render <root> -o <root>-movies` runs
- **THEN** movies are written under `<root>-movies/` as given

#### Scenario: Explicit output inside the walked root is refused
- **WHEN** `render <root> -o <root>/out` runs, with `<root>/2024/2024-07-20 - A/a.mp4` and an earlier
  `<root>/out/2024/2024-07-20 - A.mp4`
- **THEN** the command prints the error above to stderr and exits 1, no event is enumerated (so no
  `ERROR  2024: no date: folder name has a year only (2024)` line for the output's year folder appears),
  and no file is written under `<root>`

#### Scenario: Scan refuses the same output
- **WHEN** `scan <root> -o <root>/out` runs with `--layout flat`
- **THEN** it exits 1 with the same error, and `out` is never listed as an event

#### Scenario: The output equals the walked root
- **WHEN** `render <root> -o <root>` runs
- **THEN** it exits 1 with the error naming both paths

#### Scenario: Output inside the project root but outside the input directory
- **WHEN** `config.yaml` sets `input: media` and `render <root> -o <root>/out` runs
- **THEN** the walk root is `<root>/media`, the output is allowed, and movies are written under
  `<root>/out/`

### Requirement: adopt-renders previews without writing

`auto-reel adopt-renders` SHALL accept `--dry-run`. In dry-run mode it SHALL evaluate every selected event
exactly as a real run does, including the collision check and the staleness verdict, and report the
same outcome for each event: that it would be adopted, is already fresh, is unrendered (no output at its
derived path) or collides. It SHALL print the same totals and exit with the same code a real run would.
It MUST NOT write a manifest, create a directory, or change any file. Its output SHALL mark the run as a
dry run, so a preview is never mistaken for a completed adoption.

#### Scenario: Previewing adoption of a legacy archive
- **WHEN** `adopt-renders --dry-run` runs over an archive where three events have outputs at their derived
  paths and one does not
- **THEN** it reports three events it would adopt and one unrendered event, writes no manifest, and a
  following real `adopt-renders` adopts exactly those three

#### Scenario: A dry run leaves the archive untouched
- **WHEN** `adopt-renders --dry-run` runs over a read-only mounted archive
- **THEN** it completes without any write error, because it attempts no write

#### Scenario: A dry run still reports collisions
- **WHEN** `adopt-renders --dry-run` runs over two colliding events
- **THEN** both are reported as colliding, and the command exits non-zero as a real run would

### Requirement: An event without a real date and title fails on its own

An event SHALL be processable only when its resolved metadata has a real date and a title, and when that
date is not after the current day. When one of these fails, the event SHALL be reported as an error that
names the event, the reason and the fix. The reason is the folder name's stated problem when the date or
title was expected from the folder: an impossible date, a year only, no date, or no title. It can also be a
date in the future. The fix is to set the field in `reel.yaml` or to correct the folder name. An event
whose `reel.yaml` cannot be parsed SHALL be reported the same way, and so SHALL an event whose folder or
`reel.yaml` the process cannot list or read (permission denied, or another operating-system error): the reason
is the operating system's, and no traceback is printed.

`scan`, `render`, `enqueue` and `adopt-renders` SHALL isolate these errors per event. They SHALL:

- print `ERROR <event>: <reason>`
- process no further step for that event (no render, no job row, no manifest)
- continue with the remaining events
- exit non-zero when any event failed

No such error SHALL abort the whole command. A worker that claims a job for such an event SHALL fail that job
with the same reason. The service's events reads SHALL report it through their existing per-event problem
body.

#### Scenario: An impossible folder date fails only its event
- **WHEN** `render` runs over a year containing `2019-04-31 - Golfträning med Emil - Tjörn`, with no
  `reel.yaml`, and two valid events
- **THEN** the Golfträning event is reported as `ERROR` naming `2019-04-31` as not a real date and suggesting
  `metadata.date` in `reel.yaml`, both valid events render, and the command exits non-zero

#### Scenario: A year-only folder fails until reel.yaml supplies the date
- **WHEN** `scan` runs over `2004/2004 - Yngve berättar om skövde` with no `reel.yaml`
- **THEN** the event is reported as `ERROR` stating the folder name has a year only; and after
  `metadata.date: 2004-05-01` is added to its `reel.yaml`, the next `scan` lists it normally

#### Scenario: A future date is rejected
- **WHEN** an event resolves to a date after today
- **THEN** it is reported as `ERROR` naming the date as in the future

#### Scenario: A malformed reel.yaml no longer aborts the batch
- **WHEN** `scan` runs over three events and one has an unparseable `reel.yaml`
- **THEN** that event is reported as `ERROR` with the parse failure, the other two are listed, and the
  command exits non-zero

#### Scenario: An unreadable event folder fails only its event
- **WHEN** `scan` runs over three events and one is a folder with no `reel.yaml` whose permissions are `000`
- **THEN** that event is reported as `ERROR` with the permission-denied reason and no traceback, the other two
  are listed, and the command exits non-zero

#### Scenario: A failing event never reaches adoption
- **WHEN** `adopt-renders --dry-run` runs over an archive containing the three bad folder names
- **THEN** they are reported as `ERROR`, not as claimants of a shared `Untitled.mp4`, and every other event is
  evaluated as before

### Requirement: `thumbs` fills the thumbnail cache without touching the library

The `thumbs` subcommand SHALL walk the project with the resolved layout, like `scan`. It SHALL honour
`--years`, `--layout` and `.reelignore`. For every clip that discovery lists on disk in each event, it
SHALL generate the clip's thumbnail (capability `clip-thumbnails`) unless that thumbnail is already cached.
The clips it covers:

- root clips and chapter-subfolder clips
- IGNORED clips included
- not the `original/` debris, and not a `.reelignore`d chapter folder, which discovery already excludes

`thumbs` SHALL NOT read or write `reel.yaml`, so a MISSING clip, which is not on disk, is never requested.
It SHALL NOT require an event to have a real date or title.

It SHALL run at most `--jobs N` extractions at once. `N` is a positive integer with a default of `2`; any
other value SHALL be a usage error. It SHALL print, in walk order:

- one line per event, with its generated, cached and failed counts. Those counts add up to the event's
  clips, and a thumbnail file counts as generated at most once per event. Clips whose thumbnail is one file,
  such as several symlinks to one clip in an event, SHALL cause one extraction. The first of them in the
  event's listing order SHALL count as generated, and the others as cached.
- exactly one `ERROR  <event>/<clip>: <cause>` line per clip that failed, naming the clip once: the cause
  does not repeat its path or quote the failing command, and a file name that is not valid UTF-8 is
  printed with its raw bytes escaped; the failing command and its stderr are logged at debug level
- a final summary with the totals and the cache directory

A clip that fails SHALL NOT stop the run. Nor SHALL an event whose folder cannot be listed; that event is
reported as `ERROR  <event>: <reason>`. When clips that share one thumbnail file fail, each of them SHALL get
its own `ERROR` line and count as failed, and the extraction SHALL still have been attempted only once.

The command SHALL exit `0` when nothing failed, and non-zero when any clip or event failed. A cache
directory that cannot be created or written, and an invalid `thumbnails` setting, SHALL each stop the run.
The command SHALL then print one error naming the directory or the key, and exit non-zero.

`thumbs` SHALL write only into the thumbnail cache directory: no file under the project root is created or
modified. It SHALL therefore work on a library mounted read-only. An interrupted run (Ctrl-C) SHALL start
no further extraction and SHALL leave no partial thumbnail behind.

#### Scenario: Filling the cache for the dev library
- **WHEN** `auto-reel thumbs` runs for the first time over the dev library
- **THEN** every other clip on disk has a thumbnail afterwards. A clip symlinked into an earlier event, or
  twice into one event, is counted as cached.
- **AND** exactly one `ERROR` line is printed, for `2024-10-05 - Trasig/trasig.mp4`, whose file is zero
  bytes
- **AND** the summary counts that clip as failed, and the command exits non-zero

#### Scenario: Two links to one clip in one event are extracted once
- **WHEN** `thumbs` reaches `2024-09-14 - Kräftskiva`, which holds only the root `s1710004.mp4` and
  `Kvällen/s1710004.mp4`, both symlinks to one clip, and neither has a cached thumbnail
- **THEN** ffmpeg runs once for that clip
- **AND** the event's line reads `2024-09-14 - Kräftskiva: 2 clips, 1 generated, 1 cached`
- **AND** exactly one thumbnail file for it exists in the cache directory

#### Scenario: Two links to a broken clip fail as two clips from one attempt
- **WHEN** `thumbs` reaches an event holding `a.mp4` and a symlink `b.mp4` to the same zero-byte file
- **THEN** one `ERROR` line is printed for `a.mp4` and one for `b.mp4`, the event's line reads
  `2 clips, 2 failed`, and ffprobe ran once for that file

#### Scenario: A MISSING clip is never requested
- **WHEN** `thumbs` reaches `2024-09-01 - Sommarlov`, whose `reel.yaml` lists `s1710002.mp4`, `s1710004.mp4`
  and `borttagen.mp4  # MISSING`, and only the first two are on disk
- **THEN** thumbnails exist for `s1710002.mp4` and `s1710004.mp4`
- **AND** nothing is requested and no line is printed for `borttagen.mp4`

#### Scenario: Chapter subfolders and IGNORED clips are covered
- **WHEN** `thumbs` reaches `2024-08-20 - Två kapitel - Tjörn`, which holds the root clips `s1710001.mp4` and
  `s1710004.mp4` (IGNORED in its `reel.yaml`) and the `Kvällen/` clips `s1710002.mp4`, `s1710003.mp4` and
  `s1710004.mp4`
- **THEN** each of those five clips has a thumbnail, and the event's line counts five clips

#### Scenario: Camera originals are skipped
- **WHEN** an event folder holds `s1710001.mp4` and `original/C0001.MTS`
- **THEN** only `s1710001.mp4` gets a thumbnail

#### Scenario: An event the render family refuses still gets thumbnails
- **WHEN** `thumbs` reaches `2024-02-30 - Omöjligt datum`, whose folder date is impossible
- **THEN** its clip's thumbnail is generated, and no `ERROR` line is printed for the event

#### Scenario: A second run generates nothing
- **WHEN** `thumbs` runs again over the dev library with no clip changed
- **THEN** every clip that succeeded before is counted as cached, no thumbnail is generated, and
  `2024-10-05 - Trasig/trasig.mp4` is reported as failed again

#### Scenario: The library is left untouched
- **WHEN** `thumbs` runs over the dev library
- **THEN** no file under the project root is created or modified, and every `reel.yaml` is byte-for-byte
  unchanged

#### Scenario: A read-only library
- **WHEN** `thumbs` runs over a library whose directories cannot be written, like the MOL drive mounted
  read-only, with the cache directory elsewhere
- **THEN** every readable clip gets its thumbnail, and no clip or event fails for lack of write access

#### Scenario: Ctrl-C stops the run
- **WHEN** the operator presses Ctrl-C while `thumbs` is extracting an event with many uncached clips
- **THEN** no clip still waiting in the queue is started, no temporary file or partial `<key>.jpg` remains,
  and the command exits non-zero

#### Scenario: An unwritable cache directory stops the run
- **WHEN** `config.yaml` sets `thumbnails: {cache_dir: /read-only/thumbs}`, which cannot be created
- **THEN** the command prints one error naming that directory and exits non-zero
- **AND** no per-clip `ERROR` lines are printed

#### Scenario: An invalid setting stops the run before any extraction
- **WHEN** `config.yaml` sets `thumbnails: {position: 1.5}`
- **THEN** the command prints a configuration error naming `thumbnails.position`, runs no ffmpeg, and exits
  non-zero

#### Scenario: A non-positive job count is a usage error
- **WHEN** `auto-reel thumbs <root> --jobs 0` is run
- **THEN** the command exits non-zero with a usage message and runs no ffmpeg

### Requirement: A referenced clip missing from disk fails its event by identity
Before it probes any clip, the build path shared by `render` and the worker SHALL check that every clip
the event's `reel.yaml` references and has not excluded is present in the event folder. When one or more are
absent, the event SHALL fail with one error that names every missing clip by its identity (its path
relative to the event folder), in the order `reel.yaml` lists them, and says how to fix it: restore the
file, or remove the clip from the event (in Edit mode or in `reel.yaml`). The error MUST NOT contain an
absolute path of the machine, and MUST NOT stop at the first missing clip. No ffprobe, no ffmpeg process, no
output and no manifest SHALL follow for that event. A clip that is excluded is not checked, and a clip that
is on disk but not listed is not affected. `render` SHALL report the failure as `ERROR <event>: <the error>`
for that event only, continue with the remaining events, and exit non-zero; a worker that claims a job for
such an event SHALL fail the job with the same text as the job error. `scan` keeps reporting the clip as
`MISSING`, and a `MISSING` clip is still never removed from `reel.yaml`.

#### Scenario: One missing clip is named with the fix
- **WHEN** `render` runs over an event whose `reel.yaml` lists `clip1.avi` and `borttagen.mp4`, and
  `borttagen.mp4` is not on disk
- **THEN** the event is reported as `ERROR` naming `borttagen.mp4` as listed in `reel.yaml` but missing and
  telling the user to restore it or remove it from the event, the text has no absolute path, nothing is
  rendered for it, and the command exits non-zero

#### Scenario: Every missing clip is listed at once
- **WHEN** an event lists `a.mp4`, `b.mp4`, `Dag 2/c.mp4` and `d.mp4`, and `b.mp4` and `Dag 2/c.mp4` are
  absent
- **THEN** one error names `b.mp4` and `Dag 2/c.mp4`, in that order, and not `a.mp4` or `d.mp4`

#### Scenario: An excluded missing clip is not an error
- **WHEN** a clip that `reel.yaml` marks `exclude: true` is absent from disk and every other clip is present
- **THEN** the event renders normally

#### Scenario: The job error is the same text
- **WHEN** a worker claims a job for the event with the missing `borttagen.mp4`
- **THEN** the job is `failed` and its error equals the text `render` printed for that event, with no
  `File does not exist` and no absolute path

#### Scenario: Other events in the batch still render
- **WHEN** `render` runs over three events and only one has a missing clip
- **THEN** the other two render, and the exit code reflects the one failure

#### Scenario: A broken symlink counts as missing
- **WHEN** a listed clip is a symlink whose target no longer exists
- **THEN** it is reported as missing with the others, not as a probe failure
