## Context

See proposal.md, section Why. These code facts (at `47e46f4`) shape the approach.

- **`probe/`: the duration source.**
  - `probe_media(path, *, runtime)` (`probe/media.py:43`) runs one ffprobe pass.
  - It raises `ProbeError` for a missing file, an empty (zero-byte) file, no video stream, or
    unparseable output. It checks for an empty file before ffprobe runs.
  - `ClipMetadata.duration` comes from the format block, then the video stream, and is **`0.0` when
    neither has one** (`_parse_duration`, `media.py:183-193`). A caller that needs a real duration must
    reject `<= 0` itself.
  - `get_default_runtime()` gives the process-wide shared runtime.
- **`ffmpeg/`: the one place that runs subprocesses (Principle VI).**
  - `FfmpegRuntime()` resolves `ffmpeg` and `ffprobe`: explicit argument, then
    `AUTO_REEL_NG_FFMPEG`/`_FFPROBE`, then jellyfin, then `PATH`. It asserts ffmpeg >= 7.1 at
    construction.
  - `run(args)` runs with a list of arguments, no shell, and captured output.
  - A non-zero exit raises `FfmpegError("Command exited N: <cmd>\nstderr:\n…")`
    (`ffmpeg/runtime.py:192-201`).
  - `analysis/runner.py` is the precedent for wrapping `FfmpegError` and `ProbeError` into a
    per-clip typed error that names the clip.
- **`config/`: project settings.** `ProjectConfig` is frozen and every field is optional.
  - The `worker` and `api` maps are **opaque** there.
  - Their consumers validate them: `scheduler/config.resolve_worker_config` raises
    `config.project.ConfigError` naming `worker.<key>`.
  - A non-mapping value fails in `_require_mapping`.
- **CLI walk.**
  - `_project_context(args)` (`cli/commands.py:87`) loads `config.yaml`, applies `input`, `--years`
    and `--layout`, and enumerates `EventRef`s. The layout already drops `.reelignore` events
    (`ingest/layouts.py:108`). It reads `args.output`.
  - `scan_event(event_dir)` (`event/discovery.py:119`) lists video files one level deep: root clips,
    then one chapter per subfolder. It skips `original/` in any case, and chapter folders holding
    `.reelignore`.
  - A MISSING clip is by definition not on disk, so it never appears in the listing.
  - `scan` prints `ERROR  <event>: <reason>` per failed event and exits 1 if any failed.
- **Atomic write precedent.** `reel/writer.write_document` (`reel/writer.py:59-83`):
  1. writes a hidden sibling temporary file created with `O_EXCL`
  2. flushes and `fsync`s it
  3. `os.replace`s it over the target
  4. on `BaseException`, unlinks the temporary file and re-raises
- **A cache that must not be copied.** `analysis/cache.py` keys on `size` and `mtime_ns`, the right
  signal, but it writes into `<event>/.auto-reel/cache/`, that is, into the library. Thumbnails cannot
  live there: the MOL drive is often mounted read-only.
- **The dev library** (`scripts/make_dev_library.py`) symlinks clips from `DEST/clips/` into the events.
  - `s1710001.mp4` appears in five events.
  - `2024-10-05 - Trasig/trasig.mp4` is zero bytes.
  - `2024-09-01 - Sommarlov` references the MISSING `borttagen.mp4`.
  - `2024-08-20 - Två kapitel - Tjörn` has a `Kvällen/` chapter and an IGNORED root clip.

## Goals / Non-Goals

**Goals:**

- One engine operation, used unchanged by the CLI now and by the API in T2. A cache hit costs one
  `stat` and one hash, and no subprocess.
- Every failure is typed, per clip, and names its cause. No partial file, no fallback frame.
- The library is only read, by the CLI and by the operation.

**Non-Goals:**

- A negative cache, eviction, sharding, or a manifest of the cache. The directory holds nothing but
  `<key>.jpg` files and leftover temporary files.
- Concurrency control inside the engine. The CLI bounds it with `--jobs`, and T2 with its semaphore and
  in-flight map.
- Anything that reads `reel.yaml`.

## Research & Decisions

### Where the frame comes from

**Context**: The operator asked for "not the first frame but some percentage into the clip". Principle I
forbids guessing a duration.

**Explored**:
- **The first frame** (`-ss 0`): rejected by the request. For `s1710001.mp4` it is a different shot from
  the 25% frame.
