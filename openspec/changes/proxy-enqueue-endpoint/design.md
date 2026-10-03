## Context

See proposal.md, "Why". Written against `origin/main` at `8fb4d16`, **before** its gates merged; task 1.1 re-checked it against
`74ecef5` (all three gates merged) and the "Gate" table below records the names the code really has.
Line numbers are omitted: the gates move `api/events_read.py`, `api/schemas.py` and the persistence modules.

**The jobs surface today** (`api/routes/jobs.py`, `api/schemas.py`, `api/serialize.py`, `api/ws.py`):
- `POST /api/v1/jobs` resolves the event, checks the output claim, looks for the active job
  (`store.active_job(project_root, event_id)`), the missing clips and the staleness gate, then
  `store.submit(...)`; `submit` reports whether *it* created the row (the partial unique index is the arbiter).
- `JobOut` (`id`, `status`, `event_dir`, `project_root`, `device`, `progress`, `worker_id`, `cancel_requested`,
  `requeue_count`, `force`, `fingerprint`, `error`, the three times) is built by `serialize.job_to_out`, which
  the routes and the WebSocket hub share. `JobSummaryOut` is its projection for `latest_job`.
- `events_read` fills `latest_job` from `JobStore.latest_by_project(project_root)`: one query, a
  `row_number()` over `PARTITION BY event_dir ORDER BY created_at DESC, id DESC`, rank 1. It is **not** scoped
  by kind today because there is one kind.
- The hub (`ws.py`) polls `list_by_status` for the active jobs and `list_finished_since` for terminal rows,
  both scoped to the served project, and sends `job_to_out(job)` for each.
- `routes/events.py` registers `.../analysis`, `.../reel`, `.../thumbnail` before the greedy
  `/events/{event_id:path}` detail route; `routes/media.py` does the same for `/media` and `/movie`.

**What the research says this change must respect** (`research/v2/synthesis.md`):
- X6: clip facts come from the proxy job, so the timeline opens only for an event whose proxies are prepared
  and otherwise shows a Prepare action with job progress. This endpoint is that action's server half.
- X8: the unique-active index becomes per (project, event, kind); a proxy job classifies as a CPU job; a proxy
  and a render for one event must not refuse each other.
- §5 row 8: "`POST .../proxies` with the jobs' 201 / 200-fresh / 409 semantics; `kind` in the job read model and
  WebSocket frames; jobs client-contract and WS lifecycle tests extended".
- §6 risk 7: the `kind` work "touches the unique index, the claim query, `JobOut` and the WebSocket frames; a
  mistake would block renders". Hence render behaviour is pinned by tests here too (tasks 2.2, 3.2).
