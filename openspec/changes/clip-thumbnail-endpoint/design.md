## Context

See proposal.md, Why. These are the code facts that shape the approach:

- **Route order.** `api/routes/events.py` registers `/events/{event_id:path}/analysis` and
  `/events/{event_id:path}/reel` before the greedy `/events/{event_id:path}` detail route. Starlette
  matches routes in registration order, so a suffix route declared after the detail route would be
  swallowed by it. Every events route is a sync `def`, which FastAPI runs in the shared AnyIO threadpool.
- **Existing helpers.**
  - `events_read.resolve_event_dir` rejects unknown ids and `..` escapes with `EventNotFoundError`.
  - `event/discovery.scan_event(event_dir)` is the disk listing. It covers root clips and one level of
    chapter folders, skips `original/` and `.reelignore` folders, and its identities are the
    event-relative POSIX paths that the detail's `ClipOut.identity` carries.
  - Every non-MISSING clip the detail shows is in that listing. `_build_chapters` places every listing
    identity either in a document chapter or as an appended NEW clip, and IGNORED is a reconcile
    classification of a disk clip. A MISSING clip is exactly one the document names and the listing
    lacks.
- **Problems.** `problem.py` builds problem JSON, and `ProblemOut` publishes its fields. `failure` is typed
  `EventFailure`, the API's classification of engine errors (`unparseable_reel_yaml`, `unusable_metadata`,
  `unreadable_disk`). The web client depends on that exact type:
  - `EventDetail.tsx` assigns `problem.failure` to an `EventFailure` field
  - `labels.ts` has an exhaustive `Record<EventFailure, string>`
- **Schema publishing.** `api/openapi.py` dumps the schema offline (no database contacted), and
  `tests/test_api_openapi.py` asserts it equals the committed `web/openapi.json`. A spike in the scratchpad
  (FastAPI 0.139) showed how a binary route publishes: `response_class=Response` plus
  `responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}},
  "headers": …}}` publishes a 200 with `image/jpeg` content only, and a 304 entry publishes as a
  description with headers.
- **App state.** `app.py` builds per-app state in `create_app` (`jobs_hub`, `runtime`) and never at import
  time. `create_app` only builds a lazy database engine. A route that never touches the job store works
  with Postgres down.
- **Discovery lists only what it could stat.** `_video_identities` keeps an entry only when
  `path.is_file()` is true. That follows symlinks and is false for a dangling link or an entry that cannot
  be statted, so a listed clip can fail its stat only if it changes between the listing and the stat.
- **The engine seam, from `clip-thumbnails` (package `auto_reel_ng/thumbs/`), which this change is gated
  on.** The names and signatures are as its design states them:
  - `errors.ThumbnailError` names the clip and why it cannot give a thumbnail: a clip that cannot be
    statted, a probe failure (a zero-byte clip is refused by `probe_media` as "File is empty" before
    ffprobe runs), no usable duration, or ffmpeg failing or producing no frame
  - `errors.ThumbnailCacheError` names a cache directory that cannot be created or written, or a rename
    that fails. It is not a property of the clip. The two classes are **siblings** under `EngineError`,
    so `except ThumbnailError` never catches a cache failure
  - `thumbnail_for(clip_path, *, position, cache_dir, runtime=None) -> Path` returns the cached JPEG,
    generating it when absent (cache-first: an existing `<key>.jpg` is returned with no subprocess), and
    writes atomically
  - `thumbnail_path(clip_path, *, position, cache_dir) -> Path` gives the same path without creating or
    generating anything: a stat plus a sha256. The stat's `OSError` propagates unchanged
    (`FileNotFoundError` for a vanished clip); callers handle it
  - `resolve_thumbnail_settings(config, project_root) -> ThumbnailSettings` (`position`, `cache_dir`)
    validates the `thumbnails` map of `ProjectConfig`, raising `ConfigError` naming `thumbnails.<key>`.
    It refuses a `cache_dir` inside the project root or its `input` directory, the default included
  - `auto_reel_ng.thumbs` exports `thumbnail_for`, `thumbnail_path`, `resolve_thumbnail_settings` and
    `ThumbnailSettings`
  - the cache key is a sha256 over (resolved path, size, mtime_ns, position, box, `THUMBNAIL_VERSION`);
    the file is `<cache_dir>/<key>.jpg`. The key does not include the ffmpeg build
  - the config keys are `thumbnails.position` (0 < p < 1, default 0.25) and `thumbnails.cache_dir`
    (default `$XDG_CACHE_HOME/auto-reel/thumbnails/`)
  - measured cost (its design): a probe plus an extraction is about 0.5 s per 1080p50 fixture clip on
    local disk, and a JPEG is about 15 KB
