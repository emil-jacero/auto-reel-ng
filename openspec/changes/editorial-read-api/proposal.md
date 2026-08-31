## Why

`editorial-write-api` (archived 2026-08-31) shipped `PUT /api/v1/events/{event_id}/reel` as a **coarse
whole-document write** (D-E2): the client sends the complete desired editorial state and the server merges it
onto the event's existing structure. **No endpoint returns that state.** `GET /api/v1/events/{event_id}`
returns `EventDetailOut` — the *reconcile* view — which carries `metadata` and `chapters` but not `look`,
`clips`, or `ignore`.

The write's merge treats an absent section as *clear*, not *unchanged*, and pydantic's field defaults erase
the distinction between "omitted" and "empty" before the engine ever sees it:

- `_apply_clips` — empty map → `data.pop("clips")` → every trim, `rotate`, `title` flag and `exclude` is gone
- `_apply_ignore` — empty list → `data.pop("ignore")` → the ignore list is gone
- `_apply_look` — keys absent from the desired map are deleted

So the natural GUI v1 save loop — render the detail view, edit a title, PUT what you hold — **silently
destroys the analysis trims phase 6 produced**, on disk, in the file Principle II names the source of truth,
with no undo (event dirs are media, not git repos). The only client that can round-trip safely today is one
that has already written once and kept the PUT's echo. That chicken-and-egg is what this change removes, and
it is Principle I read from the client's side: a client must not have to guess at state the server declined
to return.

Second, nothing guards a **lost update**. `auto-reel analyze` writes trims to the same file; a GUI tab left
open for an evening holds a stale document. The write endpoint has no precondition, so the later PUT wins and
the trims are gone — the same data loss by a different route.

This is HLD **§6 phase 8 (GUI v1)**. Its §8 research gate — item 10, frontend framework — is resolved as
**D-8** (§4.10, LOCKED): React + Vite + TypeScript, a static build served by FastAPI. This change is the
backend half of that phase: Python, headlessly testable, and shipped before the SPA exists — the same
de-risking order `editorial-write-api` used.

## What Changes

- **Add `GET /api/v1/events/{event_id}/reel`**, returning `EditorialDocumentBody` — the exact inverse of the
  PUT, via the `document_to_body` serializer the write endpoint already echoes. Thin over `load_document`
  (Principle V). An unknown event is 404; a malformed `reel.yaml` fails loud with the same problem body the
  detail route already produces. An event with **no `reel.yaml` yet** returns the empty document rather than
  404 — the write endpoint already accepts that case (it seeds from `ReelDocument()`), so the read must too.
- **Return an `ETag` on that GET**, and **honor `If-Match` on the PUT**: a match writes, a mismatch is
  `412 Precondition Failed` with `reel.yaml` untouched. An absent `If-Match` stays unconditional per RFC 9110,
  so every existing client — and `curl` — is unaffected.
- **Expose the editorial hash the ETag uses.** It is not a new input: `compute_fingerprint` already derives
  the fingerprint's `editorial` component as a hash over `document.to_dict()` (§4.13, D-C1). This change lifts
  that expression into a named function in `staleness/fingerprint.py` and calls it from both places. The reuse
  is what makes the ETag *correct*: it is canonical over typed fields, so a comment-only or reformatting edit
  does **not** change it and cannot raise a spurious 412, while any editorial change does.
- **Write down the rule a GUI must obey**, as a spec requirement rather than folklore: *the write body is
  built from the editorial document, never from the reconcile view.* `_build_chapters` deliberately **merges**
  disk-only NEW clips into the document's chapters and tags every clip with a reconcile status. A client that
  rebuilds a write body from it therefore adopts every NEW clip into `reel.yaml` implicitly, and — combined
  with an emptied `ignore` list — promotes previously ignored footage into the render. Both are silent, and
  neither was chosen by the user.

## Non-goals

- **No look picker and no config endpoint.** Editing the look is GUI v2 (§4.10, updated in this change's
  branch of the doc); v1 displays it read-only from this endpoint's `look` map. A `GET /api/v1/config`
  exposing project defaults — and any notion of *named* look presets — is deliberately out: the latter is a
  `config.yaml` schema change and its own product decision.
- **No SPA hosting.** Mounting the built `web/dist` (D-8) lands with the GUI change that produces a `dist`
  worth mounting.
- **No change to `EventDetailOut`.** It stays the reconcile view. Widening it with `look`/`clips`/`ignore` was
  considered and rejected: it conflates "what does the scan see" with "what is the editorial state", and hands
  the GUI two sources for `chapters` — the precise bug this change exists to prevent.
- **No PATCH or sparse writes.** D-E2's coarse whole-document write stands; this change supplies the read it
  was missing rather than reshaping the write.
- **No mandatory `If-Match`.** Requiring it would break unconditional scripted clients the spec already
  guarantees.
- **No frontend code**, and no new CLI subcommand (see Impact).

## Impact

- **Packages:** `api/` (one new route, the precondition check on the existing PUT) and `staleness/` (extract
  one function; no behavior change). Two packages, one endpoint added, one modified — within Principle VIII.
- **API / CLI (Principle V):** API only, and this adds **no engine capability**. Reading an event's document
  is `load_document`, which the CLI already reaches (`scan`, `render`, and `enqueue` all load it; the raw file
  is `cat reel.yaml`). "New engine capability lands with its CLI surface" therefore does not trigger — nothing
  lands here that the CLI cannot already reach.
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump.**
- **Staleness fingerprint inputs:** unchanged. The `editorial` component is refactored into a named function
  and MUST hash identically to today; a test pins that, so this change makes **no event stale**.
- **Schemas:** no `reel.yaml` change, no `config.yaml` change, no Postgres schema change. **No Alembic
  migration and no rescan.**
- **Dependencies:** none added (Principle VII).
