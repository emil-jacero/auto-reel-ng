## Context

See proposal.md, "Why". The code on `main` at `6a7fe16`, `auto_reel_ng/scheduler/worker.py`:

- `run()` claims a job and `_spawn`s a daemon thread running `_run_and_untrack(job)`, which calls
  `_process(job)` inside `try/finally` that pops `_inflight`. `process_next()` (tests, single-threaded use)
  calls `_process` directly in the caller's thread.
- `_process` has `except EngineError` at the build and the `resolve_target` classification, and
  `_render_and_finish` handles `EngineError` and `RenderCancelledError` around the render. After `token.acquire()` the render
  runs inside `try/finally: token.release()`.
- Work that is not covered by any handler includes: the progress callback (`ThrottledProgress` ->
  `JobStore.set_progress`), the cancel poll (`_cancel_requested` -> `JobStore.get`), the claim-time
  `_is_fresh` (`evaluate`), `set_progress(1.0)` and anything an injected `build_job`/`render` raises.
- `_safe_transition` swallows `IllegalJobTransitionError` (the row left `running` under us, usually the
  shutdown requeue). `JobStore.transition` only moves a `running` row, so a late write cannot clobber a
  `queued` or `canceled` row.
- A thread that dies without a transition leaves a `running` row that `_requeue_inflight` cannot see (the
  entry is popped) and `ux_jobs_active_identity` keeps blocking re-enqueue of the event.

## Goals / Non-Goals

**Goals:**
- Every `Exception` raised while processing a claimed job ends in a terminal `failed` row (unless the row
  already left `running`), with a message an operator can act on.
- One place, so a new call added to `_process` later is covered without remembering to catch it.
- The thread and the claim loop survive, and the capacity token is always released.

**Non-Goals:** liveness of a worker that is alive but stuck, retries, error taxonomy changes. See
proposal.md, "Non-goals".

## Decisions

### One backstop around the whole of `_process`

The current body of `_process` becomes `_process_job` unchanged; `_process` is

```python
def _process(self, job: Job) -> None:
    try:
        self._process_job(job)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        self._fail_unexpected(job, exc)
```

Because `process_next()` and `_run_and_untrack` both go through `_process`, one `except` covers the threaded
and the synchronous paths. The typed handlers stay inside `_process_job`, so they run first and keep their
message and the cancel semantics; the backstop only sees what they let through. The token `finally` is also
inside `_process_job`, so the capacity token is released before the backstop writes anything.

Alternatives: wrapping `_run_and_untrack` only (leaves `process_next`, and its tests, uncovered, and the
fix would then not be the thing the tests exercise); a `try/except` at each of the unprotected calls
(the status quo, which missed these and will miss the next).

### The error text and the log

`_fail_unexpected` logs with `logger.exception` (the traceback goes to the worker log) and writes
`error = f"{type(exc).__name__}: {exc}"` through `_safe_transition(..., FAILED, error=...)`; an exception
with an empty message gives the bare type name. The row keeps one line: the traceback is for the log, the
job error is for the GUI and `jobs show`. Naming the type matters because `str(KeyError("x"))` or a bare
`TypeError()` says little alone.

### The backstop's own write is guarded

`_fail_unexpected` wraps `_safe_transition` in `try/except Exception` that only logs
(`logger.exception("job %s: could not record failure")`). Reason: the usual cause of a failing write here is
the database itself, and an exception from the backstop would kill the thread, which is the bug again.
`_safe_transition` already turns `IllegalJobTransitionError` into a warning, so a requeue or cancel that won
the race is respected. When the guarded write fails, the row stays `running` for the next startup
reconcile; that is no worse than today and cannot be improved without a heartbeat (out of scope).

### What is not caught

`except Exception` only. `KeyboardInterrupt` and `SystemExit` pass through (a signal handler or an
explicit exit is not a job failure). `RenderCancelledError` and `EngineError` are handled before the backstop.
An unexpected exception while `cancel_requested` is set still ends `failed`: a cancel produces
`RenderCancelledError` from the engine, so anything else is a real error and is reported as one.

### No spec text about internals

The spec requirement states the observable result (failed, error recorded, other jobs unaffected, cancel
and requeue unchanged). The names `_process` and `_fail_unexpected` stay in this document.

## Risks / Trade-offs

- [A broad catch can hide bugs] -> it logs the traceback and records the type and message on the row, so the
  failure is louder than the silent hang it replaces (Principle I).
- [The job fails where a retry might succeed, for example a transient `OSError`] -> the user can enqueue
  again at once because the row is terminal; auto-retry is not added.
- [A failed backstop write leaves the row `running`] -> unchanged from today; the next worker start
  requeues it. Logged so it is visible.
- [Overlap with `worker-claim-guards`] -> it edits `default_build_job` and `cli/build`, not `_process`; its
  errors stay typed and keep their exact messages through the existing `EngineError` handler.
