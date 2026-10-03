## ADDED Requirements

### Requirement: Job kind is a closed, published vocabulary
Every job the service reports SHALL carry its `kind`, drawn from the job store's closed set of job kinds:
`render` and `proxy`. `kind` SHALL be present, non-null and **required** wherever the service describes a job: in
the job detail (`GET /api/v1/jobs/{id}`), in each item of the jobs list, in the job the enqueue returns, in the
latest-job summary that the events list rows and the event detail carry, and in every job of a WebSocket frame.
`GET /api/v1/jobs` lists the served project's jobs of every kind, each marked, and the job detail answers for a
job of either. It SHALL have the same value for the same job in all of them. The service's OpenAPI schema SHALL publish the set
as an enumeration rather than as a free-form string, so a client can derive an exhaustive type, and removing or
renaming a value is a compile-time failure in generated client code rather than a silent runtime change (D-8,
§4.10); the latest-job model's `kind` SHALL be defined exactly as the job detail's.

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

#### Scenario: The schema publishes the kind set
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the job's `kind` is described as the enumeration `render`, `proxy`, is in the job detail's `required`
  list and in the latest-job model's, and the two definitions are identical
- **AND** a client generated from it that handles every kind exhaustively fails to compile until it handles
  `proxy`

### Requirement: An event's latest job is its latest render job
Wherever an events response carries an event's latest job (each summary row of `GET /api/v1/events`, and
`GET /api/v1/events/{event_id}`), that job SHALL be the newest job of kind `render` for the event, whatever its
status. A job of any other kind SHALL NOT appear there, however recent: a queued, running, finished or failed
proxy job for the event leaves `latest_job` as it was, and an event whose only jobs are proxy jobs reports
`latest_job: null`. The proxy side of an event is read from its clips' `proxy` state and, while a job runs, from
the jobs WebSocket.

#### Scenario: A newer proxy job does not replace the render
- **WHEN** `2024/2024-06-27 - Grillning med grannar`'s `done` render finished at 10:00 and a proxy job for it
  was created at 10:05 and is `running`, and the events list and the event detail are read
- **THEN** both reads' `latest_job` is the 10:00 render, `kind: "render"`, status `done`

#### Scenario: An event with only a proxy job has no latest job
- **WHEN** the only job `2024/Blandat` has ever had is a `done` proxy job, and the events list is read
- **THEN** its row's `latest_job` is null, as for an event never rendered

#### Scenario: A finished proxy job does not make a render look done
- **WHEN** `2024/Blandat`'s newest render is `failed` and a proxy job created after it is `done`
- **THEN** its `latest_job` is the `failed` render

### Requirement: An event's proxies are prepared by a job the service enqueues
The service SHALL expose `POST /api/v1/events/{event_id}/proxies`, taking no request body, which enqueues the
event's proxy job (the job `kind: proxy` of "Job kind is a closed, published vocabulary", whose work is
`proxy-job`'s) with the enqueue's semantics:

- **201** with the job in the shape `POST /api/v1/jobs` returns (`JobOut`), `kind` `proxy`, `status` `queued`,
  `event_dir` the event's id exactly as the events list shows it, `force` false and `fingerprint` null. A 201
  SHALL mean this request created the job; whether a job was created SHALL be decided by the store at insertion,
  never by an earlier read.
- **200 "fresh - not enqueued"**, with `status` the constant `fresh`, the event id and `clip_count`, when every
  clip the event's folder holds already has a proxy whose state is `ready`. No job is created. `clip_count` is
  the number of those clips and is 0 for an event whose folder holds none; the response then says so rather than
  implying anything was checked.
- **409** with the shared problem body, `conflict` `active_job` and `job_id` the active job's id, when a proxy
  job is already `queued` or `running` for the event: found beforehand, or found at insertion when a concurrent
  request created it (never a 201). The `conflict` value is the one the enqueue's published enumeration already
  has; no other conflict is possible, because a proxy job has no output path and a missing clip is not a reason
  to refuse (below).
- **404** with the shared problem body naming the event in `event_id`, for an id the events list does not show,
  spelled as it spells it.
- **502** with the shared problem body: for an event folder that cannot be listed, naming `event_id` and the
  `failure` kind the events list's error row gives that failure (`unreadable_disk`); and, with no kind, for a
  proxy cache or `proxies` configuration that cannot be used, for a clip that cannot be statted for its cache
  key, and for a project walk that fails. Nothing is enqueued, and the proxy state of a clip that cannot be read
  is never taken as `absent` or `ready`.
- **503** with the shared problem body naming the database (`check` `database`) when the job store is
  unreachable, exactly as the jobs routes answer it.

