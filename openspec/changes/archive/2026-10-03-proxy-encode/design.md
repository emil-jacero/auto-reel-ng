## Context

See proposal.md, section Why. These code facts (at `8fb4d16`) and research facts shape the approach.

- **`thumbs/` is the model (D-11).** `thumbs/settings.py` resolves `thumbnails.cache_dir` (XDG default, refused
  inside the library by path and by identity). `thumbs/thumbnail.py` keys by the resolved file's name, size and
  `mtime_ns` plus a version, answers a hit with one `stat` and one hash, writes through a hidden temporary and
  `os.replace`, sweeps stale temporaries once per process, and keeps `ThumbnailError` (this clip) apart from
  `ThumbnailCacheError` (the directory). `cli/thumbnails.py` walks events, groups clips that share a target,
  runs a pool, and prints one line per event, one `ERROR` line per clip and a summary. This change follows each of
  those on purpose.
- **`probe/`.** `probe_media(path, *, runtime)` returns a `ClipMetadata`: `duration` (0.0 when ffprobe gave none),
  `fps` (average rate first), `video_codec`, `pix_fmt`, `width`/`height` (coded), `sample_aspect_ratio` (a string
  such as `16:15`, or `None`), `rotation` (degrees or `None`), `is_hdr`, `audio` (or `None`). It carries neither the
  container's `r_frame_rate` nor `nb_frames`, which the facts and the frame-count check need, so the run makes one
  more small ffprobe call of its own.
- **`ffmpeg/`.** `FfmpegRuntime.run_with_progress(args, *, duration, on_progress, stall_timeout, should_cancel)`
  streams `-progress`, kills on a stall (`FfmpegStalledError`, D-19) or a cancel (`FfmpegCancelledError`), and
  raises `FfmpegError` with the command and stderr otherwise. `with_timeout(seconds)` bounds `run` and
  `run_ffprobe`. All subprocess work stays here (Principle VI).
- **`accel/`.** `select_profile(inventory, override=…)` returns an `AccelProfile`. `profile.can_hw_decode(codec,
  pix_fmt)` is the per-clip answer (D-18), and `profile.fragment(OpClass.DECODE, OpParams(render_node=…))` returns
  the decode flags and where the frames then live. The VAAPI profile's decode flags already carry the named device
  (`-init_hw_device vaapi=va:<node> -filter_hw_device va -hwaccel vaapi -hwaccel_device va
  -hwaccel_output_format vaapi`). The profile's NORMALIZE fragment is **not** reusable: it uses
  `force_original_aspect_ratio=decrease`, which letterboxes a clip with a non-square pixel, and a proxy must scale to
  exact display dimensions (see "Encode paths").
- **`config/`.** `ProjectConfig` carries `worker`, `api` and `thumbnails` as opaque maps that their consumers
  validate. `proxies` is the fourth.
- **CLI.** `project_context(args)` loads `config.yaml` and enumerates events; `scan_event()` lists the clips on
  disk (root and chapter folders, no `original/`, no `.reelignore`d folder). `--device` selects an acceleration
  profile for `render`, `enqueue` and `worker`.
- **Research (`research/v2`, `proxies/`).** Every number in this document that is not from the repo comes from the
  proxies experiment: encode ladder (`results_final.json`, `final.log`), size and quality (`results_matrix.json`,
  `results_knobs.json`), browser latency (`res/seek_*_r2.jsonl`), frame accuracy (`res/acc_*.json`), disk budget
  (`results_budget.json`, `budget_derive.py`), two whole events (`results_event.json`), reference command builder
  (`mkproxy.py`). The research's own proxies report did not exist when the synthesis was written, so the contract
  below is the synthesis's section 3 (the supervisor's locked decisions), checked against those files.

## Goals / Non-Goals

**Goals:**

- One function, `ensure_proxy`, that turns a clip into a verified cache entry and is safe to call from a CLI
  thread, a service thread or a worker job.
- Golden-testable ffmpeg arguments for each encode path, with no GPU needed to test them.
- A hardware speed-up that can never produce a wrong proxy silently, and a CPU path that is always available.
- A cache entry whose `facts.json` lets later changes lay out a timeline without a probe.

