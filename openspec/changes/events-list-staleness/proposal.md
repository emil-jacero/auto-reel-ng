## Why

GUI v1 (HLD **§6 phase 8**, stack locked as **D-8**, §4.10) opens on the scan/ingest view: every event
under the project root, listed. The operator's first question at that screen is the only question the
list exists to answer — **which of these need a render?** The staleness gate (change-detection, §8.14)
computes exactly that verdict, and `GET /api/v1/events/{event_id}` already returns it. The **list**
response does not.

That is the wrong endpoint to withhold it from. `EventSummaryOut` carries `clip_count`, `new_count`,
`missing_count` and `latest_job` — everything except the verdict the gate exists to produce. A list
screen therefore has three ways to learn what is stale, and all three are bad:

1. **Fan out to detail.** One `GET /events/{id}` per row, each re-walking that event's directory and
   re-parsing its `reel.yaml`. The list already did that walk once.
2. **Infer from `latest_job`.** A completed job is not freshness — the clips may have changed since,
   which is the entire premise of §8.14. This reproduces the legacy failure mode (HLD §2, problem 8):
   the operator tracks what needs re-rendering **in their head**, because the tool will not say.
3. **Click Render and see.** `POST /api/v1/jobs` answers `200 FreshResult` for a fresh event, so the
   button becomes the discovery mechanism — one write request per event to learn a read fact.

The gate was built to answer this in bulk. `scan` already prints staleness per event for exactly this
reason; the API's list is the same read surface for the GUI, and it is the one client that cannot fall
back to reading a terminal.

**The blocker is not the schema field — it is a latent N× cost in `staleness_for`.** That helper
resolves the project's look defaults itself:

```python
look_defaults = resolve_look_defaults(load_project_config(settings.project_root))
```

`load_project_config` is uncached: it re-reads and re-parses `config.yaml` on every call. With two
call sites that each handle **one** event (detail, editorial write) that is invisible. Dropped into
`list_events`' per-event loop unchanged, it becomes one YAML read + parse **per event per request** to
re-derive a value that is identical for every row. The project's look defaults are a per-request fact,
not a per-event one, and this change makes the code say so before the loop exists to punish it.

## What Changes

- **`EventSummaryOut` gains `staleness`** — the same `StalenessOut` (`stale` + `reasons`) the detail
  response carries, computed per event by the existing gate. `GET /api/v1/events` answers "what needs
  rendering?" in one request.
- **`staleness_for` takes its per-request inputs as parameters** rather than resolving them itself:
  the resolved look defaults are computed **once** per request and passed in. The detail and editorial
  write call sites resolve them at the route and pass them down, keeping one code path.
- **The list SHALL NOT use the content-hash opt-in.** `compute_fingerprint(use_hash=True)` reads every
  clip's bytes to sha256 them. Nothing in `api/` passes it today, so this is written down as a
  requirement rather than left as an accident: a read endpoint over the whole library must never become
  a full-library content read.
- **No new endpoint, no new query parameter, no probe, no write.** The list stays read-only and
  probe-free; the per-clip file facts stay on the detail response only.

## Non-goals

- **No `?staleness=` toggle.** An opt-in flag is a second code path and an option bag for a parameter
  the GUI would always set (Principle VII). The list either answers the question or it does not.
- **No caching of the verdict, and no DB column for it.** Staleness is derived from disk and MUST stay
  rebuildable from disk (Principle II); a cached verdict is a second source of truth for a fact whose
  whole purpose is being current.
- **No de-duplication of the directory walk.** `list_events` walks each event once for reconcile, and
  `compute_fingerprint`'s clip-set component walks it again. Removing the second walk is an
  optimization with no measurement behind it yet (Principle VII) — this change measures it instead
  (design.md), and a follow-up may act on the number.
- **No GUI.** No `web/` directory, no frontend dependency. This is the `api/` prerequisite that lands
  before the GUI v1 scaffold slice.
- **No change to `scan`, `render`, `enqueue` or the worker.** They already have the verdict.

## Capabilities

### Modified Capabilities
- `api-service`: `Requirement: Events read model is scanned from disk per request` extends the events
  **list** response with the per-event staleness verdict, and bounds how it is computed — the resolved
  look defaults are a per-request value, and the fingerprint stays on its probe-free, hash-free path.

## Impact

- **Packages:** `api/` only — `schemas.py` (one field on `EventSummaryOut`), `events_read.py`
  (`staleness_for` signature, `list_events` loop), `routes/events.py` (the list route passes
  `app.state.runtime`, as the detail route already does). Nothing below `api/` changes: `staleness/`,
  `config/` and `persistence/` are called exactly as they are.
- **CLI vs API (Principle V):** API-only, and it adds **no** behavior the CLI lacks — `auto-reel scan`
  already reports staleness with reasons per event. This closes a gap where the API was *behind* the
  CLI, which is the allowed direction.
- **Rendered output:** unchanged for identical inputs. **No `RENDER_GRAPH_VERSION` bump.**
- **Staleness fingerprint inputs:** unchanged. The same four components are hashed from the same
  sources; only the number of call sites changes.
- **Schemas:** no `reel.yaml` change, no project `config.yaml` change, **no Alembic migration**, no
  rescan required. The response shape gains a field, which is additive for existing clients.
- **Dependencies:** none added (Principle VII).
- **Size (Principle VIII):** one package, one response shape, one helper signature, one capability
  spec.
