## Context

`render_movie` -> `_execute` (`render/orchestrator.py`) runs, per segment, either "copy" (a copy-eligible
source segment is used in place) or `_normalize_segment` (one ffmpeg run with `-progress`, its local fraction
forwarded through `_Progress.step(index)`). Then `is_copy_uniform` probes the set; if it is not uniform and
copied segments exist, `_execute` re-normalizes every copied segment through `_normalize_segment` again,
passing the same `_Progress`. A final `runtime.run(concat_command)` has no progress; `progress.complete(n)`
reports `1.0` after it. Today `_Progress(len(segments)+1)` maps `step(index)` to `(index + local) / total`:
equal slots, positioned by segment index.

The worker installs `ThrottledProgress(store, job.id)` as `on_progress`
(`scheduler/worker.py`); it writes on first call, on a delta of 0.01, on a 1 s interval, or on `>= 1.0`, and
`JobStore.set_progress` clamps only to `[0, 1]`. A requeued job gets a new `ThrottledProgress` and a row reset
to `progress = 0.0`, so state held per instance is per job run. The CLI (`cli/build.py`) passes the same
callback type.

The gate `render-vaapi-software-decode-fallback` has merged: `_normalize_segment` retries a source segment once
(`_retry_in_software`) with software decode after a hardware-decode-init `EngineError`. That retry calls
`run_with_progress` a second time with the same `progress.step(index)` callback, so a segment can report `0.6`
and then, on retry, start again at `0.0`. This change must hold for it.

## Goals / Non-Goals

**Goals:**
- The `on_progress` sequence of one render is strictly increasing; the stored job progress never decreases.
- Weights follow expected work; copy is free; the re-encode pass is a forward stretch, not a rewind.
- Two call sites change (`_Progress` plus its three uses in `_execute`, and `ThrottledProgress`); no new
  public API and no new config key.

**Non-Goals:**
- Accuracy against wall-clock time, per-pass progress in the API, an ETA, progress inside the concat.
- Changing `FfmpegRuntime.run_with_progress` (already per-call monotonic), `set_progress` or the job schema.

## Decisions

