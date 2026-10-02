Start from main after the gate changes `ffmpeg-runtime-utf8-and-timeout` and `cli-project-context-module`
have merged. Tasks name functions, not lines, because both gates move code in these two files.

## 1. thumbs/

- [x] 1.1 `thumbnail_key` (`thumbs/thumbnail.py`): replace `str(resolved)` in the hashed payload with
  `resolved.name` (the stat stays on `resolved`, its `OSError` still propagates); rewrite the module and
  function docstrings that say the key covers "the resolved clip path". Tests in `tests/test_thumbs.py`:
  `shutil.copy2` of a clip into another directory (same size, same `mtime_ns`) gives an equal key; a copy
  under a different file name gives a different key; a symlink whose own name differs from its target's
  shares the target's key (the name hashed is the resolved file's); the existing size, mtime, position,
  version and two-symlinks key tests still pass unchanged.
- [x] 1.2 Set `THUMBNAIL_VERSION = 2` and widen its comment to "bump when `thumbnail_args` changes the output
  bytes or the key's payload changes". Test: after `thumbnail_for` generated a thumbnail in `library/`, the
  same clip copied to `elsewhere/` (copy2) and requested with the same cache is a hit that runs neither the
  probe nor ffmpeg and returns the same file; a pinned test asserts the version is greater than 1 so a
  revert is caught.

## 2. cli/

- [x] 2.1 Make the `tests/test_cli_thumbs.py` library fixture independent of the clock: `_write` sets a distinct
  `mtime_ns` for every file it writes (a counter passed to `os.utime(ns=...)`), because the fixture holds
  same-named, same-sized clips in different folders (`s1710004.mp4` in Tjörn's root and in `Kvällen/`) that
  now differ only by `mtime_ns`. Verify: `.venv/bin/python -m pytest tests/test_cli_thumbs.py` passes with the
  existing expectations (`5 clips, 5 generated`, `14 clips in 6 events: 13 generated, 0 cached, 1 failed`).
- [x] 2.2 `_thumbs_event` (`cli/thumbnails.py`): group identities by target path in listing order, skipping
  identities whose stat failed; for each target, count every member as `cached` when the file exists,
  otherwise submit one `thumbnail_for` future (for the first member); on success the first member counts as
  `generated` and the rest as `cached`; on `ThumbnailError` every member gets the reason and counts as
  failed. ERROR lines stay in identity order. Update the module and function docstrings. Tests in
  `tests/test_cli_thumbs.py` with the fake `thumbnail_for`: an event of two symlinks to one file runs the
  fake once and prints `2 clips, 1 generated, 1 cached`, with the summary adding up; two symlinks to a
  zero-byte file print two `ERROR` lines, `2 clips, 2 failed`, and the fake ran once; a second run prints
  `2 clips, 2 cached`; an event whose clips are distinct files is counted as before.
- [x] 2.3 Real-ffmpeg test (`@pytest.mark.has_ffmpeg`, `make_clip`) in `tests/test_cli_thumbs.py`: a scratch
  project whose one event holds `real.avi` and a symlink `link.avi` to it prints `2 clips, 1 generated,
  1 cached` and the cache directory holds exactly one `.jpg` and no `.tmp`; a second scratch library of real
  clip files is copied with `shutil.copytree` (which keeps size and `mtime_ns`) to another path, and `thumbs`
  run on the copy with the same cache prints `0 generated` and leaves the cache directory unchanged.

## 3. docs

- [x] 3.1 `README.md` (thumbnails paragraph: "named by a hash of the clip's resolved path ... moving or remounting
  the library at another path regenerates them all") and `docs/high-level-design.md` D-11, "The cache": say the key is the resolved file's name, size,
  mtime, position, box and `THUMBNAIL_VERSION`, not its path, so a move or remount keeps the cache; add a
  dated sub-bullet naming the change `thumbs-cache-key-and-count`, the version bump to 2 and the
  never-evicted orphans. Verify with `grep -n "resolved clip path" docs/high-level-design.md README.md`
  returning nothing (also `grep -n "regenerates them all" README.md`).

## 4. Validation gates

- [x] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  leave no diff; `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` are
  clean (known cairo `no-member` aside).
- [x] 4.2 `.venv/bin/python -m pytest` passes in full (podman for the DB tests, else
  `-m "not requires_db"` with the reason stated), including `tests/test_thumbs.py`,
  `tests/test_cli_thumbs.py` and `tests/test_api_thumbnails.py`. A thumbnail test that told same-named,
  same-sized clips in different folders apart only by path is fixed with distinct `mtime_ns` values, as in
  2.1, never by weakening its assertion.
