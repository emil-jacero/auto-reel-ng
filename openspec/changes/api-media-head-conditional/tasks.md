## 1. api/ — conditional evaluation

- [ ] 1.1 In `api/media.py`, give `media_response` an `if_modified_since: Optional[str] = None` parameter: with
  `If-None-Match` absent, parse the value (`email.utils.parsedate_to_datetime`, naive read as UTC, unparseable
  ignored) and return the same 304 as the tag match when `int(stat.st_mtime) <= int(date.timestamp())`; with
  `If-None-Match` present, never look at the date. Verify in `tests/test_api_media.py` (unit, on a `MediaFile`):
  the file's own `Last-Modified` string and a 2099 date give 304 with exactly `etag` and `cache-control`; a date
  one second before the truncated mtime gives a `FileResponse`; `yesterday` and an empty string give a
  `FileResponse`; a mismatching tag with a 2099 date gives a `FileResponse`; a matching tag with an old date
  gives 304; a date in the zone-less RFC 850 form parses.
- [ ] 1.2 In `api/routes/media.py`, add the optional `If-Modified-Since` header parameter to both routes and pass
  the value to `media_response` only when `request.headers.getlist("if-modified-since")` has exactly one line;
  update the docstrings. Verify over HTTP in `tests/test_api_media.py`: the clip and the movie answer 304 with
  no body to the earlier response's `Last-Modified` and to 2099 (also with `Range: bytes=0-`), 200 to a date a
  day before the file's mtime (set with `os.utime`), 200 to `If-Modified-Since: yesterday`, and 200 to two
  `If-Modified-Since` lines.

## 2. api/ — HEAD

- [ ] 2.1 Register both media routes for `HEAD` by stacking `@router.head(...)` over the existing
  `@router.get(...)` with the same `response_class` and `MEDIA_RESPONSES` (not `api_route` with two methods:
  duplicate `operationId`, design D1). Verify with `tests/test_api_media.py` over HTTP: `HEAD` of the clip and the
  movie is 200 with `Content-Length` equal to the size, the `GET`'s `ETag`, `Last-Modified`, `Content-Type`,
  `Cache-Control` and `Accept-Ranges`, and no body; `HEAD` with `Range: bytes=0-99` is 206 with
  `Content-Range` and `Content-Length: 100`; with the matching `ETag` it is 304.
- [ ] 2.2 Verify `HEAD` fails as `GET` fails, in `tests/test_api_media.py`: unknown event 404, MISSING clip 404,
  never-rendered movie 404, a directory at the movie path 404, an unreadable clip 502 (skip as the existing test
  does for root), a malformed `Range` 400 and `bytes=<N>-` 416, each with the `GET`'s status, no body, and no
  `ETag` or `Cache-Control` on the problem statuses; and `HEAD` passes the authentication hook (the existing
  hook-scenario fixture counts a `HEAD`).
- [ ] 2.3 Verify `HEAD` with the built client mounted in `tests/test_api_media.py`: point `web_dist_dir` (monkeypatch)
  at a temp directory holding an `index.html`, build the app, and assert `HEAD` of the media and movie URLs is 200
  with the file's `Content-Length`, not 404; and without a dist it is 200 as well, never 405.

## 3. api/ — schema

- [ ] 3.1 Add `If-Modified-Since` to the published header parameters and make `head` operations appear for both
  paths. Update `test_the_media_routes_publish_their_parameters_and_responses` in `tests/test_api_openapi.py` to
  assert, for the `get` and the `head` operation of each path, the four optional headers, the same response
  codes and headers, and that the two operations have distinct `operationId`s; assert the build raises no
  duplicate-operation-id warning (`pytest.warns` inverse, `warnings.simplefilter("error")`).
- [ ] 3.2 Regenerate `web/openapi.json` (`.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json`) and
  `web/src/api/schema.d.ts` (`npm run generate:types` and `npx tsc --noEmit` in a Node 22 container, per the
  brief); verify `test_committed_schema_is_not_stale` passes and `git diff --stat web/` shows only the two
  `head` operations, the new parameter and the shifted line numbers.

## 4. Docs

- [ ] 4.1 Update the measured table in `docs/research/browser-playback.md` §5: the `If-None-Match` row is now
  answered 304, add an `If-Modified-Since` row and replace the "HEAD on a `@router.get` route" row with the
  current answer, and in HLD §4.9 (the paragraph that introduces the media routes) say they answer
  `GET` and `HEAD` with `If-None-Match` and `If-Modified-Since` validators. Verify with `grep -n "HEAD" docs/research/browser-playback.md docs/high-level-design.md`.

## 5. Validation gates

- [ ] 5.1 `black` + `isort` on `auto_reel_ng tests`, `mypy auto_reel_ng`, `pylint auto_reel_ng` (only the known
  cairo `no-member` noise), `.venv/bin/python -m pytest -m "not requires_db"` for the inner loop and the full
  `.venv/bin/python -m pytest` at the end; all pass.
