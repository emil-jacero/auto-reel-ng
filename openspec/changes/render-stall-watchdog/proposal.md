## Why

A render whose ffmpeg is alive but not making progress (a wedged VAAPI driver, a clip on a mount that stopped
answering) holds its job `running` forever, and nothing can stop it. `job-scheduler` decision **D-S5**
requeues only the `running` rows a *dead* worker left behind, and rejected a started-at cutoff because a long
render legitimately outlasts any cutoff and the engine had no liveness signal (HLD §6 phase 7). That signal
now exists in the process that needs it: `FfmpegRuntime.run_with_progress` already reads ffmpeg's `-progress`
stream line by line. What it lacks is any use of the silence:

- **No stall detection.** `run_with_progress` blocks in `for line in proc.stdout` with no deadline. A hung
  ffmpeg keeps the loop, the job thread, the job's capacity token and its `running` row forever, and the
  worker keeps counting it against its in-flight limit (README: "no heartbeat / hung-worker detection").
- **No mid-segment cancel.** **D-S6** polls `should_cancel` only between segments
  (`render/orchestrator.py` `_check_cancelled`), so `jobs cancel` on a job stuck inside a segment sets a flag
  that is never read. A stuck ffmpeg segment can be neither canceled nor killed; a healthy one delays a cancel
  by a whole segment's encode (README: "seconds to roughly a minute on VAAPI", more for a long clip).

Principle I: a render that cannot finish must end as `failed` with the failing ffmpeg invocation, not as an
eternal `running`. The supervisor chose the in-process answer over a database heartbeat and reaper (which
would also need a migration and a worker registry before a second worker is safe): the heartbeat/reaper stays
deferred until multi-worker support needs it.

This is part of the pre-v1 bug round that follows HLD §6 phase 7 (scheduler) and runs alongside phase 8
(GUI v1). It depends on no open §8 research item.

## What Changes

- **A stall watchdog on every segment encode.** While `run_with_progress` runs ffmpeg for a segment, it
  tracks the last time ffmpeg's reported output time (`out_time_us`) *advanced*. If it does not advance for
  **10 minutes** (a module constant, no config key), the runtime kills ffmpeg, reaps it, and raises a typed
  `FfmpegStalledError(FfmpegError)` naming the stall and the invocation. The orchestrator already wraps that as
  `RenderError: normalize failed for segment N (...)`, so the job ends `failed` with that text through the
  worker's existing path, its `.part` is removed, its GPU token is released, and no manifest is written.
- **Mid-segment cancel.** The same wait loop polls the caller's `should_cancel` about once a second. A true
  result kills ffmpeg and raises a new `FfmpegCancelledError`, which the orchestrator turns into
  `RenderCancelledError` exactly as the between-segment check does, so the job ends `canceled` within about
  a second of the request instead of after the segment. The between-segment polls stay.
