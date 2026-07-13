# auto-reel-ng (engine)

The engine foundation for auto-reel-ng: a binary-agnostic **ffmpeg runtime** and a
**fail-loud media-probe** layer. Every later change (capability profiles, render
pipeline, analysis, service/GUI) builds on this package.

## Requirements

- **ffmpeg / ffprobe ≥ 7.1** (locked decision **D-1**). Later filter work relies on
  7.1-only filters, so `FfmpegRuntime` asserts the version at construction and fails
  loud with a clear message rather than producing a cryptic error mid-render.
- Python ≥ 3.13.

The runtime resolves the binaries in a fixed precedence order:

1. explicit constructor argument,
2. `AUTO_REEL_NG_FFMPEG` / `AUTO_REEL_NG_FFPROBE` environment variables,
3. bundled jellyfin-ffmpeg (`/usr/lib/jellyfin-ffmpeg`),
4. system `PATH`.

## Fail-loud guarantee

`probe_media()` runs **exactly one** `ffprobe` per file and returns an immutable
`ClipMetadata`. If a file is missing, empty, has no video stream, is unparseable, or
reports an implausible frame rate, it raises `ProbeError`. It **never fabricates
metadata** (no assumed 1920×1080 / 25 fps). Absent audio and absent rotation are modeled
as explicit `None`, never invented defaults. Use `probe_many()` to probe a batch while
skipping and reporting failures.

## Quick start

```python
from auto_reel_ng import FfmpegRuntime, probe_media

runtime = FfmpegRuntime()           # resolves binaries, asserts ffmpeg >= 7.1
meta = probe_media("clip.mp4", runtime=runtime)
print(meta.width, meta.height, meta.fps, meta.is_hdr, meta.has_audio)
```

## Command line (`auto-reel`)

Installing the package provides an `auto-reel` entry point that drives the whole
pipeline headless. It takes a **project root** (the directory an ingest layout
walks; defaults to the current directory) and writes one movie per event.

```bash
auto-reel render  <root> -o out           # scan -> gate -> reconcile -> probe -> resolve -> render
auto-reel scan    <root>                  # inventory: events + NEW/ACTIVE/IGNORED/MISSING clips + staleness
auto-reel analyze <root>                  # detect black/white/freeze segments, cache suggestions
auto-reel import  <root>                  # adopt auto-reel legacy metadata into a v2 reel.yaml
auto-reel enqueue <root>                  # scan -> gate -> insert one queued job per stale event
auto-reel worker  <root>                  # run the job-scheduler loop until SIGINT/SIGTERM
auto-reel jobs list|show|cancel <root>    # read the job store; request cancellation
auto-reel serve   <root>                  # run the API service (REST + WS) until SIGINT/SIGTERM
auto-reel adopt-renders <root>            # one-time: write manifests for an already-rendered archive
```

Shared options: `--years 2023,2024` (year-event layout), `--layout flat|year-event`,
and `-o/--output`. `render` and `enqueue` also take `--force` (bypass the staleness
gate below); `render` additionally takes `--dry-run` (print the ffmpeg commands and
write nothing) and `--device <amd|nvidia|intel|cpu|device-id>`.

- **Layouts** map the project root to event directories: `year-event`
  (`<root>/<year>/<event>/`, the default) and `flat` (events directly under the root).
- **Adoption policy:** an event with no `reel.yaml` is seeded from its folder
  structure; on later runs `render` adopts any newly added clip into the default
  chapter (so it is never silently dropped) and reports clips that went `MISSING`.
- **Per-event isolation:** one event failing to render is reported with its cause
  and does not abort the rest; the exit code is non-zero if any event errored.

### Change detection (staleness gate)

`render`, `enqueue` (CLI and `POST /api/v1/jobs`), and the worker's claim-time
recheck all go through **one staleness gate**: an event is **stale** if it has no
render manifest, its current fingerprint differs from the manifest's, or the
manifest's recorded output file is missing — otherwise it is **fresh** and is
skipped (not rendered, not enqueued, or completed without rendering).