- **The dev library shares clip files.** `scripts/make_dev_library.py` symlinks every clip from
  `DEST/clips/`, which holds only the four fixture cuts and `trasig.mp4`. The key follows symlinks, so
  the whole dev library has five distinct cache keys, and requests for `s1710001.mp4` in different events
  share one thumbnail.

## Goals / Non-Goals

**Goals:**

- A page of thumbnails is cheap on a warm cache and bounded on a cold one. Every revalidation is a
  `config.yaml` read, a listing of the event folder, a `stat` and a hash, never a subprocess.
- Each failure has one status by cause, in the house problem shape, and every response is published.
- Nothing is written into the library, and the route works while the database is down.

**Non-Goals:**

- Engine behavior: the frame position, scaling, the cache layout and key. All of it is `clip-thumbnails`'.
- A second extraction path in `api/`. The route only calls the engine.

## Research & Decisions

### The route: a query parameter, registered before the detail route, `async`

**Context**: The event id is a greedy `{event_id:path}` and the clip identity can contain `/`
(`Kvällen/s1710002.mp4`). Two greedy path parameters cannot be split unambiguously.

**Explored**: The existing suffix routes (`/analysis`, `/reel`) and their order comment. A
`/events/{event_id:path}/clips/{clip:path}/thumbnail` shape was considered. The regex split is
ambiguous whenever a chapter folder is named `clips`, which the fixture `2024-07-04 - Barbecue`
already has.

