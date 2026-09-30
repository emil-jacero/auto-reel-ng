## 1. Gate

- [ ] 1.1 Confirm that `openspec/changes/archive/*-clip-thumbnails` exists on `main`. If it does not, stop and report. Then read what it shipped against this design's "What this change needs from `clip-thumbnails`":
  - `errors.ThumbnailError` and `errors.ThumbnailCacheError`, and that they are siblings under `EngineError`
  - `thumbs.thumbnail_for(clip_path, *, position, cache_dir, runtime=None) -> Path`, cache-first
  - `thumbs.thumbnail_path(clip_path, *, position, cache_dir) -> Path`: the pure cache-path function (stat plus hash, no subprocess, nothing created), whose stat's `OSError` propagates unchanged
  - `thumbs.resolve_thumbnail_settings(config, project_root) -> ThumbnailSettings` (`position`, `cache_dir`), raising `ConfigError`
  - `auto_reel_ng.thumbs` exports `thumbnail_for`, `thumbnail_path`, `resolve_thumbnail_settings` and `ThumbnailSettings`

  If `thumbnail_path` is missing, or raises anything but an `OSError` for a clip that is not there, stop and report: it belongs to the engine change. If a name or signature moved, use the archived one in every task below. Behavior is unchanged whatever they are called.

  Verify:
  - `ls openspec/changes/archive/ | grep clip-thumbnails` prints one directory
  - `.venv/bin/python -c "from auto_reel_ng.errors import ThumbnailError, ThumbnailCacheError; from auto_reel_ng.thumbs import ThumbnailSettings, resolve_thumbnail_settings, thumbnail_for, thumbnail_path; assert not issubclass(ThumbnailCacheError, ThumbnailError)"` succeeds
  - the behaviour: `.venv/bin/python -c "from pathlib import Path; import pytest; from auto_reel_ng.thumbs import thumbnail_path; pytest.raises(FileNotFoundError, thumbnail_path, Path('/nonexistent/clip.mp4'), position=0.25, cache_dir=Path('unused'))"` succeeds: `thumbnail_path` raises the stat's `OSError`, not a `ThumbnailError`
  - `openspec validate clip-thumbnail-endpoint --strict` passes

## 2. api/ — the failure kind, the lookup, the gate

- [ ] 2.1 Add `ThumbnailFailure(StrEnum)` (`THUMBNAIL_FAILED = "thumbnail_failed"`) and `ProblemOut.thumbnail_failure: Optional[ThumbnailFailure] = None` to `api/schemas.py`, and export the enum (design "The failure kind's home"). Verify with a new case in `tests/test_api_openapi.py`:
  - `ProblemOut.thumbnail_failure`'s non-null member references `ThumbnailFailure`
  - its `enum` is exactly `["thumbnail_failed"]`
  - `EventFailure` still has exactly three values
  - `EXPECTED_MODELS` gains `ThumbnailFailure`
- [ ] 2.2 Add `ClipNotFoundError`, the frozen `ThumbnailSource` and `thumbnail_source(settings, event_id, clip)` to `api/events_read.py`, in the design's five-step order ("Which clips have a thumbnail"). Verify with a new `tests/test_api_thumbnails.py`. These tests need no database and no ffmpeg: clips are `_touch`ed, and `thumbnail_path` needs only a stat. The project is `tmp_path / "proj"` and its `config.yaml` sets `thumbnails.cache_dir` to `tmp_path / "cache"`: `clip-thumbnails` refuses a cache inside the project root. Cases:
  - a root clip and `Kvällen/s1710002.mp4` resolve. `etag` is the quoted cache-path stem, and `cache_path` lies under `tmp_path / "cache"`
  - an IGNORED clip resolves
  - the identity `Kväll, del 2/a+b & c #1.mp4` resolves
  - each of these raises `ClipNotFoundError`: a referenced-but-absent `borttagen.mp4`, `original/x.mp4`, `Original/x.mp4`, a clip in a chapter folder holding `.reelignore`, a dangling symlink, `Kvällen/../s1710001.mp4`, `../other/x.mp4`, an absolute path, and `""`
  - an unknown event raises `EventNotFoundError`
  - an event folder with mode `000` (restored in `finally`; skipped as root) raises `EventReadError` with `failure is EventFailure.UNREADABLE_DISK`
  - an out-of-range `thumbnails.position` raises `ConfigError`, while a MISSING clip in the same project still raises `ClipNotFoundError`
  - a real vanished clip: `events_read.scan_event` is wrapped to call the real one, then delete one listed clip before returning its listing. `thumbnail_source` raises `ThumbnailError` whose message starts with that clip's path and contains `cannot stat the clip`, with `__cause__` a `FileNotFoundError`
  - an unparseable `reel.yaml` in the event does not stop a clip from resolving