- **The fingerprint** is a hash over four components — the event's editorial
  document (`reel.yaml`, in canonical parsed form; a reformat/comment-only edit is
  not a change), the resolved project `look` defaults, the on-disk clip set (each
  clip's size + mtime, or a content hash under an opt-in), and the engine identity
  (a hand-bumped `RENDER_GRAPH_VERSION` constant plus the ffmpeg version). It never
  probes media and never depends on the acceleration profile/device — rendering the
  same event on CPU or GPU yields the same fingerprint.
- **The manifest** (`<event>/.auto-reel/cache/render-manifest.json`) is the *sole*
  record of an event's last successful render — no database copy. It is written by
  the engine only after a render's output is verified and atomically finalized,
  never on a skip, a dry run, or a failure.
- **`--force`** bypasses the gate entirely: `render --force` re-renders and
  replaces output even if fresh; `enqueue --force` / `POST /api/v1/jobs {"force":
  true}` enqueues even a fresh event, carrying `force` on the job row so it
  survives to the worker's claim.
- **`RENDER_GRAPH_VERSION`** (`auto_reel_ng/staleness/fingerprint.py`) must be
  bumped by hand whenever a change alters produced output for identical inputs
  (a command-graph, filter, or encoder-flag change) — under-bumping risks a missed
  re-render (mitigated by `--force`); over-bumping just costs one archive re-render.

**BREAKING: `render`'s `--overwrite` flag was removed.** `--force` now covers both
"bypass the gate" and "replace an existing output" — scripts using `--overwrite`
need only rename the flag.

**Deploying onto an already-rendered archive:** run `auto-reel adopt-renders <root>`
once. For every event whose output already exists, it writes a manifest at the
current fingerprint — the operator's assertion that today's output reflects
today's inputs — without rendering anything, so turning on the gate does not
trigger a full archive re-render. Events with no output are reported as
unrendered and left alone (they are not adoptable).

### Job scheduler (`enqueue` / `worker` / `jobs`)

A durable Postgres-backed queue (the `jobs` table) that lets rendering outlive one
CLI invocation and survive a crash or restart without losing or duplicating work.

- **`enqueue`** scans the project (same layout/`--years` selection as `render`),
  applies the staleness gate above, and inserts one `queued` job per **stale**
  event, storing its **project-root-relative** event path, the project root, its
  fingerprint, and the `force` flag; it never probes or renders. A fresh event is
  reported and not enqueued unless `--force`. Re-running it is idempotent — an
  event with an already-active (`queued`/`running`) job is reported, not
  duplicated.
- **`worker`** runs the claim/execute loop: it polls the store (every 1–2s when
  idle), and for each claimed job **rebuilds the render plan from current disk
  state** — a job row is an event reference, never a frozen plan, so an edit made
  to `reel.yaml` while a job is queued renders the latest state. After the rebuild
  it re-evaluates the staleness gate (unless the job's `force` flag is set): a
  fresh event completes `done` without rendering — this is what absorbs a
  requeued, already-finished orphan without a redundant re-render.
- **`jobs list`/`show`/`cancel`** are a read-only view plus cancellation. `cancel`
  on a `running` job only sets its `cancel_requested` flag — the worker remains the
  sole writer of `status` and stops itself between segments (**cancel latency is
  about one segment's encode**, seconds to roughly a minute on VAAPI; there is no
  mid-ffmpeg kill in this version). `cancel` on a `queued` job cancels it directly.

**Requeue-on-restart:** every `worker` process boot gets a fresh `host:pid:nonce`
identity and, before claiming any work, resets every `running` row not owned by a
*live* worker back to `queued` — unconditionally, with no verification step. This
is sound because output finalization is atomic (below): a truly-finished orphan
re-runs, hits the engine's skip-if-exists check, and completes as `done` in
milliseconds instead of re-rendering. There is currently **no heartbeat / hung-worker
detection** — this reconcile only catches a crashed or cleanly-restarted worker, not
one that is still alive but stuck.

**Capacity:** the worker selects its acceleration profile once at startup (like
`render`) and enforces two pools — one semaphore per hardware render node (default
capacity 1) plus a global CPU semaphore — classifying each job by its *resolved*
encoder after the plan rebuild, so a CPU-only job always runs alongside a GPU
render rather than waiting behind it.

**Atomic finalize (movie-assembly):** the engine concats to `<output>.mp4.part` in
the output directory and only `os.replace()`s it into the final path after
post-render verification passes. A file existing at the final path is therefore
always a complete, verified render — even across a hard kill (SIGKILL/OOM/power
loss) mid-assembly — which is what makes unconditional requeue-on-restart safe.

Pool sizes and the poll interval come from `config.yaml`'s `worker` map (below),
overridden by `worker`'s own `--gpu-sessions-per-device`, `--cpu-slots`, and
`--poll-interval` flags (same CLI-over-config precedence as everything else).

### API service (`serve`)

`auto-reel serve <root>` runs a FastAPI service (REST + a WebSocket) over the same
engine `render`/`enqueue`/`worker`/`jobs` already use — a deliberately **thin
layer**: every endpoint maps to an operation the CLI can also reach, and no scan,
render, or job logic lives in the web tier.

- **Events are scanned on request.** `GET /api/v1/events` and
  `GET /api/v1/events/{event_id}` walk the configured layout and parse each
  event's `reel.yaml` fresh on every call — there is no database copy of event or
  clip state, so an edit made on disk is visible on the very next request. The
  `event_id` is the root-relative event directory (URL-encoded), the same identity
  `jobs`/the job store already use. `GET /api/v1/events/{event_id}/analysis`
  exposes the read-only analysis sidecar cache; it never triggers analysis.
- **Jobs lifecycle over REST** is a thin wrapper over the job store:
  `POST /api/v1/jobs` (gated like `enqueue` — 201 on a stale event, 409 with the
  existing job's id on an active duplicate, 200 `"status": "fresh"` with the
  fingerprint and manifest reference when the event is fresh and `force` is not
  set), `GET /api/v1/jobs` / `GET /api/v1/jobs/{id}` (includes `force` and
  `fingerprint`), and `POST /api/v1/jobs/{id}/cancel` (`request_cancel`, same
  semantics as `jobs cancel`). The API never writes a job's `status` itself.
  `GET /api/v1/events/{event_id}` includes the same staleness verdict (`stale` +
  `reasons`) `scan` prints, computed read-only — a GET never writes a manifest.
- **`WS /api/v1/ws/jobs`** pushes live job progress: a subscriber gets a full
  snapshot of active (`queued`/`running`) jobs on connect, then delta messages
  (progress changes and status transitions, including terminal) from a single
  central poller that queries the store roughly once per `api.poll_interval` —
  and only while at least one subscriber is connected. A subscriber that falls
  behind (a full outbound queue) is disconnected rather than back-pressuring the
  poller; it reconnects and resyncs via a fresh snapshot.
- **`GET /healthz`** reports liveness and database reachability.
- **Bind/auth posture:** the default bind is `127.0.0.1` — widening it to a LAN
  address is an explicit operator choice (`api.host`/`--host`). There is **no
  authentication in v1**; a single middleware hook point exists for a future
  static-bearer-token check to drop in without any route changes.

```bash
auto-reel serve <root> --host 127.0.0.1 --port 8080
```

Settings resolve through the same config-then-flag layering as `worker`:
`api.host`/`api.port`/`api.poll_interval` in `config.yaml`, overridden by
`serve`'s own `--host`, `--port`, `--poll-interval` flags.

### Project `config.yaml`

An optional `config.yaml` at the project root supplies shared defaults. Every field
is optional; a command-line flag overrides it, and an event's `reel.yaml` overrides
the project `look`.

```yaml
# config.yaml
layout: year-event        # ingest layout name
input: media              # walk root, relative to the project root (optional)
output: out               # default output directory (optional)
look:                     # opaque defaults passed to resolve() as look_defaults
  resolution: 1080p
  video_codec: h264
worker:                    # job-scheduler worker settings (all optional)
  gpu_sessions_per_device: 1   # concurrent GPU-encode sessions per render node
  cpu_slots: 1                 # concurrent CPU-encoded renders
  poll_interval: 2.0           # seconds between empty claim polls
api:                       # API service ('serve') settings (all optional)
  host: 127.0.0.1              # bind host; widen only deliberately
  port: 8080                   # bind port
  poll_interval: 1.0           # seconds between WS hub poll ticks
```

## Development

```bash
pip install -e ".[dev]"
pytest                 # tests build synthetic clips via ffmpeg lavfi; no real media needed
black . && isort . && mypy auto_reel_ng && pylint auto_reel_ng
```

The persistence suite (`requires_db`-marked tests) needs **podman** on `PATH`: a
session-scoped fixture starts a throwaway Postgres container per test run and tears
it down after. Tests not marked `requires_db` run without it.

To provision a database by hand (dev default is
`postgresql+psycopg://auto_reel_ng:auto_reel_ng@localhost:5432/auto_reel_ng`, overridden
by `DATABASE_URL` or `config.yaml`'s `database.url` — see
`auto_reel_ng/persistence/config.py`):

```bash
DATABASE_URL=postgresql+psycopg://... alembic upgrade head
```
