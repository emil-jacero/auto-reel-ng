## MODIFIED Requirements

### Requirement: Jobs lifecycle over REST
The service SHALL expose the job store thinly: `POST /api/v1/jobs` enqueues an event (device optional,
default `auto`; `force` optional, default false) after applying the staleness gate — returning 201 with
the job on creation, **409 with the existing job's id** when an active **render** job already exists for the event
(a proxy job of the event is not one: see "A proxy job and a render job of one event do not block each other"),
and a distinct **"fresh — not enqueued" outcome** (200 with the fresh verdict and its manifest reference)
when the event is fresh and `force` is false; a forced request always enqueues unless the
output-collision check or the missing-clip check refuses it. The enqueued job carries the event's
fingerprint and the force flag.
`GET /api/v1/jobs` lists the served project's jobs of every kind, each carrying its `kind` (filterable by
status); `GET /api/v1/jobs/{id}` returns one job's detail, of either kind (kind, status, progress, device,
worker, force, fingerprint, timestamps, error, requeue count);
`POST /api/v1/jobs/{id}/cancel` invokes the store's cancel request on a job of either kind (flag a running job,
cancel a queued one directly, no-op reported for terminal jobs). The API MUST NOT transition job status itself.

A 201 SHALL mean that this request created the job. Whether a job was created SHALL be decided by the store
at the moment of insertion, not by an earlier read: an enqueue that finds, at insertion, an active job
created by a concurrent request SHALL answer 409 with that job's id, exactly like an enqueue that finds it
beforehand, and never 201.

The job id a problem body is about SHALL be carried in a typed `job_id` field of the shared problem body:
the active job's id on the enqueue 409, and the requested id on the 404 of the job detail and of cancel. The
404 of an enqueue for an unknown event SHALL name the event in `event_id`.

Every 409 that `POST /api/v1/jobs` returns SHALL carry the conflict kind in a `conflict` field, drawn from
the published enumeration of "Enqueue refuses an event whose output path another event claims":
`active_job` on the active-job 409, whether the job was found beforehand or at insertion,
`output_collision` on that requirement's refusal, which is checked first, and `missing_clips` on the
refusal of "Enqueue refuses an event that plays a clip missing from disk".

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
- **WHEN** `POST /api/v1/jobs` names `2023/2023-06-23 - Midsommar - Dalarna`, whose output path no other
  event claims, with `"force": true`
- **THEN** a `queued` job with `force = true` is created and the response is 201

#### Scenario: Duplicate enqueue is a visible conflict
- **WHEN** `POST /api/v1/jobs` names `2024/Blandat`, which already has a `queued` render job that no worker
  has claimed
- **THEN** the response is 409 with `conflict` `active_job` whose `job_id` is that queued job's id, and no
  new row is inserted

#### Scenario: An enqueue that loses a race is a conflict, not a creation
- **WHEN** two `POST /api/v1/jobs` requests for `2024/2024-06-27 - Grillning med grannar` both pass the
  active-job check before either inserts
- **THEN** exactly one response is 201, the other is 409 with `conflict` `active_job` whose `job_id` is the
  job the 201 returned, and one job row exists

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
snapshot of active (`queued`/`running`) jobs of every kind; thereafter it SHALL receive delta messages for job progress
and status changes — including terminal transitions — and for a change of a job's cancel-requested flag,
observed by a central poller that queries the store at the configured interval (default 1 s). The poller
SHALL run only while at least one subscriber is connected. A subscriber that cannot keep up (full outbound
queue) SHALL be disconnected rather than back-pressuring the hub, with WebSocket close code 1013 (try again
later); its recovery path is reconnect-and-resnapshot.

A connected subscriber SHALL receive every job's terminal transition exactly once, including a job that no
earlier frame carried because its whole active life fell between two polls. Each poll SHALL therefore also
read the jobs whose terminal transition the store stamped since the previous poll, over a window that
overlaps the previous one far enough to include a transition committed after the previous poll's read.
The poller SHALL send each such job's terminal row in that poll's delta unless an earlier frame already
carried the job as terminal, so the overlap never sends a job twice. A job that became terminal before the
poller started is not sent; a client reconciles such jobs after the snapshot.

