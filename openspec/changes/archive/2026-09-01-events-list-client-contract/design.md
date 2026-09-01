## Context

See proposal.md — Why. The facts that shape the approach:

`staleness/gate.py` already owns the reason vocabulary, but as two loose module constants
(`NO_MANIFEST = "no_manifest"`, `MISSING_OUTPUT = "output"`) plus, implicitly, the four names in
`fingerprint.COMPONENTS` — the gate builds a reason list by appending component names as plain strings,
so the closed set exists in the code's behavior but nowhere in its types. `Verdict.reasons` is
`tuple[str, ...]`.

`api/schemas.py` mirrors that with `StalenessOut.reasons: List[str]`, which is what FastAPI publishes and
`openapi-typescript` turns into `string[]`.

On the error side, `api/problem.py` already provides the whole vocabulary this change needs
(`service_unavailable` → 503 with an `extra` field, `bad_gateway` → 502), and `/healthz` already reports
an unreachable database as `503` with `check="database"`. Two events reads touch the job store:
`get_events` catches nothing at all, and `get_event` catches `EventNotFoundError`/`EventReadError` but not
a database failure.

## Goals / Non-Goals

**Goals:**
- One source of truth for the reason vocabulary, in the layer that owns it, expressible in the OpenAPI
  schema and therefore in generated client types.
- A database outage reported identically by both events reads, in the shape `/healthz` already uses.
- Zero change to any wire value, status code or response body on the success path.

**Non-Goals (design level; see proposal.md for scope):**
- Any change to how staleness is decided, or to what the gate cites and when.
- A general exception-mapping middleware. Only the two reads named in the specs gain a mapping.
- Reworking `problem.py`; it already has the shapes this needs.

## Research & Decisions

### Where the reason vocabulary lives and what type it is

**Context**: The API must publish a closed set, but `api/` MUST NOT own the vocabulary (Principle VI:
lower layers own their concepts; the API serializes them).

**Explored**: (a) a `Literal[...]` alias in `api/schemas.py`; (b) a plain `enum.Enum` in `staleness/`;
(c) an `enum.StrEnum` in `staleness/gate.py` replacing the two existing constants.

**Decision**: (c). `StalenessReason(StrEnum)` in `staleness/gate.py`, with six members — `NO_MANIFEST`,
`OUTPUT`, and one per fingerprint component — replacing the `NO_MANIFEST` / `MISSING_OUTPUT` constants.
`Verdict.reasons` becomes `tuple[StalenessReason, ...]`.

```python
class StalenessReason(StrEnum):
    """The closed set of reasons a stale verdict may cite."""

    NO_MANIFEST = "no_manifest"   # no manifest to compare against
    OUTPUT = "output"             # the manifest's recorded output file is gone
    EDITORIAL = "editorial"       # ─┐
    DEFAULTS = "defaults"         #  │ one per fingerprint component,
    CLIP_SET = "clip_set"         #  │ in COMPONENTS order
    ENGINE = "engine"             # ─┘
```

**Rationale**: (a) puts the vocabulary in the wrong layer and duplicates it. (b) would break every
existing consumer: the CLI formats reasons into output and tests compare them to strings, and a plain
`Enum` member is not a `str`. **`StrEnum` members are `str`**, so every existing comparison, f-string,
`", ".join(...)` and JSON serialization keeps working unchanged — which is what makes "no wire value
changes" true by construction rather than by care. Replacing the constants rather than adding beside them
avoids a second source of truth, which is the whole point.

### Keeping the enum and `COMPONENTS` from drifting

**Context**: The component members are written out by hand but must equal `fingerprint.COMPONENTS`
exactly. A future fifth component would be added to `COMPONENTS` and silently not to the enum, and the
gate would then try to cite a component with no member.

**Explored**: deriving the enum dynamically from `COMPONENTS` (`StrEnum("StalenessReason", ...)`), versus
declaring members statically and asserting the relationship in a test.

**Decision**: Declare the six members statically; add a test asserting that the enum's component members
are exactly `COMPONENTS`, in order. The gate SHALL map a component name to its member (`StalenessReason(name)`),
so an unknown component raises `ValueError` at the gate rather than producing an untyped reason.

**Rationale**: A dynamically built enum has no static members, so mypy and the generated TypeScript both
lose the union — defeating the change. The static declaration plus one equality test gives the strict
types *and* a loud failure the moment a component is added without its reason.

### How the closed set reaches the client

**Context**: The requirement is that the schema publishes an enumeration and generated client code gets
an exhaustive union.

