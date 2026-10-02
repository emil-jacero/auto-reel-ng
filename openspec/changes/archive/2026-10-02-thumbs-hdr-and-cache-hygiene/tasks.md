Start from main after the gate changes `thumbs-cache-key-and-count`, `ffmpeg-runtime-utf8-and-timeout` and
`cli-project-context-module` have merged. Tasks name functions, not lines, because those gates move code in
`thumbs/thumbnail.py` and the thumbnail tests. Everything is in `thumbs/`; no CLI or API code changes.
Real-ffmpeg tests carry `@pytest.mark.has_ffmpeg` and use the `runtime` and `make_clip` fixtures.

## 1. thumbs/ — HDR tone-mapping

- [x] 1.1 `thumbnail_args` (`thumbs/thumbnail.py`): add keyword `hdr: bool = False`; when true, the `-vf`
  value is `CPU_TONEMAP_FILTER` (imported from `accel/profiles/cpu.py`), a comma, then the existing scale
  chain; with `hdr=False` the list is unchanged. Extend the docstring (module and function) to say HDR input
  is tone-mapped first. Tests in `tests/test_thumbs.py`: the existing golden-list test passes untouched; a
  second golden list for `hdr=True` equals the SDR list with only the `-vf` value changed, and the value
  starts with `zscale=t=linear:npl=100,tonemap=hable,` and ends with the existing scale chain.
- [x] 1.2 `thumbnail_for`: replace `_probe_duration` with `_probe_clip`, which returns the probed duration and
  `is_hdr` (a small `NamedTuple`) under the same validation and the same `ThumbnailError`s; pass `hdr` through
  `_extract` to `thumbnail_args`. The `probe_calls` fixture in `tests/test_thumbs.py` gains an `is_hdr`
  parameter (default `False`) on the namespace it returns. Tests: a probe reporting `is_hdr=True` makes the
  recorded ffmpeg args carry the tone-map chain and `is_hdr=False` does not; a cache hit with an HDR probe
  installed runs neither probe nor ffmpeg; the probe-error, no-duration and timeout tests (from the gate)
  still pass with the same reasons.
- [x] 1.3 Bump `THUMBNAIL_VERSION` by one from its value on main (2 after `thumbs-cache-key-and-count`) and
  extend its comment: the version also changes when the extraction filter graph does for any input class.
  Test: a pinned assertion that the constant is greater than the gate's value (3 or more), and one that a
  thumbnail generated under the previous version's key is not a hit (monkeypatch the constant down, generate,
  restore, request: the fake runtime runs again).
- [x] 1.4 Real-ffmpeg test in `tests/test_thumbs_ffmpeg.py`: build a 640×360 HLG clip with the runtime's ffmpeg
  (`lavfi testsrc`, `-vf setparams=color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc`,
  `libx264 -pix_fmt yuv420p`; skip if the encode fails), probe it to confirm `is_hdr`, and `thumbnail_for` it
  with the real runtime: the result is a 320×180 JPEG that differs byte-wise from a plain extraction of the
  same frame (`thumbnail_args(hdr=False)` run through the runtime). A second test uses
  `make_clip(color_trc="smpte2084")` (transfer-only tag): `thumbnail_for` raises `ThumbnailError` naming the
  clip and the requested time, and the cache holds no `.jpg` and no `.tmp`. A third: an SDR `make_clip`
  still produces its thumbnail through the same call.

## 2. thumbs/ — cache hygiene

