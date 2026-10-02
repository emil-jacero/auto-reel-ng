## MODIFIED Requirements

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

### Requirement: Conditional editorial write
The write endpoint SHALL accept an optional `If-Match` request header carrying an ETag obtained from the
editorial read endpoint. The header SHALL be evaluated across every `If-Match` header line the request
carries, as RFC 9110 defines repeated lines to be one comma-separated list: a request with the lines
`If-Match: "stale"` and `If-Match: "<current>"` is the same request as one line holding both tags, and
matches. A request that carries the header at all, even with an empty value, is conditional. When the header is present and matches the event's current editorial state, the write
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
