## ADDED Requirements

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
