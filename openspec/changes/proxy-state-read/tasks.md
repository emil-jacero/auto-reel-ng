## 1. proxies/

- [ ] 1.1 Read the merged `proxy-encode` and `filmstrip-sprites` code first (key function, entry paths, `facts.json`
  field names, `proxies` settings resolver, typed cache error) and reconcile the seams in design.md (done at
  proposal time; the names are final). Add `proxies.read_proxy_state(clip_path, settings) -> ProxyReading`
  (frozen dataclass: `status`, validated `facts`, `filmstrip`, `proxy_path`, `reason`; `ProxyEntry` is taken by
  the gate's complete-entry type) with the states and precedence of the `clip-proxies` spec, strict on required
  facts and tolerant of extra ones, reusing `ProxyFacts.from_json` and `Filmstrip.from_json`, no process, no
  write, no directory listing, `OSError` other than "not there" raised as the package's typed cache error. Verify in `tests/test_proxies_state.py`: a table of hand-built cache
  trees (complete -> `ready`; nothing -> `absent`; proxy + facts without filmstrip -> `absent`; truncated JSON,
  JSON array, missing `duration`, `duration` 0, bool for a number, negative width, `rotation` 360, empty
  `proxy.mp4`, empty filmstrip, a filmstrip record of another format version or not matching the image's size,
  a malformed `filmstrip` object -> `stale`; a facts file with no `filmstrip` object, or a record whose image is
  not there -> `absent`; marker only -> `failed`; marker + complete -> `ready`; marker +
  damaged facts -> `failed`; extra unknown field -> still `ready`; `audio_codec: null`, `rotation: null`, `vfr: null` -> `ready`; VFR 30000/1001
  kept as two integers); a version-bumped or file-replaced clip -> `absent` with the old entry untouched; an
  unsearchable entry directory (mode 000, skipped when running as root) raises the typed error; the cache
  tree's names, sizes and mtimes are identical before and after; `subprocess.Popen`, `asyncio.create_subprocess_exec`
  and `os.system` patched to raise are never called; a `has_ffmpeg` round trip makes a real entry from a
  synthesized clip with `ensure_proxy` and reads it `ready` with the facts it wrote.
- [ ] 1.2 Record a failure: on `ensure_proxy`'s failure exits (a `ProxyError` from the probe, the encode or the
  post-encode verification; not a cache error, a cancel or `ensure_filmstrip`, whose failures `clip-filmstrips`
  says are not remembered) write `<cache_dir>/<key>.fail` as `{"reason": <one line>}` atomically (temporary file, `fsync`, rename), best
  effort with a warning when unwritable, the reason carrying the file name only and never an absolute path, no
  expiry. Verify in `tests/test_proxies_failure.py` with a fake ffmpeg runner: a failing encode leaves the marker,
  no entry directory and no `.part`; the marker's reason has no `/`-rooted path (a message containing
  `/var/home/x/lib/C0047.MP4` is recorded as `C0047.MP4`); a read-only cache gives the attempt's own error plus
  a logged warning and no second exception; a retry that succeeds reads `ready` with the marker still on disk;
  the marker for a file whose mtime changed is not found (new key); the reader returns `failed` with the reason.

## 2. api/

- [ ] 2.1 Add to `api/schemas.py` `ProxyState` (a `StrEnum` of `absent`, `ready`, `stale`, `failed`, so the schema
  publishes the closed union), `ProxyFilmstripOut`, `ProxyFactsOut` and `ProxyOut` (`state`, and optional
  nullable `facts`, `version`, `reason`), and `ClipOut.proxy: Optional[ProxyOut] = None`, with the `ClipOut`
  docstring extended (the second media-fact exception, `null` means unknown, `facts.duration` is not
  `ClipOut.duration`). Verify in `tests/test_api_openapi.py`: `ClipOut.properties.proxy` is nullable and not in
  `required`; the `ProxyState` enum is exactly the four values; `ProxyFactsOut` requires every fact and
  `fps_num`/`fps_den`/`width`/`height`/`rotation` are integers; `ProxyOut.facts`, `version` and `reason` are
  optional and nullable.