Every message SHALL be one frame shape: a `type` drawn from the closed set `snapshot` | `delta` |
`heartbeat`, and the list of jobs in the same job shape the jobs routes return. The list SHALL always be
present (a snapshot of no active jobs carries an empty list, and a heartbeat always carries one). Although a WebSocket route is not an HTTP operation, the
service's OpenAPI schema SHALL publish this frame shape and its type set as named schema components, with
both fields required, so a client generated from the schema has the frame's type without declaring it by
hand. The schema SHALL NOT describe the WebSocket as an HTTP path.

A connection that has been sent no frame for 15 s SHALL be sent a `heartbeat` frame with no jobs, so a
client can tell an idle connection from a lost one: every frame, of any type, is proof of life, and a
connection that is receiving frames at least that often needs no heartbeat. A heartbeat is a property of
its connection alone. It SHALL NOT start the poller or read the store, SHALL NOT change which jobs any
frame carries, and SHALL NOT count against the connection's outbound queue, so it never causes a
slow-consumer drop. A heartbeat is never the first frame: a connection's first frame is its snapshot.

The service SHALL watch the client side of every connection for as long as it is open, so the end of a
connection releases its subscription at once, whichever side ends it:

- When the client closes the connection, or the connection is lost, its subscription SHALL be released
  within one second, whether or not any job changes. When it was the last subscription, the poller SHALL
  stop with it and the service SHALL issue no further store queries for the feed. The next subscriber then
  starts the poller again, so its snapshot is read at its connect.
- A peer that stops answering without closing (a sleeping laptop, a dropped network) SHALL be detected by a
  keepalive: the service pings every connection every 20 s and treats a ping unanswered for 20 s as a lost
  connection. The peer's subscription is then released as above, within about 40 s. The one exception is a
  peer that vanished after the frames sent to it had filled the host's TCP send buffer. Its subscription
  MAY be released later, at the latest when the hub drops it as a slow consumer or the host's TCP stack
  abandons the connection.
- Anything a client sends SHALL be ignored. The channel stays push-only, and the connection stays open and
  keeps receiving frames.
- When the service is stopped by one SIGINT or one SIGTERM, it SHALL close every open connection with close
  code 1012 (service restart), release their subscriptions, finish its orderly shutdown (the poller stopped
  and the database connections released) and exit within a few seconds, however many connections are open.
  No second signal SHALL be needed. The exception is a connection to such a vanished peer with frames still
  backed up. The server cannot finish closing it, so it can make the shutdown fail, or stall it until the
  host's TCP stack abandons the connection, which can take many minutes. A second SIGINT ends that stall:
  the forced stop drops the connection without waiting for it to close, and the process exits (headless-cli,
  "`serve` runs the API service"). Like any stop, a stop with one signal also waits for HTTP requests still
  being handled.
- The application shutdown (the event loop and the hub's stop) SHALL NOT wait for the database to answer,
  and a database that has stopped answering SHALL NOT freeze the service while it stops; the process itself
  exits only after an abandoned read ends (below). When a store read is stalled as the stop begins, whether the
  read of a poll or the first subscriber's snapshot read, the hub's stop completes within about a second and
  the event loop keeps serving meanwhile. The same read SHALL NOT hold a client that closes its connection
  during it: the connection's end (a client close, a lost peer, the server's own shutdown close) is observed
  while the snapshot is still being read, the read is abandoned, and the subscription is released at once.
  A subscriber that was waiting for that snapshot when the hub stopped receives no snapshot and its
  connection is closed with code 1013, and so is one that connects after the stop began. The abandoned read
  itself is not interrupted: it runs on until the database or the operating system ends it, and the
  process exits only after it has, which for a connection attempt is bounded by the connect timeout
  (persistence, "Postgres connections fail fast"). The orderly shutdown (application shutdown complete,
  database connections released) does not wait for it.

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

#### Scenario: An idle connection is sent heartbeats
- **WHEN** a client is connected while no job is active, and nothing changes for 40 s
- **THEN** after its snapshot it receives two `heartbeat` frames, each with an empty job list, about 15 s
  apart
