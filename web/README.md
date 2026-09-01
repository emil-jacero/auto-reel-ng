# `web/` — the browser client (GUI v1)

React 19 + Vite + TypeScript, built ahead of time into static assets that
`auto-reel serve` mounts at `/` (decision **D-8**, HLD §4.10). **No Node process
exists at runtime** — the deployment stays the single Python process, and the
service starts normally when `dist/` is absent.

There is **no screen here yet**. `src/App.tsx` is a wiring check: it fetches
`GET /api/v1/events` through the generated types and renders the event count. The
event-list slice replaces it outright.

## The Node toolchain runs in podman

Nothing is installed on the host — the same arrangement as the containerized
Postgres test fixture. Run all four commands from the **repository root**:

```bash
# install dependencies (writes web/node_modules/ and web/package-lock.json)
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm install

# dev server on http://127.0.0.1:5173, proxying /api (and the WS) to the service;
# --network host is what lets the proxy reach 127.0.0.1:8080
podman run --rm --network host -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 \
    npx vite --host 127.0.0.1 --port 5173

# production build → web/dist/ (runs `tsc --noEmit` first)
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm run build

# the frontend gate on its own
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npx tsc --noEmit
```

`npm run dev` expects a running `auto-reel serve` on `127.0.0.1:8080` (its default
bind). Client code addresses the API **by path alone** — never an absolute base
URL — so the same code works behind the dev proxy and when the service serves the
built assets. Same origin either way; the service needs no CORS.

## Regenerating the API types

The client's types are **generated, never hand-written**. Two committed artifacts:

```
auto_reel_ng/api response models
        │  app.openapi()
        ▼
   web/openapi.json          ◄── pytest fails when this is stale
        │  openapi-typescript
        ▼
   web/src/api/schema.d.ts   ◄── tsc --noEmit fails when client code reads
        │                        what the types no longer describe
        ▼
      client code
```

After any change to an endpoint's request or response model, run **both**, from the
repository root:

```bash
.venv/bin/python -m auto_reel_ng.api.openapi > web/openapi.json
podman run --rm -v "$PWD/web:/app:Z" -w /app docker.io/library/node:22 npm run generate:types
```

Both files are committed. Hand-editing either is pointless — regenerating
overwrites it — and `tests/test_api_openapi.py` fails, naming the disagreement,
until `web/openapi.json` matches what the application produces.

## Dependency budget

`react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `typescript`, and
`openapi-typescript` (dev). **No component library, no CSS framework, no router,
and no state-management or data-fetching library at GUI v1.** Any addition must be
justified in the proposal of the slice that demonstrably needs it — the
drag-and-drop library arrives with the reorder slice, not here.

## Checks

`tsc --noEmit` is the whole frontend gate for GUI v1. There is deliberately **no
test runner and no browser automation**: the types are generated from the schema,
so drift is a compile error, and the API's behavior is covered by `pytest`. A later
slice with logic worth unit-testing may propose a runner, with its justification.
