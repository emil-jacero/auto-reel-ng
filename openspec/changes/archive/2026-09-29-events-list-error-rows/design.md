## Context

See proposal.md — Why. The code facts that shape the approach:

- **`api/events_read.list_events`** walks the layout, then for each ref calls `_load_for_reconcile`. That
  function wraps `ReelParseError` and `EventMetadataError` as `EventReadError(event_id, detail)`, and then
  builds an `EventSummaryOut` with staleness via `staleness_for`. `scan_event`/`stat` failures (`OSError`)
  are not caught anywhere.
- **`api/routes/events.get_events`**:
  - its `response_model` is `List[EventSummaryOut]`
  - it maps `SQLAlchemyError` to 503, `EventReadError` to a per-event 502, and `ReelError` to a
    "scan failed" 502
  - `LayoutError` (an `EngineError`) and `OSError` from the walk are uncaught, and become a bare 500
- **`web/src/api/events.ts`** types the list as `EventSummary[]` and treats a 502 carrying `event_id` as
  "event X could not be scanned". `EventList.tsx` then renders that problem instead of the list.
- **Generated artifacts:** `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated from
  `app.openapi()`, and `tests/test_api_openapi.py` fails on drift. `tsc --noEmit` is the frontend gate.
- **The CLI already isolates per event.** `cli/commands._checked_document` prints
  `ERROR <event>: <reason>` for `ReelError`, which includes `EventMetadataError`.

## Goals / Non-Goals

**Goals:**

- One bad event costs one row, never the list.
- The row is typed, with a closed failure kind, so the client handles it exhaustively.
- Whole-list failures stay honest (the database, the walk).

**Non-Goals:**

- The detail route and slice C.
- Fix-it actions.
- Carrying partial facts in an error row.

## Research & Decisions

### The row types

**Decision**:

```python
# api/schemas.py
class EventFailure(StrEnum):
    UNPARSEABLE_REEL_YAML = "unparseable_reel_yaml"   # ReelError other than metadata
    UNUSABLE_METADATA = "unusable_metadata"           # EventMetadataError
    UNREADABLE_DISK = "unreadable_disk"               # OSError listing/stat'ing the event

class EventSummaryOut(BaseModel):
    kind: Literal["event"]
    # ...existing fields unchanged...

class EventErrorOut(BaseModel):
    kind: Literal["error"]
    event_id: str
    failure: EventFailure
    detail: str

EventRowOut = Annotated[Union[EventSummaryOut, EventErrorOut], Field(discriminator="kind")]
```

- The list route's `response_model` becomes `List[EventRowOut]`.
- `kind` is declared **without a default**, and every constructor passes it. The serialization schema then
  marks it required, and the generated TypeScript types get a non-optional discriminator: `kind: "event"`
  and `kind: "error"`. A literal with a default can render as optional, which would weaken narrowing.

**Rationale**:
- A discriminated union is the only shape where an error row is not a summary with nullable facts. It
  matches Principle I: absent is reported, never faked as zero clips.
- `EventFailure` lives in `api/`. It is the API's classification of engine exception types for its own
  row, so no engine layer has this vocabulary to own. (The CLI prints prose, and slice C's detail screen is
  also API-side.)

**Alternative rejected**: `{events: [...], errors: [...]}`. It breaks the list's array shape for every
client and loses the per-event position, for no gain over a union.

### Classifying and isolating per event

**Decision**: `list_events` wraps each ref's work: load, validate, listing, reconcile and staleness.

- `EventMetadataError` gives `UNUSABLE_METADATA`. It is checked first, because it subclasses `ReelError`.
- Any other `ReelError` (parse, import, validation) gives `UNPARSEABLE_REEL_YAML`.
- `OSError` gives `UNREADABLE_DISK`.
- `detail` is `str(exc)`, the same text the CLI prints.
- `SQLAlchemyError` is **not** caught per event: `latest_by_project` runs once before the loop, and a
  database failure stays the whole-list 503.
- Any other exception propagates (a 500): an unanticipated error is not dressed up as a known one.

`_load_for_reconcile` stops wrapping into `EventReadError` for the list path. It raises the engine error,
and the detail route keeps its own `EventReadError` mapping, so its per-event 502 is unchanged.

### Whole-list failures

**Decision**: The list route adds `LayoutError` and `OSError` raised by the **walk** (`_list_event_refs`) to
the existing scan-failure 502 (`bad_gateway("event scan failed: …")`). The per-event `EventReadError` branch
goes away from the list route.

**Rationale**: The walk failing means no event can be accounted for, which is the one legitimately
whole-list scan failure. Today it surfaces as an unshaped 500.

### The screen

**Decision**:
- `api/events.ts` gains `EventRow`, `EventError` and `EventFailure` aliases. `EventsResult.ok` carries
  `EventRow[]`.
- `EventList.tsx` partitions rows by `kind`:
  - error rows render first, in a "Needs attention" section: a table with the folder name (the last
    segment of `event_id`), the `FAILURE_LABEL[failure]` words, and the `detail`
  - summaries go through the existing `groupByYear`, filter and table unchanged
- The summary line: "N of M events need rendering", with " · K need attention" when K > 0.
- `labels.ts` gains `FAILURE_LABEL: Record<EventFailure, string>`:
  - `unparseable_reel_yaml`: "reel.yaml can't be read"
  - `unusable_metadata`: "missing or invalid date or title"
  - `unreadable_disk`: "files can't be read"
- `describeProblem` drops its `event_id` branch, because the list no longer 502s per event. A 502 without
  `check` reads "The project could not be scanned."

### The dev library

**Decision**: `scripts/make_dev_library.py` adds `2024/2024-02-30 - Omöjligt datum` (one symlinked clip) in
**phase 2**, after rendering.

**Rationale**: In phase 1, `enqueue` would report the event as an `ERROR` and exit 1, and the script runs
`enqueue` with `check=True`.

## Failure behavior and idempotency

- **A per-event failure** becomes a row. Nothing is written, and the read stays read-only.
- **Database or walk failure** is a whole-list problem body (503 or 502).
- **Re-requests** are deterministic for unchanged disk. Fixing the folder or `reel.yaml` turns the row into
  a summary on the next request.
- **No `RENDER_GRAPH_VERSION` bump**, and no fingerprint change.

## Risks / Trade-offs

- **[Clients relying on the list's array of summaries]** The only client is the generated web app, updated
  in this change. `curl` users see an added `kind` and possibly error rows. → This is documented in the
  README's API section.
- **[`OSError` hides a real bug]** It is caught only around per-event disk work, and its detail is shown.
  Anything else still surfaces as a 500.
- **[A large library with many broken events]** Each is one small row. The list's cost is unchanged.

## Migration Plan

Regenerate `web/openapi.json` and `web/src/api/schema.d.ts` (the README's two commands), then rebuild
`web/dist`. Nothing else migrates. Rollback means reverting the union and the screen.
