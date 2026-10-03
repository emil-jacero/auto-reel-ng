## Why

GUI v2's timeline editor (HLD §4.10) must scrub, step and trim inside a clip. The v2 research
(`research/v2` proxies, PCM-audio and timeline reports, 2026-10-02) measured that the **originals cannot
do that**: a random seek in the archive's own files takes a median 78 to 1457 ms, a held scrub shows 1 to 12
frames per second, and Firefox plays none of the Sony PCM audio that makes up 47 % of the archive's hours
(HLD D-16). A small derived **proxy** fixes all three. At 540p, H.264, a half-second GOP and AAC audio, a
seek is 17 to 30 ms, a scrub runs at a median 41 to 44 frames per second (E1), and every one of 22 sample
originals plays with picture and sound in Chrome, Firefox and WebKit.

This change is the **engine half** of the proxy work (Principle V): produce one proxy per clip into a
cache outside the library, check it, and describe it (`facts.json`). It belongs to **HLD §6 phase 9 (GUI
v2)** and records the locked decision **D-21**, the proxy contract (the research calls it D-19; D-18 and D-19
are taken by the bug round). Two house rules from HLD §2 bind it:

- **#5, never fabricate** (Principle I). The research found a silent wrong output: GPU rotation of an HEVC
  clip produced a picture with SSIM 0.47 and no error. A proxy is therefore **verified** (streams,
  dimensions, duration, frame count) before it is published, and a hardware path that fails or fails the
  check is redone on the CPU.
- **#6, rotation and SAR.** A phone clip held upright stays portrait, and an anamorphic clip is not
  squashed: the proxy has square pixels and the display rotation applied.

The clip's duration, frame rate and dimensions are not available to the API without a probe (HLD §4.9 keeps
reads probe-free). The proxy run already probes each clip, so it writes them to `facts.json` beside the
proxy, and later changes read that file with a `stat` and a JSON read.

Gate: **E1** (`proxy-shape-recheck`, the experiment that fixes the GOP length and the B-frame count on the
final browsers). E1 has run. G1 passes for all three shapes it measured, but `-bf 2` with a one-second GOP clears the scrub gate by
only about 1 fps and Panasonic 1080p50 (about 24 % of the archive) stays below 30 fps on both one-second shapes. The
supervisor therefore locked the one measured shape that clears every source in both browsers: **`-bf 0` and a
half-second GOP** (scrub 40.8 / 44.1 fps, step p90 about 30 ms, A/V 0 ms, about 46 GB for the archive).

## What Changes

- **New engine package `auto_reel_ng/proxies/`:**
  - `ensure_proxy(clip_path, *, settings, runtime, profile, render_node=None, on_progress=None,
    should_cancel=None)` returns the clip's cache entry and makes it first when it is absent. It reads
    no database, prints nothing and holds no global state, so a job can wrap it later (`proxy-job`).
  - `lookup_proxy(clip_path, *, settings)` returns the complete entry or `None` using only `stat` and a
    JSON read, for the read model (`proxy-state-read`).
  - A pure command builder gives the golden ffmpeg arguments per encode path: **hybrid** (hardware decode
    and scale, `hwdownload`, libx264) for an unrotated 8-bit H.264 or HEVC clip the profile decodes, and
    **CPU** (software decode, libx264) for everything else. A hybrid failure, or a hybrid output that fails
    verification, is redone once on the CPU.
  - The proxy contract (D-21): MP4 `+faststart`, H.264 High yuv420p, square pixels with the display
    rotation applied, short side 540 and never upscaled, x264 `veryfast` CRF 26, no B-frames (`-bf 0`), a keyframe
    every `round(fps / 2)` frames with no scene-cut keyframes, timestamps passed through, and AAC-LC 128 kb/s
    stereo from ffmpeg's **native** `aac` encoder (never `libfdk_aac`, the D-1 blocker).
  - Post-encode verification, `facts.json`, `PROXY_VERSION`, and the cache entry
    `<cache_dir>/<key>/{proxy.mp4,facts.json}`, built in a hidden `.part` directory and renamed whole.
  - `resolve_proxy_settings(config, project_root)`: the optional `proxies.cache_dir`
    (default `$XDG_CACHE_HOME/auto-reel/proxies`, else `~/.cache/auto-reel/proxies`), refused inside the
    library, like D-11.
- **New errors in `errors.py`:** `ProxyError` (this clip cannot give a proxy; carries `clip` and `reason`) and
  `ProxyCacheError` (the cache directory is unusable; a sibling, not a subclass, as with thumbnails).
- **`config/project.py`:** `ProjectConfig` gains one opaque `proxies` map, the shape of `thumbnails`.
- **New CLI subcommand `auto-reel proxies <root> [--years] [--layout] [--device] [--jobs N] [-v]`:** fills
  the cache for every clip on disk, like `thumbs`; idempotent; writes nothing under the project root; one
  line per event, one `ERROR` line per failed clip, a summary; non-zero exit when anything failed.
- **HLD and README:** D-21 in §7, notes in §4.10, §6 and §8.11, and the CLI and config lists in the README.

Not changed: **rendered output**. Proxies are a second artifact made beside the render, not a render
input. **No `RENDER_GRAPH_VERSION` bump**, and **no staleness fingerprint input** (Principle IV): no proxy
file, key or fact is read by `staleness/`, `render/` or the worker, and an editorial edit never invalidates
a proxy.

