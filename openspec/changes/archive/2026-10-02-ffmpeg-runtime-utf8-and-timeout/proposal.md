## Why

Two defects in the one place every ffmpeg/ffprobe subprocess goes through, `FfmpegRuntime`
(`auto_reel_ng/ffmpeg/runtime.py`), found in a verified bug triage of main `6a7fe16`:

1. **Strict UTF-8 decoding.** `_run` calls `subprocess.run(..., text=True)` and `run_with_progress` opens
   its `Popen` with `text=True`, so output is decoded strictly. ffmpeg and ffprobe echo a clip's file name
   on stderr when they fail on it, and the MOL archive holds Latin-1 names (`caf\xe9.mp4`). A failing
   command then raises a bare `UnicodeDecodeError` instead of `FfmpegError`: `probe_media` leaks it past
   `except ProbeError`, `scheduler/worker.py` catches only `EngineError` so the exception escapes the job
   thread and the job row stays `running` until a restart requeues it (the escape is closed separately by
   `worker-exception-backstop`), and in `run_with_progress` the stderr drain thread dies with a traceback on
   `threading.excepthook` and the `FfmpegError` ends in an empty `stderr:`. `thumbs/thumbnail.py` already
   carries two workaround `except UnicodeDecodeError` branches for exactly this.
2. **No time bound.** `_run` passes no `timeout` and `run`/`run_ffprobe` expose none, and
   `thumbs/thumbnail.py` goes through them. `api/thumbnails.py::ThumbnailGate` holds two extraction slots,
   each a threadpool worker for the length of the ffmpeg process; two reads that hang on a stalled USB
   drive occupy both for good and every later uncached thumbnail waits until the service restarts.
   (`accel/selftest.py` is the only caller that bounds a command today, and it bypasses the runtime.)

## What Changes

- `FfmpegRuntime` decodes every invocation's output (`run`, `run_ffprobe`, `run_with_progress`, the
  `-version` query) as UTF-8 with `errors="backslashreplace"`: decoding never raises and a bad byte shows
  as `\xe9` in the error text.
- `FfmpegRuntime` gains an opt-in time bound: a runtime view with a default timeout. A bounded command that
  overruns is killed and raises a new `FfmpegTimeoutError` (a subclass of `FfmpegError`), and the call
  returns within a fixed grace period even if the kernel has not yet reaped the child. Unbounded stays the
  default; renders and analysis are untouched.
- Thumbnail generation bounds its ffprobe and its ffmpeg at 60 s each (module constant, no config key) and
  reports a timeout as the clip's own `ThumbnailError`, so the service's extraction slot is released.
- The two dead `UnicodeDecodeError` branches in `thumbs/thumbnail.py` go; the cause line of a non-UTF-8
  name's failure (`one_line_cause`) is made to recognise the escaped spelling of the clip path that ffmpeg
  now yields.
- No `RENDER_GRAPH_VERSION` bump: rendered bytes for identical inputs do not change (only error text and
  failure handling do), and `THUMBNAIL_VERSION` is unchanged for the same reason.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ffmpeg-runtime`: command output is decoded without ever raising; commands can be bounded in time.
- `clip-thumbnails`: probe and extraction are bounded to 60 s and a clip that exceeds it fails as its own
  thumbnail error; a non-UTF-8 file name fails with the ordinary probe cause.

## Impact

- Code: `auto_reel_ng/ffmpeg/runtime.py`, `auto_reel_ng/errors.py` (one new exception),
  `auto_reel_ng/thumbs/thumbnail.py`. Tests: `tests/test_runtime.py`, `tests/test_thumbs.py`,
  `tests/test_thumbs_ffmpeg.py`, `tests/test_cli_thumbs.py`.
- No API, CLI flag, config key, schema or dependency change. The `502` thumbnail failure kind of the
  service gains a new cause text only.
- Sibling changes touching the same files, to land in either order: `render-stall-watchdog` (also edits
  `run_with_progress`), `worker-exception-backstop` (the scheduler side of the leaked exception),
  `thumbs-cache-key-and-count` / `thumbs-hdr-and-cache-hygiene` / `thumbs-sidecar-metadata`
  (`thumbs/thumbnail.py`). This change keeps its edits to the `Popen`/`run` keyword arguments and the two
  `except` branches so conflicts stay textual.
