## Supervisor decisions (2026-10-01)

- **Movie containment is lexical** (`os.path.abspath`, never `resolve()`), as decision "Which file is the movie"
  argues: accepted.
- **`bytes=5-4`** and the other ranges browsers never send get the framework's answer, which differs between
  Starlette versions; the test accepts every answer the spec allows (see "Implementation notes"): accepted.
- **`Cache-Control: private, no-cache` with a strong `ETag` and 304s**: accepted.
- **An un-adopted legacy movie is not served** until `auto-reel adopt-renders` records it: accepted. The README
  entry and §4.9's paragraph say so (tasks 5.1, 5.2).
- **A directory at the expected movie path** is answered as absent (404), never served. The spec's 404 list and a
  scenario say so, and tasks 2.1, 3.2 and 4.1 test it.
- **A `/` in a title** (`output_filename`, and `PUT …/reel` accepting it) is an engine follow-up, recorded under
  Open Questions. This change only guards against it.
- **Chrome's replaced-file failure** (a file replaced at an address that served the old one fails, even in a new
  element) goes into `docs/research/browser-playback.md` (task 5.1), and the screens' contract below follows it.
- **HLD §4.10:** this change owns the roadmap edit (the timeline editor v3 → v2, analysis review as timeline
  overlays). Whichever of this change, `cross-chapter-drag`, `movie-player-screen` and `clip-preview-screen` lands
  later re-reads §4.10 on `main` and keeps the others' lines.

## Context

See proposal.md, Why. These are the code facts that shape the approach. Line numbers are on `main` at
6656ebc.

- **The thumbnail route is the template.** `api/routes/events.py:308-378`:
  - it resolves the id with `events_read.listed_event_dir`, which accepts only ids the events list shows
    (`events_read.py:140-160`)
  - it lists the event with `event.discovery.scan_event` and requires an exact identity match before anything
    is joined onto a path (`thumbnail_source`, `events_read.py:536-578`)
  - it maps outcomes by cause: 404 `event_id`, 502 `failure: unreadable_disk`, 502 without a kind
  - it never touches the database
- **Route order.** The detail route `/events/{event_id:path}` is greedy and Starlette matches in registration
  order. Every suffix route (`/analysis`, `/reel`, `/thumbnail`) is therefore registered before it
  (`events.py:166`, `:184`, `:308` vs `:381`). In FastAPI 0.139 `include_router` adds the router as one nested
  entry (`_IncludedRouter`), so a router included before `events_router` in `app.py:118-120` is tried first as
  a whole.
- **Auth.** One `@app.middleware("http")` calls the `AuthChecker` for every request (`app.py:96-105`, D-A8,
  no-op in v1). There is no per-route auth, so a media route inherits whatever the hook does.
- **The render manifest.** It is `<event>/.auto-reel/cache/render-manifest.json` (`staleness/manifest.py`):
  - it records `output`, the bare file name the render wrote (`render/orchestrator.py:470-475`
    `output=output_path.name`; `adopt-renders` writes the same, `cli/commands.py:980`)
  - it records the fingerprint, its components, the engine identity and `written_at`
  - it records **no** duration, codec or chapter times
  - `read_manifest` returns `None` for anything unreadable (`:77-102`)
  - `recorded_output_path(recorded, expected)` places a recorded name by the naming rule, D-9 (`:105-122`)
- **The gate's view of "the movie".** `staleness/gate.py:70-108`:
  - `evaluate` reads the manifest. With none, the verdict is `no_manifest`.
  - The expected output path (`settings.output_dir / output_relpath(metadata)`, as `events_read.staleness_for`
    computes it at `:415-426`) counts as present when it `exists()`.
  - Otherwise `_absent_output_reason` cites `output_renamed` when the recorded name differs from the expected
    one, is a bare file name (not `""`, `.`, `..`, nor anything with a separator) and `is_file()` under
    `recorded_output_path`. Else it cites `output`.
- **The output name** is `[<YYYY-MM-DD> - ]<title>[ - <location>].mp4` (`orchestrator.py:111-134`). Titles are
  not checked for `/`, so a crafted `reel.yaml` title can name a path with `..` segments. The movie lookup
  guards against serving anything outside the output directory (decision "Which file is the movie").
- **`FileResponse`** in the installed Starlette 1.3.1 (`starlette/responses.py:296-460`):
  - It streams in 64 KiB chunks and supports a single range (206), multipart ranges, 416 (`Content-Range: bytes
    */N`, `:372`) and 400 for a malformed or non-`bytes` range (`:370`). Both answers are `PlainTextResponse`
    and are produced inside the response, after the route returned.
  - It handles `If-Range` against `self.headers["etag"]` / `["last-modified"]` (`_should_use_range`).
  - It sets `etag`, `last-modified` and `content-length` with **`setdefault`** (`:331-338`), so an `ETag` passed
    in `headers=` wins, and `If-Range` is then checked against it.
  - It does **not** evaluate `If-None-Match` or `If-Modified-Since`.
  - Without `stat_result=`, it stats inside `__call__` and raises `RuntimeError` for a missing file (a 500).
  - It opens the file only **after** `http.response.start` is sent (`:385-391`, `:404-408`). An unreadable
    file therefore breaks off a response whose 200 or 206 status line has already gone out.
  - With `media_type=None` it guesses from the host's `mimetypes` database.
- **Discovery's extensions** are a fixed set of 13 (`event/discovery.py:37-53`) matched case-insensitively
  (`:328-335`), and `is_file()` follows symlinks. The dev library's clips are symlinks into `DEST/clips/`.
- **The test client buffers.** `starlette.testclient` collects each body into a `BytesIO` before returning
  (`testclient.py:296-367`). A pytest test therefore cannot observe streaming memory, and that check runs
  against a real `serve` (task 6.1).
