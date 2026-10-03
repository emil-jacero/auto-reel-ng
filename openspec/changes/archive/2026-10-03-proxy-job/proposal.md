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
- A proxy job holds one **CPU-pool** token while it prepares clips (its x264 encode is CPU work even on the hybrid
  path) and runs at most `worker.proxy_slots` (default **1**) at a time.
- A proxy job is **lower priority than a render**, in three ways: a queued render is claimed before any queued proxy
  job; a proxy job, waiting or running, never uses up the claim capacity a render needs (the in-flight bound does
  not count `proxy` jobs); and a proxy job **yields**: it starts no further clip while a render is running, giving
  its CPU token back while it waits (the clip already encoding finishes). Experiment 007 found that without the
  yield a render beside a proxy job runs 1.3 to 1.6 times slower.
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
- A measurement, not a guess: does a GPU render running beside a proxy job slow down? (Experiment 007 found it does,
  by 1.3 to 1.6 times on the development host, which refuted the 1.15x bound; the yield above is the lever, and the
  experiment was run again with it, recorded in the report.)
- HLD: D-21 gains the job rules, §4.10 and §6 note the proxy job. No `RENDER_GRAPH_VERSION` bump, no fingerprint
  input: proxies are derived state that no render reads.

## Capabilities

### New Capabilities

_None._ (`clip-proxies` is created by `proxy-encode`; this change adds requirements to it.)

### Modified Capabilities

- `job-scheduler`: ADDED requirements for the `proxy` job kind: what it prepares, its CPU token and
  `worker.proxy_slots` limit, render-before-proxy claim order and the in-flight bound, the yield to running renders,
  per-clip monotonic progress, per-clip failure and cache-fault handling, cancel, graceful shutdown and restart,
  independence from the staleness gate and the render-only claim checks, and the operation that prepares one clip
  (proxy then filmstrip, one progress fraction, one cancel check; it lives here, not in `clip-proxies`, to keep the
  change to two capability deltas). MODIFIED: "A claimed job is dispatched by its kind" (its last sentence said the
  in-flight bound treats every kind as a render; it now excludes `proxy`).
- `job-store`: MODIFIED "Race-free claim-next": the order is `render` first, then priority, then age, and a call
  may name kinds that are not eligible. (The merged requirement said priority then age, which the code no longer
  does.)

## Impact

- Code: `auto_reel_ng/scheduler/` (new `proxy_job.py`, `worker.py` admission, in-flight bound and shutdown,
  `pools.py`, `config.py`), `auto_reel_ng/proxies/` (new `prepare.py`). Two packages.
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
