## Context

See proposal.md for the why. Current state (research `analysis/findings.md`, paths relative to the repo):

- `cli/commands.py` `cmd_analyze` → `analysis/cache.py` `analyze_event` → per identity of `scan_event` (IGNORED
  clips included): `clip_signal` (size + `mtime_ns`), `read_entry` hit → skip, else `analysis/runner.py`
  `analyze_clip` (one ffprobe for the duration, two ffmpeg passes from `analysis/filters.py`, each decoding the whole
  original with `-an … -f null -`) → `write_entry` (plain `write_text`).
- `runner._run_pass` uses `FfmpegRuntime.run` (blocking `communicate`, no cancel, no progress) and returns
  `result.stderr`, which `parser.parse_pass1/2` read. `run_with_progress` (`ffmpeg/runtime.py` ~417) cancels and
  reports fractions, collects stderr on a drain thread, but returns `None`.
- `scheduler/proxy_job.py` is the precedent this change copies: a `KindHandler` registered in `cmd_worker`
  (`kind_handlers={PROXY: handler}`), one CPU token held by the handler (`_Hold`), `_take_turn` yields to running
  renders, `ThrottledProgress`, per-clip failures collected into one `EngineError` message, cancel polled through
  `store.get(job.id).cancel_requested`, `JobInterrupted` on a worker stop.
- `scheduler/worker.py`: the in-flight bound (~342) counts every non-`proxy` job against `pools.total_capacity`;
  `_claim` (~379) excludes `proxy` when `proxy_slots` are full. `JobStore.claim_next` orders `render` first, then
  `priority` desc, then `created_at`, and accepts `exclude_kinds`.
- `cpu_slots` defaults to 1, so a CPU render, a proxy job and an analysis job share one token.

## Goals / Non-Goals

**Goals:** an `analysis` job that is cancellable, resumable per clip, isolated per clip, never retried in a loop,
never delays a render or a proxy job, and leaves no half-written sidecar; CLI parity; a measured cost figure.

**Non-Goals:** see proposal.md "Non-goals". In particular no change to `JobStore.claim_next` or its spec.

## Decisions

### 1. Two modules, one per package
- `analysis/`: `analyze_clip(path, *, runtime, config, on_progress=None, should_cancel=None)`; with neither hook it
  behaves as today. Each pass runs through `run_with_progress(args, duration=d, on_progress=…, should_cancel=…)`;
  pass 1 maps to the clip fraction `0.0–0.5`, pass 2 to `0.5–1.0`. `FfmpegCancelledError` is re-raised as is (it
  subclasses `FfmpegError`, so `_run_pass` MUST catch it first, before wrapping failures in `AnalysisError`).
  When the probe reports no duration, `on_progress` is not passed to ffmpeg (no fraction can be computed, never
  invented) and the clip reports its fraction only at its end; the cancel check still applies.
- `analysis/cache.py`: `write_entry` writes `<digest>.json.part-<pid>-<random>` in the cache dir, `fsync`s, then
  `os.replace`s it over `<digest>.json`. `write_failure(event_dir, identity, signal, reason)` writes, the same way,
  `{"version": 1, "identity", "signal", "failure": "<one-line cause>"}` (no `segments`). `read_entry` returns
  `None` for such an entry (it is not a result; the API read and inline `analyze` see the clip as unanalyzed, as
  today for a missing entry). `read_failure(event_dir, identity, signal) -> Optional[str]` returns the cause when
  the marker's signal equals the current one. A successful write replaces a marker (same file).
  `analyze_event(…, force=False)`: `force=True` skips the cache read; it never reads markers (inline is the user
  asking now, and it fails loud on the first bad clip as today).
- `scheduler/analysis_job.py`: `AnalysisJobHandler`, the `analysis` `KindHandler`, same constructor shape as
  `ProxyJobHandler` (`store`, `pools`, `runtime`, `stop_event`, plus an injectable `analyze` for tests). The yield/token/cancel helpers (`_Hold`, `_acquire`, `_take_turn`, `_stop_or_cancel`) move from
  `proxy_job.py` into `scheduler/turns.py` and take the set of kinds to yield to (`{render}` for proxy,
  `{render, proxy}` for analysis). `proxy_job.py`'s behaviour is unchanged; its tests stay green unmodified.

