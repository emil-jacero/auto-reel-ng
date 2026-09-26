# api-service Specification

## Purpose

Expose a thin HTTP/WebSocket API service that lets remote clients observe and edit project state and
drive the job queue without duplicating engine logic: a read-only events view scanned from disk per
request (as `scan` does), read-only cached analysis results, a whole-document editorial write that
persists an event's `reel.yaml`, a REST lifecycle over the job store (enqueue, list, detail, cancel),
live job updates over WebSocket, a health endpoint, and an auth seam ready for a future bearer-token
check. Every endpoint maps to an operation the CLI can also reach; the service itself contains no
scan, render, editorial, or job logic of its own.

## Requirements

### Requirement: Service configuration and thin-layer constraint
The API service SHALL be built by an application factory from explicit settings — project root, ingest
layout, bind host/port, database URL (via the existing resolution), and poll interval — resolved through
the D-2 layering (`api.host` / `api.port` / `api.poll_interval` in `config.yaml`, flags/env override,
default bind `127.0.0.1:8080`). Every endpoint SHALL map to an operation the CLI can also reach; the API
MUST NOT contain scan, render, or job logic of its own.

#### Scenario: Factory serves a configured project root
- **WHEN** the app is created with a project root and layout
- **THEN** its event endpoints serve exactly the events the CLI's `scan` reports for that root and layout

#### Scenario: Default bind is localhost
- **WHEN** `api.host` is not configured
- **THEN** the service binds `127.0.0.1` and widening the bind requires explicit configuration

### Requirement: Events read model is scanned from disk per request
`GET /api/v1/events` SHALL enumerate events by walking the configured ingest layout at request time, and
`GET /api/v1/events/{event_id}` SHALL parse the event's current `reel.yaml` (seeding metadata from the
folder name when absent, as `scan` does) — returning metadata, ordered chapters/clips, reconcile state
(NEW/MISSING), and the event's **staleness verdict** (fresh, or stale with the changed components as
reasons, from the staleness gate and render manifest). The event identity in URLs SHALL be the
root-relative event directory (URL-encoded). The service MUST NOT maintain a database copy of event or
clip state, and responses MUST reflect disk changes made since any previous request. Events reads SHALL be
read-only: no request may create or modify `reel.yaml` or the render manifest.

Each clip in the detail response SHALL additionally carry the clip file's **byte size** and **modification
time** (timezone-aware, UTC), read from the file's own directory entry. These are file facts, not media
facts: no clip may be decoded or probed to produce them, so the detail response stays probe-free. A clip the
document references but which is absent from disk SHALL report both as null rather than a substituted zero
or epoch — absence is reported, never fabricated. The events **list** response SHALL NOT carry per-clip
facts; it keeps its clip counts.

Every event in the **list** response SHALL carry the same staleness verdict shape as the detail response —
whether the event is stale, and when it is, the changed components as reasons — computed from the same
staleness gate and render manifest, so a client learns what needs rendering in one request rather than one
request per event. The verdict SHALL be derived from disk on every request and MUST NOT be read from, or
persisted to, the database. A list request MUST NOT compute the verdict from a completed job's existence:
a job that finished before the clips changed describes a render, not freshness.

Computing the list's verdicts SHALL NOT make the response more expensive than the facts require. The
resolved project look defaults are a per-request value, identical for every event in one response, and
SHALL be resolved once per request rather than per event. The clip-set component SHALL be computed from
the clips' size and modification time — the fingerprint's default, content-free signal; the events list
MUST NOT use the content-hash opt-in, so no clip's bytes are read to answer a list request. No event may
be probed or decoded, and no `reel.yaml`, render manifest or rendered output may be written.

#### Scenario: Disk edit is visible on the next request
- **WHEN** an event's `reel.yaml` title is edited on disk after a previous GET
- **THEN** the next `GET /api/v1/events/{event_id}` returns the new title

