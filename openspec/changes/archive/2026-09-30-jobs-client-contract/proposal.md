## Why

GUI v1 slice **E** (HLD **§6 phase 8**, §4.10: "schedule a render and watch live progress", cancel) is the
first screen that drives the job queue: `POST /api/v1/jobs`, `WS /api/v1/ws/jobs` and
`POST /api/v1/jobs/{id}/cancel`. D-8 requires the client's types to come from the service's own schema,
and HLD §4.10 requires every closed vocabulary to be published as an enumeration, because a set typed as
`str` leaves `pytest`, the drift check and `tsc` green while the UI degrades to raw slugs.

Planning slice E against the shipped jobs surface found six gaps. As with `event-detail-client-contract`
and `editorial-client-contract`, they are closed in `api/` and the store first, so the screen stays a pure
`web/` change (Principle VIII):

1. **The jobs routes publish none of their problem responses** (`api/routes/jobs.py:31,105,115` declare no
   `responses=`). `POST /jobs` publishes only 201 and 422. Its 200 "fresh, not enqueued" body is a raw
   `JSONResponse` (`jobs.py:77`), so `FreshResult` is absent from the schema altogether, and its 404 and 409
   are unpublished. `GET /jobs/{id}` and cancel do not publish their 404. The client would have to declare
   these shapes by hand, which the `web-app` spec forbids.
2. **The 409's job id is an untyped extra.** The "already active" 409 carries the existing job as
   `id=` (`jobs.py:54-56`), and the two jobs 404s echo the missing id the same way (`jobs.py:111,121`).
   `ProblemOut` does not name the field, so a generated client cannot read it without a cast.
3. **The cancel outcome is a string, and can be wrong.** `CancelResult.outcome` is `str` with its three
   values in a comment (`api/schemas.py:287`). The route computes it from a `store.get` made *before*
   `store.request_cancel` (`jobs.py:119-132`), so a job a worker claims in between is reported as
   `canceled-queued` while its echoed status is `running`. Underneath, `request_cancel` reads without a
   lock (`persistence/job_store.py:228-243`). A cancel that meets a claim still uncommitted overwrites the
   claimed job's `running` with `canceled` (a lost update, confirmed with a scratch experiment; see design
   "Context"). The worker then renders the event to the end, and the row says `canceled` for a render
   that finished. This path is shared by the CLI's `jobs cancel`.
4. **The WebSocket frame is invisible to codegen.** `WsMessage.type` is `str` (`schemas.py:315`) and, since
   a WebSocket route is not part of OpenAPI, `WsMessage` itself is not in the schema. The client would
   hand-write the frame the whole live-progress feature parses.
5. **An enqueue race answers 201 for a job it did not create.** When the route's active-job pre-check
   (`jobs.py:52`) and the insert race, `JobStore.enqueue` falls back to the existing active job on the
   unique-index violation (`persistence/job_store.py:76-83`) and returns only an id, so the route answers
   **201** with someone else's job. The `job-store` spec already says enqueue reports "that no new job was
   created"; the store never did.
6. **The job→event link is not contractual.** `JobOut.event_dir` holds the event id the events routes use,
   because the API enqueues `payload.event_id` as `event_dir` (`jobs.py:79-81`), but nothing says so. The
   GUI matches jobs to list rows on exactly that equality.

Two more gaps surfaced while checking item 4 against the hub (`api/ws.py:137-161`):

7. **A cancel request is not pushed.** A delta is pushed only when a job's status or progress changes
   (`ws.py:141-149`). A cancel request on a running job changes neither, so every other open screen keeps
   showing the job as plainly running until its progress next changes. Slice E shows "Cancelling…" from
   `cancel_requested`, so the flag joins the change triggers.
8. **A job whose whole active life falls between two polls is never pushed.** `_tick` emits only jobs in
   the current active set or in the previous tick's (`vanished`, `ws.py:151-157`). A job enqueued, claimed
   and finished inside one poll interval is in neither. `2024-10-05 - Trasig` fails at probe right after a
   claim (the worker claims on a 2 s poll), and an event found fresh at claim ends the same way. The page
   that pressed Render then shows "Waiting for a worker" until the operator refreshes, and slice E may not
   poll to find out. The existing requirement already promises terminal transitions; the hub does not keep
   that promise.

