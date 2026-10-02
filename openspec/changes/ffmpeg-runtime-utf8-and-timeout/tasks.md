## 1. Lossless decoding in the runtime

- [x] 1.1 In `auto_reel_ng/ffmpeg/runtime.py`, pass `encoding="utf-8", errors="backslashreplace"` (alongside
  `text=True`) in `_run`, in the `run_with_progress` `Popen`, and in `_query_version_text`. Verify with
  `tests/test_runtime.py` using a fake binary that writes the raw byte `0xE9` on stdout and on stderr and
  exits 0 / 1: `run` returns text containing `\xe9` and raises `FfmpegError` (not `UnicodeDecodeError`)
  with `caf\xe9.mp4` in its stderr; `run_with_progress` raises `FfmpegError` whose message keeps the
  stderr tail and no `threading.excepthook` call occurs (capture with `threading.excepthook` patched);
  a `-version` reply with a non-UTF-8 byte still parses. Plus one `has_ffmpeg` test: real
  `run_ffprobe` on a text file named `caf\xe9.mp4` raises `FfmpegError`.

## 2. Opt-in time bound

- [x] 2.1 Add `FfmpegTimeoutError(FfmpegError)` to `auto_reel_ng/errors.py` with a docstring, and
  `FfmpegRuntime.with_timeout(seconds)` returning a shallow copy whose `run`/`run_ffprobe` apply that
  default timeout (`None` stays unbounded; `seconds` must be positive, else `ValueError`). Verify with a
  test that the copy shares the resolved paths and version, the original stays unbounded, and
  `with_timeout(0)` raises.
- [x] 2.2 Rewrite `_run` on `Popen` + `communicate(timeout=)` per design D3: on `TimeoutExpired` kill the
  child, `communicate(timeout=KILL_GRACE_SECONDS)` once, abandon (close pipes, no `wait`) if that also
  times out, log a WARNING, raise `FfmpegTimeoutError("Command timed out after <n>s: <cmd>")`; any other
  `BaseException` kills the child and re-raises. Verify in `tests/test_runtime.py` with fake binaries:
  a sleeping binary under `with_timeout(0.5)` raises `FfmpegTimeoutError` within a few seconds for both
  `run` and `run_ffprobe` and leaves no live child; a fast binary under `with_timeout(30)` returns
  normally; an unbounded runtime still waits for a 1 s binary; with `Popen.kill` patched to a no-op and
  `KILL_GRACE_SECONDS` patched to 0.5 the call still raises (the child is killed in test cleanup); a
  non-zero exit under a bound still raises the ordinary `FfmpegError` with exit code and stderr.

## 3. Bounded thumbnail generation

- [x] 3.1 In `auto_reel_ng/thumbs/thumbnail.py` add `THUMBNAIL_TIMEOUT = 60.0`; in `thumbnail_for`, after the
  cache check, derive `runtime.with_timeout(THUMBNAIL_TIMEOUT)` and use it for the probe and the
  extraction. In `_extract` catch `FfmpegTimeoutError` before `FfmpegError` and raise
  `ThumbnailError(clip, "ffmpeg timed out extracting the frame at <t>s: <exc>")`. Verify in
  `tests/test_thumbs.py` (the `FakeRuntime` gains `with_timeout` returning itself and recording the value):
  `thumbnail_for` bounds both calls with 60.0; a `FakeRuntime` raising `FfmpegTimeoutError` from `run`
  gives a `ThumbnailError` naming the clip, the time and "timed out" with no temporary file left; a probe
  that raises `ProbeError` wrapping a timeout gives a `ThumbnailError` whose reason says "timed out" and
  does not run ffmpeg; the cache is untouched in both.
- [x] 3.2 Subprocess-level timeout tests in `tests/test_thumbs_ffmpeg.py`, with `THUMBNAIL_TIMEOUT`
  monkeypatched to 0.5 and a `FfmpegRuntime` built from a fake script that answers `-version` and sleeps on
  anything else: with the fake as ffprobe, `thumbnail_for` raises `ThumbnailError` ("timed out") within a few
  seconds and ffmpeg is never run; with a real ffprobe and the fake as ffmpeg, it raises `ThumbnailError`
  naming the requested time and "timed out". Both leave no file in the cache directory and no live child.

## 4. Remove the decoding workarounds

- [x] 4.1 Delete the two `except UnicodeDecodeError` branches in `_probe_duration` and `_extract`. Make
  `_shorten` also match the backslash-escaped spelling of the clip path
  (`os.fsencode(path).decode("utf-8", "backslashreplace")`). Verify: replace
  `test_an_undecodable_probe_output_is_the_clips_failure` and
  `test_an_undecodable_ffmpeg_output_is_no_frame_and_leaves_nothing` in `tests/test_thumbs.py` with
  `one_line_cause` unit tests on a reason whose stderr names `/lib/caf\xe9.mp4` (cause ends
  `Invalid data found when processing input`, no path); rewrite
  `test_a_corrupt_clip_with_a_non_utf8_name_is_a_thumbnail_error` (`tests/test_thumbs_ffmpeg.py`) to assert
  the reason is ffprobe's failure and not "could not be decoded", and the CLI test in
  `tests/test_cli_thumbs.py` to expect `ERROR  2024-10-05 - Trasig/caf\xe9.mp4: ffprobe could not read:
  Invalid data found when processing input` (exact text confirmed against the real run), exit status 1.

## 5. Quality gates

- [x] 5.1 `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` (known cairo
  `no-member` noise only) and the full `.venv/bin/python -m pytest` all pass; confirm
  `RENDER_GRAPH_VERSION` and `THUMBNAIL_VERSION` are unchanged.
