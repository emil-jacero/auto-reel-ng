## MODIFIED Requirements

### Requirement: `serve` runs the API service
`auto-reel serve` SHALL resolve API settings through the D-2 layering (`api.host` / `api.port` /
`api.poll_interval` from `config.yaml`, CLI flags override, defaults `127.0.0.1:8080`, 1 s) and run the
API service under uvicorn until SIGINT/SIGTERM triggers a graceful shutdown (WebSocket poller stopped,
connections closed, exit zero). A failure to bind SHALL exit non-zero naming the attempted host and port.

When one SIGINT or one SIGTERM has stopped the service and its orderly shutdown has completed, the command
SHALL exit with status 0 and SHALL NOT end with a traceback. This SHALL hold whichever of the two signals
stopped it, with or without WebSocket clients connected, and whether it runs in a terminal (Ctrl-C) or under
a supervisor that sends SIGTERM. A further SIGTERM while the shutdown is still running SHALL NOT change the
outcome.

A SIGINT that arrives while the shutdown is still running, whichever signal started it, is the operator's
force-quit: the service no longer waits for request handlers that are still running, and skips its
application shutdown if that has not started yet. When the command then ends, it SHALL exit with status
130, never 0, so that a forced stop is not reported as a clean one, and it SHALL NOT end with a
`KeyboardInterrupt` traceback of its own. A request handler that the forced stop cancels MAY still be
logged as an error.

#### Scenario: Serve starts and answers
- **WHEN** `auto-reel serve` runs against a project root and a reachable database
- **THEN** `GET /healthz` on the configured host/port returns success

#### Scenario: Flags override config
- **WHEN** `config.yaml` sets `api.port: 8080` and `auto-reel serve --port 9000` is run
- **THEN** the service binds port 9000

#### Scenario: Bind failure is loud
- **WHEN** the configured port is already in use
- **THEN** the command exits non-zero naming the attempted host:port

#### Scenario: One Ctrl-C stops serve with exit zero
- **WHEN** `auto-reel serve` runs in a terminal, a GUI tab showing the event list holds its jobs WebSocket
  open, and the operator presses Ctrl-C once
- **THEN** the tab's connection is closed with code 1012 and the service logs "Application shutdown complete"
- **AND** the command exits with status 0, and its output holds no traceback

#### Scenario: One SIGTERM stops serve with exit zero
- **WHEN** `podman stop` sends one SIGTERM to a running `auto-reel serve` with a WebSocket client connected
- **THEN** the client's connection is closed with code 1012, the service completes its orderly shutdown, and
  the command exits with status 0 without a traceback

#### Scenario: A second Ctrl-C forces the exit and reports it
- **WHEN** one Ctrl-C has started the shutdown of `auto-reel serve`, the shutdown is still waiting for a
  request handler that keeps running after its client left, and the operator presses Ctrl-C again
- **THEN** the service stops waiting and skips its application shutdown, so its log has no "Application
  shutdown complete"
- **AND** the command exits with status 130 and does not end with a `KeyboardInterrupt` traceback
