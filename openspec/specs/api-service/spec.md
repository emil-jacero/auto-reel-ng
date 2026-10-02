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

The endpoint SHALL answer only for an event the events list shows. `event_id` SHALL be judged by the same
rule as the thumbnail and media endpoints: a folder the events list does not show as an event, such as the
project root, a year folder, an event's `original/` or chapter folder, or a `.reelignore`d event, is
answered 404 with a problem body naming the event, exactly as an unknown id is, and nothing under it is
read. The endpoint SHALL NOT read `reel.yaml`: analysis is a fact of the sidecar cache and the clip files,
so an event whose document is broken still answers for its cache.

A failure that is not the request's fault SHALL be a shaped 502 problem body naming the event, never an
unshaped server error: an event whose folder cannot be listed carries the unreadable-disk failure kind the
events reads use, and a layout the service cannot resolve carries no failure kind. The service's OpenAPI
schema SHALL declare the endpoint's 404 and 502 in the shared problem body shape. The endpoint SHALL NOT need
the database and SHALL declare no 503.

#### Scenario: Cached analysis is returned
- **WHEN** an event has a populated analysis sidecar cache
- **THEN** the endpoint returns its segments per clip

#### Scenario: Absent cache is not an empty result
- **WHEN** an event has never been analyzed
- **THEN** the response indicates analysis is absent (not an empty segment list)

#### Scenario: A year folder is not an event
- **WHEN** a client requests `GET /api/v1/events/2024/analysis` for a year folder that holds events
- **THEN** the response is 404 with a problem body naming `2024`, not a 200 saying nothing was analyzed

#### Scenario: An event's original folder is not an event
- **WHEN** a client requests the analysis of `2024/2024-06-21 - A/original`, a directory inside a listed
  event
- **THEN** the response is 404, the same answer the thumbnail endpoint gives for that folder

#### Scenario: A reelignored event is not an event
- **WHEN** a client requests the analysis of an event folder carrying a `.reelignore`
- **THEN** the response is 404, because the events list does not show it

#### Scenario: A broken reel.yaml does not hide the cache
- **WHEN** a listed event's `reel.yaml` cannot be parsed and its sidecar cache holds segments
- **THEN** the analysis endpoint returns those segments, because it never reads the document

#### Scenario: An event whose folder cannot be listed is a 502
- **WHEN** the listed event's directory cannot be read and a client requests its analysis
- **THEN** the response is the scan-failure problem body naming the event with the unreadable-disk failure
  kind, and never an unshaped server error

#### Scenario: An unresolvable layout is a 502 without a kind
- **WHEN** the configured ingest layout name is not one the service knows and a client requests an
  analysis
- **THEN** the response is a 502 problem body naming the event whose detail names the layout, with no
  failure kind

#### Scenario: The schema publishes the analysis problem responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the analysis endpoint declares its 404 and 502 responses in the shared problem body shape

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
editorial read endpoint. The header SHALL be evaluated across every `If-Match` header line the request
carries, as RFC 9110 defines repeated lines to be one comma-separated list: a request with the lines
`If-Match: "stale"` and `If-Match: "<current>"` is the same request as one line holding both tags, and
matches. A request that carries the header at all, even with an empty value, is conditional. When the header
is present and matches the event's current editorial state, the write SHALL proceed. When it is present and
does not match, the service SHALL respond `412 Precondition Failed` with a problem body and leave `reel.yaml`
byte-for-byte unchanged. When the header is absent, the write SHALL be unconditional exactly as before, so
scripted clients and any CLI-equivalent caller keep working without it. The ETag SHALL identify the
**editorial** state canonically: a comment-only or formatting-only edit to `reel.yaml` MUST NOT change it,
while any change to metadata, chapters, clip order, per-clip properties, `ignore`, or `look` MUST change it.

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

#### Scenario: A matching tag on a later header line writes
- **WHEN** a client PUTs with two `If-Match` header lines, the first a tag that does not match and the
  second the `ETag` from a read whose state has not changed
- **THEN** the write is applied, exactly as if the two tags had been sent comma-joined in one line

#### Scenario: No header line matches
- **WHEN** a client PUTs with two `If-Match` header lines, neither of which matches the current state
- **THEN** the response is 412 and `reel.yaml` is byte-for-byte unchanged

#### Scenario: An empty If-Match is still a precondition
- **WHEN** a client PUTs with an `If-Match` header whose value is empty
- **THEN** the response is 412, not an unconditional write

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
change (D-8, §4.10). Adding a reason is a compile-time failure in any client map that gives every reason its
words, until that map names the new reason.

The published values SHALL be exactly the reasons the staleness gate cites: `no_manifest`, `output`,
`output_renamed`, `editorial`, `defaults`, `clip_set` and `engine`. The schema's description of the enumeration
SHALL say what each reason means. For `output_renamed`, it SHALL say three things: the event's movie name changed
since its last render, the next render writes the movie under the new name, and the previous movie stays on disk.
No reason's wire value SHALL change. A client reading reasons as plain strings continues to read the same string
for every reason it already knew.

An event whose movie name changed since its last render, with that render's movie still on disk, SHALL be reported
with `output_renamed` in place of `output` by every response that carries a verdict:
- the events list;
- the event detail;
- the verdict a successful editorial write echoes.

The reason is read-only information. No response or request writes, moves or deletes a movie because of it.

#### Scenario: The schema publishes the closed set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the staleness verdict's reasons are described as an enumeration of the gate's reasons, not as
  an unconstrained array of strings, and the enumeration includes `output_renamed`

#### Scenario: A renamed reason breaks the client build
- **WHEN** a reason is renamed in the engine and the schema and client types are regenerated
- **THEN** client code that referred to the old reason fails to compile, rather than silently ceasing to
  match

#### Scenario: An added reason must be named by an exhaustive client map
- **WHEN** the schema publishes `output_renamed` and the client types are regenerated
- **THEN** a client map that gives every reason its words fails to compile until it has words for
  `output_renamed`

#### Scenario: Wire values are unchanged
- **WHEN** a client that treats reasons as plain strings reads a stale event's verdict
- **THEN** every reason it knew before arrives as the same string, and a renamed event whose previous movie is on
  disk arrives as `output_renamed` where it used to arrive as `output`

#### Scenario: A retitled event reads the same on the list and the detail
- **WHEN** `2024-06-27 - Grillning med grannar` was rendered to `2024/2024-06-27 - Grillning med Grannar.mp4` and
  its title was then changed to `Grillkväll med grannarna` on disk
- **THEN** `GET /api/v1/events` and `GET /api/v1/events/2024/2024-06-27%20-%20Grillning%20med%20grannar` both
  report its staleness as `{"stale": true, "reasons": ["editorial", "output_renamed"]}`

#### Scenario: A save that renames the movie echoes the new reason
- **WHEN** a `PUT /api/v1/events/{event_id}/reel` with a matching `If-Match` changes the location of the fresh
  `2024/2024-06-21 - Midsommar - Dalarna` from `Dalarna` to `Leksand`
