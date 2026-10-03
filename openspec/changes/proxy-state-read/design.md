## Context

State of `origin/main` 8fb4d16 (read before the gates merged), and what the gates add:

- `api/schemas.py` `ClipOut` carries identity, `status`, `size`, `mtime`, `duration`, `excluded`. Its
  docstring and HLD §4.9 say the detail is probe-free; `duration` is the one media fact, read from the
  thumbnail sidecar (`thumbs.recorded_duration`) with the settings resolved once per request
  (`events_read._thumbnail_settings`, a `ConfigError` becoming one warning and `None`). This change copies
  that plumbing for a second cache.
- `thumbs/thumbnail.py` is the model for the proxy cache (D-11): `thumbnail_key` hashes the resolved file's
  name, size, `mtime_ns`, settings and version, so a replaced file moves to a new key; sidecars sit beside
  the JPEG; `recorded_failure` reads `<key>.fail` without writing. The proxy cache differs in having a
  directory entry per key, no TTL on failures, and ready/stale/absent distinctions the thumbnail never needed.
- `api/media.py` `MediaFile.etag` is `"{size:x}-{mtime_ns:x}"` from `os.stat`; D-15 puts the tag in the media
  URL as `v` so a replaced file gets a new address.
- Gates (merged; this section was written before they were and is corrected to what they built):
  - `proxy-encode` adds `auto_reel_ng/proxies` with `ensure_proxy()`, `lookup_proxy()` (a complete entry or
    `None`), `ProxyEntry` (a *complete* entry), `ProxyFacts.from_json`, `PROXY_VERSION`, `proxy_key`, the
    `proxies.*` settings (`resolve_proxy_settings`), the typed `ProxyError` and `ProxyCacheError`, the cache
    entry (`proxy.mp4`, `facts.json`; `.part` then verify then rename) and the capability `clip-proxies`.
    `facts.json` holds `proxy_version`, `duration`, `fps {num, den}`, `vfr` (bool or null), `frames`, the
    proxy's and the source's sizes, `rotation` (0 to 359, or null), `audio_codec` (or null), `encode_path`
    and `fallback_reason`.
  - `filmstrip-sprites` adds `filmstrip.jpg` to the entry and a `filmstrip` object to `facts.json` (`version`,
    `tiles`, `interval`, `columns`, `rows`, `tile_width`, `tile_height`, `width`, `height`, `bytes`), written
    after the image so a record always has its file; `lookup_filmstrip`, `Filmstrip.from_json` and
    `FILMSTRIP_VERSION`. `ensure_filmstrip` is a separate step: the proxy is published before the sprite.
- `ClipOut` is rendered by `events_read._build_chapters` for three cases (no document, the document's clips,
  disk-only clips). All three call `_clip_out`, so one parameter threads the settings through.

## Goals / Non-Goals

**Goals:**
- One nullable `ClipOut.proxy` with a closed state vocabulary, the recorded facts, the media-URL version and a
  failure cause, read with `stat` and one JSON read per clip.
- The reader and the failure marker live in `proxies/`, next to the writer whose layout they know.

**Non-Goals:** see the proposal. Design-level additions: no in-process cache of states (a GET parses disk, D-A3);
no `ETag`/`If-None-Match` on the detail for the proxy; no new config key.

## Research & Decisions

