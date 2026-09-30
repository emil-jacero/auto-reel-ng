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
verdict, so a client needs no follow-up read. Read endpoints remain read-only and unaffected.

The request body is the event's **complete** editorial state (D-E2), not a patch. A section the body omits
SHALL be treated as empty, so omitting `ignore`, chapters, clip properties or `look` clears them. A client
preserves everything it does not mean to change by submitting what the editorial read returned, with its edit
applied.

The endpoint SHALL answer each failure by its cause, and nothing SHALL be written for any of them:

- **404:** an unknown event.
- **400, a validation problem body:** a submitted state that is invalid, including one the engine refuses
  because the event would lack a real date or a title, or would carry a future date. That refusal SHALL
  carry the unusable-metadata failure kind.
- **412:** a stale precondition (see the conditional write requirement).
- **502, the scan-failure problem body:** an event whose **existing** document cannot be read. It SHALL name
  the event and carry the same failure kind the events reads would report, and SHALL NOT be a 400, because
  the request was not at fault.
- **502, naming the operating-system error:** a validated document the filesystem refuses to store, for
  example a read-only mount. It is never an unshaped server error.

The existing document SHALL be read before the write on every request, with or without a precondition, so
the two paths answer a broken file identically. The endpoint SHALL publish each of these responses, the
shared problem body shape, and the `ETag` header of a successful write in the service's OpenAPI schema.

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

#### Scenario: Omitting a section clears it
- **WHEN** an event's `reel.yaml` holds an `ignore` list, and a body with a changed title but no `ignore` is
  written
- **THEN** the persisted document has no `ignore` list; and when the same edit is written with the `ignore`
  list the editorial read returned, the list is preserved

#### Scenario: A write onto a broken file is the file's fault
- **WHEN** a body is written, without `If-Match`, to an event whose existing `reel.yaml` cannot be parsed
- **THEN** the response is the scan-failure 502 naming the event, with the unparseable-`reel.yaml` failure
  kind, not a 400, and the file is untouched

#### Scenario: A state that would leave the event undated is refused
- **WHEN** a body for the event folder `2024/Blandat`, whose name has no date, omits `metadata.date`
- **THEN** the response is 400 with the unusable-metadata failure kind and a detail stating the missing
  date, and `reel.yaml` is unchanged

#### Scenario: Saving to a read-only archive
- **WHEN** a valid body is written to an event on a filesystem mounted read-only
- **THEN** the response is a 502 problem body whose detail names the read-only error, the file is
  unchanged, and the response is not an unshaped server error

#### Scenario: The schema publishes the write's responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the write declares its 400, 404, 412 and 502 responses in the shared problem body shape, and the
  `ETag` header of its 200 response

### Requirement: Editorial document read endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/reel`, returning the event's **complete** editorial
state — metadata, ordered chapters with their clip identities, per-clip properties, the `ignore` list, and the
`look` override — in exactly the shape the write endpoint accepts. The body SHALL be produced from the event's
`reel.yaml` as parsed at request time, and the response SHALL carry an `ETag` identifying that editorial
state. An event whose directory resolves but which has no `reel.yaml` yet SHALL return 200 with the empty
editorial document, mirroring the write endpoint's own seeding behaviour — not 404. An unknown event SHALL
yield 404 with a problem body. A `reel.yaml` that cannot be read or parsed SHALL fail loud with the
scan-failure problem body. That body names the event and carries the same failure kind the events reads
would report, rather than an empty or partial document. The endpoint SHALL be read-only: it MUST NOT create
or modify `reel.yaml` and MUST NOT write a render manifest. It SHALL publish its 404 and 502 responses, the
shared problem body shape, and its `ETag` header in the service's OpenAPI schema.

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
- **THEN** the response is the scan-failure 502 naming the failing event, with the unparseable-`reel.yaml`
  failure kind, never an empty or partial document

#### Scenario: An unprocessable event can still be read for fixing
- **WHEN** the event folder `2004/2004 - Yngve berättar om skövde`, whose name has a year only, has no
  `reel.yaml`
- **THEN** the read returns 200 with the empty editorial document and an `ETag`, so a client can submit a
  date to fix it

