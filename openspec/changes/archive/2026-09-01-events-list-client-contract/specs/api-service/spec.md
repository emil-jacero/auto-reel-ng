## ADDED Requirements

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