- [x] 2.1 `_extract` (`thumbs/thumbnail.py`): take the cache directory (the output's parent); after the gate's
  `FfmpegTimeoutError` branch and before the generic `FfmpegError` branch, when the error message's part after
  `"\nstderr:\n"` contains `No space left on device` or `Disk quota exceeded`, raise
  `ThumbnailCacheError(f"{cache_dir}: cannot write thumbnails: <the matched phrase>")`. Tests in
  `tests/test_thumbs.py` with the fake runtime raising `FfmpegError(...)`: stderr with `No space left on
  device` gives a `ThumbnailCacheError` naming the directory, not a `ThumbnailError`, and the cache directory
  holds no temporary and no `.jpg`; the same for `Disk quota exceeded`; a command line that contains `No space
  left on device.mp4` above a stderr of `Invalid data found when processing input` stays a `ThumbnailError`;
  the existing "ffmpeg failure is no frame" test passes; after the full-disk error, the same `thumbnail_for`
  call with a working fake runtime generates the thumbnail (nothing is remembered). The CLI and route
  scenarios need no new code: a full disk raises the same `ThumbnailCacheError` that the existing
  unwritable-cache tests in `tests/test_cli_thumbs.py` and `tests/test_api_thumbnails.py` already cover. In `tests/test_thumbs_ffmpeg.py` a `has_ffmpeg` test
  runs the runtime on `thumbnail_args(..., output=Path("/dev/full"))` (skip when `/dev/full` is absent) and
  asserts the raised `FfmpegError` is classified as a full disk by the same predicate (export it privately and
  import it in the test), so the match is pinned to the stderr a real ffmpeg prints.
- [x] 2.2 Add `STALE_TEMPORARY_AGE = 24 * 60 * 60` and `sweep_stale_temporaries(cache_dir, *, older_than=
  STALE_TEMPORARY_AGE, now=None) -> int` (`now` is epoch seconds, default `time.time()`; returns the number
  removed) in `thumbs/thumbnail.py`: `os.scandir` the directory; remove regular, non-symlink files whose name
  matches `^\.[0-9a-f]{64}\.[0-9a-f]{32}\.tmp$` and whose `st_mtime` is more than `older_than` seconds before
  `now`; skip everything else; catch `OSError` per entry and for the scan, log at debug level, never raise.
  Export it from `thumbs/__init__.py` and `__all__`. Tests in `tests/test_thumbs.py` (`tmp_path` cache, files
  aged with `os.utime`): two-day-old engine-named temporaries are removed and counted; a five-minute-old one
  is kept; a two-day-old `<key>.jpg`, `notes.tmp`, `.keep`, a directory named like a temporary and a
  symlink named like one are all kept; a file dated tomorrow is kept; a missing directory returns 0; an
  `os.unlink` that raises `PermissionError` (monkeypatched) neither raises nor aborts the other removals.
- [x] 2.3 Wire the sweep: `_create_temporary` calls it right after `cache_dir.mkdir(...)`, once per process per
  resolved directory (a module-level set under a `threading.Lock`, marked before the scan), logging the count
  at info level when it is above zero. Tests in `tests/test_thumbs.py` (an autouse fixture clears the set
  between tests): `thumbnail_for` on a miss with an old temporary in the cache removes it and writes the
  thumbnail; a second `thumbnail_for` for another clip does not sweep again (an old temporary created between
  the two survives); a call on a cache hit never creates or sweeps (a young-and-old pair of temporaries stays
  as it was and `os.scandir` is not called, via a spy); two threads generating at once sweep once; a
  `sweep` that raises is impossible to observe from `thumbnail_for` (monkeypatch it to raise `OSError` and the
  thumbnail is still written); a read-only cache directory is still the cache error of the existing test.

## 3. docs

- [x] 3.1 `docs/high-level-design.md` D-11: in "Extraction" say HDR clips are tone-mapped on the CPU with the
  render's chain; in "The cache" say a full disk is a cache error and temporaries older than a day are swept
  once per process; add a dated sub-bullet naming the change `thumbs-hdr-and-cache-hygiene`, the version
  bump and that older files are orphaned, not evicted. Verify with `grep -n "thumbs-hdr-and-cache-hygiene"
  docs/high-level-design.md` returning the new sub-bullet.

## 4. Validation gates

- [x] 4.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`
  leave no diff; `.venv/bin/python -m mypy auto_reel_ng` and `.venv/bin/python -m pylint auto_reel_ng` are
  clean (known cairo `no-member` aside).
- [x] 4.2 `.venv/bin/python -m pytest` passes in full (podman for the DB tests, else
  `-m "not requires_db"` with the reason stated), including `tests/test_thumbs.py`,
  `tests/test_thumbs_ffmpeg.py`, `tests/test_cli_thumbs.py` and `tests/test_api_thumbnails.py`, whose
  expectations on thumbnails and the cache are unchanged. `RENDER_GRAPH_VERSION` is not bumped (thumbnails
  are not part of a render).
