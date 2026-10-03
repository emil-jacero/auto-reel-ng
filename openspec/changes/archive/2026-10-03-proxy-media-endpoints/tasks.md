## 1. Baseline

- [x] 1.1 The gates `proxy-encode` and `filmstrip-sprites` are merged into `main`. Confirm the facts the design
  builds on, and stop and report any that do not hold (a different entry layout or finalize order changes
  design decisions 3 and 5):
  - `ls auto_reel_ng/proxies/` exists, and `grep -rn "PROXY_VERSION\|def .*cache_dir\|def .*proxy_key\|def .*entry" auto_reel_ng/proxies/`
    names the settings resolver (`proxies.cache_dir`, default `$XDG_CACHE_HOME/auto-reel/proxies/`), the key
    function and the entry-directory function. Write the real names into the task notes; this change uses them
    wherever the design says "the key" and "the entry".
  - An entry is `<cache_dir>/<key>/{proxy.mp4,filmstrip.jpg,facts.json}`, and the entry directory appears under
    its key only by the rename of the verified hidden `.<key>.<uuid>.part` build directory:
    `grep -n "\.part\|os.replace\|rename" auto_reel_ng/proxies/*.py`.
  - A clip of one second or less gets a one-tile `filmstrip.jpg` (`plan()` in the sprite module; the
    `filmstrip-sprites` archive rejected the research's sub-second skip).
  - Native `aac` is asserted for proxies (so the Firefox sound check in 5.1 is meaningful).
  - `grep -n "def proxy_source\|def .*proxy" auto_reel_ng/api/events_read.py` shows whether `proxy-state-read`
    already maps a listed clip to its entry directory. If it does, task 2.1 calls that function and adds no
    second key computation.
  - `ls openspec/changes/ openspec/changes/archive/ | grep -E "proxy|filmstrip"` lists the gates; note whether
    `proxy-state-read` is open or archived.
  - `grep -n "setdefault(\"etag\"" "$(.venv/bin/python -c 'import starlette.responses as r; print(r.__file__)')"`
    still prints a line (the shared `ETag` rule in `media_response` depends on it), and
    `grep -n "def listed_clip\|def thumbnail_source" auto_reel_ng/api/events_read.py` prints both.
  - `ls ../auto-reel-media/samples/` lists the ten samples (`sony-xavc-1080p25-pcm.mp4` … `legacy-render-mpeg4-mp3.mp4`).
  - `podman images | grep -E "playback-research|pcm-audio-research"` lists `:chrome` and `:pw163`.
  - `openspec validate proxy-media-endpoints --strict` passes.

  **Notes (checked against `main` b1b7829, 2026-10-03):** the settings resolver is
  `proxies.resolve_proxy_settings(config, project_root)` (`ProxySettings.cache_dir`), the key is
  `proxies.proxy_key(clip_path)` and the entry directory `proxies.entry_dir(clip_path, cache_dir)`; the file names are
  `spec.PROXY_FILENAME` / `FACTS_FILENAME` / `FILMSTRIP_FILENAME`. **Two facts differ from the design as first
  written, which was adapted before the proposal was committed:** (1) an entry is built as a hidden directory
  `.<key>.<uuid>.part` and renamed *whole* to `<key>`, so `proxy.mp4` never appears alone under a key (`filmstrip.jpg`
  is renamed into the finished entry later, by `os.replace`); (2) a clip of one second or less gets a **one-tile
  sprite**, it is not skipped. `proxy-state-read` had not landed and `events_read` has no entry-directory function, so
  `proxy_source` computes the entry with `entry_dir`. Gates are archived (`2026-10-03-proxy-encode`,
  `2026-10-03-filmstrip-sprites`).

## 2. api/ — which file is served

- [x] 2.1 Add `ProxySource` (frozen: `clip_path`, `entry_dir`, `proxy_path`, `filmstrip_path`) and
  `proxy_source(settings, event_id, clip)` to `api/events_read.py`, as design decision 3 orders them: `listed_clip`;
  `load_project_config` and the `proxies` settings resolver (`ConfigError`); `os.stat` of the clip following
  links, then the entry directory from the key. Nothing is opened, created or generated, and nothing probes. An
  `OSError` from the clip's stat propagates (task 2.2 translates it). Verify in
  a new `tests/test_api_proxy_media.py`, with a `project` fixture shaped like the clip-media tests' (Grillning,
  Kalas, Tjörn with `Kvällen/` and the IGNORED root clip, Sommarlov with MISSING `borttagen.mp4`, `original/x.mp4`,
  a `.reelignore`d event, an unparseable `reel.yaml`), clips of known distinct bytes, a symlinked clip to a file
  outside the project, and a `config.yaml` that sets `proxies.cache_dir` to `tmp_path / "proxy-cache"`:
  - a root clip, a chapter-folder clip, the IGNORED clip and the symlinked clip resolve; `entry_dir` equals the
    entry directory the `proxies` package computes for the same clip, cache dir and settings (call its own
    function in the test), and `proxy_path` / `filmstrip_path` are `proxy.mp4` / `filmstrip.jpg` in it
  - two events that link the same file give the same `entry_dir`
  - rewriting a clip (new bytes, `os.utime` forward) gives a different `entry_dir`; so does changing the
    configured proxy settings or monkeypatching `PROXY_VERSION`
  - an unknown event and the year folder raise `EventNotFoundError`; `borttagen.mp4`, `original/x.mp4`,
    `Kvällen/../s1710001.mp4`, `../2024-07-14 - Kalas/s1710001.mp4`, an absolute path and `""` raise
    `ClipNotFoundError`
  - an unlistable event folder (mode `000`, restored in `finally`, skipped as root) raises `EventReadError`
    with `UNREADABLE_DISK`
  - an unparseable `config.yaml` raises `ConfigError`; `proxies.cache_dir` inside the project raises it too
  - the clip of the event with the unparseable `reel.yaml` resolves (the document is never read)
  - a clip deleted after the listing (wrap `events_read.scan_event` as the thumbnail tests' `_vanish_after_listing`
    does) raises `FileNotFoundError`; a stat refused with `PermissionError` raises `PermissionError`
  - a snapshot of every path, size and `st_mtime_ns` under `tmp_path`, taken before and after all cases, is
    equal (the cache directory is never created), and `subprocess.Popen` is patched to raise for the module