- **Size limits.** pylint's `max-returns = 8`, `max-args = 8` (`pyproject.toml:137-144`).

## Goals / Non-Goals

**Goals:**

- A `<video src>` can play, seek and revalidate any listed clip and the event's rendered movie. That includes
  the 76 % of files whose index sits at the end, and the 449 MB 4K50 clip.
- The movie the route serves is exactly the movie the staleness verdict talks about, by construction, not by a
  second copy of the rule.
- Each failure has one status by cause, in the house problem shape. Every response is published. Nothing is
  written, decoded or held in memory whole.

**Non-Goals:**

- Anything that changes bytes: transcoding, remuxing or proxies (§8.11, v2).
- Any client code, and any field in the events reads.

## Research & Decisions

### R0 and the spike behind this design

**Context**: The brief asked for playback facts before any spec (R0). This design adds a spike of the exact
routes.

**Explored**:
- **R0** (this session's scratchpad `research/playback.md`; landed as `docs/research/browser-playback.md` by task
  5.1):
  - the ffprobe survey of the archive's 5,670 MP4/MOV files
  - ten samples copied to `auto-reel-media/samples/`
  - a browser matrix in Chrome 154 (channel `chrome`), Firefox 132, WebKit 18.2 and Playwright's bundled
    Chromium 131
  - a render of a scratch event, and Starlette's Range behavior