#### Scenario: The schema publishes the read's responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the read declares its 404 and 502 responses in the shared problem body shape, and the `ETag`
  header of its 200 response

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
when the event is fresh and `force` is false; a forced request always enqueues unless the
output-collision check refuses it. The enqueued job carries the event's fingerprint and the force flag.
`GET /api/v1/jobs` lists jobs (filterable by status); `GET /api/v1/jobs/{id}` returns one job's detail
(status, progress, device, worker, force, fingerprint, timestamps, error, requeue count);
`POST /api/v1/jobs/{id}/cancel` invokes the store's cancel request (flag a running job, cancel a queued one
directly, no-op reported for terminal jobs). The API MUST NOT transition job status itself.

A 201 SHALL mean that this request created the job. Whether a job was created SHALL be decided by the store
at the moment of insertion, not by an earlier read: an enqueue that finds, at insertion, an active job
created by a concurrent request SHALL answer 409 with that job's id, exactly like an enqueue that finds it
beforehand, and never 201.

The job id a problem body is about SHALL be carried in a typed `job_id` field of the shared problem body:
the active job's id on the enqueue 409, and the requested id on the 404 of the job detail and of cancel. The
404 of an enqueue for an unknown event SHALL name the event in `event_id`.

Every 409 that `POST /api/v1/jobs` returns SHALL carry the conflict kind in a `conflict` field, drawn from
the published enumeration of "Enqueue refuses an event whose output path another event claims":
`active_job` on the active-job 409, whether the job was found beforehand or at insertion, and
`output_collision` on that requirement's refusal, which is checked first.

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
- **WHEN** `POST /api/v1/jobs` names `2024/Blandat`, which already has a `queued` job that no worker has
  claimed
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

Every message SHALL be one frame shape: a `type` drawn from the closed set `snapshot` | `delta`, and the
list of jobs in the same job shape the jobs routes return. The list SHALL always be present (a snapshot
of no active jobs carries an empty list). Although a WebSocket route is not an HTTP operation, the
service's OpenAPI schema SHALL publish this frame shape and its type set as named schema components, with
both fields required, so a client generated from the schema has the frame's type without declaring it by
hand. The schema SHALL NOT describe the WebSocket as an HTTP path.

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
  backed up. The server cannot finish closing it, so it can make the shutdown fail, or stall it until a
  second SIGINT forces the exit.

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

#### Scenario: A dropped subscriber is told to reconnect
- **WHEN** the hub disconnects a subscriber whose outbound queue is full
- **THEN** that client receives close code 1013
- **AND** when it reconnects, its first message is a fresh snapshot

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

On the **list**, a failure that belongs to one event SHALL NOT fail the request. Such an event SHALL
appear as an **error row** in place of its summary, and every other event SHALL be listed as usual. A
per-event failure is any of: an unparseable or invalid `reel.yaml`, metadata without a real date and a
title, or files that cannot be listed. The error row SHALL carry:

- the event's ID
- a **failure kind** drawn from a closed set: an unparseable `reel.yaml`, unusable metadata, or an
  unreadable disk
- the engine's detail, which names the fix

It SHALL NOT carry clip counts, a staleness verdict, a title or any other fact that could not be read.
Every row, summary or error, SHALL state which of the two it is. The schema SHALL publish the list's item as
a union discriminated by that field, and the failure kind as an enumeration.

On an event's **detail**, the same per-event failures SHALL be answered with the scan-failure problem body.
It SHALL name the event and carry the same failure kind the list's error row would carry for that event.
Both reads SHALL classify a failure by the same rule, so they never disagree about why one event cannot be
read, and no per-event failure on either read SHALL surface as an unshaped server error.

The list SHALL NOT degrade otherwise: a request that cannot account for every walked event SHALL fail
rather than return a partial list, a list with the unavailable facts omitted, or a list with substituted
values. An unreachable job store fails the whole list, because every summary's latest job depends on it.
A walk of the project root that fails SHALL be reported as the scan-failure problem body, never an unshaped
error. Absence is reported, never fabricated, and a client is never left to guess whether a missing fact
means "none" or "could not be read".

