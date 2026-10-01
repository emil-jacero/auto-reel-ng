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
