## Why

GUI v2's timeline opens only for an event whose clips have proxies and facts (v2 synthesis §2 X6, §6 risk 9),
and a first-time event costs 41 to 78 s per 10 minutes of footage (research `proxies.md` §3.9). That work must
not run inside a request, block a render, or die with the process. After `job-kind` (a `kind` on every job),
`proxy-encode` (`ensure_proxy`, `facts.json`) and `filmstrip-sprites` (the sprite step) land, nothing yet
*runs* a proxy job: this change teaches the worker to prepare one event's proxies as a `proxy` job, with
progress, cancel and restart behaviour that match a render's, and without ever delaying a render.

## What Changes

- The worker runs jobs of kind `proxy`: for every clip discovery lists in the event, make the proxy and then the
  filmstrip sprite, in listing order, skipping what the cache already holds. The event's `reel.yaml` is never
  read or written; the library is never written; the job needs no staleness verdict and records no fingerprint.
- A proxy job holds one **CPU-pool** token for its whole run (its x264 encode is CPU work even on the hybrid
  path) and runs at most `worker.proxy_slots` (default **1**) at a time.
- A proxy job is **lower priority than a render**: a queued render is claimed before any queued proxy job, and a
  proxy job that is waiting never uses up the claim capacity a render needs.
- Progress is per clip and monotonic: weighted by each clip's source size, with the clip in flight contributing
  its own fraction; `1.0` only at `done`. It travels over the existing job progress and WebSocket frames.
- A clip that fails is reported, the other clips are still prepared, and the job ends `failed` naming every
  failed clip; a cache fault (unwritable or full cache directory) ends it at once. Prepared clips stay cached.
- Cancel stops the encode within about a second, leaves no `.part` file and no half entry in the proxy cache,
  and ends the job `canceled`. A requeue (graceful shutdown or crash recovery) re-runs the job, and every clip
  already prepared costs one `stat`.
- The proxies package gains one operation that prepares a clip (proxy, then sprite) with one progress callback
  and one cancel check. `ensure_proxy` already takes both hooks, removes its build directory on every exit and
  publishes by atomic rename (proxy-encode), and the sprite already takes the cancel check
  (filmstrip-sprites); this change only joins them. Two writers of one entry were already safe.
- A measurement, not a guess: a GPU render running beside a proxy job is not materially slower than alone.
- HLD: D-21 gains the job rules, §4.10 and §6 note the proxy job. No `RENDER_GRAPH_VERSION` bump, no fingerprint
  input: proxies are derived state that no render reads.

## Capabilities

### New Capabilities

_None._ (`clip-proxies` is created by `proxy-encode`; this change adds requirements to it.)

### Modified Capabilities

- `job-scheduler`: ADDED requirements for the `proxy` job kind: what it prepares, its CPU token and
  `worker.proxy_slots` limit, render-before-proxy claim order, per-clip monotonic progress, per-clip failure
  and cache-fault handling, cancel, graceful shutdown and restart, and independence from the staleness gate
  and the render-only claim checks.
- `clip-proxies`: ADDED requirement for being driven by a job: preparing a clip (proxy and filmstrip) as one
  operation with progress that reaches `1.0` only after the filmstrip, and a cancel check across both. (The
  cleanup-on-cancel and concurrent-writer rules a job needs are already requirements of the merged
  `clip-proxies` spec.)

## Impact

- Code: `auto_reel_ng/scheduler/` (new `proxy_job.py`, `worker.py` admission and shutdown, `pools.py`,
  `config.py`), `auto_reel_ng/proxies/` (new `prepare.py`). Two packages.
- One line of wiring outside them: `cmd_worker` in `cli/commands.py` passes the resolved `proxy_slots` and
  `config.yaml` stays the only place the setting lives (no new flag, no new subcommand).
- Dependency on the gates (merged, read): `job-kind` gave a `kind` column, a per-kind unique index and the worker's
  `kind_handlers` seam, but its `claim_next` neither filters nor orders by kind, so task 4 adds an
  `exclude_kinds` argument and a render-first order term to `claim_next` in `persistence/job_store.py` (no
  migration). It is the one touch outside the two packages and is called out in the PR.
- No API, WebSocket or web change: `kind` in the job read model and the enqueue endpoint belong to
  `proxy-enqueue-endpoint`. No Alembic revision, no new runtime dependency, no `RENDER_GRAPH_VERSION` bump.
- Compose stack: the worker already runs with `XDG_CACHE_HOME=/data/cache`; proxies land beside the
  thumbnails with no compose change (task 8 pins that with a test).
