## Why

Principle I allows exactly one softening: **per-event isolation**. One bad event must not kill a batch, and
it must be reported as failed, never as rendered. The CLI got this in `event-metadata-resolution`:
`scan`, `render`, `enqueue` and `adopt-renders` print `ERROR <event>: <reason>` and carry on. The events
**list** API did not. `list_events` raises `EventReadError` for the first unreadable event, and the route
turns that into one 502 for the whole library. The GUI's list screen (slice B) then shows "Event X could
not be scanned" *instead of* the list.

The real archive makes this the normal state, not an edge case. The read-only `adopt-renders --dry-run`
(2026-09-27) found 3 events whose folder names fail the date rule:

- `2004 - Yngve…` (year only)
- `2016 - Kents film…` (year only)
- `2019-04-31 - Golfträning…` (impossible date)

With the GUI pointed at the archive, **one of the three blanks the whole screen**. Every future typo in a
folder name, or a malformed `reel.yaml`, would do the same. The HLD's v1 GUI is meant to be where the
operator *sees* what needs attention (§4.10), and today it hides the whole library behind the first problem.

This is HLD **§6 phase 8** (GUI v1), the first step of finishing it. The API carries the rows, and the web
list renders them. The two ship together, because the list's item type changes, so the regenerated client
types fail `tsc` until the screen handles the new row.

## What Changes

- **The events list reports an unreadable event as an error row, not a failed request.** A per-event failure
  becomes an **error row** in place of that event's summary, and every other event is listed normally. It
  names the event, a closed **failure kind**, and the engine's detail, which already states the fix. The
  kinds:
  - `unparseable_reel_yaml`: the `reel.yaml` is malformed or fails validation
  - `unusable_metadata`: no real date or title, or a future date, per `event-metadata-resolution`
  - `unreadable_disk`: the event's files cannot be listed or stat'ed
- **Rows are discriminated.** Every row carries `kind`: `"event"` for a summary, `"error"` for an error row.
  The schema publishes the list as a discriminated union, so generated client code switches on `kind`
  exhaustively. Existing rows gain only the `kind` field.
- **Whole-list failures stay whole-list.**
  - An unreachable database is still the 503 problem body. A list without every event's latest job would
    fabricate "no job".
  - A walk of the project root that fails is a 502 problem body, where today it is an unshaped 500.
  - There is never a partial list: every event walked appears, as a summary or as an error row.
- **The list screen shows a "Needs attention" group first.** Each error row shows its folder name, the
  failure kind in words, and the detail. The summary reads "N of M events need rendering · K need
  attention". The needs-render filter never hides an error row. Failure kinds get words through an
  exhaustive label map, like reasons and job statuses.
- **The dev library gains one failing event** (`scripts/make_dev_library.py`): an impossible folder date,
  so the new row is exercised in development.

## Non-goals

- **The detail route is unchanged.** `GET /api/v1/events/{id}` still answers a failing event with its
  per-event 502, since one event is the whole of that response. Slice C decides how the detail screen shows
  it.
- **No retry and no partial facts inside an error row.** An error row carries no clip counts, staleness or
  title, because those are exactly what could not be read. The folder name comes from the event ID.
- **No fix-it actions in the GUI.** Showing the fix is enough for v1. Editing a date is slice D.
- **No change to the CLI.** It already isolates per event, and the API now catches up with it (Principle V).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: `Requirement: Events reads fail loud with a problem body`. A per-event failure becomes an
  error row in the list; the database and walk failures stay whole-list; the list's union item type is
  published.
- `web-app`:
  - `Requirement: The event list reports failures by cause`: error rows in a "Needs attention" group.
  - `Requirement: The event list answers what needs rendering, from disk`: the summary and filter treat
    error rows.
  - `Requirement: Screen labels are exhaustive over the generated vocabularies`: adds the failure kinds.

## Impact

- **Packages:**
  - `api/`:
    - `schemas.py`: `EventErrorOut`, the `EventFailure` enum, and `kind` on `EventSummaryOut`
    - `events_read.list_events`: per-event catch and classification
    - `routes/events.py`: the list's response model, plus mapping a walk failure to a 502
  - `web/`:
    - `api/events.ts`: the aliases
    - `events/labels.ts`: `FAILURE_LABEL`
    - `events/EventList.tsx`: the group, summary and filter
    - regenerated `openapi.json` and `schema.d.ts`
  - `scripts/make_dev_library.py`
- **CLI vs API (Principle V):** CLI unchanged. The API reaches the parity the CLI already has.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** Fingerprint inputs unchanged.
- **Schemas:** no `reel.yaml` or `config.yaml` change, **no Alembic migration**, no rescan. **API response
  shape:** list items gain `kind`, and the item type becomes a union. That is additive for a client that
  reads fields as strings, and a compile error by design for the generated client until it handles the
  error row.
- **Dependencies:** none.
- **Size (Principle VIII):** one response union and one catch in `api/`, and one row type and group in
  `web/`. The two ship together because the drift pipeline makes them inseparable.