- **ffmpeg's `thumbnail` filter**, which picks a "representative" frame from a batch. It decodes many
  frames, so it is slower, and choosing a good frame is the black- and frozen-frame avoidance that the
  brief defers.
- **`-sseof`**, which seeks from the end. It still needs a duration to express a fraction.
- **`position × probe_media(...).duration`**, with one attempt.

**Decision**: `t = position × duration`, where the duration is `probe_media(clip, runtime=runtime).duration`.
- A `ProbeError` becomes a `ThumbnailError`.
- A duration that is not finite or not `> 0` raises `ThumbnailError("<clip>: ffprobe reported no usable
  duration (<value>)")` before any ffmpeg runs.
- `t` is formatted as `f"{t:.3f}"`.
- One attempt only. A failure raises; no other timestamp is tried.

**Rationale**:
- The probe is the engine's single fail-loud source, and the analysis runner already uses it the same
  way.
- One attempt keeps a failure honest. The GUI shows "no preview" rather than a frame the operator did not
  ask for.

### The extraction command, measured

**Context**: The command must honour rotation and SAR (§2 #6), stay CPU-only (Principle III), and be
cheap enough for a 6,538-clip archive.

**Explored** on this host (ffmpeg 8.1.2 from `PATH`, 16 threads, local disk, warm page cache). The harness
was a scratch script outside the repository, using the engine's own `probe_media` and `FfmpegRuntime`. The
clips were:
- the four fixture clips: 1920×1080p50 H.264, about 45 Mb/s, keyframe every 0.48 s
- synthetic clips made in scratch: 3840×2160, coded 1080×1920, a 1920×1080 clip with a 90° display
  matrix, and a 720×576 clip with SAR 64:45

| clip | probe ms | extract ms (median of 3) | output | bytes |
|---|---|---|---|---|
| s1710001.mp4 (61.44 s) | 315 (first, colder) | 226–278 | 320×180 | 13,355 |
| s1710002.mp4 (39.84 s) | 173 | 310–320 | 320×180 | 16,106 |
| s1710003.mp4 (20.64 s) | 216 | 322–341 | 320×180 | 17,249 |
| s1710004.mp4 (27.84 s) | 160 | 302–307 | 320×180 | 12,844 |
| 3840×2160 synthetic | 83 | 172–179 | 320×180 | 4,395 |
| 1080×1920 synthetic | 83 | 109 | 101×180 | 3,230 |
| 1920×1080 + 90° matrix | 75 | 113 | 101×180 | 2,636 |
| 720×576 SAR 64:45, without the SAR fix | 74 | 88 | **225×180** (squashed) | 5,638 |
| 720×576 SAR 64:45, with the SAR fix | 74 | 92 | **320×180** | 6,318 |

- **Throughput** for probe plus extract, over 16 extractions of the fixture clips:
  - `--jobs 1`: 538 ms per clip
  - `--jobs 2`: 263 ms per clip
  - `--jobs 4`: 164 ms per clip
  - `-threads 1` made no material difference (514, 322 and 150 ms), so no thread flag is set.
- **JPEG size:** the average over the fixture was `-q:v 3` 20.2 KB, **`-q:v 5` 14.8 KB**, and `-q:v 7`
  11.7 KB.
- **10-bit HLG input** encodes without error to `yuvj420p`, not tone-mapped.
- **Output is byte-identical** across runs for the same input and time.
- **A review re-ran it independently** (2026-09-30). The fixture gave the same bytes per clip (13,355,
  16,106, 17,249 and 12,844), probe 147–168 ms, extraction 220–289 ms, and 437, 236 and 143 ms per clip
  at 1, 2 and 4 jobs. It also found:
  - **Output-path patterns.** Without `-update 1`, the `image2` muxer reads `%d` in the output path as
    an image-sequence pattern. A cache directory named `p%d` made ffmpeg write to `p1/…` and fail with
    exit 254, which would be reported against every clip. With `-update 1` the path is used literally,
    and the bytes are otherwise identical.
  - **Unknown SAR** (`N/A`): `sar` evaluates to 1, giving 320×180. A 720×576 SAR 64:45 clip with a 90°
    display matrix gives 101×180, so rotation and SAR compose.
  - **Names** with spaces, commas, `å ä ö` and a colon read fine as an absolute path. A *relative*
    `file:odd.mp4` is taken for ffmpeg's `file:` protocol and fails, so the engine passes the
    resolved absolute path.

**Decision**: `thumbs/thumbnail.thumbnail_args(clip, *, at, output)` returns exactly:

```
-hide_banner -nostdin -v error
-ss <at:.3f> -i <clip>
-map 0:v:0 -frames:v 1
-vf scale=trunc(iw*sar/2)*2:ih,scale=320:180:force_original_aspect_ratio=decrease,setsar=1
-c:v mjpeg -q:v 5 -f image2 -update 1 -y <output>
```

- **Input seeking.** `-ss` before `-i` is fast. ffmpeg's accurate seek decodes from the previous
  keyframe up to `at`, so the frame is the one at `at`, not the keyframe before it.
- **The first `scale` makes pixels square**, at even width, so anamorphic footage is not squashed.
- **The second `scale` fits the box** and keeps the aspect ratio.
- **Rotation is ffmpeg's default `autorotate`.** The display matrix is applied before the filter graph,
  so `iw` and `ih` are already the upright size. No `-hwaccel` is used.
- **`-q:v 5`** is about 15 KB per clip, crisp at 2× device pixel ratio for a 160×90 CSS thumbnail.
- **`-update 1`** makes `image2` write the literal output path, so a `%` in the cache directory is never
  read as a sequence pattern.

**Rationale**:
- Measured correct for every shape the archive holds: mixed 720p, 1080p, 4K and portrait, per the survey.
- About 0.54 s per clip serially, so ≈59 min for the whole archive at `--jobs 1` and ≈29 min at the
  default `--jobs 2`, on local disk. That is an upper bound: the 6,538 clips include the `.reelignore`d
  trips, which the walk skips.
- The pure argument builder gets a golden-argument unit test (Technology Standards).

### What "no frame" looks like

**Context**: The brief wants "ffmpeg yields no frame" to fail. How ffmpeg 8.1 reports that was not known.

**Explored**:
- a seek past the end (`-ss 100` on a 27.84 s clip)
- a seek at exactly the duration
- a faststart copy truncated to 25% of its bytes: ffprobe still reports the full 8 s, and the cut falls
  at 2.08 s
- audio-only and zero-byte files

**Decision**:
- **Exit 234 and no frame.** Every "nothing decoded at `t`" case exited **234** and wrote no frame.
  - This covers the seek past the end, the seek at the duration, and the truncated copy at 4 s and
    6 s. At 1 s and 2 s, before the cut, the truncated copy gave a real frame with exit 0.
  - The stderr is misleading: mjpeg "Non full-range YUV is non-standard … Could not open encoder
    before EOF … Nothing was written into output file".
  - `thumbnail_for` therefore wraps any `FfmpegError` as `ThumbnailError(clip, f"no frame extracted
    at {at:.3f}s of {duration:.3f}s: {exc}")`, so the operator reads the real cause first and still
    gets the command and stderr.
- **Exit 0 with an empty or missing temporary file** raises the same error. It was never observed, and
  the check is cheap insurance for Principle I.
- **Audio-only files and zero-byte files** never reach ffmpeg. `probe_media` raises first ("No video
  stream", "File is empty").
- **The review's extra cases fail the same way (exit 234, no frame):**
  - a one-frame clip (0.04 s) at the default 0.25: its only frame lies before `t` and is dropped
  - a 0.2 s clip at `p = 0.99`, and a clip whose audio (6 s) outlasts its video (4 s) at `p = 0.99`
  - an MPEG-TS clip near its end
  - a 0.2 s clip at 0.25 gives a frame
- **Any exit code, same wording.** Exit 234 is `EINVAL`, which ffmpeg also returns for a bad option, so
  the code is not a "no frame" signal and the design does not branch on it.

**Rationale**: One message shape for "no frame", whichever way ffmpeg expresses it. The truncated faststart
clip at `position=0.75` makes a real `has_ffmpeg` test of the no-fallback rule.

### Cache location, key and write

**Context**: The cache must be outside the library, survive restarts, be shared by the CLI and the
service, and be invalidated by a changed clip without reading it.

**Explored**:
- **The analysis-style sidecar under `<event>/.auto-reel/`:** it writes into the library, so it is
  rejected.
- **Postgres rows:** D-7 allows derived state, but blobs in the job database would make the thumbnail
  route depend on the database, which T2 does not want.
- **A content hash in the key:** it would read every byte of every clip, about 1 TB for the archive,
  so it is rejected.
- **The resolved path, size and `mtime_ns`:** the analysis cache's signal, plus the path.

**Decision**:

```python
THUMBNAIL_VERSION = 1           # bump when thumbnail_args changes the output bytes
THUMBNAIL_BOX = (320, 180)

def thumbnail_key(clip_path: Path, *, position: float) -> str:
    """sha256 hex over json.dumps([str(resolved), st_size, st_mtime_ns, position,
    list(THUMBNAIL_BOX), THUMBNAIL_VERSION]). The stat's OSError propagates unchanged."""

def thumbnail_path(clip_path: Path, *, position: float, cache_dir: Path) -> Path:
    """cache_dir / f"{thumbnail_key(...)}.jpg" — computes, never creates or generates.
    The stat's OSError propagates unchanged (FileNotFoundError for a vanished clip)."""

def thumbnail_for(
    clip_path: Path,
    *,
    position: float,
    cache_dir: Path,
    runtime: Optional[FfmpegRuntime] = None,
) -> Path:
    """The cached JPEG for the clip, generating it first when absent."""
```

`thumbnail_for` does the following:

1. **Cache hit:** `target = thumbnail_path(...)`. An `OSError` from the stat raises
   `ThumbnailError(clip, "cannot stat the clip: <strerror>")`. If `is_cached(target)`, it returns
   `target`, with no probe and no ffmpeg. `is_cached` wraps `target.is_file()`: Python 3.13 lets a
   `PermissionError` through for an unsearchable cache directory, and that raises
   `ThumbnailCacheError("<cache_dir>: cannot read thumbnails: <exc>")`.
2. **Probe:** `runtime = runtime or probe.get_default_runtime()`. It probes the clip's resolved,
   absolute path and computes `at`, as in "Where the frame comes from". ffmpeg reads the same path.
3. **Temporary file:**
   - `cache_dir.mkdir(parents=True, exist_ok=True)`
   - it creates `tmp = cache_dir / f".{key}.{uuid4().hex}.tmp"` with
     `os.open(O_WRONLY|O_CREAT|O_EXCL, 0o666)` and closes it
   - any `OSError` in this step raises `ThumbnailCacheError("<cache_dir>: cannot write thumbnails:
     <exc>")`
4. **Extract:** `runtime.run(thumbnail_args(clip, at=at, output=tmp))`. `FfmpegError` becomes the
   "no frame" `ThumbnailError`. A `tmp` of size 0 afterwards raises the same error.
5. **Finalize:** it opens `tmp`, `fsync`s it, and runs `os.replace(tmp, target)`. An `OSError` here
   raises `ThumbnailCacheError`. It then returns `target`.
6. **Clean up:** on any `BaseException` from step 3 on, it unlinks `tmp` with `OSError` suppressed and
   re-raises.

The key details:
- **`clip_path.resolve()`** follows symlinks, so the dev library's shared clips share one file. The
  resolved path is also what the probe and ffmpeg read, so a relative name such as `file:x.mp4` is
  never taken for an ffmpeg protocol.
- **Two layers of error.** The pure functions let the stat's `OSError` through unchanged, as
  `scan_event` does, and each caller handles it: the CLI's cached check counts the clip as failed ("The
  `thumbs` subcommand"). `thumbnail_for` wraps it as a `ThumbnailError`, and the CLI reports it as that
  clip's failure.
- **Every `ThumbnailError` message starts with the clip's path**, then `: ` and the cause, like
  `AnalysisError`'s. The error carries `clip` and `reason` (the pattern of `EventMetadataError`), and the
  reason never repeats the path: for a probe failure it is the `ProbeError` message with its first
  mention of the probed path dropped, and for an `OSError` it is the `strerror`. The CLI prints
  `ERROR  <event>/<identity>: <reason>`, so each line names the clip once.
- **`json.dumps` of a list** is a canonical, unambiguous encoding: floats use their shortest repr. With
  the default `ensure_ascii`, a non-UTF-8 file name (surrogate escapes) still encodes.
- **The full 64-hex digest is the file stem.** T2 uses it as the strong ETag.
- **The directory is flat:** about 6.5 k files, which is fine for ext4 or btrfs.

**Rationale**:
- The key costs 27 µs per clip, warm and local: a stat plus a sha256.
- **Pre-creating `tmp` classifies an unwritable cache before ffmpeg runs.** Otherwise the operator
  would see ffmpeg failing to open its output, reported against the clip. That is why `-y` is in the
  arguments. It catches a missing, read-only or permission-denied directory. It does **not** reliably
  catch a full disk: an empty file needs no data blocks, so ffmpeg's write fails instead (Risks).
- The same shape as `write_document` means one pattern in the codebase.

### Two error types

**Context**: The brief names `ThumbnailError`. T2 answers a failed extraction with the closed failure kind
`thumbnail_failed`, and a failed cache write with a 502 detail and no kind. The CLI must not print 6,538
identical `ERROR` lines when the cache directory is read-only, missing or not permitted.

**Decision**: two classes in `errors.py`, both direct subclasses of `EngineError` and siblings, so that
`except ThumbnailError` never catches a cache failure:
- **`ThumbnailError(EngineError)`:** this clip cannot give a thumbnail. It covers a clip that cannot be
  statted, a probe failure, no usable duration, and no frame.
- **`ThumbnailCacheError(EngineError)`:** the cache directory cannot be created, read or written, or the
  rename fails.

**Rationale**: Each has a real consumer that treats it differently: per clip versus fatal in the CLI, and
`thumbnail_failed` versus no kind in T2. Principle VII requires a real use, and this has two.

### Settings

**Context**: Two keys, D-2 layering. The CLI and the service run with different working directories.

**Decision**: `ProjectConfig` gains `thumbnails: Mapping[str, object]`, parsed with `_require_mapping`
exactly like `worker`. `thumbs/settings.py` holds:

```python
DEFAULT_POSITION = 0.25

@dataclass(frozen=True)
class ThumbnailSettings:
    position: float
    cache_dir: Path

def default_cache_dir() -> Path:
    """$XDG_CACHE_HOME/auto-reel/thumbnails when XDG_CACHE_HOME is absolute, else
    Path.home()/.cache/auto-reel/thumbnails (a relative XDG_CACHE_HOME is ignored, per the XDG spec)."""

def resolve_thumbnail_settings(config: ProjectConfig, project_root: Path) -> ThumbnailSettings:
    """Validate config.thumbnails; ConfigError naming thumbnails.<key> on a bad value."""
```

The validation rules:
- **`position`:** an `int` or `float`, not `bool`, finite, with `0 < p < 1`. Otherwise it raises
  `ConfigError("thumbnails.position must be a number between 0 and 1 (exclusive), got …")`.
- **`cache_dir`:** a `str`, run through `Path(...).expanduser()`, which must then be absolute. Otherwise it
  raises `ConfigError` naming `thumbnails.cache_dir`.
- **Outside the library, whatever its source.** The chosen directory, configured or default, is
  `.resolve()`d. It must not be relative to `project_root.resolve()`, nor to the walked input directory
  `(project_root / config.input_dir).resolve()` when `input` is set, which may lie outside the root.
  Otherwise it raises `ConfigError` naming `thumbnails.cache_dir` and the directory it falls inside. For
  the default it also says to set `thumbnails.cache_dir`.
- **Unknown keys** under `thumbnails` are ignored, as they are under `worker`.
- **The returned `cache_dir`** is the expanded, absolute path as configured or defaulted; the `.resolve()`d
  form is used only for the outside-the-library check.

**Rationale**:
- **Absolute only:** a relative path would mean different directories for `serve` and the CLI, silently
  splitting the cache.
- **Outside the root and the input directory, default included:** this is what makes "writes nothing
  under the project root" unconditional. Checking only a configured value would let an absolute `input`
  on the archive, or an `XDG_CACHE_HOME` inside the library, put the cache in the library. The archive is
  often read-only anyway.
- **No CLI flag for either key (YAGNI):** `--jobs` is the only new flag.
- **No injectable environment.** `Path.home()` and `expanduser()` both read `$HOME`, so the tests set
  `HOME` and `XDG_CACHE_HOME` with `monkeypatch.setenv`/`delenv`. An `environ` parameter would not have
  isolated `~` expansion anyway.

### The `thumbs` subcommand

**Context**: Principle V wants the engine capability reachable from the CLI in the same change. The
operator also wants to pre-fill the cache for the archive overnight, rather than paying ffmpeg on first
view.

**Decision**: `cmd_thumbs(args)` in a new `cli/thumbnails.py`, registered in `cli/main.py`. It is not in
`cli/commands.py`, because adding it there takes that module from 930 to 1,056 lines, past pylint's
`too-many-lines` limit (1,000), and nothing in the repository disables that check. It imports
`_project_context` from `.commands` unchanged.
- **Flags:** `root`, `--years`, `--layout`, `-v` and `--jobs`. `--jobs` is `type=_positive_int`, default
  2. `_positive_int` is a **new** argparse type in `cli/main.py`: `int(value)`, and
  `argparse.ArgumentTypeError` below 1. No such helper exists at `47e46f4`; the worker's pool flags use
  plain `int`. There is no `-o`, since output is irrelevant here. `set_defaults(output=None)` lets
  `_project_context` be reused unchanged. `_add_common_args` gains an `output: bool = True` keyword so
  `thumbs` can leave `-o` out.
- **Order of work:** `_project_context` first. Then `resolve_thumbnail_settings(ctx.config,
  ctx.project_root)`, so a `ConfigError` stops before anything runs. Then one `FfmpegRuntime()`, which
  asserts the version once.
- **Per event, in walk order:**
  - `scan_event(ref.event_dir)`, where an `OSError` gives `ERROR  <event>: cannot list event folder:
    <strerror>`, and the event counts as failed
  - then, for each identity in `listing.identities` (sorted), clip path `event_dir / identity`: if
    `is_cached(thumbnail_path(...))`, the clip is **cached**. An `OSError` from the path's stat (the clip
    vanished between listing and `stat`) counts the clip as failed. Otherwise it is submitted to one
    shared `ThreadPoolExecutor(max_workers=args.jobs)` as `thumbnail_for(...)`.
  - **The event is a barrier.** `cmd_thumbs` waits for all of an event's futures before it prints that
    event and moves on. A clip shared with a later event is therefore already cached when that event is
    checked, and the counts below are deterministic. Two identities of one event with the same symlink
    target are both extracted, harmlessly.
  - `ThumbnailError` counts the clip as failed and collects its `ERROR` line,
    `ERROR  <event>/<identity>: <reason>`. The event's results are collected in identity order, so
    output is deterministic.
- **Fatal errors and interruption:** on `ThumbnailCacheError`, or any other `BaseException` such as
  Ctrl-C, the pool is shut down with `cancel_futures=True` before re-raising, so no queued clip starts.
  The pool's default shutdown on leaving a `with` block would otherwise run the rest of a large event's
  queue after Ctrl-C. `main` prints `error: …` and returns 1 for the cache error. `KeyboardInterrupt`
  propagates as it does for every other subcommand.
- **Output:**

  This is what a first run over the dev library prints. It has 22 clips in 11 events, but only five
  distinct symlink targets:

  ```
  2023-06-23 - Midsommar - Dalarna: 2 clips, 2 generated
  …
  2024-06-27 - Grillning med grannar: 4 clips, 1 generated, 3 cached
  …
  ERROR  2024-10-05 - Trasig/trasig.mp4: File is empty (zero bytes)
  2024-10-05 - Trasig: 1 clip, 1 failed
  …
  thumbnails: 22 clips in 11 events: 4 generated, 17 cached, 1 failed (cache: /home/emil/.cache/auto-reel/thumbnails)
  ```

  An `OSError` from the cached check itself prints `ERROR  <event>/<identity>: cannot stat the clip:
  <strerror>` and counts the clip as failed. When an event folder could not be listed, the summary
  also says `, N event(s) unreadable` before the cache path.

- **Exit code:** 1 when any clip or event failed, else 0. "No events found under …" exits 0, like `scan`.

**Rationale**:
- **Threads, not processes:** the work is a subprocess, which releases the GIL.
- **One shared pool** keeps `--jobs` a true global bound.
- **Per-event collection** gives progress lines during a long run, and the archive averages about 46
  clips per event.
- **Default 2:** measured 2× over serial, and the same bound T2 uses in the service.
- **Cached versus generated** is decided by the no-generation path check, so `thumbnail_for` keeps T2's
  simple `-> Path` contract.

### Where D-11 is recorded

**Decision**: This change adds **D-11** to HLD §7. It is a v1 scope change, and a cache location and
format that T2 and T3 build on, so it outlives the change. The text:

> **D-11 — Clip thumbnails in GUI v1** (2026-09-30, change `clip-thumbnails`). Every clip on disk gets one
> JPEG thumbnail, pulled forward from v2 at the operator's request.
> - **The frame** is the one at `thumbnails.position` × the clip's ffprobe duration (default 0.25,
>   0 < p < 1). It is never the first frame and never at a guessed time. There is one attempt: a clip with
>   no frame there has no thumbnail.
> - **Extraction** uses CPU decode through the engine's ffmpeg runtime: input seek, one frame,
>   SAR-corrected, the display rotation applied and the editorial `rotate` not, fitted inside 320×180.
> - **The cache** is derived state in a file cache outside the library: `$XDG_CACHE_HOME/auto-reel/thumbnails/`
>   (else `~/.cache/…`), or `thumbnails.cache_dir`. It is keyed by the resolved clip path, size, mtime,
>   position, box and `THUMBNAIL_VERSION`, written atomically, never in Postgres (D-7), and never evicted
>   in v1 (≈15 KB per clip).
> - **Filling it:** `auto-reel thumbs` fills it in batch. The service's thumbnail route fills it on
>   request (change `clip-thumbnail-endpoint`).
> - **Still open:** proxies and scrubbing stay v3 (§8.11). (§4.10)

