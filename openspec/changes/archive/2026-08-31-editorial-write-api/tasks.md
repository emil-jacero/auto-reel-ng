## 1. Engine: the editorial-write operation

- [x] 1.1 Create the editorial apply/persist module: take an event dir + a desired editorial state
  (metadata, chapters+clip order, clip properties, `ignore`, `look`); **load the current document and apply
  the state onto its ruamel round-trip structure** (`doc.raw`), then `build_document` the merged mapping and
  `write_document` it. Never construct the mapping from the desired state alone (D-E1). Fall back to a fresh
  build when the event has no `reel.yaml`.
- [x] 1.2 Test comment/key-order preservation on a **hand-authored commented fixture**: change only the
  title → every comment survives, key order holds, only the title line differs. This is the regression guard
  for the whole design — make its intent explicit in the test name and the module docstring.
- [x] 1.3 Test the write surface: metadata edit, reorder within a chapter, move a clip across chapters,
  set a `look` override on a document that had none, set `ignore`. Assert each persists and reloads.
- [x] 1.4 Test round-trip no-op: applying the document's current state persists a byte-identical file.
- [x] 1.5 Test the fresh-build fallback: an event with no `reel.yaml` gets a valid canonical file.
- [x] 1.6 Test validation is fail-loud and non-destructive: an invalid state (bad cross-reference) raises
  naming the problem and leaves the existing file untouched; assert **no partial write**.
- [x] 1.7 Test that a clip referenced but absent from disk is **preserved, not rejected or dropped**
  (MISSING is reconcile's business, D-CLI3) — and that the operation performs no probe and no filesystem
  reference check.
- [x] 1.8 Test the operation writes no manifest, creates no job, and leaves any existing output untouched;
  and that a previously-fresh event evaluates **stale citing editorial** afterwards (integration with the
  staleness gate).

## 2. API: the write endpoint

- [x] 2.1 Add the pydantic request schema for the desired editorial state (mirroring the read model's shape
  so a `GET` body round-trips) and the response schema (persisted document + staleness verdict).
- [x] 2.2 Add `PUT /api/v1/events/{event_id}/reel` to the events router: resolve the event id (reusing 7c's
  resolution), call the engine operation, echo the persisted document + new verdict. Keep the route free of
  editorial logic (D-E6).
- [x] 2.3 Test the route: successful save persists + echoes; a previously fresh event's response verdict
  reports `stale: editorial` and no job exists; invalid state → validation problem body with `reel.yaml`
  unchanged; unknown event → 404; URL round-trip with spaces/Swedish characters still resolves.
- [x] 2.4 Test the GET→PUT no-op: submitting an unmodified `GET` body back leaves the file byte-identical
  (proves the read and write models agree).

## 3. End-to-end and closeout

- [x] 3.1 End-to-end over podman PG + a fixture project: save via `PUT` → `GET` reports `stale: editorial`
  → `POST /jobs` enqueues → worker renders the edited state → event returns to fresh. Assert the rendered
  output reflects the edit (e.g. the new title on the title card).
- [x] 3.2 Docs: README section for the write endpoint — the coarse-PUT contract, the comment-preservation
  guarantee, save-is-not-render, and the **known limitation**: no concurrency control, so a GUI save during
  that event's render can clobber (or be clobbered by) adoption; the `If-Match` path is left open.
- [x] 3.3 Full suite + lint green; dogfood on a scratch copy of `auto-reel-media/`: `serve`, save an
  edit via `PUT`, watch the event go stale, enqueue, render, confirm the output changed. Record the result
  in the change notes.

### Change notes

- Engine module: `auto_reel_ng/event/editorial.py` (`apply_editorial_write`), merging field-by-field onto
  the loaded `CommentedMap` (metadata/look key-by-key, chapters/clips node-reuse by name/identity, trims
  left untouched when unchanged to avoid a flow-style -> block-style reformat). Tests:
  `tests/test_event_editorial.py` (11 cases).
- API: `EditorialDocumentBody`/`TrimBody`/`ClipPropertiesBody`/`ChapterBody`/`MetadataBody`/
  `EditorialWriteResult` in `api/schemas.py` (all `extra="forbid"`); `PUT /api/v1/events/{event_id}/reel` in
  `api/routes/events.py`; a new `bad_request` (400) problem helper distinct from FastAPI's structural 422;
  `events_read._staleness` made public as `staleness_for` so the write route can reuse it. Tests:
  `tests/test_api_editorial_write.py` (7 cases).
- Three design.md open questions settled during implementation: echo the persisted document (yes), inline
  staleness verdict (yes), `ignore` in the v1 write surface (yes, included in the schema).
- One resolved deviation, now reflected in the spec itself (the api-service scenario was reworded during
  verification): the "submitting an unmodified document via `PUT` is a no-op" scenario is implemented
  against the **PUT response's own echoed document**, not the existing `GET` response — `EventDetailOut` deliberately stays read-only/unaffected (untouched per the proposal's Impact
  section) and does not expose `look`/`ignore`/per-clip properties, so it cannot literally serve as write
  input. The round-trip guarantee itself (save what you just read back changes nothing) is preserved exactly
  via the echo.
- End-to-end (3.1): `tests/test_editorial_write_e2e.py`, a full save → stale → enqueue → real CPU render →
  fresh cycle against real Postgres (podman) and a real ffmpeg render of a synthetic clip; the rendered
  output filename (derived from title) demonstrably reflects the edit.
- Dogfood (3.3): ran `auto-reel serve` against a scratch copy of the real `auto-reel-media` fixture event
  (`2024-06-27 - grillning med grannar`, clips symlinked, `reel.yaml` never touched) with a throwaway podman
  Postgres container. Via `curl`: saved an initial editorial write, enqueued, ran the real worker — produced
  a genuine ~150s 1080p render (`Grillkväll med grannarna - Baksidan.mp4`) and the event went fresh. Edited
  the title again — the event reported `stale: [editorial, output]` — enqueued and rendered again, producing
  `Grillfest 2024 - Baksidan.mp4` and returning to fresh. Container, server process, and the scratch copy
  were torn down afterward; `auto-reel-media/` itself was never mutated (symlinked clips only).
- Full suite (`pytest`), `black`, `isort`, `mypy auto_reel_ng`, and `pylint auto_reel_ng` all green (see
  below).