- **The spike** (scratch only, `g-spec/media-endpoints/spike_app.py`). The real `create_app` against a dev
  library built by `scripts/make_dev_library.py`, with prototype `/media` and `/movie` routes inserted before
  the events router, served by uvicorn on 8195. It added an event `2024/2024-05-19 - Provklipp` of symlinks to
  every sample, and `Kväll, del 2/a+b & c #1.mp4`. It measured:
  - **curl:**
    - 200 and `Range` `0-99`, open-ended, suffix → 206 with exact `Content-Range`
    - past the end → 416 `bytes */9167671`, empty `text/plain` body; `Range: lines=0-1` → 400 `text/plain`
      "Only support bytes range"
    - `If-Range` with our `ETag` or the `Last-Modified` → 206; stale → 200
    - `If-None-Match` exact, `W/`, list, `*`, and with `Range` → 304; non-matching → 200
    - HEAD → 404 (fell through to the static mount of `web/dist`)
    - `Content-Disposition: inline; filename*=utf-8''a%2Bb%20%26%20c%20%231.mp4`
    - the zero-byte `trasig.mp4`: 200 with an empty body, and `bytes=0-` → 416 `bytes */0`
    - a `chmod 000` clip without a mapping → **500** (the case "open before answering" fixes)
  - **Movie lookups on the dev library:**

    | event | answer |
    |---|---|
    | Kalas, Midsommar | 200 |
    | Badutflykt (`clip_set`) | 200 |
    | Grillning (`output_renamed`) | 200 with the movie under its **old** name `2024-06-27 - Grillning med Grannar.mp4` |
    | `2024-07-14 - kalas` (no manifest, while **Kalas's movie sits at its expected path**) | 404 |
    | Sommarlov, Trasig, Blandat | 404 |
    | Omöjligt datum | 502 `EventMetadataError` |
    | `2024`, `…/original` | 404 |
  - **Chrome 154 (channel `chrome`, `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `playwright install
    chrome`), a page on the same origin:**
    - `<video>` from `/media` played the 1080p50 AAC clip, the Sony PCM clip (moov at the end) and the
      punctuated chapter clip: metadata, seek to 50 % in 22–83 ms, 1.96 s advanced in 2 s
    - the renamed movie played
    - the 404 movie and the zero-byte clip gave `MediaError` 4
    - every media request was a 206, and loading the `no-cache` movie again produced a **304** among its
      requests: Chrome revalidates with `If-None-Match`
  - **Memory:** the 449 MB clip downloaded whole in 0.62 s while serve's RSS stayed at 113 MB (sampled every
    50 ms). A client abort mid-stream left no traceback, and the next request answered 206.
  - **OpenAPI:** the publishing shape below, dumped and fed to the repo's `openapi-typescript`, generated
    `content: { "video/*": string }` for 200 and 206 and typed header parameters. `tsc --strict` passed.

**Decision**: The decisions below rest on these measurements. R0's facts that the screens need go into the
research note (task 5.1), and the consumer contract below.

**Rationale**: Every claim this design makes about Starlette, Chrome or the dev library was observed, not
assumed.

### Serve files unchanged; PCM audio is a v2 problem

**Context**: Fifty-two per cent of the archive's clips (every Sony XAVC `C####.MP4`) carry `pcm_s16be` audio. R0:
Chrome 154 and WebKit decode it; Firefox 132 plays the picture with no sound (`mozHasAudio === false`), and
raises no error. `canPlayType` returns `""` for PCM in Chrome even though Chrome plays it.

**Explored**:
- An on-request AAC remux (`-c:v copy -c:a aac`) streamed to the browser: it is a new engine path with a
  subprocess per request, and seeking a stream that is not a file needs either a full transcode before the
  first byte or fragmented MP4. It also needs the cache, concurrency pool and invalidation that §8.11's proxy
  work exists to design.
- Serving bytes unchanged and telling the user.

**Decision**: Both routes serve the file unchanged. The clip preview (`clip-preview-screen`) shows a note when
`mozHasAudio === false`, as R0 recommends. The PCM audio path becomes an item of §8.11, the research that opens
GUI v2 (task 5.2).

**Rationale**: A one-off remux built now would be thrown away by the proxy design. The failure is visible and
harmless: the picture plays. Chrome, the browser the GUI is verified in, plays the sound.

### Streaming: `FileResponse` with our own stat, opened once before answering

**Context**: Files run to hundreds of megabytes and browsers seek with byte ranges. `FileResponse` already does
ranges and `If-Range` correctly. Its weak points are a stat race (a 500) and an open after the status line.

**Explored**:
- A hand-written range streamer: more code to get wrong, and `FileResponse` already passes the spike.
- `FileResponse` as is: it stats and opens on its own.
- `FileResponse` with `stat_result=` from our own stat, after our own open and close.

**Decision**: `api/media.open_media(path, *, label)`:
1. stats the path, following symlinks: `FileNotFoundError` → `MediaGoneError`; another `OSError` →
   `MediaReadError(label, strerror)`
2. requires `S_ISREG`, else `MediaGoneError`
3. opens the file for reading and closes it: `FileNotFoundError` → `MediaGoneError`; another `OSError` →
   `MediaReadError`
4. returns `MediaFile(path, stat)`

The response passes that `stat_result`, so `FileResponse` never stats again.

```python
@dataclass(frozen=True)
class MediaFile:
    """A file a media route serves, statted and proven readable once."""

    path: Path                 # the clip as discovery listed it, or the movie file
    stat: os.stat_result       # os.stat, following symlinks: the target's size and mtime

    @property
    def name(self) -> str:     # Content-Disposition's file name
        return self.path.name

    @property
    def media_type(self) -> str:
        return MEDIA_TYPES.get(self.path.suffix.lower(), "application/octet-stream")

    @property
    def etag(self) -> str:     # strong: size and mtime_ns, hex
        return f'"{self.stat.st_size:x}-{self.stat.st_mtime_ns:x}"'
```

**Rationale**:
- **The open before answering** turns an unreadable file into a 502 problem before the status line. The spike
  showed the alternative: a 500 here, and a broken 200 when `FileResponse` opens it itself.
- **The open is cheap:** one `open()` and `close()`, no read.
- **A file that changes or vanishes between this open and `FileResponse`'s own** is a race no server can close.
  What is left of it is an aborted response, logged by uvicorn (Risks).
- **Memory:** the chunked read keeps memory flat (spike: 113 MB RSS before and during a 449 MB download), and no
  route code ever calls `read_bytes`.

### Validators and caching

**Context**: The thumbnail route answers with `Cache-Control: private, max-age=86400` and a `v` cache buster.
That suits about 400 small immutable images a page. A video is one file at a time, the movie is rewritten in
place by every render, and a browser's media cache stores **ranges** of a file.

**Explored**:
- `max-age=86400` plus `v`, as the thumbnail does. A clip replaced in place while the browser holds some of
  its ranges could splice old and new bytes unless every client sends `v`. The movie has no `mtime` in the
  event detail to send as `v`.
- Starlette's own `ETag`, an md5 of `str(st_mtime) + "-" + size`. Reproducing it to evaluate `If-None-Match`
  would copy a library's private formula.
- `private, no-cache` with our own strong `ETag` and a 304: the browser revalidates before reusing stored
  bytes, and the revalidation is a lookup plus a stat. The spike saw Chrome use it.

**Decision**:
- `ETag: "<size hex>-<mtime_ns hex>"` (strong). It is passed in `headers=`, where `setdefault` keeps it, so the
  `ETag` sent, the one `If-Range` is checked against and the one `If-None-Match` is compared with are the
  same string.
- `Cache-Control: private, no-cache` on 200, 206 and 304.
- `If-None-Match`, read from every header line (`request.headers.getlist`, as the thumbnail route does),
  is answered **304** under weak comparison, or `*` for any existing file. It is evaluated before
  `FileResponse` sees `Range`, as RFC 9110 orders preconditions before Range.
- `If-Modified-Since` is not evaluated.
- The weak-comparison test moves into one helper, `api/media.etag_matches(header, etag) -> bool` (no `*`
  rule). The media routes and the thumbnail route's `_revalidated` both call it; the thumbnail's own `*` rule
  stays in `_revalidated`, and its behavior and tests are unchanged.
- `v` is accepted and ignored on both routes, published like the thumbnail's.

```python
MEDIA_CACHE_CONTROL = "private, no-cache"

def etag_matches(header: str, etag: str) -> bool:
    """RFC 9110 weak comparison over a comma-separated ``If-None-Match`` value (no ``*`` rule)."""
    candidates = [c.strip() for c in header.split(",") if c.strip()]
    return any(c.removeprefix("W/") == etag for c in candidates)

def _revalidates(header: str, etag: str) -> bool:
    """``*`` matches any existing file: the route has already opened it."""
    return etag_matches(header, etag) or "*" in (c.strip() for c in header.split(","))

def media_response(media: MediaFile, if_none_match: Optional[str]) -> Response:
    headers = {"ETag": media.etag, "Cache-Control": MEDIA_CACHE_CONTROL}
    if if_none_match is not None and _revalidates(if_none_match, media.etag):
        return Response(status_code=304, headers=headers)
    return FileResponse(
        media.path,
        media_type=media.media_type,
        headers=headers,
        stat_result=media.stat,
        filename=media.name,
        content_disposition_type="inline",
    )
```

**Rationale**:
- `no-cache` never mixes two versions of a file, with or without `v`.
- The cost is one conditional request per reuse. On the service's localhost bind that is milliseconds: the
  spike's whole lookup was about 1 ms on the dev library.
- `mtime_ns` and size change on every rewrite a camera, a copy or a render makes. A same-size rewrite within the
  same nanosecond is not a real case.
- Hex keeps the tag short. Neither the tag nor the 304 needs the file's content, so no byte is read to answer a
  revalidation.

### Content-Type from a fixed table; Content-Disposition inline

**Decision**:
- `api/media.MEDIA_TYPES` maps every member of `event.discovery.VIDEO_EXTENSIONS`:

  | extensions | `Content-Type` |
  |---|---|
  | `.mp4`, `.m4v` | `video/mp4` |
  | `.mov` | `video/quicktime` |
  | `.mkv` | `video/x-matroska` |
  | `.webm` | `video/webm` |
  | `.avi` | `video/x-msvideo` |
  | `.mts`, `.m2ts` | `video/mp2t` |
  | `.mpg`, `.mpeg` | `video/mpeg` |
  | `.wmv` | `video/x-ms-wmv` |
  | `.3gp` | `video/3gpp` |
  | `.flv` | `video/x-flv` |

  A test asserts the key set equals `VIDEO_EXTENSIONS`, so a new discovery extension cannot ship without a
  type. `application/octet-stream` is the unreachable fallback for a movie name outside the set: renders and
  adoptions always name `.mp4`.
- `Content-Disposition: inline` with `filename=` the file's own name, which Starlette encodes RFC 5987-style
  when it is not plain ASCII.

**Rationale**:
- `mimetypes` reads the host's `/etc/mime.types`, so the same file could get different types on two hosts.
- `inline` keeps navigation and `<video>` playing in place. "Save video as…" and a fallback "open the file"
  link then get the clip's real name, not the URL's last segment (`media`/`movie`).

### The routes: a router of their own, included before the events router, sync

**Context**: The event id is a greedy `{event_id:path}`, and the clip identity may contain `/` (`Kvällen/…`), so
the identity is a query parameter, as on the thumbnail route.

**Decision**:
- `GET /api/v1/events/{event_id:path}/media?clip=<identity>[&v=]`, operation `get_clip_media`.
- `GET /api/v1/events/{event_id:path}/movie[?v=]`, operation `get_movie`.
- Both live in a new `api/routes/media.py` with `router = APIRouter(prefix="/api/v1", tags=["events"])`.
  `app.py` includes it **before** `events_router`, with a comment naming the greedy detail route.
- Both are plain `def`, so FastAPI runs the lookup in its threadpool. `FileResponse` then streams on the event
  loop, and anyio reads each chunk in a worker thread.
- `clip` is a required `Query` described like the thumbnail's.
- `_version`, `_if_none_match`, `_range` and `_if_range` are declared as unused `Query` / `Header` parameters
  (aliases `v`, `If-None-Match`, `Range`, `If-Range`), so the schema publishes them. The handler reads
  `If-None-Match` itself from every header line, and Starlette reads the other two.

**Rationale**:
- **A module of its own** keeps `routes/events.py` (494 lines) from growing, and keeps this change's routes out
  of the hunks `cross-chapter-drag` or a later events change touches.
- **The order** is asserted by a test: `/reel`, `/thumbnail` and the detail route keep answering as before,
  and `/media` and `/movie` are not swallowed by the detail route.
- **Sync, unlike the thumbnail route:** there is no gate to wait on, so nothing would hold a thread while
  idle. The lookup is a listing, a stat and an open: the same order of work as the sync detail route.
- **The shadowing trade-off is the existing one.** An event whose last path segment is literally `media` or
  `movie` has its detail shadowed, as with `/reel` and `/thumbnail`. No layout yields such a name: dated event
  folders start with a date.

### Which clips are served: the thumbnail's lookup, shared

**Decision**: `thumbnail_source`'s first three steps move into
`events_read.listed_clip(settings, event_id, clip) -> Path`:
- `listed_event_dir`
- `scan_event`, with an `OSError` from either becoming `EventReadError(..., UNREADABLE_DISK)`
- the exact identity match, else `ClipNotFoundError`

The function returns `event_dir / clip`. `thumbnail_source` calls it and is otherwise unchanged, and its tests
stay green. `api/media.clip_media(settings, event_id, clip)` is `open_media(listed_clip(...), label=clip)`.

**Rationale**: One rule for "a clip of this event" across both per-clip media reads. Discovery's rules are
reused, not restated, and nothing from the request touches a path before it matched a listed identity.
`reel.yaml` is not read: a clip's bytes are a fact of the file, not of the document.

### Which file is the movie: the gate's rule, made callable

**Context**: The brief asks for the movie "from the render manifest / expected output path". Read naively, those
two disagree, and the dev library shows where:
- **Grillning** was renamed: its expected file is absent and the manifest's file exists.
- **`2024-07-14 - kalas`** has no manifest, while its expected path holds **Kalas's** movie, because the output
  names collide case-only.

**Explored**:
- **The expected path whenever it is a file.** That serves Kalas's movie as kalas's, and serves an un-adopted
  legacy file as if auto-reel had rendered it.
- **The manifest's recorded name only.** That disagrees with the gate when the expected file exists under a
  name the manifest does not record, for example after a title was changed back.
- **Exactly what the gate counts.** A manifest is required; then the expected path, else the renamed file.

**Decision**: The gate's rule, as one function in `staleness/gate.py`, exported from `auto_reel_ng.staleness`:

```python
def rendered_output(event_dir: PathLike, output_path: PathLike) -> Optional[Path]:
    """The event's rendered movie as the gate counts it, or None.

    None without a readable manifest: no render record, no movie. Otherwise the
    expected output when it is a file, else the file the last render recorded under
    the event's old name (the ``output_renamed`` case). Reads the filesystem; never
    raises for a missing file.
    """
    manifest = read_manifest(event_dir)
    if manifest is None:
        return None
    expected = Path(output_path)
    if expected.is_file():
        return expected
    return _renamed_output(manifest, expected)


def _renamed_output(manifest: RenderManifest, expected: Path) -> Optional[Path]:
    """The recorded movie under its old name, when the gate would cite ``output_renamed``."""
    recorded = manifest.output
    if (
        recorded != expected.name
        and recorded not in _NOT_A_FILE_NAME
        and Path(recorded).name == recorded
    ):
        candidate = recorded_output_path(recorded, expected)
        if candidate.is_file():
            return candidate
    return None
```

`_absent_output_reason` becomes `OUTPUT_RENAMED if _renamed_output(manifest, expected) is not None else OUTPUT`.
That is the same predicate it evaluates today, so `tests/test_staleness_gate.py` stays green.

`api/media.movie_media(settings, event_id) -> MediaFile`:
1. Calls `events_read.listed_event_dir` (`EventNotFoundError`). An `OSError` becomes `EventReadError(...,
   UNREADABLE_DISK)`.
2. Reads the metadata as the enqueue's output claim does (`events_read._output_claim`): `load_event_document(event_dir,
   order=settings.clip_order)`, then `require_processable(..., today=date.today())`. A `ReelError` or
   `OSError` becomes `EventReadError` with `classify_event_failure(exc)`, so the 502 carries the kind and detail
   the event detail gives.
3. Takes `expected = settings.output_dir / output_relpath(document.metadata)`: the path `staleness_for` gives the
   gate.
4. Takes `movie = rendered_output(event_dir, expected)`. `None` → `MovieNotFoundError(event_id)`.
5. Checks containment **lexically**, else `MovieNotFoundError`:
   `Path(os.path.abspath(movie)).is_relative_to(os.path.abspath(settings.output_dir))`. `abspath` drops `.`
   and `..` segments without touching the filesystem. A title is request-writable through `PUT …/reel`, and
   neither the loader nor the naming rule refuses `/` in it (checked: `load_document` keeps
   `x/../../../outside`). The guard MUST therefore refuse any name that climbs out with `..`, before a file is
   opened.
6. Returns `open_media(movie, label=movie.name)`.

Why lexical rather than `resolve()`, which is `resolve_event_dir`'s rule for event ids:
- The threat is a **name**: a title, or a recorded name, that the request side can influence. Lexical
  normalization stops every such name.
- `resolve()` would also refuse a movie that a symbolic link inside the output directory places on another
  disk. One example is a `2024` year folder linked to a second drive. The gate counts that movie as present,
  so the player would be offered and then fail. Discovery follows such links for clips too.
- Escaping through a link needs a symlink planted inside the output directory, which takes write access to
  the disk. Nothing this service guards against has that.

**Rationale**:
- **The contract M2 needs falls out of it.** A movie exists exactly when the verdict cites neither `no_manifest`
  nor `output`, so the event page decides from data it already has. There are two edges besides a race:
  - a **directory** at the expected path: `evaluate` counts it with `exists()`, and the route needs a file
  - an expected path whose title climbs out with `..`: the gate stats it, and the route refuses it

  The route answers 404 for both. That is accepted (Risks) rather than changing a gate verdict in an API change.
- **Principle V:** the decision stays the engine's. The API only shapes the response.
- **A file at the expected path with no render record is not this event's movie.** It may be another event's,
  as kalas shows. `adopt-renders` is the documented way to claim a legacy movie: it refuses colliding claimants.

### Status by cause

**Decision**:

| Outcome | Status | Body |
|---|---|---|
| `EventNotFoundError` (an id the events list does not show as an event) | 404 | problem, `event_id` |
| `ClipNotFoundError` (identity not exactly one the listing holds) | 404 | problem, `event_id` |
| `MovieNotFoundError` (no render record, recorded movie gone, outside the output dir) | 404 | problem, `event_id`, detail `event '<id>' has no rendered movie` |
| `MediaGoneError` (vanished or not a regular file at the open) | 404 | problem, `event_id`, detail names the identity or file name |
| `EventReadError` (listing or walk `OSError`; for the movie also `reel.yaml` / metadata) | 502 | problem, `event_id`, `failure` as the detail gives it |
| `LayoutError` (unknown layout) | 502 | problem, `event_id`, no kind |
| `MediaReadError` (stat or open refused) | 502 | problem, `event_id`, no kind, detail `<identity or file name>: cannot read the file: <strerror>` |
| `If-None-Match` matches | 304 | no body; `ETag`, `Cache-Control` |
| no `Range` | 200 | file; headers above |
| one satisfiable range | 206 | bytes; plus `Content-Range` |
| range past the end | 416 | Starlette's: empty `text/plain`, `Content-Range: bytes */N` |
| malformed or non-`bytes` range | 400 | Starlette's: `text/plain` message |
| `clip` missing | 422 | FastAPI's validation body |
| anything else | 500 | a bug, not mapped |

Every 502 is logged at WARNING with the event, the identity or file name, and the detail, as the thumbnail
route logs. 404s are not logged. Problem bodies carry no `ETag` or `Cache-Control`.

**Rationale**:
- **No new vocabulary.** A media element cannot read a status or a problem body: a 404 and a 502 are both
  `MediaError` 4 to the page (spike). A kind would only serve curl users, and the detail already does that.
  The `failure` on the movie's 502 is the existing `EventFailure`, so the regenerated client types are
  unchanged.
- **A vanished file is a 404**, not the thumbnail's 502. Here nothing failed to *produce* anything: the file is
  simply not there any more.
- **Path-free details.** Clips are named by identity and movies by file name. The `EventReadError` detail stays
  exactly as the detail route words it (`str(exc)`, which for an unlistable folder includes its path), as the
  thumbnail change decided for consistency across the events reads.

### Publishing in OpenAPI

**Decision**: Both routes declare `response_class=Response` and one shared `MEDIA_RESPONSES`:

```python
_MEDIA_HEADERS = {   # ETag, Last-Modified, Cache-Control, Accept-Ranges, Content-Disposition
    "ETag": {"description": "Strong entity-tag: the file's size and mtime", "schema": {"type": "string"}},
    ...
}
_VIDEO = {"video/*": {"schema": {"type": "string", "format": "binary"}}}
MEDIA_RESPONSES = {
    200: {"description": "The whole file", "content": _VIDEO, "headers": _MEDIA_HEADERS},
    206: {"description": "One byte range of the file", "content": _VIDEO,
          "headers": {**_MEDIA_HEADERS, "Content-Range": {...}}},
    304: {"description": "Not modified: `If-None-Match` names the current file",
          "headers": {"ETag": ..., "Cache-Control": ...}},
    400: {"description": "A malformed `Range` header (plain text)"},
    404: {"model": ProblemOut},
    416: {"description": "The range starts past the end of the file", "headers": {"Content-Range": {...}}},
    502: {"model": ProblemOut},
}
```

`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated with `web/README.md`'s commands. `tsc` must
pass with no client change.

**Rationale**: The spike generated these types and they compiled. `video/*` is honest about a per-file type,
and the exact type is the response header's job.

### Auth parity

**Decision**: Nothing route-specific. A test registers an `AuthChecker` and shows that it runs once per request,
each range request included, and that a rejection reaches no file bytes. HLD §4.9 records that a future token
must be a cookie or a query parameter, because `<img>` and `<video>` cannot send `Authorization`.

**Rationale**: The middleware already sees every request (R0 §6). The only thing to guard is that a later
change does not give the media routes a different auth path.

### What the screens can rely on (the contract for M2 and M3)

Recorded here because M2 (`movie-player-screen`, D-15) and M3 (`clip-preview-screen`, D-16) are written
against this change:

- **URLs:**
  - `/api/v1/events/${encodeEventId(id)}/media?${new URLSearchParams({clip: identity, v: mtime})}`
  - `/api/v1/events/${encodeEventId(id)}/movie`
  - Use `route.ts`'s per-segment `encodeEventId`. `v` is optional on both.
  - A file rewritten in place must get a new address: Chrome fails a replaced file at an address that served the
    old one, even in a new element (`MediaError` 3; `movie-player-screen`'s spike). Clips: `v` = the detail's
    `mtime`. Movie: `v` = the `ETag` without quotes, read with a `GET` carrying `Range: bytes=0-0` and `cache:
    'no-store'` (a 206 with `ETag`, `Content-Range` and `Content-Disposition`).
- **Has a movie:** `!staleness.reasons.includes("no_manifest") && !staleness.reasons.includes("output")`. Then
  current = `!staleness.stale`. The movie may be the one under the event's old name (`output_renamed`).
- **Errors are invisible to the element.** 404, 502 and a zero-byte clip all surface as `MediaError` 4. HEVC and
  MPEG-4 part 2 raise no error at all in Chrome and Firefox, and show `videoWidth === 0` after `loadedmetadata`
  (R0 §3). A legacy MPEG-4 movie can become an event's movie through `adopt-renders`.
- **Loading cost:** `preload="metadata"` costs 3–4 requests per file. A list must not create `<video>`
  elements; create one when a preview opens (R0 §7).
- **PCM audio:** `mozHasAudio === false` in Firefox means no playable audio. There is no cross-browser check.
- **No chapter times** are available. A jump list is left out of v1. Chapter times in the render manifest and a
  movie version (size and mtime) in the event detail are v2 items beside the proxy work.
- **Edit mode (M3):** the clip route is a read of the clip's file, never of `reel.yaml`. It takes no `If-Match`,
  and a save neither changes a clip's bytes nor its `ETag`. So an open preview MUST NOT be closed or reloaded by
  a save in flight, a failed save, a draft or the pending lock (G1). A successful save leaves Edit mode, as
  today. Those rules govern the cut fields and the save bar, not the
  `<video>`.
- **No text tracks:** the files carry no subtitles, and the routes serve none. A player offers no captions
  control rather than an empty one.
- **Verification** MUST use Chrome (channel `chrome`, the image `localhost/playback-research:chrome` whose
  Containerfile `docs/research/browser-playback.md` gives) or Firefox. Playwright's bundled Chromium cannot decode
  H.264 (R0 §3), so a check run with it would look like a player bug.

### HLD: the roadmap edit and the media routes

**Decision** (task 5.2): `docs/high-level-design.md` gets:
- **§4.9**, after the thumbnail sentence: "The media routes (`GET /api/v1/events/{event_id}/media?clip=` and
  `/movie`, change `media-endpoints`) are, like the thumbnail, per-request media reads, not fields of the events
  read model. They stream the file on disk unchanged with byte ranges: no transcode, no probe. The movie is the
  file the staleness gate counts as the event's movie (`staleness.rendered_output`), so a legacy movie with no
  render record is not served until `auto-reel adopt-renders` records it. `<img>` and `<video>` send no
  `Authorization` header, so a future token is a cookie or a query parameter (D-A8)."
- **§4.10**, the roadmap edit (user decision, 2026-10-01):
  - The **v2** line becomes: the look/style editor (as now); **the full timeline editor, moved from v3**: a
    per-clip track with proxies, filmstrip, drag-trim in/out and scrub preview; **analysis review built as
    overlays on that timeline** (approve black/white/freeze trims in place, not a separate screen); and event
    poster frames; and, beside the proxy work, chapter times in the render manifest (a chapter list for the movie
    player) and a movie version in the event detail. Then: "v2 starts with a research step: §8.11 (proxies, the
    PCM-audio path) and the timeline library against D-8's dependency budget."
  - The **v3** line becomes: "nothing planned for the GUI: the timeline editor moved to v2 on 2026-10-01."
  - A dated sentence records the decision and that v1 gains the movie player and the clip preview (changes
    `movie-player-screen`, `clip-preview-screen`), whose one `api/` prerequisite is `media-endpoints`, as the
    thumbnail paragraph does for D-11.
  - "drag across chapters" is not carried into v2: `cross-chapter-drag` puts it in v1 (D-13).
