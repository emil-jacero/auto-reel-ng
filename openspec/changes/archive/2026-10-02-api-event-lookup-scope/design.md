## Context

`events_read` has two lookups. `resolve_event_dir` answers "is this a directory inside the project root";
`listed_event_dir` answers "does the configured layout list this id as an event", walking only the id's
first folder (one year, not the archive). The thumbnail and media routes use `listed_clip`, which wraps
`listed_event_dir` and maps an `OSError` to `EventReadError` with `classify_event_failure` (the list's
`unreadable_disk` kind); their routes map `LayoutError` to a 502 with no kind.

Re-checked on main (6a7fe16):
- `get_analysis` (events_read.py) still calls `resolve_event_dir` then `scan_event`; neither the walk nor
  an `OSError` is mapped, and the route (routes/events.py) catches only `EventNotFoundError` and declares
  no `responses`. `GET /events/2024/analysis` therefore returns `{analyzed:false}` and
  `.../original/analysis` likewise, while the list does not show either as an event.
- `put_reel` still declares `if_match: Optional[str] = Header(default=None, alias="If-Match")` and
  passes it to `_if_match_satisfied`, which already splits on commas. Starlette's header parameter keeps
  one value for a repeated line, so only the comma-join is missing. `get_thumbnail` does the right thing:
  `", ".join(request.headers.getlist("if-none-match")) or None`.

## Goals / Non-Goals

**Goals:**
- One rule for "an event" across the analysis, thumbnail and media reads: the id must be one the events
  list shows.
- Failures of that lookup are shaped problem bodies, never a 500.
- `If-Match` means the same thing on one line or several.

**Non-Goals:**
- `GET`/`PUT .../reel` keep `resolve_event_dir`. They are outside the two reported items, and tightening a
  write route is its own behaviour change with its own tests; it is noted for a follow-up, not folded in.
- No change to what analysis returns for a listed event, no new failure kind, no new status code beyond
  the 404/502 the sibling routes already use.
- No change to `_if_match_satisfied` (comma split, `*`, strong comparison).

## Decisions

**D1. `get_analysis` uses `listed_event_dir`, with `listed_clip`'s error mapping.**
`listed_event_dir` plus `scan_event` run inside one `try` that turns `OSError` into
`EventReadError(event_id, str(exc), classify_event_failure(exc))`; `clip_signal` (a stat) joins that `try`
because a clip removed between `scan_event` and the stat is the same disk fault, not a server error.
`EventNotFoundError` and `LayoutError` propagate. Alternative: factor a shared helper out of
`listed_clip` - rejected, the two bodies share three lines and their second halves differ (YAGNI, VII).
`reel.yaml` stays unread: analysis is a fact of the sidecar cache and the clip files, so an event whose
document is broken (a list error row) still answers 200 for its cache, as it does today.

**D2. The route answers like the thumbnail route.** `EventNotFoundError` -> existing 404;
`EventReadError` -> `_event_read_failed` (502, `failure` kind); `LayoutError` -> `bad_gateway(str(exc),
event_id=event_id)` with no kind. `responses={404, 502: ProblemOut}` is added so the generated OpenAPI
types and the web client see them. No 503: the route does not touch the database.

**D3. `put_reel` reads `If-Match` from the request; the Header parameter stays for OpenAPI only.**
Rename the parameter to `_if_match` (unused, `alias="If-Match"`), as `get_thumbnail` does for
`If-None-Match`, and join every line: `lines = request.headers.getlist("if-match")`, then
`if_match = ", ".join(lines) if lines else None`. The guard is on the list, not on the joined string, so
the existing outcomes hold: no header is unconditional, and a present-but-empty `If-Match:` is still a
precondition that matches nothing (412), as it is today. Alternative: a FastAPI `list[str]` header
parameter - rejected, it changes the published OpenAPI parameter type, and the thumbnail route's pattern
is already the house idiom.

## Risks / Trade-offs

- [A client that relied on analysis of a non-event directory gets 404] -> It never listed as an event;
  the web client requests analysis only for listed events. Covered by the spec scenario and test.
- [`listed_event_dir` walks a year on each analysis request] -> Same cost the thumbnail route pays per
  clip, narrowed to one year; the analysis page fetches once per event view.
- [The `...reel` routes keep the looser lookup] -> Recorded as a non-goal above so it is a decision, not
  an oversight.
