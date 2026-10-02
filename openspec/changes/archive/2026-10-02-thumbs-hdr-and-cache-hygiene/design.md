## Context

See proposal.md for why. State of `thumbs/thumbnail.py` on main f19e24f, plus what the gate changes do to it
before this one is implemented:

- `thumbnail_for` computes the key (stat only), returns on a hit, otherwise probes the clip once
  (`_probe_duration` keeps only `.duration` of the `ClipMetadata`), makes `.<key>.<uuid hex>.tmp`
  (`_create_temporary`: `mkdir`, then `O_CREAT|O_EXCL`), runs `_extract`, then `_finalize` (`fsync`,
  `os.replace`). `except BaseException` removes the temporary.
- `thumbnail_args(clip, *, at, output)` is a pure function with a golden test. The `-vf` is
  `scale=trunc(iw*sar/2)*2:ih,scale=320:180:force_original_aspect_ratio=decrease,setsar=1`.
- `ClipMetadata.is_hdr` is `color_transfer in {smpte2084, arib-std-b67}`. The renderer's CPU HDR chain is the
  constant `CPU_TONEMAP_FILTER` in `accel/profiles/cpu.py`:
  `zscale=t=linear:npl=100,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p`.
- The CLI (`thumbs`) lets a `ThumbnailCacheError` from a future propagate, cancels queued clips and exits
  non-zero with one message; the thumbnail route maps it to a `502` without the clip-failure kind. Both are
  specified and tested already (headless-cli "An unwritable cache directory stops the run"; api-service "A
  cache that cannot be written is the service's fault").
- Gates that merge first and shape the code this change edits: `thumbs-cache-key-and-count` (payload is
  `[resolved.name, size, mtime_ns, position, box, VERSION]`, `THUMBNAIL_VERSION = 2`);
  `ffmpeg-runtime-utf8-and-timeout` (`thumbnail_for` derives `runtime.with_timeout(THUMBNAIL_TIMEOUT)` and
  passes it to the probe and `_extract`; `_extract` catches `FfmpegTimeoutError` before `FfmpegError`;
  the `UnicodeDecodeError` branches are gone, so stderr is always a `str` with `\xNN` escapes).

## Goals / Non-Goals

**Goals:**
- An HDR clip's thumbnail looks like its rendered movie, not like a clipped signal.
- A full disk stops a `thumbs` run or fails a service request once, as a cache error.
- Killed extractions do not accumulate hidden files, without ever deleting a live writer's file.

**Non-Goals:** see the proposal. Design-level boundary: no new module, no new config key, no new error type.

## Research & Decisions

### The tone-map chain works for a fully tagged clip and fails loud otherwise
**Context**: The triage sketch named the chain from `normalize.py`; it had to be shown to work on one frame
with the thumbnail's other filters and the `mjpeg` encoder.
**Explored**: Scratch ffmpeg runs (system ffmpeg 8.x, outside the repo). A 640x360 clip tagged
`bt2020` / `arib-std-b67` / `bt2020nc` (x264, 8-bit, and x265, 10-bit): `CPU_TONEMAP_FILTER` followed by the
two scales and `mjpeg` exits 0 and writes a 320x180 JPEG. A clip tagged with only a transfer, as
`tests/conftest.py::make_clip(color_trc=…)` makes (primaries and matrix `unknown`, which the probe still
flags `is_hdr`): `zscale` fails with `no path between colorspaces`, exit 187, nothing written.
**Decision**: Prepend `CPU_TONEMAP_FILTER` ahead of the existing scales, for `is_hdr` clips only.
**Rationale**: Same operator, same npl and same output colour space as the render, so a thumbnail and its
movie agree. Tone-mapping at source resolution before scaling costs well under a second for one 4K frame and
sits inside the 60 s bound of the gate change; scaling first would blend in a non-linear HDR signal.

### An HDR clip with missing tags
**Context**: The same chain fails on a clip tagged only with a transfer function.
**Decision**: It is that clip's `ThumbnailError` ("no frame extracted at …", with ffmpeg's `no path between
colorspaces`). The system does not add `zscale=pin=…:min=…` hints.
**Rationale**: Principle I: supplying primaries and matrix for a file that does not declare them is
fabricating metadata. The renderer's own HDR segment fails the same way on that file, so the GUI is not
promising a movie the engine cannot make. The failure names its cause once per clip, as any other clip
failure does. A real camera HDR file carries all three tags.