- **Bounded kill.** After the kill, the runtime waits at most 5 s (the runtime's existing `KILL_GRACE_SECONDS`) for the process to exit. A process that
  does not die (uninterruptible driver sleep) is abandoned with a logged error rather than waited on, so the
  job still fails instead of re-creating the hang inside the cleanup.
- **Docs and spec.** `ffmpeg-runtime` states the watchdog and cancel contract; `job-scheduler`'s cancellation
  requirement is renamed and widened from "between segments" to "of a running render" (cancel latency and the
  mid-ffmpeg kill that README says does not exist), and gains a requirement for the stalled job's outcome.
  README corrects the cancel-latency and hung-worker sentences; HLD gets **D-19** so the policy and the
  deferral outlive the change.

## Non-goals

- **No database heartbeat, no `jobs.heartbeat_at`, no reaper, no worker registry, no Alembic migration**
  (supervisor decision). A hung *process that never reaches the watchdog* (the worker itself wedged, the
  machine down) is still only recovered by the next worker boot's reconcile (D-S5). Multi-worker safety is
  unchanged: reconcile still assumes one worker.
- **No configurable timeout and no new flag or config key** (supervisor; Principle VII). The 10 minutes is a
  constant in `render/orchestrator.py`.
- **Only progress-streaming segment encodes are watched.** The final stream-copy concat (`runtime.run`), every
  ffprobe call (`probe_media`, the copy-uniformity check) and analysis keep running unbounded and
  uncancellable mid-call. The concat is a bounded stream copy and the probes are short; the
  `ffmpeg-runtime-utf8-and-timeout` change adds an opt-in `timeout` to `run`/`run_ffprobe` that a later
  change can apply to them. Running the concat through the watchdog is a candidate follow-up, not included
  (it would also have to move the progress weights that `render-progress-monotonic` is reworking).
- **No retry after a stall.** A killed segment fails the job; re-enqueuing is the operator's call. A stall is
  not retried automatically, and the software-decode retry in `_retry_in_software` must not match it (a stall is a `FfmpegStalledError`,
  which the retry skips even when its captured stderr carries a hardware-decode phrase).
- **No change to what a render produces.** No `RENDER_GRAPH_VERSION` bump.
- **No change to the CLI's or API's surface.** No new command, flag, endpoint or WebSocket field.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ffmpeg-runtime`: ADDED `Requirement: A progress run is stopped when it stalls or is canceled`: the
  stall deadline on `-progress` advance, the cancel poll, the bounded kill, and the two typed errors (`FfmpegStalledError`, `FfmpegCancelledError`).
- `job-scheduler`: `Requirement: Cooperative cancellation between segments` is RENAMED to `Cooperative
  cancellation of a running render` and MODIFIED (cancel takes effect inside a segment, not only at its
  boundaries); ADDED `Requirement: A stalled render fails its job`.

The triage named `movie-assembly` as the second capability. The orchestrator behaviour is fully observable
through these two (job end states, no output at the final path), and the existing job-scheduler requirement
would otherwise keep promising "between segments" against code that cancels inside one, so this change edits
that capability and leaves `movie-assembly` alone (the two-delta limit).

## Impact

- **Baseline:** written against `main` at `6a7fe16`. It is implemented after `ffmpeg-runtime-utf8-and-timeout`
  and `staleness-output-lookup` merge (design, "Order and the neighbouring changes"); task 1.1 re-checks the
  code against the design first.
- **Packages:** `ffmpeg/` (`runtime.py`: the wait loop, two keyword arguments, the kill) and `render/`
  (`orchestrator.py`: one constant, the call site, the error mapping). `errors.py` gains `FfmpegStalledError` and `FfmpegCancelledError`
  (it is the shared error module, not a package). Tests: `tests/test_runtime.py`, `tests/test_render.py`.
  Docs: `README.md`, `docs/high-level-design.md` (D-19). Wording only, no behaviour: the `jobs cancel` CLI message (`cli/commands.py`) and a `JobStore.request_cancel` docstring
  (`persistence/job_store.py`) said "between segments".
- **CLI vs API (Principle V):** both, through the engine and with no surface of their own. `auto-reel render`
  gets the stall watchdog (a stalled event is reported failed by the batch, the rest still render);
  `worker` and therefore the API's jobs get that plus mid-segment cancel, because only the worker supplies
  `should_cancel`.
- **Complexity (Principle VII):** a reader thread and a queue replace a blocking `for line in proc.stdout`
  loop in one method. No new dependency, no new config.
- **Rendered output:** unchanged for every input that finishes. **No `RENDER_GRAPH_VERSION` bump**, and the
  staleness fingerprint inputs are unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. OpenAPI and
  `web/openapi.json` unchanged.
- **Operators:** a render with no output-time advance for 10 minutes now fails (it used to hang). A slow but
  advancing render is never killed. A hung ffmpeg that ignores SIGKILL leaks that one process (design, Risks).
- **Size (Principle VIII):** two capability deltas, two packages, 8 tasks.
