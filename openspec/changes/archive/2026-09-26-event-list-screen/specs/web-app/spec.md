## ADDED Requirements

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

The screen SHALL state how many of the listed events need a render, out of how many events in total. It
SHALL offer a filter that shows only those events. The screen SHALL read the list from the service when it
opens and again whenever the operator refreshes it. It MUST NOT poll, cache a list across refreshes, or
derive freshness from anything but the verdict the response carries: a completed job is not freshness. The
screen SHALL be read-only: it MUST NOT write any file, enqueue any job, or change any state.

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

### Requirement: The event list reports failures by cause

When the list cannot be read, the screen SHALL say why, distinguishing:

- the service being unable to reach its database
- an event that could not be scanned, named by its event
- the service not answering at all

It SHALL take these distinctions from the published problem body, not from its prose. A failed read SHALL
replace any previously shown list: the screen MUST NOT keep showing an earlier list as though it were
current. It MUST NOT show a partial list.

#### Scenario: The database is down
- **WHEN** the service answers the list with its database-failure problem body
- **THEN** the screen says the service cannot reach its database, and shows no events

#### Scenario: An event cannot be scanned
- **WHEN** the service answers with a scan-failure problem body naming an event
- **THEN** the screen says that event could not be scanned and names it

#### Scenario: The service is down
- **WHEN** the request gets no response from the service
- **THEN** the screen says the service is not reachable

#### Scenario: A refresh fails after a successful load
- **WHEN** a list was shown and a refresh then fails
- **THEN** the earlier list is no longer shown, and the failure is

### Requirement: Screen labels are exhaustive over the generated vocabularies

Every staleness reason and every job status the screen shows SHALL be put into words through a mapping
defined over the generated types' union for that vocabulary, so that the client's type-check fails when
the vocabulary gains, loses or renames a member that the mapping does not match. The screen MUST NOT
display a reason or status slug verbatim, and MUST NOT fall back to one for an unrecognized value.

#### Scenario: A new staleness reason fails the build
- **WHEN** a staleness reason is added to the engine, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the reason mapping until the new reason is given words

#### Scenario: A renamed job status fails the build
- **WHEN** a job status is renamed and the schema and client types are regenerated
- **THEN** the client's type-check fails at the job status mapping
