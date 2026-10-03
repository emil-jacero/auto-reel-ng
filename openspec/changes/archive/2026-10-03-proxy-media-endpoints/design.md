## Context

See proposal.md for the motivation. State on main (8fb4d16), and what the gates add before this change is applied:

- `api/routes/media.py` registers `get_clip_media` and `get_movie` (each stacked `@router.head` over `@router.get`)
  and maps errors by cause. `api/media.py` holds the lookup (`clip_media`, `movie_media`), `open_media` (stat,
  `S_ISREG`, open once, so an unreadable file is a 502 before a status line), `MediaFile` (`etag` = size and
  `st_mtime_ns` in hex) and `media_response` (304 by `If-None-Match` / `If-Modified-Since`, else a
  `FileResponse` that answers `Range` and `If-Range`).
- `events_read.listed_clip` is the one "a clip of this event" rule the thumbnail and the clip route share;
  `thumbnail_source` is its cache-shaped sibling: listed clip, then `config.yaml`, then a cache path computed
  from `stat` alone, nothing generated.
- **Gates (merged before this change is applied; read from the plan, pinned by task 1.1):** `proxy-encode`
  creates `auto_reel_ng/proxies` with a settings resolver (`proxies.cache_dir`, default
  `$XDG_CACHE_HOME/auto-reel/proxies/`, refused inside the library), the cache key (resolved clip path, size,
  `mtime_ns`, `PROXY_VERSION`, settings hash; the encoder path is not in it), the entry directory
  `<cache_dir>/<key>/` holding `proxy.mp4`, `facts.json` and, from `filmstrip-sprites`, `filmstrip.jpg`, and the
  atomic finalize: the whole entry is built in a hidden sibling directory `.<key>.<uuid>.part`, verified, and
  renamed to `<key>` as one directory, so an entry directory that exists holds a finished `proxy.mp4`; the sprite
  is renamed into the existing entry later. `filmstrip-sprites` gives a clip of one second or less **one tile**
  (merged: no sub-second skip), so a short clip has a filmstrip too. D-21 lands in the HLD with `proxy-encode`.
- The router carries the single authentication hook (D-A8), so the new routes pass it like the clip route.

## Goals / Non-Goals

**Goals:**
- A `<video src>` plays a clip's proxy, and an `<img src>` shows its filmstrip, through URLs built from the event
  id and the clip identity alone, with byte ranges, validators and `HEAD`.
- The same trust boundary as the clip route: nothing from the request is joined onto a path; the cache path
  comes from the key of a clip discovery listed.
- Absent is unmistakable to a client and to a browser's media element: a 404 problem, never bytes.

**Non-Goals:**
- Anything that decides whether a proxy should exist or makes one (`proxy-job`, `proxy-enqueue-endpoint`).
- Proxy state in the events read model (`proxy-state-read`).
- Faster lookups than the clip route's (design Risks).

## Research & Decisions

### 1. Two routes on the media router, not one route with a `kind`

**Context**: The plan names `…/proxy` and `…/filmstrip`; one is `video/mp4`, the other `image/jpeg`.
**Explored**: One route with `?kind=proxy|filmstrip`; two routes sharing one lookup; the thumbnail route's
shape (a JPEG route beside the clip route).
**Decision**: Two paths, `…/proxy` and `…/filmstrip`, each `GET` and `HEAD`, in `api/routes/media.py` beside
the clip route. `app.py` already includes that router before the events router, because the event detail's
`{event_id:path}` is greedy; `/proxy` and `/filmstrip` are tried first for the same reason. `proxy-enqueue-endpoint`'s
`POST …/proxies` does not collide: Starlette matches the whole path suffix, and `proxies` is not `proxy`.
**Rationale**: OpenAPI publishes a content type per operation; one route would publish a union and make
`openapi-typescript` emit `video/mp4 | image/jpeg` for both. The cost is the event folder literally named
`proxy` or `filmstrip` being shadowed on the detail route, which `media`, `movie`, `reel` and `thumbnail`
already do (event folders are `yyyy-mm-dd - Title`).

### 2. Reuse `open_media` and `media_response`; the only new thing on `MediaFile` is a declared type

**Context**: `MediaFile.media_type` is looked up by extension in `MEDIA_TYPES`, and a test pins that table's keys
to discovery's video extensions. A filmstrip is `.jpg`; a proxy is `.mp4`.
**Explored**: Add `.jpg` to `MEDIA_TYPES` (breaks the pinned equality and the "a video extension table" meaning);
a second table for cache files; an optional declared type.
**Decision**: `open_media(path, *, label, media_type: Optional[str] = None)`; `MediaFile` gains
`declared_type`, and `media_type` returns it when set. `proxy_media` passes `video/mp4`, `filmstrip_media`
passes `image/jpeg`. The clip and movie paths pass nothing and are byte-for-byte unchanged. The `ETag`
(size and `st_mtime_ns` of the cache file), `Last-Modified`, `Cache-Control` and the `Content-Disposition`
(the cache file's own name: `proxy.mp4`, `filmstrip.jpg`) come from the shared code.
**Rationale**: The type is a property of what the cache holds, not of a clip's extension (a `.mov` source has an
`.mp4` proxy). Nothing else in the response differs.

