## MODIFIED Requirements

### Requirement: Jobs lifecycle over REST
The service SHALL expose the job store thinly: `POST /api/v1/jobs` enqueues an event (device optional,
default `auto`; `force` optional, default false) after applying the staleness gate — returning 201 with
the job on creation, **409 with the existing job's id** when an active job already exists for the event,
and a distinct **"fresh — not enqueued" outcome** (200 with the fresh verdict and its manifest reference)
when the event is fresh and `force` is false; a forced request always enqueues. The enqueued job carries
the event's fingerprint and the force flag. `GET /api/v1/jobs` lists jobs (filterable by status);
`GET /api/v1/jobs/{id}` returns one job's detail (status, progress, device, worker, force, fingerprint,
timestamps, error, requeue count); `POST /api/v1/jobs/{id}/cancel` invokes `request_cancel` (flag a
running job, cancel a queued one directly, no-op reported for terminal jobs). The API MUST NOT transition
job status itself.

#### Scenario: Enqueue over REST
- **WHEN** `POST /api/v1/jobs` names a stale event with no active job
- **THEN** a `queued` job row exists carrying the event's fingerprint and the response is 201 with its id

#### Scenario: Fresh event is not enqueued
- **WHEN** `POST /api/v1/jobs` names a fresh event without `force`
- **THEN** no job is created and the response reports the event as fresh

#### Scenario: Force enqueues a fresh event
- **WHEN** `POST /api/v1/jobs` names a fresh event with `"force": true`
- **THEN** a `queued` job with `force = true` is created and the response is 201

#### Scenario: Duplicate enqueue is a visible conflict
- **WHEN** `POST /api/v1/jobs` names a stale event that already has a `queued` or `running` job
- **THEN** the response is 409 carrying the existing job's id and no new row is inserted

#### Scenario: Cancel a running job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets a `running` job
- **THEN** the job's `cancel_requested` flag is set, its status is unchanged, and the response reports the
  request was recorded

### Requirement: Events read model is scanned from disk per request
`GET /api/v1/events` SHALL enumerate events by walking the configured ingest layout at request time, and
`GET /api/v1/events/{event_id}` SHALL parse the event's current `reel.yaml` (seeding metadata from the
folder name when absent, as `scan` does) — returning metadata, ordered chapters/clips, reconcile state
(NEW/MISSING), and the event's **staleness verdict** (fresh, or stale with the changed components as
reasons, from the staleness gate and render manifest). The event identity in URLs SHALL be the
root-relative event directory (URL-encoded). The service MUST NOT maintain a database copy of event or
clip state, and responses MUST reflect disk changes made since any previous request. Events reads SHALL be
read-only: no request may create or modify `reel.yaml` or the render manifest.

#### Scenario: Disk edit is visible on the next request
- **WHEN** an event's `reel.yaml` title is edited on disk after a previous GET
- **THEN** the next `GET /api/v1/events/{event_id}` returns the new title

#### Scenario: Staleness is part of the event detail
- **WHEN** an event's clips changed since its last render
- **THEN** `GET /api/v1/events/{event_id}` reports it stale citing the clip-set component

#### Scenario: Event identity round-trips with spaces and non-ASCII characters
- **WHEN** an event directory is named `2024/2024-06-21 - Midsommar i Dalarna`
- **THEN** the URL-encoded id returned by the list endpoint fetches that event's detail

#### Scenario: Unknown event yields 404
- **WHEN** `GET /api/v1/events/{event_id}` names a directory that does not exist under the root
- **THEN** the response is 404 with a problem body

#### Scenario: Scan failure is loud, never fabricated
- **WHEN** an event's `reel.yaml` is unparseable
- **THEN** the response is an error naming the failing event, not an empty or partial success
