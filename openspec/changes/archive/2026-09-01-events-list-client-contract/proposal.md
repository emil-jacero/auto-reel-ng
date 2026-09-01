## Why

The GUI v1 slice plan (HLD §6 phase 8, §4.10) puts the **event list screen** next — slice B, the first
real screen, over the verdicts `events-list-staleness` added. Exploring that screen against the shipped
API surfaced two gaps in the events **list** response, both of which the screen would have to work
around and both of which belong to `api/`, not to a frontend slice.

**1. A database outage is unshaped on both events reads.** `GET /api/v1/events` has no error handling at
all: a database outage (the list reads `latest_job`) or a scan/probe failure propagates to a bare
`500 {"detail":"Internal Server Error"}`. `GET /api/v1/events/{event_id}` reads `latest_job` too and maps
`ReelError` to a 502 problem body, but leaves a database failure equally bare. D-A6 chose one problem
shape precisely so a client parses errors uniformly; a screen that **fails hard** on a backend outage
therefore cannot say *why* it failed, and cannot distinguish "the database is down" from "a `reel.yaml`
is malformed" — a distinction Principle I exists to preserve.

**2. `staleness.reasons` is typed `List[str]`.** The vocabulary is closed — the four fingerprint
components plus `no_manifest` and `output` — but the OpenAPI schema publishes it as an untyped string
array, so `openapi-typescript` generates `string[]`. Every client that renders a reason humanizes it
through a hand-maintained map, which is exactly the hand-maintained schema ⇄ view mapping D-8 rejected
htmx to avoid. Renaming a component in the engine would leave `pytest`, the schema drift test and
`tsc --noEmit` all green while the UI silently degraded to raw slugs. This is the first hole found in
D-8's "a backend schema change becomes a frontend build error" promise, and it is cheapest to close
before the first screen depends on it rather than after three do.

Both are one route and one field. Doing them here keeps slice B a pure frontend change (Principle VIII)
instead of smuggling backend edits inside a screen.

## What Changes

- **The staleness reason vocabulary becomes a closed, named type in `staleness/`.** The six reasons the
  gate can cite (`no_manifest`, `output`, and the four fingerprint components `editorial`, `defaults`,
  `clip_set`, `engine`) become an enumeration alongside the existing `NO_MANIFEST` / `MISSING_OUTPUT` /
  `COMPONENTS` constants, which it replaces rather than duplicates. The gate keeps producing exactly the
  strings it produces today — **the wire values do not change**.
- **`StalenessOut.reasons` is typed with that enumeration**, so the OpenAPI schema publishes the closed
  set and the generated TypeScript becomes a union rather than `string[]`. A client that switches on a
  reason gets exhaustiveness; a renamed component becomes a `tsc` error.
- **Both events reads fail in the shared problem shape.** On `GET /api/v1/events` and
  `GET /api/v1/events/{event_id}`, an unreachable job store maps to a problem body naming the database as
  the failing dependency — the shape `/healthz` already uses — and on the list an engine scan/probe
  failure maps to the same 502 problem body the detail route already returns. One mapping, applied to the
  two events reads that touch the job store.
- **`web/openapi.json` and `web/src/api/schema.d.ts` are regenerated** — the reasons field's schema
  changes, so both committed artifacts move and the drift test proves the pipeline works exactly as
  `web-app-scaffold` designed it.

## Non-goals

- **No screen.** Slice B is the next change; nothing in `web/` changes here beyond the two regenerated
  artifacts.
- **No new reason.** The vocabulary is closed at what the gate already emits; no reason is added,
  removed, split or renamed, and no wire value changes.
- **No change to how staleness is decided.** The gate, the fingerprint, its four components and the
  manifest are untouched — this change types what they already say.
- **No error-shape work beyond the two events reads.** The jobs routes, the editorial read/write
  endpoints, the analysis route, the WS endpoint and `/healthz` keep the behavior they have. Only the
  database-unavailable path on the two routes that read the job store, and the list's missing scan-failure
  mapping, are added.
- **No new endpoint, no CLI change, no scheduler or persistence change.**
- **No retry, degradation or partial response.** A list request that cannot be answered fails loud with
  a problem body (Principle I); it MUST NOT return a jobless or partial list.

## Capabilities

### Modified Capabilities
- `api-service`: the events list gains a failure requirement — an unavailable database or a failed scan
  yields the shared problem body naming which occurred, never a bare 500 and never a partial list; and
  the staleness verdict's reasons are required to be a closed set the schema publishes.
- `change-detection`: the staleness gate's reasons are required to come from a closed, named vocabulary
  rather than free-form strings, so the contract the API publishes has a single source of truth in the
  engine.

## Impact

- **Packages:** `staleness/` (the reason enumeration, replacing two loose constants) and `api/` —
  `schemas.py` (one field's type) and `routes/events.py` (one shared database-failure mapping on the two
  events reads, plus the list's missing scan-failure mapping). Nothing else below `api/` is touched.
- **CLI vs API (Principle V):** no CLI surface changes. `scan` and `render` already print gate reasons
  and keep printing the same strings; the API gains no behavior the CLI cannot reach.
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump** — the enum is
  a type over existing values and no fingerprint input, component or sub-hash changes.
- **Staleness fingerprint inputs:** unchanged.
- **Schemas:** no `reel.yaml` change, no project `config.yaml` change, **no Alembic migration**, no
  rescan. `render-manifest.json` is unchanged — reasons are computed, never persisted.
- **Generated artifacts:** `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated; both are
  committed, and `tests/test_api_openapi.py` fails until they are.
- **Dependencies (Principle VII):** none added. The enumeration is `enum.StrEnum` from the standard
  library, which pydantic and FastAPI already serialize as a schema `enum`.
- **Size (Principle VIII):** one enumeration, one field annotation, one shared error mapping across two
  routes, two regenerated artifacts.
