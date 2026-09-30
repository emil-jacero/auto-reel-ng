## MODIFIED Requirements

### Requirement: Jobs lifecycle over REST
The service SHALL expose the job store thinly: `POST /api/v1/jobs` enqueues an event (device optional,
default `auto`; `force` optional, default false) after applying the staleness gate — returning 201 with
the job on creation, **409 with the existing job's id** when an active job already exists for the event,
and a distinct **"fresh — not enqueued" outcome** (200 with the fresh verdict and its manifest reference)
when the event is fresh and `force` is false; a forced request always enqueues. The enqueued job carries
the event's fingerprint and the force flag. `GET /api/v1/jobs` lists jobs (filterable by status);
`GET /api/v1/jobs/{id}` returns one job's detail (status, progress, device, worker, force, fingerprint,
timestamps, error, requeue count); `POST /api/v1/jobs/{id}/cancel` invokes the store's cancel request (flag
a running job, cancel a queued one directly, no-op reported for terminal jobs). The API MUST NOT transition
job status itself.

A 201 SHALL mean that this request created the job. Whether a job was created SHALL be decided by the store
at the moment of insertion, not by an earlier read: an enqueue that finds, at insertion, an active job
created by a concurrent request SHALL answer 409 with that job's id, exactly like an enqueue that finds it
beforehand, and never 201.

The job id a problem body is about SHALL be carried in a typed `job_id` field of the shared problem body:
the active job's id on the enqueue 409, and the requested id on the 404 of the job detail and of cancel. The
404 of an enqueue for an unknown event SHALL name the event in `event_id`.

A cancellation's reported outcome SHALL be the one the store applied in the same transaction that applied
it (see the job store's cancel request): `flagged-running`, `canceled-queued` or `no-op-terminal`, together
with the job's status after that transaction. It SHALL NOT be derived from an earlier read of the job.

A job's `event_dir` SHALL be the event's root-relative id: a job enqueued with an event id that the events
routes returned as `event_id` SHALL carry exactly that value as its `event_dir`, so a client matches jobs
to events by equality. The schema SHALL describe the field so.

The service's OpenAPI schema SHALL publish every one of these responses: for the enqueue, the 201 job, the
200 fresh result (whose `status` is the constant `fresh`), and the 404 and 409 problem bodies; for the job
detail and for cancel, the 404 problem body. Every published problem response SHALL use the shared problem
body shape.

#### Scenario: Enqueue over REST
- **WHEN** `POST /api/v1/jobs` names `2024/2024-06-27 - Grillning med grannar`, whose title was edited
  after its last render, and it has no active job
- **THEN** a `queued` job row exists carrying the event's fingerprint, and the response is 201 with the
  job, whose `event_dir` is `2024/2024-06-27 - Grillning med grannar`

#### Scenario: Fresh event is not enqueued
- **WHEN** `POST /api/v1/jobs` names the rendered, unchanged `2023/2023-06-23 - Midsommar - Dalarna`
  without `force`
- **THEN** no job is created, and the response is 200 with `status` `fresh`, the event id, its fingerprint
  and its manifest reference

#### Scenario: Force enqueues a fresh event
- **WHEN** `POST /api/v1/jobs` names `2023/2023-06-23 - Midsommar - Dalarna` with `"force": true`
- **THEN** a `queued` job with `force = true` is created and the response is 201

#### Scenario: Duplicate enqueue is a visible conflict
- **WHEN** `POST /api/v1/jobs` names `2024/Blandat`, which already has a `queued` job that no worker has
  claimed
- **THEN** the response is 409 whose `job_id` is that queued job's id, and no new row is inserted

#### Scenario: An enqueue that loses a race is a conflict, not a creation
- **WHEN** two `POST /api/v1/jobs` requests for `2024/2024-06-27 - Grillning med grannar` both pass the
  active-job check before either inserts
- **THEN** exactly one response is 201, the other is 409 whose `job_id` is the job the 201 returned, and
  one job row exists

#### Scenario: Unknown event on enqueue
- **WHEN** `POST /api/v1/jobs` names `2024/2024-12-24 - Finns inte`, which is not a directory under the
  project root
- **THEN** the response is 404 with the shared problem body naming the event in `event_id`

#### Scenario: Unknown job id
- **WHEN** `GET /api/v1/jobs/{id}` or `POST /api/v1/jobs/{id}/cancel` names a well-formed id that no job has
- **THEN** the response is 404 with the shared problem body whose `job_id` is the requested id, and no row
  changes

#### Scenario: Cancel a running job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the `running` job a worker is rendering for
  `2024/2024-08-02 - Badutflykt - Varberg`
- **THEN** the job's `cancel_requested` flag is set, its status is unchanged, and the response's outcome is
  `flagged-running` with status `running`

#### Scenario: Cancel a queued job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the unclaimed `queued` job of `2024/Blandat`
- **THEN** the job is `canceled`, and the response's outcome is `canceled-queued` with status `canceled`

#### Scenario: Cancel a finished job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the `failed` job of `2024/2024-10-05 - Trasig`
- **THEN** nothing changes, and the response's outcome is `no-op-terminal` with status `failed`

#### Scenario: A cancel racing a claim reports what it did
- **WHEN** a worker claims the `queued` job of `2024/Blandat` while a cancel request for it is in flight
- **THEN** the response's outcome and status agree: either `canceled-queued` with `canceled` (the cancel
  applied first, and the worker never claims the job), or `flagged-running` with `running` and
  `cancel_requested` set (the claim applied first); never `canceled-queued` with `running`