**Decision**: `GET /api/v1/events/{event_id:path}/thumbnail?clip=<identity>`. It is registered
directly after `/reel` and before the detail route, with a comment pointing at the `/analysis`
rationale. `clip` is a required `Query` with a description ("the clip's identity as the event detail
lists it: its event-relative path"). A missing `clip` is FastAPI's own 422. `v` is an optional string
`Query` ("an opaque cache-busting version; accepted and ignored"), declared as `_version: Optional[str]
= Query(None, alias="v", …)` so the schema publishes it and the handler, which never reads it, passes
pylint. The route is an `async def` with `response_class=Response`. It pushes every blocking step to the
threadpool explicitly, with `starlette.concurrency.run_in_threadpool`.

**Rationale**:
- The query parameter keeps the one greedy parameter the other events routes have. The client already
  holds both values: `event_id` from the list and `identity` from the detail.
- **Why `async`:** a sync route would hold a threadpool worker while it waits for an extraction slot. The
  pool is shared with every other route, so a page of cold thumbnails would starve `GET /events` and the
  jobs routes. An `async` route waits on an `asyncio` primitive, which holds no thread. Review spike
  (uvicorn 0.51, Starlette 1.3.1, the app's `@app.middleware("http")`): with two 1.5 s extractions running
  and four requests waiting, a sync route answered in 8 ms.
- **The `clip` value on the wire** is a percent-decoded query value. The client encodes it as a query
  value (T3 uses `URLSearchParams`), and it arrives exactly as the detail listed it: in the spike,
  `Kv%C3%A4ll%2C%202%2Fx%20%26%20y%20%231.mp4` arrived as `Kväll, 2/x & y #1.mp4`. As in any
  form-encoded query, a literal `+` arrives as a space, so `a+b.mp4` sent unencoded is looked up as
  `a b.mp4` and answers 404. The event id keeps the client's per-segment path encoding (`route.ts`
  `encodeEventId`).
- **HEAD** is not added: FastAPI registers GET only, so `HEAD` answers 405 (spike).
- **Why a published `v`.** The URL otherwise names the clip, not its version, so a browser holding a
  fresh copy would not ask again within `max-age` after the clip is replaced on disk. The screen appends
  the clip's `mtime` from the event detail as `v`, so a replaced clip gets a new URL. Publishing `v`
  lets the screen type it from the schema. The server ignores the value, so the lookup, the key, the
  `ETag` and the status stay a function of the event, the clip and the cache alone.

### Which clips have a thumbnail: the event's disk listing

**Context**: The brief's rule is: 404 for a clip that is not in the event's listing, MISSING clips
included. The detail's clip list comes from the document plus the disk listing, and it needs the job
store for `latest_job`.

**Explored**:
- `events_read.get_event`: loads `reel.yaml`, requires processable metadata, and reads the job store
- `scan_event`: disk only
- joining `event_dir / clip` and checking that it exists: that would accept `original/` debris and any
  path the discovery rules exclude, and it has to defend against traversal by itself

**Decision**: a new `events_read.thumbnail_source(settings, event_id, clip) -> ThumbnailSource`. In this
order, so each outcome has one answer:
1. It resolves the event (`EventNotFoundError`).
2. It lists it with `scan_event`. An `OSError` there becomes `EventReadError(..., failure=UNREADABLE_DISK)`
   via `classify_event_failure`.
3. A clip whose identity is not exactly one of `listing.identities` raises the new `ClipNotFoundError`.
   The match is an exact string comparison: no path normalization (`Kvällen/../s1710001.mp4` is not a
   listed identity) and no Unicode normalization (a folder whose name is stored decomposed on disk is
   listed, and matched, decomposed).
4. It resolves the settings: `resolve_thumbnail_settings(load_project_config(settings.project_root),
   settings.project_root)`, which raises `ConfigError`.
5. It computes `thumbnail_path(event_dir / clip, position=..., cache_dir=...)`. An `OSError` from its
   stat (the listed clip can no longer be statted) is re-raised as
   `ThumbnailError(f"{clip_path}: cannot stat the clip: {exc}")` from `exc`: the wording `thumbnail_for`
   gives the same case.

`reel.yaml` is not read.

```python
@dataclass(frozen=True)
class ThumbnailSource:
    clip_path: Path       # event_dir / clip, for a clip the listing holds
    position: float       # ThumbnailSettings.position, resolved per request
    cache_dir: Path       # ThumbnailSettings.cache_dir, resolved per request
    cache_path: Path      # clip-thumbnails' no-generation path: <cache_dir>/<key>.jpg

    @property
    def etag(self) -> str:
        return f'"{self.cache_path.stem}"'   # the cache key, quoted: a strong entity-tag
```

**Rationale**:
- The set of accepted identities is exactly the detail's non-MISSING clips, IGNORED included (the screen
  dims them but still shows them). Discovery's rules are reused, not restated.
- Nothing from the request is joined onto a path before it has matched a listed identity, so `..` or
  absolute paths are simply "not in the listing".
- **The order** makes an unknown event or an unlisted clip a 404 even when `config.yaml` is broken, and
  parses `config.yaml` only for a request that can be answered.
- **A listed clip whose stat fails.** `thumbnail_path` lets the `OSError` through (its own CLI relies on
  that), so `thumbnail_source` wraps it in the `ThumbnailError` wording `thumbnail_for` uses for "a clip
  that cannot be statted". Discovery lists only entries it could stat, so this is the race of a clip
  removed or replaced between the listing and the stat. It is answered like any other clip that cannot
  give a thumbnail (502 `thumbnail_failed`, detail naming the clip), whatever the `errno`: one answer for
  the race, not a 404 for one `OSError` subtype.
- **Why not read `reel.yaml`:** a thumbnail is a fact of the clip file, not of the editorial model.
  Reading `reel.yaml` would turn a broken `reel.yaml` into a thumbnail failure and cost a parse per image.
  An event whose detail fails shows no clip rows, so the screen never asks for its thumbnails anyway.
- **The listing is one `scan_event` per request.** That is a read of the event folder and of each chapter
  folder, with a stat per entry. Review measurement: for a 400-clip event on tmpfs, the whole warm lookup
  (config, listing, stat, hash, reading the JPEG) was 5.3 ms, and `scan_event` alone was 4.6 ms. That is
  accepted (see Risks).

### What this change needs from `clip-thumbnails`

**Context**: The 304 path and the cached fast path need the key and the cache location *without*
generating. `thumbnail_for` alone would extract on a cold cache even for a request that ends in 304.

