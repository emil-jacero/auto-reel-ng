## 1. Gate

- [ ] 1.1 Gate: none. `clip-thumbnail-endpoint` (T2) waits for this change. Check the starting point:
  - `test ! -e auto_reel_ng/thumbs`
  - `git diff 47e46f4 -- openspec/specs/headless-cli/spec.md` prints nothing. If the `auto-reel entry point with subcommands` requirement differs, re-base this change's MODIFIED block on the current text before implementing.
  - `git diff --stat 47e46f4 -- auto_reel_ng/errors.py auto_reel_ng/config/project.py auto_reel_ng/cli/` is informational. Code drift there merges normally, and only spec drift needs the re-base.
  - `ls openspec/changes/*/specs/headless-cli` lists only this change. If another open change modifies `headless-cli`, stop and report.

  Verify: every check holds, or the re-base or the stop is recorded in this task.

## 2. config/ + thumbs/ — settings and errors

- [ ] 2.1 Add the settings and errors (design "Settings", "Two error types"):
  - `errors.py`: `ThumbnailError(EngineError)` and `ThumbnailCacheError(EngineError)`, as siblings, each with a docstring
  - `config/project.py`: `ProjectConfig.thumbnails: Mapping[str, object]`, parsed with `_require_mapping(data.get("thumbnails"), "thumbnails", source)`, and the module docstring updated
  - new `auto_reel_ng/thumbs/__init__.py` and `thumbs/settings.py`: `DEFAULT_POSITION = 0.25`, `ThumbnailSettings`, `default_cache_dir()`, `resolve_thumbnail_settings(config, project_root)`. `__init__.py` exports `ThumbnailSettings` and `resolve_thumbnail_settings`.

  Tests go in a new `tests/test_thumbs_settings.py`. Each sets `HOME` to `tmp_path / "home"` with `monkeypatch.setenv`, and sets or deletes `XDG_CACHE_HOME` the same way. `Path.home()` and `expanduser()` both read `$HOME`, so nothing touches the real home. The project root is `tmp_path / "library"`, a sibling of both:
  - no settings: the position is `0.25` and the cache is `<home>/.cache/auto-reel/thumbnails`
  - `XDG_CACHE_HOME=/var/cache/emil` gives `/var/cache/emil/auto-reel/thumbnails`
  - a relative `XDG_CACHE_HOME` is ignored
  - `cache_dir: ~/thumbs` wins over `XDG_CACHE_HOME`
  - these each raise `ConfigError` naming `thumbnails.position`: `position` set to `0`, `1`, `1.5`, `"a quarter"`, `true` and `.nan`
  - `position: 0.5` is accepted
  - these each raise `ConfigError` naming `thumbnails.cache_dir`:
    - `cache_dir: thumbs` (relative)
    - an absolute path under the project root, reached both directly and through a symlink
    - a path under an absolute `input:` directory that lies outside the project root
    - no `cache_dir`, with `XDG_CACHE_HOME` pointing inside the project root (the default is checked too)

  Add one case to `tests/test_project_config.py`: `thumbnails: 3` raises `ConfigError` naming `'thumbnails'`.

  Verify:
  - `.venv/bin/python -m pytest tests/test_thumbs_settings.py tests/test_project_config.py` passes
  - `.venv/bin/python -m mypy auto_reel_ng` is clean

## 3. thumbs/ — key, arguments, extraction

- [ ] 3.1 Add `thumbs/thumbnail.py` with `THUMBNAIL_VERSION = 1`, `THUMBNAIL_BOX = (320, 180)`, `thumbnail_key`, `thumbnail_path` and `thumbnail_args` (design "The extraction command, measured", "Cache location, key and write"). Export them from `thumbs/__init__.py`. Tests in a new `tests/test_thumbs.py`:
  - **golden arguments:** `thumbnail_args(Path("s1710001.mp4"), at=15.36, output=Path("/c/.k.x.tmp"))` equals the exact list in the design, with `-ss 15.360` before `-i`, `-update 1` before `-y`, and no `-hwaccel`
  - **the key** is stable across calls, and changes when:
    - one byte is appended to the clip
    - `os.utime(ns=…)` changes the mtime
    - the position changes
    - `THUMBNAIL_VERSION` is monkeypatched
  - **two symlinks** to one file give the same key
  - **a missing clip:** `thumbnail_key` and `thumbnail_path` raise `FileNotFoundError` unchanged (callers handle it)
  - **`thumbnail_path`** leaves a non-existent `cache_dir` non-existent

  Verify:
  - `.venv/bin/python -m pytest tests/test_thumbs.py` passes
  - mypy is clean
  - `grep -rn "subprocess\|vaapi\|nvenc\|qsv\|cuda" auto_reel_ng/thumbs` prints nothing
