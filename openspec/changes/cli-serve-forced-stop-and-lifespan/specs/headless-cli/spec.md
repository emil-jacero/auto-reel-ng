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
outcome. Once the service has finished its shutdown, a further SIGINT or SIGTERM that arrives while the
command exits SHALL NOT change it either.

The orderly shutdown waits for the request handlers that are still running. A SIGINT that arrives while the
shutdown is still running, whichever signal started it, is the operator's force-quit: the service stops
waiting for those handlers, including one blocked in a worker thread (any synchronous route, for example on
a stalled database), which the command abandons when it exits instead of waiting for it to return. uvicorn's
application shutdown step is skipped if it has not started yet, so the log has no "Application shutdown
complete". The application's own cleanup (the WebSocket poller stopped, the database connections released)
still runs, when its lifespan is cancelled as the service exits, and the command waits for it. The force also ends the service's client connections: every connection
still open is dropped at once, without waiting for it to close, so none holds the command running, including one whose client sent only part of a
request and one whose peer stopped reading with frames backed up for it (api-service, "WebSocket live job
updates"). The command SHALL then exit with status 130, never 0, so that a forced stop is not reported as a
clean one, within a few seconds of the force, and it SHALL NOT end with a `KeyboardInterrupt` traceback of its
own, however many further SIGINTs arrived. A request handler that the forced stop cancels, and the application
lifespan, cancelled at exit or interrupted by a further SIGINT while its cleanup still waits, MAY still be
logged as errors with their tracebacks.

When the application's lifespan fails, the command SHALL NOT exit with status 0 and SHALL NOT report the
failure only in its log: an application shutdown that failed after one SIGINT or SIGTERM, or an application
startup that failed, makes the command exit with status 1 (uvicorn logs the failure, the traceback and
"Application shutdown failed. Exiting." or "Application startup failed. Exiting." but ends normally). A forced
stop skips the application shutdown and keeps status 130.

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
- **THEN** the service stops waiting without uvicorn's application shutdown step, so its log has no
  "Application shutdown complete"
- **AND** the command exits with status 130 and does not end with a `KeyboardInterrupt` traceback

#### Scenario: A forced stop does not wait for a handler blocked in a worker thread
- **WHEN** a `GET /healthz` is blocked in a worker thread on a database that accepts the connection and
  never answers, its client has given up, one Ctrl-C has started the shutdown of `auto-reel serve`, and
  the operator presses Ctrl-C twice more
- **THEN** the command exits with status 130 within a few seconds of the second Ctrl-C, while that handler
  is still blocked
- **AND** its output holds no `KeyboardInterrupt` traceback

#### Scenario: A forced stop does not wait for a client that holds its request open
- **WHEN** a client has sent the headers of a `POST /api/v1/jobs` announcing a body and only part of it, and
  keeps the connection open, one Ctrl-C has started the shutdown of `auto-reel serve` (which logs "Waiting for
  connections to close"), and the operator presses Ctrl-C again
- **THEN** the command exits with status 130 within a few seconds of the second Ctrl-C, while the client
  still holds the connection open
- **AND** its output holds no `KeyboardInterrupt` traceback and no "Application shutdown complete"

#### Scenario: A forced stop does not wait for a peer that stopped reading
- **WHEN** a client has requested a response larger than the host's socket buffers and reads none of it, one
  Ctrl-C has started the shutdown of `auto-reel serve`, and the operator presses Ctrl-C again
- **THEN** the command exits with status 130 within a few seconds of the second Ctrl-C, while the client has
  not closed the connection

#### Scenario: A failed application shutdown does not exit zero
- **WHEN** the application's lifespan raises while `auto-reel serve` shuts down after one SIGTERM, or, in a
  second run, one SIGINT
- **THEN** the log holds "Application shutdown failed" and the traceback
- **AND** the command exits with status 1, not 0

#### Scenario: A failed application startup does not exit zero
- **WHEN** the application's lifespan raises while `auto-reel serve` starts
- **THEN** the command exits with status 1, not 0

#### Scenario: A late signal does not change the exit status
- **WHEN** one SIGTERM or one Ctrl-C has stopped `auto-reel serve` and its orderly shutdown has completed,
  and a further SIGINT or SIGTERM arrives while the command exits
- **THEN** the command still exits with status 0, and its output holds no traceback