**Decision**: this change calls five things from `clip-thumbnails`, by the names its design states:
- `ThumbnailError`
- `ThumbnailCacheError` (a sibling of `ThumbnailError`, not a subclass)
- `thumbnail_for(clip_path, *, position, cache_dir, runtime=...) -> Path`. The route passes
  `app.state.runtime`, the service's one resolved ffmpeg, so a request never re-resolves the binaries.
- `thumbnail_path(clip_path, *, position, cache_dir) -> Path`: the pure path function (stat plus hash, no
  subprocess, nothing created). The stat's `OSError` propagates unchanged, and `thumbnail_source` wraps
  it
- `resolve_thumbnail_settings(load_project_config(settings.project_root), settings.project_root)`: a
  `ThumbnailSettings` with the validated position and cache directory, raising `ConfigError`

All but the errors are imported from `auto_reel_ng.thumbs`, with `ThumbnailSettings`. Task 1.1 confirms
the archived signatures and adapts the calls to them if they moved. The behavior does not change. If the
pure path function is gone, or it no longer lets the `OSError` through, the gate task stops and reports:
that belongs to the engine change, not to `api/`.

**Rationale**: the key is the engine's own (Principle V). The API never recomputes or copies it, so the
`ETag`, the CLI's cache and the file on disk cannot disagree.

### Validators and caching headers

**Context**: A page of thumbnails is re-fetched on every visit. Clips are camera files that do not change,
and the cache key already covers size, mtime, position, box and version.

**Decision**:
- **200:** `Content-Type: image/jpeg`, `ETag: "<key>"` (strong), `Cache-Control: private, max-age=86400`.
  The body is the cached file's bytes, read in the threadpool. At about 15 KB, reading it whole is simpler
  than `FileResponse`, which would add its own `ETag` and `Last-Modified`. On a hit, `<key>` is
  `source.cache_path.stem`. On a miss it is the stem of the path `thumbnail_for` returned, not the key
  computed before extraction: a clip that changes mid-request must not get the old key's strong tag.
- **304:** the same `ETag` and `Cache-Control`, no body. It is answered when `If-None-Match` matches under
  RFC 9110's **weak** comparison: a `W/` prefix is ignored, and a comma-separated list is accepted. `*`
  matches only when the JPEG is already cached, because only then does a current representation exist. The
  304 is decided *before* any extraction, from `thumbnail_source` alone.
- **Problem responses** carry no caching headers, so a later request retries.

**Rationale**: `private` keeps shared caches out of the archive's pictures. `max-age=86400` stops re-requests
within a day, and the strong `ETag` makes revalidation after that a stat plus a hash. A changed clip, a
changed `thumbnails.position` or a bumped `THUMBNAIL_VERSION` changes the key, so the old tag no longer
matches.

### Bounded, shared extraction: `api/thumbnails.ThumbnailGate`

**Context**: The brief sets at most 2 concurrent extractions per process, and concurrent requests for the
same key share one.

**Explored**:
- A `threading.BoundedSemaphore` plus a dict of `concurrent.futures.Future` in a sync route: every waiter
  would hold a threadpool worker.
- `asyncio.Semaphore` plus a dict of `asyncio.Task`: waiting costs no thread.
- Putting the limit in the engine: the CLI already bounds itself with `thumbs --jobs N`, and the limit is
  a property of serving, not of extracting.

**Decision**: one gate per app, built in `create_app` next to `jobs_hub` and held on
`app.state.thumbnail_gate`. The limit is the module constant `MAX_CONCURRENT_EXTRACTIONS = 2`, not a
config key.

```python
class ThumbnailGate:
    """At most ``limit`` extractions at once; one shared extraction per cache key."""

    def __init__(self, limit: int = MAX_CONCURRENT_EXTRACTIONS) -> None:
        self._slots = asyncio.Semaphore(limit)
        self._in_flight: dict[str, asyncio.Task[Path]] = {}

    async def produce(self, key: str, extract: Callable[[], Path]) -> Path:
        task = self._in_flight.get(key)
        if task is None:
            task = asyncio.create_task(self._run(extract))
            self._in_flight[key] = task
            task.add_done_callback(partial(self._settled, key))
        # asyncio.wait never cancels what it waits on: a cancelled waiter leaves the shared
        # extraction running. Not asyncio.shield: see "Cancelled waiters" below.
        await asyncio.wait((task,))
        return task.result()

    async def _run(self, extract: Callable[[], Path]) -> Path:
        async with self._slots:
            return await run_in_threadpool(extract)

    def _settled(self, key: str, task: asyncio.Task[Path]) -> None:
        if self._in_flight.get(key) is task:
            del self._in_flight[key]
        if not task.cancelled():
            task.exception()   # mark it retrieved: no "never retrieved" warning when every waiter left
```

