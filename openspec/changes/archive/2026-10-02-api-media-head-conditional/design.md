## Context

See proposal.md for the motivation. State on main (6a7fe16):

- `api/routes/media.py` registers `get_clip_media` and `get_movie` with `@router.get`. Each does the lookup
  (`clip_media` / `movie_media`), maps errors to problem bodies, and returns
  `media_response(media, _if_none_match(request))`.
- `api/media.py::media_response` returns `Response(304)` when `If-None-Match` names the file, else a
  `FileResponse` that carries its own `Last-Modified` (Starlette formats `st_mtime` with `formatdate`, so the
  header is the mtime truncated to whole seconds) and answers `Range` / `If-Range`.
- Measured on the pinned stack (Starlette 1.3.1, FastAPI 0.139.0, a scratch app): a route registered for
  `GET` and `HEAD` makes `FileResponse` send the headers of the `GET` (200, 206 and their `Content-Length` /
  `Content-Range`) and no body; a `JSONResponse` problem on `HEAD` carries its status and `Content-Length`
  and no body. A `HEAD` with the web client built reaches the static mount only because no API route took the
  method.
- The router carries the single authentication hook, so a `HEAD` passes it like a `GET`.

## Goals / Non-Goals

**Goals:**
- `HEAD` is the `GET` without a body, for every status the routes answer, built client or not.
- `If-Modified-Since` is a validator as RFC 9110 §13.1.3 defines it, ordered with `If-None-Match` and before
  `Range`.
- The schema and the spec describe both.

**Non-Goals:**
- The staleness gate. The triage found that `staleness.evaluate` counts a directory at the expected output
  path as present (`exists()`) while `rendered_output` / the movie route require a file. That is a verdict
  change in `staleness/` and is carried by `staleness-output-lookup`; this change leaves the movie
  requirement, which already lists the case as an exception, untouched. An un-adopted legacy movie stays
  404 by design (`adopt-renders`).
- `If-Match`, `If-Unmodified-Since`: they guard writes; these routes only read.

## Decisions

### 1. Two decorators on one function, not `api_route(methods=["GET", "HEAD"])`

**Context**: The route needs `HEAD` beside `GET`, with the same parameters and the same documented responses.
**Explored**: `@router.api_route(path, methods=["GET","HEAD"])` and stacked `@router.head(...)` /
`@router.get(...)` on the same function, both run against the pinned FastAPI.
**Decision**: Stack `@router.head` over `@router.get` with the same `response_class` and `responses`.
**Rationale**: `api_route` with two methods yields two OpenAPI operations with one `operationId`
(`UserWarning: Duplicate Operation ID`), which `openapi-typescript` and any client generator reject or
mangle. Stacked decorators give two routes with `…_get` and `…_head` ids, no warning, and the `get` operation
keeps its published id, so the committed schema changes only by the added `head` operations and the new
header parameter.

### 2. `If-Modified-Since` is evaluated in `media_response`, beside `If-None-Match`

**Context**: `media_response` already orders the preconditions before `FileResponse` sees `Range`.
**Decision**: Add a parameter `if_modified_since: Optional[str]` (the route passes the header). The order is
`If-None-Match` first; the date is considered only when `If-None-Match` is absent altogether.
- **absent**: `If-None-Match` not sent on any line.
- The route passes the header only when the request carries exactly one `If-Modified-Since` line (a repeated
  field is not a single HTTP-date). `media_response` parses it with `email.utils.parsedate_to_datetime`; a
  value that does not parse is ignored. A parsed value with no zone is read as UTC.
- 304 when `int(media.stat.st_mtime) <= int(date.timestamp())`: the same truncation `Last-Modified` carries,
  so a client echoing a `Last-Modified` it received always gets a 304 while the file is unchanged, and a file
  rewritten within the same second is the known limit of a one-second validator (the `ETag`, which has
  nanosecond mtime and size, is what a careful client sends).
- A date in the future is valid and gives 304 (the triage repro; RFC 9110 has no clock rule).
- The 304 carries the same two headers as the `If-None-Match` 304 (`ETag`, `Cache-Control`).
**Alternatives**: evaluating it in the route (rejected: the helper is where `If-None-Match` lives and where
the unit tests are); using `st_mtime_ns` exactly (rejected: a client holds the second-truncated date it was
sent, so exact comparison would never 304).

### 3. A non-matching `If-None-Match` ends the conditional evaluation

**Context**: The current spec says a non-matching `If-None-Match` is "answered as if it were absent". With
`If-Modified-Since` evaluated that sentence would let a stale tag fall through to the date, which RFC 9110
forbids ("MUST ignore `If-Modified-Since` if the request contains `If-None-Match`").
**Decision**: Reword to "answered 200 or 206 as if no conditional header were sent", and implement it by
checking `if_none_match is not None` before looking at the date.

### 4. `HEAD` needs no handler logic

`media_response` is method-agnostic; `FileResponse` drops the body on `HEAD`, including for `Range` (206 with
`Content-Range` and the range's `Content-Length`, no body), and the 304 and problem responses have none or
lose it. So the only code is the registration, the shared docstring and the schema. No body is built or
read on `HEAD`; the file is still statted and opened once, so an unreadable file is a 502 on `HEAD` too (it
tells the client the truth).

### 5. Schema

`MEDIA_RESPONSES` is shared by both methods: the `head` operations publish the same statuses and headers
(a `HEAD` 200 declares `video/*` content in the schema, which is accurate for the media type and keeps one
shared dict; the spec says the body is not sent). `If-Modified-Since` becomes a fourth optional header
parameter, declared like the others with `Header(default=None, alias="If-Modified-Since")` so the
generated types know it; the route reads the lines from the request to see a repeated field. `web/openapi.json`
is regenerated with `python -m auto_reel_ng.api.openapi`, and `web/src/api/schema.d.ts` with the existing
`generate:types` script in Node under podman, because `test_committed_schema_is_not_stale` compares the
committed JSON; no TypeScript source uses the new operations, so `tsc --noEmit` is the only web check.

## Risks / Trade-offs

- A client that sent `If-Modified-Since` and relied on always receiving the bytes now receives 304 for an
  unchanged file → that is the contract; the browser media element sends `If-None-Match`, so the GUI is
  unaffected.
- Second-resolution validator → a file replaced within the same second as the client's stored date and with
  the same size would revalidate as unchanged by date; `If-None-Match` is evaluated first and carries the
  nanosecond mtime, and clients that send both are never affected.
- `HEAD` on a problem response is the `GET`'s status with no body → clients see the same status as `GET`
  by design; there is no `HEAD`-specific 405 left.
- The old static-mount 404 for `HEAD` disappears when the web client is built → intended.

## Idempotency and failure

Pure reads: a repeat, a `HEAD` followed by a `GET`, and a service restart change nothing on disk or in
Postgres. No new failure kind: an unlistable folder, an unreadable file and a vanished file answer exactly as
for `GET` (`HEAD` included), because the lookup and the open run before any status is chosen.
