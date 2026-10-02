## Context

`FfmpegRuntime` is the only sanctioned subprocess seam (constitution VI). Today:

- `_run(executable, args)` is `subprocess.run(cmd, capture_output=True, text=True, check=False)`;
  `run_with_progress` opens `Popen(..., text=True)` and reads stderr on a daemon thread (`_collect`);
  `_query_version_text` is another `subprocess.run(text=True)`. `text=True` alone decodes with the locale
  encoding and `errors="strict"`.
- `probe_media` calls `runtime.run_ffprobe`, catches `FfmpegError` and re-raises `ProbeError`
  (`probe/media.py:143-145`); a `UnicodeDecodeError` passes straight through it.
- `thumbs/thumbnail.py` works around that in `_probe_duration` and `_extract` with
  `except UnicodeDecodeError` -> `ThumbnailError("... could not be decoded")`, pinned by
  `tests/test_thumbs.py` (two tests), `tests/test_thumbs_ffmpeg.py` (one) and `tests/test_cli_thumbs.py`
  (one).
- `api/thumbnails.py::ThumbnailGate` runs `thumbnail_for` in the threadpool under a 2-slot semaphore; the
  slot is held until the call returns or raises.

The triage reproduced the decoding failure with a fake binary and with real ffprobe on a corrupt
`caf\xe9.mp4`. The hang was not reproduced live (it needs a stalled mount) but the unbounded call is
directly visible.

## Goals / Non-Goals

**Goals:**
- No ffmpeg/ffprobe output can make the runtime raise anything but `FfmpegError` (or a subclass).
- A thumbnail request on a stalled clip returns an error in bounded time and frees its slot.
- Stay inside `ffmpeg/` and `thumbs/` (plus the one exception class in `errors.py`).

**Non-Goals:**
- The scheduler's missing `Exception` backstop (`worker-exception-backstop`) and the render stall watchdog
  (`render-stall-watchdog`, which owns bounding `run_with_progress`). This change does not bound renders,
  analysis, concat or verify.
- Other strict decoders outside the runtime: `probe/media.py` (`exiftool` fallback, off by default),
  `accel/devices.py`, and `accel/selftest.py`. They bypass the runtime (a pre-existing layering gap) and
  only see synthetic or device output, not clip names. Left as they are, to stay within two packages.
- A `thumbnails.timeout` config key (supervisor decision: module constant; constitution VII).
- Cache-key, thumbnail format or ffmpeg arguments: unchanged.

## Decisions

**D1. `encoding="utf-8", errors="backslashreplace"` on all three spawn sites.** Output is then always a
`str`, bad bytes render as `\xe9`, and nothing raises, so the `_collect` drain thread cannot die and
`FfmpegError` always carries stderr. Alternatives: `errors="replace"` (loses which byte, so a Latin-1 name
is ambiguous), `surrogateescape` (a lone surrogate is not encodable when the text is later logged or put in
JSON, the problem `thumbnail_key` already works around), decoding bytes by hand (re-implements
`text=True`). `backslashreplace` matches how the CLI already prints such names (`caf\xe9.mp4`).

