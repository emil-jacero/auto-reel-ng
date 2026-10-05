## Why

The user asked what "Not analyzed" means and why analysis cannot be started from the web, and chose option 3
(2026-10-05, verbatim "3 both"): analysis runs **automatically in the background**, plus a Re-analyze button and
"Analyze all" on the event list. The `analysis-job` change (this change's gate) makes analysis a queued, cancellable
`analysis` job with failure markers; `analysis-enqueue-api` and `analysis-web-controls` give it the buttons. Nothing
enqueues it on its own: today no job of any kind is ever enqueued automatically (research
`scratchpad/research/analysis/findings.md` §3, "Who enqueues proxies: NOBODY automatically ... 'automatic' has NO
precedent; it is new machinery"). This change is that automatic part.

## What Changes

- The worker runs a periodic **automatic analysis sweep** (supervisor decision, findings §5 Q1): every
  `worker.auto_analyze_interval` seconds it walks its project's events with **stat-only** reads (no ffprobe, no
  ffmpeg, no `reel.yaml`) and enqueues an `analysis` job for each event that has a clip the analysis job would
  analyze: no analysis entry, or an entry whose clip signal changed (new or changed clip).
- A clip whose analysis **failed** for its current signal (the gate's failure marker) does not count, so a bad clip
  is not retried in a loop; it is retried when the clip changes or on a Re-analyze (`force`). Likewise an event
  whose latest analysis job ended `canceled` or `failed` is left alone until one of its clip files changes after
  that job started, so a user's cancel is not undone five minutes later and a job-level fault (an unwritable cache
  directory) does not loop.
- The sweep is **capped**: at most `worker.auto_analyze_max_events` (default 2) events are enqueued per sweep, newest
  event first, so the first sweep over a large archive (findings "Risks": the 13-year MOL library) trickles.
- The sweep is **quiet when the queue is busy**: it enqueues nothing while any job of its project is `queued`, or a
  `render` or `proxy` job is `running`. Analysis jobs are already the lowest-ranked kind at claim time (render >
  proxy > analysis, `analysis-job`), and yield to running renders.
- New `worker.*` keys layered like the existing ones (D-2): `auto_analyze` (bool, default **true**),
  `auto_analyze_interval` (seconds, default 300), `auto_analyze_max_events` (int ≥ 1, default 2); wrong values fail
  loud naming the key.
- Restart-safe: the sweep keeps no state of its own; the job store's one-active-job index and the on-disk failure
  markers are what stop duplicates and retry loops across restarts.
- README documents the keys (worker config block and the compose section: the stack's worker sweeps its scratch
  library by default; turning it off is `worker: {auto_analyze: false}` in the library's `config.yaml`). No compose or
  `.env.example` change: the stack needs no new toggle.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `job-scheduler`: ADDED requirements for the automatic analysis sweep (what it enqueues, the cap and order, the quiet
  rule, stat-only reads, failure-marker skip, config keys, failure isolation and restart safety).
- `analysis-cache`: MODIFIED "Analysis is an explicit pass, never auto-run on scan" (scans and API reads stay free;
  an `analysis` job, including one the sweep enqueues, may run it); ADDED the third entry state (a failure marker:
  readable, keyed by the current signal, not a result, not re-run unless forced or the clip changes) and the atomic
  sidecar write, so a reader of the cache capability finds them there (supervisor, from the `analysis-job` review:
  the gate stated them only in `job-scheduler`).

## Impact

- Code (packages `scheduler` and `analysis`): new `auto_reel_ng/scheduler/analysis_sweep.py` (the sweep, a pure
  `sweep_once` plus a stoppable loop); `scheduler/config.py` (three keys and a bool resolver); `cli/commands.py`
  `cmd_worker` starts the sweep thread beside `Worker.run` and stops it with the same stop event;
  `analysis/cache.py` gains `entry_state`/`pending_clips`, the handler's inline per-clip rule lifted unchanged so
  the handler and the sweep share it. No new analysis logic.
- No database migration, no API or schema change, no web change, no `RENDER_GRAPH_VERSION` bump.
- Disk: the sweep writes nothing itself; the analysis jobs it enqueues write sidecars under each event's
  `.auto-reel/cache/` as the gate defines.
- CPU: with the default on, an idle worker analyzes the library in the background on the CPU token (gate's
  measured seconds-per-minute-of-footage figure in the HLD sets the expectation).
- Docs: README, HLD §4.5/§4.8/§6 and the analysis-job decision.
