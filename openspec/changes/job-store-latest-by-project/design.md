## Context

`latest_by_project(project_root)` returns `dict[event_dir, Job]` holding each event's newest job of any
status, for one project. It backs the events list (one call per `GET /api/v1/events`) and the event
detail, which need "latest job per event" without an N+1 lookup (api-service D-A3). Today it is
`select(Job).where(project_root == …).distinct(Job.event_dir).order_by(Job.event_dir, Job.created_at.desc())`,
i.e. Postgres `DISTINCT ON (event_dir)`.

Re-checked against the code on main (6a7fe16): installed SQLAlchemy is 2.0.51 and the statement compiles
cleanly there; 2.1 deprecates `distinct(<expr>)` as the `DISTINCT ON` spelling and points to
`sqlalchemy.dialects.postgresql.distinct_on`, which is absent from 2.0.x. `pyproject.toml:20` is
`sqlalchemy>=2.0.51` with no cap. The only callers are `api/events_read.py:228` and `:456`; `tests/`
has no direct test of the method.

The `jobs` table has no index on `(project_root, event_dir, created_at)`; only the claim-next and
active-identity indexes. The current query already reads every row of the project, and so will the
replacement.

## Goals / Non-Goals

**Goals:**
- Remove the dependency on the 2.1-deprecated `DISTINCT ON` spelling without raising or capping the
  SQLAlchemy requirement.
- Keep it one query, same result shape, same project scoping.
- Make the tie-break deterministic and cover the method with direct tests.

**Non-Goals:**
- Capping `sqlalchemy<2.1` (postpones the problem and blocks a legitimate upgrade).
- Adding an index or a migration; the read's cost profile is unchanged.
- Changing the API, the events read model, or any other job-store read.
- The `active_job` docstring (see Decisions).

## Decisions

**Window function, not `postgresql.distinct_on`.** Rejected alternatives: the dialect `distinct_on`
extension (2.1 only — breaks the declared floor); a version-conditional import (two code paths for one
query, against Principle VII); a correlated `MAX(created_at)` subquery (ties return two rows and needs a
second dedupe). The chosen shape works on 2.0.x and 2.1 as written:

```python
ranked = (
    select(
        Job.id,
        func.row_number()
        .over(partition_by=Job.event_dir, order_by=(Job.created_at.desc(), Job.id.desc()))
        .label("rn"),
    )
    .where(Job.project_root == project_root)
    .subquery()
)
stmt = select(Job).join(ranked, Job.id == ranked.c.id).where(ranked.c.rn == 1)
```

Selecting the plain `Job` entity (joined on id) keeps ORM-mapped rows, so the result type and the callers'
attribute access are untouched. `func.row_number()` needs the existing `# pylint: disable=not-callable`
convention used for `func.now()` in this module.

**Deterministic tie-break on `id`.** `created_at` is the database's transaction-start `now()`. The
one-active-job-per-event index means two jobs of one event are normally created in different transactions
and so differ, but nothing forbids equal values (a bulk insert in one transaction, a restored dump), and
`DISTINCT ON … ORDER BY created_at DESC` then returned an arbitrary row. `id DESC` is arbitrary but
stable, which is what the contract needs (a repeated read answers the same).

**Statement built by a module-level function.** `_latest_by_project_stmt(project_root)` returns the
`Select`, so a test can compile it with the PostgreSQL dialect and assert it contains `row_number()` and
not `DISTINCT ON`. That is the only check that would catch a regression on SQLAlchemy 2.0.x, where the old
spelling still works at runtime; the behavioural tests cover correctness.

**`active_job` docstring left alone.** Triage suspected its docstring stale ("names the CLI as a
pre-read user"). Re-checked: `cli/commands.py:663` still calls `store.active_job(...)` before
`store.enqueue(...)` to classify the `enqueue` report, and `api/routes/jobs.py:103` still pre-reads before
the staleness gate, so the docstring is accurate. Not a bug; no task. (Observation, out of scope: the CLI
could take its `created` verdict from `submit()` instead of a racy pre-read — a CLI change, not this one.)

## Risks / Trade-offs

- A window function sorts every project job once; `DISTINCT ON` sorted them too. Libraries have hundreds of
  events and a small number of jobs per event, and there is no index to exploit either way. If the
  `jobs` table ever grows large per project, an index on `(project_root, event_dir, created_at DESC)` is a
  separate, measured change.
- The statement-compile test asserts on rendered SQL text; it is intentionally narrow (absence of
  `DISTINCT ON`, presence of `row_number`), not a golden SQL string, so harmless SQLAlchemy formatting
  changes do not break it.
