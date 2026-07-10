# persistence Specification

## Purpose

Provide the SQLAlchemy engine/session lifecycle the rest of the service builds on: resolve the
`DATABASE_URL` connection through the env → `config.yaml` → dev-default precedence, own the schema
exclusively through Alembic migrations, and uphold the D-7 invariant that everything the database holds
is *derived* and rebuildable from disk — `reel.yaml` remains the sole editorial source of truth. Also
provides the containerized Postgres test fixture the persistence and job-store suites run against.

## Requirements

### Requirement: Database connection and configuration resolution
The system SHALL provide a single SQLAlchemy engine/session factory whose connection URL is resolved in
this precedence order: the `DATABASE_URL` environment variable, then a `database.url` key in the project
`config.yaml` (through the existing D-2 layering), then a documented dev default pointing at a
containerized Postgres. Resolution MUST fail loud with the attempted sources named if no URL can be
resolved and no default applies.

#### Scenario: DATABASE_URL wins over config
- **WHEN** both `DATABASE_URL` is set and `config.yaml` declares `database.url`
- **THEN** the engine connects using `DATABASE_URL` and ignores the config value

#### Scenario: Falls back to config then default
- **WHEN** `DATABASE_URL` is unset but `config.yaml` declares `database.url`
- **THEN** the engine connects using the config value
- **AND WHEN** neither is set
- **THEN** the engine uses the documented dev default (containerized Postgres)

#### Scenario: Sessions are scoped and closed
- **WHEN** a caller obtains a session via the session factory context manager
- **THEN** the session is committed on clean exit and rolled back on exception, and is closed in both cases

### Requirement: Alembic owns the schema
The system SHALL manage all schema changes through Alembic migrations. Applying migrations from an empty
database MUST produce the complete `jobs` schema, including the status enum and the indexes required for
claim-next. The SQLAlchemy `metadata.create_all` path MUST NOT be used outside the test fixture.

#### Scenario: Migrations build the schema from empty
- **WHEN** Alembic `upgrade head` runs against an empty database
- **THEN** the `jobs` table, its status enum, and the claim-next indexes exist

#### Scenario: Models and migrations agree
- **WHEN** the schema produced by the models (`create_all`) is compared to the schema produced by
  `upgrade head`
- **THEN** they are equivalent (a drift test fails if a model change lacks a migration)

### Requirement: Derived state is rebuildable from disk
The persistence layer SHALL hold only derived, non-editorial state. It MUST NOT write editorial data
(clip order, trims, metadata, look) back to `reel.yaml`, and dropping and recreating the database MUST
cost at most re-enqueuing work — never the loss of any editorial decision, which lives only in `reel.yaml`
on disk (D-7).

#### Scenario: Database drop loses no editorial state
- **WHEN** the entire database is dropped and recreated empty
- **THEN** every `reel.yaml` on disk is unchanged and remains the authoritative editorial source
- **AND** only the transient work ledger (pending/finished jobs) is lost

#### Scenario: Layer never mutates reel.yaml
- **WHEN** any persistence-layer operation runs
- **THEN** no `reel.yaml` file is created or modified by that operation

### Requirement: Containerized Postgres test fixture
The test suite SHALL exercise persistence against a real containerized Postgres (podman), not a SQLite
stand-in, so dialect-specific behavior (`FOR UPDATE SKIP LOCKED`, `LISTEN/NOTIFY`, JSONB) is covered.
Tests that do not touch the database MUST still run without the container.

#### Scenario: Persistence tests use real Postgres
- **WHEN** the persistence/job-store test suite runs
- **THEN** it connects to a containerized Postgres started by a session-scoped fixture, and the container
  is torn down afterward

#### Scenario: Non-DB tests do not require the container
- **WHEN** a test not marked as requiring the database runs
- **THEN** it executes without starting or connecting to the Postgres container
