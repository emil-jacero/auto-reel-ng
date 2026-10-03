## Context

GUI v2 plays and edits on 540p proxies (D-21, written by `proxy-encode`) and reads clip facts from the proxy
cache entry (`facts.json`) rather than probing, so the timeline can open only for an event whose clips are
prepared (research synthesis §2 X6, §3 "Generation", §6 risk 9). Preparation is slow and I/O bound:
9.5 min of Sony footage took 49 s on one worker and 41 s on two (88 MB/s, near the USB drive's 101 MB/s); a
10.8 min 50p event took 78 s and 57 s (compute bound) (`proxies.md` §3.9; synthesis §3: two workers gave only
+20 to +35 %, so the default is one). It must therefore be a job: visible, cancelable, restartable, and
behind renders (synthesis §6 risk 8).

What this change builds on, now merged and read (names are the merged code's):

| Gate | What it gave |
|---|---|
| `job-kind` | `JobKind.PROXY`, `jobs.kind`, the unique-active index per (project, event, kind), and `Worker(kind_handlers=...)`: a `KindHandler` is `Callable[[Job], None]`, owns its own capacity token, returns for `done`, raises `RenderCancelledError` for `canceled` or an `EngineError` for `failed`; the render-only checks live in `_process_render` only. `claim_next` is unchanged (no kind filter or order). |
| `proxy-encode` | `ensure_proxy(clip, settings=, runtime=, profile=, render_node=, on_progress=, should_cancel=)` (cache hit = one `stat`; build in a uniquely named hidden `.part` directory, removed on every exit; atomic publish that survives a concurrent writer; monotonic progress ending at 1.0; `FfmpegCancelledError` on cancel), `lookup_proxy`, `ProxyError` / `ProxyCacheError`, `resolve_proxy_settings(config, project_root)`, `proxy_key`. |
| `filmstrip-sprites` | `ensure_filmstrip(clip, entry, runtime=, should_cancel=)` and `lookup_filmstrip`; a clip of one second or less gets a one-tile sprite (every clip gets a sprite, so "no sprite" is not a normal outcome after all, but a `FilmstripError` is a clip failure that leaves the proxy valid); `FilmstripError`; no progress callback (one ffmpeg output frame). |

Repo facts used: `scheduler/worker.py` (`Worker._process_job`, injectable seams, `_cancel_requested`),
`scheduler/pools.py` (one CPU semaphore, `token_for`), `scheduler/progress.py` (`ThrottledProgress` is already
non-decreasing), `persistence/job_store.py` (`claim_next` orders `priority DESC, created_at`; `submit` has no
priority; `priority` is "reserved-unused"), `ffmpeg/runtime.py` (`run_with_progress(should_cancel=, on_progress=)`
kills ffmpeg and raises `FfmpegCancelledError`), `cli/thumbnails.py` (the model for "every clip discovery lists,
no `reel.yaml`, never MISSING"), `compose.yaml` (`XDG_CACHE_HOME: /data/cache` for server and worker).

## Goals / Non-Goals

**Goals**
- A worker runs `proxy` jobs: per event, per clip, `ensure_proxy` then the sprite step, with the guarantees
  of the render path where they apply (isolation, progress, cancel, requeue) and without the render-only ones.
- A running or queued proxy job never delays a render's start on the GPU path, and a queued render is always
  claimed first.
- Cancel and kill leave the cache without `.part` files or torn entries.
- Evidence about how much slower a concurrent render is (decision 9), and a lever that brings it down: the yield
  (decision 6).

**Non-Goals**
- The API (`kind` in `JobOut`/WS frames, the enqueue endpoint): `proxy-enqueue-endpoint`.
- Any web change; reading proxy state: `proxy-state-read`.
- Cache eviction or a size cap (brief: none in v2; `--prune` of orphans belongs to `proxy-encode`).
- A second concurrent proxy worker pool, auto-enqueue on scan or on opening an event.
- Preempting a running proxy job for a render (the render waits for a token only if it needs the CPU one).

## Decisions

### 1. A proxy job is one event; its work is "every clip discovery lists"

The runner (`scheduler/proxy_job.py`) lists the event with `scan_event`, like `thumbs`: every clip on disk, the
IGNORED ones too, never `reel.yaml`, so editorial edits can neither add work nor invalidate any (brief: editorial
edits never invalidate the cache; a clip a user ignores today is a clip the timeline shows tomorrow). Clips that
resolve to one cache entry (symlinks to one file; the key follows symlinks, D-11) are prepared once. Order is
the listing order, so the first clips of the event are ready first.

Why not read `reel.yaml`: Principle II makes `reel.yaml` the editorial truth, but proxies are *derived from
media*, not from editorial; reading it would add a failure mode (a parse error) that has nothing to do with
the media and would make the job's work depend on a file the user is editing.

Why none of the render claim checks (output collision, claimed movie, running-output refusal, staleness
recheck): a proxy job writes no output path, no `reel.yaml`, no manifest. Those requirements guard files the
proxy job never touches. The job-kind dispatch is the place they stop applying; this change relies on
`job-kind` having scoped them to `render` and adds a test that a colliding or stale event still gets its proxies.

### 2. Settings come from the job's own project, resolved per job

As `default_build_job` loads the claimed job's own `config.yaml`, the proxy runner resolves `proxies.*` from the
job's `project_root`. A config that does not load, or a cache directory the resolver refuses (inside the
library), fails the job with the resolver's message before any ffmpeg runs (Principle I). The default location
is `$XDG_CACHE_HOME/auto-reel/proxies/` (brief), so in the compose stack proxies land in `/data/cache/auto-reel/proxies/`
beside the thumbnails with no compose change; task 8 pins that.

### 3. Progress: weighted by source size, per-clip fraction inside, monotonic

Fraction = (bytes of finished clips + `size(current) * clipfraction`) / total bytes, where `clipfraction`
comes from the encode's own `-progress` and the sprite step counts as the last small slice of its clip.
Considered and rejected:
- *Equal weight per clip*: one 1-hour clip among 20 short ones would park the bar at 95 % for most of the job.
  Real events do mix (p90 event is 58 min of footage, `proxies.md` §3.9).
- *Footage duration*: not known before the work (durations come from the probe that `ensure_proxy` itself runs,
  and the staleness/read paths must stay probe-free); file size is a `stat`. Encode time is I/O and decode bound
  at a fairly constant bytes-per-second per source class (47 to 88 MB/s on MOL), so size tracks time well enough
  for a progress bar.
- A cache hit weighs its full size but completes at once: the bar jumps over cached clips, never back.

It goes through the existing `ThrottledProgress`, which already drops any lower fraction and never drops the
terminal `1.0`. A zero-size file weighs 1 byte. A job whose every clip is cached reaches `1.0` and `done`
immediately.

### 4. A clip failure does not stop the others; the job still fails loudly

Per-clip isolation is the thumbnail model (`thumbs` reports each failed clip and goes on). The job ends:
- `done` when every clip has a proxy and a sprite;
- `failed` otherwise, error `"<n> of <m> clips failed: <identity>: <reason>; ..."` (one-line causes, capped to
  the first few with a count), after the other clips were prepared. Re-enqueueing is cheap because prepared
  clips are cache hits.
- A **cache fault** (cache dir unwritable or full) ends the job at once with that cause, because it is not a
  property of any clip (`ThumbnailCacheError` precedent): every remaining clip would fail the same way.
- Cancel and shutdown end it immediately (decision 7).

Nothing is fabricated: a failed clip has no proxy and no facts, and the next read says `failed`/`absent`, never a
guess (Principle I).

### 5. Capacity: one CPU token while it works, at most `worker.proxy_slots` at once

A proxy job takes the **CPU** semaphore (`CapacityPools`) while it prepares clips, never a GPU token (it gives
the token back only while it yields to a running render, decision 6): the hybrid path's
VAAPI decode is ~0.03 core-s per footage second and not a scarce session (synthesis X8), while its libx264 encode
is 0.18 to 0.47 core-s per footage second (`proxies.md`). The render worker's tokens are untouched; GPU renders
therefore run concurrently with a proxy job. A job that falls back to CPU decode is the same class, so one token
is still right (no mid-job handoff, as D-S3).

`worker.proxy_slots` (default **1**, validated like `cpu_slots`) caps proxy jobs in flight. Why a separate limit
if the CPU pool already serialises at the default of 1: with `cpu_slots: 4` the CPU pool would admit four
proxy jobs and starve CPU renders; the brief asks for "concurrency 1". Two proxy jobs gave +20 to +35 % at best
and doubled the load on one USB disk.

Known limit, stated not hidden: with the default single CPU slot, a CPU-encoded render claimed while a proxy
job runs waits for the token until the clip being prepared ends (the proxy job yields it at the next clip
boundary, decision 6; a clip takes seconds to a few minutes). On the VAAPI hosts this project targets, renders take
the GPU token and do not wait. Raising `worker.cpu_slots` lifts it.

### 6. Priority: kind-aware claim, not a priority number, not preemption

"Lower priority than renders" means four things the worker enforces:
1. **Order**: a queued render is claimed before any queued proxy job, however old the proxy job is.
2. **Admission**: a proxy job is claimable only while fewer than `proxy_slots` proxy jobs are in flight. Without
   this, a second queued proxy job would be claimed, sit waiting for the CPU token and hold an in-flight slot.
3. **The in-flight bound does not count proxy jobs.** The claim loop stops at `total_capacity` in-flight jobs
   (D-S3), counting jobs that wait for a token. Review found that a claimed proxy job could take one of those
   slots: with a CPU-classified render queued first and a GPU render second, the CPU render is claimed, waits for
   the proxy job's CPU token, and the bound is full, so the GPU render stays queued with the GPU idle. `proxy`
   jobs are therefore left out of the count (they have `proxy_slots` as their own bound); every other kind counts
   as before. The cost: up to `proxy_slots` threads beyond `total_capacity`, one of them working.
4. **Yield**: a proxy job starts no clip while a `render` job is `running` (`list_by_status(RUNNING,
   kind=render)`, one cheap query, between clips, polled once a second while it waits). A clip already encoding
   finishes: no preemption, so no half-done state to resume. While it waits it **releases its CPU token**,
   otherwise a CPU render that is claimed (so `running`) and waiting for that token would wait for a proxy job that
   waits for it. The job takes the token back when no render runs. Why it is in this change and not a follow-up
   (this design first deferred it as `proxy-yield`): experiment 007 refuted the bound the change was to meet, and a
   claim order that leaves every concurrent render 1.5 times slower for minutes does not make a proxy job
   "lower priority". Cost: with renders running back to back, a proxy job waits; that is the meaning of lower
   priority, and the job can be cancelled. A render that is `running` on another worker counts too. A fully
   cached event also waits for a running render before it reports `done` (the check is per clip, not per
   encode); that is accepted rather than adding a cache look-up to the handler.

So `claim_next` takes the kinds the worker will accept now and orders `render` before `proxy` ahead of
`priority`/`created_at`. Alternatives rejected:
- *Stamp proxy rows with a low `priority`*: `submit` has no priority argument and the column is documented
  "reserved-unused"; every enqueuer (API, CLI, a future auto-prepare) would have to remember the number. The
  kind-based rule has one home and cannot be forgotten. It also cannot express (2).
- *Claim then requeue a proxy job when a render waits*: a requeue puts the older proxy job first again;
  the worker would claim it forever (starvation) and bump `requeue_count` as noise.
- *Preempt a running proxy job when a render arrives*: needs cancel-and-resume semantics for little gain, since
  the proxy job takes no GPU token and a finished clip is never redone.

`job-kind`'s `claim_next` has no kind support, so task 4.1 adds an `exclude_kinds` argument and an order term
(`render` first, then `priority`, then `created_at`) to `claim_next` (a few lines in
`persistence/job_store.py`, no migration). `exclude_kinds` rather than an allow-list so that a kind this build
has never heard of is still claimed and failed loud (job-kind), not left queued forever. That is the single
file outside `scheduler`/`proxies` and is called out in the proposal and the PR. The merged `job-store` spec
orders by priority then age and says nothing of kinds, so this change carries a MODIFIED "Race-free claim-next"
for it; the "dispatched by its kind" requirement of `job-scheduler` is MODIFIED for point 3.

### 7. Cancel, shutdown, requeue

- **Cancel**: the runner passes `should_cancel` (the same `store.get(...).cancel_requested` poll renders use)
  to `ensure_proxy` and `ensure_filmstrip`, which hand it to `run_with_progress` (polled about once a second,
  ffmpeg killed, `FfmpegCancelledError`; `ensure_proxy` removes its build directory on the way out, as the
  sprite step does). The runner maps `FfmpegCancelledError` to the scheduler's `RenderCancelledError`, which
  the worker's handler path maps to `canceled`. The cancel is also checked between clips, while the job
  waits for its CPU token and while it yields to a render. Clips already finished stay.
- **Graceful shutdown / restart**: the existing `_requeue_inflight` and `reconcile` already requeue any
  `running` row regardless of kind; the re-run finds finished clips in the cache. But requeueing a row does
  not stop the thread that works on it, and the process exits right after, which would leave ffmpeg running
  and its `.part` behind. So the worker shares one stop event with its handlers (`Worker(stop_event=...)`;
  `cmd_worker` passes the same event to the proxy handler); the handler polls it with the cancel check, and
  after requeueing, `run` waits a bounded few seconds for handler threads to finish their cleanup. A render
  thread is not waited for (it does not watch the event; unchanged). A killed (SIGKILL) worker can leave a
  `.part` directory; the next preparation of that clip builds in its own uniquely named directory and never
  trusts a leftover (the stale sweep is `proxy-encode`'s).
- **Concurrent writers**: the job, `auto-reel proxies` and a second worker may prepare the same clip.
  `proxy-encode` already builds in a uniquely named directory and publishes by atomic rename, adopting a
  complete winner; this change adds no lock (`proxies.md` §4 suggested one; a lock needs stale-detection and
  heartbeats for a case that costs at most one duplicated encode, Principle VII).

### 8. A proxy job and a render of one event coexist

With the unique-active index per (project, event, kind), an event may have a running render and a running proxy
job. They share the source files read-only; the proxy job writes only the cache. Neither makes the other
stale: no fingerprint input, no `RENDER_GRAPH_VERSION` bump (rendered bytes are unchanged), no manifest write.
Test: the staleness verdict and the manifest are identical before and after a proxy job.

### 9. The measurement

Hypothesis: with a GPU-classified render of one event running, a concurrent proxy job on another event of the
dev library makes the render's wall time at most **1.15x** its solo time (median of three, same clips, warm
page cache for both arms; one cold-cache pass reported separately). Both run on the VAAPI device (proxy: VAAPI
decode + `scale_vaapi`; render: VAAPI normalize + encode), so contention would show on the GPU, the CPU
(x264 at 0.18 to 0.47 core-s per footage second), or the shared USB disk. If it exceeds the bound, the first lever
is a thread cap on the proxy's x264 (a `proxies` setting from `proxy-encode`); anything beyond that (pausing
proxy jobs while a render runs) is reported as a follow-up change, not built here.
Run per the repo's
`running-experiments` skill (report with host, commands, verdict). **Result (experiment 007, 2026-10-03): refuted as first built.** On the development host (a Radeon 860M APU, shared and loaded by
other work, VAAPI) the median render took 1.28 to 1.56 times its solo time beside a proxy job; a thread cap
(4 and 2) and the CPU decode path did not bring it under 1.15, so the cost is not x264's threads and not the
proxies' GPU decode. The change first shipped anyway and the review refused to accept a refuted bound on a ticked
task, so the lever the report proposed, the yield (decision 6, point 4), was folded in and the experiment run again
with a no-yield control: warm median **1.12** (pairs 1.12 to 1.13, bound 1.15), cold pair 1.29; the control on a busier
host 1.17. The yield bounds the overlap to the clip in flight; it does not remove it, and the two runs are not a
clean A/B (the host load differed). `nice`/`ionice` on the proxy ffmpeg was not tried.
