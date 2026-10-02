## Why

The worker isolates a failing job by catching `EngineError`, and nothing else. In `Worker._process`, the
plan rebuild (`build_job`), the target classification (`resolve_target`) and `_render_and_finish` each catch
`EngineError` (the render also `RenderCancelledError`); `_run_and_untrack` is a bare `try/finally`. Any other
exception — an `OSError` while reading the event, a `TypeError` or `KeyError` from a bug, a failed
`set_progress` write from the progress callback — leaves the job's thread through the `finally` that only
pops `_inflight`. Nothing writes a terminal status:

- the row stays `running` under this worker's id, and the shutdown requeue (`_requeue_inflight`) no longer
  sees it, because the entry is already gone;
- the startup reconcile fixes it only on the next worker boot, and only because that boot has a new nonce id;
- until then the partial unique index `ux_jobs_active_identity` refuses to enqueue the event again
  ("already active"), so the user can neither retry nor see a failure.

Reproduced on `main` at `6a7fe16` with a mock store: a build-time `OSError("disk gone")` and a render-time
`TypeError("boom")` each kill the thread, and the recorded `transition` and `requeue` calls are empty in both
cases. The job-scheduler requirement "Per-job failure isolation" promises that a failure of one job
transitions it to `failed` with the error recorded and never stops the worker; the code only keeps that
promise for the failures somebody thought of. Principle I (fail loud, per-event isolation: reported as
failed, never silently dropped) is the rule that applies. The triage item is
`worker-process-catches-only-engineerror`; earlier fixes (for example the impossible-date `ValueError`) made
single causes into `EngineError`s one at a time, which is the pattern this change ends.

## What Changes

- **A backstop in the worker:** an exception that is not an `EngineError` or a cancellation, raised anywhere
  while a claimed job is processed (build, freshness recheck, classification, progress or cancel writes,
  render), fails that job. Its row ends `failed` with the exception's type and message as the error, the
  traceback is logged, the capacity token is released and the worker keeps claiming.
- **The existing outcomes are untouched:** `EngineError` keeps its specific message, a cooperative cancel
  still ends `canceled`, and a shutdown requeue still ends `queued`. A job that already left `running`
  (a requeue or a cancel that won a race) is not rewritten.
- **The backstop cannot kill the thread itself:** if recording the failure raises (for example the database
  is down), that is logged and swallowed. The row is then left for the next startup reconcile, which is what
  a crash would give today. `KeyboardInterrupt` and `SystemExit` are not caught.
- **Tests** for a build-time `OSError`, a render-time `TypeError`, a `set_progress` that raises, a failing
  backstop transition, and the cancel and shutdown-requeue outcomes staying as they are.
- **Spec:** "Per-job failure isolation" states that any failure, expected or not, fails only that job.

## Non-goals

- **No heartbeat, lease or reaper** for a job whose worker is alive but wedged or whose process dies: that
  stays with startup reconcile (and, for a stuck ffmpeg, the separate `render-stall-watchdog` change).
- **No new error classes** and no change to which causes are `EngineError`. The backstop is the net, not a
  replacement for typed errors.
- **No retry** of a failed job and no change to the `failed` row's shape; `error` is the existing text column.
- **No change to the CLI `render`/`enqueue` batch paths**, which have their own per-event isolation, and no
  change to `api/` or the web app.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `job-scheduler`: `Requirement: Per-job failure isolation` covers any failure while processing a job, not
  only the engine's typed errors, and says cancellation and shutdown requeue keep their own outcomes.

## Impact

- **Baseline:** written against `main` at `6a7fe16`.
- **Packages:** `auto_reel_ng/scheduler` only (`worker.py`). Tests: `tests/test_scheduler_worker.py`.
- **CLI vs API (Principle V):** the worker is a CLI command (`auto-reel worker`); the API is untouched.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, no Alembic migration, no OpenAPI change.
- **Ordering:** `worker-claim-guards` edits the same file after this change merges; it relies on this
  backstop only for causes it cannot type, and keeps raising `EngineError` subclasses for its own.
- **Size (Principle VIII):** one capability delta, one package, 5 tasks.