- [ ] 3.2 Add `thumbnail_for` with the six steps in design "Cache location, key and write", and export it from `thumbs/__init__.py`, which then exports `thumbnail_for`, `thumbnail_path`, `resolve_thumbnail_settings` and `ThumbnailSettings` (the names T2 imports). Tests go in `tests/test_thumbs.py`. They use a fake runtime that records its argument lists and writes JPEG bytes to the last argument, or raises, plus a monkeypatched `thumbs.thumbnail.probe_media`:
  - **a cache hit** returns the existing `<key>.jpg` and calls neither the probe nor the runtime
  - **a missing clip** raises `ThumbnailError` whose message starts with the clip's path
  - **a miss** with duration `61.44` runs once with `-ss 15.360`. Afterwards `<key>.jpg` exists and no `.tmp` file remains in the cache directory.
  - **a clip reached through a relative symlink** is probed and read (`-i`) at its resolved, absolute path
  - **duration `0.0`** raises `ThumbnailError` ("no usable duration"), and the runtime is not called
  - **a `ProbeError`** ("File is empty (zero bytes)") becomes a `ThumbnailError` that names the clip
  - **an `FfmpegError`** becomes `ThumbnailError`, whose message starts with `<clip>: no frame extracted at 6.960s of 27.840s` and keeps the stderr. No file is left in the cache directory.
  - **exit 0 with an empty output** raises the same error
  - **a cache path under a regular file** (not creatable) raises `ThumbnailCacheError` naming the directory, not `ThumbnailError`
  - **a `KeyboardInterrupt`** from the fake runtime propagates, and leaves neither the `.tmp` file nor `<key>.jpg`
  - **two concurrent calls for one clip**, from two threads whose fake runtime waits on a shared `threading.Barrier(2)` before writing, both return the same `<key>.jpg`. It holds the fake's full bytes, and no `.tmp` file remains.

  Verify:
  - `.venv/bin/python -m pytest tests/test_thumbs.py` passes
  - mypy is clean
  - `.venv/bin/python -c "from auto_reel_ng.thumbs import ThumbnailSettings, resolve_thumbnail_settings, thumbnail_for, thumbnail_path"` succeeds
