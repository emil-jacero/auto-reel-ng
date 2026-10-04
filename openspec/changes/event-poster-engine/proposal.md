## Why

Every event has one movie and no picture of it. The movie player already borrows the first played clip's
thumbnail as its poster (`web-app`, D-15), but a media server (Jellyfin, Plex, Kodi) that scans the output
folder sees a bare `.mp4` and shows a black tile, and the operator cannot choose the frame. HLD §4.10 and the
§6 roadmap keep "event poster frames" as the last open v2 item. This change is the **engine half**: a chosen
(or default) frame becomes `<movie stem>-poster.jpg` beside the movie and the movie's embedded cover. It
belongs to the §6 v2 phase (the GUI picker follows as its own change, which is why the scope here is
`reel.yaml`, render and manifest only, Principle V: the engine and CLI first).

Decisions relied on: **D-2** (`reel.yaml` is the source of truth; the poster is an editorial fact, Principle
II), **D-9** (the engine never deletes a movie; `prune-renamed` is the one deleting place), **D-11** (the
thumbnail frame is the default: position 0.25 of the clip, duration from the engine's own probe), **D-23**
(clip rotation applied by the engine), **D-24** (`card:` is the model for a top-level optional key carried by
every writer). Research evidence: `docs/research/` has no poster note; the container behaviour (an
`attached_pic` stream is a video stream to ffprobe, so `verify_output`'s one-video-stream rule must be
adjusted) is read from `render/verify.py` and is the one risk the design resolves by a test against real
ffmpeg, in Chrome and Firefox (task 5).

## What Changes

- `reel.yaml` gains an optional top-level `poster: {clip: <identity>, at: <seconds>}`: parsed, validated,
  round-tripped and carried by every writer (the editorial write keeps it when the client omits it).
- A render writes the poster frame from the ORIGINAL clip (display rotation and `rotate:` honoured, HDR
  tone-mapped as the thumbnails do), scaled to the movie's target size, as `<stem>-poster.jpg` beside the movie
  (`.part` → verify → rename), and embeds it as the movie's cover (`attached_pic`, mjpeg, the movie streams
  stream-copied). Both are part of the atomic finalize.
- Default when `poster` is absent, or names a clip that is missing, ignored or excluded: the first played
  clip's frame at the thumbnail position; a fallback of the second kind is a render warning, never a failure.
  An event with no playable clip has no poster and records none.
- `render-manifest.json` claims the sidecar (`poster`, a bare file name or `null`); the claims guard,
  `prune-renamed` and the scan treat the sidecar with its movie.
- **Rendered output changes for identical inputs** (the movie now carries a cover and has a sibling file), so
  `RENDER_GRAPH_VERSION` goes 8 → 9 and every rendered event shows stale once. `poster` joins the editorial
  hash only when present, so a document without it hashes as before.
- `reel.yaml` schema: one new optional key, no `version` change. No Alembic migration, no rescan. No new
  dependency (Principle VII).
- Packages: `reel` (parse, validate, write, hash), `render` (frame extraction, embed, verify, finalize,
  claims). `staleness/manifest` and `cli/prune` change only to read and delete the sidecar named by the
  manifest, as the consequence of the claim (counted under `render`'s output contract). CLI and engine
  only; the API is untouched.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `reel-document`: the optional `poster` key (shape, validation, hash, round trip, carried by every writer).
- `movie-assembly`: the poster sidecar and embedded cover, atomic with the movie; verification ignores the
  cover; the manifest claim, the render guard, `prune-renamed` and the staleness verdict for the sidecar.

## Non-goals

- The GUI picker and any API field (a later change reads `poster` through the existing document read).
- Posters for chapters, per-chapter frames, animated or multi-frame art, or `poster` from a proxy frame.
- Writing the sidecar for a movie that is not re-rendered (no adoption backfill); the version bump makes
  events stale and the next render writes it.
- Changing the web player's poster (it keeps the first played clip's thumbnail until the GUI change).
- NFO/metadata files for Jellyfin/Plex.

## Impact

`auto_reel_ng/reel/{schema,parser,document,writer}.py`, `render/{orchestrator,verify,poster.py (new)}.py`,
`render/claims.py`, `staleness/{fingerprint,manifest,gate}.py`, `cli/prune.py`; `docs/high-level-design.md`.
