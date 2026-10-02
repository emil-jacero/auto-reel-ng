## Context

State of `origin/main` at `5bd92ad`, which already holds the merged gates `thumbs-cache-key-and-count` and
`thumbs-hdr-and-cache-hygiene`. Everything below was re-checked against the code, not taken from the triage alone.

- **`thumbs/thumbnail.py`.** `thumbnail_for(clip, *, position, cache_dir, runtime)` computes
  `key = thumbnail_key(...)`, `target = cache_dir / f"{key}.jpg"`, returns `target` on `is_cached`, otherwise
  runs `_probe_duration` (one `probe_media`, which raises `ThumbnailError` on a probe failure or a duration
  that is not positive and finite), then `_create_temporary` (creates the cache dir and an empty
  `.<key>.<hex>.tmp`, raising `ThumbnailCacheError` on an `OSError`), `_extract` (ffmpeg once; any failure or
  an empty output is `ThumbnailError`), and `_finalize` (`fsync`, `os.replace`). Any `BaseException` removes
  the temporary. On a failure it writes nothing else. The probed `duration` is used once, for
  `at = position * duration`, and dropped. Verified: `grep` finds no other reader of it.
- **The route is in `api/routes/events.py`, not `api/thumbnails.py`.** The triage named `api/thumbnails.py`,
  but that module is only `ThumbnailGate` (two slots, one extraction per key). The route's
  `_serve_thumbnail` does: `If-None-Match` revalidation, `_read_cached_thumbnail`, then
  `gate.produce(key, partial(thumbnail_for, ...))`, then reads the file. `ThumbnailError` becomes
  `_clip_failed` (502 with `thumbnail_failure: "thumbnail_failed"`, detail `<identity>: <one_line_cause>`);
  `ThumbnailCacheError`, `ConfigError` and `LayoutError` become `_thumbnail_failed` (502, no kind). The gate
  needs no edit.
- **The CLI goes through the same function.** `cli/thumbnails.py` `_thumbs_event` calls `is_cached` then
  `thumbnail_for`, and prints `exc.reason` through `one_line_cause`. Whatever `thumbnail_for` does for a
  recorded failure, the CLI inherits.
- **Existing tests pin the old rule.** `tests/test_thumbs.py` asserts `_leftovers(cache_dir) == []` after
  failures (lines ~359, 378, 390, 429, 467, 483), `tests/test_thumbs_ffmpeg.py` asserts
  `_cache_files(cache_dir, "*") == []` (line ~98), and `tests/test_api_thumbnails.py`
  (`test_real_thumbnails_from_a_read_only_library`) asserts a second request "tries again" and that the
  cache holds only the two JPEGs. These change by exactly the marker.
- **Triage evidence for the duration, re-checked.** `ClipOut` (api/schemas.py) has no duration and the
  event detail is probe-free; `probe_media(...).duration` inside `_probe_duration` is the only server-side
  duration, and it is not persisted. `recorded_duration` is the missing read path; the `ClipOut` field that
  uses it is `api-clip-duration`.

## Goals / Non-Goals

**Goals:**
- A clip that failed is not re-attempted for 60 s, by the engine (so the CLI too) and by the API without
  waiting for an extraction slot.
- A clip's probed duration is readable later from the cache with no ffprobe, so a later change can put it
  on `ClipOut` and keep the events routes probe-free.
- A cache or config fault is never remembered against a clip.
- Nothing is invented: an absent or damaged sidecar reads as "unknown".

**Non-Goals:** see proposal.md.

## Research & Decisions

### Where the sidecars live and how they are named
**Context**: Both facts belong to one clip under one set of settings, and the cache already has an
invalidation scheme: the key.
**Explored**: (a) a SQLite or JSON index in the cache dir; (b) a second key without `position`, since a
duration does not depend on it; (c) files beside `<key>.jpg`.
**Decision**: (c). `<key>.json` and `<key>.fail`, in the same directory, named by replacing the `.jpg` suffix
of the `target` path. No code in this change recomputes a key: `thumbnail_for` and the readers take the
`target` that `thumbnail_path` already returns.
**Rationale**: (a) needs locking and a schema; Principle VII says no. (b) needs a second key function that
the merged gates (`thumbs-cache-key-and-count`, `thumbs-hdr-and-cache-hygiene`) would have to be kept in
step with. With (c) those gates change the key and the sidecars follow for free. The cost is that a changed
position, box or `THUMBNAIL_VERSION` makes the duration unknown until a thumbnail is made again; the web
treats `null` as unknown already (`api-clip-duration`).

