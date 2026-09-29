## Why

GUI v1 slice **C**, the event detail screen (HLD **§6 phase 8**, §4.10, stack **D-8**), is next. It reads
`GET /api/v1/events/{event_id}`. The response is already nearly complete for a read-only screen:

- chapters and clips in play order, with NEW clips placed as adoption would place them
- IGNORED clips flagged, and the MISSING list
- per-clip size and mtime
- the staleness verdict and the latest job

Two gaps remain, and both are the kind §4.10's pipeline rule exists to prevent. As with slice B, they are
closed in `api/` first, so the screen change stays a pure `web/` change (Principle VIII):

1. **A clip's status is a bare string.** `ClipOut.status` is `str`, so `openapi-typescript` generates
   `string`, and the screen would switch on `new`/`active`/`missing`/`ignored` through a hand-maintained
   map. §4.10's rule is that a closed set published as `str` is a hole the drift checks cannot see. The
   vocabulary is already owned by `event/` as `ClipStatus`. It is also the one engine vocabulary that is a
   plain `Enum`: `StalenessReason` is a `StrEnum`, and `JobStatus` is a `str` enum.
2. **The detail route fails differently from the list for the same broken event.**
   `events-list-error-rows` classifies a per-event failure into a closed `EventFailure` kind for the list.
   The detail route maps only `ReelParseError` and `EventMetadataError` to its 502, and that 502 carries
   prose but no kind. For the same event:
   - an `OSError` listing the event's files escapes as an **unshaped 500**
   - so do a `ReelImportError` and a `ReconcileError`
   - the web client reads a 500 as "the service is not reachable", which is false

   So the list can say "missing or invalid date or title" for an event whose detail says something else,
   or claims the service is down.

## What Changes

- **`ClipStatus` becomes a `StrEnum`** with the same four values. Every `is`/`==`/`.value` use keeps working,
  and a member now also compares equal to its string, like the other vocabularies.
- **`ClipOut.status` is typed as `ClipStatus`.** The schema publishes the enumeration, and the generated
  client gets a union. **Wire values do not change.**
- **The detail's per-event failures use the list's classification.** A failure that makes the list emit an
  error row makes the detail answer with the **scan-failure 502** problem body, naming the event and
  carrying the same **`failure`** kind. The three kinds are an unparseable `reel.yaml`, unusable metadata,
  and an unreadable disk. It is never an unshaped 500. One helper classifies for both reads.
- **`ProblemOut` publishes the optional `failure`** (an `EventFailure`), so the client derives it from
  generated types.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.** No client code changes, since the
  web app does not yet read either field.

## Non-goals

- **No screen.** Slice C (`event-detail-screen`) is the next change.
- **No jobs-route contract work.** The name-clash check on `POST /api/v1/jobs`, the jobs routes' published
  problem responses (409, 404), and `CancelResult.outcome`/`WsMessage.type` as closed vocabularies are
  slice E's prerequisites.
- **No per-clip editorial properties on the detail.** Trims, the title flag and rotation are served by the
  editorial read (`GET …/reel`), which slice D uses.
- **No media facts** (duration, resolution): the events reads stay probe-free (§4.9). Those belong to the
  analysis cache and v2.
- **No change to the editorial read's 502.** It keeps its current body, and slice D decides whether it needs
  the kind.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - new `Requirement: Clip status is a closed, published vocabulary`
  - `Requirement: Events reads fail loud with a problem body`: the detail's per-event failures match the
    list's classification, are never unshaped, and publish the failure kind

## Impact

- **Packages:**
  - `api/`:
    - `schemas.py`: `ClipOut.status`, and `ProblemOut.failure`
    - `events_read.py`: a shared `classify_event_failure`, used by `list_events` and `get_event`, and
      `EventReadError` carrying the kind
    - `routes/events.py`: the detail's 502 carries `failure`
  - `event/reconcile.py`: `ClipStatus` becomes a `StrEnum` (a base-class change only).
- **CLI vs API (Principle V):** the CLI is unchanged. It already prints the same engine text per event and
  gains no behavior here. The API's two reads now agree with each other.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. **Wire:**
  `status` values are unchanged, and the detail's 502 body gains a `failure` field. Paths that returned a
  bare 500 now return that 502.
- **Generated artifacts:** `web/openapi.json` and `web/src/api/schema.d.ts` move, and
  `tests/test_api_openapi.py` fails until both are regenerated.
- **Dependencies:** none.
- **Size (Principle VIII):** one enum base, one field annotation, one shared classifier, one optional problem
  field, one capability delta.
