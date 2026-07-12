## MODIFIED Requirements

### Requirement: Job schema captures the full lifecycle
The `jobs` table SHALL persist, for each job: a unique id, the event identity (`event_dir`, stored
**relative to the project root**), a nullable `project_root` (the absolute project root recorded at
enqueue), an optional `output_path`, a `status` of exactly one of `queued` / `running` / `done` / `failed`
/ `canceled`, a `device` selector (`auto` or a render-node id), an integer `priority` (default 0,
reserved-unused in v1), a `progress` fraction in `[0.0, 1.0]` (default 0.0), a `cancel_requested` boolean
(default false), a nullable `error`, a nullable `fingerprint` (reserved for §8.14), a nullable
`worker_id`, and `created_at` / `started_at` / `finished_at` timestamps. Timestamps MUST be sourced from
the database server, not application wall-clock. At most one **active** (`queued` or `running`) job SHALL
exist per (`project_root`, `event_dir`), enforced by the database.

#### Scenario: A new job persists with defaults
- **WHEN** a job is enqueued for an event with no explicit priority or device
- **THEN** the stored row has `status = queued`, `priority = 0`, `device = auto`, `progress = 0.0`,
  `cancel_requested = false`, a server-assigned `created_at`, and null `started_at` / `finished_at` /
  `error` / `fingerprint`

#### Scenario: Status is constrained
- **WHEN** a write attempts to set `status` to a value outside the five allowed states
- **THEN** the database rejects it

#### Scenario: Duplicate active job is rejected by the database
- **WHEN** an insert would create a second `queued`/`running` job for the same (`project_root`, `event_dir`)
- **THEN** the database rejects it (finished jobs — `done`/`failed`/`canceled` — do not block a new one)

### Requirement: Enqueue a job
The store SHALL expose an operation that inserts a new `queued` job for a given project root and
root-relative event identity, optional `device` (default `auto`) and `output_path`, returning the created
job's id. Enqueue MUST NOT execute or schedule anything — it only records intent. When an active
(`queued`/`running`) job already exists for the same (`project_root`, `event_dir`), enqueue SHALL return
the existing job's id instead of inserting (idempotent enqueue), reporting that no new job was created.

#### Scenario: Enqueue records a queued job
- **WHEN** `enqueue(project_root, event_dir, device="renderD128")` is called
- **THEN** a new row exists with `status = queued`, `device = "renderD128"`, the given `project_root` and
  root-relative `event_dir`, and the returned id addresses it

#### Scenario: Enqueue is idempotent for an active event
- **WHEN** `enqueue` is called for an event that already has a `queued` or `running` job
- **THEN** no new row is inserted and the existing job's id is returned

## ADDED Requirements

### Requirement: Request cancellation of a job
The store SHALL expose a `request_cancel` operation. For a `running` job it sets `cancel_requested = true`
and does not change `status` — the worker observes the flag and performs the terminal transition. For a
`queued` job it cancels directly (equivalent to `cancel_queued`). For a job already in a terminal state it
is a no-op reporting that nothing changed.

#### Scenario: Running job is flagged, not transitioned
- **WHEN** `request_cancel` is called on a `running` job
- **THEN** `cancel_requested` becomes true and `status` remains `running`

#### Scenario: Queued job is canceled immediately
- **WHEN** `request_cancel` is called on a `queued` job
- **THEN** the job becomes `canceled` and is never claimed

### Requirement: Requeue a running job
The store SHALL expose a `requeue` operation that resets a `running` job to `queued`, clearing
`worker_id`, `started_at`, and `progress` (and leaving `cancel_requested` intact so a cancel requested
before a crash still applies after requeue). Requeueing a job that is not `running` MUST be rejected. The
operation SHALL increment a `requeue_count` on the row so repeated crash-requeue loops are visible.

#### Scenario: Orphan reset for a fresh claim
- **WHEN** `requeue` is called on a `running` job
- **THEN** the job is `queued` with null `worker_id`/`started_at`, `progress = 0.0`, and an incremented
  `requeue_count`, and a subsequent `claim_next` can claim it

#### Scenario: Only running jobs can be requeued
- **WHEN** `requeue` is called on a `queued` or terminal-state job
- **THEN** the operation is rejected and the row is unchanged