The route reads the cached file first (fast path) and uses the gate only on a miss:

```python
body = await run_in_threadpool(_read_if_present, source.cache_path)   # bytes | None
etag = source.etag
if body is None:
    path = await gate.produce(source.cache_path.stem, partial(
        thumbnail_for, source.clip_path, position=source.position, cache_dir=source.cache_dir,
        runtime=request.app.state.runtime))
    body = await run_in_threadpool(path.read_bytes)
    etag = f'"{path.stem}"'   # the key of the bytes served, not the one computed before extraction
```

**Rationale**:
- **Cached reads skip the queue.** A cached thumbnail never waits behind two slow extractions.
- **One extraction per key.** The in-flight map is keyed by the engine's cache key, so "the same
  thumbnail" means exactly what the cache means by it.
- **Cancelled waiters.** A waiter that is cancelled never cancels the shared extraction, and the other
  waiters still get its result. Review spike (uvicorn 0.51, Starlette 1.3.1, with the app's
  `@app.middleware("http")`): a client that disconnects mid-extraction does **not** cancel the handler,
  which runs to completion. The guarantee still matters for any cancellation that does reach a waiter:
  server shutdown, or a future timeout middleware. The thread cannot be interrupted anyway, and
  `clip-thumbnails`' atomic write means a finished extraction is simply a cache hit next time. React
  StrictMode's double mount and fast scrolling are covered the same way: a repeated request shares the
  in-flight extraction, and an aborted one leaves it running.
- **Why not `asyncio.shield`.** On Python 3.14, when a shielded waiter is cancelled before the inner task
  finishes, `shield` attaches its own callback to the inner task. That callback reports any exception
  through the loop's exception handler ("… exception in shielded future", logged at ERROR with a
  traceback), even though `_settled` retrieves it. The spike reproduced it: one ERROR traceback for each
  abandoned request on a clip that fails, such as `trasig.mp4`. `asyncio.wait` gives the same
  cancellation behavior without that log (spike: no log, the same results).
- **Failures.** A failed extraction fails every request that shared it, with the same 502, and leaves the
  map, so the next request retries.
- **Race with a concurrent CLI run.** A cache file that appears between the fast-path miss and the gate is
  harmless: `thumbnail_for` is cache-first. Such a request may still wait for a slot before
  `thumbnail_for` returns the file without a subprocess. That is accepted: its thumbnail was not cached
  when it arrived.
- **Symlinked clips** in several events share one key, and therefore one extraction.
- **Event loops.** `asyncio.Semaphore` binds to a loop only when a caller has to wait. Production has one
  loop. Tests of contention drive the gate directly under one loop, and each route test builds its own
  app, so no gate outlives the `TestClient` loop it waited in.

### The failure kind's home: `api/schemas.ThumbnailFailure`

**Context**: The brief fixes the value `thumbnail_failed` and leaves the enum's home to this change: "the
layer that owns the vocabulary".

**Explored**:
- **An engine-owned enum in `clip-thumbnails`, like `CancelOutcome` in `persistence/`.** The store
  *computes* a cancel outcome. The engine's thumbnail vocabulary is the exception type
  `ThumbnailError`, and the classification into a wire kind is the API's, exactly as `EventFailure`
  classifies `ReelError`, `EventMetadataError` and `OSError`.
- **Adding `thumbnail_failed` to `EventFailure`.** That would break `tsc`: `labels.ts`' exhaustive
  `Record<EventFailure, string>` would miss a key. It would also put a value that never describes an event
  into the list's error-row type.
- **Widening `ProblemOut.failure` to `EventFailure | ThumbnailFailure`.** That would break `tsc` too:
  `EventDetail.tsx` assigns `problem.failure` to an `EventFailure`.