- **THEN** the 200 response's verdict is `{"stale": true, "reasons": ["editorial", "output_renamed"]}`
- **AND** no job is enqueued, and `2024/2024-06-21 - Midsommar - Dalarna.mp4` in the output directory is unchanged

#### Scenario: A deleted movie still reads as missing
- **WHEN** the fresh `2024/2024-07-14 - Kalas` has its movie deleted from the output directory, with no edit
- **THEN** the list and the detail report its staleness as `{"stale": true, "reasons": ["output"]}`

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

### Requirement: An event's latest job reports when it started and finished

Wherever an events response carries an event's latest job (each summary row of `GET /api/v1/events`, and
`GET /api/v1/events/{event_id}`), that job SHALL carry `started_at` and `finished_at` alongside its `id`,
`status`, `progress` and `created_at`. Both SHALL have the same value and meaning as the same-named fields of
the job's own detail (`GET /api/v1/jobs/{id}`) at the same moment:

- `started_at` SHALL be the time a worker claimed the job for its current run. It SHALL be null while the
  job is queued, including after a requeue, and for a job that was cancelled while it was queued.
- `finished_at` SHALL be the time the job reached `done`, `failed` or `canceled`. It SHALL be null while
  the job is queued or running.

Both keys SHALL always be present in the latest job, holding a time or null. A time the job store did not
record SHALL be reported as null: it MUST NOT be replaced with `created_at`, the current time, or any other
value. The list and the detail SHALL report the same times for the same event when no job changed between
the two requests.

The service's OpenAPI schema SHALL publish every field of the latest-job model exactly as it publishes the
same-named field of the job detail. The two new fields are therefore optional, nullable date-times, and a
generated client types each field identically in both places. The four existing fields SHALL keep their
names, types, required status and values, so a client that reads only them receives exactly what it
received before.

#### Scenario: A rendered event's latest job says when it ran
- **WHEN** `GET /api/v1/events` lists `2024-06-27 - Grillning med grannar`, whose latest job a worker
  rendered to `done`
- **THEN** its `latest_job` carries `created_at`, `started_at` and `finished_at`, each equal to the
  same-named field of `GET /api/v1/jobs/{id}` for that job
- **AND** `created_at` ≤ `started_at` ≤ `finished_at`

#### Scenario: A render that failed at probe reports its times on both reads
- **WHEN** `2024-10-05 - Trasig`, whose only clip is a zero-byte file, has a latest job that a worker
  claimed and that failed at probe, and the event is read through `GET /api/v1/events` and
  `GET /api/v1/events/{event_id}`
- **THEN** both reads report the same non-null `started_at` and `finished_at`, equal to the job detail's

#### Scenario: A job no worker has claimed has no start or finish time
- **WHEN** `2024/Blandat`'s latest job is `queued` and no worker is running
- **THEN** its `latest_job` has `started_at: null` and `finished_at: null`, with both keys present

#### Scenario: A job cancelled before it started is not given a start time
- **WHEN** a job for `2024-08-02 - Badutflykt - Varberg` is enqueued and cancelled before any worker
  claims it, and the events list is then read
- **THEN** that event's `latest_job` has status `canceled`, `started_at: null`, and a non-null
  `finished_at` equal to the one `GET /api/v1/jobs/{id}` reports for that job

#### Scenario: A running job has a start time until a stopped worker requeues it
- **WHEN** a worker has claimed a render of `2024-06-27 - Grillning med grannar`, and the events list is
  read
- **THEN** that event's `latest_job` has status `running`, a `started_at` equal to the job detail's, and
  `finished_at: null`
- **AND** once that worker is stopped gracefully and the job is requeued, the `latest_job` has status
  `queued`, `started_at: null` and `finished_at: null`

#### Scenario: The schema publishes the times as the job detail does
- **WHEN** the service's OpenAPI schema is generated
- **THEN** every property of the latest-job model has a definition identical to the job detail's
  same-named property, and `started_at` and `finished_at` are not required
- **AND** its required fields are exactly `id`, `status`, `progress` and `created_at`, as before

### Requirement: Clip thumbnail endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/thumbnail?clip=<identity>`. It returns one clip's
thumbnail as the engine's thumbnail operation produces it: a JPEG frame taken at the configured fraction of
the clip's duration and fitted within 320×180. `event_id` is the event identity the events routes use. `clip`
is a required query parameter carrying the clip's identity exactly as the event detail lists it, which is its
event-relative path, including any chapter folder. It is percent-encoded as a query value: as in any
form-encoded query, a literal `+` reads as a space. The identity SHALL be matched exactly, with no path or
Unicode normalization.

The endpoint SHALL accept an OPTIONAL query parameter `v`, an opaque string a client MAY send to give a
changed clip a new URL. The service SHALL ignore its value: `v` SHALL NOT affect the clip lookup, the
thumbnail's cache key, the `ETag` or the status.

**Which clips have a thumbnail.** A clip SHALL have a thumbnail when its identity is one of the clips the
engine's discovery finds on disk for that event, which is every clip the event detail lists that is not
MISSING, IGNORED clips included. The endpoint SHALL answer the following with 404 and a problem body naming
the event, without running ffmpeg or ffprobe and without reading any file outside the event:
- an unknown event, or a folder the events list does not show as an event, such as a year folder, an
  event's `original/` folder or a `.reelignore`d event
- a clip the event's document references but disk does not have (MISSING)
- a file discovery skips, such as one under `original/`
- any identity that is not a discovered clip of that event, including one that points outside the event

**Success and validators.**
- A 200 response SHALL carry the JPEG as `image/jpeg`, a strong `ETag` identifying the cache entry whose
  bytes it carries, and `Cache-Control: private, max-age=86400`.
- The entity-tag SHALL change whenever the clip file's size or modification time changes, the configured
  frame position changes, or the engine's thumbnail version changes.
- A request whose `If-None-Match` matches the current entity-tag, under weak comparison and across all its
  `If-None-Match` header lines, SHALL be answered 304 with the same `ETag` and `Cache-Control` and no body.
  That answer SHALL be given without extracting a frame, even when no thumbnail is cached on the server.

**Extraction.**
- A thumbnail already cached SHALL be served without extraction and without waiting behind extractions in
  progress.
- A missing thumbnail SHALL be generated on request through the engine's thumbnail operation, which caches
  it outside the library.
- At most two extractions SHALL run at once in one service process. Further requests SHALL wait for a
  slot, not fail.
- Concurrent requests that need the same thumbnail SHALL share a single extraction.
- The endpoint SHALL NOT block the service's event loop on disk or ffmpeg work, so other endpoints keep
  answering while thumbnails are extracted.
- A requester that disconnects SHALL NOT abort an extraction that other requests share.