- [x] 2.2 In `api/media.py` add the declared content type and the two lookups, which also translate
  `proxy_source`'s `OSError`: `FileNotFoundError` → `MediaGoneError`, any other → `MediaReadError`. `open_media(path, *, label,
  media_type=None)` and `MediaFile.declared_type` (`media_type` returns it when set; every existing caller is
  unchanged). Add `ProxyAbsentError(label, what)` (404; `str()` is `<label>: no <what>`, `what` in `proxy`,
  `filmstrip`), `proxy_media(settings, event_id, clip)` and `filmstrip_media(...)`: `proxy_source`, then
  `open_media` on `proxy_path` (`video/mp4`) or `filmstrip_path` (`image/jpeg`), turning `MediaGoneError` into
  `ProxyAbsentError`. `MediaReadError` passes through, labelled with the clip's identity so its text is path-free.
  Verify in `tests/test_api_proxy_media.py` (entries fabricated with the `proxies` package's own entry function,
  files of 300 KiB of a repeating counter so ranges compare exactly):
  - a prepared clip: `proxy_media` returns a `MediaFile` whose `media_type` is `video/mp4`, `name` is `proxy.mp4`
    and `etag` is `'"%x-%x"' % (size, mtime_ns)` of the proxy, not the clip's; `filmstrip_media` gives
    `image/jpeg` and `filmstrip.jpg`
  - `MEDIA_TYPES` still equals `VIDEO_EXTENSIONS`; `clip_media` and `movie_media` results have no
    `declared_type`; `tests/test_api_media.py` passes unchanged
  - no entry, no cache directory, only the encoder's hidden build directory `.<key>.<uuid>.part` holding a
    `proxy.mp4` (the name the cache module uses, from 1.1), an entry directory without `proxy.mp4`, a directory named `proxy.mp4`, and a proxy for the clip's previous bytes all raise
    `ProxyAbsentError`; an entry with a proxy and no filmstrip: `proxy_media` resolves, `filmstrip_media` raises
    `ProxyAbsentError`
  - a proxy with mode `000` (skipped as root) raises `MediaReadError` whose `str()` has the identity and
    `Permission denied` and not `str(tmp_path)`
  - a proxy deleted after `proxy_source` (wrap it) raises `ProxyAbsentError`; a clip deleted after the listing
    raises `MediaGoneError`, and one whose stat is refused raises `MediaReadError`

## 3. api/ — routes

- [x] 3.1 In `api/routes/media.py` add `get_clip_proxy` and `get_clip_filmstrip`, each `@router.head` stacked
  over `@router.get` with `response_class=Response` and `PROXY_RESPONSES` / `FILMSTRIP_RESPONSES` (design
  decision 8: `MEDIA_RESPONSES` with the 200 and 206 content swapped), sync `def`, the clip route's declared
  `clip`, `v`, `If-None-Match`, `If-Modified-Since`, `Range`, `If-Range` parameters, and the clip route's
  `_if_none_match` / `_if_modified_since` readers. Map by cause per design decision 7, with a WARNING on every
  502 (`_media_failed`, `_unreadable`): `ProxyAbsentError` → `not_found` naming the event, the clip and "no
  proxy" / "no filmstrip"; `ConfigError` and `LayoutError` → 502 with no kind; the rest as the clip route. The
  router stays included before `events_router` in `app.py`. Verify in `tests/test_api_proxy_media.py`, each test
  building its own app on `UNREACHABLE_DATABASE_URL`:
  - proxy, prepared clip: 200 with the entry's bytes, `video/mp4`, `Accept-Ranges: bytes`, `Last-Modified`, the
    `ETag` format, `Cache-Control: private, no-cache`, `Content-Disposition` `inline; filename="proxy.mp4"`,
    and an `ETag` different from `/media`'s for the same clip
  - ranges: `bytes=0-99`, `bytes=1000-`, `bytes=-500` → 206 with exactly those bytes; `bytes=<size>-` → 416
    `bytes */<size>`; `bytes=abc` → 400 `text/plain`; `If-Range` with the tag → 206, with `"old"` → 200
  - validators: `If-None-Match` with the tag (alone, with `Range`, on two lines) → 304 empty; `If-Modified-Since`
    with the `Last-Modified` → 304; a proxy replaced in place (new bytes, `os.utime` forward) with the old tag →
    200 and a new `ETag`; `v=a`, `v=b`, no `v` → identical bodies and `ETag`
  - `HEAD` for 200, 206 (`Range: bytes=0-99`, `Content-Length: 100`), 304 and 404: the `GET`'s status and
    headers, no body; the `HEAD` `ETag` equals the `GET`'s
  - filmstrip: 200 `image/jpeg` with `filename="filmstrip.jpg"`; a range → 206; `If-None-Match` → 304; an entry
    with a proxy and no filmstrip → proxy 200 and filmstrip 404
  - absent: never prepared, no cache directory, partial only, replaced clip, other `PROXY_VERSION` → 404 problem
    with `event_id`, the clip identity and "no proxy" in the detail, no `ETag` or `Cache-Control`, no body of
    the original; none of 200, 202, 204 or 3xx; the cache tree snapshot is equal before and after
  - lookups: the IGNORED clip with an entry → 200; the symlinked clip → 200; two events linking one file → the
    same bytes; MISSING, outside, normalizing, `original/`, the year folder, unknown event, vanished clip → 404
    with `event_id`; the punctuated identity sent with `urllib.parse.quote(identity, safe="")` → 200; a missing
    `clip` → 422
  - 502s: mode `000` on `proxy.mp4` (skipped as root) → no `failure`, detail has the identity and `Permission
    denied` and not `str(tmp_path)`, WARNING logged (`caplog`), and no 200/206 status line; an unparseable
    `config.yaml` → 502 with no `failure`; an unlistable folder → 502 `failure: unreadable_disk`
  - scope: the database is unreachable on every app here (never 503), `subprocess.Popen` raises for the module
    (nothing probes), and no 404, 422 or 502 carries `ETag` or `Cache-Control`
  - routing: `GET …/media?clip=`, `…/movie`, `…/thumbnail?clip=` and `…/reel` still reach their own routes, and
    `GET /api/v1/events/{id}` still answers the database's 503 on this app
  - auth: an app with an `auth_checker` that counts calls and rejects requests without `X-Test: 1` with 401:
    three requests with it (no `Range`, `bytes=0-9`, `bytes=10-19`) → three calls and 200/206/206; one without it
    → 401 from the checker with none of the file's bytes
  - `tests/test_api_media.py`, `tests/test_api_thumbnails.py` and `tests/test_api_events.py` pass unchanged

- [x] 3.2 Serve a real proxy end to end (`has_ffmpeg`; no `gpu` marker: force the CPU path). Build a
  2 s synthetic clip with audio (`lavfi` testsrc2 and sine) in a tmp event, make its entry with the `proxies`
  package's `ensure_proxy` (CPU path, the gates' own entry point) into a tmp cache, and request the proxy and
  the filmstrip over the app. Verify in `tests/test_api_proxy_media.py`:
  - the proxy response body equals the entry's `proxy.mp4` byte for byte, and `ffprobe` of those bytes (written
    to a tmp file) shows one H.264 stream, one `aac` stream, and a duration within 50 ms of the clip's
  - a `Range: bytes=-1000` request returns the file's last 1000 bytes (the `moov` is up front: `faststart`)
  - the filmstrip body starts with `FF D8` and ends with `FF D9`
  - a 0.48 s synthetic clip gets a proxy 200 and a one-tile filmstrip 200 (the gates' one-tile rule, 1.1)
  - the libfdk guard is not repeated here (it is `proxy-encode`'s test)

## 4. OpenAPI and generated types

- [x] 4.1 Regenerate `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and
  `web/src/api/schema.d.ts` (`npm run generate:types` in `docker.io/library/node:22`). Verify:
  - `tests/test_api_openapi.py` gains both paths in `EXPECTED_PATHS`; `EXPECTED_MODELS` is unchanged. A new case
    asserts, for `/api/v1/events/{event_id}/proxy` and `/filmstrip`, for `get` and for `head`:
    - the response codes are exactly `{"200", "206", "304", "400", "404", "416", "502", "422"}`
    - 200 and 206 have only `video/mp4` (proxy) or `image/jpeg` (filmstrip) content with `format: binary`
    - 206 and 416 publish `Content-Range`; 200 publishes `ETag`, `Last-Modified`, `Cache-Control`,
      `Accept-Ranges`, `Content-Disposition`
    - 404 and 502 reference `ProblemOut`
    - the parameters include a required `clip` and an optional `v` query parameter and optional
      `If-None-Match`, `If-Modified-Since`, `Range`, `If-Range` header parameters
  - `test_committed_schema_is_not_stale` and `test_the_served_schema_is_the_committed_one` pass.
  - In `podman run --rm -v $WT/web:/app:Z -w /app docker.io/library/node:22` (with `TMPDIR` exported, `npm ci`
    first): `npx tsc --noEmit`, `npm test`, and `npm run build` all pass with no client change.
  - `grep -c '"/api/v1/events/{event_id}/proxy"\|"/api/v1/events/{event_id}/filmstrip"' web/src/api/schema.d.ts`
    prints 2, and `grep -n '"video/mp4": string\|"image/jpeg": string' web/src/api/schema.d.ts` finds the
    responses.

