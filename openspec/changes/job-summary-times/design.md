## Context

See proposal.md, "Why". The code facts that shape the approach come from `main` at `fb73846`, where
none of the files below has changed since `47e46f4`. They also come from `render-progress-screen`'s
working tree, which is on `main` before this change starts.

- **The store records both times.** In `persistence/job_store.py`:
  - `claim_next` stamps `started_at = func.now()`
  - `transition` (to `done`/`failed`/`canceled`), `cancel_queued` and `cancel` (the `canceled-queued` branch)
    stamp `finished_at = func.now()`
  - `requeue` sets `started_at = None`, and the orphan reconcile (D-S5) and graceful stop (D-S8) go
    through it

  Every terminal write stamps `finished_at`. A running job always has `started_at`.
- **The summary is built from whole rows.** `JobStore.latest_by_project(project_root)` runs one
  `select(Job) … DISTINCT ON (event_dir) ORDER BY event_dir, created_at DESC`. Its session factory has
  `expire_on_commit=False` (`persistence/engine.py`), so every column, both times included, is loaded and
  readable after the session closes.
- **`api/events_read.py` `_job_summary(job)`** is the only place a `JobSummaryOut` is built. It passes four
  fields: `id`, `status`, `progress`, `created_at`. Both `list_events` (via `_event_summary`) and
  `get_event` call it, so the list and the detail cannot disagree.
- **`api/schemas.py`:**
  - `JobSummaryOut` declares `id`, `status: JobStatus`, `progress`, `created_at`
  - `JobOut` declares `started_at: Optional[datetime] = None` and `finished_at: Optional[datetime] = None`
  - the published schema has them as `anyOf: [{type: string, format: date-time}, {type: null}]`, not
    required, which `openapi-typescript` emits as `started_at?: string | null`
- **`api/serialize.py` `job_to_out(job)`** builds `JobOut` from the same row type with the same two fields.
  Both conversions therefore serialize the same `datetime` objects through the same pydantic serializer.
  For `created_at`, which both already carry, the strings on the wire are identical: Trasig's job reads
  `…T18:44:14.361887Z` in `GET /api/v1/events` and in `GET /api/v1/jobs`.
