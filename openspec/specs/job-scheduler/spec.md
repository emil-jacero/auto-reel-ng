# job-scheduler Specification

## Purpose

Run a worker process that drives the durable job queue (job-store) end to end: poll for and race-free
claim queued jobs, rebuild each job's render plan from current disk state at claim time, enforce
two-pool (per-device GPU + global CPU) capacity, persist throttled progress, requeue orphaned work left
by a crashed worker, support cooperative mid-render cancellation, isolate per-job failures, and shut down
gracefully on SIGINT/SIGTERM without ever leaving a job `running` when the process exits cleanly.

## Requirements

### Requirement: Worker claims jobs and rebuilds the plan at claim time
A worker process SHALL poll the job store (`claim_next`) on a short interval (1–2 s when idle) and, for
each claimed job, rebuild the render plan from disk at claim time — prepare/adopt the event, probe its
clips, and resolve the plan — sharing the same build path as the CLI's `render` command. A job row SHALL
be treated as an event reference only; the system MUST NOT persist or execute a plan serialized at enqueue
time.

#### Scenario: Claimed job renders from current disk state
- **WHEN** a job is enqueued, its event's `reel.yaml` is edited, and a worker then claims the job
- **THEN** the render reflects the edited `reel.yaml`, not the state at enqueue time

#### Scenario: Idle worker keeps polling
- **WHEN** the queue is empty
- **THEN** the worker sleeps its poll interval and claims promptly once a job is enqueued

### Requirement: Claim-time staleness recheck
After claiming a job and rebuilding its plan, the worker SHALL re-evaluate the staleness gate against
current disk state — unless the job's `force` flag is set. A job whose event evaluates fresh SHALL be
completed as `done` without rendering (its progress set to 1.0); a stale (or forced) job SHALL render
with output replacement (the gate verdict, not bare file existence, decides). This catches both disk
changes made while the job was queued and reverts to the last-rendered state, and it absorbs requeued
already-finished orphans by manifest verification rather than file existence.

#### Scenario: Reverted event skips at claim time
- **WHEN** an event is enqueued stale, then restored on disk to exactly its last-rendered state before a
  worker claims the job
- **THEN** the claim-time recheck evaluates fresh and the job completes `done` without any ffmpeg process

#### Scenario: Forced job never rechecks
- **WHEN** a job with `force = true` is claimed for a fresh event
- **THEN** the worker renders it, replacing the existing output

#### Scenario: Requeued finished orphan absorbed by manifest
- **WHEN** a job that finished its render (manifest written) is orphaned before its status transition and
  requeued by reconciliation
- **THEN** the re-claiming worker evaluates it fresh and completes it `done` without re-rendering

#### Scenario: Stale job replaces outdated output
- **WHEN** a claimed job's event has an existing output but a differing fingerprint
- **THEN** the worker renders and the output is replaced (no skip on bare existence)

### Requirement: Two-pool capacity enforcement
The worker SHALL select its acceleration profile once at startup and enforce capacity as two pools: one
semaphore per hardware render node (default capacity 1, configurable) and one global CPU pool (capacity N,
configurable). After rebuilding a claimed job's plan, the worker SHALL classify the job by its resolved
encoder — hardware encoder → that device's GPU token, software encoder → a CPU token — and MUST hold
exactly one token for the job's full duration. A CPU-classified job and a GPU-classified job SHALL be able
to run concurrently.

#### Scenario: GPU sessions are capped per device
- **WHEN** two GPU-classified jobs are claimed and the device's capacity is 1
- **THEN** the second render does not start until the first releases the device token

#### Scenario: CPU job runs alongside a GPU job
- **WHEN** a GPU-classified job is running and a CPU-classified job is claimed
- **THEN** the CPU job renders concurrently without waiting for the GPU token

#### Scenario: One token for the whole job
- **WHEN** a job's pipeline mixes CPU filter stages with a hardware encode
- **THEN** the job holds only its GPU token from start to finish (no mid-job token handoff)

### Requirement: Progress is persisted, throttled
The worker SHALL forward the engine's `on_progress` fraction into the job row via `set_progress`,
throttled (a minimum delta and/or minimum interval between writes) so progress updates do not flood the
database. The stored progress MUST reach 1.0 no later than the job's terminal transition to `done`.
The forwarding callback SHALL NOT write a fraction lower than the highest one it has already received for
that job run: a lower fraction is dropped, not written, so the stored value never decreases while a job runs
even if the engine delivers one; the terminal `1.0` is never dropped.

