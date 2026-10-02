## Context

`FfmpegRuntime.run_with_progress` (`ffmpeg/runtime.py`) is the only caller-visible way a segment is encoded: the
orchestrator's `_normalize_segment` calls it once per normalized segment. It starts ffmpeg with
`-nostats -progress pipe:1`, drains stderr on a daemon thread, and consumes stdout with
`for line in proc.stdout`, which blocks until ffmpeg writes. Nothing bounds that wait, and `should_cancel` is
only consulted by `_check_cancelled` between segments and once before the final assembly. See proposal.md for
why that is a defect.

ffmpeg prints a `-progress` block (`out_time_us=…`, `speed=…`, `progress=continue`) about every 0.5 s while it
works. A healthy encode therefore advances `out_time_us` continually; a wedged one stops printing, or keeps
printing an unchanged `out_time_us`. The silence is the liveness signal D-S5 said did not exist.

Callers of `run_with_progress`: only `render/orchestrator.py` (checked with `grep -rn run_with_progress
auto_reel_ng`). Callers of `should_cancel`: the worker sets it to `lambda: self._cancel_requested(job.id)`,
a `JobStore.get` per call; the CLI's `render` passes none unless a caller does.

## Goals / Non-Goals

**Goals:**
- A segment encode whose output time does not advance for 10 minutes is killed and fails the job loudly.
- A cancel request takes effect within about a second, inside a segment.
- The wait loop cannot itself hang: neither the kill nor the stderr drain may block the failure path forever.
- Everything that finishes behaves exactly as before: same progress callbacks, same errors on non-zero exit.

**Non-Goals:**
- A database heartbeat, reaper or worker registry; a config key or flag; retrying a stalled segment;
  watching the concat, ffprobe or analysis (proposal, Non-goals).

## Decisions

### Research & Decisions

#### What counts as progress

**Context**: The deadline needs one definition of "advanced" that cannot be satisfied by a stuck ffmpeg.
**Explored**: The current parser (`_parse_progress_line`) returns a clamped, non-decreasing fraction and returns
`None` when `duration <= 0` or the value is `N/A`. `progress=continue` blocks repeat every 0.5 s whether or not
the encode moves; a stuck GPU decode typically stops writing, but a stuck filter graph can keep printing the
same `out_time_us`.
**Decision**: The clock resets only when a line carries an `out_time_us`/`out_time_ms` value strictly greater
than the greatest seen so far in this run, or the line is `progress=end`. It is parsed independently of
`duration` (a zero-duration request still advances; only the fraction callback needs the duration). Lines that
repeat, `N/A`, or other keys never reset it. The clock starts when the process is launched, so a hang before
the first frame (opening a file on a dead mount, driver initialisation) counts.
**Rationale**: Output time is the quantity the user's render is waiting on. Counting any output line would let
a spinning ffmpeg defeat the watchdog; counting the fraction would break for `duration <= 0`.

#### The deadline is a constant, owned by the orchestrator

**Decision**: `SEGMENT_STALL_TIMEOUT_S = 600.0` in `render/orchestrator.py`, passed to
`run_with_progress(..., stall_timeout=SEGMENT_STALL_TIMEOUT_S)`. In `runtime.py` the parameter defaults to
`None` (no deadline), so any other caller is unchanged and the runtime stays policy-free; the orchestrator owns
the policy, because the policy is about renders.
**Rationale**: Supervisor decision (module constant, no config key; Principle VII). ffmpeg writes a progress
block about twice a second while it works, so 10 minutes without output time advancing is orders of magnitude
beyond any normal gap and still bounded; no stall figure was measured on a real hung device (none is
reproducible on this host), so the number is a policy choice, not a measurement. Tests set `orch.SEGMENT_STALL_TIMEOUT_S` with `monkeypatch` to a fraction of a second; they do not
wait 10 minutes. `time.monotonic()` is the clock (immune to wall-clock steps, and it does not run during a host
suspend on Linux, so a laptop lid does not read as a stall).
**Alternatives**: A `RenderOptions` field (an option bag for one test seam: rejected, Principle VII); a config
key (rejected by the supervisor); a stall figure derived from the segment's duration (an encode's speed varies
by 100x between CPU and VAAPI, so any derived figure is a guess).

#### A reader thread and a queue, with a short tick

