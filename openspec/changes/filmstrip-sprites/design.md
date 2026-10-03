## Context

See `proposal.md` for the why. Facts that shape the approach:

- **The gate has merged.** `proxy-encode` created `auto_reel_ng/proxies/` with `ensure_proxy()`,
  `lookup_proxy()`, `PROXY_VERSION`, and one cache entry per clip under `$XDG_CACHE_HOME/auto-reel/proxies/<key>/`:
  `proxy.mp4` and `facts.json` (this change adds `filmstrip.jpg`, whose name `spec.FILMSTRIP_FILENAME` already
  reserves). Its CLI is `auto-reel proxies <root>` with `--years`/`--layout`/`--device`/`--jobs`. The cache is
  derived state, never Postgres, not a staleness input. The locked proxy shape is H.264, `-bf 0`, a keyframe
  every **half second** (`round(0.5 x fps)` frames, `-sc_threshold 0`; E1's result), AAC.
- **The proxy is the sprite's only input.** Research X7: from the proxy's keyframes the sprite costs 0.04 to
  0.25 s per 25 s clip (100 to 250 x real time, independent of source size); from the source it costs 1.2 to
  10 s wall and 2.3 to 66 CPU-s (`v2/proxies/results_film.json`, `v2/proxies.md` section 3.8). Building proxy
  and sprite in one ffmpeg run saved nothing (`results_onepass.json`: 2.2 s vs 2.3 s), so two steps keep the
  artifacts independent.
- **Subprocess rule.** All ffmpeg/ffprobe calls go through `FfmpegRuntime` (Principle VI), like `thumbs/`.
- **Dev-host ffmpeg is 8.1.2**; the engine asserts >= 7.1.

### Gate contract (reconciled at apply)

What the merged code offers and this change uses, by name: `ProxyEntry` (`key`, `directory`, `proxy_path`,
`facts_path`, `facts`); `lookup_proxy(clip, settings=)`; `spec.FILMSTRIP_FILENAME`, `spec.FACTS_FILENAME`,
`spec.PROXY_PROBE_TIMEOUT_S`; `cache.new_part_dir(cache_dir, key)` (creates the cache directory, sweeps it once,
makes a hidden `.<key>.<uuid>.part` directory), `cache.discard`, `cache.is_full_disk`; `ProxyCacheError` for
anything wrong with the cache directory; in the CLI, `_proxies_event`'s per-entry grouping (symlinks to one clip
share one entry) and its `lookup_proxy` / `ensure_proxy` split. Differences from what the first draft assumed:
the GOP is half a second, not one; `read_facts` validates `facts.json` strictly but ignores unknown keys, so a
`filmstrip` member does not disturb it; the stale-build sweep removes only hidden **directories** named
`.<64 hex>.<32 hex>.part` in the cache directory, so the sprite is built in such a directory and not in a loose
file inside the entry; `--prune` does not exist (the sweep is automatic).

## Goals / Non-Goals

**Goals:**
- A sprite for every proxied clip, including clips of one second or less, with tile count and geometry exact
  and recorded.
- The first task reproduces the C0047-like failure and pins it as a regression test.
- Idempotent, atomic, cheap to re-run; a sprite change never re-encodes a proxy.

**Non-Goals:**
- Serving the sprite over HTTP (`proxy-media-endpoints`), generating it as a job (`proxy-job`, which will also
  want cancellation of this step), drawing it (`timeline-view`). No API, WebSocket, DB or web change.
- A second image format (WebP saves 17 % at the same quality; not worth two formats, X7), a configurable tile
  size (a constant until a real need), a waveform lane (decided out of v2).
- Negative caching of failed sprites (the retry costs about 0.2 s).

## Research & Decisions