The HLD also changes in these places:
- **§4.10:** v1 gains "clip thumbnails (D-11)", and v2's "thumbnails/poster frames" becomes
  "event poster frames".
- **§4.10's slice plan:** one standalone sentence after the D-10 paragraph, the same way D-10 is
  recorded there rather than as a table row. It says that clip thumbnails are pulled forward as D-11 in
  three changes (`clip-thumbnails` → `clip-thumbnail-endpoint` → `clip-thumbnails-screen`), and that
  `clip-thumbnail-endpoint` is the one extra `api/` prerequisite this adds to v1. The slice notes' existing
  sentence about further `api/` prerequisites is `render-progress-screen`'s to rewrite; this change does
  not edit it.
- **§4.7:** the Postgres index parenthesis drops "thumbnails".
- **§6:** phase 9 becomes "look editor + analysis review".
- **§8.11:** "clip thumbnails ✅ resolved → D-11; proxies/HLS for scrubbing remain open (v3)".
- **The §4.10 research pointer** is updated to match.

### No fingerprint or render impact

**Decision**: No `RENDER_GRAPH_VERSION` bump, and no fingerprint change.

**Rationale**:
- Nothing under `render/` or `staleness/` changes.
- The cache is outside every event directory, so no clip signal or manifest sees it.
- `thumbs` never writes `reel.yaml`.