**Non-Goals:**

- Anything the proposal lists as a non-goal: the sprite, the job, the API, the web code, eviction, a prune.
- A generic "derived media" cache shared with thumbnails. The two caches have different keys, entries and
  lifetimes; unifying them would reopen `thumbs/` (Principle VII).

## Research & Decisions

### The contract (D-21), and what E1 decided

**Context**: The proxy must seek in about one display frame, scrub at 30 frames per second or better, play with
sound in Firefox and Chrome, and cost about 40 GB for the archive.

**Explored**: `research/v2/proxies` (encoder paths, 7 sources; GOP intra, 0.5 s, 1 s, 2 s, 10 s; CRF 22 to 32;
presets; 540p, 720p, 360p), `pcm-audio` (AAC from PCM in Firefox 155 and 157), synthesis sections 2 and 3.

**Decision**: the values in the proposal. In one table:

| Item | Value | Evidence |
|---|---|---|
| Container | MP4, `-movflags +faststart` | 76 % of originals keep the index at the end; first frame 15 to 23 ms for proxies, 97 to 191 ms for originals |
| Video | libx264 `veryfast`, CRF 26, `-profile:v high`, `-pix_fmt yuv420p` | `preset_medium` is the same size at 4x the CPU; `tune fastdecode` is +10 to 18 % size with no speed gain; +2 CRF is -30 % size and -0.017 SSIM |
| Size | short side 540, never upscaled, even dimensions | 720p is +52 % disk for SSIM +0.004; 360p saves 1 % on the Sony class |
| Keyframes | `-g round(fps) -sc_threshold 0`, **B-frames `-bf 2`** (locked by E1) | x264's default GOP (10 s) gives 108 to 428 ms steps and 8 to 11 fps scrub; 1 s gives 17 to 53 ms and 35 to 39 fps; E1 re-measured seek, step, accuracy and A/V sync with `-bf 2` on Chrome 154 and Firefox 155 (gate G1 passed) |
| Timestamps | `-fps_mode passthrough` | keeps VFR and proxy time = source time (0 ms deviation on 20 of 22 files, 20 ms on one VFR phone clip) |
| Audio | `-c:a aac -b:a 128k -ac 2`, native encoder | 16.4 KB/s = 3.0 GB for 52 h; fixes Firefox for PCM (52 % of the archive), AC-3 and MP3 sources |
| Fixed values, not settings | all of the above | Principle VII; changing one is a code change plus `PROXY_VERSION` |

**E1 result (locked).** `proxy-shape-recheck` re-measured {`-bf 0`, 1 s}, {`-bf 2`, 1 s} and {`-bf 0`, 0.5 s} on
Chrome 154 and Firefox 155, four real sources at 540p plus synthetic accuracy and A/V clips. Gate G1 passed for all
three; the cheapest passing shape is **`-bf 2`, GOP one second** (file size 0.826 of the `-bf 0` baseline over the four
sources, so the archive estimate falls from about 39 GB to about 32 GB). The two values stay two constants,
`PROXY_BFRAMES = 2` and `PROXY_GOP_SECONDS = 1`, in one module; a future change to either is a change to this table, the
golden arguments and the spec sentence, plus a `PROXY_VERSION` bump. E1's own caveats are kept as risks below: the
scrub margin is about 1 fps, and the Panasonic 1080p50 class is under 30 fps per source.

**Rationale**: every row is a measured choice or a house rule; none is tunable at run time, so a proxy's key can
hold a digest of the contract and a proxy made under another contract can never be read as current.

### Encode paths: the golden arguments

**Context**: a GPU makes the biggest saving on decode and scale (the CPU cost per footage second falls from 1.06 to
3.24 cores to 0.18 to 0.47 on the measured classes), but pure hardware encode is bigger and fails on legacy
MPEG-4, and GPU rotation of an HEVC clip produced a wrong picture without an error.

**Explored**: `mkproxy.py` and `final_proxy.py` (modes `vaapi`, `hybrid`, `x264`), `results_final.json`: hybrid
for 17 of 22 sources, CPU for the two rotated clips, the MPEG-4 movie and the SD MPEG-4 clip.

