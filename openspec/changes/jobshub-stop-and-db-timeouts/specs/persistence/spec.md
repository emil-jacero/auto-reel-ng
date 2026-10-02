## ADDED Requirements

### Requirement: Postgres connections fail fast
Opening a connection to a Postgres database through the engine SHALL give up after 5 seconds with the
driver's own connection error, rather than wait for the operating system's TCP timeouts. This bounds every
use of the engine alike: a REST route, the health check, the worker, the CLI's job commands, and the
WebSocket hub's polls. A `connect_timeout` that the resolved connection URL itself sets SHALL take
precedence over the 5 seconds, so the operator overrides it through `DATABASE_URL` or `database.url`
without a new key. The bound applies to connecting only: a query on an established connection is not
limited by it. A connection error SHALL NOT be retried or swallowed here; each caller reports it as it
reports any database failure.

#### Scenario: A database host that drops packets
- **WHEN** the database host accepts the TCP connection but never answers the Postgres handshake (or drops
  all traffic), and a caller asks the engine for a connection
- **THEN** the attempt fails after about 5 seconds with the driver's connection error, not after minutes

#### Scenario: Health check reports an unreachable database
- **WHEN** `GET /healthz` is requested while connecting to the database times out
- **THEN** it answers 503 with the connection error's message within about 5 seconds

#### Scenario: The URL's own timeout wins
- **WHEN** `DATABASE_URL` ends in `?connect_timeout=30`
- **THEN** the engine connects with a 30-second bound, not 5

#### Scenario: A healthy database is unaffected
- **WHEN** the database answers
- **THEN** connections open as before and no query is limited by the connect bound