#### Scenario: Progress advances during a render
- **WHEN** a job is rendering
- **THEN** its stored `progress` increases monotonically toward 1.0 without a write per ffmpeg progress line

#### Scenario: A lower fraction is never written
- **WHEN** the callback has received `0.80` and then receives `0.19`, even after the throttle interval has
  elapsed
- **THEN** no write is made for `0.19`, the stored `progress` stays at `0.80`, and a later `0.85` is written
  normally

#### Scenario: The terminal fraction is not throttled or dropped
- **WHEN** the callback has received `0.999` and then receives `1.0` within the throttle interval
- **THEN** `1.0` is written

### Requirement: Startup reconciliation requeues orphans unconditionally
Each worker boot SHALL use a fresh unique `worker_id` (host, pid, nonce). Before claiming any work, the
worker SHALL find `running` jobs not owned by a live worker (`find_orphaned_running(live_workers=[its id])`)
and reset every one to `queued` (clearing `worker_id`, `started_at`, and `progress`). Reconciliation MUST
NOT attempt to verify outputs or rebuild plans — a previously-completed orphan is absorbed by the engine's
skip-if-exists check when it re-runs (sound because output finalization is atomic).

#### Scenario: Orphaned running job is requeued on startup
- **WHEN** a worker starts and a job is `running` under a dead worker's id
- **THEN** the job returns to `queued` and is claimed and processed normally

#### Scenario: Finished orphan completes without re-rendering
- **WHEN** a requeued job's event already has a complete output at the final path
- **THEN** the re-run skips rendering and the job transitions to `done`

### Requirement: Cooperative cancellation of a running render
The worker SHALL check the job's `cancel_requested` flag at segment boundaries during a render, and SHALL
also check it while a segment is being encoded, about once a second. When set, the worker SHALL stop the
render — before the next segment starts, or by terminating the running ffmpeg process if a segment is in
progress — clean up its scratch work, and transition the job `running → canceled`. The worker SHALL remain
the sole writer of job status transitions.

#### Scenario: Running job is canceled at a segment boundary
- **WHEN** `cancel_requested` is set while a job is rendering segment k of n (k < n)
- **THEN** no segment after k is started, no output appears at the final path, and the job ends `canceled`

#### Scenario: Running job is canceled inside a segment
- **WHEN** `cancel_requested` is set while ffmpeg is encoding a long clip's segment k of n
- **THEN** within about a second that ffmpeg process is terminated rather than allowed to finish the segment,
  no segment after k is started, no output and no `.part` file remain at the final path, and the job ends
  `canceled`

### Requirement: Per-job failure isolation
A failure building or rendering one job (missing event dir, probe error, render error) SHALL transition
that job to `failed` with the error message recorded, and MUST NOT stop the worker or affect other jobs —
mirroring the CLI batch's per-event isolation. This SHALL hold for any failure while a claimed job is
processed, not only for the engine's own typed errors: an unexpected exception (an I/O error reading the
event, a defect in the build or render, a failed progress or cancel-flag write) SHALL also transition that
job to `failed`, with the error recorded as the exception's type and message, and the job's capacity token
MUST be released. A job MUST NOT be left `running` by a failure of its own processing. If recording the
failure itself fails (for example the database is unreachable), the worker SHALL log it and keep running;
the row is then left for startup reconciliation. A cancellation raised by the engine SHALL still end
`canceled`, and a requeue by graceful shutdown SHALL still end `queued` even if an unexpected error follows,
rather than being rewritten as `failed`. An unexpected error is not a cancellation: a pending cancel request
does not turn it into `canceled`.

#### Scenario: Failed plan rebuild fails only that job
- **WHEN** a claimed job's event directory no longer exists
- **THEN** the job is marked `failed` with the cause and the worker continues claiming other jobs

#### Scenario: Unexpected error while building fails the job
- **WHEN** rebuilding a claimed job's plan raises an error that is not one of the engine's typed errors
  (for example `OSError: disk gone`)
- **THEN** the job is marked `failed` with the error `OSError: disk gone`, not left `running`, and the
  worker continues claiming other jobs

#### Scenario: Unexpected error while rendering fails the job and frees its token
- **WHEN** the render of a claimed job raises an error that is not one of the engine's typed errors
  (for example `TypeError: boom`)
- **THEN** the job is marked `failed` with the error `TypeError: boom`, its capacity token is released so a
  following job can start, and the event can be enqueued again

