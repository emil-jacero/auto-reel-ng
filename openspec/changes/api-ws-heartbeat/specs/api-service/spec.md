## MODIFIED Requirements

### Requirement: WebSocket live job updates
The service SHALL expose `WS /api/v1/ws/jobs`. On connect a subscriber SHALL immediately receive a full
snapshot of active (`queued`/`running`) jobs; thereafter it SHALL receive delta messages for job progress
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
  host's TCP stack abandons the connection, which can take many minutes. A second SIGINT does not shorten
  that stall: the process still exits only once that connection has ended. Like any stop, it also waits for
  HTTP requests still being handled (headless-cli, "`serve` runs the API service").
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

### Requirement: Cancel outcome and WebSocket frame type are closed, published vocabularies
A cancellation result's outcome SHALL be drawn from the job store's closed set of cancel outcomes
(`flagged-running`, `canceled-queued`, `no-op-terminal`), and a WebSocket frame's type from the closed set
`snapshot` | `delta` | `heartbeat`. The service's OpenAPI schema SHALL publish each set as an enumeration rather than as a
free-form string, so a client can derive an exhaustive type for each, and removing or renaming a value is a
compile-time failure in generated client code rather than a silent runtime change (D-8, §4.10).

This requirement MUST NOT change any value already on the wire: a client reading an outcome or a frame
type as a plain string continues to read the same strings. The one value added is the frame type
`heartbeat`.

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
  received before this change, plus `heartbeat` frames while the connection is idle

#### Scenario: The schema publishes the frame type set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the frame's type is described as the enumeration `snapshot`, `delta`, `heartbeat`, and a client
  generated from it that handles every frame type exhaustively fails to compile until it handles
  `heartbeat`

