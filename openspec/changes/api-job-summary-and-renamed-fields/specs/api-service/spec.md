## MODIFIED Requirements

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

## ADDED Requirements

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