Alternatives: a handler living in `analysis/` (rejected: Principle VI, `analysis/` must not import `scheduler/` or
`persistence/`); keeping `_take_turn` duplicated (rejected: two copies of a subtle token protocol).

### 2. What the job does, per clip
```
plan = scan_event(event_dir).identities          # listing order, IGNORED included, reel.yaml never read
for identity in plan:
    stop_or_cancel(); take_turn(yield_to={render, proxy})
    signal = clip_signal(clip)                    # OSError → that clip fails ("cannot stat")
    if not force and read_entry(...) is not None: done (weight counted)
    elif not force and (cause := read_failure(...)): failed again, no ffmpeg (message says "earlier failure")
    else: segments = analyze_clip(clip, on_progress=…, should_cancel=…)
          write_entry(...)                        # on AnalysisError: write_failure(...), record, continue
```
Weights are `max(1, st_size)`; progress = (finished weight + weight × clip fraction) / total, capped at
`FAILED_PROGRESS_CAP` once a clip failed, through `ThrottledProgress`; `1.0` only at `done`. The job ends `done`
when no clip failed, otherwise raises `AnalysisJobError` ("2 of 9 clips failed: a.mp4: …; …", the proxy
`_failure_message` shape, first three named). Symlinked clips are not de-duplicated: entries are per identity, as
`analyze_event` already does.

**Failure classes**: `AnalysisError` (probe failure, non-zero ffmpeg, stall) and a clip that cannot be statted are
the clip's failure. An `OSError` writing the sidecar (unwritable event folder, full disk) is not the clip's fault:
it ends the job at once, `failed`, naming the cache fault; no marker is attempted. `FfmpegCancelledError` → the
engine's cancellation (`RenderCancelledError`) unless the worker is stopping (`JobInterrupted`, requeue). Any other
exception propagates and the worker fails the job with its type and message ("Per-job failure isolation").

**Stall**: each pass runs with a `stall_timeout` constant of `analysis/` (600 s, the proxy encode's
`PROXY_STALL_TIMEOUT_S`, not imported: `analysis/` does not depend on `proxies/`); a stalled pass is that clip's
`AnalysisError`.

**Settings**: thresholds are the experiment-005 defaults (`AnalysisConfig()`), exactly what inline `analyze`
uses today; no new key, and no project configuration is read by the handler.

### 3. Claim order without touching `claim_next`
The worker claims in two steps:
1. `claim_next(exclude_kinds={analysis} ∪ {proxy if proxy slots full})` — renders first, then proxy and any other
   kind, exactly today's order;
2. only if that returns nothing and fewer than `worker.analysis_slots` analysis jobs are in flight:
   `claim_next(exclude_kinds={proxy if proxy slots full})`.