### The duration sidecar
**Decision**:
```python
def recorded_duration(target: Path) -> Optional[float]: ...
```
`thumbnail_for` writes `{"duration": <float>}` (JSON, `json.dumps` of the float the probe returned, which
round-trips exactly) after `_probe_duration` returned and `_create_temporary` created the directory, and
before `_extract`. It is written even if extraction then fails: the probe was real, and a clip that
probed fine but has no frame at `position × duration` still has a known length. `recorded_duration`:
- returns the float when the file holds a JSON object whose `duration` is a number (not a bool), finite and
  `> 0`;
- returns `None` for a missing file, an unreadable one (any `OSError`), invalid JSON, or any other value. It
  logs at debug and never raises. A read that serves the probe-free events routes must not fail because a
  cache file is damaged, and it must not turn damage into a number.
It never runs ffprobe and never writes. A cache hit in `thumbnail_for` stays "no ffprobe", so it does not
backfill: a JPEG made before this change has no sidecar until its key changes. The `THUMBNAIL_VERSION` bump
that the merged gates make re-keys everything once anyway.
A failure to write the sidecar (after the directory was created) is the cache's fault:
`ThumbnailCacheError`, as `_finalize`'s. This composes with the gate's disk-full rule (a full disk is a
cache fault, reported once).

### The failure marker
**Decision**:
```python
FAILURE_TTL_SECONDS = 60.0
def recorded_failure(clip_path: Path, target: Path) -> Optional[ThumbnailError]: ...
```
`<key>.fail` holds `{"reason": "<ThumbnailError.reason>"}`. Its age is the file's mtime; no timestamp field.
- **Written** when `thumbnail_for` is about to raise `ThumbnailError` *from an attempt it made*: a probe
  failure, no usable duration, no frame, or undecodable ffmpeg output. Not written for: the stat failure
  (no key exists), `ThumbnailCacheError` (the cache's fault, and the marker could not be written reliably
  anyway), `KeyboardInterrupt` or other `BaseException`, or a success.
- **Not refreshed by a read.** The marker check sits outside the "record on failure" handler. If it did not,
  a page polling a broken clip every 10 s would extend the window forever and a fixed ffmpeg would never be
  tried. The window is 60 s from the failed attempt.
- **Read** by `recorded_failure`: returns `ThumbnailError(str(clip_path), reason)` when the file exists, is
  valid JSON with a string `reason`, and `0 <= now - mtime < FAILURE_TTL_SECONDS`. An expired marker, a
  marker dated in the future (clock moved back), or damaged content reads as "no marker" and the clip is
  attempted again. A missing file is no marker. Any other `OSError` (an unreadable cache directory) raises
  `ThumbnailCacheError`, the same classification `is_cached` gives it.
- **Order in `thumbnail_for`**: stat and key; `is_cached` (a JPEG always wins over a marker); `recorded_failure`
  (raise it, before the runtime is even resolved: no ffprobe, no ffmpeg); then the existing probe, record
  duration, extract, finalize. A success then removes `<key>.fail` (`suppress(OSError)`): an expired marker
  does not linger beside a good JPEG.
- **Written** atomically like every cache file, through the temporary name the merged gate's sweep recognises
  (`.<key>.<hex>.tmp`), so a crash mid-write is swept like a crashed JPEG. Writing is best effort: the
  directory is created if needed, and an `OSError` is logged at warning and swallowed, because the clip's own
  `ThumbnailError` is the real outcome and the next real attempt reports the cache fault properly
  (`_create_temporary`).
- **Idempotency**: re-running within the TTL repeats the recorded error; after it, tries again and rewrites
  or removes the marker. A worker or service restart changes nothing: the marker is on disk. Two processes
  failing at once each replace the marker atomically with the same content.

