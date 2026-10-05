## MODIFIED Requirements

### Requirement: Job kind is a closed, published vocabulary
Every job the service reports SHALL carry its `kind`, drawn from the job store's closed set of job kinds:
`render`, `proxy` and `analysis`. `kind` SHALL be present, non-null and **required** wherever the service describes a job: in
the job detail (`GET /api/v1/jobs/{id}`), in each item of the jobs list, in the job the enqueue returns, in the
latest-job summary that the events list rows and the event detail carry, and in every job of a WebSocket frame.
`GET /api/v1/jobs` lists the served project's jobs of every kind, each marked, and the job detail answers for a
job of any of them. It SHALL have the same value for the same job in all of them. The service's OpenAPI schema SHALL publish the set
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
- **THEN** the job's `kind` is described as the enumeration `render`, `proxy`, `analysis`, is in the job detail's `required`
  list and in the latest-job model's, and the two definitions are identical
- **AND** a client generated from it that handles every kind exhaustively fails to compile until it handles
  `proxy` and `analysis`

#### Scenario: An analysis job says it is an analysis job on every read
- **WHEN** `auto-reel analyze --enqueue` queued an analysis job for `2024/Blandat`, and it is read through
  `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs` and a WebSocket frame while it runs
- **THEN** all three carry `kind: "analysis"` and `event_dir` `2024/Blandat`, and the event's `latest_job` on
  `GET /api/v1/events` is still its latest render (or null when it has none)
