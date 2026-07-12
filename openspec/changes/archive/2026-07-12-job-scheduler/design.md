## Context

7a shipped the durable store (`JobStore`: `enqueue`, `claim_next` via `FOR UPDATE SKIP LOCKED`,
`transition`, `set_progress`, `find_orphaned_running`, `cancel_queued`) with no consumer. The engine is a
synchronous library — `render_movie(plan, profile, options)` with an `on_progress` callback, skip-if-exists,
partial-output unlink on exception — driven today by `cmd_render`'s in-process loop, which selects one
acceleration profile per process and builds plans per event (`_build_job`). T2 decided a **separate worker
process** over a durable table; T4 decided the **two-pool capacity model** and **requeue** reconciliation.
The 2026-07-11 explore session settled the remaining forks and surfaced one correction: the engine does
**not** write temp-then-move — a hard kill mid-concat can leave a partial file at the final output path.

## Goals / Non-Goals

**Goals:**
- A worker process that turns queued rows into completed renders using the existing engine, unchanged
  except for atomic finalize.
- §4.8 capacity: at most 1 encode session per GPU render node (configurable), CPU-only jobs alongside.
- Crash/restart safety: no lost jobs, no partial output ever presented as done, no duplicate concurrent
  renders of the same event.
- Operator control without the API: enqueue, run worker, cancel (queued and running).
- Settle 7a's deferred identity questions (`event_dir` relative, `project_root` column).

**Non-Goals:**
- FastAPI/WS (7c), change detection (§8.14/T1), heartbeat/hung-worker detection, mid-ffmpeg kill,
  LISTEN/NOTIFY, multi-host, retries, priorities — all explicitly deferred (see proposal Non-goals).

## Decisions

### D-S1 — A job row is an event reference; the plan is rebuilt at claim time
The worker rebuilds the plan (prepare_event → probe → resolve) when it claims, reusing the same path as
`cmd_render._build_job` (factored into a shared `build_render_job` helper in `cli/build.py`, not
duplicated — a separate module from `cli/commands.py` so the scheduler can import it without a
`scheduler` ↔ `cli.commands` cycle). Nothing serializes a `RenderPlan` into the DB. *Why:* D-7 makes
`reel.yaml` + disk the source of truth; a frozen plan could contradict disk by run time. Consequence
(accepted, arguably a feature): edits made while a job is queued render the latest state. *Alternative
rejected:* serializing the plan at enqueue — freezes intent, fights the source-of-truth model, and adds a
schema for a large object graph nothing else reads.

### D-S2 — Atomic finalize in the engine; requeue becomes unconditional
`_execute` concats to `<output>.part` (same directory → same filesystem → `os.replace` is atomic) and
renames into place only **after** `verify_output` passes. The `BaseException` cleanup unlinks the `.part`.
*Why:* discovered hole — direct-to-`output_path` concat + skip-trusts-existence means a SIGKILL/OOM/power
loss mid-concat yields a truncated file that both the CLI skip and the worker's reconcile would present as
done. With atomic finalize, "a file exists at the final path" ⇒ "it is a complete, verified render", so
startup reconcile can **requeue every orphan unconditionally**: a genuinely finished orphan re-runs, hits
the skip check, and transitions to `done` in milliseconds — the T4-4d "verify then done" policy becomes
emergent engine behavior instead of scheduler code. *Alternatives rejected:* verify-at-reconcile (drags
probe/resolve/derive_target into reconciliation); trusting `finished_at`/progress (race-prone bookkeeping).
Note `verify_output` moves to *before* the rename and runs against the `.part` file.

### D-S3 — Claim-then-classify, two pools, profile selected once per worker
Worker startup runs `detect_capabilities` + `select_profile` once (same as the CLI, D-CLI4). Pools:
`{render_node: Semaphore(cap)}` for each hardware device (default cap **1**) plus a global CPU
`Semaphore(N)`. The classification (hardware encoder → that device's GPU token; software encoder → CPU
token) only happens *after* a claim rebuilds the plan, so the loop cannot literally check "is the token
*this specific job* will need free" before claiming — it does not yet know which pool a job needs. Instead
the claim loop bounds *total concurrently claimed-and-spawned jobs* to `pools.total_capacity` (every GPU
cap summed + the CPU cap): once that many are in flight, claiming pauses until one finishes, so a burst of
queued jobs never spawns more waiting threads than there is eventual token capacity to run them (this is
the "thread pool sized to total tokens" invariant from Risks, enforced in code rather than left as an
operational assumption). Within that bound: claim → rebuild plan → classify → acquire the matching
semaphore → `render_movie` in a thread. A claimed job needing the busy pool blocks its thread until the
token frees (accepted: with a ~all-VAAPI workload and GPU cap 1, contention is rare and FIFO order is
preserved). *Alternative rejected:* classify-before-claim — requires stamping the encoder class at enqueue,
which forces enqueue-time plan resolution and re-freezes what D-S1 unfroze. Per T4: an HDR job (CPU
tonemap → VAAPI encode) holds only its GPU token start-to-finish (4a); a job is atomic — one token,
internal segments sequential (4b); `device=auto|<node>` per job (4c).

### D-S4 — Poll wakeup at 1–2 s; no NOTIFY yet
The claim loop sleeps ~2 s when the queue is empty. *Why:* renders take minutes; sub-second pickup buys
nothing yet, and LISTEN/NOTIFY needs a dedicated listening connection + reconnect handling. NOTIFY is a
clean later additive (the store already runs on real PG in tests). Revisit for 7c GUI responsiveness.

