## Context

The thumbnail endpoint turns any `ThumbnailError` into a 502 whose detail is the clip identity plus a
one-line cause. For an unreadable file the cause comes from `probe/media.py`, which raises
`ffprobe could not read ...` when ffprobe exits non-zero and `No video stream found in ...` when ffprobe
succeeds but finds no video. Random bytes mostly exit non-zero (`moov atom not found`), but in a rough
trial of 200 buffers 2 were accepted by ffprobe, so the test's expected wording holds about 99% of the time.

## Goals / Non-Goals

**Goals:**
- The test is deterministic: same bytes, same ffprobe path, same detail, on every run and host.
- The test still proves what it was written for: a non-media clip gets a one-line detail without server
  paths, and the log keeps the full reason.

**Non-Goals:**
- Not loosening the assertion to accept either ffprobe wording: it would pass on the flaky input and
  stop distinguishing "unreadable" from "no video".
- Not changing probe wording or the endpoint.
- Not touching the other `os.urandom` test, which asserts no wording.

## Decisions

**A constant text pattern, not seeded random bytes.** The clip body is `b"This is not a media file.\n" * 800`
(about 20 kB), held in a module constant in the test file. Checked with ffprobe 8.x: it exits 1 with
`moov atom not found ... Invalid data found when processing input`, which the engine reports as
`ffprobe could not read`. A `random.Random(0).randbytes(20_000)` would also be deterministic and was
checked to fail the same way, but its pass depends on the PRNG's output staying stable across Python
versions and tells a reader nothing; plain text shows at a glance that it is not media. Zeros also fail
the same way but a text line is clearer. Alternative rejected: accept both wordings, see Non-Goals.

**Rename the clip to `not-media.mp4`.** `random.mp4` would be a lie after the change. The file name is
asserted in the detail prefix, so the rename lands in the same edit as the bytes.

**Stability is shown by repetition, not by a retry plugin.** The test is run 50 times in a row (a shell
loop over `pytest`, or one invocation with the node id repeated if the runner supports it) and must pass
every time. No `pytest-repeat` or flaky-retry dependency is added.

**The spec scenario changes with the test.** The scenario currently says "a clip of random bytes", which
is the same non-deterministic input as the test and cannot be promised. It now says fixed non-media
bytes and states the cause for each kind of clip, which the test already asserts.

## Risks / Trade-offs

- [A future ffprobe sniffs the text pattern as a media format] -> The test fails every run, not 1% of
  runs, so the failure is loud and the constant is changed in one place.
- [The `ffprobe could not read` wording changes] -> Same loud failure; the assertion is intentionally on
  the engine's own wording in `probe/media.py`.
