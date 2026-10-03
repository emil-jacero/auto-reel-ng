## Why

GUI v2's timeline, clip preview and movie-facing screens play a clip's **proxy**, not the clip (HLD §4.10, §6
phase 9, decision D-21's "Serving" and "Playback" rows). The reason is measured, not stylistic
(`research/v2/proxies.md` §3.1, §3.7; `synthesis.md` X4): a random seek in an original costs a median 78 to
1457 ms and a held scrub shows 1 to 12 frames/s, Chrome and Firefox show HEVC and legacy MPEG-4 clips as black
or error 4, and Firefox 155 plays **no** sound of the Sony XAVC clips' PCM audio (52 % of the archive's
footage), while every 540p proxy plays with picture and AAC sound in Chrome 154 and Firefox 155
(`pcm-audio.md`, decoded peaks 0.264 / 0.085 equal to Chrome).

`proxy-encode` and `filmstrip-sprites` (the gates) put a clip's `proxy.mp4`, `filmstrip.jpg` and `facts.json`
in a file cache outside the library (D-21, shaped like D-11's thumbnails). Nothing serves them yet. The v1
media route (`GET …/media?clip=`, `media-endpoints`) streams the **original** and is documented to leave a
PCM clip silent in Firefox; it cannot be pointed at the cache, because its lookup is "a clip discovery lists",
not "a file under a cache key".

This change is the serving half of D-21: two read-only routes that stream a clip's proxy and filmstrip with
the media routes' Range, `If-Range`, `ETag`, `HEAD` and conditional-request behavior, so a `<video>` and an
`<img>` can load them. Every web change after it (`clip-preview-proxy`, `timeline-view`) depends on it.

## What Changes

- **`GET` and `HEAD /api/v1/events/{event_id}/proxy?clip=<identity>[&v=]`** streams the clip's `proxy.mp4`
  (`video/mp4`) from the proxy cache, unchanged, under the shared media behavior of the requirement "Media files
  are streamed with ranges and validators" (the same `media_response`: `Range`, `If-Range`, strong `ETag`,
  `Last-Modified`, `Cache-Control: private, no-cache`, `If-None-Match`, `If-Modified-Since`, `HEAD`).
- **`GET` and `HEAD /api/v1/events/{event_id}/filmstrip?clip=<identity>[&v=]`** streams the clip's
  `filmstrip.jpg` (`image/jpeg`) the same way.
- **Same guard and auth as the clip route.** `clip` must be an identity discovery lists for an event the
  events list shows, matched exactly (the thumbnail's and the clip route's lookup, `listed_clip`); every request
  passes the single authentication hook; no database, no ffmpeg or ffprobe, no write, not even the cache
  directory.
- **Absent is a problem body, never a 200.** A clip with no finished proxy (never prepared, being written, made
  for an older version of the file or under another proxy version or settings, or, for the filmstrip, a clip
  whose sprite step has not run or failed) is a 404 problem body naming the event. There is no 202, no placeholder and no
  fall-back to the original: the client decides from the event detail's proxy state (`proxy-state-read`).
- **`v` is accepted and ignored by the server** (D-15). A client puts the route's `ETag` in `v` (read with a
  `HEAD`), so a proxy re-made at the same cache key gets a new URL and Chrome does not keep playing the old one.
- OpenAPI: both paths publish `get` and `head`, the parameters, the responses and the problem bodies;
  `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated. No client code changes.
- HLD (task 6.1): §4.9's media-routes paragraph, D-21's "Serving" row, D-15's `v` rule, §4.10 and §6 notes,
  README's API section, and the measured results in `docs/research/browser-playback.md`.

Rendered output: **unchanged**, no `RENDER_GRAPH_VERSION` bump (D-21: proxies are not a render input). Staleness
fingerprint inputs: **unchanged**; the proxy cache is not a staleness input. `reel.yaml` / `config.yaml` schema:
**unchanged** (`proxies.cache_dir` is `proxy-encode`'s key; this change only reads it). No Alembic migration, no
rescan. Affected package: **`api/`** (the generated `web/openapi.json` and `web/src/api/schema.d.ts` count with
it, Principle VIII). CLI: not touched; Principle V holds because the routes add no behavior the CLI cannot
reach: the files they stream are what `auto-reel proxies` writes, and the routes only shape a file response
(HLD §4.9). No new dependency.

## Non-goals

- No generation, no job and no enqueue: preparing proxies is `proxy-job` and `proxy-enqueue-endpoint`.
- No proxy state, facts or progress in a body: `proxy-state-read` puts `proxy {state, facts}` in the event
  detail. These routes answer bytes or a 404.
- No transcode, remux, HLS, `<audio>` sidecar or virtual remux of the original (locked: the original stays silent
  in Firefox; the proxy is the Firefox path).
- No change to the clip or movie routes, the thumbnail route or the media lookup; no `Cache-Control: immutable`
  (design decision 6); no cache eviction or `--prune` (D-21).
- No web client change beyond regenerated types: the screens that play the proxy are `clip-preview-proxy` and
  `timeline-view`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: two ADDED requirements, "Clip proxy endpoint" and "Clip filmstrip endpoint". They bind to the
  existing requirement "Media files are streamed with ranges and validators" by reference and state only what
  differs, so that requirement's text, and the clip and movie endpoints it governs, stay as they are.

## Impact

- `auto_reel_ng/api/events_read.py` (`ProxySource`, `proxy_source`), `auto_reel_ng/api/media.py` (a declared
  content type on `MediaFile`, `proxy_media`, `filmstrip_media`, `ProxyAbsentError`),
  `auto_reel_ng/api/routes/media.py` (two routes, four decorators, the published responses).
- Reads the `auto_reel_ng/proxies` package that `proxy-encode` creates (settings resolver, cache key, entry
  layout); nothing in `proxies/` changes.
- `web/openapi.json`, `web/src/api/schema.d.ts` (regenerated).
- `tests/test_api_proxy_media.py` (new), `tests/test_api_openapi.py`; `README.md`, `docs/high-level-design.md`,
  `docs/research/browser-playback.md`.