#### Scenario: Staleness is part of the event detail
- **WHEN** an event's clips changed since its last render
- **THEN** `GET /api/v1/events/{event_id}` reports it stale citing the clip-set component

#### Scenario: The list answers "what needs rendering?" in one request
- **WHEN** a project root holds three events — one rendered with an unchanged fingerprint, one whose clips
  changed since its last render, and one never rendered at all
- **THEN** a single `GET /api/v1/events` reports the first fresh, the second stale citing the clip-set
  component, and the third stale citing the absent manifest, with no follow-up detail request

#### Scenario: List and detail agree on the same event
- **WHEN** the same event is read through `GET /api/v1/events` and `GET /api/v1/events/{event_id}` with no
  disk change in between
- **THEN** both report the identical verdict and the identical reasons

#### Scenario: A completed job is not freshness
- **WHEN** an event's most recent job completed successfully and a clip was then added to its directory
- **THEN** the list still reports that event stale, even though it carries a completed latest job

#### Scenario: A list request reads no clip content
- **WHEN** `GET /api/v1/events` is served for a project whose events hold large clips
- **THEN** the verdicts are derived from the clips' size and modification time, and no clip's bytes are read
  to produce them

#### Scenario: Project look defaults are resolved once per list request
- **WHEN** `GET /api/v1/events` is served for a project root holding many events and a `config.yaml`
- **THEN** the project configuration is read and resolved once for that request, not once per event, and
  every event's verdict is computed against that one resolved value

#### Scenario: A list request writes nothing
- **WHEN** `GET /api/v1/events` is served for a project containing events that have no `reel.yaml` and no
  render manifest
- **THEN** the verdicts are returned and no `reel.yaml`, manifest or output file is created

#### Scenario: Event identity round-trips with spaces and non-ASCII characters
- **WHEN** an event directory is named `2024/2024-06-21 - Midsommar i Dalarna`
- **THEN** the URL-encoded id returned by the list endpoint fetches that event's detail

#### Scenario: Unknown event yields 404
- **WHEN** `GET /api/v1/events/{event_id}` names a directory that does not exist under the root
- **THEN** the response is 404 with a problem body

#### Scenario: Scan failure is loud, never fabricated
- **WHEN** an event's `reel.yaml` is unparseable
- **THEN** the response is an error naming the failing event, not an empty or partial success

#### Scenario: Clips carry the file facts a reorder view needs
- **WHEN** an event holds three clips named `P1000123.MP4`, `P1000124.MP4` and `P1000125.MP4`, written to
  disk in an order that does not match their names
- **THEN** each clip in the detail response carries its own byte size and modification time, so a client can
  present them in the order they were shot rather than the order they are named

#### Scenario: A clip missing from disk reports no file facts
- **WHEN** the document references a clip whose file has been deleted or renamed
- **THEN** that clip is still reported MISSING, and its size and modification time are both null

#### Scenario: A disk-only NEW clip carries file facts like any other
- **WHEN** a clip exists on disk but is not yet referenced by `reel.yaml`
- **THEN** it appears in the detail response as NEW, carrying its size and modification time

#### Scenario: File facts cost no probe
- **WHEN** an event's clips are truncated, header-damaged, or otherwise undecodable
- **THEN** the detail response still returns their size and modification time and does not fail, because no
  clip was decoded to produce them

### Requirement: Analysis results are exposed read-only
`GET /api/v1/events/{event_id}/analysis` SHALL return the event's cached analysis segments from the
existing sidecar cache, and SHALL distinguish "no analysis has been run" from "analysis ran and found
nothing". It MUST NOT trigger analysis.

#### Scenario: Cached analysis is returned
- **WHEN** an event has a populated analysis sidecar cache
- **THEN** the endpoint returns its segments per clip

#### Scenario: Absent cache is not an empty result
- **WHEN** an event has never been analyzed
- **THEN** the response indicates analysis is absent (not an empty segment list)

