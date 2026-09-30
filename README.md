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
                                          #   (--dry-run previews without writing)
```

Shared options: `--years 2023,2024` (year-event layout), `--layout flat|year-event`,
and `-o/--output`. `render` and `enqueue` also take `--force` (bypass the staleness
gate below); `render` additionally takes `--dry-run` (print the ffmpeg commands and
write nothing) and `--device <amd|nvidia|intel|cpu|device-id>`.

- **Layouts** map the project root to event directories: `year-event`
  (`<root>/<year>/<event>/`, the default) and `flat` (events directly under the root).
  An event directory containing a `.reelignore` file (contents unread) is not an
  event: both layouts skip it and log `skipping <dir>: .reelignore` at INFO. A marker
  at year or root level has no effect; deleting the marker restores the event.
- **Adoption policy:** an event with no `reel.yaml` is seeded from its folder
  structure; on later runs `render` adopts any newly added clip into the default
  chapter (so it is never silently dropped) and reports clips that went `MISSING`.
  Clips are discovered one level deep: root clips form the default chapter and each
  immediate subfolder a named chapter. A subfolder named `original` (any case; legacy
  pre-conversion camera originals) or containing `.reelignore` is never a chapter, and
  its files are never touched.
- **Legacy documents:** a `reel.yaml` without `version` is auto-reel's format and is
  imported on every load (not only by `auto-reel import`). Its `sort` (`method`,
  `reverse`, `custom_order`) is carried as the event's own `sort`, so it orders the
  event's clips when they are first adopted; only an unknown method is reported. A
  top-level `title` of the form `<YYYY-MM-DD> - <rest>` (auto-reel's movie-name stem)
  imports as title `<rest>`, and supplies the date when none is given, provided the
  date is real and matches any `metadata.date`; any other title is kept verbatim.
  Before running `auto-reel import`, remove the trailing location from a legacy
  `metadata.yaml` title such as `Dans hemma - Kungälv`, or the name repeats it.
- **Event metadata resolves field by field.** Date, title and location each come
  from the event's `reel.yaml` when set there (blank counts as unset), else from the
  folder name, read as `[<YYYY-MM-DD> - ]<title>[ - <location>]`. The folder name is
  only a fallback: resolution happens at load and is never written back to
  `reel.yaml`, and renaming a folder changes only the fields `reel.yaml` leaves unset.
  Nothing is guessed from media (file dates of digitized footage are digitization
  dates).
- **An event needs a real date and a title.** An event whose resolved metadata has no
  date, no title, or a date after today is reported per event, naming the reason and
  the fix, for example
  `ERROR  2019-04-31 - Golfträning: no date: folder name date 2019-04-31 is not a real date; set metadata.date in reel.yaml or correct the folder name`.
  A folder name with a year only (`2004 - …`) or no date (`Blandat`) is reported the
  same way. It is not an error when `reel.yaml` supplies the field.
- **Per-event isolation:** one event failing to render is reported with its cause
  and does not abort the rest; the exit code is non-zero if any event errored. This
  includes document errors: in `scan`, `render`, `enqueue` and `adopt-renders`, an
  event whose `reel.yaml` cannot be parsed or whose metadata fails the rule above is
  reported as `ERROR`, gets no seed, render, job or manifest, and the rest proceed.
- **Output layout:** each movie is written to
  `<output>/<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`, where the year folder
  and the date prefix both come from the event's `metadata.date` (the layout and
  names legacy auto-reel used). With no `-o` and no `config.yaml` `output`, the
  output directory is the sibling folder `<parent>/<root-name>-output` (for
  example, `videos/sorted` → `videos/sorted-output`). Do not point the output
  inside the walked root: the layouts would scan its year folders back in as events.
- **Output collisions fail loud:** `render`, `enqueue` and `adopt-renders` refuse
  every event whose output path it shares with another selected event (compared
  case-insensitively). Each such event is reported as `ERROR`, nothing is rendered,
  queued or adopted for it, an existing file at that path is left untouched, and
  the exit code is non-zero. Fix it by giving one event a distinct `title` or
  `location` in its `reel.yaml`.

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
Point `-o` at the legacy auto-reel output root: adoption looks for
`<output>/<YYYY>/<YYYY-MM-DD> - <title>[ - <location>].mp4`, the same layout and
names legacy wrote. Preview first: mount the archive read-only and run
`auto-reel adopt-renders <root> -o <output> --dry-run`. It reports what it would
adopt, with the same totals and exit code as a real run, and writes nothing.
Remount read-write only for the real run. Check the `unrendered` count before the
first library-wide `render`: an event whose legacy name differs from its current
title shows up there instead of being adopted, and would otherwise be re-rendered.
A legacy `reel.yaml` title that starts with its date (`2025-01-13 - Resa till Gran
Canaria`) is split on load, so it adopts under its legacy name. `import` still reads
legacy `metadata.yaml` titles verbatim; see *Legacy documents* above.

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
the final output's own directory (its year folder) and only `os.replace()`s it into the final path after
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
  `jobs`/the job store already use. Each clip in the **detail** response also
  carries its file's byte `size` and `mtime` (UTC), read straight from the
  directory entry, so a reorder view can show more than an opaque camera
  filename; both are `null` for a clip the document references but disk does not
  have. These are *file* facts — nothing is decoded to produce them, and media
  facts (duration, dimensions, codec) are deliberately not here. The **list**
  response keeps its clip counts and carries no per-clip facts. A detail clip's
  `status` is one of `new`, `active`, `missing` or `ignored`.
  Every **list** row carries `kind`: `"event"` for a summary, `"error"` for an
  event that could not be read. An error row carries only `event_id`, a
  `failure` (`unparseable_reel_yaml`, `unusable_metadata` or `unreadable_disk`)
  and the engine's `detail`, which names the fix, so one bad event costs one row,
  never the list (as `scan` prints `ERROR <event>: …` and carries on). The detail
  route answers such an event with a 502 carrying the same `failure` and `detail`
  as its error row, never a 500. A database or walk failure still fails the whole
  list (503 or 502).
  `GET /api/v1/events/{event_id}/analysis` exposes the read-only analysis sidecar
  cache; it never triggers analysis.
- **`GET /api/v1/events/{event_id}/reel`** returns the event's **complete**
  editorial document — metadata, ordered chapters/clips, per-clip properties,
  `ignore` and `look` — in exactly the shape the `PUT` below accepts, parsed
  fresh from `reel.yaml`. It is read-only: it never creates the file and never
  writes a manifest. An event with clips but no `reel.yaml` yet reads as the
  **empty document** (200, not 404), mirroring the write's own seeding, so read
  and write accept the same set of events — including one whose folder name has
  no usable date, which is how a client gives it one. An unparseable or
  unreadable document is the scan-failure 502 carrying the same `failure` and
  `detail` the detail route reports, never a partial one. **A write body comes from this endpoint,
  never from `GET /api/v1/events/{event_id}`** — the events-detail response is
  the *reconcile* view: it merges disk-only NEW clips into the chapters and tags
  every clip with a status, so rebuilding a write body from it would adopt every
  NEW clip and drop `look`, `clips` and `ignore` on the floor. The response
  carries an `ETag` over the editorial state; there is no conditional `GET`.
- **`PUT /api/v1/events/{event_id}/reel`** saves an editorial write: the body is
  the *complete* desired editorial state (metadata, ordered chapters/clips,
  per-clip properties, `ignore`, `look`) and the server merges it onto the
  event's existing `reel.yaml` field by field, never replacing the file
  outright — a hand-authored file's comments and key order survive a GUI save
  unchanged apart from the lines that actually differ. Because the body is the
  *complete* state, an omitted field or section is a deletion, not "leave it
  alone" — a body without `ignore` clears the event's ignore list. A client
  must write back what it read, with its edit applied (the response echo is
  exactly that body), rather than a partial patch. The response echoes the
  persisted document plus the event's new staleness verdict, so no follow-up
  `GET` is needed. **Saving is not rendering**: the write never enqueues and
  never touches the render manifest — it only moves the fingerprint's
  editorial component, so the very next read reports `stale: editorial` and
  the existing `POST /api/v1/jobs` enqueues the re-render as usual. Failures
  answer by cause, and none writes anything: **400** is the request's fault —
  an invalid state (e.g. a dangling cross-reference), or one that would leave
  the event without a real date or title, or with a future date, which carries
  `failure: unusable_metadata` (the folder name still supplies what the body
  leaves unset); **404** is an unknown event; **412** is a lost race (below);
  **502** is the disk's fault — an existing `reel.yaml` that cannot be read
  (with the same `failure` kind the reads report, with or without `If-Match`),
  or a save the filesystem refuses, such as a read-only mount (the detail names
  the OS error). `reel.yaml` is replaced **atomically**: the new content goes to
  a hidden `.reel.yaml.<hex>.tmp` beside it, is synced, and is renamed over the
  original, so a failed save leaves the previous document intact. A leftover
  `.reel.yaml.*.tmp` holds a save that did not finish: if `reel.yaml` is
  missing, rename the leftover back to `reel.yaml`; otherwise delete it.
  Referencing a
  clip absent from disk is legal here — that is a MISSING clip for `scan` to
  report, never silently dropped. The write accepts an optional **`If-Match`**
  header carrying an `ETag` from the read above: a matching tag (or `*`) writes,
  a stale tag is `412 Precondition Failed` with `reel.yaml` byte-for-byte
  untouched, and an absent header stays unconditional (last-write-wins) exactly
  as before, so scripted `curl` clients are unaffected. The tag is canonical
  over the document's typed fields — the same hash the staleness fingerprint's
  editorial component uses — so a comment-only or reformatting edit never
  triggers a spurious 412. A **successful** write returns an `ETag` of its own,
  identifying the state it just persisted — the same value the read above would
  then give — so a client can chain conditional saves, using one write's tag as
  the next write's `If-Match`, with no read in between. A **412 carries no
  `ETag`**: recovery from a 412 is re-read, re-apply, retry, never a blind retry
  against a tag the service handed back.
- **Jobs lifecycle over REST** is a thin wrapper over the job store:
  `POST /api/v1/jobs` (gated like `enqueue` — 201 on a stale event, 409 on an
  active duplicate carrying the active job's id in `job_id`, 200
  `"status": "fresh"` with the fingerprint and manifest reference when the event
  is fresh and `force` is not set, 404 naming an unknown event in `event_id`),
  `GET /api/v1/jobs` / `GET /api/v1/jobs/{id}` (includes `force` and
  `fingerprint`), and `POST /api/v1/jobs/{id}/cancel` (same semantics as
  `jobs cancel`); both of the latter answer an unknown id with a 404 carrying it
  in `job_id`. The API never writes a job's `status` itself, and it reports the
  store's facts rather than predicting them: whether a job was created is decided
  by the insertion, so two requests racing for one event get one 201 and one 409
  naming the job the 201 created, never two 201s. A cancel answers the `outcome`
  the store applied — `flagged-running` (a running job's `cancel_requested` is
  set; the worker stops it between segments), `canceled-queued` or
  `no-op-terminal` — with the job's `status` after that same transaction, decided
  under a lock on the job's row, so a worker claiming the job at that moment can
  neither be mislabeled nor overwritten. A job's `event_dir` is the event's id: the
  value the events routes take and return as `event_id`, so a client matches jobs
  to events by equality. **Breaking (wire):** the 409 and the jobs 404s used to
  carry the job id in an untyped `id` field; it is now the typed `job_id`, and
  `id` is gone.
  **Output collisions:** `POST /api/v1/jobs` refuses an event whose output path
  another event of the served project also claims — the rule `render`, `enqueue`
  and `adopt-renders` apply (D-9), comparing paths case-insensitively and after
  Unicode normalization, over every event the layout walks (an event that fails on
  its own claims no path). The refusal is a 409 whose `conflict` is
  `output_collision`, whose `claimed_by` lists the other claimants' event ids, and
  whose detail names the shared path and the fix: a distinct title or location in
  `reel.yaml`. It is checked before anything else, so neither `force` nor a fresh
  event's 200 overrides it, and nothing is written. Every 409 of
  `POST /api/v1/jobs` carries `conflict` — `active_job` on the active duplicate —
  so a client tells the two apart from the type alone. A project walk that fails
  is the events list's scan-failure 502, and nothing is enqueued.
  **One project:** the service serves its configured project root, and its jobs
  views follow it: `GET /api/v1/jobs`, `GET /api/v1/jobs/{id}`, cancel and
  `WS /api/v1/ws/jobs` cover only the jobs enqueued for that root. Another
  project's job — one database commonly holds several — answers 404 exactly like
  an unknown id, and a cancel never touches it. `auto-reel jobs list|show|cancel`
  and the worker stay database-wide: the queue is shared, and a worker claims any
  project's job.
  `GET /api/v1/events/{event_id}` includes the same staleness verdict (`stale` +
  `reasons`) `scan` prints, computed read-only — a GET never writes a manifest.
- **`WS /api/v1/ws/jobs`** pushes live job progress. Every frame is
  `{"type": "snapshot" | "delta", "jobs": [...]}`, with jobs in the shape the jobs
  routes return; the schema publishes it as `WsMessage`, although no HTTP path
  describes the WebSocket. A subscriber gets a full snapshot of active
  (`queued`/`running`) jobs on connect, then deltas (progress changes, status
  transitions including terminal, and a cancel request on a running job) from a
  single central poller that queries the store roughly once per
  `api.poll_interval` — and only while at least one subscriber is connected. A
  connected subscriber receives every terminal transition exactly once, even for
  a job that was enqueued, claimed and ended between two polls. A job that ended
  while the subscriber was disconnected is not replayed: after a reconnect's
  snapshot, a client re-reads the jobs it was tracking (`GET /api/v1/jobs/{id}`).
  A subscriber that falls behind (a full outbound queue) is disconnected rather
  than back-pressuring the poller; it reconnects and resyncs via a fresh snapshot.
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

The render canvas defaults to 1920×1080 at the highest frame rate among the event's
clips; clip order never decides it, and portrait or 4K clips are fitted into it.
Set `look.target_resolution` / `look.fps` in one event's `reel.yaml` to override the
canvas for that event only.

`sort` sets the order clips enter an event's `reel.yaml`: when it is first seeded, and
when NEW clips are adopted. The default, `datetime`, orders by file modification time,
oldest first, as auto-reel did; equal times fall back to the filename order. It reads
only `stat`, never probes. `filename` is natural and case-insensitive (`clip2` before
`clip10`, `img_4863` before `IMG_4933`). `reverse: true` flips either. Chapters keep
their order (root clips first, then subfolders by name). An order already in a
`reel.yaml` is never re-sorted: NEW clips are appended after a chapter's existing
clips, in rule order among themselves. Change an existing order by editing `reel.yaml`.

An event's `reel.yaml` may set its own `sort`, which overrides `config.yaml` for clips
entering that event. It also accepts `custom`, which is per event only: clips named in
`custom_order` (file name → position) come first by position, then every other clip in
`filename` order; `reverse` flips the whole list. A malformed `sort` fails that event
loud.

```yaml
# <event>/reel.yaml
version: 0
sort:
  method: custom              # datetime | filename | custom
  reverse: false
  custom_order: {P1110550.MP4: 1, S1600003.MP4: 2}
