## ADDED Requirements

### Requirement: Job schema captures the full lifecycle
The `jobs` table SHALL persist, for each job: a unique id, the event identity (`event_dir`), an optional
`output_path`, a `status` of exactly one of `queued` / `running` / `done` / `failed` / `canceled`, a
`device` selector (`auto` or a render-node id), an integer `priority` (default 0, reserved-unused in v1),
a `progress` fraction in `[0.0, 1.0]` (default 0.0), a nullable `error`, a nullable `fingerprint`
(reserved for §8.14), a nullable `worker_id`, and `created_at` / `started_at` / `finished_at` timestamps.
Timestamps MUST be sourced from the database server, not application wall-clock.

#### Scenario: A new job persists with defaults
- **WHEN** a job is enqueued for an event with no explicit priority or device
- **THEN** the stored row has `status = queued`, `priority = 0`, `device = auto`, `progress = 0.0`, a
  server-assigned `created_at`, and null `started_at` / `finished_at` / `error` / `fingerprint`

#### Scenario: Status is constrained
- **WHEN** a write attempts to set `status` to a value outside the five allowed states
- **THEN** the database rejects it

### Requirement: Enqueue a job
The store SHALL expose an operation that inserts a new `queued` job for a given event identity, optional
`device` (default `auto`) and `output_path`, returning the created job's id. Enqueue MUST NOT execute or
schedule anything — it only records intent.

#### Scenario: Enqueue records a queued job
- **WHEN** `enqueue(event_dir, device="renderD128")` is called
- **THEN** a new row exists with `status = queued`, `device = "renderD128"`, and the returned id addresses it

### Requirement: Race-free claim-next
The store SHALL expose a `claim_next` operation that atomically selects the highest-priority, oldest
`queued` job eligible for the caller's device filter and transitions it to `running`, stamping `worker_id`
and `started_at`. Two workers calling `claim_next` concurrently MUST NEVER claim the same job; selection
MUST use `FOR UPDATE SKIP LOCKED` rather than locking the whole queue. Ordering MUST be `priority`
descending then `created_at` ascending (FIFO within a priority).

#### Scenario: Two workers never claim the same job
- **WHEN** two workers call `claim_next` concurrently against a queue with one eligible job
- **THEN** exactly one worker receives the job (now `running` with its `worker_id`) and the other receives
  nothing, with neither blocking on the other

#### Scenario: FIFO within priority
- **WHEN** several `queued` jobs share the default priority
- **THEN** `claim_next` returns them in ascending `created_at` order

#### Scenario: Device filter excludes ineligible jobs
- **WHEN** a worker claims with a device filter that a `queued` job's `device` does not satisfy
- **THEN** that job is not returned to this worker

### Requirement: Transition a running job to a terminal state
The store SHALL expose an operation to move a `running` job to `done`, `failed`, or `canceled`, stamping
`finished_at` and, for `failed`, recording an `error` message. Transitioning a job that is not `running`
MUST be rejected (no `done` from `queued`, no re-terminating a finished job).

#### Scenario: Successful completion
- **WHEN** a `running` job transitions to `done`
- **THEN** its `status` is `done`, `finished_at` is set, and `error` is null

#### Scenario: Failure records the reason
- **WHEN** a `running` job transitions to `failed` with a message
- **THEN** its `status` is `failed`, `finished_at` is set, and `error` holds the message

#### Scenario: Illegal transition rejected
- **WHEN** a transition to a terminal state is attempted on a job whose status is not `running`
- **THEN** the operation is rejected and the row is unchanged

### Requirement: Update job progress
The store SHALL expose an operation to persist a job's `progress` fraction (the value the engine's
`on_progress` callback already emits). A progress update MUST only apply to a `running` job and MUST clamp
to `[0.0, 1.0]`.

#### Scenario: Progress persists for a running job
- **WHEN** `set_progress(job_id, 0.42)` is called on a `running` job
- **THEN** the stored `progress` is `0.42`

#### Scenario: Progress ignored for non-running jobs
- **WHEN** `set_progress` is called on a `queued`, `done`, `failed`, or `canceled` job
- **THEN** the stored `progress` is unchanged

### Requirement: Query jobs
The store SHALL expose read operations to fetch a job by id and to list jobs filtered by status, ordered
by `created_at`. These back the later API/GUI without granting them write access to the queue mechanics.

#### Scenario: Fetch by id
- **WHEN** a job's id is queried
- **THEN** its current row (status, progress, timestamps, error) is returned, or null if absent

#### Scenario: List by status
- **WHEN** jobs are listed filtered to `queued`
- **THEN** only `queued` jobs are returned, ordered by `created_at` ascending

### Requirement: Reconcile orphaned running jobs
The store SHALL expose a query that returns jobs left in `running` by a worker that is no longer live
(orphaned by a crash or restart). This query is the input to the scheduler's requeue policy (7b); this
capability provides the detection, not the requeue decision.

#### Scenario: Orphaned running job is surfaced
- **WHEN** a job is `running` with a `worker_id` that is not among the live workers (or older than the
  reconcile cutoff)
- **THEN** the reconcile query returns that job

#### Scenario: Active running job is not surfaced
- **WHEN** a job is `running` under a currently live worker
- **THEN** the reconcile query does not return that job

### Requirement: Cancel a queued job
The store SHALL expose an operation to cancel a `queued` job, moving it to `canceled` and stamping
`finished_at`, so it is never claimed. Cancellation of a *running* job (terminating the live ffmpeg) is a
scheduler concern (7b) and is out of scope here.

#### Scenario: Queued job is canceled before it runs
- **WHEN** a `queued` job is canceled
- **THEN** its `status` is `canceled` and a subsequent `claim_next` never returns it