## 5. Verification against the dev library, in real browsers

- [x] 5.1 Run the routes for real with slug `proxy-media-endpoints`, port **8307**, database
  `arel_proxy_media_endpoints`, `DEV` and `ENVF` as the brief gives (never 8080, 5173, 8132, 8141–8143 or 5432
  except through the dev container exec; never the database `auto_reel_ng`, `../auto-reel-dev`, or any other
  agent's `wt-*` / `dev-*`). Playwright scripts, screenshots and logs stay in `SCRATCH`; export `TMPDIR`.

  **Setup:** create the database, `alembic upgrade head`, build the dev library at `$DEV` with
  `scripts/make_dev_library.py`, and add `2024/2024-05-19 - Provklipp` holding **symlinks** to the ten samples
  (never copies of the samples, never writes into `auto-reel-media/`), plus a regular-file copy of
  `h264-720p25-aac-msnv.mp4` named `kopia.mp4` (the stale-source case; the only file the script may `touch`),
  plus a 0.48 s clip made with ffmpeg from `lavfi` into a scratch event of the dev library. Set
  `XDG_CACHE_HOME=$TMPDIR/xdg` for the service and for `auto-reel proxies`, run `auto-reel proxies $DEV` (the
  gates' command) so that the entries are real, leave one clip (`h264-1080p50-aac.mp4`) unprepared by passing
  the CLI's per-event or per-clip selection (or delete its entry), `touch <SCRATCH>/marker`, snapshot
  `$TMPDIR/xdg` (paths, sizes, mtimes), and start `serve` on 8307 in the background, recording its PID.

  **curl checks**, each status as stated:
  - proxy of `sony-xavc-1080p25-pcm.mp4`: 200 `video/mp4`; `Range: bytes=0-99` → 206; `Range: bytes=<size>-` →
    416; `If-None-Match` with the `ETag` and a `Range` → 304; `HEAD` has the `GET`'s `ETag`; `v=x` changes
    nothing; the `ETag` differs from `/media`'s for the clip
  - the downloaded proxy passes `ffprobe`: H.264 and `aac`, `faststart` (the `moov` precedes `mdat`)
  - the unprepared `h264-1080p50-aac.mp4` → 404 with a problem body and no `ETag`; its filmstrip → 404
  - the filmstrip of the Sony clip: 200 `image/jpeg`, starts with `FFD8`; the 0.48 s clip: proxy 200, filmstrip 200
  - `kopia.mp4` after `touch -d '+1 hour' kopia.mp4` (a new mtime): proxy 404 although the old entry is still in
    `$TMPDIR/xdg`; after `auto-reel proxies` again: 200 with another `ETag`
  - MISSING / outside / unknown identities → 404; a clip with `chmod 000` on its `proxy.mp4` → 502 with no `failure`
    and no `$TMPDIR` in the body (restore the mode)
  - `GET /api/v1/events` and an event detail still answer without probing (their bodies are unchanged by this
    change)

  **Resources and cost:**
  - download the largest proxy whole while sampling `ps -o rss= -p <pid>` every 50 ms: the peak exceeds the
    pre-download RSS by less than 64 MiB
  - `curl --max-time 0.2` the same URL, then `bytes=0-9` → 206, and `grep -c Traceback` on the serve log is 0
  - lookup cost: 50 sequential `Range: bytes=0-0` requests for a Provklipp proxy (11 clips) and for a clip of a
    400-clip event (hard links as in `media-endpoints`; a scratch script writes a one-byte `proxy.mp4` into
    `$TMPDIR/xdg` at the entry the `proxies` package computes for it). Record p50 and p95 for each in design
    Risks, "One lookup per range request"; a p95 over 50 ms is a finding to report, not to fix here

  **Browsers** (Playwright from `SCRATCH`, same origin `http://127.0.0.1:8307/healthz`, each browser launched
  with autoplay allowed so the audio tap runs):
  - Chrome: `localhost/playback-research:chrome`, `channel="chrome"`, version 154. Firefox:
    `localhost/pcm-audio-research:pw163`, `firefox`; the script prints `browser.version` and fails below 155.
  - For the proxies of `sony-xavc-1080p25-pcm.mp4` and `sony-xavc-4k25-pcm.mp4` in **both** browsers:
    - `loadedmetadata`, `videoWidth` 960 and `videoHeight` 540, a non-black frame read back
      through a canvas
    - 3 s of `play()` with an `AnalyserNode` on `createMediaElementSource`: decoded **peak > 0** (expect about
      0.26 and 0.085, the PCM research's peaks); Firefox `mozHasAudio` true
    - `currentTime` advances by at least 2 s; a seek to 50 % fires `seeked`; ten random seeks have a p90 of at
      most 100 ms to the next presented frame
    - **first frame:** five fresh elements, each `src` assigned and timed with `performance.now()` to the first
      `requestVideoFrameCallback`: median at most 100 ms (record median and max, and the original's for contrast)
  - Control, unchanged behavior: the **original** of the Sony PCM clip from `…/media` in Firefox has
    `mozHasAudio` false and peak 0, and in Chrome peak > 0.
  - The proxies of `hevc-mov-rotate90-aac.mov` and `legacy-render-mpeg4-mp3.mp4` (the originals show black or
    error 4 in browsers) play with a non-black frame in both browsers.
  - A replaced proxy: after loading the Sony proxy with `v=<ETag>`, overwrite its cache `proxy.mp4` with the
    4K25 proxy's bytes (a new mtime), `HEAD` again for the new `ETag`, and load with `v=<new ETag>`: it plays
    and reports the new duration. (Chrome's failure at the old address is D-15's; only the new-`v` path is asserted.)
  - Absent is a failed load, not a silent one: the unprepared clip's proxy URL ends in `MediaError` code 4
    (or a network error), and the page reports it.
  - Filmstrip: an `<img>` of the Sony filmstrip has `naturalWidth` > 0; take one screenshot and LOOK at it
    (tiles in order, not blank, not skewed).
  - Console errors and failed requests other than the intended 404s: none.

  **Database down:** restart `serve` with `DATABASE_URL=postgresql+psycopg://x:x@127.0.0.1:1/x` (never stop the
  shared `auto-reel-ng-dev-db`): the Sony proxy and filmstrip still answer 200 and the unprepared clip 404.

  **No writes:** `find $DEV -newer <SCRATCH>/marker` lists nothing (apart from the files the setup created before
  the marker), nor does `find ../auto-reel-media -newer <SCRATCH>/marker`, and the `$TMPDIR/xdg` snapshot taken
  after the proxies were made is identical to one taken after all the requests (serving created nothing). Stop
  `serve` afterwards and drop the database `arel_proxy_media_endpoints`. Do not touch any container you did not
  start.

## 6. Docs

- [x] 6.1 Update the docs, re-reading each against the spec, and record the measured results from 5.1:
  - `README.md`, API service section beside the clip media entry: `GET`/`HEAD …/proxy?clip=` and
    `…/filmstrip?clip=`: what each serves (the cache entry, unchanged, `video/mp4` with AAC / `image/jpeg`); the
    clip identity encoded as for `media`; `v` ignored and meant to carry the `ETag` (read with `HEAD`); absent is
    a 404 problem and never a 200 or 202; ranges, validators and `HEAD` as the clip route; the cache is read
    only, no database, no ffmpeg, nothing created; 502s by cause; a proxy is for a clip as it is now (a replaced
    clip is absent until `auto-reel proxies` runs again).
  - `docs/high-level-design.md`: §4.9's media-routes paragraph (the two routes, "per-request reads of the cache,
    not fields of the events read model"); D-21's "Serving" row (the routes, 404 not 202, `v` = `ETag`,
    `private, no-cache`, filmstrip independent of the proxy file); D-15's `v` sentence (the proxy routes follow
    the same rule); §4.10's v2 bullet and §6 phase 9 (one sentence: the proxy routes land the serving half of
    D-21, `proxy-media-endpoints`); §8.11 (proxy serving resolved). No new D-n: D-20 and D-21 belong to the
    timeline and proxy-contract changes. Re-read each section on `main` first.
  - `docs/research/browser-playback.md`: a "Proxy playback through the routes" section with 5.1's browser
    versions, the peaks, `mozHasAudio`, first-frame medians, seek p90 and the lookup p50/p95, and the control
    (the original stays silent in Firefox). No absolute scratchpad paths.
  - Verify: `grep -n "/proxy?clip=\|/filmstrip?clip=" README.md` finds both entries;
    `grep -n "proxy-media-endpoints" docs/high-level-design.md` finds §4.9 and §6; `grep -n "RENDER_GRAPH_VERSION"`
    shows no new mention besides the "unchanged" statement; `openspec validate proxy-media-endpoints --strict`
    passes.

## 7. Validation

- [x] 7.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`,
  then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full
  `.venv/bin/python -m pytest` (in the background with a generous timeout, `TMPDIR` exported), including
  `requires_db` and `has_ffmpeg`. Then, in the node:22 container, `npm test`, `npx tsc --noEmit` and
  `npm run build`. Verify:
  - all are clean or green, apart from the known cairo `no-member` noise and the environmental title-card skips
  - `git diff main -- auto_reel_ng/staleness/fingerprint.py` does not touch `RENDER_GRAPH_VERSION`, and
    `git status --short alembic/ auto_reel_ng/proxies/ auto_reel_ng/persistence/ auto_reel_ng/scheduler/`
    is empty
  - `git diff main --stat -- auto_reel_ng` touches only `api/` files
  - no leftover `auto-reel-ng-test-pg-*` container that this run started (report, never remove, one that is not
    yours)
  - `openspec validate proxy-media-endpoints --strict` passes