```

```yaml
# config.yaml
layout: year-event        # ingest layout name
input: media              # walk root, relative to the project root (optional)
output: ../out            # output directory (optional; default <parent>/<root-name>-output)
sort:                     # order clips enter a reel.yaml (seed + NEW-clip adoption)
  method: datetime            # datetime (file mtime, default) | filename (natural, case-insensitive)
  reverse: false              # flip the order
look:                     # opaque defaults passed to resolve() as look_defaults
  target_resolution: [1920, 1080]   # canvas [width, height] (default 1920x1080)
  # fps: 25                         # pin the frame rate (default: highest clip fps)
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

### Web client

The browser client lives in `web/` (React + Vite + TypeScript, D-8). Its Node
toolchain runs in **podman** — nothing is installed on the host — and it is needed
only to *build* the client: `auto-reel serve` mounts `web/dist` when it exists and
runs unchanged when it does not, so tests and dev runs never require a build. Build,
dev-server and type-regeneration commands are in [`web/README.md`](web/README.md).

To provision a database by hand (dev default is
`postgresql+psycopg://auto_reel_ng:auto_reel_ng@localhost:5432/auto_reel_ng`, overridden
by `DATABASE_URL` or `config.yaml`'s `database.url` — see
`auto_reel_ng/persistence/config.py`):

```bash
DATABASE_URL=postgresql+psycopg://... alembic upgrade head
```
