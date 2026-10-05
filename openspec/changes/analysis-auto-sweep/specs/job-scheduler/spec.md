## ADDED Requirements

### Requirement: The worker enqueues analysis for events that need it
While `worker.auto_analyze` is on, the worker SHALL run an automatic analysis sweep over its own project when it
starts and then every `worker.auto_analyze_interval` seconds until it stops. A sweep SHALL enqueue an `analysis` job
for an event when, and only when, a non-forced `analysis` job of that event would analyze at least one clip: a clip
with no analysis entry, or with an entry whose clip signal no longer matches the file (a new or changed clip). A clip
whose analysis failed for its current signal (it carries a failure marker for that signal) SHALL NOT make its event
due; it makes the event due again once the clip's signal changes, or after a forced analysis clears the marker. The
sweep and the `analysis` job SHALL decide which clips are due by the same rule, so that an event the job has just
brought up to date is never enqueued again by the next sweep. Jobs the sweep enqueues SHALL be ordinary,
non-forced `analysis` jobs: they are claimed, yield, report progress and can be canceled like any other.

#### Scenario: A never-analyzed event is enqueued
- **WHEN** the queue is empty and an event has clips but no analysis entries
- **THEN** the sweep enqueues one non-forced `analysis` job for that event

#### Scenario: A changed clip makes its event due again
- **WHEN** every clip of an event has a current analysis entry and then one clip file is replaced (its size or
  mtime changes), or a new clip is added to the event
- **THEN** the next sweep enqueues an `analysis` job for that event

#### Scenario: An up-to-date event is left alone
- **WHEN** every clip of an event has an analysis entry matching its current signal
- **THEN** the sweep enqueues nothing for that event

#### Scenario: A failed clip is not retried in a loop
- **WHEN** the only clip of an event without a current entry carries a failure marker for its current signal
- **THEN** the sweep enqueues nothing for that event, on this and every later sweep, until the clip changes or a
  forced analysis of the event runs

#### Scenario: The job and the sweep agree
- **WHEN** a sweep enqueues an event, its `analysis` job ends (`done`, or `failed` with failure markers for the
  clips that failed), and the next sweep runs with nothing changed on disk
- **THEN** the next sweep enqueues nothing for that event

### Requirement: The analysis sweep reads metadata only
A sweep SHALL decide from directory listings, file `stat` results, the analysis sidecar entries and job rows only.
It SHALL NOT run ffprobe or ffmpeg, SHALL NOT read clip contents (no content hash), SHALL NOT read or write
`reel.yaml`, and SHALL NOT write any file. It SHALL enumerate events with the project's configured layout and
input directory, as a render job's collision check does, so an event the layout skips (for example one under
`.reelignore`) is never enqueued.

#### Scenario: No probe or decode during a sweep
- **WHEN** a sweep runs over a project whose events are never analyzed, stale and up to date
- **THEN** no ffprobe or ffmpeg process is started and no file in the project changes; only job rows are added

#### Scenario: Ignored events are not enqueued
- **WHEN** an event folder holds a `.reelignore`, or lies outside the project's `input_dir`
- **THEN** the sweep never enqueues it

