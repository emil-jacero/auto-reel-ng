## Why

7a (`service-persistence`) shipped a durable Postgres job store — but nothing consumes it: renders still
run only as the CLI's transient in-process `render_batch` loop, jobs cannot outlive a process, and nothing
enforces the §4.8 requirement to limit concurrent encode sessions per GPU while letting CPU-only work run
alongside. This change is the middle slice of phase #7: a **worker process** (T2) that claims jobs from the
store, drives the existing engine, respects **per-device capacity** (T4), survives restarts via
**unconditional requeue**, and supports operator cancellation. It also closes a **real durability hole
found during design**: the final concat writes directly to `output_path`, so a hard kill (SIGKILL/OOM/power
loss) mid-concat leaves a partial file that the existing skip-if-exists path would trust — under a
requeue-on-restart worker that becomes "truncated movie presented as done". The fix (atomic finalize) is
what makes unconditional requeue sound.

## What Changes

- Add a **job-scheduler worker** (`auto_reel_ng/scheduler/`): a long-running process that polls
  `claim_next` (1–2 s), **rebuilds the render plan at claim time** from disk (prepare_event → probe →
  resolve, exactly like `cmd_render._build_job`) — a job row is an *event reference*, never a frozen plan
  (D-7: `reel.yaml` is the truth; edits made while queued render the latest state).
- Enforce **two-pool capacity** (T4): per-render-node GPU semaphores (default cap 1) + a global CPU pool
  (cap N). The worker selects its acceleration profile **once at startup** (like the CLI), claims when any
  token is free, classifies the job by its resolved encoder after the plan rebuild, then acquires the
  matching pool token (claim-then-classify; brief post-claim waits accepted).
- Add **restart reconciliation**: each worker boot gets a unique `worker_id` (`host:pid:nonce`); on startup
  it calls `find_orphaned_running(live_workers=[its_new_id])` and **unconditionally requeues** every orphan.
  Sound because of atomic finalize (below): a requeued finished job re-runs, hits the now-trustworthy skip
  check, and completes as `done` in milliseconds.
- **BREAKING-safe engine fix — atomic finalize** (`movie-assembly` modified): the final concat writes to
  `<output>.part` in the output directory and `os.replace()`s into place only after verification, so a file
  at the final path is always complete — for the worker's requeue *and* the CLI's existing skip path.
- Add **running-job cancellation** (settles the parked lean: YES): a new additive `cancel_requested` flag
  on the job row, set by operator surfaces; the worker — the sole writer of `status` — checks it **between
  segments** and transitions `running → canceled`. Mid-ffmpeg kill is deferred.
- Extend the **job schema** (additive migration): `cancel_requested` (bool), nullable `project_root`;
  `event_dir` is stored **project-root-relative** (settles 7a's open questions; the DB survives a project
  move, consistent with rebuildable-from-disk).
- Add **operator subcommands** (`headless-cli` modified): `auto-reel enqueue` (scan events → job rows,
  reusing ingest layouts) and `auto-reel worker` (run the scheduler loop), so 7b is dogfoodable without
  the 7c API.

## Capabilities

### New Capabilities
- `job-scheduler`: The worker process — poll/claim loop, plan rebuild at claim time, claim-then-classify
  two-pool capacity, progress reporting into the store, startup requeue reconciliation, between-segment
  cancellation, and per-job failure isolation mirroring `render_batch`'s.

### Modified Capabilities
- `movie-assembly`: Output writing becomes atomic (`<output>.part` → `os.replace` after verification) so
  the existence of a file at the final path guarantees a complete render; the skip-if-exists behavior may
  then trust existence.
- `job-store`: Schema gains `cancel_requested` and nullable `project_root`; `event_dir` semantics become
  project-root-relative; `enqueue` accepts the project root; a new `request_cancel` operation flags a
  running job for cooperative cancellation.
- `headless-cli`: The `auto-reel` entry point gains `enqueue` and `worker` subcommands.

## Impact

- **New modules**: `auto_reel_ng/scheduler/` (worker loop, pools, classification, reconcile, cancel).
- **Engine**: `render/orchestrator.py` `_execute` finalizes atomically; `render_movie`'s partial-cleanup
  now unlinks the `.part`, never a completed final file. `RenderOptions` also gains an optional
  `should_cancel` callback, polled at each segment boundary and once more before final assembly, raising
  a new `RenderCancelledError` on a hit (D-S6) — the minimal engine touch cooperative cancel needs; it
  never reaches into `run_with_progress`/ffmpeg execution itself.
- **Persistence**: one additive Alembic migration (`cancel_requested`, `project_root`); `job_store.py`
  gains `request_cancel` and the enqueue signature grows.
- **CLI**: `cli/main.py` + `cli/commands.py` gain `enqueue`/`worker`/`jobs`; the plan-building logic
  shared with `cmd_render` is factored out to `cli/build.py` (not `cli/commands.py` itself) so the
  scheduler can import it without a `scheduler` ↔ `cli.commands` cycle.
- **Reuses unchanged**: `claim_next`/`transition`/`set_progress`/`find_orphaned_running`,
  `render_movie`, `on_progress`, `detect_capabilities`/`select_profile`, ingest layouts.
- **Tests**: podman-PG-backed scheduler tests (claim/requeue/cancel), engine atomic-finalize tests, CLI
  subcommand tests.

## Non-goals

- **No API / no WebSocket** — 7c (`api-service`). The worker writes progress to the store; nothing reads
  it live yet except `auto-reel` queries and SQL.
- **No change detection** — `_staleness_filter` stays a no-op; `fingerprint` stays unused (T1, §8.14).
- **No heartbeat / hung-worker detection** — startup reconcile covers crash/restart only; a live-but-hung
  worker is out of scope (deferred with the heartbeat column).
- **No mid-ffmpeg cancellation** — cancel granularity is between segments; no kill hook in
  `run_with_progress` yet.
- **No LISTEN/NOTIFY wakeup** — polling only; NOTIFY is a later additive optimization.
- **No multi-host workers, no auto-retry, no priority scheduling** — single host, FIFO, `priority`
  remains reserved-unused.