### Why a version bump and not an `hdr` key flag
**Context**: Triage suggested adding an `hdr` entry to the key payload for HDR clips only, so that SDR keys,
and the SDR files already cached, stay valid.
**Explored**: `thumbnail_key` runs before any probe, and `thumbnail_path` (used by the CLI's cached count and
the thumbnail route's `ETag` and lookup) never probes. D-11 and the spec require "a cache hit costs one `stat`
and one hash" and "returned without running ffprobe or ffmpeg". `is_hdr` is known only after a probe.
Alternatives: (a) probe on every lookup, which turns a cache hit into an ffprobe per clip per list view;
(b) look under an SDR key, then an HDR key, which still needs a probe to know which file to write and returns
a stale clipped picture for an HDR clip cached before the fix; (c) a second probe-free signal for HDR, which
the staleness contract (Principle IV: no media decoding for a lookup) rules out in spirit.
**Decision**: Bump `THUMBNAIL_VERSION` by one. The key's payload shape is untouched; the extraction, not the
key, learns about HDR (from the probe `thumbnail_for` already runs on a miss).
**Rationale**: The constant exists for this ("bump whenever extraction changes its output"). The cost is one
regeneration of the thumbnail set, which is bounded by `--jobs` and by the service's two-slot gate, and the
`ETag` changing once. That is the second bump in a short time (the gate change made it 2); if both ship
together, operators pay once. The old files are orphaned and stay (D-11, never evicted).

### Reuse `CPU_TONEMAP_FILTER` instead of copying the string
**Context**: `thumbs/` must not drift from the render's chain.
**Decision**: `thumbnail.py` imports `CPU_TONEMAP_FILTER` from `accel/profiles/cpu.py`.
**Rationale**: `thumbs/` is a leaf feature module consumed by `cli/` and `api/`, above `probe/`, like
`render/` is; importing a lower `accel/` constant breaks no boundary and leaks no vendor name (the CPU profile
is the vendor-neutral fallback). A copy would be a second place to change when the render's chain does, and
nothing would tell us. If `accel/__init__` ever imports `thumbs/`, move the constant; no cycle exists today.
Subprocess invocation stays in `ffmpeg/` (Principle VI): the chain is a string, run through the runtime.

### `thumbnail_args` takes an explicit `hdr` flag; the probe is read once
**Context**: `thumbnail_args` is pure and golden-tested; `thumbnail_for` needs `is_hdr` as well as the
duration.
**Decision**: `thumbnail_args(clip, *, at, output, hdr=False)`; `_probe_duration` becomes `_probe_clip`
returning the probed duration and `is_hdr` (a small `NamedTuple`), with the same duration validation and
errors. `thumbnail_for` passes `hdr=is_hdr` to `_extract` and then `thumbnail_args`. With `hdr=False` the
list is byte-for-byte what it is today.
**Rationale**: One probe, one source of truth for `is_hdr` (the engine's), no `color_transfer` string
matching in `thumbs/` (nothing guessed). A default value keeps existing callers and the existing golden test.

### Classify a full disk from ffmpeg's stderr, not from a free-space floor
**Context**: `os.open(O_CREAT)` succeeds on a full disk, so the preflight cannot see it. Triage offered two
options: parse stderr, or `statvfs` against a floor.
**Explored**: `ffmpeg … -f image2 -update 1 -y /dev/full` prints `Error submitting a packet to the muxer: No
space left on device` and `Task finished with error code: -28 (No space left on device)`. That is the stderr
a full cache directory produces (the same errno), and it is reproducible without a tiny filesystem.
**Decision**: In `_extract`, after the timeout branch of the gate change and before the generic one, an
`FfmpegError` whose stderr part contains `No space left on device` or `Disk quota exceeded` raises
`ThumbnailCacheError(f"{cache_dir}: cannot write thumbnails: No space left on device")`. "Stderr part" is the
text after `\nstderr:\n` in the message, so a clip called `No space left on device.mp4` (the failing command
is quoted above the stderr) is not misread. The existing `except BaseException` removes the temporary.
**Rationale**: Evidence beats a threshold: no constant to tune, no race between the check and the write, and
it also catches a quota. `statvfs` stays out (Principle VII). The text is the C library's `strerror` as ffmpeg prints it (English in the C locale, as seen here); if a build
ever localised it, the failure degrades to today's per-clip error, never to a wrong success.
**Failure behaviour**: nothing is written under the final name; the temporary is removed; the CLI prints one
error and exits non-zero without per-clip lines; the service answers `502` with a detail naming the
directory. A re-run after freeing space regenerates everything missing (idempotent); `--force` is not
involved.

### Sweep from the cache-directory ensure path, once per process per directory
**Context**: Both `thumbs` and `serve` fill the cache through `thumbnail_for`; routing the sweep through
`cli/` and `api/` startup hooks would touch two more packages and a shutdown/lifespan path.
**Decision**: `sweep_stale_temporaries(cache_dir, *, older_than=STALE_TEMPORARY_AGE, now=None) -> int`
(public in `thumbs/`, returns the count removed). `_create_temporary` calls it right after the `mkdir`, guarded
by a module-level set of already-swept resolved directories and a lock, so it runs at most once per process
per directory, and only on a cache miss (a process that only serves hits writes nothing and sweeps nothing).
`STALE_TEMPORARY_AGE` is a module constant of one day (86 400 s).
- A candidate is a regular file whose name matches `^\.[0-9a-f]{64}\.[0-9a-f]{32}\.tmp$` (the engine's
  `.<sha256>.<uuid4 hex>.tmp`) and whose `st_mtime` is more than `older_than` seconds before `now`. Directories,
  symlinks, `<key>.jpg` and any other name are skipped.
- mtime, not creation time: a writer touches the file as it writes, so a day without a write is not a live
  writer; with the gate change's 60 s bound an extraction cannot outlive its file's mtime by a day. A file
  dated in the future (clock skew) is not old, so it stays.
- The sweep never raises: an unreadable directory or a failed `unlink` is logged at debug level and the run
  continues. The directory's readability is already reported by `mkdir` and the `open` that follow, as a
  cache error. A removal count above zero is logged at info level.
- The set is marked before the scan, so a failing scan is not retried in a loop.
**Rationale**: Smallest wiring that reaches both clients, no new startup contract, and a day is long
against any live extraction yet short against an accumulating leak. A `thumbs` run over an hours-long batch
cannot have its own young files deleted by a concurrent `serve` for the same reason.
**Idempotency**: a second call finds nothing; a worker restart mid-extraction leaves a young temporary that a
later run, a day on, removes.

## Risks / Trade-offs

- [Every cached thumbnail regenerates once after the bump, SDR ones included, for a benefit that today
  reaches no clip of the surveyed archive] -> Bounded work (`--jobs`, the service's two slots, ≈15 KB per
  clip); the alternative is a silent stale picture the day HDR footage arrives. Folded into one regeneration
  if the gate's bump and this one ship together.
- [An HDR clip lacking primaries or matrix now has no thumbnail where it had a clipped one] -> Deliberate
  (Principle I); the error names ffmpeg's cause, and the render of that clip fails the same way.
- [The English-text match on stderr] -> Falls back to today's per-clip error, never wrongly succeeds.
- [A sweep deletes a file another process still writes] -> Only files untouched for a day are removed.
  Writers stamp the mtime continuously and are bounded to 60 s by the gate change.
- [Tone-mapping at source resolution is slower for a 4K frame] -> One frame; within the 60 s bound.
- [`thumbs/` now imports `accel/profiles/cpu.py`] -> A constant only; documented above.

## Migration Plan

Deploy by shipping the code. The first run after upgrade regenerates thumbnails under new keys; nothing is
migrated and nothing is removed. The next cache miss in any process sweeps stale temporaries. Roll back by
reverting: files keyed by the bumped version are orphaned, and any older file with the previous version's
key is read again.

D-11 in `docs/high-level-design.md` is amended in the same change (dated sub-bullet, task 3.1): HDR is
tone-mapped, a full disk is a cache error, stale temporaries are swept after a day.