**Context**: A blocking `for line in proc.stdout` cannot also watch a clock or poll cancel.
**Explored**: `selectors` on the stdout fd (text-mode line buffering makes `select` + `readline` unreliable: a
partial line can sit in the TextIOWrapper buffer while the fd reads empty); `asyncio` subprocess (a different
execution model for one method); a watchdog `threading.Timer` that kills the process (works for stall, but
cancel polling and the check would then live in a third place).
**Decision**: A daemon reader thread puts each stdout line on a `queue.Queue` and a final end marker at EOF
(the stderr drain thread already exists beside it). The calling thread loops on `queue.get(timeout=TICK)` with
`TICK = 0.25` s. On every wake, with or without a line, it:
1. handles a line as today (fraction callback, monotonic clamp) and resets the stall clock if out time advanced;
2. if `should_cancel` was given and at least `CANCEL_POLL_INTERVAL_S = 1.0` s passed since the last poll, calls
   it; true means kill and raise `FfmpegCancelledError`;
3. if `stall_timeout` was given and `monotonic() - last_advance >= stall_timeout`, kill and raise the stall
   `FfmpegError`.
Order matters: a cancel wins over a simultaneous stall (the operator asked for it), and both are evaluated only
after any queued line, so a line already received is never discarded.
**Rationale**: `queue.get(timeout)` is the simplest portable blocking-with-deadline. The 0.25 s tick bounds the
detection lag of any deadline test and costs nothing while idle. The cancel poll is once a second, the same
cadence at which `ThrottledProgress` already writes the row, so cancel adds at most one `JobStore.get` per
running job per second.
**Failure behaviour**: `should_cancel` raising (database down) propagates like a raising `on_progress` does
today: ffmpeg is killed, the exception surfaces, the job fails with it. Before this change the same blip would
fail the job at the next boundary; the exposure is higher (once a second) but the policy is unchanged, and
`ThrottledProgress` already writes the same database at the same rate.

#### The kill is bounded

**Context**: SIGKILL does not act on a process in uninterruptible sleep, which is exactly what a wedged GPU
driver produces. `with subprocess.Popen(...)` waits for the child on exit, so a stall handler that kills and
then leaves the `with` could hang in `__exit__`, recreating the bug inside its fix.
**Decision**: `run_with_progress` stops using the context manager for the process and owns teardown:
`proc.kill()`, then `proc.wait(timeout=KILL_GRACE_SECONDS)` (the constant the gate added, 5 s), then
`drain.join(timeout=...)` for the stderr thread. If `wait` times out, it logs an error naming the pid and
command and raises anyway, leaving the process and the two daemon threads to the OS. The stdout/stderr pipes
are closed on the way out. The existing `except BaseException: proc.kill()` path (a failing progress callback)
goes through the same teardown. The gate change `ffmpeg-runtime-utf8-and-timeout` left `_timed_out`, which kills
and then `communicate`s; that cannot serve here, because the reader thread owns the stdout pipe, so a small
`_kill_and_reap` helper is added beside it and shares only the `KILL_GRACE_SECONDS` bound and the abandon log.
The same bound covers the normal path: after stdout reaches EOF the engine waits for the exit status for at
most `KILL_GRACE_SECONDS`; a process that closed its output and still has not exited is killed and reported
as stalled, because today's unbounded `proc.wait()` there is a second place a wedged ffmpeg can hold the job.
**Rationale**: The job must end `failed`/`canceled` and release its token whatever the kernel does with the
child. A leaked unkillable process is visible in the log and in `ps`; an eternal `running` job is not.

#### Two outcomes, two errors