### 1. `_Progress` holds a high-water mark and only emits increases
`_Progress` keeps `_high` (starts `0.0`) and one private `_emit(value)`: `value = min(1.0, value)`; if
`value <= _high` it returns; otherwise `_high = value` and the callback is called. Every path (step
callbacks, `advance_to`, `finish`) goes through it. This is the safety net: whatever the weights do, nothing
lower than a value already delivered reaches the callback, which also covers the gate's per-segment retry
(the retry's restart from `0.0` is swallowed until it passes the earlier point). A step callback delivers
nothing when `_callback` is `None` (unchanged: `step` returns `None`, so `run_with_progress` skips parsing).

### 2. Weights and phases (module constants)
```python
_CONCAT_SHARE = 0.05      # top of the span: [0.95, 1.0]
_REENCODE_SHARE = 0.15    # reserved only when a copy-eligible segment exists: [0.80, 0.95]
```
- `normalize_end = 1.0 - _CONCAT_SHARE - (_REENCODE_SHARE if any copy-eligible segment else 0.0)`, so the
  normalize pass spans `[0, normalize_end]` and the whole `0.95` goes to it when nothing can be re-encoded.
- Weight of a normalized segment: `segment.span_duration`, else `options.clip_facts[identity].duration` (a
  whole clip), else `0.0` (a source segment with no facts fails loudly in `_build_segment_command` anyway;
  the weight is only an estimate, never written anywhere). Weight of a copy-eligible segment in the normalize
  pass: `0.0`. `_Progress` is built from these weights and returns for `step(index)` a callback mapping the
  local fraction `f` to `cum_before[index] + weight[index] * f` over the pass total, scaled into the pass
  interval. A pass whose total weight is `0` (all copy) has nothing to scale and `step` is never asked.
- Re-encode pass: `progress.begin_reencode(copied_indices)` is called when `is_copy_uniform` is false and
  `copied_indices` is non-empty. It sets the pass interval to `[_high, normalize_end + _REENCODE_SHARE]` and
  weights each copied segment by its duration (same function). `step(index)` then refers to the re-encode
  mapping. Starting from `_high` instead of a fixed `normalize_end` means an all-copy event whose first check
  fails sweeps `0.0 -> 0.95` over the re-encode, and a mixed event continues from where it stopped.
- When `is_copy_uniform` is true at the first check, `progress.advance_to_concat()` emits the start of the
  concat share (`1.0 - _CONCAT_SHARE`). After a re-encode pass the same call follows the second check. After
  the concat, `progress.finish()` emits `1.0`. No `complete(index)` call remains for a copy-eligible segment
  (the all-copy jump is gone); the method is removed.
- Order in `_execute` stays: normalize loop, `is_copy_uniform`, optional re-encode loop,
  second `is_copy_uniform` (raising `RenderError` if still not uniform, unchanged), cancel check, measured
  durations, concat, `finish()`.

**Signatures** (private; names are for the implementation, not the spec):
```python
class _Progress:
    def __init__(self, callback: Optional[ProgressCallback], weights: Mapping[int, float],
                 *, normalize_end: float) -> None: ...
    def step(self, index: int) -> Optional[ProgressCallback]: ...
    def begin_reencode(self, weights: Mapping[int, float], *, end: float) -> None: ...
    def advance_to_concat(self) -> None: ...
    def finish(self) -> None: ...
```

### 3. `ThrottledProgress` keeps its own high-water mark
`ThrottledProgress.__call__` first returns when `fraction` is below the highest value it has seen (including
one it skipped for throttling): it keeps `_high` separately from `_last_written`, since the throttle's
reference value (`_last_written`) lags `_high`. The comparison runs before the clock is read and before any
write, so a dropped value costs neither a write nor a clock tick. `1.0` is always written, and a repeated
`1.0` is a no-op write as today. This protects the row against any caller (CLI helpers, future engines), not
only `_Progress`.

### 4. Gate interaction
The merged gate retries a segment in `_retry_in_software` with a fresh `run_with_progress` call and the same
`progress.step(index)` callback; this change does not touch `_normalize_segment` or `_retry_in_software`
beyond what the callback already does. Decision 1 makes the retry's rewind a no-op by construction, and the
weights are keyed by segment index, which the retry does not change. A retry scenario test covers it
(task 1.3).

### 5. What is deliberately not done
- No fixed re-encode share handed back to the normalize pass after the fact: the pass boundary is known up
  front and stays put; a skipped re-encode simply jumps `normalize_end -> 0.95` once the pre-flight passes.
  Progress stays honest (it moves only when something finished) at the cost of one small forward jump.
- No timer-driven interpolation for the concat stretch; no new thread.
- No change to idempotency: a re-run, a `--force` run and a worker-restart mid-render each build a fresh
  `_Progress`/`ThrottledProgress` (the restart resets the row to `0.0`), so each starts from zero and is
  monotonic on its own.

## Failure behaviour

Progress never raises and never changes the render outcome. A failed normalize, a failed pre-flight or a
cancel leaves the last delivered fraction as the last one; the worker's terminal transition decides the job
status (`failed`/`canceled` do not set `1.0`). Nothing here touches the `.part` file or the atomic finalize;
`finish()` still fires after the concat and before verify, as `progress.complete` did.

## Risks / Trade-offs

- [Progress parked at 0 during the uniformity probe of an all-copy event] -> The probe is a few ffprobe
  calls per clip, seconds even for 32 clips; it is the honest picture (nothing has been done). The old
  behaviour reported 97% for the same work.
- [Duration weights misjudge slow clips (HDR tonemap on CPU, software decode)] -> Only the pacing is off;
  monotonicity and the final `1.0` do not depend on weights.
- [A rendered intermediate being re-encoded makes its ffmpeg `-progress` fraction jump to 1.0 at the end
  (`run_with_progress` emits a trailing `1.0`)] -> Expected; the segment's slot is simply finished.

## Test strategy

Orchestrator tests use the existing fake-runtime pattern in `tests/test_render.py`
(`test_mismatch_forces_reencode_before_join`, with `orch.is_copy_uniform` monkeypatched, is the template)
with a fake `run_with_progress` that reports a fixed local sequence. `ThrottledProgress` tests extend the
`_FakeStore` and injected clock in `tests/test_scheduler_progress.py`. No test needs hardware or a database.
