## Why

Two defects in the clip-thumbnail cache (D-11, HLD §4.10, phase 8 GUI v1), both confirmed on main 6a7fe16.

1. **Moving or remounting the library regenerates every thumbnail.** `thumbnail_key` puts the clip's absolute
   resolved path in the sha256 payload. A `cp -a` of a clip to another directory keeps its size and `mtime_ns`
   and still gets a different key. The archive lives on the MOL drive, which mounts at different paths on
   different hosts, and the compose stack mounts the library at `/library`. Each such change re-extracts every
   thumbnail, and the old files are never evicted, so the cache grows by one full set per mount point.
2. **`auto-reel thumbs` overstates `generated` for linked clips.** In one event, two identities that resolve
   to one file (the dev library links `s1710004.mp4` and `Kvällen/s1710004.mp4` to one clip) have one key. The
   command submits an extraction for each, because neither is cached when the event is walked. The two race
   to replace the same file, and both count as `generated`. Observed on a scratch project with `real.avi` and
   a symlink `link.avi` in one event: `thumbnails: 2 clips in 1 event: 2 generated, 0 cached`, with exactly
   one file in the cache directory.

Principle I (report what happened, not a guess) covers the count. Principle VII (simplest thing that serves a
real library) covers the key: a path is not needed to tell clip files apart.

## What Changes

- **The cache key no longer contains the clip's directory.** It is the SHA-256 over the clip's file name
  (after following symlinks, so a link and its target share one name), its size, its `mtime_ns`, the position,
  the box and the thumbnail format version. A moved, copied or remounted library keeps its cache.
- **The thumbnail format version is bumped once**, so no file keyed the old way is read as a hit under the new
  key by accident. Existing files are orphaned and stay in place (nothing is evicted); every clip regenerates
  once.
- **`auto-reel thumbs` extracts each distinct thumbnail file once per event** and counts it once. Identities
  that share a file report as `cached` (the first of them in listing order is the one that generates). A
  failure applies to every identity that shares the file, and each still gets its own `ERROR` line.
- Tests: a `cp -a` copy gets an equal key; a renamed clip gets a different one; a symlink pair in one event
  runs ffmpeg once and prints `1 generated, 1 cached`.

Rendered output and the staleness fingerprint do not change: thumbnails are not part of a render, so
`RENDER_GRAPH_VERSION` is not bumped. No `reel.yaml` or `config.yaml` schema change, no Alembic migration, no
rescan. The thumbnail route's `ETag` is the cache key, so it changes once with the version bump and no longer
changes when a clip only moves; the route's behavior, as specified, is otherwise untouched. Both the CLI and
(through `thumbnail_path`) the API use the one key function, so no code in `api/` changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `clip-thumbnails`: the cache key covers the resolved file's name instead of its resolved path.
- `headless-cli`: `thumbs` extracts and counts each distinct thumbnail file once per event.

## Impact

- `auto_reel_ng/thumbs/thumbnail.py`: `thumbnail_key`, `THUMBNAIL_VERSION`, and the module docstring that
  describes the key.
- `auto_reel_ng/cli/thumbnails.py`: `_thumbs_event`.
- `tests/test_thumbs.py`, `tests/test_cli_thumbs.py` (and its library fixture).
- `docs/high-level-design.md` D-11 and the `README.md` thumbnails paragraph name the key; both are amended in the same change.
- Two packages (`thumbs/`, `cli/`), CLI and API both read the new key; the API's code is unchanged.
- **Ordering.** Gate changes `ffmpeg-runtime-utf8-and-timeout` (edits `thumbnail_for` and `_extract` in
  `thumbnail.py`) and `cli-project-context-module` (replaces the `_project_context` import in
  `cli/thumbnails.py`) merge first. This change is written against main after both and touches neither area.

## Non-goals

- Evicting orphaned thumbnails, from the version bump or from old mount points. D-11 says "never evicted in
  v1" (about 15 KB per clip).
- Keeping the cache across a move to a filesystem with a different `mtime_ns` resolution. The key still
  includes `mtime_ns`; a copy that rounds it is a new clip.
- Content hashing. See design, "Residual collisions".
- Any change to the thumbnail route, its limits, or the `v` query parameter.
- A separate `shared` column in the `thumbs` output.