#### Scenario: Failed progress write fails the job
- **WHEN** persisting a render's progress raises while the job renders
- **THEN** the job is marked `failed` with that error rather than left `running`

#### Scenario: Failure to record the failure does not stop the worker
- **WHEN** a job fails unexpectedly and the transition to `failed` itself raises
- **THEN** the failure is logged, the worker does not stop, and the row is left for the next startup
  reconciliation to requeue

#### Scenario: Cancellation and shutdown requeue keep their own outcome
- **WHEN** a render raises the engine's cancellation, or a job is gracefully shut down and requeued and an
  unexpected error then ends its processing
- **THEN** the canceled job ends `canceled` and the requeued job stays `queued`, neither is rewritten as
  `failed`

#### Scenario: Unexpected error during a pending cancel still fails the job
- **WHEN** a cancel was requested for a running job and its processing then raises an error that is not the
  engine's cancellation (for example `TypeError: boom`)
- **THEN** the job is marked `failed` with that error, not `canceled`

### Requirement: Graceful shutdown
On SIGINT/SIGTERM the worker SHALL stop claiming, requeue its in-flight jobs (`running → queued`), and
exit cleanly. No job may be left `running` by a cleanly-stopped worker.

#### Scenario: Signal during a render requeues the job
- **WHEN** the worker receives SIGTERM while a job renders
- **THEN** the job returns to `queued` before the process exits, and no partial file exists at the final
  output path

### Requirement: Claim-time output-collision recheck
After claiming a job and before the claim-time staleness recheck, the worker SHALL apply the output-collision
rule of the batch commands (headless-cli, "Batch commands refuse colliding output paths") to the claimed
job's event, over the whole project: the claimants are every event the configured ingest layout walks from the
project's walk root, plus the claimed event itself. Paths SHALL be compared exactly as the batch commands
compare them (case-insensitively, after Unicode normalization). An event that fails on its own (an unparseable
`reel.yaml`, no real date or title, a folder or file that cannot be listed or read) SHALL claim no path, as in
the batch commands.

A job whose event shares its output path with another event SHALL be failed with a reason that states the
shared output path, names the other claimants, and names the fix (a distinct title or location in
`reel.yaml`), the same sentence the CLI and `POST /api/v1/jobs` use. For that job the worker MUST NOT probe,
adopt clips into or otherwise write a `reel.yaml`, render, replace an existing output file, create an
`<output>.part` file, or write a render manifest. This
SHALL hold whether the event is fresh or stale and whether or not `force` is set, and the job SHALL NOT be
requeued: the operator resolves the collision by editing `reel.yaml`, then enqueues again. The worker SHALL
continue with other jobs.

A check that cannot be made, because the layout walk itself fails (an unknown layout, or the walk root cannot
be listed), SHALL fail the job with that cause; the worker MUST NOT render an event whose collision it could
not check. The check itself SHALL only read: it writes no file and no row other than the job's own terminal state.

#### Scenario: An event edited into a collision after enqueue fails at claim
- **WHEN** jobs are enqueued for `2024/2024-06-21 - Midsommar` and `2024/2024-06-21 - Midsommar 2`, each
  with its own output path, and the second event's `reel.yaml` title is then edited to `Midsommar` before a
  worker claims either job
- **THEN** each job, when claimed, is failed with a reason naming `2024/2024-06-21 - Midsommar.mp4` and the
  other event, no ffmpeg process starts for either, no file appears under `<output>/2024/`, no manifest is
  written, and neither event's `reel.yaml` is changed by the worker

#### Scenario: A fresh colliding event is not completed as done
- **WHEN** a job is claimed for an event whose render manifest matches its fingerprint and whose output exists,
  and a newly added event now resolves to the same output path
- **THEN** the job is failed with the collision reason, not completed `done`, and the existing movie is
  byte-for-byte unchanged

#### Scenario: Force does not override the collision
- **WHEN** a job with `force = true` is claimed for an event whose output path another event claims
- **THEN** the job is failed with the collision reason and nothing is rendered

#### Scenario: A case-only difference collides
- **WHEN** a claimed event resolves to `2024/2024-06-21 - Midsommar.mp4` and another event to
  `2024/2024-06-21 - midsommar.mp4`
- **THEN** the claimed job is failed with the collision reason

#### Scenario: An unreadable sibling does not fail the job
- **WHEN** a job is claimed for a uniquely named event whose sibling event folder has permissions `000`
- **THEN** the sibling claims no path, the job passes the check and is rendered or skipped as fresh by the
  staleness recheck, as it would be without the sibling

