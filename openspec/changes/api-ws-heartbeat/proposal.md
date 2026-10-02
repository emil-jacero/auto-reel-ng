## Why

The header says "Live" for as long as the browser's WebSocket object has not fired `close`. A connection that
died without a close (a laptop that slept and woke on a dead network, a NAT that dropped the flow, a service
that was killed without a FIN) stays open to the browser for minutes, and an idle healthy connection looks
exactly like it: the service sends a frame only when a job changes, so a quiet minute carries no traffic
either way. The operator reads "Live", sees no progress, and trusts a render panel that is no longer being
fed. HLD §4.10 ("Live progress needs no library") and D-A4 make the socket the only source of live job
state, so its liveness has to be observable by the client. The service's own keepalive pings (every 20 s, `api-service`) do not help: they are
answered by the browser's network stack and are invisible to page JavaScript.

Triage item `websocket-heartbeat-half-open-reads-live` (severity medium, user-visible), re-checked on `main`
`99224ab`: `WsMessageType` has only `snapshot` and `delta`; `_broadcast` runs only when `_tick` found
deltas; `web/src/jobs/store.ts` `connect()` reacts only to the socket's `close` and `error` events, and
`FRAME_TYPES` is `{snapshot, delta}`. There is no timer anywhere that notices silence.

HLD phase: §6 phase 8 (GUI v1), the live-job-state screens, hardening of the D-A4 channel. No §8 research
item is open.

## What Changes

- **api-service**: a third frame type, `heartbeat` (an empty job list), sent to a connection that has been
  sent no frame for 15 s. It is per connection and does not touch the hub's poller, its store reads or its
  queues. The published frame type set grows to `snapshot` | `delta` | `heartbeat`.
- **web-app**: the jobs store treats a connection that has delivered no frame for 40 s (counted from the
  socket's creation and from each frame) as lost: it drops the socket itself and takes the existing
  reconnect path, so the header reads "reconnecting" and the next snapshot reconciles the jobs. A heartbeat
  frame changes nothing on screen.
- `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated; the client's exhaustive frame-type
  `Record` forces the new type to be handled at compile time.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`: "WebSocket live job updates" gains the heartbeat frame; "Cancel outcome and WebSocket frame
  type are closed, published vocabularies" gains the third value.
- `web-app`: "The client follows render jobs live over one connection" gains the silence watchdog and the
  no-op heartbeat.

## Non-goals

- No server-side detection of a dead peer beyond the existing uvicorn keepalive (`api-service`, "A peer that
  stops answering..."); the heartbeat serves the client's detection only.
- No detection of a wedged poller: a heartbeat proves the connection and its handler, not that the hub's
  store reads are succeeding. The hub's failure handling is `jobshub-stop-and-db-timeouts`' concern.
- No config key and no CLI surface: both intervals are module constants (Principle VII); the WebSocket is API
  only and no engine behaviour changes (Principle V).
- No application-level ping from client to server, and no change to the "anything a client sends is
  ignored" rule.
- No change to reconnect backoff, the snapshot-reconcile rule, or what any screen shows.

## Impact

- **Rendered output / fingerprint**: unchanged for identical inputs; no `RENDER_GRAPH_VERSION` bump and no
  fingerprint input changes.
- **Schema**: no `reel.yaml` or `config.yaml` change; no Alembic migration or rescan. The published OpenAPI
  schema changes (one enum value), so `web/openapi.json` and `web/src/api/schema.d.ts` are regenerated.
- **Packages**: `auto_reel_ng/api` (`ws.py`, `schemas.py`) and `web/` (`src/jobs/store.ts`, generated
  files). API only; the CLI is not touched.
- **Compatibility**: a client bundle that predates this change treats an unknown frame type as malformed and
  reconnects. The service serves its own bundle, so a cached old tab sees a reconnect loop with growing
  backoff until it is reloaded (design, Risks).
- **Ordering**: `ws.py` was also edited by `jobshub-stop-and-db-timeouts`, now on `main` (design, "Context").
