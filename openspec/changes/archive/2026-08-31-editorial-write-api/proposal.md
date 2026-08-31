## Why

7c shipped a **read-only** API and explicitly deferred editorial writes to "GUI v1, where a real consumer
exercises them" (§4.7 sync semantics). That consumer is now next: GUI v1 (§4.10) must persist drag-reorder,
metadata edits, and look selection to `reel.yaml`. This change is the **write half of the API** — and it is
deliberately the framework-independent workstream of phase 8: it is Python, testable headlessly like every
slice since phase 1, and it de-risks the GUI by existing before the GUI does. The frontend (React SPA in a
`web/` subdir) is a separate workstream that consumes this.

Two things make this smaller than §4.7 implies. First, **§4.7's text is stale**: it describes mutations
writing `reel.yaml` "with Postgres updated as a cache" — but 7a/7c deferred the event index, so there is no
cache to sync and the write path is simply "write the file; the next scan-on-request read sees it." Second,
the primitives already exist: `build_document` validates a mapping fail-loud, and `write_document`
round-trips comments and key order.

## What Changes

- Add an **editorial write operation** to the engine: given an event and a desired editorial state
  (metadata, chapter/clip order, look override), **apply it onto the event's existing document**, validate,
  and persist to `reel.yaml`. Transport-independent and CLI-reachable by construction (§4.9).
- **Preserve comments and key order.** The operation applies the desired state onto the loaded ruamel
  round-trip structure — it MUST NOT construct a fresh document from the request body, which would retain a
  plain mapping as the document's source structure and **strip every comment** from a hand-authored
  `reel.yaml` on first save. This mirrors the existing reconcile apply-operations, whose mutations already
  preserve comments (only changed lines differ).
- Add **`PUT /api/v1/events/{event_id}/reel`** — a coarse, whole-document write: the client sends the full
  desired editorial state; the server applies, validates, and persists it. Thin over the engine operation;
  the API adds no logic of its own.
- **Persist the look override to `reel.yaml`** (D-2's per-event override of `config.yaml` defaults; carried
  opaquely per the v0 schema). This is what makes GUI v1's "pick output look" coherent with the staleness
  gate: the look lands in the editorial component of the fingerprint, so changing it makes the event stale
  and a re-render actually produces the new look. (A render-time-only look param would escape the
  fingerprint entirely and be silently skipped as "fresh".)
- **Save is not render, and never writes a manifest.** An editorial write changes the fingerprint → the
  event goes stale → the next read reports `stale: editorial` → the GUI's render action enqueues. All of
  this already works; the write path's job is to not break it.
- **Validation is fail-loud and probe-free**: the submitted state is validated exactly as a loaded document
  is (schema + cross-references), rejecting bad writes with a problem body and never partially writing. A
  clip referenced but absent from disk is **not** an error — that is a MISSING clip, reported loud by
  reconcile per D-CLI3, and the write must not "helpfully" reject or drop it.
- **No concurrency control** (last-write-wins) — see design for the accepted risk and the migration door.

## Capabilities

### New Capabilities
- `editorial-write`: The engine-level operation that applies a desired editorial state (metadata, chapter/
  clip order, look) onto an event's document, validates it fail-loud, and persists it to `reel.yaml` with
  comments/key order preserved — writing no manifest, and leaving the staleness consequence to emerge.

### Modified Capabilities
- `api-service`: Gains the `PUT /api/v1/events/{event_id}/reel` write endpoint (thin over `editorial-write`).
  The existing read endpoints remain read-only and unchanged.

## Impact

- **New module**: the editorial apply/persist operation (alongside `reel/`), plus its pydantic request
  schema and route.
- **API**: one new route in `api/routes/events.py`; request schema in `api/schemas.py`. `GET` endpoints
  untouched.
- **Reuses unchanged**: `load_document`, `build_document` (fail-loud schema + cross-reference validation),
  `write_document`/`document_to_data` (round-trip preservation), the staleness gate and fingerprint, the
  ingest layouts and event-id resolution from 7c.
- **No changes below the engine**: no migration, no store change, no scheduler change, no engine/render
  change. The staleness gate and manifest discipline are consumed, not modified.
- **Tests**: apply/validate/persist unit tests (including a comment-preservation test on a hand-authored
  fixture), API route tests (success, validation failure, 404), and an end-to-end
  save → `GET` shows `stale: editorial` → enqueue → render assertion.

## Non-goals

- **No GUI.** The React SPA (`web/` subdir, per the phase-8 framework research) is the separate downstream
  workstream; this change ships no frontend.
- **No trim editing.** Trims are the v3 timeline editor's surface; v1's editable set is metadata,
  chapter/clip order, and look — which keeps validation probe-free.
- **No fine-grained mutation endpoints** (`:reorder`, `PATCH /metadata`, …). The coarse whole-document PUT
  is v1; per-operation routes are a later refinement if payload size or conflict granularity ever demands
  them.
- **No concurrency control / optimistic locking.** Last-write-wins; the `If-Match` door stays open.
- **No CLI subcommand** for editorial writes — the operation lives in the engine (so the CLI *can* reach
  it), but no `auto-reel edit` surface ships until something needs it.
- **No event index, no auth, no multi-project** — all unchanged from 7c.
