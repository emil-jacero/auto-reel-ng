## Context

See proposal.md — Why. The constraints that shape the approach:

D-8 (§4.10) fixes the stack, the layout (`web/` at the repo root, the dev server proxying `/api`,
`create_app` mounting `web/dist` when it exists), the dependency budget, and that the Node toolchain runs
in podman. What it does not say is *how* the schema reaches the types, or what checks enforce the
"schema change becomes a build error" promise. That is this design's work.

Two existing facts make an offline schema dump possible. `create_app` builds its engine with
SQLAlchemy's `create_engine`, which does not connect — it is lazy, so an app can be constructed without a
reachable database. And FastAPI derives `app.openapi()` from the declared `response_model`s alone, which
every route already has (D-A1, and the API's own convention). So the schema is obtainable from a plain
Python process with no service, no container and no network.

`ApiSettings` is resolved from a project root; for a schema dump the root is irrelevant — no route is
called — but one must be supplied to construct the app.

## Goals / Non-Goals

**Goals:**
- One command regenerates the schema and the types; two independent checks fail when they are stale.
- The test suite and every development run work with no frontend build and no Node present.
- The client's API surface is derived, so removing a backend field breaks compilation at the line that
  reads it.

**Non-Goals (design level; see proposal.md for scope):**
- Serving the client from an installed wheel or container image (phase 11).
- A history fallback for client-side deep links (no router at v1).
- Any decision about how later screens fetch, cache or render data.

## Research & Decisions

### How the OpenAPI schema is produced

**Context**: `openapi-typescript` needs a schema. The obvious source is a running service's
`/openapi.json`, which would make type generation depend on a live service and a database.

**Explored**: (a) generate against a running service; (b) add an `auto-reel openapi` CLI subcommand;
(c) a small module in `api/` with a `__main__` entry point.

**Decision**: (c). A module — `auto_reel_ng/api/openapi.py` — exposing a function that builds an app from
throwaway settings and returns `app.openapi()`, plus `python -m auto_reel_ng.api.openapi` to write it to
stdout. The committed artifact is `web/openapi.json`.

**Rationale**: (a) is disqualified by CI: a type generation step that needs Postgres running is a step
that gets skipped. (b) would add a tenth `auto-reel` subcommand for a build-time concern no operator ever
runs, which Principle VII rejects — the CLI's subcommands are the product's surface, not its toolchain.
(c) keeps the entry point next to the app it describes and, critically, gives the drift test a **plain
function to call**: the test compares `web/openapi.json` against the same function's output, with no
subprocess and no Node.

### Where the drift check lives

**Context**: The promise is "a backend schema change becomes a frontend build error". A `tsc` failure
only appears if the generated types were regenerated; if nobody regenerates, `tsc` passes against stale
types and the drift is silent — the exact failure mode D-8 chose React to avoid.

**Decision**: Two checks, on the two sides of the committed schema.

```
    api/ response models
            │  app.openapi()
            ▼
   web/openapi.json  (committed)  ◄── pytest: regenerate and compare → fails on backend drift
            │  openapi-typescript
            ▼
   web/src/api/schema.d.ts (committed)
            │
            ▼
      client code  ◄── tsc --noEmit → fails when client code reads what the types no longer have
```

**Rationale**: The Python check is the one that matters and it is the one that runs in the existing
suite — a developer who changes a response model and never opens `web/` still gets a failure, with no
Node involved. `tsc` then catches the second half: code that reads a field the regenerated types dropped.
Neither check can be satisfied by hand-editing a generated file, because regenerating overwrites it.

**Alternative rejected**: generating types in CI and diffing, without committing them. It makes `tsc`
unrunnable from a clean checkout without Node, and hides the API surface from code review.

### How `web/dist` is located

**Context**: The mount needs a path. `web/dist` is a sibling of the installed package in a checkout and
absent from a wheel, and D-8 defers packaging to phase 11.

**Explored**: an `ApiSettings` field (D-2 layered), a `create_app` keyword argument, and a module-level
resolver function.

**Decision**: A module-level function in `api/` returning the checkout path (`web/dist` relative to the
package's parent), which `create_app` mounts **only if the directory exists**. Tests monkeypatch the
function.

**Rationale**: A settings field would be a configuration key with no operator use — there is exactly one
correct answer per deployment and the operator never chooses it (Principle VII: a new key needs a real
use). A `create_app` argument is the same complexity with worse discoverability. A function is one
symbol, is the natural seam for tests, and is the single place phase 11 edits when the assets move into
the package.

### Mount ordering and what the mount may serve

**Decision**: The client SHALL be mounted **after** every router is included, so route matching reaches
the API routes, `/healthz` and the WebSocket first and the mount only handles what is left. The mount
SHALL serve the built directory's contents and nothing above it.

**Rationale**: Starlette matches routes in registration order, so ordering is the whole mechanism — it
is stated as a requirement with its own scenario because a future refactor that moves the mount earlier
would silently answer `/api/v1/events` with `index.html`. Serving only the built directory is the
standard static-files guarantee; the scenario exists so it is asserted rather than assumed.

**No history fallback**: with no router at v1 (D-8) there are no client-side deep links, so an unknown
path correctly 404s. When a router arrives, the fallback arrives with it, in that slice.

### What the scaffold's page does

**Context**: A scaffold with no page proves nothing at runtime — the mount, the proxy and the generated
types would all be unexercised until the first screen slice.

**Decision**: One page that fetches `GET /api/v1/events` through the generated types and renders the
**count** of events. It is a wiring check, not a screen: the event-list slice replaces it entirely.

**Rationale**: It is the smallest client that exercises all four things at once — the dev proxy, the
same-origin fetch, a generated response type, and the mount. `/healthz` was considered and rejected: it
returns a hand-built response with no `response_model`, so it proves nothing about generated types.
Rendering a count rather than a list keeps the event-list slice's design decisions entirely in that
slice.

### Failure behavior and idempotency

**Decision**: A missing `web/dist` is not an error — the service starts, logs nothing alarming, and
serves the API. A malformed or partial build is out of scope for detection: the mount serves what is
there, because a half-built directory is a developer's own local state, not a condition the service can
meaningfully distinguish. Neither the schema dump nor the mount reads or writes any event, `reel.yaml`,
manifest or database row.

**Idempotency**: regenerating the schema and the types is deterministic — the same application code
produces byte-identical output, which is what makes the drift test a comparison rather than a heuristic.
Building the client repeatedly is idempotent. Starting the service twice against the same build serves
the same assets; nothing is written at startup.

## Risks / Trade-offs

- **Generated files in review diffs.** `web/openapi.json` and `schema.d.ts` change whenever a response
  model does, adding noise to the diff. → Accepted deliberately: the noise *is* the signal that a client
  contract moved, and it is what makes the change visible to a reviewer who only reads Python.
- **A developer regenerates the schema without regenerating the types.** `pytest` passes, `tsc` passes
  against types that no longer match the schema. → Both are produced by one documented command, and the
  window is one commit wide; a test runner cannot close it without putting Node in `pytest`, which this
  slice explicitly refuses.
- **The mount resolves a development path.** An installed wheel finds no `web/dist` and serves no
  client. → Intended (D-8 defers packaging to phase 11), and the "no build present" requirement makes
  that a supported state rather than a break.
- **`tsc` alone is a thin gate.** Nothing checks that the page renders. → Correct for a slice whose page
  is a wiring check that the next slice deletes; the first slice with real logic can propose a runner.

## Migration Plan

Purely additive. No database migration, no rescan, no `RENDER_GRAPH_VERSION` bump, no `reel.yaml` or
`config.yaml` change, and no change to any endpoint. Existing deployments are unaffected: without a
build, the service is byte-for-byte the service it was. Rollback is deleting `web/` and the mount.

Two things outlive the change and belong in `docs/high-level-design.md` §4.10 rather than only here: the
schema → committed JSON → generated types → two checks pipeline, and that **`tsc --noEmit` is the
frontend gate for GUI v1** with no test runner or browser automation. Both extend D-8's existing text;
neither is a new locked decision.

## Open Questions

- **npm versus another package manager inside the container.** `npm` ships with the `node:22` image and
  needs no extra install step, so this slice uses it. Switching later changes a lockfile and a command,
  not the specs, the approach or the task breakdown.
