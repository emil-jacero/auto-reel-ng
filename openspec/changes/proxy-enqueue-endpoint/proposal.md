## Why

GUI v2 plays every clip from a 540p proxy with sound in Firefox, and lays its timeline out from facts (duration,
fps, dimensions) that only a proxy job records (`research/v2/synthesis.md` §3 D-19 "Facts", X6; HLD §4.10 v2,
D-20, D-21). So the timeline opens only for an event whose proxies are prepared, and the page needs a way to
ask the service to prepare them and to follow the work. Three gates build the pieces underneath: `job-kind`
gives a job a `kind` and a unique-active slot per (project, event, kind), `proxy-job` makes the worker run
`kind=proxy` jobs, and `proxy-state-read` gives each clip of the event detail a `proxy` state. Nothing yet lets
a client **enqueue** a proxy job, and no API shape tells a client which kind of job it is looking at
(synthesis §5 row 8; X8 and risk 7: "the `kind` migration touches ... `JobOut` and the WebSocket frames").

Two facts make the exposure more than a new route:

- **The jobs shapes were written for one kind.** `JobOut`, the latest-job summary of the events reads, and every
  WebSocket frame describe a job by `event_dir`, `status` and `progress` only. Once a proxy job exists for an
  event, a client cannot tell it from a render, and the events reads' "latest job" would report whichever of the
  two is newer, so a finished proxy job would stand where the event's last render belongs.
- **A proxy job and a render job of one event are independent.** The first runs on the CPU pool at a lower
  priority, the second may hold a GPU; neither may refuse the other (synthesis X8).

## What Changes

- **`POST /api/v1/events/{event_id}/proxies`** prepares the proxies of every clip of the event, with the jobs'
  enqueue semantics: **201** with the new `kind: proxy` job; **200 "fresh - not enqueued"** when every clip
  the job would handle (every clip file of the event folder) already has a `ready` proxy; **409 `active_job`** (with the job's id) when a proxy job
  is already queued or running for the event, found beforehand or at insertion; 404 for an id the events list
  does not show; 502 for an event folder or a proxy cache that cannot be read; 503 naming the database. No request
  body: a proxy is a function of the clip file and the proxy settings, so there is nothing to force or choose.
- **A job reports its `kind`** (`render` | `proxy`, a closed published enumeration): in `JobOut`, in the events
  reads' `latest_job`, and so in every WebSocket frame. A render job reads `kind: render` and is otherwise
  byte-for-byte what it was.
- **The events reads' `latest_job` stays the event's latest *render* job.** A proxy job never stands in it. The
  proxy side of an event is read from the clips' `proxy` state (`proxy-state-read`) and, while a job runs, from
  the WebSocket.
- **Per-kind independence is visible over REST:** an active proxy job does not make a render enqueue a 409, and
  the reverse; each kind has at most one active job per event. Cancel works on a proxy job unchanged.
- **The WebSocket follows proxy jobs** in its snapshot and deltas (they are jobs), each frame's jobs carrying
  `kind`; the terminal-exactly-once rule holds for them. `job-kind` made the store's reads default to renders,
  so the hub and `GET /api/v1/jobs` ask for every kind explicitly.
- `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated; the web's types compile and its tests pass.
- **No change to what a render produces.** No `RENDER_GRAPH_VERSION` bump (rendered bytes are unchanged), no
  staleness fingerprint input, no `reel.yaml` or `config.yaml` schema change, no Alembic migration (`job-kind`
  owns the column), no rescan.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: two MODIFIED requirements ("Jobs lifecycle over REST": the 409 is for an active render, list,
  detail and cancel cover every kind; "WebSocket live job updates": the snapshot holds every kind) and five ADDED requirements - "Job kind is a closed, published vocabulary", "An event's latest job
  is its latest render job", "An event's proxies are prepared by a job the service enqueues", "A proxy job and a
  render job of one event do not block each other", "The jobs WebSocket follows proxy jobs". The two latest-job
  requirements stay true as written, with "an event's latest job" read as these requirements narrow it (design
  "Spec deltas and the three gates").

## Impact

- **Packages (two, plus a review-driven guard in the web's `src/jobs/`):** `auto_reel_ng/api` (`routes/events.py`, `events_read.py`, `schemas.py`, `serialize.py`,
  the generated `web/openapi.json` and `web/src/api/schema.d.ts`, which count with the api change) and
  `auto_reel_ng/persistence` (no code change: `job-kind` already scoped the latest-per-event read; task 1.2 records
  it and keeps the tests).
- **CLI vs API (Principle V):** the engine capability is `proxy-encode`'s `auto-reel proxies <root>`, which
  prepares proxies inline. This endpoint is the **job lifecycle** half (enqueue, follow, cancel), which the API
  may own; the work it queues is `proxy-job`'s, reachable from the CLI the same way a render is. A CLI
  `enqueue` for proxies is a follow-up (non-goals).
- **Gates:** `proxy-job`, `proxy-state-read`, `proxy-media-endpoints` merge first; this change is implemented
  on top of them (design "Gate"). `job-kind` and the `proxy-encode` / `filmstrip-sprites` changes are
  underneath those.
- **Tests:** `tests/test_api_jobs.py` (`requires_db`), `tests/test_api_events.py`, `tests/test_api_openapi.py`,
  `tests/test_api_ws_hub.py`, `tests/test_api_ws_lifecycle.py`, `tests/test_job_store.py` (if the store read is
  scoped here), the web's `npm test` / `tsc` / `npm run build`, and a real-browser run in Chrome and Firefox.
- **Evidence relied on:** `research/v2/synthesis.md` §5 row 8, X6 (facts come from the job, so the timeline
  needs a Prepare action), X8 (jobs table, per-kind slots, CPU pool), §6 risks 7-9 (kind touches `JobOut` and
  the frames; I/O contention, so concurrency 1; the timeline cannot open unprepared).

## Non-goals

- **No Prepare control in the web.** The screens that call this endpoint (`timeline-view`'s Prepare state) come
  later. This change only makes the types compile and the existing screens unchanged.
- **No proxy screen, and no proxy count.** The web's job store, event rows, event page, render control and
  header count read *renders only* (`web/src/jobs/kinds.ts`, added in answer to review, because the endpoint is
  reachable with curl and a proxy job would otherwise show as the event's render). Showing proxy jobs is
  `timeline-view`'s.
- **No `force`, `device` or other body.** A proxy that is `stale` (settings or file changed) or `failed` is
  re-attempted by the plain request; a `ready` one is never re-encoded here (`--prune` and re-encode belong to
  the CLI, `proxy-encode`).
- **No `kind` filter on `GET /api/v1/jobs`.** It lists every kind, each marked.
- **No CLI `enqueue` for proxies**: the proxy enqueue is deliberately API-only (`auto-reel proxies <root>` prepares
  inline). `auto-reel jobs list` / `show` do report every kind, with its `kind`, so a proxy job is not invisible there.
- **No refusal for a missing clip, and no `reel.yaml` read.** A proxy job prepares the clips that are on disk
  (ignored and excluded ones too, as `proxy-job` does); a missing one has nothing to prepare and does not hold the
  others back (unlike a render, which would fail at probe), and an unparseable `reel.yaml` does not matter.
- **No proxy-job progress shape.** The job's `progress` is `proxy-job`'s (monotonic, per clip); this change
  carries it unchanged.