### Why C0047 failed, and what the `fps` filter really breaks
**Context**: the proxies research reported one failure in 25 clips: a 0.48 s, 12-frame clip, whose sprite step
"produced no file, cause not isolated" (`v2/proxies/event.log`; synthesis section 6 risk 6). The report's guess
was "`fps=1` leaves no frame" for clips under 1 s, with the remedy "skip below 1 s" (35 clips in the archive).
**Explored**: reproduced on ffmpeg 8.1.2 (scratch `verify/v2/filmstrip-sprites/exp/grid.py`) with synthesized
H.264 clips at the **merged** proxy shape (`-bf 0`, `-g round(fps/2)`, `-sc_threshold 0`), the research
command `-skip_frame nokey ... fps=1 ... tile` and its `eof_action=pass` variant. "Want" is `ceil(duration)`:

| clip | keyframes | `fps=1` | `fps=1:eof_action=pass` | want |
|---|---:|---:|---:|---:|
| 0.04 s (1 frame) | 1 | **0** | 1 | 1 |
| 0.48 s (12 frames, C0047) | 1 | **0** | 1 | 1 |
| 1.00 s | 3 | 1 | 1 | 1 |
| 1.04 s | 3 | 1 | **1** | 2 |
| 1.52 s | 4 | 1 | 2 | 2 |
| 2.52 s | 6 | 2 | 3 | 3 |
| 25 s at 25 fps | 53 | 25 | 25 | 25 |
| 12 s at 50 fps | 24 | 12 | 12 | 12 |
| 25.025 s at 29.97 fps | 50 | 25 | **25** | 26 |
| 30.03 s at 29.97 fps | 60 | 30 | **30** | 31 |

With zero frames out, mjpeg is opened without a picture and ffmpeg exits 234 ("Error while opening encoder",
"Nothing was written into output file"), which is the research's "no file". So the failure is a property of the
`fps` filter and a clip with a single keyframe, not of clip length as such; the `eof_action=pass` variant, which
the first draft of this design relied on, fixes the zero-frame case and the shorter-by-one cases but not the
clips whose last slot falls in a tail shorter than a keyframe gap (1.04 s, 25.025 s, 30.03 s): there the `fps`
filter's end-of-stream rounding still drops the final tile, silently. Chasing that with filter options means
depending on rounding behaviour that differs between shapes.
**Decision**: stop asking a filter to resample and choose the frames ourselves: list the proxy's keyframes,
pick for each slot the latest keyframe at or before it, and `select` exactly those. Tile count is
`ceil(duration / interval)`, minimum 1.
**Rationale**: the count and the content of every tile are exact by construction and testable (the test clips
carry their own timestamp in their luma, so each tile can be read back), a single-keyframe clip needs no special
code path, and nothing depends on how a filter rounds. Skipping sub-second clips (the research's suggestion) was
rejected: it would add a "no filmstrip" state that `proxy-state-read`, the media endpoints and the timeline
would each need to handle for 35 clips of 3,000, and the timeline wants a strip on every clip. The one-tile
sprite of a 0.48 s clip shows its first frame; its D-11 thumbnail (taken at 25 %) remains the poster. Nothing is
invented: the tile is a real decoded frame of that clip.

### Tile count, interval and geometry
**Context**: research spec: 90 px tile height, one tile per second, at most 120 tiles, 10 columns, JPEG q5
(`v2/proxies.md` section 3.8; synthesis section 3 table row "Filmstrip").
**Decision** (constants in `proxies/filmstrip.py`):
```python
FILMSTRIP_VERSION = 1
TILE_HEIGHT, COLUMNS, MAX_TILES, JPEG_QSCALE = 90, 10, 120, 5

def plan(duration: float, width: int, height: int) -> FilmstripPlan:
    interval = max(1, math.ceil(duration / MAX_TILES))          # whole seconds
    tiles = max(1, math.ceil(duration / interval))              # <= 120
    tile_w = max(2, round(TILE_HEIGHT * width / height / 2) * 2)  # even; 160 for 16:9, 50 for 9:16
    columns = min(COLUMNS, tiles)
    return FilmstripPlan(interval, tiles, tile_w, TILE_HEIGHT, columns, math.ceil(tiles / columns))
```
Tile `k` is the latest keyframe at or before `k x interval` seconds (the first keyframe when none is at or
before, which only `k = 0` can meet), placed at column `k % columns`, row `k // columns`. A 62-minute clip
(3,720 s) gets interval 31 s and 120 tiles. `math.ceil` of an exact multiple is exact (a 120.0 s clip is 120
tiles at 1 s; 120.5 s is 61 tiles at 2 s). `duration` is the proxy's **video-stream** duration, as `ffprobe`
prints it to the microsecond; the container duration is up to 21 ms longer (AAC priming, `proxies/facts.py`) and
would turn a 25.000 s clip into 26 tiles.
**Rationale**: slot `k` covers the instant `k x interval`, so tile `k` shows what is on screen at that instant
to within one GOP (half a second); with `k x interval < duration` for every tile, each slot has a frame at or
before it. Width follows the proxy's displayed shape (the proxy has display rotation and SAR applied, so its
stored width/height are the displayed ones); a mixed grid never occurs because a sprite is per clip.

