## 1. Engine: atomic finalize (independently shippable, do first)

- [x] 1.1 Change `_execute` to concat to `<output>.mp4.part` **in the output directory**, run
  `verify_output` against the `.part`, then `os.replace` into the final path; update `render_movie`'s
  `BaseException` cleanup to unlink the `.part` (never a completed final file). Test: success path
  renames; verification failure leaves nothing at the final path; the temp file's parent equals the
  output dir.
- [x] 1.2 Add a hard-kill simulation test: interrupt after the concat wrote the `.part` (before rename) →
  final path absent, `.part` present; skip-if-exists then correctly does NOT skip on re-run.

## 2. Store: migration + new operations

- [x] 2.1 Additive Alembic migration: `cancel_requested` (bool, default false), `project_root` (text,
  nullable), `requeue_count` (int, default 0), and a **partial unique index** on
  (`project_root`, `event_dir`) where status in (queued, running). Update the model + schema-drift test.
- [x] 2.2 Update `enqueue(project_root, event_dir, …)` to store root-relative identity and be
  **idempotent**: return the existing active job's id (flagging no-insert) instead of violating the index;
  test create, idempotent-return, and that terminal-state jobs don't block a new enqueue.
- [x] 2.3 Add `request_cancel(job_id)`: running → set flag only; queued → cancel directly; terminal →
  no-op report. Test all three branches and that `status` is untouched for running.
- [x] 2.4 Add `requeue(job_id)`: running → queued, clearing `worker_id`/`started_at`/`progress`, keeping
  `cancel_requested`, incrementing `requeue_count`; reject non-running. Test reset fields, counter,
  rejection, and that a requeued job is claimable.

## 3. Scheduler core

- [x] 3.1 Create `auto_reel_ng/scheduler/` with worker identity (`host:pid:nonce`) and config resolution
  (pool caps + poll interval from `config.yaml` `worker.*`, CLI overrides, D-2). Test config precedence.
- [x] 3.2 Factor the CLI's plan build (`_build_job`'s prepare/probe/resolve) into a shared helper used by
  both `cmd_render` and the worker (no behavior change to `render`); test `cmd_render` parity.
- [x] 3.3 Implement pools: per-render-node semaphores (from the startup profile's devices) + global CPU
  semaphore; encoder-based classification (hardware encoder → device token, software → CPU). Test
  classification against a hardware and a CPU profile.
- [x] 3.4 Implement the claim/execute loop: poll → claim (only when a token is free) → rebuild plan →
  classify → acquire token → `render_movie` in a thread → `transition(done)`; `EngineError` at any stage
  → `transition(failed, error=…)` and continue. Test with a stubbed engine: done path, failed-build path,
  failed-render path, FIFO order.
- [x] 3.5 Wire progress: `on_progress` → throttled `set_progress` (≥1% delta or ≥1 s). Test throttling and
  final progress 1.0 at `done`.
- [x] 3.6 Capacity behavior test: two GPU jobs serialize on a cap-1 device while a CPU job runs
  concurrently (stub engine with controllable durations).

## 4. Reconciliation and shutdown

- [x] 4.1 Startup reconcile: `find_orphaned_running(live_workers=[my_id])` → `requeue` each, before the
  first claim. Test: seeded orphan is requeued and processed; a finished orphan's re-run hits skip and
  transitions `done` without re-rendering (integration with task 1).
- [x] 4.2 SIGINT/SIGTERM handler: stop claiming, requeue in-flight jobs, exit 0. Test no job left
  `running` after a signal mid-render (stub engine).

## 5. Cancellation

- [x] 5.1 Between-segment cancel check in the worker's render path (checked via the store before each
  segment); on hit: stop, clean scratch, `transition(canceled)`. Test cancel at segment k stops before
  k+1, no final output, status `canceled`; cancel_requested set pre-claim also cancels promptly.

## 6. CLI surface

- [x] 6.1 `auto-reel enqueue`: scan via ingest layout (`--years`, `--device`), insert jobs (idempotent),
  report created vs existing; never probes or renders. Test against a fixture project + podman PG.
- [x] 6.2 `auto-reel worker`: run the loop with config/flag capacity + interval; graceful-shutdown exit
  code. Smoke-test end-to-end: enqueue → worker (short-lived) → job done, output exists.
- [x] 6.3 `auto-reel jobs list|show|cancel`: read views + `request_cancel` wiring; test list filter,
  show detail, cancel sets the flag.
- [x] 6.4 Update the entry-point help/usage test for the seven subcommands.

## 7. Docs and closeout

- [x] 7.1 Document the worker in the README/module docstrings: config keys (`worker.*`), operational notes
  (requeue-on-restart semantics, cancel latency = one segment, no heartbeat yet), and the atomic-finalize
  guarantee.
- [x] 7.2 Full suite + lint green; verify the end-to-end dogfood path on `auto-reel-media/` (enqueue →
  worker → done) and record the result in the change notes.

  **Result (2026-07-11):** Full suite green (`pytest`, real podman-Postgres `requires_db` tests
  included); `black`/`isort` clean; `mypy` clean (73 source files); `pylint` 9.96/10 with the only
  remaining findings pre-existing (`cairo` no-member in `render/title/render.py`, unrelated to this
  change). Dogfooded against a scratch copy of `auto-reel-media/input/2024/2024-06-27 - grillning med
  grannar` (4 real 1080p h264 clips, ~150s total) rather than the shared fixture directly, since a real
  worker run adopts + persists `reel.yaml` — a destructive side effect on shared sample media. Ran
  `auto-reel enqueue` → `auto-reel worker` end-to-end against a throwaway podman Postgres: the job was
  claimed, the plan rebuilt, the event adopted/persisted, classified onto the AMD VAAPI GPU pool token,
  rendered in ~4.5s, and transitioned `queued → running → done` with `progress = 1.0`. Output verified
  via `ffprobe`: a single valid 1920x1080 h264/aac stream, duration 149.76s — exactly the sum of the four
  source clips' durations (61.44 + 39.84 + 20.64 + 27.84s), confirming a real, correct, non-truncated
  render (atomic finalize) rather than a stub.

  **Post-verification pass (2026-07-11):** `/opsx:verify` surfaced 4 warnings, all addressed: (1)
  `design.md` D-S6 wrongly claimed "zero engine change" for cancellation — corrected to document the
  `RenderOptions.should_cancel` addition; (2) `Worker.run`'s claim loop had no bound on concurrently
  spawned threads, diverging from D-S3's "thread pool sized to total tokens" mitigation — added
  `CapacityPools.total_capacity` and gated claiming on it; (3–4) added direct tests for two previously
  spec-only scenarios: "claimed job renders from current disk state" (edits `reel.yaml` after enqueue,
  before claim) and "duplicate active job rejected by the database" (raw session insert bypassing
  `JobStore.enqueue`). Also closed 3 suggestion-level gaps with tests: idle-poll-then-claim-promptly,
  one-token-held-for-the-whole-job (HDR/mixed pipeline), and `device_filter` end-to-end wiring. Full
  suite re-run green (377 passed, 5 skipped); `mypy`/`pylint`/`black`/`isort` all clean.