### The 502 from the marker
**Decision**: in `_serve_thumbnail`, after the cached-JPEG read returns `None` and before `gate.produce`:
```python
failure = await run_in_threadpool(recorded_failure, source.clip_path, source.cache_path)
if failure is not None:
    raise failure
```
The route's existing `except ThumbnailError` turns it into the usual `_clip_failed` response: same status,
same `thumbnail_failure` kind, same detail format, same log line, no caching headers. A recorded failure
never takes a gate slot. `If-None-Match` is decided before this, as today (a client that holds the current
entity-tag gets its 304 regardless). No failure kind is added, so the closed set `thumbnail_failed` and the
generated client types are unchanged.

### Service-wide faults
The page-level hint for a service-wide fault is the client's (`web-playback-and-notices`). Server side, the
split already exists and is kept: a cache fault (`ThumbnailCacheError`) and a config fault answer 502 with
no kind and are never remembered. A broken ffmpeg binary, by contrast, surfaces as a per-clip
`ThumbnailError` ("no frame extracted ..."), and a stalled read as a `ThumbnailError` time-out (60 s
bound), so both are remembered per clip for 60 s. That is the accepted
trade-off, not a bug: after the operator fixes the binary, the previews recover within a minute.

### Interaction with the merged gate
`thumbs-hdr-and-cache-hygiene` edits `thumbnail.py` too. Read before this change is implemented:
- **HDR flag in the key / chain in `thumbnail_args`**: sidecars are named from `target`, so they follow any
  key. The marker is written from the same `except ThumbnailError` path whatever the extraction args are.
- **Disk full → `ThumbnailCacheError`**: neither sidecar write turns a `ThumbnailError` into a marker; a
  full disk raises the cache error from the duration write or the extraction and is never remembered.
- **Sweep of `.<key>.<hex>.tmp` older than a day**: sidecar temporaries use exactly that name, so they
  are swept, and `tests/test_thumbs.py` helpers that list leftovers must ignore nothing new.
- If the gate ends up changing `thumbnail_for`'s structure (for example an `hdr` argument), the implementer
  re-reads the merged function and places the marker check and the duration write by the rules above, not by
  line numbers.

## Decisions (summary of choices the supervisor already made)
- TTL is the module constant `FAILURE_TTL_SECONDS = 60.0`; no config key.
- The marker is never written for `ThumbnailCacheError`.

## Failure behaviour (Principles I and IV)
- Nothing is fabricated: unknown duration is `None`, never 0 or an estimate.
- A damaged sidecar is ignored, never repaired by guessing; the clip is simply attempted again.
- A failed clip still raises a typed `ThumbnailError` naming the clip, from the marker or from a live
  attempt; the CLI still prints one ERROR line and exits 1; the API still answers 502 with the kind.
- No file that looks like a thumbnail is ever left: `<key>.jpg` appears only after `fsync` and rename.
  The sidecars are not thumbnails and the spec says so.
- No ffmpeg graph or rendered byte changes: no `RENDER_GRAPH_VERSION` bump, no `THUMBNAIL_VERSION` bump.
- Doc fold-back: the sidecars are a cache-format decision that outlives the change, so HLD D-11 gets one
  bullet (tasks, group 5).

## Risks / Trade-offs
- **A transient fault is remembered for up to 60 s** (a USB archive that was spinning up, a momentary
  decode error). Accepted: the alternative is the current re-attempt on every request, and the window is short
  and bounded. The CLI inherits it; re-running `auto-reel thumbs` after a quick fix within a minute reports
  the earlier reason. The message is the same one the live attempt gave.
- **Durations are unknown until a thumbnail is made, and again after a key change.** Honest, documented, and
  handled as `null` by the consumers.
- **Wall clock.** The TTL uses the marker's mtime against `time.time()`. A clock set back is treated as
  expired (the marker is ignored), never as valid forever.
- **Orphans.** Sidecars of old keys stay, like old JPEGs (D-11: never evicted in v1). A few hundred bytes each.
