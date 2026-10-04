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

Each clip in the detail response SHALL also carry a **duration** in seconds, which is a media fact and the first
exception to "file facts only" (the second is each clip's proxy state, defined in its own requirement). It SHALL be the duration the engine's thumbnail operation already measured for
that exact file, read from the sidecar the thumbnail cache keeps beside the clip's cached thumbnail (the
clip-thumbnails capability), and SHALL never be obtained by decoding or probing a clip: reading the detail
response MUST NOT run `ffprobe` or `ffmpeg`, and MUST NOT write, create or refresh any cache entry. It SHALL be
`null`, meaning unknown, for a clip the document references but disk does not have, for a clip whose
thumbnail has not been made since its size or modification time last changed (the cache key covers both), and
for a clip whose sidecar cannot be read or does not hold a finite number above zero, and for every clip when
the project's `thumbnails` configuration cannot be resolved (the thumbnail endpoint reports that error itself).
A cache entry or configuration that cannot be used SHALL NOT fail the response and SHALL NOT be reported as a
zero or any other substitute; the clip's other facts are unaffected. The duration is the probe's number, so it can differ from the length a browser
reads from the same file by a few tens of milliseconds. The response schema SHALL publish the field as nullable
and optional, so a client built from it treats `null` and an absent field alike as "not known".

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

#### Scenario: A clip with a cached thumbnail reports its duration
- **WHEN** the thumbnail of `P1000123.MP4` (6.02 s long) was made earlier, and `GET /api/v1/events/{event_id}`
  is served
- **THEN** that clip carries a duration of `6.02`, taken from the thumbnail cache's sidecar, and neither
  `ffprobe` nor `ffmpeg` ran

#### Scenario: A clip whose thumbnail was never made reports a null duration
- **WHEN** the detail is read for an event whose clips have no cached thumbnail
- **THEN** each clip carries a duration of `null`, along with its size and modification time, and nothing was
  written into the thumbnail cache

#### Scenario: A replaced file does not keep the old file's duration
- **WHEN** the thumbnail of `P1000123.MP4` was made, then the file was replaced by another of the same name with
  a different size or modification time
- **THEN** the detail reports a duration of `null` for it until a thumbnail of the new file is made

#### Scenario: An unusable sidecar is unknown, not an error
- **WHEN** a clip's duration sidecar is present but holds invalid JSON, a duration of `0`, a negative number or a
  non-number
- **THEN** the detail response is still a success, that clip's duration is `null`, and every other clip keeps
  its own

#### Scenario: An unusable thumbnails configuration leaves durations unknown
- **WHEN** the project's `config.yaml` sets `thumbnails.position` to `2`, which the thumbnail endpoint refuses,
  and the event detail is read
- **THEN** the detail is still a success, every clip's duration is `null`, and the clips' other facts and the
  rest of the response are unchanged

#### Scenario: A missing clip has no duration
- **WHEN** the document references a clip whose file has been deleted or renamed
- **THEN** that clip is reported MISSING with a duration of `null`, alongside its null size and modification
  time

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
for the event (metadata, ordered chapters and their clips, per-clip properties, each chapter's optional title-card overrides, `ignore`, and the `look`
override) and delegating to the engine's editorial-write operation. The endpoint MUST contain no editorial
logic of its own: it parses and validates the request shape, calls the operation, and maps outcomes to
responses. The response SHALL echo the persisted document together with the event's resulting staleness
verdict, so a client needs no follow-up read. Read endpoints remain read-only and unaffected.

The request body is the event's **complete** editorial state (D-E2), not a patch. A section the body omits
SHALL be treated as empty, so omitting `ignore`, chapters, clip properties or `look` clears them; the one
exception is a chapter's `card`, which when absent or `null` keeps the card `reel.yaml` already holds (see
the chapter title-card requirement). A client
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
yield 404 with a problem body. A `reel.yaml` that cannot be read or parsed, and an event folder that cannot be
searched so that the existence of its `reel.yaml` cannot be established, SHALL fail loud with the
scan-failure problem body. That body names the event and carries the same failure kind the events reads
would report (`unparseable_reel_yaml`, or `unreadable_disk` for a permission failure), rather than an empty
or partial document. Only a `reel.yaml` that is absent reads as the empty document. The endpoint SHALL be read-only: it MUST NOT create
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

#### Scenario: An unsearchable event folder is loud, not empty
- **WHEN** the event folder `2024/2024-06-21 - A`, which holds a `reel.yaml` with the title `Real`, has mode
  `0600`, so that the file inside it cannot be looked up
- **THEN** the response is the scan-failure 502 naming the event, with the unreadable-disk failure kind, not
  200 with the empty editorial document, and the folder and the file are unchanged

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

A verdict SHALL name the movie files behind `output_renamed`. Wherever a verdict appears in a response (the three
responses above), it SHALL carry two more keys, `renamed_from` and `output_name`, always present, each a string or
`null`:
- `renamed_from` SHALL be the bare file name of the movie the last render wrote, the one still on disk under the old
  name. `output_name` SHALL be the bare file name the next render will write, the name the event's date, title and
  location give it now. Neither SHALL contain a directory.
- Both SHALL be non-null exactly when `reasons` contains `output_renamed`, and both `null` otherwise. The service
  MUST NOT fill them from the current time, from the folder name, or from anything but the gate's own finding, and
  MUST NOT name a file that is not on disk as `renamed_from`.
- The same event SHALL carry the same two values on the list, the detail and an editorial write's echo, and the same
  names the CLI's `scan` prints for it.

The service's OpenAPI schema SHALL publish both keys as optional, nullable strings on the verdict, so that a
generated client types them as `string | null`. The verdict's existing keys, `stale` and `reasons`, keep their names,
types and values.

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
  report its staleness as `{"stale": true, "reasons": ["editorial", "output_renamed"], "renamed_from":
  "2024-06-27 - Grillning med Grannar.mp4", "output_name": "2024-06-27 - Grillkväll med grannarna.mp4"}`

#### Scenario: A save that renames the movie echoes the new reason
- **WHEN** a `PUT /api/v1/events/{event_id}/reel` with a matching `If-Match` changes the location of the fresh
  `2024/2024-06-21 - Midsommar - Dalarna` from `Dalarna` to `Leksand`
