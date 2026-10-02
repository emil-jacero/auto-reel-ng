## Why

Two events routes read their request more loosely than their siblings do. `GET /events/{id}/analysis`
accepts any directory under the project root as an event (a year folder, an event's `original/`), while
the events list, the thumbnail and the media routes only accept what the configured layout lists. And
`PUT /events/{id}/reel` reads `If-Match` through a single-valued header parameter, so a precondition sent
on repeated header lines is judged on its first line only, while RFC 9110 treats repeated lines as one
comma-joined list and the thumbnail route already honours that.

## What Changes

- `GET /api/v1/events/{event_id}/analysis` answers 404 for any id the events list does not show as an
  event (a year folder, an event's `original/` or chapter folder, a `.reelignore`d event), exactly as the
  thumbnail and media routes do.
- The same route answers a directory it cannot list, or a layout it cannot resolve, with the 502 problem
  body the other event reads use (unreadable-disk failure kind for the former, no kind for the latter)
  instead of an unshaped 500, and publishes its 404 and 502 in the OpenAPI schema.
- `PUT /api/v1/events/{event_id}/reel` evaluates `If-Match` across every header line the request carries,
  so two lines are equivalent to the same two tags comma-joined in one line.
- No engine, CLI, database, config or rendered-output change; `RENDER_GRAPH_VERSION` is untouched.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `api-service`: "Analysis results are exposed read-only" gains the listed-event scope and its failure
  answers; "Conditional editorial write" states that `If-Match` is read across all header lines.
  (`editorial-write` is the engine operation and carries no `If-Match` requirement, so it is unchanged.)

## Impact

- `auto_reel_ng/api/events_read.py` (`get_analysis`), `auto_reel_ng/api/routes/events.py` (the analysis
  and `put_reel` routes), `tests/test_api_events.py`, `tests/test_api_editorial_write.py`.
- Clients: a request that used to get a 200 `{analyzed: false}` for a non-event directory now gets 404.
  The web client only requests analysis for listed events, so nothing it sends changes.
- Not in scope, observed: `GET`/`PUT .../reel` still resolve with the any-directory rule (see design).