## Failure behavior and idempotency

- **Per clip:** a `ThumbnailError` names the clip and its cause, and leaves no `<key>.jpg` and no temporary
  file behind, since cleanup runs on `BaseException`. The CLI reports it and continues. The next run
  retries it, because there is no negative cache.
- **Cache:** a `ThumbnailCacheError` names the directory. The CLI stops, with exit 1. T2 answers 502 with
  no kind.
- **Config:** a `ConfigError` names `thumbnails.<key>`. It is raised before any subprocess runs.
- **Missing ffmpeg or ffmpeg < 7.1:** `FfmpegError` or `FfmpegVersionError` is raised when the CLI builds
  its runtime, before any clip is touched.
- **Re-run:** cached thumbnails are skipped, costing one stat and one hash each. Only new or changed clips,
  and previously failed ones, run ffmpeg. There is no `--force`. To regenerate everything, delete the
  cache directory. A changed extraction bumps `THUMBNAIL_VERSION`, which re-keys every file.
- **Killed mid-extraction** (Ctrl-C, a killed `serve`):
  - normally the temporary file is unlinked by the `BaseException` handler
  - Ctrl-C in `thumbs` also reaches the running ffmpeg children (one process group), so their clips fail
    and clean up, and the cancelled pool starts no queued clip
  - on SIGKILL a hidden `.<key>.<hex>.tmp` may remain, but it is never read, because only `<key>.jpg`
    is served, and the next request regenerates the thumbnail
  - `<key>.jpg` only ever appears complete, through `os.replace` after `fsync`
