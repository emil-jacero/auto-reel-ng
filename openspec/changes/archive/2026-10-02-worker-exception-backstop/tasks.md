## 1. Baseline

- [x] 1.1 Confirm the code this change was designed against. Stop and report if a check fails in a way the
  design does not cover. `git diff 6a7fe16 -- auto_reel_ng/scheduler/worker.py tests/test_scheduler_worker.py openspec/specs/job-scheduler/spec.md`
  prints nothing (or the difference is read and the MODIFIED block re-based on the current spec text), and
  `grep -n "except EngineError\|except Exception" auto_reel_ng/scheduler/worker.py` shows only the three
  `EngineError` handlers.

## 2. scheduler/ — an unexpected exception fails the job

- [x] 2.1 Red first, in `tests/test_scheduler_worker.py` (real Postgres, stubbed engine, `process_next()`):
  a `build_job` raising `OSError("disk gone")`; a `render` raising `TypeError("boom")`; a `render` that calls
  `options.on_progress(0.5)` with `JobStore.set_progress` patched to raise `RuntimeError("db down")`. Each
  asserts the job is `failed` and `error` equals `"OSError: disk gone"`, `"TypeError: boom"` and
  `"RuntimeError: db down"`, and a second queued job is still claimable afterwards. Verify the three fail on
  the unchanged worker (the exception escapes `process_next`).
- [x] 2.2 Add the backstop to `auto_reel_ng/scheduler/worker.py` as in the design: `_process` wraps the
  renamed `_process_job` in `except Exception`, and `_fail_unexpected` logs the traceback, writes the failure
  through `_safe_transition` with `Type: message` (bare type for an empty message), and guards that write with
  its own logging-only `except Exception`. Verify the 2.1 tests pass, `.venv/bin/python -m mypy auto_reel_ng`
  is clean, and `.venv/bin/python -m pylint auto_reel_ng/scheduler/worker.py` reports nothing beyond the
  intentional `broad-exception-caught` disables.
- [x] 2.3 Tests that pin what the backstop must not change, in the same file:
  - threaded path: under `run(max_polls=...)` a render raising `TypeError` leaves the job `failed`, nothing
    stays in `_inflight`, and the worker claims and finishes the next job;
  - capacity: after an unexpected render exception the (cpu capacity 1) token can be acquired again;
  - cancel: the existing cancel-between-segments and pre-claim cancel tests still end `canceled`, and a
    render raising `RenderCancelledError` is not turned into `failed`;
  - shutdown requeue: a render that requeues its own row and then raises `TypeError` leaves the row `queued`
    with no error and no exception out of `process_next()`;
  - guarded write: with `JobStore.transition` patched to raise `RuntimeError` on the backstop's write,
    `process_next()` returns without raising and the token is released.

  Verify `.venv/bin/python -m pytest tests/test_scheduler_worker.py` passes.

## 3. Validation

- [x] 3.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng`, and the full
  `.venv/bin/python -m pytest` including `requires_db` (podman). Then run
  `openspec validate worker-exception-backstop --strict`. Verify all are clean or green, apart from the known
  cairo `no-member` noise and the five font-dependent skips.