**Decision**: `StalenessOut.reasons: List[StalenessReason]`. pydantic emits the enum as a named schema
component with an `enum` list; `openapi-typescript` renders that as a string union. `api/` imports the
enum from `staleness/` — a downward import, which the layer rule allows.

**Rationale**: It is the smallest possible expression of the contract, and it makes the two committed
artifacts (`web/openapi.json`, `web/src/api/schema.d.ts`) move in the same change, exercising the
`web-app-scaffold` pipeline end to end for the first time on a real backend change. That is a deliberate
secondary benefit: this change is also the pipeline's first proof.

### How a database failure is mapped

**Context**: Both events reads may raise `SQLAlchemyError` from the job store. The list may additionally
raise `ReelError` from the scan, which the detail route already maps to 502.

**Decision**: A small shared helper in `routes/events.py` used by both reads: catch `SQLAlchemyError` →
`service_unavailable(..., check="database")`, the identical shape `/healthz` returns. The list
additionally catches `ReelError` → `bad_gateway(...)`, matching the detail route's existing mapping.
Nothing broader is caught.

**Rationale**: Reusing `check="database"` means a client has one predicate for "the service cannot reach
its database" across `/healthz` and both reads, rather than three shapes. Catching only the two typed
failures keeps Principle I intact: an unanticipated exception still surfaces as a 500 rather than being
dressed up as a known condition.

**Alternative rejected**: a FastAPI exception handler registered on the app for `SQLAlchemyError`
globally. It would silently change the jobs routes' behavior too — outside this change's specs, and a
behavior change nobody asked for.

## Failure behavior and idempotency

**What raises, what is reported**: a scan or probe failure raises out of the engine as it does today and
is reported per-request as a 502 problem body; a job-store failure is reported as a 503 problem body
naming the database. Neither is retried, and neither is softened into a value: the list MUST NOT return a
partial set, and `latest_job` MUST NOT be reported as absent because it could not be read (Principle I —
absence is reported, never fabricated). No response is assembled from a partially failed read, which
holds naturally because `list_events` builds the complete list before returning.

**Idempotency**: both reads stay read-only and side-effect free — no `reel.yaml`, no manifest, no
rendered output, no database row is written, so a re-run, a repeated failing request, and a request
during a worker restart all behave identically. `--force` has no meaning here; there is no gate decision,
only a reported verdict.

**Rendered output** is unchanged for identical inputs, so `RENDER_GRAPH_VERSION` is **not** bumped: the
enum types existing values and touches no fingerprint input, component or sub-hash.

## Risks / Trade-offs

- **`Verdict.reasons` changes type, and consumers compare it to strings.** → `StrEnum` makes members
  `str`, so comparisons, joins and serialization are unaffected; the existing gate/CLI tests are the
  proof, and they must pass unmodified. A test that asserts a reason's *type* rather than its value would
  need updating — none is expected to.
- **The drift test fails until both artifacts are regenerated.** → Intended, and the reason this change
  is worth doing before three screens exist. Regenerating both is the documented one-two command in
  `web/README.md`.
- **A hand-written enum can drift from `COMPONENTS`.** → The equality test above; a new component
  without its reason fails the suite rather than reaching the wire.
- **The 503 mapping could mask a bug that presents as a `SQLAlchemyError`.** → Only `SQLAlchemyError` is
  caught, and only around the read; a programming error raises its own type and still surfaces as a 500.
- **`web/src/api/schema.d.ts` regeneration needs the Node container.** → A developer without podman can
  still run the Python gates; `tsc` and the type regeneration are already container-only by D-8, and the
  drift test does not need Node.

## Migration Plan

Purely additive and backward-compatible on the wire. No database migration, no rescan, no
`RENDER_GRAPH_VERSION` bump, no `reel.yaml` or `config.yaml` change. An existing client that reads
`reasons` as plain strings sees identical bytes; a generated-types client gains a union where it had
`string[]`. Rollback is reverting the enum to the two constants and dropping the two `except` clauses.

One thing outlives the change and belongs in `docs/high-level-design.md` §4.10, extending the pipeline
text `web-app-scaffold` added rather than becoming a new locked decision: **a closed vocabulary must be
typed as an enumeration for the schema→types pipeline to cover it** — a bare `list[str]` is a hole the
two checks cannot see, and this change is the worked example.

## Open Questions

None. The two questions this change raised — whether the detail route is in scope, and whether the
vocabulary belongs to the gate or the API — were resolved before the specs were written.
