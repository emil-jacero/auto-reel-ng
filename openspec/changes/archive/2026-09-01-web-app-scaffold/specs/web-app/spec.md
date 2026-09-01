## Purpose

The browser client for the auto-reel-ng service: how it is built, how its view of the API is derived
from the service's own schema rather than hand-written, and what it is allowed to depend on.

## ADDED Requirements

### Requirement: The client is a static build with no runtime Node process
The web client SHALL be built ahead of time into static assets that the existing service process serves.
No part of running the service may require Node, a JavaScript runtime, or a second server process: a
deployment SHALL remain the single Python process `auto-reel serve` starts. Node MAY be required to
*build* the client, and that toolchain SHALL run in a container rather than being installed on the host.

#### Scenario: The service runs with no Node present
- **WHEN** the service is started on a host that has no Node installed, from a checkout whose client was
  built elsewhere
- **THEN** the service starts and serves the client

#### Scenario: Building the client installs nothing on the host
- **WHEN** a developer builds the client from a clean checkout
- **THEN** the build runs inside a container and leaves no Node toolchain installed on the host

### Requirement: API types are generated from the service's own schema
The client's TypeScript types for API requests and responses SHALL be generated from the service's
OpenAPI schema, and MUST NOT be hand-written or hand-maintained. The schema SHALL be produced from the
application itself, offline — without a running service, a reachable database, or network access — and
SHALL be committed to the repository alongside the types generated from it, so that both the Python and
the TypeScript checks can compare against a fixed artifact.

#### Scenario: The schema is produced without a running service
- **WHEN** the schema is generated on a machine with no database reachable and no service running
- **THEN** the schema is produced successfully and describes the API's current endpoints and models

#### Scenario: Types are derived, never authored
- **WHEN** a developer needs the type of an API response in client code
- **THEN** it is available from the generated types, and no equivalent shape is declared by hand

### Requirement: A backend schema change fails a check, never drifts silently
A change to any endpoint's request or response model SHALL cause a check to fail until the committed
schema and generated types are regenerated. The Python test suite SHALL fail when the committed schema
does not match the schema the application currently produces, naming the disagreement. The client's
type-check SHALL fail when client code uses a field or shape the generated types do not describe.

#### Scenario: A response model gains a field
- **WHEN** a field is added to an endpoint's response model and the committed schema is not regenerated
- **THEN** the Python test suite fails, reporting that the committed schema is out of date

#### Scenario: A response model loses a field the client reads
- **WHEN** a field the client reads is removed from an endpoint's response model, and the schema and
  types are regenerated
- **THEN** the client's type-check fails at the place that reads the removed field

#### Scenario: Regenerating clears the failure
- **WHEN** the committed schema and generated types are regenerated after a backend model change
- **THEN** both checks pass with no hand edit to the generated files

### Requirement: The type-check is the frontend's gate
`tsc --noEmit` SHALL be the check the client must pass, and the project SHALL NOT require a frontend
test runner or browser automation for GUI v1. Adding either later requires its own justified proposal.

#### Scenario: The client is checked without a browser
- **WHEN** the client's validation is run
- **THEN** it type-checks the client and requires no browser, headless or otherwise

### Requirement: The dependency budget is explicit and small
The client SHALL depend on React, React DOM, Vite, the Vite React plugin and TypeScript, plus the
schema-to-types generator as a development dependency. It MUST NOT depend on a component library, a CSS
framework, a router, or a state-management or data-fetching library at GUI v1. Any dependency beyond
this set SHALL be justified in the proposal of the change that introduces it, by a slice that
demonstrably needs it.

#### Scenario: A slice needs a capability no budgeted dependency provides
- **WHEN** a later slice requires drag-and-drop reordering
- **THEN** that slice's proposal justifies the one library it adds, rather than it appearing as an
  incidental dependency of this scaffold

### Requirement: Development serves the client and the API from one origin
In development the client SHALL be served by its own dev server, which SHALL forward API and WebSocket
requests to the running service, so that client code addresses the API by path alone. The client MUST
NOT be configured with an absolute API base URL, and the service MUST NOT need cross-origin permissions
for the client to work in development or in production.

#### Scenario: The client calls the API in development
- **WHEN** the dev server is running against a running service and the client requests an API path
- **THEN** the request reaches the service and succeeds without any cross-origin configuration

#### Scenario: The same client code works when served by the service
- **WHEN** the built client is served by the service itself
- **THEN** the same API paths resolve against the serving origin, with no build-time URL substitution
