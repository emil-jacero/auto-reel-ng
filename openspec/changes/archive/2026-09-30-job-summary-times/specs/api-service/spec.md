## ADDED Requirements

### Requirement: An event's latest job reports when it started and finished

Wherever an events response carries an event's latest job (each summary row of `GET /api/v1/events`, and
`GET /api/v1/events/{event_id}`), that job SHALL carry `started_at` and `finished_at` alongside its `id`,
`status`, `progress` and `created_at`. Both SHALL have the same value and meaning as the same-named fields of
the job's own detail (`GET /api/v1/jobs/{id}`) at the same moment:

- `started_at` SHALL be the time a worker claimed the job for its current run. It SHALL be null while the
  job is queued, including after a requeue, and for a job that was cancelled while it was queued.
- `finished_at` SHALL be the time the job reached `done`, `failed` or `canceled`. It SHALL be null while
  the job is queued or running.

Both keys SHALL always be present in the latest job, holding a time or null. A time the job store did not
record SHALL be reported as null: it MUST NOT be replaced with `created_at`, the current time, or any other
value. The list and the detail SHALL report the same times for the same event when no job changed between
the two requests.

The service's OpenAPI schema SHALL publish every field of the latest-job model exactly as it publishes the
same-named field of the job detail. The two new fields are therefore optional, nullable date-times, and a
generated client types each field identically in both places. The four existing fields SHALL keep their
names, types, required status and values, so a client that reads only them receives exactly what it
received before.

#### Scenario: A rendered event's latest job says when it ran
- **WHEN** `GET /api/v1/events` lists `2024-06-27 - Grillning med grannar`, whose latest job a worker
  rendered to `done`
- **THEN** its `latest_job` carries `created_at`, `started_at` and `finished_at`, each equal to the
  same-named field of `GET /api/v1/jobs/{id}` for that job
- **AND** `created_at` ≤ `started_at` ≤ `finished_at`

#### Scenario: A render that failed at probe reports its times on both reads
- **WHEN** `2024-10-05 - Trasig`, whose only clip is a zero-byte file, has a latest job that a worker
  claimed and that failed at probe, and the event is read through `GET /api/v1/events` and
  `GET /api/v1/events/{event_id}`
- **THEN** both reads report the same non-null `started_at` and `finished_at`, equal to the job detail's

#### Scenario: A job no worker has claimed has no start or finish time
- **WHEN** `2024/Blandat`'s latest job is `queued` and no worker is running
- **THEN** its `latest_job` has `started_at: null` and `finished_at: null`, with both keys present

#### Scenario: A job cancelled before it started is not given a start time
- **WHEN** a job for `2024-08-02 - Badutflykt - Varberg` is enqueued and cancelled before any worker
  claims it, and the events list is then read
- **THEN** that event's `latest_job` has status `canceled`, `started_at: null`, and a non-null
  `finished_at` equal to the one `GET /api/v1/jobs/{id}` reports for that job

#### Scenario: A running job has a start time until a stopped worker requeues it
- **WHEN** a worker has claimed a render of `2024-06-27 - Grillning med grannar`, and the events list is
  read
- **THEN** that event's `latest_job` has status `running`, a `started_at` equal to the job detail's, and
  `finished_at: null`
- **AND** once that worker is stopped gracefully and the job is requeued, the `latest_job` has status
  `queued`, `started_at: null` and `finished_at: null`

#### Scenario: The schema publishes the times as the job detail does
- **WHEN** the service's OpenAPI schema is generated
- **THEN** every property of the latest-job model has a definition identical to the job detail's
  same-named property, and `started_at` and `finished_at` are not required
- **AND** its required fields are exactly `id`, `status`, `progress` and `created_at`, as before
