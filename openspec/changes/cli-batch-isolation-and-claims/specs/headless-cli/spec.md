## MODIFIED Requirements

### Requirement: `scan`/`list` reports inventory without rendering

The `scan` subcommand SHALL report, per selected event, its clips and their reconcile
classification (`NEW`/`ACTIVE`/`IGNORED`/`MISSING`) and its staleness verdict — fresh, or stale with the
changed components as reasons — without running any render or ffmpeg encode. An event whose folder or
`reel.yaml` cannot be read for lack of permission SHALL be reported as an `ERROR` for that event, naming the folder and the permission failure. It
MUST NOT be listed as an empty or folder-seeded event, and it MUST NOT end the command: the remaining events
are still listed and the command exits non-zero. Whether a `reel.yaml` exists SHALL be decided by the disk
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

#### Scenario: An event folder that cannot be searched is an error row
- **WHEN** `scan` runs over three events and one is a folder with mode `0600` (names listable, nothing
  inside it can be looked up) holding a `reel.yaml` titled `Real` and `a.mp4`
- **THEN** that event is reported as `ERROR` naming the permission failure, it is not listed with the
  folder-name title or as an event with no clips, the other two are listed, and the command exits non-zero

#### Scenario: An event folder that cannot be listed is an error row
- **WHEN** `scan` runs over a project and one event folder has mode `0300` and holds a `reel.yaml`
- **THEN** that event is reported as `ERROR` naming the permission failure rather than ending the command
  with a traceback, the other events are listed, and the command exits non-zero

### Requirement: `import` adopts auto-reel legacy metadata

The `import` subcommand SHALL read an auto-reel legacy `reel.yaml`/`metadata.yaml` via
`import_legacy` and produce a v2 `reel.yaml`, reporting what was imported.

`import` SHALL isolate failures per event. An event whose legacy file (or whose `reel.yaml`, when it is the
legacy source or must be checked for a `version` key) cannot be read, is not valid UTF-8, is not valid YAML,
is not a mapping, cannot be imported by `import_legacy`, or whose `reel.yaml` cannot be written, SHALL be
reported as `ERROR <event>: <reason>`. `import` SHALL then continue with the remaining events. A failed
event keeps whatever `reel.yaml` it had (the write is atomic). `import` SHALL print its final count line
even when events failed, stating how many failed, and SHALL exit non-zero when any event failed. Skipping an event
(no legacy source, or a v2 `reel.yaml` without `--overwrite`) is not a failure. Whether an event's
`metadata.yaml` or `reel.yaml` exists SHALL be decided by the disk answering: a lookup the disk refused is
that event's `ERROR`, not "no such file".

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