**Decision**: a pure function builds the arguments; it never touches the file system.

```python
class EncodePath(str, Enum):
    HYBRID = "hybrid"
    CPU = "cpu"

def plan_encode(clip: ClipMetadata, profile: AccelProfile, *, render_node: Optional[str]) -> EncodePath: ...

def build_proxy_command(
    clip: ClipMetadata, *, source: Path, output: Path, path: EncodePath,
    profile: AccelProfile, render_node: Optional[str], size: tuple[int, int],
) -> ProxyCommand: ...        # args, path, width, height, duration
```

`plan_encode` returns `HYBRID` only when **all** hold: `profile.can_hw_decode(clip.video_codec, clip.pix_fmt)`;
`clip.video_codec in {"h264", "hevc"}` and the pixel format is a known 8-bit one (a 10-bit HEVC clip is not measured); `clip.rotation` is `None` or `0`; `not clip.is_hdr`; and the profile's DECODE
fragment leaves frames in a location that has a verified scale filter in a table the module owns
(`{FrameLocation.VAAPI: "scale_vaapi=w={w}:h={h}:format=nv12"}`). Everything else is `CPU`. No vendor name appears:
the location of the decode fragment's frames is the capability. A new vendor's hybrid path is one table row, added
only after it is measured on that hardware (Principle III; the table has one row today).

Hybrid, `sony-xavc-1080p25-pcm.mp4` (1920x1080, 25 fps, PCM) on the AMD profile, render node `/dev/dri/renderD128`:

```
-hide_banner -nostdin -y
-init_hw_device vaapi=va:/dev/dri/renderD128 -filter_hw_device va
-hwaccel vaapi -hwaccel_device va -hwaccel_output_format vaapi
-i /lib/2020/.../C0123.MP4
-map 0:v:0
-vf scale_vaapi=w=960:h=540:format=nv12,hwdownload,format=nv12,setsar=1
-fps_mode passthrough
-c:v libx264 -preset veryfast -crf 26 -profile:v high -pix_fmt yuv420p -bf 2 -g 25 -sc_threshold 0
-map 0:a:0 -c:a aac -b:a 128k -ac 2
-movflags +faststart
/cache/.<key>.<unique>.part/proxy.mp4
```

The decode flags are the profile's own `input_flags` (not retyped), and `hwdownload,format=nv12` is the repo's
`_transfer_filter("hwdownload")` string. `scale_vaapi` gets exact `w:h` with no aspect option, so a non-square pixel
is resolved by the scale: the planned size is the display size, and `setsar=1` states it.

CPU, a phone clip, `h264-720p-rotate90-aac.mp4` (1280x720, display rotation -90°), planned 540x960:

```
-hide_banner -nostdin -y
-i /lib/.../IMG_0001.MOV
-map 0:v:0
-vf scale=540:960:flags=bicubic,setsar=1
-fps_mode passthrough
-c:v libx264 -preset veryfast -crf 26 -profile:v high -pix_fmt yuv420p -bf 2 -g 30 -sc_threshold 0
-map 0:a:0 -c:a aac -b:a 128k -ac 2
-movflags +faststart
/cache/.<key>.<unique>.part/proxy.mp4
```

There is no `-noautorotate` and no `transpose`: software decode applies the container's display rotation before the
filter (the same behaviour D-11's thumbnails rely on), and the planned size already has the sides swapped. An HDR
clip's `-vf` is `<CPU_TONEMAP_FILTER>,scale=…,setsar=1`. A clip without audio has no `-map 0:a:0` and no audio
options. `-g` is `round(clip.fps)` (at least 1).

**Rationale**: reuse of the profile's decode fragment keeps the VAAPI device recipe in one place (the self-test and
the render use the same). The profile's NORMALIZE fragment is not used because it cannot express "scale to exactly
this display size" for an anamorphic clip. The hybrid chain is the one `mkproxy.py` measured.

