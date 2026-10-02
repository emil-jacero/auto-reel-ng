## Why

Three gaps in the clip-thumbnail cache (D-11, HLD §4.10, phase 8 GUI v1), all confirmed on main f19e24f and
re-checked against the code:

1. **An HDR clip's thumbnail is range-clipped, not tone-mapped.** `thumbnail_args` emits only
   `scale=…,scale=…,setsar=1` into `mjpeg`. A PQ or HLG clip (`ClipMetadata.is_hdr`, set from `smpte2084` /
   `arib-std-b67`) reaches the encoder in its HDR signal range, so the picture is washed out or crushed. The
   renderer already tone-maps the same clips on the CPU (`CPU_TONEMAP_FILTER`, `render/normalize.py`), so the
   GUI shows a thumbnail that does not look like the movie. Reproduced here with a tagged HLG clip: the
   plain chain succeeds and writes a 5.7 KB frame in the HDR range, the tone-mapped chain writes a 4.4 KB
   one. The surveyed archive is still entirely SDR, so no operator sees this today.
2. **A full cache disk fails once per clip.** `_create_temporary` creates an empty file, which needs no data
   block and so succeeds on a full disk. The error only appears inside ffmpeg (`Error submitting a packet to
   the muxer: No space left on device`), is classed as that clip's `ThumbnailError`, and `auto-reel thumbs`
   reports a "no frame extracted" `ERROR` line for every remaining clip and keeps running; the service
   answers each request with a clip-failure `502`. Only `_finalize`'s `OSError` is classed as a cache error.
   Observed: ffmpeg writing to `/dev/full` prints exactly that stderr and exits non-zero.
3. **Stale hidden temporaries are never removed.** A `SIGKILL`, OOM kill or power loss during extraction
   leaves `.<key>.<hex>.tmp` in the cache directory. `thumbnail_for`'s `except BaseException` cannot run, and
   nothing else lists the directory, so the files stay forever.

Principle I (name the real cause once; a clip is not at fault for a full disk) covers 2, Principle IV's
spirit (a key must mean one picture) covers 1, and D-11's "derived state, rebuildable" covers 3.

## What Changes

- **HDR clips are tone-mapped.** For a clip the probe flags `is_hdr`, the `-vf` chain starts with the
  engine's CPU HDR to SDR chain, then the existing scales. SDR clips emit the arguments they emit today. The
  probe is the one `thumbnail_for` already runs on a cache miss, so a cache hit stays free of ffprobe.
- **`THUMBNAIL_VERSION` is bumped once** (to the value after `thumbs-cache-key-and-count`, plus one), so a
  range-clipped HDR picture cached earlier is never returned. Triage proposed an `hdr` flag in the key
  payload for HDR clips only, to leave SDR keys alone; that is not possible, because the key is computed
  before any probe and a hit must not probe (see design, "Why a version bump and not an `hdr` key flag").
  Every clip regenerates once; older files are orphaned and stay (D-11: never evicted).
- **A full disk is a cache error.** An ffmpeg failure whose stderr says `No space left on device` (or
  `Disk quota exceeded`) raises `ThumbnailCacheError` naming the cache directory, with the temporary file
  removed, instead of the clip's `ThumbnailError`. The CLI and the service already stop and report a cache
  error once, so neither changes.
- **Stale temporaries are swept.** The first time a process makes sure a cache directory exists
  (`auto-reel thumbs` and `auto-reel serve` both do, through `thumbnail_for`), temporaries named like the
  engine's own (`.<key>.<hex>.tmp`) and older than one day are deleted. Younger files, `<key>.jpg` files and
  other names are never touched. The sweep never raises.
- Tests: golden arguments for SDR (unchanged) and HDR, a probe-driven `thumbnail_for` test, a real-ffmpeg
  tagged HLG clip, the `/dev/full` stderr classified, and sweep tests with old and young files.

Rendered output and the staleness fingerprint do not change: thumbnails are not part of a render, so
`RENDER_GRAPH_VERSION` is not bumped. No `reel.yaml` or `config.yaml` schema change, no Alembic migration, no
rescan. The thumbnail route's `ETag` is the cache key and changes once with the version bump. Only
`thumbs/` is edited; the CLI and the API use `thumbnail_for` and `ThumbnailCacheError` as they do now.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `clip-thumbnails`: an HDR clip is tone-mapped (a modified extraction requirement plus one added
  requirement), a full cache disk is a cache error, and stale temporaries are swept (two added
  requirements).

## Impact

- `auto_reel_ng/thumbs/thumbnail.py` (`thumbnail_args`, `thumbnail_for`, `_probe_duration`, `_extract`,
  `_create_temporary`, `THUMBNAIL_VERSION`, a new `sweep_stale_temporaries`) and `thumbs/__init__.py`
  (export).
- `tests/test_thumbs.py` (including its `probe_calls` fixture), `tests/test_thumbs_ffmpeg.py`.
- `docs/high-level-design.md` D-11 gains a dated sub-bullet.
- One package (`thumbs/`), reaching `accel/profiles/cpu.py` for one constant; neither CLI nor API code
  changes.
- **Ordering.** Gate change `thumbs-cache-key-and-count` (rewrites `thumbnail_key` and bumps
  `THUMBNAIL_VERSION` to 2, edits the "cached outside the library" requirement) merges first, and so do its
  own gates `ffmpeg-runtime-utf8-and-timeout` (edits `thumbnail_for` and `_extract`: a bounded runtime view,
  `FfmpegTimeoutError`, no `UnicodeDecodeError` branches) and `cli-project-context-module`. This change is
  written against main after all three (merged). It adds new requirements instead of modifying that cached
  requirement, so the two deltas cannot collide at archive time; tasks name functions, not lines.

## Non-goals

- Tone-mapping on the GPU, or a thumbnail look that differs from the render's. The thumbnail uses the same
  CPU chain; speed is not a concern for one frame.
- Guessing the colour tags of an HDR clip that lacks them. See design, "An HDR clip with missing tags".
- Dolby Vision profile handling, HDR10+ metadata, or an HDR badge in the GUI.
- A free-space floor check before extracting, or a config key for the sweep age (Principle VII: the
  extraction's own error is the evidence, the age is a module constant).
- Sweeping `.reel.yaml.<hex>.tmp` files left by `reel/writer.py` in event folders. That would write into the
  library from a read path (the library may be mounted read-only), and the triage plan scoped this change to
  `thumbs/`. Left as a known residual for a separate change.
- Evicting orphaned `<key>.jpg` files (D-11: never evicted in v1).
- Retrying a failed extraction, or resuming the run after a cache error.
