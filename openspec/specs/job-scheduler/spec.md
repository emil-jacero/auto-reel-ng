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
the claim loop's bound on in-flight jobs counts every job except `proxy` and `analysis` jobs, so a render that
waits for the CPU token behind a proxy job does not keep a GPU-classified render from being claimed. Among jobs
of one kind the order is unchanged (`priority` descending, then oldest first). A running proxy job is never
interrupted for a render, but it starts no further clip while one runs ("A proxy job yields to running renders").

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
active analysis job already exists, with the job's id. With `--force` the queued jobs carry `force`, and an active
analysis job that is still `queued` without `force` SHALL be given `force`, so the request is not lost; an active job
that is already `running` without `force` is left as it is, and the line for its event SHALL say so. It SHALL run no
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

#### Scenario: Re-analyze meets a queued unforced job
- **WHEN** `auto-reel analyze <root> --enqueue` queues an event's job and, before a worker claims it,
  `auto-reel analyze <root> --enqueue --force` runs for the same event
- **THEN** the second run prints the same job id as already active, that job's `force` is now true, one `analysis`
  row exists, and the worker that claims it analyzes every clip again, a clip with a failure marker included

#### Scenario: Re-analyze meets a running unforced job
- **WHEN** an event's unforced `analysis` job is `running` and `auto-reel analyze <root> --enqueue --force` runs
- **THEN** the running job's `force` stays false, the line for the event names the job as active and says it is
  already running without `--force`, and the command exits 0

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
