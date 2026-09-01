## Context

See `proposal.md` — Why. The state this design builds on:

- `PUT /api/v1/events/{event_id}/reel` already exists as a coarse whole-document write (D-E2), and already
  **echoes** the persisted document via `api/serialize.py::document_to_body`. The exact body this change must
  return therefore already has a producer; nothing needs a second serializer.
- `staleness/fingerprint.py::compute_fingerprint` already derives the fingerprint's `editorial` component as
  `_hash_json(document.to_dict())` (D-C1) — a canonical hash over the document's typed fields, deliberately
  blind to comments and formatting.
- `api/events_read.py::resolve_event_dir` already maps an `event_id` to a directory and raises the
  `EventNotFoundError` the detail route turns into a 404 problem body.

The binding constraints are Principle V (nothing in `api/` the CLI cannot reach), Principle II (`reel.yaml` is
the source of truth and round-trips comments), and Principle VII (no second code path added "for later").

## Goals / Non-Goals

**Goals:**

- The read response and the write body MUST be the same model, produced by the same function — not two shapes
  kept in agreement by hand.
- The ETag MUST derive from the same expression the staleness fingerprint's `editorial` component uses, so an
  ETag and a staleness verdict can never disagree about whether the editorial state changed.
- The fingerprint MUST be bit-identical before and after this change: no event goes stale.

**Non-Goals:**

- No conditional **GET** (`If-None-Match` / 304). See D-R4.
- No ETag on `GET /api/v1/events` or `GET /api/v1/events/{event_id}`; the reconcile view is not a write model
  and needs no precondition.
- No change to the engine operation `apply_editorial_write`. The precondition is a transport concern.

## Research & Decisions

### D-R1 — The ETag is the fingerprint's editorial component

**Context**: The ETag must answer exactly one question — "has the editorial state changed since the client
read it?" — and must not answer it differently from the staleness gate, which asks the same question to decide
whether to re-render.

**Explored**: Three candidates. (a) The file's `mtime_ns`: changes on `touch` and on a comment-only edit, so a
GUI would get 412s for edits that changed nothing editorial. (b) A hash of the file's bytes: same failure —
reformatting or a comment invalidates a held ETag. (c) The existing `editorial` fingerprint component, a hash
over `document.to_dict()`.

**Decision**: (c). Lift the existing expression into a named function and call it from both places:

```python
# auto_reel_ng/staleness/fingerprint.py
def editorial_hash(document: ReelDocument) -> str:
    """The fingerprint's ``editorial`` component: a hash over the document's canonical typed fields."""
```

`compute_fingerprint` calls it in place of the inline expression; `api/` calls it for the ETag. A regression
test pins a known document's four component hashes across the refactor.

**Rationale**: It is canonical over typed fields, so it changes when — and only when — the editorial state
changes, which is precisely the 412's question. Sharing one function makes disagreement between the ETag and
the staleness verdict structurally impossible rather than merely tested. It adds no fingerprint input and does
not alter any hash (Principle IV: no `RENDER_GRAPH_VERSION` bump).

### D-R2 — An event with no `reel.yaml` reads as the empty document (200, not 404)

**Context**: `apply_editorial_write` seeds `ReelDocument()` when the file is absent, so the write accepts an
event that has never been saved. The read has to decide whether to mirror that.

**Explored**: 404 (treat "no document" as "no resource"), versus 200 with the empty editorial document.

**Decision**: 200 with the empty document. The event *directory* is the resource; `reel.yaml` is its state.

**Rationale**: A 404 would force the GUI to special-case "never saved" by hand-constructing a write body — the
exact hand-construction this change exists to eliminate. Mirroring the write's seeding keeps read and write
accepting the same set of events.

### D-R3 — `If-Match` is optional, and `*` is honored

**Context**: The precondition must protect the GUI without breaking the scripted, CLI-equivalent clients the
`api-service` spec already guarantees.

**Explored**: Mandatory `If-Match` (rejected: breaks unconditional callers and cuts against Principle V's
CLI-reachability); a version field embedded in the request body (rejected: it would enter the editorial
vocabulary and land in `reel.yaml`, polluting the source of truth with transport bookkeeping).