Both reads SHALL publish these failures in the service's OpenAPI schema: each status code a read may
answer with a problem body, and the problem body's shape. The shape comprises its title, numeric status
and detail, plus the optional fields that name the failing dependency, the failing event, or the event's
failure kind. The list SHALL declare its scan-failure and database-failure responses, and the detail SHALL
additionally declare its unknown-event response. A client SHALL therefore derive the problem body's type
from the generated types rather than declaring it by hand, and every problem body these reads return SHALL
conform to the published shape.

#### Scenario: The job store is unreachable on the list
- **WHEN** the database is down and a client requests the events list
- **THEN** the response is a problem body identifying the failure as the job store's, not a bare error and
  not a list with every `latest_job` reported as absent

#### Scenario: The job store is unreachable on an event's detail
- **WHEN** the database is down and a client requests a single event's detail
- **THEN** the response is the same problem body the list returns for that failure, not a bare error and
  not a detail whose `latest_job` is reported as absent

#### Scenario: The scan itself fails
- **WHEN** the project root cannot be walked and a client requests the events list
- **THEN** the response is the scan-failure problem body, distinguishable from a database failure, and never
  an unshaped server error

#### Scenario: An unparseable reel.yaml becomes an error row
- **WHEN** one of three events has a `reel.yaml` that cannot be parsed and a client requests the events list
- **THEN** the response lists two summaries and one error row for that event, whose failure kind is the
  unparseable-`reel.yaml` kind and whose detail names the parse failure

#### Scenario: An event without a usable date becomes an error row
- **WHEN** an event folder named `2004 - Yngve berättar om skövde` has no `reel.yaml`
- **THEN** it is listed as an error row with the unusable-metadata kind, whose detail says the folder name
  has a year only and suggests `metadata.date` in `reel.yaml`

#### Scenario: A failed list is never partial
- **WHEN** a list request fails part-way through enumerating events, because the database or the walk
  failed
- **THEN** no partial list is returned, and the events that were read successfully are not reported as the
  whole set

#### Scenario: An unreadable event still 404s and 502s as before
- **WHEN** a client requests an unknown event, or one whose `reel.yaml` cannot be parsed
- **THEN** the detail route returns the 404 problem body as before, and a 502 problem body that now also
  carries the unparseable-`reel.yaml` failure kind

#### Scenario: A detail whose files cannot be listed is a 502, not a 500
- **WHEN** a client requests the detail of an event whose directory cannot be listed
- **THEN** the response is the scan-failure problem body naming the event, with the unreadable-disk failure
  kind, and never an unshaped server error

#### Scenario: List and detail agree on why an event cannot be read
- **WHEN** an event folder named `2019-04-31 - Golfträning med Emil - Tjörn` has no `reel.yaml`, and a client
  reads both the events list and that event's detail
- **THEN** the list's error row and the detail's problem body carry the same failure kind, the
  unusable-metadata kind, and the same detail

#### Scenario: A healthy read is unaffected
- **WHEN** the database is reachable and every event scans cleanly
- **THEN** both reads respond as before, except that each list row also states that it is an event summary;
  there is no added envelope and no new status code

#### Scenario: The schema publishes the problem responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the events list declares its 502 and 503 responses and the detail declares its 404, 502 and
  503 responses, each described by the shared problem body shape, which includes the optional failure kind,
  rather than left undeclared

#### Scenario: A returned problem body matches the published shape
- **WHEN** the database is down and a client requests the events list
- **THEN** the 503 body it receives validates against the published problem shape, including the field
  naming the database as the failing dependency

#### Scenario: The schema publishes the error row
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the list's item is a union of the summary and the error row discriminated by their kind field,
  and the failure kind is an enumeration of the three kinds

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

### Requirement: Clip status is a closed, published vocabulary

Every response field that carries a clip's reconcile status SHALL be drawn from the engine's closed set of
statuses (`new`, `active`, `missing`, `ignored`). The service's OpenAPI schema SHALL publish that set as an
enumeration rather than as a free-form string. A client SHALL therefore be able to derive an exhaustive type
for a clip's status, so that removing or renaming a status is a compile-time failure in generated client
code rather than a silent runtime change (D-8, §4.10).

This requirement MUST NOT change any status's wire value: an existing client reading a clip's status as a
plain string continues to read the same string.

#### Scenario: The schema publishes the clip status set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** a clip's status on the event detail is described as the enumeration of clip statuses, not as an
  unconstrained string