### 3. The lookup mirrors `thumbnail_source`: `events_read.proxy_source`

**Context**: The route must find the entry without generating, probing or trusting the request.
**Decision**: In order, so each outcome has one answer:
1. `listed_clip(settings, event_id, clip)`: the event must be one the list shows (`EventNotFoundError`), the
   listing must succeed (`EventReadError`, `unreadable_disk`), the identity must be exactly one listed
   (`ClipNotFoundError`). `reel.yaml` is never read.
2. `load_project_config(project_root)` then the `proxies` settings resolver (`ConfigError`), as
   `thumbnail_source` does for the thumbnail.
3. The entry directory from the key of the clip **as it is now**: `os.stat` following links (a symlinked clip's
   size and mtime are its target's, as for the thumbnail and the clip route). An `OSError` from that stat
   propagates, as it does from `thumbnail_source` before its caller wraps it.
4. `ProxySource(clip_path, entry_dir, proxy_path, filmstrip_path)` is returned, with nothing opened.
`proxy_media` / `filmstrip_media` (in `api/media.py`, which imports `events_read`, so there is no cycle) call
`proxy_source` and translate: a `FileNotFoundError` from the clip's stat is `MediaGoneError` (404), another
`OSError` is `MediaReadError` (502). They then call `open_media` on `proxy_path` / `filmstrip_path` and turn a
`MediaGoneError` (no such file, or not a regular file) into `ProxyAbsentError(label, what)`, `what` being
`proxy` or `filmstrip`, which the route answers 404. A missing cache directory is `FileNotFoundError` at the
same `stat`, so "never prepared" and "no cache directory yet" are the same 404. `ENOTDIR` on a component of
the path is likewise absent; `EACCES` and the like stay `MediaReadError`.
**Rationale**: One lookup rule per kind of per-clip read, so a clip the thumbnail serves is a clip the proxy
serves. If `proxy-state-read` merged first and already added a function that maps a listed clip to its entry
directory, `proxy_source` calls it instead of computing a second key (one place defines the key; task 1.1
checks).
**Layering**: `api/` importing `proxies/` is downward (Principle VI), as it imports `thumbs/`. `proxies/` is
not changed.

### 4. Absent is 404, not 202 or a placeholder

**Context**: `proxies.md` §4 sketched a 200/202 route with progress. The brief locks "absent = problem body
(404), never 200".
**Explored**: 202 with `{state, progress}`; 200 with the original; 404.
**Decision**: 404 with a problem body naming the event and the clip. The detail says what is absent ("no
proxy" or "no filmstrip") without a cache path. No `ETag` and no `Cache-Control` (the rule for every media 404
and 502).
**Rationale**: A media element cannot use a 202, and a 200 with the original would be silently wrong in exactly
the case the proxy exists for (a PCM clip silent in Firefox, a HEVC clip black). State and progress already
have homes: `proxy.state` in the event detail and the job's frames over the WebSocket. A 404 is the one answer a
client cannot mistake for a proxy.

### 5. "Ready" is "present under its final name"; the route does not read `facts.json`

**Context**: D-21's finalize builds the entry in a hidden `.<key>.<uuid>.part` directory, verifies, then renames the
whole directory to `<key>`. `filmstrip.jpg` is renamed into the finished entry by a later step.
**Decision**: The proxy route serves `proxy.mp4` when it is a regular file, the filmstrip route serves
`filmstrip.jpg` when it is. A partly written entry lives in a hidden `.part` directory outside any key and is never opened. The routes do not read
`facts.json` and do not check that the filmstrip's proxy exists.
**Rationale**: The rename is the commit point (Principle IV), so existence is the whole contract and the routes
stay stat-only. A proxy with no sprite (a sprite step that has not run yet or failed) is a proxy 200 and a
filmstrip 404, which the client treats as "no strip, use the thumbnail". Task 1.1 confirms that the entry is
renamed into place only after verification; if the merged `proxy-encode` finalizes another way, stop and report
(it would change this rule).

### 6. `v` is ignored by the server and carries the `ETag`; `Cache-Control` stays `private, no-cache`

**Context**: D-15: Chrome fails to play a replaced file at an address that served the old one. A cache entry
is keyed by the source file's identity, so a new source gets a new entry and a new URL by itself, but a forced
re-encode (or a `PROXY_VERSION`-independent rebuild after a prune) writes a different `proxy.mp4` at the **same**
key.
**Decision**: The routes accept `v` and ignore it, as the clip and movie routes do. The route's `ETag` is the
proxy file's size and `st_mtime_ns`, so it changes with every re-encode; `HEAD` returns it without a body. A
client builds `…/proxy?clip=…&v=<ETag>` (`clip-preview-proxy`, `timeline-view`). `Cache-Control` is the shared
`private, no-cache`, not `immutable`.
**Rationale**: `immutable` would pin the replaced file in a browser that never revalidates, which is the failure
`v` exists to avoid, and the saving is only a 304 per element. Revalidation is a stat.

### 7. Failures by cause

| Situation | Status | Body |
|---|---|---|
| unknown event, unlisted identity, MISSING / outside / `original/` / year folder | 404 | problem, `event_id` |
| listed clip gone before its stat; no proxy or no filmstrip; a directory at the file's name | 404 | problem, `event_id` |
| event folder cannot be listed | 502 | problem, `failure: unreadable_disk` |
| unknown ingest layout; invalid `config.yaml` or `proxies.cache_dir` | 502 | problem, no kind |
| cache file exists but cannot be statted or opened (permission, dead drive) | 502 | problem, no kind, path-free |

Every 502 is logged at WARNING with the event and the clip. A 502 for a cache file names the clip identity and
the operating system's reason, never the cache path. `config.yaml` is read on every request, as for the
thumbnail. A `ConfigError` is not remembered: the next request reads it again.

### 8. OpenAPI

`PROXY_RESPONSES` and `FILMSTRIP_RESPONSES` are `MEDIA_RESPONSES` with the 200 and 206 content replaced by
`video/mp4` and `image/jpeg` (both `format: binary`). The parameters are the clip route's (`clip` required, `v`
optional, `If-None-Match`, `If-Modified-Since`, `Range`, `If-Range`). Response codes are exactly 200, 206, 304,
400, 404, 416, 502 and 422; no 503.

