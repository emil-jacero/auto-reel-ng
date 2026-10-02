## Why

Two findings from the 2026-10-02 bug triage share one fix: the thumbnail cache keeps nothing about a clip
except the JPEG, so what the engine learns while making (or failing to make) a thumbnail is thrown away.

1. **A failing clip is re-extracted on every request.** `thumbnail_for` raises `ThumbnailError` and writes
   nothing (the temporary file is removed), so there is no negative cache. An event page asks for one
   thumbnail per clip. A clip that fails costs a full ffprobe plus ffmpeg attempt on every page view, and
   every attempt holds one of the service's two extraction slots (`ThumbnailGate`, D-11). One broken clip
   in a cold event therefore slows the healthy clips behind it. The api-service spec says it outright: "A
   failed extraction SHALL NOT be remembered". That rule was right while nothing could tell a clip's fault
   from the service's, and it is wrong for a clip that is simply undecodable.
2. **A clip's duration is learned and dropped.** `thumbnail_for` already runs `probe_media` on every cache
   miss and uses `duration` for one multiplication (`position × duration`). The value is then discarded.
   Nothing on the server knows a clip's length until the browser's `<video>` element reports it
   (`previews.setLength`), so the cuts screen cannot reject `out > duration` up front. The event detail
   cannot carry the value without probing, because the detail is probe-free (Principle IV, HLD §4.9).

Both are fixed by two small files written next to `<key>.jpg` in the cache directory (D-11), keyed
identically to it, so they inherit its invalidation (a changed clip, position, box or format version gets
a new key and the old files are never read again).

This change is the **engine and API half** of both items. Its consumers are separate changes: the
`ClipOut.duration` field and the schema regeneration are `api-clip-duration`, and the client's page-level
"previews are unavailable" note is `web-playback-and-notices`. It belongs to HLD §6 GUI v1 (phase 8), as
refinements of D-11, and depends on no §8 research item.

It builds on the merged gate change `thumbs-hdr-and-cache-hygiene`, which edits the same file
(`thumbs/thumbnail.py`). That change adds an HDR flag to the cache key payload for HDR clips only,
`ThumbnailCacheError` on "No space left on device", and a once-per-process sweep of stale
`.<key>.<hex>.tmp` files. This change is written to compose with all three (see design, "Interaction with
the merged gate").

## What Changes

- **`thumbs/`: a duration sidecar `<key>.json`.** `thumbnail_for` writes `{"duration": <seconds>}`
  atomically after a probe that gave a usable duration, before it extracts. A new
  `recorded_duration(...)` reads it with no ffprobe and no ffmpeg and returns `None` when the sidecar is
  absent, unreadable or not a positive finite number. It never guesses.
- **`thumbs/`: a failure marker `<key>.fail`.** When `thumbnail_for` raises `ThumbnailError` for a clip it
  could stat, it records the reason in `<key>.fail`. For `FAILURE_TTL_SECONDS` (60) afterwards, a call for
  the same key raises the recorded `ThumbnailError` without running ffprobe or ffmpeg. A marker is never
  written for `ThumbnailCacheError`, for a stat failure, or for a success. A later success removes it.
  `recorded_failure(...)` exposes the check.
- **`api/`: the thumbnail route answers from the marker.** `GET /api/v1/events/{id}/thumbnail` consults
  the marker after the cached-JPEG check and before the extraction gate, so a recorded failure answers the
  same 502 with the thumbnail failure kind, without waiting for a slot and without a process. The "failed
  extraction SHALL NOT be remembered" rule is replaced by the 60 s rule. A cache or config fault stays
  unremembered.
- **Existing tests that assert "nothing left in the cache after a failure"** are updated to allow exactly
  the marker.

### Rendered output and fingerprint

None. Thumbnails are not part of a render. `RENDER_GRAPH_VERSION` is unchanged and the staleness
fingerprint inputs are unchanged. `THUMBNAIL_VERSION` is unchanged by this change (no thumbnail byte
changes); the sidecars add files only.

### Schema and storage

No `reel.yaml` or `config.yaml` change, no new config key, no Alembic migration, no rescan. The sidecars
live in the existing cache directory, outside the library, and are derived state (D-7, D-11).

### Packages and surfaces

Packages: `auto_reel_ng/thumbs` and `auto_reel_ng/api`. The engine owns the behaviour, so the CLI
`auto-reel thumbs` inherits the marker through `thumbnail_for` with no `cli/` edit (Principle V); the API
gains no behaviour the CLI cannot reach.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `clip-thumbnails`: a failed clip may leave a short-lived failure marker (and no `<key>.jpg`); the cache
  holds sidecars beside the JPEG; the duration sidecar and the failure marker are new requirements.
- `api-service`: the clip thumbnail endpoint remembers a clip's failure for 60 s and answers it without
  extraction; it still never remembers a cache or config fault.

## Non-goals

- **`ClipOut.duration`**, the OpenAPI/`schema.d.ts` regeneration and any change to the events routes:
  `api-clip-duration`. This change only makes the value readable from the cache.
- **Any client change**: the page-level "Previews are unavailable" note and the cuts screen's use of the
  duration are `web-playback-and-notices`.
- **Probing to fill a missing duration.** The reader never runs ffprobe; a JPEG made before this change
  has no sidecar and its duration stays unknown (`null` downstream). Principle IV keeps the events routes
  probe-free.
- **Backfilling on a cache hit.** A cache hit still returns with no ffprobe.
- **A new failure kind, a `Retry-After` header or a configurable TTL.** The TTL is a module constant
  (supervisor decision). The 502 body is exactly today's.
- **Evicting markers or sidecars.** The cache is still never evicted in v1 (D-11). An expired marker is
  overwritten or removed by the next attempt for the same key.
- **The HDR tone-map, the disk-full classification and the temporary-file sweep**: already in the gate
  change.

## Impact

- `auto_reel_ng/thumbs/thumbnail.py`, `auto_reel_ng/thumbs/__init__.py` (exports).
- `auto_reel_ng/api/routes/events.py` (the thumbnail route). `api/thumbnails.py` (the gate) is unchanged.
- Tests: `tests/test_thumbs.py`, `tests/test_thumbs_ffmpeg.py`, `tests/test_api_thumbnails.py`,
  `tests/test_cli_thumbs.py`.
- Docs: HLD D-11 gets one bullet (design, "Sidecars").
- No new dependency.
