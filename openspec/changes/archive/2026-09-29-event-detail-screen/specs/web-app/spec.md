## ADDED Requirements

### Requirement: Each event opens on its own page

Every event the list shows with its render state SHALL link to that event's page. The page's address SHALL
identify the event, so that:

- the browser's Back and Forward move between the list and event pages
- reloading an event page reopens the same event
- an event page's address can be bookmarked and opened directly

Returning from an event page to the list SHALL show the list as it was left, with the same filter setting and
the same scroll position, and SHALL NOT re-read the list from the service. The list is still read only when
it is first shown and when the operator refreshes it. An address the client does not recognize SHALL show the
list. Navigation SHALL add no dependency: the client MUST NOT gain a router library.

#### Scenario: An event row opens its page
- **WHEN** the operator clicks the title of `2024-06-21 - Midsommar - Dalarna` in the list
- **THEN** that event's page is shown, and the address identifies that event

#### Scenario: Back returns to the list as it was
- **WHEN** the operator filtered the list to events that need rendering, scrolled down, opened an event, and
  then pressed Back
- **THEN** the list is shown with the filter still on and at the same scroll position, and no new list
  request was made

#### Scenario: An event page survives a reload
- **WHEN** the operator reloads the browser on an event's page, or opens a bookmark of it in a new tab
- **THEN** that event's page is shown

#### Scenario: Event identities with spaces, slashes and non-ASCII letters work
- **WHEN** the operator opens `2024/2024-04-20 - Lasse 80 år, M-A och Lasse kärleksförklaring - Kungälv`
- **THEN** its page is shown, and its address round-trips through Back, Forward and reload

#### Scenario: An unrecognized address shows the list
- **WHEN** the address names no known page, for example `#/nonsense`
- **THEN** the list is shown

### Requirement: The event page shows the event's chapters and clips

An event's page SHALL show, from the event detail the service returns:

- the event's title, or its folder name when it has no title, with its date, location and description
  when present
- whether it needs a render, with every reason in words, or that it is up to date
- its latest job's status and time, when it has one
- counts of its clips, their total size, and its new, missing and ignored clips

Each chapter SHALL be shown as a table, in the order the service returns, with the default chapter's clips
under the label `Main` when the event also has named chapters. Each clip SHALL be listed in play order, with
its position in the chapter, its file name, its status in words, its size and its modification time. A clip
the service reports without a size or time (a missing clip) SHALL show those as absent, never as zero or a
placeholder date. When `reel.yaml` lists clips that are missing from disk, the page SHALL name them in a
warning above the chapters.

The page SHALL read the event from the service when it opens and whenever the operator refreshes it, and
SHALL NOT poll. It SHALL be read-only: it MUST NOT write any file, enqueue any job, or change any state.

#### Scenario: Chapters and clips appear in play order
- **WHEN** an event has root clips and a `Kvällen` chapter
- **THEN** the page shows a `Main` table and a `Kvällen` table, each listing its clips in the order the
  service returns, numbered from 1

#### Scenario: Every clip status is visible
- **WHEN** an event has an included clip, a NEW clip in a named chapter, a MISSING clip and an IGNORED clip
- **THEN** each is listed in its chapter with its status in words, and the counts line reports one new, one
  missing and one ignored clip

#### Scenario: A missing clip shows no invented facts
- **WHEN** `reel.yaml` lists `borttagen.mp4` and the file is not on disk
- **THEN** its row shows no size and no time, and a warning above the chapters names `borttagen.mp4`

#### Scenario: A stale event says why
- **WHEN** an event's `reel.yaml` was edited after its last render
- **THEN** the page shows that it needs a render, citing the edit in words

#### Scenario: A large event is fully listed
- **WHEN** an event holds 380 clips in one chapter
- **THEN** all 380 are listed, numbered 1 to 380

### Requirement: The event page reports failures by cause

When an event's page cannot show the event, it SHALL say why, taking the distinction from the published
problem body, not from its prose:

- **an unknown event**, for example a stale bookmark: the page says the event was not found under the project
  root, and offers the way back to the list
- **an event the service cannot read**: the page shows the failure kind in the same words the list's "Needs
  attention" group uses, and the service's detail, which states the fix
- **the service being unable to reach its database**
- **the service not answering at all**

A failed read SHALL replace whatever the page showed before. It MUST NOT keep showing an earlier state of the
event as though it were current.

#### Scenario: A stale bookmark
- **WHEN** the operator opens the page of an event whose folder was renamed since
- **THEN** the page says that event was not found, and offers a link back to the list

#### Scenario: An unreadable event reads the same as in the list
- **WHEN** the operator opens the page of `2024-02-30 - Omöjligt datum`, whose folder date is impossible
- **THEN** the page shows the same failure words and detail that event's "Needs attention" row shows in the
  list

#### Scenario: The database is down
- **WHEN** the service answers the event read with its database-failure problem body
- **THEN** the page says the service cannot reach its database, and shows no event content

#### Scenario: A refresh fails after a successful load
- **WHEN** an event's page was shown and a refresh then fails
- **THEN** the earlier content is no longer shown, and the failure is

## MODIFIED Requirements

### Requirement: Screen labels are exhaustive over the generated vocabularies

Every staleness reason, every job status, every event failure kind and every clip status the screens show
SHALL be put into words through a mapping defined over the generated types' union for that vocabulary. The
client's type-check then fails when a vocabulary gains, loses or renames a member that the mapping does not
match. The screens MUST NOT display a reason, status or kind slug verbatim, and MUST NOT fall back to one for
an unrecognized value.

#### Scenario: A new staleness reason fails the build
- **WHEN** a staleness reason is added to the engine, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the reason mapping until the new reason is given words

#### Scenario: A renamed job status fails the build
- **WHEN** a job status is renamed and the schema and client types are regenerated
- **THEN** the client's type-check fails at the job status mapping

#### Scenario: A new failure kind fails the build
- **WHEN** an event failure kind is added to the service, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the failure-kind mapping until the new kind is given words

#### Scenario: A new clip status fails the build
- **WHEN** a clip status is added to the engine, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the clip-status mapping until the new status is given words