## What Changes

- **Every jobs route publishes its responses.** `POST /api/v1/jobs`: 201 `JobOut`, 200 `FreshResult`, 404
  and 409 `ProblemOut`. `GET /api/v1/jobs/{id}` and `POST /api/v1/jobs/{id}/cancel`: 404 `ProblemOut`.
  `FreshResult.status` becomes the constant `"fresh"`, required.
- **`ProblemOut.job_id`** is a typed problem field. The "already active" 409 carries the active job's id
  there, and the two jobs 404s carry the id that was not found. **BREAKING (wire):** the untyped `id` extra
  on those three bodies is replaced by `job_id`. No client reads it, so there is no shim.
- **Enqueue reports whether it created the job.** The store gains `submit`, which returns the job id
  together with a `created` flag, decided by the same insert-or-fall-back `enqueue` already performs.
  `enqueue` becomes a wrapper that keeps returning the id alone. The route calls `submit` and answers
  **409 with the existing job's id** whenever the store did not create one, so a race can no longer yield
  201.
- **Cancel is decided in one locked transaction, and its outcome is a closed vocabulary.** The store's
  cancel reads the job under a row lock, applies the transition and returns the outcome it applied:
  `CancelOutcome` = `flagged-running` | `canceled-queued` | `no-op-terminal`, owned by `persistence/`.
  `CancelResult.outcome` is typed with it. The route makes one store call and no pre-read.
- **The WebSocket frame is a published, closed shape.** `WsMessageType` = `snapshot` | `delta` types
  `WsMessage.type`, and `WsMessage.jobs` is required (the hub always sends it). The application adds
  `WsMessage` and `WsMessageType` to its OpenAPI components, so the generated types include them. No HTTP
  route is invented for it. The path stays `/api/v1/ws/jobs`.
- **A cancel request on a running job is pushed.** A change of `cancel_requested` is a delta trigger, like
  status and progress.
- **Every terminal transition reaches connected subscribers exactly once.** The store gains a read,
  `list_finished_since`, that returns the jobs whose terminal transition was stamped since a given instant,
  together with the database's own current time. Each tick the hub also emits the jobs it returns that no
  frame has yet carried as terminal, so a job that was never seen active still gets one delta with its
  terminal row. The window overlaps the previous one, so a transition committed late is not missed, and
  the hub de-duplicates by job id, so no job is sent twice.
- **`JobOut.event_dir` is documented** in the schema as the event's id, the same value the events routes
  take and return as `event_id`.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.** No client code reads these
  responses yet.

## Non-goals

- **No output-path collision refusal and no project scoping** of `GET /jobs`, the WebSocket or job lookups
  (`jobs-project-guards`, C3).
- **No screen** (slice E, `render-progress-screen`).
- **No ETA, fps, stage or output path on `JobOut`.** The client derives an ETA from `progress` over time;
  new columns would need a migration for a display nicety (Principle VII).
- **No WebSocket filter** by event or job, and no replay of terminal transitions missed while disconnected.
  The hub-gap fix covers connected subscribers only; a client reconciles its tracked jobs with
  `GET /jobs/{id}` after a snapshot.
- **No project scoping of the finished-jobs read.** `list_finished_since` is database-wide here, like
  `list_by_status`. `jobs-project-guards` (C3) narrows it to the served project together with the active
  snapshot, and re-bases its MODIFIED `Query jobs` on this change's text.
- **Follow-up, not this round: a published 503 (`check: database`) on the jobs routes.** A
  `SQLAlchemyError` on `POST /jobs`, `GET /jobs`, `GET /jobs/{id}` or cancel still escapes as an unshaped
  500, while the events reads answer 503 with `check: database`. Consequence: when the database is down,
  slice E cannot name the cause on a jobs action and reports an unexpected answer, and the schema
  publishes no 503 for these routes. A small follow-up change after slice E maps the error to the events
  reads' 503 on all four routes.
