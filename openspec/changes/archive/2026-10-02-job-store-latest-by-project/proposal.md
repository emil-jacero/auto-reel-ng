## Why

`JobStore.latest_by_project` — the read behind the events list and the event detail
(`api/events_read.py`) — selects "the most recent job per event" with
`select(Job).distinct(Job.event_dir)`. SQLAlchemy 2.1 deprecates passing an expression to
`distinct()` to produce `DISTINCT ON` (`SADeprecationWarning`, an error under `-W error`; the
replacement, `postgresql.distinct_on`, does not exist in 2.0.x). `pyproject.toml` pins
`sqlalchemy>=2.0.51` without an upper bound, so the next resolver run that picks 2.1 turns the events
list into a deprecation warning, and into a failure wherever warnings are errors. The behaviour is also
specified nowhere in `job-store` and no test calls the method directly (only the API's events tests reach
it, indirectly).

## What Changes

- `latest_by_project` computes "latest job per event" with a `ROW_NUMBER() OVER (PARTITION BY event_dir
  ORDER BY created_at DESC, id DESC)` subquery filtered to row 1, which behaves identically on SQLAlchemy
  2.0.x and 2.1 — no dependency pin edit, no `DISTINCT ON`. Still a single query.
- The tie between two jobs of one event with an identical `created_at` is broken by `id`, so the answer
  is deterministic (`DISTINCT ON` left it to the planner).
- `job-store` gains a requirement pinning the read's behaviour (project-scoped, any status, one job per
  event, newest wins), which was previously unspecified.
- Direct `requires_db` tests for the read, plus a statement-level guard that the query no longer renders
  `DISTINCT ON`.

No change to the `jobs` table, no migration, no new dependency, no change to what the API returns.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `job-store`: adds the "Latest job per event in a project" requirement (an ADDED requirement — the read
  existed but its contract was never written down; no current requirement text changes).

## Impact

- Code: `auto_reel_ng/persistence/job_store.py` (`latest_by_project` and a module-level statement
  builder). Callers (`api/events_read.py`, two sites) are untouched.
- Tests: `tests/test_job_store.py`.
- Rendered output: unchanged, so `RENDER_GRAPH_VERSION` is not bumped.
- Dependencies: none; `sqlalchemy>=2.0.51` stays as is.