- **§6:** phase 9 reads "GUI v2 (look editor + the full timeline editor, with analysis review as timeline
  overlays; starts with the §8.11 research)". Phase 10 reads "ML analysis (parallel, behind existing interfaces);
  GUI v3 has no planned scope since the timeline editor moved to v2".
- **v3 → v2 where the text means the timeline:** D-8's "Why React" ("the v3 timeline editor", "v3 is not
  reachable"), the §4.10 research note at about line 428, D-11's "Still open: proxies and scrubbing stay v3",
  and D-14's "Scrubbing, previews and drag-trim stay v3." The last becomes "Scrubbing, previews and drag-trim are
  not part of it: the timeline editor is v2 (§4.10, 2026-10-01)." M3 amends it again for previews (D-16).
- **§8.11:** "Still open (v3)" becomes "Still open (v2, the research that opens GUI v2)". It adds the PCM item
  ("52 % of the archive's clips carry PCM audio that Firefox does not play; the v1 media routes serve files
  unchanged") and the R0 facts that size the proxy work (76 % moov-at-end; HEVC only in `original/`), citing
  `docs/research/browser-playback.md`.
- **No new D-n.** D-15 and D-16 are reserved for M2 and M3. The media routes are §4.9 text, like the thumbnail
  route, and the roadmap edit is §4.10's own text, dated.

**Rationale**: A decision that outlives the change is folded back into the HLD (config.yaml design rule). The
roadmap lives in §4.10 and §6, and the v3 mentions elsewhere would contradict it if left.

## Failure behavior and idempotency

- **No writes anywhere.** Neither route writes into the library, the output directory or any cache. Neither runs
  a subprocess or touches the database.
- **Repeat requests** are idempotent: the same file gives the same bytes and the same `ETag`, and a matching
  `If-None-Match` is a 304 with no file read.
- **A render finishing during playback.**
  - The worker's atomic finalize `os.replace`s the movie. An in-flight response keeps reading the old inode it
    opened, so its bytes stay consistent.
  - The next request stats the new file, and its new `ETag` makes the browser's `no-cache` revalidation fetch
    the new bytes.
  - A range request that `If-Range`s against the old tag gets the whole new file (200), never a splice.
- **`--force`, worker restarts and the job queue** do not apply: nothing is enqueued.
- **A killed service** leaves nothing behind. The client retries the range.
- **No `RENDER_GRAPH_VERSION` bump** and no fingerprint change. The gate refactor keeps every verdict, which
  `tests/test_staleness_gate.py` asserts unchanged.

## Risks / Trade-offs

- **[A file swapped between the open check and `FileResponse`'s open]** The response then breaks off after its
  status line (a uvicorn ERROR log), or serves bytes whose `Content-Length` is the old stat's. → Accepted:
  the window is microseconds. The atomic finalize means a movie is replaced, never truncated, and an
  in-flight read keeps the old inode.
- **[One lookup per range request]** Each seek repeats `listed_event_dir` (a walk of one year folder) and
  `scan_event`. The spike measured about 1 ms on the dev library. The thumbnail change measured `scan_event` at
  5.8 ms for 400 clips. On the archive's FUSE NTFS drive it will be more, and is not measured here. → Accepted:
  a seek already reads megabytes from the same drive. Task 6.1 measures the 400-clip event. A slow result is a
  follow-up for a discovery-level membership check, as the thumbnail's Risks say.
  Measured (task 6.1, 50 sequential `Range: bytes=0-0` requests over curl on the dev library, warm cache):
  `2024-09-19 - Fyrahundra/f400.mp4` (400 clips) p50 8.1 ms, p95 14.5 ms; Provklipp's
  `h264-1080p25-aac.mp4` (11 clips) p50 1.7 ms, p95 2.4 ms. Not slow on a local disk: no follow-up from
  these numbers.
- **[Threads for slow reads]** anyio reads each 64 KiB chunk in a worker thread from the shared pool (40 by
  default). A stalled USB drive can hold a few threads per stalled stream. → Accepted for v1: one preview plays
  at a time, and the movie player is one element.
- **[400 and 416 are plain text]** They are Starlette's, produced after the route returned. A non-`bytes` unit
  answers 400 where RFC 9110 says to ignore the header. → Accepted and published: browsers send `bytes`
  only. A media element never shows a body.
- **[A directory at the expected movie path]** The gate counts it as present. The route answers 404. → Accepted;
  no real library has one. Changing the gate to `is_file()` would be a verdict change for another change.
- **[A movie rendered with `-o` elsewhere]** It is not the service's movie, and the staleness already says
  `output`. → Consistent with the detail. The service serves one output directory (`ApiSettings.output_dir`).
- **[Titles with `/`]** An output name with a separator puts the movie in a subfolder. The route still serves
  it if its lexically normalized path lies inside the output directory, and otherwise answers 404. The naming
  gap is the engine's (`output_filename`, and `PUT …/reel` accepts such a title), recorded as a follow-up, not
  fixed here.
- **[Symlinks out of the library]** A clip that is a symbolic link, or that sits in a symlinked chapter folder
  (discovery's `is_file()` / `is_dir()` follow links), is served from wherever it points. The dev library's
  clips are exactly that. → By design: the request can name only identities discovery listed, and a render
  and a thumbnail already read the same targets. The trust boundary is the library's filesystem, which only
  its owner writes. The movie follows links inside the output directory for the same reason (decision "Which
  file is the movie").
- **[Range values browsers never send]** These are Starlette's answers, measured on 1.3.1:
  - `bytes=5-4` (last byte = first byte − 1) is a 206 with an empty body and `Content-Range: bytes 5-4/N`.
  - A set holding one unsatisfiable range, such as `bytes=0-1,99999-`, is a 416 for the whole set, although RFC
    9110 would serve the satisfiable part.
  - A unit other than `bytes` is a 400, where RFC 9110 says to ignore the header.
  - Several ranges that do not overlap are one `multipart/byteranges` 206. Overlapping ones are merged first.

  → Accepted: none sends a byte outside the file or a 5xx, which is all the spec promises for them. The HTTP
  parser's header limit (h11's 16 KiB here; httptools is not installed) bounds the multipart set to a few
  thousand parts, so a multipart response stays small. A hand-written range parser to fix the empty 206 would be more code than the defect is worth.
  Task 4.1 tests them. Starlette 1.7.0 answers `bytes=5-4` with a plain-text 400 instead (see "Implementation
  notes"); the test accepts either answer, since the spec allows both.
- **[`no-cache` costs a round trip per reuse]** → Cheap on localhost, and the spike's Chrome made one 304 per
  reload. A wider bind or a slow link would favor `max-age` with `v`. That is a header change if ever needed.
- **[Event folders named `media` or `movie`]** Their detail is shadowed, as with `/reel` and `/thumbnail`. → The
  existing, documented trade-off. No layout yields those names for dated events.
- **[The `ETag` reveals size and mtime]** → The service already publishes both in the detail (`size`, `mtime`).

## Migration Plan

- Regenerate `web/openapi.json` and `web/src/api/schema.d.ts`. `tsc` passes with no client change. If a
  cherry-pick conflicts on them, take `main`'s and re-run the generator and the drift test. Never merge them
  by hand.
- No data migration and no rescan.
- Rollback: remove the router, `api/media.py`, `listed_clip` and `rendered_output` (the gate's inline check
  returns), then regenerate.

## Open Questions

None that change the specs, the approach or the tasks. Deferred, by design:
- The PCM audio path and proxies: §8.11, v2.
- Chapter times in the manifest, for a jump list, and a movie version in the event detail: v2, beside the proxy
  work (§4.10's v2 line, task 5.2).
- A `/` in a title: `output_filename` does not refuse it and `PUT …/reel` accepts it, so a movie can land in a
  subfolder. An engine follow-up; the lexical guard here keeps such a name inside the output directory.
- A discovery-level membership check if task 6.1's numbers are slow.

## Implementation notes (2026-10-01, accepted by the supervisor)

- **Starlette drift.** `pyproject.toml` pins only `fastapi>=0.139.0`, so a fresh `pip install -e .` resolves
  FastAPI 0.142.2 with Starlette 1.7.0, not the 1.3.1 this design measured. The one difference the tests see:
  1.7.0 refuses `bytes=5-4` (last byte = first byte − 1) with a plain-text 400 instead of 1.3.1's empty 206
  (`start >= end` in its range parser); it also answers more than 100 ranges with the whole file. **No new
  pin.** The test accepts every answer the spec allows for a range browsers never send (206, 400 or 416, no
  file byte), with a comment naming both versions. The media, OpenAPI and thumbnail tests pass on the
  pinned 1.3.1 venv and on a freshly resolved 1.7.0 venv. The implementing venv was pinned to the main
  checkout's versions (FastAPI 0.139.0, Starlette 1.3.1, uvicorn 0.51.0) so task 1.1's baseline holds.
  More than 100 ranges are a 206 on 1.3.1 and a 200 with the whole file on 1.7.0 (`max_ranges`); the spec's
  "any other `Range` value" bullet allows 200 (the header ignored, as RFC 9110 permits), and a 101-range
  case in the test accepts 200 or 206.
- **`starlette>=1.0` is declared** in `pyproject.toml`. It is not a new dependency: FastAPI already brings it,
  and `api/` imports it directly (`FileResponse`, `run_in_threadpool`). FastAPI 0.139 accepts Starlette from
  0.46, but releases before 1.0 send the 416 as `Content-Range: */<size>` with no unit, which breaks the
  spec's 416 scenarios; 1.0 is the first release that sends `bytes */<size>`.
- **Problem bodies.** A 502 from an unreadable file or an unknown layout carries no `failure` key at all, as
  the thumbnail route's kindless 502s do; a 502 from an event read carries `failure`. A client reads the
  field as absent either way.
- **`MediaGoneError(label, reason)`.** The 404 detail is `<identity or file name>: no such file` or `…: not a
  regular file`, path-free like `MediaReadError`'s.
- **HLD §4.10's v3 line and §6 phase 10:** `cross-chapter-drag` landed on `main` first, putting dragging
  across chapters in v1, so this change's v3 line and phase 10 say GUI v3 has no planned scope (task 5.2's
  "if it has archived" branch, applied when the PR branch was rebuilt on that `main`).
- **The revalidation check runs without `page.route`.** Playwright's routing disables the browser's HTTP
  cache, so a routed page never shows Chrome's `If-None-Match` 304s. The check loads `/healthz` (no script
  of its own) and asserts through `page.on("request")` that only GETs were sent; the playback check, which
  needs no cache, aborts every non-GET with a route. Recorded in `docs/research/browser-playback.md` for the
  screens' verifications.
- **Tests beyond the task list:** an unknown layout answers 502 with no kind on both routes (a spec
  requirement the tasks did not list), a broken `reel.yaml` does not stop a clip over HTTP, and
  `Last-Modified` follows a symlinked clip's target.
