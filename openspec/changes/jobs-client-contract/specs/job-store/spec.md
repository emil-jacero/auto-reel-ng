## MODIFIED Requirements

### Requirement: Enqueue a job
The store SHALL expose an operation that inserts a new `queued` job for a given project root and
root-relative event identity, with optional `device` (default `auto`), `output_path`, `force` (default
false), and `fingerprint` (the gate's enqueue-time value, stamped for observability). Enqueue MUST NOT
execute or schedule anything — it only records intent; the staleness decision belongs to the callers, not
the store. When an active (`queued`/`running`) job already exists for the same (`project_root`,
`event_dir`), enqueue SHALL NOT insert (idempotent enqueue).

Enqueue SHALL report both the job's id and whether this call created it: the new job's id with *created*
when it inserted a row, and the existing active job's id with *not created* when it did not. The report
SHALL be decided by the insertion itself, with the database's one-active-job-per-event guarantee as the
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

#### Scenario: Concurrent enqueues agree on one creation
- **WHEN** two enqueues for `2024/2024-06-27 - Grillning med grannar` run concurrently and the event has no
  active job
- **THEN** one row exists, one report says *created* and the other *not created*, and both name that row's id

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

### Requirement: Query jobs
The store SHALL expose read operations to fetch a job by id and to list jobs filtered by status, ordered
by `created_at`. These back the later API/GUI without granting them write access to the queue mechanics.

The store SHALL also expose a read of the jobs that finished since a given instant: every job whose
`finished_at` (stamped only by a terminal transition) is at or after that instant minus a caller-given
overlap, ordered by `finished_at` ascending, returned together with the database's current time as seen by
the same read. When no instant is given, the database's current time is the instant. The instant and the
returned time SHALL be database time, the same clock that stamps `finished_at`, so a caller that passes
back the time it received never depends on the application host's clock.

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
