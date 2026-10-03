# job-store Specification

## Purpose

Own the durable `jobs` table and its repository API: the render lifecycle (`queued` → `running` →
`done`/`failed`/`canceled`), the `device` selector, FIFO ordering with a reserved `priority`, `progress`
reporting, and the operations — `enqueue`, race-free `claim_next`, terminal `transition`, `set_progress`,
read queries, and an orphaned-`running` reconcile query — that a separate worker process (and, later, the
scheduler and API) drive the queue through. This capability provides the store only; it does not execute
jobs or decide requeue policy.

## Requirements

### Requirement: Job schema captures the full lifecycle
The `jobs` table SHALL persist, for each job: a unique id, the event identity (`event_dir`, stored
**relative to the project root**), a nullable `project_root` (the absolute project root recorded at
enqueue), an optional `output_path`, a `status` of exactly one of `queued` / `running` / `done` / `failed`
/ `canceled`, a `device` selector (`auto` or a render-node id), an integer `priority` (default 0,
reserved-unused in v1), a `progress` fraction in `[0.0, 1.0]` (default 0.0), a `cancel_requested` boolean
(default false), a `force` boolean (default false — bypass the staleness gate and replace output), a
nullable `error`, a nullable `fingerprint` (the event's render fingerprint computed at enqueue), a
`kind` (text, never null, default `render`: what sort of work the job is; `render` and `proxy` are the kinds
this system defines), a nullable `worker_id`, and `created_at` / `started_at` / `finished_at` timestamps. Timestamps MUST be
sourced from the database server, not application wall-clock. At most one **active** (`queued` or
`running`) job SHALL exist per (`project_root`, `event_dir`, `kind`), enforced by the database: an event MAY
have an active job of each kind at once, and never two of one kind. The database MUST NOT restrict `kind` to
a closed set of values.

#### Scenario: A new job persists with defaults
- **WHEN** a job is enqueued for an event with no explicit priority, device, or force
- **THEN** the stored row has `status = queued`, `priority = 0`, `device = auto`, `progress = 0.0`,
  `cancel_requested = false`, `force = false`, `kind = render`, a server-assigned `created_at`, and null `started_at` /
  `finished_at` / `error`

#### Scenario: Status is constrained
- **WHEN** a write attempts to set `status` to a value outside the five allowed states
- **THEN** the database rejects it

#### Scenario: Duplicate active job is rejected by the database
- **WHEN** an insert would create a second `queued`/`running` job of the same `kind` for the same
  (`project_root`, `event_dir`)
- **THEN** the database rejects it (finished jobs — `done`/`failed`/`canceled` — do not block a new one)

#### Scenario: A render and a proxy job for one event are active together
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has a `running` `render` job and a `proxy` job is inserted
  for it as `queued`
- **THEN** both rows exist, and a second `queued` `proxy` job for the same event is rejected

#### Scenario: Existing rows become renders
- **WHEN** the schema is upgraded while `jobs` already holds `queued`, `running` and `done` rows
- **THEN** every existing row has `kind = render`, and a still-active one still blocks a second active render
  of its event

#### Scenario: The database accepts a kind this build does not know
- **WHEN** a row is inserted with `kind = "thumbnails"`
- **THEN** the database stores it (the worker, not the database, decides what a kind means)

### Requirement: Enqueue a job
The store SHALL expose an operation that inserts a new `queued` job for a given project root and
root-relative event identity, with optional `kind` (default `render`), `device` (default `auto`), `output_path`, `force` (default
false), and `fingerprint` (the gate's enqueue-time value, stamped for observability). Enqueue MUST NOT
execute or schedule anything — it only records intent; the staleness decision belongs to the callers, not
the store. When an active (`queued`/`running`) job of the same `kind` already exists for the same (`project_root`,
`event_dir`), enqueue SHALL NOT insert (idempotent enqueue); an active job of another kind does not count. The
lookup of an event's active job SHALL likewise take a `kind` (default `render`) and answer for that kind only.

Enqueue SHALL report both the job's id and whether this call created it: the new job's id with *created*
when it inserted a row, and the existing active job's id with *not created* when it did not. The report
SHALL be decided by the insertion itself, with the database's one-active-job-per-event-and-kind guarantee as the
arbiter, so two concurrent enqueues for the same event yield exactly one *created* and one *not created*
naming the same job. A caller that needs only the id MAY keep receiving only the id.

#### Scenario: Enqueue records a queued job
- **WHEN** enqueue is called for `2024/2024-06-27 - Grillning med grannar` with `device="renderD128"`,
  `force=True` and a fingerprint, and the event has no active job
- **THEN** a new row exists with `status = queued`, `device = "renderD128"`, `force = true`, the given
  fingerprint, the given `project_root` and root-relative `event_dir`, and the report names that row's id as
  *created*

#### Scenario: Enqueue is idempotent for an active event
- **WHEN** enqueue is called for `2024/Blandat`, which already has a `queued` job
- **THEN** no new row is inserted, and the report names the existing job's id as *not created*

#### Scenario: Enqueue is idempotent per kind
- **WHEN** `2024/Blandat` has a `queued` `render` job, and enqueue is called for it with `kind = "proxy"`, then
  again with `kind = "proxy"`
- **THEN** the first call inserts a `queued` `proxy` row and reports it *created*, and the second inserts
  nothing and reports that same row *not created*, while the `render` job is untouched

#### Scenario: The active-job lookup is per kind
- **WHEN** `2024/Blandat` has an active `proxy` job and no active `render` job, and its active job is looked up
  without a kind
- **THEN** the lookup finds no job, and the same lookup with `kind = "proxy"` finds the proxy job

#### Scenario: Concurrent enqueues agree on one creation
- **WHEN** two enqueues for `2024/2024-06-27 - Grillning med grannar` run concurrently and the event has no
  active job
- **THEN** one row exists, one report says *created* and the other *not created*, and both name that row's id

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

The store SHALL also expose a read of the jobs that finished since a given instant: every job whose
`finished_at` (stamped only by a terminal transition) is at or after that instant minus a caller-given
overlap, ordered by `finished_at` ascending, returned together with the database's current time as seen by
the same read. When no instant is given, the database's current time is the instant. The instant and the
returned time SHALL be database time, the same clock that stamps `finished_at`, so a caller that passes
back the time it received never depends on the application host's clock.

The status listing and the finished-since read SHALL each accept an optional project root. When one is
given, the read SHALL return only jobs recorded with exactly that project root, and never a job with no
recorded project root; the returned database time is unaffected. When none is given, it SHALL return every
project's jobs, as before.

The status listing and the finished-since read SHALL each accept an optional `kind`, which defaults to
`render`: by default they return only `render` jobs, so a caller that predates job kinds sees what it always
saw. An explicit `kind` narrows the read to that kind, and an explicit "every kind" selection returns jobs of
all kinds. The kind narrowing composes with the project narrowing and leaves the returned database time
unaffected. A read by id is not narrowed by kind.

#### Scenario: Fetch by id
- **WHEN** a job's id is queried
- **THEN** its current row (status, progress, timestamps, error) is returned, or null if absent

#### Scenario: List by status
- **WHEN** jobs are listed filtered to `queued`
- **THEN** only `queued` jobs are returned, ordered by `created_at` ascending

#### Scenario: List jobs finished since an instant
- **WHEN** the finished-since read returns time `T` with no overlap, then the `running` job of
  `2024/2024-10-05 - Trasig` is transitioned to `failed`, and the read is made again from `T` with no
  overlap
- **THEN** the second read returns the Trasig job with status `failed`, returns no `queued` or `running`
  job, and returns no job that finished before `T`

#### Scenario: The overlap reaches back before the instant
- **WHEN** a job finished shortly before time `T`, and the finished-since read is made from `T` with an
  overlap longer than that gap
- **THEN** the job is returned

#### Scenario: List by status within one project
- **WHEN** `queued` jobs exist for `2024/Blandat` under both `/dev/a/library` and `/dev/b/library`, and
  `queued` jobs are listed narrowed to `/dev/a/library`
- **THEN** only `/dev/a/library`'s job is returned
- **AND** the same listing without the project narrowing returns both jobs, ordered by `created_at`
  ascending

#### Scenario: Finished jobs within one project
- **WHEN** the finished-since read returns time `T`, then `running` jobs of `2024/2024-10-05 - Trasig` under
  both `/dev/a/library` and `/dev/b/library` are transitioned to `failed`, and the read is made again from
  `T` narrowed to `/dev/a/library`
- **THEN** only `/dev/a/library`'s job is returned
- **AND** the same read without the project narrowing returns both jobs

#### Scenario: Reads default to render jobs
- **WHEN** `2024/Blandat` has a `queued` `render` job and a `queued` `proxy` job, and `queued` jobs are
  listed without a kind
- **THEN** only the `render` job is returned
- **AND** the same listing with `kind = "proxy"` returns only the proxy job, and with every kind selected
  returns both, ordered by `created_at` ascending

#### Scenario: A finished proxy job is not a finished render
- **WHEN** the finished-since read returns time `T`, then a `running` `proxy` job of
  `2024/2024-10-05 - Trasig` is transitioned to `done`, and the read is made again from `T` without a kind
- **THEN** the proxy job is not returned, and it is returned when every kind is selected

#### Scenario: A job is fetched by id whatever its kind
- **WHEN** the id of a `proxy` job is queried
- **THEN** its row is returned

#### Scenario: A job with no recorded project root is never in a narrowed listing
- **WHEN** a `queued` job row has no recorded project root, and `queued` jobs are listed narrowed to
  `/dev/a/library`
- **THEN** that job is not returned, and the listing without narrowing still returns it

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

### Requirement: Request cancellation of a job
The store SHALL expose a cancel operation that decides and applies a cancellation in **one transaction**,
holding a lock on the job's row from the read of its status to the commit, so a concurrent claim, terminal
transition or requeue of the same job is applied entirely before or entirely after it. For a `running` job
it sets `cancel_requested = true` and does not change `status` — the worker observes the flag and performs
the terminal transition. For a `queued` job it cancels directly (equivalent to `cancel_queued`). For a job
already in a terminal state it changes nothing.

The operation SHALL report the outcome it applied, drawn from a closed set owned by the store:
`flagged-running`, `canceled-queued` or `no-op-terminal`, together with the job as it stands after the
transaction. It SHALL report a missing job distinctly from a terminal one. The existing request-cancel verb
SHALL keep its behavior for its callers: the job for a flagged or canceled job, nothing for a terminal or
missing one.

#### Scenario: Running job is flagged, not transitioned
- **WHEN** a cancel is requested for the `running` job of `2024/2024-08-02 - Badutflykt - Varberg`
- **THEN** `cancel_requested` becomes true, `status` remains `running`, and the outcome is `flagged-running`

#### Scenario: Queued job is canceled immediately
- **WHEN** a cancel is requested for the `queued` job of `2024/Blandat`
- **THEN** the job becomes `canceled` and is never claimed, and the outcome is `canceled-queued`

#### Scenario: Terminal job is left alone
- **WHEN** a cancel is requested for the `failed` job of `2024/2024-10-05 - Trasig`
- **THEN** the row is unchanged, and the outcome is `no-op-terminal` with the job's status `failed`

#### Scenario: Missing job is not a terminal job
- **WHEN** a cancel is requested for an id no job has
- **THEN** the operation reports that no such job exists, not a `no-op-terminal` outcome

#### Scenario: A cancel waits for a claim holding the row
- **WHEN** the `queued` job of `2024/Blandat` is being claimed in an uncommitted transaction that already
  holds its row, and a cancel for it starts
- **THEN** the cancel waits for that transaction, then reads the job as `running`, flags it, and reports
  `flagged-running`; it never overwrites the claimed job's status with `canceled`

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

### Requirement: Latest job per event in a project
The store SHALL expose a read that returns, for one project root, the most recent job of each event: for
every `event_dir` that has at least one job recorded with exactly that project root, the job of the requested `kind` (default `render`) with the
greatest `created_at`, whatever its status (`queued`, `running`, `done`, `failed` or `canceled`). The result
SHALL hold one job per event, keyed by `event_dir`, and SHALL be produced by a single query rather than one
lookup per event. A job recorded with a different project root, or with no project root, SHALL NOT appear. A job of another
kind SHALL NOT appear and SHALL NOT displace an event's latest job of the requested kind, however recent it
is; an explicit "every kind" selection ranks all of an event's jobs together.
An event whose jobs tie on `created_at` SHALL resolve to the same job on every read. The read MUST NOT
depend on a SQL construct that SQLAlchemy has deprecated, so it behaves identically across the supported
SQLAlchemy 2.x releases.

#### Scenario: The newest job of an event wins whatever its status
- **WHEN** `2024/2024-06-27 - Grillning med grannar` under `/dev/a/library` has a `done` job, later a
  `failed` job, and later still a `queued` job, and the latest-per-event read is made for `/dev/a/library`
- **THEN** the result holds the `queued` job for that event, and no other job of that event

#### Scenario: One job per event across several events
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has two jobs and `2024/Blandat` has one, all under
  `/dev/a/library`
- **THEN** the result has exactly two entries, keyed `2024/2024-06-27 - Grillning med grannar` (its newer
  job) and `2024/Blandat` (its only job)

#### Scenario: Other projects and unrooted jobs are excluded
- **WHEN** `2024/Blandat` has jobs under both `/dev/a/library` and `/dev/b/library`, `2024/2024-10-05 -
  Trasig` has a job with no recorded project root, and the read is made for `/dev/a/library`
- **THEN** the result holds only `/dev/a/library`'s job for `2024/Blandat`, and no entry for
  `2024/2024-10-05 - Trasig`

#### Scenario: A newer proxy job does not displace the latest render
- **WHEN** `2024/Blandat` under `/dev/a/library` has a `done` `render` job and later a `queued` `proxy` job,
  and the latest-per-event read is made for `/dev/a/library` without a kind
- **THEN** the entry for `2024/Blandat` is the `done` render job
- **AND** with `kind = "proxy"` it is the proxy job, and with every kind selected it is the proxy job (the
  newest of all)

#### Scenario: An event with only proxy jobs has no latest render
- **WHEN** `2024/Blandat` has only a `queued` `proxy` job and the read is made without a kind
- **THEN** the result has no entry for `2024/Blandat`

#### Scenario: A project with no jobs yields an empty result
- **WHEN** the read is made for a project root no job was recorded with
- **THEN** the result is empty

#### Scenario: A tie on creation time resolves the same way every time
- **WHEN** two jobs of `2024/Blandat` under `/dev/a/library` carry an identical `created_at`, and the read
  is made twice
- **THEN** both reads return the same one of those jobs