**D2. Bounding is a runtime view, `FfmpegRuntime.with_timeout(seconds)`, not a keyword on `run`.** It
returns a shallow copy that shares the resolved paths and version and carries a default timeout applied by
`run` and `run_ffprobe`. Rationale: `thumbnail_for` reaches ffprobe through `probe_media(source,
runtime=...)`, which wraps the runtime; a `timeout=` keyword on `run_ffprobe` would also need a passthrough
in `probe/media.py` (a third package, and a `probe_media` signature change for one caller). A view needs no
change outside `ffmpeg/` and `thumbs/`, never mutates the shared (session-scoped, multi-threaded) runtime,
and gives one mechanism instead of two. Alternative rejected: a mutable `timeout` attribute on the shared
runtime (racy across the service's threads). Cost: tests' `FakeRuntime` doubles need a `with_timeout` that
returns `self`.

**D3. `_run` uses `Popen` + `communicate(timeout=)` instead of `subprocess.run`.** `subprocess.run` does
kill on timeout but then blocks in `wait()`; a child stuck in uninterruptible I/O on a dead USB mount
ignores `SIGKILL` until the I/O returns, so the caller would still hang, which is the very bug. On
`TimeoutExpired` the runtime kills the child, makes one more `communicate(timeout=KILL_GRACE_SECONDS)` (5 s,
module constant) to reap and collect output, and if that also times out abandons the child (closes the
pipes, does not `wait()`; no `with Popen(...)` block, whose `__exit__` waits) and raises. The kernel
reaps it when the I/O finally returns. Any other `BaseException` still kills the child and re-raises,
as `subprocess.run` does. Unbounded (`None`) calls take the same path with `communicate()`.

**D4. New `FfmpegTimeoutError(FfmpegError)` in `errors.py`**, message `Command timed out after 60s: <cmd>`
(`{seconds:g}`). A subclass, so every existing `except FfmpegError` (probe, selftest helpers, worker
`EngineError` handlers) keeps working, while `thumbs/` can word its own reason without parsing text.
`probe_media` wraps it in `ProbeError("ffprobe could not read <path>: Command timed out after 60s: ...")`;
`_probe_reason` strips the path and the "timed out" text stays in the reason. For the extraction,
`_extract` catches `FfmpegTimeoutError` before `FfmpegError` and raises
`ThumbnailError(clip, "ffmpeg timed out extracting the frame at <t>s: <exc>")`: not the "no frame
extracted" wording, because nothing is known about the frame. `one_line_cause` already cuts at the first
absolute path (the binary), leaving `... timed out extracting the frame at 15.360s: Command timed out
after 60s`.

**D5. 60 s each for probe and extraction, as `THUMBNAIL_TIMEOUT = 60.0` in `thumbs/thumbnail.py`.**
`thumbnail_for` builds `bounded = runtime.with_timeout(THUMBNAIL_TIMEOUT)` once after the cache check and
uses it for `_probe_duration` and `_extract`. A healthy thumbnail takes well under a second on the MOL
drive; the worst case for one stalled clip is 2 x 60 s. The service needs no change: `thumbnail_for` now
returns (raising `ThumbnailError`), `ThumbnailGate._run` leaves its `async with`, the slot is free, and the
existing `502` thumbnail-failure mapping reports the clip. Unfinished temporary files are already removed by
`thumbnail_for`'s `except BaseException`.

**D6. Remove the two `UnicodeDecodeError` branches, but keep their user-visible promise.** After D1 a
non-UTF-8 name takes the ordinary path: ffprobe exits non-zero, `ProbeError`, `ThumbnailError`. The CLI's
`one_line_cause` takes ffmpeg's last stderr line as the gist and shortens the clip's path in it to the file
name. The stderr now spells the path with `\xe9`, while the engine's `source` string holds a surrogate
escape (`\udce9`), so `_shorten` would not find it, `_before_any_path` would cut the line at its leading
`/`, and the cause would be empty. `_shorten` therefore also tries the backslash-escaped spelling of the path
(`os.fsencode(path).decode("utf-8", "backslashreplace")`). `_probe_reason` needs no change: `ProbeError`
names the path in the engine's own spelling. Alternative: keep catching
`UnicodeDecodeError`: dead code and a worse message. The existing tests asserting `"could not be decoded"`
are rewritten to assert the real cause.

**D7. Layering.** `errors.py` is the shared exception module, not a layer; `thumbs/` already imports
`ffmpeg/`. No new import direction.

## Risks / Trade-offs

- [A hung child is abandoned rather than reaped] -> it is already SIGKILLed; the kernel reaps it when the
  stalled read returns. Python's `Popen.__del__` queues it for later reaping. Logged at WARNING with the
  command.
- [A real extraction legitimately exceeds 60 s (very large 4K HEVC seek over a slow network share)] -> that
  clip shows a clear timeout error and can be retried; 60 s is the supervisor-chosen bound, and a constant is
  one line to change. Not measured on the MOL drive here (the backlog item that asked for it is
  independent).
- [`with_timeout` copies the runtime, so a test that monkeypatches `runtime.run` on the original still
  records calls only because a shallow copy carries the instance attribute] -> acceptable; the spy test in
  `test_thumbs_ffmpeg.py` is re-run to confirm.
- [Escaped-spelling handling in `one_line_cause` is a heuristic] -> only adds a second string to match; the
  fallback is today's behaviour.
- [`render-stall-watchdog` also edits `run_with_progress`] -> this change touches only its `Popen`
  keyword arguments; whichever lands second resolves a textual conflict, no semantic overlap.