### Requirement: Editorial write endpoint
The service SHALL expose `PUT /api/v1/events/{event_id}/reel`, accepting the full desired editorial state
for the event (metadata, ordered chapters and their clips, per-clip properties, `ignore`, and the `look`
override) and delegating to the engine's editorial-write operation. The endpoint MUST contain no editorial
logic of its own: it parses and validates the request shape, calls the operation, and maps outcomes to
responses. The response SHALL echo the persisted document together with the event's resulting staleness
verdict, so a client needs no follow-up read. Unknown events SHALL yield 404; a rejected state SHALL yield a
validation problem body and leave `reel.yaml` unchanged. Read endpoints remain read-only and unaffected.

#### Scenario: Save persists and echoes
- **WHEN** `PUT /api/v1/events/{event_id}/reel` sends a state with a changed title and clip order
- **THEN** the event's `reel.yaml` reflects it, and the response echoes the persisted document with the
  event's new staleness verdict

#### Scenario: Save makes the event stale over the API
- **WHEN** a previously fresh event is saved via the write endpoint
- **THEN** the response's verdict — and a subsequent `GET /api/v1/events/{event_id}` — report it stale
  citing the editorial component, while no job has been created

#### Scenario: Invalid state is rejected loudly
- **WHEN** the submitted state fails validation
- **THEN** the response is a validation problem body naming the offending part, and the event's `reel.yaml`
  is unchanged

#### Scenario: Unknown event
- **WHEN** the endpoint targets an event id that does not resolve under the configured project root
- **THEN** the response is 404 with a problem body

#### Scenario: Saving an unmodified document is a no-op
- **WHEN** the document echoed by the write endpoint is submitted back unmodified via the write endpoint
- **THEN** the persisted `reel.yaml` is byte-for-byte unchanged, and the response echoes the same document
  again (the write endpoint's read and write models are the same shape; the read endpoints' detail model
  stays read-only and is deliberately not a write body)

### Requirement: Editorial document read endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/reel`, returning the event's **complete** editorial
state — metadata, ordered chapters with their clip identities, per-clip properties, the `ignore` list, and the
`look` override — in exactly the shape the write endpoint accepts. The body SHALL be produced from the event's
`reel.yaml` as parsed at request time, and the response SHALL carry an `ETag` identifying that editorial
state. An event whose directory resolves but which has no `reel.yaml` yet SHALL return 200 with the empty
editorial document, mirroring the write endpoint's own seeding behaviour — not 404. An unknown event SHALL
yield 404 with a problem body, and an unparseable `reel.yaml` SHALL fail loud rather than return an empty or
partial document. The endpoint SHALL be read-only: it MUST NOT create or modify `reel.yaml` and MUST NOT
write a render manifest.

#### Scenario: Editorial state the detail view does not carry
- **WHEN** an event's `reel.yaml` holds analysis trims, an `ignore` list, and a `look` override
- **THEN** `GET /api/v1/events/{event_id}/reel` returns all three, none of which appear anywhere in
  `GET /api/v1/events/{event_id}`

#### Scenario: The response is a valid write body
- **WHEN** the response body is submitted verbatim to `PUT /api/v1/events/{event_id}/reel`
- **THEN** the write is accepted, `reel.yaml` is byte-for-byte unchanged, and the event's staleness verdict is
  the same as before the round trip

#### Scenario: Event with clips but no reel.yaml
- **WHEN** the event directory contains clips but no `reel.yaml`
- **THEN** the response is 200 with the empty editorial document, and no `reel.yaml` is created

#### Scenario: Comments and formatting are not part of the read model
- **WHEN** a hand-authored `reel.yaml` carries comments and a flow-style trim span
- **THEN** the response describes the same editorial state as an equivalent comment-free file, and the file
  on disk is untouched

