## ADDED Requirements

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

## MODIFIED Requirements

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
