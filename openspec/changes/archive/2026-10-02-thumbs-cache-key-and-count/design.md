## Context

See proposal.md for the motivation. Current state, re-checked on main 6a7fe16:

- `thumbs/thumbnail.py::thumbnail_key` hashes `json.dumps([str(resolved), st_size, st_mtime_ns, position,
  list(THUMBNAIL_BOX), THUMBNAIL_VERSION])`, where `resolved = Path(clip_path).resolve()` and the stat is of
  `resolved`. `THUMBNAIL_VERSION` is `1`. `thumbnail_path` and `thumbnail_for` call it; so do the CLI
  (`thumbnail_path`) and the service (`api/events_read.py::thumbnail_source`, which uses the stem of the path
  as the strong `ETag`).
- `cli/thumbnails.py::_thumbs_event` loops over `listing.identities`. For each it computes the target, counts
  the identity as `cached` when the file exists, and otherwise submits one `thumbnail_for` future keyed by
  identity. It then counts one `generated` per future that does not raise. Two identities with one target are
  both uncached when the loop reaches them, so both are submitted and both counted.
- A repro of the first defect: `cp -a clip.mp4 other/clip.mp4` (same size, same `mtime_ns`) gives a different
  key. A repro of the second: `real.avi` plus a symlink `link.avi` in one event prints `2 generated, 0 cached`
  with one file in the cache.
- Pool barrier: `cmd_thumbs` waits for every future of an event before the next event starts, so a clip shared
  with a later event is already cached when that event is walked. That already works and does not change.
- Two gate changes merge first and are designed around, not duplicated:
  - `ffmpeg-runtime-utf8-and-timeout` edits `_extract`, `_probe_duration` and the `thumbnail_for` call to the
    runtime in `thumbnail.py`. This change edits `thumbnail_key`, the `THUMBNAIL_VERSION` constant and the
    module docstring. The hunks do not overlap. The gate leaves the "cached outside the library" requirement
    of `clip-thumbnails` alone, so the MODIFIED block below does not conflict.
  - `cli-project-context-module` moves `_project_context` to `cli/context.py` and edits the import and the
    first line of `cmd_thumbs` in `cli/thumbnails.py`. This change edits only `_thumbs_event`.

## Goals / Non-Goals

**Goals:**
- A thumbnail survives a move, copy or remount of the library.
- Several identities that share one file produce one extraction and one `generated`, and the per-event counts
  still add up: `clips = generated + cached + failed`.

**Non-Goals:**
- Content hashing or any read of the clip's bytes on a cache check (a hit costs one `stat` and one hash
  today, and keeps doing so).
- Eviction of orphaned files.
- A new `thumbs` output column or a new CLI flag.

## Decisions

### The key is the file's name, size, mtime and settings, not its location

**Context**: A key must change when the clip's bytes change and may not change when only its location does.
The clip file's identity inside a library is not the path: the same clip is linked into several events, and
the whole library moves between hosts and mount points (MOL drive, compose `/library`).

**Explored**: (a) Keep the path, strip a configured library root: needs the root in every caller, and does not
help a clip linked from outside the root. (b) Hash the first and last 64 KiB: sound, but every cache check,
which today only stats, would read from a drive that may be a spinning disk or a network share, and the CLI
checks every clip of the archive. (c) Drop the path and keep the stat signal plus the file name.

**Decision**: (c). The key payload becomes

```python
resolved = Path(clip_path).resolve()      # symlinks followed, as today
stat = resolved.stat()
payload = json.dumps([resolved.name, stat.st_size, stat.st_mtime_ns,
                      position, list(THUMBNAIL_BOX), THUMBNAIL_VERSION])
```

`resolved.name` is the final component after resolution. A link `Kvällen/grillen, del 1.mp4 ->
clips/s1710001.mp4` therefore hashes `s1710001.mp4`, the name of the file itself, and a link and its target
still share one key. `ensure_ascii` stays on (the default), so a non-UTF-8 name (surrogate escapes) still
encodes. The stat is still of `resolved`, and its `OSError` still propagates unchanged
(`FileNotFoundError` for a vanished clip), which the CLI and the route both rely on.

**Rationale**: Size and `mtime_ns` already separate edited or replaced files. The name adds discrimination
for free, and a rename gets a new thumbnail, which is conservative. Nothing about the check's cost changes.

### Residual collisions are accepted

**Context**: Two different files with the same name, size and `mtime_ns` now share a key and so a thumbnail.
**Explored**: How realistic this is for this archive: camera files carry counters (`s1710004.mp4`), and the
same name recurs across events and chapters, even inside one event (`s1710004.mp4` and `Kvällen/s1710004.mp4`
in the dev library). Two of them would also have to match to the byte in size and in `mtime_ns`. Two different
recordings do not, even on a filesystem with a coarse timestamp resolution.
**Decision**: Accept it; document it in the proposal's non-goals and here. If it ever bites, hash the first
and last 64 KiB then, and bump `THUMBNAIL_VERSION` again.
**Rationale**: Principle VII; the failure is a wrong preview image, never a wrong render, and the thumbnail is
derived, rebuildable state (Principle II): deleting the cache directory repairs it.