### Requirement: The analysis sweep is capped, newest first, and quiet while the queue is busy
A sweep SHALL enqueue nothing while any job of its project is `queued`, or a `render` or `proxy` job of its project
is `running`; a `running` `analysis` job alone does not stop it. Otherwise it SHALL visit the project's events
newest first (the reverse of the layout's walk order) and SHALL stop once it has enqueued
`worker.auto_analyze_max_events` new jobs. An event that already has an active (`queued` or `running`) `analysis`
job SHALL be skipped and SHALL NOT count toward that cap. Automatic jobs SHALL take no claim precedence over any
other job: renders and proxy jobs are claimed first by their kind.

#### Scenario: The first sweep over a large library trickles
- **WHEN** fifty events need analysis, the queue is empty and `auto_analyze_max_events` is the default `2`
- **THEN** the sweep enqueues the two newest of them and no other job, and the next two are enqueued only by a
  later sweep after those have been claimed

#### Scenario: A queued render keeps the sweep quiet
- **WHEN** a `render` job (or a `proxy` job, or any other job) of the project is `queued`, or a `render` or `proxy`
  job is `running`
- **THEN** the sweep enqueues nothing, whichever events need analysis

#### Scenario: A running analysis job does not count toward the cap
- **WHEN** an `analysis` job is running for the newest due event, nothing is queued, and two older events are due
- **THEN** the sweep skips the running event and enqueues the two older ones

### Requirement: The analysis sweep backs off after a canceled or failed analysis job
A sweep SHALL NOT enqueue an event whose latest `analysis` job ended `canceled` or `failed`, unless a clip file of
that event changed after the job started (its `stat` modification time or status-change time is later than the
job's start time, or its finish time for a job canceled before it started), so a clip copied in while the job ran,
which the job never listed, still counts. A newer `analysis` job of the event, such as a Re-analyze, replaces that
job as the one considered. This holds across worker restarts, since it is decided from job rows and file status
only.

#### Scenario: A user's cancel is respected
- **WHEN** the user cancels an `analysis` job that the sweep enqueued, and nothing in the event changes afterwards
- **THEN** no later sweep enqueues that event again

#### Scenario: A change after the cancel makes the event due again
- **WHEN** an event's latest `analysis` job ended `canceled`, and afterwards a clip is copied into the event
- **THEN** the next sweep enqueues the event

#### Scenario: A job-level failure does not loop
- **WHEN** an event's latest `analysis` job ended `failed` before writing any entry, and nothing changed since
- **THEN** no later sweep enqueues that event

#### Scenario: A clip copied in while a failed job ran is still analyzed
- **WHEN** an event holds a failure-marked clip, so its non-forced analysis job ends `failed`, and a new clip was
  copied into the event after that job started and before it ended
- **THEN** the next sweep enqueues the event

### Requirement: The analysis sweep is configured under `worker.*` and is on by default
`worker.auto_analyze` (default `true`), `worker.auto_analyze_interval` (seconds, default `300`) and
`worker.auto_analyze_max_events` (default `2`) SHALL layer over the built-in defaults like the other `worker.*`
keys. A worker with `auto_analyze` off SHALL run no sweep at all. A value of the wrong type, an interval that is not
greater than zero, or a cap that is not an integer of at least one SHALL make the worker refuse to start with an
error naming the key.

#### Scenario: Off means no sweep
- **WHEN** `config.yaml` sets `worker: {auto_analyze: false}` and events need analysis
- **THEN** the worker runs no sweep and enqueues no `analysis` job on its own

#### Scenario: Defaults apply without configuration
- **WHEN** `config.yaml` has no `worker.auto_analyze*` keys
- **THEN** the sweep is on, runs every 300 seconds and enqueues at most two events per sweep

#### Scenario: A bad value fails loud
- **WHEN** `config.yaml` sets `worker: {auto_analyze: "yes"}`, `worker: {auto_analyze_interval: 0}` or
  `worker: {auto_analyze_max_events: 0}`
- **THEN** the worker refuses to start with an error naming that key

### Requirement: The analysis sweep never stops the worker and is safe across restarts
A failing sweep SHALL NOT stop the worker or delay a job: a database error or a failing event walk SHALL end that
sweep with an error in the log and the next sweep SHALL try again; an event whose clips cannot be listed or
`stat`-ed SHALL be skipped with a warning naming it while the other events are still considered. The sweep SHALL
stop promptly when the worker stops, without waiting out its interval. A worker restart SHALL NOT create a second
active `analysis` job for an event, and SHALL NOT re-enqueue an event that the failure-marker or back-off rules
leave alone.

#### Scenario: A database outage skips one sweep
- **WHEN** the job store cannot be reached during a sweep
- **THEN** the sweep logs the error and enqueues nothing, the worker keeps running, and the next sweep runs as usual
  once the store is back

#### Scenario: An unreadable event is skipped
- **WHEN** one event folder cannot be listed during a sweep and another event is due
- **THEN** the sweep logs a warning naming the unreadable event and enqueues the other one

#### Scenario: A restart does not duplicate work
- **WHEN** the worker is stopped while a swept `analysis` job is queued and is then started again
- **THEN** the event still has exactly one active `analysis` job

#### Scenario: Stopping during the interval is prompt
- **WHEN** the worker is told to stop while its sweep waits for the next interval
- **THEN** the sweep ends without waiting for the interval to pass and the worker exits cleanly
