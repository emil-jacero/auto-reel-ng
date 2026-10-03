## 1. Gate

- [x] 1.1 Gate: E1 (`proxy-shape-recheck`) has run, and the starting point is clean. Check:
  - E1 locked **`gop_seconds` 1 and `bframes` 2** (gate G1 passed; report in the session scratchpad, not in
    `experiments/`). The design's contract table, the spec's "at most two B-frames" sentence and scenario, the golden
    arguments (`-bf 2`) and tasks 3.1 and 7.1 (`PROXY_BFRAMES = 2`, `has_b_frames` at most 2) were changed **before any
    code**; record in this task that they were.
  - `test ! -e auto_reel_ng/proxies`
  - `git diff 8fb4d16 -- openspec/specs/headless-cli/spec.md` prints nothing. If the `auto-reel entry point with
    subcommands` requirement differs, re-base this change's MODIFIED block on the current text.
  - `ls openspec/changes/*/specs/headless-cli` lists only this change. If another open change modifies
    `headless-cli`, stop and report.
  - `python3.14 -m venv .venv --system-site-packages && .venv/bin/pip install -q -e ".[dev]"` succeeds, and
    `ffmpeg -hide_banner -encoders | grep -w aac` lists the native AAC encoder.

  Verify: every check holds, or the re-base, the new E1 values or the stop is recorded in this task.

  Recorded: E1's report is in the supervisor's session scratchpad, not in `experiments/` (no `experiments/*proxy-shape*`
  exists); its outcome was given with the task: gate G1 passed for all three shapes and the cheapest passing one is
  `-bf 2`, GOP one second. Applied before any code (design table, spec sentence and scenario, golden arguments,
  tasks 3.1 and 7.1) and committed with the proposal. `test ! -e auto_reel_ng/proxies` held, `git diff 8fb4d16 --
  openspec/specs/headless-cli/spec.md` printed nothing, this is the only open change under `openspec/changes/` with a
  `headless-cli` delta, and the venv installs. The host `ffmpeg` is 8.1.2 and lists the native `aac` (and
  `libfdk_aac`, which the code never selects).

## 2. config/ and proxies/ — errors, settings

- [x] 2.1 Add the errors and the settings (design "Settings"):
  - `errors.py`: `ProxyError(EngineError)` with `clip` and `reason` (message `<clip>: <reason>`) and
    `ProxyCacheError(EngineError)`, as siblings, each with a docstring
  - `config/project.py`: `ProjectConfig.proxies: Mapping[str, object]`, parsed with
    `_require_mapping(data.get("proxies"), "proxies", source)`, and the module docstring updated
  - new `auto_reel_ng/proxies/__init__.py` and `proxies/settings.py`: `ProxySettings(cache_dir)`,
    `default_cache_dir()`, `resolve_proxy_settings(config, project_root)`, the three cache-location helpers copied
    from `thumbs/settings.py` with the key `proxies.cache_dir` and the leaf `proxies`

  Tests go in a new `tests/test_proxies_settings.py`. Each sets `HOME` to `tmp_path / "home"` with `monkeypatch.setenv`
  and sets or deletes `XDG_CACHE_HOME` the same way; the project root is `tmp_path / "library"`:
  - no settings: the cache is `<home>/.cache/auto-reel/proxies`
  - `XDG_CACHE_HOME=/data/cache` gives `/data/cache/auto-reel/proxies`; a relative `XDG_CACHE_HOME` is ignored
  - `cache_dir: ~/proxies` wins over `XDG_CACHE_HOME`
  - each raises `ConfigError` naming `proxies.cache_dir`: a relative path, a non-string, an absolute path under the
    project root (directly and through a symlink), a path under an absolute `input:` directory outside the project
    root, and no `cache_dir` with `XDG_CACHE_HOME` inside the project root
  - no home directory (`HOME` unset, `Path.home` raising `RuntimeError`) raises `ConfigError` naming the key

  Add one case to `tests/test_project_config.py`: `proxies: 3` raises `ConfigError` naming `'proxies'`.

  Verify:
  - `.venv/bin/python -m pytest tests/test_proxies_settings.py tests/test_project_config.py` passes
  - `.venv/bin/python -m mypy auto_reel_ng` is clean