**Test consequence.** The test library fixture in `tests/test_cli_thumbs.py` writes clips with equal names and
equal sizes in different folders (`tjorn s1710004.mp4` and `kvall s1710004.mp4`, both 18 bytes). They only
differed by their write-time `mtime_ns`, which the kernel's timestamp granularity can make equal. The fixture
must set distinct `mtime_ns` values explicitly (`os.utime`) so the tests do not rely on the clock.

### One bump of `THUMBNAIL_VERSION`, no eviction

**Context**: Files keyed the old way can never be read again once the payload changes, but a stale version
number would make the payload change invisible to anyone reading the code.
**Decision**: `THUMBNAIL_VERSION = 2`. Its documented purpose ("bump whenever thumbnail_args changes the
output bytes") is extended to "or whenever the key's payload changes".
**Rationale**: The payload is a list, so the new list could never collide with an old one even without a
bump (different length, different first element). The bump is still the honest signal and also changes the
route's `ETag`, so browsers drop their held copies once.
**Consequence**: Every thumbnail regenerates once after the upgrade. The orphaned files stay (D-11: never
evicted in v1, about 15 KB per clip, so a library of 5,000 clips leaves roughly 75 MB). Deleting the cache
directory removes them. Eviction is a separate change if ever wanted.

### `_thumbs_event` works on distinct thumbnail files

**Context**: The per-identity loop treats a clip and a file as one thing. They are not, and the count is the
number of files generated.

**Decision**: Group identities by target path in listing order, then submit one future per target:

```python
groups: Dict[Path, List[str]] = {}      # target -> identities, in listing order
for identity in identities:
    ...                                 # stat failure: errors[identity] = ..., continue
    groups.setdefault(target, []).append(identity)

for target, members in groups.items():
    if is_cached(target):
        cached += len(members)          # every member is already served
        continue
    futures[target] = pool.submit(thumbnail_for, ref.event_dir / members[0], ...)
```

After the futures finish, for each target `members[0]` counts as `generated` and `members[1:]` as `cached`
when the future succeeded. When it raised `ThumbnailError`, every member gets `errors[member] = exc.reason`
(the `ERROR` line names the member itself) and `failed` counts each of them.

- The clip handed to `thumbnail_for` is the first member, which resolves to the same file as the rest
  (that is how they came to share a target), so the probe and the extraction see the same bytes.
- A cache error (`ThumbnailCacheError`) or an interrupt still propagates and cancels the queue, unchanged.
- The stat failure for an identity (the clip vanished between listing and stat) is still its own failure and
  joins no group.
- `clips = generated + cached + failed` holds for every event, and the final summary adds them as before.
- Output order is unchanged: ERROR lines in identity order, then the event line. No new column: a clip that
  shares a file with a sibling is "cached" in the sense that its thumbnail was there, from its sibling, by the
  time it was reported.

**Alternatives**: (a) Count distinct files and print `shared N` in the event line: a second number to explain
for no decision the operator can make. (b) Submit all identities but let `thumbnail_for` serialize on a
per-key lock: it still counts each as generated and adds a lock table. (c) Tell the two apart by comparing
`generated` with the cache directory's file count: not a count of what happened.

**Failure behavior** (Principle I): a failed shared file is reported once per clip, never as generated and
never as cached. Extraction is attempted once per file, not once per link.

**Idempotency**: a re-run finds every target cached and prints all clips as `cached`, including links. An
interrupted run leaves no temporary file (unchanged; `thumbnail_for` cleans up). Two runs at once (CLI and
service) still race safely, because the file is written and renamed atomically; the grouping only stops one
process racing itself.

## Risks / Trade-offs

- [Two unrelated files share name, size and mtime and so one wrong preview] → Documented above; deleting the
  cache directory repairs it; hash a clip's ends if it is ever seen.
- [A copy to a filesystem with coarser mtime resolution regenerates] → Accepted; the thumbnail is rebuilt
  once and then cached under the new signal.
- [One-time regeneration after the version bump of a large archive] → Bounded by `--jobs`; the route fills
  thumbnails on demand in the meantime.
- [Orphaned files from earlier versions and mount points stay] → D-11 (no eviction); deleting the cache
  directory is safe because it is derived state.
- [The gate changes merge first and move lines in `thumbnail.py` and `cli/thumbnails.py`] → Tasks name
  functions, not line numbers; implementation starts from main after both merged.

## Migration Plan

None. There is no schema, no config key and no rescan. After the upgrade, thumbnails regenerate on demand
or on the next `auto-reel thumbs`. Rolling back the code finds any surviving version-1 file again where the clip's path
is unchanged and regenerates the rest, so no step is needed in either direction.

D-11 in `docs/high-level-design.md` says the cache is "keyed by the resolved clip path, size, mtime, position,
box and `THUMBNAIL_VERSION`". It outlives this change and is amended in it (see tasks).