#### Scenario: A renamed clip status breaks the client build
- **WHEN** a clip status is renamed in the engine and the schema and client types are regenerated
- **THEN** client code that referred to the old status fails to compile, rather than silently ceasing to
  match

#### Scenario: Wire values are unchanged
- **WHEN** a client that treats a clip's status as a plain string reads the detail of an event with a NEW, an
  ACTIVE, a MISSING and an IGNORED clip
- **THEN** it receives `new`, `active`, `missing` and `ignored`, the same strings it received before this
  change

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

### Requirement: Enqueue refuses an event whose output path another event claims
`POST /api/v1/jobs` SHALL apply the output-collision rule the batch commands apply (D-9). The event it names
SHALL be refused when its output path is also the output path of another event of the served project. Paths
SHALL be compared exactly as the batch commands compare them: case-insensitively and after Unicode
normalization. The claimants SHALL be every event the configured layout walks from the served root, the
same events the events list shows, plus the named event itself. There is no selection: the check covers the
whole project, as `auto-reel enqueue <root>` does without `--years`. An event whose `reel.yaml` cannot be
read, whose files cannot be listed, or whose resolved metadata lacks a real date or a title (or carries a
future date) SHALL claim no path. Such an event fails on its own, as the events list's error row already
reports.

The check SHALL run before the active-job check and before the staleness gate. An event that collides and
also has an active job SHALL therefore be answered as a collision. `force` SHALL NOT override the check,
and it SHALL apply whether the event is fresh or stale. A refused event SHALL be answered with **409** and
a problem body that:

- names the event (`event_id`)
- carries the conflict kind `output_collision`
- lists the other claimants' event ids in `claimed_by`, sorted
- has a detail that states the shared output path, names the other claimants, and names the fix: a
  distinct title or location in `reel.yaml`

For a refused event nothing SHALL be written: no job row, no render manifest, and no change to an output
file that already exists at the shared path. A refusal SHALL NOT be resolved by renaming, suffixing or
skipping one side.

The `conflict` field that every 409 of `POST /api/v1/jobs` carries ("Jobs lifecycle over REST") SHALL take
its value from a closed set that the service's OpenAPI schema publishes as an enumeration:

- `active_job`: an active (`queued` or `running`) job already exists for the event. The body carries that
  job's id.
- `output_collision`: as above.

A client can therefore choose its reaction from the published type alone, never from the detail text.

When the project walk itself fails, the collision cannot be checked. The endpoint SHALL then answer with the
scan-failure 502 that the events list uses, and SHALL NOT enqueue. The schema SHALL publish that 502, and the
`conflict` and `claimed_by` fields of the shared problem body.

#### Scenario: A case-only twin is refused
- **WHEN** `POST /api/v1/jobs` names `2024/2024-07-14 - kalas` in the dev library, whose folder name
  differs from `2024/2024-07-14 - Kalas` only in letter case, so that both events resolve to the output
  path `2024/2024-07-14 - Kalas.mp4` (a title taken from a folder name is title-cased)
- **THEN** the response is 409 with `conflict` `output_collision` and `claimed_by`
  `["2024/2024-07-14 - Kalas"]`
- **AND** its detail names `2024/2024-07-14 - Kalas.mp4` and says to set a distinct title or location in
  `reel.yaml`
- **AND** no job row is inserted

#### Scenario: A rendered event's movie is protected
- **WHEN** `POST /api/v1/jobs` names the fresh, already rendered `2024/2024-07-14 - Kalas` without `force`
- **THEN** the response is 409 with `conflict` `output_collision` naming `2024/2024-07-14 - kalas`, not the
  200 "fresh" outcome
- **AND** `2024/2024-07-14 - Kalas.mp4` in the output directory is byte-for-byte unchanged, and no job row
  or manifest is written

#### Scenario: Force does not override a collision
- **WHEN** `POST /api/v1/jobs` names `2024/2024-07-14 - kalas` with `"force": true`
- **THEN** the response is the same 409 `output_collision`, and no job row is inserted

#### Scenario: An event outside any collision enqueues as before
- **WHEN** `POST /api/v1/jobs` names the stale `2024/2024-06-27 - Grillning med grannar`, whose output path
  no other event claims
