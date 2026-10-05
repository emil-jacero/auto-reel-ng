## ADDED Requirements

### Requirement: A clip's analysis reports progress and can be canceled
Analyzing one clip SHALL accept an optional progress callback and an optional cancel check, for a caller that wants
them: the worker's analysis job. The detection itself SHALL be unchanged: the same probe, the same two ffmpeg passes
with the same filter arguments, the same segments. The callback SHALL receive the fraction of that clip done,
non-decreasing: the first pass fills `0.0` to `0.5` and the second `0.5` to `1.0`, and `1.0` SHALL be received only
when both passes have finished. When the probe reports no duration, no fraction is computed and the callback
receives `1.0` at the end only; nothing is estimated. The cancel check SHALL be passed to both passes and checked
between them; when it reports true the running ffmpeg process SHALL be terminated and the engine's cancellation
error, distinct from a failure of the clip, SHALL be raised, and nothing SHALL be written for the clip. Without a
callback or a check the behaviour is that of today's analysis.

#### Scenario: Progress rises through both passes
- **WHEN** a 60 s 1080p50 clip with no entry is analyzed with a progress callback
- **THEN** the callback receives increasing fractions below `0.5` during the black/freeze pass, between `0.5` and
  `1.0` during the white pass, and `1.0` after the second pass exits

#### Scenario: Cancel inside a pass leaves nothing
- **WHEN** the cancel check turns true while the first pass of a long clip runs
- **THEN** the ffmpeg process ends within about two seconds, the cancellation error is raised rather than an
  analysis failure, the second pass never starts and the clip's sidecar entry is as it was before

#### Scenario: The detection arguments are unchanged
- **WHEN** a clip is analyzed with and without hooks
- **THEN** both runs pass ffmpeg the same detection filter chains (`blackdetect=d=2.0:pic_th=0.98:pix_th=0.1,
  freezedetect=n=0.003:d=2.0` and `negate,blackdetect=…`) and return the same segments

### Requirement: An analysis job analyzes every clip of its event that has no current result
A worker that claims a job of kind `analysis` SHALL analyze, in listing order, every clip that discovery lists in
the job's event folder (IGNORED clips included, as `auto-reel analyze` does) and whose analysis sidecar holds no
entry for the clip's current content-change signal. A clip with such an entry SHALL cost no ffmpeg or ffprobe
process. A job enqueued with `force` SHALL analyze every listed clip whatever the sidecar holds, replacing each
entry. The event's `reel.yaml` SHALL be neither read nor written, and a clip it lists that the disk lacks is never
requested. The original clip is analyzed, never a proxy. The job SHALL end `done` when every clip has a current
entry, and `failed` otherwise ("A clip whose analysis fails is marked and does not stop the others").

#### Scenario: Only changed and new clips are analyzed
- **WHEN** an event lists `a.mp4`, `b.mp4` and `c.mp4`, `a.mp4` has a current entry, `b.mp4` was re-copied (its
  size and modification time changed) and `c.mp4` has no entry, and an `analysis` job runs
- **THEN** `b.mp4` and `c.mp4` are analyzed (two ffmpeg passes each), `a.mp4` costs no process, all three have
  current entries and the job ends `done`

#### Scenario: A fully analyzed event completes without work
- **WHEN** an `analysis` job is claimed for an event whose clips all have current entries
- **THEN** no ffmpeg or ffprobe process starts, the job's progress is `1.0` and it ends `done`

#### Scenario: A forced job analyzes everything
- **WHEN** an `analysis` job enqueued with `force` runs on the same fully analyzed event
- **THEN** every clip is analyzed again and its entry rewritten, and the job ends `done`

#### Scenario: Editorial state does not choose the clips
- **WHEN** the event's `reel.yaml` lists only `a.mp4`, marks `b.mp4` as ignored and lists `gone.mp4` that is not
  on disk, and an `analysis` job runs
