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

## A library to develop against

The shared fixture holds one event, which cannot show what the screens must render.
`scripts/make_dev_library.py` builds a small real-footage library from it (the fixture
is only read). It cuts 6 s stream-copied clips and lays out 9 events across 2023 and
2024. Part of the library is rendered through the real queue, then disk is edited so
the list shows every state:

- fresh, and stale for `editorial`, `output`, `clip_set` and `no_manifest`
- NEW and MISSING clips
- an undated event
- a same-name output clash (`2024-07-14 - Kalas` and `2024-07-15 - Kalas`)
- latest jobs that are `done`, `failed` and `queued`

The service needs Postgres even to list events (the list carries each event's latest
job). One-time setup, from the repository root:

```bash
# a persistent dev database at the dev-default URL (named volume survives restarts)
podman run -d --name auto-reel-ng-dev-db \
    -e POSTGRES_USER=auto_reel_ng -e POSTGRES_PASSWORD=auto_reel_ng -e POSTGRES_DB=auto_reel_ng \
    -v auto-reel-ng-dev-db:/var/lib/postgresql/data -p 127.0.0.1:5432:5432 \
    docker.io/library/postgres:16-alpine
.venv/bin/python -m alembic upgrade head

# build (or rebuild from scratch) the library beside the fixture
.venv/bin/python scripts/make_dev_library.py ../auto-reel-dev
```

Then run the service against it and the dev server as above, and open
<http://127.0.0.1:5173/>:

```bash
.venv/bin/auto-reel serve ../auto-reel-dev/library   # after a reboot: podman start auto-reel-ng-dev-db
```

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