## 3. proxies/ — contract, geometry, key

- [x] 3.1 Add `proxies/spec.py` (design "The contract", "Cache layout, key and publish"): `PROXY_VERSION = 1`, the
  contract constants (`PROXY_SHORT_SIDE = 540`, `PROXY_CRF = 26`, `PROXY_PRESET = "veryfast"`, `PROXY_BFRAMES = 2`,
  `PROXY_GOP_SECONDS = 1`, `PROXY_AUDIO_ENCODER = "aac"`, `PROXY_AUDIO_BITRATE = "128k"`, `PROXY_AUDIO_CHANNELS = 2`,
  the 50 ms `DURATION_TOLERANCE`), `spec_digest()` (a function, not a constant, so a patched constant changes it at once), `proxy_dimensions(width, height, sar,
  rotation) -> (w, h)` computed in exact fractions, `proxy_key(clip_path)` and `entry_dir(clip_path, cache_dir)`. Export
  them from `proxies/__init__.py`. Tests in a new `tests/test_proxies_spec.py`:
  - **dimensions** (the spec's scenarios): 1920x1080, 3840x2160 and 1280x720 give 960x540; 1080x1920 gives 540x960;
    1280x720 with rotation -90 and 90 give 540x960; 720x576 with SAR `16:15` gives 720x540; 640x360 gives 640x360 and
    720x480 gives 720x480 (no upscale); display 1000x667 gives 810x540; SAR `None`, `"0:1"` and `"1:1"` all count as
    square; rotation 180 does not swap; every result is even and at least 2
  - **the key** is stable across calls and changes when: one byte is appended to the clip, `os.utime(ns=…)` changes
    the mtime, the file is renamed, `PROXY_VERSION` is monkeypatched, or one contract constant (`PROXY_BFRAMES`) is
    monkeypatched without a version change (the digest re-keys)
  - **two symlinks** to one file give the same key, and a `cp -a` copy in another directory gives it too
  - **a missing clip:** `proxy_key` raises `FileNotFoundError` unchanged
  - **`entry_dir`** leaves a non-existent `cache_dir` non-existent
  - **constants:** `PROXY_AUDIO_ENCODER == "aac"`

  Verify:
  - `.venv/bin/python -m pytest tests/test_proxies_spec.py` passes
  - mypy is clean

## 4. proxies/ — encode paths and golden arguments

- [x] 4.1 Add `proxies/command.py` (design "Encode paths"): `EncodePath`, `plan_encode`, `ProxyCommand` and
  `build_proxy_command`, with the one-row hardware scale table. Pure: no file system, no subprocess. Tests in a new
  `tests/test_proxies_command.py`, with a `ClipMetadata` factory and profiles built from `AcceleratorCapabilities`
  (a VAAPI profile with `hw_decode={"h264": 8, "hevc": 10}`, a CPU profile, a CUDA-shaped profile whose decode frames
  are `FrameLocation.CUDA`):
  - **golden arguments**, the exact lists in the design, for: the Sony 1080p25 PCM clip on the hybrid path
    (`scale_vaapi=w=960:h=540:format=nv12,hwdownload,format=nv12,setsar=1`, `-g 25`, the profile's decode flags first);
    the 720p -90° phone clip on the CPU path (`scale=540:960:flags=bicubic,setsar=1`, `-g 30`); a 50 fps clip
    (`-g 50`); a 29.97 fps clip (`-g 30`); a sub-second 12-frame 25 fps clip (`-g 25`); a clip with no audio (no
    `-map 0:a:0`, no `-c:a`); an HDR clip (`CPU_TONEMAP_FILTER` ahead of the scale); a legacy MPEG-4 clip (no hardware
    flag)
  - **the ladder** (`plan_encode`), one case each: H.264 8-bit on VAAPI is `HYBRID`; HEVC 8-bit is `HYBRID`; rotation
    -90 is `CPU`; MPEG-4 Part 2 is `CPU`; HEVC 10-bit is `CPU`; HDR is `CPU`; the CPU profile is `CPU`; the CUDA-shaped
    profile is `CPU`; a hardware profile whose `can_hw_decode` is false is `CPU`; rotation `0` and `None` both allow
    hybrid
  - **native AAC:** over eight golden commands (both paths, rotated, HDR, MPEG-4 with MP3, AC-3 5.1), exactly one
    `-c:a` is present, its value is `aac`, and no argument contains `fdk`. The builder takes no encoder list, so
    there is no runtime to fake: the test fails when a code change names `libfdk_aac` (shown by patching
    `PROXY_AUDIO_ENCODER`), and an `has_ffmpeg` check shows the host ffmpeg does offer the native encoder.
  - **no vendor name:** `grep -rniE "amd|nvidia|intel|nvenc|qsv" auto_reel_ng/proxies` prints nothing (the filter
    string `scale_vaapi` names an API, not a vendor)

  Verify:
  - `.venv/bin/python -m pytest tests/test_proxies_command.py` passes
  - mypy is clean
  - `grep -rn "subprocess" auto_reel_ng/proxies` prints nothing

## 5. proxies/ — facts and verification

- [x] 5.1 Add `proxies/facts.py` and `proxies/verify.py` (design "Verification", "`facts.json`"): `ProxyFacts`
  (frozen dataclass, `to_json`/`from_json`), `read_source_facts(source, runtime)` (the one extra ffprobe call),
  `write_facts`, `read_facts`, and `verify_proxy(staged, *, expected, runtime)`. Tests in a new
  `tests/test_proxies_facts.py` with a fake runtime that returns canned ffprobe JSON:
  - **facts for the Sony clip** equal the spec's scenario values (`duration` 24.96, `fps` 25/1, `vfr` false, `frames`
    624, `rotation` null, `audio_codec` `pcm_s16be`); the rotated phone clip gives `width` 540, `height` 960,
    `rotation` 270 (the probe's spelling of -90°; the spec says so); a clip with no audio gives `audio_codec` null; `vfr` is false at average 30.0003 against rate 30
    and true at 24 against 30
  - **round trip:** `write_facts` then `read_facts` returns an equal object; a file with a missing key, invalid JSON
    or a different `proxy_version` reads as absent (`None`), never as defaults
  - **verification passes** on the right streams, and **fails naming the check, the value found and the value
    expected** for: no audio stream where the source has one; an audio stream where the source has none; two video
    streams; a non-H.264 video stream; the wrong width or height (found 960x540, expected 540x960); a video duration
    60 ms short (while 40 ms short passes); 623 frames against a declared 624; a non-square pixel
  - **no declared frame count** skips only that check and logs it at debug level
  - **the source's duration, not the proxy's** is what `duration` holds when the proxy container is 21 ms longer

  Verify:
  - `.venv/bin/python -m pytest tests/test_proxies_facts.py` passes
  - mypy is clean

## 6. proxies/ — `ensure_proxy`, cache entry and sweep

- [x] 6.1 Add `proxies/cache.py` (publish, lookup, sweep) and `proxies/ensure.py` (`ensure_proxy`, `lookup_proxy`,
  `ProxyEntry`), exported from `proxies/__init__.py` with `ProxySettings`, `resolve_proxy_settings`, `ProxyError` and
  `ProxyCacheError` (design "Cache layout, key and publish", "`ensure_proxy` and `lookup_proxy`", "The CPU retry").
  Tests go in a new `tests/test_proxies_ensure.py`, with a fake runtime whose `run_with_progress` records the argument
  list, reports progress, and writes a configurable output to the last argument, and `probe_media` monkeypatched in
  `proxies.ensure`:
  - **a hit** (`lookup_proxy` and `ensure_proxy`) returns the complete entry and calls neither the probe nor the runtime
  - **a miss** publishes `<key>/proxy.mp4` and `<key>/facts.json`, returns `generated=True`, and leaves no `.part`
    directory
  - **a vanished clip** and a **duration of 0** each raise `ProxyError`, and the runtime is not called
  - **a `ProbeError`** (zero-byte file) becomes a `ProxyError` that names the clip
  - **hybrid failure:** the first run raises `FfmpegError("… Failed setup for format vaapi")`; the second run is the CPU
    command; the entry's facts hold `encode_path` `cpu` and a `fallback_reason` naming the cause
  - **hybrid output that fails verification** (wrong size) is discarded and redone on the CPU; if the CPU output also
    fails, `ProxyError` names the check and no entry or part remains
  - **a stall** (`FfmpegStalledError`) is not retried: one run, `ProxyError`, no entry
  - **a cancel:** `should_cancel` true makes the runtime raise `FfmpegCancelledError`, which propagates (not a
    `ProxyError`); no `.part` and no `<key>` remains
  - **progress** after a retry that restarts at 0 never reports a fraction below the highest one reported, and ends at 1.0
  - **`KeyboardInterrupt`** from the fake runtime propagates and leaves neither a part directory nor an entry
  - **two threads**, one clip, a `threading.Barrier(2)` inside the fake runtime: both return the same complete entry,
    one build is discarded, and no `.part` remains; and a monkeypatched `os.rename` that creates the entry first gives
    the same result
  - **an incomplete `<key>/`** (no `facts.json`) is replaced by a complete entry
  - **a cache path under a regular file** raises `ProxyCacheError` naming the directory, not `ProxyError`; ffmpeg stderr
    `No space left on device` raises `ProxyCacheError`
  - **the sweep:** a `.part` directory two days old is removed, one a minute old is kept, a removal that raises
    `OSError` is logged and does not fail the request, and a second build in the same process does not sweep again
  - **the source clip's bytes and `st_mtime_ns` are unchanged**
  - **isolation** (`tests/test_proxies_isolation.py`): an AST walk finds no import of `auto_reel_ng.proxies` in
    `staleness/`, `render/` or `persistence/`. `scheduler/` and `api/` are left out on purpose: `proxy-job`, the read
    model and the media routes wrap `ensure_proxy` there by design and would otherwise have to edit this test.
    `tests/test_proxies_staleness.py` shows a fresh event stays fresh across making and deleting proxies, and a cut
    edit makes it stale while the proxy stays current.

  Verify:
  - `.venv/bin/python -m pytest tests/test_proxies_ensure.py tests/test_proxies_isolation.py` passes
  - mypy is clean
  - `.venv/bin/python -c "from auto_reel_ng.proxies import ensure_proxy, lookup_proxy, ProxyEntry, ProxySettings, resolve_proxy_settings"` succeeds

## 7. proxies/ — real encodes

- [x] 7.1 Add `tests/test_proxies_ffmpeg.py`, every test marked `has_ffmpeg` and using the `runtime` fixture and the
  CPU profile, with the clips from `make_clip` (synthetic, 1 to 2 s) unless stated. Each proxy's streams are read with
  `run_ffprobe`; the cache is under `tmp_path`:
  - **the contract:** a 1920x1080 25 fps H.264 + AAC clip gives one H.264 `High` `yuv420p` stream of 960x540 with
    `has_b_frames` at most 2, a keyframe at every 25th packet (packet flags), `moov` before `mdat` (the first top-level boxes
    read from the file), and one AAC stream with two channels; 1080x1920 gives 540x960; 640x360 stays 640x360
  - **rotation is upright:** a 1280x720 clip built from `color=red` and `color=green` halves side by side, given a
    display rotation of -90° the way `make_clip` does, gives a 540x960 proxy whose frame, read back with `-frames:v 1
    -f rawvideo -pix_fmt rgb24`, has the red half at the top and the green half at the bottom (the pixel at 25 % and
    75 % of the height), and is not squashed
  - **anamorphic:** 720x576 with `setsar=16/15` gives 720x540 and `sample_aspect_ratio` `1:1`
  - **audio:** mono gives two channels; an AC-3 5.1 source gives two channels; a `pcm_s16be` source in an MP4/MOV (the
    Sony shape) gives AAC; a clip with no audio gives none and `audio_codec` null
  - **sub-second clips:** a 12-frame 0.48 s clip and a one-frame clip each publish and pass the verification, with one
    keyframe
  - **variable frame rate:** a clip with irregular timestamps (`setpts` jitter) keeps its frame count and its first and
    last timestamps within one frame
  - **verification catches a bad output:** a monkeypatched command builder that drops the audio map makes a clip with
    audio fail naming the audio check, with no entry published
  - **a zero-byte `trasig.mp4`** raises `ProxyError`; **a second call** returns the entry without running ffmpeg (a
    spy on `run_with_progress`); the source's bytes and `st_mtime_ns` are unchanged
  - **a `gpu`-marked test** makes the proxy of a 1080p H.264 clip with the detected profile: it takes `hybrid`, passes
    the verification, and has the same frame count and dimensions as the CPU proxy of that clip
  - **samples:** parametrised over `auto-reel-media/samples/*` (read-only; skipped when absent), each through the CPU
    path and, on a host with a usable accelerator, the hybrid path: an AAC stream with two channels is present
    (the two Sony PCM clips included), the dimensions are the table's (the 1080p, 4K, 720p25 and legacy clips 960x540;
    the portrait, the 720p rotated and the HEVC rotated clips 540x960), the video duration is within 50 ms of the
    source's, the frame count equals the source's, and the video `start_time` equals the source's. The 12.6-minute
    legacy MPEG-4 clip is its own test.

  Verify:
  - `.venv/bin/python -m pytest tests/test_proxies_ffmpeg.py -m has_ffmpeg` passes (the synthetic tests in under about
    30 s; the samples in a few minutes, recorded in this task)
  - `find ../auto-reel-media -newer <marker>` prints nothing after the run

  Recorded: the synthetic tests take 14 s, the ten samples (CPU path, and the hardware profile on this host) 81 s
  together, of which the 12.6-minute legacy MPEG-4 clip is 24 s (about 31 times real time on 16 cores); nothing under
  `auto-reel-media/` is newer than the marker. Every sample's video `start_time`, duration (within 50 ms) and frame
  count equal the source's with `-bf 2`, so the E1 shape needed no special case. The rotated samples
  (`h264-720p-rotate90`, `hevc-mov-rotate90`) take the CPU path on the AMD profile and come out 540x960.

## 8. cli/ — `auto-reel proxies`

- [x] 8.1 Move `_emit`, `_printable`, `_plural` and `_os_reason` unchanged from `cli/thumbnails.py` to a new
  `cli/printing.py`, imported by both. Add `cli/proxies.py` with `cmd_proxies` (design "The `proxies` subcommand"),
  register `proxies` in `cli/main.py` with `root`, `--years`, `--layout`, `--device`, `-v` and `--jobs`
  (`type=_positive_int`, default 1; reuse the helper `thumbs` uses), `set_defaults(output=None, func=cmd_proxies)`, and
  update the module and `build_parser` docstrings (twelve subcommands). Tests in a new `tests/test_cli_proxies.py`:
  - they monkeypatch `cli.proxies.FfmpegRuntime` to a `Mock`, `detect_capabilities` and `select_profile` to a fixed
    profile, and `ensure_proxy` to a fake that writes a complete entry at the real `entry_dir(...)` or raises
    `ProxyError`; `XDG_CACHE_HOME` is `tmp_path / "xdg"`
  - the library is the one `tests/test_cli_thumbs.py` builds (Grillning, Trasig with a zero-byte `trasig.mp4`,
    Sommarlov with a MISSING entry, Tjörn with chapters and an IGNORED clip, an `original/` event, a `.reelignore`
    event, Omöjligt datum, and two links to one clip in one event)
  - they assert: the exact `ERROR  2024-10-05 - Trasig/trasig.mp4: …` line, the per-event lines, the summary (counts,
    bytes written, cache directory) and exit 1; the identities passed to the fake (no `borttagen.mp4`, no `original/…`,
    nothing from the `.reelignore` event, all five Tjörn clips, the Omöjligt clip); two links to one clip encode once
    (`2 clips, 1 generated, 1 cached`); a second run calls the fake only for `trasig.mp4`; `--jobs 0` raises
    `SystemExit` with code 2; `proxies: {cache_dir: proxies}` exits 1 naming `proxies.cache_dir` with no ffmpeg;
    a fake raising `ProxyCacheError` exits 1 with one `error:` line and no `ERROR  ` lines; `select_profile` raising
    `AccelError` (`--device nvidia`) exits 1 with one error and no encode; a fake raising `KeyboardInterrupt` propagates,
    sets the shared cancel flag the fakes were given, and the pool was shut down with `cancel_futures=True`; a library
    snapshot (paths, sizes, `st_mtime_ns`, every `reel.yaml`'s bytes) is identical before and after
  - `tests/test_cli_main.py` lists `proxies` and the test is renamed `…_twelve_subcommands`; `tests/test_cli_thumbs.py`
    still passes unchanged
  - one `has_ffmpeg` end-to-end test with the real runtime and the CPU profile (`--device cpu`): two generated clips
    and a zero-byte `trasig.mp4` symlinked into events so one clip appears twice, every library directory made
    read-only (restored in a `finally`); asserts exit 1, one `ERROR` line, two complete entries, no `.part`, the second
    run reporting `0 generated`, and the library snapshot unchanged

  Verify:
  - `.venv/bin/python -m pytest tests/test_cli_proxies.py tests/test_cli_main.py tests/test_cli_thumbs.py` passes
  - mypy is clean
  - `.venv/bin/auto-reel proxies --help` lists `--device` and `--jobs`

## 9. docs — HLD and README

- [x] 9.1 Record the decision (design "Where D-21 is recorded"):
  - `docs/high-level-design.md`:
    - add **D-21 — The proxy contract** to §7 after D-19 (after D-20 if `timeline-model` has merged): the contract
      table, the cache layout and key, the CPU retry, `facts.json`, native `aac` only, "not a staleness input, no
      `RENDER_GRAPH_VERSION` bump", and the 40 to 50 GB ceiling with no eviction; and the E1 outcome
    - §4.10 v2 bullet: proxies have an engine half and a `proxies` command, with the job, the API and the timeline to
      follow
    - §6 phase 9: a proxy cache is built by `proxy-encode`
    - §8.11: the proxy research is resolved by D-21; the PCM remux, the prune and the sprite remain
  - `README.md`: add `auto-reel proxies <root> [--device D] [--jobs N]` to the CLI list; document `proxies.cache_dir`,
    the default path, that it must lie outside the project root and the `input` directory, about 0.75 GB per footage
    hour (about 40 GB for the whole archive) with no eviction, and the advice to set `cache_dir` when `serve` runs as
    another user or in a container

  Verify:
  - `grep -n "D-21" docs/high-level-design.md` shows the §7 entry and the three references
  - `grep -n "proxies" README.md` shows the CLI line and the config key
  - `grep -n "RENDER_GRAPH_VERSION" docs/high-level-design.md` still matches the D-21 sentence that none was bumped

## 10. Validation and dogfood

- [x] 10.1 Run the validation gates and dogfood on a scratch library:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, including `has_ffmpeg`, `gpu` and `requires_db` (run in the background)
  - dogfood: a scratch library under the session scratchpad (never `auto-reel-media/`) with symlinks to the ten samples
    in two events plus one zero-byte clip. Then `touch <scratch>/marker`; `XDG_CACHE_HOME=<scratch>/cache auto-reel
    proxies <scratch>/library` twice; and once more with `--device cpu` into a second cache. Open each Sony proxy in
    Chrome and in Firefox (>= 155) from a scratch Range server and read `videoWidth`, a decoded audio peak greater
    than 0 in Chrome and `mozHasAudio` in Firefox (Playwright from the scratch directory only)

  Verify:
  - all gates are clean or green, apart from the known cairo `no-member` noise and the environmental title-card skips
  - `git diff --stat -- auto_reel_ng/staleness auto_reel_ng/render auto_reel_ng/scheduler auto_reel_ng/persistence
    auto_reel_ng/api alembic web` prints nothing, so `RENDER_GRAPH_VERSION` is unchanged and there is no migration
  - the first run exits 1 with one `ERROR` line (the zero-byte clip); the second reports `0 generated` in under 1 s;
    `find ../auto-reel-media -newer <scratch>/marker` prints nothing; the cache holds one entry per distinct sample and
    no `.part` directory
  - the wall time per footage second and the cache bytes per footage hour are recorded in this task next to the
    research's (about 12 times real time for Sony 1080p25 on the hybrid path; about 0.75 GB per footage hour)
  - the Sony proxies show picture and sound in both browsers, and the screenshots or values are in the scratch directory
  - `openspec validate proxy-encode --strict` passes

  Recorded (2026-10-03; 16 cores, AMD VAAPI on `renderD128`, ffmpeg 8.1.2, Chrome 154.0.8037.92, Firefox 155.0):
  - Gates: `black --check` and `isort --check-only` clean; `mypy auto_reel_ng` clean (115 files); `pylint
    auto_reel_ng` 9.98 with only noise that is not from this change (the cairo `no-member` set and one
    `too-many-positional-arguments` in `api/events_read.py`); the full `pytest` (background, with `has_ffmpeg`, `gpu` and
    `requires_db`): 2514 passed, 6 skipped (the title-card tests that need Cairo/Pango and DejaVu Sans), in 4 min 54 s.
    A first full run failed three caplog tests because an earlier Alembic test had disabled the loggers; the proxy
    tests now re-enable theirs (as `test_runtime.py` does).
  - Nothing outside this change's packages: `git diff --stat -- auto_reel_ng/staleness auto_reel_ng/render
    auto_reel_ng/scheduler auto_reel_ng/persistence auto_reel_ng/api alembic web` prints nothing.
  - Dogfood on a scratch library of the ten samples in two events plus a zero-byte `tom.mp4` (959 s of footage):
    the first run (hybrid where it applies) took 46.6 s, exit 1, one `ERROR  2024-07-02 - Telefon och gamla/tom.mp4:
    File is empty (zero bytes)`, `10 generated (130.7 MB)`. The second run reported `0 generated`, `10 cached` in 2.1 s,
    **not under 1 s as the task guessed**: `auto-reel --help` alone takes 0.9 s of imports, and the rest is the
    version check and the capability self-test, which run before the first cache lookup. `--device cpu` into a
    second cache took 54.3 s (`124.9 MB`). `find auto-reel-media -newer marker` printed nothing; the cache held ten
    entries and no `.part`.
  - Speed: 20.6 times real time over the set on the hybrid path, 17.7 on the CPU path; Sony 1080p25 alone 13.9 and 11.3
    times (research: about 12 on the hybrid path). The three rotated or MPEG-4 clips took the CPU path on the AMD profile.
  - Size: 0.47 to 0.49 GB per footage hour over this set, but 79 % of its seconds are the legacy MPEG-4 clip; the nine
    camera clips alone are 1.05 GB per hour on the hybrid path (they are heavy clips). Research: 0.75 GB per hour at
    `-bf 0`; E1: `-bf 2` is 0.83 of that, so about 0.62. The hybrid path is not always smaller: the 4K50 clip is
    11.8 MB hybrid against 7.2 MB on the CPU path, the others within 12 %.
  - Browsers (scratch Range server, Playwright from the scratch directory only): Chrome 154: `videoWidth` 960 for both
    Sony proxies (PCM sources, 1080p and 4K), decoded audio peak 0.219 and 0.048, first frame 26 and 32 ms, the MP3
    legacy clip 0.17, the rotated phone clip 540x960 with peak 0.76. Firefox 155.0: the same four files give
    `videoWidth` 960 / 540, `mozHasAudio` true, playback advances 2.45 s, first frame 15 to 94 ms. A decoded peak could not
    be read in Firefox: the headless AudioContext stays suspended (the research hit the same). Screenshots looked at:
    picture correct in both; the rotated sample is upright as `ffmpeg`'s own autorotate shows it (the sample's content
    is landscape and tagged -90°, so it is sideways when displayed, in the proxy and in the source alike).
  - Mutations: 24 deliberate breaks of the behaviours above (the key's digest, `libfdk_aac`, scene-cut keyframes, GPU
    rotation, 10-bit on the GPU, no CPU retry, retrying a stall, the 50 ms tolerance, the frame-count and audio checks,
    replacing an incomplete entry, the sweep, the lost-rename branch, discarding the build directory, hand
    rotation, `-noautorotate`, anamorphic scaling, HDR tone-mapping, the progress guard, a hit that rebuilds, the cancel
    flag, link grouping, the ERROR line's cause, the facts' duration, the non-atomic publish) were each killed by a
    test. One more (a clamp in the progress wrapper) turned out to be dead code behind its own guard and was removed.
