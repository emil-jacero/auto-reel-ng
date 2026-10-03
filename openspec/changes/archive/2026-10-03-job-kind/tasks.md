## 1. persistence/

- [x] 1.1 Add the `JobKind` StrEnum (`render`, `proxy`) and `Job.kind` (text, not null, default `render`, server
  default `'render'`) to `persistence/models.py`, and widen `ux_jobs_active_identity` to (`project_root`,
  `event_dir`, `kind`). `requires_db` tests in `tests/test_job_store.py`: a new row has `kind = render`; a
  render and a proxy for one event are active together; a second active job of either kind is rejected; a
  `thumbnails` kind row is stored; a finished job does not block.
- [x] 1.2 Alembic revision after `505f2d2c5ca1`: add the column with the server default, then swap the index
  for the widened one in the same transaction; `downgrade` deletes non-render rows, drops the wider index and the
  column, and recreates the original index. `requires_db` tests in `tests/test_persistence_migrations.py`:
  `upgrade head` from empty gives the columns (add `kind` to `_EXPECTED_COLUMNS`) and the drift test still
  passes; upgrading a database at the previous revision that holds `queued`, `running` and `done` rows
  backfills every row to `render` and keeps an active row blocking a second active render; `downgrade -1` with
  a render and a proxy job active succeeds and leaves only the render, then `upgrade head` again is clean.
- [x] 1.3 `JobStore.submit`, `enqueue` and `active_job` (and `_active_job`) take `kind` (default
  `JobKind.RENDER`); the unique-violation fallback looks up the active job of that kind. `requires_db`
  tests in `tests/test_job_store.py`: enqueue is idempotent per kind (the proxy scenario: created, not created,
  render untouched); the active-job lookup is per kind; two concurrent proxy enqueues for one event yield one
  *created*; all existing enqueue tests pass unmodified.
- [x] 1.4 `list_by_status`, `list_finished_since` and `latest_by_project` take `kind` (default render; `None`
  = every kind); the latest-per-event query filters before ranking. `claim_next`, `get`, `transition`,
  `cancel`, `requeue` and `find_orphaned_running` stay kind-agnostic. `requires_db` tests in
  `tests/test_job_store.py`: the four read scenarios of the `job-store` delta (reads default to render, a
  finished proxy is not a finished render, a newer proxy does not displace the latest render and an
  event with only a proxy has no entry, `get` by id returns a proxy), `kind=None` sees both kinds, and
  `claim_next` claims a higher-priority proxy before an older render and a render before an older
  equal-priority proxy by FIFO.

## 2. scheduler/

- [x] 2.1 `Worker` gains `kind_handlers: Mapping[str, KindHandler] | None`; `_process_job` dispatches: `render`
  runs today's body moved verbatim into `_process_render`; any other kind runs its handler (return -> progress
  1.0 and `done`; `RenderCancelledError` -> `canceled`; `EngineError` -> `failed` with the message; any other
  exception -> the existing `_process` catch-all); a kind with no handler fails the job with a reason naming
  the kind before any token, build or ffprobe; a handler registered under `render` raises `ValueError` at
  construction. Tests in `tests/test_scheduler_worker.py` (stubbed engine, as the existing ones): each
  scenario of the `job-scheduler` "dispatched by its kind" requirement, asserting the unhandled kind took no
  token (a pool whose token would raise or block), ran no build (`build_job` stub not called) and left the next
  `render` job to render, and that a restart-requeued proxy job reaches the handler again.
- [x] 2.2 `_refuse_running_output` lists running jobs with the default render scope so a `proxy` job claims no
  output. Test in `tests/test_scheduler_worker.py`: with a `running` proxy job for the same event, the claimed
  render is not refused; the existing collision tests pass unmodified.

## 3. Render behaviour unchanged

- [x] 3.1 Add a regression test (`tests/test_api_jobs.py`) with a `queued` render job plus a `queued` proxy
  job for one event in the store: `GET /jobs`, an event's `latest_job` and the WebSocket frames
  are identical to the render-only case, and the published `JobOut` schema has no `kind` property. Run the
  existing suites for the touched surfaces unmodified (`tests/test_job_store*.py`, `tests/test_scheduler_*.py`,
  `tests/test_api_jobs*.py`, `tests/test_api_ws*.py`, `tests/test_cli_jobs.py`, `tests/test_api_events*.py`) and
  confirm no existing assertion was edited other than the column list in 1.2.

## 4. Documentation

- [x] 4.1 HLD (`docs/high-level-design.md`): in the §4.10 v2 bullet note that proxy generation is a job of its own
  kind (`proxy`) in the durable queue, with one active job per (project, event, kind), reads defaulting to
  `render`, and an unhandled kind failing loud; in the §6 item 9 entry note that `job-kind` has landed as the
  first GUI v2 slice (no render, fingerprint, API or WebSocket change, so no `RENDER_GRAPH_VERSION` bump); and
  add a forward pointer that the proxy contract is recorded as D-21 and the timeline as D-20 by their own
  changes (D-18 and D-19 are taken), without writing either decision here. Verify by grep that D-20/D-21 are
  referenced only as pointers and that no existing D-n text changed.

## 5. Validation gates

- [x] 5.1 `black` and `isort` on `auto_reel_ng tests` leave no diff; `mypy auto_reel_ng` and `pylint
  auto_reel_ng` are clean (modulo the known cairo noise).
- [x] 5.2 Full `.venv/bin/python -m pytest` including `requires_db` passes with the throwaway Postgres;
  `alembic upgrade head` runs clean on an empty database and `alembic downgrade -1 && alembic upgrade head`
  round-trips.
