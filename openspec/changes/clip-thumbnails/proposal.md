## Why

On 2026-09-30 the operator asked: "add thumbnails to the clips — not the first frame but some percentage
into the clip". A clip row today shows only a camera file name (`s1710001.mp4`), which says nothing about
what is in the clip. GUI v1 exists to reorder clips (slice D, HLD §4.10), and that is where the missing
picture hurts. The first frame is a poor choice: a camera clip often opens on a lens cap, the ground or a
fade, so the frame comes from a fraction of the clip's duration instead.

HLD §4.10 places "thumbnails/poster frames" in GUI v2, and §8.11 lists proxy and thumbnail generation as
research. The operator approved pulling **clip thumbnails** (not proxies, not scrubbing) into this round.
This change records that as the new locked decision **D-11** (HLD §7). It belongs to **HLD §6 phase 8
(GUI v1)**. The §8.11 item is resolved for single-frame clip thumbnails by this design's measurements;
proxies and scrubbing stay open for v3.

The house pattern is engine and CLI first, then API, then screen (Principle V). This change is the engine
half. `clip-thumbnail-endpoint` (T2) serves its output over HTTP, and `clip-thumbnails-screen` (T3) shows
it. Two §2 learnings bind the extraction:

- **#5, never fabricate:** the frame time comes from the engine's real ffprobe duration and is never
  guessed. A clip that cannot give a frame at that time has no thumbnail and is reported. No other
  timestamp is tried in its place.
- **#6, rotation and SAR:** a phone clip held upright stays portrait, and an anamorphic clip is not
  squashed.

Thumbnails are derived state (D-7), so they live in a rebuildable file cache and never in `reel.yaml` or
Postgres. The cache is **outside the library**, because the MOL archive is a flaky USB NTFS drive that is
often mounted read-only.

## What Changes

- **New engine package `auto_reel_ng/thumbs/`:**
  - `thumbnail_for(clip_path, *, position, cache_dir, runtime=None) -> Path` returns the cached JPEG, and
    generates it first if it is absent
  - `thumbnail_path(...)` gives the same path without generating anything, and lets the stat's `OSError`
    through unchanged; each caller handles it
  - the frame is taken at `position × duration`, where the duration comes from `probe/`
  - extraction runs through the `ffmpeg/` runtime: input seek, one frame, CPU decode
  - the frame is SAR-corrected and scaled to fit inside **320×180**, keeping its aspect ratio, then
    written as a JPEG to a literal path (`-update 1`, so a `%` in the cache path is not a pattern)
  - the file is written atomically (a temporary file, then `fsync` and rename)
  - the source clip is only read
- **Cache key:** sha256 over the resolved clip path, its size and `mtime_ns`, the position, the box and
  `THUMBNAIL_VERSION`. The file is `<key>.jpg`. A changed clip therefore gets a new thumbnail, and a
  cache hit never runs ffprobe or ffmpeg.
- **New errors in `errors.py`:**
  - `ThumbnailError`: this clip cannot give a thumbnail. It covers a probe failure, no usable
    duration, and ffmpeg failing or producing no frame, and it names the clip and the cause.
  - `ThumbnailCacheError`: the cache directory cannot be created or written. It names the directory.
    This is not a property of the clip, so the CLI stops on it and the API reports it apart.
- **Two optional `config.yaml` keys (D-2):**
  - `thumbnails.position`: a number with 0 < p < 1, default **0.25**
  - `thumbnails.cache_dir`: an absolute path (`~` is expanded). The default is
    `$XDG_CACHE_HOME/auto-reel/thumbnails/`, or `~/.cache/auto-reel/thumbnails/` when that is unset.
  - the chosen directory, configured or default, must lie outside the project root and outside its
    `input` directory
  - a wrong value raises `ConfigError`
  - `ProjectConfig` gains one opaque `thumbnails` map, like `worker` and `api`, and
    `thumbs.resolve_thumbnail_settings` validates it
- **Package exports:** `auto_reel_ng/thumbs/__init__.py` exports `thumbnail_for`, `thumbnail_path`,
  `resolve_thumbnail_settings` and `ThumbnailSettings`, the names T2 imports.
- **New CLI subcommand `auto-reel thumbs <root> [--years] [--layout] [--jobs N] [-v]`:**
  - walks the layout like `scan`, honouring `--years`, `--layout` and `.reelignore`
  - makes a thumbnail for every clip that discovery lists on disk: root clips and chapter
    subfolders, IGNORED clips included, `original/` debris excluded
  - never reads or writes `reel.yaml`, so a MISSING clip, which is not on disk, is never requested
  - skips cached thumbnails
  - runs up to `N` extractions at once (default **2**)
  - prints one line per event, one `ERROR` line per failed clip, and a summary with counts
  - exits non-zero when any clip or event failed
  - writes nothing under the project root