**Decision**: Follow RFC 9110. Absent header → unconditional write, exactly as today. `If-Match: *` → succeeds
when the event resolves. A non-matching tag → `412` with a problem body, checked **before** the engine
operation runs.

**Rationale**: Standard HTTP conditional-request semantics rather than a bespoke mechanism, so the generated
TypeScript client (D-8) and `curl` both behave predictably, and existing clients observe no change at all.

### D-R4 — No conditional GET

**Context**: Emitting an ETag invites implementing `If-None-Match`/304 alongside it.

**Decision**: Do not. The ETag exists solely as the write precondition.

**Rationale**: Reads are scan-on-request by design (D-A3) — a fresh parse per call is the contract, not an
inefficiency to cache around — and a 304 branch is a second code path with no demonstrated need
(Principle VII). It can be added later without changing this contract.

### D-R5 — The read lives at the write's URL, not widened into the detail model

**Context**: The alternatives (widen `EventDetailOut`; make the write sparse/PATCH) are rejected in
`proposal.md` — Non-goals, on correctness grounds.

**Decision**: `GET` and `PUT` on `/api/v1/events/{event_id}/reel`, over one model.

**Rationale**: Beyond the proposal's argument, GET/PUT symmetry over a single model is what makes the contract
self-describing in the OpenAPI schema the GUI generates its types from (D-8): the generated client gets a
`getReel`/`putReel` pair over `EditorialDocumentBody`, so "what you read is what you may write" is enforced by
the type checker on the client side, not by GUI discipline.

## Failure behaviour

- **Unknown event** → 404 problem body, via the same `resolve_event_dir` path the detail and write routes use.
- **Unparseable `reel.yaml`** → the loud problem body the detail route already produces; never an empty or
  partial document (Principle I).
- **`If-Match` mismatch** → 412 problem body, evaluated **before** `apply_editorial_write` is called, so no
  partial write is possible and the operation's own validate-then-persist guarantee is untouched.
- **No new failure mode reaches the engine.** The engine operation's signature and behaviour are unchanged.

## Idempotency

- `GET` is safe and idempotent: it never creates `reel.yaml`, never writes a render manifest, never enqueues.
- `PUT` keeps its existing idempotency — the same body applied twice leaves `reel.yaml` byte-for-byte
  identical. With `If-Match`, a replayed PUT of a **no-op** body still succeeds (a no-op does not move the
  ETag), while a replayed PUT of a **real edit** returns 412 (the first write moved it). That asymmetry is the
  intended protection, not a defect.
- Nothing here renders: there is no `--force` interaction, no worker involvement, and no manifest write. The
  staleness consequence of an editorial write is exactly as before.

## Risks / Trade-offs

- **Extracting `editorial_hash` could silently alter the fingerprint** → A test pins a known document's four
  component hashes and the combined hash across the refactor. Drift would make every rendered event stale —
  loud, but expensive to discover late.
- **A GUI holding an ETag across a long editing session will see 412s when another writer touches the event**
  → The 412 is the correct answer; recovery is client-side (re-read, re-apply, retry) and is specced as a
  scenario. Single-user v1 makes it rare.
- **The precondition costs one extra parse of `reel.yaml` per conditional PUT** → Negligible on a probe-free
  path, and it keeps the check in `api/` where Principle V wants it. Threading the hash out of the engine
  operation was rejected as leaking a transport concern into the engine.
- **Optional `If-Match` gives a naive client no protection** → Accepted for v1 (D-R3): the GUI is the client
  that matters and will send it; mandating it would break scripted callers.

## Migration Plan

None required. No `reel.yaml` or `config.yaml` schema change, no Postgres schema change, no Alembic revision,
no rescan, no manifest rewrite. The change is purely additive to the HTTP surface: a client that never sends
`If-Match` observes identical behaviour before and after. Rollback is reverting the commit.

## Open Questions

- Whether the GUI presents a 412 as a merge UI or as a "reload and re-apply your edit" prompt is a decision for
  the GUI change; it affects neither these specs nor this change's tasks.
