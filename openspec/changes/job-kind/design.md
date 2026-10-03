## Context

The `jobs` table is the durable queue (D-P2) and assumes one kind of job, a render of an event:

- `ux_jobs_active_identity` is unique on (`project_root`, `event_dir`) where `status IN ('queued','running')`
  (`persistence/models.py`), enforced by the database and used by `JobStore.submit` as the arbiter of
  idempotent enqueue (D-S7/D-S8).
- `claim_next` selects any `queued` row; `Worker._process_job` treats the row as a render.
- Three read paths answer render questions from "any job": `list_by_status` (API `GET /jobs`, CLI
  `jobs list`, the worker's own running-output check), `list_finished_since` (the WebSocket poller), and
  `latest_by_project` (the event list and event detail `latest_job`).

See proposal.md for why. Evidence relied on: `research/v2/synthesis.md` X8 (index and pool classification
evidence), §3 "Generation" (a job of kind `proxy`, per event, lower priority than renders, concurrency 1),
§5 row 1 (the gate for this change), §6 risk 7 (the migration must leave render behaviour identical), and
`research/v2/proxies.md` §5.2 option B (the worker job kind: a migration, a claim-loop branch, and the API
contract as a separate step).

## Goals / Non-Goals

**Goals:**
- Make a second job kind representable, uniquely-active per kind, claimable, and dispatched, with an unhandled
  kind failing loud.
- Prove render behaviour unchanged: the existing job-store, scheduler, API, WebSocket and CLI tests pass
  unmodified apart from the ones that enumerate columns.

**Non-Goals:** see proposal.md.

## Decisions

### `kind` is a text column, not a Postgres enum
**Context**: `status` is a Postgres enum (`job_status`). The next change adds `proxy`; later ones may add more.
**Explored**: a PG enum (`ALTER TYPE ... ADD VALUE` per new kind, awkward inside a migration transaction, and
the database would reject an unknown kind, so "the worker fails loud on an unknown kind" would be untestable
and unreachable); a `CHECK` constraint (same problem); a text column.
**Decision**: `kind TEXT NOT NULL DEFAULT 'render'`, mirrored by a `JobKind` `StrEnum` (`render`, `proxy`)
in `persistence/models.py` that names the kinds this build knows. The ORM attribute is a `str`.
**Rationale**: a new kind needs no migration, and a row written by a newer build and claimed by an older worker
reaches the worker, which fails it with a reason (Principle I) instead of the database refusing or the worker
rendering it. The server default makes the migration a single additive statement and backfills existing rows.

### The unique index gains `kind`
**Decision**: drop `ux_jobs_active_identity` and create it over (`project_root`, `event_dir`, `kind`) with the
same `WHERE status IN ('queued','running')`, same name. Two indexes cannot share a name, so the migration drops
the old one and creates the new one inside the revision's single transaction (PostgreSQL DDL is transactional and
the drop holds its table lock until commit), so no other session ever sees a moment without protection.
**Rationale**: this is what lets a render and a proxy job for one event coexist (X8) while keeping the
database, not the application, as the arbiter. Because the old index is strictly narrower than the new one's
key, every existing row satisfies the new index: the upgrade cannot fail on data.

**Downgrade**: delete rows whose `kind` is not `render`, drop the `kind` column and the wider index, recreate the
original. Deleting is required, not tidy: a render and a proxy job active for one event would violate the
narrower index. It is safe under Principle II (the table is derived and rebuildable; the proxy cache lives on
disk and is untouched). The downgrade docstring says so.

### Idempotent enqueue is per kind
`submit(project_root, event_dir, *, kind=JobKind.RENDER, ...)` inserts first and, on a unique violation, looks
up the active job **of that kind**; `_active_job` and `active_job` gain the `kind` predicate. Every existing
call site omits `kind` and is therefore a render enqueue. The report (`created`) stays the insertion's own
verdict.

