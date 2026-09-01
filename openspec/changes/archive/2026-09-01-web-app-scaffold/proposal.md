## Why

GUI v1 is HLD **§6 phase 8**, and its stack is locked as **D-8** (§4.10): React 19 + Vite + TypeScript,
built to static assets and served by the FastAPI process, under a hard dependency budget. Every backend
prerequisite is now in place — `editorial-write-api`, `editorial-read-api` and `gui-event-screen-api-prep`
closed the write precondition and the per-clip file facts, and `events-list-staleness` gives the list the
verdict a scan view exists to show. There is no `web/` directory, so phase 8 has not started.

D-8 makes one promise that has to be built before any screen, or it cannot be added later without
retrofitting every screen at once: **a backend schema change becomes a frontend build error.** That was
the deciding argument for React over htmx — hand-maintaining a template ⇄ schema mapping was judged the
larger maintenance cost. The promise is only real if the OpenAPI schema, the generated TypeScript, and
the check that they agree all exist from the first commit. Bolt type generation onto three finished
screens later and the intervening period is exactly the silent-runtime-drift the decision was made to
avoid.

The same is true of the two other pieces of wiring D-8 specifies: the service mounting the built assets,
and the dev server proxying `/api` to it. Both are load-bearing for every later slice, both are cheap,
and neither is testable through a screen. Doing them as their own slice keeps the screen slices about
screens.

**This slice deliberately ships no screen.** GUI v1's first screen — the event list — is the next change.
What ships here is the wiring, plus the smallest possible client that proves the wiring end to end.

## What Changes

- **A `web/` directory at the repository root**: Vite + React 19 + TypeScript, built with the Node
  toolchain running in podman (`node:22`), mirroring how the containerized-Postgres test fixture keeps
  tooling off this immutable host. Nothing is layered onto the host, and no Node process exists at
  runtime.
- **The OpenAPI schema becomes a committed artifact.** A small module dumps `create_app(...).openapi()`
  to `web/openapi.json`; `openapi-typescript` generates the TypeScript types from that file. A test in
  the existing Python suite regenerates the schema and fails when the committed file disagrees, so a
  backend response-shape change is caught by `pytest` and the stale types are caught by `tsc`.
- **`create_app` serves the built client.** When `web/dist` exists, the app mounts it at `/`; when it
  does not, the service behaves exactly as it does today. Dev runs and the whole test suite therefore
  never require a frontend build.
- **A wiring check, not a screen.** The client renders one line: the number of events returned by
  `GET /api/v1/events`, read through the generated types. It exercises the proxy, the same-origin fetch,
  the generated types and the mount in one page — and the event-list slice replaces it outright.
- **`tsc --noEmit` is the frontend gate for GUI v1.** Type-checking is the whole frontend check: the
  types are generated from the schema, so drift is a compile error, and the API's behavior is already
  covered by pytest. No test runner and no browser automation are added; a later slice that grows logic
  worth unit-testing may propose one, with its justification.
- **Dependencies added** (D-8's budget, minus what this slice does not need): `react`, `react-dom`,
  `vite`, `@vitejs/plugin-react`, `typescript`, and `openapi-typescript` as a dev dependency. **No
  drag-and-drop library** — that arrives with the reorder slice that needs it. No component library, no
  CSS framework, no router, no state or data-fetching library.

## Non-goals

- **No screens.** No event list, no event detail, no reorder, no metadata form, no job progress. Each is
  its own slice.
- **No client-side routing**, so no SPA history fallback. D-8 forbids a router at v1; the mount serves
  `index.html` for the root and static files, and nothing needs a deep-link rewrite until a router
  exists.
- **No packaging of `web/dist`** into the wheel or the container image — D-8 defers that to §6 phase 11.
  The mount resolves the development checkout's `web/`; making it work from an installed package is
  phase 11's problem, not this slice's.
- **No authentication or CORS work.** The client is same-origin by construction, and the no-op
  `AuthChecker` (D-A8) is unchanged.
- **No engine, CLI, scheduler or database change.** No new `auto-reel` subcommand.
- **No frontend test runner** (vitest) and **no browser automation** (Playwright).

## Capabilities

### New Capabilities
- `web-app`: the browser client — how it is built, how its API types are derived from the service's own
  schema, how a schema change is forced to surface as a build failure, and what it may depend on.

### Modified Capabilities
- `api-service`: gains a requirement that the service serves the built web client when it is present and
  runs unchanged when it is not, without shadowing any API route.

## Impact

- **Packages:** `web/` (new) and `api/` — `app.py` (a conditional mount) plus a new module that dumps the
  OpenAPI schema. No route changes, no schema changes, nothing below `api/` touched.
- **CLI vs API (Principle V):** `auto-reel serve` is unchanged and is how the CLI reaches this; the
  service gains no behavior the CLI cannot start. No endpoint logic is added.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.**
- **Staleness fingerprint inputs:** unchanged.
- **Schemas:** no `reel.yaml` change, no project `config.yaml` change, **no Alembic migration**, no
  rescan. `web/openapi.json` is a new committed artifact describing the API as it already is.
- **Dependencies (Principle VII):** six npm packages, all named in D-8's budget, none at Python runtime.
  `openapi-typescript` is the one that carries this slice's argument: it is what makes the schema ⇄ types
  agreement mechanical instead of manual.
- **Size (Principle VIII):** two packages, one conditional mount, one generated artifact, one page that
  the next slice deletes.