- [ ] 2.2 Wire the read in `api/events_read.py`: `_proxy_settings` resolves the `proxies` settings once per detail
  request (a `ConfigError` -> one warning -> `None`, as `_thumbnail_settings`), `_build_chapters` and `_clip_out`
  carry it, and `_clip_proxy` maps `ProxyEntry` to `ProxyOut` after the MISSING short-circuit (`version` from
  `MediaFile(path, stat).etag` without quotes; `reason` through `thumbs.one_line_cause`; the typed cache error
  or a failed key `stat` -> `None` for that clip). The events list is untouched. Verify in
  `tests/test_api_proxy_state.py`: a prepared PCM Sony-like clip and a rotated portrait clip report the
  recorded facts exactly and a `version` equal to the proxy file's quoted-stripped `MediaFile.etag`; an
  unprepared clip is `{state: absent}` and the cache listing is identical before and after; a failed clip
  reports its pathless reason; a file replaced after its proxy was made reads `absent`; a MISSING clip, an
  unresolved `proxies` config (`cache_dir: relative/path`, with a single warning logged, 200 and other fields
  unchanged), an unsearchable cache and a no-document (seeding) event each behave per the spec; `staleness` is
  identical with and without proxies; the events list response has no `proxy`; a 25-clip event with
  `subprocess.Popen`, `asyncio.create_subprocess_exec` and `os.system` patched to raise returns 200 (the
  probe-free test) and `ClipOut.duration` is unchanged.
- [ ] 2.3 Regenerate `web/openapi.json` with `.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json` on
  top of the merged gates. Verify `tests/test_api_openapi.py`: the drift test passes, `EXPECTED_MODELS` lists
  the four new models, and the committed file still equals what the application produces.

## 3. web/ (generated client and verification only)

- [ ] 3.1 Regenerate `web/src/api/schema.d.ts` (`npm run generate:types` in the `node:22` container, `TMPDIR`
  exported) and verify `npm test`, `npx tsc --noEmit` and `npm run build` pass with `proxy?: ProxyOut | null`
  on the clip type and `ProxyState` a four-member union; the bundle size is unchanged (no runtime code was
  added), recorded from the build output.
- [ ] 3.2 Verify in real browsers (Chrome 154 image `localhost/playback-research:chrome` and Firefox >= 155 from
  `localhost/pcm-audio-research:pw163`, Playwright from the scratch directory only): on a dev library of
  symlinked sample clips, run `auto-reel proxies` for one event with `XDG_CACHE_HOME` pointing at a scratch
  directory, leave one clip unprepared, one with a damaged `facts.json` and one with a `.fail` marker, serve it
  on port 8306, then `fetch` the event detail from the page and assert the four states, the facts of the ready
  clips (Sony PCM clip reports `audio_codec` `pcm_s16be`, the rotated clip `rotation` 90) and that `version`
  equals `"{size:x}-{mtime_ns:x}"` computed in the scratch script from a `stat` of the proxy file (no
  repository route is added); open the event page in light and dark at 1280 and 390 px with writes routed away (only
  `**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel`, `**/reel?*`), scope locators to `main:not([hidden])`, and
  look at the screenshots to confirm the page is unchanged by the new field.

## 4. docs/

- [ ] 4.1 Amend `docs/high-level-design.md` (the D-20 timeline entry is `timeline-model`'s and is not touched
  here): the §4.9 probe-free paragraph (a second sanctioned cache read: the detail's per-clip `proxy`, from
  `facts.json` by `stat` + JSON, `null` when unknown, never `absent` for an unreadable cache), the §4.10 v2
  bullet on proxies (state and facts in the detail; the list stays without them; the timeline opens on `ready`),
  the D-21 entry (the four states and their precedence, `stale` meaning an unusable entry at the current
  key, a replaced file or version bump reading `absent`, the `<key>.fail` marker without TTL, `version` as the
  proxy's entity tag, the state not a staleness input) and the §6 phase 8 line for this change. Verify with
  `grep -n "proxy-state-read\|\.fail" docs/high-level-design.md` showing each of the four places, and that
  the §4.9 text no longer says the duration is the only media fact in the detail.

## 5. Validation gates

- [ ] 5.1 Run `black`/`isort` (line length 100), `mypy auto_reel_ng`, `pylint auto_reel_ng` (only the known cairo
  `no-member`) and the full `pytest` (`-m "not requires_db"` only when podman is unavailable, and say so);
  all pass. Confirm `RENDER_GRAPH_VERSION` is unchanged and no staleness fingerprint input was added, and run
  `openspec validate proxy-state-read --strict`.