- **THEN** the 200 response's verdict is `{"stale": true, "reasons": ["editorial", "output_renamed"],
  "renamed_from": "2024-06-21 - Midsommar - Dalarna.mp4", "output_name": "2024-06-21 - Midsommar - Leksand.mp4"}`
- **AND** no job is enqueued, and `2024/2024-06-21 - Midsommar - Dalarna.mp4` in the output directory is unchanged

#### Scenario: A deleted movie still reads as missing
- **WHEN** the fresh `2024/2024-07-14 - Kalas` has its movie deleted from the output directory, with no edit
- **THEN** the list and the detail report its staleness as `{"stale": true, "reasons": ["output"],
  "renamed_from": null, "output_name": null}`, with both keys present

#### Scenario: A verdict without the reason names no file
- **WHEN** the fresh `2024/2024-07-04 - Barbecue` is read, and `2024/2024-07-14 - Kalas` has its clips changed
- **THEN** their staleness are `{"stale": false, "reasons": [], "renamed_from": null, "output_name": null}` and
  `{"stale": true, "reasons": ["clip_set"], "renamed_from": null, "output_name": null}`

#### Scenario: A renamed event with its old movie gone names no old file
- **WHEN** the title of `2024-06-27 - Grillning med grannar` was changed after its last render, and its movie under the
  old name was then deleted from the output directory
- **THEN** its staleness cites `output`, not `output_renamed`, and both `renamed_from` and `output_name` are `null`

#### Scenario: The schema publishes the two names
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the staleness verdict has `renamed_from` and `output_name`, each a nullable string and neither required,
  and `stale` and `reasons` are unchanged

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

### Requirement: Enqueue refuses an event whose output path another event claims
`POST /api/v1/jobs` SHALL apply the output-collision rule the batch commands apply (D-9). The event it names
SHALL be refused when its output path is also the output path of another event of the served project. Paths
SHALL be compared exactly as the batch commands compare them: case-insensitively and after Unicode
normalization. The claimants SHALL be every event the configured layout walks from the served root, the
same events the events list shows; the named event is one of them, because the route only accepts a listed
id and has already found it processable ("Enqueue names an event the events list shows and refuses one it
cannot process"). There is no selection: the check covers the whole project, as `auto-reel enqueue <root>`
does without `--years`. An event whose `reel.yaml` cannot be read, whose files cannot be listed, or whose
resolved metadata lacks a real date or a title (or carries a future date) SHALL claim no path. Such an
event fails on its own, as the events list's error row already reports. The service SHALL choose claimants by
the one rule the batch commands state ("headless-cli"), so that an event which cannot be read or listed
claims no path and is never the reason the check fails; the failure of a claimant other than the named
event SHALL NOT fail the check.

The check SHALL run after the named event is found processable, before the active-job check and before
the staleness gate. An event that collides and also has an active job SHALL therefore be answered as a
collision. `force` SHALL NOT override the check,
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
- `missing_clips`: the event plays a clip that is missing from disk (see "Enqueue refuses an event that
  plays a clip missing from disk"). The body carries the clips' identities in `missing`.

A client can therefore choose its reaction from the published type alone, never from the detail text.

When the project walk itself fails, the collision cannot be checked. The endpoint SHALL then answer with the
scan-failure 502 that the events list uses, and SHALL NOT enqueue. The schema SHALL publish that 502, and the
`conflict`, `claimed_by` and `missing` fields of the shared problem body.

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

#### Scenario: A sibling that cannot be listed claims no path
- **WHEN** `2024/2024-07-14 - kalas`, which would collide with `2024/2024-07-14 - Kalas`, has mode `0000`,
  and `POST /api/v1/jobs` names `2024/2024-07-14 - Kalas`
- **THEN** the sibling claims no path, the check does not fail because of it, and the response is not an
  unshaped server error

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
- **THEN** the shared problem body's `conflict` field is the enumeration of exactly `active_job`,
  `output_collision` and `missing_clips`, and `claimed_by` and `missing` are lists of strings
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

### Requirement: An event's latest job reports its cancel request and requeue count

Wherever an events response carries an event's latest job (each summary row of `GET /api/v1/events`, and
`GET /api/v1/events/{event_id}`), that job SHALL also carry `cancel_requested` and `requeue_count`. Both SHALL
have the same value and meaning as the same-named fields of the job's own detail (`GET /api/v1/jobs/{id}`) at the
same moment:

- `cancel_requested` SHALL be true once a cancel was requested for the job, including a request made while the job
  was running and a request that a requeue left in place, and false otherwise.
- `requeue_count` SHALL be the number of times the job was returned to `queued` after a claim (a stopped or
  crashed worker), and 0 for a job never requeued.

Both keys SHALL always be present and non-null: a boolean and an integer. The service MUST NOT derive either from
`status`, `started_at` or any other field. The list and the detail SHALL report the same values for the same event
when no job changed between the two requests.

The service's OpenAPI schema SHALL publish both fields on the latest-job model exactly as it publishes them on the
job detail, as **required** fields, so that a generated client types them as `boolean` and `number`. The fields
the latest job already had keep their names, types, required status and values.

#### Scenario: A job that was requeued says so, on both reads
- **WHEN** a worker claimed the job for `2024/2024-07-04 - Barbecue`, a stopped worker then requeued it with
  `JobStore.requeue`, and the event is read through `GET /api/v1/events` and `GET /api/v1/events/{event_id}`
- **THEN** both reads' `latest_job` has status `queued`, `started_at: null`, `requeue_count: 1` and
  `cancel_requested: false`, each equal to `GET /api/v1/jobs/{id}`'s

#### Scenario: A cancel requested while running is visible in the latest job
- **WHEN** a worker has claimed a render of `2024-06-27 - Grillning med grannar`, and
  `POST /api/v1/jobs/{id}/cancel` answers that the cancel was requested
- **THEN** the event's `latest_job` has status `running`, `cancel_requested: true` and `requeue_count: 0`, equal to the
  job detail's

#### Scenario: A job never requeued or cancelled reports the defaults
- **WHEN** `2024/Blandat`'s only job is `queued`
- **THEN** its `latest_job` has `cancel_requested: false` and `requeue_count: 0`, with both keys present

#### Scenario: The schema requires both fields
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the latest-job model's `cancel_requested` and `requeue_count` equal the job detail's definitions of the same
  names, and both are in its `required` list

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
- A clip whose failure the engine recorded less than 60 seconds ago, and whose thumbnail is not cached,
  SHALL be answered with that failure without ffprobe or ffmpeg and without waiting for a slot. The 60
  seconds SHALL run from the failed attempt: a request that reads the recorded failure does not renew it.
- The endpoint SHALL NOT block the service's event loop on disk or ffmpeg work, so other endpoints keep
  answering while thumbnails are extracted.
- A requester that disconnects SHALL NOT abort an extraction that other requests share.

**Failures, by cause.** Each SHALL be a problem body naming the event:
- **502 with the thumbnail failure kind:** the engine cannot produce a thumbnail. For example, the clip is
  empty or undecodable, it has no frame at the configured position, or it can no longer be statted
  because it changed after the event was listed, or its failure was recorded less than 60 seconds ago. The
  detail SHALL name the clip by its requested identity and give the engine's reason cut to one line,
  without server paths, commands or tool output. A recorded failure SHALL answer exactly as the failed
  attempt did. No placeholder image is returned.
- **502 with the unreadable-disk failure kind the events reads use:** the event's folder cannot be listed.
- **502 whose detail names the problem, with no failure kind:** the thumbnail cache cannot be read or
  written, or the project `config.yaml` cannot be loaded or holds an invalid thumbnail setting.

A clip's failed extraction SHALL be remembered for 60 seconds, by the engine's failure marker, so the
next requests in that window for the same clip get the same 502 without a new attempt. After that window
the next request tries again. A cache or `config.yaml` fault, and a listing failure, SHALL NOT be
remembered: the next request for the same clip tries again. Problem responses SHALL carry no caching
headers.

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
  reporting that the file is empty. No image is produced. A second request within 60 seconds answers the
  same 502 without starting ffprobe or ffmpeg, and one after that window tries again.

#### Scenario: A corrupt clip's detail is one line without server paths
- **WHEN** an event holds a clip of fixed bytes that are no media container at all (for example a line of
  plain text repeated), or an mp4 whose media data is cut short behind an intact index, and each is requested
- **THEN** each response is 502 with the thumbnail failure kind, and its detail is the clip's identity
  followed by a one-line cause: no newline, no ffmpeg or ffprobe command, and no path of the server
- **AND** the cause for the non-media bytes says the probe could not read the file, every time the same
  bytes are requested, and the cause for the cut-short mp4 says no frame was extracted
- **AND** the service's log keeps the full reason, with the failing command and its output

#### Scenario: A cache that cannot be written is the service's fault, not the clip's
- **WHEN** the configured thumbnail cache directory is read-only and an uncached clip is requested
- **THEN** the response is 502 whose detail names the operating-system error, with no thumbnail failure
  kind
- **AND** the same request made again tries again, because a cache fault is not remembered

#### Scenario: A recorded failure is answered without extraction or a slot
- **WHEN** `trasig.mp4` in `2024/2024-10-05 - Trasig` has failed, two other extractions hold both slots, and
  the clip is requested again 5 s later
- **THEN** the response is 502 with the thumbnail failure kind and the same detail as the first, without
  waiting for either extraction, and no ffmpeg or ffprobe process is started for it

#### Scenario: A recorded failure expires
- **WHEN** `trasig.mp4` failed 61 s ago, and the clip is requested
- **THEN** the probe runs again and the response is whatever that attempt gives

#### Scenario: A cached thumbnail wins over a recorded failure
- **WHEN** a clip has both `<key>.jpg` and a recorded failure of the same key
- **THEN** the response is 200 `image/jpeg`

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
`output`. There are two exceptions:
- a file removed between the two reads
- an expected path whose name climbs out of the output directory

A client SHALL be able to decide from the event detail alone whether to offer a player: the staleness verdict
decides it. The detail's `movie` carries the movie's version and chapter times (requirement "The event detail
reports the rendered movie's version and chapter times"); it is also `null` where this route answers 200: a render
record whose `written_at` is not a timezone-aware date-time has a movie this route
serves but no version to report. A client MUST NOT withhold a player because `movie` is `null`.

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
- **AND** the event's staleness cites `output`, as it does for an absent file

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

### Requirement: Enqueue names an event the events list shows and refuses one it cannot process
`POST /api/v1/jobs` SHALL enqueue only an event whose id is exactly an id that `GET /api/v1/events` lists
for the served project, spelled as the list spells it. The configured layout decides what an event is, as it
does for the list and for the media routes. Every other id SHALL be answered with the 404 problem body of an
unknown event, naming the id in `event_id`, and nothing SHALL be written. That covers:

- an alternative spelling of a listed event: a `./` segment, a trailing `/`, a `..` segment, a different
  letter case or Unicode normalization form
- a directory the list does not show: the project root, a year folder, an event's `original/` or a chapter
  folder, an event with a `.reelignore` marker, a folder outside the configured `input`
- an id that names no directory

The job's `event_dir` is therefore the one canonical id of an event, so the one-active-job rule, the
events reads' latest job and a client that matches jobs to events by equality all agree on it, and an event
cannot be rendered by two jobs at once through two spellings. A year folder that can be searched but not listed while the
id is looked up SHALL be the scan-failure 502 problem body of the events list (`event scan failed`), and
nothing SHALL be enqueued.

Once the id is found, the service SHALL load the event's document and require it processable, as the batch
commands do, before it checks anything else about the event. An event it cannot process SHALL be answered
with the scan-failure **502** problem body of the events reads: it names the event in `event_id` and carries
the `failure` kind the events list gives that event, and a `detail` that is the engine's own message, which
names the fix. The kinds are:

- `unparseable_reel_yaml`: a `reel.yaml` that cannot be parsed or fails validation
- `unusable_metadata`: resolved metadata without a real date or without a title, or with a date in the
  future
- `unreadable_disk`: a `reel.yaml` or event folder that cannot be read or listed

Such a request SHALL NOT be answered with an unshaped server error, with 201, with 200 "fresh" or with 409,
and SHALL write nothing: no job row and no render manifest. The processable check SHALL run after the
lookup and before the output-collision check, the active-job check and the staleness gate, because an event
that cannot be processed claims no path and could not be rendered. The route SHALL declare its 404 and 502
responses in the shared problem body shape in the service's OpenAPI schema.

#### Scenario: A listed event enqueues under its id
- **WHEN** `POST /api/v1/jobs` names `2024/2024-06-21 - A`, which `GET /api/v1/events` lists
- **THEN** the response is 201 and the job's `event_dir` is `2024/2024-06-21 - A`

#### Scenario: Alternative spellings of a listed event are unknown
- **WHEN** `POST /api/v1/jobs` names `2024/./2024-06-21 - A`, `2024/2024-06-21 - A/` or
  `2024/2024-06-21 - A/../2024-06-21 - A`, each of which resolves to the listed folder `2024/2024-06-21 - A`
- **THEN** each response is 404 with the problem body of an unknown event, whose `event_id` is the id as
  sent, and no job row exists

#### Scenario: A directory that is not an event is unknown
- **WHEN** `POST /api/v1/jobs` names the year folder `2024`, the folder `2024/2024-06-21 - A/original`, or
  the project root
- **THEN** each response is 404 and no job row exists

#### Scenario: A folder outside the configured input is unknown
- **WHEN** `config.yaml` sets `input: input`, the folder `2024/2024-07-14 - Kalas` exists beside `input/`
  rather than in it, and `POST /api/v1/jobs` names it
- **THEN** the response is 404, and no job row exists

#### Scenario: An event with a .reelignore marker is unknown
- **WHEN** `2024/2024-06-22 - B` carries a `.reelignore` file and `POST /api/v1/jobs` names it
- **THEN** the response is 404 and no job row exists

#### Scenario: A symbolic link to an event, inside the project, is not an event of its own
- **WHEN** `2024/2024-07-20 - Fest` is a symbolic link to the rendered, fresh `2024/2024-07-14 - Kalas`, the
  list shows `Kalas` only (the layout walks a folder once), and `POST /api/v1/jobs` names
  `2024/2024-07-20 - Fest`
- **THEN** the response is 404 with the problem body of an unknown event, whose `event_id` is the id as sent,
  and no job row exists; naming `2024/2024-07-14 - Kalas` is judged at its own output as before

#### Scenario: An unparseable reel.yaml is a 502, not a 500
- **WHEN** `2024/2024-06-22 - B` has a `reel.yaml` that reads `metadata: [unclosed`, and
  `POST /api/v1/jobs` names it
- **THEN** the response is 502 whose `event_id` is that id and whose `failure` is `unparseable_reel_yaml`,
  with the same `detail` as `GET /api/v1/events/{event_id}` gives, and no job row exists

#### Scenario: An event without a date is refused up front
- **WHEN** `POST /api/v1/jobs` names `2024/NoDate`, whose folder name has no date and which has no
  `reel.yaml`
- **THEN** the response is 502 whose `failure` is `unusable_metadata` and whose `detail` is the events
  list's error row's, and no job row exists

#### Scenario: An event with a future date is refused up front
- **WHEN** `2024/2024-06-21 - A` has a `reel.yaml` setting `metadata.date` to a date after today, and
  `POST /api/v1/jobs` names it
- **THEN** the response is 502 whose `failure` is `unusable_metadata`

#### Scenario: An event folder that cannot be searched is refused up front
- **WHEN** the folder `2024/2024-06-21 - A` has mode `0600`, and `POST /api/v1/jobs` names it
- **THEN** the response is 502 whose `failure` is `unreadable_disk`, and no job row exists

#### Scenario: A failing event outranks an active job
- **WHEN** `2024/2024-06-21 - A` has a `queued` job, then its `reel.yaml` is changed so that it cannot be
  parsed, and `POST /api/v1/jobs` names it
- **THEN** the response is 502 with `unparseable_reel_yaml`, not 409 `active_job`, and the queued job is
  unchanged

### Requirement: The event reads report excluded clips and the missing clips that block a render

`reel.yaml` can exclude a clip it lists (`clips.<identity>.exclude: true`): the clip stays in the document and
on disk, and a render drops it from the movie without probing it. The events reads SHALL carry that fact, and
the consequence for missing clips, so a client does not have to guess which of them matter.

**Detail.** Each clip in `GET /api/v1/events/{event_id}` SHALL carry `excluded`, a boolean that is true when
the document's `clips` map marks that identity `exclude: true`. It is false for every other clip, including a
NEW or an IGNORED clip (the document cannot hold properties for a clip no chapter lists) and every clip of an
event without a `reel.yaml`. `excluded` is a flag beside the clip's status, not a member of it: the closed
status vocabulary is unchanged, and an excluded clip reports its own status, so an excluded clip whose file is
gone reports `missing` and `excluded: true`.

The detail SHALL also carry `blocking_missing`, the identities of the clips that the document lists, that are
absent from disk and that it does not exclude, in the order of `missing`. A render fails on such a clip, so
this is the set that holds a render back. `missing` SHALL keep listing every missing clip, excluded or not, so
a client can still report all of them.

**List.** Each event in `GET /api/v1/events` SHALL carry, besides the counts it has:

- `clip_count`: the number of clips the event lists that are not ignored, which is every ACTIVE, NEW and
  MISSING clip. It is the number the event's detail page counts, so a list row and its page agree.
- `ignored_count`: the number of IGNORED clips, which `clip_count` does not include.
- `blocking_missing_count`: the number of clips in the detail's `blocking_missing`.

`missing_count` SHALL keep counting every missing clip, excluded or not.

These are read-model fields only. They are derived from disk and the document on each request, nothing is
probed, written or stored, and the staleness verdict is unchanged: `exclude` is already part of the document's
editorial hash, and a missing clip adds nothing to the clip-set component, which covers the clips on disk.

#### Scenario: An excluded clip is flagged
- **WHEN** an event's `reel.yaml` lists `a.mp4`, `b.mp4` and `c.mp4` in one chapter and excludes `b.mp4`, and
  all three are on disk
- **THEN** the detail lists the three with `excluded` false, true and false, and `status` `active` for each

#### Scenario: A NEW, an IGNORED and an undocumented clip are not excluded
- **WHEN** an event holds a NEW clip, an IGNORED clip, and (in another event) no `reel.yaml` at all
- **THEN** every one of those clips reports `excluded: false`

#### Scenario: An excluded missing clip does not block
- **WHEN** an event's `reel.yaml` lists the absent `gone.mp4`, excludes it, and lists nothing else absent
- **THEN** the detail reports `missing` as `["gone.mp4"]`, `blocking_missing` as `[]`, and the clip as status
  `missing` with `excluded: true`

#### Scenario: Only the non-excluded missing clip blocks
- **WHEN** the same event also lists the absent `gone2.mp4`, which it does not exclude
- **THEN** `missing` is `["gone.mp4", "gone2.mp4"]` and `blocking_missing` is `["gone2.mp4"]`

#### Scenario: The list agrees with the detail on how many clips there are
- **WHEN** an event holds `00400.mp4` and `00401.mp4`, which `reel.yaml` lists, and `00402.mp4`, which it
  ignores
- **THEN** the list row reports `clip_count` 2 and `ignored_count` 1, and the detail lists three clips of which
  two are not ignored

#### Scenario: The list counts blocking missing clips apart
- **WHEN** an event lists one excluded absent clip and one non-excluded absent clip
- **THEN** its list row reports `missing_count` 2 and `blocking_missing_count` 1

#### Scenario: Reading the flags writes and probes nothing
- **WHEN** an event with an excluded clip is read through the list and the detail, with `ffprobe` made to fail
- **THEN** both answer, no file under the event changes, and the staleness verdict equals the one read before
  this change for the same files

### Requirement: Enqueue refuses an event that plays a clip missing from disk
`POST /api/v1/jobs` SHALL refuse an event that plays a clip which is absent from disk. A clip is played
when `reel.yaml` references it in a chapter and does not exclude it. A referenced clip that `reel.yaml`
excludes is not played: a render skips it and never probes it, so its absence SHALL NOT refuse the
enqueue. A clip on disk that `reel.yaml` does not reference (NEW) or lists in `ignore` (IGNORED) is not
missing, and SHALL NOT refuse it. The refusal SHALL name exactly the clips that the event's detail
publishes as blocking a render (`blocking_missing`), so that a client's guard and the server's refusal
cannot disagree about which clips matter.

The check SHALL run after the output-collision check and the active-job check, and before the staleness
gate. An event that has an active job SHALL therefore be answered as an active job (a client follows that
job). `force` SHALL NOT override this check, because the render it would queue fails at probe, and the
staleness verdict SHALL NOT matter to it. A refused event SHALL be answered with **409** and a
problem body that:

- names the event (`event_id`)
- carries the conflict kind `missing_clips`
- lists the played, missing clips' identities in `missing`, sorted
- has a detail that names those clips and says to restore them, or remove them from `reel.yaml`

For a refused event nothing SHALL be written: no job row, no render manifest, no change to `reel.yaml`,
and no change to an output file that already exists. The service SHALL NOT remove the clips from
`reel.yaml` itself, as removing a clip is an editorial write that the operator makes.

The check reads the event's folder listing and its `reel.yaml`; it SHALL NOT probe any clip. A clip that is
present when the request is checked and gone when the worker probes it still fails that job at probe, with
the engine's own error, as before this change. When the event's folder cannot be listed, the clips cannot be
checked, and the endpoint SHALL answer with the scan-failure 502 that the events list uses and SHALL NOT
enqueue. The schema SHALL publish the 409 in the shared problem body shape, with `missing` a list of strings.

#### Scenario: A stale event that plays a missing clip is refused
- **WHEN** `POST /api/v1/jobs` names `2024/2024-09-01 - Sommarlov`, whose `reel.yaml` lists `s1710002.mp4`,
  `s1710004.mp4` and the absent `borttagen.mp4` without excluding any of them
- **THEN** the response is 409 with `conflict` `missing_clips`, `event_id` `2024/2024-09-01 - Sommarlov`
  and `missing` `["borttagen.mp4"]`
- **AND** its detail names `borttagen.mp4` and says to restore it or remove it from `reel.yaml`
- **AND** no job row is inserted and no manifest is written

#### Scenario: Force does not override the refusal
- **WHEN** `POST /api/v1/jobs` names `2024/2024-09-01 - Sommarlov` with `"force": true`
- **THEN** the response is the same 409 `missing_clips`, and no job row is inserted

#### Scenario: Several missing clips are all named, sorted
- **WHEN** `POST /api/v1/jobs` names an event whose `reel.yaml` plays two absent clips, `gone-b.mp4` in
  its root chapter and `Kväll/gone-a.mp4` in its `Kväll` chapter
- **THEN** the response is 409 `missing_clips` with `missing` `["Kväll/gone-a.mp4", "gone-b.mp4"]`

#### Scenario: A missing clip that reel.yaml excludes does not refuse
- **WHEN** `POST /api/v1/jobs` names an event whose `reel.yaml` lists the absent `borta.mp4` with
  `exclude: true` and no other absent clip
- **THEN** the response is 201 with the queued job, and the job carries the event's fingerprint

#### Scenario: Excluded and played missing clips together name only the played one
- **WHEN** `POST /api/v1/jobs` names an event whose `reel.yaml` lists the absent `borta.mp4` (excluded) and
  the absent `saknas.mp4` (not excluded)
- **THEN** the response is 409 `missing_clips` with `missing` `["saknas.mp4"]`

#### Scenario: A NEW or IGNORED clip is not missing
- **WHEN** `POST /api/v1/jobs` names `2024/2024-08-20 - Två kapitel - Tjörn`, which holds a NEW clip and an
  IGNORED clip on disk and references no absent clip
- **THEN** the response is 201, as before this change

#### Scenario: An active job is followed, not refused
- **WHEN** `2024/2024-09-01 - Sommarlov` already has a `queued` job and `POST /api/v1/jobs` names it
- **THEN** the response is 409 with `conflict` `active_job` and that job's id, not `missing_clips`

#### Scenario: A collision outranks the refusal
- **WHEN** `POST /api/v1/jobs` names an event that plays a missing clip and also shares its output path
  with another event
- **THEN** the response is 409 `output_collision`

#### Scenario: A folder that cannot be listed is a scan failure
- **WHEN** the event's folder cannot be listed while `POST /api/v1/jobs` names it
- **THEN** the response is the scan-failure 502 problem body, and no job row is inserted

#### Scenario: The schema publishes the refusal
- **WHEN** the service's OpenAPI schema is generated
- **THEN** `POST /api/v1/jobs` declares its 409 and 502 responses in the shared problem body shape, and that
  body's `conflict` enumeration includes `missing_clips` and its `missing` field is a list of strings

### Requirement: Clip proxy endpoint
The service SHALL expose `GET` and `HEAD /api/v1/events/{event_id}/proxy?clip=<identity>`, which serves one
clip's **proxy**: the `proxy.mp4` that the proxy cache holds for the clip as it is on disk now, with its bytes
unchanged. `event_id` and `clip` are the clip media endpoint's: the event identity the events routes use and
the clip's identity exactly as the event detail lists it, percent-encoded as a query value and matched
exactly. An OPTIONAL query parameter `v` SHALL be accepted and ignored, as on the clip media endpoint.

**Shared behavior.** Every clause of the requirement "Media files are streamed with ranges and validators" that
governs the clip media endpoint SHALL hold for this endpoint as it holds for that one: `GET` and `HEAD`
(`HEAD` is the `GET` without its body, for every status), whole file, ranges and `If-Range`, the 400 and 416
plain-text answers, `Last-Modified`, the strong `ETag`, `Cache-Control: private, no-cache`, the conditional
requests (`If-None-Match`, then `If-Modified-Since`), bounded reads, a client that disconnects, a file that is
gone or unreadable when opened, path-free problem details, no ETag or Cache-Control on a 404 or 502, and the
single authentication hook for every request. The differences are only these:
- `Content-Type` SHALL be `video/mp4`.
- `Content-Disposition: inline` SHALL carry the cache file's own name, `proxy.mp4`.
- The `ETag` and `Last-Modified` SHALL be those of the proxy file, so a proxy that is made again has a
  different `ETag`, and a client MAY read it with a `HEAD` and send it as `v`.

**Which proxy.** The clip's proxy SHALL be the one the proxy cache holds under the cache key of the clip file
as it is now: its resolved path (a symbolic link is followed), size and modification time, the proxy version
and the proxy settings. The cache directory SHALL be the configured `proxies.cache_dir`, else the default cache
directory outside the library. Consequently:
- a proxy made for an earlier version of the file (the clip was replaced or rewritten), or under another proxy
  version or other proxy settings, is not this clip's proxy
- two events that link the same file share its proxy
- a file that is not finished is never served: a proxy that is still being written is in a hidden build
  directory of the cache, not in the clip's entry

**Which clips are served.** The clip lookup SHALL be the clip media endpoint's: the identity SHALL be one of the
clips discovery finds on disk for an event the events list shows, IGNORED clips included, and `reel.yaml` SHALL
NOT be read. The following SHALL be answered 404 with a problem body naming the event, without opening any file
outside the cache entry of a listed clip: an unknown event or a folder that is not an event; a MISSING clip; a
file discovery skips; any identity that is not a discovered clip of that event, including one that points
outside the event.

**Absent is never a 200.** A listed clip that has no proxy SHALL be answered 404 with a problem body that names
the event, the clip's identity and that it has no proxy, and carries no `ETag` or `Cache-Control`. That covers a
clip that was never prepared, a cache directory that does not exist yet, an entry without a finished
`proxy.mp4`, a proxy made for a file the clip no longer is, and something other than a regular file at the
proxy's place. The service SHALL NOT answer such a request with 200, 202, 204, a placeholder body, a redirect or
the original clip's bytes.

**Failures.**
- A listed clip that cannot be read after the listing, because it is gone, SHALL be answered 404.
- An event folder that cannot be listed SHALL be answered 502 with the unreadable-disk failure kind the events
  reads use.
- An ingest layout that cannot be resolved, a `config.yaml` that cannot be read or a `proxies.cache_dir` it
  names that is not usable SHALL be answered 502 with no failure kind and a path-free detail that points to the
  server log, which carries the full reason.
- A proxy file that exists but cannot be statted or opened, such as one the process lacks permission to read,
  SHALL be answered 502 with a problem body naming the event, the clip's identity and the operating system's
  reason, and no failure kind, before any byte of the file is sent. The detail SHALL NOT contain an absolute
  server path.

**Scope.**
- The endpoint SHALL answer while the database is unreachable and SHALL declare no 503.
- It SHALL NOT run ffmpeg or ffprobe, write any file or create any directory (the cache directory included),
  enqueue a job, or change the events read model, the staleness verdict or any job.
- The OpenAPI schema SHALL publish, for `get` and for `head` alike: the required `clip` and optional `v` query
  parameters; `If-None-Match`, `If-Modified-Since`, `Range` and `If-Range` as optional header parameters; the
  200 and 206 as `video/mp4` binary content with the `ETag`, `Last-Modified`, `Cache-Control`, `Accept-Ranges`
  and `Content-Disposition` headers, and `Content-Range` on the 206; the 304 with `ETag` and `Cache-Control`; the
  400 and 416; the 404 and 502 in the shared problem body shape; the 422 for a missing `clip`; and no 503.

#### Scenario: A prepared clip's proxy
- **WHEN** the proxy cache holds a finished `proxy.mp4` for the clip `s1710001.mp4` of `2024/2024-06-27 -
  Grillning med grannar`, and the proxy is requested without `Range`
- **THEN** the response is 200 with the proxy file's bytes, `Content-Type: video/mp4`, a `Content-Length`
  equal to its size, `Accept-Ranges: bytes`, the `ETag` and `Last-Modified` of the proxy file, `Cache-Control:
  private, no-cache` and `Content-Disposition` naming `proxy.mp4`
- **AND** none of these is the clip's: the clip's `ETag` differs from the proxy's

#### Scenario: A seek reads a range of the proxy
- **WHEN** that proxy is requested with `Range: bytes=1000-`, again with `bytes=0-99` and `If-Range` set to its
  current `ETag`, and again with `If-Range: "an-older-tag"`
- **THEN** the first response is 206 with the bytes from offset 1000 and `Content-Range: bytes 1000-<size -
  1>/<size>`, the second is 206 with 100 bytes, and the third is 200 with the whole proxy

#### Scenario: The Sony PCM clip's proxy has AAC sound in Firefox
- **WHEN** the proxy of `sony-xavc-1080p25-pcm.mp4`, made by `auto-reel proxies`, is loaded in a `<video>` of
  the same origin in Chrome 154 and in Firefox 155 or later, and played for 3 seconds
- **THEN** each browser shows a picture, Firefox reports an audio track (`mozHasAudio`), and the decoded
  audio's peak, tapped from the element, is greater than 0 in both
- **AND** the original of the same clip, loaded from the clip media endpoint, still has no audio in Firefox

#### Scenario: The first frame is quick
- **WHEN** a fresh `<video preload="auto">` is given the Sony PCM clip's proxy URL on the dev host over the
  loopback interface, five times
- **THEN** the median time from setting `src` to the first presented frame is at most 100 ms

#### Scenario: A clip that was never prepared
- **WHEN** `s1710002.mp4` of `2024/2024-06-27 - Grillning med grannar` has no entry in the proxy cache, and its
  proxy is requested, with `GET` and with `HEAD`
- **THEN** both responses are 404 with a problem body naming the event and the clip, no body for the `HEAD`, and
  no `ETag` or `Cache-Control`
- **AND** neither the cache directory nor any file in it was created

#### Scenario: The cache directory does not exist yet
- **WHEN** `proxies.cache_dir` names a directory that does not exist and a proxy is requested
- **THEN** the response is 404, and the directory still does not exist

#### Scenario: A proxy that is still being written
- **WHEN** the clip's proxy is being encoded, so the cache holds only the encoder's hidden build directory and the
  clip has no entry, or an entry without a finished `proxy.mp4`
- **THEN** the response is 404, and no byte of the partly written file is sent

#### Scenario: A clip that was replaced since its proxy was made
- **WHEN** the proxy cache holds a proxy made for the clip `s1710001.mp4`, and the clip is then replaced by
  another recording (its size and modification time change), and the proxy is requested
- **THEN** the response is 404, although the old entry is still on disk

#### Scenario: A proxy made under another proxy version
- **WHEN** the proxy cache holds an entry for the clip made under an earlier proxy version or other proxy
  settings, and the proxy is requested
- **THEN** the response is 404

#### Scenario: A proxy that is made again gets a new entity-tag
- **WHEN** a clip's `proxy.mp4` is replaced by a different file at the same place, and the proxy is requested
  with the old `ETag` in `If-None-Match`
- **THEN** the response is 200 with the new file's bytes and a different `ETag`
- **AND** `v=old`, `v=new` and no `v` give identical bodies and the same `ETag`

#### Scenario: A HEAD gives the entity-tag a client puts in v
- **WHEN** the proxy is requested with `HEAD`, and then with `GET`
- **THEN** both carry the same `ETag`, the `HEAD` has the `Content-Length` of the file and no body

#### Scenario: Revalidation is a 304 without a body
- **WHEN** the proxy is requested with `If-None-Match` set to its `ETag`, and again with `If-Modified-Since` set
  to its `Last-Modified`
- **THEN** each response is 304 with the `ETag` and `Cache-Control: private, no-cache` and no body

#### Scenario: An IGNORED clip's proxy is served
- **WHEN** the proxy of the root clip `s1710004.mp4` of `2024/2024-08-20 - Två kapitel - Tjörn`, which its
  `reel.yaml` lists under `ignore`, is requested and the cache holds it
- **THEN** the response is 200

#### Scenario: A symlinked clip shares its target's proxy
- **WHEN** two events each hold a symbolic link to the same sample file, the cache holds the proxy made for it,
  and each event's proxy is requested
- **THEN** both responses are 200 with the same bytes

#### Scenario: Identities that are not clips of the event
- **WHEN** the proxy is requested for `borttagen.mp4` (MISSING) of `2024/2024-09-01 - Sommarlov`, for
  `clip=../2024-06-27 - Grillning med grannar/s1710001.mp4`, for a file under an event's `original/` folder, and
  for the year folder `2024`
- **THEN** each response is 404 with a problem body naming the requested id, and no file outside the cache entry
  of a listed clip is opened

#### Scenario: A clip that vanishes after the listing
- **WHEN** a listed clip is deleted between the event's listing and the moment its cache key is computed
- **THEN** the response is 404, never a 500

#### Scenario: A proxy the process cannot read
- **WHEN** a clip's `proxy.mp4` exists but its permissions deny reading, and it is requested
- **THEN** the response is 502 with a problem body naming the event, the clip's identity and `Permission
  denied`, with no failure kind and no absolute server path, and no status line of 200 or 206 is sent

#### Scenario: A configuration that cannot be read
- **WHEN** the project's `config.yaml` cannot be parsed, or `proxies.cache_dir` names a place inside the
  library, and a proxy is requested
- **THEN** the response is 502 with a problem body and no failure kind

#### Scenario: An event folder that cannot be listed
- **WHEN** the event's folder cannot be listed and a proxy is requested
- **THEN** the response is 502 with the failure kind `unreadable_disk`

#### Scenario: No database, no ffmpeg, no writes
- **WHEN** the database is unreachable, the process is not allowed to start a subprocess, and a prepared proxy
  and an absent one are requested
- **THEN** the first is 200 and the second is 404, never 503, and a snapshot of every path, size and
  modification time under the library and the cache directory is equal before and after

#### Scenario: Every range request passes the authentication hook
- **WHEN** an authentication check is registered at the hook point, and a proxy is requested once without
  `Range` and twice with different ranges
- **THEN** the check runs for each of the three requests, and a request it rejects is answered by the check and
  receives no file bytes

#### Scenario: The schema publishes the proxy responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the `get` and the `head` operation of `/api/v1/events/{event_id}/proxy` declare the required `clip`
  and the optional `v` query parameters and the optional `If-None-Match`, `If-Modified-Since`, `Range` and
  `If-Range` header parameters, and publish 200 and 206 as `video/mp4` binary content, 304, 400, 404, 416, 422
  and 502, with the problem body shape for 404 and 502 and no 503

### Requirement: Clip filmstrip endpoint
The service SHALL expose `GET` and `HEAD /api/v1/events/{event_id}/filmstrip?clip=<identity>`, which serves one
clip's **filmstrip**: the `filmstrip.jpg` sprite that the proxy cache holds in the clip's entry, with its bytes
unchanged. Its parameters, the clip lookup, the choice of the cache entry (the requirement "Clip proxy
endpoint", "Which proxy"), the shared media behavior, the failures and the scope SHALL be those of the clip
proxy endpoint, with these differences:
- `Content-Type` SHALL be `image/jpeg`, and `Content-Disposition: inline` SHALL name `filmstrip.jpg`.
- The `ETag` and `Last-Modified` SHALL be those of the filmstrip file.
- The 200 and 206 SHALL be published as `image/jpeg` binary content.
- The filmstrip SHALL be served whenever a finished `filmstrip.jpg` is in the clip's entry, whether or not the
  entry's `proxy.mp4` is present, and an entry that holds a proxy but no filmstrip SHALL be answered 404. A clip
  that has a proxy but no filmstrip is therefore an ordinary case: a clip whose sprite step has not run yet or
  failed. (A clip shorter than one second has a one-tile sprite like any other.)

The endpoint SHALL NOT read the sprite's tile geometry or any other fact; those are part of the clip's proxy
state in the event detail.

#### Scenario: A prepared clip's filmstrip
- **WHEN** the clip `s1710001.mp4` of `2024/2024-06-27 - Grillning med grannar` has a finished `filmstrip.jpg`
  in the proxy cache and the filmstrip is requested
- **THEN** the response is 200 with the file's bytes, `Content-Type: image/jpeg`, `Content-Disposition`
  naming `filmstrip.jpg`, the file's `ETag` and `Last-Modified`, and `Cache-Control: private, no-cache`
- **AND** an `<img>` of the same origin loads it and reports a natural width and height greater than 0

#### Scenario: A range and a revalidation of the filmstrip
- **WHEN** the filmstrip is requested with `Range: bytes=0-99`, and again with `If-None-Match` set to its `ETag`
- **THEN** the first response is 206 with the file's first 100 bytes and `Content-Range: bytes 0-99/<size>`,
  and the second is 304 with no body

#### Scenario: A clip with a proxy and no filmstrip yet
- **WHEN** the clip `s1710001.mp4` has a finished `proxy.mp4` and no `filmstrip.jpg` in its entry, and its proxy
  and its filmstrip are requested
- **THEN** the proxy is 200 and the filmstrip is 404 with a problem body naming the event and the clip, and no
  `ETag` or `Cache-Control`

#### Scenario: A sub-second clip has a one-tile filmstrip
- **WHEN** the clip `kort.mp4`, 0.48 s long, was prepared by the proxy work, and its proxy and filmstrip are
  requested
- **THEN** both are 200, and the filmstrip body is a JPEG

#### Scenario: A filmstrip for a clip that was never prepared
- **WHEN** a listed clip has no entry in the proxy cache and its filmstrip is requested
- **THEN** the response is 404, and nothing was created in the cache directory

#### Scenario: A filmstrip of a replaced clip
- **WHEN** a clip has been replaced since its filmstrip was made, and the filmstrip is requested
- **THEN** the response is 404

#### Scenario: A filmstrip the process cannot read
- **WHEN** a clip's `filmstrip.jpg` exists but its permissions deny reading
- **THEN** the response is 502 with a problem body naming the event and the clip, no failure kind and no
  absolute server path

#### Scenario: The schema publishes the filmstrip responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the `get` and the `head` operation of `/api/v1/events/{event_id}/filmstrip` declare the same
  parameters as the proxy operations, and publish 200 and 206 as `image/jpeg` binary content, 304, 400, 404,
  416, 422 and 502, and no 503

### Requirement: The event detail reports each clip's proxy state
Each clip in the detail response SHALL carry a `proxy` object that reports whether the clip has a prepared
proxy (the clip-proxies capability) and, when it has, the media facts the proxy job recorded for it. The object
SHALL have `state`, a closed and published vocabulary of exactly `absent`, `ready`, `stale` and `failed`, and
these other members, each nullable and optional in the schema and present only for the state named:

- `facts`, for `ready` only: `duration` (seconds, the probe's number, finite and above zero), `fps_num` and
  `fps_den` (the frame rate as a fraction of positive integers), `vfr` (true when the source's frame times are
  variable, `null` when the container gave no average rate to compare), `width` and `height` (positive integers,
  the picture as displayed: sample aspect ratio and display rotation applied), `rotation` (the source's display
  rotation in degrees as the probe reported it, 0 to 359, or `null` when the source declares none),
  `audio_codec` (the source's audio codec name, or `null` when the source has no audio) and `filmstrip` (the
  sprite's `tile_width`, `tile_height`, `columns`, `tiles` and `interval`, the whole seconds of footage per tile).
  Each value SHALL be copied from the cache entry's recorded facts; none SHALL be computed, defaulted or
  derived from another field.
- `version`, for `ready` only: the proxy file's entity tag without its quotes, byte for byte the tag the
  media routes send for that file (the same size-and-nanosecond-mtime formula), so a client can put it in the
  proxy URL as `v`.
- `reason`, for `failed` only: a single line that states the cause and contains no server file path.

The `proxy` object SHALL be `null`, meaning unknown, never `absent`, for a clip the document references but disk
does not have, and for every clip when the project's `proxies` configuration cannot be resolved; the latter
SHALL NOT fail the response and SHALL log one warning per request. A clip's other fields are unaffected in
every case. The events **list** response SHALL NOT carry `proxy` or any per-clip proxy fact.

Reading the detail SHALL NOT run `ffprobe`, `ffmpeg` or any other process for a proxy, SHALL NOT write,
create, rename or touch any file in the proxy cache, and SHALL NOT list the cache directory: each clip costs
a bounded number of `stat` calls and one read of one small JSON file. A cache directory or entry that cannot be
read SHALL read as unknown (`proxy` is `null`) for that clip, not as a failed response and not as `absent`.
The proxy state SHALL NOT be an input of the staleness verdict: a clip's proxy becoming ready, stale or failed
SHALL NOT change an event's `staleness`. `ClipOut.duration` SHALL be unchanged and independent of the proxy.

#### Scenario: A clip with a prepared proxy reports its facts
- **WHEN** `C0047.MP4` (a 1080p25 Sony clip with PCM audio) has a complete proxy entry for the file as it is
  now and the detail is read
- **THEN** that clip's `proxy` has `state` `ready`, `facts.duration` as recorded, `fps_num` 25, `fps_den` 1,
  `width` 960, `height` 540, `rotation` `null` (the source declares none), `audio_codec` `pcm_s16be`, a `filmstrip` with `tile_width` 160 and
  `tile_height` 90, and a `version` equal to the proxy file's entity tag without quotes; neither `ffprobe`
  nor `ffmpeg` ran

#### Scenario: A rotated phone clip reports its rotation and displayed size
- **WHEN** a portrait HEVC clip recorded with a 90 degree display rotation has a ready proxy of 540 by 960
- **THEN** its `facts` carry `rotation` 90 with `width` 540 and `height` 960, as recorded

#### Scenario: A clip with no proxy is absent
- **WHEN** the detail is read for a clip that has never been prepared
- **THEN** its `proxy` is `{state: "absent"}` with no `facts`, `version` or `reason`, and the proxy cache
  directory's listing is identical before and after the request

#### Scenario: A clip without audio reports a null audio codec
- **WHEN** a ready proxy's recorded facts say the source has no audio track
- **THEN** `facts.audio_codec` is `null` and the state is still `ready`

#### Scenario: A variable frame rate clip is flagged, not rounded
- **WHEN** a ready proxy's recorded facts say the source is variable frame rate with an average of 30000/1001
- **THEN** `facts.vfr` is true and `fps_num` 30000 with `fps_den` 1001, not a rounded float

#### Scenario: A failed attempt is reported with its cause
- **WHEN** the last attempt to prepare a clip failed, recording the cause `moov atom not found`, and no usable
  entry exists
- **THEN** its `proxy` is `{state: "failed", reason: "moov atom not found"}` and the reason names no path

#### Scenario: A replaced file reads as absent
- **WHEN** a clip had a ready proxy and the file is then replaced by another of the same name with a different
  size or modification time
- **THEN** the detail reports `state` `absent` for it, because the cache key moved with the file, and does not
  serve the old facts

#### Scenario: The proxy state is not part of the staleness verdict
- **WHEN** every clip of a freshly rendered event gains a ready proxy
- **THEN** the event's `staleness` is unchanged and still reports fresh

#### Scenario: An unusable proxies configuration leaves the state unknown
- **WHEN** the project's `config.yaml` sets `proxies.cache_dir` to a relative path, which the proxy commands
  refuse, and the event detail is read
- **THEN** the detail is a success, every clip's `proxy` is `null`, one warning is logged, and the other
  fields and the rest of the response are unchanged

#### Scenario: A missing clip has no proxy state
- **WHEN** the document references a clip whose file has been deleted or renamed
- **THEN** it is reported MISSING with a `proxy` of `null`, alongside its null size and modification time

#### Scenario: An unreadable cache is unknown, not an error
- **WHEN** the proxy cache directory cannot be read (permission denied)
- **THEN** the detail is a success and each affected clip's `proxy` is `null`

#### Scenario: Reading starts no process
- **WHEN** the detail is read for an event of 25 clips with every process-starting facility made to raise
- **THEN** the response is a 200 and no process was started

#### Scenario: The list carries no proxy facts
- **WHEN** `GET /api/v1/events` is read for a project whose clips have ready proxies
- **THEN** the response has no per-clip fields, as before

### Requirement: The event detail reports the rendered movie's version and chapter times

`GET /api/v1/events/{event_id}` SHALL carry `movie`, always present, holding either `null` or an object. It
SHALL be read from the event's render manifest and the filesystem by reading and statting only: producing it
MUST NOT run `ffprobe` or `ffmpeg`, decode any file, or write, create or refresh any file, cache entry or
database row. The events **list** (`GET /api/v1/events`) SHALL NOT carry it.

**When it is null.** `movie` SHALL be `null` when the event has no rendered movie, and it SHALL be an object
otherwise. An event has a rendered movie by the same rule as `GET /api/v1/events/{event_id}/movie`, one rule
used by both: the file the staleness gate counts, whose path (with `.` and `..` removed lexically) lies inside
the service's output directory. `movie` is therefore non-null exactly when that route would find the file, save that a manifest
whose `written_at` is not a timezone-aware date-time (or is one that UTC cannot hold) gives `null` (no version can be told). A
manifest the engine cannot read, a movie that is gone or is not a file, and a path that climbs out of the output
directory each give `null`; none of them SHALL fail the detail, whose own failures (an unparseable `reel.yaml`,
unusable metadata, an unreadable folder) are unchanged.

**What it holds.** The object SHALL carry:

- `recorded_at`: the render manifest's `written_at`, a timezone-aware UTC date-time. It is when the render
  record was written: the engine writes it only after the atomic finalize verified the movie, so for a render
  it is when the render finished; for a movie `adopt-renders` recorded it is when it was adopted. It MUST NOT
  be replaced with the movie file's modification time, the current time or any other value.
- `fingerprint`: the first 12 hexadecimal characters of the manifest's combined fingerprint, the identity of
  the inputs that render was made from. It is not a hash of the movie's bytes: two renders of identical inputs
  share it and differ in `recorded_at`. `recorded_at` and `fingerprint` together are the movie's version.
- `chapters`: the chapter start times that render recorded in the manifest (change `render-chapter-times`),
  a list of objects with `name` and `start`, where `start` is seconds from the beginning of the rendered
  movie (the recorded millisecond count divided by 1000). The list SHALL be exactly the recorded one: same order, same names, same times, with no chapter
  added, dropped, renamed, sorted or clamped, and no entry for the title card. `chapters` SHALL be `null`,
  meaning unknown, when the manifest records no chapter times (a manifest written before that change, or a
  movie adopted rather than rendered) or when its recorded list is unreadable (including a time too large to be seconds). It MUST NOT be an empty list
  to mean unknown, and the API MUST NOT compute, estimate or guess a time from the reel, the clips' durations
  or the movie. A recorded list that is empty is reported as empty.

`recorded_at`, `fingerprint` and `chapters` SHALL all come from one read of the manifest, so they always
describe the same render. (The lookup that decides whether there is a movie reads the manifest on its own, so a
render landing between the two reads can pair that render's facts with the previous render's file for one read.)

**The facts describe the movie on disk.** They are the last render's, not the current editorial state's: after
the title or a chapter name changes, or a clip is added, the event is stale and `movie.chapters` still lists
the chapters and names the last render produced, while `staleness` says the movie is outdated. The movie of a
renamed event (`output_renamed`) is the file under its old name, and its facts are that render's.

**Published schema.** The service's OpenAPI schema SHALL publish `movie` as an optional, nullable property of
the detail, and `recorded_at` and `fingerprint` as required properties of the object, `chapters` as optional
and nullable, and `name` and `start` as required properties of a chapter. A generated client therefore types
absent and `null` alike as "not known". Every existing property of the detail SHALL keep its name, type,
required status and value.

#### Scenario: A rendered event reports its movie's version and chapters
- **WHEN** `2024/2024-07-14 - Kalas`, rendered by an engine that records chapter times, with chapters `Ankomst`
  and `Tårtan` that start at 4.0 and 71.5 seconds in its movie, is read with `GET /api/v1/events/{event_id}`
- **THEN** `movie.chapters` is `[{"name": "Ankomst", "start": 4.0}, {"name": "Tårtan", "start": 71.5}]`
- **AND** `movie.recorded_at` equals the manifest's `written_at`, and `movie.fingerprint` is the first 12
  characters of the manifest's `fingerprint`

#### Scenario: A real small render feeds the detail
- **WHEN** an event of two real sample clips in two chapters is rendered by the engine and its detail is read
- **THEN** `movie` is non-null and its `chapters` has two entries whose `start` values equal the manifest's,
  the first smaller than the second
- **AND** `movie.recorded_at` is not later than the time of the read

#### Scenario: A manifest from before chapter times has a movie and no chapter list
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has a readable manifest without chapter times and its movie
  file exists, and its detail is read
- **THEN** `movie` is an object with `recorded_at` and `fingerprint`, and `movie.chapters` is `null`
- **AND** `movie.chapters` is not `[]`

#### Scenario: A movie adopted rather than rendered reports no chapters
- **WHEN** an event whose pre-gate movie `adopt-renders` recorded is read
- **THEN** `movie.recorded_at` is the manifest's `written_at` (the adoption time), and `movie.chapters` is `null`

#### Scenario: An unrendered event has no movie
- **WHEN** `2024/2024-09-01 - Sommarlov` or `2024/Blandat`, events with no render record, is read
- **THEN** `movie` is `null`, with the key present

#### Scenario: A deleted movie file leaves no movie facts
- **WHEN** an event has a readable manifest and neither the expected nor the recorded movie file exists
- **THEN** `movie` is `null`, the detail answers 200, and the staleness cites `output`

#### Scenario: A directory where the movie belongs is no movie
- **WHEN** an event has a readable manifest and the expected movie path is a directory, with no movie under the
  recorded name
- **THEN** `movie` is `null`

#### Scenario: An unreadable manifest is treated as absent
- **WHEN** an event's `render-manifest.json` is malformed, of an unknown version or truncated, and a file stands
  at the expected movie path
- **THEN** `movie` is `null` and the detail answers 200 with the staleness citing `no_manifest`

#### Scenario: A record without a usable time reports no movie
- **WHEN** an event's readable manifest has a `written_at` that is not a date-time, one without a UTC offset, or one
  that cannot be expressed in UTC (`0001-01-01T00:00:00+05:00`), and its movie file exists
- **THEN** `movie` is `null` and the detail answers 200

#### Scenario: A chapter time too large to be seconds makes the chapters unknown
- **WHEN** an event's readable manifest records a chapter whose `start_ms` is `10**400`, and its detail is read
- **THEN** the detail answers 200, `movie` is an object with its `recorded_at` and `fingerprint`, and
  `movie.chapters` is `null`

#### Scenario: A stale event keeps the last render's chapters
- **WHEN** `2024/2024-08-02 - Badutflykt - Varberg` was rendered with a chapter `Bad`, its `reel.yaml` then
  renames that chapter to `Badet` and adds a clip, and its detail is read
- **THEN** the staleness cites `editorial` and `clip_set`, the detail's own `chapters` name `Badet`, and
  `movie.chapters` still names `Bad` with the starts the render recorded

#### Scenario: A renamed event reports the facts of the movie under its old name
- **WHEN** `2024/2024-06-27 - Grillning med grannar` was rendered and its title then changed, so its staleness
  cites `output_renamed`, and its detail is read
- **THEN** `movie` is non-null and holds the manifest's `recorded_at`, `fingerprint` and `chapters`, the facts
  of the file the last render wrote under the old name

#### Scenario: A re-render changes the version
- **WHEN** an event's detail is read, the event is rendered again with `--force` and no edit, and the detail is
  read again
- **THEN** `movie.fingerprint` is the same in both reads and `movie.recorded_at` is later in the second

#### Scenario: A title cannot make the detail report a file outside the output directory
- **WHEN** an event with a render record has the title `x/../../../outside` and the folders exist so that its
  expected path resolves to an existing `outside.mp4` beside the output directory
- **THEN** `movie` is `null`, as `GET …/movie` answers 404 for it

#### Scenario: The detail and the movie route agree for every event
- **WHEN** for each event the dev library's events list shows (not as an error row), the detail's `movie` and
  `GET /api/v1/events/{event_id}/movie` are read
- **THEN** `movie` is non-null exactly for the events whose route answers 200

#### Scenario: Reading the movie facts probes and writes nothing
- **WHEN** an event with a manifest that records chapters is read with every subprocess launch made to raise
  and the event directory and output directory snapshotted before and after
- **THEN** the detail answers 200 with `movie` filled, no process is launched, and no file under either
  directory is created, changed or removed

#### Scenario: The list does not carry the movie
- **WHEN** `GET /api/v1/events` lists the same events
- **THEN** no row has a `movie` key, and every row keeps the keys and values it had before

#### Scenario: The schema publishes the movie object
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the detail's properties include `movie`, which is not required
- **AND** the movie object's required properties are exactly `recorded_at` and `fingerprint`, its `chapters` is
  nullable and not required, and a chapter's required properties are exactly `name` and `start`
- **AND** the committed `web/openapi.json` equals the generated one

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

### Requirement: The editorial document carries each chapter's title card
The editorial body that `PUT /api/v1/events/{event_id}/reel` accepts, that `GET /api/v1/events/{event_id}/reel`
returns and that the write echoes SHALL carry, for each chapter, an optional `card`: the chapter's title-card
**overrides**, with the keys and meaning the engine's card mapping has in `reel.yaml` - `title`, `subtitle`,
`duration`, `background` (`black` or `video`), and the style overrides `font_family`, `title_font_size`,
`subtitle_font_size`, `text_color` and `position`. Every field is optional and a field that is `null` or absent
means "no override": the card inherits it, and nothing is written for it. A chapter whose `card` has no field set
(`{}`, or only `null` fields) has no card entry in `reel.yaml`; a chapter whose `card` is absent or `null` keeps the
card `reel.yaml` already holds (the engine's rule, so a client that does not know cards cannot erase one). The default chapter `""` holds the opening card. The event-wide card
style is the existing `look.title_card` part of `look`; `look` stays an opaque map in the body.

The endpoint SHALL contain no card validation of its own: the request shape (known keys, JSON types) is checked
by the body model, and every value rule - ranges, the allowed `background` and `position` values, and that
`font_family` is a family of the font registry - is the engine's, so a card is refused over the API exactly as
the engine refuses it in a loaded document. A submitted card the engine refuses SHALL be a **400** problem body
whose `detail` names the chapter and the field (for example `card.duration` of chapter `Dag 2`), as for any
other invalid submitted state; a `look.title_card` the engine refuses SHALL be refused the same way, naming the
`look.title_card` field. A card key the body model does not know is rejected, naming the key. Nothing is written
for any of them.

The write SHALL keep every property the editorial write already has for the rest of the document: comments and
key order of `reel.yaml` survive, an unmodified echo submitted back leaves the file byte-for-byte unchanged, and
a write that changes a card makes the event stale through the editorial component without enqueuing a job. A
chapter's `card` follows the chapter by name: renaming a chapter in a write carries its card to the new name,
and a write that sends a chapter's `card` with no field set removes that chapter's card.

#### Scenario: A card is saved and returned
- **WHEN** `PUT …/reel` sends a chapter `Dag 2` with `card: {title: "Dag två", subtitle: "Stranden", duration: 5,
  background: "video", font_family: <a registry family>}`
- **THEN** the chapter's entry in `reel.yaml` holds those five card keys and no others, the response echoes the
  same `card` (the unset fields `null`), and `GET …/reel` returns it

#### Scenario: The title can be overridden without renaming the chapter
- **WHEN** a write sets `card.title` on the chapter `Dag 2` and leaves the chapter's `name` unchanged
- **THEN** the chapter is still named `Dag 2` in `reel.yaml`, the clips' order is untouched, and the card carries
  the new title

#### Scenario: The opening card lives on the default chapter
- **WHEN** a write sets `card: {subtitle: "Sommaren 2024"}` on the chapter named `""`
- **THEN** `reel.yaml` holds the card on the default chapter, and no other chapter gains one

#### Scenario: An invalid card is refused, naming the field
- **WHEN** a write sends `card.duration` as `-3`, or `card.font_family` as a family that is not in the registry,
  or `card.background` as `"gradient"`
- **THEN** the response is 400 with a problem body whose `detail` names the chapter and that field, and
  `reel.yaml` is byte-for-byte unchanged

#### Scenario: An unknown card key is rejected
- **WHEN** a write sends `card: {colour: "#fff"}`
- **THEN** the response rejects the body, naming `colour`, and `reel.yaml` is unchanged

#### Scenario: An invalid event-wide card style is refused
- **WHEN** a write sends `look: {title_card: {title_font_size: "big"}}`
- **THEN** the response is 400 with a problem body naming `look.title_card.title_font_size`, and `reel.yaml` is
  unchanged

#### Scenario: Saving an unmodified document with cards is a no-op
- **WHEN** an event whose `reel.yaml` holds a commented chapter with a `card` is read with `GET …/reel` and the
  body is written back unmodified
- **THEN** `reel.yaml` is byte-for-byte unchanged and the comments survive

#### Scenario: A card edit makes the event stale and enqueues nothing
- **WHEN** a fresh, rendered event is saved with a changed `card.title`
- **THEN** the response's staleness verdict is stale citing the editorial component, and no job exists

#### Scenario: A card follows its chapter's rename
- **WHEN** a write renames the chapter `Dag 2` to `Dag två` and sends the same `card` on it
- **THEN** the persisted chapter `Dag två` holds the card, and `Dag 2` no longer exists

#XX
- **WHEN** a chapter with a persisted card is written with no `card`
- **THEN** the persisted chapter has no card entry, in keeping with the body being the complete state

### Requirement: The event detail reports each chapter's resolved title card and the event's card style
`GET /api/v1/events/{event_id}` SHALL report, for every chapter it lists (the default chapter `""` included),
a `card`: the **resolved** card the engine would draw for that chapter, and, for the event, a `title_card`: the
event's resolved card style. The values are produced by the engine's own resolution of the document (the layering
of the project `config.yaml` `look`, the event `look.title_card` and the chapter's own overrides, and the defaulting
of the title and subtitle), not by the service and not by the client.

A chapter's `card` SHALL carry concrete, never null, values: `title`, `subtitle`, `duration` (seconds),
`background` (`black` or `video`) and the effective style `font_family`, `title_font_size`,
`subtitle_font_size`, `text_color` and `position`. `title` is the chapter's override when it has one, else the
chapter's name, and for the default chapter the event's title; `subtitle` is the override, else empty (a card shows no date or
place unless the author wrote it). The event's `title_card` SHALL carry `duration`, `background` and the same
five style fields, as the event-wide layer leaves them before any chapter overrides. A font family no override
named is the bundled default. The report SHALL be probe-free and read-only, and SHALL add no database read.
It describes what a render would draw; it does not claim the render draws a card for a chapter whose clips all
turn out not to play, which only a render knows.

When the event-wide `look.title_card` cannot be resolved (a hand-edited value the engine refuses), the detail
SHALL still answer 200 so the author can open the event and correct it: `title_card` and every chapter's `card`
are `null` and `title_card_error` names the field and the reason. Absence of an error is `title_card_error:
null`. A single chapter whose own card the engine cannot resolve (a hand-written `font_family` outside the
registry) has `card: null` and a `card_error` naming the field, while the other chapters are reported. Nothing is fabricated in place of a card that cannot be resolved.

#### Scenario: An event with no card configuration reports the defaults
- **WHEN** the detail of an event whose `reel.yaml` has no `look.title_card` and no `card` is read, in a project
  whose `config.yaml` has none either
- **THEN** every chapter's `card` carries the documented defaults, the title is the chapter name (the event title
  for the default chapter), the subtitle is empty, the font is `DejaVu Sans`, and `title_card` carries the same
  defaults

#### Scenario: An override wins over the event style and the project style
- **WHEN** the project `config.yaml` sets `look.title_card.font_family` to one registry family, the event's
  `reel.yaml` sets another, and the chapter `Dag 2` sets a third on its `card`
- **THEN** that chapter's `card.font_family` is the third, another chapter's is the second, and `title_card`
  reports the second

#### Scenario: The title can differ from the chapter name
- **WHEN** the chapter `Dag 2` has `card: {title: "Dag två"}`
- **THEN** its resolved `card.title` is `Dag två` and the chapter is still listed as `Dag 2`

#### Scenario: The opening card shows no date or place
- **WHEN** an event with a date, a location and a description and no card on the default chapter is read
- **THEN** the default chapter's `card.title` is the event title and its `card.subtitle` is empty

#### Scenario: A chapter that the document does not list still has a card
- **WHEN** a clip on disk belongs to a chapter the document does not list, so the detail adds that chapter
- **THEN** the added chapter has a resolved `card` from the defaults, with its name as the title

#### Scenario: A bad event style does not lock the event
- **WHEN** a hand-edited `look.title_card.position` holds a value the engine refuses
- **THEN** the detail is 200, `title_card` and every `card` are `null`, and `title_card_error` names
  `look.title_card.position`, while the clips, chapters and staleness are reported as usual

#### Scenario: The read is read-only and probe-free
- **WHEN** the detail is read
- **THEN** no file is written under the event, no subprocess is started, and the request reads no more of the
  media than it did before this requirement

### Requirement: The font registry is listed over REST
The service SHALL expose `GET /api/v1/fonts`, returning the engine's font registry in its order: for each
bundled font its `family` (the name `card.font_family` and `look.title_card.font_family` accept), its
`display_name`, its `weights` (the weights the registry bundles, as integers) and `default`, true for exactly the
one font the engine uses when none is named. The list SHALL be produced by the registry module the schema and the
renderer read, so the three cannot disagree, and SHALL not read the disk, the project or the database. It SHALL be
read-only, need no event, and publish its response model in the OpenAPI schema.

#### Scenario: The list is the registry
- **WHEN** `GET /api/v1/fonts` is requested
- **THEN** the response is 200 and lists every registry family exactly once, in the registry's order, each with
  its display name and weights, and exactly one entry has `default: true`, the bundled default

#### Scenario: Every listed family is accepted by the write
- **WHEN** each listed `family` is used as a chapter's `card.font_family` in a write
- **THEN** every write succeeds

#### Scenario: A family that is not listed is refused by the write
- **WHEN** a write uses a family that the list does not hold
- **THEN** the write is refused as an invalid card, naming `font_family`

### Requirement: A draft title card is previewed as a PNG
The service SHALL expose `POST /api/v1/events/{event_id}/title-card/preview`, which renders **one title card**
from a posted draft and returns it as `image/png`. The request body holds the draft only: `chapter` (the
chapter's name, `""` for the opening card, default `""`), `card` (the same overrides as the editorial `card`,
default none), `style` (optionally a draft of the event-wide `look.title_card`; when absent, the event's saved
one) and `event_title` (optionally the draft event title the opening card defaults to; when absent, the saved
document's title). The draft is resolved by the same resolution the event detail and a render use, layered on the
project `config.yaml` and the event's saved `look`, so what is previewed is what the draft would render once saved.
The image SHALL be produced by the same renderer a render uses, at the event's target resolution (the resolved
`look.target_resolution`, 1920x1080 by default), and for a `background` of `black` it SHALL be the card the
render draws on black. For a `background` of `video` it SHALL be the text on a **fully transparent**
background, because the card is drawn over the clip's picture; the client composes it over the frame.

The operation SHALL be read-only and light: it writes nothing (not `reel.yaml`, not a cache, not a file under the
event), starts no subprocess and no ffmpeg, reads no media, takes no job slot and reads no database row. The
response SHALL be `Cache-Control: no-store`. It SHALL answer each failure by cause:

- **404:** an unknown event.
- **400, a problem body naming the field:** a draft the engine refuses (including a font family not in the
  registry), the same refusal the editorial write gives.
- **422:** a body that is structurally malformed or breaks a size bound (see the bounded requirement).
- **502:** an event whose existing `reel.yaml` cannot be read (the scan-failure problem body with its failure
  kind, as the other event routes), or a card that cannot be drawn although the draft is valid (a registry
  font the host's font configuration does not resolve), naming the cause.
- **503:** the drawing backend (Cairo/Pango) is not available in this process, naming it; or the service is busy
  (see the bounded requirement).

The endpoint SHALL publish its 200 as `image/png`, its failures in the shared problem body shape, and the request
and response models in the OpenAPI schema.

#### Scenario: A black card is previewed at the target resolution
- **WHEN** a draft for the chapter `""` with `card: {title: "Sommaren", subtitle: "2024"}` is posted to an event
  whose resolved target resolution is 1920x1080
- **THEN** the response is 200 `image/png`, a 1920x1080 image, whose bytes equal the image the render's card
  renderer produces for that card, and the headers carry `Cache-Control: no-store`

#### Scenario: The target resolution of the event decides the size
- **WHEN** the event's `look` sets `target_resolution: [1280, 720]`
- **THEN** the preview is a 1280x720 image

#### Scenario: A video card is the text on transparency
- **WHEN** a draft with `card: {background: "video"}` is posted
- **THEN** the image is RGBA and its corner pixel is fully transparent, while a pixel in the text is opaque

#### Scenario: The draft is previewed without saving it
- **WHEN** a draft title differs from the one in `reel.yaml` and is posted
- **THEN** the image shows the draft title, and `reel.yaml` is byte-for-byte unchanged afterwards

#### Scenario: The draft event style overrides the saved one
- **WHEN** a draft posts `style: {text_color: "#ff0000"}` for an event whose saved style has a white text
- **THEN** the image's text is red, and a draft without `style` shows the saved colour

#### Scenario: The opening card defaults to the draft event title
- **WHEN** the default chapter's draft carries no `card.title` and the request sends `event_title: "Nytt namn"`
- **THEN** the image shows `Nytt namn`; with no `event_title` it shows the saved title

#### Scenario: Each registry font renders
- **WHEN** a draft names each registry family in turn
- **THEN** each response is a PNG, and no two families produce byte-identical images for the same text

#### Scenario: An invalid draft names the field
- **WHEN** a draft posts `card.title_font_size` as `0`, or `font_family` as `"Comic Sans"`
- **THEN** the response is 400 with a problem body naming that field, and no image is produced

#### Scenario: An unknown event is 404
- **WHEN** the preview targets an event id that does not resolve under the project root
- **THEN** the response is 404 with a problem body

#### Scenario: A broken reel.yaml is the file's fault
- **WHEN** the event's existing `reel.yaml` cannot be parsed
- **THEN** the response is the scan-failure 502 with the unparseable-`reel.yaml` failure kind, not a 400

#### Scenario: The drawing backend is missing
- **WHEN** the process cannot load Cairo/Pango
- **THEN** the response is 503 whose detail names the backend, never an unshaped 500

#### Scenario: The preview touches nothing
- **WHEN** a preview is requested with the dev library's cache directories, `reel.yaml` and the job table observed
- **THEN** none of them changed, and no subprocess was started

### Requirement: The title-card preview is bounded
The preview endpoint SHALL bound what one caller can make the service do. The draft's free text SHALL be limited:
`card.title` and `event_title` to 200 characters and `card.subtitle` to 400; a longer one is a 422 naming the
field. The image SHALL be only the size the event renders at, never a size the request chooses. The service SHALL
draw at most two previews at once per process; a request that cannot start within 10 seconds of waiting for a
slot SHALL be answered 503 with `Retry-After` and a problem body, and SHALL not be drawn after it was answered.
Waiting SHALL NOT occupy a worker thread, so the rest of the API keeps answering while previews wait. The bounds
belong to the preview request only: the editorial `card` the write accepts has no length limit of its own beyond
the engine's, so a document that is longer than the preview allows still round-trips.

#### Scenario: An over-long title is refused
- **WHEN** a draft's `card.title` is 201 characters
- **THEN** the response is 422 naming `card.title`, and nothing is drawn

#### Scenario: A document longer than the preview bound still saves
- **WHEN** a write sets a 300-character `card.title`
- **THEN** the write succeeds (the engine sets no such limit), and only the preview refuses that title

#### Scenario: A busy service says so
- **WHEN** two previews are drawing and a third waits longer than the wait limit
- **THEN** the third is answered 503 with `Retry-After`, and the other API routes answer while it waits

#### Scenario: Previews of the same draft share no state
- **WHEN** two different drafts are posted at the same time
- **THEN** each response shows its own draft

### Requirement: The event detail reports whether title cards are enabled and where that was decided
`GET /api/v1/events/{event_id}` SHALL report `title_cards`, an object with `enabled` (boolean) and `source` (one
of `event`, `project`, `default`). `enabled` is whether the effective decorators of the merged look include
`title`, that is whether a render draws the chapters' cards at all. `source` is `event` when the event's
`reel.yaml` sets `look.decorators`, else `project` when the project `config.yaml` sets it, else `default`, where
the effective decorators are `[title]`. The value SHALL be produced by the engine's own function, the one the
render resolves its decorators with, from the document's `look` and the project's `look` defaults, and not by the
service or the client. It SHALL be probe-free, read-only and add no database read, and it SHALL always be present as a key;
it is an object unless `look.decorators` is not a list, when it is null (see below). It describes what a render would do; like a chapter's `card`, it does not claim that a chapter with no
title clip, or whose clips are all cut away, gets a card. The published OpenAPI schema SHALL carry `title_cards`
with `source` as a closed enumeration, and the checked-in generated web types SHALL match it.

When `look.decorators` holds a value that is not a list, the detail SHALL still answer 200 so the author can open
the event and correct it: `title_cards` is then `null` and a `title_cards_error` names `look.decorators` and the
reason; nothing is guessed in its place. Absence of an error is
`title_cards_error: null`.

#### Scenario: Event null decorators override a project opt-out
- **WHEN** the event `look.decorators` is present but null and the project sets `decorators: []`
- **THEN** the null counts as the event's own (empty) value in the shallow merge, so the cards are on with `source` `default`

#### Scenario: Nothing sets decorators
- **WHEN** neither the event's `reel.yaml` nor the project `config.yaml` sets `look.decorators`
- **THEN** the detail's `title_cards` is `{enabled: true, source: "default"}`

#### Scenario: The event opts out
- **WHEN** the event's `reel.yaml` sets `look.decorators: []`
- **THEN** `title_cards` is `{enabled: false, source: "event"}`

#### Scenario: The project opts out
- **WHEN** the project `config.yaml` sets `look.decorators: []` and the event's `reel.yaml` does not set it
- **THEN** `title_cards` is `{enabled: false, source: "project"}`

#### Scenario: The event overrides the project
- **WHEN** the project `config.yaml` sets `look.decorators: []` and the event's `reel.yaml` sets `[title]`
- **THEN** `title_cards` is `{enabled: true, source: "event"}`

#### Scenario: A list without title is disabled
- **WHEN** the event sets `look.decorators` to a list that does not include `title`
- **THEN** `title_cards.enabled` is `false` and `source` is `event`

#### Scenario: A bad value does not lock the event
- **WHEN** the event's `look.decorators` is the string `title`
- **THEN** the detail is 200, `title_cards` is `null` and `title_cards_error` names `look.decorators`, while the clips, chapters and staleness are reported as usual

#### Scenario: The read is read-only and probe-free
- **WHEN** the detail is read
- **THEN** no file is written under the event, no subprocess is started, and no database read is added

#### Scenario: The schema is published and the types match
- **WHEN** the OpenAPI document is generated
- **THEN** it carries `title_cards` on the event detail with `source` restricted to `event`, `project` and `default`, and the drift test finds `schema.d.ts` unchanged after regeneration

### Requirement: The resolved card reports what it shows by default
Each chapter's resolved `card` in `GET /api/v1/events/{event_id}` SHALL carry `default_subtitle`, a string: what the
card's subtitle is when its `subtitle` key is absent. For the default chapter it is the engine's date-and-place text
(`title-card`, "The opening card's default subtitle is its date and place"), possibly empty; for any other chapter it
is the empty string. The card's `subtitle` SHALL be the effective one: the override when the key is present (an empty
string included), else `default_subtitle`. Both values SHALL be produced by the engine's own resolution, probe-free,
read-only, with no database read; neither the service nor a client composes them. An editorial `card` SHALL
keep an explicit `subtitle: ""` through `PUT` and `GET`, and the preview SHALL treat `""` as no subtitle and `null` or absent as
the default. The published OpenAPI schema SHALL carry `default_subtitle`, and the checked-in generated web types
SHALL match it. This requirement takes precedence over "else empty (a card shows no date or place unless the
author wrote it)" and the scenario "The opening card shows no date or place" of "The event detail reports each
chapter's resolved title card and the event's card style".

#### Scenario: The opening card reports the default
- **WHEN** the detail of an event dated 2024-08-20 with location `Tjörn` and no `subtitle` key is read
- **THEN** the default chapter's `card.subtitle` and `card.default_subtitle` are both `2024-08-20\nPlats: Tjörn`

#### Scenario: An explicit empty subtitle is reported empty, the default still shown
- **WHEN** the default chapter's card sets `subtitle: ""`
- **THEN** its `card.subtitle` is `""` and its `card.default_subtitle` is still `2024-08-20\nPlats: Tjörn`

#### Scenario: A chapter card has no default
- **WHEN** the detail of a chapter other than the default is read
- **THEN** its `card.default_subtitle` is `""`

#### Scenario: Empty is kept, null removes
- **WHEN** `PUT .../reel` writes the default chapter's `card: {subtitle: ""}` and later `card: {}` 
- **THEN** `reel.yaml` holds `subtitle: ""` after the first and no card entry after the second, and a `GET` after each reports it

#### Scenario: The preview follows the rule
- **WHEN** the preview is asked for the opening card with `card: {subtitle: ""}`, then with no subtitle
- **THEN** the first image has the title only and the second has the date and place lines
