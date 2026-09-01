## ADDED Requirements

### Requirement: The built web client is served when present, and is never required
When a built web client is present in the development checkout, the service SHALL serve it at the root
path, returning its entry document for `/` and its assets by path. When no built client is present, the
service SHALL start and behave exactly as it does without one — a missing build is a normal state, not
an error, so development runs and the test suite never require a frontend build.

Serving the client MUST NOT shadow the service's own routes: every API path, the health endpoint and the
WebSocket endpoint SHALL continue to resolve to their handlers whether or not a build is present. The
service SHALL NOT serve any file outside the built client's directory.

#### Scenario: The service starts with no build present
- **WHEN** the service starts from a checkout that has never built the client
- **THEN** it starts normally, every API endpoint works, and the root path is simply not served

#### Scenario: The built client is served at the root
- **WHEN** the client has been built and the service is started
- **THEN** requesting `/` returns the client's entry document and its assets resolve by path

#### Scenario: API routes win over the client mount
- **WHEN** the client has been built and the service is started
- **THEN** `GET /api/v1/events`, `GET /healthz` and the jobs WebSocket still reach their handlers and are
  not answered with the client's entry document

#### Scenario: The mount does not expose the wider filesystem
- **WHEN** a request asks for a path that traverses outside the built client's directory
- **THEN** the service does not return a file from outside that directory