**Failures, by cause.** Each SHALL be a problem body naming the event:
- **502 with the thumbnail failure kind:** the engine cannot produce a thumbnail. For example, the clip is
  empty or undecodable, it has no frame at the configured position, or it can no longer be statted
  because it changed after the event was listed. The detail SHALL name the clip by its requested identity
  and give the engine's reason cut to one line, without server paths, commands or tool output. No
  placeholder image is returned.
- **502 with the unreadable-disk failure kind the events reads use:** the event's folder cannot be listed.
- **502 whose detail names the problem, with no failure kind:** the thumbnail cache cannot be read or
  written, or the project `config.yaml` cannot be loaded or holds an invalid thumbnail setting.

A failed extraction SHALL NOT be remembered: the next request for the same clip tries again. Problem
responses SHALL carry no caching headers.

**Scope.**
- The endpoint SHALL NOT need the database: it answers while the database is unreachable, and it declares
  no 503.
- It SHALL NOT write anything into the library: no `reel.yaml`, no render manifest, no file beside the
  clips.
- It SHALL NOT enqueue a job.
- The events list and the event detail SHALL gain no thumbnail field, and they stay probe-free. A client
  builds the thumbnail URL from the event id and the clip identity it already holds, and MAY add the clip's
  modification time from the event detail as `v`.
- The endpoint SHALL publish in the service's OpenAPI schema:
  - its required `clip` and optional `v` query parameters
  - its optional `If-None-Match` request header
  - its 200 as `image/jpeg`, with the `ETag` and `Cache-Control` headers
  - its 304
  - its 404 and 502 in the shared problem body shape

#### Scenario: A clip's thumbnail is served from the cache outside the library
- **WHEN** `GET /api/v1/events/2024/2024-06-27%20-%20Grillning%20med%20grannar/thumbnail?clip=s1710001.mp4`
  is requested for the first time
- **THEN** the response is 200 `image/jpeg` whose body is a JPEG no larger than 320×180, with an `ETag` and
  `Cache-Control: private, max-age=86400`. The thumbnail is stored in the configured cache directory, and no
  file is created or changed under the event's folder.

#### Scenario: A repeat request is served from the cache
- **WHEN** the same Grillning clip is requested again without `If-None-Match`
- **THEN** the response is 200 with a byte-identical body and the same `ETag`, and no ffmpeg or ffprobe
  process is started

#### Scenario: The version parameter changes nothing on the server
- **WHEN** the same Grillning clip is requested with `v=2024-06-27T14:03:11.123456Z`, and again with
  `v=other`
- **THEN** both responses are 200 with byte-identical bodies and the same `ETag` as a request without `v`,
  and no second extraction runs

#### Scenario: Revalidation costs no extraction
- **WHEN** the Grillning clip is requested with `If-None-Match` set to the `ETag` of the earlier response,
  or to the same tag prefixed `W/`
- **THEN** the response is 304 with that `ETag` and the same `Cache-Control`, no body, and no ffmpeg or
  ffprobe process is started

#### Scenario: A changed clip gets a new entity-tag
- **WHEN** a clip's file is replaced by another recording, changing its size and modification time, and it
  is requested with the old `ETag` in `If-None-Match`
- **THEN** the response is 200 with the new frame and a different `ETag`

#### Scenario: A clip in a chapter folder
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for `clip=Kv%C3%A4llen%2Fs1710002.mp4`
- **THEN** the response is 200 `image/jpeg` for the clip in the `Kvällen` chapter folder

#### Scenario: An identity with spaces, punctuation and Swedish letters
- **WHEN** an event holds the chapter folder `Kväll, del 2` with the clip `a+b & c #1.mp4`, and the
  thumbnail is requested with `clip=Kv%C3%A4ll%2C%20del%202%2Fa%2Bb%20%26%20c%20%231.mp4`
- **THEN** the response is 200 `image/jpeg` for that clip
- **AND** the same identity sent with a literal `+` is looked up as `a b & c #1.mp4` and answers 404

#### Scenario: An IGNORED clip still has a thumbnail
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for its root clip `s1710004.mp4`,
  which its `reel.yaml` lists under `ignore`
- **THEN** the response is 200 `image/jpeg`

#### Scenario: A MISSING clip has no thumbnail
- **WHEN** the event `2024/2024-09-01 - Sommarlov` is asked for `borttagen.mp4`, which its `reel.yaml`
  references but disk does not have
- **THEN** the response is 404 with a problem body naming the event, and no ffmpeg or ffprobe process is
  started

#### Scenario: An identity outside the event is not a clip of the event
- **WHEN** the event `2024/2024-07-14 - Kalas` is asked for `clip=../2024-06-27 - Grillning med grannar/s1710001.mp4`
- **THEN** the response is 404 and no file outside the Kalas folder is read

#### Scenario: A path that only normalizes to a clip is not its identity
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for `clip=Kvällen/../s1710001.mp4`
- **THEN** the response is 404, although `s1710001.mp4` is a clip of that event

#### Scenario: Unknown event
- **WHEN** the endpoint names an event id that does not resolve under the configured project root
- **THEN** the response is 404 with a problem body

#### Scenario: A folder that is not an event
- **WHEN** the endpoint names the year folder `2024` with `clip=2024-06-27 - Grillning med grannar/s1710001.mp4`,
  or the folder `2024/2024-06-27 - Grillning med grannar/original` with a file in it
- **THEN** each response is 404 with a problem body naming the requested id, and no ffmpeg or ffprobe
  process is started

#### Scenario: An undecodable clip fails loud with the thumbnail kind
- **WHEN** the event `2024/2024-10-05 - Trasig` is asked for its zero-byte clip `trasig.mp4`
- **THEN** the response is 502 with the thumbnail failure kind, and a detail naming `trasig.mp4` and
  reporting that the file is empty. No image and no cache entry are produced, and a second request tries
  again and answers the same 502.

#### Scenario: A corrupt clip's detail is one line without server paths
- **WHEN** an event holds a clip of random bytes, or an mp4 whose media data is cut short behind an intact
  index, and each is requested
- **THEN** each response is 502 with the thumbnail failure kind, and its detail is the clip's identity
  followed by a one-line cause: no newline, no ffmpeg or ffprobe command, and no path of the server
- **AND** the service's log keeps the full reason, with the failing command and its output

#### Scenario: A cache that cannot be written is the service's fault, not the clip's
- **WHEN** the configured thumbnail cache directory is read-only and an uncached clip is requested
- **THEN** the response is 502 whose detail names the operating-system error, with no thumbnail failure
  kind

#### Scenario: A read-only library still gets thumbnails
- **WHEN** the library is mounted read-only, as the MOL archive often is, and an uncached clip of
  `2024/2024-06-27 - Grillning med grannar` is requested
- **THEN** the response is 200 `image/jpeg`, and the thumbnail is written only into the cache directory

#### Scenario: Extraction is bounded
- **WHEN** a client requests the thumbnails of twelve distinct uncached clips at once
- **THEN** every request is answered 200, and at no moment are more than two extractions running in the
  service process