- **The client** (`render-progress-screen`, `web/src/jobs/`):
  - `useJob.ts`: `ShownJob = { source: 'live'; job: JobOut } | { source: 'read'; job: JobSummary }`, where
    `JobSummary` is `components['schemas']['JobSummaryOut']` (`web/src/api/events.ts`)
  - `JobProgress.tsx` `stateTime(shown)` returns "finished" or "started" only when `shown.source === 'live'`,
    and otherwise always "queued" + `created_at`
  - `JobState` renders `{label} <time dateTime={iso}>{short format}</time>`. It is used by both
    `LiveJobCell` (list rows, through `JobProgress`) and `RenderControl` (the page's "Last job"). On
    the page it sits inside `<p className="render-status" role="status">`, whose comment says its words
    "change with the job's state only".
  - `RenderControl` reads a `failed` job it knows only from the read once, with `load(id)`, for its
    error text. The answer lands in the store, so the page then shows the job as `live`. In C5 the
    page's `role="status"` text therefore changes from "queued <created_at>" to "finished <finished_at>"
    when that read answers, with no state change. A `done` or `canceled` job that is known only from a
    read is never loaded, so its page keeps "queued …". List rows never load a job.
- **Measured** on the agent's own dev library (port 8112): see proposal.md. Every ended job the list shows
  (`done`, `failed`, `canceled`) has both times in `GET /api/v1/jobs`, and none in `latest_job`.
- **Prototype.** A scratch copy of C5's `web/` was used, with `web/openapi.json` given the two properties
  exactly as `JobOut` publishes them. There, `npm run generate:types` adds
  `started_at?: string | null; finished_at?: string | null;` to `JobSummaryOut`. The `stateTime` below then
  passes `tsc --noEmit` with no other client change.
- **Review spike, before and after.** `api/` was patched as below, both artifacts were regenerated from
  it, and the `requires_db` cases of task 2.1 passed. A dev library was then served on port 8112 and
  checked with Playwright, first with C5's build and then with this design's `stateTime`:

  | shown | C5 build | this design |
  |---|---|---|
  | Grillning's and Trasig's list rows | `queued`, `datetime` = `created_at` | `finished`, `datetime` = the job detail's `finished_at` |
  | Trasig's page, job read held | "Last job Failed queued …" | "Last job Failed finished …" |
  | Trasig's page, after the job read | "Last job Failed finished …" (changed) | unchanged |
  | Grillning's page | `queued` | `finished` |
  | Badutflykt's row after a queued cancel | (not run) | `Canceled`, `finished`, `datetime` = `finished_at` |
  | Två kapitel rendered with the page open, then reloaded | (not run) | the same `finished` `datetime` before and after |

## Goals / Non-Goals

**Goals:**

- The latest job on the events reads carries `started_at` and `finished_at` with `JobOut`'s values and
  schema definitions.
- Every screen dates a job by its state, whichever source it came from.

**Non-Goals:**

- More summary fields, a store change, a new format or wording, `JobCell`. See proposal.md, "Non-goals".
- Any change to `useEventJob`'s choice of which job a screen shows.

## Research & Decisions

### Declaring the two fields exactly as `JobOut` does

**Context**: The fields can be optional with a `None` default, as on `JobOut`, or required and nullable
(no default), as this codebase does for `kind` and `WsMessage.jobs`. Required and nullable would give
`started_at: string | null` instead of `started_at?: string | null`.

**Explored**: `api/schemas.py` (`JobOut`, `EventSummaryOut.kind`, `WsMessage.jobs`); `web/openapi.json`;
the prototype's generated `schema.d.ts`.

**Decision**: Declare them as `JobOut` does:

```python
class JobSummaryOut(BaseModel):
    """The latest job for an event, as embedded in the events list and detail (D-A3).

    A projection of the job's detail (``JobOut``): every field here has the same value,
    meaning and schema definition there. ``started_at``/``finished_at`` are null until the
    store stamps them (a claim; a terminal transition), never substituted.

    ``status`` is typed with the job store's own closed vocabulary, so the schema
    publishes the enumeration and generated clients get an exhaustive union
    (D-8, §4.10). ``JobStatus`` is a ``str`` enum: the wire values are unchanged.
    """

    id: uuid.UUID
    status: JobStatus
    progress: float
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
```

**Rationale**:
- The client handles `JobOut | JobSummary`, and identical declarations give the union one type per
  field. `stateTime` then reads `job.finished_at` without narrowing on the source.
- The spec's "identical definitions" is one equality assertion in `tests/test_api_openapi.py`, over every
  `JobSummaryOut` property against `JobOut`'s same-named one. The spike confirmed that all six are
  equal once the two fields are added.
- The docstring is the model's schema `description`, so the regenerated `schema.d.ts` also changes
  `JobSummaryOut`'s `@description` block. That block and the two properties are the whole diff.
- Nothing here is a discriminator, so marking the fields required buys a client nothing. The service always
  sends the keys anyway: pydantic serializes `None` as `null`, as `GET /api/v1/jobs` already shows
  (`"started_at": null` on `2024/Blandat`'s queued job).

### Filling them where the summary is built

**Context**: The two values could be passed explicitly in `_job_summary`, taken from the ORM row with
`model_validate(job, from_attributes=True)`, or derived from `job_to_out(job)`.

**Explored**: `api/events_read.py` `_job_summary`, `api/serialize.py` `job_to_out` (explicit keyword
arguments with `# type: ignore[attr-defined]` for duck-typed hub fakes).

**Decision**: Two more keyword arguments in `_job_summary`, which stays in `events_read.py`:

```python
def _job_summary(job: Optional[Job]) -> Optional[JobSummaryOut]:
    if job is None:
        return None
    return JobSummaryOut(
        id=job.id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
```

**Rationale**:
- This follows the house pattern: `job_to_out` is explicit too.
- `from_attributes` would be a new, implicit mapping style for one model.
- Going through `job_to_out` would build a full `JobOut` per event only to drop most of it.
- Drift between the two shapes is guarded by the schema test (identical definitions) and by the
  `requires_db` test that compares the list's times with `GET /api/v1/jobs/{id}`, not by sharing code.

### The client: one source-independent `stateTime`

**Context**: C5's `stateTime` gates "finished" and "started" on `shown.source === 'live'`, because the
summary lacked the times. With the times in the summary, the gate is the whole defect.

**Explored**: `web/src/jobs/JobProgress.tsx` (`stateTime`, `JobState`, `JobProgress`), `useJob.ts`
(`ShownJob`, `choose`), `RenderControl.tsx` and `LiveJobCell.tsx` (the two callers of `JobState`).
The scratch prototype passed `tsc --noEmit`.

**Decision**: Destructure the job and drop the guard. The fallback stays:

```ts
/**
 * The time that matches the job's state, labelled for what it is: when it
 * finished (ended), started (running) or was queued. Every job the service
 * reports, from the connection, a job read or an events read, carries the times
 * it recorded; a time it has not recorded is absent, and then when the job was
 * queued is shown, labelled so — never a time presented as one it is not.
 */
function stateTime({ job }: ShownJob): { label: string; iso: string } {
  if (!isActive(job.status) && job.finished_at != null) {
    return { label: 'finished', iso: job.finished_at }
  }
  if (job.status === 'running' && job.started_at != null) {
    return { label: 'started', iso: job.started_at }
  }
  return { label: 'queued', iso: job.created_at }
}
```

**Rationale**:
- `JobState`, `JobProgress`, `RenderControl` and `LiveJobCell` need no change, because they already render
  whatever `stateTime` returns. The format stays C5's.
- One job now gives one time whatever its source. When a failed job's read turns a `read` job into a
  `live` one on the page, the status region's words stay the same, so nothing is announced. This is
  C5's rule that only state changes are announced. It needs no change to `RenderControl`'s load, and
  the spike measured it with the job read held.
- The fallback is kept even though the store stamps both times on every path today. The generated types
  make them optional, and a client served by an older service (no keys) must still show a truthful time.
  Showing "—" instead would lose a true fact the job does carry.
- A requeued job (`queued`, `started_at` null) reads "queued <created_at>". That is the first enqueue, and
  the store records no requeue time (Risks).

### ADDED requirements, not MODIFIED

**Context**: The web behavior refines `render-progress-screen`'s "A render's progress is shown live". Its
"done" bullet says the time is "labelled as a finish time only when the service reported one". The API
behavior could instead be folded into "Events read model is scanned from disk per request".

**Explored**: `openspec/specs/api-service/spec.md` and `web-app/spec.md`; the in-flight changes' deltas.
`missing-clips-screen` (C10) is written in parallel on the same gate. `clip-thumbnails-screen` MODIFIES
"Reading a screen never changes state". `jobs-ws-lifecycle`, which MODIFIED "WebSocket live job
updates", has been archived on `main` since (`64ac980`). No main-spec requirement lists `latest_job`'s
fields, so an ADDED requirement contradicts none.

**Decision**: One ADDED requirement per capability. Nothing is MODIFIED.

**Rationale**:
- C5's text stays true: once the service reports a finish time, "labelled as a finish time" follows.
- A MODIFIED block replaces a requirement's whole text, so two changes modifying the same requirement lose
  one side's edit. C10 plausibly touches C5's render and list requirements.
- An ADDED block against a requirement that is not yet on `main` also cannot fail
  `openspec validate --strict` before the gate lands.

### HLD: one sentence, no D-n

**Context**: The config asks for a D-n entry when a decision outlives the change.

**Explored**: HLD §4.10's slice paragraph as `render-progress-screen` leaves it. It names
`jobs-client-contract` and `jobs-project-guards` as slice E's `api/` prerequisites. Also HLD §7 (D-1 to
D-10), and the precedent of `jobs-client-contract`, which published schema changes with one §4.10
sentence and no D-n.

**Decision**: No D-n. The lasting rule, "the latest job is a projection of `JobOut` with identical values
and definitions", is the api-service requirement itself. HLD §4.10's slice paragraph gains one sentence
naming `job-summary-times` as a slice-E follow-up, next to `jobs-client-contract` and
`jobs-project-guards`.

**Rationale**: No graph, fingerprint, `reel.yaml` or database decision is made. §4.10 lists the `api/`
changes slice E needed, and this follow-up is one more.

## Failure behavior & idempotency

- **Nothing new raises.** The two values are read from an already-loaded row. A job store that cannot be
  reached still fails both events reads with the published 503 (`Events reads fail loud with a problem
  body`), unchanged. An event that cannot be read is still an error row with no `latest_job` at all.
- **Absent is null, never substituted (Principle I).** A queued job, and one cancelled while queued,
  report `started_at: null`. A queued or running job reports `finished_at: null`.
- **Idempotency:**
  - **re-run:** the reads are read-only, and repeating a GET with no job change returns the same times
  - **`--force` run:** it creates a new job, which becomes the latest job: `started_at` and `finished_at`
    stay null until a worker claims and ends it, and the previous job's times are no longer shown
  - **worker restart mid-render:** the orphan reconcile or graceful stop requeues the job, which clears
    `started_at`, so the summary reports `queued` with no start time. Its `finished_at` was never set.
- No file is written and nothing is rendered, so there is no partial-output concern.

## Risks / Trade-offs

- **[Another in-flight `api/` change regenerates the same artifacts]** `clip-thumbnail-endpoint` also
  changes `web/openapi.json` and `schema.d.ts`. (`jobs-ws-lifecycle` is archived and changed neither.)
  → Regenerate both after rebasing, and never merge them by hand. Both files are byte-deterministic, and
  the staleness test names any disagreement.
- **[A requeued job reads "queued <first enqueue time>"]** The store records no requeue time, and
  `requeue_count` is on `JobOut` only. → Accepted, because the label is true: the job was queued then.
  Adding a requeue timestamp would be a store and migration change for a rare case (Principle VII).
- **[`JobCell` still shows the queued time unlabelled]** Nothing renders it after
  `render-progress-screen`. → Left alone (proposal, Non-goals). Open Questions names its removal.
- **[Parallel web change on the same gate]** `missing-clips-screen` is expected to edit `RenderControl`,
  `LiveJobCell` and the screens; its brief names `RenderControl`'s `blockedReason` and the list row's
  Render. → On the web side this change touches only `stateTime` and its comment in `JobProgress.tsx`,
  plus the regenerated types. C10 is web-only and does not regenerate them.
- **[Response size]** Two timestamps per listed event, about 70 bytes each. This is negligible next to the
  staleness verdict every row already carries.

## Migration Plan

- Restart `serve` and rebuild `web/dist` with the `web/README.md` container command.
- **New service, old client:** the extra keys are ignored at runtime, since generated types are
  compile-time only.
- **New client, old service:** the keys are absent, and `stateTime` falls back to "queued …", which is
  today's behavior.
- No data, schema or migration is involved. Rollback means reverting the commit.

## Open Questions

- **Removing `JobCell`** (`web/src/events/common.tsx`), unused once `render-progress-screen` is on `main`,
  is a follow-up clean-up. It changes no spec, approach or task here.
