## Context

Phase 8 = GUI v1 (§4.10) + the editorial write API deferred out of 7c. The 2026-07-15 explore session split
it into two orthogonal workstreams: **(1) the write API** — Python, framework-independent, headlessly
testable, this change — and **(2) the GUI** — a React/Vite SPA in a `web/` subdir, downstream, gated on
open framework questions that do not touch this design.

What already exists and is load-bearing here:
- `load_document` → `ReelDocument` carrying `_data`, the ruamel round-trip structure (`doc.raw`).
- `build_document(mapping)` → validates version, metadata, look, chapters, clips, ignore, **and
  cross-references**, fail-loud — retaining the passed mapping as `_data`.
- `write_document` → `document_to_data`: **if `doc.raw` is not None it re-emits that structure** (deep
  copied, `version` forced), else `_build_fresh` from typed fields.
- The `reel-document` spec's round-trip requirement: unchanged documents are byte-stable, and preservation
  "extends to documents mutated by reconcile apply-operations — only the changed lines differ."
- The staleness gate keys on an **editorial** component (the canonical `reel.yaml`), so any write moves the
  fingerprint; `look` is part of the document (carried opaquely in v0).

§4.7's "Postgres updated as a cache" is **stale text** — 7a/7c deferred the event index, so there is no
cache and no sync problem: write the file, the next scan-on-request read sees it.

## Goals / Non-Goals

**Goals:**
- Persist GUI v1's editable set — metadata, chapter/clip order, look override — to `reel.yaml`.
- Never regress the round-trip guarantee: a hand-authored `reel.yaml`'s comments survive GUI saves.
- Validate writes exactly as loads are validated; fail loud, never partially write.
- Keep save/render distinct and let the existing staleness gate do its job untouched.

**Non-Goals:** the GUI, trims, fine-grained routes, concurrency control, a CLI subcommand, index/auth/
multi-project (see proposal).

## Decisions

### D-E1 — Apply onto the loaded structure; never construct fresh from the request body
The operation MUST: load the event's current document (obtaining `doc.raw`, the ruamel `CommentedMap`),
apply the submitted desired state onto **that** structure, then `build_document` the merged map and write.
*Why this is the whole ballgame:* `build_document` retains whatever mapping it is handed as `_data`, and
`document_to_data` re-emits `_data`. Hand it a plain JSON-derived dict and the writer faithfully re-emits a
plain dict — **every comment and the author's key order are gone on the first save**. The docstring says it
outright: "Callers that construct `data` as a ruamel `CommentedMap` get comment/key-order preservation for
free." Applying onto the loaded map is exactly what reconcile's apply-operations already do, and the
`reel-document` spec already promises "only the changed lines differ" for that path — so this decision keeps
an existing guarantee rather than inventing one. *Alternative rejected:* body → `build_document` →
`write_document` (the obvious three-liner) — silently destroys hand-authored files; a data-loss bug, not a
style preference. *Consequence:* an event with **no** `reel.yaml` yet (`doc.raw is None`, seeded in memory)
correctly falls back to `_build_fresh` — nothing to preserve.

### D-E2 — Coarse whole-document PUT (client sends full desired state)
`PUT /api/v1/events/{event_id}/reel` with the complete editorial state. *Why:* v1's editable surface is
tiny (metadata, order, look), the GUI already holds the document as its client-side model, and one
validated route is far less surface than a family of operation endpoints — which would additionally require
new mutation helpers on `ReelDocument` (immutable dataclasses today). *Alternative rejected:* fine-grained
`:reorder` / `PATCH /metadata` routes — more endpoints, more validation paths, no v1 benefit. Note "coarse"
describes the **request**, not the write: per D-E1 the server still merges, it does not replace the file.

### D-E3 — The look override persists to `reel.yaml` (reverses the explore-session lean)
GUI v1's "pick output look" writes a per-event `look` override (D-2's documented layering; carried opaquely
by the v0 schema). *Why the reversal:* a render-time-only look param escapes the fingerprint — render with
look A (manifest records F), then render with look B, fingerprint is still F → the gate says **fresh** →
skips → the output silently keeps look A. Persisting puts look in the editorial component, so changing it
makes the event stale and the re-render actually produces the new look. It also reuses the mechanism D-2
already designed instead of adding a parallel one. *Alternative rejected:* adding look to the fingerprint as
an invocation-time input — makes fingerprints depend on how a render was launched, breaking the
host/invocation-independence D-C1 deliberately established.