- §6 risks 8 and 9: proxy generation shares the USB disk with renders (concurrency 1, lower priority - both are
  `proxy-job`'s); a first-time event costs 41 to 78 s per 10 minutes of footage, so the request must return at
  once with a job, never run the work.

## Gate

`proxy-job`, `proxy-state-read` and `proxy-media-endpoints` are merged into `origin/main` before this change is
implemented (`job-kind`, `proxy-encode` and `filmstrip-sprites` come through them). Task 1.1 confirms it and
re-reads the code they leave. This design assumes, and 1.1 checks, the following; each is stated as the thing this
change *uses*, never as something it adds, except where marked.

| Assumed from | What this change uses | Found on `main` (task 1.1) |
|---|---|---|
| `job-kind` | a kind enumeration, `submit` / `active_job` taking a kind, a per-kind unique index | `persistence.models.JobKind` (`StrEnum`: `RENDER = "render"`, `PROXY = "proxy"`), re-exported by `persistence`; `Job.kind` is free text in the column; `JobStore.submit(..., kind=JobKind.RENDER)` returns `Submission(job_id, created)`; `active_job(project_root, event_dir, kind=JobKind.RENDER)`; index `ux_jobs_active_identity` on (project_root, event_dir, kind). Holds. |
| `job-kind` | `latest_by_project` scoped to one kind | **Already scoped**: `latest_by_project(project_root, *, kind=JobKind.RENDER)` ranks inside the `kind` filter. Task 1.2 is a no-op (recorded; its tests are kept). |
| `job-kind` | the jobs reads' scope | **Differs from the draft**: `list_by_status` and `list_finished_since` also default to `kind=JobKind.RENDER` (`None` lists every kind). So `GET /api/v1/jobs` and the WebSocket hub, which call them without a kind, would show renders only. This change passes `kind=None` in both (tasks 2.2, 3.2). |
| `proxy-state-read` | a per-clip state function the route can call | `proxies.read_proxy_state(clip_path, *, settings) -> ProxyReading` (`ProxyStatus`: absent, ready, stale, failed), `stat` and JSON only; raises `ProxyError` (clip not statted) / `ProxyCacheError` (cache unreadable). The detail wraps it in `events_read._clip_proxy`, which turns those into "unknown" (`None`); this route calls `read_proxy_state` directly so they stay errors (502). Settings: `proxies.resolve_proxy_settings(load_project_config(root), root)` raising `ConfigError`. |
| `proxy-job` | the clip set the job prepares | `ProxyJobHandler._plan`: every clip of `event.scan_event(event_dir).identities`, grouped by `proxy_key`; `reel.yaml` is never read, IGNORED clips included. **The draft's "detail's active/new" set was wrong**; the spec and design now use `scan_event`'s listing (see "The clip set"). |
| `proxy-media-endpoints` | route names and registration order | `routes/media.py` registers `.../media`, `.../movie`, `.../proxy`, `.../filmstrip` before the events router; `.../proxies` matches none. Holds. |

## Goals / Non-Goals

**Goals**
- One enqueue verb for proxies that behaves like the render enqueue where the meaning is the same (201 / 200 /
  409 / 404 / 502 / 503), and says nothing it cannot know.
- A client can tell any job's kind from any read of it, and can never mistake a proxy job for the event's
  render.
- A render's observable behaviour is unchanged except for the added `kind` field.

**Non-Goals** (beyond the proposal's)
- No store verb, migration, job column or job status: `job-kind` owns them. No change to the worker, the
  scheduler pools or `proxies/`.
- No new conflict kind, no new problem field: `active_job` and `job_id` already say what a proxy conflict is.
- No polling or "wait until ready" parameter: the client follows the job over the WebSocket.

## Research & Decisions

### Where the route lives and what it is named
**Context**: the proxy is a property of a clip of an event, and the endpoint acts on an event.
**Explored**: `POST /api/v1/jobs` with a `kind` field in `EnqueueRequest`; `POST /api/v1/events/{id}/proxies`.
**Decision**: `POST /api/v1/events/{event_id:path}/proxies`, in `routes/events.py`, registered before the greedy
detail route (as `/thumbnail` is, for the reason its docstring gives), returning the same `JobOut`.
**Rationale**: `POST /jobs` has a render-shaped request (`force`, `device`) and render-shaped refusals
(`output_collision`, `missing_clips`, the staleness gate). A `kind` field would make most of its body and 409
vocabulary not apply to one of its two values, and every client switch would have to know which. A separate verb
keeps the render route byte-identical (risk 7) and names its own refusals. The synthesis names the route
(§5 row 8) and the media routes already hang off `/events/{id}/...`.

### Freshness is read from the clips' proxy state, not from a job
**Context**: the render's 200 comes from the staleness gate (a fingerprint and a manifest). A proxy has neither:
D-21 makes the cache independent of staleness and of editorial edits, and a proxy's identity is its entry in the
cache (D-11's key plus `PROXY_VERSION` plus the settings hash).
**Explored**: (a) always enqueue and let the job skip ready clips; (b) ask the cache which clips are `ready`
and enqueue only if one is not; (c) a flag on the event.
**Decision**: (b). The route computes each clip's state with `proxy-state-read`'s function (stat and JSON
only, no subprocess) and answers 200 `fresh` when all are `ready`.
**Rationale**: (a) creates a job row, a WebSocket frame and a worker claim for nothing every time a page opens
the timeline of a prepared event; the job's own skip is the right cost for a *partly* prepared event, not for a
prepared one. (b) is the same cheap read the detail already does, and the two can never disagree about "ready"
because they call one function. (c) is a second source of truth (Principle II). The job still skips ready
clips on its own (`proxy-job`), so a race where a clip became ready between the read and the claim costs
nothing.

### `latest_job` stays the render
**Context**: with two kinds, "the latest job of an event" has two readings, and the web builds its render state
(badge, progress, the "Render anyway" gate) from it.
**Explored**: (a) latest of any kind, with `kind` to tell; (b) latest render only; (c) one field per kind.
**Decision**: (b). `latest_job` is the newest `render` job. No `latest_proxy_job`.
**Rationale**: (a) makes a finished proxy job replace the last render in every existing screen: the list would
show "done" for an event whose render failed, and a running proxy would show as render progress. That breaks
"render behaviour and API answers unchanged" (`job-kind`'s own gate) for any event that has both. (c) adds a
field that nothing needs yet: the proxy side is read from the clips' `proxy` state (which says what exists) and,
while a job is active, from the WebSocket snapshot (which says what is happening, including after a page
reload). Revisit when a screen needs the *last finished* proxy job's error; it is one query away.

### Latest render job
**Decision**: `JobStore.latest_by_project(project_root, *, kind=<render>)`: the ranking's partition stays
`event_dir` and the subquery has `.where(Job.kind == kind)`. `job-kind` already did this, so task 1.2 is a no-op;
the `events_read` call sites name `kind=JobKind.RENDER` so the choice is visible where `latest_job` is built.
**Rationale**: a post-filter in Python would rank across kinds first and lose the render when a proxy job is
newer; the scoping has to be in the query. No index is needed beyond `job-kind`'s: the table is small and the
read is one query per request, as today.

### The 409 and `active_job`
**Decision**: reuse `EnqueueConflict.ACTIVE_JOB` and `ProblemOut.job_id`; update the enumeration's docstring so
it reads "Why an enqueue refused an event with a 409". The check is `store.active_job(project_root, event_id,
kind=PROXY)` first, then `submit(kind=PROXY)`, whose `created` flag decides 201 versus the race's 409 (the same
pattern as `create_job`).
**Rationale**: a client's `switch` on `conflict` already handles it; a new member would force every client to
change for a case that behaves identically. The published enum members are unchanged, so no client breaks.

### Event resolution and the 502
**Decision**: the route resolves the event with `listed_event_dir(settings, event_id)` (the id the list shows,
so `event_dir` of the job is the list's id and the per-kind unique index and the WebSocket matching work) and
lists its clips with `scan_event`; an `OSError` becomes an `EventReadError` with `classify_event_failure`
(`unreadable_disk`), which the route answers as the detail does (`_event_read_failed`). `reel.yaml` is not read and
`require_processable` is not called (corrected from the first draft, which assumed the detail does not require it:
it does, through `_load_for_reconcile`, so the route cannot reuse that).
**Rationale**: the render enqueue demands a processable event because its output path derives from metadata;
nothing of that applies. Refusing proxies for an event the operator is on its way to fix (the metadata page)
would block the timeline for no reason, and the job would not read the file either.

### The clip set
**Decision (corrected by task 1.1 against the merged `proxy-job`)**: `events_read.proxy_clips(event_dir) ->
list[str]`: the identities `event.scan_event(event_dir)` lists, which is what `ProxyJobHandler._plan` walks.
`reel.yaml` is not read, so `ignored` and `excluded` clips are prepared and a clip `reel.yaml` lists that is not on
disk is not in the set. Zero clips is a 200 with `clip_count: 0`.
**Rationale**: the 200 and the job must agree on the set, and `proxy-job` made editorial state neither add work
nor invalidate any. A missing clip has nothing to encode, and refusing the event for it (the render does, because
it would fail at probe) would block a timeline over the clips that are there. A vacuous 200 is stated as such by
`clip_count: 0`. This replaces the first draft's "detail's active/new set"; it also removes the `reel.yaml` parse
and metadata failure modes from this route, since neither is read.

### Failure behaviour (Principle I) and idempotency
- An unreadable event, listing, proxies configuration or cache directory raises, and the route answers 502
  without enqueueing. A clip's state is never defaulted to `absent` because its entry could not be read (that
  would enqueue a job over a cache the worker cannot write either) or to `ready` (that would hide a missing
  proxy). `proxy-state-read` decides what an *unreadable single entry* is (`failed` or a raise); this route
  takes its answer.
- `SQLAlchemyError` from the store answers the jobs routes' 503 (`_job_store_unreachable`), applied to the new
  route; no 201 is reported that the store did not confirm.
- Re-run: a repeat while a job is active is 409 with its id; after it finished, a repeat is 200 when all
  `ready`, else a new job that re-attempts the clips that are not (a `failed` clip is retried by the plain
  request). A worker restart mid-job requeues it (`proxy-job`); the event's active slot stays occupied, so a
  repeat during the restart is still a 409, never a second job. There is no `--force`.
- Nothing here writes a file: the route inserts one row. The cache is only ever written by the worker, atomically
  (`.part` to rename, `proxy-encode`).

### The jobs WebSocket
**Decision**: the hub reads active and finished jobs with `kind=None` (every kind; the store defaults to render
since `job-kind`), and the frames carry `kind` because `JobOut` does. A test that a proxy job reaches the snapshot
and deltas fails without the argument. `GET /api/v1/jobs` passes `kind=None` for the same reason.
**Rationale**: any filtering by kind in the hub would hide proxy progress from the Prepare screen, which is the
reason the field is on the frame. The client decides what to do with a kind it does not handle.

### Spec deltas and the three gates
Every requirement in the `api-service` delta is ADDED. The existing "Jobs lifecycle over REST", "WebSocket live job
updates" and the two latest-job requirements stay true as written: `GET /api/v1/jobs` lists jobs (now of every
kind, each marked); the frame's jobs are "in the same job shape the jobs routes return"; and their phrase "an
event's latest job" is narrowed to the render by "An event's latest job is its latest render job". The three
gates also edit `api-service` (the `proxy` field of the clip, the media routes), and `job-kind` may edit the
jobs requirements for its per-kind index. Using ADDED blocks only keeps this change from copying and overwriting
text the gates changed. Task 1.1 re-reads the archived text of every requirement this delta refers to and
corrects the cross-references (names, not behaviour).

## Decisions

**Response model for the 200.** `ProxiesFreshResult { event_id: str, status: Literal["fresh"], clip_count: int }`,
`status` declared without a default so the schema marks it required (as `FreshResult` does). It is a new named
model rather than `FreshResult`: that one's `fingerprint` and `manifest` are the render gate's facts and have no
proxy equivalent; making them optional would weaken a published type the web narrows on.

**`kind` on `JobOut` and `JobSummaryOut`.** `kind: JobKind`, required, where `JobKind` is the persistence
layer's enum re-exported into the schema (as `JobStatus` is, with a docstring that speaks to a client, because
FastAPI publishes it). `job_to_out` reads `job.kind.value` like `status`; the hub tests' duck-typed stand-ins gain
a `kind`. The latest-job model's field is the same type, so the "identical definitions" test passes.

**Route sketch** (`routes/events.py`; not a signature to copy):

```python
@router.post(
    "/events/{event_id:path}/proxies",
    response_model=JobOut,
    status_code=201,
    responses={
        200: {"model": ProxiesFreshResult},
        404: {"model": ProblemOut},
        409: {"model": ProblemOut},
        502: {"model": ProblemOut},
        503: {"model": ProblemOut},
    },
)
@job_store_unreachable
def enqueue_proxies(event_id: str, request: Request) -> Union[JobOut, ProxiesFreshResult, Response]:
    # 404 listed_event_dir -> 502 proxy_clips/OSError (unreadable_disk) -> active proxy job 409
    # -> proxies_fresh (stat/JSON; 502 on a cache fault) -> all ready: 200 -> store.submit(kind=PROXY)
```

`_job_store_unreachable` lived in `routes/jobs.py`; it moved to `routes/guards.py` (`job_store_unreachable`), which
both route files import (one definition of the 503, not two). The clip set and freshness read live in
`api/proxy_read.py`, because `events_read.py` is at pylint's module-size limit.

## Risks / Trade-offs

- **[The web's job store treats every job as a render]** `web/src/jobs/store.ts` keeps the newest job per
  `event_dir`, `useConnection` counts every running job as "rendering", and the render control shows that job's
  progress. A proxy job that reaches the socket (started with curl, since no screen enqueues one yet) would be
  counted and shown as a render. → Out of scope here (a third package, and the first web consumer of this
  endpoint is `timeline-view`'s Prepare state). The first web change that enqueues a proxy job MUST filter by
  `kind` in the store, the header count and the render control, and carry the tests for it. Called out to the
  supervisor; if an earlier guard is wanted it is a one-task web change (store filter plus `store.test.ts`).
- **[`latest_job` semantic change for an event with proxy jobs]** only observable after this change, because
  before it no proxy job can be enqueued through the API. → The scenarios of "An event's latest job is its latest
  render job" pin it, including the all-proxy event (`null`).
- **[A job row of a kind this build does not name]** `jobs.kind` is free text on purpose (`job-kind`), but `JobOut.kind`
  is the closed enumeration, so serializing a row written by a newer build raises instead of inventing a value
  (Principle I). It surfaces in the jobs list and the socket as a failure, not a wrong kind. Only a mixed-version
  deployment can produce such a row; widening the enumeration is the fix when a third kind is added.
- **[Disagreement between the 200 and the job on the clip set]** → one shared definition (task 1.1 gate row,
  task 2.1 test of the set on a mixed event).
- **[A 200 hides a proxy that became stale since the page read]** the read is made on the request, from disk, so
  it is as fresh as the detail; between the request and the user's next action it can go stale, which the next
  request catches. No caching.
- **[Hybrid-encode and I/O load]** a client that enqueues proxies for every event at once fills the queue. →
  Concurrency 1 and lower priority are `proxy-job`'s; the endpoint adds no fan-out (one event per request).
- **[Unauthenticated enqueue]** same as the render enqueue (D-A8: auth seam only).

## Migration Plan

No schema change and no data migration. Deploying adds a route and a field; a client written before this change
ignores `kind` and never calls the route. Rollback is reverting the commit; any proxy job rows created in the
meantime stay valid for `job-kind`'s worker.
