## Why

The media routes (change `media-endpoints`, HLD §4.9, §6 phase 8) are per-request reads of a file that a
browser, a proxy or a script fetches by URL. Triage of main (6a7fe16) found two gaps in how they speak HTTP:

- **`HEAD` is not answered.** Both routes are registered for `GET` only. A `HEAD` on `…/media?clip=` or
  `…/movie` is a 405 when the web client is not built, and a 404 from the static mount when it is. A client
  that wants a clip's size, type or `ETag` before it commits to the body (a download manager, a health probe,
  `curl -I`) gets an error for a file the service would serve.
- **`If-Modified-Since` is ignored.** The routes send `Last-Modified` and the spec even says
  "`If-Modified-Since` SHALL NOT be evaluated". A client that stored only the date (a plain HTTP cache, a
  `curl -z`) is sent the whole file again: `GET` with `If-Modified-Since: Wed, 01 Jan 2099 00:00:00 GMT`
  returns 200 with the full body where RFC 9110 §13.1.3 requires 304.

Neither is visible in the GUI (the media element sends `Range` and `If-None-Match`), so both are low
severity. Both are small, in one file pair, and fixed together because they are the same two routes' HTTP
semantics.

The third triage observation, that the movie route and the staleness verdict disagree about a directory at
the expected output path, is **not** in this change: its fix is in `staleness/` and belongs to the change
`staleness-output-lookup`. See design.md.

## What Changes

- Both media routes answer **`HEAD`** with the status and headers `GET` gives for the same request (200,
  206, 304, 400, 404, 416, 502, with `Content-Length`, `Content-Range`, `ETag`, `Last-Modified`,
  `Cache-Control`, `Content-Type`, `Accept-Ranges`) and no body. This holds with and without the built web
  client.
- Both routes evaluate **`If-Modified-Since`** on `GET` and `HEAD`: a valid HTTP-date at or after the file's
  modification time, truncated to whole seconds, is a 304 with the `ETag` and `Cache-Control`; it is
  ignored when `If-None-Match` is present (RFC 9110 §13.1.3) or when it is not a single valid HTTP-date.
- The OpenAPI schema publishes the `head` operations and `If-Modified-Since` as an optional header
  parameter; `web/openapi.json` is regenerated.
- **Replaced requirement text:** "`If-Modified-Since` SHALL NOT be evaluated" and "A non-matching
  `If-None-Match` SHALL be answered as if it were absent" (which would let `If-Modified-Since` act after
  a mismatching tag).

Rendered output: **unchanged**, no `RENDER_GRAPH_VERSION` bump. Staleness fingerprint inputs: unchanged.
`reel.yaml` / `config.yaml` schema: unchanged. No Alembic migration, no rescan. Touches the **API** only (the
CLI has no media surface; Principle V is met because both routes stay per-request reads with no engine
behavior). No new dependency (`email.utils` from the standard library).

## Non-goals

- No `ETag` or `Last-Modified` format change; no `HEAD` on other routes (events, thumbnail);
  no `If-Match` / `If-Unmodified-Since` (writes are not served here); no change to the movie lookup or to
  the staleness gate (`staleness-output-lookup`); no web client change beyond regenerated types.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: the requirement "Media files are streamed with ranges and validators" gains `HEAD` and
  `If-Modified-Since` and loses the two sentences above.

## Impact

- `auto_reel_ng/api/routes/media.py` (both routes registered for `HEAD` as well, the new header parameter,
  the schema), `auto_reel_ng/api/media.py` (`media_response` evaluates the date).
- `web/openapi.json` and the generated `web/src/api/schema.d.ts` (a `head` operation per path and one
  optional header parameter; no client code reads them).
- `tests/test_api_media.py`, `tests/test_api_openapi.py`; one line in `docs/research/browser-playback.md`
  whose measured table records the old answers.