- **Concurrent writers of one key** (the CLI and `serve`, or two CLI workers on a shared symlink target):
  each writes its own temporary file and renames it over the other. The output is byte-deterministic, so
  the last rename wins harmlessly.
- **Worker or job restarts:** not applicable. No job, no DB row, no manifest.

## Risks / Trade-offs

- **[Cache per user and host]** `serve` running as another user, or in a container, has its own
  `$XDG_CACHE_HOME`, so a CLI pre-fill would not help it. → Set `thumbnails.cache_dir` in the project's
  `config.yaml` so both use one directory. README gives that advice; a worked container example waits
  for the Containerfile fix, out of scope for this round.
- **[No cache beside the media]** A `thumbnails.cache_dir` inside the project root or the `input`
  directory is refused, the default included. → Accepted: it keeps "no library writes" unconditional; an
  operator with a read-write library who wants one there needs a follow-up.
- **[Remounting re-keys everything]** The key includes the resolved path, so mounting MOL at another path,
  or copying the library, regenerates every thumbnail: about 30 minutes at `--jobs 2`, measured on local
  disk. → Accepted. A content hash would read about 1 TB. Old files stay until the directory is deleted
  (no eviction).
- **[USB throughput unmeasured]** All timings are local disk with a warm page cache. Each extraction reads
  roughly one GOP around `t`, 3–6 MB at the fixture's bitrate, plus the header for the probe. → `--jobs`
  lets the operator trade speed against thrashing a flaky drive. The default of 2 stays; the operator
  lowers it on a slow USB drive.
