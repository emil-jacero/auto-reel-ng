## MODIFIED Requirements

### Requirement: Analysis results are exposed read-only
`GET /api/v1/events/{event_id}/analysis` SHALL return the event's cached analysis segments from the
existing sidecar cache, and SHALL distinguish "no analysis has been run" from "analysis ran and found
nothing". It MUST NOT trigger analysis.

The response SHALL carry the event's analysis `state` and, in `clips`, one entry per clip file the event's folder
lists (the clips the analysis job walks, ignored and excluded ones included) with that clip's `state`, both drawn
from the vocabulary of "Analysis state is a closed, published vocabulary" and both required. A clip whose state is
`failed` SHALL carry the failure's message in `detail` when the recorded failure has one, else `detail` is null.
While the event has a `queued` or `running` job of kind `analysis`, the response SHALL carry that job in `job`, in
the shape the jobs routes return (`JobOut`, with its `progress`), and `job` SHALL be null otherwise. The states
SHALL be the ones the analysis cache's state rule gives for the clips as they are on disk, read by `stat` and JSON
only: the request MUST NOT start a process, probe or decode a clip, or write anything. The `analyzed` field SHALL
keep its existing value and is legacy; a client SHALL read `state` instead. The `segments` field is unchanged: a
clip's segments are present exactly when its cache entry is valid for the clip as it is now.

The endpoint SHALL answer only for an event the events list shows. `event_id` SHALL be judged by the same
rule as the thumbnail and media endpoints: a folder the events list does not show as an event, such as the
project root, a year folder, an event's `original/` or chapter folder, or a `.reelignore`d event, is
answered 404 with a problem body naming the event, exactly as an unknown id is, and nothing under it is
read. The endpoint SHALL NOT read `reel.yaml`: analysis is a fact of the sidecar cache and the clip files,
so an event whose document is broken still answers for its cache.

A failure that is not the request's fault SHALL be a shaped 502 problem body naming the event, never an
unshaped server error: an event whose folder cannot be listed carries the unreadable-disk failure kind the
events reads use, and a layout the service cannot resolve carries no failure kind; a clip that cannot be statted or
a cache entry that exists but cannot be read (as distinct from one that is absent) is a 502 with no failure kind,
and is never reported as `never`. Because `analyzing` is a fact of the job store, a job store that cannot be reached
SHALL be the 503 problem body naming the database (`check` `database`) that the jobs routes give, never a state
reported without it. The service's OpenAPI schema SHALL declare the endpoint's 404, 502 and 503 in the shared
problem body shape.

#### Scenario: Cached analysis is returned
- **WHEN** an event has a populated analysis sidecar cache
- **THEN** the endpoint returns its segments per clip

#### Scenario: Absent cache is not an empty result
- **WHEN** an event has never been analyzed
- **THEN** the response indicates analysis is absent (not an empty segment list): `state` is `never` and every
  clip's `state` is `never`

#### Scenario: A render manifest does not make an event look analyzed
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has been rendered (its `.auto-reel/cache/` holds
  `render-manifest.json`) but no clip has an analysis entry
- **THEN** `state` is `never` and every clip reads `never`, whatever the legacy `analyzed` says

#### Scenario: A changed clip is stale, not never
- **WHEN** an event's three clips were analyzed and one of them was then replaced (new size and mtime)
- **THEN** `state` is `stale`, that clip reads `stale` and has no `segments` entry, and the other two read
  `current` with their segments

#### Scenario: A new clip makes the event stale
- **WHEN** an analyzed event gains a fourth clip file
- **THEN** `state` is `stale` and the new clip reads `never`

#### Scenario: A failed clip is reported with its reason
- **WHEN** the analysis job of `2024/Blandat` recorded a failure for `broken.mp4` under its current signal and
  analyzed the other clips
- **THEN** `state` is `failed`, `broken.mp4` reads `failed` with the recorded message in `detail`, and the others
  read `current`

#### Scenario: A running job is reported with its progress
- **WHEN** a `running` analysis job for the event holds progress 0.4 and two of its five clips are `current`
- **THEN** `state` is `analyzing`, `job` is that job with `kind` `analysis` and `progress` 0.4, the two clips read
  `current` and the three others read `analyzing`

#### Scenario: A forced job leaves current clips current
- **WHEN** a forced analysis job is `queued` for an event whose clips are all `current`
- **THEN** `state` is `analyzing`, `job` is that job, and every clip still reads `current` with its segments

#### Scenario: Reading the state starts nothing
- **WHEN** the analysis of an event with stale and never-analyzed clips is read
- **THEN** no ffmpeg or ffprobe process is started, no file is written, and no job is created

#### Scenario: A year folder is not an event
- **WHEN** a client requests `GET /api/v1/events/2024/analysis` for a year folder that holds events
- **THEN** the response is 404 with a problem body naming `2024`, not a 200 saying nothing was analyzed

