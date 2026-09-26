## Context

See proposal.md — Why. The facts that shape the approach:

- `persistence/models.py` owns `JobStatus(str, enum.Enum)` with the five lifecycle values. The schema
  already publishes it as the `JobStatus` component, because `GET /api/v1/jobs` takes it as a query
  parameter.
- `api/schemas.py` declares `JobSummaryOut.status`, `JobOut.status` and `CancelResult.status` as `str`.
  Their producers pass `job.status.value`: `events_read._job_summary`, `serialize.job_out` and the cancel
  route.
- `api/problem.py` builds every deliberate error as a `JSONResponse` with body
  `{title, status, detail, **extra}`. No pydantic model describes it, so FastAPI's schema knows nothing
  of it. The events reads send two extras: `check="database"` on 503, and `event_id` on 502/404.
- `tests/test_api_openapi.py` fails whenever `web/openapi.json` differs from `app.openapi()`.

## Goals / Non-Goals

**Goals:**

- Job status reaches the generated client types as a union, from the enum `persistence/` already owns.
- The events reads' problem responses reach the generated types as a named shape, with no hand
  declaration in `web/`.
- Zero change to any wire value, body, header or status code.

**Non-Goals:**

- A global error handler or a response-model change on the error path. The routes keep returning the
  helper's `JSONResponse`. Only the schema changes.
- Declaring problem responses on routes other than the two events reads (proposal: Non-goals).

## Research & Decisions

### Where the job status vocabulary comes from

**Context**: §4.10's rule is that a closed set is typed by the enumeration owned by the layer that owns
the vocabulary. For job status, that layer is `persistence/` (D-P4).

**Explored**:
- (a) a new `Literal[...]` in `api/schemas.py`
- (b) a new enum in `api/`
- (c) the existing `persistence.models.JobStatus`

**Decision**: (c). Annotate the three fields `status: JobStatus`. The producers pass the member
(`job.status`), not `job.status.value`: pydantic would accept the value string at runtime, but strict
mypy rejects `str` for a `JobStatus` field. A `str`-mixin enum serializes to the same string.

**Rationale**:
- (a) and (b) duplicate a vocabulary that already exists. The schema already publishes `JobStatus` for
  the query parameter, so reusing it means the response fields and the filter share one generated type.
  A client can pass a job's status straight back as a filter without a cast.
- `JobStatus` subclasses `str`, so every existing comparison and serialization is unchanged. The existing
  API tests, which compare statuses to strings, are the proof, and they must pass unmodified.

### How the problem body reaches the schema

**Context**: The routes return `JSONResponse`, which FastAPI cannot introspect. A schema entry needs a
model, declared through the decorator's `responses=` mapping.

**Decision**: A `ProblemOut` model in `api/schemas.py`:

```python
class ProblemOut(BaseModel):
    """The shared problem body every deliberate error uses (D-A6), as published in the schema."""

    model_config = ConfigDict(extra="allow")

    title: str
    status: int
    detail: str
    #: The failing dependency on a 503 (``"database"``), as ``/healthz`` reports it.
    check: Optional[str] = None
    #: The event a per-event failure is about (502/404/400 on the events routes).
    event_id: Optional[str] = None
```

The list decorator declares `responses={502: {"model": ProblemOut}, 503: {"model": ProblemOut}}`, and
the detail adds `404`. `extra="allow"` publishes `additionalProperties`, so route-specific fields such as
the jobs routes' `id` stay legal without this change enumerating them.

**Rationale**:
- Declaring responses is schema-only. FastAPI does not validate a returned `JSONResponse` against it,
  so runtime behavior cannot change.
- The known optional fields are the ones the screens will branch on: `check` for "database down", and
  `event_id` for which event failed. Everything else stays open.

**Alternative rejected**: a `ProblemOut`-returning exception handler, which would replace `problem.py`'s
helpers. That is a runtime refactor of every error path, and it is outside what the screen needs.

### Keeping the model honest

**Context**: A declared shape that the helpers do not actually produce would be a new silent drift.

**Decision**: A test builds each problem body the two events reads can return and validates it with
`ProblemOut.model_validate`: 503 database, 502 scan, 502 per-event, 404. A second test asserts the
schema declares the right status codes on each route and references `ProblemOut`.

**Rationale**: It makes the helper ↔ model contract a test failure, not a code-review hope. This is the
same pattern as the reason-enum ↔ `COMPONENTS` equality test.

## Failure behavior and idempotency

Nothing new raises. The reads keep their existing mappings: 503 database, 502 scan or per-event, 404
unknown event. They remain read-only and side-effect free, so re-runs and worker restarts are unaffected,
and `--force` has no meaning here. No rendered output changes, so there is **no `RENDER_GRAPH_VERSION`
bump**.

## Risks / Trade-offs

- **[Pydantic rejects an unknown status string]** A job row with a status outside `JobStatus` would now
  fail response validation where it used to pass through. → The column is written only through
  `JobStatus` (the store's transitions), so such a row cannot exist. If one did, a loud 500 is the
  correct Principle I outcome, rather than a string the client cannot type.
- **[`extra="allow"` makes the TS type open]** Generated code gets an index signature. → That is
  accurate: route-specific extras exist. The named fields still type-check.
- **[Both artifacts must be regenerated]** The drift test fails until they are. → This is intended, and
  it is the documented two-command step in `web/README.md`.

## Migration Plan

Additive and wire-compatible. No database migration, no rescan, and no `reel.yaml`/`config.yaml`
change. Rollback means reverting the annotations, the model and the two `responses=` arguments, then
regenerating the artifacts.
