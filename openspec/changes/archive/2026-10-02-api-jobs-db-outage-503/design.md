## Context

See proposal.md, "Why". The code on `main` at `6a7fe16`:

- `routes/events.py` answers an unreachable job store with `_job_store_unavailable(exc, **extra)`:
  `logger.warning(...)` then `service_unavailable(f"job store unreachable: {exc}", check="database", **extra)`
  from `api/problem.py`. `/healthz` returns the same 503 shape from `app.py`. `ProblemOut.check` is the
  published optional field (`schemas.py`).
- `routes/jobs.py` has four sync routes. Where each first touches the database (the engine is lazy, so the
  first query raises `sqlalchemy.exc.OperationalError`, a `SQLAlchemyError`):
  - `create_job`: `events_read.named_event_dir` (disk, 404), `events_read.output_collision` (disk, 502/409),
    then `store.active_job` (**first query**), `compute_fingerprint`/`evaluate` (disk), `store.submit`,
    `store.get`.
  - `list_jobs`: `store.list_by_status` (first query).
  - `get_job` and `cancel_job`: `_served_job` -> `store.get` (first query), then for cancel `store.cancel`.
- No exception handler is registered on the app, so each of these surfaces as Starlette's plain-text 500.
  Reproduced with an app whose `DATABASE_URL` is `postgresql+psycopg://nobody:nobody@127.0.0.1:1/nothing`
  (the fixture `tests/test_api_events_failures.py` already uses): the four jobs requests answer 500
  `Internal Server Error`, the two events reads answer 503 `check: "database"`.
- The generated types: `components['schemas']['ProblemOut']` already has `check?: string | null`.
  `web/src/api/jobs.ts` publishes `ENQUEUE_PROBLEM_STATUSES = {404, 502}` and `JOB_PROBLEM_STATUSES = {404}`;
  anything else is `unpublished`, whose message the screens print after "The render was not queued." /
  "The cancel was not confirmed.".
- The event screens already branch on `problem.check === 'database'` (`EventList.tsx`, `EventDetail.tsx`) and
  word it with `DATABASE_CAUSE`; `RenderControl.tsx` and `LiveJobCell.tsx` already import
  `UNREACHABLE_CAUSE` from the same module.

## Goals / Non-Goals

**Goals:**
- All four jobs routes answer an unreachable job store as the events reads do: 503, shared problem body,
  `check: "database"`.
- The OpenAPI schema and the generated client types publish that answer.
- The client tells it from every other 503 and from a 500 without a problem body, and words it with the
  existing database sentence for the enqueue, the cancel and, silently, the job read.

**Non-Goals:** see proposal.md "Non-goals" (no app-wide handler, no `routes/events.py` change, no request
validation, no retry).

## Decisions

### Where the 503 is produced: a local decorator in `routes/jobs.py`

**Context**: four routes need the same mapping, and `routes/events.py` already has one for two routes.
**Explored**: (a) an app-level `@app.exception_handler(SQLAlchemyError)` in `app.py`, as the triage sketch
offered; (b) moving `_job_store_unavailable` to `problem.py` and calling it from `try/except` in each of the
four routes; (c) a decorator in `routes/jobs.py`.
**Decision**: (c).

```python
def _job_store_unreachable(handler: Callable[_P, _R]) -> Callable[_P, Union[_R, JSONResponse]]:
    @functools.wraps(handler)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Union[_R, JSONResponse]:
        try:
            return handler(*args, **kwargs)
        except SQLAlchemyError as exc:
            logger.warning("jobs: job store unreachable: %s", exc)
            return service_unavailable(f"job store unreachable: {exc}", check="database")
    return wrapper
```

applied as `@router.post(...)` over `@_job_store_unreachable` on each route.
**Rationale**: (a) relabels a database error on *every* current and future route and edits `app.py`; the
events reads already catch the error themselves, so the handler would only ever fire for the jobs routes
plus whatever is added later, with no say from them. (b) repeats a four-line `try/except` around bodies that
are 20-60 lines long, and `create_job` has several early returns, so the `try` would wrap most of the body
anyway. (c) keeps the whole behavior in the file whose routes it describes, leaves `app.py` and
`routes/events.py` untouched (the next change in the chain, `api-jobs-create-validation`, also edits
`routes/jobs.py`, and a decorator is a small, mechanical merge), and is a single place to read.
The detail text is the events reads' text, `job store unreachable: <exc>`, so both surfaces read alike; the
duplication of that one f-string is accepted until a follow-up shares the helper through `problem.py`.

**Implementation notes** (checked at apply time, not assumed): FastAPI builds the route's parameters from
`inspect.signature`, which follows `functools.wraps`' `__wrapped__`, and it resolves the string annotations
(`from __future__ import annotations`) in the wrapper's globals, which are this module's, so `Request`,
`uuid.UUID` and `Optional[JobStatus]` resolve. Every route already sets `response_model` explicitly, so the
changed return annotation (`Union[..., JSONResponse]`) cannot alter the schema; the regenerated
`web/openapi.json` must differ from today's only by the four 503 entries.

### What counts as "unreachable": every `SQLAlchemyError`, as the events reads do