### Where the facts live and why the detail may carry them
**Context**: The timeline needs duration, fps, dimensions and rotation per clip; the detail is probe-free.
**Explored**: `research/v2/synthesis.md` X6 (the API has no duration or fps; the proxy batch already runs
`ffprobe`; write the facts into the cache entry and read them by `stat` + JSON; do not use the proxy's own
`video.duration`, which differs from the source by about 21 ms in the browser and up to 60 ms in Firefox, D-16),
§3 "Facts" and "Cache" rows (`facts.json` beside the proxy; never Postgres; not a staleness input), risk 9
(the timeline cannot open on an unprepared event), risk 14 (a replaced file at an unchanged URL, hence `v`).
`api-clip-duration` (archived 2026-10-02) is the precedent for a cache-read media field in the detail.
**Decision**: `ClipOut.proxy` carries the entry's recorded facts verbatim; `facts.duration` is the probe's
number from the proxy job and is independent of `ClipOut.duration` (the thumbnail sidecar's), which stays.
**Rationale**: no new store, no probe, the key makes a stale number impossible, and the timeline gets the
number X6 says to use. Two durations for one clip are both the probe's measurement of the same file; folding
them would couple the thumbnail cache to the proxy cache for no gain (the proxy facts "must not depend on" the
thumbnail sidecar, brief).

### The four states, and what `stale` means here
**Context**: the plan names `absent | ready | stale | failed`. The cache is keyed like D-11, so the key
already covers the file's name, size, mtime, `PROXY_VERSION` and the settings hash.
**Explored**: (a) report `stale` when an entry exists for the same clip under an older key (a replaced file, an
older `PROXY_VERSION`): finding it needs a per-clip locator the key-addressed layout does not have, so it means
scanning the cache directory per request (5,574 entries for the archive, a read of every entry's facts to
match a name) or a second index that the writer must keep exactly right; rejected, it breaks "stat + JSON
only" and HLD §4.9's whole-library rule for a distinction no consumer needs (the Prepare action, the fresh
check of `POST …/proxies`, the media route and the timeline all treat "no usable proxy for this file" the
same); (b) `stale` for an entry that exists at the current key but cannot be used: damaged or incomplete-typed
facts, an empty proxy or filmstrip file (a truncated copy, a disk-full write that survived the rename, an
entry written by an engine whose facts lack a field this reader requires); (c) drop `stale`: the plan and the
downstream changes name it.
**Decision**: (b). `ready` needs the proxy, the filmstrip and fully valid facts; `failed` is a recorded cause
and nothing usable; `stale` is an entry present at the current key that fails those checks; `absent` is the rest.
Precedence `ready > failed > stale > absent`, with one refinement found while testing the retry: the marker
is about the proxy, so an entry whose proxy and facts are usable (only its sprite is pending or unusable)
is decided by the sprite alone. Otherwise a successful retry would read `failed` with the old cause until
its sprite was cut. A replaced file or a version bump reads `absent`.
`stale` is repairable by the writer: `ProxyFacts.from_json` (shared by the writer's `read_entry` and this reader)
holds the finite/positive/range checks, and `read_entry` treats an empty `proxy.mp4` as absent, so `ensure_proxy`
rebuilds such an entry and `publish` replaces the leftover. Reader and writer agree on "usable".
The filmstrip refines (b): the proxy is published before its sprite, so an entry whose `facts.json` has no
`filmstrip` object, or whose record names an image that is not there, is incomplete, not damaged: `absent`.
A `filmstrip` object that is malformed, of another `FILMSTRIP_VERSION`, or whose image is empty or not the
recorded byte size, is an unusable entry: `stale`.
**Rationale**: each state is decided from files at known paths; a damaged entry is surfaced (Principle I)
instead of read as absent and quietly overwritten, and a consumer can tell "never prepared" from "prepared but
broken, replace it". The incomplete-entry case (proxy and facts exist, filmstrip not yet) is `absent`, not
`stale`, so a job that is between its two steps never shows a damaged-entry state; `proxy-job` makes progress
visible through the job.

### The failure marker, and why it lives in `proxies/`
**Context**: `failed` has to be observable by a read; a failed `ensure_proxy` leaves no entry (the `.part`
is removed), so nothing on disk says it was tried. The job row (`proxy-job`) is per event and in Postgres,
which is not a per-clip answer and not rebuildable from disk (Principle II).
**Explored**: (a) the job's last error; rejected, per event, in the DB; (b) a `<cache>/<key>.fail` JSON file as
D-11 does (`recorded_failure`), with a 60 s TTL; (c) the same without a TTL.
**Decision**: (c): `{"reason": "<one line>"}` written atomically beside the entry directory by `ensure_proxy`'s
failure path (any `ProxyError`: probe, encode, post-encode verification), best effort. `ensure_filmstrip` does
not record one: `clip-filmstrips` (merged) says a sprite failure "SHALL NOT be remembered", and a third
capability delta to change that would break the two-delta limit. A clip whose sprite failed has a valid
proxy and reads `absent`; the CLI and the proxy job report the cause once, and a retry rebuilds only the sprite. No TTL: D-11's TTL exists because a thumbnail is attempted on every page view, so
a failure there must stop being remembered. A proxy is attempted only when an operator or a job asks, and
the answer to "did it fail" must not flip back to `absent` after a minute. A ready entry outranks the marker,
so a later success needs no cleanup, and the key scoping drops the marker when the file changes.
**Rationale**: smallest thing that makes `failed` true on disk; reuses D-11's sidecar idiom (`_write_sidecar`:
temporary file, `fsync`, rename). The reason passes through `thumbs.one_line_cause`-style path stripping on
write (the file name only), so a read can return it as stored; the reader strips again on read
(`one_line_cause(reason, clip_path)`) because the file is data a person could edit, so the API passes the
reason through.