#### Scenario: A walk that cannot be made fails the job
- **WHEN** the project's configured layout names a layout that is not registered, and a job is claimed
- **THEN** the job is failed with the unknown-layout cause and nothing is rendered

#### Scenario: A uniquely named event is unaffected
- **WHEN** a job is claimed for an event whose output path no other event claims
- **THEN** the claim-time staleness recheck and the render proceed exactly as before

### Requirement: A claimed job is refused while another running job writes its output
After claiming a job, and before the worker rebuilds its plan (so before it writes the event's `reel.yaml`,
probes a clip or starts ffmpeg), the worker SHALL refuse the job when a different `render` job that is `running` in
the job store writes the same output path, whichever project that job belongs to. A job's output path is its
project's output directory plus the file name its event's current metadata gives it; paths SHALL be compared
case-insensitively, after Unicode normalization, as for the batch commands' collision rule. The refused job
SHALL transition to `failed` with a reason that names the shared output path and the running job's event,
and SHALL NOT render, write the event's `reel.yaml`, write a render manifest or an `<output>.part` file, or
touch an output file that exists at that path. The running job is never interrupted. The check applies to a
`force` job as to any other, and a requeued job (for example after a worker restart) SHALL be checked again at
its next claim.

A job's own row, which is `running` from the moment it is claimed, SHALL NOT count as another running job. A
running job of any kind other than `render` writes no movie and SHALL NOT count, whatever its event. A
running job whose project configuration or event cannot be loaded, or whose event is not processable, claims
no path and SHALL NOT refuse the claimed job. When the claimed job's own output path cannot be resolved the
check refuses nothing, and the plan rebuild fails the job with its own reason as before. The disk rule of the
same-project collision is "Claim-time output-collision recheck"; this requirement adds the store-wide check
the disk rule cannot make (another project with the same output directory, an event the layout walk does not
reach). When the claimed job's output is also claimed on disk by another event of its project, the refusal SHALL be the disk rule's (the shared sentence), not this requirement's, because that rival is itself refused and writes nothing. Two jobs claimed at the same moment MAY both be refused, and at most one of them renders.

#### Scenario: A running job in another project holds the same output
- **WHEN** a job of project P1 is `running` and renders `<shared output>/2024/2024-06-21 - Midsommar.mp4`,
  and a worker then claims a job of project P2 whose `config.yaml` names the same output directory and whose
  event resolves to the same path
- **THEN** the P2 job is `failed` with a reason naming that path and the running job's event, the P1 job is
  not touched and finishes `done`, and the P2 event can be enqueued again once the P1 job has ended

#### Scenario: A refusal writes nothing into the event
- **WHEN** a claimed job is refused because of a running job and its event folder holds a clip that
  `reel.yaml` does not yet list
- **THEN** the job fails, `reel.yaml` is not rewritten to adopt that clip, and no ffprobe or ffmpeg process
  runs for it

#### Scenario: Force does not override a running job's output
- **WHEN** a job with `force = true` is claimed while another job writes its output path
- **THEN** the job is `failed` with the reason and nothing is rendered

#### Scenario: A running job with a different output does not block
- **WHEN** another job is `running` and resolves a different output path
- **THEN** the claimed job is not refused

#### Scenario: A running proxy job does not hold an output
- **WHEN** a `proxy` job for `2024/2024-06-21 - Midsommar` is `running`, and a worker claims the `render` job
  of the same event
- **THEN** the render job is not refused because of it

#### Scenario: A job's own row never blocks itself
- **WHEN** a worker claims a job, which makes its own row `running`
- **THEN** that row is not counted as another running job

#### Scenario: A running job whose event cannot be loaded claims nothing
- **WHEN** another `running` job's event folder has since been deleted, and a worker claims a job
- **THEN** the claimed job is not refused because of it

#### Scenario: A refusal does not hold a capacity token
- **WHEN** a claimed job is refused because of a running job
- **THEN** no capacity token was taken for it, and a following job can start at once

### Requirement: A stalled render fails its job
A render whose segment encode makes no progress for ten minutes SHALL be terminated and its job SHALL
transition `running → failed` with an error that names the segment and says ffmpeg stalled, through the same
path as any other render failure. The worker MUST release the job's capacity token and MUST NOT stop or
delay other jobs. No output SHALL appear at the final path and no render manifest SHALL be written, so the
event remains stale and can be enqueued again. A job that makes steady progress SHALL NOT be failed for
taking long, however long it takes.