### 9. Verification in real browsers

**Context**: The brief requires the Sony PCM proxy to play **with sound** in Chrome and Firefox >= 155, and its
first frame within 100 ms locally.
**Decision**: Playwright from the scratchpad. Chrome 154 in `localhost/playback-research:chrome` (channel
`chrome`); Firefox >= 155 in `localhost/pcm-audio-research:pw163` (the PCM research's image: Firefox 155.0; the
script prints `browser.version` and fails below 155). The page is same-origin with the service
(`/healthz`), so `createMediaElementSource` works. Sound is judged as the PCM research did: the element's
audio is tapped with an `AnalyserNode` over 3 s of playback and the peak must be > 0 (Firefox adds
`mozHasAudio`), with the **original** of the same clip as the control (Chrome peak > 0, Firefox
`mozHasAudio` false and peak 0: unchanged and out of scope). First frame is `performance.now()` at the `src`
assignment to the first `requestVideoFrameCallback`, on a fresh element, warm cache, median of 5.
**Rationale**: The proxies research could not judge Firefox audio on 132 (suspended `AudioContext`), and the
PCM research closed it on 155; this repeats the PCM measurement against the route rather than a static file.

## Risks / Trade-offs

- **[Gate surface assumed]** Names and layout of `proxies/` are read from the plan, not from merged code. →
  Task 1.1 pins them and stops the change if the entry layout or the finalize order differs from decision 5.
- **[One lookup per range request]** Each seek repeats `listed_event_dir`, `scan_event`, the config read and two
  `stat`s. The clip route measured p50 8.1 ms / p95 14.5 ms on a 400-clip event and 1.7 / 2.4 ms on an 11-clip
  event; the proxy adds a YAML read and a stat. A timeline scrub asks for many small ranges. → Task 5.1 measured
  the same 50 sequential `Range: bytes=0-0` requests: **p50 2.3 ms / p95 2.8 ms** on an 11-clip event and **p50 7.7 ms /
  p95 9.2 ms** on a 400-clip event (shared, busy host); the bar is below; the budget is the 100 ms first-frame bar (X2 in the
  synthesis: seek p90 <= 100 ms). A slow result is a follow-up for a lookup shared with `proxy-state-read`,
  not a change here.
- **[Two parallel changes may each add an entry lookup]** `proxy-state-read` reads the same cache. → Decision 3:
  whoever merges second reuses the first's function; task 1.1 greps for it.
- **[A proxy replaced while it streams]** The finalize is a rename, so an open stream keeps the old inode and
  the next request sees the new file and a new `ETag`. → Accepted, as for a re-rendered movie.
- **[Disk reads of the cache]** The cache is on the local disk, not the USB archive, so a seek is cheap; a
  stalled disk can hold worker threads as the clip route's can. → Accepted for v2.
- **[Firefox original stays silent]** Not changed; the proxy is the path. → Out of scope by lock.
- **[Entry exists, sprite missing]** A client sees proxy 200 and filmstrip 404. → Specified (decision 5) so the
  client falls back to the thumbnail without treating it as an error.

## Idempotency and failure behavior

Read-only: a repeat request, a `HEAD`, a restart of `serve` and a worker running a proxy job concurrently change
nothing here. A request never creates the cache directory or an entry. A killed `serve` leaves nothing behind.
No ffmpeg argument is emitted and no encoder path exists on these routes, so there is no CPU fallback to state.
A cache file that vanishes after the lookup is a 404; one that cannot be read is a 502 before a status line of
200 or 206 (`open_media`), never a response that breaks off.