- **THEN** `a.mp4` and `b.mp4` are analyzed, `gone.mp4` is never requested, and `reel.yaml` is byte-for-byte
  unchanged

### Requirement: The analysis sidecar is the only thing written, and never half written
An `analysis` job SHALL write only into its event's `.auto-reel/cache/` directory: not `reel.yaml`, not a clip, not
the output directory, not a render manifest, not the proxy or thumbnail caches. It SHALL NOT apply the render-only
claim checks (the claim-time staleness recheck, the output-collision recheck, the running-output refusal and the
claimed-movie refusal), SHALL NOT record a fingerprint, and finishing it SHALL NOT change any event's staleness
verdict. A render job, a proxy job and an analysis job for one event MAY all exist at the same time.

Every write of a sidecar entry, by an analysis job or by `auto-reel analyze`, SHALL be atomic: the content is
written to a temporary file in the same directory and then renamed over the entry, so a concurrent reader (the
analysis read of the API, another writer) reads either the previous entry or the complete new one, never a partial
one. A temporary file left by a killed process SHALL NOT be read as an entry and SHALL NOT make a later run fail.

#### Scenario: Analysis does not make an event stale
- **WHEN** an event is fresh and an `analysis` job for it ends `done`
- **THEN** its staleness verdict is still fresh, its render manifest is unchanged, and the only new or changed
  files are under `<event>/.auto-reel/cache/`

#### Scenario: A reader never sees half an entry
- **WHEN** the API's analysis read of an event runs while a job rewrites the entry of one of its clips
- **THEN** the read returns that clip's previous segments or its new ones, never an error and never a clip with a
  truncated list

#### Scenario: A leftover temporary file is harmless
- **WHEN** a clip's cache directory holds a temporary file a killed writer left behind
- **THEN** a later `analysis` job analyzes the clip normally, writes its entry and ends `done`

### Requirement: A clip whose analysis fails is marked and does not stop the others
When analyzing one clip of an `analysis` job fails (the clip cannot be statted or probed, an ffmpeg pass exits
non-zero or stalls), the worker SHALL record the clip and its one-line cause, SHALL write a **failure marker** for
the clip in the sidecar (keyed, like an entry, by the clip's identity and current content-change signal, carrying
the cause and no segments), and SHALL go on to the event's remaining clips. After the last clip the job SHALL end
`failed` when any clip failed, with an error stating how many of how many clips failed and naming the failed clips
and causes (a long list MAY be shortened to its first clips and a count); clips analyzed before and after the
failure keep their entries. Nothing is invented for a failed clip.

A marker is not an analysis result: the analysis read and `auto-reel analyze` SHALL treat a marked clip as having
no entry. A job that is not forced SHALL NOT run ffmpeg or ffprobe for a clip whose marker matches its current
signal; it SHALL count the clip as failed again, naming its recorded cause. A forced job, or a change to the clip's
signal, SHALL analyze the clip again, and a success SHALL replace the marker with an entry.