The checks SHALL run in this order: the event (404, 502), then the active proxy job (409), then freshness (200),
then the insertion (201, or the 409 of a lost race). An event with a proxy job already active is therefore
answered by following that job, whether or not its proxies are ready. The clips an event's proxy job prepares
SHALL be the ones the 200 counts: every clip file the event's folder lists on disk (the listing the proxy job
walks), whatever `reel.yaml` says of it (ignored or excluded clips included), and nothing `reel.yaml` lists that is
not on disk. `reel.yaml` is never read: editorial state can neither add work nor make the request refuse. The state
of each clip SHALL be the one the event detail reports in its `proxy` field (the same function of the clip file
and the proxy settings), read by `stat` and JSON only: the request MUST NOT start a process, probe a clip,
encode, or write anything but the job row. Only a clip whose proxy is `ready` counts as ready; `absent`,
`stale` and `failed` each make the request enqueue, so a repeated request re-attempts a failed clip.

An event whose `reel.yaml` does not parse, or whose metadata is unusable (no real date or title), is not refused:
a proxy is a function of the clip file, and the proxy job does not read `reel.yaml` either.

The service's OpenAPI schema SHALL publish every one of these responses, each problem body using the shared
shape, and the 200 body as a named model whose `status` is a required constant. The route SHALL be registered
before the greedy event detail route and answer for event ids that contain `/`.

#### Scenario: Enqueue proxies for an unprepared event
- **WHEN** `POST /api/v1/events/2024/2024-06-27 - Grillning med grannar/proxies` is sent for an event
  whose three clips have no cache entries, and it has no active proxy job
- **THEN** the response is 201 with a job whose `kind` is `proxy`, `status` `queued`, `event_dir` is
  `2024/2024-06-27 - Grillning med grannar`, `force` is false and `fingerprint` is null
- **AND** one `queued` proxy row exists, no file was written to the proxy cache, and no ffmpeg or ffprobe
  process was started

#### Scenario: A repeated request is a conflict, not a second job
- **WHEN** the same `POST .../proxies` is sent again while the first job is `queued` or `running`
- **THEN** the response is 409 with `conflict` `active_job` whose `job_id` is the first job's id, and no new row
  is inserted

#### Scenario: An enqueue that loses a race is a conflict, not a creation
- **WHEN** two `POST .../proxies` requests for `2024/Blandat` both pass the active-job check before either
  inserts
- **THEN** exactly one response is 201, the other is 409 with `conflict` `active_job` whose `job_id` is the job
  the 201 returned, and one proxy row exists

#### Scenario: A prepared event is fresh
- **WHEN** `POST .../proxies` names `2023/2023-06-23 - Midsommar - Dalarna`, all four of whose clips have a
  `ready` proxy
- **THEN** the response is 200 with `status` `fresh`, the event id and `clip_count` 4, and no job exists

#### Scenario: One stale or failed proxy makes the event enqueue
- **WHEN** the same event has three `ready` proxies and one whose entry was made under other proxy settings
  (`stale`), or whose last attempt failed (`failed`)
- **THEN** the response is 201 with a `queued` proxy job

#### Scenario: A clip that is not on disk is not a reason to refuse
- **WHEN** `2024/Blandat`'s `reel.yaml` lists `gone.mp4`, which is absent from disk, and its two clips on disk have
  `ready` proxies
- **THEN** the response is 200 `fresh` with `clip_count` 2
- **AND** with one of the clips on disk `absent`, the response is 201

#### Scenario: An ignored or excluded clip is prepared with the others
- **WHEN** `2024/Blandat` has a clip its `reel.yaml` ignores and one it excludes, both `absent`, and its other
  clips are `ready`
- **THEN** the response is 201, and with those two `ready` as well it is 200 `fresh` counting them

#### Scenario: An event with no clips on disk
- **WHEN** `POST .../proxies` names an event whose folder holds no clip files
- **THEN** the response is 200 `fresh` with `clip_count` 0, and no job is created

#### Scenario: An active job is answered before freshness
- **WHEN** `2024/Blandat` has a `running` proxy job and every one of its clips is `ready`
- **THEN** `POST .../proxies` answers 409 `active_job` with that job's id, not 200

#### Scenario: Unknown event
- **WHEN** `POST /api/v1/events/2024/2024-12-24 - Finns inte/proxies` names a directory that is not
  under the project root
- **THEN** the response is 404 with the shared problem body naming the event in `event_id`, and nothing is
  enqueued

#### Scenario: An event folder that cannot be listed
- **WHEN** `POST .../proxies` names `2024/2024-06-27 - Grillning med grannar`, whose folder cannot be listed
  (permission denied)
- **THEN** the response is 502 with the shared problem body whose `event_id` is that id and whose `failure` is
  `unreadable_disk`, the kind the events list gives that failure, and nothing is enqueued