### D-E4 — Validation is the loader's validation; a MISSING clip is not a validation error
The merged mapping goes through `build_document`, inheriting its fail-loud schema and cross-reference
checks, with the failure surfaced as a problem body and **no** file written. Crucially, a clip referenced by
the document but **absent from disk is legal** — that is a MISSING clip, which reconcile reports loud and
D-CLI3 forbids silently removing. The write path therefore does **not** check the filesystem and does not
reject or drop such references. *Why:* the alternative ("validate references against disk") would make the
API quietly delete the operator's record of a temporarily-detached clip — exactly the fabrication/silent-
loss class of bug this project exists to avoid. *Consequence:* v1 validation touches no media → probe-free
and fast (trims, which would need durations, are v3).

### D-E5 — Save never writes a manifest; staleness is emergent
The write persists `reel.yaml` and stops. It does not write a render manifest, does not enqueue, does not
touch the gate. The fingerprint's editorial component moves on its own → the next `GET /events/{id}` reports
`stale: editorial` → the GUI lights its render action → enqueue is the existing separate call. *Why record
a decision for "do nothing":* the manifest-write discipline (engine-only, on actual render success) is what
makes the gate trustworthy; a well-meaning "mark it rendered" here would silently break change detection.

### D-E6 — Logic in the engine, route stays thin (§4.9)
The apply/validate/persist operation is an engine function; the route parses the body, calls it, and maps
errors to problem responses. This satisfies §4.9's thin-layer constraint — the operation is CLI-reachable by
construction — without shipping an `auto-reel edit` subcommand, which has no consumer yet. *Interpretation
noted:* §4.9 is read as "no logic exclusive to the API," not "every endpoint needs a CLI twin today." If
that reading is too loose, the remedy is additive (expose a subcommand later), not a redesign.

### D-E7 — No concurrency control (last-write-wins)
No `If-Match`, no version token. *Why:* single-operator reality. *The one real race, accepted:* a render's
`prepare_event` adoption rewrites `reel.yaml` (picking up NEW clips) while the GUI holds an edit; the save
then clobbers the adoption (or vice versa). Rare — it requires editing an event that is rendering — and the
loss is a re-adoptable NEW-clip entry, not editorial intent. *Migration door:* the fingerprint is already
computed per event, so an `If-Match: <fingerprint>` guard is purely additive to this API shape if the
collision ever bites.

## Risks / Trade-offs

- **[Comment destruction if D-E1 is implemented naively]** → The tempting three-liner is a data-loss bug on
  hand-authored files. *Mitigation:* an explicit test that saves onto a commented fixture and asserts
  comments survive and only changed lines differ; call it out in the module docstring.
- **[Adoption/save clobber (D-E7)]** → accepted; documented as a known limitation with the `If-Match` path
  noted so it is a deliberate gap, not an oversight.
- **[Coarse PUT lets a buggy client blank the document]** → sending a partial "full state" writes a
  legitimately-emptier document. *Mitigation:* schema validation catches structural nonsense, but semantic
  self-harm is the client's; the GUI must round-trip what it loaded. Worth a test that a PUT of the
  unmodified GET body is a no-op.
- **[Key ordering of newly-added sections]** → adding a `look` map to a document that never had one appends
  in canonical position; only that addition differs. Covered by the round-trip test.
- **[Event with no `reel.yaml`]** → `doc.raw is None` → fresh build; correct, and worth an explicit test so
  the fallback is not mistaken for the D-E1 anti-pattern.

## Migration Plan

1. Engine operation + tests (apply-onto-raw, validation, comment preservation, fresh-build fallback).
2. Request schema + `PUT` route + tests (201/200 success, validation problem body, 404 unknown event).
3. End-to-end: save → `GET` reports `stale: editorial` → `POST /jobs` → worker renders the new state.
4. **Rollback:** fully additive — remove the route/module; reads and everything below are untouched.

## Open Questions

- **Response body of the PUT:** echo the persisted document (client resyncs, one round-trip) vs 204 No
  Content (client trusts its own state)? Lean: **echo the persisted document** — it lets the GUI observe
  server-side normalization and the new staleness verdict without a second GET. Settle when writing the route.
- **Does the PUT return the new staleness verdict inline?** It is free to compute (probe-free) and the GUI
  wants it immediately after save. Lean: yes, alongside the echoed document. Confirm with the schema shape.
- **`ignore` list in the v1 write surface?** The document models `ignore` (ignored clips) and the GUI could
  plausibly expose "hide this clip" in v1. Lean: include it — it is part of the editorial document, costs
  nothing to accept, and excluding it means a GUI-side round-trip could drop it. Verify against §4.10's v1
  scope.
