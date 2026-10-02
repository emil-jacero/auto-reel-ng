## 1. Baseline

- [x] 1.1 Confirm the code this change was designed against, now that both gates have merged. Stop and report
  to the supervisor if a check fails in a way the design does not cover.
  - `git log --oneline -30 origin/main` contains `ffmpeg-runtime-utf8-and-timeout` and
    `staleness-output-lookup`; the worktree is on that `main`.
  - `grep -n "run_with_progress" -r auto_reel_ng` still lists only `render/orchestrator.py`'s
    `_normalize_segment` as a caller; `grep -n "should_cancel" auto_reel_ng/scheduler/worker.py` still shows
    the `_cancel_requested` lambda.
  - Read `ffmpeg/runtime.py`: note whether the gate left a shared kill-and-reap helper (design, "The kill is
    bounded") and use it; note the `encoding`/`errors` pair on the Popen and keep it.
  - Read `_normalize_segment` and `_retry_in_software` (the software-decode retry): it must not match the
    stall or the cancel error (design, "Order and the neighbouring changes").
  - If the "Cooperative cancellation between segments" requirement in `openspec/specs/job-scheduler/spec.md`
    changed text, re-base this change's MODIFIED block on it and re-run
    `openspec validate render-stall-watchdog --strict`.

  Verify: every check holds, or the difference is in the final report.

## 2. ffmpeg/ — the watchdog, the cancel poll and the bounded kill

- [x] 2.1 Stall watchdog. Add `FfmpegStalledError(FfmpegError)` and `FfmpegCancelledError(FfmpegError)` to `auto_reel_ng/errors.py`
  (docstrings beside `FfmpegTimeoutError`). In `ffmpeg/runtime.py` reshape
  `run_with_progress` as the design describes: a daemon reader thread feeding a `queue.Queue`, a 0.25 s tick,
  the stall clock on strictly-greater `out_time_us`/`out_time_ms` or `progress=end`, parsed independently of
  `duration`, and the new keyword `stall_timeout: Optional[float] = None`. Tests in `tests/test_runtime.py`
  extend the fake binary (new modes, no `has_ffmpeg` marker needed) and use limits of about 0.5 s:
  - ffmpeg prints one `out_time_us` then sleeps: raises `FfmpegStalledError` containing `stalled`, the limit and the
    command, within a few seconds, and the callback saw only the first fraction
  - ffmpeg prints nothing at all: the same error (clock starts at launch)
  - ffmpeg repeats an unchanged `out_time_us` and `progress=continue` forever: the same error
  - ffmpeg advances its output time every 0.1 s for longer than the limit, then ends: no error, fractions
    non-decreasing (a steady encode is never stalled)
  - `duration=0` with an advancing output time and a limit: not stalled
  - no `stall_timeout`: every existing test in the file passes unchanged (`flood`, `flood-fail`, `slow`
    callback failure)
  Verify: `.venv/bin/python -m pytest tests/test_runtime.py` passes, each new case bounded by `_within`.
- [x] 2.2 Cancel poll. Add `should_cancel: Optional[Callable[[], bool]] = None` to `run_with_progress`; the
  wait loop polls it at most once per `CANCEL_POLL_INTERVAL_S = 1.0`, kills ffmpeg on true and raises
  `FfmpegCancelledError` (checked before the stall test in the same wake). A raising check kills ffmpeg and
  propagates. Tests: a check that turns true after 0.3 s against a sleeping fake raises
  `FfmpegCancelledError` (not `FfmpegError`'s stall text) within 3 s; a check that returns false never ends the
  run and is called about once per second (count the calls over a 2.5 s run and assert at most 4); a raising check propagates its exception and the child is dead
  (`proc.poll()` is not `None`, found through the fake's pid file). Verify: `-k cancel` selection passes.
- [x] 2.3 Bounded kill. Replace `with subprocess.Popen` in `run_with_progress` with explicit teardown: kill,
  `wait(timeout=KILL_GRACE_SECONDS)`, bounded `drain.join`, pipes closed, in a `_kill_and_reap` helper (the
  gate's `_timed_out` cannot be reused: it `communicate`s); on an unreapable child log an error with the pid
  and command and still raise the original error. The existing `BaseException` kill path uses the same teardown. Test: monkeypatch
  `subprocess.Popen` with a stub whose `wait` raises `TimeoutExpired` and whose stdout never yields, set
  `KILL_GRACE_SECONDS` to 0.2 s, and assert the stall error is raised within a few seconds and an error
  record naming the pid was logged (`caplog`). Second test: a fake that closes stdout (`os.close(1)`) and then sleeps raises the stall error after
  the reap bound. Verify: both tests pass and the 2.1 and 2.2 tests still do.

## 3. render/ — wire the policy and map the errors

- [x] 3.1 In `render/orchestrator.py` add `SEGMENT_STALL_TIMEOUT_S = 600.0` (comment: policy constant, no
  config key) and pass `stall_timeout=SEGMENT_STALL_TIMEOUT_S, should_cancel=options.should_cancel` from a `_run_segment`
  helper that both `_normalize_segment` and `_retry_in_software` call. The helper catches
  `FfmpegCancelledError` (before the callers' `except EngineError`) and raises
  `RenderCancelledError(f"render canceled during segment {index} ({label})") from exc`; update
  `_check_cancelled`'s and `RenderCancelledError`'s docstrings (no longer "rather than mid-ffmpeg"). Tests in
  `tests/test_render.py` with a recording stand-in for `runtime.run_with_progress`: it receives the 600 s
  constant and the options' `should_cancel`; a raised `FfmpegCancelledError` surfaces as
  `RenderCancelledError` naming the segment; a raised stall `FfmpegError` surfaces as `RenderError` whose
  message contains `normalize failed for segment 0` and `stalled`; neither leaves an output, a `.part` or a
  manifest; a stall whose stderr carries a hardware-decode phrase is not retried in software
  (`FfmpegStalledError`), and a cancel during the software retry surfaces as `RenderCancelledError`. Verify: the new tests pass with the existing cancellation tests in section 9 of that file.
- [x] 3.2 End-to-end through `render_movie` with the real orchestrator and a fake ffmpeg (`has_ffmpeg`, since
  the clips and probes use the real binaries): build a `FfmpegRuntime` with the fake script as ffmpeg and the
  real `ffprobe`, probe a generated clip first with the real runtime, set
  `monkeypatch.setattr(orch, "SEGMENT_STALL_TIMEOUT_S", 0.5)`, and render a one-clip plan whose fake ffmpeg
  hangs after one progress line. Assert `RenderError` mentioning the stall, the elapsed time under 10 s, no
  `Movie.mp4`, no `Movie.mp4.part`, and that the per-render scratch directory under `temp_dir` was removed.
  Second case: `should_cancel` becomes true after the fake started; assert `RenderCancelledError` within 5 s
  and the same absence of files. Verify: both tests pass; run them twice to check they are not timing-flaky.

## 4. Docs

- [x] 4.1 `README.md`: in the `jobs list|show|cancel` bullet, replace the between-segments and "no
  mid-ffmpeg kill" sentences with the cancel-within-about-a-second behaviour; in "Requeue-on-restart"
  replace the "no heartbeat / hung-worker detection" sentence with the stall watchdog (10 minutes without
  output-time advance fails the job; a wedged worker process is still only recovered by the next boot's
  reconcile; no heartbeat); fix the cancel sentence in the API paragraph ("the worker stops it between
  segments"). `docs/high-level-design.md`: add **D-19** after D-17 recording the policy (in-process
  watchdog, definition of progress, 10 minutes as a constant, bounded kill, the heartbeat/reaper and the
  concat/probe coverage deferred until multi-worker support / a follow-up). Verify:
  `grep -n "mid-ffmpeg\|hung-worker\|between segments" README.md` shows no stale claim, and D-19 is present.

## 5. Validation gates

- [x] 5.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` (only the known
  cairo `no-member` noise). Verify: all clean.
- [x] 5.2 `.venv/bin/python -m pytest` (podman for the `requires_db` tests; otherwise
  `-m "not requires_db"` and say so). Also run `openspec validate render-stall-watchdog --strict`. Verify: the
  suite passes and the change validates.