**Context**: `SQLAlchemyError` also covers a missing table, a constraint violation or a bad query, not only a
down server.
**Decision**: catch `SQLAlchemyError` as `routes/events.py` does, and log it at warning with the exception
text in the log and in `detail`.
**Rationale**: one predicate across the surface (the proposal's reason); the operator's next step is the same
(read the service log, check the database), and `detail` carries the driver's text, so a schema error is not
hidden. Narrowing to `OperationalError` would turn a half-migrated database back into a bare 500.

### Order of failures with the database down

**Decision**: the 503 happens at the first store call, so on `POST /api/v1/jobs` the disk-only checks keep
their answers and run first: an unknown event is still 404, a failed walk 502, an output collision 409, all
without the database. Only a request that reaches the store is a 503.
**Rationale**: those answers are true without the database, and the collision rule must not depend on it.
No reordering of `create_job`.

### An enqueue's 503 means "not confirmed queued", and a retry is safe

**Context**: `store.submit` commits in its own transaction. A connection that drops after the server
committed but before the client read the reply raises `SQLAlchemyError` for a job that exists.
**Decision**: accept it and say what a retry does: a second Render press finds that job and answers 409
`active_job`, which both screens already follow as "someone already started it" (no error, no second job).
The service never reports a job it cannot read as "not created" with more certainty than its 503 gives; the
screen's words are about the cause ("can't reach its database"), not a guarantee about the row.
**Rationale**: closing the window needs idempotency keys on `submit`, which is out of scope and unreported.

### Client: a `database` kind, not a flag on `problem`

**Context**: `EnqueueResult`'s `problem` kind is rendered by `RenderControl` and `LiveJobCell` as "The
project could not be scanned" for every non-404 problem. Adding 503 to `ENQUEUE_PROBLEM_STATUSES` would
silently word an outage as a scan failure.
**Explored**: reuse `problem` and branch on `status`/`check` at each caller; or a separate kind.
**Decision**: a separate kind, `{ kind: 'database'; problem: Problem }`, on `EnqueueResult`, `JobResult` and
`CancelAnswer`, produced by one helper in `api/jobs.ts`:

```ts
function isDatabaseDown(body: unknown): body is Problem {
  return isProblem(body) && body.status === 503 && body.check === 'database'
}
```

checked before the route's own problem statuses. A 503 that fails it (a proxy's, or one without the field)
stays `unpublished`, so it never claims a cause it does not carry (web-app, "An event's page schedules its
render": "MUST NOT name a cause the answer does not carry").
**Rationale**: every `switch (result.kind)` in the jobs slice is exhaustive over these unions, so adding the
kind makes `tsc --noEmit` list each caller that must decide (`RenderControl`, `LiveJobCell`, `store.load`).
The decision is by the published status and the typed `check` field, never the detail prose.

### Screen wording

- Event page enqueue (`Notice` in `RenderControl.tsx`): a `notQueued` notice whose title is
  `${NOT_QUEUED} ${DATABASE_CAUSE}` and whose detail is the service's `problem.detail`. The notice's
  `answered: boolean` becomes a three-way cause (`unpublished` | `unreachable` | `database`) so the title,
  the detail and the existing alert are chosen in one place per notice.
- Cancel: the same on `cancelUnconfirmed`, with `NOT_CONFIRMED`.
- List row (`LiveJobCell.tsx` `tellRowAnswer`): `toast.error(`${name}: ${NOT_QUEUED} ${DATABASE_CAUSE}`)` and
  no `Open` action (the problem is not about the event).
- `store.load`: `database` keeps the last known copy, as `unreachable`/`unpublished` do ("never on a timer").
  No toast: the store's reads are background reads.
- `DATABASE_CAUSE` is imported from `events/common` beside `UNREACHABLE_CAUSE`; no new sentence is invented.

### Verification

- API: `tests/test_api_jobs.py` gains offline tests (closed-port `DATABASE_URL`; no container, so no
  `requires_db` marker) that call the four routes and validate each body against `ProblemOut`, plus the
  disk-first ordering of the enqueue; and an OpenAPI test that the four operations declare 503 as
  `ProblemOut`. `tests/test_api_openapi.py`'s drift check covers `web/openapi.json`.
- Web has no unit-test runner (the type-check is the gate, web-app "The type-check is the frontend's gate"),
  so behavior is verified in Chromium: a Playwright script run from the scratchpad, with only
  `**/api/v1/jobs` and `**/api/v1/jobs/**` routed to answer 503, 503 without `check`, and 500, in light and
  dark at 1280 and 390 wide. A real outage is also exercised against `GET /api/v1/jobs` of a served process
  with an unreachable `DATABASE_URL` by `curl`.

## Risks / Trade-offs

- **A non-outage database error reads as "can't reach its database".** Same trade-off as the events reads;
  `detail` carries the driver's text and the log carries the traceback line.
- **Merge friction with `api-jobs-create-validation`**, which edits `create_job` next. The decorator sits on
  the line above the function and does not move the body; that change adds its checks inside `create_job` and
  inherits the 503 for any store call it makes.
- **The 503 body repeats an f-string** from `routes/events.py` (see Decisions); a follow-up can share it.
- **`detail` includes the driver's message.** For a refused connection it names host and port, not the
  password; the events reads already publish the same text.
