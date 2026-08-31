# api-service Specification

## Purpose

Expose a thin HTTP/WebSocket API service that lets remote clients observe and edit project state and
drive the job queue without duplicating engine logic: a read-only events view scanned from disk per
request (as `scan` does), read-only cached analysis results, a whole-document editorial write that
persists an event's `reel.yaml`, a REST lifecycle over the job store (enqueue, list, detail, cancel),
live job updates over WebSocket, a health endpoint, and an auth seam ready for a future bearer-token
check. Every endpoint maps to an operation the CLI can also reach; the service itself contains no
scan, render, editorial, or job logic of its own.

## Requirements

### Requirement: Service configuration and thin-layer constraint
The API service SHALL be built by an application factory from explicit settings — project root, ingest
layout, bind host/port, database URL (via the existing resolution), and poll interval — resolved through
the D-2 layering (`api.host` / `api.port` / `api.poll_interval` in `config.yaml`, flags/env override,
default bind `127.0.0.1:8080`). Every endpoint SHALL map to an operation the CLI can also reach; the API
MUST NOT contain scan, render, or job logic of its own.

#### Scenario: Factory serves a configured project root
- **WHEN** the app is created with a project root and layout
- **THEN** its event endpoints serve exactly the events the CLI's `scan` reports for that root and layout

#### Scenario: Default bind is localhost
- **WHEN** `api.host` is not configured
- **THEN** the service binds `127.0.0.1` and widening the bind requires explicit configuration

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

### Requirement: Analysis results are exposed read-only
`GET /api/v1/events/{event_id}/analysis` SHALL return the event's cached analysis segments from the
existing sidecar cache, and SHALL distinguish "no analysis has been run" from "analysis ran and found
nothing". It MUST NOT trigger analysis.

#### Scenario: Cached analysis is returned
- **WHEN** an event has a populated analysis sidecar cache
- **THEN** the endpoint returns its segments per clip

#### Scenario: Absent cache is not an empty result
- **WHEN** an event has never been analyzed
- **THEN** the response indicates analysis is absent (not an empty segment list)

### Requirement: Editorial write endpoint
The service SHALL expose `PUT /api/v1/events/{event_id}/reel`, accepting the full desired editorial state
for the event (metadata, ordered chapters and their clips, per-clip properties, `ignore`, and the `look`
override) and delegating to the engine's editorial-write operation. The endpoint MUST contain no editorial
logic of its own: it parses and validates the request shape, calls the operation, and maps outcomes to
responses. The response SHALL echo the persisted document together with the event's resulting staleness
verdict, so a client needs no follow-up read. Unknown events SHALL yield 404; a rejected state SHALL yield a
validation problem body and leave `reel.yaml` unchanged. Read endpoints remain read-only and unaffected.

#### Scenario: Save persists and echoes
- **WHEN** `PUT /api/v1/events/{event_id}/reel` sends a state with a changed title and clip order
- **THEN** the event's `reel.yaml` reflects it, and the response echoes the persisted document with the
  event's new staleness verdict

#### Scenario: Save makes the event stale over the API
- **WHEN** a previously fresh event is saved via the write endpoint
- **THEN** the response's verdict — and a subsequent `GET /api/v1/events/{event_id}` — report it stale
  citing the editorial component, while no job has been created

#### Scenario: Invalid state is rejected loudly
- **WHEN** the submitted state fails validation
- **THEN** the response is a validation problem body naming the offending part, and the event's `reel.yaml`
  is unchanged

#### Scenario: Unknown event
- **WHEN** the endpoint targets an event id that does not resolve under the configured project root
- **THEN** the response is 404 with a problem body

#### Scenario: Saving an unmodified document is a no-op
- **WHEN** the document echoed by the write endpoint is submitted back unmodified via the write endpoint
- **THEN** the persisted `reel.yaml` is byte-for-byte unchanged, and the response echoes the same document
  again (the write endpoint's read and write models are the same shape; the read endpoints' detail model
  stays read-only and is deliberately not a write body)

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

### Requirement: WebSocket live job updates
The service SHALL expose `WS /api/v1/ws/jobs`. On connect a subscriber SHALL immediately receive a full
snapshot of active (`queued`/`running`) jobs; thereafter it SHALL receive delta messages for job progress
and status changes — including terminal transitions — observed by a central poller that queries the store
at the configured interval (default 1 s). The poller SHALL run only while at least one subscriber is
connected. A subscriber that cannot keep up (full outbound queue) SHALL be disconnected rather than
back-pressuring the hub; its recovery path is reconnect-and-resnapshot.

#### Scenario: Snapshot on connect
- **WHEN** a client connects while two jobs are active
- **THEN** its first message is a snapshot containing both jobs' current status and progress

#### Scenario: Progress and completion are pushed
- **WHEN** a running job's stored progress advances and the job later transitions to `done`
- **THEN** subscribers receive delta messages for the progress change and for the terminal transition
  within approximately one poll interval each

#### Scenario: Idle service does not poll
- **WHEN** no WebSocket subscriber is connected
- **THEN** the central poller issues no store queries

### Requirement: Health endpoint
`GET /healthz` SHALL report service liveness and database reachability, returning non-success when the
database cannot be reached.

#### Scenario: Healthy service
- **WHEN** the service is up and the database is reachable
- **THEN** `/healthz` returns success

#### Scenario: Database outage is reported
- **WHEN** the database is unreachable
- **THEN** `/healthz` returns a non-success status naming the database check

### Requirement: Auth seam without auth
The service SHALL provide a single middleware hook point where a bearer-token check can later be
registered via configuration, and SHALL apply no authentication by default. Adding a token MUST NOT
require restructuring routes.

#### Scenario: v1 is open on localhost
- **WHEN** the service runs with default settings
- **THEN** requests require no credentials

#### Scenario: Token check is a drop-in
- **WHEN** a token check is registered at the hook point (as tests do)
- **THEN** requests without the token are rejected and no route code changes