- **[Duplicate extraction across symlinks in one event]** `thumbs` has no in-flight de-duplication, so two
  identities of one event with the same symlink target are each extracted once in a run. → Accepted:
  harmless, the output is byte-identical and the last rename wins.
- **[The probe dominates cheap clips]** Probing (75–315 ms) costs as much as extraction. → Principle I and
  the brief require the probe's duration, and a cache hit skips both.
- **[Positions near 1 can fail]** The probe's duration is the container's. When audio outlasts video, or
  the last frame's timestamp precedes the duration, `p = 0.99` can land past the last frame and fail. →
  One attempt by design. The default 0.25 is far from the end. This is documented in the config
  reference.
- **[Very short clips]** A one-frame clip fails at any position: its only frame lies before `t` and is
  dropped (measured, exit 234). → Accepted by D-11's single-attempt rule: such a clip never gets a
  thumbnail. A camera never records a one-frame clip, and the GUI shows "no preview". Task 3.3 pins the
  message.
- **[MPEG-TS has no seek index]** For `.mts`/`.m2ts`, ffmpeg's input seek is timestamp-searched, not
  indexed. On a synthetic TS with a 0.48 s GOP and a 1.4 s start time, `-ss 1.000` gave the frame at
  1.44 s, the next keyframe, and `-ss 3.900` of 4.0 s gave none. With a single keyframe, no position
  gave a frame. The start-time offset itself is honoured. → Accepted, as the spec's MAY states: the frame
  is still a real frame within one GOP of `t`, never a guessed one. The archive's MTS files sit in
  `original/`, which is skipped.