**Decision**: `class ThumbnailFailure(StrEnum): THUMBNAIL_FAILED = "thumbnail_failed"` lives in
`api/schemas.py`, published as a component. `ProblemOut` gains `thumbnail_failure:
Optional[ThumbnailFailure] = None`. `clip-thumbnails` defines no enum.

**Rationale**:
- The API owns the classification of engine errors into wire kinds; `EventFailure` and `EnqueueConflict`
  are the precedents.
- A separate field leaves every existing client type untouched, so the regenerated types compile with no
  client change.
- A one-value set is still a closed set. A later kind (for example telling an undecodable clip from one
  too short to seek into) becomes a client build error, not a silent new string.

### Status by cause

**Decision**: the route maps outcomes as follows. Nothing is written into the library in any case.

| Outcome | Status | Problem fields |
|---|---|---|
| `EventNotFoundError` | 404 | `event_id` |
| `ClipNotFoundError` (the identity is not exactly one the listing holds) | 404 | `event_id` |
| Listing the event folder fails (`OSError`, classified as `EventReadError`) | 502 | `event_id`, `failure: unreadable_disk` |
| `ConfigError` loading `config.yaml` or resolving `thumbnails.*` | 502 | `event_id`, detail names the config problem |
| `ThumbnailError` from `thumbnail_source` (the listed clip can no longer be statted: `thumbnail_path`'s `OSError`, wrapped) or from `thumbnail_for` | 502 | `event_id`, `thumbnail_failure: thumbnail_failed`, detail = the `ThumbnailError` message |
| `ThumbnailCacheError` from `thumbnail_for` (a sibling class, caught on its own) | 502 | `event_id`, detail = the engine message naming the cache directory |
| `OSError` reading the cached JPEG (the cache directory) | 502 | `event_id`, detail names the OS error and the cache directory |
| Anything else | 500 (a bug, not mapped) | |

Every 502 is also logged at WARNING with the event, the clip and the detail, as the editorial write logs
its refused save. An extraction whose waiters have all gone logs nothing: no request is left to answer.

**Rationale**:
- **No 503.** The route needs no database, and extraction is local. "The cache directory cannot be
  written" is a misconfiguration answered like the editorial save's refused write: a 502 naming the OS
  error, with no kind.
- A kind describes the *clip's* failure, and a cache failure is not the clip's.
- A `ConfigError` is answered, not left as a 500. That is stricter than the detail route, which lets it
  escape today (a follow-up, not this change's).

### Configuration is read per request

**Decision**: `thumbnail_source` resolves `thumbnails.position` and `thumbnails.cache_dir` from the project
`config.yaml` on every request, through `clip-thumbnails`' resolver.

**Rationale**: D-A3 (a config edit is visible on the next request) and the precedent of
`project_look_defaults`. The cost is one small YAML parse per image, beside the directory listing the
request already does.

## Failure behavior and idempotency

- **No library writes.** The route never writes into the library: no `reel.yaml`, no manifest, no sidecar.
  Its only write is `clip-thumbnails`' atomic cache write, outside the library.
- **A killed service** mid-extraction leaves no partial cache file, because the write is atomic
  (`clip-thumbnails`). The next request extracts again.
- **Repeat requests** are idempotent. A cached thumbnail is served byte-for-byte the same with the same
  `ETag`. A revalidation with a matching tag is a 304 without extraction.
- **Failed clips are retried.** A failed extraction is not remembered, so a repeated request for
  `2024-10-05 - Trasig/trasig.mp4` tries again and answers the same 502. The probe refuses the empty
  file before ffprobe runs, so a retry of that clip costs a stat, not a subprocess. Negative caching is a
  non-goal.
- **Clips with no frame at the position.** A clip too short to hold a frame at `position × duration`
  answers 502 `thumbnail_failed`, as D-11's single attempt requires. Review check with `clip-thumbnails`'
  exact command: a one-frame clip (0.034 s) at 0.25 exits 234 with no frame, while a three-frame clip
  (0.1 s) gives one. Portrait (360×640 → 101×180), 640×360 (→ 320×180) and 3840×2160 (→ 320×180, 237 ms)
  clips all give a JPEG.
- **Worker and render interplay:** none. The route neither enqueues nor reads jobs. `--force` does not
  apply.
- **No `RENDER_GRAPH_VERSION` bump**, and no fingerprint change.

## Risks / Trade-offs

- **[One event listing per image]** An event with N clips costs one `scan_event` of N entries per
  thumbnail request, so a fully scrolled page costs N² stats. Measured on tmpfs, that is 4.6 ms per
  request for a 400-clip event. On the NTFS USB archive it is FUSE readdirs and stats, which are not
  measured. → Accepted: `loading="lazy"` limits requests to the rows near the viewport, the browser sends
  at most six at once, and `max-age` means a thumbnail is requested once a day, not once per visit. Task
  4.1 measures a warm burst against a 400-clip event. If it is slow, the follow-up is a discovery-level
  membership check in `event/`, not an `api/` re-implementation of the discovery rules.
- **[A cold page fills slowly]** At about 0.5 s per 1080p50 clip (`clip-thumbnails`' measurement) and two
  slots, the ~30 rows a browser loads lazily on a cold cache take about 8 s on local disk, and longer from
  the USB drive. → That is the bound working as intended. `auto-reel thumbs` pre-fills the cache
  overnight.
- **[A replaced clip under an unchanged URL]** A client that sends no `v` keeps a browser copy for up to a
  day after the clip is replaced. → Decided: the published `v` parameter. The screen sends the clip's
  `mtime` as `v`, so a replaced clip gets a new URL on the page's next read; `Cache-Control: private,
  max-age=86400` stays.
- **[A hung ffmpeg holds a slot indefinitely]** No layer has a timeout. `FfmpegRuntime.run` calls
  `subprocess.run` without one, and `clip-thumbnails` adds none. An extraction stuck on a stalled USB drive
  therefore holds its slot until the process exits. One stuck extraction leaves one lane. Two stuck
  extractions stop every uncached thumbnail: those requests wait instead of failing. Cached thumbnails,
  304s and every other route keep answering, because the waits hold no thread. → Accepted for v1. The
  recovery is to restart `serve`, which the same stalled drive would force anyway. A timeout is a
  follow-up in `ffmpeg/` after measuring extraction on the MOL drive (`clip-thumbnails`' Risks, "No
  extraction timeout"): an optional `timeout` on `FfmpegRuntime.run` raising `FfmpegError`, which
  `thumbnail_for` already turns into a `ThumbnailError`. This route adds none around a thread it cannot
  interrupt.
- **[A cache failure is not the clip's]** `ThumbnailCacheError` stays a sibling of `ThumbnailError`. →
  Accepted: it answers 502 with no thumbnail kind, so a kind only ever describes the clip.
- **[A service-wide 502 looks like many clip failures on the page]** An unwritable cache or a bad
  `config.yaml` fails every uncached thumbnail with the same 502. → Accepted for v1: the screen shows "No
  preview" in every box, and the cause is in each problem detail and in `auto-reel thumbs`.
- **[Unbounded waiters]** Requests waiting for a slot are not capped. → A browser opens about 6
  connections per origin, and the service binds `127.0.0.1` by default (api-service). Adding a cap is a
  follow-up if a real client needs one.
- **[Event folders named `thumbnail`]** As with `/reel` and `/analysis`, the detail of an event whose last
  path segment is literally `thumbnail` is shadowed by this route. → This is the existing, documented
  trade-off of greedy suffix routes. No archive folder is named that.
- **[The `ETag` exposes the cache key]** The tag is a sha256 over the resolved path, size and mtime.
  → It reveals nothing a client of this localhost service cannot already read, and a hash is not
  reversible in practice.
- **[A strong tag across an ffmpeg upgrade]** The key does not include the ffmpeg build. After an upgrade,
  a thumbnail regenerated into an emptied cache may differ in bytes under the same strong tag. →
  Harmless here. The route evaluates only `If-None-Match`, which uses weak comparison, and serves no
  `Range`, so no client ever combines bytes from two generations. A change that alters the picture bumps
  `THUMBNAIL_VERSION` (`clip-thumbnails`), which changes the tag.

## Migration Plan

- Regenerate `web/openapi.json` and `web/src/api/schema.d.ts`. `tsc` must pass with no client change.
- No data migration. The thumbnail cache is created on demand by the engine.
- Rollback means removing the route, the gate, the enum and the problem field, and regenerating.

## Open Questions

None. The extraction timeout is settled under Risks ("A hung ffmpeg holds a slot indefinitely").
