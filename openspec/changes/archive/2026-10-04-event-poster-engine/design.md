## Context

`render_movie` writes `<movie>.part`, verifies it (`verify_output`: exactly one video stream, matching the
target), renames it, then writes `render-manifest.json`. `reel.yaml` carries per-chapter `card:` (D-24), the
model for an optional editorial key that every writer must carry. Thumbnails (D-11) already compute "the frame
at `position × duration` of a clip, duration from our own probe, HDR tone-mapped". Output claims are decided by
manifests (`render/claims.py`); `prune-renamed` deletes superseded movies only.

## Goals / Non-Goals

**Goals:** a deterministic poster per event, chosen in `reel.yaml`, written atomically with the movie, claimed
and pruned with it. **Non-goals:** see the proposal.

## Research & Decisions

### Where the poster lives
**Context**: the frame is an editorial choice. **Explored**: `card:` handling in `reel/schema.py`, `writer.py`,
and `reel-document` "A chapter's card is carried by every writer". **Decision**: top-level optional
`poster: {clip, at}`; `clip` is a clip identity (event-relative path, same rule as `clips:` keys), `at` a
number of seconds `>= 0` in the ORIGINAL clip, before any cut. Unknown keys inside `poster`, a non-mapping, a
missing `clip`/`at`, a negative or non-finite `at`, an `at` that is not a number fail loud at load naming
`poster.<key>`. A `poster.clip` that no chapter, `clips:` entry or file of the event can name is NOT a load
error (a clip may be on disk but not yet adopted); it is resolved at render. **Rationale**: `reel.yaml` stays
the truth (II); resolution needs the probe, which loading must not do.

### Resolution at render (typed error vs warning)
**Decision**: `resolve_poster(document, played_clips, probes) -> PosterChoice` with `PosterChoice(clip, at,
source)`, `source` in `explicit | default`.
- `poster` absent → default: first PLAYED clip (first clip of the movie after chapters, ignores and
  exclusions), `at = DEFAULT_POSITION × duration` (the thumbnail's 0.25).
- `poster.clip` named but missing / ignored / excluded / not played → default, one render warning naming the
  clip and the reason; the render succeeds.
- `poster.clip` played but `at >= duration` (our own probe) → `PosterFrameError` (new, typed, in `errors.py`)
  naming the clip, `at` and the real duration. This fails the event, like any bad editorial input, before
  anything is encoded (resolved in the plan step, before segments). Failing loud here is deliberate: the
  operator asked for a frame that does not exist; silently picking another would fabricate (I).
- No played clip at all → no poster; `poster: null` in the manifest; no sidecar.

### Extraction
**Decision**: one ffmpeg run on the original clip: `-ss <at>` (input seek, accurate), `-an -frames:v 1`,
the renderer's own transpose chain (D-23: ffmpeg autorotate off, display rotation + `rotate:`), SAR
normalised, the HDR tone-map chain when the probe says PQ/HLG, scaled with `force_original_aspect_ratio=decrease`
then padded to the movie's target size (same box as the movie's frames), `-q:v 2`, `-f image2 -c:v mjpeg`.
Always on the CPU: one frame, so every profile shares it and there is nothing to fall back from (III). No
frame at that time → `PosterFrameError`, never a placeholder. The pure function `poster_args(...)` returns the
argument list (golden-string tested); `extract_poster(...)` runs it through `FfmpegRuntime` (only `ffmpeg/`
spawns, VI).

### Sidecar and embedded cover, atomic with the movie
Output `<stem>-poster.jpg` is `output_path.with_suffix("")` + `-poster.jpg`. Finalize order:
1. movie `.part` assembled and verified as today;
2. poster extracted to `<stem>-poster.jpg.part`, verified (JPEG magic, probe: one mjpeg frame, dimensions =
   target);
3. embed: `ffmpeg -i movie.part -i poster.part.jpg -map 0 -map 1 -c copy -disposition:v:1 attached_pic
   -f mp4 movie.cover.part` (movie streams copied; `-map 0` keeps audio, chapters via `-map_chapters 0`,
   metadata via `-map_metadata 0`; `+faststart` re-applied). The cover file replaces the movie `.part` and
   is re-verified;
4. rename poster `.part` → `<stem>-poster.jpg`, then movie `.part` → movie (movie last, so a movie that
   exists never lacks a poster that the manifest claims); then the manifest, as today.
A kill before 4 leaves only `.part` files (swept as today). A kill between the two renames leaves a poster
without a movie update, and no manifest: the event reads stale and the next render replaces both.
Idempotency: a re-run and `--force` rewrite both files; a worker restart mid-render restarts from the plan.
Cost: one extra stream-copy pass over the finished movie (I/O only, no re-encode).

### Verification ignores the cover
`verify_output`'s `_video_stream_count` counts ffprobe `v` streams, and an `attached_pic` is one. The rule
becomes "exactly one video stream that is NOT `disposition.attached_pic`", and the cover, when expected, must
be exactly one mjpeg `attached_pic`. `probe_media` of a rendered movie (movie facts, chapter probing) is
checked for the same: it MUST pick the real video stream. A test renders a movie with a cover and asserts the
movie facts equal those of the same movie without. Playback: tests assert Chrome and Firefox play the
covered movie through the existing media endpoint (Playwright from the scratchpad, task 5).

### Manifest claim, guard, prune, staleness
- Manifest gains `poster` (bare file name or `null`); schema version stays 1; absent or malformed reads as
  `null` without making the manifest unreadable (same fail-open rule as `superseded`).
- The sidecar is a claim on a file: `claimed_movie` / "a render refuses to replace a movie another event
  records" treat `<claimed output stem>-poster.jpg` as claimed too, so an event cannot overwrite another
  event's poster unforced.
- `prune-renamed` deletes a superseded movie's sidecar (derived by the name rule) with it, under the same
  checks (regular file, inside the output dir, unclaimed); a sidecar with no movie is not listed.
- Scan: when the manifest records a `poster` and that file is not a regular file beside the movie, the
  verdict cites the existing `output` reason (the render output is not whole) — no new reason code, no probe.
  A manifest with `poster: null` or no field expects no sidecar.
- Fingerprint: `poster` is in the editorial component only when present (a document without it hashes as
  before). `RENDER_GRAPH_VERSION` 10 → 11 ("11: event-poster-engine — the movie carries a cover and a
  `-poster.jpg` sidecar"). Clip signals are unchanged: no probe enters the fingerprint (IV).

### Writers
Round-trip writer keeps `poster` byte-stable with comments and writes it after `look`/before `chapters` for
typed documents. The editorial write follows the `card` rule: key absent or `null` keeps the existing
`poster`; a mapping replaces it key by key, preserving equal values' comments; an empty mapping `{}` removes
it. The merged document is validated before writing. Renaming a clip identity in the same write is NOT
followed (clip identities do not change in this schema; a dangling `poster.clip` falls back with a warning).

## Risks / Trade-offs

- **Silent wrong frame** (the GPU-rotation lesson from proxies): the CPU-only transpose chain removes it; a
  test extracts from a rotated clip with non-1:1 SAR and compares the dimensions and orientation.
- **mp4 cover support**: some players ignore `attached_pic`; harmless. The sidecar is the media-server path.
- **Extra remux pass** on long movies (seconds, I/O bound); accepted over a re-encode.
- **Every rendered event goes stale once** (version bump); the operator re-renders at will, as for every
  prior bump.
- A `poster.clip` outside the event does not fail at load, so a typo is found at render (typed error or
  warning, naming the clip); a GUI picker will only offer real clips.