- **[No extraction timeout]** `FfmpegRuntime.run` has no timeout, and this change adds none. An ffmpeg
  blocked on a stalled USB read holds one CLI worker, or one of T2's two slots, until the read returns.
  T2's design points its hang risk at this change, so the answer is recorded here. → A non-goal for v1. A
  drive that drops off returns `EIO` and ffmpeg exits. A process blocked in uninterruptible I/O
  cannot be killed by a timeout either. A `timeout=` on the runtime is a follow-up in `ffmpeg/`, after
  measuring extraction on the real MOL drive.
- **[A full cache disk]** Creating the empty temporary file usually succeeds on a full disk, so ffmpeg's
  write fails instead. Each clip is then a `ThumbnailError` whose stderr says "No space left on device",
  not one `ThumbnailCacheError`. → Accepted, with classification left as a follow-up: the whole cache is
  about 100 MB. Reserving space in step 3 (`os.posix_fallocate`) would classify it, but ffmpeg's `-y`
  truncation frees the reservation again, so it is a heuristic this change does not add.
- **[Flat HDR]** HLG and PQ clips are not tone-mapped. → Non-goal. The surveyed archive is all SDR.
- **[Leftover temporary files after SIGKILL]** → Hidden and never read, so rare and harmless. A
  sweep can come with eviction, if ever.
- **[A misleading ffmpeg message]** ffmpeg 8.1 reports "no frame decoded" as an mjpeg encoder-open error.
  → The `ThumbnailError` message leads with "no frame extracted at <t>s of <d>s" and keeps the stderr
  after it.
- **[Task 4.1 is the largest task]** It holds the parser, `cmd_thumbs` and most CLI tests. → If it
  overruns its 1–2 hours, it may be split in two (parser, then command); a note only, the count stays 10.

## Migration Plan

There is no data or schema migration.
- **`thumbnails` in `config.yaml`** is optional. Existing projects behave as before until `thumbs` runs,
  which then creates the default cache directory.
- **Rollout:** optionally run `auto-reel thumbs <root>` once over the archive to pre-fill the cache.
- **Rollback:** revert the package, the CLI and the config field. The cache directory can be deleted at
  any time.

## Open Questions

None. The earlier questions are settled under Risks: the refused in-library `cache_dir`, no
de-duplication across symlinks within one run, and README advice (not a worked container example) for a
shared `cache_dir`.