#### Scenario: Concurrent requests share one extraction
- **WHEN** five requests for the same uncached clip arrive at once
- **THEN** exactly one extraction runs, and all five responses are 200 with identical bodies and `ETag`s

#### Scenario: A cached thumbnail does not wait for a slot
- **WHEN** two slow extractions hold both slots and a thumbnail that is already cached is requested
- **THEN** that thumbnail is answered 200 without waiting for either extraction to finish

#### Scenario: Other endpoints keep answering during extraction
- **WHEN** extractions occupy both slots and further thumbnail requests are waiting for a slot
- **THEN** `GET /api/v1/events` is still answered without waiting for any extraction

#### Scenario: No database needed
- **WHEN** the database is unreachable and a clip of `2024/2024-06-27 - Grillning med grannar` is requested
- **THEN** the response is 200 `image/jpeg`, never a 503

#### Scenario: The read model gains no field
- **WHEN** `GET /api/v1/events` and `GET /api/v1/events/{event_id}` are served after this endpoint exists
- **THEN** their responses carry no thumbnail field, and no clip is probed or decoded to answer them

#### Scenario: The schema publishes the thumbnail responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the thumbnail route declares a required `clip` query parameter, an optional string query
  parameter `v` and an optional `If-None-Match` header parameter, and publishes:
  - a 200 as `image/jpeg` with the `ETag` and `Cache-Control` headers
  - a 304
  - 404 and 502 in the shared problem body shape
  - no 503

### Requirement: Thumbnail failure kind is a closed, published vocabulary
A thumbnail endpoint problem that the engine's thumbnail operation caused SHALL carry its kind in a
problem field of its own, drawn from a closed set that is currently `thumbnail_failed`. The service's
OpenAPI schema SHALL publish that set as an enumeration rather than as a free-form string. A client SHALL
therefore be able to derive an exhaustive type for it, and removing or renaming a value is a compile-time
failure in generated client code rather than a silent runtime change (D-8, §4.10).

The thumbnail kind SHALL be separate from the events failure kind:
- the events failure set (`unparseable_reel_yaml`, `unusable_metadata`, `unreadable_disk`) SHALL be unchanged
- an event's error row SHALL never carry a thumbnail kind
- a client type generated for the existing problem fields SHALL be unchanged

#### Scenario: The schema publishes the thumbnail failure set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the problem body declares an optional thumbnail failure field described as the enumeration
  `thumbnail_failed`, and the events failure enumeration still has exactly its three values

#### Scenario: The existing client still compiles
- **WHEN** the schema and client types are regenerated with this change and the unchanged web client is
  type-checked
- **THEN** the type check passes with no client edit

#### Scenario: The failure kind on the wire
- **WHEN** the thumbnail of `2024/2024-10-05 - Trasig`'s `trasig.mp4` is requested
- **THEN** the 502 problem body carries the thumbnail failure field with the value `thumbnail_failed`,
  and no `failure` field

### Requirement: The event detail places clips not in reel.yaml by the render's adoption rule

`GET /api/v1/events/{event_id}` SHALL list every clip on disk that the event's `reel.yaml` does not list,
whether NEW or IGNORED, in the chapter that a render's adoption rule names for it (headless-cli, "NEW-clip
adoption policy"). That is the chapter named after the clip's folder when `reel.yaml` names that chapter, and
the default chapter otherwise. When `reel.yaml` names no chapters at all, it is the chapter named after the
clip's folder, as seeding places it. A NEW clip is therefore shown in the chapter a render adopts it into.

Within a chapter, those clips SHALL follow the clips that `reel.yaml` lists. Among themselves they SHALL be
in the sort rule's order, which is the order a render appends them in. When `reel.yaml` does not name the
default chapter and a clip is placed there, the detail SHALL list the default chapter after the chapters
`reel.yaml` names. When `reel.yaml` names no chapters, the detail SHALL list the chapters its folders seed,
in seeding order. The detail SHALL list no other chapter that `reel.yaml` does not name. An event without a
`reel.yaml` SHALL keep listing the chapters its folders seed, which are the chapters a render seeds.

Leaving ignored clips aside, the detail read before a render SHALL therefore list the same chapters, in the
same order and each with the same clips in the same order, as `reel.yaml` lists once the render has adopted
the event's NEW clips. The one exception is a chapter that the detail lists only for ignored clips: a render
adopts no ignored clip, so `reel.yaml` does not gain that chapter. The read SHALL apply this placement
without adopting anything, and SHALL stay read-only and probe-free.

#### Scenario: A NEW clip is shown in its folder's chapter

- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `s1710001.mp4` in its default chapter
  and `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` in `Kvällen`, and `Kvällen/s1710004.mp4` is on disk
  but not listed
- **THEN** the detail lists `Kvällen` as `Kvällen/s1710002.mp4` (active), `Kvällen/s1710003.mp4` (active),
  `Kvällen/s1710004.mp4` (new), and the default chapter as `s1710001.mp4` (active) alone

#### Scenario: A clip in a folder without a chapter is shown in the default chapter

- **WHEN** an event's `reel.yaml` names only the default chapter, listing `s1710001.mp4`, and
  `Dag 2/s1710002.mp4` and `Dag 2/s1710003.mp4` are on disk
- **THEN** the detail lists exactly one chapter, the default chapter, holding `s1710001.mp4` (active) and then
  both `Dag 2` clips (new) in the sort rule's order, and lists no `Dag 2` chapter

#### Scenario: A document that names no chapters is shown as its folder seed

- **WHEN** an event's `reel.yaml` holds only `metadata`, and the event holds `s1710001.mp4` in its folder and
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4` in a subfolder
- **THEN** the detail lists the default chapter holding `s1710001.mp4` (new), then a `Kvällen` chapter holding
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4` (new) in the sort rule's order
- **AND** after `auto-reel render` adopts them, `reel.yaml` lists the same two chapters with the same clips
  in the same order, and the detail lists them again with every clip active

#### Scenario: An ignored clip in a folder without a chapter is shown in the default chapter

- **WHEN** an event's `reel.yaml` names only the default chapter and ignores `Dag 2/s1710002.mp4`, which is
  on disk
- **THEN** the detail lists `Dag 2/s1710002.mp4` in the default chapter with status ignored, and lists no
  `Dag 2` chapter

#### Scenario: An event without reel.yaml shows its folder seed

- **WHEN** an event has no `reel.yaml` and holds `s1710001.mp4` in its folder and `Kvällen/s1710002.mp4`
- **THEN** the detail lists the default chapter holding `s1710001.mp4` and a `Kvällen` chapter holding
  `Kvällen/s1710002.mp4`, both new, and no `reel.yaml` is written

#### Scenario: The page's chapters are the movie's chapters

- **WHEN** the detail of an event is read while it has NEW clips in a folder whose chapter `reel.yaml` names,
  in a folder whose chapter it does not name, and in the event folder; then `auto-reel render` adopts them;
  then the detail is read again