### The reader returns a value; only an unreadable cache raises
**Decision**: `proxies.read_proxy_state(clip_path, settings) -> ProxyReading` (a frozen dataclass: `status`,
`facts` or `None`, `filmstrip` or `None`, `proxy_path` or `None`, `reason` or `None`; the gate's `ProxyEntry`
already means a complete entry, so the reading has its own name). `FileNotFoundError`/`NotADirectoryError` on the
entry or the cache root mean no entry (`absent`, then the marker check). Any other `OSError` raises the package's
typed cache error. A clip that cannot be statted for the key (it changed under the scan) raises `ProxyError`, and
the API turns both into `proxy: null` for that clip, as `_recorded_duration` does for `duration`.
**Rationale**: "no entry" is a fact, "cannot tell" is not; reporting `absent` for a permission error would send the
operator to Prepare something that already exists. The API's rule ("a cache that cannot be read is unknown")
is the single place the softening happens, per clip, with one debug log; the whole response never fails for it.

### Facts mapping is explicit, strict and forward compatible
**Decision**: the reader validates each field the wire shape needs, on top of `ProxyFacts.from_json`
(`duration` finite and above zero; `fps` a pair of positive integers; `vfr` a bool or `null`; `width`/`height`
positive integers; `rotation` an integer 0 to 359 or `null`, the probe's own range; `audio_codec` a string or
`null`; the filmstrip's `tile_width`, `tile_height`, `columns`, `tiles`, `interval` positive integers) and ignores
any extra field. `vfr` and `rotation` are nullable on the wire because the probe's "could not say" is `null` in
`facts.json` (`clip-proxies`: never a default), and mapping `null` to `false` or `0` would be a default. A bool is not a number (the same rule as
`recorded_duration`). The wire names are `fps_num`/`fps_den`, `audio_codec`, `filmstrip`; the on-disk names are
`proxy-encode`'s and `filmstrip-sprites`', and the mapping from one to the other is the only translation, in
one function.
**Rationale**: the timeline snaps and lays out by frame, and 30000/1001 rounded to a float drifts; the schema
publishes integers so the generated client cannot receive 29.97. Strict on required, tolerant of extras, so
`filmstrip-sprites`-style additions to `facts.json` do not turn every entry `stale`.

### `version` is the proxy file's entity tag, computed with `MediaFile`
**Decision**: for a `ready` entry the API stats `proxy.mp4` and builds the version as `"{size:x}-{mtime_ns:x}"`
(`MediaFile.etag` without its quotes). `api/media.py` imports `events_read`, so `events_read` cannot import
`MediaFile`: the formula sits in a new two-line module `api/entity_tag.py`, and a test pins its output to
`MediaFile(path, stat).etag` so the two cannot drift. (Making `MediaFile.etag` call it is a one-line follow-up
left to `proxy-media-endpoints`, which is editing `media.py` now.) The same string serves as `v` for the filmstrip URL
(the sprite is written once per key, so the proxy's tag is a valid cache-buster for it; the service ignores `v`).
**Rationale**: one formula for the tag the media routes will send and the tag the detail reports (D-15,
risk 14); a client can build `…/proxy?clip=…&v=…` from the detail alone. The stat is one more per ready clip,
on the local cache disk, not on the archive.

### Plumbing in `events_read`
**Decision**: `get_event` resolves the proxy settings once (`_proxy_settings(settings, config)`: `ConfigError` ->
one warning -> `None`), passes them with the thumbnail settings through `_build_chapters` to `_clip_out`, which
adds `proxy=_clip_proxy(path, proxy_settings)` after its MISSING short-circuit (a missing clip is not looked up).
The list does not call any of it. The config is the one already loaded for the sort rule and the look defaults.
**Rationale**: the same per-request pattern as `thumbnails`, so a `config.yaml` edit shows on the next request
and N clips never parse config N times.

### Process-free by construction, enforced by a test
**Decision**: `proxies/` readers import nothing from `ffmpeg/` or `probe/` (Principle VI: subprocess lives only
in `ffmpeg/`). The test patches `subprocess.Popen` (which `run`, `check_output` and `check_call` use),
`asyncio.create_subprocess_exec`/`_shell` and `os.system`/`os.posix_spawn` to raise during a detail GET, and
asserts the cache directory's tree (names, sizes, mtimes) is identical before and after.
**Rationale**: the brief and §4.9 make probe-freedom a rule, and a rule needs a failing test, not a code review.

## Seams, confirmed against the merged gates

- The key function is `proxies.proxy_key(clip)`; the entry is `<cache_dir>/<key>/` with `proxy.mp4`,
  `facts.json` and `filmstrip.jpg`; the marker is `<cache_dir>/<key>.fail`, beside the directory, as D-11's.
  The key is unchanged.
- The capability file is `openspec/specs/clip-proxies/spec.md`; this change ADDS to it. Its sentence "this
  capability neither writes nor reads `filmstrip.jpg`" predates the filmstrip and is the filmstrip capability's
  to refine; the added requirement reads the image's size, which is consistent with `clip-filmstrips`.
- The reader does not exist in the gates: `lookup_proxy` answers "complete entry or `None`" and conflates absent
  with damaged, which is the distinction this change publishes. The gates' failure record does not exist
  either (`ensure_proxy` records nothing; `ensure_filmstrip` states it remembers nothing).
- `rotation` and `vfr` are nullable in `facts.json`, so they are nullable on the wire (above).

## Risks / Trade-offs

- [A replaced file or a version bump reads `absent`, not `stale`] -> accepted and documented; the cause is the
  D-11 key design, and the consumers treat both alike. Orphaned entries wait for a later `--prune`.
- [Reading `facts.json` per clip on every detail request] -> 25 clips are 25 small local reads and about 125
  `stat`s; no archive-drive I/O beyond what `_file_facts` already does. The list does not read it. If a library
  ever has events of thousands of clips this is the place to add a per-request memo, not a cache.
- [`stale` is stricter than the gates' writer] -> a required fact the writer omits turns every entry `stale`
  and the timeline would never open. Mitigated by the round-trip test (task 1.1): a real `ensure_proxy` entry
  must read `ready`, so writer and reader cannot drift apart unseen.
- [Two durations for a clip] -> documented in the schema docstring; the timeline uses `proxy.facts.duration`,
  the cuts panel keeps `duration`.
- [Conflict with sibling changes in `schemas.py`, `events_read.py`, `openapi.json`, `schema.d.ts`] -> textual;
  `movie-facts-read` (gated on this change) edits the same detail. Regenerate the artifacts from the merged
  code, never merge them by hand.
- [Marker without a TTL could hide a fixed cause] -> a retry always attempts; success outranks the marker; the
  UI offers Prepare for `failed`.

## Migration Plan

Additive nullable field and a new marker file in the cache; no Alembic migration, no `reel.yaml`/`config.yaml`
change, no rescan. Entries written before this change read as `ready`/`absent` by the same rules; a cache with
no markers has no `failed`. Rollback is a revert; clients ignoring the field are unaffected.

## Idempotency

Reading writes nothing, so repeated detail requests, a `--force` render and a worker restart neither read nor
change the cache. Recording a failure is idempotent per key (the same atomic file is replaced); a re-run of
`auto-reel proxies` on a failed clip attempts it again and either replaces the marker or produces an entry that
outranks it.