A fault of the sidecar itself (the event's cache directory cannot be created or written, or the disk is full) is not
a clip's failure: it SHALL end the job at once as `failed` naming that fault, without attempting a marker. A
failure SHALL NOT stop the worker or affect other jobs.

#### Scenario: One undecodable clip among three
- **WHEN** the second of three clips is truncated so that ffprobe cannot read it, and an `analysis` job runs
- **THEN** the first and third clips get entries, the second gets a failure marker naming the probe failure, and
  the job ends `failed` with an error of the form "1 of 3 clips failed: <clip>: <cause>"

#### Scenario: A failed clip is not retried in a loop
- **WHEN** a new `analysis` job, not forced, is enqueued for that event without any clip changing
- **THEN** no ffmpeg or ffprobe process starts, and the job ends `failed` naming the second clip and its recorded
  cause

#### Scenario: Force or a fixed clip retries it
- **WHEN** the second clip is replaced by a good copy (its signal changes), or a forced job is enqueued, and the job
  runs
- **THEN** the second clip is analyzed, its marker is replaced by an entry, and the job ends `done`

#### Scenario: An unwritable event folder ends the job at once
- **WHEN** the event folder is read-only and an `analysis` job runs on an event of three clips
- **THEN** the job ends `failed` naming the cache directory after the first clip's detection, the other clips are
  not analyzed, and its capacity token is released

### Requirement: Analysis job progress is weighted by source size and never decreases
An `analysis` job's `progress` SHALL be the share of the event's clip bytes already analyzed: each clip weighs its
source file size (a file of size zero weighs one byte), a finished clip counts fully (one skipped as current or as
marked too), and the clip in flight counts its own fraction. The value SHALL be written through the same throttle as
a render's, SHALL NOT decrease while the job runs, SHALL stay below `1.0` until the last clip is finished and below
`1.0` for good once a clip failed, and SHALL reach `1.0` no later than the transition to `done`. Computing it SHALL
NOT require a probe.

#### Scenario: Progress is weighted by size
- **WHEN** an event holds a 900 MB clip and a 100 MB clip, in that order, and the first has been analyzed
- **THEN** the stored progress is about `0.9`, not `0.5`

#### Scenario: Progress moves inside a clip
- **WHEN** the only clip of an event is in its second pass
- **THEN** the stored progress is above `0.5` and below `1.0`

### Requirement: An analysis job holds one CPU token and only `worker.analysis_slots` run at once
While an `analysis` job analyzes a clip it SHALL hold exactly one token of the CPU pool and no GPU token, so a
GPU-classified render can run beside it. It gives that token back while it waits ("An analysis job yields to running
renders and proxy jobs"). At most `worker.analysis_slots` analysis jobs SHALL be in flight in one worker; the setting
defaults to `1`, layers over the built-in default like the other `worker.*` keys, and a value that is not an
integer of at least one fails loud naming `worker.analysis_slots`. The token is released on every outcome (`done`,
`failed`, `canceled`, requeued).

#### Scenario: One analysis job at a time by default
- **WHEN** two `analysis` jobs are queued and the worker uses the default `analysis_slots`
- **THEN** the second is not claimed until the first has ended

#### Scenario: A bad `analysis_slots` fails loud
- **WHEN** `config.yaml` sets `worker: {analysis_slots: 0}` or `worker: {analysis_slots: "two"}`
- **THEN** the worker refuses to start with an error naming `worker.analysis_slots`

#### Scenario: The token is released on failure
- **WHEN** an `analysis` job fails, and a CPU-classified render is queued behind it
- **THEN** the render starts at once

### Requirement: An analysis job is claimed after every render and proxy job
A worker SHALL claim a queued `analysis` job only when no queued `render` job and no queued `proxy` job it may claim
remains, whichever is older and whatever their `priority`, and only while fewer than `worker.analysis_slots`
analysis jobs are in flight. An `analysis` job, claimed or waiting, SHALL NOT use up the in-flight capacity that a
queued render needs: the claim loop's bound counts neither `proxy` nor `analysis` jobs. Among analysis jobs the
order is the store's (`priority` descending, then oldest first). The order between `render` and `proxy` jobs is
unchanged. A running analysis job is never interrupted for another job, but it starts no further clip while one
runs ("An analysis job yields to running renders and proxy jobs").

#### Scenario: A newer render and a newer proxy job go first
- **WHEN** an `analysis` job was queued an hour ago, a `proxy` job ten minutes ago and a `render` job a minute ago
- **THEN** the worker claims the `render` job, then the `proxy` job, then the `analysis` job

#### Scenario: A waiting analysis job does not block a render
- **WHEN** an `analysis` job is running, a second `analysis` job is queued, and a GPU-classified `render` job is
  then queued
- **THEN** the second analysis job stays `queued` and the `render` job is claimed and starts

#### Scenario: Renders are never starved by analysis
- **WHEN** ten `analysis` jobs are queued and render jobs keep arriving
- **THEN** each render is claimed as soon as the render capacity bound allows, exactly as with no analysis job
  queued, and at most `worker.analysis_slots` analysis jobs are ever in flight

### Requirement: An analysis job yields to running renders and proxy jobs
An `analysis` job SHALL NOT start analyzing a clip (including the first) while any `render` or `proxy` job is
`running`. A clip already being analyzed SHALL finish. While it waits the job SHALL NOT hold a CPU token, so a
running render or proxy job that waits for the CPU token is never blocked by the job that yields to it, and it SHALL
keep answering a cancel and a worker stop. When none is running it SHALL take the token again and continue with the
next clip. Its progress does not change while it waits.

#### Scenario: A proxy job waiting for the CPU token gets it
- **WHEN** an `analysis` job holds the only CPU token and is analyzing the first of five clips, and a `proxy` job is
  claimed and waits for the token
- **THEN** the first clip finishes, the analysis job gives the token back, the proxy job prepares its event, and
  the analysis job continues with the second clip after the proxy job ends

#### Scenario: A render that starts holds back the next clip
- **WHEN** a `render` job starts running while an `analysis` job analyzes its first of two clips
- **THEN** the second clip does not start while the render runs, and starts after it ends

### Requirement: Cancelling or restarting an analysis job keeps finished clips
The worker SHALL check an `analysis` job's `cancel_requested` flag between clips and about once a second while a
clip is analyzed; when it is set the running ffmpeg process SHALL be terminated, the job SHALL transition
`running → canceled`, and the cancellation SHALL NOT be recorded as a failed clip or a marker. A graceful shutdown
(SIGINT or SIGTERM) SHALL stop the ffmpeg process and requeue the job like any job; startup reconciliation SHALL
requeue one orphaned by a crash. In every case the entries of clips finished before SHALL stay, no partial entry SHALL
exist, and a job that runs the event again SHALL cost no ffmpeg process for those clips.

#### Scenario: Cancel inside a clip
- **WHEN** `cancel_requested` is set while the second of three long clips, none analyzed before, is analyzed
- **THEN** within about two seconds its ffmpeg process is gone, the job ends `canceled`, the third clip is not
  started, the first clip's entry remains and the second clip has neither an entry nor a marker

#### Scenario: A crash is recovered
- **WHEN** a worker is killed while an `analysis` job analyzes its second of three clips, and a new worker starts
- **THEN** the job is requeued and claimed, the first clip costs no ffmpeg process, the second and third are
  analyzed, and the job ends `done`

### Requirement: `auto-reel analyze` can queue analysis jobs
`auto-reel analyze <root> --enqueue` SHALL queue one `analysis` job for each event it selects, through the job
store's idempotent submit, instead of analyzing inline, and SHALL print, per event, whether a job was queued or an
active analysis job already exists, with the job's id. With `--force` the queued jobs carry `force`. It SHALL run no
ffprobe or ffmpeg process and write no file. A database that cannot be reached SHALL be reported as `auto-reel
enqueue` reports it, with the same exit code, and an event already having an active analysis job is not an error
(exit 0). `auto-reel analyze <root> --force` without `--enqueue` SHALL analyze inline every clip of the selected
events, ignoring existing entries. Without either flag `auto-reel analyze` is unchanged.

#### Scenario: Queue an event twice
- **WHEN** `auto-reel analyze <root> --enqueue` runs twice for a project with one event and no worker running
- **THEN** the first run prints the event as queued with a job id, the second prints the same job id as already
  active, one `analysis` row exists in the store, both exit 0, and no ffmpeg or ffprobe process ran

#### Scenario: Re-analyze from the CLI
- **WHEN** `auto-reel analyze <root> --enqueue --force` queues an event and a worker claims it
- **THEN** the job's `force` is true and every clip of the event is analyzed again

## MODIFIED Requirements

### Requirement: A claimed job is dispatched by its kind
After claiming a job, the worker SHALL process it according to its `kind`. A `render` job SHALL follow the
render path unchanged: the claim-time recheck, collision checks, capacity tokens, progress, cancellation and
output behaviour of the requirements above apply to it exactly as before, whatever other kinds exist. A job of
any other kind SHALL be processed by the handler registered for that kind when the worker was constructed, and
a handler cannot replace the `render` path.

A job whose `kind` has no registered handler, whether a kind this system defines but the worker does not
handle or a value it has never heard of, SHALL transition to `failed` with a reason that names the kind. It
SHALL be failed before a capacity token is taken and before the event, its project configuration, ffprobe or
ffmpeg is touched, SHALL NOT be requeued, and SHALL NOT stop the worker or delay other jobs.

A handler that returns normally SHALL end its job `done` with progress `1.0`. A handler that raises the engine's
cancellation SHALL end its job `canceled`; one that raises one of the engine's typed errors SHALL end it
`failed` with that error's message; any other exception SHALL end it `failed` with the exception's type and
message, as for a render ("Per-job failure isolation"). Graceful shutdown and startup reconciliation SHALL treat a job
of any kind as they treat a render. The claim loop's in-flight bound SHALL count a job of any kind except
`proxy` and `analysis` as it counts a render; `proxy` jobs are bounded by `worker.proxy_slots` alone ("A queued
render is claimed before any proxy job") and `analysis` jobs by `worker.analysis_slots` alone ("An analysis job
is claimed after every render and proxy job").

#### Scenario: A render job is processed as before
- **WHEN** a worker with a `proxy` handler registered claims a `render` job for
  `2024/2024-06-27 - Grillning med grannar`
- **THEN** the job renders (or completes as fresh) through the render path, the `proxy` handler is not
  called, and the outcome, progress and capacity token use are those of a worker with no handlers

#### Scenario: A job of a handled kind runs its handler
- **WHEN** a worker with a handler registered for `proxy` claims a `proxy` job and the handler returns
- **THEN** the handler is called with that job, and the job ends `done` with progress `1.0`

#### Scenario: A job of a known kind with no handler fails loud
- **WHEN** a worker with no `proxy` handler claims a `proxy` job
- **THEN** the job is `failed` with a reason naming `proxy`, no capacity token was taken, no ffprobe or ffmpeg
  process ran and no file in the event folder was written, and the worker goes on to claim the next job

#### Scenario: A job of an unknown kind fails loud
- **WHEN** a worker claims a job whose `kind` is `thumbnails`, which no build of this system defines
- **THEN** the job is `failed` with a reason naming `thumbnails`, it is not requeued, and a `render` job
  queued behind it is claimed and rendered normally

#### Scenario: A handler's failure is isolated and typed
- **WHEN** a `proxy` handler raises an engine error with message `no audio stream` and a later `proxy`
  handler call raises `TypeError: boom`
- **THEN** the first job is `failed` with `no audio stream`, the second is `failed` with `TypeError: boom`,
  and the worker keeps claiming

#### Scenario: A handler's cancellation ends the job canceled
- **WHEN** a `proxy` handler raises the engine's cancellation
- **THEN** the job ends `canceled`

#### Scenario: A handler cannot take over the render path
- **WHEN** a worker is constructed with a handler registered under `render`
- **THEN** construction is refused, and no worker with that mapping exists

#### Scenario: A requeued proxy job is dispatched again
- **WHEN** a worker restarts while a `proxy` job is `running`
- **THEN** startup reconciliation requeues it, and the next claim dispatches it to the `proxy` handler again

#### Scenario: A requeued analysis job is dispatched again
- **WHEN** a worker restarts while an `analysis` job is `running`
- **THEN** startup reconciliation requeues it, and the next claim dispatches it to the `analysis` handler again
