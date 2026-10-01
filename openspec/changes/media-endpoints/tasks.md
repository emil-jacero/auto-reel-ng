## 1. Baseline

- [ ] 1.1 This change has no gate. Confirm that the facts the design builds on still hold on your `main`, and
  stop and report any that do not.
  - **Starlette** still uses `setdefault` for the `etag` header, opens the file after `http.response.start`,
    and answers 416 and 400 as `PlainTextResponse`: `grep -n 'setdefault("etag"\|anyio.open_file\|status_code=416\|status_code=400' "$(.venv/bin/python -c 'import starlette.responses as r; print(r.__file__)')"`
    prints each line, and `.venv/bin/python -c "import starlette; print(starlette.__version__)"` prints
    `1.3.1`.
  - **The gate's renamed-output predicate** is still inline in `_absent_output_reason`:
    `grep -n "def _absent_output_reason\|_NOT_A_FILE_NAME\|recorded_output_path" auto_reel_ng/staleness/gate.py`.
  - **`thumbnail_source`** still starts with `listed_event_dir`, `scan_event` and the exact
    `clip not in listing.identities` check: `grep -n "listed_event_dir(settings, event_id)\|clip not in listing.identities" auto_reel_ng/api/events_read.py`.
  - **The samples are there:** `ls ../auto-reel-media/samples/` lists the ten files the design names
    (`sony-xavc-1080p25-pcm.mp4` … `legacy-render-mpeg4-mp3.mp4`).
  - **`cross-chapter-drag`:** `ls openspec/changes/ openspec/changes/archive/ | grep cross-chapter-drag` tells
    whether it has archived. Note the answer for task 5.2.
  - `openspec validate media-endpoints --strict` passes.

## 2. staleness/ — the movie the gate counts

- [ ] 2.1 Add `rendered_output(event_dir, output_path) -> Optional[Path]` and `_renamed_output(manifest, expected)` to
  `staleness/gate.py`, as design "Which file is the movie" sketches them. Rewrite `_absent_output_reason` on top of
  `_renamed_output`, and export `rendered_output` from `auto_reel_ng/staleness/__init__.py` (`__all__` included).
  Verify:
  - every existing test in `tests/test_staleness_gate.py` passes unchanged
  - new tests in `tests/test_staleness_gate.py`, built with the file's `_render_named` / `_evaluate_named`
    helpers, cover:
    - no manifest but a file at the expected path → `None`, and the verdict cites `no_manifest`
    - manifest and expected file → the expected path
    - retitled after a render (the old movie kept) → the recorded path under its old name, and the verdict
      cites `output_renamed`
    - retitled with the old movie deleted → `None`, and the verdict cites `output`
    - each recorded value of `test_a_recorded_value_that_is_not_a_bare_movie_file_cites_output` and
      `test_a_recorded_value_naming_a_folder_is_never_looked_up` (`""`, `.`, `..`, `2024`, an absolute path,
      `../Grillning.mp4`) → `None`
  - one parametrized test asserts, for every case above,
    `(rendered_output(...) is not None) == not ({NO_MANIFEST, OUTPUT} & set(verdict.reasons))`
  - a separate test pins the accepted edge: a directory at the expected path gives `None` while the verdict
    cites neither `output` nor `output_renamed`
  - `.venv/bin/python -m pytest tests/test_staleness_gate.py tests/test_staleness_manifest.py tests/test_cli_render_staleness.py` is green

## 3. api/ — which file is served