- **THEN** both reads list the same chapters, each with the same clips in the same order, ignored clips
  aside, and these are the chapters and clips that `reel.yaml` then lists
- **AND** every clip the first read listed as new, the second lists as active

### Requirement: Media files are streamed with ranges and validators
The clip media endpoint and the rendered movie endpoint SHALL serve a media file's bytes exactly as they are on
disk, with one shared HTTP behavior. The service SHALL NOT transcode, remux, probe or decode a file to serve
it. A clip whose audio a browser cannot decode, such as the PCM audio of a Sony XAVC clip, SHALL be served
unchanged.

**Methods.** Both endpoints SHALL answer `GET` and `HEAD`, with and without the built web client mounted.
A `HEAD` request SHALL be answered with the status and the headers that a `GET` of the same URL and request
headers is answered with, `Content-Length`, `Content-Range`, `Content-Type`, `ETag`, `Last-Modified` and
`Cache-Control` included, and with no body. That covers every status the endpoints give: 200, 206, 304, 400,
404, 416 and 502. A `HEAD` SHALL run the same lookup and open the file once, as a `GET` does, so it never
answers 200 or 206 for a file a `GET` would answer 404 or 502 for.

**Whole file and ranges.**
- A request without `Range` SHALL be answered 200 with the whole file, a `Content-Length` equal to its size
  and `Accept-Ranges: bytes`.
- A request with one satisfiable byte range SHALL be answered 206 with exactly the requested bytes,
  `Content-Range: bytes <first>-<last>/<size>` and the matching `Content-Length`. This covers `bytes=<first>-<last>`,
  the open-ended `bytes=<first>-` that browsers send, and the suffix form `bytes=-<n>`.
- A last byte past the end of the file SHALL be read as the file's last byte, so `bytes=0-<huge>` is the
  whole file as 206. A suffix longer than the file SHALL likewise be the whole file as 206.
- A range whose first byte lies at or past the end of the file SHALL be answered 416 with `Content-Range:
  bytes */<size>`. This includes the empty suffix `bytes=-0` and any range on a zero-byte file.
- A `Range` header with no `=`, with no range in it, with a first byte after its last byte plus one, or
  naming a unit other than `bytes` SHALL be answered 400. The 400 and 416 bodies are plain text, not problem
  bodies.
- Any other `Range` value, including several ranges, SHALL be answered with 200 (the whole file, the header
  ignored), 206, 400 or 416, never with a 5xx, and SHALL NOT send a byte outside the file. Several ranges that
  do not overlap MAY be answered as one `multipart/byteranges` 206. Browsers send neither, so their exact
  answer is the framework's, not a contract.
- `If-Range` SHALL be honored: the range is served only when its validator is the file's current `ETag` or
  `Last-Modified`, and the whole file with 200 otherwise.

**Headers of a 200 or 206.**
- `Content-Type` SHALL follow the file name's extension, case-insensitively, from a fixed table that has an entry
  for every video extension the engine's discovery lists: `video/mp4` for `.mp4` and `.m4v`, and
  `video/quicktime` for `.mov`. It SHALL never depend on the host's MIME database.
- `Last-Modified` SHALL carry the file's modification time.
- A strong `ETag` SHALL change whenever the file's size or modification time changes. For a symlinked file, the
  size and time are those of the file the link points to.
- `Cache-Control: private, no-cache` SHALL be sent, so a browser revalidates before it reuses stored bytes.
- `Content-Disposition: inline` SHALL carry the file's own name. A name that percent-encoding would change, such
  as one with a space, punctuation or a letter outside ASCII (`2024-07-14 - Kalas.mp4` included), is sent only in
  the RFC 5987 `filename*=utf-8''<percent-encoded>` form. Any other name is sent as `filename="<name>"`.

**Conditional requests.**
- A request whose `If-None-Match` matches the current entity-tag SHALL be answered 304 with the `ETag` and
  `Cache-Control` and no body, whether or not it also carries `Range`. The match uses weak comparison, across
  every `If-None-Match` header line and comma-separated entry, and `*` matches any existing file.
- A non-matching `If-None-Match` SHALL be answered as if the request carried no conditional header: 200 or
  206 as the `Range` header decides, and `If-Modified-Since` SHALL NOT then be evaluated.
- A request without `If-None-Match` whose `If-Modified-Since` is a valid HTTP-date at or after the file's
  modification time, truncated to whole seconds as `Last-Modified` carries it, SHALL be answered 304 with the
  `ETag` and `Cache-Control` and no body, whether or not it also carries `Range`. A date in the future is
  valid. A date before the file's modification time SHALL be answered as if it were absent.
- An `If-Modified-Since` that is not a valid HTTP-date, or that is sent on more than one header line, SHALL be
  ignored. `If-Modified-Since` SHALL be evaluated for `GET` and `HEAD` alike.
- `If-Range` SHALL still be checked only after these preconditions, on a request that was not answered 304.

**Version parameter.** Both endpoints SHALL accept an OPTIONAL query parameter `v`, an opaque string a client MAY
send to give a changed file a new URL. The service SHALL ignore its value: `v` SHALL NOT affect the lookup, the
headers or the status.

**Resources and failures.**
- The service SHALL read a file in bounded chunks while it sends it, and SHALL NOT hold a whole file in
  memory, so the memory a request uses does not grow with the file's size.
- A client that disconnects mid-file SHALL leave the service answering further requests.
- A file that the lookup found but that can no longer be found when it is opened SHALL be answered 404.
- A file that exists but cannot be read, for example for lack of permission, SHALL be answered 502 with a
  problem body naming the event and no failure kind. That answer SHALL come before any byte of the file is
  sent, never as a 200 that breaks off.
- A problem detail about a file that cannot be served (vanished or unreadable) SHALL name it by its
  event-relative identity or its file name, never by an absolute server path. An event folder that cannot be
  read is worded as the event detail words it.
- Every 404 and 502 is a problem body naming the event, and carries no `ETag` or `Cache-Control`.

**Scope.**
- Both endpoints SHALL answer while the database is unreachable, and SHALL declare no 503.
- They SHALL NOT run ffmpeg or ffprobe, write any file, or enqueue a job.
- Every request, each range request included, SHALL pass through the service's single authentication hook, as
  the thumbnail endpoint's requests do. A media element can then load these URLs with no custom header.
- Both endpoints SHALL publish in the service's OpenAPI schema, for `get` and for `head` alike:
  - the `v` query parameter, and `If-None-Match`, `If-Modified-Since`, `Range` and `If-Range` as optional
    header parameters
  - their 200 and 206 as `video/*` binary content, with the `ETag`, `Last-Modified`, `Cache-Control`,
    `Accept-Ranges` and `Content-Disposition` headers, and `Content-Range` on the 206
  - their 304 with `ETag` and `Cache-Control`
  - their 400 and their 416 with `Content-Range`
  - their 404 and 502 in the shared problem body shape, and no 503

