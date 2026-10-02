## ADDED Requirements

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
cannot be rendered by two jobs at once through two spellings. A year folder that cannot be listed while the
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

#### Scenario: A symbolic link to an event, inside the project, is its own listed event
- **WHEN** `2024/2024-07-20 - Fest` is a symbolic link to the rendered, fresh `2024/2024-07-14 - Kalas`, the
  list shows both, and `POST /api/v1/jobs` names `2024/2024-07-20 - Fest`
- **THEN** the event is judged at the path its own id names: it is stale, because `2024-07-20 - Fest.mp4` was
  never rendered, so the response is 201 and the job's `event_dir` is `2024/2024-07-20 - Fest`

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

## MODIFIED Requirements

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
- **THEN** the shared problem body's `conflict` field is the enumeration of exactly `active_job` and
  `output_collision`, and `claimed_by` is a list of strings
- **AND** `POST /api/v1/jobs` declares its 409 and 502 responses in that shape

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
