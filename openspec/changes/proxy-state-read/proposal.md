## Why

GUI v2's timeline lays clips out from media facts (duration, frame rate, dimensions, rotation, audio codec)
that the events detail has never carried: it is probe-free by rule (HLD §4.9, Principle IV; research
`synthesis.md` X6), and its one media field, `duration`, is only the thumbnail sidecar's number. The proxy work
(D-21: `proxy-encode`, `filmstrip-sprites`) writes exactly those facts into a cache entry next to each clip's
proxy and filmstrip, so the detail can pass them on by reading that entry, with no probe. The same read tells
the page which clips are ready to play and which need preparing: the timeline "opens only for events whose
proxies are prepared" (synthesis X6, risk 9), and the proxy-first clip preview, the Prepare action and the
`POST …/proxies` fresh check all branch on it. HLD §6 phase 8 (GUI v2), §4.10 v2 scope; D-11 (the cache this
copies), D-15 (the entity tag as `v`), D-21 (the proxy contract). No §8 research item is open for it.

## What Changes

- `GET /api/v1/events/{event_id}`: each clip gains `proxy` (nullable, optional in the schema):
  `{state, facts, version, reason}`.
  - `state` is a closed, published vocabulary: `absent` (no usable entry, nothing recorded), `ready`,
    `stale` (an entry exists for the clip as it is now but cannot be used), `failed` (the last attempt failed
    and nothing usable exists).
  - `facts` (only when `ready`): the ffprobe duration, frame rate as a fraction, a VFR flag (null when the
    container gave no average rate to compare), dimensions as displayed, source rotation (null when the source
    declares none), source audio codec (null when the source has none) and the filmstrip tile geometry, copied
    from the entry's `facts.json`.
  - `version` (only when `ready`): the proxy file's entity tag without quotes, exactly as the proxy route will
    send it, so the client can put it in the media URL as `v` (D-15) without a request per clip.
  - `reason` (only when `failed`): a one-line cause with no server paths.
  - `proxy` is `null` (unknown, never `absent`) for a MISSING clip and for every clip when the project's
    `proxies` configuration cannot be resolved (one warning), as `duration` is for `thumbnails`.
- The state is read by `stat` and one small JSON read per clip. The read runs no process, writes nothing and
  never lists the cache directory; a test forbids subprocess.
- `proxies/` gains the read-only counterpart of `ensure_proxy` (`read_proxy_state`, beside the merged
  `lookup_proxy`, which answers only "is there a complete entry"): classify a clip's cache entry into a state
  and facts, and a failure marker `<key>.fail` that `ensure_proxy` records when a clip's proxy cannot be made
  (probe, encode, post-encode verification), which is what makes `failed` observable. A failed filmstrip is
  not recorded: `clip-filmstrips` says a sprite failure is not remembered, and that clip reads `absent`.
- `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated; the drift test stays green.
- HLD: §4.9 probe-free paragraph (a second sanctioned cache read), §4.10 v2 notes, D-21 (the state vocabulary
  and the key-moves-means-absent rule) are amended.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `api-service`: "Events read model is scanned from disk per request" says `duration` is no longer the one
  media-fact exception; a new requirement, "The event detail reports each clip's proxy state", defines the
  field, its nullability and its probe-free, write-free rules.
- `clip-proxies`: (created by `proxy-encode`; this change ADDS to it) "A clip's proxy state is read from its
  cache entry" defines the four states, their precedence and the failure marker.

## Impact

- Packages: `auto_reel_ng/api` (`schemas.py`, `events_read.py`, plus the regenerated `web/openapi.json` and
  `web/src/api/schema.d.ts`, which count with the api change) and `auto_reel_ng/proxies` (the reader and the
  failure marker). The plan listed `api` alone; the reader sits in `proxies/` because the cache layout belongs
  to the layer that writes it (Principle VI), and the failure marker has no other home. Two packages is the
  limit.
- Gates: `proxy-encode` (`ensure_proxy`, `lookup_proxy`, the cache entry layout, `facts.json`, `PROXY_VERSION`,
  the `proxies` settings and the capability `clip-proxies`) and `filmstrip-sprites` (`filmstrip.jpg` and the
  `filmstrip` record in `facts.json`; capability `clip-filmstrips`). Both are merged; the names below are the
  ones they export (design, "Seams, confirmed against the merged gates").
- Rendered output for identical inputs does not change: no `RENDER_GRAPH_VERSION` bump. The staleness
  fingerprint inputs do not change: the proxy state is not an input (D-21). No `reel.yaml` or `config.yaml`
  schema change (the `proxies` keys are `proxy-encode`'s), no Alembic migration, no rescan.
- CLI/API (Principle V): the API projects an engine read (`proxies/`). `auto-reel proxies` already prints what
  it did; no CLI surface is added.

## Non-goals

- No proxy media route, no filmstrip route (`proxy-media-endpoints`), no enqueue endpoint or job `kind` on the
  wire (`proxy-enqueue-endpoint`), no web screen reading the field (`clip-preview-proxy`, `timeline-view`).
- No `proxy` field on the events list: the list keeps its clip counts, and a per-clip read per event would
  turn one request into a read of every cache entry in the library (HLD §4.9, whole-library reads).
- No probe, no ffmpeg, no cache write on a read; no backfill. An absent entry stays absent until a job or
  `auto-reel proxies` makes it.
- No detection of a previous source file's or previous `PROXY_VERSION`'s entry: a replaced file or a version
  bump moves the key and reads `absent` (those entries are orphans; pruning them is a later `--prune`).
- No eviction, no size accounting, no scan of the cache directory.
- `ClipOut.duration` (the thumbnail sidecar's number) is unchanged and is not replaced by `proxy.facts.duration`.