#### Scenario: A browser fetches the tail of a clip whose index is at the end
- **WHEN** an event holds the Sony XAVC clip `sony-xavc-1080p25-pcm.mp4` (153 MB, `moov` after `mdat`) and its
  media is requested with `Range: bytes=152000000-`
- **THEN** the response is 206 with exactly the bytes from offset 152000000 to the end, `Content-Range: bytes
  152000000-<size - 1>/<size>`, `Content-Type: video/mp4` and `Accept-Ranges: bytes`

#### Scenario: The whole file, then a range of it
- **WHEN** the Grillning clip `s1710001.mp4` is requested without `Range`, and again with `Range: bytes=0-99`
- **THEN** the first response is 200 with the whole file and a `Content-Length` equal to its size, and the second
  is 206 with the file's first 100 bytes and `Content-Range: bytes 0-99/<size>`

#### Scenario: A range past the end
- **WHEN** a clip of size N is requested with `Range: bytes=<N>-`
- **THEN** the response is 416 with `Content-Range: bytes */<N>` and no file bytes

#### Scenario: An empty clip is served as it is
- **WHEN** the zero-byte clip `trasig.mp4` of `2024/2024-10-05 - Trasig` is requested without `Range`, and again
  with `Range: bytes=0-`
- **THEN** the first response is 200 with an empty body and the second is 416 with `Content-Range: bytes */0`,
  and nothing is probed

#### Scenario: A malformed range
- **WHEN** a clip is requested with `Range: lines=0-1`, again with `Range: bytes=abc`, and again with `Range:
  bytes=5-3`
- **THEN** each response is 400 with a plain-text body

#### Scenario: Ranges a browser does not send stay bounded
- **WHEN** a clip of size N is requested with `bytes=-<N + 5>`, `bytes=0-<N * 10>`, `bytes=-0`, `bytes=0-0,2-2` and
  `bytes=5-4`
- **THEN** the first two are 206 with the whole file, `bytes=-0` is 416, `bytes=0-0,2-2` is a 206
  `multipart/byteranges` body holding bytes 0 and 2, and no answer is a 5xx or carries a byte the range does
  not name

#### Scenario: If-Range keeps a resumed download consistent
- **WHEN** a clip is requested with `Range: bytes=0-99` and `If-Range` set to its current `ETag`, and again with
  `If-Range: "an-older-tag"`
- **THEN** the first response is 206 with 100 bytes and the second is 200 with the whole file

#### Scenario: Revalidation is a 304 without a body
- **WHEN** the movie of `2024/2024-07-14 - Kalas` is requested with `If-None-Match` set to the `ETag` of an
  earlier response, with the same tag prefixed `W/`, or with a list that contains it, each also carrying `Range:
  bytes=0-`
- **THEN** each response is 304 with that `ETag`, `Cache-Control: private, no-cache` and no body

#### Scenario: A HEAD is the GET without its body
- **WHEN** the clip `s1710001.mp4` is requested with `HEAD`, and again with `HEAD` and `Range: bytes=0-99`
- **THEN** the first response is 200 with a `Content-Length` equal to the file's size, `Content-Type: video/mp4`,
  `Accept-Ranges: bytes`, the `ETag`, `Last-Modified` and `Cache-Control` a `GET` gives, and no body
- **AND** the second is 206 with `Content-Range: bytes 0-99/<size>`, `Content-Length: 100` and no body

#### Scenario: A HEAD is answered with and without the built web client
- **WHEN** the movie of `2024/2024-07-14 - Kalas` is requested with `HEAD`, once by a service with no built
  web client and once by a service that serves a built `web/dist`
- **THEN** both responses are 200 with the movie's `Content-Length` and `ETag` and no body, never 405 or the
  static mount's 404

#### Scenario: A HEAD fails as a GET fails
- **WHEN** `HEAD` is sent for `borttagen.mp4` (MISSING) of `2024/2024-09-01 - Sommarlov`, for the movie of the
  never-rendered `2024/Blandat`, and for a listed clip whose permissions deny reading
- **THEN** the responses are 404, 404 and 502, the statuses a `GET` gives, with no body and no `ETag` or
  `Cache-Control`

#### Scenario: Revalidation by date is a 304 without a body
- **WHEN** the clip `s1710001.mp4` is requested with `If-Modified-Since` set to the `Last-Modified` of an earlier
  response, again with `If-Modified-Since: Wed, 01 Jan 2099 00:00:00 GMT`, and again as `HEAD` with the first
  date and `Range: bytes=0-`
- **THEN** each response is 304 with the file's `ETag`, `Cache-Control: private, no-cache` and no body

#### Scenario: A file modified since the stored date is sent again
- **WHEN** a clip last modified on `Sat, 15 Jun 2024 10:00:00 GMT` is requested with `If-Modified-Since: Fri, 14
  Jun 2024 10:00:00 GMT`
- **THEN** the response is 200 with the whole file

#### Scenario: If-None-Match decides alone when it is present
- **WHEN** a clip is requested with `If-None-Match: "an-older-tag"` and `If-Modified-Since: Wed, 01 Jan 2099
  00:00:00 GMT`, and again with its current `ETag` in `If-None-Match` and a date before its modification time
- **THEN** the first response is 200 with the whole file, and the second is 304

#### Scenario: A date that is not a date is ignored
- **WHEN** a clip is requested with `If-Modified-Since: yesterday`, and again with two `If-Modified-Since` lines,
  each a valid date after the file's modification time
- **THEN** both responses are 200 with the whole file

#### Scenario: A replaced file gets a new entity-tag
- **WHEN** a clip's file is replaced by another recording, changing its size and modification time, and it is
  requested with the old `ETag` in `If-None-Match`
- **THEN** the response is 200 with the new file's bytes and a different `ETag`

#### Scenario: Content type by extension, never the host's
- **WHEN** an event holds `hevc-mov-rotate90-aac.mov` and `CLIP.MP4`, and each is requested
- **THEN** the first is served as `video/quicktime` and the second as `video/mp4`, on any host

#### Scenario: The file's name travels with it
- **WHEN** the clip `Kväll, del 2/a+b & c #1.mp4` is requested
- **THEN** the response carries `Content-Disposition: inline` with `filename*=utf-8''a%2Bb%20%26%20c%20%231.mp4`

#### Scenario: A large file is streamed, not loaded
- **WHEN** the 449 MB clip `h264-4k50-aac-119mbps.mp4` is downloaded whole from a running service
- **THEN** every byte arrives, and the service's resident memory grows by far less than the file's size

#### Scenario: An unreadable file is a problem, not a broken 200
- **WHEN** a listed clip's file exists but its permissions deny reading, and it is requested
- **THEN** the response is 502 with a problem body naming the event and the clip's identity and the operating
  system's reason, with no failure kind and no absolute server path, and no status line of 200 or 206 is sent

#### Scenario: The version parameter changes nothing
- **WHEN** the same clip is requested with `v=2024-06-27T14:03:11.123456Z`, again with `v=other`, and again without `v`
- **THEN** all three responses are 200 with identical bodies and the same `ETag`