#### Scenario: Unknown event yields 404
- **WHEN** the endpoint names a directory that does not resolve under the configured project root
- **THEN** the response is 404 with a problem body

#### Scenario: Unparseable document is loud
- **WHEN** the event's `reel.yaml` cannot be parsed
- **THEN** the response is an error naming the failing event, never an empty or partial document

### Requirement: Conditional editorial write
The write endpoint SHALL accept an optional `If-Match` request header carrying an ETag obtained from the
editorial read endpoint. When the header is present and matches the event's current editorial state, the write
SHALL proceed. When it is present and does not match, the service SHALL respond `412 Precondition Failed` with
a problem body and leave `reel.yaml` byte-for-byte unchanged. When the header is absent, the write SHALL be
unconditional exactly as before, so scripted clients and any CLI-equivalent caller keep working without it.
The ETag SHALL identify the **editorial** state canonically: a comment-only or formatting-only edit to
`reel.yaml` MUST NOT change it, while any change to metadata, chapters, clip order, per-clip properties,
`ignore`, or `look` MUST change it.

A **successful** write SHALL carry an `ETag` response header identifying the editorial state it persisted —
the same value a read of that event would then return. A client may therefore chain conditional writes,
using the tag from one write as the precondition for the next, without an intervening read. A write refused
with `412` SHALL NOT carry an `ETag`: a client that lost the race MUST re-read the document it is about to
overwrite, not retry blindly against a tag the service handed it.

#### Scenario: A concurrent write is refused, not clobbered
- **WHEN** a client reads the document, another writer adds analysis trims to the same event, and the client
  then PUTs its edited state with the `If-Match` it originally received
- **THEN** the response is 412, and the trims added in the meantime are still on disk

#### Scenario: A matching precondition writes
- **WHEN** a client PUTs with the `If-Match` from a read whose state has not changed since
- **THEN** the write is applied and the response is the usual persisted-document echo with its staleness
  verdict

#### Scenario: An absent precondition is unconditional
- **WHEN** a client PUTs with no `If-Match` header
- **THEN** the write is applied regardless of any intervening change, matching the endpoint's existing
  behaviour

#### Scenario: A comment-only edit does not invalidate a held ETag
- **WHEN** a comment is added by hand to an event's `reel.yaml` after a client read it, and the client PUTs
  with the `If-Match` from that read
- **THEN** the write proceeds, because the editorial state did not change

#### Scenario: A round trip is enough to obtain a fresh precondition
- **WHEN** a client receives 412, re-reads the editorial document, re-applies its edit, and PUTs with the new
  `If-Match`
- **THEN** the write succeeds

#### Scenario: Consecutive conditional writes need no intervening read
- **WHEN** a client reorders an event's clips, PUTs with the `If-Match` from its read, then reorders again
  and PUTs with the `ETag` the first write returned
- **THEN** both writes are applied, and no read of `/reel` occurred between them

#### Scenario: The write's tag is the tag a read would give
- **WHEN** a client PUTs an editorial change and then reads `GET /api/v1/events/{event_id}/reel`
- **THEN** the read's `ETag` equals the one the write returned

#### Scenario: An unmodified save returns the tag it was given
- **WHEN** a client PUTs the document exactly as it read it
- **THEN** the write's `ETag` equals the read's, because the editorial state did not change

#### Scenario: A refused write hands back no precondition
- **WHEN** a write is refused with 412 because the event changed since the client's read
- **THEN** the response carries no `ETag`, so the client cannot retry without re-reading

### Requirement: The events detail response is not an editorial write body
The events detail response and the editorial document are **separate models and SHALL NOT be interchangeable**.
`GET /api/v1/events/{event_id}` reports the *reconcile* view: it merges disk-only NEW clips into the
document's chapters and tags every clip with a reconcile status, so it describes what the scan sees rather
than what is persisted. `GET /api/v1/events/{event_id}/reel` reports the document as authored. The write
endpoint SHALL reject a detail-shaped body rather than coerce it, and the two responses SHALL be observably
different whenever the event has clips not yet referenced by its document.

