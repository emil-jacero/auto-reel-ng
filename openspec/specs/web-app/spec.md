# web-app Specification

## Purpose

The browser client for the auto-reel-ng service: how it is built, how its view of the API is derived
from the service's own schema rather than hand-written, and what it is allowed to depend on.

## Requirements

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

### Requirement: The event list shows every event with its render state

The client's first screen SHALL list every event the events list response returns. Events SHALL be grouped
by the year of their date, groups newest year first, and events within a group newest date first. Events
with no date SHALL form their own group after every dated group. Each event SHALL show:

- its date
- its title, or the event's folder name when it has no title
- its location when it has one
- its clip count
- its NEW and MISSING clip counts when either is non-zero
- whether it needs a render and, if so, every reason the verdict cites, in words
- its latest job's status, when it has one

The screen MUST NOT omit an event the response contains, invent a fact the response does not carry, or
present a missing fact (no date, no title, no job) as a value.

#### Scenario: A multi-year library is grouped newest first
- **WHEN** the list contains events dated in 2023 and 2024 and one event with no date
- **THEN** the 2024 group appears first, then 2023, then the undated group, and each dated group is ordered
  newest date first

#### Scenario: An untitled event is shown by its folder name
- **WHEN** an event has no title in its metadata
- **THEN** it is shown under its event folder's name, not as an empty row or "Untitled"

#### Scenario: A stale event names every reason
- **WHEN** an event was renamed after its last render, so its verdict cites the editorial change and the
  missing output
- **THEN** its row says it needs a render and names both reasons in words

#### Scenario: NEW and MISSING clips are visible
- **WHEN** an event has one NEW clip, and another references one clip that is absent from disk
- **THEN** the first row shows one new clip and the second shows one missing clip

#### Scenario: The latest job's outcome is visible
- **WHEN** one event's latest job failed, another's is queued, and a third has no job
- **THEN** the first row shows the failure, the second shows that it is queued, and the third shows no job
  status at all

### Requirement: The event list answers what needs rendering, from disk

The screen SHALL state how many of the listed events need a render, out of how many readable events in
total, and, when any exist, how many events need attention because they are error rows. It SHALL offer a
filter that shows only the events needing a render. Error rows SHALL remain visible whatever the filter,
because they also need action.

The screen SHALL read the list from the service when it opens and again whenever the operator refreshes
it. It MUST NOT poll, cache a list across refreshes, or derive freshness from anything but the verdict the
response carries: a completed job is not freshness. The screen SHALL be read-only: it MUST NOT write any
file, enqueue any job, or change any state.

#### Scenario: The summary counts stale events
- **WHEN** the list holds nine events of which six need a render
- **THEN** the screen states that 6 of 9 events need rendering

#### Scenario: The filter hides fresh events
- **WHEN** the operator turns on the needs-render filter
- **THEN** only events whose verdict is stale remain listed, still grouped and ordered as before

#### Scenario: A refresh shows disk changes
- **WHEN** a clip is added to a fresh event's folder and the operator refreshes
- **THEN** that event is shown as needing a render, citing the changed clips, and with one new clip

#### Scenario: A finished job does not make an event fresh
- **WHEN** an event's latest job is done but its clips changed afterwards
- **THEN** the event is shown as needing a render

#### Scenario: Events needing attention are counted separately
- **WHEN** the list holds nine summaries, six of them stale, and one error row
- **THEN** the screen states that 6 of 9 events need rendering and that 1 needs attention

#### Scenario: The filter keeps error rows
- **WHEN** the operator turns on the needs-render filter over a list that contains an error row
- **THEN** the error row remains shown in "Needs attention"

### Requirement: The event list reports failures by cause

When the list cannot be read at all, the screen SHALL say why, distinguishing:

- the service being unable to reach its database
- the project scan failing as a whole
- the service not answering at all

It SHALL take these distinctions from the published problem body, not from its prose. A failed read SHALL
replace any previously shown list: the screen MUST NOT keep showing an earlier list as though it were
current. It MUST NOT show a partial list.

When the list is read but contains **error rows**, the screen SHALL show every other event as usual, plus
a **"Needs attention"** group placed before all other groups. For each error row, the group SHALL show:

- the event's folder name
- its failure kind in words
- the service's detail, which states the fix

An error row SHALL never be presented as a render-state row, and no fact the row does not carry (clip
counts, staleness, title, date) SHALL be shown for it.

#### Scenario: The database is down
- **WHEN** the service answers the list with its database-failure problem body
- **THEN** the screen says the service cannot reach its database, and shows no events

#### Scenario: An event cannot be scanned
- **WHEN** the list holds eight summaries and one error row for `2019-04-31 - Golfträning med Emil - Tjörn`
  with the unusable-metadata kind
- **THEN** the screen shows the eight events in their year groups, and a "Needs attention" group first
  showing that folder name, the kind in words, and the detail that `2019-04-31` is not a real date

#### Scenario: The service is down
- **WHEN** the request gets no response from the service
- **THEN** the screen says the service is not reachable

#### Scenario: A refresh fails after a successful load
- **WHEN** a list was shown and a refresh then fails
- **THEN** the earlier list is no longer shown, and the failure is

#### Scenario: The whole scan fails
- **WHEN** the service answers the list with its scan-failure problem body
- **THEN** the screen says the project could not be scanned, shows the detail, and shows no events

### Requirement: Screen labels are exhaustive over the generated vocabularies

Every staleness reason, every job status and every event failure kind the screen shows SHALL be put into
words through a mapping defined over the generated types' union for that vocabulary. The client's
type-check then fails when a vocabulary gains, loses or renames a member that the mapping does not match.
The screen MUST NOT display a reason, status or kind slug verbatim, and MUST NOT fall back to one for an
unrecognized value.

#### Scenario: A new staleness reason fails the build
- **WHEN** a staleness reason is added to the engine, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the reason mapping until the new reason is given words

#### Scenario: A renamed job status fails the build
- **WHEN** a job status is renamed and the schema and client types are regenerated
- **THEN** the client's type-check fails at the job status mapping

#### Scenario: A new failure kind fails the build
- **WHEN** an event failure kind is added to the service, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the failure-kind mapping until the new kind is given words