**Alternatives**: (a) pure VAAPI encode: 1.9x bigger on 1080p50, fails on MPEG-4, CQP rate control is poor.
(b) `transpose_vaapi` for rotated clips: right on H.264 (SSIM 0.995), wrong geometry on HEVC (SSIM 0.35 at best),
so rotation takes the CPU path as `render/normalize.py` already does. (c) A `-noautorotate` plus explicit transpose
on the CPU path: version-independent, but it would differ from the thumbnails; the dimension check and the upright
test (task 7.1) catch an ffmpeg that stops auto-rotating.

### The CPU retry

**Context**: the self-test proves hardware decode with one H.264 clip, and a table entry can be wrong for a clip
(D-18's MPEG-4 failure).

**Decision**: `ensure_proxy` runs the planned path once. If it is `HYBRID` and ffmpeg raises `FfmpegError` (any
non-zero exit, but not `FfmpegStalledError` or `FfmpegCancelledError`), or the output fails verification, the
`.part` output is removed, the failure's first line is kept, and the same clip is encoded once on `CPU`. The CPU
result is verified like any other. The facts record `encode_path: "cpu"` and `fallback_reason`.

**Rationale**: the synthesis locks "any hybrid failure retries on CPU", and a hybrid output that fails the check is
exactly the silent wrong output the research warns of. D-18 retried only on two known strings, because a blind retry
doubles a render's wait; a proxy encode is a derived artifact with no job state to protect, a CPU encode of a 10 s
window costs 1 to 3 core-seconds per footage second, and a stall is excluded so a hang is not doubled.

### Verification, and what it cannot see

**Decision**: `verify_proxy(staged, *, expected) -> None` raises `ProxyError`. It runs one ffprobe on the staged
file with `-count_packets`, which counts video packets without decoding them (a 540p proxy reads in well under a
second), and checks the four conditions of the spec. The source's frame count is the container's declared
`nb_frames` from the run's own ffprobe call (an MP4 or MOV declares it; a container that does not skips that one
check and logs it). Expected duration is `ClipMetadata.duration`; the proxy's **video stream** duration is compared,
not the container's, because AAC priming pads the container by up to 21 ms.

**What it cannot see**: a correctly sized, correctly timed proxy of a wrong picture (a flipped, squashed or
mis-coloured one). The ladder is the defence: rotated and non-H.264/HEVC clips never meet the GPU. The test plan
covers the rest with real encodes: an asymmetric synthetic clip, upright after a -90° rotation, checked by pixel
position (task 7.1). A similarity threshold (SSIM against a source frame) is not added: the research's lowest CPU
path score is 0.744 for a rotated 720p phone clip and 0.87 for full-range `yuvj` clips, unexplained, so any
threshold would be a guess between 0.47 (known wrong) and 0.74 (unexplained but looks right). Left to a follow-up
once someone explains the 0.744.

### `facts.json`

**Decision**: written by `write_facts(staged_dir, facts)` as sorted-key JSON with the keys the spec lists. The run
makes one extra call, `ffprobe -select_streams v:0 -show_entries stream=r_frame_rate,avg_frame_rate,nb_frames -of
json`, for `fps` (as `num`/`den` from `r_frame_rate`), `vfr` (`|avg - r| / r > 0.01`) and the declared frame count.
`frames` in the facts is the proxy's own video packet count from the verification. A value that ffprobe does not give
(`nb_frames`, an audio stream, a rotation) is `null`.

**Why not the thumbnail sidecar's duration**: the proxy run probes the clip anyway for its encode plan, so reading
`<key>.json` from `thumbs/` would save nothing and tie two caches together; a clip with no thumbnail yet would have
no duration. The brief allows the reuse and forbids depending on it; this change does neither.

**Why not the proxy's duration**: the research measured 21 ms gaps (Firefox 24.981 s against 24.960 s, 1080p50
24.981 against 25.003 s); `duration` is the source's probed duration, which is also what cuts (D-14) refer to.

**Which duration the verification compares**: the proxy's video stream against the source's *video stream* duration
(`stream=duration` from the one extra ffprobe), not the container's. The container duration spans the longest stream
from the earliest start, so a clip whose audio outruns its video by more than 50 ms, or whose video starts late
(phone audio tracks, MPEG-TS/AVCHD), would fail a correct proxy. The container's duration is the fallback only when
the source gives no stream duration. A late start is still not normalised.