**Decision**: A stall raises `FfmpegStalledError(FfmpegError)` (new, in `errors.py`) with a message of the form `ffmpeg stalled: no progress for 600s
(limit 600s): <cmd>` followed by `stderr:` and the stderr captured so far (empty when the drain could not be
joined). A cancel raises `FfmpegCancelledError(FfmpegError)` (new, in `errors.py`, documented beside
`RenderCancelledError`), message `ffmpeg canceled: <cmd>`.
Both call sites of `run_with_progress` (`_normalize_segment` and `_retry_in_software`) go through one helper,
`_run_segment`, which passes the two keywords, catches `FfmpegCancelledError` *before* the callers' `except
EngineError` and raises
`RenderCancelledError("render canceled during segment N (<label>)") from exc`; the stall falls through the
existing wrapper to `RenderError("normalize failed for segment N (<label>): ffmpeg stalled: …")`.
`render_movie` already deletes the `.part` on any `BaseException`, `_execute` has not reached
`os.replace` or `write_manifest`, and the worker already maps `RenderCancelledError` to `canceled` and any
other `EngineError` to `failed` with the message recorded. **No worker change.**
**Rationale**: A distinct cancel type is required because the layers below `render/` may not import
`RenderCancelledError` (Principle VI: lower layers never import higher ones; `errors.py` is shared). A distinct
stall type is also needed, now that the software-decode retry exists: it decides by scanning the error text, and a
stall's text carries the stderr captured so far, which could hold a hardware-decode phrase from before the hang;
retrying would double the wait. `_hw_decode_init_failure` therefore returns `None` for a `FfmpegStalledError`.

### Order and the neighbouring changes

This change is implemented after both gates have merged to `main`. They touch the same two files:

- `ffmpeg-runtime-utf8-and-timeout` changes `runtime.py`: `encoding="utf-8", errors="backslashreplace"` on
  every `subprocess.run`/`Popen` (including the `run_with_progress` Popen, whose `text=True` becomes the
  explicit pair) and an opt-in `timeout` on `run`/`run_ffprobe`/`_run`. This change keeps the explicit
  encoding on the Popen it reshapes, and names its new keywords `stall_timeout` and `should_cancel`, so they
  never collide with `timeout`. The reader thread reads text lines, so undecodable bytes are already replaced
  and cannot kill the reader.
- `staleness-output-lookup` changes `_execute`'s `write_manifest(...)` call and `staleness/`. This change
  touches `_normalize_segment` and adds a constant; the hunks do not overlap.
- Earlier members of the orchestrator chain also edited `_normalize_segment` and are on `main` now.
  The software-decode fallback retries an `FfmpegError` whose text matches the hwaccel-initialisation
  signatures (`_retry_in_software` is a second `run_with_progress` call site); the retry MUST NOT run for
  `FfmpegCancelledError` (caught first) or for the stall (a retry would double the wait; see above).
  `render-progress-monotonic` changed how `_Progress` weights and clamps steps; the callback passed to
  `run_with_progress` stays a `(fraction) -> None`, so nothing here depends on it.

Task 1.1 re-reads these files on the merged `main` and adjusts only the call-site details if they moved.

### Idempotency and restart

- **Re-run after a stall:** the job is `failed`; no output at the final path (the atomic `.part` is removed),
  no manifest, so the event is still stale and `enqueue` creates a fresh job. A forced job behaves the same.
- **Re-run after a cancel:** as today, the job is `canceled`; the `.part` is removed.
- **Worker restart mid-render (SIGTERM):** unchanged: graceful shutdown requeues in-flight rows. The render
  thread's ffmpeg is not killed by `_requeue_inflight` today; that is unchanged and out of scope.
- **`--force`:** bypasses the staleness gate only; the watchdog applies to forced renders too.

## Risks / Trade-offs

- **A process SIGKILL cannot kill** → the job still fails and frees its token within about
  `KILL_GRACE_SECONDS`; the process is logged by pid and leaks until the kernel releases it. Hardware that
  wedges this way usually also fails the *next* render on that device, which now fails loudly instead of
  queueing behind a ghost.
- **A legitimately silent 10 minutes** (an extremely slow first frame) is killed → 10 minutes is generous
  against the ~0.5 s cadence; if it ever fires on a healthy library the failure message states the limit,
  and the fix is the constant, in one place.
- **Hang outside the watched call** (concat, probes) is still undetected → documented in the proposal as a
  non-goal; the opt-in `timeout` is the later route.
- **Cancel poll load** → one `JobStore.get` per running job per second, bounded by the capacity pools
  (a handful of concurrent jobs).
- **Reader-thread leak on abandonment** → only when the child cannot be reaped; daemon threads end with the
  process.
- **Test timing** → the fake-binary tests use sub-second limits against a 0.25 s tick; assertions bound the
  elapsed time generously (a few seconds) and never assert exact timings.

## Migration Plan

None: no schema, config or on-disk change. Rollback is reverting the commit; no `RENDER_GRAPH_VERSION` is
involved, so no event turns stale.
