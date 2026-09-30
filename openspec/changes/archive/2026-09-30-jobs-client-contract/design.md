## Context

See proposal.md — Why. The code facts that shape the approach:

- **`api/routes/jobs.create_job`** (`jobs.py:31-88`) declares `response_model=JobOut, status_code=201` and
  no `responses=`. It resolves the event (404 `event_id=`), pre-checks `store.active_job` (409 with
  `id=str(existing.id)`, `jobs.py:52-56`), runs the gate, answers a fresh event with
  `JSONResponse(status_code=200, content=FreshResult(...).model_dump(mode="json"))` (`jobs.py:72-77`), then
  calls `store.enqueue(...)` and answers 201 with `store.get(job_id)` whatever `enqueue` did.
- **`JobStore.enqueue`** (`persistence/job_store.py:41-84`) inserts, and on `IntegrityError` from the partial
  unique index `ux_jobs_active_identity` (`persistence/models.py:52-58`) rolls back and returns the
  existing active job's id. The return value is a bare `uuid.UUID`. 78 test call sites in six files, the
  CLI (`cli/commands.py:660`) and `scripts/make_dev_library.py` use it.
- **`api/routes/jobs.cancel_job`** (`jobs.py:115-132`) does `store.get`, derives `outcome` from that read,
  then calls `store.request_cancel`, and echoes `result.status` (or the pre-read job's). **`request_cancel`**
  (`job_store.py:219-243`) reads with a plain `session.get` and writes in the same session. Under Postgres'
  default READ COMMITTED, a concurrent `claim_next` holding the row (`FOR UPDATE SKIP LOCKED`,
  `job_store.py:115-132`) is invisible to that read. The cancel then sees `queued`, blocks on the row at its
  `UPDATE`, and overwrites the committed `running` with `canceled`. **Confirmed** by a scratch experiment
  during review (throwaway Postgres 16; the real `request_cancel` against a held, uncommitted claim): the
  committed row ended `canceled`, with the claim's `worker_id` and `cancel_requested` false. The same
  scenario with a `FOR UPDATE` read ended `running` with `cancel_requested` true. The consequence is
  worse than a label:
  - the worker's `should_cancel` reads `cancel_requested`, which is still false (`scheduler/worker.py:273-275`)
  - so the render runs to the end and writes the movie
  - its final `transition` raises `IllegalJobTransitionError`, which `_safe_transition` logs as a warning
    and swallows (`scheduler/worker.py:293-307`)
  - the row says `canceled` for a render that finished

  The route-level mislabel in the proposal is the visible half of this race. Task 2.2 keeps the
  experiment as a regression test.
- **The CLI** calls `request_cancel` (`cli/commands.py:808`) and prints from its `Optional[Job]`. The worker
  tests call it too (`tests/test_scheduler_worker.py:674`).
- **`api/ws.JobsHub._tick`** (`ws.py:137-161`) emits a row when it is new or its `status` or `progress`
  changed. `_encode(message_type: str, …)` builds `WsMessage(type=…)`.
- **The hub sees only the active set.** `_tick` reads `list_by_status` for `queued` and `running`
  (`ws.py:175-183`) and fetches the final row only of a job that was in the previous tick's set and is not
  in this one (`vanished`, `ws.py:151-157`). A job that is enqueued, claimed and finished between two
  ticks is in neither set, so no frame ever carries it. The worker claims on a 2 s poll, and
  `2024-10-05 - Trasig` fails at probe right after its claim, so this is an ordinary path, not a corner.
- **`finished_at` is `func.now()`** in `transition`, `cancel_queued` and `request_cancel`
  (`job_store.py:157,214,239`). In Postgres `now()` is the *start* of the writing transaction, so a
  terminal row becomes visible to other sessions slightly after its `finished_at`. The table has no index
  on `finished_at` (`persistence/models.py:47-58`).
- **The schema** is `app.openapi()` of an app built with fixed settings (`api/openapi.py:54-57`); the drift
  test compares it byte for byte with `web/openapi.json` (`tests/test_api_openapi.py:184-221`). FastAPI
  0.139 and pydantic 2.12 are installed. A prototype in the session scratchpad confirmed that
  `pydantic.json_schema.models_json_schema([(WsMessage, "serialization")],
  ref_template="#/components/schemas/{model}")` yields `WsMessage` and `WsMessageType` definitions that
  reference `JobOut` and `JobStatus` by component name. It also showed that pydantic's own `JobOut`
  definition is **not** byte-identical to the one FastAPI already publishes (FastAPI omits the `null`
  defaults), so the merge must not overwrite existing components.
- **`ProblemOut`** (`schemas.py:290-309`) is schema-only, with `extra="allow"`. The routes build bodies with
  `problem.problem_response(**extra)`. No `web/src` code reads a problem's `id`. A grep of
  `problem.<field>` outside `schema.d.ts` finds only `check`, `detail`, `failure`, `status` and `title`.

## Goals / Non-Goals

**Goals:**

- Every jobs response a client can receive has one published shape, and every closed set in it is an
  enumeration.
- The store decides "created?" and "which cancel outcome?" at the moment it acts, so the API reports facts,
  not predictions.

**Non-Goals:**

- Changing the CLI's reports (they keep their best-effort `was_active` classification; see Risks).
- Canonicalizing or refusing a client-supplied `event_id` before it is stored as `event_dir`, and a
  published 503 on the jobs routes. Both are follow-ups; the proposal's Non-goals state their consequence.
- Project scoping and collision refusal (C3), including scoping `list_finished_since`.

## Research & Decisions

### Result-bearing store verbs, old verbs kept as wrappers

**Context**: The route needs "created or not" from `enqueue` and "which outcome" from the cancel, but both
verbs have many callers that want only what they return today.

**Explored**:
- Changing `enqueue`'s return type to a tuple or dataclass means rewriting 78 test call sites, the CLI and
  the dev-library script. That touches a third package (`cli/`) for no behavior change there.
- A route-side comparison (the returned job's `created_at` against the request time) is a heuristic.
- A new verb that returns the fact, with the old verb delegating to it, keeps one code path.

**Decision**: In `persistence/job_store.py`:

```python
class CancelOutcome(StrEnum):
    FLAGGED_RUNNING = "flagged-running"
    CANCELED_QUEUED = "canceled-queued"
    NO_OP_TERMINAL = "no-op-terminal"

@dataclass(frozen=True)
class Submission:
    job_id: uuid.UUID
    created: bool

@dataclass(frozen=True)
class Cancellation:
    job: Job              # the row as committed by the cancel's transaction
    outcome: CancelOutcome

def submit(self, project_root, event_dir, *, device="auto", output_path=None,
           force=False, fingerprint=None) -> Submission: ...      # today's enqueue body
def enqueue(self, ...) -> uuid.UUID:
    return self.submit(...).job_id                                # unchanged contract

def cancel(self, job_id: uuid.UUID) -> Optional[Cancellation]: ...  # None: no such job
def request_cancel(self, job_id: uuid.UUID) -> Optional[Job]:
    result = self.cancel(job_id)
    if result is None or result.outcome is CancelOutcome.NO_OP_TERMINAL:
        return None
    return result.job                                             # unchanged contract
```

`submit` returns `Submission(job.id, True)` after a successful flush, and `Submission(existing.id, False)` on
the `IntegrityError` fallback.

**Rationale**:
- One insert path and one cancel path. The wrappers are one line each, so Principle VII's "no second code
  path" holds.
- The enumeration lives with the transition that produces it (HLD §4.10: "owned by the layer that owns the
  vocabulary"), the way `JobStatus` lives in `persistence/`.
- `Cancellation.job` lets the route echo the post-transaction status without another read.

### One locked transaction for the cancel

**Context**: The outcome and the write must agree with each other and with concurrent claims.

**Explored**:
- A route-side re-read after the cancel. The store's own lost update would remain.
- `FOR UPDATE NOWAIT`. A cancel that meets a claim would fail instead of waiting a few milliseconds.
- Conditional updates: `UPDATE … SET status = 'canceled' WHERE id = :id AND status = 'queued'`, then the
  same for `running`. These are correct under READ COMMITTED, but they need two or three statements to find
  the outcome. A locked read keeps today's branch structure.

**Decision**: `cancel` reads the row with `session.get(Job, job_id, with_for_update=True)`, then branches on
the locked status exactly as `request_cancel` does today, flushes, refreshes, and returns
`Cancellation(job, outcome)`. A terminal job returns `Cancellation(job, NO_OP_TERMINAL)` with the row
unchanged. A missing row returns `None`.

**Rationale**:
- `FOR UPDATE` without `SKIP LOCKED` waits for a claim's transaction. Under READ COMMITTED Postgres then
  re-reads the row's latest committed version, so the cancel acts on `running` and flags it.
- If the cancel takes the lock first, `claim_next` skips the row (`SKIP LOCKED`) and, after the commit,
  never sees it as `queued` again. Both orders give a truthful outcome.
- The worker's `transition` and `requeue` write the same row, so they serialize against the cancel the same
  way. Neither writes `cancel_requested`, so a flag set just before a terminal transition or a requeue
  survives it.
- The lock is held for one read and one write. It never spans a render.
- The cancel cannot take part in a deadlock. It holds at most one row lock, and it requests no other lock
  while holding it.

### The route: the store's facts, mapped

**Decision**:

```python
submission = store.submit(project_root, payload.event_id, device=..., force=..., fingerprint=...)
if not submission.created:
    return conflict(f"an active job already exists for event {payload.event_id!r}",
                    job_id=str(submission.job_id))
...
result = store.cancel(job_id)
if result is None:
    return not_found(f"no job with id {job_id}", job_id=str(job_id))
return CancelResult(id=result.job.id, status=result.job.status, outcome=result.outcome)
```

The `active_job` pre-check stays: it answers the common duplicate before the fingerprint is computed and
before the gate can answer "fresh", which keeps today's order (409 before 200). The store's flag closes the
window after it.

**Rationale**: the route keeps doing request/response shaping only (Principle V); both facts come from the
store the CLI also calls.

### `job_id` as the typed problem field

**Context**: The 409 must carry the active job's id in a field the generated client can read.

**Explored**: keeping `id` and declaring it on `ProblemOut`. But `id` on a problem body reads as the
problem's own id, and the events routes' problems already name their subject (`event_id`).

**Decision**: `ProblemOut.job_id: Optional[uuid.UUID] = None`, documented as "the job a jobs problem is
about: the active job on the enqueue 409, the requested id on a jobs 404". The three call sites pass
`job_id=`. The `id=` extra is removed, with no alias: no client reads it (grep of `web/src`), and the
fixed-names contract for C3 and C5 uses `job_id`.

### Publishing the responses

**Decision**: `responses=` on three routes:
- `POST /jobs`: `{200: {"model": FreshResult, "description": "The event is fresh; nothing was enqueued"},
  404: {"model": ProblemOut}, 409: {"model": ProblemOut}}`
- `GET /jobs/{job_id}` and `POST /jobs/{job_id}/cancel`: `{404: {"model": ProblemOut}}`

The fresh body stays a `JSONResponse`, because the declared `response_model` is the 201's `JobOut`.
`FreshResult.status` becomes `Literal["fresh"]` **without a default**, and the route passes
`status="fresh"`. FastAPI's output schemas do not mark defaulted fields required (the committed `JobOut`
leaves `force` optional), so a default would generate `status?: "fresh"`. `JobOut.event_dir` gets
`Field(description="The event's id: the root-relative event directory, the same value the events routes
take as {event_id} and return as event_id")`.

### Publishing the WebSocket frame without inventing a route

**Context**: `openapi-typescript` emits every entry of `components.schemas`, whether or not a path
references it. A WebSocket route contributes nothing to `app.openapi()`.

**Explored**:
- A dummy HTTP route or a fake `responses=` entry. This is rejected by the brief, and it would be a lie in
  the schema.
- Adding the model only in `api/openapi.py`'s offline dump. Then the served `/openapi.json` and the
  committed file would disagree.
- Wrapping `app.openapi` in `create_app`, so both agree.

**Decision**:
- `api/schemas.py`: `class WsMessageType(StrEnum): SNAPSHOT = "snapshot"; DELTA = "delta"`, and
  `WsMessage.type: WsMessageType`. `WsMessage.jobs` loses its `= []` default and becomes required.
  pydantic's serialization schema leaves a defaulted field out of `required`, as the prototype showed
  (`"required": ["type"]`), so the default would generate `jobs?: JobOut[]`. Every client would then need
  a `?? []` for a field the hub always sends. Nothing constructs a `WsMessage` without `jobs`: `_encode`
  is the only constructor (`ws.py:127`). The wire is unchanged.
- `api/ws.py`:
  - `publish_ws_schema(schema: dict) -> None` adds the `$defs` of
    `models_json_schema([(WsMessage, "serialization")], ref_template="#/components/schemas/{model}")` to
    `schema["components"]["schemas"]`, but only for names not already present. `JobOut` and `JobStatus`
    stay FastAPI's.
  - `_encode` takes a `WsMessageType`.
- `api/app.py`: after the routers are included, wrap the default:

```python
default_openapi = app.openapi
def _openapi() -> dict[str, Any]:
    schema = default_openapi()     # FastAPI's own cache: the same dict until the routes change
    publish_ws_schema(schema)      # in place and idempotent: adds only absent components
    return schema
app.openapi = _openapi             # type: ignore[method-assign]
```

- The wrapper keeps no cache of its own. FastAPI 0.139's `openapi()` rebuilds its cached schema when the
  router's routes version changes (`fastapi/applications.py`, `_openapi_routes_version`). A wrapper that
  short-circuited on `app.openapi_schema is not None` would bypass that. An idempotent merge on every
  call is correct under both paths.
- FastAPI's `/openapi.json` handler calls `self.openapi()`, so the served schema goes through the wrapper
  too. `api/openapi.build_openapi_schema` calls `app.openapi()` and needs no change.

**Rationale**:
- One schema for the live service and for the committed artifact.
- Merge-if-absent means a reference in the frame always resolves to the component the routes publish.
- A test asserts `WsMessage.properties.jobs.items.$ref` names `JobOut` and that no path names
  `/api/v1/ws/jobs`.

### `cancel_requested` as a delta trigger

**Decision**: `_tick` also emits a row whose `cancel_requested` differs from the previous snapshot's.

**Rationale**: the flag is the only state a running job's cancel changes (the worker, not the API, writes
the terminal status). Without it, screens other than the one that asked keep showing plain progress until
the next progress *change*. `ThrottledProgress` (`scheduler/progress.py`) writes at most once per second
or per 1 % step, and the hub ignores a write that leaves the value unchanged. A stretch of the render that
reports no advance therefore pushes nothing. The cost is at most one extra row per job per cancel.
`render-progress-screen` (C5) works either way: its own forced `GET /jobs/{id}` after a cancel stays
correct, and the delta adds the same state for every other open screen.

### Jobs whose whole active life falls between two polls

**Context**: The hub must push a terminal transition for a job no frame carried (Context, "The hub sees
only the active set"). Slice E cannot find out otherwise: its spec forbids polling on a timer.

**Explored**:
- Shortening the poll interval. The gap narrows but stays, and every connected GUI tab pays for it.
- Watching `created_at >= previous tick`. It finds new jobs, but the hub then needs a second read for the
  ones that already finished, and a job enqueued just before the previous tick's read committed is still
  missed.
- Postgres `LISTEN/NOTIFY` from the store's writes. It is exact, but it adds a second channel, a
  dedicated connection and trigger or write-side code for a gap a query closes. Principle VII.
- A read of the jobs finished since the previous tick, keyed on the database's clock, with an overlap and
  de-duplication.

**Decision**: In `persistence/job_store.py`:

```python
@dataclass(frozen=True)
class FinishedJobs:
    as_of: datetime       # the database's now() in the read's own transaction
    jobs: list[Job]       # finished_at >= (since or as_of) - overlap, by finished_at ascending

def list_finished_since(self, since: Optional[datetime], *,
                        overlap: timedelta) -> FinishedJobs: ...
```

One session, one transaction: `as_of = session.scalar(select(func.now()))`, then
`select(Job).where(Job.finished_at >= (since or as_of) - overlap).order_by(Job.finished_at.asc())`. Only a
terminal transition stamps `finished_at`, so the read returns terminal jobs only.

In `api/ws.py`, `JobsHub` keeps a watermark (`_finished_as_of: datetime`) and the ids already sent as
terminal with their `finished_at` (`_terminal_sent: dict[uuid.UUID, datetime]`). `_FINISHED_OVERLAP =
timedelta(seconds=30)` is a module constant.
- **Poller start** (first subscriber): read `list_finished_since(None, overlap=_FINISHED_OVERLAP)` **before**
  the active snapshot. Its `as_of` seeds the watermark, and its jobs seed `_terminal_sent` without being
  sent: they finished before the poller existed. The order matters: a job that finishes between the two
  reads is then in neither, and the first tick sends it.
- **Each tick**: read `list_finished_since(watermark, overlap=_FINISHED_OVERLAP)`, then the active
  snapshot. The rows that left the active set are the `vanished` final rows plus the finished-read jobs,
  merged by id. A terminal row (a status in the store's `TERMINAL_STATUSES`) is appended to the delta only
  if its id is not in `_terminal_sent`, and once sent it is recorded there with its `finished_at`. Only
  terminal rows with a `finished_at` are recorded. Two kinds of row go out without being recorded:
  - a `vanished` row that is still active: the snapshot is two reads (queued, then running), so a requeue
    landing between them hides a job from one tick. Its row is current state and is sent as before, but
    recording it would suppress the job's real terminal row later.
  - a terminal row without a `finished_at` (only a row written outside the store's transitions): no
    finished read can return it, so there is nothing to de-duplicate it against.

  The watermark becomes the read's `as_of`. Entries whose `finished_at` is older than
  `watermark - _FINISHED_OVERLAP` are dropped from `_terminal_sent`, because no later read can return them.
- The existing `vanished` path stays. When a job leaves the active set by a commit that lands between
  this tick's finished read and its active read, `vanished` sends it in this tick rather than the next.
  The shared `_terminal_sent` then keeps the next tick's finished read from sending it again.

**Rationale**:
- `as_of` and `finished_at` come from one clock, the database's, so host clock skew cannot open a gap.
- A terminal row whose writing transaction started before `as_of` but committed after the read has
  `finished_at < as_of`. The 30 s overlap re-reads that stretch. The writing transactions are one read and
  one update (the cancel's row lock waits milliseconds), so 30 s is orders of magnitude of slack, at the
  cost of re-reading at most 30 s of finished rows per tick, filtered in memory.
- `_terminal_sent` is bounded by the jobs finished in one window, so memory stays small during a batch.
- The first subscriber's start costs one more query. An idle service still issues none.
- C3 adds `project_root` to `list_finished_since` exactly as it does to `list_by_status`, so the scoped hub
  scopes both reads.

## Failure behavior and idempotency

- **Enqueue**:
  - 404 (unknown event), 409 (active job, before or at insertion) and 200 (fresh) write nothing.
  - 201 inserts exactly one row.
  - Re-sending the same request while the job is active answers 409 with the same `job_id`. After the job
    is terminal, a stale event enqueues anew.
  - `force` bypasses only the gate; it never bypasses the 409.
- **Cancel**:
  - Re-sending a cancel for a running job answers `flagged-running` again (the flag is already set; no
    change, and so no second WebSocket delta).
  - Re-sending a cancel for a job the first cancel canceled while it was queued answers `no-op-terminal`
    with status `canceled`. Two concurrent cancels serialize on the row lock, so exactly one of them
    reports `canceled-queued`.
  - A cancel for a canceled or finished job answers `no-op-terminal` and changes nothing.
  - A 404 changes nothing.
- **Hub**:
  - A job's terminal row is sent at most once while the poller runs, whichever path found it, and at least
    once when its transition commits within `_FINISHED_OVERLAP` of the transaction's start.
  - When the last subscriber leaves, the poller stops and the watermark and `_terminal_sent` are dropped.
    The next first subscriber seeds them again, and a job that finished while nobody was connected is
    never sent; the client's reconcile after the snapshot covers it.
  - A failed finished read fails the tick exactly as a failed active read does today.
  - A poller start whose reads fail, or which is cancelled, registers no subscriber and resets the watermark
    and `_terminal_sent`, so the next subscriber is the first one again and starts the poller. The WebSocket
    handler subscribes inside its `try`, so a subscriber it registered is always unsubscribed. Before this
    change a failed start left its subscriber registered, and no later subscriber started the poller.
- **Worker restart mid-render**: unchanged. A requeue keeps `cancel_requested`, so a cancel flagged before a
  crash still applies after the requeue. The hub pushes the requeued row as a status change.
- **Nothing here renders or writes files.** No `RENDER_GRAPH_VERSION` bump, and no fingerprint or manifest
  change.

## Risks / Trade-offs

- **[The CLI's `enqueue` report keeps its best-effort pre-check]** `cli/commands.py:656-659` classifies
  "already queued" with its own `active_job` read, which can misreport the same race. → It could switch to
  `submit` in one line, but that makes this change touch a third package (Principle VIII). It is left as a
  follow-up. Its effect is limited to a printed label; the database still prevents a duplicate row.
- **[`event_dir` is stored as the client sent it]** `create_job` stores `payload.event_id` verbatim after
  `resolve_event_dir` accepted it (`events_read.py:86-100`). That check only requires an existing directory
  under the root. So:
  - a non-canonical spelling (`2024/./Blandat`, `2024/Blandat/`) resolves to the same directory but is a
    different `event_dir`, and it would slip past the one-active-job index
  - a year folder (`2024`), or the root itself (`.`), passes the check, as if it were an event

  → The GUI only sends ids the events routes returned. Those are canonical (`events_read.event_id_for`),
  and so are the CLI's (`cli/commands.py`, `ref.event_dir.relative_to(...)`). The spec therefore promises
  the equality only for such ids. Refusing other spellings is a recorded follow-up (proposal Non-goals),
  not part of this round or of C3.
- **[Row lock on cancel]** A cancel waits while a claim's transaction is open. → That transaction is one
  `SELECT … FOR UPDATE SKIP LOCKED` plus one update, so the wait is milliseconds, never a render.
- **[Wire rename `id` → `job_id`]** An external script reading the 409's `id` would break. → The CLI does
  not use the API, and `web/` reads no such field. The rename is listed as **BREAKING (wire)** in the
  proposal and README.
- **[A terminal write slower than the overlap]** A terminal transaction that commits more than 30 s after
  it started would be outside every window, and a job that also lived between two polls would then go
  unsent. → No such write exists: each is one read and one update. The effect would be today's gap for
  that one job, and the client's reconcile after a reconnect still covers it.
- **[A scan per tick]** `list_finished_since` has no index on `finished_at`, so each tick scans `jobs`
  while a subscriber is connected. → The table holds one row per render request, thousands at most for the
  MOL archive. An index is a later migration if a measurement asks for it (Principle VII); this change
  adds none.
- **[Schema-hook drift]** A future pydantic that renames `$defs` keys would add near-duplicate components. →
  The drift test and a test pinning the component names (`WsMessage`, `WsMessageType`) would fail loudly.

## Migration Plan

No data migration and no Alembic revision: the row lock is a query change. Regenerate `web/openapi.json`
and `web/src/api/schema.d.ts` with the `web/README.md` commands. Rollback means reverting the store verbs,
the route mapping, the schema hook and the declarations. The two wrappers mean no other caller changes.

## Open Questions

None. The two questions the first draft raised (a 503 on the jobs routes, and refusing non-canonical
event ids on enqueue) are decided as follow-ups; the proposal's Non-goals state each one's consequence.
