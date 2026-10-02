## Context

Triage item `clip-duration-only-known-after-preview`, re-checked against `origin/main` 6a7fe16:

- `api/schemas.py` `ClipOut` has `identity`, `status`, `size`, `mtime`. Its docstring says duration "belongs to
  the analysis cache" and the detail is probe-free (Principle IV). `api/events_read.py` `_clip_out` stats the
  file (`_file_facts`) and nothing else; `_build_chapters` receives only `event_dir`.
- `thumbs/thumbnail.py` `thumbnail_for` probes the duration (`_probe_duration`) on a cache miss to place the
  frame at `position x duration`, and discards it. `thumbnail_key` hashes the resolved path, size, mtime in ns,
  position, box and version; a replaced file or a changed `thumbnails.position` re-keys.
- The page learns a length only from the `<video>` (`ClipPreview.tsx` -> `previews.setLength`, in memory, per
  Edit mode). `cuts/times.ts` `checkCut(listed, typedIn, typedOut, length?)` refuses `out > length` only when
  `length` is defined; `CutsPanel.tsx` gets it from `useClipLength(previews, clipMediaUrl(eventId, {identity,
  mtime}))`. `CutsPanel` is rendered from `edit/ClipOrderList.tsx` with `mtime={clip.mtime ?? null}`.
- `render/segments.py` `kept_spans` clamps `min(duration, t.end)`: the render is the authority and a cut past
  the end is harmless there, just unseen by the operator.

Gates, designed around (both implement before this change; their triage entries were read):

- `thumbs-sidecar-metadata` adds, next to `<key>.jpg`, a `<key>.json` holding the duration `thumbnail_for`
  probed, "readable with no ffprobe", and a `<key>.fail` negative marker (not used here). This change depends
  on that sidecar and its reader in `thumbs/`, and uses them by whatever names that change exports; it does
  not define the sidecar format.
- `api-job-summary-and-renamed-fields` edits `schemas.py`, `events_read.py`, `tests/test_api_events.py`,
  `web/openapi.json` and `schema.d.ts` (a `JobSummaryOut` and a staleness change). This change touches
  different models (`ClipOut`) and functions (`_clip_out`, `_build_chapters`), so the conflict is textual only:
  apply on top and regenerate `openapi.json`/`schema.d.ts` from the merged code rather than merging them.

## Goals / Non-Goals

**Goals:**
- A probe-free, write-free, nullable `ClipOut.duration` on the detail response.
- The cuts panel refuses an end past the clip's end, states where the clip ends, and marks past-end cuts
  before any preview opens when the duration is known; the preview-read length keeps priority.

**Non-Goals:** see the proposal (no backfill, no probe, no server-side refusal, no list field).

## Decisions

### The sidecar is the source; the detail never probes
**Context**: `GET /events/{id}` is probe-free by D-A3 and Principle IV, and §4.9 quotes that as "the rule to
quote when a response field would need an `ffprobe`".
**Explored**: (a) probe in `_clip_out`: rejected, it reads the archive's USB drive once per clip per request
and breaks the rule; (b) store durations in Postgres or the analysis cache: rejected, the analysis cache is
keyed by event and analysis settings and is written by analysis runs, and Postgres must stay rebuildable from
disk (Principle II); (c) the thumbnail sidecar the gate adds: the number is already measured, keyed by the same
(file name, size, mtime) that identifies the file, and lives in the cache that is already outside the library.
**Decision**: (c). `_clip_out` computes the clip's cache path with `thumbs.thumbnail_path(clip, position=, cache_dir=)`
(both from `resolve_thumbnail_settings`) and asks the gate's `thumbs.recorded_duration(path)` for the number, and `ClipOut.duration: Optional[float] = None`.
**Rationale**: no new store, no new probe, the key makes staleness impossible (a replaced file re-keys to
`null`). The §4.9 rule is amended, not broken: the field is a media fact served from a cache written by the
thumbnail operation, which is not an events read (see Docs below).

### Plumbing: resolve settings once per detail request
`thumbnail_settings` is resolved once in the detail path (`load_project_config` + `resolve_thumbnail_settings`,
as `thumbnail_source` does) and passed down to `_build_chapters`/`_clip_out` as a small `cache_dir`+`position`
pair, the way the list passes `look_defaults` once. `_clip_out` keeps its MISSING short-circuit: a missing clip
is neither statted nor looked up. The sidecar read is one small file per clip, by key; it shares the
`thumbnail_key` stat/resolve with nothing else, so a detail of N clips costs 2N stats and N small reads, with
no process spawned.