- **AND** the store is read no more often than without the heartbeat, and the connection stays open

#### Scenario: A busy connection needs no heartbeat
- **WHEN** the `running` job of `2024/2024-08-02 - Badutflykt - Varberg` advances its progress every second
  for 30 s
- **THEN** the client receives a delta for each change and no heartbeat, because no 15 s passes without a
  frame

#### Scenario: A heartbeat does not cost a job
- **WHEN** a job's progress changes at the moment a connection's heartbeat falls due
- **THEN** the client receives that delta exactly once, before or after the heartbeat, and no later frame
  repeats it

#### Scenario: Idle service does not poll
- **WHEN** no WebSocket subscriber is connected
- **THEN** the central poller issues no store queries

#### Scenario: The schema publishes the frame
- **WHEN** the service's OpenAPI schema is generated
- **THEN** its components include the frame shape, whose required `type` references the enumeration
  `snapshot` | `delta` | `heartbeat` and whose required `jobs` items reference the published job shape, and no path
  describes `/api/v1/ws/jobs`

#### Scenario: Closing the last tab stops the poller
- **WHEN** the only connected client, a GUI tab showing the event list while no job is active, closes its
  connection
- **THEN** within one second the service has no subscriber, and it issues no store query for the feed
  afterwards, although no job changed
- **AND** a client that connects later receives a snapshot read at its connect, not one cached before the
  first tab closed

#### Scenario: Closing one of two tabs keeps the other live
- **WHEN** two clients are connected and one of them closes its connection, and the `running` job of
  `2024/2024-06-27 - Grillning med grannar` then advances its progress
- **THEN** the closed client's subscription is released within one second
- **AND** the remaining client receives the progress delta within approximately one poll interval

#### Scenario: A peer that vanished is released by the keepalive
- **WHEN** a laptop whose tab shows the event list while no job is active is suspended, so it neither
  closes the connection nor answers pings
- **THEN** within about 40 s the service releases its subscription, and when it was the last one, the
  poller stops

#### Scenario: A client's message is ignored
- **WHEN** a connected client sends a text message
- **THEN** the connection stays open, and the client keeps receiving deltas

#### Scenario: One signal stops a service with open connections
- **WHEN** `auto-reel serve` has a WebSocket client connected that has read its snapshot, and the process
  receives one SIGTERM, or, in a second run, one SIGINT
- **THEN** the client receives close code 1012
- **AND** the service completes its application shutdown and the process exits within five seconds,
  without a second signal

#### Scenario: A second SIGINT ends the stall behind a vanished peer
- **WHEN** `auto-reel serve` has a connection whose peer stopped reading with frames still backed up for
  it, one SIGINT has started the shutdown and it waits for that connection, and a second SIGINT arrives
- **THEN** the service drops that connection at once and the process exits with status 130 within a few
  seconds of the second SIGINT, without waiting for the peer or the host's TCP stack

#### Scenario: A stalled poll does not freeze the stop
- **WHEN** a client is connected and the poller's store read has been waiting on a database that dropped
  off the network, and the service is stopped
- **THEN** the hub's stop completes within one second, and the event loop answers a request made during
  the stop without waiting for the read

#### Scenario: A stalled first snapshot does not hold the shutdown
- **WHEN** a client connects to an idle service and its first snapshot read blocks on the database, so the
  client has received no frame, and the process then receives one SIGTERM
- **THEN** the client's connection ends (close code 1012 from the server's shutdown) and the service completes
  its application shutdown within five seconds, without waiting for the read
- **AND** the read is abandoned: no snapshot is ever sent on that connection

#### Scenario: Closing a tab during a stalled first snapshot releases it
- **WHEN** the first client connects while the snapshot read blocks on the database, and closes its
  connection before the read returns
- **THEN** within one second the service holds no subscription and no connection handler for it, although the
  database has not answered
- **AND** a client that connects after the database answers receives a normal snapshot

#### Scenario: A subscriber arriving after the stop began is refused
- **WHEN** the hub's stop has begun and a client's WebSocket upgrade is then handled
- **THEN** that client is closed with code 1013 and receives no snapshot

