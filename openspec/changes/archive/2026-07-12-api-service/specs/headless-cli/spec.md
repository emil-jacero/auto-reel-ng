## MODIFIED Requirements

### Requirement: `auto-reel` entry point with subcommands

The system SHALL install a `console_scripts` entry point named `auto-reel` exposing the
subcommands `render`, `scan` (alias `list`), `analyze`, `import`, `enqueue`, `worker`, `jobs`, and
`serve`. Invalid arguments or an unknown subcommand SHALL produce a non-zero exit and a usage message.

#### Scenario: Entry point is installed

- **WHEN** the package is installed and `auto-reel --help` is run
- **THEN** the eight subcommands are listed and the command exits zero

#### Scenario: Unknown subcommand fails

- **WHEN** `auto-reel frobnicate` is run
- **THEN** the command exits non-zero with a usage message

## ADDED Requirements

### Requirement: `serve` runs the API service
`auto-reel serve` SHALL resolve API settings through the D-2 layering (`api.host` / `api.port` /
`api.poll_interval` from `config.yaml`, CLI flags override, defaults `127.0.0.1:8080`, 1 s) and run the
API service under uvicorn until SIGINT/SIGTERM triggers a graceful shutdown (WebSocket poller stopped,
connections closed, exit zero). A failure to bind SHALL exit non-zero naming the attempted host and port.

#### Scenario: Serve starts and answers
- **WHEN** `auto-reel serve` runs against a project root and a reachable database
- **THEN** `GET /healthz` on the configured host/port returns success

#### Scenario: Flags override config
- **WHEN** `config.yaml` sets `api.port: 8080` and `auto-reel serve --port 9000` is run
- **THEN** the service binds port 9000

#### Scenario: Bind failure is loud
- **WHEN** the configured port is already in use
- **THEN** the command exits non-zero naming the attempted host:port