#### Scenario: An event's original folder is not an event
- **WHEN** a client requests the analysis of `2024/2024-06-21 - A/original`, a directory inside a listed
  event
- **THEN** the response is 404, the same answer the thumbnail endpoint gives for that folder

#### Scenario: A reelignored event is not an event
- **WHEN** a client requests the analysis of an event folder carrying a `.reelignore`
- **THEN** the response is 404, because the events list does not show it

#### Scenario: A broken reel.yaml does not hide the cache
- **WHEN** a listed event's `reel.yaml` cannot be parsed and its sidecar cache holds segments
- **THEN** the analysis endpoint returns those segments, because it never reads the document

#### Scenario: An event whose folder cannot be listed is a 502
- **WHEN** the listed event's directory cannot be read and a client requests its analysis
- **THEN** the response is the scan-failure problem body naming the event with the unreadable-disk failure
  kind, and never an unshaped server error

#### Scenario: An unreadable cache entry is a 502, not never
- **WHEN** a clip's cache entry file exists but cannot be read (permission denied)
- **THEN** the response is a 502 problem body with no failure kind, never a 200 reporting that clip `never`

#### Scenario: An unresolvable layout is a 502 without a kind
- **WHEN** the configured ingest layout name is not one the service knows and a client requests an
  analysis
- **THEN** the response is a 502 problem body naming the event whose detail names the layout, with no
  failure kind

#### Scenario: The job store is down
- **WHEN** the database is unreachable and the analysis of `2024/Blandat` is read
- **THEN** the response is 503 with `check` `database`, and no state is reported

#### Scenario: The schema publishes the analysis problem responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the analysis endpoint declares its 404, 502 and 503 responses in the shared problem body shape, and
  its 200 model has `state` and `clips` in its `required` list and a nullable `job`

### Requirement: Job kind is a closed, published vocabulary
Every job the service reports SHALL carry its `kind`, drawn from the job store's closed set of job kinds:
`render`, `proxy` and `analysis`. `kind` SHALL be present, non-null and **required** wherever the service describes a job: in
the job detail (`GET /api/v1/jobs/{id}`), in each item of the jobs list, in the job an enqueue returns, in the
latest-job summary that the events list rows and the event detail carry, in the active job the analysis read
carries, and in every job of a WebSocket frame.
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
received before. An analysis job SHALL be reported, followed over the WebSocket and cancelled exactly as a proxy job
is, and SHALL never stand in an event's `latest_job`.

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
- **WHEN** an analysis job for `2024/Blandat` was queued (by `auto-reel analyze --enqueue` or the analysis enqueue),
  and it is read through `GET /api/v1/jobs/{id}`, `GET /api/v1/jobs`, the analysis read of the event and a
  WebSocket frame while it runs
- **THEN** all four carry `kind: "analysis"` and `event_dir` `2024/Blandat`, and the event's `latest_job` on
  `GET /api/v1/events` is still its latest render (or null when it has none)

## ADDED Requirements

### Requirement: Analysis state is a closed, published vocabulary
The analysis state of an event and of a clip SHALL be one of `never` (no analysis result or recorded failure exists
for any version of the clip, or of any clip of the event), `stale` (some clip has no valid result for the file as it
is now but other results exist, or a clip changed since it was analyzed or failed), `current` (every clip has a valid
result for the file as it is now; also an event with no clips), `analyzing` (an analysis job for the event is
`queued` or `running`) and `failed` (no clip needs analysis, and at least one clip's analysis failed for the file as
it is now). The service's OpenAPI schema SHALL publish it as one enumeration used by the event's and every clip's
`state`.

#### Scenario: The schema publishes the analysis state set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the event's `state` and each clip's `state` reference one enumeration `never`, `stale`, `current`,
  `analyzing`, `failed`

#### Scenario: An event with no clips is current
- **WHEN** an event folder holds no clip files and its analysis is read
- **THEN** `state` is `current` and `clips` is empty

### Requirement: An event's analysis is enqueued by a job the service enqueues
The service SHALL expose `POST /api/v1/events/{event_id}/analysis`, with an optional JSON body `{force: bool}`
(absent body or field = `false`), which enqueues the event's job of kind `analysis` with the enqueue's semantics:

- **201** with the job in the shape `POST /api/v1/jobs` returns (`JobOut`), `kind` `analysis`, `status` `queued`,
  `event_dir` the event's id exactly as the events list shows it, `force` as requested and `fingerprint` null. A 201
  SHALL mean this request created the job, decided by the store at insertion.
