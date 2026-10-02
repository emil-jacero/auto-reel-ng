## 1. render/ — monotonic, work-weighted `_Progress`

- [x] 1.1 In `render/orchestrator.py`, rebuild `_Progress` around a high-water mark with the single `_emit`
  (never delivers a value `<=` the highest so far, clamps to `1.0`), a constructor taking per-segment weights
  and `normalize_end`, and the module constants `_CONCAT_SHARE = 0.05` / `_REENCODE_SHARE = 0.15`; add the
  weight function (span duration, else clip duration, else `0.0`). Verify with `tests/test_render.py` unit
  tests on `_Progress` directly: out-of-order and repeated step values are never emitted lower, a 10 s plus a
  30 s normalized pair reports `0.25 * 0.95` after the first, a zero-weight pass emits nothing, and a `None`
  callback makes `step` return `None`.
- [x] 1.2 Wire `_execute`: build the weights up front (zero for copy-eligible in the normalize pass), drop
  `progress.complete(index)` for copy-eligible segments, call `begin_reencode(...)` from `[high-water,
  normalize_end + _REENCODE_SHARE]` when the first `is_copy_uniform` is false with copied segments,
  `advance_to_concat()` after a passing check, and `finish()` after the concat in place of
  `progress.complete(len(segments))`. Verify with two fake-runtime tests: (a) four copy-eligible clips with the
  first `is_copy_uniform` forced false record a strictly increasing sequence that ends at `1.0` (the old
  sequence went `0.8 -> 0.187`); (b) 32 copy-eligible clips with a uniform set record no value before the
  pre-flight (assert via the order of the probe call and the callback), then `0.95`, then `1.0`; plus a mixed
  case (title card, two normalized, three copy) whose sequence stays inside `[0, 0.80]` until the pre-flight
  passes and delivers nothing inside `(0.80, 0.95)`.
- [x] 1.3 Cover the software-decode retry (`_retry_in_software`): with a fake `run_with_progress` that
  reports `0.6`, raises the hardware-decode-init `EngineError`, then reports from `0.0` on the retry, assert
  the delivered sequence has no decrease and still reaches `1.0`.
- [x] 1.4 Check that no all-copy path emits `n/(n+1)` and no path emits after `1.0`: a short test over the
  three render shapes above asserting `max(sequence) <= 1.0`, `sequence[-1] == 1.0` and
  `sequence == sorted(set(sequence))`.

## 2. scheduler/ — `ThrottledProgress` clamp

- [x] 2.1 In `scheduler/progress.py`, keep a `_high` mark separate from `_last_written`; return before reading
  the clock or writing when `fraction < _high`; update `_high` for every accepted call (including ones the
  throttle then skips); `>= 1.0` is always written. Update the module docstring to say it also guarantees a
  non-decreasing row. Verify in `tests/test_scheduler_progress.py` with the existing `_FakeStore` and injected
  clock: `0.80` then `0.19` after the interval writes only `0.80`; `0.80`, a throttled `0.805`, then `0.803`
  writes only `0.80` (the dropped value is compared with the high-water, not the last write); a later `0.85`
  writes; a `1.0` after `0.999` inside the interval writes; the existing tests still pass unchanged.

## 3. Validation gates

- [x] 3.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  and confirm no diff remains.
- [x] 3.2 Run `.venv/bin/python -m mypy auto_reel_ng` (strict) and `.venv/bin/python -m pylint auto_reel_ng`
  (only the known cairo `no-member` noise).
- [x] 3.3 Run `.venv/bin/python -m pytest` (podman required; otherwise `-m "not requires_db"` and say so).