#### Scenario: A detail-shaped body is rejected
- **WHEN** an events-detail response body is submitted to `PUT /api/v1/events/{event_id}/reel`
- **THEN** the response is a validation problem body naming the fields that do not belong in an editorial
  write, and `reel.yaml` is unchanged

#### Scenario: The two views differ where it matters
- **WHEN** an event has a clip on disk that its `reel.yaml` does not reference
- **THEN** the detail response lists that clip with reconcile status NEW, while the editorial read response
  does not mention it — only the latter describes what is persisted

#### Scenario: Ignored clips are not silently promoted
- **WHEN** an event's `reel.yaml` lists a clip in `ignore`
- **THEN** the editorial read response carries that identity in `ignore`, so a client round-tripping it
  preserves the exclusion rather than adopting the clip into a chapter

### Requirement: Jobs lifecycle over REST
The service SHALL expose the job store thinly: `POST /api/v1/jobs` enqueues an event (device optional,
default `auto`; `force` optional, default false) after applying the staleness gate — returning 201 with
the job on creation, **409 with the existing job's id** when an active job already exists for the event,
and a distinct **"fresh — not enqueued" outcome** (200 with the fresh verdict and its manifest reference)
when the event is fresh and `force` is false; a forced request always enqueues. The enqueued job carries
the event's fingerprint and the force flag. `GET /api/v1/jobs` lists jobs (filterable by status);
`GET /api/v1/jobs/{id}` returns one job's detail (status, progress, device, worker, force, fingerprint,
timestamps, error, requeue count); `POST /api/v1/jobs/{id}/cancel` invokes `request_cancel` (flag a
running job, cancel a queued one directly, no-op reported for terminal jobs). The API MUST NOT transition
job status itself.

#### Scenario: Enqueue over REST
- **WHEN** `POST /api/v1/jobs` names a stale event with no active job
- **THEN** a `queued` job row exists carrying the event's fingerprint and the response is 201 with its id

#### Scenario: Fresh event is not enqueued
- **WHEN** `POST /api/v1/jobs` names a fresh event without `force`
- **THEN** no job is created and the response reports the event as fresh

#### Scenario: Force enqueues a fresh event
- **WHEN** `POST /api/v1/jobs` names a fresh event with `"force": true`
- **THEN** a `queued` job with `force = true` is created and the response is 201

#### Scenario: Duplicate enqueue is a visible conflict
- **WHEN** `POST /api/v1/jobs` names a stale event that already has a `queued` or `running` job
- **THEN** the response is 409 carrying the existing job's id and no new row is inserted

#### Scenario: Cancel a running job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets a `running` job
- **THEN** the job's `cancel_requested` flag is set, its status is unchanged, and the response reports the
  request was recorded

### Requirement: WebSocket live job updates
The service SHALL expose `WS /api/v1/ws/jobs`. On connect a subscriber SHALL immediately receive a full
snapshot of active (`queued`/`running`) jobs; thereafter it SHALL receive delta messages for job progress
and status changes — including terminal transitions — observed by a central poller that queries the store
at the configured interval (default 1 s). The poller SHALL run only while at least one subscriber is
connected. A subscriber that cannot keep up (full outbound queue) SHALL be disconnected rather than
back-pressuring the hub; its recovery path is reconnect-and-resnapshot.

#### Scenario: Snapshot on connect
- **WHEN** a client connects while two jobs are active
- **THEN** its first message is a snapshot containing both jobs' current status and progress

#### Scenario: Progress and completion are pushed
- **WHEN** a running job's stored progress advances and the job later transitions to `done`
- **THEN** subscribers receive delta messages for the progress change and for the terminal transition
  within approximately one poll interval each

#### Scenario: Idle service does not poll
- **WHEN** no WebSocket subscriber is connected
- **THEN** the central poller issues no store queries

