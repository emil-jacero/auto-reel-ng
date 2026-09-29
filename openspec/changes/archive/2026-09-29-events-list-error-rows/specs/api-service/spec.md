## MODIFIED Requirements

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

The list SHALL NOT degrade otherwise: a request that cannot account for every walked event SHALL fail
rather than return a partial list, a list with the unavailable facts omitted, or a list with substituted
values. An unreachable job store fails the whole list, because every summary's latest job depends on it.
A walk of the project root that fails SHALL be reported as the scan-failure problem body, never an unshaped
error. Absence is reported, never fabricated, and a client is never left to guess whether a missing fact
means "none" or "could not be read".

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
- **THEN** the detail route returns the 404 and 502 problem bodies it already returns, unchanged

#### Scenario: A healthy read is unaffected
- **WHEN** the database is reachable and every event scans cleanly
- **THEN** both reads respond as before, except that each list row also states that it is an event summary;
  there is no added envelope and no new status code

#### Scenario: The schema publishes the problem responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the events list declares its 502 and 503 responses and the detail declares its 404, 502 and
  503 responses, each described by the shared problem body shape rather than left undeclared

#### Scenario: A returned problem body matches the published shape
- **WHEN** the database is down and a client requests the events list
- **THEN** the 503 body it receives validates against the published problem shape, including the field
  naming the database as the failing dependency

#### Scenario: The schema publishes the error row
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the list's item is a union of the summary and the error row discriminated by their kind field,
  and the failure kind is an enumeration of the three kinds