- [ ] 3.1 Move `thumbnail_source`'s first three steps into `events_read.listed_clip(settings, event_id, clip) -> Path`,
  and have `thumbnail_source` call it. Add `api/media.py` with:
  - `MEDIA_TYPES` (the design's table)
  - the frozen `MediaFile` (`name`, `media_type`, `etag`)
  - `MediaGoneError` and `MediaReadError` (fields `label`, `reason`; `str()` is `<label>: cannot read the file:
    <reason>`, path-free; the route adds the `event_id`)
  - `open_media(path, *, label)` (stat → `S_ISREG` → open and close, design "Streaming")
  - `clip_media(settings, event_id, clip) -> MediaFile`

  Verify:
  - `tests/test_api_thumbnails.py` passes unchanged
  - a new `tests/test_api_media.py` holds a `project` fixture shaped like the thumbnail tests' (Grillning, Kalas,
    Tjörn with `Kvällen/` and an IGNORED root clip, Sommarlov with MISSING `borttagen.mp4`, `Kväll, del 2/a+b & c #1.mp4`,
    `original/x.mp4`, a `.reelignore`d event, an unparseable `reel.yaml`). Its clips are plain files of distinct,
    known bytes (for example 300 KiB of a repeating counter, so byte ranges can be compared exactly), plus a
    `CLIP.MP4`, a `.mov`, a zero-byte `trasig.mp4` and a symlink to a file outside the project. Cases:
    - `set(MEDIA_TYPES) == VIDEO_EXTENSIONS`, and every value starts with `video/`
    - a root clip, `Kvällen/s1710002.mp4`, the IGNORED clip, the punctuated identity and the symlink resolve. The
      symlink's `MediaFile.stat` is the target's (`st_size`, `st_mtime_ns`), and `etag` is
      `'"%x-%x"' % (size, mtime_ns)`
    - `CLIP.MP4` → `video/mp4`, and `.mov` → `video/quicktime`
    - each of `borttagen.mp4`, `original/x.mp4`, `Kvällen/../s1710001.mp4`, `../2024-07-14 - Kalas/s1710001.mp4`,
      an absolute path and `""` raises `ClipNotFoundError`; an unknown event and the year folder raise
      `EventNotFoundError`
    - an unlistable event folder (mode `000`, restored in `finally`, skipped as root) raises `EventReadError` with
      `UNREADABLE_DISK`
    - a clip of the event with the unparseable `reel.yaml` resolves
    - `open_media` raises:
      - `MediaGoneError` for a dangling path and for a directory
      - `MediaReadError` for a clip with mode `000` (skipped as root). Its `str()` contains the identity and
        `Permission denied` and does not contain `str(tmp_path)`.
    - a clip deleted after the listing (wrap `events_read.scan_event` to delete it before returning, as
      `_vanish_after_listing` does in the thumbnail tests) raises `MediaGoneError`

- [ ] 3.2 Add `MovieNotFoundError` and `movie_media(settings, event_id) -> MediaFile` to `api/media.py`, with the
  design's six steps ("Which file is the movie"): listed event, metadata via `load_event_document` +
  `require_processable`, the expected path from `settings.output_dir`, `rendered_output`, lexical containment
  under the output directory (`os.path.abspath`, never `resolve()`), `open_media`. Verify in
  `tests/test_api_media.py` with an output directory `tmp_path / "proj-output"` and version-1 manifests written as JSON (every `COMPONENTS` key, any strings, the
  `output` under test):
  - Kalas, manifest `2024-07-14 - Kalas.mp4` with that file in `proj-output/2024/` → that file
  - Grillning, its `reel.yaml` retitled after a manifest recorded `2024-06-27 - Grillning med grannar.mp4`, which
    is still on disk → the old file
  - a second event `2024/2024-07-14 - kalas` with no manifest, whose expected path is Kalas's file →
    `MovieNotFoundError`
  - a directory at Kalas's expected path (its manifest kept, its file moved aside) → `MovieNotFoundError`, and
    nothing under the directory is opened
  - a manifest whose file was deleted, and manifests recording `../x.mp4`, `str(tmp_path / "x.mp4")` and `""`,
    with a real file at each such place under `tmp_path` → `MovieNotFoundError`
  - containment: an event `2024/2024-07-15 - Utbrytning` with a manifest and the title `x/../../../outside` in
    its `reel.yaml`. Create the folder `proj-output/2024/2024-07-15 - x/` so the OS resolves the `..` segments,
    and the file `tmp_path / "outside.mp4"`. Assert that `rendered_output` returns a path for it, which proves
    the guard and not the gate refuses it, and that `movie_media` raises `MovieNotFoundError`
  - links are followed: settings whose output directory `proj-output-2/` holds `2024` as a symbolic link to
    `tmp_path / "other-disk/2024"`, where Kalas's movie lies → that file, as
    `rendered_output` also returns it
  - the unparseable `reel.yaml` → `EventReadError` with `UNPARSEABLE_REEL_YAML`
  - a folder `2024/2024-02-30 - Omöjligt datum` → `EventReadError` with `UNUSABLE_METADATA` and the detail the
    event detail gives
  - an unknown event and the year folder → `EventNotFoundError`
  - a movie with mode `000` (skipped as root) → `MediaReadError` naming the movie's file name, not its path
  - nothing under `tmp_path` changes: a snapshot of every path, size and `st_mtime_ns` taken before and after
    the cases is equal