### Cache layout, key and publish

**Decision**:

```
<cache_dir>/
  <sha256 key>/              # an entry: complete when both files exist
    proxy.mp4
    facts.json
    filmstrip.jpg            # reserved; written by filmstrip-sprites, never by this change
  .<key>.<unique>.part/      # a build in progress
```

`proxy_key(clip_path) -> str` is the SHA-256 of `json.dumps([resolved.name, st_size, st_mtime_ns, PROXY_VERSION,
spec_digest()])` (ASCII-safe, as D-11). `spec_digest()` is a function, not a constant, so a monkeypatched or edited constant changes it at once; it is the SHA-256 of the canonical JSON of the contract's values
(short side, CRF, preset, GOP seconds, B-frames, audio bitrate, channels). It is a second guard: a contract constant
edited without a version bump still re-keys. The encode path is **not** hashed, so a laptop reuses a workstation's
proxy.

Publish: `mkdir .<key>.<unique>.part`, encode to `proxy.mp4` in it, verify, write `facts.json`, `fsync` both files
and the directory, then `os.rename(part, entry)`. On `FileExistsError` or `ENOTEMPTY` (another process won), the
build is removed and the existing entry is returned if complete. An existing but incomplete `<key>` is removed
first and the build is renamed in its place (if the removal races, the rename error path above applies). A `finally`
removes the part directory on any exit, including `KeyboardInterrupt`.

**Alternatives**: (a) D-11's flat `<key>.mp4` plus `<key>.json` files: two files cannot be published atomically
together, so a reader could see a proxy without facts. (b) A lock file per key (the research's `O_CREAT|O_EXCL`
idea): handles duplicate work but adds stale-lock logic; a duplicate encode is harmless here and the CLI already
groups by key, so the atomic rename alone is enough. (c) Postgres rows: forbidden by D-7, and the proxy must work
without a database.

**Sweep**: `sweep_stale_parts(cache_dir)` removes `.*.part` directories whose mtime is over 24 hours old, once per
process per directory (a lock-guarded set, as `thumbs`), before the first build. An encode is bounded by its
10-minute stall limit, so a 24-hour-old part is dead.

