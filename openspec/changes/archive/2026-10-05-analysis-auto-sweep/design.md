## Context

See proposal.md (Why). Built on the `analysis-job` gate, merged on `origin/main` (704d8e3, HLD D-27). What it
actually built, and what this change relies on:

- `JobKind.ANALYSIS` (`"analysis"`), one job per event, `AnalysisJobHandler` registered in `cmd_worker` beside
  `ProxyJobHandler`, sharing the worker's `stop_event`.
- `submit_analysis(store, project_root, event_dirs, *, force)` in `scheduler/analysis_job.py` is "the one place an
  analysis job is enqueued" (CLI `analyze --enqueue`, the API); its docstring already names the auto-sweep as an
  unforced submitter. The sweep calls it with `force=False`.
- The handler lists **every** clip with `scan_event` (IGNORED included) and decides per clip, **inline** in
  `_analyze_one`: `read_entry(...)` current → skip; else `read_failure(...)` for the current signal → count the clip
  failed again with its recorded cause, no ffmpeg; else analyze. So a job over an event that holds a marked clip
  ends **`failed`** even when every other clip is now current (the gate's "A failed clip is not retried in a loop").
- Failure markers and atomic writes live in `analysis/cache.py` (`write_failure`, `read_failure`, `_write_atomic`),
  but the requirements stating them were put in `job-scheduler` (the gate's two-delta limit). The supervisor moved
  the cache-side statement here: this change carries the `analysis-cache` delta.
- Claim order render > proxy > analysis (the worker claims `analysis` only when nothing else is claimable),
  `worker.analysis_slots` (default 1) outside the render capacity bound, the CPU token, and yield to running
  renders **and proxy jobs** (`scheduler/turns.py`).
- D-27's measurement: ~17 s wall / ~2 CPU-min per minute of 1080p50, ~1.5–2 min wall per minute of 4K50 HEVC; the
  gate noted "the automatic sweep's cap should be counted in minutes of footage, not events" (see Decision 4).

Other code this change sits on (`origin/main` 704d8e3):

- `JobStore.submit(project_root, event_dir, kind=...)` is idempotent per `(project, event, kind)` through the
  `ux_jobs_active_identity` partial unique index and reports `created` (`persistence/job_store.py:111`).
  `list_by_status(status, project_root=, kind=None)` and `latest_by_project(project_root, kind=)` exist (one query
  each), so the sweep needs no new store method and no migration.
- `scan_event` lists clips with `iterdir`/`stat` only (`event/discovery.py:121`); `clip_signal` is
  `stat().st_size` + `st_mtime_ns` (`analysis/cache.py:53`); `read_entry` reads one small JSON
  (`analysis/cache.py:113`). Events are enumerated with `get_layout(config.layout or DEFAULT_LAYOUT)(walk_root)`
  exactly as `scheduler/worker.py:187` already does.
- The worker is project-scoped (`cmd_worker` resolves one project root, findings §4 "Worker is PROJECT-scoped ...
  a worker-side periodic sweep is feasible").
- `worker.*` keys resolve in `scheduler/config.py` with fail-loud type checks (`_resolve_int`/`_resolve_float`).

Research: `scratchpad/research/analysis/findings.md` §3 (queue facts above), §5 Q1 (worker-side stat-only sweep,
idempotent via the unique index, failure markers against retry loops), "Risks" (first sweep over the 13-year MOL
library would enqueue hundreds of events → cap per sweep).

## Goals / Non-Goals

**Goals:**
- An idle worker brings every event's analysis up to date on its own, a few events at a time.
- Zero media decoding and zero ffprobe in the sweep; zero effect while renders or proxies are queued or running.
- No retry loops: per-clip failures (markers) and job-level failures/cancels both stop re-enqueueing until
  something on disk changes.

**Non-Goals:**
- Any new analysis logic, threshold, or sidecar format (the gate owns them).
- An API or web surface for the sweep (state reads and buttons are `analysis-enqueue-api` /
  `analysis-web-controls`). The jobs it enqueues are ordinary `analysis` jobs, visible wherever those are.
- Auto-enqueueing proxies or renders.
- Using the `priority` column to order automatic behind manual analysis jobs (see Decisions 5).

## Decisions

1. **One sweep thread beside the claim loop, not inside it.** `scheduler/analysis_sweep.py` holds
   `AnalysisSweep` with a pure-ish `sweep_once() -> SweepReport` (the testable unit) and `run(stop_event)`, which
   calls `sweep_once` and then `stop_event.wait(interval)` until the event is set. `cmd_worker` starts it on a daemon
   thread when `worker.auto_analyze` is true, sharing the worker's existing `stop_event`, and joins it after
   `worker.run()` returns. *Why not in `Worker.run`*: a full walk of a big library on a NAS can take seconds, and
   the claim loop must stay responsive to a newly queued render; `Worker` also stays untouched (its spec is
   already long). *Alternative*: a cron-like separate `auto-reel sweep` command — rejected, the compose stack would
   need another service, and the worker already owns the project and the store.

2. **The sweep reuses the gate's clip selection, never its own copy.** An event is "due" iff the stat-only rule
   the `analysis` handler uses for a non-forced job selects at least one clip to analyze: no current entry and no
   failure marker for the current signal. If the sweep and the handler disagreed, a clip the sweep counts but the
   handler skips would be enqueued every interval forever. The gate left the rule inline in the handler, so task 1.1
   lifts it, unchanged, into `analysis/cache.py`: `entry_state(event_dir, identity, signal) -> EntryState`
   (`current` / `failed` with its cause / `missing`), which the handler's `_analyze_one` now calls, and
   `pending_clips(event_dir) -> list[str]` (every `scan_event` identity whose `entry_state` is `missing`), which the
   sweep calls. Neither runs ffprobe/ffmpeg or hashes content (`use_hash=False`). This touches the `analysis`
   package, the second of the two this change may touch.

3. **Quiet rule is project-wide and read once per sweep.** Before walking, the sweep reads the project's
   `queued` jobs (all kinds) and `running` jobs (all kinds) with `list_by_status(..., kind=None)`. If any job is
   `queued`, or any `render`/`proxy` job is `running`, it returns without walking ("queue busy"). A `running`
   analysis job alone does not stop it, so the next events can be lined up while one is analyzed; with the cap this
   keeps at most `max_events` analysis jobs waiting. The per-event rule "never while a render or proxy job is
   queued/running for that event" is implied by the project-wide one. A render enqueued between the read and a
   submit is harmless: it is claimed first by kind rank.

4. **Cap and order: newest event first, stop at the cap.** Events come from the layout walk; the sweep visits them
   in reverse walk order (the `year-event` layout walks oldest to newest, so recent footage is analyzed first, which
   is what the user is most likely editing) and stops walking as soon as `max_events` jobs were *created*. A
   submission that reports `created=False` (an active analysis job already exists) neither counts nor errors. An
   event with an active analysis job is skipped before its clips are read (from the `running` list of Decision 3).
   Cost when every event is current: one `stat` + one small JSON read per clip per interval; with the default 300 s
   that is negligible next to a render. *Events, not minutes of footage* (D-27 suggested minutes): a duration needs
   ffprobe, which the sweep must not run, and bytes are a poor proxy across codecs. Because of the quiet rule the cap
   bounds only how much automatic work is queued *ahead of* a user's manual request, never total CPU time; an
   event-count cap of 2 keeps that wait at two events. Revisitable once facts.json durations are cheap to read.

5. **Lowest priority comes from the kind rank, not from `priority`.** The gate already claims analysis after every
   render and proxy job and makes it yield to running renders. Automatic and manual analysis jobs are the same kind;
   setting a lower `priority` on automatic ones would need a `submit(priority=)` keyword in `persistence/` (a third
   package) for a small gain: because the sweep enqueues nothing while any job is queued, a user's Re-analyze or
   Analyze all waits behind at most `max_events` automatic events. Recorded as a trade-off, revisitable.

6. **Back-off after a canceled or failed job.** Per-clip failures are covered by markers (gate). Two cases are
   not: the user cancels an automatic job (its unanalyzed clips are still "missing", so the next sweep would
   re-enqueue it, undoing the cancel), and a job that fails before any marker is written (e.g. the cache
   directory is not writable). Rule: the sweep reads `latest_by_project(project_root, kind="analysis")` once; an
   event whose latest analysis job is `canceled` or `failed` is skipped unless one of its clip files has a `stat`
   `st_mtime` or `st_ctime` later than that job's `started_at` (its `finished_at` when it was canceled while still
   queued; the start, not the finish, because the job listed the folder when it started: a clip copied in while it
   ran would otherwise never count, and an event with a failure-marked clip always ends `failed`; no loop, since a
   later job starts after every change it was enqueued for — review fix). `st_ctime` is included because ingest tools
   (reel-ingest) may preserve a camera file's old mtime on copy; a copy, rename or replace always moves ctime. A
   Re-analyze (a new job) supersedes the back-off because it becomes the latest job. Stat-only, restart-safe (the
   state is the job row and the file).

7. **Config.** `worker.auto_analyze` (bool, default `true`, a non-bool fails loud), `worker.auto_analyze_interval`
   (number of seconds > 0, default `300` — "every few minutes", supervisor; findings Q1 suggested 60 s, but
   analysis is minutes per event so a faster sweep buys nothing), `worker.auto_analyze_max_events` (int ≥ 1,
   default `2`, supervisor). Resolved in `resolve_worker_config` with the same D-2 layering; no CLI flags
   (Principle VII: the compose stack and a host both use the library's `config.yaml`; nobody asked for a flag).

8. **Failure isolation.** The sweep never stops the worker. A database error ends that sweep with an error log and
   the next interval tries again. A layout walk that raises ends that sweep with an error log naming the walk root.
   An event whose clips cannot be listed or stat'ed (vanished mid-walk, permission) is logged as a warning naming
   the event and skipped; the others continue. Each sweep logs one INFO line when it enqueued something (events
   and job ids) and a DEBUG line otherwise.

## Risks / Trade-offs

- [Sweep and handler disagree about which clips are due → endless re-enqueue] → Decision 2 (one shared function)
  plus a real-store test that runs the real handler over the sweep's choice and asserts a second sweep enqueues
  nothing.
- [An event with a marked clip and a new clip: the job analyzes the new clip and still ends `failed` (the marked
  clip is reported again)] → the next sweep finds nothing pending (the new clip is current, the marked one is not
  due), and the back-off (Decision 6) would hold it anyway. The `failed` status is the gate's choice, not changed.
- [First sweep over the whole MOL archive] → cap 2 per sweep and the quiet rule: at most 2 waiting analysis jobs at
  any time; the archive trickles through while the worker is idle.
- [User's force Re-analyze meets a queued non-force automatic job (unique index per kind)] → solved by the gate:
  `submit_analysis(force=True)` forces a `queued` unforced job (`force_queued`); a `running` one cannot be forced
  and the submission says so.
- [Clock skew between DB `started_at` and file times] → the DB and the files live on the same host in both the
  dev setup and the compose stack; a skew only delays or advances one retry, never loops.
- [Analysis is on by default and uses CPU on an idle machine] → documented in README with the off switch; it yields
  to renders and only runs when nothing else is queued.
- [Library on a slow network share: a full stat walk every 5 minutes] → bounded by the interval and configurable;
  the walk reads no media.

## Migration Plan

None: no schema change. Existing deployments get the sweep on by default after upgrading the worker; setting
`worker: {auto_analyze: false}` in the project's `config.yaml` turns it off. Rollback = that switch, or the previous
build.