#### Scenario: Hung ffmpeg fails the job and frees the device
- **WHEN** a job's ffmpeg for segment 2 of `2024/2024-10-05 - Trasig` stops reporting output time and ten
  minutes pass
- **THEN** the job is `failed` with an error naming segment 2 and the stall, the GPU token it held is
  released so the next queued job on that device can start, and no movie or `.part` file exists at the
  output path

#### Scenario: A stalled event can be re-enqueued
- **WHEN** a job failed because its render stalled and the operator enqueues the same event again
- **THEN** the event is still stale (no manifest was written) and a new job is created and rendered normally

#### Scenario: A long healthy render is not failed
- **WHEN** a segment takes 45 minutes to encode and ffmpeg advances its output time throughout
- **THEN** the job is not failed for its duration and completes `done`

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
`proxy` as it counts a render; `proxy` jobs are bounded by `worker.proxy_slots` alone ("A queued render is
claimed before any proxy job").

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

### Requirement: A clip's proxy and filmstrip are prepared as one operation that reports progress and can be canceled
Preparing a clip SHALL be one operation that makes the clip's proxy (when its entry is not complete) and then its
filmstrip (when none is recorded), for a caller that wants both: the worker's proxy job. It SHALL accept an optional
progress callback and an optional cancel check, and return the clip's entry and its filmstrip. The callback SHALL
receive the fraction of that one clip done, non-decreasing, and SHALL receive `1.0` only when the proxy and the
filmstrip are both complete; a clip whose proxy and filmstrip are already complete SHALL report `1.0` without
starting a process. The cancel check SHALL be passed to every ffmpeg run of the operation and SHALL be checked
between the proxy and the filmstrip; when it reports true the running process SHALL be terminated and the
cancellation error of the engine, distinct from a failure of the clip, SHALL be raised, with no temporary file left
in the cache. A failure of the proxy SHALL skip the filmstrip; a failure of the filmstrip SHALL leave the finished
proxy in the cache and be raised as the filmstrip's own error. Without a callback or a check the behaviour is that
of the two calls made one after the other.

#### Scenario: Progress rises to one after the filmstrip
- **WHEN** a clip with no entry is prepared with a progress callback
- **THEN** the callback receives increasing fractions below `1.0` while the proxy is encoded and while the
  filmstrip is cut, and `1.0` only after `filmstrip.jpg` is recorded

#### Scenario: A complete entry reports one at once
- **WHEN** a clip whose proxy and filmstrip are complete is prepared with a progress callback
- **THEN** `1.0` is received, and no ffmpeg or ffprobe process starts

#### Scenario: A proxy without a filmstrip only cuts the filmstrip
- **WHEN** a clip has a complete proxy and no recorded filmstrip, and is prepared
- **THEN** the proxy is not encoded again, the filmstrip is cut, and `1.0` is received after it

#### Scenario: Cancel terminates the encode and leaves nothing
- **WHEN** the cancel check turns true while a long clip is encoding
- **THEN** the ffmpeg process ends within about two seconds, the cancellation error is raised rather than a
  failure, and the cache directory holds exactly the files it held before

#### Scenario: Cancel between the proxy and the filmstrip
- **WHEN** the cancel check turns true after the proxy was published and before the filmstrip starts
- **THEN** the cancellation error is raised, no filmstrip process starts, and the finished proxy stays

#### Scenario: A failed proxy gets no filmstrip attempt
- **WHEN** the proxy of a clip cannot be made
- **THEN** the proxy's error is raised and no filmstrip process starts

### Requirement: A proxy job prepares every clip of its event
A worker that claims a job of kind `proxy` SHALL prepare the proxy and then the filmstrip of every clip that
discovery lists in the job's event folder, in listing order, using the proxy cache settings of the job's own
project. The clips are the ones on disk, as for `thumbs`: IGNORED clips are included, the event's `reel.yaml`
is neither read nor written, and a clip that `reel.yaml` lists but the disk lacks is never requested. Clips that
resolve to one cache entry (symlinks to one file) SHALL be prepared once. A clip whose entry is already complete
SHALL cost no ffmpeg or ffprobe process. A clip of under one second is prepared like any other (the filmstrip rule
gives it a one-tile sprite). The job SHALL end `done` when every clip is prepared, and `failed` otherwise
("A clip that fails does not stop the others").

#### Scenario: Every listed clip is prepared in order
- **WHEN** a `proxy` job is claimed for an event whose folder lists `a.mp4`, `b.mp4` and `ch/c.mp4`, none cached
- **THEN** the proxy and the filmstrip of `a.mp4`, then `b.mp4`, then `ch/c.mp4` are made in the project's
  proxy cache and the job ends `done`

#### Scenario: Editorial state does not choose the clips
- **WHEN** the event's `reel.yaml` lists only `a.mp4`, marks `b.mp4` as ignored, and lists `gone.mp4` that is
  not on disk, and a `proxy` job runs
- **THEN** `a.mp4` and `b.mp4` are prepared, `gone.mp4` is never requested, and `reel.yaml` is byte-for-byte
  unchanged

#### Scenario: A fully cached event completes without work
- **WHEN** a `proxy` job is claimed for an event whose clips all have complete entries
- **THEN** no ffmpeg or ffprobe process starts, the job's progress is `1.0` and it ends `done`

#### Scenario: Linked clips are prepared once
- **WHEN** two files of the event are symlinks to one clip
- **THEN** one entry is made, and both are counted as prepared

#### Scenario: A sub-second clip is prepared
- **WHEN** an event's only clip is shorter than one second
- **THEN** its proxy and its one-tile filmstrip exist and the job ends `done`

### Requirement: A proxy job touches nothing but the proxy cache
A `proxy` job SHALL write only into the proxy cache directory: not `reel.yaml`, not a clip, not the output
directory, not a render manifest, and no file under the project root. It SHALL NOT apply the render-only claim
checks (the output-collision recheck, the running-output refusal, the claimed-movie refusal, the claim-time
staleness recheck, and the stall rule of segment encodes), because it writes none of the paths they protect. It
SHALL NOT record a fingerprint, and finishing it SHALL NOT change any event's staleness verdict. A render job
and a proxy job for one event MAY run at the same time.

#### Scenario: A colliding or stale event still gets proxies
- **WHEN** a `proxy` job is claimed for an event whose output path another event also claims, and another
  event is stale and a third is fresh
- **THEN** each job prepares its clips and ends `done`; none is failed for a collision or completed early as fresh

#### Scenario: The library is not written
- **WHEN** a `proxy` job runs against a read-only library
- **THEN** it succeeds and no file under the project root is created, changed or removed

#### Scenario: Preparing proxies does not make an event stale
- **WHEN** an event is fresh and a `proxy` job for it ends `done`
- **THEN** the event's staleness verdict is still fresh, and its render manifest is unchanged

#### Scenario: A render and a proxy job of one event coexist
- **WHEN** a `render` job for `2024/Midsommar` is running and a `proxy` job for the same event is enqueued
- **THEN** the proxy job is accepted and claimed, and both end `done` without either blocking the other

### Requirement: A proxy job's settings come from its own project
A `proxy` job SHALL resolve the proxy cache directory and encoding settings from the `config.yaml` of the job's
recorded project root, not from the project the worker was started near. A project configuration that does not
load, or a cache directory the settings refuse (for example one inside the library), SHALL fail the job before any
ffmpeg process starts, with the settings' own message, and the worker SHALL continue with other jobs.

#### Scenario: Two projects, two caches
- **WHEN** two `proxy` jobs of different projects run, and the projects name different `proxies.cache_dir` values
- **THEN** each project's clips are prepared in its own cache directory

#### Scenario: A refused cache directory fails the job
- **WHEN** a `proxy` job is claimed for a project whose `proxies.cache_dir` is inside its library
- **THEN** the job ends `failed` with the refusal's message and no ffmpeg process starts

### Requirement: A clip that fails does not stop the others
When preparing one clip of a `proxy` job fails, the worker SHALL record the clip and its one-line cause, and
SHALL go on to the event's remaining clips. After the last clip the job SHALL end `failed` when any clip failed,
with an error that states how many of how many clips failed and names the failed clips and their causes (a long list
MAY be shortened to its first clips and a count); clips prepared before and after the failure SHALL stay in the
cache. A fault of the cache itself (the directory cannot be created, read or written, or the disk is full) is not a
clip's failure: it SHALL end the job at once as `failed` with that cause. A failure SHALL NOT stop the worker or
affect other jobs, and no entry of a failed clip SHALL exist half written. Nothing is invented for a failed clip.

#### Scenario: One bad clip among three
- **WHEN** the second of three clips cannot be encoded
- **THEN** the first and third are prepared, the job ends `failed` with an error of the form
  "1 of 3 clips failed: <clip>: <cause>", and the second clip has no cache entry

#### Scenario: A re-enqueue redoes only the failure
- **WHEN** the failed clip is fixed and a new `proxy` job is enqueued for the event
- **THEN** only that clip is encoded; the other two cost no ffmpeg process, and the job ends `done`

#### Scenario: A full cache ends the job at once
- **WHEN** the cache disk is full while the first of three clips is written
- **THEN** the job ends `failed` naming the cache fault, the second and third clips are not attempted, and the
  job's capacity token is released

#### Scenario: An unexpected error is still a failure
- **WHEN** preparing a clip raises an error that is not one of the engine's typed errors
- **THEN** the job ends `failed` with the error's type and message, its token is released, and the worker keeps
  claiming

### Requirement: Proxy job progress is weighted by source size and never decreases
A `proxy` job's `progress` SHALL be the share of the event's clip bytes already prepared: each clip weighs its
source file size (a file of size zero weighs one byte), a finished clip counts fully (a cached one too), and the
clip in flight counts its own progress fraction. The proxy and filmstrip of one clip together make that clip's
fraction. The value SHALL be written through the same throttle as a render's, SHALL NOT decrease while the job
runs, SHALL stay below `1.0` until the last clip is finished, and SHALL reach `1.0` no later than the transition
to `done`. Computing it SHALL NOT require a probe.

#### Scenario: Progress is weighted by size
- **WHEN** an event holds a 900 MB clip and a 100 MB clip, in that order, and the first has finished
- **THEN** the stored progress is about `0.9`, not `0.5`

#### Scenario: Progress moves inside a clip
- **WHEN** a clip is half encoded and it is the only clip
- **THEN** the stored progress rises toward `0.5` before the clip finishes

#### Scenario: Cached clips advance the bar without going back
- **WHEN** the first and third of three equal clips are cached and the second is encoded
- **THEN** the progress never decreases and ends at `1.0`

#### Scenario: Done means one
- **WHEN** a `proxy` job ends `done`
- **THEN** its stored progress is `1.0`

### Requirement: A proxy job holds one CPU token and only `worker.proxy_slots` run at once
While a `proxy` job prepares clips it SHALL hold exactly one token of the CPU pool and no GPU token, so a
GPU-classified render runs beside it. It gives that token back while it waits for a running render ("A proxy job
yields to running renders"). At most `worker.proxy_slots` proxy jobs SHALL be in flight in one worker; the
setting defaults to `1`, layers over the built-in default like the other `worker.*` keys, and a value that is not an
integer of at least one fails loud naming `worker.proxy_slots`. The token is released on every outcome (`done`,
`failed`, `canceled`, requeued).

#### Scenario: One proxy job at a time by default
- **WHEN** two `proxy` jobs are queued and the worker uses the default `proxy_slots`
- **THEN** the second is not claimed until the first has ended

#### Scenario: A GPU render runs beside a proxy job
- **WHEN** a `proxy` job is running and a GPU-classified `render` job is claimed
- **THEN** the render starts without waiting for the proxy job

#### Scenario: The token is released on failure
- **WHEN** a `proxy` job fails, and a CPU-classified job is queued behind it
- **THEN** the next job starts at once

#### Scenario: A bad `proxy_slots` fails loud
- **WHEN** `config.yaml` sets `worker: {proxy_slots: 0}` or `worker: {proxy_slots: "two"}`
- **THEN** the worker refuses to start with an error naming `worker.proxy_slots`

### Requirement: A queued render is claimed before any proxy job
A worker SHALL claim a queued `render` job before any queued `proxy` job, whichever is older and whatever their
`priority`, and SHALL claim a `proxy` job only while fewer than `worker.proxy_slots` proxy jobs are in flight. A
`proxy` job, claimed or waiting, SHALL NOT use up the in-flight capacity that a queued render needs to be claimed:
the claim loop's bound on in-flight jobs counts every job except `proxy` jobs, so a render that waits for the CPU
token behind a proxy job does not keep a GPU-classified render from being claimed. Among jobs of one kind the
order is unchanged (`priority` descending, then oldest first). A running proxy job is never interrupted for a
render, but it starts no further clip while one runs ("A proxy job yields to running renders").

#### Scenario: A newer render is claimed first
- **WHEN** a `proxy` job was queued an hour ago and a `render` job was queued a minute ago
- **THEN** the next claim is the `render` job, then the `proxy` job

#### Scenario: A waiting proxy job does not block a render
- **WHEN** a `proxy` job is running, a second `proxy` job is queued, and a `render` job is then queued
- **THEN** the second proxy job stays `queued` and the `render` job is claimed

#### Scenario: A CPU render behind a proxy job does not hold back a GPU render
- **WHEN** a `proxy` job holds the only CPU token, a CPU-classified `render` job is claimed and waits for that
  token, and a GPU-classified `render` job is then queued
- **THEN** the GPU render is claimed and runs while the CPU render still waits

#### Scenario: Order within a kind is unchanged
- **WHEN** three `proxy` jobs are queued at the same priority
- **THEN** they are claimed oldest first, one at a time

#### Scenario: A running proxy job is not preempted
- **WHEN** a `render` job is queued while a `proxy` job is running
- **THEN** the proxy job's clip in flight is not interrupted and finishes

### Requirement: A proxy job yields to running renders
A `proxy` job SHALL NOT start preparing a clip (including the first) while any `render` job is `running`. A clip
that is already being prepared SHALL finish. While it waits the job SHALL NOT hold a CPU token, so a running render
that waits for the CPU token is never blocked by the job that yields to it, and it SHALL keep answering a cancel
and a worker stop. When no render is running it SHALL take the token again and continue with the next clip. A
render that never ends keeps the job waiting; cancelling the job ends it. The job's progress does not change while
it waits.

#### Scenario: A render that starts between clips holds back the next clip
- **WHEN** a `render` job starts running while a `proxy` job is encoding its first of two clips
- **THEN** the first clip finishes, the second is not started while the render runs, and it starts after the
  render ends

#### Scenario: A render waiting for the CPU token gets it
- **WHEN** a CPU-classified `render` job is running and waits for the CPU token held by a `proxy` job that is
  between clips
- **THEN** the proxy job gives the token back, the render takes it and renders, and the proxy job continues after
  the render ends

#### Scenario: A cancel or a stop ends the wait
- **WHEN** a `proxy` job waits for a running render and its `cancel_requested` flag is set, or the worker stops
- **THEN** the job ends `canceled`, or is requeued by the shutdown, without having started another clip

### Requirement: Cancelling a proxy job stops its encode and leaves the cache clean
The worker SHALL check a `proxy` job's `cancel_requested` flag between clips and about once a second while a clip
is being encoded. When it is set the worker SHALL stop the preparation, by terminating the running ffmpeg process if a
clip is in progress, and transition the job `running → canceled`. No temporary or `.part` file of the job SHALL
remain in the proxy cache, no incomplete entry SHALL exist, and entries of clips finished before the cancel SHALL
stay. A cancellation SHALL NOT be recorded as a failed clip.

#### Scenario: Cancel inside a clip's encode
- **WHEN** `cancel_requested` is set while the second of three long clips is encoding
- **THEN** within about two seconds that ffmpeg process is gone, the job ends `canceled`, the third clip is not
  started, the first clip's entry remains, and the cache holds no `.part` or temporary file

#### Scenario: Cancel between clips
- **WHEN** `cancel_requested` is set while the worker moves from one clip to the next
- **THEN** the next clip is not started and the job ends `canceled`

#### Scenario: A canceled job can be enqueued again
- **WHEN** a canceled `proxy` job's event is enqueued again
- **THEN** a new job is created and prepares only the clips without an entry

### Requirement: A proxy job survives a restart
A graceful shutdown (SIGINT or SIGTERM) SHALL requeue an in-flight `proxy` job like any job, stop its ffmpeg process,
and leave no `.part` file of it in the proxy cache. Startup reconciliation SHALL requeue a `proxy` job orphaned by a
crash like any `running` job. A requeued `proxy` job SHALL, when claimed again, cost no ffmpeg process for any clip
that was finished before. A temporary file left by a killed process SHALL NOT make the re-run fail or yield an
incomplete entry.

#### Scenario: SIGTERM requeues a proxy job
- **WHEN** the worker receives SIGTERM while a `proxy` job encodes its second clip
- **THEN** the job returns to `queued` before the process exits and the cache holds no `.part` file of it

#### Scenario: A crash is recovered
- **WHEN** a worker is killed while a `proxy` job runs, and a new worker starts
- **THEN** the job is requeued and claimed, the first clip (finished earlier) costs no ffmpeg process, the
  clip that was in flight is encoded again, and the job ends `done`

#### Scenario: A leftover temporary file is harmless
- **WHEN** the cache holds a stale temporary file of a clip a killed process was writing
- **THEN** a later `proxy` job for the event prepares that clip normally and ends `done`
