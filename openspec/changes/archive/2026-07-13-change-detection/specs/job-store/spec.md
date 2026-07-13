## MODIFIED Requirements

### Requirement: Job schema captures the full lifecycle
The `jobs` table SHALL persist, for each job: a unique id, the event identity (`event_dir`, stored
**relative to the project root**), a nullable `project_root` (the absolute project root recorded at
enqueue), an optional `output_path`, a `status` of exactly one of `queued` / `running` / `done` / `failed`
/ `canceled`, a `device` selector (`auto` or a render-node id), an integer `priority` (default 0,
reserved-unused in v1), a `progress` fraction in `[0.0, 1.0]` (default 0.0), a `cancel_requested` boolean
(default false), a `force` boolean (default false — bypass the staleness gate and replace output), a
nullable `error`, a nullable `fingerprint` (the event's render fingerprint computed at enqueue), a
nullable `worker_id`, and `created_at` / `started_at` / `finished_at` timestamps. Timestamps MUST be
sourced from the database server, not application wall-clock. At most one **active** (`queued` or
`running`) job SHALL exist per (`project_root`, `event_dir`), enforced by the database.

#### Scenario: A new job persists with defaults
- **WHEN** a job is enqueued for an event with no explicit priority, device, or force
- **THEN** the stored row has `status = queued`, `priority = 0`, `device = auto`, `progress = 0.0`,
  `cancel_requested = false`, `force = false`, a server-assigned `created_at`, and null `started_at` /
  `finished_at` / `error`

#### Scenario: Status is constrained
- **WHEN** a write attempts to set `status` to a value outside the five allowed states
- **THEN** the database rejects it

#### Scenario: Duplicate active job is rejected by the database
- **WHEN** an insert would create a second `queued`/`running` job for the same (`project_root`, `event_dir`)
- **THEN** the database rejects it (finished jobs — `done`/`failed`/`canceled` — do not block a new one)

### Requirement: Enqueue a job
The store SHALL expose an operation that inserts a new `queued` job for a given project root and
root-relative event identity, with optional `device` (default `auto`), `output_path`, `force` (default
false), and `fingerprint` (the gate's enqueue-time value, stamped for observability), returning the
created job's id. Enqueue MUST NOT execute or schedule anything — it only records intent; the staleness
decision belongs to the callers, not the store. When an active (`queued`/`running`) job already exists for
the same (`project_root`, `event_dir`), enqueue SHALL return the existing job's id instead of inserting
(idempotent enqueue), reporting that no new job was created.

#### Scenario: Enqueue records a queued job
- **WHEN** `enqueue(project_root, event_dir, device="renderD128", force=True, fingerprint="abc…")` is
  called
- **THEN** a new row exists with `status = queued`, `device = "renderD128"`, `force = true`, the given
  fingerprint, the given `project_root` and root-relative `event_dir`, and the returned id addresses it

#### Scenario: Enqueue is idempotent for an active event
- **WHEN** `enqueue` is called for an event that already has a `queued` or `running` job
- **THEN** no new row is inserted and the existing job's id is returned