#### Scenario: A dropped subscriber is told to reconnect
- **WHEN** the hub disconnects a subscriber whose outbound queue is full
- **THEN** that client receives close code 1013
- **AND** when it reconnects, its first message is a fresh snapshot

## ADDED Requirements

### Requirement: Job kind is a closed, published vocabulary
Every job the service reports SHALL carry its `kind`, drawn from the job store's closed set of job kinds:
`render` and `proxy`. `kind` SHALL be present, non-null and **required** wherever the service describes a job: in
the job detail (`GET /api/v1/jobs/{id}`), in each item of the jobs list, in the job the enqueue returns, in the
latest-job summary that the events list rows and the event detail carry, and in every job of a WebSocket frame.
`GET /api/v1/jobs` lists the served project's jobs of every kind, each marked, and the job detail answers for a
job of either. It SHALL have the same value for the same job in all of them. The service's OpenAPI schema SHALL publish the set
as an enumeration rather than as a free-form string, so a client can derive an exhaustive type, and removing or
renaming a value is a compile-time failure in generated client code rather than a silent runtime change (D-8,
§4.10); the latest-job model's `kind` SHALL be defined exactly as the job detail's.

A job row whose stored kind is not one of the closed set (the column is free text, so a row written by another
build can hold one) cannot be described, and SHALL be left out of `GET /api/v1/jobs` and of every WebSocket frame
and logged, never fail the list or the feed for the jobs that can be described.

A render job SHALL read `kind: render`. Adding the field MUST NOT change the name, type, required status or value
of any other field of a job, nor any render behaviour: a client that ignores `kind` receives exactly what it
received before.

#### Scenario: A render job says it is a render
- **WHEN** `POST /api/v1/jobs` enqueues `2024/2024-06-27 - Grillning med grannar`, and the job is then read
  through `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs` and `GET /api/v1/events`
- **THEN** the 201 body, the detail, the list item and the event row's `latest_job` all carry `kind: "render"`,
  and every other field has the value it had before the field existed

#### Scenario: A proxy job says it is a proxy job on every read
- **WHEN** a `queued` proxy job exists for `2024/Blandat`, and it is read through `GET /api/v1/jobs/{id}` and
  `GET /api/v1/jobs`
- **THEN** both carry `kind: "proxy"`, `event_dir` `2024/Blandat` and `status` `queued`

#### Scenario: A row of an unknown kind costs only itself
- **WHEN** the jobs table holds a `queued` render job and a job of the kind `future`, and `GET /api/v1/jobs` is
  read
- **THEN** the response is 200 and lists the render job only

#### Scenario: The schema publishes the kind set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the job's `kind` is described as the enumeration `render`, `proxy`, is in the job detail's `required`
  list and in the latest-job model's, and the two definitions are identical
- **AND** a client generated from it that handles every kind exhaustively fails to compile until it handles
  `proxy`

### Requirement: An event's latest job is its latest render job
Wherever an events response carries an event's latest job (each summary row of `GET /api/v1/events`, and
`GET /api/v1/events/{event_id}`), that job SHALL be the newest job of kind `render` for the event, whatever its
status. A job of any other kind SHALL NOT appear there, however recent: a queued, running, finished or failed
proxy job for the event leaves `latest_job` as it was, and an event whose only jobs are proxy jobs reports
`latest_job: null`. The proxy side of an event is read from its clips' `proxy` state and, while a job runs, from
the jobs WebSocket.

#### Scenario: A newer proxy job does not replace the render
- **WHEN** `2024/2024-06-27 - Grillning med grannar`'s `done` render finished at 10:00 and a proxy job for it
  was created at 10:05 and is `running`, and the events list and the event detail are read
- **THEN** both reads' `latest_job` is the 10:00 render, `kind: "render"`, status `done`

#### Scenario: An event with only a proxy job has no latest job
- **WHEN** the only job `2024/Blandat` has ever had is a `done` proxy job, and the events list is read
- **THEN** its row's `latest_job` is null, as for an event never rendered