### Requirement: Health endpoint
`GET /healthz` SHALL report service liveness and database reachability, returning non-success when the
database cannot be reached.

#### Scenario: Healthy service
- **WHEN** the service is up and the database is reachable
- **THEN** `/healthz` returns success

#### Scenario: Database outage is reported
- **WHEN** the database is unreachable
- **THEN** `/healthz` returns a non-success status naming the database check

### Requirement: Auth seam without auth
The service SHALL provide a single middleware hook point where a bearer-token check can later be
registered via configuration, and SHALL apply no authentication by default. Adding a token MUST NOT
require restructuring routes.

#### Scenario: v1 is open on localhost
- **WHEN** the service runs with default settings
- **THEN** requests require no credentials

#### Scenario: Token check is a drop-in
- **WHEN** a token check is registered at the hook point (as tests do)
- **THEN** requests without the token are rejected and no route code changes

### Requirement: The built web client is served when present, and is never required
When a built web client is present in the development checkout, the service SHALL serve it at the root
path, returning its entry document for `/` and its assets by path. When no built client is present, the
service SHALL start and behave exactly as it does without one — a missing build is a normal state, not
an error, so development runs and the test suite never require a frontend build.

Serving the client MUST NOT shadow the service's own routes: every API path, the health endpoint and the
WebSocket endpoint SHALL continue to resolve to their handlers whether or not a build is present. The
service SHALL NOT serve any file outside the built client's directory.

#### Scenario: The service starts with no build present
- **WHEN** the service starts from a checkout that has never built the client
- **THEN** it starts normally, every API endpoint works, and the root path is simply not served

#### Scenario: The built client is served at the root
- **WHEN** the client has been built and the service is started
- **THEN** requesting `/` returns the client's entry document and its assets resolve by path

#### Scenario: API routes win over the client mount
- **WHEN** the client has been built and the service is started
- **THEN** `GET /api/v1/events`, `GET /healthz` and the jobs WebSocket still reach their handlers and are
  not answered with the client's entry document

#### Scenario: The mount does not expose the wider filesystem
- **WHEN** a request asks for a path that traverses outside the built client's directory
- **THEN** the service does not return a file from outside that directory

### Requirement: Events reads fail loud with a problem body
When an events read — the list or an event's detail — cannot be answered, the service SHALL respond with
the same problem body shape every other deliberate error uses, naming which failure occurred: the job
store being unreachable and the event scan itself failing are distinct conditions and SHALL be reported
distinctly. The service MUST NOT answer a failed events read with an unshaped error body.

An unreachable job store SHALL be reported the same way on both reads, identifying the database as the
failing dependency exactly as the health endpoint does, so a client distinguishes "the service cannot
reach its database" from "this event could not be read" without inspecting prose.

The list SHALL NOT degrade: a request that cannot produce every event's full summary — including its
latest job — SHALL fail rather than return a partial list, a list with the unavailable facts omitted, or a
list with substituted values. Absence is reported, never fabricated, and a client is never left to guess
whether a missing fact means "none" or "could not be read".

Both reads SHALL publish these failures in the service's OpenAPI schema: each status code a read may
answer with a problem body, and the problem body's shape. The shape comprises its title, numeric status
and detail, plus the optional fields that name the failing dependency or the failing event. The list SHALL
declare its scan-failure and database-failure responses, and the detail SHALL additionally declare its
unknown-event response. A client SHALL therefore derive the problem body's type from the generated types
rather than declaring it by hand, and every problem body these reads return SHALL conform to the
published shape.

#### Scenario: The job store is unreachable on the list
- **WHEN** the database is down and a client requests the events list
- **THEN** the response is a problem body identifying the failure as the job store's, not a bare error and
  not a list with every `latest_job` reported as absent