### The emitted ffmpeg arguments
CPU only; no hardware path exists or is needed (a 540p keyframe decode costs 0.04 to 0.25 s per 25 s clip, so
the CPU fallback of Principle III *is* the path). For a 16:9 proxy of 2.5 s (3 tiles):
```
ffmpeg -hide_banner -nostdin -v error -y
  -skip_frame nokey -i <entry>/proxy.mp4 -map 0:v:0 -an -sn -dn
  -vf select=eq(n\,0)+eq(n\,2)+eq(n\,4),scale=160:90:flags=bicubic,tile=3x1:nb_frames=3
  -frames:v 1 -c:v mjpeg -q:v 5 -f image2 -update 1 <build>/filmstrip.jpg
```
`n` counts the frames that survive `-skip_frame nokey`, that is the proxy's keyframes in order, so the
ordinals come straight from the keyframe list. `tile=...:nb_frames=<tiles>` closes the grid at the planned
count. `-update 1` writes the output path literally, as `thumbnail_args` does. The golden-argument unit test
asserts the list for 16:9, portrait (`scale=50:90`) and a 3-tile clip.
**Source of keyframes, duration and shape**: the step runs two `ffprobe` calls on the finished `proxy.mp4`
through `FfmpegRuntime.with_timeout(PROXY_PROBE_TIMEOUT_S)`: the first for the first video stream's width,
height and duration; the second for `packet=pts_time,flags` of that stream (an index read, no decode: 0.17 s
for 900 s of 540p; the keyframes are the packets flagged `K`). Tile times are in proxy time, which is what the
timeline plays. A probe that fails, a duration that is not positive and finite, a keyframe without a time, or no
keyframe at all raises `FilmstripError` (never a default, Principle I).
**Keyframes too far apart**: if two tiles would need the same keyframe (a proxy with a keyframe gap longer than
`interval`, which the half-second GOP rules out except for a variable-frame-rate clip with a pause), `select`
could not repeat a frame and `tile` would pad with black. That is refused with a `FilmstripError` that names the
tile instead. The first thing to look at if a real clip meets it is whether to repeat the keyframe.