#### Scenario: A finished proxy job does not make a render look done
- **WHEN** `2024/Blandat`'s newest render is `failed` and a proxy job created after it is `done`
- **THEN** its `latest_job` is the `failed` render

### Requirement: An event's proxies are prepared by a job the service enqueues
The service SHALL expose `POST /api/v1/events/{event_id}/proxies`, taking no request body, which enqueues the
event's proxy job (the job `kind: proxy` of "Job kind is a closed, published vocabulary", whose work is
`proxy-job`'s) with the enqueue's semantics:

- **201** with the job in the shape `POST /api/v1/jobs` returns (`JobOut`), `kind` `proxy`, `status` `queued`,
  `event_dir` the event's id exactly as the events list shows it, `force` false and `fingerprint` null. A 201
  SHALL mean this request created the job; whether a job was created SHALL be decided by the store at insertion,
  never by an earlier read.
- **200 "fresh - not enqueued"**, with `status` the constant `fresh`, the event id and `clip_count`, when every
  clip the event's folder holds already has a proxy whose state is `ready`. No job is created. `clip_count` is
  the number of those clips and is 0 for an event whose folder holds none; the response then says so rather than
  implying anything was checked.
- **409** with the shared problem body, `conflict` `active_job` and `job_id` the active job's id, when a proxy
  job is already `queued` or `running` for the event: found beforehand, or found at insertion when a concurrent
  request created it (never a 201). The `conflict` value is the one the enqueue's published enumeration already
  has; no other conflict is possible, because a proxy job has no output path and a missing clip is not a reason
  to refuse (below).
- **404** with the shared problem body naming the event in `event_id`, for an id the events list does not show,
  spelled as it spells it.
- **502** with the shared problem body: for an event folder that cannot be listed, naming `event_id` and the
  `failure` kind the events list's error row gives that failure (`unreadable_disk`); and, with no kind, for a
  proxy cache or `proxies` configuration that cannot be used, for a clip that cannot be statted for its cache
  key, and for a project walk that fails. Nothing is enqueued, and the proxy state of a clip that cannot be read
  is never taken as `absent` or `ready`.
- **503** with the shared problem body naming the database (`check` `database`) when the job store is
  unreachable, exactly as the jobs routes answer it.

The checks SHALL run in this order: the event (404, 502), then the active proxy job (409), then freshness (200),
then the insertion (201, or the 409 of a lost race). An event with a proxy job already active is therefore
answered by following that job, whether or not its proxies are ready. The clips an event's proxy job prepares
SHALL be the ones the 200 counts: every clip file the event's folder lists on disk (the listing the proxy job
walks), whatever `reel.yaml` says of it (ignored or excluded clips included), and nothing `reel.yaml` lists that is
not on disk. `reel.yaml` is never read: editorial state can neither add work nor make the request refuse. The state
of each clip SHALL be the one the event detail reports in its `proxy` field (the same function of the clip file
and the proxy settings), read by `stat` and JSON only: the request MUST NOT start a process, probe a clip,
encode, or write anything but the job row. Only a clip whose proxy is `ready` counts as ready; `absent`,
`stale` and `failed` each make the request enqueue, so a repeated request re-attempts a failed clip.

An event whose `reel.yaml` does not parse, or whose metadata is unusable (no real date or title), is not refused:
a proxy is a function of the clip file, and the proxy job does not read `reel.yaml` either.

The service's OpenAPI schema SHALL publish every one of these responses, each problem body using the shared
shape, and the 200 body as a named model whose `status` is a required constant. The route SHALL be registered
before the greedy event detail route and answer for event ids that contain `/`.

#### Scenario: Enqueue proxies for an unprepared event
- **WHEN** `POST /api/v1/events/2024/2024-06-27 - Grillning med grannar/proxies` is sent for an event
  whose three clips have no cache entries, and it has no active proxy job
- **THEN** the response is 201 with a job whose `kind` is `proxy`, `status` `queued`, `event_dir` is
  `2024/2024-06-27 - Grillning med grannar`, `force` is false and `fingerprint` is null
- **AND** one `queued` proxy row exists, no file was written to the proxy cache, and no ffmpeg or ffprobe
  process was started

