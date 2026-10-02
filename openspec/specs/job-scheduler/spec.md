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

#### Scenario: Progress advances during a render
- **WHEN** a job is rendering
- **THEN** its stored `progress` increases monotonically toward 1.0 without a write per ffmpeg progress line

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

### Requirement: Cooperative cancellation between segments
The worker SHALL check the job's `cancel_requested` flag at segment boundaries during a render. When set,
the worker SHALL stop before the next segment, clean up its scratch work, and transition the job
`running → canceled`. The worker SHALL remain the sole writer of job status transitions.

#### Scenario: Running job is canceled at a segment boundary
- **WHEN** `cancel_requested` is set while a job is rendering segment k of n (k < n)
- **THEN** no segment after k is started, no output appears at the final path, and the job ends `canceled`

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
probes a clip or starts ffmpeg), the worker SHALL refuse the job when a different job that is `running` in
the job store writes the same output path, whichever project that job belongs to. A job's output path is its
project's output directory plus the file name its event's current metadata gives it; paths SHALL be compared
case-insensitively, after Unicode normalization, as for the batch commands' collision rule. The refused job
SHALL transition to `failed` with a reason that names the shared output path and the running job's event,
and SHALL NOT render, write the event's `reel.yaml`, write a render manifest or an `<output>.part` file, or
touch an output file that exists at that path. The running job is never interrupted. The check applies to a
`force` job as to any other, and a requeued job (for example after a worker restart) SHALL be checked again at
its next claim.

A job's own row, which is `running` from the moment it is claimed, SHALL NOT count as another running job. A
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

#### Scenario: A job's own row never blocks itself
- **WHEN** a worker claims a job, which makes its own row `running`
- **THEN** that row is not counted as another running job

#### Scenario: A running job whose event cannot be loaded claims nothing
- **WHEN** another `running` job's event folder has since been deleted, and a worker claims a job
- **THEN** the claimed job is not refused because of it

#### Scenario: A refusal does not hold a capacity token
- **WHEN** a claimed job is refused because of a running job
- **THEN** no capacity token was taken for it, and a following job can start at once
