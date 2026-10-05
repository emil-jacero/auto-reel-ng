## Why

The user asked "What does not analyse mean?" and then "Why can i not trigger that from the web?" (2026-10-05), and
chose option 3: automatic per-clip analysis in the background, a Re-analyze button, and "Analyze all" on the event
list. None of that can exist yet. Black/white/freeze detection (HLD §4.5, experiment 005) runs only inline, in
`auto-reel analyze`, and that path cannot be a job: it uses the blocking `FfmpegRuntime.run`, so it cannot be
canceled or report progress; the first bad clip aborts the whole event; and the sidecar is written with a plain
`write_text`, which a concurrent API reader can see half written (research `analysis/findings.md` §1). HLD §4.8
already says "Renders and analysis are **jobs**"; this change makes that true for the worker, so the API
(`analysis-enqueue-api`), the automatic sweep (`analysis-auto-sweep`) and the web controls
(`analysis-web-controls`) each have something to enqueue. It is the first of those four changes and the only one
none of them can do without.

HLD §6: GUI v2 (phase 8 follow-up), beside the proxy job (`proxy-job`, D-21) whose shape it copies. No §8 research
item blocks it; the one unknown, what analysis costs per minute of footage (no figure exists in the HLD or in
experiment 005, which used 20 to 61 s 1080p50 clips), is measured here (task 7.1) and decides nothing in the specs.

## What Changes

- The worker runs jobs of a new kind, `analysis`: for each clip discovery lists in the event folder, in listing
  order, it runs the existing two-pass detection on the **original** clip (experiment 005 calibrated the thresholds
  on originals) when the clip has no valid sidecar entry for its current signal, and skips it when it has one.
  `reel.yaml` is never read or written; nothing outside the event's `.auto-reel/cache/` is written.
- **Force** (the job's existing `force` column): a forced job, which is what Re-analyze will enqueue, analyzes
  every clip whatever the sidecar holds.
- **Cancellable and with progress**: both ffmpeg passes run through `run_with_progress`, so a cancel stops the pass
  within about a second; progress is weighted by clip size (a `stat`, no probe), with each clip's two passes
  filling its share, and travels over the existing job progress and WebSocket.
- **Per-clip failure isolation**: a clip whose analysis fails gets a **failure marker** in its sidecar entry, keyed
  by its current signal, and the job continues; the job ends `failed` naming the failed clips when any clip failed,
  `done` otherwise (the `proxy` precedent). A later job that is not forced does not run ffmpeg on a clip whose marker
  matches its current signal (it reports it failed again, without retrying), so nothing retries it in a loop; a
  forced job, or a changed clip, retries it.
- **Atomic sidecar writes** for every writer (the job and inline `auto-reel analyze`): write a temporary file in the
  cache directory, then rename it over the entry. A reader sees the old entry or the new one, never a partial one.
- **Lowest priority**: claim order `render` > `proxy` > `analysis`; an analysis job holds one CPU token, runs at most
  `worker.analysis_slots` (default **1**) at once, is not counted against the render in-flight bound, and **yields**:
  it starts no clip while a `render` or a `proxy` job is running, giving its CPU token back while it waits.
- **CLI parity** (Principle V): `auto-reel analyze <root> --enqueue [--force]` queues one analysis job per selected
  event instead of running inline; `--force` without `--enqueue` re-analyzes inline, ignoring the cache.
- `JobKind` gains `analysis`, so the jobs API and the WebSocket report analysis jobs with `kind: "analysis"` (the
  published kind enumeration grows; `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated).
  `latest_job` stays the latest render.
- A measured runtime figure (experiment, next free number, 008 at the time of writing): analysis seconds per minute
  of footage for a 1080p50 H.264 and a 4K HEVC original on CPU, recorded in the HLD.
- HLD: a new decision (next free D-number, D-27 at the time of writing) "Analysis is a job", §4.5 and §4.8 notes,
  §6 status.

## Non-goals

- No API route to enqueue analysis, no analysis `state` in `AnalysisOut` (`analysis-enqueue-api`).
- No automatic sweep and no `worker.auto_analyze` setting (`analysis-auto-sweep`); this change only leaves the
  failure marker the sweep needs.
- No web change beyond the regenerated type file (`analysis-web-controls`).
- No analysis of proxies, no hardware decode, no `scale` prefilter, no merging of the two passes: the cost is
  measured first.
- No change to the detection filters, thresholds, parser or overlap rules (media-analysis is unchanged).
- No threshold hash in the cache key (research Q8, deferred).

## Rendered output, staleness, schema

- Rendered output for identical inputs does not change: no `RENDER_GRAPH_VERSION` bump. The staleness fingerprint's
  inputs do not change: analysis results are suggestions, never a render input.
- `reel.yaml` schema: unchanged. Project `config.yaml`: one new key, `worker.analysis_slots` (integer ≥ 1, default 1).
- No Alembic migration: `jobs.kind` is free text and the one-active-per-(project, event, kind) index is generic
  (migration `c4a1d7e9b230`). No rescan.
- The sidecar entry format gains an optional `failure` member. An entry with one has no `segments`, so a build
  without this change reads it as a cold entry and re-runs detection, which is the current behaviour.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `job-scheduler`: ADDED requirements for the `analysis` kind: what it analyzes and writes (only the event's
  sidecar, atomically, never `reel.yaml`), force, per-clip cancel and progress, failure isolation and failure
  markers, the CPU token and `worker.analysis_slots`, the claim order `render` > `proxy` > `analysis`, the yield to
  running renders and proxy jobs, restart, and the CLI's `analyze --enqueue`. MODIFIED: "A claimed job is
  dispatched by its kind" (its in-flight bound now excludes `analysis` as it excludes `proxy`).
- `api-service`: MODIFIED "Job kind is a closed, published vocabulary": the set is `render`, `proxy`, `analysis`.

The research's split named `analysis-cache` as this change's second delta. It is not modified here, deliberately:
its "explicit pass, never auto-run on scan" requirement stays true (a job is enqueued explicitly, and scanning and
the analysis read still run nothing), and `analysis-auto-sweep` is the change that makes analysis implicit and owns
that wording; touching it here too would put two parallel changes on one requirement. The sidecar rules this change
adds (atomic writes, failure markers) are stated in `job-scheduler` as what the job leaves, as `proxy-job` did for
the proxy cache to stay at two deltas. `api-service` is forced: adding the kind changes the published enumeration.

## Impact

- Packages: `auto_reel_ng/analysis/` (atomic `write_entry`, failure marker read/write, a cancellable `analyze_clip`
  with progress, force on `analyze_event`) and `auto_reel_ng/scheduler/` (new `analysis_job.py`, `worker.py` claim
  order, in-flight bound and slot count, `config.py` `analysis_slots`, a yield helper shared with `proxy_job.py`).
- One-line touches outside the two packages, called out in the PR as `proxy-job` did: `persistence/models.py`
  (`JobKind.ANALYSIS`), `ffmpeg/runtime.py` (`run_with_progress` returns the stderr it already collects, which the
  detection parser needs), `cli/main.py` + `cli/commands.py` (the `--enqueue`/`--force` flags and the handler wiring
  in `cmd_worker`). Regenerated: `web/openapi.json`, `web/src/api/schema.d.ts` (no hand-written web change).
- API: the job kind enumeration only. CLI: `analyze --enqueue`, `analyze --force`. No new dependency.
- Compose stack: none; the worker container already has ffmpeg and writes `.auto-reel/cache` in the library's
  event folders (as the render manifest does).