#### Scenario: The job store is unreachable on an event's detail
- **WHEN** the database is down and a client requests a single event's detail
- **THEN** the response is the same problem body the list returns for that failure, not a bare error and
  not a detail whose `latest_job` is reported as absent

#### Scenario: The scan itself fails
- **WHEN** an event's `reel.yaml` cannot be parsed and a client requests the events list
- **THEN** the response is a problem body identifying the failure as the scan's, distinguishable from a
  database failure

#### Scenario: A failed list is never partial
- **WHEN** a list request fails part-way through enumerating events
- **THEN** no partial list is returned, and the events that were read successfully are not reported as the
  whole set

#### Scenario: An unreadable event still 404s and 502s as before
- **WHEN** a client requests an unknown event, or one whose `reel.yaml` cannot be parsed
- **THEN** the detail route returns the 404 and 502 problem bodies it already returns, unchanged

#### Scenario: A healthy read is unaffected
- **WHEN** the database is reachable and every event scans cleanly
- **THEN** both reads respond exactly as before, with no added envelope, field or status code

#### Scenario: The schema publishes the problem responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the events list declares its 502 and 503 responses and the detail declares its 404, 502 and
  503 responses, each described by the shared problem body shape rather than left undeclared

#### Scenario: A returned problem body matches the published shape
- **WHEN** the database is down and a client requests the events list
- **THEN** the 503 body it receives validates against the published problem shape, including the field
  naming the database as the failing dependency

### Requirement: Staleness reasons are a closed, published vocabulary
The staleness verdict's reasons SHALL be drawn from a closed set, and the service's OpenAPI schema SHALL
publish that set as an enumeration rather than as free-form strings, wherever a verdict appears in a
response. A client SHALL therefore be able to derive an exhaustive type for the reasons, so that removing
or renaming a reason is a compile-time failure in generated client code rather than a silent runtime
change (D-8, §4.10).

The published values SHALL be exactly the reasons the staleness gate already cites, and this requirement
MUST NOT change any reason's wire value: an existing client reading a reason as a plain string continues
to read the same string.

#### Scenario: The schema publishes the closed set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the staleness verdict's reasons are described as an enumeration of the gate's reasons, not as
  an unconstrained array of strings

#### Scenario: A renamed reason breaks the client build
- **WHEN** a reason is renamed in the engine and the schema and client types are regenerated
- **THEN** client code that referred to the old reason fails to compile, rather than silently ceasing to
  match

#### Scenario: Wire values are unchanged
- **WHEN** a client that treats reasons as plain strings reads a stale event's verdict
- **THEN** it receives the same reason strings it received before this change

### Requirement: Job status is a closed, published vocabulary

Every response field that carries a job's lifecycle status SHALL be drawn from the job store's closed set
of statuses (`queued`, `running`, `done`, `failed`, `canceled`). The service's OpenAPI schema SHALL
publish that set as an enumeration rather than as a free-form string. This covers a job embedded in an
events response as the latest job, a job returned by the jobs routes or pushed over the WebSocket, and a
cancellation result. A client SHALL therefore be able to derive an exhaustive type for a job's status, so
that removing or renaming a status is a compile-time failure in generated client code rather than a
silent runtime change (D-8, §4.10).

This requirement MUST NOT change any status's wire value: an existing client reading a status as a plain
string continues to read the same string.

#### Scenario: The schema publishes the job status set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the latest job's status on an events response, a job's status on the jobs routes, and a
  cancellation result's status are each described as the enumeration of job statuses, not as an
  unconstrained string

#### Scenario: A renamed status breaks the client build
- **WHEN** a job status is renamed in the job store and the schema and client types are regenerated
- **THEN** client code that referred to the old status fails to compile, rather than silently ceasing to
  match

#### Scenario: Wire values are unchanged
- **WHEN** a client that treats a job's status as a plain string lists events whose latest jobs finished,
  failed and are still queued
- **THEN** it receives `done`, `failed` and `queued`, the same strings it received before this change