#### Scenario: No database needed
- **WHEN** the database is unreachable and a clip of `2024/2024-06-27 - Grillning med grannar` and the movie of
  `2024/2024-07-14 - Kalas` are requested
- **THEN** both are answered 200, never 503

#### Scenario: Every range request passes the authentication hook
- **WHEN** an authentication check is registered at the hook point, and a clip is requested once without `Range`
  and twice with different ranges
- **THEN** the check runs for each of the three requests, and a request it rejects is answered by the check and
  receives no file bytes

#### Scenario: The schema publishes the media responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the `get` and the `head` operation of both media paths declare the optional `v` query parameter and the
  optional `If-None-Match`, `If-Modified-Since`, `Range` and `If-Range` header parameters, and publish:
  - 200 and 206 as `video/*` binary content, with `Content-Range` on the 206
  - 304
  - 400 and 416
  - 404 and 502 in the shared problem body shape
  - no 503

### Requirement: Clip media endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/media?clip=<identity>`, which serves one clip's file
under the shared media behavior. `event_id` is the event identity the events routes use. `clip` is a required
query parameter carrying the clip's identity exactly as the event detail lists it: its event-relative path,
chapter folder included, percent-encoded as a query value. The identity SHALL be matched exactly, with no path
or Unicode normalization.

**Which clips are served.** A clip SHALL be served when its identity is one of the clips the engine's discovery
finds on disk for an event the events list shows. That is every clip the event detail lists that is not
MISSING, IGNORED clips included: the same set the thumbnail endpoint serves. The endpoint SHALL answer the
following with 404 and a problem body naming the event, without opening any file outside the event:
- an unknown event, or a folder the events list does not show as an event, such as a year folder, an
  event's `original/` folder or a `.reelignore`d event
- a clip the event's document references but disk does not have (MISSING)
- a file discovery skips, such as one under `original/`
- any identity that is not a discovered clip of that event, including one that points outside the event

**Failures.**
- An event folder that cannot be listed SHALL be answered 502 with the unreadable-disk failure kind the
  events reads use.
- An ingest layout that cannot be resolved SHALL be answered 502 with no kind.
- The event's `reel.yaml` SHALL NOT be read, so a broken `reel.yaml` does not stop a clip from being served.

#### Scenario: A clip in a chapter folder
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for `clip=Kv%C3%A4llen%2Fs1710002.mp4`
- **THEN** the response is 200 with the bytes of that clip in the `Kvällen` chapter folder

#### Scenario: An identity with spaces, punctuation and Swedish letters
- **WHEN** an event holds the chapter folder `Kväll, del 2` with the clip `a+b & c #1.mp4`, and its media is
  requested with `clip=Kv%C3%A4ll%2C%20del%202%2Fa%2Bb%20%26%20c%20%231.mp4`
- **THEN** the response is 200 with that clip's bytes
- **AND** the same identity sent with a literal `+` is looked up as `a b & c #1.mp4` and answers 404

#### Scenario: An IGNORED clip is still served
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for its root clip `s1710004.mp4`, which its
  `reel.yaml` lists under `ignore`
- **THEN** the response is 200

#### Scenario: A symlinked clip serves the file it points to
- **WHEN** a clip of the event is a symbolic link to a sample file outside the library
- **THEN** the response is 200 with the target file's bytes, and its `ETag` and `Last-Modified` follow the target
  file's size and modification time

#### Scenario: A MISSING clip is not served
- **WHEN** the event `2024/2024-09-01 - Sommarlov` is asked for `borttagen.mp4`, which its `reel.yaml` references
  but disk does not have
- **THEN** the response is 404 with a problem body naming the event

#### Scenario: An identity outside the event is not a clip of the event
- **WHEN** the event `2024/2024-09-01 - Sommarlov` is asked for
  `clip=../2024-06-27 - Grillning med grannar/s1710001.mp4`, or for `clip=Kvällen/../s1710001.mp4` on
  `2024/2024-08-20 - Två kapitel - Tjörn`
- **THEN** each response is 404, and no file outside the asked event's discovered clips is opened

#### Scenario: A folder that is not an event
- **WHEN** the endpoint names the year folder `2024` with `clip=2024-06-27 - Grillning med grannar/s1710001.mp4`,
  or the folder `2024/2024-06-27 - Grillning med grannar/original` with a file in it
- **THEN** each response is 404 with a problem body naming the requested id

#### Scenario: A clip that vanishes after the listing
- **WHEN** a listed clip is deleted between the event's listing and the moment its file is opened
- **THEN** the response is 404, never a 500

#### Scenario: A missing clip parameter
- **WHEN** the endpoint is requested without `clip`
- **THEN** the response is the service's 422 validation error

#### Scenario: A broken reel.yaml does not stop a clip
- **WHEN** an event's `reel.yaml` cannot be parsed and one of its clips on disk is requested
- **THEN** the response is 200 with that clip's bytes

### Requirement: Rendered movie endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/movie`, which serves the event's rendered movie under
the shared media behavior. The rendered movie SHALL be the file the staleness gate counts as the event's movie,
and nothing else:
- the event SHALL have a readable render record (manifest); without one, it has no rendered movie
- when the event's expected output path, as its current title, date and location name it in the service's
  output directory, holds a file, the movie SHALL be that file
- otherwise, when the render record names a different, bare file name whose file exists where the output
  naming rule puts that name (the `output_renamed` case), the movie SHALL be that file
- the movie's path, with its `.` and `..` segments removed without touching the filesystem, SHALL lie inside
  the service's output directory. A title or render record that names `..` therefore never reaches a file
  outside it. Symbolic links inside the output directory are followed, as the gate follows them.

An event therefore has a rendered movie exactly when its staleness verdict cites neither `no_manifest` nor
`output`. There are three exceptions:
- a file removed between the two reads
- a directory, not a file, at the expected path, which the gate counts as present
- an expected path whose name climbs out of the output directory
A client SHALL be able to decide from the event detail alone whether to offer a player.

**Failures, by cause.** Each SHALL be a problem body naming the event:
- **404:**
  - an unknown event, or a folder the events list does not show as an event
  - an event with no render record
  - an event whose recorded movie is not on disk, whether under the expected or the recorded name
  - a render record whose recorded name is not a bare file name
  - a file at the expected path that this event has no render record for, such as one that another event of a
    case-only output collision rendered
  - something other than a regular file, such as a directory, at the expected path, with no movie under the
    recorded name: it is answered as absent and never served
- **502 with the events failure kind the event detail reports:** the event's `reel.yaml` cannot be parsed
  (`unparseable_reel_yaml`), the event has no real date or title (`unusable_metadata`), or its folder cannot be
  read (`unreadable_disk`).
- **502 with no kind:** an ingest layout that cannot be resolved.

