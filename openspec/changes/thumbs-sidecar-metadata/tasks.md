Conventions: this change is implemented after the merged gate `thumbs-hdr-and-cache-hygiene`. Re-read
`thumbs/thumbnail.py` as it is on `main` first and place each step by the rules in design.md, not by line
numbers. Tests use the existing fakes in `tests/test_thumbs.py` (`FakeRuntime`, `probe_calls`, `_leftovers`)
and need no marker unless stated. A marker's age is set with `os.utime`, never `sleep`.

## 1. thumbs/: sidecar files

- [x] 1.1 In `thumbs/thumbnail.py` add `FAILURE_TTL_SECONDS = 60.0`, a private `_sidecar(target, suffix)`
  (the JPEG `target` with `.jpg` replaced by `.json` / `.fail`) and a private `_write_sidecar(cache_dir,
  target, suffix, payload)` that writes through a hidden temporary named `.<key>.<hex>.tmp` (the name the
  gate's sweep matches), `fsync`s, then `os.replace`s, and removes the temporary on any failure.
  Test (`tests/test_thumbs.py`): the file appears complete under the right name, no temporary remains, a
  read-only directory raises `OSError` from the helper.
- [x] 1.2 Duration: after `_probe_duration` and `_create_temporary` succeed, and before `_extract`, write
  `{"duration": d}` to `<key>.json`; an `OSError` becomes `ThumbnailCacheError` naming the directory (the
  temporary files are removed). Add `recorded_duration(target) -> Optional[float]` per design: `None` for
  absent, unreadable, invalid JSON, non-object, non-numeric, bool, non-finite or `<= 0`; never raises, never
  runs a process. Tests: a generation leaves `{"duration": 27.84}` beside the JPEG and `recorded_duration`
  reads 27.84 with `probe_calls` and `FakeRuntime` untouched; a failed extraction still leaves it; a failed
  probe, a zero duration and a stat failure leave none; a cache hit with no sidecar creates none and runs no
  probe; damaged contents (`not json`, `{"duration": 0}`, `{"duration": "61"}`, `{"duration": true}`, a
  directory in its place) read as `None`; a changed mtime gives a different target with `None`.

## 2. thumbs/: failure marker

- [x] 2.1 `recorded_failure(clip_path, target) -> Optional[ThumbnailError]` per design: valid when the
  file parses to an object with a string `reason` and `0 <= time.time() - st_mtime < FAILURE_TTL_SECONDS`;
  expired, future-dated, damaged or absent reads as `None`; any other `OSError` raises `ThumbnailCacheError`
  (`<dir>: cannot read thumbnails: ...`). Tests: valid at age 5 s; `None` at 61 s and at -10 s; `None` for
  `not json` and for `{"reason": 3}`; a directory chmod 000 raises the cache error (skip as root, like the
  existing cache-permission tests).
- [x] 2.2 `thumbnail_for` integration: after the `is_cached` miss and before the runtime or the probe, raise
  `recorded_failure(...)` if any (outside the recording handler, so a read never renews the marker). Wrap
  the probe, duration write, extraction and finalize so a `ThumbnailError` writes `<key>.fail`
  (`{"reason": exc.reason}`, best effort: create the directory, log a warning and swallow an `OSError`) and
  is re-raised; `ThumbnailCacheError` and `BaseException` write none. A success removes `<key>.fail`
  (`suppress(OSError)`). Update the `thumbnail_for` docstring (Raises). Tests: a no-frame failure leaves
  `<key>.fail` and no JPEG, and a second call within the window raises an equal error with the runtime and
  probe not called again; at 61 s the second call runs again; a read at 50 s followed by a call at 70 s
  runs again (not renewed); a success after an expired marker removes it; a read-only cache writes none
  and the second call tries again; a `ThumbnailCacheError` from the runtime (disk-full classification of
  the gate) writes none; an unwritable marker location still raises the clip's `ThumbnailError` and logs
  a warning (`caplog`); a JPEG present wins over a marker; a stat failure writes none.
- [x] 2.3 Export `FAILURE_TTL_SECONDS`, `recorded_duration`, `recorded_failure` from `thumbs/__init__.py`
  and `__all__`. Update the existing assertions that expect an empty cache after a failure to expect
  exactly the `<key>.fail` file (`tests/test_thumbs.py` `_leftovers(...) == []` after failures,
  `tests/test_thumbs_ffmpeg.py` `_cache_files(cache_dir, "*") == []`); the `*.jpg` and `.*.tmp` globs keep
  asserting empty.

## 3. thumbs/ with real ffmpeg, and the CLI

- [x] 3.1 `has_ffmpeg` tests in `tests/test_thumbs_ffmpeg.py`: a generated 1 s clip leaves a
  `<key>.json` whose duration equals `probe_media`'s for the clip, and a second `thumbnail_for` is a cache
  hit; a clip of random bytes fails once, leaves `<key>.fail` with the one-line-cause-able reason, and the
  second call within the window raises the same `ThumbnailError` (compare `reason`) with ffmpeg not run
  (wrap the runtime to count). In `tests/test_cli_thumbs.py`: `auto-reel thumbs` on an event with a corrupt
  clip prints its ERROR line and exits 1; run again, it prints the same line, exits 1, and the fake or
  wrapped runtime was not asked to run a command for the clip; the good clips are reported `cached`.

## 4. api/: the route answers from the marker

- [x] 4.1 In `api/routes/events.py` `_serve_thumbnail`, after the cached read returns `None` and before
  `gate.produce`, call `recorded_failure(source.clip_path, source.cache_path)` in the threadpool and raise
  the error when there is one. Update `_serve_thumbnail`'s docstring; the route's own docstring is the published
  OpenAPI description and stays word for word, so the schema and `web/openapi.json` do not change (a
  comment above the route says so). `ThumbnailGate` (`api/thumbnails.py`) is unchanged. Tests in
  `tests/test_api_thumbnails.py` (fake runtime as in the existing tests): a failing clip is requested
  twice and the second response equals the first (status, `thumbnail_failure`, detail) with the fake's
  `calls` unchanged; with both slots held by blocked extractions, a recorded failure is answered at once;
  after `os.utime` ages the marker 61 s the clip is attempted again; a cached JPEG plus a marker answers
  200; `If-None-Match` still gets 304 first; a read-only cache gives the no-kind 502 twice with the
  fake's `calls` growing each time. Update `test_real_thumbnails_from_a_read_only_library`: `retried`
  now comes from the marker (equal body) and the cache listing holds the two JPEGs, their two `.json`
  files and the one `.fail`. Add a test that the schema is unchanged (the 502 problem body still has the
  one-member `thumbnail_failure` enumeration).

## 5. Docs

- [x] 5.1 In `docs/high-level-design.md` D-11, "The cache" bullet: add that beside `<key>.jpg` the cache
  holds `<key>.json` (the probed duration, read probe-free) and `<key>.fail` (a failure remembered for
  60 s, never for a cache fault), keyed identically and written atomically. Check that the existing
  specs referenced there (`clip-thumbnails`, `api-service`) read consistently after sync.

## 6. Validation gates

- [x] 6.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
- [x] 6.2 `.venv/bin/python -m mypy auto_reel_ng`
- [x] 6.3 `.venv/bin/python -m pylint auto_reel_ng` (only the known cairo `no-member` noise remains)
- [x] 6.4 `.venv/bin/python -m pytest` (podman for the DB tests, or `-m "not requires_db"` with the reason
  stated); `RENDER_GRAPH_VERSION` and `THUMBNAIL_VERSION` are unchanged.