#### Scenario: A repeated request is a conflict, not a second job
- **WHEN** the same `POST .../proxies` is sent again while the first job is `queued` or `running`
- **THEN** the response is 409 with `conflict` `active_job` whose `job_id` is the first job's id, and no new row
  is inserted

#### Scenario: An enqueue that loses a race is a conflict, not a creation
- **WHEN** two `POST .../proxies` requests for `2024/Blandat` both pass the active-job check before either
  inserts
- **THEN** exactly one response is 201, the other is 409 with `conflict` `active_job` whose `job_id` is the job
  the 201 returned, and one proxy row exists

#### Scenario: A prepared event is fresh
- **WHEN** `POST .../proxies` names `2023/2023-06-23 - Midsommar - Dalarna`, all four of whose clips have a
  `ready` proxy
- **THEN** the response is 200 with `status` `fresh`, the event id and `clip_count` 4, and no job exists

#### Scenario: One stale or failed proxy makes the event enqueue
- **WHEN** the same event has three `ready` proxies and one whose entry was made under other proxy settings
  (`stale`), or whose last attempt failed (`failed`)
- **THEN** the response is 201 with a `queued` proxy job

#### Scenario: A clip that is not on disk is not a reason to refuse
- **WHEN** `2024/Blandat`'s `reel.yaml` lists `gone.mp4`, which is absent from disk, and its two clips on disk have
  `ready` proxies
- **THEN** the response is 200 `fresh` with `clip_count` 2
- **AND** with one of the clips on disk `absent`, the response is 201

#### Scenario: An ignored or excluded clip is prepared with the others
- **WHEN** `2024/Blandat` has a clip its `reel.yaml` ignores and one it excludes, both `absent`, and its other
  clips are `ready`
- **THEN** the response is 201, and with those two `ready` as well it is 200 `fresh` counting them

#### Scenario: An event with no clips on disk
- **WHEN** `POST .../proxies` names an event whose folder holds no clip files
- **THEN** the response is 200 `fresh` with `clip_count` 0, and no job is created

#### Scenario: An active job is answered before freshness
- **WHEN** `2024/Blandat` has a `running` proxy job and every one of its clips is `ready`
- **THEN** `POST .../proxies` answers 409 `active_job` with that job's id, not 200

#### Scenario: Unknown event
- **WHEN** `POST /api/v1/events/2024/2024-12-24 - Finns inte/proxies` names a directory that is not
  under the project root
- **THEN** the response is 404 with the shared problem body naming the event in `event_id`, and nothing is
  enqueued

#### Scenario: An event folder that cannot be listed
- **WHEN** `POST .../proxies` names `2024/2024-06-27 - Grillning med grannar`, whose folder cannot be listed
  (permission denied)
- **THEN** the response is 502 with the shared problem body whose `event_id` is that id and whose `failure` is
  `unreadable_disk`, the kind the events list gives that failure, and nothing is enqueued

#### Scenario: A proxy cache that cannot be read is not read as absent
- **WHEN** the proxy cache directory exists but cannot be listed (permission denied) and
  `POST .../proxies` names `2024/Blandat`
- **THEN** the response is 502 with no `failure` kind, and no job row exists

#### Scenario: The job store is down
- **WHEN** the database is unreachable and `POST .../proxies` names `2024/Blandat`
- **THEN** the response is 503 with `check` `database`, and no state is reported for the job

#### Scenario: An unusable reel.yaml does not block proxies
- **WHEN** `POST .../proxies` names `2024/2024-10-06 - Trasig reel`, whose `reel.yaml` does not parse, or
  `2024/2024-10-07 - Utan titel`, whose `reel.yaml` has no title, so the render enqueue would refuse it
- **THEN** the response is 201 (or 200 `fresh`), not an error

#### Scenario: The schema publishes the proxy enqueue
- **WHEN** the service's OpenAPI schema is generated
- **THEN** `POST /api/v1/events/{event_id}/proxies` declares its 201 job, its 200 result (a named model whose
  `status` is the required constant `fresh` and which has `clip_count`), and its 404, 409, 502 and 503 problem
  bodies, and takes no request body