## Non-goals

- **The filmstrip sprite.** `filmstrip.jpg` is reserved in the entry layout but made by `filmstrip-sprites`,
  which also owns the sub-second tile rule (the C0047 failure). A proxy is complete without it.
- **A job, a queue, progress over the WebSocket, an enqueue endpoint.** `proxy-job`,
  `proxy-enqueue-endpoint` and `job-kind` own those. `ensure_proxy` only offers the progress and cancel
  callbacks they will use.
- **Any API route or state field** (`proxy-state-read`, `proxy-media-endpoints`) and any `web/` code.
- **Playing the original with sound in Firefox** (the virtual remux). The original stays silent there, with
  the existing D-16 note. No live transcode, no `<audio>` sidecar, no HLS.
- **A size cap, eviction, `--prune` of orphan entries.** The whole archive costs about 46 GB at this
  setting, planned at 50 GB; entries are immutable. A prune is the parked `proxy-prune`.
- **Hardware encoders for the proxy.** Pure VAAPI encode was 1.9 times bigger on 1080p50 and fails on legacy
  MPEG-4; the encode is always libx264.
- **A picture-similarity check (SSIM) after the encode.** The research's lowest CPU-path score (0.744, a
  rotated 720p phone clip) is unexplained, so no threshold can be set honestly. The ladder and the structural
  check stand in; see design, Risks.
- **Proxies for the `original/` folders.** Discovery skips them and so does this change.
- **New config keys beyond `proxies.cache_dir`.** Short side, CRF, GOP and audio rate are constants of the
  contract, hashed into the key; changing one is a code change plus a `PROXY_VERSION` bump (Principle VII).
- **Intel and NVIDIA hybrid paths.** Unverified; those hosts take the CPU path.

## Capabilities

### New Capabilities

- `clip-proxies`:
  - the proxy contract: container, video, audio, geometry, timestamps, sub-second clips
  - the encode path ladder and the CPU retry
  - post-encode verification
  - `facts.json`
  - the cache: location, key, entry layout, atomic publish, concurrency, stale-part sweep
  - the `proxies.cache_dir` setting
  - the typed failures, cancel and stall behaviour
  - no render, staleness or database involvement

### Modified Capabilities

- `headless-cli`:
  - MODIFIED `Requirement: auto-reel entry point with subcommands`: it now lists twelve subcommands, with
    `proxies` added
  - ADDED `Requirement: proxies fills the proxy cache without touching the library`

## Impact

- **Packages:**
  - new `proxies/` (settings, spec and key, command builder, facts and verification, `ensure_proxy`)
  - `cli/`: a new `proxies.py` for `cmd_proxies`, `main.py` for the parser, and the four output helpers
    that `thumbnails.py` already has move to a shared `cli/printing.py` unchanged
  - `errors.py`: two classes. `config/project.py`: one opaque field, parsed by the existing helper, the same
    shape as `thumbnails`. Principle VIII counts two packages, `proxies/` and `cli/`; the `config/` edit is
    one line and the `errors.py` edit is two classes, as with `clip-thumbnails`.
  - tests, `docs/high-level-design.md`, `README.md`
  - nothing in `api/`, `render/`, `staleness/`, `persistence/`, `scheduler/`, `ffmpeg/`, `accel/`, `probe/`
    or `web/`
- **CLI vs API (Principle V):** the CLI only. The engine operation lands with its CLI surface; the API
  follows in `proxy-state-read`, `proxy-media-endpoints` and `proxy-enqueue-endpoint`.
- **Layers (Principle VI):** `proxies/` imports `probe/`, `ffmpeg/`, `accel/`, `config/` and `errors`. All
  subprocess work goes through `FfmpegRuntime`. Nothing below `api/` imports `proxies/` except `cli/`. No
  vendor name appears in `proxies/`: the hardware path is chosen from the profile's decode fragment, its
  `can_hw_decode` answer and its frame location (Principle III), and a host with no usable accelerator
  encodes every proxy on the CPU.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** The staleness fingerprint inputs are
  unchanged.
- **Schemas:**
  - no `reel.yaml` change
  - **`config.yaml` gains the optional `proxies` map** (`cache_dir`). An existing file without it behaves as
    before.
  - **no Alembic migration**, no rescan, nothing in Postgres
- **New third-party dependencies:** none. ffmpeg, `hashlib`, `json`, `os`, `shutil` and
  `concurrent.futures` are all already in use.
- **Disk (measured, `research/v2`):** about 0.9 GB per footage hour; the whole archive (5,574 clips,
  52.1 h) about 46 GB, plan for 50 GB. Cache on the local disk, not on the USB library drive.
- **Size (Principle VIII):** one small engine package, one subcommand, two capability deltas, 10 tasks.
  The sprite, the job, the read model, the routes and every screen are separate changes.
- **Dependencies (gate):** E1 fixes the GOP length and B-frame count (constants only). `filmstrip-sprites`,
  `proxy-job`, `proxy-state-read` and `proxy-media-endpoints` build on this change: they import
  `ensure_proxy`, `lookup_proxy`, `ProxySettings`, `resolve_proxy_settings`, `ProxyError` and
  `ProxyCacheError`, and read `proxy.mp4` and `facts.json` from the entry directory.