**Disk full**: ffmpeg's `No space left on device` / `Disk quota exceeded` on the cache disk is a `ProxyCacheError`
(not the clip's fault), the same classification as `thumbs`.

### Settings

`resolve_proxy_settings(config, project_root) -> ProxySettings(cache_dir)` mirrors `resolve_thumbnail_settings`:
`proxies.cache_dir` only; XDG default `…/auto-reel/proxies`; refused inside the project root or the `input`
directory by path and by identity (`os.path.samestat`); a wrong type or relative path raises `ConfigError` naming
`proxies.cache_dir`. The three helpers are **copied** from `thumbs/settings.py` with the key and leaf name changed,
not shared: sharing them means editing `thumbs/`, a third package, to remove about 70 lines of duplication that no
requirement needs (Principle VIII). A follow-up can move both to a common module; the duplication is recorded in
Risks.

### `ensure_proxy` and `lookup_proxy`

```python
def ensure_proxy(clip_path, *, settings, runtime, profile, render_node=None,
                 on_progress=None, should_cancel=None) -> ProxyEntry: ...
def lookup_proxy(clip_path, *, settings) -> Optional[ProxyEntry]: ...   # stat + JSON read only

@dataclass(frozen=True)
class ProxyEntry:
    key: str
    directory: Path
    proxy_path: Path
    facts_path: Path
    facts: ProxyFacts
    generated: bool          # True when this call built it
```

Steps of `ensure_proxy`: (1) key, from one `stat` (an `OSError` becomes `ProxyError`); (2) `lookup_proxy`, return on a
hit; (3) create the cache directory (`ProxyCacheError`) and sweep once; (4) `probe_media` through
`runtime.with_timeout(60)`, then reject a duration of 0 or less; (5) the facts ffprobe; (6) `plan_encode`,
`build_proxy_command`, run with `stall_timeout=PROXY_STALL_TIMEOUT_S` (600) and the caller's `should_cancel`,
progress through a wrapper that never reports a lower fraction than before; (7) on a hybrid failure, steps 6 again
on `CPU`; (8) `verify_proxy`; (9) write facts, publish. The function takes the runtime and profile as arguments, and
it neither prints nor imports `api/`, `persistence/` or `scheduler/` (`ProxyEntry` and the cache helpers live in `proxies/cache.py`, `ensure_proxy` and `lookup_proxy` in `proxies/ensure.py`); `proxy-job` wraps it and maps
`FfmpegCancelledError` to a canceled job.

`lookup_proxy` reads and parses `facts.json` only; a missing or unparseable file is "absent", never a default.
Because `facts.json` is written into the part directory before the rename, a complete entry always has valid facts.

### The `proxies` subcommand

`cli/proxies.py`, beside `thumbnails.py` and shaped like it: `project_context`, `resolve_proxy_settings`, one
`FfmpegRuntime`, `detect_capabilities(runtime)` and `select_profile(inventory, override=args.device)` once (an
`AccelError` is one `error:` line, exit 1, before any encode), the render node of the selected profile, a
`ThreadPoolExecutor(max_workers=args.jobs)` with `--jobs` default **1**. Per event: group identities by
`proxy_key`; skip complete entries (`lookup_proxy`, no process); submit one `ensure_proxy` per remaining key; the
event is a barrier that prints its `ERROR` lines in identity order and then its counts line. A shared
`threading.Event` is the `should_cancel` of every encode; any `BaseException` (Ctrl-C) sets it, shuts the pool down
with `cancel_futures=True`, and re-raises, so running ffmpeg processes are killed and their part directories removed
before the process exits. `ProxyCacheError` stops the run like `ThumbnailCacheError`. The four output helpers
(`_emit`, `_printable`, `_plural`, `_os_reason`) move unchanged from `thumbnails.py` to `cli/printing.py`, imported by
both.

`--jobs` defaults to 1: one libx264 encode uses several cores, and two workers gave only +20 to +35 % on this
host's USB library drive (I/O bound at 47 to 88 MB/s). The summary adds the bytes written, so the operator sees the
disk cost as it accrues.

### Where D-21 is recorded

Task 9.1 adds **D-21 — The proxy contract** to HLD §7 after D-19 (or after D-20 if `timeline-model` has merged, which
records the timeline as D-20), and updates three places: §4.10's v2 bullet (proxies and the filmstrip now have an
engine half, with the `proxies` command), §6 phase 9 (a proxy cache is built by `proxy-encode`), and §8.11 (the
proxy research is resolved; the PCM remux, the prune and the sprite remain). The entry records: the contract table
above; the cache layout and key; the CPU retry; the facts file; "not a staleness input, no `RENDER_GRAPH_VERSION`
bump"; native `aac` only; and the ceiling (40 to 50 GB, no eviction). D-20 belongs to `timeline-model`; this change
does not write it.

### No fingerprint or render impact

Proxies are written beside renders, never into one. `staleness/`, `render/` and `persistence/` do not import
`proxies/`, and a test fails if they ever do (task 6.1). `RENDER_GRAPH_VERSION` is unchanged and the fingerprint
inputs are unchanged. `PROXY_VERSION` (starts at 1) is the proxy's own version: it changes the key, nothing else.

## Failure behavior and idempotency

| Situation | Behavior |
|---|---|
| Re-run, nothing changed | `lookup_proxy` hits; no ffprobe, no ffmpeg; counted cached |
| Clip changed (size, mtime, name) | new key; new build; the old entry stays unread |
| `PROXY_VERSION` or a contract constant changed | every clip re-keys; old entries stay unread |
| Hybrid ffmpeg fails, or its output fails the check | part output removed; one CPU encode; the cause logged and in the facts |
| CPU ffmpeg fails, or its output fails the check | `ProxyError` with the command, stderr and the failed check; no entry |
| Probe fails, empty file, duration 0 | `ProxyError`; no ffmpeg; no entry |
| ffmpeg stalls 10 minutes | killed; `ProxyError` naming the stall; not retried |
| Cancel (job cancel, Ctrl-C) | ffmpeg killed; part removed; `FfmpegCancelledError` propagates |
| Process killed (`SIGKILL`, power) | a `.part` directory stays; never read as an entry; swept after 24 h; next request builds |
| Two builds of one clip | both finish; the first rename wins; the other is discarded and returns the winner |
| Cache directory unwritable or disk full | `ProxyCacheError` naming the directory; the CLI stops |
| `--force` | none: there is no flag. Deleting an entry directory is the reset |