### Requirement: A proxy job and a render job of one event do not block each other
The one-active-job rule of the enqueue SHALL hold per kind. An event SHALL have at most one `queued` or `running`
job of kind `render` and at most one of kind `proxy`, and an active job of one kind SHALL NOT make the enqueue of
the other a 409: `POST /api/v1/jobs` SHALL look for an active **render** job only, and
`POST /api/v1/events/{event_id}/proxies` for an active **proxy** job only. The 409 `job_id` of either SHALL be
a job of the kind requested. `POST /api/v1/jobs/{id}/cancel` SHALL act on a job of either kind with the store's
cancel and report its outcome as for a render (`flagged-running`, `canceled-queued`, `no-op-terminal`); a
cancelled proxy job leaves the event's render jobs untouched.

#### Scenario: A running proxy job does not block a render enqueue
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has a `running` proxy job and its title was edited after
  its last render, and `POST /api/v1/jobs` names it
- **THEN** the response is 201 with a `queued` job of kind `render`, and the proxy job is unchanged

#### Scenario: An active render does not block a proxy enqueue
- **WHEN** the same event has a `queued` render job, and `POST /api/v1/events/{event_id}/proxies` names it with
  unprepared clips
- **THEN** the response is 201 with a `queued` job of kind `proxy`, and the render job is unchanged

#### Scenario: A render conflict names the render
- **WHEN** the event has both a `queued` render job and a `queued` proxy job, and `POST /api/v1/jobs` names it
- **THEN** the response is 409 `active_job` whose `job_id` is the render job's id

#### Scenario: Cancel a running proxy job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the `running` proxy job of `2024/Blandat`
- **THEN** the job's `cancel_requested` is set, its status is unchanged, the response's outcome is
  `flagged-running` with status `running`, and the event's render jobs are unchanged

### Requirement: The jobs WebSocket follows proxy jobs
`WS /api/v1/ws/jobs` SHALL carry jobs of every kind, in the frame shape of "WebSocket live job updates", each job
with its `kind`. The first frame's snapshot SHALL include every `queued` and `running` proxy job of the served
project beside the render jobs; later deltas SHALL carry a proxy job's progress, status and cancel-request
changes; and a proxy job's terminal transition SHALL be delivered exactly once, including a job whose whole active
life fell between two polls. A proxy job's `progress` SHALL be the value the job store holds, sent as a render's
is. A job of another project SHALL NOT be sent. A frame carrying only render jobs SHALL differ from what it was
only by each job's `kind: "render"`. A poll that fails (a database that does not answer, a row that cannot be
described) SHALL NOT end the feed: the poller logs it and the next poll goes on, so subscribers do not sit on
heartbeats for good.

#### Scenario: A subscriber's snapshot holds both kinds
- **WHEN** `2024/Blandat` has a `running` proxy job and `2024/2024-06-27 - Grillning med grannar` a `queued`
  render, and a client connects
- **THEN** the first frame has `type` `snapshot` and holds both jobs, the first with `kind: "proxy"` and the
  second with `kind: "render"`

#### Scenario: A proxy job's progress and end arrive as deltas
- **WHEN** a connected client watches a proxy job go from `queued` to `running` with progress 0.4 and then to
  `done`
- **THEN** it receives deltas carrying that job with `kind: "proxy"`, in that order, and the `done` row exactly
  once

#### Scenario: A proxy job that lives between two polls is still delivered once
- **WHEN** a proxy job for `2024/Blandat` is created, claimed and finished between two polls
- **THEN** the next delta carries its terminal row once, with `kind: "proxy"`

#### Scenario: A failed poll does not end the feed
- **WHEN** one poll of the store fails while a client is connected and a job then changes
- **THEN** the client still receives the change in a later delta

#### Scenario: A job of an unknown kind is not sent
- **WHEN** a job of the kind `future` is active or ends while a client is connected
- **THEN** no frame carries it, and the other jobs' frames are unchanged

#### Scenario: Another project's proxy job is not sent
- **WHEN** a proxy job exists for an event of a different project root
- **THEN** no frame of the served project's subscribers carries it
