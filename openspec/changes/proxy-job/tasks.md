## 1. Prepare one clip

- [x] 1.1 Add `auto_reel_ng/proxies/prepare.py`: `prepare_clip(clip, *, settings, runtime, profile, render_node,
  on_progress, should_cancel)` makes the proxy with `ensure_proxy` then the sprite with `ensure_filmstrip`,
  re-exported from the package. Progress maps the proxy's fraction into 0..0.97, reaches `1.0` only after the
  sprite is recorded, never decreases and is `1.0` at once (no process) for a clip that is complete; the cancel
  check is passed to both and tested between them; a failed proxy attempts no sprite; a failed sprite leaves the
  proxy. Verify with `tests/test_proxies_prepare.py` (fake runtime, as `test_proxies_ensure.py`): fractions
  below one then one after the sprite, complete entry reports one with no process, proxy-only entry cuts only
  the sprite, cancel between the two, failed proxy no sprite, failed sprite keeps the proxy; and
  `tests/test_proxies_prepare_ffmpeg.py` on a synthesized `lavfi` clip (skipped without ffmpeg): real progress
  rises to one, cancel mid-encode ends within two seconds and leaves the cache listing unchanged.

## 2. Proxy job runner

- [x] 2.1 Add `scheduler/proxy_job.py`: a handler that lists the event with `scan_event` (no `reel.yaml`),
  resolves the job's project `proxies.*` settings before any process, prepares each distinct cache entry in
  listing order with `prepare_clip`, keeps going after a clip failure, stops at a cache fault, maps
  `FfmpegCancelledError` to `RenderCancelledError`, and reports the failed clips in one `EngineError`. Weighted
  monotonic progress (clip bytes by `stat`, the clip in flight by its fraction, no probe) goes through
  `ThrottledProgress`. It holds one CPU token for its whole run (acquired in a loop that keeps checking cancel
  and stop) and releases it on every path. Verify with `tests/test_scheduler_proxy_job.py` (fake
  `prepare_clip`, no DB): order and IGNORED/MISSING handling with `reel.yaml` byte-identical, linked clips
  once, fully cached event starts no process, 900 MB/100 MB weighting reads 0.9, cached clips never move
  progress back, one bad clip of three gives "1 of 3 clips failed: ..." with the others prepared, a cache fault
  stops at once, a refused cache dir fails before any process, a read-only library is written nowhere, cancel
  between clips, token released on done, failed, canceled and an unexpected error.

## 3. Worker wiring

- [x] 3.1 Register the handler for `proxy` in `cmd_worker` (`CapacityPools` gains a plain CPU-token accessor),
  and give `Worker` a shared `stop_event` that handlers poll, and a bounded wait for handler threads after the
  shutdown requeue. Verify in `tests/test_scheduler_proxy_worker.py` (requires_db, fake preparation): done, failed and
  canceled map correctly and release the token (a following CPU job starts), an unexpected `TypeError` fails
  the job with `TypeError: ...`, a proxy job for a colliding, a fresh and a stale event is not failed or skipped
  as fresh, a GPU render starts while a proxy job holds the CPU token, two projects use their own caches, and a
  stop while the handler runs requeues the row and the handler thread has cleaned up before `run` returns.

## 4. Admission and priority

- [x] 4.1 Add `worker.proxy_slots` (default 1, integer >= 1, fails loud naming the key) to
  `resolve_worker_config`, pass it from `cmd_worker`, add `exclude_kinds` and the render-first order term to
  `JobStore.claim_next`, and make the worker exclude `proxy` while `proxy_slots` proxy jobs are in flight.
  Verify with `tests/test_scheduler_config.py` (default, config value, `0` and `"two"` rejected) and
  `tests/test_scheduler_proxy_worker.py` + `tests/test_job_store_kind.py` (requires_db): an hour-old proxy job and
  a new render are claimed render first, a second queued proxy job stays queued while one runs and a newly
  queued render is claimed, three proxy jobs claim oldest first one at a time, a running proxy job is not
  interrupted by a queued render, an unknown kind is still claimed, and render claim order is identical to
  before.

## 5. Cancel, shutdown and restart

- [x] 5.1 Wire `should_cancel` (the `cancel_requested` poll, or the stop event) through the runner between
  clips and into each clip's preparation. Verify in `tests/test_scheduler_proxy_job_lifecycle.py`
  (requires_db, real ffmpeg on three synthesized clips long enough to catch mid-encode): cancel during clip 2
  ends `canceled` within two seconds with clip 1's entry kept, no `.part` or temporary file and no clip 3
  start; cancel between clips; a stop requeues the job with no `.part` left; a killed worker (row left
  `running`, a stale hidden build directory in the cache) is requeued by the next worker, which spends no ffmpeg
  process on clip 1, re-encodes clip 2 and ends `done`; a canceled event can be enqueued again and prepares only
  what is missing.

## 6. Independence from the render path

- [x] 6.1 Prove a proxy job is invisible to the staleness contract and coexists with a render: enqueue a
  `render` and a `proxy` job for one event and run both. Verify with
  `tests/test_scheduler_proxy_job_independence.py` (requires_db): both are accepted and end `done`; the event's
  staleness verdict and render manifest are byte-identical before and after the proxy job;
  `RENDER_GRAPH_VERSION` is unchanged (asserted against its literal value of the base commit); the fingerprint
  of the event is identical with and without a prepared proxy cache; a failed proxy job leaves a running render
  untouched.

## 7. Concurrent-render measurement

- [x] 7.1 Run and report the experiment from design decision 9 under `experiments/` (next free `NNN`, the repo's
  `running-experiments` skill): a GPU-classified render of one dev-library event alone (3 runs), then with a
  proxy job on another event running throughout (3 runs), warm cache, plus one cold-cache pair; host, GPU,
  commands and verdict recorded. Verify by the report's table: the median render wall time with the proxy job
  is at most 1.15x the solo median, or the report says Refuted with the lever tried (x264 thread cap) and the
  follow-up it proposes. (Done: Refuted, ratios 1.28 to 1.56; the cap did not help; follow-up `proxy-yield`.)

## 8. Compose stack and docs of the setting

- [x] 8.1 Document `worker.proxy_slots`, render-before-proxy, the single-CPU-slot limit and the proxy cache
  location in the README (beside the thumbnail cache text), and pin that the compose worker prepares proxies
  into its mounted cache. Verify with `tests/test_compose_proxy_cache.py`: `compose.yaml` and `compose.cpu.yaml`
  give both `server` and `worker` `XDG_CACHE_HOME=/data/cache` and a bind mount for it, and the default proxy
  cache directory resolved under that variable is `/data/cache/auto-reel/proxies` (the same test file fails if
  the worker loses either).

## 9. HLD and gate record

- [x] 9.1 Update `docs/high-level-design.md`: add the proxy job rules to D-21 (kind `proxy`, per event, CPU
  token, `proxy_slots` 1, render claimed first, size-weighted progress, per-clip failure, no fingerprint input,
  no `RENDER_GRAPH_VERSION` bump) citing research `proxies.md` §3.9 and the experiment of 7.1; in §4.10 add
  "the timeline opens only for prepared events; preparation is a `proxy` job"; in §6 slice 9 note the job as
  landed; D-20 gets only the one line that the timeline's Prepare state enqueues this job. Verify with
  `openspec validate proxy-job --strict` and `grep -n "proxy_slots" docs/high-level-design.md` showing D-21,
  and `.venv/bin/python -m pytest -m "not requires_db"` plus black, isort, mypy and pylint clean.
