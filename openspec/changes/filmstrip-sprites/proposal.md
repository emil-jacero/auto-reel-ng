## Why

The GUI v2 timeline (D-20) draws each clip as a strip of small frames so the operator can see where to cut
without scrubbing. The locked proxy contract (D-21, change `proxy-encode`) gives every clip a seekable 540p
H.264 proxy with a keyframe every half second; research item X7 (`v2/synthesis.md` §2; `v2/proxies.md`
§3.8) measured the cheap way to turn that into a filmstrip: **one JPEG sprite per clip, cut from the finished
proxy's keyframes** (0.04 to 0.25 s per 25 s clip, about 3.4 KB per footage second, about 0.65 GB for the
whole archive), against 1.2 to 10 s and up to 66 CPU-s when cut from the source.

The research run also found one real failure: clip C0047 (0.48 s, 12 frames, a single GOP) encoded its proxy
and then produced no sprite, and 24 of 25 clips passed in the 2020 event batch (`v2/proxies/event.log`,
synthesis section 6 risk 6, cause "not isolated"). This change reproduces it on ffmpeg 8.1.2 against the
contract as merged (`-bf 0`, a **half-second** GOP: `proxy-encode` locked that after the research) and fixes
it. The cause is not "sub-second clips" but the `fps` filter, which hands the encoder zero frames when a clip
has a single keyframe (ffmpeg then exits 234, "Nothing was written into output file") and, on the shapes
measured here, also loses the **last tile** of clips whose tail is shorter than a keyframe gap (a 1.04 s clip
gets 1 tile, a 25.025 s clip 25 instead of 26). A sprite with the wrong tile count must not be recorded as a
filmstrip (Principle I), so the tiles are chosen from the proxy's own keyframe list, the geometry is exact
and verified, before the timeline (D-20, HLD section 6 item 9) and the proxy job build on it.

## What Changes

- New `proxies` module code: a sprite step that runs **after** `ensure_proxy` on the finished `proxy.mp4`
  and writes `filmstrip.jpg` into the same cache entry. Tiles are 90 px high (160 x 90 for 16:9, 50 x 90 for
  a 540x960 portrait), 10 columns, one tile per `interval` seconds where `interval = max(1, ceil(duration /
  120))`, so a clip never has more than 120 tiles; JPEG `-q:v 5`; decoded from keyframes only
  (`-skip_frame nokey`). `duration` is the finished proxy's **video-stream** duration.
- **Fix of the one-failure case.** Tile `k` is the latest keyframe of the proxy at or before `k x interval`
  seconds, chosen from the proxy's keyframe list (one `ffprobe` over the packets) and cut with an explicit
  `select` of those keyframes, not with the `fps` filter. The tile count is `ceil(duration / interval)`,
  never fewer than 1. A clip of 1.0 s or less therefore gets a **one-tile sprite showing its first frame**; no
  clip is skipped and no clip has a placeholder. The count is exact by construction, so there is no silent
  black padding; a proxy whose keyframes are too far apart to give every tile its own fails loudly.
- The tile geometry is recorded in the entry's `facts.json` under a `filmstrip` object (tile size, columns,
  rows, tiles, interval, sprite size, `FILMSTRIP_VERSION`), written after the JPEG, both atomically
  (built in the cache's hidden `.part` directory, verified, renamed into the entry). The timeline reads the geometry from there and never recomputes it.
- `FILMSTRIP_VERSION` is a module constant. A bump rebuilds only the sprites, from the existing proxies; it
  is not part of the proxy key, so the 40 GB of proxies are never re-encoded for a sprite change.
- `auto-reel proxies <root>` also makes the sprite of every clip whose proxy is ready (generated or already
  cached), reports sprite generated / cached / failed counts, and exits non-zero when a sprite failed.
- HLD notes (a task): D-21 gains the sprite sub-bullet and the fix; D-20 gains the one-line statement that the
  timeline's filmstrip is read from `facts.json`; the sub-second rule and the `fps`-filter cause are recorded.

**Unchanged by design:** rendered output (no `RENDER_GRAPH_VERSION` bump), the staleness fingerprint and its
inputs, `reel.yaml` / `config.yaml` schema (no new setting: the tile spec is a constant, Principle VII), the
proxy key and `PROXY_VERSION`, Postgres (no migration, no rescan), the HTTP API and OpenAPI schema (no web
type regeneration; serving the sprite is `proxy-media-endpoints`, scheduling it is `proxy-job`).

## Capabilities

### New Capabilities

- `clip-filmstrips`: the sprite of a proxied clip: tile geometry, the tile-count rule including clips of one
  second or less, keyframe-only extraction from the finished proxy, the `facts.json` record, atomic write,
  idempotent rebuild by `FILMSTRIP_VERSION`, and what a sprite failure leaves behind.

### Modified Capabilities

- `headless-cli`: `proxies` (added by `proxy-encode`) also makes the sprites and reports their counts. The
  delta is an ADDED requirement, because the `proxies` requirement is not in the main specs until the gate
  merges.

## Impact

- Packages: `proxies/` (new `filmstrip.py`; `errors.py` gains `FilmstripError`) and `cli/` (the `proxies`
  command's per-clip step, summary and exit code). No change to `ffmpeg/`, `accel/`, `render/`,
  `staleness/`, `persistence/`, `scheduler/`, `api/` or `web/`.
- Gate: `proxy-encode` has merged. This change uses its `auto_reel_ng/proxies` package: `ProxyEntry`
  (`directory`, `facts`), `lookup_proxy`, the cache entry layout (`proxy.mp4`, `facts.json`, and
  `spec.FILMSTRIP_FILENAME`, which it reserved), the cache's `new_part_dir` / `discard` / stale sweep,
  `ProxyCacheError`, and the `proxies` command's per-event loop. Reconciled in the design ("Gate contract").
- No new dependency (ffmpeg through `FfmpegRuntime`, `json` from the standard library). Complexity added
  (Principle VII): one module, one constant, one error class; no setting, no table, no second image format.
- Size: about 3.4 KB per footage second (a 25 s clip about 100 KB), about 0.65 GB for the archive, inside the
  40 to 50 GB proxy disk decision; nothing is evicted in v2.