### Reads default to `render`; `None` means every kind
**Context**: once a `proxy` job exists, an unscoped `latest_by_project` would make a proxy job an event's
"latest job" and blank or change `latest_job` in the event list; an unscoped `list_by_status` would show it on
`GET /jobs` without a `kind` field to tell it apart; `list_finished_since` would put it on the WebSocket as a
render frame; and the worker's output-collision check would compute a render output path for a proxy job and
refuse an innocent render.
**Explored**: (a) leave reads unscoped and have each caller filter (touches `api/` and `cli/`, outside this
change's two packages, and every future caller must remember); (b) default the filter to `render`.
**Decision**: `list_by_status`, `list_finished_since` and `latest_by_project` take
`kind: str | None = JobKind.RENDER`; `None` selects every kind. Their callers are unchanged, so API answers, WS
frames and CLI output are byte-identical. `proxy-enqueue-endpoint` and the proxy UI pass `kind=None` or
`kind="proxy"` where they need to. The latest-per-event query partitions by `event_dir` after filtering to the
kind, so a newer proxy job never displaces the render.
**Rationale**: the safe default for the unchanged surfaces; the cost is that `auto-reel jobs list` does not show
proxy jobs until a later change opts in. That is deliberate and recorded as a non-goal.
`claim_next`, `transition`, `set_progress`, `cancel*`, `requeue` and `find_orphaned_running` are by id or by
ownership and stay kind-agnostic: a proxy job is claimed, cancelled, requeued and reconciled exactly like a render.

### The worker dispatches by kind through a handler mapping
```python
KindHandler = Callable[[Job], None]   # returns normally -> done; raises -> failed/canceled below

class Worker:
    def __init__(self, ..., kind_handlers: Mapping[str, KindHandler] | None = None) -> None: ...

    def _process_job(self, job: Job) -> None:
        if job.kind == JobKind.RENDER:
            return self._process_render(job)        # today's body, moved verbatim
        handler = self._kind_handlers.get(job.kind)
        if handler is None:
            self._safe_transition(job.id, JobStatus.FAILED, error=f"unknown job kind {job.kind!r} ...")
            return
        self._run_handler(job, handler)
```
- `render` is not in the mapping: it is the worker's own path and its code is moved, not rewritten, so the
  claim-time collision, staleness, token and cancel behaviour cannot drift. A caller cannot override it.
- **Unknown or unhandled kind** fails the job with `unknown job kind 'x'` (an unhandled-but-known kind reads
  `no handler for job kind 'proxy'`) before any token is acquired and before the engine, disk or ffprobe is
  touched. Nothing is requeued: requeueing would spin, and Principle I wants the reason on the row.
  The worker keeps running.
- **Handler outcome**: return -> progress 1.0 then `done`; `RenderCancelledError` -> `canceled`; `EngineError`
  -> `failed` with `str(exc)`; any other exception falls through to the existing `_process` catch-all
  (`_fail_unexpected`, so per-job failure isolation holds for every kind). A handler owns its capacity token:
  it receives no pool from the worker here, because the proxy change decides how it acquires the CPU token.
- Graceful shutdown, startup reconciliation and the claim-capacity bound are kind-agnostic already
  (`_inflight`, `find_orphaned_running`); the capacity bound counts a proxy job against `total_capacity`,
  which is acceptable at proxy concurrency 1 and revisited by the proxy change if it matters.
- **Mixed fleet**: an older worker that claims a `proxy` job fails it loud. The documented operating rule is to
  upgrade workers with the API; the alternative (a per-worker kind filter in `claim_next`) is more machinery than a
  version-skew window earns (Principle VII).

### Idempotency and restarts
- Re-running the migration is a no-op under Alembic. `submit` twice for one (project, event, kind) is one row.
- A worker restart mid-job requeues any running row of any kind (`reconcile`); a requeued `proxy` row is
  claimed again and dispatched again.
- `--force` is a render concept (it rides the `force` column) and is ignored by non-render dispatch.

## Risks / Trade-offs

- **A mistake blocks renders** (risk 7) -> the render body moves verbatim; the whole existing suite, including
  `requires_db`, must pass; the migration test upgrades a database that already holds render rows and checks the
  backfill, the index, and a down/up round trip; tests assert the API schema and WS frames carry no `kind`.
- **Reads hide non-render jobs by default** -> deliberate (above); a test pins that `kind=None` sees them, so the
  next change has a tested way to opt in.
- **Downgrade deletes non-render rows** -> documented; derived state only.
- **Old worker, new rows** -> fails loud with a reason; operating rule above.
- **`kind` as free text** -> typos are caught by `JobKind` at every in-repo writer and by the worker for any
  other writer; no database constraint, by decision.

## Migration Plan

`alembic upgrade head` adds the column (server default `'render'`, so existing rows backfill without a rewrite on
PostgreSQL 11+) and swaps the index. Rollback is `alembic downgrade -1` (deletes non-render rows). No rescan, no
`reel.yaml` change, no render fingerprint change, so no event becomes stale.