- **THEN** the response is 201 with the queued job, as before this change

#### Scenario: An event that fails on its own claims no path
- **WHEN** the dev library holds `2024/2024-02-30 - Omöjligt datum`, whose folder date is impossible, and
  an event whose `reel.yaml` cannot be parsed is added beside it
- **THEN** neither is counted as a claimant, the check does not fail because of them, and
  `POST /api/v1/jobs` for `2024/2024-06-27 - Grillning med grannar` answers 201

#### Scenario: The CLI and the service refuse the same events
- **WHEN** `auto-reel enqueue <library>` runs over the dev library
- **THEN** it reports `2024-07-14 - Kalas` and `2024-07-14 - kalas` as colliding with each other, exactly as
  before this change
- **AND** `POST /api/v1/jobs` for either event answers 409 `output_collision`, whose `claimed_by` names the
  other

#### Scenario: A walk that fails refuses to enqueue
- **WHEN** a year folder of the served project cannot be listed while `POST /api/v1/jobs` names an event
  in another year
- **THEN** the response is the scan-failure 502 problem body, and no job row is inserted

#### Scenario: The schema publishes the conflict vocabulary
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the shared problem body's `conflict` field is the enumeration of exactly `active_job` and
  `output_collision`, and `claimed_by` is a list of strings
- **AND** `POST /api/v1/jobs` declares its 409 and 502 responses in that shape

### Requirement: The jobs surface is scoped to the served project
The service serves exactly one project, its configured project root. Every jobs view it offers SHALL cover
only jobs whose recorded project root is that root, the same root the service enqueues with and the events
reads use for an event's latest job. The views are:

- `GET /api/v1/jobs`, with or without the status filter
- `GET /api/v1/jobs/{id}`
- `POST /api/v1/jobs/{id}/cancel`
- the snapshot and every delta on `WS /api/v1/ws/jobs`

Wherever another requirement of this capability speaks of "the jobs", "the active jobs" or "a job", it means
the served project's jobs.

A job of another project, and a job with no recorded project root, SHALL be treated as absent:

- `GET /api/v1/jobs/{id}` and `POST /api/v1/jobs/{id}/cancel` SHALL answer 404 exactly as for an unknown id.
- A cancel SHALL NOT change such a job in any way.
- Such a job SHALL NOT be listed.
- Such a job SHALL NOT appear in a snapshot or a delta, and a change to it SHALL NOT cause a delta. This
  includes a job that became terminal since the previous poll although no earlier frame carried it: the
  hub reports such a job once only when it is the served project's.

This scoping governs only what the service shows and cancels. The job queue itself stays shared: a worker
claims the oldest eligible job of any project, as before.

#### Scenario: Two libraries in one database
- **WHEN** the service serves dev library A, and dev library B, built into the same database, has its own
  `queued` job for `2024/Blandat`
- **THEN** `GET /api/v1/jobs` and `GET /api/v1/jobs?status=queued` list A's `2024/Blandat` job and not B's

#### Scenario: Another project's job is unknown by id
- **WHEN** `GET /api/v1/jobs/{id}` or `POST /api/v1/jobs/{id}/cancel` names library B's queued job
- **THEN** both answer 404 with the problem body an unknown id gets
- **AND** B's job is still `queued` with `cancel_requested` false

#### Scenario: The live feed carries only the served project
- **WHEN** a client connects to `WS /api/v1/ws/jobs` while library A and library B each have a running
  job, both jobs' progress then advances, and B's job then finishes
- **THEN** the snapshot contains only A's job, and deltas arrive for A's job and never for B's, including
  B's terminal transition

#### Scenario: A foreign job's short life is never reported
- **WHEN** a client is connected to `WS /api/v1/ws/jobs` served for library A, and library B's job for
  `2024/2024-10-05 - Trasig` is enqueued, claimed and fails at probe between two polls, then library A's
  job for the same event does the same between two later polls
- **THEN** no frame carries B's job, and exactly one delta carries A's job with status `failed`

#### Scenario: The queue stays shared
- **WHEN** the service serves library A and a worker runs against the same database while only library B
  has a queued job
- **THEN** the worker claims and renders B's job, as before this change, and the service's views never show
  it