#### Scenario: A proxy cache that cannot be read is not read as absent
- **WHEN** the proxy cache directory exists but cannot be listed (permission denied) and
  `POST .../proxies` names `2024/Blandat`
- **THEN** the response is 502 with no `failure` kind, and no job row exists

#### Scenario: The job store is down
- **WHEN** the database is unreachable and `POST .../proxies` names `2024/Blandat`
- **THEN** the response is 503 with `check` `database`, and no state is reported for the job

#### Scenario: An unusable reel.yaml does not block proxies
- **WHEN** `POST .../proxies` names `2024/2024-10-06 - Trasig reel`, whose `reel.yaml` does not parse, or
  `2024/2024-10-07 - Utan titel`, whose `reel.yaml` has no title, so the render enqueue would refuse it
- **THEN** the response is 201 (or 200 `fresh`), not an error

#### Scenario: The schema publishes the proxy enqueue
- **WHEN** the service's OpenAPI schema is generated
- **THEN** `POST /api/v1/events/{event_id}/proxies` declares its 201 job, its 200 result (a named model whose
  `status` is the required constant `fresh` and which has `clip_count`), and its 404, 409, 502 and 503 problem
  bodies, and takes no request body

### Requirement: A proxy job and a render job of one event do not block each other
The one-active-job rule of the enqueue SHALL hold per kind. An event SHALL have at most one `queued` or `running`
job of kind `render` and at most one of kind `proxy`, and an active job of one kind SHALL NOT make the enqueue of
the other a 409: `POST /api/v1/jobs` SHALL look for an active **render** job only, and
`POST /api/v1/events/{event_id}/proxies` for an active **proxy** job only. The 409 `job_id` of either SHALL be
a job of the kind requested. `POST /api/v1/jobs/{id}/cancel` SHALL act on a job of either kind with the store's
cancel and report its outcome as for a render (`flagged-running`, `canceled-queued`, `no-op-terminal`); a
cancelled proxy job leaves the event's render jobs untouched.

#### Scenario: A running proxy job does not block a render enqueue
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has a `running` proxy job and its title was edited after
  its last render, and `POST /api/v1/jobs` names it
- **THEN** the response is 201 with a `queued` job of kind `render`, and the proxy job is unchanged

#### Scenario: An active render does not block a proxy enqueue
- **WHEN** the same event has a `queued` render job, and `POST /api/v1/events/{event_id}/proxies` names it with
  unprepared clips
- **THEN** the response is 201 with a `queued` job of kind `proxy`, and the render job is unchanged

#### Scenario: A render conflict names the render
- **WHEN** the event has both a `queued` render job and a `queued` proxy job, and `POST /api/v1/jobs` names it
- **THEN** the response is 409 `active_job` whose `job_id` is the render job's id

#### Scenario: Cancel a running proxy job over REST
- **WHEN** `POST /api/v1/jobs/{id}/cancel` targets the `running` proxy job of `2024/Blandat`
- **THEN** the job's `cancel_requested` is set, its status is unchanged, the response's outcome is
  `flagged-running` with status `running`, and the event's render jobs are unchanged

### Requirement: The jobs WebSocket follows proxy jobs
`WS /api/v1/ws/jobs` SHALL carry jobs of every kind, in the frame shape of "WebSocket live job updates", each job
with its `kind`. The first frame's snapshot SHALL include every `queued` and `running` proxy job of the served
project beside the render jobs; later deltas SHALL carry a proxy job's progress, status and cancel-request
changes; and a proxy job's terminal transition SHALL be delivered exactly once, including a job whose whole active
life fell between two polls. A proxy job's `progress` SHALL be the value the job store holds, sent as a render's
is. A job of another project SHALL NOT be sent. A frame carrying only render jobs SHALL differ from what it was
only by each job's `kind: "render"`.

#### Scenario: A subscriber's snapshot holds both kinds
- **WHEN** `2024/Blandat` has a `running` proxy job and `2024/2024-06-27 - Grillning med grannar` a `queued`
  render, and a client connects
- **THEN** the first frame has `type` `snapshot` and holds both jobs, the first with `kind: "proxy"` and the
  second with `kind: "render"`

#### Scenario: A proxy job's progress and end arrive as deltas
- **WHEN** a connected client watches a proxy job go from `queued` to `running` with progress 0.4 and then to
  `done`
- **THEN** it receives deltas carrying that job with `kind: "proxy"`, in that order, and the `done` row exactly
  once

#### Scenario: A proxy job that lives between two polls is still delivered once
- **WHEN** a proxy job for `2024/Blandat` is created, claimed and finished between two polls
- **THEN** the next delta carries its terminal row once, with `kind: "proxy"`

#### Scenario: Another project's proxy job is not sent
- **WHEN** a proxy job exists for an event of a different project root
- **THEN** no frame of the served project's subscribers carries it