## Risks / Trade-offs

- **E1's scrub margin is thin.** `-bf 2`, 1 s passes the 30 fps median-scrub gate by about 1 fps (31.0 Chrome, 31.1
  Firefox), as the `-bf 0` baseline does; Panasonic 1080p50 is under 30 per source (26.1 Chrome, 27.0 Firefox). A 0.5 s
  GOP clears 30 on every source at +19 % disk (about +13.6 GB). → The GOP is locked at one second by the gate's own
  metric; `timeline-view` re-measures on the real timeline, and moving to 0.5 s is one constant plus a
  `PROXY_VERSION` bump plus a regeneration (about 4 to 6 hours for the whole archive), never a migration.
- **Seek, step and accuracy were never measured on other B-frame shapes.** → E1 measured the shipped shape; the
  verification and the real-encode tests assert the stream really carries at most two B-frames and the keyframe
  interval. A change after this change is archived is a `PROXY_VERSION` bump plus a regeneration
  (about 4 to 6 hours for the whole archive), never a migration.
- **The hybrid path is validated on one AMD VAAPI stack (Mesa) only: the research host's Radeon 860M.** Intel and NVIDIA
  take the CPU path (4 to 9 times the CPU), and the CPU path is the tested default: every encode test runs on it, and
  only one `gpu`-marked test runs the hybrid. → The scale-filter table has one row; a vendor is added after it is
  measured.
- **Silent wrong output is still possible below the structural check** (above). → The ladder, the dimension check
  and a real-encode upright test; an SSIM check is recorded as a follow-up once the 0.744 is explained.
- **The frame-count check depends on the container declaring `nb_frames`.** → Skipped, and logged, when absent. If
  a sample shows a legitimate off-by-one on a declared count, the finding is reported and the check adjusted with
  evidence, never widened silently (Principle I).
- **`start_time`.** The synthesis gate asks that a proxy's video `start_time` equal the source's. All ten samples
  start at 0, so a clip with a non-zero start is unmeasured. → Task 7.1 asserts equality on the samples and
  records the values; a clip that starts late is reported, not normalised.
- **Duplicated cache-location helpers** (`thumbs/settings.py` and `proxies/settings.py`). → Accepted for scope
  (above); named in the HLD so a later change can unify them.
- **`project-config`'s requirement lists the opaque maps by name and will not mention `proxies`.** This change keeps
  to two spec deltas (Principle VIII), so the sentence is stale by one word until a change that touches that
  requirement; `clip-proxies` states the key's behaviour. → Noted for the archive step.
- **I/O contention.** Proxy generation reads the USB library at 47 to 88 MB/s, as a render does. → `--jobs`
  defaults to 1; `proxy-job` owns running below render priority.
- **Disk.** About 40 GB (range 22 to 79 GB across settings, 90 % interval 34 to 45 GB), planned at 50 GB because
  per-clip variance is large. → Reported in the CLI summary; the cache is on the local disk by default; no eviction
  (D-11 never evicts either). A hard cap would be `proxy-prune`.
- **Sample-based tests are slow.** The legacy MPEG-4 sample is 12.6 minutes; a CPU encode at about 11 times real
  time is about 70 s. → That one clip is a separate test; the rest of the samples take under a minute together.

## Migration Plan

None. No schema, no `reel.yaml` change, no rescan. `config.yaml` gains an optional key; a file without it behaves
as before. Existing thumbnails are untouched. Rollback is deleting the `proxies` cache directory.

## Open Questions

None that change the specs, the approach or the tasks. For the follow-up changes: whether `filmstrip-sprites` writes
into the published entry directory (assumed, since `filmstrip.jpg` is additive and its absence leaves the entry
complete), and whether `proxy-job` wants `ensure_proxy` to report phases beyond the encode fraction (it can wrap the
callback).