- **HLD:**
  - adds **D-11** to §7
  - §4.10: clip thumbnails move from the v2 bullet to v1, and the slice plan gains one D-11 sentence
    naming `clip-thumbnail-endpoint` as the extra `api/` prerequisite
  - §4.7: the "Postgres index" sentence no longer lists thumbnails
  - §6: phase 9 drops "thumbnails"
  - §8.11 is narrowed to proxies and scrubbing
  - README's CLI list gains `thumbs`

## Non-goals

- **Editorial `rotate` applied to thumbnails.** Only the container's display rotation is applied, as
  ffmpeg does by default.
- **HDR tone mapping.** An HLG or PQ clip is converted to 8-bit JPEG without a tone map, so its colors
  look flat. The archive surveyed is all SDR.
- **Poster or cover images for events**, and anything on the event list.
- **Hover scrubbing, proxies and HLS** (v3, §8.11).
- **Black or frozen frame avoidance.** It comes later, with the analysis review.
- **Cache eviction and a size cap.** The measured cost is about 15 KB per clip, so ≈100 MB for the
  archive's 6,538 clips, and still only ≈130 MB at 20 KB per clip. Deleting the directory is the reset.
- **GPU decode**, a configurable box or format, and a `--force` flag. A changed clip gets a new key by
  itself, and a changed extraction bumps `THUMBNAIL_VERSION`.
- **Negative caching.** A failed clip is retried on the next run.
- **An extraction timeout.** `FfmpegRuntime.run` has none, and adding one is an `ffmpeg/` change. A read
  blocked on a stalled drive holds one worker until it returns (design, Risks). T2 points its hang risk
  here, and this is the answer: a follow-up in `ffmpeg/` after measuring extraction on the real drive.
- **The HTTP route (T2) and the screen (T3).**

## Capabilities

### New Capabilities

- `clip-thumbnails`:
  - the frame position rule
  - the extraction contract: fit, rotation and SAR, JPEG, source only read
  - the cache location, key, atomic write and no DB rows
  - the `thumbnails.*` settings and their validation
  - the typed failures

### Modified Capabilities

- `headless-cli`:
  - MODIFIED `Requirement: auto-reel entry point with subcommands`: it now lists ten subcommands, with
    `thumbs` added
  - ADDED `Requirement: thumbs fills the thumbnail cache without touching the library`

## Impact

- **Packages:**
  - new `thumbs/`: `settings.py` and `thumbnail.py`
  - `errors.py`: two classes
  - `config/project.py`: one opaque field
  - `cli/`: `main.py` for the parser, `commands.py` for `cmd_thumbs`
  - tests
  - `docs/high-level-design.md` and `README.md`
  - nothing in `api/`, `render/`, `staleness/`, `persistence/` or `web/`
- **CLI vs API (Principle V):** the CLI only. The engine operation lands with its CLI surface, and the API
  follows in T2.
- **Layers (Principle VI):**
  - `thumbs/` imports `probe/`, `ffmpeg/`, `config/` and `errors`, the same as `analysis/`
  - all subprocess work goes through `FfmpegRuntime.run`
  - no vendor name appears (Principle III): the extraction is CPU decode only, so there is no GPU
    profile to fall back from
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** The staleness fingerprint inputs are
  unchanged. Thumbnails are never an input, and `thumbs` writes nothing that a fingerprint reads.
- **Schemas:**
  - no `reel.yaml` change
  - **`config.yaml` gains the optional `thumbnails` map** (`position`, `cache_dir`). An existing file
    without it behaves as before.
  - **no Alembic migration**, no rescan
- **New third-party dependencies:** none. JPEG encoding is ffmpeg's `mjpeg` encoder, and `hashlib`,
  `concurrent.futures` and `os` are stdlib.
- **Size (Principle VIII):** one small engine package, one subcommand and one config field, in two
  capability deltas and 10 tasks. `api/` and `web/` are split out as T2 and T3.
  - The code spans `thumbs/` and `cli/`, plus `config/`. The `config/` edit is a single opaque field
    parsed by an existing helper, the same shape as `worker` and `api`.
  - The CLI subcommand must land with the engine operation (Principle V), so the three packages
    cannot be split further.
- **Dependencies (gate):** none. This change can start now. `clip-thumbnail-endpoint` (T2) is gated on
  this change. It uses `ThumbnailError`, `ThumbnailCacheError`, `thumbnail_for`, `thumbnail_path` and
  `resolve_thumbnail_settings`.