## 4. api/ — responses, routes, schema

- [ ] 4.1 Add `etag_matches(header, etag)` (weak comparison over a comma-separated list), `MEDIA_CACHE_CONTROL`
  and `media_response(media, if_none_match)` to `api/media.py` (design "Validators and caching"). Make the
  thumbnail route's `_revalidated` use `etag_matches` for its tag test and keep its own `*` rule. Then add
  `api/routes/media.py` with `get_clip_media` and `get_movie` (sync `def`, the declared `v`,
  `If-None-Match`, `Range` and `If-Range` parameters, `If-None-Match` read with `request.headers.getlist`). Map
  the status by cause per the design table, with a WARNING log on every 502, and include the router in
  `app.py` **before** `events_router`, with a comment. Verify:
  - Unit tests in `tests/test_api_media.py` for the helper:
    - `media_response(m, None)` is a `starlette.responses.FileResponse` whose `stat_result is m.stat`, whose
      `ETag`, `Cache-Control` and `Content-Type` headers are the media file's, and whose `Content-Disposition`
      starts with `inline`. The type check is the "never in memory" guard, because the test client buffers
      bodies (design Context).
    - a 304 `Response` with exactly `ETag` and `Cache-Control` for the exact tag, for `W/` plus the tag, for a
      list containing it, and for `*`
    - a `FileResponse` for a non-matching tag
  - `tests/test_api_thumbnails.py` passes unchanged.
  - The HTTP cases below go in `tests/test_api_media.py`. Each test builds its own app on
    `UNREACHABLE_DATABASE_URL`, as the thumbnail tests build theirs.
  - Ranges and validators, on a clip:
    - no `Range` → 200 with the whole bytes
    - `bytes=0-99`, `bytes=1000-` and `bytes=-500` → 206 with exactly those bytes and `Content-Range`
    - `bytes=<size>-` → 416 with `Content-Range: bytes */<size>`
    - `lines=0-1`, `bytes=abc` and `bytes=5-3` → 400 `text/plain`
    - `bytes=-<size + 5>` and `bytes=0-<size * 10>` → 206 with the whole file; `bytes=-0` → 416
    - the ranges browsers never send, pinned as Starlette 1.3.1 answers them (design Risks): `bytes=0-0,2-2` →
      206 `multipart/byteranges` holding bytes 0 and 2, and `bytes=5-4` → 206 with an empty body and
      `Content-Range: bytes 5-4/<size>` (accepted as Starlette's answer, supervisor decision)
    - `If-Range` with the current `ETag` → 206, and with `"old"` → 200
    - `If-None-Match` with the tag (alone, with `Range`, and on two header lines) → 304 with an empty body
    - a replaced file (new bytes and size, `os.utime` forward) with the old tag → 200 and a new `ETag`
    - `v=a` and `v=b` → identical bodies and `ETag`
  - Headers on every 200 and 206: `Content-Type` per extension, `Accept-Ranges: bytes`, `Last-Modified`, the
    `ETag` format, `Cache-Control: private, no-cache`, and `Content-Disposition` equal to
    `inline; filename*=utf-8''a%2Bb%20%26%20c%20%231.mp4` for the punctuated clip.
  - Lookups:
    - the punctuated identity sent with `urllib.parse.quote(identity, safe="")` → 200, and sent with a literal
      `+` → 404
    - the zero-byte clip → 200 with an empty body, and with `bytes=0-` → 416 `bytes */0`
    - 404 problems with `event_id` for: MISSING, outside, normalizing, `original/`, the year folder, an unknown
      event, and the vanished clip
    - 422 without `clip`
    - mode `000` → 502 with no `failure` and no `thumbnail_failure`, its detail free of `str(tmp_path)`, and
      the WARNING logged (`caplog`)
    - an unlistable folder → 502 `failure: unreadable_disk`
  - Movie, over HTTP:
    - Kalas → 200 with its bytes and `Content-Disposition` naming `2024-07-14 - Kalas.mp4`
    - Grillning renamed → 200 with the old file
    - kalas → 404
    - a directory at Kalas's expected path → 404 with a problem body
    - the title `x/../../../outside` (task 3.2's fixture) → 404, and the 404's body holds none of
      `outside.mp4`'s bytes
    - Omöjligt datum → 502 `failure: unusable_metadata`
    - the unparseable `reel.yaml` → 502 `failure: unparseable_reel_yaml`
    - a 304 on the movie with `If-None-Match` and `Range`
  - No 404, 422 or 502 carries `ETag` or `Cache-Control`.
  - Routing: `GET …/reel` answers 200, `GET …/thumbnail?clip=` reaches its own route (any status but the detail
    route's 503), and `GET /api/v1/events/{id}` still answers the database's 503 on this app.
  - Auth: an app built with an `auth_checker` that counts calls and rejects requests lacking the header
    `X-Test: 1` with 401. Three requests with `X-Test: 1` (no `Range`, `bytes=0-9`, `bytes=10-19`) → three calls
    and 200/206/206. One without it → 401 from the checker, with no file bytes in the body.
  - `tests/test_api_events.py` and `tests/test_api_thumbnails.py` pass unchanged.

- [ ] 4.2 Declare `response_class=Response` and the design's `MEDIA_RESPONSES` on both routes. Regenerate
  `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and
  `web/src/api/schema.d.ts` (`npm run generate:types` in `docker.io/library/node:22`). Verify:
  - `tests/test_api_openapi.py` gains both paths in `EXPECTED_PATHS`. `EXPECTED_MODELS` is unchanged: no new
    component.
  - A new case asserts, for `/api/v1/events/{event_id}/media` and `/movie`:
    - the response codes are exactly `{"200", "206", "304", "400", "404", "416", "502", "422"}`
    - 200 and 206 have only `video/*` content, with `format: binary`
    - 206 and 416 publish `Content-Range`
    - 200 publishes `ETag`, `Last-Modified`, `Cache-Control`, `Accept-Ranges` and `Content-Disposition`
    - 404 and 502 reference `ProblemOut`
    - the parameters include an optional `v` query parameter (plus a required `clip` on `/media`) and
      optional `If-None-Match`, `Range` and `If-Range` header parameters
  - `test_committed_schema_is_not_stale` and `test_the_served_schema_is_the_committed_one` pass.
  - `podman run --rm -v $PWD/web:/app:Z -w /app docker.io/library/node:22 npx tsc --noEmit` passes with no
    client change.
  - `grep -c '"/api/v1/events/{event_id}/media"\|"/api/v1/events/{event_id}/movie"' web/src/api/schema.d.ts`
    prints 2, and `grep -n '"video/\*": string' web/src/api/schema.d.ts` finds the four responses.

## 5. Docs

- [ ] 5.1 Write `docs/research/browser-playback.md` from R0. Use the session scratchpad's `research/playback.md`
  when it is there, else design "R0 and the spike". It covers:
  - the archive survey table
  - the ten samples and what each covers
  - the browser matrix
  - the silent failure modes (`videoWidth === 0`, `mozHasAudio`)
  - the rendered movie's facts (H.264 High, AAC, `faststart`, real chapters that `<video>` does not expose)
  - Starlette's Range behavior
  - auth for media elements
  - the `preload` request counts
  - this change's spike results
  - the replaced-file behaviour in Chrome (the same URL fails, even in a new element; a new `v` plays), from
    `movie-player-screen`'s spike
  - the Chrome-channel Playwright image (`FROM mcr.microsoft.com/playwright/python:v1.49.0-noble`, `RUN pip
    install -q playwright==1.49.0 && python -m playwright install chrome`, tagged
    `localhost/playback-research:chrome`), which every playback check uses, or Firefox; never the stock Chromium

  It is not a copy of the scratchpad, and no absolute scratchpad paths appear in it.

  Then add the two routes to `README.md`'s API service section, next to the thumbnail entry, covering:
  - what each serves; the movie being the file the gate counts, so an un-adopted legacy movie is not served
    until `auto-reel adopt-renders` records it, and a directory at the movie's path is answered 404
  - `clip` encoding and the ignored `v`
  - ranges and the 416/400 plain-text answers
  - the validators, `Cache-Control: private, no-cache` and the 304
  - statuses by cause
  - no database, no ffmpeg, no writes, files served unchanged: PCM audio is silent in Firefox

  Verify by rereading both against the spec, and `grep -n "media?clip=\|/movie" README.md` finds both entries.

- [ ] 5.2 Edit `docs/high-level-design.md` as design "HLD: the roadmap edit and the media routes" lists:
  - §4.9's media-routes paragraph
  - §4.10's v2 and v3 lines and the dated roadmap sentence, with the media-endpoints prerequisite
  - §6 phases 9–10
  - D-8's "Why React" v3 wording
  - the §4.10 research note
  - D-11's and D-14's "stay v3" sentences
  - §8.11

  Before editing §4.10, re-read its current text on `main`.
  - If `cross-chapter-drag` has archived (task 1.1), its v1 bullet, v3-line and slice-row-D edits are
    already there. Keep them, and only move what is left of the v3 line to v2.
  - If it has not, do not carry "drag across chapters" into v2: `cross-chapter-drag` moves it to v1 when it
    lands, and edits the v3 line that this task replaces. Leave D-13's "Dragging across chapters stays v3."
    to that change.

  Verify:
  - `grep -n "media-endpoints" docs/high-level-design.md` finds §4.9 and §4.10
  - `grep -n "v3" docs/high-level-design.md` shows no line that still places the timeline editor, proxies,
    scrubbing, previews or drag-trim in v3 (D-13's cross-chapter sentence excepted until `cross-chapter-drag`
    lands)
  - `grep -n "PCM" docs/high-level-design.md` finds §8.11
  - no `D-15` or `D-16` is added

## 6. Verification against the dev library

- [ ] 6.1 Run the routes for real (runbook §9, with slug `media-endpoints` and port **8129**; never 8080 or 5173,
  never the default database `auto_reel_ng`, never `../auto-reel-dev`). There is no screen here: viewport,
  theme, keyboard and axe checks belong to `movie-player-screen` and `clip-preview-screen`.

  **Setup:**
  - Create the database `arel_media_endpoints`, run `alembic upgrade head`, and build the dev library at
    `$AR/dev-media-endpoints` with `scripts/make_dev_library.py`, `DATABASE_URL` exported.
  - Add the samples event by **symlinks**, never copies or moves:
    - `library/2024/2024-05-19 - Provklipp/<name>` → `../auto-reel-media/samples/<name>` for each of the ten
      samples
    - `library/2024/2024-05-19 - Provklipp/Kväll, del 2/a+b & c #1.mp4` →
      `samples/h264-720p25-aac-msnv.mp4`
  - Add `2024/2024-09-19 - Fyrahundra`: `f001.mp4`…`f400.mp4`, hard links cycling through `clips/s1710001.mp4`…
    `s1710004.mp4`.
  - `touch <scratch>/marker`, start `serve` on 8129 in the background, and record its PID.

  **curl checks**, each status as stated:
  - Provklipp:
    - `sony-xavc-1080p25-pcm.mp4` with `Range: bytes=152000000-` → 206 and the tail
    - `hevc-mov-rotate90-aac.mov` → `video/quicktime`
    - the punctuated chapter clip, encoded → 200
    - a past-the-end range → 416
    - `If-None-Match` with the tag and a `Range` → 304
  - Sommarlov `borttagen.mp4` → 404; Trasig `trasig.mp4` → 200 empty, and `bytes=0-` → 416
  - `/movie` for each event of `GET /api/v1/events`. A scratch script asserts 200 exactly where the row's
    `staleness.reasons` contain neither `no_manifest` nor `output` (Midsommar ×2, Grillning, Kalas, Badutflykt,
    Två kapitel), and 404 for the others, kalas included. The error row Omöjligt datum → 502
    `unusable_metadata`.
  - Grillning's movie carries the old name in `Content-Disposition`.

  **Resources:**
  - Download `h264-4k50-aac-119mbps.mp4` whole while sampling `ps -o rss= -p <pid>` every 50 ms. The peak exceeds
    the pre-download RSS by less than 64 MiB.
  - `curl --max-time 0.2` the same URL, then a `bytes=0-9` request → 206, and `grep -c Traceback` on the serve log
    is 0.
  - Lookup cost: 50 sequential `Range: bytes=0-0` requests for `Fyrahundra/f400.mp4` and for Provklipp's
    `h264-1080p25-aac.mp4`. Record each p50 and p95 under design Risks, "One lookup per range request".

  **Chrome:** run Playwright in `mcr.microsoft.com/playwright/python:v1.49.0-noble` with `--network host`, `pip
  install playwright==1.49.0 && python -m playwright install chrome`, `channel="chrome"`. The script and
  output stay in the scratchpad. On a page of the same origin (`http://127.0.0.1:8129/healthz`), a `<video
  preload="metadata" muted>` per URL:
  - Provklipp's Sony PCM clip, `h264-4k50-aac-119mbps.mp4`, `h264-portrait-1080x1920-aac.mp4`,
    `h264-720p-rotate90-aac.mp4`, the punctuated clip, Grillning's movie and Kalas's movie each reach
    `loadedmetadata`:
    - `duration` within 0.1 s of `ffprobe -show_entries format=duration`
    - the rotate clip reports `videoWidth` 720 and `videoHeight` 1280
    - seeking to 50 % fires `seeked`
    - 2 s of `play()` advance `currentTime` by at least 1 s
  - Sommarlov's movie and Trasig's clip end in `MediaError` code 4.
  - Loading Kalas's movie a second time puts at least one `304` for `/movie` in the serve log.

  **Database down:** restart `serve` with `DATABASE_URL=postgresql+psycopg://x:x@127.0.0.1:1/x` (never stop the
  shared `auto-reel-ng-dev-db` container). A Grillning clip and Kalas's movie still answer 200.

  **No writes:**
  - `find $AR/dev-media-endpoints -newer <scratch>/marker` lists nothing, and nor does
    `find ../auto-reel-media -newer <scratch>/marker`.
  - Stop `serve` afterwards.

## 7. Validation

- [ ] 7.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then
  `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full
  `.venv/bin/python -m pytest`, including `requires_db` and `has_ffmpeg`. Verify:
  - all are clean or green, apart from the known cairo `no-member` noise and the environmental title-card skips
  - `git diff main -- auto_reel_ng/staleness/fingerprint.py` does not touch `RENDER_GRAPH_VERSION`
  - `git status --short alembic/` is empty
  - `openspec validate media-endpoints --strict` passes
