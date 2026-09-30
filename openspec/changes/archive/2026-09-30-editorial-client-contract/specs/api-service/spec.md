## MODIFIED Requirements

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