- [ ] 3.3 Add a new `tests/test_thumbs_ffmpeg.py`, with every test marked `has_ffmpeg` and using the `runtime` fixture. The shaped clips come from the existing `make_clip` fixture (`tests/conftest.py`), 1–2 s long. Its `rotate=` already attaches the display matrix in the input-side `-display_rotation` stream-copy pass that ffmpeg ≥ 8 needs; the option is refused after `-i`. Each output's size is read with `run_ffprobe(["-v","error","-show_entries","stream=width,height","-of","csv=p=0", jpg])`:
  - 1920×1080 gives `320,180`
  - 1080×1920 gives `101,180`
  - 1920×1080 with `rotate=90` gives `101,180`
  - 720×576 with `setsar="64/45"` gives `320,180`
  - 720×576 with `setsar="64/45"` and `rotate=90` gives `101,180`
  - 3840×2160 gives `320,180`
  - a zero-byte `trasig.mp4` raises `ThumbnailError`
  - **a truncated copy:** a 4 s `testsrc2` clip made through `runtime.run` with `-preset ultrafast -movflags +faststart`, cut to its first quarter of bytes. At `position=0.75` it raises `ThumbnailError` containing `no frame extracted`, and leaves the cache directory with no `.jpg` and no `.tmp`.
  - **a one-frame clip:** `make_clip("one.mp4", fps=30, duration=1/30, audio=False)`, about 0.034 s. At the default `position=0.25` it raises `ThumbnailError` whose message contains `no frame extracted at {0.25 * d:.3f}s of {d:.3f}s`, with `d` read from `probe_media`, and leaves no `.jpg` and no `.tmp`. No other timestamp is tried (D-11's single attempt).
  - **a `%d` in the cache directory:** a `cache_dir` named `p%d` gets its `<key>.jpg` inside `p%d/`, and no `p1/` appears
  - the source clip's bytes and `st_mtime_ns` are unchanged
  - the same call a second time returns the same path without running ffmpeg (a spy on `run`)

  Verify: `.venv/bin/python -m pytest tests/test_thumbs_ffmpeg.py` passes in under about 20 s on this host.

## 4. cli/ — `auto-reel thumbs`

- [ ] 4.1 Register `thumbs` in `cli/main.py`:
  - flags `root`, `--years`, `--layout`, `-v`, and `--jobs` with `type=_positive_int` and default 2. `_positive_int` is new: `int(value)`, and `argparse.ArgumentTypeError` below 1. No such helper exists yet.
  - `set_defaults(output=None, func=cmd_thumbs)`
  - the module and `build_parser` docstrings updated: ten subcommands (the latter still says "seven")

  Add `cmd_thumbs` to `cli/commands.py` (design "The `thumbs` subcommand"), with the per-event barrier and the `cancel_futures=True` shutdown on any `BaseException`. Tests go in a new `tests/test_cli_thumbs.py`:
  - they monkeypatch `commands.FfmpegRuntime` to a `Mock` (as `tests/test_cli_commands.py:115` does), and `commands.thumbnail_for` to a fake. The fake writes bytes at the real `thumbnail_path(...)`, or raises `ThumbnailError` for zero-byte files.
  - `XDG_CACHE_HOME` is `tmp_path / "xdg"`, a sibling of the library, because a cache inside the project root is refused
  - the library is a `year-event` one built at `tmp_path / "library"`, like the dev library:
    - `2024-06-27 - Grillning med grannar` (4 clips)
    - `2024-10-05 - Trasig` (a zero-byte `trasig.mp4`)
    - `2024-09-01 - Sommarlov`: the `SOMMARLOV` `reel.yaml` text from `tests/test_event_editorial.py` (`borttagen.mp4  # MISSING`), and 2 clips
    - `2024-08-20 - Två kapitel - Tjörn`: root `s1710001.mp4` and `s1710004.mp4`, `Kvällen/` with 3 clips, and a `reel.yaml` ignoring `s1710004.mp4`
    - an event with `s1710001.mp4` and `original/C0001.MTS`
    - a `.reelignore` event
    - `2024-02-30 - Omöjligt datum`

  The tests assert:
  - the exact `ERROR  2024-10-05 - Trasig/trasig.mp4: …` line, the per-event lines, the summary counts, and exit 1
  - the set of identities passed to the fake: no `borttagen.mp4`, no `original/…`, nothing from the `.reelignore` event; all five Tjörn clips and the Omöjligt datum clip included
  - a second run counts every successful clip as cached, and the fake is called only for `trasig.mp4`
  - `--jobs 0` raises `SystemExit` with code 2
  - `thumbnails: {position: 1.5}` exits 1 naming `thumbnails.position`, and the fake is never called
  - a fake raising `ThumbnailCacheError` exits 1 with one `error:` line naming the directory, and no `ERROR  ` lines
  - a fake raising `KeyboardInterrupt` propagates out of `main`, and the pool was shut down with `cancel_futures=True`. A `ThreadPoolExecutor` subclass monkeypatched as `commands.ThreadPoolExecutor` records the `shutdown` arguments. A call count would race with the worker dequeuing the next clip.
  - `commands.thumbnail_path` raising `FileNotFoundError` for one clip prints `ERROR  <event>/<clip>: cannot stat the clip: …`, counts it failed, and the run continues
  - a snapshot of every path, size and `st_mtime_ns` under the library root, plus the bytes of each `reel.yaml`, is identical before and after

  Update `tests/test_cli_main.py` to list `thumbs` and name the test `…_ten_subcommands`.

  Verify:
  - `.venv/bin/python -m pytest tests/test_cli_thumbs.py tests/test_cli_main.py` passes
  - mypy is clean
- [ ] 4.2 Add one `has_ffmpeg` end-to-end test to `tests/test_cli_thumbs.py`, using the real runtime and real `thumbnail_for`:
  - two generated 1080p clips and a zero-byte `trasig.mp4` in `tmp_path/clips/`, symlinked into three events under `tmp_path/library` so that one clip appears in two events
  - one link lives in `2024-08-20 - Två kapitel - Tjörn/Kvällen/` and is named `grillen, del 1.mp4` (spaces, a comma and Swedish letters)
  - before the first run, every directory under `tmp_path/library` is made read-only (`chmod a-w`). A `finally` restores the modes so `tmp_path` can be cleaned.
  - `main(["thumbs", str(root), "--jobs", "2"])` with `XDG_CACHE_HOME` at `tmp_path / "xdg"`

  The test asserts:
  - exit 1, and exactly one `ERROR` line
  - the cache holds exactly two `.jpg` files (the distinct targets) and no `.tmp` file
  - the second run's summary reports `0 generated`
  - the library snapshot from 4.1 is unchanged

  Verify: `.venv/bin/python -m pytest tests/test_cli_thumbs.py -m has_ffmpeg` passes.

## 5. docs — HLD and README

- [ ] 5.1 Record the decision (design "Where D-11 is recorded"):
  - `docs/high-level-design.md`:
    - add the **D-11** entry after D-10 in §7
    - §4.10: v1 gains clip thumbnails (D-11), and v2 keeps "event poster frames"
    - §4.10's slice plan: the standalone D-11 sentence after the D-10 paragraph, naming `clip-thumbnail-endpoint` as the extra `api/` prerequisite. The existing sentence about further `api/` prerequisites is `render-progress-screen`'s to rewrite; leave it as it is.
    - update the §4.10 research pointer
    - §4.7: drop "thumbnails" from the Postgres index parenthesis
    - §6: phase 9 drops "thumbnails"
    - §8.11: mark clip thumbnails resolved (D-11), leaving proxies/HLS open
  - `README.md`:
    - add `auto-reel thumbs <root> [--jobs N]` to the CLI list
    - document `thumbnails.position` and `thumbnails.cache_dir`, the default cache path, that the cache must lie outside the project root and the `input` directory, ≈15 KB per clip with no eviction, and the advice to set `cache_dir` when `serve` runs as another user or in a container

  Verify:
  - `grep -n "D-11" docs/high-level-design.md` shows the §7 entry and the §4.10 reference
  - `grep -n "thumbs" README.md` shows the CLI line and the config keys
  - `grep -n "GUI v2" docs/high-level-design.md` no longer lists thumbnails

## 6. Verification against the fixture

- [ ] 6.1 Dogfood on a scratch library of symlinks. `auto-reel-media/` is only read; nothing is written there. Build it under the session scratchpad:
  - `library/2024/2024-06-27 - Grillning med grannar/` with symlinks to the four fixture clips
  - `library/2024/2024-08-20 - Två kapitel - Tjörn/Kvällen/s1710002.mp4`, a symlink
  - `library/2024/2024-10-05 - Trasig/trasig.mp4`, zero bytes

  Then:
  1. `touch <scratch>/marker`
  2. run `XDG_CACHE_HOME=<scratch>/cache time .venv/bin/auto-reel thumbs <scratch>/library`, then run it again

  Verify:
  - the first run exits 1, with one `ERROR` line for `trasig.mp4`, and its wall time is recorded next to the design's ≈0.54 s per clip
  - the second run reports `0 generated` in under 1 s
  - `find ../auto-reel-media -newer <scratch>/marker` prints nothing
  - `<scratch>/cache/auto-reel/thumbnails/` holds four `.jpg` files and no `.tmp` file
  - `s1710001.mp4`'s thumbnail is a 320×180 JPEG that differs from an `-ss 0` frame extracted into scratch. Look at both images to confirm it is the 15.36 s shot.

## 7. Validation

- [ ] 7.1 Run the validation gates:
  - `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  - `.venv/bin/python -m mypy auto_reel_ng`
  - `.venv/bin/python -m pylint auto_reel_ng`
  - the full `.venv/bin/python -m pytest`, including `has_ffmpeg` and `requires_db`

  Verify:
  - all are clean or green, apart from the known cairo `no-member` noise and the environmental title-card skips
  - `RENDER_GRAPH_VERSION` in `staleness/fingerprint.py` is unchanged
  - `git status --short alembic/` is empty: no migration
  - `openspec validate clip-thumbnails --strict` passes