### Where the record lives and how it is written
**Decision**: `filmstrip.jpg` and a `filmstrip` object in the entry's `facts.json`:
```json
"filmstrip": {"version": 1, "tiles": 25, "interval": 1, "columns": 10, "rows": 3,
              "tile_width": 160, "tile_height": 90, "width": 1600, "height": 270, "bytes": 96412}
```
Write order: (1) `cache.new_part_dir(cache_dir, entry.key)` makes the cache's own hidden build directory
`.<key>.<uuid>.part`, and ffmpeg writes `filmstrip.jpg` there; (2) verify: `ffprobe` finds one `mjpeg` stream
whose size is `columns * tile_width` x `rows * tile_height`, and the file is non-empty; (3) `fsync`, `os.replace`
into the entry as `filmstrip.jpg`; (4) read `facts.json`, set `filmstrip`, write a copy in the build directory,
`fsync`, `os.replace` over the entry's `facts.json`; (5) the build directory is removed. The build directory
and the entry share the cache directory, so both renames are on one filesystem. `facts.json` is read-modify-
write: every other key is preserved, an unreadable or non-object `facts.json` raises (a sprite never repairs or
invents the proxy's facts).
**Rationale**: the JPEG lands before the record, so a reader that sees `filmstrip` in `facts.json` can rely on
the file. A crash between (3) and (4) leaves a `filmstrip.jpg` that nothing refers to; the next run rebuilds
it. A killed step leaves only a hidden `.part` directory, which the cache's existing stale-build sweep removes
after a day, exactly as for a killed encode; nothing new to sweep.

### Idempotency and versioning
**Decision**: `lookup_filmstrip(entry)` returns the recorded `Filmstrip` (one `stat`, one JSON read, no ffprobe,
no ffmpeg) when `facts.json` has `filmstrip.version == FILMSTRIP_VERSION` and `filmstrip.jpg` exists with
`bytes` equal to the recorded size, else `None`. `ensure_filmstrip(clip_path, entry, *, runtime)` returns it, or
builds one (`generated=True`). `FILMSTRIP_VERSION` is **not** in the proxy key, so bumping it rebuilds sprites
(about 0.2 s each; the whole archive of about 17,000 clips takes about an hour) from the proxies already on disk
and never re-encodes one. A `--force`-like switch is not added: delete the entry's `filmstrip.jpg` or bump the
version. A worker restart or a second `proxies` run mid-way repeats only the clips without a recorded sprite.
Two writers racing on one entry both produce the same bytes and both `os.replace` atomically; sprites need no
lock of their own.

### Failure behaviour
**Decision**: `FilmstripError(clip, reason)` (a sibling of `ThumbnailError`, in `errors.py`, subclass of
`EngineError`) for a failed probe, a non-positive duration, keyframes that cannot give every tile, an ffmpeg
failure (the reason carries the command and stderr), a verify mismatch or an unreadable `facts.json`. A cache
directory that cannot be written, or a full disk, is `ProxyCacheError` (the cache's fault, not the clip's), as
in `ensure_proxy`. A sprite failure **never** deletes or invalidates the proxy: the entry is then "proxy ready,
no filmstrip", the build directory is removed, and `facts.json` is untouched. Failures are not remembered.
Consumers decide what to show for a proxy without a filmstrip.
**Rationale**: the proxy plays without the sprite; throwing it away would cost minutes to save a 100 KB file.

### CLI
**Decision**: in `_proxies_event`, after a distinct entry is found cached or generated, call
`ensure_filmstrip` (inside the same pool slot as its proxy; for an already cached entry it is submitted to the
pool too). A clip whose proxy failed gets no sprite attempt and counts in neither sprite figure. Per event the
line gains `filmstrips: <g> generated, <c> cached, <f> failed`; a failed sprite prints exactly one
`ERROR  <event>/<clip>: <cause>` line (the same one-line cause rule as proxies and `thumbs`); the final summary
gains the totals; the exit code is non-zero when any proxy or sprite failed. Symlinks to one clip share one
entry and one sprite, counted as for proxies (the first generated, the others cached). Per-event isolation
holds: a failed sprite does not stop the run; a `ProxyCacheError` stops it as for proxies.

## Risks / Trade-offs

- [Keyframe gap longer than `interval`] -> refused loudly, see above; the half-second GOP makes it a
  variable-frame-rate edge case, and a test pins the refusal.
- [The ordinal of the packet flagged `K` differs from the ordinal of the frame `-skip_frame nokey` yields] ->
  both come from the same proxy; a test reads each tile back by its luma and fails on any off-by-one, and the
  dogfood task checks the real proxies of the sample clips.
- [A 62-minute proxy decodes about 7,200 keyframes] -> about 30 s; the step is bounded by a generous timeout
  and is the job's work, not a request's.
- [HDR or wide-gamut sources] -> already SDR in the proxy (`proxy-encode` tone-maps on the CPU path); the
  sprite never sees the source.
- [`facts.json` read-modify-write races with a proxy rewrite] -> the sprite only runs on a finished entry; a
  rewritten proxy (new key) is a new entry directory, so the old one is orphaned, not edited.

## Migration Plan

None: new files in a derived cache, additive `facts.json` key, no schema, no rescan. Rollback = ignore the
files; entries made by `proxy-encode` alone remain valid (no `filmstrip` key means "not built", and the next
`proxies` run builds it).