- **200 "fresh"**, a named model with the required constant `status` `fresh`, the event id, `clip_count` (the clip
  files the event's folder lists) and `failed_count` (how many of them read `failed`), when `force` is false and no
  clip reads `never` or `stale`; and, whatever `force` says, when the folder lists no clip files. No job is created.
- **409** with the shared problem body, `conflict` `active_job` and `job_id` the active analysis job's id, when one
  is `queued` or `running` for the event, found beforehand or at insertion (never a 201), whatever `force` says. A
  forced request that meets a `queued` job without `force` SHALL give that job `force` before answering, as
  `auto-reel analyze <root> --enqueue --force` does, so a Re-analyze is not lost behind a queued unforced job; a
  `running` job is left as it is. The body SHALL carry `forced`, whether the active job carries `force` after the
  request (as the CLI's "already running without --force" note tells), so a Re-analyze that took effect and one
  lost behind a `running` unforced job never answer alike.
- **404** with the shared problem body naming the event in `event_id`, for an id the events list does not show.
- **502** with the shared problem body: for an event folder that cannot be listed, naming `event_id` and the
  `unreadable_disk` failure kind; and, with no kind, for a clip or a cache entry that cannot be read. Nothing is
  enqueued.
- **503** with the shared problem body naming the database (`check` `database`) when the job store is unreachable.

The checks SHALL run in this order: the event (404, 502), the active analysis job (409), the clips' states (502),
freshness (200), then the insertion (201, or the 409 of a lost race). The clips counted and the states read SHALL
be the ones the analysis read reports for the event; `reel.yaml` is never read, so an unparseable or untitled
document does not refuse the request. The request MUST NOT start a process, probe, decode or write anything but the
job row: in particular a forced request does not remove a recorded failure itself; the forced job analyzes every
clip, overriding results and recorded failures, when it runs. The job SHALL be inserted through the same enqueue
function `auto-reel analyze <root> --enqueue` uses. The service's OpenAPI schema SHALL publish every one of
these responses and the request body. The route SHALL be registered before the greedy event detail route and answer
for event ids that contain `/`.

#### Scenario: Analyze an event that was never analyzed
- **WHEN** `POST /api/v1/events/2024/2024-06-27 - Grillning med grannar/analysis` is sent with no body for an event
  whose three clips read `never`, with no active analysis job
- **THEN** the response is 201 with a job whose `kind` is `analysis`, `status` `queued`, `event_dir`
  `2024/2024-06-27 - Grillning med grannar`, `force` false and `fingerprint` null
- **AND** one `queued` analysis row exists, no file was written, and no ffmpeg or ffprobe process was started

#### Scenario: An analyzed event is fresh
- **WHEN** the request names `2023/2023-06-23 - Midsommar - Dalarna`, whose four clips read `current`
- **THEN** the response is 200 with `status` `fresh`, `clip_count` 4, `failed_count` 0, and no job exists

#### Scenario: A failed clip alone does not re-enqueue
- **WHEN** `2024/Blandat` has two `current` clips and one `failed`, and the request has no body
- **THEN** the response is 200 `fresh` with `clip_count` 3 and `failed_count` 1, and no job exists

#### Scenario: Re-analyze forces a job
- **WHEN** the same request for `2024/Blandat` carries `{"force": true}`
- **THEN** the response is 201 with a `queued` analysis job whose `force` is true, and the recorded failure is still
  on disk when the response is sent

#### Scenario: A stale clip makes the event enqueue
- **WHEN** one of an analyzed event's clips was replaced since its analysis, and the request has no body
- **THEN** the response is 201

#### Scenario: A repeated request is a conflict
- **WHEN** the request is sent again, with or without `force`, while the first job is `queued` or `running`
- **THEN** the response is 409 with `conflict` `active_job` whose `job_id` is the first job's id and `forced` false,
  and no new row is inserted

#### Scenario: An enqueue that loses a race is a conflict
- **WHEN** two requests for `2024/Blandat` both pass the active-job check before either inserts
- **THEN** exactly one response is 201, the other is 409 `active_job` naming the job the 201 returned, and one
  analysis row exists

#### Scenario: Forcing an event with no clips creates nothing
- **WHEN** `{"force": true}` names an event whose folder holds no clip files
- **THEN** the response is 200 `fresh` with `clip_count` 0, and no job exists

#### Scenario: Unknown event
- **WHEN** the request names `2024/2024-12-24 - Finns inte`, which the events list does not show
- **THEN** the response is 404 naming the event in `event_id`, and nothing is enqueued

#### Scenario: An event folder that cannot be listed
- **WHEN** the request names an event whose folder cannot be listed (permission denied)
- **THEN** the response is 502 with `event_id` and `failure` `unreadable_disk`, and nothing is enqueued

#### Scenario: An unusable reel.yaml does not block analysis
- **WHEN** the request names `2024/2024-10-06 - Trasig reel`, whose `reel.yaml` does not parse
- **THEN** the response is 201 (or 200 `fresh`), not an error

#### Scenario: The job store is down
- **WHEN** the database is unreachable and the request names `2024/Blandat`
- **THEN** the response is 503 with `check` `database`

#### Scenario: Re-analyze meets a queued unforced job
- **WHEN** an unforced analysis job is `queued` for `2024/Blandat` and the request carries `{"force": true}`
- **THEN** the response is 409 `active_job` naming that job with `forced` true, the job's `force` is now true, and
  one analysis row exists

#### Scenario: Re-analyze meets a running unforced job
- **WHEN** an unforced analysis job is `running` for `2024/Blandat` and the request carries `{"force": true}`
- **THEN** the response is 409 `active_job` naming that job with `forced` false, and its `force` stays false

#### Scenario: The schema publishes the analysis enqueue
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the route declares its optional request body with `force`, its 201 job, its 200 result (a named model
  whose `status` is the required constant `fresh` and which has `clip_count` and `failed_count`), and its 404, 409,
  502 and 503 problem bodies

### Requirement: Every event that needs analysis is enqueued in one request
The service SHALL expose `POST /api/v1/analysis`, taking no body, which considers every event the events list shows,
in the order it shows them, and for each: counts it `active` when an analysis job is `queued` or `running` for it
(also when one is found at insertion); records it in `unreadable` (`event_id`, `detail` and the events list's
`failure` kind, null when there is none) when its folder, a clip or a cache entry cannot be read; counts it `fresh`
when no clip reads `never` or `stale`; and otherwise enqueues its analysis job, unforced, with the store's
insertion, and counts it `queued`. The response SHALL be 200 with a named model holding the required integers
`queued`, `fresh` and `active` and the required list `unreadable`. One event that cannot be read SHALL NOT prevent
the others from being considered. A project walk that fails SHALL be a 502 problem body with nothing enqueued, and
an unreachable job store a 503 naming the database; jobs inserted before the store failed stay queued, so a repeated
request counts them `active`. The request MUST NOT start a process, probe, decode, read `reel.yaml`, or write
anything but job rows; it SHALL insert each job through the same enqueue function `auto-reel analyze <root>
--enqueue` uses, with the analysis cache's state rule deciding freshness.

#### Scenario: Analyze all queues what needs it
- **WHEN** the project shows four events: one `never`, one `stale`, one `current`, and one with a `running` analysis
  job, and `POST /api/v1/analysis` is sent
- **THEN** the response is 200 with `queued` 2, `fresh` 1, `active` 1 and an empty `unreadable`, and exactly two new
  `queued` analysis rows exist, both with `force` false

#### Scenario: A repeat finds the jobs it queued
- **WHEN** the same request is sent again before the worker claims anything
- **THEN** the response is 200 with `queued` 0, `fresh` 1, `active` 3, and no new row exists

#### Scenario: One unreadable event costs only itself
- **WHEN** one of the events' folders cannot be listed and another needs analysis
- **THEN** the response is 200, `unreadable` holds the first with `failure` `unreadable_disk`, and the second is
  queued

#### Scenario: Ignored folders are not considered
- **WHEN** the project holds a `.reelignore`d event folder with never-analyzed clips
- **THEN** no job is created for it and it appears in no count

#### Scenario: A failed walk queues nothing
- **WHEN** the configured ingest layout cannot be resolved
- **THEN** the response is a 502 problem body and no row is inserted

#### Scenario: The schema publishes Analyze all
- **WHEN** the service's OpenAPI schema is generated
- **THEN** `POST /api/v1/analysis` declares no request body, its 200 result model with `queued`, `fresh`, `active`
  and `unreadable` required, and its 502 and 503 problem bodies

### Requirement: An analysis job and the jobs of other kinds of one event do not block each other
An event SHALL have at most one `queued` or `running` job of kind `analysis`, independently of its render and proxy
jobs. An active analysis job SHALL NOT make the render enqueue or the proxy enqueue a 409, and an active render or
proxy job SHALL NOT make the analysis enqueue a 409. `POST /api/v1/jobs/{id}/cancel` SHALL act on an analysis job
with the store's cancel and report its outcome as for a render; cancelling it leaves the event's other jobs
untouched.

#### Scenario: A running render does not block analysis
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has a `running` render and never-analyzed clips, and the
  analysis enqueue names it
- **THEN** the response is 201 with a `queued` analysis job, and the render is unchanged

#### Scenario: An active analysis job does not block a render or proxies
- **WHEN** the event has a `queued` analysis job, and the render enqueue and the proxy enqueue name it with work to do
- **THEN** both answer 201 with jobs of their own kind

#### Scenario: Cancel a queued analysis job
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the `queued` analysis job of `2024/Blandat`
- **THEN** the outcome is `canceled-queued`, and the event's render and proxy jobs are unchanged
