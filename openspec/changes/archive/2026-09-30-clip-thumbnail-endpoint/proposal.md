## Why

On 2026-09-30 the operator asked for clip thumbnails: "add thumbnails to the clips — not the first frame but
some percentage into the clip". A camera filename like `s1710003.mp4` says nothing about what the clip
shows, and the reorder view of GUI v1 (slice D, HLD §4.10) is where that hurts. Pulling clip thumbnails
from v2 into v1 is locked as **D-11** (HLD §7, recorded by `clip-thumbnails`). This is **HLD §6 phase 8
(GUI v1)**. §8.11's proxy/thumbnail research item is narrowed by `clip-thumbnails` to single-frame clip
thumbnails; proxies and scrubbing stay v3, and this change depends on nothing else from it.

`clip-thumbnails` adds the engine operation and its CLI (`auto-reel thumbs`). It extracts one JPEG at
`thumbnails.position × duration`, fitted to 320×180, and caches it outside the library. A browser cannot
call the engine. As with every earlier screen, the API contract lands first and on its own, so the screen
(`clip-thumbnails-screen`) stays a pure `web/` change (Principle VIII). This change is that contract: one
read endpoint that serves a clip's thumbnail.

The endpoint has to hold up under a real page. An event page shows one image per clip, so opening a
40-clip event on a cold cache asks for 40 extractions at once. Each one is an ffmpeg process reading from
the archive's USB NTFS drive (HLD §2: the legacy tool had no resource bounds and fell over on real
libraries). The endpoint therefore bounds extraction concurrency, shares one extraction between concurrent
requests for the same clip, and lets the browser revalidate for free, so a return visit costs no ffmpeg
at all.

## What Changes

- **`GET /api/v1/events/{event_id}/thumbnail?clip=<identity>`** serves one clip's thumbnail. The clip
  identity is a **query** parameter because two greedy path parameters cannot be told apart. The route is
  registered before the greedy detail route, like `/reel` and `/analysis`.
  - **200 `image/jpeg`:** the cached thumbnail, generated through the engine on a cache miss. It carries
    a strong `ETag` (the engine's cache key of the file served) and `Cache-Control: private,
    max-age=86400`.
  - **An optional `v` query parameter** for cache busting: an opaque string the server accepts and
    ignores. It never affects the lookup, the key, the `ETag` or the status. The screen sends the clip's
    `mtime` from the event detail as `v`, so a clip replaced on disk gets a new URL instead of a day-old
    browser copy.
  - **304:** `If-None-Match` matches the current key. Nothing is extracted and no body is sent.
  - **404 problem:** an unknown event, or a clip that is not on disk in that event: a MISSING clip,
    `original/` debris, or anything outside the event.
  - **502 problem, by cause:**
    - the engine could not produce a thumbnail (for example an empty clip, or no frame at the position):
      the new closed failure kind `thumbnail_failure: thumbnail_failed`
    - the event folder cannot be listed: `failure: unreadable_disk`, as the detail reports it
    - the cache cannot be read or written, or the project `config.yaml` is invalid: a detail naming the
      error, with no kind
- **Bounded, shared extraction.** At most **2** extractions run at once per service process. Concurrent
  requests for the same cache key share one extraction. A cached thumbnail is served without waiting for
  a slot. All disk and ffmpeg work runs off the event loop.
- **No database.** The route reads disk and the thumbnail cache only, so it answers while Postgres is
  down, and it declares no 503.
- **The failure kind is a closed, published vocabulary:** `ThumbnailFailure` (`thumbnail_failed`) and
  the problem field `thumbnail_failure`. It follows `EventFailure`: an API classification of an engine
  error.
- **Every response is published in OpenAPI:** 200 (`image/jpeg`, with the `ETag` and `Cache-Control`
  headers), 304, 404, 502. `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated. **No client
  code reads them yet.**
- **The events list and detail are unchanged.** They gain no field and stay probe-free. The client builds
  the thumbnail URL from the event id, the clip identity and the clip's `mtime` it already has.

## Non-goals

- **Anything in the engine or CLI.** Extraction, the cache, its key, `THUMBNAIL_VERSION`, the config keys
  and `auto-reel thumbs` all belong to `clip-thumbnails`.
- **The screen** (`clip-thumbnails-screen`).
- **A thumbnail URL or flag in the list or detail JSON.** HLD §4.9's probe-free read model stays as it is.
- **Negative caching.** A clip whose extraction failed is retried on the next request, not remembered as
  failed.
- **Other image work:** a batch or prefetch endpoint, HEAD support, configurable image sizes or formats,
  and a configurable concurrency limit.
- **The D-11 non-goals:** editorial `rotate` applied to thumbnails, event poster images, scrubbing or
  proxies, black-frame avoidance, cache eviction and GPU decode.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - ADDED `Requirement: Clip thumbnail endpoint`: the route, its statuses, validators and caching, the
    bounded and shared extraction, and no database
  - ADDED `Requirement: Thumbnail failure kind is a closed, published vocabulary`

## Impact

- **Packages:** `api/` only.
  - `routes/events.py`: the new route, registered before the greedy detail route
  - new `api/thumbnails.py`: the concurrency gate (a semaphore plus the in-flight map), held on
    `app.state`
  - `events_read.py`: the clip lookup against the event's disk listing
  - `schemas.py`: `ThumbnailFailure` and `ProblemOut.thumbnail_failure`
  - `app.py`: builds the gate
  - regenerated `web/openapi.json` and `web/src/api/schema.d.ts`, plus `README.md` and HLD §4.9 docs
- **CLI vs API (Principle V):** API only. The CLI already reaches the same engine operation through
  `auto-reel thumbs` (`clip-thumbnails`). The endpoint adds only request and response shaping: lookup,
  validators and headers, status mapping, and the concurrency bound.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** The staleness fingerprint inputs
  are unchanged. Thumbnails are never an input, and the route writes nothing into the library.
- **Schemas:** no `reel.yaml` change. **No `config.yaml` change in this change:** it reads
  `thumbnails.position` and `thumbnails.cache_dir`, which `clip-thumbnails` adds. **No Alembic
  migration**, no rescan.
- **Wire:** one new path with a required `clip` and an optional, ignored `v` query parameter and an
  optional `If-None-Match` header, one new schema component (`ThumbnailFailure`), one new optional
  problem field.
  Every existing response is unchanged, and the regenerated types compile against the existing client.
- **New third-party dependencies:** none. `starlette.concurrency.run_in_threadpool` and `asyncio` are already available.
- **Size (Principle VIII):** one route, one small gate class, one lookup helper, one enum, one capability
  delta, ten tasks in one package (`api/`) plus regenerated artifacts and docs.
- **Dependencies (gate):** `clip-thumbnails` (T1) must be archived on `main` first. This change calls
  its `ThumbnailError`, `ThumbnailCacheError`, `thumbnail_for`, `thumbnail_path` and
  `resolve_thumbnail_settings` (with `ThumbnailSettings`, all exported from `auto_reel_ng.thumbs`).
