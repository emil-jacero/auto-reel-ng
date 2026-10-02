## 1. persistence/

- [x] 1.1 In `auto_reel_ng/persistence/job_store.py`, add a module-level `_latest_by_project_stmt(project_root)`
  that ranks the project's jobs with `row_number() OVER (PARTITION BY event_dir ORDER BY created_at DESC,
  id DESC)` in a subquery, joined back to `Job` on `id` and filtered to rank 1; make `latest_by_project`
  execute it and return `{job.event_dir: job}`. Drop `.distinct(...)`, keep it one query, and rewrite the
  docstring to describe the window-function approach and the deterministic tie-break (no pyproject change).
  Test: covered by 2.1–2.4.

## 2. tests/ (`tests/test_job_store.py`)

- [x] 2.1 Test `latest_by_project` directly (`requires_db`): `Grillning` with `done` → `failed` →
  `queued` jobs and `Blandat` with one job under `PROJECT_ROOT` yield two entries, each the newest job of
  its event whatever its status (insert with explicit, distinct `created_at` values through a session so the
  order is not subject to transaction timing).
- [x] 2.2 Test scoping: another project's job for the same event and a job with `project_root` NULL do not
  appear, and the other project's own read returns its own job; a project with no jobs returns `{}`.
- [x] 2.3 Test the tie: two jobs of one event inserted with an identical `created_at`; two consecutive reads
  return the same job id.
- [x] 2.4 Test that `_latest_by_project_stmt("/p")` compiled with the PostgreSQL dialect contains
  `row_number()` and does not contain `DISTINCT ON`, so a regression to the deprecated spelling fails on
  SQLAlchemy 2.0.x too.

## 3. Validation gates

- [x] 3.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  clean.
- [x] 3.2 `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` clean (only
  the known cairo `no-member` noise), with the `not-callable` disable on `func.row_number()` if pylint
  flags it.
- [x] 3.3 `.venv/bin/python -m pytest` green, including `tests/test_job_store.py` and the events-read API
  tests that call `latest_by_project`.