### D-S5 — Worker identity: unique per boot; startup reconcile only
`worker_id = f"{hostname}:{pid}:{nonce}"`, fresh each start. On startup, before claiming:
`find_orphaned_running(live_workers=[my_id])` → every `running` row from any previous life is orphaned →
reset to `queued` (an additive `requeue` store operation: running → queued, clearing
`worker_id`/`started_at`/`progress`). *Why not the `cutoff` variant:* a legitimate long render exceeds any
sane `started_at` cutoff; without a heartbeat column there is no liveness signal, so cutoff-based detection
is wrong here. Hung-but-alive workers are explicitly deferred (would need heartbeat + cutoff). Single
worker process assumed in v1; the scheme extends to multiple workers via a registry later.

### D-S6 — Cooperative cancel via `cancel_requested`, checked between segments
Additive `cancel_requested` bool column. Operator surfaces (`auto-reel` now, API in 7c) only set the flag —
the **worker remains the sole writer of `status` transitions**, preserving 7a's transition discipline. The
worker checks the flag between segments (a natural boundary) and on a hit stops, cleans scratch, and
transitions `running → canceled`. This does need one small, deliberately minimal engine touch — an initial
"zero engine change" framing turned out not to hold up once implemented: `RenderOptions` gains an optional
`should_cancel: () -> bool` callback, and `_execute`'s segment loop (`render/orchestrator.py`) polls it once
before each segment and once more before final assembly, raising a new `RenderCancelledError` (a
`RenderError` subclass) on a hit. `run_with_progress`/ffmpeg execution itself is untouched — the check only
ever fires *between* subprocess calls, never interrupts one, so the mid-ffmpeg-kill non-goal still holds.
Cancel latency ≈ one segment's encode (seconds to ~a minute on VAAPI) — accepted for v1. `cancel_queued`
keeps handling the pre-claim case; `request_cancel` on a `queued` job simply cancels it directly.
*Alternative rejected:* API writes `running → canceled` directly — races the worker's own terminal
transition and breaks single-writer; mid-ffmpeg kill hook in `run_with_progress` — deferred until the
latency actually hurts.

### D-S7 — Identity: root-relative `event_dir` + nullable `project_root` (settles 7a's leftovers)
`event_dir` is stored **relative to the project root**; a new nullable `project_root` column records the
root at enqueue time. The worker resolves `project_root / event_dir` at claim. *Why:* the DB survives a
project move (rebuildable-from-disk spirit); `project_root` now avoids a churn migration when 7c's project
model lands, and nullable keeps 7a rows valid. One additive migration carries both columns (D-S6's flag
included).

### D-S8 — Operator surface: `enqueue` and `worker` subcommands
`auto-reel enqueue` scans via the existing ingest layouts (like `scan`) and inserts one `queued` row per
selected event (respecting `--years`, `--device`); it never renders. `auto-reel worker` runs the scheduler
loop until signaled (SIGINT/SIGTERM → finish or requeue in-flight work, exit clean). `auto-reel jobs`
(list/status via `list_by_status`/`get`) rides along as a trivial read surface for dogfooding. *Why:* 7b
must be exercisable end-to-end without 7c; both commands are thin over existing pieces.

## Risks / Trade-offs

- **[Duplicate render of one event]** Same event enqueued twice → two workers/threads could render the
  same output concurrently (`.part` clobber). → Mitigation: `enqueue` skips insertion when an active
  (`queued`/`running`) job exists for the same (`project_root`, `event_dir`); enforced with a partial
  unique index so the guarantee is DB-level, not application-level.
- **[Claim-then-classify starvation]** A claimed job blocking on a busy pool token occupies a worker
  thread. → Mitigation: the claim loop bounds in-flight claimed-and-spawned jobs to
  `CapacityPools.total_capacity` (GPU caps + CPU cap) — enforced in `Worker.run` (D-S3), not just
  documented; with cap defaults the worst case is one waiter per pool.
- **[Plan rebuild fails at claim]** Event dir deleted/corrupted after enqueue. → Mitigation: build failure
  transitions the job to `failed` with the `EngineError` message (mirrors `cmd_render`'s per-event
  isolation, D-CLI5); the worker moves on.
- **[SIGTERM during render]** Operator stops the worker mid-encode. → Mitigation: handler requeues
  in-flight jobs (running → queued) before exit; the `.part` in scratch/output is abandoned or unlinked —
  atomic finalize guarantees no partial at the final path either way.
- **[`os.replace` cross-filesystem]** `.part` must live in the **output directory** (not the scratch
  `TemporaryDirectory`, which may be another fs) for rename atomicity. Test asserts same-dir placement.
- **[Progress writes hammer PG]** `on_progress` fires per ffmpeg progress line. → Mitigation: throttle
  `set_progress` (e.g. ≥1% delta or ≥1 s since last write).

## Migration Plan

1. Engine first: atomic finalize + tests (independently shippable; fixes the CLI hole on its own).
2. Additive Alembic migration: `cancel_requested`, `project_root`, the active-job partial unique index;
   store ops `request_cancel`, `requeue`; enqueue signature.
3. Scheduler module (pools → classify → loop → reconcile → cancel), then CLI subcommands.
4. **Rollback:** engine change is behavior-compatible (same outputs, safer write); scheduler/CLI are
   additive; the migration is additive (columns nullable/defaulted) — downgrade drops them.

## Open Questions

- **Pool sizes' config home:** worker CLI flags vs `config.yaml` keys (lean: `config.yaml`
  `worker.gpu_sessions_per_device` / `worker.cpu_slots`, flags override, per D-2 layering) — settle in
  implementation.
- **`jobs` read surface naming:** `auto-reel jobs list|show` vs folding into `scan` — trivial, settle in
  implementation.
- **Requeue counter:** should `requeue` bump a `requeue_count` to surface crash loops (job requeued → crashes
  worker → requeued …)? Lean yes if free during the migration; a crash-looping job otherwise requeues
  forever with no visibility.