- **Follow-up, not this round: refusing a non-canonical event id on `POST /jobs`.** The route keeps
  storing `event_id` as spelled once `resolve_event_dir` finds a directory under the root. Consequence:
  - a spelling such as `2024/./Blandat` or `2024/Blandat/` is stored as a different `event_dir`, so it
    passes the one-active-job index (two concurrent renders of one event) and its job never matches the
    event's row by `event_dir === event_id`
  - a year folder (`2024`) or the root (`.`) is accepted as an event

  This is safe for v1 only because the GUI sends only ids the events routes returned, and the CLI
  enqueues the same canonical ids. A direct API caller is not protected. The follow-up accepts only an
  `event_id` equal to `event_id_for` of a walked event and answers 404 otherwise.
- **No change to the CLI's enqueue or cancel reports.** `enqueue` and `jobs cancel` keep their output; the
  store's existing `enqueue` and `request_cancel` keep their signatures and return contracts.
  `request_cancel` gains the row lock only because it wraps the new cancel.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - `Requirement: Jobs lifecycle over REST`: published responses, the typed `job_id`, 409 on an enqueue
    race, and a cancel outcome taken from the store's own transition
  - `Requirement: WebSocket live job updates`: a published frame shape, `cancel_requested` as a delta
    trigger, and exactly one delta for a terminal transition no earlier frame carried
  - ADDED `Requirement: Cancel outcome and WebSocket frame type are closed, published vocabularies`
- `job-store`:
  - `Requirement: Enqueue a job`: the result says whether a job was created
  - `Requirement: Request cancellation of a job`: one locked transaction reporting which of the three
    outcomes it applied, distinguishing a missing job from a terminal one
  - `Requirement: Query jobs`: a read of the jobs whose terminal transition was stamped since an instant,
    with the database's current time

## Impact

- **Dependencies (gates):** none. This change may be implemented and archived in parallel with
  `web-design-system`. `jobs-project-guards` (C3) and `render-progress-screen` (C5) are gated on it. Task
  1.1 checks the baseline (`541c44c`) instead of a gate. C3 re-bases its MODIFIED `Query jobs` on this
  change's archived text and project-scopes `list_finished_since`.
- **Packages:**
  - `persistence/`: `job_store.py` gains `CancelOutcome`, the result-bearing enqueue and cancel verbs and
    the `list_finished_since` read, and keeps `enqueue` and `request_cancel` as thin wrappers.
  - `api/`: `routes/jobs.py` (`responses=`, `job_id`, the created flag, the one-call cancel),
    `schemas.py` (`FreshResult`, `CancelResult`, `ProblemOut.job_id`, `WsMessageType`, the `JobOut.event_dir`
    description, `WsMessage.jobs` required), `ws.py` (the delta trigger, the finished-jobs emission and
    the frame publication),
    `app.py` (the schema hook) and `problem.py` (a docstring that cites `.id`).
  - Regenerated `web/` artifacts. No hand-written `web/` code changes.
  - Docs: `README.md`'s API service section and one sentence in HLD §4.10.
- **CLI vs API (Principle V):** the outcome and the created flag are decided by the store, which the CLI
  already calls; the API only maps them to status codes. The CLI's output is unchanged. Its `jobs cancel`
  gets the lost-update fix too, because `request_cancel` delegates to the locked cancel.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration** (no column or index
  changes; the row lock and the finished-jobs read are query changes), no rescan.
- **Wire:**
  - `POST /jobs` 409 and the jobs 404s carry `job_id` instead of `id`
  - an enqueue that loses a race answers 409 instead of 201
  - a cancel racing a claim reports the outcome it applied, and no longer overwrites the claimed job's
    `running` with `canceled`
  - the WebSocket pushes a delta when `cancel_requested` changes
  - the WebSocket pushes one delta for a job that became terminal without ever appearing in a frame
  - every other response is unchanged, byte for byte
- **Runtime dependencies:** none.
- **Size (Principle VIII):** two capability deltas, two packages (`persistence/`, `api/`), 10 tasks (one of
  them the baseline check). The hub-gap fix is folded into the existing store and hub tasks.