#### Scenario: A fresh event's movie
- **WHEN** the movie of `2024/2024-07-14 - Kalas` is requested, an event rendered with no edit since
- **THEN** the response is 200 `video/mp4` with the bytes of `2024/2024-07-14 - Kalas.mp4` in the output
  directory, `Content-Disposition: inline` naming that file, and `Cache-Control: private, no-cache`

#### Scenario: A stale event still has its movie
- **WHEN** the movie of `2024/2024-08-02 - Badutflykt - Varberg` is requested, whose staleness cites `clip_set`
  because a NEW clip appeared after its render
- **THEN** the response is 200 with the movie of that last render

#### Scenario: A renamed event serves the movie under its old name
- **WHEN** `2024/2024-06-27 - Grillning med grannar` was rendered and its title was then changed in `reel.yaml`, so
  its staleness cites `editorial` and `output_renamed`, and its movie is requested
- **THEN** the response is 200 with the movie the last render wrote under the old name, and that name in
  `Content-Disposition`

#### Scenario: An event that was never rendered
- **WHEN** the movie of `2024/2024-09-01 - Sommarlov` or `2024/Blandat` is requested, events with no render record
- **THEN** the response is 404 with a problem body naming the event

#### Scenario: A failed render leaves no movie
- **WHEN** the movie of `2024/2024-10-05 - Trasig` is requested, whose only render failed
- **THEN** the response is 404

#### Scenario: Another event's movie at the same path is not this event's
- **WHEN** `2024/2024-07-14 - kalas`, which has no render record, names the same output file as the rendered
  `2024/2024-07-14 - Kalas`, and its movie is requested
- **THEN** the response is 404, although a file exists at its expected path

#### Scenario: A recorded movie that was deleted
- **WHEN** an event has a render record and neither the expected nor the recorded movie file exists any longer
- **THEN** the response is 404, and the event's staleness cites `output`

#### Scenario: A directory where the movie belongs is answered as absent
- **WHEN** `2024/2024-07-14 - Kalas` has a render record, and its expected movie path in the output directory is a
  directory rather than a file, and its movie is requested
- **THEN** the response is 404 with a problem body naming the event, and nothing under that directory is opened

#### Scenario: A render record cannot point outside the output directory
- **WHEN** an event's render record names `../elsewhere.mp4`, an absolute path or an empty name, and its expected
  movie is absent
- **THEN** the response is 404, and no file outside the output directory is opened

#### Scenario: A title cannot climb out of the output directory
- **WHEN** an event with a render record has the title `x/../../../outside` in its `reel.yaml`, and the folders
  exist so that its expected path resolves to an existing `outside.mp4` beside the output directory
- **THEN** the response is 404, and that file is not opened

#### Scenario: A symlinked folder in the output directory is followed
- **WHEN** the output directory's `2024` folder is a symbolic link to a folder on another disk that holds
  `2024-07-14 - Kalas.mp4`, and the movie of `2024/2024-07-14 - Kalas` is requested
- **THEN** the response is 200 with that file's bytes, as the event's staleness counts the movie as present

#### Scenario: An event the detail cannot read
- **WHEN** the movie of `2024/2024-02-30 - Omöjligt datum` is requested, whose folder date is not a real date
- **THEN** the response is 502 with the failure kind `unusable_metadata` and the detail the event detail gives

#### Scenario: An unparseable reel.yaml
- **WHEN** an event's `reel.yaml` cannot be parsed and its movie is requested
- **THEN** the response is 502 with the failure kind `unparseable_reel_yaml`

#### Scenario: Whether a movie exists matches the staleness verdict
- **WHEN** for each event the dev library's events list shows as an event (not as an error row), the event's
  staleness verdict and its movie are read
- **THEN** the movie answers 200 exactly for the events whose staleness cites neither `no_manifest` nor `output`,
  and 404 for the others

### Requirement: Jobs routes fail loud when the job store is unreachable
When the job store cannot be reached, each of `POST /api/v1/jobs`, `GET /api/v1/jobs`,
`GET /api/v1/jobs/{id}` and `POST /api/v1/jobs/{id}/cancel` SHALL respond 503 with the shared problem body,
identifying the database as the failing dependency in its `check` field exactly as the events reads and the
health endpoint do, so a client has one predicate for "the service cannot reach its database" across all of
them. The response SHALL carry a `detail` naming the job store as unreachable. The service MUST NOT answer
such a request with an unshaped error body, and MUST NOT soften it: no job list with the unreadable jobs
omitted, no job reported as absent (404) because it could not be read, no cancel outcome that was not
applied, and no 201 for a job whose creation was not confirmed.

Only a request that needs the job store is answered 503. An enqueue SHALL still answer from the disk checks
that come before its first store call as it does with the database up: 404 for an unknown event, the
scan-failure 502 for a failed walk of the project, and the `output_collision` 409.

An enqueue whose creation of the job was not confirmed (the store failed during the insertion) is answered
503; repeating it SHALL give the answer the store would give any repeated enqueue: the existing job's 409
`active_job` when that insertion had been applied, a new 201 otherwise.

The service's OpenAPI schema SHALL publish this response: each of the four operations declares its 503
described by the shared problem body shape, which includes the `check` field. A client SHALL derive the type
of that body from the generated types.

#### Scenario: The database is down on the jobs list
- **WHEN** the database is unreachable and a client requests `GET /api/v1/jobs`
- **THEN** the response is 503 with the shared problem body whose `check` is `database`, not a bare 500 and
  not an empty list

#### Scenario: The database is down on a job's detail
- **WHEN** the database is unreachable and a client requests `GET /api/v1/jobs/{id}` for a well-formed id
- **THEN** the response is 503 with `check` `database`, not the 404 an unknown id gets

#### Scenario: The database is down on cancel
- **WHEN** the database is unreachable and a client sends `POST /api/v1/jobs/{id}/cancel`
- **THEN** the response is 503 with `check` `database`, and no outcome is reported

#### Scenario: The database is down on an enqueue
- **WHEN** the database is unreachable and `POST /api/v1/jobs` names `2024/2024-06-27 - Grillning med
  grannar`, which exists on disk and claims a distinct output path
- **THEN** the response is 503 with `check` `database`, and no 201 or fresh result is returned

#### Scenario: An enqueue's disk checks still answer first
- **WHEN** the database is unreachable and `POST /api/v1/jobs` names `2024/2024-12-24 - Finns inte`, which is
  not a directory under the project root
- **THEN** the response is the 404 problem body naming the event in `event_id`, as with the database up

#### Scenario: The 503 matches the events reads
- **WHEN** the database is unreachable and a client requests `GET /api/v1/events` and `GET /api/v1/jobs`
- **THEN** both responses are 503 with the same `title`, the same `status` and `check` `database`

#### Scenario: A returned problem body matches the published shape
- **WHEN** the database is unreachable and a client sends each of the four jobs requests
- **THEN** each 503 body validates against the published problem shape, including the field naming the
  database as the failing dependency

#### Scenario: The schema publishes the 503
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the enqueue, the jobs list, the job detail and cancel each declare a 503 response described by the
  shared problem body shape