#### Scenario: The schema publishes the jobs responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the enqueue declares its 201 job, its 200 fresh result with `status` the required constant
  `fresh`, and its 404 and 409 problem bodies; the job detail and cancel each declare a 404 problem body;
  the problem body declares `job_id`; and the job's `event_dir` carries a description naming it the event id

### Requirement: WebSocket live job updates
The service SHALL expose `WS /api/v1/ws/jobs`. On connect a subscriber SHALL immediately receive a full
snapshot of active (`queued`/`running`) jobs; thereafter it SHALL receive delta messages for job progress
and status changes — including terminal transitions — and for a change of a job's cancel-requested flag,
observed by a central poller that queries the store at the configured interval (default 1 s). The poller
SHALL run only while at least one subscriber is connected. A subscriber that cannot keep up (full outbound
queue) SHALL be disconnected rather than back-pressuring the hub; its recovery path is
reconnect-and-resnapshot.

A connected subscriber SHALL receive every job's terminal transition exactly once, including a job that no
earlier frame carried because its whole active life fell between two polls. Each poll SHALL therefore also
read the jobs whose terminal transition the store stamped since the previous poll, over a window that
overlaps the previous one far enough to include a transition committed after the previous poll's read.
The poller SHALL send each such job's terminal row in that poll's delta unless an earlier frame already
carried the job as terminal, so the overlap never sends a job twice. A job that became terminal before the
poller started is not sent; a client reconciles such jobs after the snapshot.

Every message SHALL be one frame shape: a `type` drawn from the closed set `snapshot` | `delta`, and the
list of jobs in the same job shape the jobs routes return. The list SHALL always be present (a snapshot
of no active jobs carries an empty list). Although a WebSocket route is not an HTTP operation, the
service's OpenAPI schema SHALL publish this frame shape and its type set as named schema components, with
both fields required, so a client generated from the schema has the frame's type without declaring it by
hand. The schema SHALL NOT describe the WebSocket as an HTTP path.

#### Scenario: Snapshot on connect
- **WHEN** a client connects while two jobs are active
- **THEN** its first message is a snapshot containing both jobs' current status and progress

#### Scenario: Progress and completion are pushed
- **WHEN** a running job's stored progress advances and the job later transitions to `done`
- **THEN** subscribers receive delta messages for the progress change and for the terminal transition
  within approximately one poll interval each

#### Scenario: A job that lived and ended between two polls is pushed once
- **WHEN** a client is connected, and a job for `2024/2024-10-05 - Trasig` is enqueued, claimed and fails
  at probe entirely between two polls, so no frame ever carried it as `queued` or `running`
- **THEN** within approximately one poll interval the client receives one delta whose row for that job
  has status `failed` and its error
- **AND** no later delta carries that job again, although the next polls' windows still include its
  terminal transition

#### Scenario: A cancel request is pushed
- **WHEN** a cancel is requested for the `running` job of `2024/2024-08-02 - Badutflykt - Varberg` while its
  stored progress does not change
- **THEN** subscribers receive, within approximately one poll interval, a delta whose row for that job has
  `cancel_requested` true and status `running`

#### Scenario: Idle service does not poll
- **WHEN** no WebSocket subscriber is connected
- **THEN** the central poller issues no store queries

#### Scenario: The schema publishes the frame
- **WHEN** the service's OpenAPI schema is generated
- **THEN** its components include the frame shape, whose required `type` references the enumeration
  `snapshot` | `delta` and whose required `jobs` items reference the published job shape, and no path
  describes `/api/v1/ws/jobs`

## ADDED Requirements

### Requirement: Cancel outcome and WebSocket frame type are closed, published vocabularies
A cancellation result's outcome SHALL be drawn from the job store's closed set of cancel outcomes
(`flagged-running`, `canceled-queued`, `no-op-terminal`), and a WebSocket frame's type from the closed set
`snapshot` | `delta`. The service's OpenAPI schema SHALL publish each set as an enumeration rather than as a
free-form string, so a client can derive an exhaustive type for each, and removing or renaming a value is a
compile-time failure in generated client code rather than a silent runtime change (D-8, §4.10).

This requirement MUST NOT change any value on the wire: a client reading an outcome or a frame type as a
plain string continues to read the same strings.

#### Scenario: The schema publishes the cancel outcome set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the cancellation result's outcome is described as the enumeration `flagged-running`,
  `canceled-queued`, `no-op-terminal`, not as an unconstrained string

#### Scenario: A renamed outcome breaks the client build
- **WHEN** a cancel outcome is renamed in the job store and the schema and client types are regenerated
- **THEN** client code that referred to the old outcome fails to compile, rather than silently ceasing to
  match

#### Scenario: Wire values are unchanged
- **WHEN** a client that treats outcomes and frame types as plain strings cancels the queued job of
  `2024/Blandat` and reads the WebSocket
- **THEN** it receives `canceled-queued`, and frames typed `snapshot` then `delta`, the same strings it
  received before this change
