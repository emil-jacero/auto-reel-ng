## Why

The cuts panel cannot refuse a cut that runs past a clip's end until the clip has been previewed in this Edit
mode, because the service gives no duration (HLD §4.9 "the events read model is probe-free"; D-14, D-16: "the
API still carries no duration, so a clip never previewed keeps D-14's rule"). The operator can therefore type
a cut such as `5` to `7` on a 6.02 s clip, save it, and learn nothing: the render clamps it silently
(`kept_spans` takes `min(duration, t.end)`), so the movie shows less cut than the operator asked for.

The duration is already measured. The thumbnail operation probes every clip it makes a thumbnail for (D-11),
and the gate change `thumbs-sidecar-metadata` keeps that number in a small JSON sidecar beside the cached
JPEG, readable with no `ffprobe`. This change lets the event detail carry that number, so the panel knows the
length of every clip that has a thumbnail (the event page asks for one per clip, so that is most of them)
before any preview opens. HLD §6 phase 8 (GUI v1 polish); no §8 research item is open for it.

## What Changes

- `GET /api/v1/events/{event_id}`: each clip gains `duration` (seconds, nullable, optional in the schema).
  It is read from the thumbnail cache's duration sidecar with no `ffprobe`/`ffmpeg` and no cache write. `null`
  means unknown: a missing clip, a thumbnail not yet made for the clip's current size and mtime, an unusable
  sidecar, or an unresolvable `thumbnails` config. It is never zero or a guess (Principle I). The events list
  is unchanged.
- `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.
- The cuts panel takes a clip's length from the preview when the preview has read it, else from the detail's
  duration when non-null, else it does not know (today's wording and behaviour, kept as the fallback). With a
  known length it states where the clip ends, refuses an end past it, and marks listed cuts past it, before
  any preview opens. The preview's length keeps priority because Set From/Set To write times in it.
- HLD: §4.9's probe-free paragraph, D-14's "cannot refuse a cut past the clip's end" sentence and D-16's
  "The length" bullet are amended.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `api-service`: "Events read model is scanned from disk per request" gains the nullable per-clip duration
  and its probe-free, write-free, never-fabricated rules.
- `web-app`: "Edit mode lists, adds and removes a clip's cuts" and "A clip's preview sets cut times at the
  playhead and plays the clip as the movie will" take the length from the preview, else from the detail.

## Impact

- Packages: `auto_reel_ng/api` (`schemas.py`, `events_read.py`) and `web/` (`src/cuts/`, `src/edit/`,
  generated `openapi.json`, `schema.d.ts`). The reader of the sidecar is the one `thumbs-sidecar-metadata`
  adds to `thumbs/`; this change only calls it.
- Rendered output for identical inputs does not change: no `RENDER_GRAPH_VERSION` bump. The staleness
  fingerprint inputs do not change (the duration is not an input; Principle IV). No `reel.yaml` or
  `config.yaml` schema change, no Alembic migration, no rescan.
- CLI/API (Principle V): the API is a projection of an engine read (`thumbs/`); `auto-reel scan` prints no
  per-clip facts, so there is no CLI surface to add.
- Gates: `thumbs-sidecar-metadata` (the sidecar and its reader) and `api-job-summary-and-renamed-fields`
  (it edits `schemas.py`, `events_read.py` and `tests/test_api_events.py`; this change applies after it).

## Non-goals

- No `ffprobe` in the events routes, and no backfill: a clip with no sidecar stays `null` until its thumbnail
  is made. Nothing here makes or refreshes a thumbnail.
- No change to the overlap rule or to how the engine clamps a cut at render (the render stays the authority).
- No server-side refusal of a cut past the end in the editorial write (the write endpoint keeps accepting
  what `reel.yaml` allows); this is a GUI up-front check only.
- No duration in the events list, and no duration in the analysis cache.
- The preview, its cut bar and playhead are unchanged: they need the browser's own media length.