The in-flight bound counts every kind except `proxy` and `analysis`. Alternative: a `CASE` rank in `claim_next`'s
`ORDER BY` (the research's suggestion). Rejected for this change: it modifies `job-store` "Race-free claim-next"
(a third capability delta) for no behaviour the worker cannot get from the `exclude_kinds` it already has. The
window between the two calls only matters across workers, and a proxy job claimed late is still served first at
run time by the yield (decision 4).

### 4. Yield to renders and proxy jobs
An analysis job does not start a clip while any `render` **or `proxy`** job is `running` (a claimed job waiting for
the CPU token is already `running`), and holds no CPU token while it waits. With `cpu_slots: 1` this is what makes
"render > proxy > analysis" true at run time and not only at claim time: without it an analysis job would hold the
single token from clip to clip and a proxy job (which the user is waiting for to open the Timeline) would wait for
the whole event. A clip already being analyzed finishes (≤ two passes of one clip).

### 5. `worker.analysis_slots`
Layered like `proxy_slots` (`resolve_worker_config`, D-2): integer ≥ 1, default 1, else `ConfigError` naming
`worker.analysis_slots`. No CLI flag (as `proxy_slots`).

### 6. CLI
`auto-reel analyze <root> [--enqueue] [--force]`:
- `--enqueue`: for each selected event, `store.submit(project_root, event_dir, kind="analysis", force=force)`;
  prints `queued  <event>  <job id>` or `active  <event>  <job id>` (an active analysis job already exists; the
  store's idempotent submit); exit 0; a database that cannot be reached is the same error and exit code as
  `auto-reel enqueue`'s. No ffmpeg, no ffprobe, no sidecar write.
- `--force` without `--enqueue`: inline, `analyze_event(force=True)`.
The shared function is `submit_analysis(store, project_root, event_dirs, force)` in `scheduler/analysis_job.py`,
which `analysis-enqueue-api` will call too (Principle V).

### 7. Idempotency
- Re-run (not forced): every clip with a current entry costs one `stat` and one small JSON read; a marked clip costs
  the same and is reported failed again.
- Forced run: every clip is analyzed; entries and markers are replaced by atomic rename.
- Worker restart mid-clip: the graceful stop terminates ffmpeg and requeues (as for proxy); a crash leaves the
  row `running`, startup reconciliation requeues it. Finished clips keep their entries; the clip in flight is
  analyzed again. A leftover `*.part-*` file of a killed process is never read (its name is not an entry's),
  is a few KB, and is left alone; `write_entry` removes its own temporary file when its write fails.

### 8. Research & Decisions

#### Analyze originals, not proxies
**Context**: proxies would be cheaper to decode. **Explored**: research `analysis/findings.md` §5 Q3; experiment
005 calibrated `freezedetect n=0.003` on originals. **Decision**: originals. **Rationale**: re-encoded proxy noise
changes freeze detection; proxies are optional and user-prepared, so an event without them could never be analyzed.

#### Priority and pool
**Context**: analysis is long CPU decode work. **Explored**: findings §3 (`cpu_slots` 1, worker bound ~342),
experiment 007 (a proxy job beside a GPU render costs the render 1.3–1.6x without the yield). **Decision**: one CPU
token, own `analysis_slots`, outside the render bound, yield to render and proxy. **Rationale**: same lever 007
validated; renders and the Timeline's proxies are what the user waits for.

#### Failure marker
**Context**: the automatic sweep (`analysis-auto-sweep`) must not re-enqueue a clip that fails every time.
**Explored**: findings §5 Q1. **Decision**: a signal-keyed marker in the same sidecar entry; forced jobs and a
changed clip clear it. **Rationale**: no new store, survives a Postgres rebuild like the entry (Principle II), and
an older build reads it as cold.

#### Cost per minute of footage
**Context**: no figure exists (findings §1). **Explored**: to be measured in the experiment (task 7.1) on a
1080p50 H.264 and a 4K HEVC original, CPU, symlinked read-only from `auto-reel-media` into a scratch library under
`dev-analysis-job/`. **Decision**: recorded in the HLD; it informs `analysis-auto-sweep`'s cap and a later
hardware-decode experiment, and changes nothing in this change's specs.

## Risks / Trade-offs

- [One CPU token shared by CPU renders, proxy jobs and analysis] → yield to both; analysis is outside the render
  bound; `cpu_slots` can be raised by the operator.
- [A 4K HEVC event analyzes for a long time] → per-clip resume, cancel within a second, lowest priority; the
  measured figure goes in the HLD for the sweep's cap.
- [Two-step claim races across several workers] → benign: the yield serves a proxy job first at run time.
- [Leftover `.part-*` files after a kill] → never read as entries, tiny; cleaned by nobody (accepted).
- [Library folders that are read-only] → the job fails at once naming the folder; nothing invented.
- [Published kind enumeration grows] → additive; the web client has no exhaustive map over kinds today (checked:
  `web/src/jobs/kinds.ts` uses predicates), so the regenerated types compile unchanged.

## Migration Plan

None: no Alembic revision, no rescan. Rollback: an older worker fails a queued `analysis` job with a reason naming
the kind ("A claimed job is dispatched by its kind"); sidecar markers read as cold entries.

## Open Questions

- The HLD decision number and the experiment number are the next free ones when the change is applied (D-27 and
  008 at the time of writing; parallel changes may take them first).