### Failure behaviour: unknown, not an error
**Decision**: the reader returning nothing (no sidecar, invalid JSON, non-finite, <= 0, unreadable cache
directory) yields `null`; an `OSError` from the key's stat yields `null` (the clip changed under the scan, as
`_file_facts` already treats it). A `ConfigError` from `resolve_thumbnail_settings` yields `null` for every
clip and one `logger.warning`; the thumbnail endpoint still fails loud on the same config.
**Rationale**: Principle I forbids a fabricated value, not an absent one. Failing the whole detail for a broken
thumbnail cache or a bad `thumbnails.position` would take the editor down for a hint, so the softening is per
field. Alternative (let `ConfigError` propagate like the look defaults' config errors) was rejected: the look
defaults are needed to answer the staleness verdict; the duration is optional.

### Schema: nullable and optional
`duration: Optional[float] = None` (pydantic emits `anyOf [number, null]`, not in `required`), so the response
stays backward compatible and `schema.d.ts` gets `duration?: number | null`. The client treats `null` and
absent as unknown. No bound is encoded in the schema; the reader guarantees a finite number above zero.

### Web: preview length first, detail duration second
`CutsPanel` gets a `duration: number | null` prop (from `ClipOrderList`'s `clip.duration ?? null`, next to
`mtime`) and computes `length = previewLength ?? (duration ?? undefined)`. The preview's value wins because
Set From/Set To write times in it, and Firefox reads up to 60 ms more than the probe (D-16); the reverse
precedence would refuse a cut set at the end of the clip. Everything downstream already keys on `length !==
undefined`: `checkCut`'s `past-end` refusal, the "This clip ends at" hint (`lengthHint`), and the `pastEnd`
badge on listed cuts. `CUT_HINT` (the "page does not know" text) therefore appears only when both sources are
unknown. `ClipPreview`, `CutBar` and `previews.ts` are unchanged: they need the video's own length, and
`previews.setLength` stays the fallback and the priority source. The hint says whose length it states: "as this browser reads it" once the preview read it (today's words), "as measured for its thumbnail" when it is the detail's duration; both keep "This clip ends at <time>". The duration is not copied into the
previews store, so there is no lifetime to manage: it arrives with each detail response and belongs to the
mtime that response reported.

### Docs (folded into the HLD)
§4.9's probe-free paragraph gets one sentence: the detail's per-clip duration is read from the thumbnail
cache's sidecar, never probed, `null` when unknown. D-14's "cannot refuse a cut past the clip's end ..." and
D-16's "The length" bullet ("The API still carries no duration") are amended in place; no new D-n, because
the decision refines D-14/D-16 and does not outlive them. The spec line "The events list and the event detail
SHALL gain no thumbnail field" in the clip-thumbnail endpoint requirement stays true: `duration` is a clip
media fact, not a thumbnail field, and it is not a URL or a cache path.

## Risks / Trade-offs

- [Cold or pre-gate caches show `null`] Clips whose thumbnails were cached before the gate have a JPEG but no
  sidecar; the gate decides whether those are re-keyed or backfilled. Until then the field is `null` and the
  panel behaves exactly as today. This change makes no probe to fill the gap.
- [Changing `thumbnails.position` re-keys, so durations go `null` until thumbnails are remade] Accepted; the
  duration does not depend on position, but sharing the JPEG's key keeps one cache lifecycle (the gate's
  choice). The fallback covers it.
- [Probe vs browser length differ by up to ~60 ms] The preview length wins when known. Before a preview, a
  cut ending between the probe's duration and the browser's is refused as past the end; the render would have
  clamped it by that same few milliseconds, so nothing the operator could use is lost.
- [Stale page] A detail fetched before a thumbnail existed keeps `null` until the next detail read; the panel
  falls back to the preview, as before.
- [Conflict with the job-summary gate in `schemas.py`/`events_read.py`/`openapi.json`] Textual only; re-run the
  schema dump after rebasing onto the merged code.

## Migration Plan

None: additive optional field, no stored state, no data change. Rollback is reverting the change; clients that
ignore the field are unaffected.

## Idempotency

Reading is idempotent and writes nothing: repeated detail requests, a `--force` render and a worker restart
neither read nor change the sidecar.
