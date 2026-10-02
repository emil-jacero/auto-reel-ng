## Why

A job's progress is the one number the GUI, the WebSocket and `auto-reel jobs show` give an operator while a
render runs, and today it can go backwards and lie. The engine's `_Progress` maps every step into an equal
`1/(n+1)` slot of the overall span, indexed by segment position (HLD §4.9, D-A7: the hub fans out whatever the
row says). Two symptoms, both reproduced on `6a7fe16` with a fake runtime (four copy-eligible 640x480 clips,
CPU profile, the first `is_copy_uniform` forced false):

- **Backwards step.** When the equivalence pre-flight (movie-assembly; D-A) fails, the copied segments are
  re-normalized through the same `_Progress`, so each re-encode maps back onto its early slot. The recorded
  callback sequence was `0.2, 0.4, 0.6, 0.8, 0.187, 0.2, 0.387, 0.4, 0.587, 0.6, 0.787, 0.8, 1.0`; the step
  `0.8 -> 0.187` reached the job row and the WebSocket unchanged, because `ThrottledProgress` writes any value
  on its 1 s interval and `set_progress` only clamps to `[0, 1]`. The job-scheduler requirement "Progress is
  persisted, throttled" already says stored progress "increases monotonically"; it does not hold.
- **Early jump, then a stall.** A copy-eligible segment reports "complete" instantly, so an all-copy event
  jumps to `n/(n+1)` (about 97% with 32 clips) before anything has been probed or joined, and sits there
  through the uniformity probe and the concat. An equal slot per step also ignores that a 40-minute clip and a
  3-second title card take wildly different time.

Belongs to HLD §6 phase 8's v1 polish round (live progress, "render + live progress" screen E). It depends on
no open §8 research item.

## What Changes

- **The progress fraction the engine reports never decreases.** Whatever the order of steps, a re-run of a
  step (the re-encode pass, or a segment the software-decode fallback retries) can only
  hold or raise the reported value.
- **Steps are weighted by expected work, not counted.** A normalized segment weighs its duration; a
  stream-copied segment weighs nothing (no work) and reports no progress of its own; the final concat has a
  fixed small share at the top of the span. When the set could need re-encoding (any copy-eligible segment),
  the re-encode pass has its own reserved share between the normalize pass and the concat, so a re-encode
  moves progress forward instead of restarting it.
- **No early jump for copy.** An all-copy event reports nothing until the uniformity pre-flight has passed; it
  then advances to the start of the concat share, and reaches `1.0` when the concat finishes.
- **`ThrottledProgress` (the worker's callback into the job row) drops any fraction below the highest value
  it has seen**, so no engine path can walk the stored value back; the terminal `1.0` is still never
  throttled.

### Non-goals

- No change to `set_progress`, the job-store schema, the `JobOut` shape or the WebSocket messages (a lower
  value simply never arrives).
- No per-segment or per-pass progress in the API; no ETA. The fraction stays a single `0.0-1.0` number.
- No progress inside the concat or the verify (ffmpeg's concat runs without `-progress` here); that stays a
  flat stretch inside its reserved share.
- No attempt to make the fraction linear in wall-clock time: hardware and codecs make normalize speed vary
  per clip, so weights are a duration-based estimate whose guarantee is monotonicity, not accuracy.
- Mid-segment cancel polling and the stall watchdog (`render-stall-watchdog`) are separate changes.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `movie-assembly`: adds the requirement that the engine's overall render progress is non-decreasing and
  weighted by expected work (copy costs nothing, a re-encode pass has its own share).
- `job-scheduler`: "Progress is persisted, throttled" gains the guarantee that a lower fraction is never
  written to the job row.

## Impact

- **Packages:** `auto_reel_ng/render` (`orchestrator.py`: `_Progress` and its use in `_execute`) and
  `auto_reel_ng/scheduler` (`progress.py`: `ThrottledProgress`). Tests: `tests/test_render.py`,
  `tests/test_scheduler_progress.py`.
- **CLI / API:** neither gains behaviour. Both are clients of the same `on_progress` callback, so
  `auto-reel render` and the API worker see the corrected sequence (Principle V).
- **Rendered output:** unchanged for identical inputs; **no `RENDER_GRAPH_VERSION` bump** and no staleness
  fingerprint input changes (progress is reporting only).
- **Schema:** no `reel.yaml` / `config.yaml` change, no Alembic migration, no rescan.
- **Ordering:** edits `_execute`/`_Progress` in `orchestrator.py`, as did the merged gate
  `render-vaapi-software-decode-fallback` (a one-shot software-decode retry, `_retry_in_software`); the retry
  is covered (design, Decision 4).
- **Dependencies / complexity:** none added (Principle VII); two module constants.
