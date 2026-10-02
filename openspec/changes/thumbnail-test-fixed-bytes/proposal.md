## Why

`test_an_undecodable_clip_gets_a_one_line_detail_without_server_paths` writes `os.urandom(20_000)` as a
clip and asserts the detail starts with `ffprobe could not read`. About 1 in 100 random buffers happens to
parse as some container, so ffprobe succeeds and the engine answers `No video stream found` instead. The
test failed by chance in the #44 and #74 CI runs and passed on rerun. A test that fails by chance on
unchanged code teaches people to rerun red builds.

## What Changes

- The test writes a fixed, constant non-media byte pattern instead of random bytes, so the clip fails
  at the same point in ffprobe on every run.
- The clip is renamed from `random.mp4` to `not-media.mp4` and the docstring says "fixed non-media bytes",
  so the names no longer promise randomness.
- The `api-service` scenario "A corrupt clip's detail is one line without server paths" says "fixed bytes
  that are no media container" instead of "random bytes", and pins which cause each kind of corrupt clip
  reports. The one-line, no-path contract is unchanged.
- The test is run 50 times in a row with no failure.
- No engine, API or rendered-output change, so `RENDER_GRAPH_VERSION` stays as it is.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: the "Clip thumbnail endpoint" requirement's corrupt-clip scenario names deterministic
  non-media bytes instead of random ones and states the cause for each kind of corrupt clip.

## Impact

- `tests/test_api_thumbnails.py` only. No new dependency.
- Out of scope: `tests/test_thumbs_ffmpeg.py::test_a_clip_that_fails_is_remembered_and_not_probed_again`
  also writes `os.urandom`, but it asserts no ffprobe wording (any failure reason satisfies it), so it
  cannot fail by chance.
