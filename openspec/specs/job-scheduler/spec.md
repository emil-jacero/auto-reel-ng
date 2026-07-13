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
mirroring the CLI batch's per-event isolation.

#### Scenario: Failed plan rebuild fails only that job
- **WHEN** a claimed job's event directory no longer exists
- **THEN** the job is marked `failed` with the cause and the worker continues claiming other jobs

### Requirement: Graceful shutdown
On SIGINT/SIGTERM the worker SHALL stop claiming, requeue its in-flight jobs (`running → queued`), and
exit cleanly. No job may be left `running` by a cleanly-stopped worker.

#### Scenario: Signal during a render requeues the job
- **WHEN** the worker receives SIGTERM while a job renders
- **THEN** the job returns to `queued` before the process exits, and no partial file exists at the final
  output path