- [ ] 2.3 Add `api/thumbnails.py` with `MAX_CONCURRENT_EXTRACTIONS = 2` and `ThumbnailGate`, as the design sketches it ("Bounded, shared extraction": `asyncio.wait`, not `asyncio.shield`). Verify with `async def` tests in `tests/test_api_thumbnails.py` (`asyncio_mode = "auto"`). They use a blocking fake `extract` that records concurrency under a lock and is released by a `threading.Event`:
  - 6 distinct keys: the observed maximum is exactly 2 and all six return
  - 5 waiters on one key: `extract` is called once and all five get the same path
  - a failing `extract` raises the same exception to every waiter, and the next `produce` for that key calls `extract` again
  - cancelling the first waiter does not cancel the extraction, and a second waiter still gets the path
  - an extraction whose only waiter was cancelled, and which then fails, logs nothing at `ERROR` (`caplog`)
  - the in-flight map is empty after every case

## 3. api/ — the route and its contract

- [ ] 3.1 Build the gate in `create_app` (`app.state.thumbnail_gate`). Add the `async` route `GET /events/{event_id:path}/thumbnail` in `routes/events.py`, directly after `/reel` and before the detail route, with the required `clip` and the optional, ignored `v` (design "The route"), the status mapping of the design ("Status by cause") and its WARNING log on every 502. Blocking work goes through `run_in_threadpool`. The success path serves the cached file or extracts through the gate, with `Content-Type: image/jpeg`.

  Verify in `tests/test_api_thumbnails.py`. The app is built on an unreachable database URL (`127.0.0.1:1`, as the schema dump uses), one app per test. `thumbnail_for` is monkeypatched, under the name the route module looks up, to a fake that counts calls, records its `runtime` argument, and writes a fixed small JPEG to the real `thumbnail_path(...)` of its arguments, so the next request finds it:
  - 200 `image/jpeg`, and a second request makes no new call and returns an identical body
  - the same clip with `v=2024-06-27T14:03:11.123456Z` and then `v=other` answers 200 with the same bytes and the same `ETag` both times, and the fake is called at most once
  - the recorded `runtime` is `app.state.runtime`
  - `Kvällen/s1710002.mp4` and `Kväll, del 2/a+b & c #1.mp4`, each encoded with `urllib.parse.quote(identity, safe="")`, answer 200. The second one sent with a literal `+` answers 404
  - 404 with `event_id` for a MISSING clip and for an unknown event, and 422 when `clip` is missing
  - a fake raising `ThumbnailError`, and the vanished clip of 2.2, each give 502 with `thumbnail_failure == "thumbnail_failed"` and no `failure`
  - a fake raising `ThumbnailCacheError` gives 502 whose detail names the cache directory, with neither kind
  - an unlistable event folder gives 502 with `failure == "unreadable_disk"`
  - a bad `thumbnails.position` gives 502 with neither kind
  - `GET /api/v1/events/{event_id}` for the same event still reaches its own route (the database's 503 on this app), and `/reel` answers 200: the registration order holds
  - `tests/test_api_events.py` passes unchanged
- [ ] 3.2 Add the validators and caching headers of the design ("Validators and caching headers") to the route. Verify with the 3.1 fixture:
  - a 200 carries `ETag` (the quoted cache-path stem) and `Cache-Control: private, max-age=86400`
  - on a miss, the `ETag` is the stem of the path `thumbnail_for` returned: a fake that writes and returns a different `<key>.jpg` than `thumbnail_path` computed (a clip changed mid-request) gives that path's stem
  - `If-None-Match` with the tag, with `W/` plus the tag, and with a list containing it gives 304 with the same two headers and an empty body. No `thumbnail_for` call is made, even with the cache directory emptied first
  - a non-matching tag gives 200
  - `If-None-Match: *` gives 304 only when the JPEG is cached, and 200 (one call) otherwise
  - no problem response (404, 422, 502) carries `Cache-Control` or `ETag`
- [ ] 3.3 Add a test marked `has_ffmpeg` that runs the real engine through the route, using the `runtime` and `make_clip` fixtures. Create the event folder `tmp_path/"proj"/2024/2024-06-27 - Grillning med grannar/` first, because `make_clip` writes to `tmp_path / name` and ffmpeg creates no folders. In it go a 640×360 clip, a 360×640 portrait clip, both 1 s long, and a zero-byte `trasig.mp4`. `config.yaml` points `thumbnails.cache_dir` at `tmp_path / "cache"`. Make the whole project tree read-only (`chmod -R a-w`, restored in `finally`; skipped as root). Verify:
  - both bodies start with the JPEG marker `FF D8`
  - ffprobe on the cached files reports 320×180 and 101×180
  - a snapshot of every path, size and `st_mtime_ns` under the project is unchanged afterwards
  - `trasig.mp4` answers 502 `thumbnail_failed` with a detail naming it, and the cache directory then holds exactly the two JPEGs and no temporary file
- [ ] 3.4 Declare `response_class=Response` and `responses=` on the route:
  - 200: `image/jpeg` (`{"type": "string", "format": "binary"}`), with the `ETag` and `Cache-Control` headers
  - 304: those two headers
  - 404 and 502: `ProblemOut`

  Regenerate `web/openapi.json` and `web/src/api/schema.d.ts` with the `web/README.md` commands. Verify:
  - a new `tests/test_api_openapi.py` case asserts:
    - the path `/api/v1/events/{event_id}/thumbnail`, added to `EXPECTED_PATHS`
    - a required `clip` query parameter, and an optional string query parameter `v`
    - exactly the codes `{"200", "304", "404", "502"}` besides `422`
    - `image/jpeg` as the 200's only content type
    - both headers on the 200 and the 304
  - the schema staleness test passes
  - `npx tsc --noEmit` passes in the node:22 container with no client change
  - `grep` finds `thumbnail_failed` and `/thumbnail` in `web/src/api/schema.d.ts`, and the route's query type there has `clip` and an optional `v`

## 4. Docs and verification against the dev library

- [ ] 4.1 Document the endpoint and verify it against a real library.

  Docs:
  - a `GET /api/v1/events/{event_id}/thumbnail?clip=` entry in `README.md`'s API service section. It covers:
    - what it serves, and the query parameters: `clip`, percent-encoded as a query value, and the optional, ignored cache-busting `v`
    - the validators and `Cache-Control`
    - the statuses by cause
    - the bound of 2
    - no database
    - the cache outside the library
    - no timeout on a hung extraction: restart `serve`
  - one sentence in HLD §4.9: the thumbnail route is a per-clip media read on request, not a field of the events read model, so the read model stays probe-free and gains no field

  Verify by rereading both against the spec.

  Then run against a real library. Use the runbook's slug `clip-thumbnail-endpoint` (dev-env-runbook §9) and port **8110** (never 8080; 8109 is `clip-thumbnails`' and 8111 `clip-thumbnails-screen`'s):
  - build the dev library at `$AR/dev-clip-thumbnail-endpoint` with `scripts/make_dev_library.py`, using your own `DATABASE_URL`
  - add `library/config.yaml` with `thumbnails.cache_dir` pointing into the scratchpad
  - the dev library's symlinks resolve to only five clip files, so add two events of **hard links**, which give distinct cache keys and use no extra disk:
    - `2024/2024-09-18 - Tolv`: `t01.mp4`…`t12.mp4`, cycling through `clips/s1710001.mp4`…`s1710004.mp4`
    - `2024/2024-09-19 - Fyrahundra`: `f001.mp4`…`f400.mp4`, the same way
  - `touch <scratch>/marker`
  - start `serve` in the background and record its PID

  With `curl`:
  - Grillning `s1710001.mp4`: 200, then 304 with `If-None-Match`
  - Två kapitel `Kvällen/s1710002.mp4`, URL-encoded: 200
  - Sommarlov `borttagen.mp4`: 404
  - Trasig `trasig.mp4`: 502 `thumbnail_failed`
  - the twelve `Tolv` clips, requested in parallel on a cold cache, all answer 200. Meanwhile `pgrep -c -P <serve pid> -x 'ffmpeg|ffprobe'`, sampled every 50 ms, never exceeds 2. Children of `serve` only, because other agents' workers run ffmpeg on this host
  - restart `serve` with `DATABASE_URL=postgresql+psycopg://x:x@127.0.0.1:1/x`. Never stop the shared `auto-reel-ng-dev-db` container. Grillning still answers 200
  - `find $AR/dev-clip-thumbnail-endpoint/library -newer <scratch>/marker` lists nothing

  Then pre-fill the cache with `auto-reel thumbs <library>`. Request all 400 `Fyrahundra` thumbnails, six at a time. Record the per-request p50 and p95 and the total for the Risks note on event listings.

## 5. Validation

- [ ] 5.1 Run `.venv/bin/python -m black auto_reel_ng tests && .venv/bin/python -m isort auto_reel_ng tests`, then `.venv/bin/python -m mypy auto_reel_ng`, `.venv/bin/python -m pylint auto_reel_ng` and the full `.venv/bin/python -m pytest`, including `has_ffmpeg` and `requires_db`. Verify:
  - all are clean or green, apart from the known cairo `no-member` noise and the environmental title-card skips
  - `RENDER_GRAPH_VERSION` is unchanged and `git status --short alembic/` is empty
  - `openspec validate clip-thumbnail-endpoint --strict` passes
