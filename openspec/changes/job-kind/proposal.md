## Why

GUI v2 generates clip proxies as background work. The locked decision is that this is a job of a new kind
`proxy`, per event, on the CPU pool, behind renders (HLD §4.10, GUI v2 locked decisions; research
`v2/synthesis.md` §3 "Generation" and §5 row 1). The durable queue cannot hold it today: research item X8
found that `ux_jobs_active_identity` is unique on (`project_root`, `event_dir`) for `queued`/`running`
with no `kind` column, so a proxy job for an event would be refused while a render of that event is active
(and the reverse), and the worker treats every claimed row as a render. Research risk 7 names this
migration as one that "would block renders" if wrong, which is why it ships alone, first, and must leave
render behaviour byte-identical.

This is a prerequisite slice of the GUI v2 phase (HLD §6 item 9). No proxy code lands here.

## What Changes

- The `jobs` table gains `kind` (text, not null, default `render`). Existing rows become `render`.
  New migration, with a downgrade.
- The unique-active index becomes per (`project_root`, `event_dir`, `kind`): one active job per event
  **per kind**. A render and a proxy job for one event may be active together; two of one kind may not.
- `JobStore.submit` / `enqueue` / `active_job` take a `kind` (default `render`); idempotent enqueue is
  decided per kind. `claim_next` is unchanged and claims across kinds by the existing priority order.
- The store's read surfaces that feed render-facing answers (`list_by_status`, `list_finished_since`,
  `latest_by_project`) take a `kind` filter that **defaults to `render`** (`None` = every kind), so an
  existing caller, the API, the WebSocket poller and the CLI, keep returning exactly what they returned.
- The worker dispatches a claimed job by its kind: `render` takes the existing path untouched; any other
  kind runs the handler registered for it; a kind with no handler (including every kind in this change
  other than `render`, and any value this build does not know) fails the job loud, without taking a
  capacity token or touching the engine.
- The claim-time "another running job writes this output" check considers running **render** jobs only.
- HLD notes (see tasks).

**Unchanged by design:** rendered output (no `RENDER_GRAPH_VERSION` bump), the staleness fingerprint and its
inputs, `reel.yaml` / `config.yaml` schema, the CLI surface, the HTTP API, the OpenAPI schema, and WebSocket
frames. The API exposure of `kind` (job read model, frames, the enqueue endpoint) is the later
`proxy-enqueue-endpoint` change.

**Migration:** one Alembic revision (additive column with a server default, index swap). No rescan: the
jobs table is derived state (Principle II), and existing rows are backfilled by the column default.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `job-store`: the job schema carries a `kind` and the one-active-job guarantee is per kind; enqueue and
  the active-job lookup take a kind; the status, finished-since and latest-per-event reads are scoped to a
  kind, defaulting to `render`.
- `job-scheduler`: the worker dispatches by job kind and fails an unhandled kind loud; the running-output
  collision check counts render jobs only.

## Impact

- Packages: `persistence/` (`models.py`, `job_store.py`, new Alembic revision) and `scheduler/`
  (`worker.py`). No change to `api/`, `cli/`, `render/`, `staleness/`, or `web/`; no web type regeneration.
- No new dependency. CLI and API are not touched (Principle V: the CLI/API surfaces for proxies arrive with
  the engine capability in `proxy-encode` and `proxy-enqueue-endpoint`).
- Complexity added (Principle VII): one column, one enum, one handler mapping on the worker. Each has a
  caller in the next two GUI v2 changes; none is speculative plumbing beyond the `kind` the locked
  decisions already require.

## Non-goals

- Proxy encoding, the proxy cache, `facts.json`, `ensure_proxy`, the `proxy` handler itself, or the CPU
  pool's use by it (`proxy-encode` and the proxy job change).
- Exposing `kind` on the API, in `JobOut`, in WebSocket frames, or in `auto-reel jobs list`.
- A `priority` argument on `submit` for "lower priority than renders": `priority` is already a column and
  `claim_next` already orders by it; the proxy enqueue path adds the argument where it first has a use.
- Per-kind concurrency limits or pools; a database-level constraint on the set of kinds.
