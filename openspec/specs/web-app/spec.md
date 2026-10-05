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
- its clip count: the clips it lists that are not ignored, the new and missing ones among them, as the
  event's page counts them
- its ignored clip count, when it is non-zero
- its NEW and MISSING clip counts when either is non-zero
- whether it needs a render and, if so, every reason the verdict cites, in words
- its latest job's status, when it has one

When two or more events the list shows would read the same, because they have the same date, the same title
(or, for an event with no title, the same folder name in its place) and the same location, compared without
regard to letter case, each of them SHALL also show its folder's path under the project root, for example
`2024/2024-07-14 - Kalas`. No two events share that path, so rows that would otherwise read the same are
told apart, even when their folders have the same name in different parent folders.

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
- **WHEN** the title of `2024-06-27 - Grillning med grannar` was changed after its last render, while its
  movie is still on disk under the old name, so its verdict cites the editorial change and the changed movie
  name
- **THEN** its row says it needs a render and names both reasons in words, "edited since last render" and
  "movie name changed", and does not say that the movie file is missing

#### Scenario: A movie deleted from disk is named missing
- **WHEN** the movie of `2024-06-21 - Midsommar - Dalarna` was deleted after its last render, and nothing
  else about the event changed
- **THEN** its row says it needs a render because the movie file is missing, and names no other reason

#### Scenario: NEW and MISSING clips are visible
- **WHEN** an event has one NEW clip, and another references one clip that is absent from disk
- **THEN** the first row shows one new clip and the second shows one missing clip

#### Scenario: Ignored clips are counted apart
- **WHEN** an event lists two clips and its folder holds a third that `reel.yaml` ignores
- **THEN** its row shows 2 clips and 1 ignored, the same two numbers its page shows, and not 3 clips

#### Scenario: The latest job's outcome is visible
- **WHEN** one event's latest job failed, another's is queued, and a third has no job
- **THEN** the first row shows the failure, the second shows that it is queued, and the third shows no job
  status at all

#### Scenario: Look-alike events are told apart
- **WHEN** the list shows `2024/2024-07-14 - Kalas` and `2024/2024-07-14 - kalas`, both titled "Kalas", dated
  2024-07-14 and with no location
- **THEN** the first row also shows `2024/2024-07-14 - Kalas`, and the second `2024/2024-07-14 - kalas`
- **AND** no other row of the dev library shows its folder's path beside its title

#### Scenario: Look-alike folders of the same name are told apart
- **WHEN** the list shows `2023/Blandat` and `2024/Blandat`, neither with a date, a title or a location
- **THEN** both rows read "Blandat" in the undated group, and the first also shows `2023/Blandat` and the
  second `2024/Blandat`

### Requirement: The event list answers what needs rendering, from disk

When the list holds at least one readable event, the screen SHALL state how many of the listed events need
a render, out of how many readable events in total. When error rows exist, it SHALL state how many events
need attention because they are error rows. It SHALL offer a choice between showing all events and showing
only the events needing a render. Error rows SHALL remain visible whatever the choice, because they also
need action.

When the list holds no event at all, the screen SHALL show no counts. It SHALL say that no events were
found, and that adding an event folder and refreshing shows it.

When the choice hides every event, the screen SHALL say that nothing needs rendering, and SHALL offer a
control that shows all events again. That control SHALL move keyboard focus to the choice it changed.

The screen SHALL announce, through a status message, how many events it shows and how many of them need
rendering, plus how many need attention when any do:

- after each read the operator started (the first read and every refresh)
- after each change of the choice

A re-read the client starts by itself SHALL announce the counts only when they changed.

The screen SHALL read the list from the service:

- when it is first shown
- whenever the operator refreshes it
- whenever it is shown and the client has recorded, since the list was last read, that an event changed
  (for example a save on an event page, or a finished render)

It MUST NOT cache a list across refreshes, or derive freshness from anything but the verdict the response
carries: a completed job is not freshness.

#### Scenario: The summary counts stale events
- **WHEN** the list holds nine events of which six need a render
- **THEN** the screen states that 6 of 9 events need rendering

#### Scenario: The filter hides fresh events
- **WHEN** the operator switches the list to show only events that need a render
- **THEN** only events whose verdict is stale remain listed, still grouped and ordered as before
- **AND** the status message announces how many of the events are shown

#### Scenario: A refresh shows disk changes
- **WHEN** a clip is added to a fresh event's folder and the operator refreshes
- **THEN** that event is shown as needing a render, citing the changed clips, and with one new clip
- **AND** when the read finishes, the status message announces the counts

#### Scenario: A finished job does not make an event fresh
- **WHEN** an event's latest job is done but its clips changed afterwards
- **THEN** the event is shown as needing a render

#### Scenario: Events needing attention are counted separately
- **WHEN** the list holds nine summaries, six of them stale, and one error row
- **THEN** the screen states that 6 of 9 events need rendering and that 1 needs attention

#### Scenario: The filter keeps error rows
- **WHEN** the operator switches the list to only events needing a render, over a list that contains an
  error row
- **THEN** the error row remains shown in "Needs attention"

#### Scenario: An event changed in the client is re-read on return
- **WHEN** the list was read, the operator opened `2024-06-27 - Grillning med grannar`, the client recorded
  that this event changed, and the operator goes back to the list
- **THEN** the list is read again, and the Needs render choice is as the operator left it

#### Scenario: An empty library
- **WHEN** the service's project holds no event folder
- **THEN** the screen shows no counts, says that no events were found, and says that adding an event folder
  and refreshing shows it

#### Scenario: Nothing needs rendering
- **WHEN** every event of the list is up to date and the operator switches the list to only events needing a
  render
- **THEN** the screen says that nothing needs rendering and offers "Show all events"
- **AND** pressing it with the keyboard shows every event again, with focus on the "All" choice

### Requirement: The event list reports failures by cause

When the list cannot be read at all, the screen SHALL say why, distinguishing:

- the service being unable to reach its database
- the project scan failing as a whole
- the service answering with a status or body it does not publish for this read (see "A request that gets
  no usable answer says which")
- the service not answering at all

It SHALL take these distinctions from the published problem body, not from its prose. A failed read SHALL
replace any previously shown list: the screen MUST NOT keep showing an earlier list as though it were
current. It MUST NOT show a partial list.

When the list is read but contains **error rows**, the screen SHALL show every other event as usual, plus
a **"Needs attention"** group placed before all other groups. For each error row, the group SHALL show:

- the event's folder name
- its failure kind in words
- the service's detail, which states the fix

When the detail begins with the event's folder name, which the row already shows, that repetition SHALL be
left out. The rest of the detail SHALL be shown as the service wrote it, with only its first letter made a
capital.

An error row SHALL never be presented as a render-state row, and no fact the row does not carry (clip
counts, staleness, title, date) SHALL be shown for it.

#### Scenario: The database is down
- **WHEN** the service answers the list with its database-failure problem body
- **THEN** the screen says the service cannot reach its database, and shows no events

#### Scenario: An event cannot be scanned
- **WHEN** the list holds eight summaries and one error row for `2019-04-31 - Golfträning med Emil - Tjörn`
  with the unusable-metadata kind
- **THEN** the screen shows the eight events in their year groups, and a "Needs attention" group first
- **AND** the group shows that folder name, the kind in words, and the detail that `2019-04-31` is not a
  real date
- **AND** the detail does not start with the folder name again

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

### Requirement: Each event opens on its own page

Every event the list shows with its render state SHALL link to that event's page. A click anywhere on such
an event's row SHALL open that event's page, as its title does, unless the click is on one of the row's
controls. The row SHALL show that it is a target when the pointer is over it. Selecting text in a row SHALL
NOT open the page. Keyboard access is unchanged: the title's link is the row's one stop in the tab order.

The page's address SHALL identify the event, so that:

- the browser's Back and Forward move between the list and event pages
- reloading an event page reopens the same event
- an event page's address can be bookmarked and opened directly

Returning from an event page to the list SHALL show the list as it was left, with the same filter setting and
the same scroll position, and SHALL NOT re-read the list from the service. The one exception is when the
client has recorded, since the list was last read, that an event changed. In that case the list SHALL be
read again on return, keeping its filter setting. Otherwise, the list is read only when it
is first shown and when the operator refreshes it. An address the client does not recognize SHALL show the
list. Navigation SHALL add no dependency: the client MUST NOT gain a router library.

#### Scenario: An event row opens its page
- **WHEN** the operator clicks the title of `2024-06-21 - Midsommar - Dalarna` in the list
- **THEN** that event's page is shown, and the address identifies that event

#### Scenario: A click beside the title opens the event
- **WHEN** the operator clicks the clip count in the row of `2024-08-20 - Två kapitel - Tjörn`
- **THEN** that event's page is shown, as if its title had been clicked

#### Scenario: A row's own control does not open the page
- **WHEN** the operator presses the Render of the `2024-06-27 - Grillning med grannar` row
- **THEN** the list stays shown, and the row follows its job

#### Scenario: Selecting a row's text does not open the page
- **WHEN** the operator drags across the date of a row to select it
- **THEN** the date is selected and the list stays shown

#### Scenario: Back returns to the list as it was
- **WHEN** the operator filtered the list to events that need rendering, scrolled down, opened an event, and
  then pressed Back, and no event was recorded as changed in between
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
  when present. When the heading shows a title that differs from the event's folder name, the page SHALL
  also show the folder name as secondary text, and SHALL give it to assistive technology as the heading's
  description, so that two events with the same title and date can be told apart.
- whether it needs a render, with every reason in words, or that it is up to date
- its latest job's status and time, when it has one
- counts of its clips, their total size, and its new, missing, excluded and ignored clips

The verdict and the latest job SHALL be shown together, in the one region that holds the page's render
controls, between the page's heading and its chapters. The clip counts SHALL be shown with the event's facts
under the heading, not between that region and the chapters.

Each chapter SHALL be shown as a table, in the order the service returns, with the default chapter's clips
under the label `Main` when the event also has named chapters. Each chapter SHALL first list the clips it
plays, in play order, each with its position in the chapter, numbered from 1. After them it SHALL list the
clips the event ignores, marked as ignored and with no position, because an ignored clip is not part of the
play order. A chapter's heading SHALL count the clips it plays, followed by the number of its ignored clips
when it has any. Every clip SHALL be listed with its name, its status in words, its size and its modification
time. A new, missing or ignored clip SHALL show its status as a status label. An included clip, the usual
case, SHALL show its status as quiet words with its icon, without a label's fill or edge, so that the other
statuses stand out. A clip the service reports without a size or time (a missing clip) SHALL show those as
absent, never as zero or a placeholder date. When `reel.yaml` lists clips that are missing from disk, the
page SHALL name them in a warning above the chapters, and SHALL mark each one that `reel.yaml` excludes as
excluded there. A clip that `reel.yaml` excludes SHALL be marked in its row, as "A clip that reel.yaml excludes
is marked as excluded" says.

A clip's name SHALL be its file name while every clip its chapter lists lies in the chapter's own folder
(the event folder, for the default chapter). A chapter that lists a clip from another folder SHALL name each
of its clips by its path inside the event folder, so that no two of its rows read alike.

The page SHALL read the event from the service when it opens and whenever the operator refreshes it. While
that read runs, the page SHALL show placeholders in the shape of what it will show: its heading, its facts
line, its render region, and clip rows laid out as the loaded rows are, each with its thumbnail box of the
loaded size. The heading SHALL show a placeholder, never a name that the read may replace, and SHALL still be
named by the event's folder name for assistive technology. The placeholders SHALL fit the window as the
loaded page does, without horizontal scroll from 320 CSS pixels up.

#### Scenario: Chapters and clips appear in play order
- **WHEN** an event has root clips and a `Kvällen` chapter
- **THEN** the page shows a `Main` table and a `Kvällen` table, each listing the clips it plays in the order
  the service returns, numbered from 1

#### Scenario: Every clip status is visible
- **WHEN** an event has an included clip, a NEW clip in a named chapter, a MISSING clip and an IGNORED clip
- **THEN** each is listed in its chapter with its status in words: the new, missing and ignored clips as
  status labels, and the included clip as the quiet word "Included" with its icon; and the counts line
  reports one new, one missing and one ignored clip

#### Scenario: An ignored clip has no position
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose `reel.yaml` ignores its root clip
  `s1710004.mp4`
- **THEN** `Main` lists `s1710001.mp4` at position 1 and then `s1710004.mp4`, marked as ignored and with no
  position, as Edit mode lists that chapter, and `Main`'s heading counts "1 clip" and "1 ignored"

#### Scenario: A new clip the service lists after an ignored one is numbered before it
- **WHEN** the root folder of `2024-08-20 - Två kapitel - Tjörn` also holds a NEW clip `s1710009.mp4`, which
  the service lists after the ignored `s1710004.mp4` because it sorts after it on disk
- **THEN** `Main` lists `s1710001.mp4` at position 1, `s1710009.mp4` as new at position 2, and then
  `s1710004.mp4`, marked as ignored and with no position, in the order Edit mode lists them

#### Scenario: A clip from another folder is named by its path
- **WHEN** `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its root
  chapter and ignores the root clip `s1710004.mp4`, as a hand edit leaves it (a render adopts no ignored
  clip, D-12)
- **THEN** `Main` names its rows `s1710001.mp4`, `Kvällen/s1710004.mp4` and `s1710004.mp4`, and `Kvällen`
  still names its rows `s1710002.mp4` and `s1710003.mp4`

#### Scenario: Two events with the same title are told apart
- **WHEN** the operator opens `2024-07-14 - Kalas` and then `2024-07-14 - kalas`, both titled `Kalas`
- **THEN** each page's heading reads `Kalas` with the date `2024-07-14`, and each page also shows its own
  folder name, `2024-07-14 - Kalas` on the first and `2024-07-14 - kalas` on the second, which assistive
  technology reads as the heading's description

#### Scenario: A folder name that is the title is not repeated
- **WHEN** the operator opens `2024/Blandat`, whose title `Blandat` equals its folder name
- **THEN** the heading reads `Blandat`, and the page shows no separate folder name

#### Scenario: The render state reads as one region
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, which needs a render and whose latest
  job is rendered
- **THEN** "Needs render" with its reasons, the latest job "Rendered" with its time, and Render are shown
  in one region between the heading and the `Clips` table, and the line with its clip count and total size
  is shown under the heading

#### Scenario: The counts name the excluded clips
- **WHEN** the operator opens an event that lists three clips, one of which `reel.yaml` excludes
- **THEN** the facts line reads "3 clips" with the total size and "1 excluded", and the excluded clip is
  one of the three numbered rows

#### Scenario: A missing clip shows no invented facts
- **WHEN** `reel.yaml` lists `borttagen.mp4` and the file is not on disk
- **THEN** its row shows no size and no time, and a warning above the chapters names `borttagen.mp4`

#### Scenario: A stale event says why
- **WHEN** an event's `reel.yaml` was edited after its last render
- **THEN** the page shows that it needs a render, citing the edit in words

#### Scenario: A large event is fully listed
- **WHEN** an event holds 380 clips in one chapter
- **THEN** all 380 are listed, numbered 1 to 380

#### Scenario: A slow read keeps the page's shape
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide, and its read
  takes two seconds
- **THEN** during those seconds the heading shows a placeholder and no visible text, assistive technology
  names the heading `2024-06-27 - Grillning med grannar`, and each placeholder clip row is as tall as a
  loaded row; when the read answers, the heading reads `Grillkväll med grannarna` and the `Clips` table
  starts within 8 pixels of where the placeholder table started

### Requirement: The event page reports failures by cause

When an event's page cannot show the event, it SHALL say why, taking the distinction from the published
problem body, not from its prose:

- **an unknown event**, for example a stale bookmark: the page says, once, that the event was not found under
  the project root, and offers the way back to the list. The service's own sentence says the same thing, so
  it is not shown.
- **an event the service cannot read**: the page shows the failure kind in the same words the list's "Needs
  attention" group uses, and the service's detail, which states the fix, as that group shows it
- **the service being unable to reach its database**
- **the service answering with a status or body it does not publish for this read** (see "A request that
  gets no usable answer says which")
- **the service not answering at all**

A failed read SHALL replace whatever the page showed before. It MUST NOT keep showing an earlier state of the
event as though it were current.

#### Scenario: A stale bookmark
- **WHEN** the operator opens the page of an event whose folder was renamed since
- **THEN** the page says that event was not found, once, and offers a link back to the list

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

### Requirement: Every page shares one header and follows the operator's color scheme

Every page SHALL show the same header. The header SHALL contain:

- the product's mark and name
- a link to the event list, marked as the current page while the list is shown
- a control for choosing the color scheme: System, Light or Dark

The header SHALL stay visible while the page scrolls.

The screens SHALL render in a light and a dark color scheme drawn from one set of design tokens. Tokens SHALL
exist for colors, spacing, radii, type and motion. The screens SHALL follow the operating system's color
preference until the operator chooses Light or Dark. The choice SHALL persist in that browser across reloads
and new tabs, and SHALL apply before the first paint, so a reload never flashes the other scheme. Choosing
System SHALL return to following the operating system.

The color the page declares for the browser's own interface, such as a mobile browser's address bar, SHALL be
the page background of the scheme in effect. That is the chosen scheme when the operator chose Light or Dark,
and the operating system's otherwise. It SHALL be in effect from the first paint, and SHALL follow a new choice
without a reload.

When the browser refuses storage, the screens SHALL follow the operating system and render without error.
The control SHALL still switch the scheme for the current page.

#### Scenario: The operating system's preference is followed by default
- **WHEN** the operator's system prefers dark and no choice was made in this browser
- **THEN** the event list for the dev library renders in the dark scheme, and the control shows System

#### Scenario: A chosen scheme survives a reload
- **WHEN** the operator's system prefers dark, the operator chooses Light on the page of
  `2024-08-20 - Två kapitel - Tjörn`, and then reloads
- **THEN** the page renders in the light scheme from the first paint, and the control shows Light

#### Scenario: System returns to the operating system's preference
- **WHEN** the operator chose Dark earlier and now chooses System on a system that prefers light
- **THEN** the page renders in the light scheme

#### Scenario: The browser's interface color follows the choice
- **WHEN** the operator's system prefers dark, the operator chose Light, and the event list is reloaded
- **THEN** from the first paint the page declares the light scheme's page background as the browser's
  interface color, and choosing Dark then declares the dark scheme's page background, without a reload

#### Scenario: System hands the browser's interface color back
- **WHEN** the operator chose Light earlier and now chooses System on a system that prefers dark
- **THEN** the page declares the dark scheme's page background as the browser's interface color

#### Scenario: Storage is blocked
- **WHEN** the browser throws on every storage access and the operator opens the event list
- **THEN** the list renders in the operating system's scheme with no error shown, and choosing Dark switches
  the current page to the dark scheme

#### Scenario: The header marks where the operator is
- **WHEN** the event list is shown
- **THEN** the header's Events link is marked as the current page, and it is not marked on the page of
  `2024-09-01 - Sommarlov`

### Requirement: State is never shown by color alone

Every render verdict, job status, clip status and event failure kind a screen shows SHALL be shown as its
words, paired with an icon, and never as a color alone. The same holds for warnings and failure messages:
each shows its words and an icon. Tones SHALL be consistent across screens: the same status has the same
tone and icon on every page.

In both color schemes, text SHALL meet WCAG 2.1 AA contrast: at least 4.5:1 for normal-size text, and at
least 3:1 for large text and for the focus indicator against its background. This includes the words inside
status labels and secondary ("muted") text. As in WCAG, the label of a control that is currently
unavailable (such as Refresh while it reads) is exempt.

A busy button SHALL show a loader before its label, in place of its icon, drawn in the button's own text
color. In the operating system's forced-colors mode, where the browser replaces the page's colors with the
system palette, that loader SHALL stay visible, in the same color as the button's label.

#### Scenario: Verdicts read in grayscale
- **WHEN** the event list for the dev library is viewed with all color removed
- **THEN** `2024-06-27 - Grillning med grannar` still reads "Needs render" with its reasons, and
  `2023-06-23 - Midsommar - Dalarna` still reads "Up to date"

#### Scenario: Status labels meet contrast in both schemes
- **WHEN** the contrast of every status label's text on its own background, and of the scan time's muted
  text on the page background, is measured in the light and in the dark scheme
- **THEN** every ratio is at least 4.5:1

#### Scenario: A failed job is marked by words and icon
- **WHEN** the list shows `2024-10-05 - Trasig`, whose latest job failed
- **THEN** its job status reads "Failed" beside an icon, and not only in a red color

#### Scenario: A busy button's loader survives forced colors
- **WHEN** the operator's system uses forced colors, and the operator presses Render on
  `2024-06-27 - Grillning med grannar` while the service takes two seconds to answer
- **THEN** during those seconds Render shows a loader in the same color as its label, in place of its icon,
  and the loader is not drawn in the button's background color

### Requirement: The screens are operable by keyboard

Every interactive control SHALL be reachable with the keyboard, in a logical order, and SHALL show a visible
focus indicator in both color schemes when focused from the keyboard.

Each page SHALL have exactly one level-one heading, naming the page. Each section SHALL have a level-two
heading: a year group, "Needs attention", or a chapter.

The first control in the tab order SHALL be a skip control. It SHALL move focus to the page's level-one
heading and SHALL NOT change the page's address.

After the operator moves between pages (opening an event, Back, Forward, or the header's Events link), focus
SHALL be on the new page's level-one heading. A control that becomes busy (such as Refresh while reading)
SHALL keep keyboard focus, and SHALL NOT be removed from the tab order. A focused control SHALL NOT be hidden
behind anything that stays in place while the page scrolls, such as the header.

#### Scenario: The skip control reaches the content without navigating
- **WHEN** the operator loads the event list and presses Tab once, then Enter
- **THEN** the skip control is visible while focused, focus moves to the "Events" heading, and the address
  is unchanged

#### Scenario: Opening an event moves focus to its heading
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn` from the list with the keyboard
- **THEN** focus is on that page's level-one heading, and the page has a level-two heading for `Main` and
  one for `Kvällen`

#### Scenario: Refresh keeps focus
- **WHEN** the operator presses Enter on the list's Refresh button
- **THEN** the list is read again, and focus stays on the Refresh button throughout

#### Scenario: Focus is visible in the dark scheme
- **WHEN** the operator tabs to an event link in the dark scheme
- **THEN** a focus indicator is visible around it

#### Scenario: The sticky header never covers focus
- **WHEN** the operator tabs down through every event link of the dev library's list
- **THEN** each focused link is fully visible below the header and below its year's heading

### Requirement: The screens respect reduced motion

When the operating system asks for reduced motion, the screens SHALL NOT animate. That means no transitions,
no shimmering placeholders, no spinning indicators, and no enter animations. When it does not ask, motion
SHALL be limited to short feedback on hover, focus, loading and appearing elements, and no information SHALL
depend on seeing an animation.

#### Scenario: Placeholders stand still under reduced motion
- **WHEN** the operator's system asks for reduced motion and the event list is being read
- **THEN** the placeholder rows are shown without any animation

### Requirement: The screens fit a phone-width window

In a window 390 CSS pixels wide, no page SHALL scroll horizontally. Every fact about an event, a clip or a
failure that a page shows in a wide window SHALL still be shown in the narrow one, rearranged and never
dropped. Long names and details SHALL wrap rather than overflow.

The header SHALL stay one bar tall at every window width from 320 pixels, in any font the browser falls
back to, narrower or wider than the design font. Its job counts SHALL NOT be broken over several lines.
When the words of the counts do not fit beside the header's other content, each count SHALL shrink to its
status icon and number, the words staying for assistive technology. Which of the two is shown SHALL depend
on the room the header leaves the counts, not on the window's width alone.

#### Scenario: The list at phone width
- **WHEN** the operator opens the dev library's event list in a window 390 pixels wide
- **THEN** the page does not scroll horizontally, and each event still shows its date, title, location, clip
  counts, verdict with reasons, and latest job

#### Scenario: An event page at phone width
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn` in a window 390 pixels wide
- **THEN** the page does not scroll horizontally, and every clip still shows its position, file name,
  status, size and modification time

#### Scenario: A failure detail wraps
- **WHEN** the operator opens the list at 390 pixels wide, and it shows `2024-02-30 - Omöjligt datum` under
  "Needs attention"
- **THEN** its folder name, failure words and detail wrap within the window

#### Scenario: The header's counts in a wider font
- **WHEN** the connection is live with 99 jobs rendering and 99 queued, the browser's sans-serif font is
  Liberation Sans or DejaVu Sans, and the operator opens the event list in windows 470, 480, 485 and 500
  pixels wide
- **THEN** the header's content stays inside its bar and the connection's pill and the counts do not overlap
  the navigation or the color-scheme control, and the counts are on one line, in words where they fit and as
  icons with numbers where they do not

### Requirement: A read in progress is shown as a placeholder and announced

While a screen reads its own content from the service, it SHALL show placeholder rows shaped like its
content in place of the content. A screen's own content is what the screen is about: the event list's read
of the list, an event page's read of its event, and, where the event page has an editor, the editor's
first read of the event's document. It SHALL also show a status message naming the read ("Scanning
events…" on the list, "Reading event…" on an event page), which assistive technology announces.
Placeholders SHALL carry no event data, and SHALL NOT show an earlier state of the screen as current. Other
reads a screen makes, such as reading one job's state or re-reading a document only for its version, are
not reads of its content, and this requirement does not govern them.

The one exception is a re-read the client starts by itself because events changed, while the screen is
shown or when a hidden list is shown again (see "A shown screen re-reads in place when events change").
There, the screen keeps its current content, marked as updating, instead of showing placeholders.

The other exception is the player of an event page's "Movie" section. An operator's Refresh of an event page
that shows the section SHALL keep it, with its player as it is, while the page reads, as "The event page plays
the event's rendered movie" requires. The section SHALL show nothing of the earlier read that the read may
change while it runs: not its verdict, its file name, its size or its outdated sentence. Its heading and its
player SHALL remain, so that the page never shows an earlier state of the event as current.

#### Scenario: A slow list read
- **WHEN** the events list response takes two seconds
- **THEN** during those seconds the list shows placeholder rows and the announced message "Scanning events…",
  and no event from an earlier read

#### Scenario: A slow event read
- **WHEN** the operator opens `2024-09-01 - Sommarlov` and its read takes two seconds
- **THEN** during those seconds the page shows its heading, placeholder rows and the announced message
  "Reading event…"

#### Scenario: A Refresh keeps the movie player and nothing else
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and the operator presses Refresh, and the read takes
  two seconds
- **THEN** during those seconds the page shows its heading as a placeholder, placeholder rows and the announced
  message "Reading event…", and the "Movie" section shows its heading and its player, still playing, with no
  "Current" or "Outdated", no file name, no size and no outdated sentence

#### Scenario: A re-read after a finished render keeps the rows
- **WHEN** the list is shown, the render of `2024-06-27 - Grillning med grannar` completes, and the
  re-read takes two seconds
- **THEN** during those seconds the list keeps its rows, marked as updating, and shows no placeholder rows

#### Scenario: Reading a job shows no placeholders
- **WHEN** `2024-10-05 - Trasig`'s page is shown and reads its failed job's error text from the service
- **THEN** the page keeps its content while that read runs, and shows no placeholder rows

### Requirement: Reading a screen never changes state

Opening, refreshing, returning to, or moving between screens SHALL NOT write any file, enqueue or cancel any
job, or change any state the service holds. Such state SHALL change only through an explicit operator action
on a control that names what it does. The theme choice is a preference kept in the browser, not service
state.

The one exception is the service's thumbnail cache. Reading a clip's thumbnail MAY make the service extract
the frame and store it there. That cache is derived and rebuildable, lives outside the library, and is not
editorial or job state. Reading a screen SHALL still write nothing under the library.

The screens SHALL NOT re-read on a timer. A server push channel the client subscribes to is not polling.

#### Scenario: Browsing the dev library changes nothing
- **WHEN** the operator opens the list, refreshes it, switches it to Needs render, opens
  `2024-08-20 - Två kapitel - Tjörn`, refreshes that page, and goes back
- **THEN** every request the client made was a read, no file under the library changed, and the jobs the
  service lists are the same as before

#### Scenario: Thumbnails fill only the service's cache
- **WHEN** the service's thumbnail cache is empty and the operator opens `2024-06-27 - Grillning med grannar`
- **THEN** the cache holds a thumbnail for each of its four clips, no file under the library changed, and the
  jobs the service lists are the same as before

#### Scenario: An idle screen makes no requests
- **WHEN** the event list is shown, no job runs, and the operator does nothing for a minute
- **THEN** the client makes no HTTP request during that minute

### Requirement: The event page reorders clips within a chapter

An event's page SHALL offer an **Edit** mode on the page itself. Entering or leaving it SHALL NOT change the
page's address. Entering Edit mode SHALL read the event's editorial document from the service. When that read
fails, the page SHALL say why, using the same words it uses for a failed event read, and SHALL offer no
editing. Entering Edit mode SHALL keep keyboard focus on the control that entered it, and leaving Edit mode,
by any path, SHALL move keyboard focus to the page's level-one heading.

While in Edit mode, the editor's chapter lists and metadata fields SHALL take the place of the chapter tables,
the facts and the description. Each chapter keeps its level-two heading, and each clip row keeps the facts the
table shows: its position, the clip's name as the event page's table names it, its status in words, size and
modification time, with absent facts shown as absent. The event's verdict and latest job stay shown. Leaving
Edit mode, by any path, SHALL read the event again and show the tables. Only the operator's own actions SHALL
end Edit mode or change what it holds: a read of the event that the page would start by itself while Edit mode
is open SHALL NOT discard the edits.

In Edit mode, each chapter SHALL list its clips in the order the page shows them. The operator SHALL be able
to move a clip to any other position **within its own chapter** in each of three ways:

- by dragging the clip's handle with a mouse, pen or touch. A drag SHALL start only from the handle, and a
  tap or click on the handle SHALL NOT start one. A scroll gesture that starts anywhere else on the page
  SHALL scroll it.
- from the keyboard, on the clip's handle: one key lifts the clip, the arrow keys move it, one key drops it,
  and Escape cancels, leaving the order as it was
- with a **Move up** and a **Move down** control on every movable row. After such a move, keyboard focus SHALL
  stay on the moved clip's row.

Every keyboard or control move, and every drop or cancel, SHALL be announced to assistive technology with the
clip's name, as the event page's table names it, and its position out of the number of clips the chapter plays
(its ignored clips, and the missing clips the operator removed, are not counted). Move up and Move down SHALL
NOT take a clip into another chapter. A clip changes chapter only when it is dragged into another chapter (see
"Edit mode drags clips between chapters") or moved with Move marked to… (see "Edit mode moves the marked clips to a chapter"). A missing clip's drag SHALL stop at its own chapter's edge. Among the clips
a chapter held when Edit mode opened and still holds, the page SHALL count as moved the fewest clips whose
moves explain the new order, so that moving one clip from position 1 to position 5 moves one clip, not five.
Each such clip counted as moved SHALL show its position from when Edit mode opened. A clip moved in from
another chapter SHALL count as one moved clip, and SHALL show the chapter it came from instead.

Clips the event ignores are not part of the play order. Each chapter SHALL list them after its other clips,
marked as ignored, and they SHALL NOT be movable or counted in the chapter's positions. A missing clip SHALL
stay listed and movable, and SHALL never be dropped from its chapter, except when the operator removes it
with its own control (see "Edit mode removes a missing clip from reel.yaml on request"). A NEW clip SHALL be
movable like any other.

#### Scenario: Dragging a clip to the front
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator drags `s1710004.mp4` above
  `s1710001.mp4`
- **THEN** the chapter lists `s1710004.mp4`, `s1710001.mp4`, `s1710002.mp4`, `s1710003.mp4`, and
  `s1710004.mp4` shows that it was at position 4

#### Scenario: Reordering from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator focuses the handle of `Kvällen/s1710002.mp4`,
  lifts it, presses Down once, and drops it
- **THEN** `Kvällen` lists `s1710003.mp4`, `s1710002.mp4`, `s1710004.mp4`, and a screen reader hears that
  `s1710002.mp4` moved to position 2 of 3

#### Scenario: Escape cancels a keyboard move
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator lifts `s1710001.mp4` from the keyboard, moves
  it two places, and presses Escape
- **THEN** the clip is back at position 1, the order is unchanged, and the cancel is announced

#### Scenario: The move controls keep focus on the moved clip
- **WHEN** on `2024-09-01 - Sommarlov`, the operator activates **Move down** on `s1710002.mp4`
- **THEN** `s1710002.mp4` is at position 2, keyboard focus is still on its row, and its move is announced

#### Scenario: A clip cannot leave its chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator activates **Move up** on `Kvällen/s1710002.mp4`,
  the first clip of `Kvällen`
- **THEN** the control says that it is unavailable, nothing moves, and `Main` is unchanged: only a drag or Move marked to… takes a clip into another chapter

#### Scenario: A missing clip cannot leave its chapter
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator drags `borttagen.mp4`
  downward toward `Morgon`, past the bottom of `Main`, and releases it
- **THEN** the dragged clip stopped at the bottom edge of `Main`, `borttagen.mp4` is still at position 3 of
  `Main`, and `Morgon` plays no clip

#### Scenario: An ignored clip is listed but cannot move
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` lists `s1710001.mp4` and then `s1710004.mp4`, marked as ignored, and `s1710004.mp4` has no
  handle and no move controls

#### Scenario: A missing clip keeps its place
- **WHEN** Edit mode opens on `2024-09-01 - Sommarlov`, whose `reel.yaml` lists the missing `borttagen.mp4`
  last
- **THEN** `borttagen.mp4` is listed at position 3, marked as missing, and can be moved like the others

#### Scenario: A large chapter is fully editable
- **WHEN** an event holds 400 clips in one chapter
- **THEN** all 400 are listed in Edit mode, and any of them can be moved to any position in the chapter

#### Scenario: The editorial document cannot be read
- **WHEN** the operator enters Edit mode on an event whose `reel.yaml` became unparseable after the page was
  read
- **THEN** the page shows the unparseable-document failure in words, with the service's detail, and offers
  no editing

### Requirement: The event page edits the event's metadata

In Edit mode the page SHALL offer the event's title, date, location and description as editable fields. The
fields SHALL be filled with what the event's `reel.yaml` itself says, not with the values the page resolves
from the folder name. A field that `reel.yaml` leaves unset SHALL be shown empty. When the page shows a value
for that field derived from the folder name, that value SHALL be shown next to the field as inherited from
the folder name. A field the operator empties, after `reel.yaml` had set it, SHALL say that it will inherit
from the folder name once saved, and SHALL NOT present the value `reel.yaml` set as the folder name's.

A field left empty, or holding only whitespace, SHALL be saved as unset, so that it inherits again. The date
SHALL be entered as a calendar date. A date the operator has not finished entering SHALL NOT be saved, as
unset or otherwise: the page SHALL say that the date is incomplete and SHALL NOT offer to save until it is
completed or cleared. Beyond that, the page SHALL leave the judgement of whether a date or title is usable,
for example a date in the future, to the service. When the service refuses one, the page SHALL show the
service's explanation at the date and title fields.

#### Scenario: Authored values fill the form
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose `reel.yaml` sets the title
  `Grillkväll med grannarna` and the date `2024-06-27`
- **THEN** the title field holds `Grillkväll med grannarna`, the date field holds `2024-06-27`, and the
  location and description fields are empty

#### Scenario: Inherited values are shown as inherited
- **WHEN** Edit mode opens on `2024-07-14 - kalas`, which has no `reel.yaml`
- **THEN** every field is empty, and the title and date fields show `Kalas` and `2024-07-14` as inherited from
  the folder name

#### Scenario: Clearing a field makes it inherit
- **WHEN** the operator empties the title field of `2024-06-27 - Grillning med grannar`
- **THEN** the field says it will inherit from the folder name, without naming `Grillkväll med grannarna` as
  the folder name's title; and after saving, `reel.yaml` sets no title and the page shows the folder name's
  title, `Grillning med Grannar`

#### Scenario: An unfinished date is never saved as unset
- **WHEN** the operator clears only the day of the date of `2024-06-21 - Midsommar - Dalarna`, leaving the
  date incomplete
- **THEN** the page says the date is incomplete and offers no Save, and `reel.yaml` still sets `2024-06-21`

#### Scenario: A future date is refused at the field
- **WHEN** the operator sets the date of `2024-06-21 - Midsommar - Dalarna` to a day after today and saves
- **THEN** the date and title fields show the service's explanation that the date is in the future, and
  `reel.yaml` is unchanged

### Requirement: Saving an edit writes only what the operator changed

Edits SHALL be saved only when the operator asks. While Edit mode holds changes that differ from what it
read, the page SHALL keep visible:

- which metadata fields changed
- how many clips moved, counted as the reorder requirement counts them
- how many missing clips will be removed from `reel.yaml`
- how many chapters were added, renamed and deleted, and whether the chapters' order changed
- how many cuts were added and how many removed
- when saving would add NEW clips to `reel.yaml`, how many
- a **Reset** control, which restores what was read
- a **Save** control

An edit that is undone SHALL leave no change to save: a clip moved and moved back, within its chapter or to
another chapter and back, a removal undone, a chapter renamed back or moved back, a deleted chapter restored,
a chapter added and deleted again, a cut added and removed again, a removed cut restored, or a removed cut
added again with the same times and reason. The cut counts SHALL count only the clips whose saved cuts would
change.

Saving SHALL write the editorial document exactly as Edit mode read it, with only the operator's edits
applied:

- **Edited metadata fields** take their new values.
- **A chapter whose order changed** is written in the order shown, with its ignored clips and its removed
  clips left out, and its other missing clips and its NEW clips kept in place. A chapter's order changes when
  it is reordered, when a missing clip is removed from it, and when a clip is moved into it or out of it.
- **A removed clip's own per-clip properties** (its trims, title-clip choice, rotation and exclusion) are left
  out with it, since `reel.yaml` no longer lists the clip.
- **A clip moved to another chapter keeps its per-clip properties.**
- **A clip whose cuts changed** gets the cuts its panel lists, in that order, without the removed ones. Its
  title-clip choice, rotation and exclusion stay as read. When it is then left with no cut and none of those
  set, its entry is left out of the per-clip properties rather than written empty.
- **A chapter that plays a NEW clip whose cuts changed** is written as a chapter whose order changed, because
  `reel.yaml` can hold a clip's cuts only while a chapter lists the clip.
- **Everything else** is written exactly as read: every other chapter, every other per-clip property, the
  ignored clips and the look.

Two kinds of save SHALL instead write every chapter the page lists, in the order the chapters are shown and
under its current name. Each chapter's clips are written in the order shown, without its ignored and removed
clips, and with its missing and NEW clips in place. A deleted chapter is left out.

- **A save that changes the chapters themselves**: a chapter added, renamed or deleted, or the chapters'
  order changed. Every NEW clip then joins `reel.yaml` in the chapter where the page shows it. So after the
  save, the page shows each clip where it showed it before, and a chapter's name only decides where clips
  added to its folder later go.
- **A save that changes any order, any chapter or any cut when `reel.yaml` names no chapters**, either because
  the event has no `reel.yaml` or because its `reel.yaml` sets none.

A save that changes only metadata SHALL still write the chapters as read, and none when `reel.yaml` names
none.

The save SHALL be conditional on the editorial state being the one Edit mode read, so that a change made
elsewhere in the meantime is detected rather than overwritten. While a save is in flight, the page SHALL
NOT start another save or accept further edits. The control that started it (Save, Retry, or the overwrite
after a conflict) SHALL show that it is busy and SHALL keep keyboard focus until the service answers.

When a save succeeds, the page SHALL:

- confirm it
- leave Edit mode
- read the event again, which then shows the event as needing a render
- read the list again the next time the list is shown

A save SHALL NOT enqueue a render. Entering Edit mode also has a guard. When the event's chapters as the page
shows them no longer agree with the editorial document it just read (the event changed on disk in between),
Edit mode SHALL say so and offer to read the event again, and SHALL NOT offer to save.

#### Scenario: Reordering one chapter leaves the rest untouched
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `Kvällen/s1710004.mp4` (NEW) to the
  front of `Kvällen` and saves
- **THEN** `reel.yaml` lists `Kvällen` as `Kvällen/s1710004.mp4`, `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, lists `Main` as `s1710001.mp4` alone, and still ignores `s1710004.mp4`

#### Scenario: The editor says a reorder adopts NEW clips
- **WHEN** on `2024-08-02 - Badutflykt - Varberg`, whose `reel.yaml` lists two of its three clips, the
  operator moves `s1710001.mp4` below `s1710003.mp4`
- **THEN** before saving, the page says that saving adds 1 new clip to `reel.yaml`, and after saving,
  `reel.yaml` lists `s1710003.mp4`, `s1710001.mp4` and `s1710004.mp4`

#### Scenario: A missing clip survives a reorder
- **WHEN** on `2024-09-01 - Sommarlov`, the operator swaps `s1710002.mp4` and `s1710004.mp4` and saves
- **THEN** `reel.yaml` lists `s1710004.mp4`, `s1710002.mp4` and `borttagen.mp4`, and `borttagen.mp4` keeps
  its end-of-line comment

#### Scenario: A metadata edit leaves the clip order alone
- **WHEN** the operator changes only the location of `2024-06-27 - Grillning med grannar` to `Hönö` and saves
- **THEN** `reel.yaml` gains the location, and its chapters are unchanged

#### Scenario: A document without chapters stays without chapters
- **WHEN** the operator changes only the title of `2024/Blandat`, whose `reel.yaml` names no chapters, and
  saves
- **THEN** the saved `reel.yaml` has the new title and still names no chapters

#### Scenario: A first reorder writes every chapter
- **WHEN** an event with clips in two chapter folders has no `reel.yaml`, and the operator reorders one
  chapter and saves
- **THEN** the new `reel.yaml` lists both chapters with every clip: the reordered one in its new order, the
  other in the order the page showed

#### Scenario: An undone move leaves nothing to save
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator moves `s1710002.mp4` down and then back up
- **THEN** the page shows no unsaved changes, and offers no Save

#### Scenario: Save keeps focus while it is in flight
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a reorder pending, the operator presses Enter on
  Save and the service has not answered yet
- **THEN** Save shows that it is busy, keyboard focus is still on Save, a second Enter sends no second save,
  and the clip lists and fields accept no edits

#### Scenario: A saved edit makes the event need a render
- **WHEN** the operator saves a new title for `2024-06-21 - Midsommar - Dalarna`
- **THEN** the page confirms the save, leaves Edit mode, and shows the new title and that the event needs a
  render because of the edit. No job was enqueued, and on returning to the list, the list is read again and
  shows the new title.

#### Scenario: The event changed on disk before editing
- **WHEN** a clip is added to `reel.yaml` of `2024-09-01 - Sommarlov` by hand after its page was read, and
  the operator then enters Edit mode
- **THEN** Edit mode says the event changed since the page was read, offers to read it again, and offers no
  Save

#### Scenario: A removed clip leaves with its own properties only
- **WHEN** on `2024-09-02 - Två saknade`, whose `reel.yaml` lists the missing `gone-a.mp4` with an end-of-line
  comment in its root chapter and gives the missing `Kväll/gone-b.mp4` of its `Kväll` chapter a trim, the
  operator removes `Kväll/gone-b.mp4` and saves
- **THEN** `reel.yaml` lists `Kväll` as `Kväll/s1710003.mp4` alone and holds no properties for
  `Kväll/gone-b.mp4`, and its root chapter, including `gone-a.mp4` and its comment, is unchanged

#### Scenario: A removal is counted apart from moves
- **WHEN** on `2024-09-01 - Sommarlov`, the operator removes `borttagen.mp4` and moves `s1710004.mp4` to the
  front
- **THEN** the page says that 1 clip moved and that 1 missing clip will be removed

#### Scenario: Moving clips writes the two chapters
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710002.mp4` and `s1710003.mp4` from
  `Kvällen` to `Main` and saves
- **THEN** `reel.yaml` lists the default chapter as `s1710001.mp4`, `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, and `Kvällen` as `Kvällen/s1710004.mp4`, which was NEW. The save bar said before the
  save that it adds 1 new clip to `reel.yaml`, and `s1710004.mp4` is still ignored.

#### Scenario: A moved clip keeps its cut
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` gives `Kvällen/s1710002.mp4` a cut from 0 to
  1.5 seconds, and the operator moves that clip to `Main` and saves
- **THEN** `reel.yaml` lists `Kvällen/s1710002.mp4` in the default chapter and still gives it that cut

#### Scenario: A renamed chapter keeps its new clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `Kväll` and saves
- **THEN** `reel.yaml` lists `Kväll` as `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and
  `Kvällen/s1710004.mp4` and names no chapter `Kvällen`. The page shows `Kväll` with those three clips, none of
  them new.

#### Scenario: A chapter added to a document without chapters
- **WHEN** the operator adds a chapter `Morgon` to `2024/Blandat`, whose `reel.yaml` names no chapters, and
  saves
- **THEN** `reel.yaml` lists the default chapter with `s1710003.mp4`, then `Morgon` with no clips, and the page
  shows `s1710003.mp4` as included, no longer new

#### Scenario: A cut writes only its clip's cuts
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a cut from `0` to `1.5` to `s1710001.mp4`
  and saves
- **THEN** `reel.yaml` gives `s1710001.mp4` one cut, from 0 to 1.5 seconds with the reason `manual`. It holds
  no other per-clip properties than before, its chapters list the same clips in the same order, and its
  metadata is unchanged. The page then shows "1 cut · −1.5 s" beside `s1710001.mp4`.

#### Scenario: A cut on a new clip adds the clip to reel.yaml
- **WHEN** on `2024-08-02 - Badutflykt - Varberg`, whose `reel.yaml` lists two of its three clips, the operator
  adds a cut from `4` to `6` to the NEW `s1710004.mp4`
- **THEN** before saving, the save bar says that 1 cut was added and that saving adds 1 new clip to `reel.yaml`
- **WHEN** the operator saves
- **THEN** `reel.yaml` lists `s1710001.mp4`, `s1710003.mp4` and `s1710004.mp4` and gives `s1710004.mp4` that cut,
  and the page shows `s1710004.mp4` as included, no longer new

#### Scenario: A clip left without cuts leaves no empty entry
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds and nothing else, and the operator removes that cut and saves
- **THEN** `reel.yaml` holds no entry for `s1710003.mp4` among its per-clip properties, and its chapters are
  unchanged

#### Scenario: A cut on a clip of a document without chapters
- **WHEN** the operator adds a cut from `1` to `2` to `s1710003.mp4` of `2024/Blandat`, whose `reel.yaml` names
  no chapters, and saves
- **THEN** `reel.yaml` lists the default chapter with `s1710003.mp4` and gives it that cut

#### Scenario: Undone cut edits leave nothing to save
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a cut to `s1710001.mp4` and removes it
  again
- **THEN** the page shows no unsaved changes, and offers no Save

### Requirement: A failed save keeps the operator's edits and says why

When a save fails, the page SHALL keep every unsaved edit and SHALL say why. It SHALL take the distinction
from the service's answer, not from its prose:

- **The event changed since Edit mode read it** (a conflict). The page SHALL say so and offer two choices:
  - "Reload latest", which discards the edits and reads the current state
  - "Overwrite with mine", which asks for confirmation, with cancelling as the choice focused first, and
    then saves the edits over the other change
- **The service refuses the date or title as unusable.** The explanation SHALL be shown at those fields.
  Any other refused state SHALL be shown with the service's detail.
- **The event no longer exists.** The page SHALL say so and offer the way back to the list.
- **The service could not read or save the event's files.** The page SHALL show the failure kind in the same
  words the list uses when the answer carries one, and the service's detail, and SHALL offer to retry.
- **The service does not answer.** The page SHALL say the service is not reachable and SHALL offer to retry.

#### Scenario: A conflicting edit made elsewhere
- **WHEN** the operator is editing `2024-06-27 - Grillning med grannar`, its `reel.yaml` title is changed by
  hand, and the operator then saves
- **THEN** the page says the event changed since it was read, the operator's edits are still shown, and
  `reel.yaml` still holds the hand-made title

#### Scenario: Overwriting after a conflict
- **WHEN** after that conflict the operator chooses "Overwrite with mine" and confirms
- **THEN** the operator's version is saved, and the page confirms the save

#### Scenario: Reloading after a conflict
- **WHEN** after that conflict the operator chooses "Reload latest"
- **THEN** the edits are discarded, and the page shows the hand-made title

#### Scenario: A read-only event folder
- **WHEN** the operator saves a reorder of `2024-09-01 - Sommarlov` while its folder cannot be written
- **THEN** the page says the save was refused, shows the service's detail naming the operating-system error,
  keeps the reorder, and offers Retry. Once the folder is writable again, Retry saves it.

#### Scenario: The service is down
- **WHEN** the operator saves a reorder of `2024-08-02 - Badutflykt - Varberg` while the service is not
  answering
- **THEN** the page says the service is not reachable, keeps the edits, and offers Retry

### Requirement: Unsaved edits are never discarded silently

While Edit mode holds unsaved changes, every way of leaving them SHALL ask first:

- **Closing or reloading the browser tab** SHALL trigger the browser's own leave-page confirmation.
- **Back, Forward, following a link, or typing another address in the app** SHALL keep the page and ask
  "Discard unsaved changes?". Its default choice keeps editing: choosing it, or pressing Escape, SHALL
  leave the page, its address and its edits as they were. Discarding SHALL continue to where the operator
  was going.
- **Refreshing the event and leaving Edit mode** SHALL ask the same question.

Reset, and "Reload latest" after a conflict, are themselves named discards and SHALL NOT ask. With no unsaved
changes, nothing SHALL ask.

#### Scenario: Back asks before discarding
- **WHEN** the operator has reordered clips on `2024-06-27 - Grillning med grannar` and presses the browser's
  Back
- **THEN** the event page stays, with its address and the reorder, and asks "Discard unsaved changes?"

#### Scenario: Keeping the edits
- **WHEN** the operator answers that question with Escape
- **THEN** the event page, its address and its edits are unchanged

#### Scenario: Discarding the edits
- **WHEN** the operator answers that question with Discard
- **THEN** the list is shown, and `reel.yaml` is unchanged

#### Scenario: Reloading the tab
- **WHEN** the operator reloads the browser tab with unsaved edits on `2024-06-27 - Grillning med grannar`
- **THEN** the browser asks for confirmation before leaving the page

#### Scenario: Refresh asks too
- **WHEN** the operator presses Refresh on the page of `2024-06-27 - Grillning med grannar` with unsaved edits
- **THEN** the page asks "Discard unsaved changes?" before reading the event again

#### Scenario: Nothing to lose, nothing asked
- **WHEN** the operator enters Edit mode on `2024-06-27 - Grillning med grannar`, changes nothing, and presses
  Back
- **THEN** the list is shown without a question

### Requirement: Events that need attention open a page that can fix their metadata

Every row of the list's "Needs attention" group SHALL link to its event's page. When the page's read of an
event fails with the unusable-metadata kind (no real date, no title, or a date in the future), the page SHALL
show that failure, as it does today, together with the metadata form. The form SHALL be filled from the
event's `reel.yaml`, or left empty when there is none. It SHALL save under the same rules as Edit mode, and
SHALL write no chapters the event's `reel.yaml` does not already hold. After a successful save, the page SHALL
read the event again and show it. The list SHALL be read again the next time it is shown. For every other
failure kind, the page SHALL show the failure only, since its detail states the fix.

#### Scenario: The impossible date is fixed from the page
- **WHEN** the operator follows the "Needs attention" row of `2024-02-30 - Omöjligt datum`, enters the date
  `2024-02-29` in the form shown with the failure, and saves
- **THEN** the page reads the event again and shows it with its clip and its title `Omöjligt Datum`. On
  returning, the list shows it among the 2024 events, and it is no longer under "Needs attention".

#### Scenario: A refused fix keeps the failure
- **WHEN** on the same page the operator enters a date after today and saves
- **THEN** the date and title fields show the service's explanation, and the failure is still shown

#### Scenario: Other failures offer no form
- **WHEN** an event's `reel.yaml` cannot be parsed, and the operator follows its "Needs attention" row
- **THEN** the page shows the unparseable-document failure and its detail, and no form

### Requirement: The client follows render jobs live over one connection

The client SHALL learn about render jobs from the service's jobs WebSocket (`/api/v1/ws/jobs`), addressed by
path on the serving origin. A browser tab SHALL hold **at most one** such connection, however many screens
or rows show job state, and SHALL NOT poll any jobs or events endpoint on a timer. The connection is a push
channel, not polling.

- A **snapshot** frame SHALL replace the client's set of active jobs. A **delta** frame SHALL update only the
  jobs it carries. A **heartbeat** frame SHALL change nothing the client shows: it only proves the
  connection is alive.
- The client SHALL treat a connection that has delivered no frame, of any type, for 40 seconds as lost,
  counted from the moment the connection was created and again from each frame. It SHALL then drop that
  connection and reconnect exactly as after a close, without waiting for the browser to report one,
  because a connection that died without a close can stay open to the browser for minutes. An idle but
  healthy connection stays well inside the window, since the service sends a frame at least every 15
  seconds.
- A job the client knew as queued or running that is absent from a new snapshot ended while the connection
  was down. The client SHALL read that job once from the service and show its real terminal state. It MUST
  NOT keep showing that job as active, and MUST NOT guess its outcome.
- After any close, including a normal one, the client SHALL reconnect:
  - after a randomized delay that grows with each failed attempt, capped at about 30 seconds
  - the delay resets only once a frame has arrived on the new connection
  - it reconnects at once when the browser reports it is back online
- The app header SHALL show the connection's state in words: live, connecting, or reconnecting. While live,
  it SHALL show how many render jobs are rendering and how many are queued, leaving out a count that is zero. A
  `proxy` job is counted in neither.
  While not live, it SHALL NOT show counts, because counts from a lost connection are not current.

#### Scenario: One connection however many views follow jobs
- **WHEN** the operator has the list open, opens `2024-06-27 - Grillning med grannar`, and returns
- **THEN** the tab has had one jobs connection open throughout, and no request repeats on a timer

#### Scenario: The header counts active jobs while live
- **WHEN** the connection is live, `2024/Blandat` has a queued job, and no worker is running
- **THEN** the header shows the connection as live and 1 queued, with no rendering count

#### Scenario: A render that finished during a disconnect is shown as finished
- **WHEN** a job for `2024-06-27 - Grillning med grannar` was running, the service was restarted, and the
  worker finished the job before the connection came back
- **THEN** after reconnecting, the event's job shows as rendered, not as running, and no toast announces it

#### Scenario: An idle connection stays live
- **WHEN** the connection is live, no job is active, and the service sends nothing but heartbeats for
  several minutes
- **THEN** the header keeps showing the connection as live, the tab opens no second connection, and
  nothing on any screen changes

#### Scenario: A connection that went silent is dropped
- **WHEN** the connection is live and the service stops sending frames without closing the connection (a
  laptop that was suspended and woke on a dead network, a path that dropped silently)
- **THEN** within 40 seconds of the last frame the header shows that the client is reconnecting, without
  job counts, and the client opens a new connection after its randomized delay
- **AND** when the new connection delivers its snapshot, the header shows live again, with no reload

#### Scenario: A lost connection says so
- **WHEN** the service stops answering while the app is open
- **THEN** the header shows that the client is reconnecting, without job counts, and it becomes live again,
  with no reload, once the service is back

#### Scenario: A proxy job is not counted as a render
- **WHEN** the connection is live and the only active job is a `proxy` job that is running
- **THEN** the header shows the connection as live and no rendering or queued count

### Requirement: A render's progress is shown live

Wherever a render job is shown for an event, the client SHALL show the newest **render** job it knows for that
event. That is the live state when the connection carries one, and otherwise the latest render job the last read
returned. A job is a render or a proxy job (the service reports its kind on every job). A proxy job SHALL NOT be shown as a render: it SHALL NOT be the job a render region, a list row or a
notification shows, SHALL NOT replace a render job as the newest, and SHALL NOT mark a shown render job as ended.
Only the Timeline's Prepare state shows a proxy job (capability `event-timeline`). For one and the same job:

- a finished state the client has learned SHALL never be replaced by an earlier queued or running state
- between two queued or running states of the job, while the connection is live, the one it carries SHALL
  be shown: it reports every change
- while the connection is not live, the state it carried last is only last known, and the job's progress
  indicator SHALL be marked as last known. When the screen's latest read shows the same queued or running job
  further along, the screen SHALL show the read's state instead, still marked as last known. A running state
  is further along than a queued one, a run that started later is further along than an earlier run, and
  more progress is further along than less. What the read does not carry, such as a requested cancel,
  stays shown as last known with the read's state.

The job SHALL be shown as follows:

- **queued:** a progress indicator with no value, and the words "Waiting for a worker"
- **running with no progress reported yet:** a progress indicator with no value, and a starting state
- **running:** a determinate progress bar from the job's progress fraction, and its percentage in whole
  percent, rounded down. While the job is running, the bar and the percentage SHALL stop at 99%: the service
  reports the full fraction a moment before it reports the job done, and only the done state says that the
  render finished.
- **cancel requested, not yet stopped:** that it is cancelling
- **done:** that it rendered, with the job's time as the service reported it, labelled as a finish time
  only when the service reported one
- **failed:** that it failed; on the event's page also the job's own error text from the service
- **canceled:** that it was canceled, as a neutral state, not as an error

On the event's page, the job's progress indicator SHALL keep one height through every queued or running
state, so the render region does not grow when the first percentage or the time-left estimate arrives.

While running, the event's page SHALL show an estimate of the time left, computed from the progress
reported over time. It SHALL stay hidden until the job is past 5% and enough progress has been observed,
and it SHALL NOT be shown increasing. It SHALL be shown only beside the progress it was computed from, so
not beside progress that a read reported while the connection was down. The client MUST NOT invent a
percentage, a time or an error text the service did not report. Progress changes SHALL NOT be announced
to assistive technology on every update; only state changes (queued, running, cancelling, and the
terminal states) are announced.

A job that this tab started or attached to, and that finishes while the connection is live, SHALL raise a
notification: rendered, failed, or canceled. A job whose end the client learns only by reading it (after a
reconnect, or because a screen still showed it as active) SHALL NOT raise one, nor SHALL a job this tab
neither started nor attached to. One ending SHALL raise at most one notification: a cancel whose answer
already said the job was canceled or had finished raises no second one. A notification SHALL name the event
by its title, as its page and its list row do, followed by its date when it has one, since titles repeat;
an event with no title SHALL be named by its folder name.

#### Scenario: A queued job waits for a worker
- **WHEN** the operator opens `2024/Blandat`, whose job is queued, with no worker running
- **THEN** the page shows a progress indicator with no value, and "Waiting for a worker"

#### Scenario: Progress moves while the page is open
- **WHEN** a worker runs the job for `2024-06-27 - Grillning med grannar` while its page is open
- **THEN** the bar and percentage advance with each update, with no reload and no refresh

#### Scenario: A failed render shows why
- **WHEN** the operator opens `2024-10-05 - Trasig`, whose latest job failed
- **THEN** the page shows that the job failed, with the error text the service recorded for it, while the
  list row for it says only that it failed

#### Scenario: A refresh corrects a missed ending
- **WHEN** the page of `2024-10-05 - Trasig` shows a job it started as queued, the job failed without the
  connection reporting it, and the operator refreshes the page
- **THEN** the page shows the job as failed, with its error text, and no longer as queued

#### Scenario: A finished render is announced once
- **WHEN** a render the operator started from `2024-06-27 - Grillning med grannar`'s page completes
- **THEN** one notification says it rendered, and reopening or reconnecting does not repeat it

#### Scenario: A short render shows no estimate
- **WHEN** a job completes before 5% of it had been reported, or before enough progress was observed
- **THEN** no time-left estimate was shown for it

#### Scenario: A refresh during a lost connection shows the job further along
- **WHEN** the operator started a render of `2024-06-27 - Grillning med grannar` from its page, the
  connection was lost while the job waited for a worker, a worker then started the job, and the operator
  refreshes the page
- **THEN** the page shows the job rendering, with the progress the read returned, marked as last known, and
  no longer as queued

#### Scenario: A render at its full fraction is not yet done
- **WHEN** the worker reports the job for `2024-06-27 - Grillning med grannar` at its full progress fraction,
  a moment before it reports the job done
- **THEN** the page shows the job rendering at 99%, with a bar that is not full, and shows it rendered only
  once the service reports the job done

#### Scenario: A notification names the event as its page does
- **WHEN** a render the operator started from `2024-06-27 - Grillning med grannar`'s page completes
- **THEN** the notification names the event "Grillkväll med grannarna", the title its page shows, with its
  date 2024-06-27, and not its folder name

#### Scenario: Two events with one title are told apart
- **WHEN** renders the operator started from the pages of `2023-06-23 - Midsommar - Dalarna` and
  `2024-06-21 - Midsommar - Dalarna` complete
- **THEN** one notification names "Midsommar" with 2023-06-23, and the other names "Midsommar" with
  2024-06-21

#### Scenario: The progress indicator does not shift the page
- **WHEN** the page of `2024-06-27 - Grillning med grannar` shows its job starting, and the first progress
  arrives
- **THEN** the progress indicator keeps its height while the percentage appears, and the render region
  does not grow

#### Scenario: The estimate does not shift a phone's page
- **WHEN** the page of `2024-06-27 - Grillning med grannar` is shown 320 pixels wide while its job renders,
  and the time-left estimate appears beside the percentage
- **THEN** the render region keeps its height

#### Scenario: A proxy job does not take a render's place
- **WHEN** the render of `2024-06-27 - Grillning med grannar` finished, the operator then pressed Prepare proxies
  on its Timeline, and the `proxy` job is running
- **THEN** the page's render region still shows the render as rendered, with its own time, and no queued or
  running render; the list row of that event shows the same, not a running job

### Requirement: A queued or running render can be cancelled

While an event's job is queued or running, its page SHALL offer a **Cancel** control:

- a queued job is cancelled without a confirmation while the connection is live
- a running job is cancelled only after the operator confirms, in a dialog that says the partial render is
  discarded and any existing movie stays as it was. So is a job the page shows as queued while the
  connection is not live, since it may have started meanwhile; that dialog also says the render may have
  started, for as long as the connection is down and the job is not shown running. The dialog opens with
  focus on the action that keeps the job rendering.

While the dialog is open and no cancel request is in flight, if the job ends, a cancel of it is requested
elsewhere, or another job of the event shows in its place, the dialog SHALL close by itself and send
nothing. Keyboard focus SHALL then move to the page's job status, whose words say how the job stands, also
when a Cancel control for another job is shown.

A pressed cancel control SHALL send one request, and until the answer arrives it SHALL stay in place, keep
keyboard focus, be marked busy, and ignore further presses.

Once the service answers, the page SHALL say which outcome occurred, in words, through a mapping defined
over the generated cancel-outcome union. The client's type-check then fails when the vocabulary gains,
loses or renames a member. The client MUST NOT show an outcome slug verbatim. After a running job is
flagged for cancellation, the page SHALL show it as cancelling until the service reports it canceled or
finished. An unknown job SHALL be reported as not found.

#### Scenario: A queued job is cancelled at once
- **WHEN** the operator presses Cancel on `2024/Blandat`'s queued job while the connection is live
- **THEN** no confirmation is asked, one notification says the job was canceled before it started and
  names the event, and the page shows the job as canceled

#### Scenario: A running job is cancelled after confirmation
- **WHEN** the operator presses Cancel while `2024-06-27 - Grillning med grannar` is rendering, and confirms
- **THEN** the page shows the job as cancelling, then as canceled once the worker stops, no partial movie
  file is left in the output directory, and any movie rendered earlier is unchanged

#### Scenario: Declining the confirmation changes nothing
- **WHEN** the operator presses Cancel on a running job and then dismisses the dialog
- **THEN** no cancel request is sent, and the job keeps rendering

#### Scenario: The job finished before the cancel arrived
- **WHEN** the job had already finished when the cancel request reached the service
- **THEN** the page says the job had already finished, and shows its terminal state

#### Scenario: Cancel asks while the connection is down
- **WHEN** the page of `2024/Blandat` shows its job as queued while the connection is lost, and the operator
  presses Cancel
- **THEN** a confirmation opens that says the render may have started, no cancel request is sent until the
  operator confirms, and dismissing the dialog sends none

#### Scenario: A job refreshed as running asks before it is cancelled
- **WHEN** the page of `2024-06-27 - Grillning med grannar` showed its job as queued when the connection was
  lost, a worker then started the job, and the operator refreshes the page and presses Cancel
- **THEN** a confirmation opens first, and no cancel request is sent until the operator confirms

#### Scenario: The cancel question closes when the render ends first
- **WHEN** the operator pressed Cancel while `2024-06-27 - Grillning med grannar` renders, and the render
  completes while the confirmation is open
- **THEN** the dialog closes by itself, no cancel request is sent, the page shows the job rendered, and
  keyboard focus is on the page's job status

#### Scenario: The cancel question closes when another job takes its place
- **WHEN** the operator pressed Cancel on `2024/Blandat`'s queued job while the connection was lost, and when
  the connection is back that job was canceled elsewhere and another job is queued for the event
- **THEN** the dialog closes by itself, no cancel request is sent, and keyboard focus is on the page's job
  status, not on the other job's Cancel control

#### Scenario: The cancel question stops saying the render may have started
- **WHEN** the operator pressed Cancel on `2024/Blandat`'s queued job while the connection was lost, and the
  connection comes back with the job still queued while the confirmation is open
- **THEN** the confirmation no longer says the render may have started, and no cancel request is sent until
  the operator confirms

### Requirement: The event list shows live job state and offers a render

Each event row the list shows with its render state SHALL show that event's job as the progress
requirement describes, and SHALL keep its height when the job's first percentage arrives. The job the
connection carries SHALL be matched to the row whose event id equals the
job's event directory. A row that needs a render, has no queued or running job, and lists no missing clip that
blocks a render (one that `reel.yaml` does not exclude) SHALL offer a compact **Render** control, whose accessible name names the event ("Render"
followed by the event's folder name), so that a list of Render controls is told apart by assistive
technology. At phone width, the row's job state keeps its "Last job" label whenever the row shows a job,
including one the connection reported after the list was read, and a row that shows no job has no such
label. The row's Render control, once
pressed, behaves as the page's: one request, focus kept, marked busy. Its answers are handled as on the
event's page, except as follows:

- when a job is created, the client tells assistive technology that the event's render was queued; when a
  job is already queued or running for the event, it tells it so. Neither answer raises a visible
  notification: the row shows the job at once, and a notification would cover the controls of the rows
  below it. The row then shows that job, and when the removed Render had keyboard focus, focus moves to
  the row's event link.
- when the event is up to date, a notification says so and links to the event's page. The list does not
  force a render.
- when another event claims the same movie file, an error notification names the other events and links to
  the pressed event's page.

A row's notifications, and what it tells assistive technology, SHALL name the pressed event as the
progress requirement's notifications do: by its title followed by its date, or by its folder name when it
has no title. The output-collision notification is the exception: it SHALL name the pressed event and the
other events by their folder names, since events that claim the same movie file share their date, title
and location.

A row that needs a render, has no queued or running job, but lists a missing clip that blocks a render SHALL
NOT offer Render, for the same reason as the event's page. In its place, the row SHALL say, in words with an
icon, that missing clips block its render. The row SHALL take which missing clips block from the list
response's `blocking_missing_count`. The row's count of missing clips, which includes an excluded one,
stays shown.

Error rows under "Needs attention" SHALL NOT offer Render.

#### Scenario: A row shows a queued job live
- **WHEN** a job is enqueued for `2024-08-02 - Badutflykt - Varberg` from its page, and the operator returns
  to the list
- **THEN** its row shows the job queued, and its progress once a worker runs it, with no refresh

#### Scenario: A row keeps its height when progress starts
- **WHEN** the list shows the job for `2024-06-27 - Grillning med grannar` starting, and the first progress
  arrives
- **THEN** the row shows the percentage and keeps its height

#### Scenario: A stale row is rendered from the list
- **WHEN** the operator presses Render on the `2024-08-20 - Två kapitel - Tjörn` row
- **THEN** a job is enqueued for that event, and the row shows it queued

#### Scenario: Fresh rows and error rows offer no Render
- **WHEN** the list shows `2023-06-23 - Midsommar - Dalarna`, which is up to date, and the `2024-02-30 -
  Omöjligt datum` error row
- **THEN** neither offers Render

#### Scenario: Live rows fit a phone-width window
- **WHEN** the list is shown 390 pixels wide, the `2024-08-20 - Två kapitel - Tjörn` row shows a job
  enqueued after the list was read, and the `2024-06-27 - Grillning med grannar` row offers Render
- **THEN** the page does not scroll horizontally, the Två kapitel job is labelled "Last job", and the
  Grillning control is announced as "Render 2024-06-27 - Grillning med grannar"

#### Scenario: A row with a missing clip offers no Render
- **WHEN** the list shows `2024-09-01 - Sommarlov`, which needs a render and lists one missing clip
- **THEN** its row shows 1 missing clip and its verdict, offers no Render, and says that missing clips block
  its render

#### Scenario: A row whose only missing clip is excluded offers Render
- **WHEN** the list shows `2024-09-03 - Utesluten`, which needs a render and whose only missing clip is one
  that `reel.yaml` excludes
- **THEN** its row shows 1 missing clip and its verdict, offers Render, and does not say that missing clips
  block its render

#### Scenario: A missing-clip row fits a phone-width window
- **WHEN** the list is shown 390 pixels wide
- **THEN** the page does not scroll horizontally, and the `2024-09-01 - Sommarlov` row still shows its missing
  clip count and the words that missing clips block its render

#### Scenario: A row's Render is confirmed in words
- **WHEN** the operator presses Enter on the Render control of the `2024-08-02 - Badutflykt - Varberg` row
- **THEN** one job is enqueued, the row shows it queued, keyboard focus is on the row's "Badutflykt" link,
  assistive technology is told once that the render of "Badutflykt", 2024-08-02, was queued, and no
  notification is shown over the list

#### Scenario: A collision notification names the folders
- **WHEN** the operator presses Render on the `2024-07-14 - kalas` row
- **THEN** no job is enqueued, and an error notification names `2024-07-14 - kalas` and `2024-07-14 - Kalas`
  by their folder names, with a link to the `2024-07-14 - kalas` page

### Requirement: A shown screen re-reads in place when events change

The client SHALL record that events changed:
- when a job finishes as done, whoever started it (this tab, another tab or the command line), whether the
  connection reported it live, or the client read it after a reconnect or because a screen showed it as
  still active
- when an enqueue answer shows that a screen's verdict was out of date: the event was already up to date,
  or it no longer exists

On such a change:
- the event list, if it is **shown at that moment**, SHALL re-read
- a hidden list re-reads the next time it is shown, as the list requirement states

An event's page, if it is **shown at that moment**, SHALL re-read when the job it shows reaches any
finished state (rendered, failed or canceled), and when its own enqueue answer showed its verdict was out
of date. An event page in Edit mode defers that re-read until Edit mode ends; the read that leaving Edit
mode makes takes its place, as an operator-started read. While Edit mode is open, the page SHALL instead
refresh only the verdict (rendered or stale, with its reasons) and the latest job in its render region:
- the refresh SHALL NOT change the chapters, clips, counts, title, date, "Read" time, the order or fields
  Edit mode shows, or its unsaved changes, and SHALL NOT mark the page as updating
- a refresh that gets no usable answer SHALL leave the region as it was and SHALL say there that the
  verdict may be out of date, without replacing the page or Edit mode with a failure; a later refresh that
  succeeds SHALL remove that note
- a refresh that answers after Edit mode ended SHALL be dropped, because the read that leaving Edit mode
  makes replaces everything
- a re-read that was on its way when Edit mode was opened SHALL be replaced by such a refresh, not lost

These re-reads, including a hidden list's re-read when it is shown again, happen **in place**; the read that
leaving Edit mode makes is not one of them. Unlike a first read or an operator's Refresh, they SHALL keep
showing the current content, marked as updating, until the new read answers. The new content then replaces it. A re-read that fails SHALL replace the content with
its failure, as any failed read does. The list's filter setting and scroll position SHALL be kept. Changes
that arrive while such a re-read is in flight SHALL lead to one more re-read after it, not to an endless
restart. A screen that shows a failure has no content to keep, so its re-read shows placeholders as a first
read does.

#### Scenario: A finished render updates the list without flashing
- **WHEN** the list is shown and the render of `2024-06-27 - Grillning med grannar` completes
- **THEN** the list keeps its rows while it re-reads, then shows the event as up to date, keeping the same
  filter and scroll position

#### Scenario: A render queued by another client also updates the shown list
- **WHEN** the list is shown and a forced job for `2023-06-23 - Midsommar - Dalarna`, queued by another
  client, completes
- **THEN** its row shows the job queued and then rendered, the list re-reads in place, and no notification is
  raised in this tab

#### Scenario: A finished render updates its page
- **WHEN** `2024-06-27 - Grillning med grannar`'s page is open and its render completes
- **THEN** the page re-reads in place and shows the event as up to date, with the job rendered

#### Scenario: Back after a finished render keeps the list's place
- **WHEN** the operator scrolled the list, opened `2024-06-27 - Grillning med grannar`, its render completed
  there, and the operator goes back
- **THEN** the list keeps its rows, marked as updating, at the same scroll position while it re-reads, and
  then shows the event as up to date

#### Scenario: Edit mode defers the page's re-read
- **WHEN** `2024-06-27 - Grillning med grannar`'s page is in Edit mode with unsaved changes, and a render of
  the event that was already running completes
- **THEN** the page does not re-read its chapters or clips and the unsaved changes stay; once Edit mode ends,
  the page re-reads and shows the event as up to date

#### Scenario: A render that ends in Edit mode updates the verdict only
- **WHEN** `2024-06-27 - Grillning med grannar`'s page shows the event as stale with a running job, the
  operator opens Edit mode, moves a clip to another chapter without saving, and the job completes
- **THEN** the render region shows the event as up to date with the job rendered, the moved clip, the
  chapters, the counts and the "Read" time are as they were, the unsaved changes stay, and the page is not
  marked as updating

#### Scenario: A verdict refresh that fails keeps Edit mode and says so
- **WHEN** the same job completes while Edit mode is open and the page's read of the event gets no answer
  from the service
- **THEN** Edit mode and its unsaved changes stay, the render region keeps its words and says that the
  verdict may be out of date and that stopping editing reads the event again, and once the operator stops
  editing the page re-reads and shows the event as up to date

#### Scenario: A render that ends as Edit mode opens is not lost
- **WHEN** a render completes, the page starts its re-read, and the operator presses Edit before it answers
- **THEN** Edit mode opens with the page's chapters and clips unchanged, and the render region shows the
  event as up to date once the read answers

#### Scenario: An in-place re-read that fails is not hidden
- **WHEN** a render completes while the list is shown, and the list's re-read gets no answer from the
  service
- **THEN** the list is replaced by the "service not reachable" failure, not left showing the earlier rows as
  current

### Requirement: A shown job is dated by the time that matches its state

Wherever a screen shows an event's job (a list row, or the event page's latest job and progress region), it
SHALL show one time with it, labelled for what it is and taken from the job as the service reported it:

- a job that rendered: when it finished, labelled as a finish time
- a job that failed or was canceled: when it ended, labelled as an end time, never as a finish time, so that
  it does not read as a completed render
- a running job: when it started, labelled as a start time
- a queued job: when it was queued, labelled as a queue time

The time SHALL NOT depend on how the client learned the job. A job known only from a screen's events read
SHALL be dated exactly as the same job received over the jobs connection or read on its own. So when a
screen that showed a job from a read later receives the same job with the same times, the shown time SHALL
NOT change, and a status region's words change only with the job's state. When the service reported no
time for the job's state, the client SHALL show when the job was queued, labelled as such, and MUST NOT
present that time, or any other, as a start, finish or end time. The client MUST NOT compute a time the
service did not report.

#### Scenario: A rendered row says when it finished, straight from the list read
- **WHEN** the operator opens the list in a new tab with no worker running, and the list shows
  `2024-06-27 - Grillning med grannar`, whose latest job rendered. A connection snapshot carries only
  active jobs, so the tab knows that job only from the list read.
- **THEN** its row shows that the job rendered, with "finished" and the job's finish time as
  `GET /api/v1/jobs/{id}` reports it
- **AND** no row whose job ended shows its time labelled "queued", and no failed or canceled row shows it
  labelled "finished"

#### Scenario: A rendered event's page says when it rendered
- **WHEN** the operator opens, in a new tab, the page of `2024-06-27 - Grillning med grannar`, whose
  latest job rendered and is known to the tab only from the event read
- **THEN** the page's latest job shows that it rendered, with "finished" and the job's finish time as
  `GET /api/v1/jobs/{id}` reports it

#### Scenario: A failed event's page says when it failed, before and after its error is read
- **WHEN** the operator opens the page of `2024-10-05 - Trasig`, whose latest job failed at probe, and the
  page reads that job for its error text
- **THEN** as soon as the event is read, the page's latest job shows that it failed, with "ended" and the
  time it ended as `GET /api/v1/jobs/{id}` reports it (`finished_at`)
- **AND** when the job read answers, the error text appears beside it, and the shown status words and
  time do not change, so nothing is announced

#### Scenario: A job cancelled before it started is dated by its cancel
- **WHEN** a job for `2024-08-02 - Badutflykt - Varberg` was cancelled before any worker claimed it, and
  the operator then opens the list
- **THEN** its row shows that the job was canceled, with "ended" and the cancel time, and no start time

#### Scenario: A queued job still says when it was queued
- **WHEN** the list shows `2024/Blandat`, whose job is queued, with no worker running
- **THEN** its row shows the job waiting, with "queued" and the time it was queued

#### Scenario: A reload does not change a finished job's time
- **WHEN** the operator starts a render of `2024-08-20 - Två kapitel - Tjörn` from its page, the job is
  rendered while the page is open, and the operator then reloads the browser tab
- **THEN** the page shows the same "finished" time before the reload, from the connection, and after it,
  from the events read

### Requirement: Edit mode removes a missing clip from reel.yaml on request

In Edit mode, every clip that `reel.yaml` lists but that is missing from disk SHALL offer a control that
removes it from `reel.yaml`. The control SHALL say that it removes the clip, SHALL name the clip to assistive
technology by the clip's name, as the event page's table names it, and SHALL be reachable with the keyboard.
No other clip SHALL offer one: a clip that is on disk (included, NEW or ignored) is never removed this way,
and nothing else in the client removes a clip from `reel.yaml`.

Removing a clip SHALL:

- take it out of its chapter's play order, so that the chapter's remaining clips are numbered, and their
  positions announced, without it
- list it under its chapter, after the clips the chapter plays, as removed from `reel.yaml` when the edits are
  saved. The listing keeps the clip's name, as the event page's table names it, and its status in words, and
  offers an **Undo** control that names the clip that way to assistive technology.
- move keyboard focus to that Undo control, and announce that the clip will be removed from `reel.yaml` when
  the edits are saved

Undo SHALL return the clip to its chapter's play order, right after whichever of the clips that came before it
when Edit mode opened comes last in the chapter's play order now, or first when none of them is still in the
play order. With no other edit to the chapter, that is the position it had. So removals undone in any order,
with no move between them, leave the chapter's order as read, and however the chapter was reordered meanwhile,
each clip still in the play order that came before it when Edit mode opened comes before it again. Undo SHALL
then move keyboard focus to the clip's remove control, and announce the clip's position out of the number of
clips the chapter plays.

A removal SHALL count as an unsaved change, like a move. The save bar says how many missing clips will be
removed, Reset returns every removed clip to its place, and leaving with a removal unsaved asks first, as
for any unsaved edit. While a save is in flight, the remove and Undo controls SHALL accept no presses.

Saving SHALL write `reel.yaml` without each removed clip, as "Saving an edit writes only what the operator
changed" states, and SHALL NOT create, change or delete any other file. After a successful save, the page
SHALL show the event without the removed clips and SHALL no longer report them as missing.

#### Scenario: Removing the missing clip of Sommarlov
- **WHEN** in Edit mode on `2024-09-01 - Sommarlov`, the operator activates the control that removes
  `borttagen.mp4` from `reel.yaml`
- **THEN** the chapter plays `s1710002.mp4` and `s1710004.mp4`, numbered 1 and 2; `borttagen.mp4` is listed
  under the chapter as removed when the edits are saved, still marked as missing, with an Undo control that
  has keyboard focus; and the page says that 1 missing clip will be removed

#### Scenario: Undo puts the clip back
- **WHEN** after removing `borttagen.mp4`, the operator activates its Undo control
- **THEN** `borttagen.mp4` is at position 3 again, keyboard focus is on its remove control, and the page
  shows no unsaved changes

#### Scenario: Undo after a move keeps the move
- **WHEN** on `2024-09-01 - Sommarlov`, the operator removes `borttagen.mp4`, moves `s1710004.mp4` up, and
  then undoes the removal
- **THEN** the chapter lists `s1710004.mp4`, `s1710002.mp4` and `borttagen.mp4`, and the page says that 1 clip
  moved, and no longer says that a missing clip will be removed

#### Scenario: Removals undone in any order restore the chapter
- **WHEN** in Edit mode on an event whose one chapter lists `s1710001.mp4` and then the missing `x.mp4` and
  `y.mp4`, the operator removes `x.mp4`, then `y.mp4`, then undoes the removal of `x.mp4`, then of `y.mp4`
- **THEN** the chapter lists `s1710001.mp4`, `x.mp4` and `y.mp4` as read, and the page shows no unsaved
  changes

#### Scenario: Reset puts every removed clip back
- **WHEN** on `2024-09-01 - Sommarlov`, the operator removes `borttagen.mp4`, moves `s1710004.mp4` up, and
  presses Reset
- **THEN** the chapter lists `s1710002.mp4`, `s1710004.mp4` and `borttagen.mp4` as read, and the page shows
  no unsaved changes

#### Scenario: Saving takes the entry out of reel.yaml
- **WHEN** the operator removes `borttagen.mp4` from `2024-09-01 - Sommarlov` and saves
- **THEN** `reel.yaml` lists `s1710002.mp4` and `s1710004.mp4` only; the line for `borttagen.mp4`, with its
  end-of-line comment, is the only line gone; and the page shows the event with no missing clip, needing a
  render, and offers Render

#### Scenario: The render succeeds once the entry is gone
- **WHEN** after that save the operator presses Render on `2024-09-01 - Sommarlov` and a worker runs the job
- **THEN** the job completes and the page shows the event as rendered and up to date

#### Scenario: Only missing clips can be removed
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, whose clips are included, NEW or ignored,
  and none is missing
- **THEN** no clip offers a control that removes it from `reel.yaml`

#### Scenario: A pending removal is an unsaved edit
- **WHEN** the operator removes `borttagen.mp4` on `2024-09-01 - Sommarlov` and presses the browser's Back
- **THEN** the event page stays, with the removal, and asks "Discard unsaved changes?"

### Requirement: Every clip row shows a frame from its clip

On an event's page, every clip row SHALL show a thumbnail of the clip beside its facts, after its position
number and ahead of its file name in the row's reading order. This applies to the chapter tables, to their
card layout in a narrow window, and to Edit mode's lists (the movable rows, the removed rows and the ignored
rows). The
thumbnail SHALL be the image the service returns for that clip from
`GET /api/v1/events/{event_id}/thumbnail?clip=<identity>`. The event id and the clip's full identity SHALL
be sent exactly as the event detail gives them, including a chapter folder and non-ASCII letters. The
request SHALL also carry the clip's modification time, exactly as the event detail gives it, as the `v`
parameter, so that a clip replaced on disk gets a new address. The client SHALL NOT choose, crop or compute
the frame itself.

The thumbnail SHALL be shown in a box of fixed 16:9 proportions, of the same size in every row. In the
chapter tables, the box SHALL be 128 × 72 CSS pixels where the chapter's panel is at least 1024 CSS
pixels wide, as in a window 1280 pixels wide, and 80 × 45 in narrower tables and in their card layout. The
whole image SHALL be visible inside the box, never cropped or stretched. A clip displayed in portrait, such
as a phone clip whose container rotates it, SHALL appear as a player shows it, whole, with empty bands at
its sides.

Each thumbnail image SHALL have the text alternative "Frame from <name>", where <name> is the clip's name as
its row shows it. The image itself SHALL NOT be focusable. In the event page's read view the thumbnail of a clip
whose file is on disk carries a play control laid over it ("The event page watches a clip on request"), which
is the only focusable thing in the thumbnail's cell and leaves the image, its text alternative, its box, its
size and its place as they are. In Edit mode, for a clip that offers no Cuts control (a missing, removed or
ignored clip), the thumbnail SHALL NOT be focusable. In Edit mode, the thumbnail of a clip that
offers a Cuts control SHALL be a button named "Watch <name>" that opens the clip's preview ("Edit mode
previews a clip on request"). Its box, its size and its place in the row SHALL stay as they are, and the
button's name stands in for the image's text alternative. No thumbnail SHALL start a drag of its own. In Edit
mode a clip moves only by its handle or its move buttons, and its thumbnail moves with its row.

A MISSING clip SHALL NOT request a thumbnail. Its row SHALL show an empty placeholder box of the same size,
and its status says why the box is empty. An IGNORED clip's thumbnail SHALL be dimmed, like the rest of its
row.

#### Scenario: Each clip of an event shows its frame
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`
- **THEN** each of its four clip rows shows an image whose text alternative is "Frame from <its file name>",
  with one thumbnail request per clip carrying that clip's identity, and as `v` that clip's modification time
  exactly as the event detail gives it

#### Scenario: Frames are larger in a wide window
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide, and again in
  a window 390 pixels wide
- **THEN** every thumbnail box is 128 × 72 CSS pixels in the first and 80 × 45 in the second, each shows its
  whole frame, and no row changes its size or position as the images arrive

#### Scenario: A frame is named as its row names the clip
- **WHEN** `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its root
  chapter and ignores the root clip `s1710004.mp4`
- **THEN** the `Main` table's thumbnails of those two clips have the text alternatives
  "Frame from Kvällen/s1710004.mp4" and "Frame from s1710004.mp4"

#### Scenario: Chapter clips are asked for by their full identity
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the `Kvällen` table's rows request their thumbnails with identities that start with `Kvällen/`,
  including the NEW `Kvällen/s1710004.mp4`, and each row shows the image for its own clip

#### Scenario: An ignored clip's frame is dimmed
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose root clip `s1710004.mp4` is IGNORED
- **THEN** that row shows its thumbnail dimmed together with the row's other facts, and the other rows'
  thumbnails are not dimmed

#### Scenario: A missing clip requests nothing
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, whose `reel.yaml` lists `borttagen.mp4` that is not
  on disk
- **THEN** no thumbnail request names `borttagen.mp4`, its row shows an empty placeholder box of the same size
  as the others, and every other clip's row shows its frame

#### Scenario: Edit mode keeps each frame with its clip
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, enters Edit mode, and moves its first clip
  down one place with the Move down button
- **THEN** every drag row shows the same frame its clip showed in the table, the moved clip's frame is now in
  the second row, and the service received no second thumbnail request for any of the four clips

#### Scenario: In Edit mode a clip's frame is a Watch button
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, and then enters Edit mode
- **THEN** in the read view no thumbnail image is focusable, and the play control over the thumbnail of a clip on
  disk is the only stop in its cell
- **AND** in Edit mode the thumbnail of every clip `Main` and `Kvällen` play is a button named "Watch <name>",
  such as "Watch s1710002.mp4" in `Kvällen`, which names its own clips without the folder, the ignored root clip `s1710004.mp4`'s thumbnail is not
  focusable, and every thumbnail box has the size and place it had before this change

#### Scenario: A clip rotated for display is shown whole
- **WHEN** an event holds a 1920×1080 clip whose container rotates it 90° for display, named with a space,
  a comma and a Swedish letter (`stående klipp, 1.mp4`)
- **THEN** its thumbnail is requested with that name as its `clip` value and arrives taller than wide, its
  box has the same size as a landscape clip's, and the whole frame is visible inside it, turned as a player
  shows it, with empty bands at its sides

### Requirement: Thumbnails never hold up or break a page

Thumbnails SHALL NOT delay the event page. Its chapters and clip facts SHALL be shown as soon as the event
detail is read, whether or not any thumbnail has arrived. The page SHALL request a clip's thumbnail only when
its row is on or near the visible part of the page. A clip's thumbnail SHALL have the same address every time
it is shown while the clip is unchanged on disk, so that a row shown again (after a Refresh, or on entering or leaving Edit mode) is served from
the browser's cache while the service's caching headers allow it.

While a thumbnail loads, its box SHALL show a placeholder. That placeholder SHALL stand still when the
operating system asks for reduced motion. A row SHALL NOT change size or position when its thumbnail
arrives, or when it fails.

When the service cannot give a clip's thumbnail (it answers with a failure status, or the image cannot be
shown), the box SHALL show a neutral "No preview" placeholder with an icon, named "No preview for <name>"
for assistive technology, where <name> is the clip's name as its row shows it (see "Every clip row shows a
frame from its clip"). The failure SHALL NOT raise an alert or a toast, SHALL NOT change the
clip's status, and SHALL NOT be retried automatically while the row stays shown.

**When no preview can be made at all.** A failed image says nothing about why. For each thumbnail that fails to
show, the page SHALL therefore make one further request for the same address, only to read the service's answer,
and SHALL NOT show anything of that answer's body in the clip's row. The answer is the clip's own failure when
it is a 502 that carries the thumbnail failure kind `thumbnail_failed`. A 502 that carries no thumbnail failure
kind and no event `failure` (the service's thumbnail cache or its `config.yaml` is at fault, so that no clip
could have a preview) SHALL be counted as the service's. Any other answer is counted nowhere, as is none: a 502
whose `failure` says that the event itself could not be read is not a thumbnail fault. The further request SHALL
be made behind the page's own requests (low priority).

When at least three thumbnails shown on the page have failed as the service's, the page SHALL show
one note, once for the page and not per clip: "Previews are unavailable. The service could not make thumbnails;
run `auto-reel thumbs` on the server to see why." The note SHALL be shown in the read view and in Edit mode, in
the same place above the clips. It SHALL be part of the page's content: no alert, no toast and no announcement,
and with a name for assistive technology that does not need the colour of the warning. It SHALL leave when fewer
than three such failures are shown, such as after a Refresh that finds the service working. Failures that are
the clips' own SHALL never raise it, however many clips fail that way.

In a window 390 CSS pixels wide, the thumbnail SHALL stay in the clip's row beside its facts, without
horizontal scroll, and no fact of a row SHALL overlap another.

#### Scenario: A clip whose frame cannot be read says "No preview"
- **WHEN** the operator opens `2024-10-05 - Trasig`, whose only clip `trasig.mp4` is an empty file
- **THEN** the row shows the "No preview" placeholder with its icon, its status and facts read as before, the
  page shows no alert, toast or note about it, and the service received at most two thumbnail requests for
  `trasig.mp4`: the image's, and the one that reads why it failed

#### Scenario: A fault of the service's thumbnail cache is said once
- **WHEN** the service's thumbnail cache directory cannot be written, and the operator opens
  `2024-06-27 - Grillning med grannar`, whose four clips are on disk
- **THEN** each of the four rows shows the "No preview" placeholder, and the page shows one note, "Previews are
  unavailable…", above the clips; no alert or toast is raised
- **WHEN** the operator enters Edit mode
- **THEN** the note is shown in the same place, once

#### Scenario: Clips that cannot be decoded raise no note
- **WHEN** an event of four clips is opened and the service answers each thumbnail with a 502 that carries the
  thumbnail failure kind `thumbnail_failed`
- **THEN** each row shows the "No preview" placeholder, and the page shows no note

#### Scenario: An event that becomes unreadable raises no thumbnail note
- **WHEN** the operator has opened `2024-06-27 - Grillning med grannar`, its `reel.yaml` is then made unreadable,
  and the service answers the thumbnails of three of its clips with a 502 that carries an event `failure`
- **THEN** each of the three rows shows the "No preview" placeholder, and the page shows no note

#### Scenario: Two failures are not a pattern
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` and the service answers the thumbnails of two
  of its four clips with a 502 that carries no thumbnail failure kind, and the others with images
- **THEN** two rows show "No preview", and the page shows no note

#### Scenario: The note leaves with the fault
- **WHEN** the note is shown, the cache directory is made writable, and the operator presses Refresh
- **THEN** the four thumbnails are shown, and the page shows no note

#### Scenario: Only rows near the view are requested
- **WHEN** the operator opens an event of 60 clips in one chapter, in a window 1280 by 800 pixels, and then
  scrolls to its end
- **THEN** fewer than 60 thumbnails are requested before the scroll, and all 60 after it

#### Scenario: Arriving thumbnails move nothing
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn` and every thumbnail arrives after the clip
  facts are shown
- **THEN** no clip row changes its size or position as the images arrive

#### Scenario: A slow thumbnail does not hold up the page
- **WHEN** every thumbnail response of `2024-06-27 - Grillning med grannar` is held back for five seconds
- **THEN** the page shows its heading, verdict and all four clip rows with their facts before the images,
  and each box shows the loading placeholder until its image arrives

#### Scenario: Placeholders stand still under reduced motion
- **WHEN** the operator's system asks for reduced motion and thumbnails are loading
- **THEN** their placeholders are shown without any animation

#### Scenario: Thumbnails at phone width
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn` in a window 390 pixels wide, in the table
  view and in Edit mode
- **THEN** the page does not scroll horizontally, every clip still shows its thumbnail, position, file name,
  status, size and modification time in its row, and no two of them overlap

### Requirement: The screens announce each change once

A notification (a toast) SHALL be announced once, when it appears: an error assertively, and any other
notification politely. Adding a notification SHALL NOT announce again any notification still shown, and
removing one SHALL NOT be announced.

A warning that is part of a page's content, as opposed to a failure that replaces the content, SHALL NOT be
announced as an alert. The event page's warning that `reel.yaml` lists clips that are not on disk is one such
warning. Opening the page or reading it again SHALL NOT announce the warning. It is read where it stands in
the page, and the page's render status, which is announced when it changes, already states the missing clip.

#### Scenario: A second notification is announced alone
- **WHEN** on the dev library's event list, the operator presses the Render of the `2024-07-14 - kalas` row
  twice, and each time the service answers that the movie file is shared with `2024-07-14 - Kalas`
- **THEN** two error notifications are shown, and the second answer is announced by the second notification
  alone, not by both notifications again

#### Scenario: The missing-clip warning is not re-announced
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, whose `reel.yaml` lists `borttagen.mp4`, and then
  presses Refresh
- **THEN** the page shows the warning that `reel.yaml` lists clips that are not on disk, naming
  `borttagen.mp4`, and neither opening the page nor the refresh announces the warning as an alert

### Requirement: Dismissing a notification keeps keyboard focus

Every notification SHALL offer a dismiss control that is reachable with the keyboard. The control SHALL be
named "Dismiss" and SHALL be described to assistive technology by the notification's message.

When a notification is dismissed while focus is within the notifications, focus SHALL move to the next target
in this order:

1. the dismiss control of the next notification shown
2. the dismiss control of the previous notification shown
3. the control that had focus before focus moved into the notifications, when it is still shown
4. the page's level-one heading

The same order SHALL apply when a notification that holds focus is removed because a newer notification took
its place. In either case, focus SHALL NOT fall to the document body, and moving it SHALL NOT scroll the page.
A dismissal made while focus is outside the notifications, for example a pointer click in a browser that does
not focus buttons on click, SHALL NOT move focus.

#### Scenario: Dismissing moves to the next notification, then back
- **WHEN** two error notifications are shown on the event list, and the operator moves focus into them with
  Tab and presses Enter on the first notification's Dismiss
- **THEN** that notification is gone, and focus is on the remaining notification's Dismiss, described by its
  message
- **WHEN** the operator presses Enter again
- **THEN** no notification is shown, and focus is back on the control that had focus just before focus moved
  into the notifications, not on the document body

#### Scenario: With no earlier control, focus goes to the heading
- **WHEN** focus reached the only notification's Dismiss without passing through another control of the page,
  and the operator presses Enter
- **THEN** focus is on the list's level-one heading "Events"

#### Scenario: A displaced notification hands focus on
- **WHEN** three error notifications are shown, keyboard focus is on the oldest notification's Dismiss, and a
  fourth notification arrives
- **THEN** the oldest notification is removed, and focus is on the Dismiss of a notification still shown,
  not on the document body

#### Scenario: A pointer dismissal leaves the page where it is
- **WHEN** one error notification is shown on the dev library's event list in a window 390 pixels wide, the
  operator focuses the list's Refresh, scrolls halfway down the list so that Refresh is out of view, and
  clicks the notification's Dismiss with the mouse
- **THEN** the notification is gone, the page has not scrolled, and focus is on Refresh, not on the document
  body

### Requirement: Notifications never cover the save bar

While the event page's save bar is shown, no notification SHALL overlap it, at any scroll position and at any
window width:

- While the bar is held at the bottom of the window, notifications SHALL sit above it.
- When the page is scrolled far enough that the bar rests in the page below the content, notifications SHALL
  sit either above the bar or in the room below it.

While the bar moves from the bottom of the window to its resting place, notifications that sit above it MAY
move with it. While the bar is held whenever the page is not scrolled to its resting place (see "Edit mode's
save bar rests in the page when it would hide the editor"), and while no save bar is shown, a control that
receives keyboard focus SHALL NOT be left under a notification at any scroll position, including while the bar
moves, while one notification is shown, or two in a window at least 844 pixels tall. While the bar rests in the
page because, held, it would hide the editor, the same SHALL hold for the controls just above the bar, such as
the last clip row's: while notifications sit above a resting bar, the page SHALL keep as much room between the
last chapter and the bar as the notifications take, so that they cover that room and no control. The room SHALL
follow the notifications as they come and go, and the bar and the notifications SHALL follow any change of the
page above the bar that moves the bar, such as content that grows or shrinks, without a scroll or a resize.
The room SHALL NOT be kept while the notifications sit below the bar or no notification is shown.

When a page is scrolled to its end, no notification SHALL cover any of the page's controls, with or without a
save bar. With no save bar shown, notifications keep their place at the bottom of the window.

#### Scenario: A notification above the held save bar
- **WHEN** an error notification is shown, and the operator, in Edit mode on
  `2024-06-27 - Grillning med grannar` with the page scrolled to its top, changes the title, in windows 1280
  and 390 pixels wide
- **THEN** the notification sits above the save bar, and covers neither Reset nor Save

#### Scenario: The end of the page
- **WHEN** in the same state, the operator scrolls step by step to the end of the page, or presses Tab until
  Save has focus
- **THEN** at no step does a notification overlap the save bar, and at the end Save is fully visible and
  can be clicked, and no control of the page is covered by a notification

#### Scenario: Tabbing through the last clips with two notifications
- **WHEN** two error notifications are shown, and the operator, in Edit mode on
  `2024-06-27 - Grillning med grannar` in a window 390 × 844 pixels, changes the title and then presses Tab
  from Title through every clip row's controls to Save
- **THEN** no notification covers any part of the control that has focus, at any step, and none overlaps the
  save bar

#### Scenario: A short page with a save bar
- **WHEN** an error notification is shown and the operator changes the title in the metadata form of
  `2024-02-30 - Omöjligt datum`, in windows 390 and 320 pixels wide
- **THEN** at no scroll position does a notification overlap the save bar, and Save can be clicked

#### Scenario: Tabbing to the last clip above a resting bar
- **WHEN** in a window 320 × 568, and again in a window 320 × 256, an error notification is shown, and the
  operator, in Edit mode on `2024-09-01 - Sommarlov`, moves its first clip down with the keyboard, saves, the
  save is answered with a conflict (the save bar now rests after the last chapter), and the operator presses
  Shift+Tab from Save through every control of the bar and every clip row's controls
- **THEN** every control that receives focus is fully visible and no part of it is covered by the
  notification, and at no step does the notification overlap the save bar

#### Scenario: The room follows the notification
- **WHEN** in the same state, with the page scrolled a little short of its end so that the notification sits
  above the bar, the operator dismisses it and scrolls to the end of the page
- **THEN** the room between the last chapter and the save bar is gone, and Save is fully visible and can be
  clicked
- **WHEN** a second error notification then arrives
- **THEN** the last clip row's controls are not covered, and, scrolled a little short of the end again so that
  the notification sits above the bar, the room is back

#### Scenario: Content above the bar changes without a scroll or a resize
- **WHEN** an error notification is shown above a resting save bar, and a change in the page above the bar
  (a chapter being added before it, or a clip list growing by one row) moves the bar down the page without
  the window being scrolled or resized
- **THEN** the notification is still directly above the bar, does not overlap it, and covers no control

### Requirement: A confirmation dialog states its consequence

Every dialog that asks the operator to confirm an action SHALL have a title that asks the question and a
text that states the consequence. The dialog SHALL expose both to assistive technology: the title as the
dialog's name, and the consequence as its description. Opening the dialog therefore SHALL make the question
and its consequence available to assistive technology, although focus moves straight to the choice that
changes nothing.

#### Scenario: Render anyway states that the movie is replaced
- **WHEN** on `2023-06-23 - Midsommar - Dalarna`, which is up to date, the operator presses Render anyway
- **THEN** a dialog named "Render anyway?" opens, described as "The event is up to date. The existing movie
  is replaced when the new render finishes.", with focus on Cancel

#### Scenario: Overwriting states what else is replaced
- **WHEN** after a conflicting save on `2024-06-27 - Grillning med grannar`, the operator chooses
  "Overwrite with mine"
- **THEN** a dialog named "Overwrite the other change?" opens. Its description says that the operator's
  version replaces everything saved since editing started, including changes to chapters the operator did not
  touch, and focus is on Cancel.

### Requirement: Every control is large enough to touch

When the browser's primary pointer is coarse, such as a finger on a phone, each of these controls SHALL
take a tap anywhere in an area of at least 44 × 44 CSS pixels around it:

- every button
- every option of a segmented choice, such as the list's All / Needs render filter and the color-scheme
  control
- the header's link to the event list, and the event page's link back to it
- a notification's link

No control's area SHALL reach into another control, including two controls stacked one above the other.
In a table row of the list, the area of a control SHALL NOT reach above the top of its own cell, so that
it never covers the line that separates the row from the one above; the area stays 44 pixels tall by
reaching further below the control instead.
Making room for these areas SHALL NOT push text out of the box that holds it, or anything out of the header.
The color-scheme options are the one exception to the width: in a window narrower than 416 pixels the header
has no room for them beside the connection's state in words, and there each option SHALL take a tap in an
area 44 pixels tall and as wide as the option.

When the primary pointer is fine, such as a mouse, every control SHALL keep the size and place it has without
this rule.

#### Scenario: The list on a phone
- **WHEN** the operator opens the dev library's event list on a touch screen 390 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area centred on the Render of
  `2024-06-27 - Grillning med grannar`, on Refresh, or on each filter option reaches that control, a tap
  anywhere in an area 44 pixels tall and as wide as each color-scheme option reaches that option, and the page
  does not scroll horizontally

#### Scenario: The header keeps the connection's state in words
- **WHEN** the jobs connection is connecting, reconnecting, or live with jobs rendering and queued, and the
  operator opens the event list on a touch screen 384, 390, 412, 430, 480 or 528 pixels wide
- **THEN** the connection's state is in words inside its pill, clear of the color-scheme control, the header's
  content stays inside the header, and from 416 pixels a tap anywhere in a 44 × 44 pixel area centred on each
  color-scheme option reaches that option

#### Scenario: A row's Render keeps out of the row above
- **WHEN** the operator opens the dev library's event list on a touch screen 1280 pixels wide, where the
  events are table rows, and taps on the line that separates the `2024-06-27 - Grillning med grannar` row
  from the row above it
- **THEN** the tap does not reach the Render of `2024-06-27 - Grillning med grannar`, and a tap anywhere in
  a 44 pixel tall area as wide as that Render, whose top is no higher than the top of its cell, reaches it

#### Scenario: Two stacked buttons keep their own areas
- **WHEN** the operator saves Edit mode on `2024-06-27 - Grillning med grannar` on a touch screen 390 pixels
  wide, and the save is refused because the event was changed elsewhere
- **THEN** "Reload latest (discard my changes)" and "Overwrite with mine" are stacked, and a tap anywhere in a
  44 × 44 pixel area centred on either reaches that button and never the other

#### Scenario: Moving a clip by touch
- **WHEN** the operator opens Edit mode on `2024-06-27 - Grillning med grannar` on a touch screen 390 pixels
  wide
- **THEN** each clip's Reorder, Move up and Move down take a tap anywhere in a 44 × 44 pixel area of their
  own, and no tap meant for Move up reaches Move down

#### Scenario: A mouse sees no change
- **WHEN** the operator opens the event list, the page of `2024-06-27 - Grillning med grannar` and its Edit
  mode with a mouse, in windows 1280, 390 and 320 pixels wide
- **THEN** every control has the size and place it had before this rule

### Requirement: Times are written one way on every screen

Every time a screen shows SHALL be written in one format:

- the month's short name and the day
- the hour and minute
- the year only when it is not the current year
- never seconds

The format follows the browser's locale. It applies to:

- when a list or an event was read
- when a clip was last modified
- when a job was queued, started, finished or ended

Each shown time SHALL carry the exact instant in machine-readable form.

An event's date is a calendar date, not a time. It SHALL be shown as the service reports it
(`YYYY-MM-DD`), which is how the event folders write it.

#### Scenario: A clip's time reads like a job's time
- **WHEN** a browser set to English (United States) opens `2024-06-27 - Grillning med grannar`, whose clips
  were last modified this year on 1 October at 00:23 in the browser's time zone, and whose latest job
  finished that day at 00:35
- **THEN** the clip's modification time reads "Oct 1, 12:23 AM"
- **AND** the job's time reads "finished Oct 1, 12:35 AM"
- **AND** neither shows seconds

#### Scenario: A time from another year names its year
- **WHEN** in the same browser, the current year is 2026 and a job shown in the list finished on 22 June
  2025 at 20:03
- **THEN** its time reads "finished Jun 22, 2025, 8:03 PM"

#### Scenario: A read time names its day
- **WHEN** in the same browser, the list is read on 1 October at 01:40
- **THEN** the list says "Scanned Oct 1, 1:40 AM"
- **AND** an event page read at the same minute says "Read Oct 1, 1:40 AM"

#### Scenario: Event dates stay as the folders write them
- **WHEN** the list shows `2024-06-27 - Grillning med grannar`
- **THEN** its date reads `2024-06-27` in every locale

### Requirement: A request that gets no usable answer says which

A screen SHALL tell apart two ways a request can fail without a published answer:

- **No answer at all:** the request failed before the service answered. The screen SHALL say that the
  service is not reachable.
- **An unpublished answer:** the service answered, but with a status or body that the request's route does
  not publish, for example a 500 with no problem body. The screen SHALL NOT say that the service is not
  reachable. It SHALL say that the service sent an unexpected answer, and show the request and the status
  it received.

This holds for:

- the event list's read
- an event page's read
- Edit mode's read of the event's editorial document
- a save

A save that got an unexpected answer SHALL keep the operator's edits and offer Retry, as a save that got no
answer does.

When the event list's read or an event page's read gets no answer at all, the screen SHALL say how to
recover, which is to check that the service is running and then refresh, instead of the browser's own
error text.

#### Scenario: A server error on the list
- **WHEN** the events list request is answered with status 500 and no problem body
- **THEN** the list says the service sent an unexpected answer
- **AND** it shows that `GET /api/v1/events` answered 500
- **AND** it does not say the service is not reachable, and shows no events

#### Scenario: A server error on a save
- **WHEN** the operator saves a reorder of `2024-08-02 - Badutflykt - Varberg`, and the save is answered with
  status 500 and no problem body
- **THEN** the page says the service sent an unexpected answer, showing the status
- **AND** it keeps the reorder and offers Retry

#### Scenario: No answer still reads as not reachable
- **WHEN** the events list request gets no response
- **THEN** the list says the service is not reachable
- **AND** it says to check that the service is running and then refresh
- **AND** it shows no browser error text

### Requirement: Edit mode's save bar stays compact and fits the window

While Edit mode shows its save bar, the bar SHALL fit the window at every width from 320 CSS pixels up.
Nothing the bar shows SHALL make the page scroll horizontally, including a failed save's explanation and
its choices, and every word of it SHALL stay inside the window.

The bar SHALL present exactly one primary action at a time: the way on from its current state.

- **Reload latest** while a conflict holds Save back
- **Back to the event list** when the event no longer exists
- **Save** in every other state

Every other control in the bar SHALL be presented as secondary. A control that the state holds back SHALL
stay in its place, SHALL say that it is unavailable, and SHALL keep keyboard focus when it has it. Save
after a conflict, or after the event is found gone, is one such control.

In a window 390 × 844 CSS pixels, with the bar held at the window's bottom edge, the bar SHALL take at most
a third of the window's height. This includes the times it shows a conflict. A failure to save SHALL show
the service's detail in full, and the bar SHALL then take at most two fifths of the window's height.

The bar SHALL NOT show the browser's own error text. When a save gets no answer at all, the bar SHALL say
that the service is not reachable and offer Retry, without the text the browser gave for the failed request.
An error in the page itself SHALL be shown as a failed save with Retry, and SHALL NOT be reported as an
unreachable service.

#### Scenario: A conflict at phone width
- **WHEN** in a window 390 × 844, the operator is editing the location of
  `2024-06-27 - Grillning med grannar`, its `reel.yaml` title is changed by hand, and the operator saves
- **THEN** the save bar says that the event changed since it was read and offers "Reload latest" and
  "Overwrite with mine", with "Reload latest" as its one primary action. Save is held back, presented as
  secondary, and still has keyboard focus. The bar takes at most a third of the window's height, and the
  page does not scroll horizontally.

#### Scenario: A conflict in the narrowest window
- **WHEN** the same conflict is answered in a window 320 pixels wide
- **THEN** the page does not scroll horizontally, and the alert's title, both choices and the note that the
  edits are kept are all inside the window

#### Scenario: No answer at phone width
- **WHEN** in a window 390 × 844, the operator saves a reorder of `2024-08-02 - Badutflykt - Varberg` and the
  request gets no answer
- **THEN** the save bar says that the service is not reachable, offers Retry, keeps the reorder and shows no
  browser error text such as "Failed to fetch". Save is its one primary action, and the bar takes at most a
  third of the window's height.

#### Scenario: A failed write at phone width
- **WHEN** in a window 390 × 844, the operator saves a reorder of `2024-09-01 - Sommarlov` while its folder
  cannot be written
- **THEN** the save bar says that `reel.yaml` could not be saved, shows the service's whole detail with the
  path it names, and offers Retry. Save is its one primary action, the bar takes at most two fifths of the
  window's height, and the page does not scroll horizontally.

### Requirement: Edit mode keeps keyboard focus in view and never drops it

After the operator drops, moves, removes or restores a clip in Edit mode, from the keyboard or with a
pointer, the control that holds keyboard focus SHALL be fully visible together with its whole row. No part
of either SHALL be covered by the page header, the chapter's heading or the save bar. This SHALL also hold
for the edit that first brings the save bar in. The one exception is a drop into another chapter (see "Edit
mode drags clips between chapters"): then the moved clip's handle and its row's first line (its handle,
name and Cuts control) SHALL be fully visible and not covered, and a row taller than the room between the
chapter's heading and the save bar SHALL be scrolled so that its first line is.

Suppose Edit mode's read of the editorial document failed and the operator presses **Try again**. Then:

- the failure SHALL stay shown while the document is read again
- Try again SHALL keep keyboard focus, and SHALL show that it is busy until the read answers
- when the read fails again, focus SHALL stay on Try again, and the failure SHALL be announced again
- when the read succeeds, focus SHALL move to the heading of the event's fields
- when the event changed on disk in the meantime, focus SHALL move to the control that reads the event
  again

Focus SHALL never fall to the page's body.

When a save is answered, the control that then holds keyboard focus SHALL be fully inside the window. This
SHALL hold when the answer makes the save bar taller than the room below the editor's top, such as a
conflict in a short window scrolled to its top.

#### Scenario: The first keyboard drop keeps the dropped clip in view
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with no other edit and in a window
  1280 × 900, the operator focuses the handle of its first clip, `s1710001.mp4`, lifts the clip, moves it
  down one place and drops it
- **THEN** the save bar appears, keyboard focus is on that handle, and the handle and its whole row are fully
  visible above the save bar

#### Scenario: The first drop at phone width
- **WHEN** the operator does the same in a window 390 × 844 with the third clip, `s1710003.mp4`
- **THEN** its handle and its whole row are fully visible above the save bar

#### Scenario: A tall row dropped into another chapter
- **WHEN** in a window 390 × 600 on `2024-08-20 - Två kapitel - Tjörn`, the operator adds four cuts in the
  Cuts panel of `Kvällen/s1710002.mp4`, so that its row is taller than the room left, and drags the clip
  into `Main` after `s1710001.mp4`
- **THEN** keyboard focus is on its handle in `Main`, and its handle, name and Cuts control are fully visible
  below the chapter's heading and above the save bar

#### Scenario: A conflict in a short window scrolled to its top
- **WHEN** in a window 320 × 568 scrolled to its top, the operator has changed the location of
  `2024-06-27 - Grillning med grannar`, presses Save, and the save is answered with a conflict
- **THEN** Save keeps keyboard focus and is fully inside the window, and so is the rest of the save bar

#### Scenario: Try again keeps focus while the document is still unreadable
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` became unparseable after its page was read,
  the operator enters Edit mode, and then presses Enter on Try again while the file is still unparseable
- **THEN** Try again shows that it is busy while the read runs, keyboard focus stays on Try again
  throughout and afterwards, and the unparseable-document failure is announced again

#### Scenario: Try again moves focus to the fields once the read succeeds
- **WHEN** after that, the file is repaired and the operator presses Enter on Try again
- **THEN** the event's fields and clip lists are shown, and keyboard focus is on the heading of the event's
  fields

### Requirement: Edit mode lines up with the event page and fits a phone

Entering Edit mode SHALL NOT move each clip's thumbnail, name, status, size or modification time sideways from
where the event page's table showed them. This SHALL hold wherever a chapter's panel is wide enough for both
the table and Edit mode's one-line rows. Only two things SHALL move: the position number makes room for the
drag handle, and the move controls take room from the end of the file column. The control that leaves Edit
mode SHALL be presented like the control that entered it, and never as an unavailable control.

In a window 320 CSS pixels wide or wider, no state of Edit mode SHALL make the page scroll horizontally.

- **A chapter's heading** SHALL stay within its panel. What the chapter holds (moved, missing, removed and
  ignored clips) SHALL NOT make the heading wrap or widen. It SHALL name the chapter, say how many clips
  moved, and say how many clips the chapter plays.
- **The lists of removed clips and of ignored clips** SHALL each say how many clips they hold.
- **A missing clip's row** SHALL keep, in a window 390 pixels wide, the two-line layout of the other rows:
  - the first line holds its name and its move controls
  - its placeholder box sits beside its status, its absent size and time, and its remove control

In both color schemes, each metadata field's edge SHALL have a contrast of at least 3:1 against the surface
around it, so that an empty field is visible.

#### Scenario: Entering Edit mode moves no column
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide and enters
  Edit mode
- **THEN** each clip's thumbnail, file name, status, size and modification time start within one pixel of
  where the table showed them, and the Stop editing control has the same button style that Edit had

#### Scenario: A chapter with a removal and a move in the narrowest window
- **WHEN** in a window 320 pixels wide, in Edit mode on `2024-09-01 - Sommarlov`, the operator removes
  `borttagen.mp4` and moves `s1710004.mp4` up
- **THEN** the page does not scroll horizontally. The chapter's heading is one line that reads "Clips",
  "1 clip moved" and "2 clips". The list below the chapter says "1 clip removed from reel.yaml when you
  save".

#### Scenario: A chapter with an ignored clip
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` in a window 390 pixels wide
- **THEN** the heading of `Main` reads "Main" and "1 clip", its ignored list says "1 ignored clip, not
  played" and lists `s1710004.mp4`, and the page does not scroll horizontally

#### Scenario: A missing clip's row at phone width
- **WHEN** Edit mode opens on `2024-09-01 - Sommarlov` in a window 390 pixels wide
- **THEN** the row of `borttagen.mp4` shows its name and move controls on its first line, and its placeholder
  box beside "Missing from disk", the absent size and time, and its remove control. The row is at most 8
  pixels taller than the row of `s1710002.mp4`.

#### Scenario: Empty fields are visible in both schemes
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in the light and in the dark scheme
- **THEN** the edges of the empty Location and Description fields measure at least 3:1 against the panel
  around them

### Requirement: Edit mode names clips and the saved event as the other screens do

Edit mode SHALL name each clip by the rule the event page's table uses, applied to the chapter's current name
and to every clip the chapter lists now or listed when Edit mode opened. A chapter names a clip by its file
name while every one of those clips lies in the folder named like the chapter's current name (the event
folder, for the event's own chapter). Otherwise it names the clip by its path inside the event folder. So a
clip moved in and a new name take the names the table will give once saved, while a clip moved out or
removed renames nothing until the edits are saved. The same name SHALL be used in
these places:

- the clip's row
- the names of its controls: its handle, its move controls, and its remove or undo control
- what Edit mode announces about the clip

Moving a clip within its chapter, or removing one, SHALL NOT change how its chapter names its clips. Two edits
can change it. A clip from another folder moved into a chapter makes the chapter name its clips by their
paths, and so does a new name that is no longer its folder's.

When a save succeeds, the notification that confirms it SHALL name the event by the title the save left it
with, followed by that date when it is known, since titles repeat. When the title is not known to the page,
the notification SHALL name the event by its folder name. The page SHALL NOT guess a title or a date that the
service resolves from the folder name.

#### Scenario: A chapter that lists a clip from another folder
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` lists `Kvällen/s1710004.mp4` in its default
  chapter after `s1710001.mp4`, and the operator opens Edit mode
- **THEN** `Main` names its clips `s1710001.mp4` and `Kvällen/s1710004.mp4`, and its ignored clip
  `s1710004.mp4`, as the page's table named them, and the handle of the second is named
  "Reorder Kvällen/s1710004.mp4"

#### Scenario: The saved event is named by its title and date
- **WHEN** the operator changes the location of `2024-06-27 - Grillning med grannar` in Edit mode and saves
- **THEN** the notification says the event was saved, and names it "Grillkväll med grannarna" with its date
  2024-06-27

#### Scenario: A clip moved in from another folder is named by its path
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710002.mp4` from `Kvällen` to `Main`
- **THEN** `Main` names its clips `s1710001.mp4` and `Kvällen/s1710002.mp4`, and its ignored clip
  `s1710004.mp4`, and the second's Move up is named "Move Kvällen/s1710002.mp4 up"

#### Scenario: A renamed chapter names its clips by their paths
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `Kväll`
- **THEN** `Kväll` names its clips `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and `Kvällen/s1710004.mp4`, as
  the event page's table names them once the rename is saved

### Requirement: The event page says what a render does when the movie's name changed

The movie's file name is made from the event's date, title and location. Suppose one of these changed
after the event's last render, and the movie rendered under the old name is still on disk. The verdict then
cites that the movie's name changed. In that case:

- **The list** SHALL name this reason in short words, "movie name changed", in the same line as the
  verdict's other reasons.
- **The event's page** SHALL show the same words. Under the verdict's reasons, on a line of its own, it SHALL
  also say that the next render saves the movie under its new name, and that the movie under its old name
  stays on disk. It SHALL name both files in that sentence, the new one as the verdict's `output_name` and the
  old one as its `renamed_from`, each shown exactly as the service sent it.

For every other reason, the page SHALL show the reason's words alone, as the list does. That includes a
movie file that is missing from disk.

The words the page adds for a reason SHALL come from a mapping defined over the generated types' union of
staleness reasons, in the same way as the reasons' own words. When a reason is added, the client's
type-check then fails until it is decided whether the page says more about it. Neither screen SHALL name a
movie file that the service's response does not carry. The list and the render region (the job's status,
Render and Cancel) SHALL name no movie file. The verdict's note on the event's page names the two files the
verdict carries, and no others. When the verdict does not carry both names (either is `null`), the page SHALL
say the same sentence without file names, and MUST NOT make one up from the event's title, date or location. The
other place the event's page names its movie file is its "Movie" section, which takes the name from the movie
route's own answer (see "The event page plays the event's rendered movie"). In this case that is the old name,
the same as the note's.

A file name is long. The note SHALL break a name across lines rather than widen the page, so the page does not
scroll horizontally in a window 390 or 320 pixels wide.

#### Scenario: The page of a renamed event
- **WHEN** the title of `2024-06-27 - Grillning med grannar` was changed after its last render, its movie is
  still on disk under the old name, and the operator opens its page in a window 390 pixels wide
- **THEN** the page says it needs a render, "edited since last render, movie name changed", and, on a line
  of its own, "The next render saves the movie as 2024-06-27 - Grillkväll med grannarna.mp4. The movie
  2024-06-27 - Grillning med Grannar.mp4 stays on disk."
- **AND** the render region names no movie file, the "Movie" section names the movie under its old name
  `2024-06-27 - Grillning med Grannar.mp4`, and the page does not scroll horizontally, in a window 390 or 320
  pixels wide and in either color scheme

#### Scenario: The list keeps the short words
- **WHEN** the operator opens the event list in a window 1280 pixels wide
- **THEN** the row of `2024-06-27 - Grillning med grannar` reads "edited since last render, movie name
  changed", and shows no sentence about the next render

#### Scenario: A verdict that names no file gets the sentence without names
- **WHEN** the page of a renamed event reads a verdict that cites `output_renamed` with `renamed_from` and
  `output_name` both `null`
- **THEN** the page says "The next render saves the movie under its new name. The movie under its old name stays
  on disk.", and shows no file name in the note

#### Scenario: A missing movie gets no note
- **WHEN** the movie of `2024-06-21 - Midsommar - Dalarna` was deleted after its last render, and the
  operator opens its page
- **THEN** the page says it needs a render because the movie file is missing, and adds no sentence about the
  next render

#### Scenario: A new staleness reason fails the build at the page's mapping
- **WHEN** a staleness reason is added to the engine, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the page's mapping until it is decided whether the page says more
  about the new reason

### Requirement: A shown job follows a requeue and a cancel request that a read reports

A job that a screen knows from its events read (`latest_job`) carries the job's `cancel_requested` flag and
`requeue_count`. The client SHALL use them as follows, wherever it chooses which version of a job to show.

- **A requeue is not hidden by the last known state.** While the jobs connection is not live, the client holds
  only the last version it received of a running job. When a read of the same job reports a higher
  `requeue_count` than that version, the job was returned to the queue after the version was received. The client
  SHALL then show the read's version of the job: its status, progress, start and finish times, `cancel_requested`
  and `requeue_count`. It SHALL keep what a read does not carry, such as the worker and the error, from the
  version it holds. It MUST NOT keep showing the last known running state, with its progress, as the job's
  state. A read with the same `requeue_count` keeps the rules it follows today. A read with a lower `requeue_count` is older than the held version and SHALL NOT replace it, however far along it shows the job.
- **While the connection is live**, the connection's version of the job SHALL stay the one shown, as today,
  because it carries every change.
- **A cancel request in a read is shown.** A job that is queued or running, and that a read reports with
  `cancel_requested` true, SHALL show "Cancelling…" and SHALL NOT offer Cancel, whether the client knows the job
  from the connection or only from the read. A job whose read reports `cancel_requested` false SHALL NOT. While the
  connection is not live, a read that reports `cancel_requested` true for a job whose held version has it false
  SHALL be shown in place of the held version, as a read of a requeue is.

#### Scenario: A job requeued while the connection is down is shown as waiting
- **WHEN** the page of `2024-06-27 - Grillning med grannar` is open with its job running at 40% from the
  connection, the service stops answering and the worker is restarted, so that the job is requeued with
  `requeue_count` 1, and the operator then leaves the page and returns to it, so that the page reads the event
  again while the connection is still reconnecting
- **THEN** the page shows the job as waiting for a worker, with no progress percentage, and does not show it as
  rendering
- **AND** when the connection returns and the worker claims the job again, the page follows the connection

#### Scenario: A running job with the same requeue count keeps the held version
- **WHEN** the connection is down, the held version of a job is running at 40%, and a read reports the same job
  running at 10% with the same `requeue_count`
- **THEN** the page keeps showing the held version

#### Scenario: An older read does not bring a job back
- **WHEN** the connection is down, the held version of a job is queued with `requeue_count` 2, and a read reports the
  same job running at 90% with `requeue_count` 1
- **THEN** the page keeps showing the held version

#### Scenario: A live connection is not overruled
- **WHEN** the connection is live and a read reports a higher `requeue_count` than the connection's version of the
  job
- **THEN** the page keeps showing the connection's version

#### Scenario: A page opened on a job with a cancel pending says so
- **WHEN** the operator opens the page of an event, in a new tab, whose running job has had its cancel requested, and
  the tab knows the job only from the events read
- **THEN** the page's job shows "Cancelling…" and offers no Cancel

#### Scenario: A cancel requested during an outage is shown once the page reads it
- **WHEN** the connection is down, the held version of a running job has `cancel_requested` false, and a read of the
  same job reports it true with the same `requeue_count`
- **THEN** the page shows "Cancelling…" and offers no Cancel

#### Scenario: A job without a cancel request offers Cancel
- **WHEN** the same page is opened for a running job whose `cancel_requested` is false
- **THEN** the page shows no "Cancelling…" and offers Cancel

### Requirement: Edit mode's save bar rests in the page when it would hide the editor

Edit mode's save bar SHALL be held at the window's bottom edge only while both of these hold:

- it takes two fifths of the window's height or less;
- the window is at least 28rem tall (448 pixels at the default text size), so that a held bar, the sticky header
  and a chapter heading leave room for a whole clip row.

Otherwise it SHALL NOT be held there. It SHALL rest in the page after the editor's last chapter, and scroll with
the page. It SHALL be held again as soon as both hold again. Which of the two it is depends only on the bar's
height and the window's, never on where keyboard focus is.
The bar SHALL follow each change of its own height and of the window's, in both directions. Such changes
include:

- a save's answer
- an edit that changes what the bar says
- a window resized or zoomed

While the bar rests, it SHALL NOT cover any part of the editor. When the page then scrolls a focused control
into view, it SHALL leave no room for the bar at the window's bottom.

The control that holds keyboard focus SHALL NOT leave the window because the bar starts to rest:

- When a save's answer makes the bar rest, the control that then holds keyboard focus SHALL be scrolled fully
  into the window. When that control is in the bar, such as Save, the page scrolls to the bar.
- When a resized or zoomed window makes the bar rest while one of the bar's controls holds keyboard focus,
  that control SHALL be scrolled fully into the window.
- While the bar rests and one of its controls holds keyboard focus and is fully inside the window, every
  further resize or zoom of the window SHALL leave that control fully inside the window, step by step. A
  resize after the operator scrolled that control out of the window, a resize event that changes neither the
  window's width nor its height (a phone's URL bar fires them), a change of what the bar says, and a change of
  the bar's own height SHALL NOT scroll the page.

When keyboard focus moves to a control of the editor that is partly hidden, outside the window or under the
sticky header, a chapter heading or a held bar, such as the description field, whose caret alone the browser
would bring into view, that control SHALL be scrolled fully into view. Focus given by a pointer press SHALL NOT
scroll the page, so the press, and a text field's caret, land where the operator pressed.

No notification SHALL overlap the bar while it is held or while it rests.

Everything else about the bar is unchanged: what it says, its one primary action, its compact layout, and the
share of a 390 × 844 window it may take while it is held.

#### Scenario: A conflict at 400 % zoom
- **WHEN** in a window 320 × 256 (a 1280 × 1024 screen at 400 % zoom), using only the keyboard, the operator
  enters Edit mode on `2024-09-01 - Sommarlov`, moves its first clip down, and saves, and the save is
  answered with a conflict
- **THEN** the save bar rests after the last chapter, Save keeps keyboard focus, and Save is fully inside the
  window
- **AND** as the operator presses Shift+Tab from Save through every control of the bar, every clip row's
  controls and the fields, and then Tab back to Save, every control that receives focus is fully visible.
  None is covered by the save bar.

#### Scenario: A failed write at 400 % zoom
- **WHEN** the same save in the same window is answered with a failure to write `reel.yaml`
- **THEN** the save bar rests after the last chapter with the failure's whole detail, and every focus stop
  of the same walk is fully visible

#### Scenario: The first edit at 400 % zoom
- **WHEN** in a window 320 × 256, the operator enters Edit mode on `2024-09-01 - Sommarlov` and moves its
  first clip down with the keyboard
- **THEN** the save bar, which says only that there are unsaved changes, rests after the last chapter, and the
  moved clip's focused control and its whole row are fully visible

#### Scenario: A conflict in a short phone window
- **WHEN** in a window 320 × 568, the operator moves the first clip of `2024-09-01 - Sommarlov` down, and the
  save bar is held at the window's bottom, and then saves, and the save is answered with a conflict
- **THEN** the save bar rests after the last chapter, Save keeps keyboard focus, and Save and the rest of the
  bar are fully inside the window

#### Scenario: Phone and desktop windows keep the held bar
- **WHEN** the same conflict, or the same failure to write, is answered in a window 390 × 844 or
  1280 × 900
- **THEN** the save bar stays held at the window's bottom edge, as before this change

#### Scenario: A taller window holds the bar again
- **WHEN** after the conflict at 320 × 256, the window becomes 390 × 844, and then 320 × 256 again
- **THEN** the save bar is held at the window's bottom edge while the window is 390 × 844, and rests after the
  last chapter again at 320 × 256
- **AND** at each size, Save keeps keyboard focus and is fully inside the window

#### Scenario: Zooming in after a failed save
- **WHEN** in a window 1280 × 1024 or 1920 × 968, using only the keyboard, the operator moves the first clip of
  `2024-09-01 - Sommarlov` down and saves, the save is answered with a conflict or with a failure to write
  `reel.yaml`, and the operator then zooms in one browser step at a time, through 110, 125, 150, 175, 200,
  250 and 300 % to 400 %
- **THEN** after every step Save keeps keyboard focus and is fully inside the window, and at 400 % the save bar
  rests after the last chapter

#### Scenario: The first edit in a short, wide window
- **WHEN** in a window 480 × 242 (a 1920 × 1080 screen at 400 % zoom), the operator enters Edit mode on
  `2024-09-01 - Sommarlov` and moves its first clip down with the keyboard, or lifts it with the keyboard and
  drops it one place down
- **THEN** the save bar, which says only that there are unsaved changes and takes less than two fifths of the
  window, rests after the last chapter, and the moved clip's focused control and its whole row are fully
  visible

#### Scenario: A notification and a resting bar
- **WHEN** an error notification is shown, and the operator answers a conflict on `2024-09-01 - Sommarlov`
  in a window 320 × 568 or 320 × 256, and then scrolls the page from its top to its end
- **THEN** at no scroll position does the notification overlap the save bar

### Requirement: Edit mode adds, renames, reorders and deletes chapters

In Edit mode the operator SHALL be able to change the event's chapters themselves. Every control below SHALL
be reachable with the keyboard and SHALL name, to assistive technology, the chapter it acts on.

- **Add chapter**, after the last chapter, SHALL ask for a name and add an empty chapter with that name at the
  end.
- **Rename** SHALL be done in the title card dialog, in its Name field ("The title card dialog holds every
  name and every title-card setting"), by the one workflow for every chapter. A chapter's header bar SHALL show its name as plain text: not a
  button, with no pencil and no hover or focus change, and pressing it SHALL do nothing. There SHALL be no Rename
  button, no inline name field and no dialog of its own for a name. The event's own chapter (the default chapter,
  whose clips are the event folder's) has no name to rename: it is headed `Main` or `Clips` ("The event's own chapter
  is headed ..." below), its title card shows the event's title, and its Name field edits that title. Clips without a
  chapter of their own join it. While the event lists other chapters, the page SHALL say this in the Clips help ("Each explanation sits behind a Help toggle of its section"), not as a line beside the chapter.
- **Move up** and **Move down** SHALL move a chapter one place among the chapters, and SHALL be offered only
  while the event lists more than one chapter. After such a move, keyboard focus SHALL stay on the pressed
  control. At either end, the control that cannot move further SHALL say that it is unavailable.
- **Delete** SHALL remove a chapter only once it plays no clip. Its clips must first be moved to another
  chapter, or removed when missing. The event's own chapter can be deleted only when, in addition, it lists no
  ignored clip that the page would list under it again after the save: one from the event folder, or from a
  folder no chapter is named after. Such a clip would bring the chapter back, holding only ignored clips.
  When a chapter cannot be deleted, pressing Delete SHALL change nothing and leave focus on Delete. The page
  SHALL show and announce why the chapter cannot be deleted.

**The header bar.** Every chapter's header bar, the event's own chapter's too, SHALL hold, in this order, the chapter's name as plain
text, an **Edit Titlecard** button and the chapter's clip count; the chapter's tools (Move up, Move down, Delete, offered by the rules above) stay in their own row under the bar, which is sticky and keeps one line. The
button SHALL show an icon and the words "Edit Titlecard", SHALL be named "Edit title card for <name>" (the event's own chapter: its
heading) and SHALL open the title card dialog on the "This title card" tab ("A selected title card opens its inspector in Edit mode"). A
chapter's section SHALL show nothing between its header bar and its clips but the tools row and the notes of this requirement and of "Edit mode says what
a chapter's name means for clips added later": no card row, no "Main title card" line, no source line ("from the folder name"). A chapter added in the draft has no saved card, and its
button SHALL be offered all the same: the dialog says that its card is drawn after Save and keeps the preview from the draft.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up or Move down, so that an event never saves without a chapter.

**The Name field.** In the dialog the field SHALL be the first of "This title card" and SHALL be named "Name of chapter <name>"
for a chapter and "Title of the event" for the event's own chapter, where <name> is the name the draft holds when the dialog opens. The
header bar and the dialog's title name the chapter by its name alone.

- An accepted name SHALL be written to the draft as it is typed, so that the dialog's heading, its preview, the chapter's header
  bar behind the dialog and the picker of Move marked to… follow it. A name equal to the chapter's current name, once the spaces
  around it are removed, SHALL change nothing. A rename SHALL be announced once, when keyboard focus leaves the field or the dialog
  closes, and not for each key; typing a name and typing the old one back announces nothing.
- A refused name SHALL be explained under the field in words, in a `role="alert"` that is remounted for each refusal, and the
  field SHALL be marked invalid. The draft keeps the last accepted name, and the field keeps the typed text. Done, with a refused
  name in the field, SHALL keep the dialog open and put keyboard focus in the field. Escape and Close SHALL close the dialog, return the
  field's text to the draft's name, and announce that the name was not changed and why; they SHALL NOT keep a refused name.
- While the field holds a refused name, Ctrl+S SHALL save nothing and SHALL say "Not saved: the name is refused."
- While a save or a move of marked clips is pending, the field and the dialog's other fields SHALL say that they are unavailable
  and SHALL change nothing (the busy-control rule); the bar's Edit Titlecard button SHALL say so too and open nothing.
- Reset, a conflict and Overwrite SHALL treat a name as any other edit; Reset SHALL restore the chapters' names as read.

**The event's own chapter's name is the event's title.** For the event's own chapter the Name field SHALL edit the draft's
title, the one the Details form's Title field edits, in step with it in both directions, counted once in the save bar ("Title") and
undone by Reset as one edit.

- The field SHALL hold the draft's title. While that is blank it SHALL be empty with the title the page resolved from the folder
  name as its placeholder and the words "From the folder name", else the word "Untitled". The page SHALL NOT guess a title.
- Any text SHALL be kept as the title, with no rule of the page's. A blank title means that it inherits from the folder name, and
  the field SHALL say so in the words of the Details form ("Left empty: inherits from the folder name when saved"). The
  service's refusal of an unusable title stays at the Details form and is retired by editing the title in either place.
- While the draft's title differs from the title read, the dialog SHALL say that saving changes the movie's file name, that if the
  movie was already rendered the next render saves it under the new name, and that the movie under its old name stays on disk. It SHALL NOT name a
  file: the event page names them after the save, from the verdict.
- The card's heading follows the name. A card that has its own title ("Card title (overrides the name)") keeps it.

When the browser's primary pointer is coarse, each of these controls, the header bar's Edit Titlecard button, Add chapter and Undo SHALL take a tap
anywhere in an area of at least 44 × 44 CSS pixels around it that reaches no other control, as every button
does ("Every control is large enough to touch").

A name SHALL be accepted only when both of these hold, once the spaces around it are removed. The spaces are
the characters the engine removes from a chapter's name, so a name the page accepts is a name `reel.yaml`
loads:

- it is not empty
- compared by full Unicode case folding, the comparison the engine makes, it differs from the name of every
  other chapter of the event, including a deleted chapter not yet saved, and from `Main`, the name the page
  shows for the event's own chapter. So `ß`, `ss`, `SS` and `ẞ` are one name, as are `Kvällen` and `KVÄLLEN`.

A refused name SHALL be explained at the name field, which keeps keyboard focus when the name was asked for
with Done or in the Add chapter dialog, and nothing SHALL change. The
name saved is the accepted name without the spaces around it. A chapter's name SHALL be described to the
operator as the words on its title card in the movie.

A chapter the page showed when Edit mode opened SHALL, once deleted, stay listed in its place until the edits
are saved, marked as deleted when the edits are saved. It lists none of its clips. Such a chapter offers an **Undo** control that returns it to its place, and keyboard focus SHALL move to that Undo. A
chapter the operator added in this Edit mode and then deletes SHALL simply be gone. A chapter that plays no
clip SHALL say so in Edit mode, and that a chapter without clips is left out of the movie. While the event
lists another chapter, a deleted one aside, it SHALL also say that clips can be dragged into it, or moved into
it with Move marked to… (see "Edit mode drags clips between chapters"). When it is the only
chapter listed, a deleted one aside, it SHALL NOT say that: no other chapter has a clip to drag or to move,
and the page offers no Move marked to… there.

The event's own chapter SHALL be headed `Main` while any other chapter is listed, a deleted one aside, and
`Clips` otherwise, as on the event page. Every change to the chapters SHALL count as an unsaved edit, like a
move:

- it SHALL be announced
- Reset SHALL restore the chapters as read
- leaving with it unsaved SHALL ask first
- the save bar SHALL count it ("Saving an edit writes only what the operator changed")

While a save is in flight, every chapter control and Add chapter SHALL say that it is unavailable and SHALL
change nothing when pressed.

#### Scenario: A first chapter added to a one-chapter event
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter, the
  operator presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** a chapter `Kvällen vid grillen` is listed last, saying that it plays no clip and that clips can be
  dragged into it or moved into it with Move marked to…; the first chapter's heading reads `Main` instead of
  `Clips`; keyboard focus is on the new chapter's heading; the addition is announced; and the save bar says
  "1 chapter added"

#### Scenario: A lone chapter offers only Add chapter
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose clips are all in its own chapter
- **THEN** its one chapter offers no Move up, Move down or Delete, its header bar shows `Clips` as plain text with an Edit Titlecard
  button (the dialog's Name field edits the event's title), and the page offers Add chapter after it

#### Scenario: A name already taken, or no name, is refused
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named `kvällen`, then one named
  only with spaces, then one named `main`
- **THEN** each is refused at the name field, which keeps keyboard focus. `kvällen` is refused because a
  chapter called `Kvällen` exists. The blank name is refused because a chapter needs a name. `main` is refused
  because `Main` is the page's name for the event's own chapter. No chapter is added.

#### Scenario: A name the engine would fold into another is refused
- **WHEN** on `2024-09-14 - Gatufest`, an event with a chapter `Straße`, the operator adds a chapter named
  `STRASSE`, then one named `strasse`
- **THEN** each is refused at the name field, which keeps keyboard focus, because a chapter called `Straße`
  exists. No chapter is added. A name that merely resembles it, such as `Strasse 2`, is accepted.

#### Scenario: The spaces the engine removes are removed
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named with a next-line character
  (U+0085) before and after `Hamnen`
- **THEN** the chapter is added as `Hamnen`, without those characters, and the next save writes `Hamnen` to
  `reel.yaml`, which loads

#### Scenario: Renaming a chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses "Edit title card for Kvällen"
- **THEN** a dialog opens on "This title card" with keyboard focus in the Name field, named "Name of chapter Kvällen" and holding
  `Kvällen`; the header bar behind it shows `Kvällen` as plain text with no pencil
- **WHEN** the operator selects the name, types ` Kväll på stranden `, with spaces around it, and presses Done
- **THEN** the dialog is closed, keyboard focus is on that chapter's Edit Titlecard button, the heading reads `Kväll på stranden`, the rename was announced once, and the save bar says that 1
  chapter was renamed. The chapter offers no Rename button and its name is not pressable.

#### Scenario: Renaming with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator tabs to "Edit title card for Kvällen", presses Enter, types `Kväll`
  in the Name field and presses Escape
- **THEN** the chapter is named `Kväll` (an accepted name is already in the draft), the dialog is closed, keyboard focus is on the
  Edit Titlecard button, and the next Tab reaches the chapter's Move up

#### Scenario: Main and a chapter are edited alike
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens "Edit title card for Main" and then "Edit title card for Kvällen"
- **THEN** each opens the same dialog on "This title card" with the Name field first; Main's is named "Title of the event" and holds
  `Två kapitel`, Kvällen's "Name of chapter Kvällen"; neither header bar has a pencil, a card row, a "Main title card" line or a
  "from the folder name" line

#### Scenario: Leaving the field keeps an accepted name
- **WHEN** the operator opens the dialog of `Kvällen`, types `Kväll` in the Name field, and presses Tab
- **THEN** the chapter is named `Kväll`, keyboard focus is on the control after the field and not back in it, the dialog stays open, and the rename is announced once

#### Scenario: Escape drops what was typed
- **WHEN** the operator opens the dialog of `Kvällen`, types `main` in the Name field, and presses Escape
- **THEN** the dialog is closed, keyboard focus is on the chapter's Edit Titlecard button, the chapter is named `Kvällen`, "Name not changed" with the reason is announced, and the page shows no unsaved changes

#### Scenario: Pressing the title and changing nothing
- **WHEN** the operator types `Kväll` in the Name field of `Kvällen` and then `Kvällen`, with spaces around it, and closes the dialog
- **THEN** the chapter is named `Kvällen`, nothing is announced or counted as an edit, and the page shows no unsaved changes

#### Scenario: A refused rename keeps the field open
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `main` in the Name field of `Kvällen`
- **THEN** the field stays as typed, is marked invalid and explains under it that `Main` is how the page names the event's own chapter; the
  refusal is announced, and the draft still holds `Kvällen`. Typing `Morgon` removes the refusal and the chapter is named `Morgon`.
- **WHEN** the operator types `main` again and presses Done
- **THEN** the dialog stays open and keyboard focus is in the field
- **WHEN** the operator presses Escape
- **THEN** the dialog closes, the chapter is named `Morgon`, the last name accepted, and "Name not changed" with the reason is announced

#### Scenario: A refused name is not lost when focus leaves
- **WHEN** the operator types `main` in that field and presses Tab
- **THEN** the field stays as typed with its refusal, keyboard focus is on the control after it, and the chapter is still named `Kvällen`

#### Scenario: An empty name, and a name already taken
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator opens its dialog, deletes the name,
  and then types `KVÄLLEN`
- **THEN** the first is refused because a chapter needs a name, and the second because a chapter called `Kvällen` exists, each in
  the words Add chapter's dialog uses for the same name

#### Scenario: One field at a time
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator renames `Kvällen` to `Kväll` in its dialog, presses Done, and opens "Edit title card for Morgon"
- **THEN** only the dialog of `Morgon` is open, `Kvällen`'s header bar reads `Kväll`, and the save bar counts the one rename

#### Scenario: A name typed and not kept holds Save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator changes the title in the Details form, opens the dialog of `Kvällen`,
  types `main` and presses Ctrl+S
- **THEN** nothing is saved and "Not saved: the name is refused." is announced. After the operator types `Kväll`, closes the dialog and presses
  Ctrl+S, one save is sent and carries both edits.

#### Scenario: Reset closes the field
- **WHEN** the operator renames `Kvällen` to `Kväll` in its dialog, closes it, and presses Reset
- **THEN** the header bar reads `Kvällen`, the page shows no unsaved changes, and "Edit title card for Kvällen" opens a dialog whose Name field holds `Kvällen`

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` has no chapter rename and says that it has no name of its own because its title card shows the event's title; its
  header bar shows `Main`, an Edit Titlecard button and no other title control

#### Scenario: Renaming the main title card edits the event's title
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, in which one chapter is listed, and the operator opens "Edit title
  card for Clips" and types `Grillkväll med grannarna` in the field named "Title of the event"
- **THEN** the Details form's Title field holds the same, the dialog's preview shows it, the save bar says "Title" changed, and the
  dialog says that saving changes the movie's file name and names no file. The chapter is still headed `Clips`.
- **WHEN** the operator closes the dialog and types `Grillkväll` in the Details form's Title field and reopens the dialog
- **THEN** the Name field holds `Grillkväll`
- **WHEN** the operator saves
- **THEN** one `PUT` is sent whose metadata title is `Grillkväll` and whose chapters and clips are as read, and the dialog no longer says anything about
  the file name

#### Scenario: Emptying the main title card
- **WHEN** the operator deletes the text of the Name field of `2024-06-27 - Grillning med grannar`, which reads `Grillning med grannar` from `reel.yaml`
- **THEN** the field says "Left empty: inherits from the folder name when saved", shows the title resolved from the folder name as its
  placeholder with "From the folder name", and the Details form's Title field is empty with the same hint

#### Scenario: The main title card with no title at all
- **WHEN** the page has no title for the event, in `reel.yaml` or resolved from the folder name
- **THEN** the field is empty with the placeholder "Untitled"

#### Scenario: Moving a chapter up
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses Move up on `Kvällen`
- **THEN** `Kvällen` is listed first and `Main` second. Keyboard focus is still on `Kvällen`'s Move up, which
  now says that it is unavailable. The move is announced as chapter 1 of 2, and the save bar says that the
  chapter order changed.

#### Scenario: A chapter that plays clips cannot be deleted
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator presses Delete on `Kvällen`
- **THEN** nothing is deleted, and keyboard focus stays on Delete. The page shows and announces that `Kvällen`
  still plays 3 clips, which must first be moved to another chapter.

#### Scenario: Deleting an emptied chapter, and undoing it
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves all three clips of `Kvällen` to `Main` and
  presses Delete on `Kvällen`
- **THEN** `Kvällen` is listed in its place as deleted when the edits are saved, with an Undo control that has
  keyboard focus. The save bar says that 3 clips moved and that 1 chapter is deleted.
- **WHEN** the operator then presses that Undo
- **THEN** `Kvällen` is listed again, playing no clip. Keyboard focus is on its Delete, and the save bar no
  longer counts a deleted chapter.

#### Scenario: Main stays while it lists an ignored clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `s1710001.mp4` to `Kvällen` and presses
  Delete on `Main`
- **THEN** nothing is deleted, and the page says that `Main` still lists 1 ignored clip that no other chapter
  will take

#### Scenario: Saving a deleted chapter
- **WHEN** after deleting the emptied `Kvällen` of `2024-08-20 - Två kapitel - Tjörn`, the operator saves
- **THEN** `reel.yaml` names one chapter, the event's own, listing `s1710001.mp4`, `Kvällen/s1710002.mp4`,
  `Kvällen/s1710003.mp4` and `Kvällen/s1710004.mp4`, and still ignores `s1710004.mp4`. The page then shows that
  one chapter, headed `Clips`.

#### Scenario: Reset restores the chapters
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen`, adds a chapter `Morgon`, moves
  `Kvällen` up, and presses Reset
- **THEN** the chapters are `Main` and `Kvällen` as read, in that order, and the page shows no unsaved changes

#### Scenario: A chapter edit is an unsaved edit
- **WHEN** the operator renames `Kvällen` on `2024-08-20 - Två kapitel - Tjörn` and presses the browser's Back
- **THEN** the event page stays, with the rename, and asks "Discard unsaved changes?"

#### Scenario: The last chapter stays
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a chapter `Kvällen vid grillen`, moves all
  four clips of `Main` to it, and deletes `Main`
- **THEN** `Kvällen vid grillen` has a Name field in its dialog, but no Delete, Move up or Move down, and the save bar
  says that 4 clips moved, 1 chapter was added and 1 chapter deleted

#### Scenario: Chapter controls on a phone
- **WHEN** the operator opens Edit mode on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area around each of `Kvällen`'s Edit Titlecard, Move up, Move down and Delete, and
  around `Main`'s Edit Titlecard and Add chapter, reaches that control and no other (centred on each, except
  that the areas of Move up and Move down meet at the edge they share, as a clip row's move pair's do), and
  the page does not scroll horizontally

#### Scenario: Chapter controls wait for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a rename pending, the operator presses Save, and the
  service has not answered yet
- **THEN** Add chapter and every chapter's Edit Titlecard, Move up, Move down and Delete say that they are unavailable, and
  pressing them changes nothing and opens nothing

#### Scenario: A lone empty chapter does not point at Move clips
- **WHEN** Edit mode opens on `2024-10-05 - Tom mapp`, an event whose folder holds no clip, and the operator
  presses Add chapter, types `Kvällen vid grillen` and confirms
- **THEN** the new chapter, the only one listed, counts 0 clips, and it says "No clips. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move marked to…, and the page offers no Move marked to…

#### Scenario: A lone chapter whose only clip is ignored
- **WHEN** Edit mode opens on `2024-10-06 - Bara ignorerad`, an event that lists one chapter, whose only clip
  `s1710004.mp4` is ignored
- **THEN** the chapter lists the ignored clip under its heading and says "It plays no clip. A chapter without
  clips is left out of the movie." It does not mention dragging clips or Move marked to…

#### Scenario: A second chapter brings the hint back
- **WHEN** on `2024-10-05 - Tom mapp`, with `Kvällen vid grillen` added, the operator presses Add chapter,
  types `Morgonen` and confirms
- **THEN** both chapters say that they have no clips and that clips can be dragged into them or moved into
  them with Move marked to…
- **WHEN** the operator then deletes `Morgonen`
- **THEN** `Kvällen vid grillen` says again, as it did before the addition, that it has no clips and is left
  out of the movie, without mentioning dragging or Move marked to…

### Requirement: Edit mode says what a chapter's name means for clips added later

A clip that appears in an event's folder after its `reel.yaml` exists joins, at the next render, the chapter
named after the folder it is in (by case folding, as below), or the event's own chapter when no chapter has
that name. So a
chapter's name decides where clips added to that folder later go. Edit mode SHALL say so wherever an edit
changes that. It SHALL say it under the Name field of the title card dialog and in the Add chapter dialog, as the name is typed, and
beside the chapter after the edit,
until the edits are saved or undone:

- **Renaming or deleting a chapter whose name was the name of a folder of the event that holds clips.** No
  chapter is then named after that folder, so clips added to it later join the event's own chapter.
- **Adding a chapter named after such a folder, or renaming one to that name.** Clips added to that folder
  later join this chapter, and clips from it that other chapters list now stay where they are. The folder's
  ignored clips will be listed under this chapter.
- **Renaming or deleting a chapter that lists ignored clips.** They will be listed under the event's own
  chapter, because the page lists an ignored clip under the chapter named after its folder, or under the
  event's own chapter when none is.
- **Deleting the event's own chapter.** Clips added to the event folder later start a new `Main` chapter at
  the end, and so do the ignored clips of a chapter renamed or deleted in the same edits.

In these words the page SHALL name the event's own chapter by its heading at that moment: `Main` while
another chapter is listed, `Clips` when it is the only one.

A folder counts only while it holds a clip on disk. The page SHALL compare a name with a folder's by full
Unicode case folding, as the engine does: a chapter takes the clips of every folder whose name folds to its
own. A name that differs from a folder's only in case therefore attracts that folder's clips, and a chapter
renamed between two spellings of a folder's name keeps them. The page SHALL say what the edit changes, in the
folder's own spelling, and nothing when it changes nothing.

#### Scenario: Renaming a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens "Edit title card for Kvällen" and types `Kväll` in the Name field
- **THEN** the text under the field says that no chapter will be named after the folder `Kvällen`, so clips added to it later will
  join `Main`. After the dialog is closed, the chapter `Kväll` says the same beside it.

#### Scenario: Dropping a rename says nothing
- **WHEN** after typing `Kväll` as above, the operator types `Kvällen` again
- **THEN** the text under the field is gone, and the chapter `Kvällen` says nothing about later clips

#### Scenario: A name that differs from the folder's only in case
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `kvällen`
- **THEN** the rename is accepted, and the page says nothing about later clips, since the folder `Kvällen`
  still joins this chapter

#### Scenario: A new chapter whose name differs from a folder's only in case
- **WHEN** after renaming `Kvällen` to `Kväll` on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a
  chapter and types `KVÄLLEN`
- **THEN** the dialog says that clips added to the folder `Kvällen` later will join this chapter

#### Scenario: A new chapter named after a folder
- **WHEN** after renaming `Kvällen` to `Kväll` on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a
  chapter and types `Kvällen`
- **THEN** the dialog says that clips added to the folder `Kvällen` later will join this chapter, and that
  the clips from it listed in other chapters stay where they are

#### Scenario: Deleting a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves the three clips of `Kvällen` to `Main` and
  deletes `Kvällen`
- **THEN** the deleted chapter says that clips added to the folder `Kvällen` later will join `Clips`, as the
  page now heads the event's own chapter, the only one left

#### Scenario: Renaming a chapter that lists an ignored clip
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` also ignores `Kvällen/s1710004.mp4`, and the
  operator renames `Kvällen` to `Kväll`
- **THEN** the text under the field and then the chapter say that its 1 ignored clip will be listed under `Main`. After
  saving, the page lists `Kvällen/s1710004.mp4` as ignored under the event's own chapter, and `Kväll` lists
  `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4`.

#### Scenario: Deleting a chapter that lists an ignored clip
- **WHEN** the `reel.yaml` of `2024-08-20 - Två kapitel - Tjörn` also ignores `Kvällen/s1710004.mp4`, and the
  operator moves the two clips `Kvällen` plays to `Main` and deletes `Kvällen`
- **THEN** the deleted chapter says that its 1 ignored clip will be listed under `Clips`, the event's own
  chapter's heading once it is the only one. After saving, the page lists `Kvällen/s1710004.mp4` as ignored under the event's own chapter.

### Requirement: The event page shows an empty chapter as empty

The event page SHALL show a chapter that plays no clip and lists no ignored clip with its heading and its
count of 0 clips. In place of a table, the page SHALL say that the chapter has no clips and is left out of
the movie. A chapter without clips has no title card and no chapter marker in the rendered movie.

#### Scenario: A saved empty chapter
- **WHEN** the operator adds a chapter `Kvällen vid grillen` to `2024-06-27 - Grillning med grannar` and saves
- **THEN**
  - `reel.yaml` lists the chapter after the event's own chapter, with no clips
  - the event page shows a `Kvällen vid grillen` panel counting 0 clips, saying that it has no clips and is
    left out of the movie, with no table
  - the page does not scroll horizontally in a window 320 pixels wide

### Requirement: Edit mode lists, adds and removes a clip's cuts

A clip's cuts are the spans of it that the movie leaves out. Each has a start and an end, in seconds from the
clip's start, and may have a reason. In Edit mode, every included or new clip that `reel.yaml` does not exclude (a clip on disk that a chapter
lists, or will list once the edits are saved) SHALL offer a **Cuts** control. The control SHALL say how many
cuts the clip has and, when it has any, how much time they cut out. Pressing it SHALL show or hide a panel
under the clip's row and SHALL leave keyboard focus on the control. The control SHALL say to assistive
technology whether the panel is shown, and SHALL name the clip as its row names it. In the keyboard order, the
Cuts control SHALL come after the row's other controls, and the panel's controls straight after it.

The panel SHALL list the clip's cuts in their order, each with its number in the list, its start and end, its
length and its reason in words. A clip without cuts SHALL say that the whole clip plays. A missing clip that
`reel.yaml` does not exclude SHALL show, in its row, how many cuts it has, and SHALL offer no Cuts control: its file is not on disk to cut, and
removing it from `reel.yaml` takes its cuts with it. Once the operator removes it, its row SHALL NOT show its
cuts any more, since the save drops them. An ignored clip SHALL have no cuts and no Cuts control.
An excluded clip is not in the movie, so its cuts do not apply: its row SHALL show no cuts and SHALL offer no
Cuts control, whether the clip is on disk or missing. Its cuts stay in `reel.yaml`, and a save SHALL write
them back unchanged.

**Times.** A cut's times are places in the clip, not moments in a day, so the format for moments ("Times are
written one way on every screen") does not apply to them. The page SHALL write a time as minutes and seconds
(`1:02.35`), with hours in front from one hour on (`1:01:15.5`). It SHALL write up to three decimals and no
trailing zero. It SHALL write a length under a minute in seconds (`1.5 s`), and from a minute on as a time. The time a clip's cuts cut out SHALL count, once,
every span that one or more of its cuts covers, as the render does.

**Adding a cut.** The panel SHALL take a start and an end, typed, and add the cut on request. Spaces around a
time SHALL be ignored. A time SHALL be accepted in each of these forms, with an optional decimal part of one
to three digits after `.` or `,`:

- seconds (`75.5`)
- minutes and seconds, the seconds as two digits below 60 (`1:15.5`)
- hours, minutes and seconds, the minutes and seconds each as two digits below 60 (`1:01:15.5`)

The cut SHALL be refused, and nothing added, when either time is empty or in no accepted form, or has more
than three decimals. It SHALL also be refused when its end is not after its start, when it shares more
than an instant with another cut of the clip that is not removed, or when it ends after the clip's length
once the page knows that length (below). A refusal SHALL be shown at the field it concerns, which SHALL
receive keyboard focus. It SHALL be announced, and it SHALL say what to type, which cut the new one overlaps,
or the clip's length. A cut that only touches another, the end of one being the start of the other, SHALL
be accepted. Times SHALL be compared to the millisecond, as they are typed and written, so a cut that starts
where another is shown to end touches it.

An added cut SHALL take its place in the list by its start, after every cut that starts at the same time or
earlier. It SHALL be saved with the reason `manual`. After an addition:

- both fields SHALL be empty again, with keyboard focus on the start field
- the addition SHALL be announced with the cut's times, the clip's name and its new cut count

**The clip's length.** The page knows a clip's length from one of two places, and the first it has wins: the
length the clip's preview has read from the clip's file in this Edit mode ("Edit mode previews a clip on
request"), else the duration the event detail gives the clip when it is not null (a thumbnail of the clip was
made before). The preview's length wins because it is the one Set From and Set To write times from, so a cut
set at the end of the clip is never refused. A null duration is unknown, never zero. When the page knows the
length from neither, the panel SHALL say that the page does not know the clip's length, that a cut that runs
past the clip's end stops there, and that a cut over the whole clip leaves the clip out of the movie, and it
SHALL NOT refuse a cut for its length. Once the page knows the length, from either place, the panel SHALL
state it beside its fields, SHALL refuse a cut that ends after it, and SHALL mark each listed cut that ends
after it ("A clip's preview sets cut times at the playhead and plays the clip as the movie will"), and
it SHALL still say that a cut over the whole clip leaves the clip out of the movie. The
duration of a clip the event detail gives SHALL NOT be sent anywhere, and neither length SHALL be saved.

**What a whole-clip cut does to a title card.** Wherever the panel says that a cut over the whole clip leaves
the clip out of the movie, it SHALL add that when the clip is its chapter's title clip, the chapter's title card
moves to the next clip of the chapter that plays. The render places a chapter's title card before the first
clip it plays when the title clip is cut away, and adds none to a chapter in which every clip is cut away. The
page does not know which clip is a chapter's title clip, so the sentence is conditional and the same for every
clip.

**Removing a cut.** Each cut SHALL offer **Remove**, which names the clip and the cut. A cut read from
`reel.yaml` SHALL then stay listed in its place, marked as removed when the edits are saved, with an **Undo**
that puts it back. Keyboard focus SHALL move to that Undo, and after an Undo to the cut's Remove. An Undo that
would make the cut share more than an instant with a cut added in this Edit mode SHALL be refused, as adding
that cut would be: the cut stays removed, keyboard focus stays on its Undo, and the refusal is shown in the
cut's row, announced, and names the cut to remove first. Two cuts read from `reel.yaml` that overlap there
SHALL NOT refuse each other's Undo: an Undo only goes back to what was read. A cut added in this Edit mode SHALL simply be gone.
Keyboard focus SHALL then move to the Remove of the cut that took its place, or of the cut before it, or to
the start field when no cut is left. Each removal and each Undo SHALL be
announced. After any addition, removal or Undo, the control holding keyboard focus SHALL be fully visible,
not covered by the page header, the chapter's heading or the save bar.

**Typed but not added.** While a panel's fields hold a typed time that was not added, the event SHALL count as
having unsaved changes. The save bar SHALL say that a cut was typed but not added, naming the clip as its row
names it when only one clip holds one, also after an edit that changes that name. Save, and Overwrite with mine after a conflict, SHALL say that they are unavailable until
the cut is added or its fields are cleared. Hiding the panel SHALL keep what was typed, and so SHALL moving the
clip to another chapter. The Cuts control of each clip whose panel holds such a time SHALL say so in words, at
every width and to assistive technology, also while its panel is hidden, so that the clip holding Save back
is found on its row. Reset SHALL empty every panel's fields.

While a save is in flight, the panel's fields, Add cut, Remove and Undo SHALL say that they are unavailable
and change nothing when used. The Cuts control SHALL still show and hide its panel, since that changes nothing
to save.

The Cuts control and every control in the panel SHALL take a tap anywhere in an area of at least 44 × 44 CSS
pixels around it when the primary pointer is coarse, reaching no other control, as every button does ("Every
control is large enough to touch"). With every panel hidden, the Cuts control SHALL NOT make a row taller in a
window 320 or 390 pixels wide. No panel SHALL make the page scroll horizontally from 320 pixels up.

#### Scenario: Opening a clip's cuts
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator presses the Cuts control of
  `s1710001.mp4`
- **THEN** a panel under its row says that the whole clip plays and offers a start and an end field and Add
  cut. Keyboard focus is still on the Cuts control, which says that its panel is shown.

#### Scenario: Adding a cut with typed times
- **WHEN** in that panel the operator types `0` as the start and `1,5` as the end and presses Enter
- **THEN**
  - the panel lists one cut, from `0:00` to `0:01.5`, 1.5 s long, its reason "Cut by hand"
  - the Cuts control reads "1 cut · −1.5 s"
  - both fields are empty, with keyboard focus on the start field
  - the addition is announced
  - the save bar says that 1 cut was added

#### Scenario: Every accepted form of a time
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from ` 0:00:01.25 `
  to `0:02.5`, and then one from `4` to `0:06`
- **THEN** the panel lists the cuts from `0:01.25` to `0:02.5` and from `0:04` to `0:06`, in that order, and the
  Cuts control reads "2 cuts · −3.25 s"

#### Scenario: A time the page cannot read
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `1:5` as the start and
  `2` as the end and asks to add the cut, then types `-1` as the start, then `0.1234`
- **THEN** each is refused at the start field, which keeps keyboard focus. The first two are refused as no time
  the page can read, naming the three forms. The last is refused for its four decimals. No cut is added.

#### Scenario: A cut that does not end after it starts
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `3` as the start and
  `2` as the end and asks to add the cut
- **THEN** the cut is refused at the end field, which receives keyboard focus, saying that a cut must end after
  it starts, and no cut is added

#### Scenario: A clip never previewed is not checked for length
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose detail gives a duration of `null`
  and whose preview was not opened in this Edit mode, the operator adds a cut from `5` to `7`
- **THEN** the cut is accepted and listed, and the panel says that the page does not know the clip's length and
  that a cut that runs past the clip's end stops there

#### Scenario: A clip whose duration the service gives is checked before any preview
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, whose detail gives a duration of `6.02`
  and whose preview was not opened in this Edit mode, the operator adds a cut from `5` to `7`
- **THEN** the panel says that the clip ends at `0:06.02`, the cut is refused at the end field, which receives
  keyboard focus, saying that `0:07` is after the clip's end at `0:06.02`, and no cut is added
- **WHEN** the operator types `0:06.02` as the end and adds the cut
- **THEN** the cut from `0:05` to `0:06.02` is listed

#### Scenario: The panel says where a whole-clip cut sends the title card
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator opens the Cuts panel of
  `s1710001.mp4`, the first clip of its chapter, before and after opening its preview
- **THEN** both times the panel says that a cut over the whole clip leaves the clip out of the movie and that,
  when it is the chapter's title clip, the chapter's title card moves to the next clip of the chapter that plays

#### Scenario: A cut that overlaps another
- **WHEN** `s1710001.mp4` of `2024-06-27 - Grillning med grannar` has a cut from `0:00` to `0:01.5`, and the
  operator adds one from `1` to `2`
- **THEN** it is refused, saying that it overlaps cut 1 (`0:00` to `0:01.5`)
- **WHEN** the operator then adds one from `1.5` to `2`
- **THEN** it is accepted and listed second

#### Scenario: Removing a cut read from reel.yaml, and undoing it
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds with the reason `black`, and in Edit mode the operator presses that cut's Remove
- **THEN** the cut stays listed, marked as removed when the edits are saved, with an Undo that has keyboard
  focus, and the save bar says that 1 cut is removed
- **WHEN** the operator presses that Undo
- **THEN** the cut is listed as before, its reason "Black frames", keyboard focus is on its Remove, and the page
  shows no unsaved changes

#### Scenario: An Undo that would overlap is refused
- **WHEN** with that same `reel.yaml`, the operator removes the cut from 0 to 1.2 seconds of `s1710003.mp4`, adds
  one from `1` to `2`, and presses the removed cut's Undo
- **THEN** the Undo is refused, saying that cut 1 overlaps cut 2 (`0:01` to `0:02`) and that cut 2 must be
  removed first. Cut 1 stays removed, keyboard focus stays on its Undo, and the save bar still says that 1 cut
  was added and 1 removed.

#### Scenario: Read cuts that overlap do not refuse each other's Undo
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` cuts from 0 to 3 seconds
  and from 2 to 4 seconds, and the operator removes both and presses each one's Undo
- **THEN** both are listed as before, and the page shows no unsaved changes

#### Scenario: A cut starts where another is shown to end
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 3.2033333
  seconds, listed as ending at `0:03.203`, and the operator adds one from `3.203` to `4`
- **THEN** it is accepted and listed second

#### Scenario: Removing a cut added in this Edit mode
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator adds a cut from `0` to `1.5`
  and presses its Remove
- **THEN** the panel says that the whole clip plays again, keyboard focus is on the start field, and the page
  shows no unsaved changes

#### Scenario: A missing clip's cuts are shown, not edited
- **WHEN** the `reel.yaml` of `2024-09-01 - Sommarlov` gives the missing `borttagen.mp4` a cut from 0 to 2
  seconds, and the operator opens Edit mode
- **THEN** the row of `borttagen.mp4` says that it has 1 cut and offers Remove but no Cuts control, while
  `s1710002.mp4` and `s1710004.mp4` offer theirs
- **WHEN** the operator presses Remove on `borttagen.mp4`
- **THEN** its row is listed as removed when the edits are saved and no longer says that it has a cut

#### Scenario: An excluded clip offers no cuts
- **WHEN** the operator enters Edit mode on an event whose `reel.yaml` excludes `s1710002.mp4`, which is on
  disk and has a cut from `0` to `1.5`
- **THEN** its row offers no Cuts control and shows no cut count, the other clips of the chapter still offer
  theirs, and saving another edit writes the cut back unchanged

#### Scenario: An ignored clip has no cuts
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the ignored `s1710004.mp4` offers no Cuts control, and every clip `Main` and `Kvällen` play offers one,
  the new `Kvällen/s1710004.mp4` included

#### Scenario: A cut typed but not added holds Save back
- **WHEN** on `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, the operator types `2` as the start, adds
  nothing, and hides the panel
- **THEN** the save bar says that a cut was typed on `s1710001.mp4` but not added, and Save says that it is
  unavailable. Opening the panel again shows `2` in the start field.
- **WHEN** the operator then presses the browser's Back
- **THEN** the page stays and asks "Discard unsaved changes?"

#### Scenario: A typed cut moves with its clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator types `2` as the start of a cut on
  `Kvällen/s1710002.mp4`, which `Kvällen` names `s1710002.mp4`, adds nothing, and marks that clip and moves it to
  `Main` with Move marked to…
- **THEN** the save bar now says that a cut was typed on `Kvällen/s1710002.mp4` but not added, Save says that
  it is unavailable, and the clip's Cuts panel, now in `Main`, is still shown with `2` in the start field

#### Scenario: Hidden panels holding typed text are marked on their rows
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator types `5` in the start field of `s1710002.mp4`
  and hides its panel, then types `1:00` in the start field of `s1710004.mp4` and hides that panel
- **THEN** the save bar says that cuts were typed on 2 clips but not added, and the Cuts controls of those two
  clips, and of no other, say "typed" and that a cut was typed but not added
- **WHEN** the operator clears the field of `s1710002.mp4`
- **THEN** its Cuts control no longer says so, and the save bar names `s1710004.mp4`

#### Scenario: Cut controls wait for a save
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its panel shown, the
  operator presses Save and the service has not answered yet
- **THEN** the start and end fields, Add cut and the cut's Remove say that they are unavailable, typing and
  pressing them change nothing, and the Cuts control still hides and shows the panel

#### Scenario: Cuts on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** each clip row is as tall as on the page before this change, and a tap anywhere in a 44 × 44 pixel area
  around the Cuts control of `Kvällen/s1710002.mp4` reaches that control and no other
- **WHEN** the operator opens that panel and adds a cut from `0` to `1`
- **THEN** the page does not scroll horizontally, and a tap anywhere in a 44 × 44 pixel area around each of the
  panel's fields, Add cut and the cut's Remove reaches that control and no other

### Requirement: The event page shows each clip's cuts

The event page SHALL show, beside the name of each clip that has cuts in `reel.yaml` and that `reel.yaml`
does not exclude, how many cuts it has and
how much time they cut out ("2 cuts · −4.5 s"), counted as Edit mode counts them. On request, the page SHALL
show the clip's cuts there, as Edit mode lists them, without any control that changes them. A clip without
cuts SHALL show nothing more than before, and so SHALL an excluded clip: it is not in the movie, so its cuts
do not apply. The indicator SHALL be operable from the keyboard. It SHALL say to
assistive technology whether the list is shown, and it SHALL be read as the number of cuts and the time cut
out, not as a minus sign. When the primary pointer is coarse, it SHALL take a tap anywhere in an area of at
least 44 × 44 CSS pixels around it, reaching no other control. No shown list SHALL make the page scroll
horizontally from 320 pixels up, whatever the length of its times.

The page SHALL read the cuts from the service each time it reads the event, after the event read, and SHALL
keep showing the cuts it read last until the new read answers. That read SHALL NOT write anything, as no read
does ("Reading a screen never changes state"). When it fails, the page SHALL show the event's clips without
cuts, with a note that says the cuts could not be read and why. The note is part of the page's content, not an
alert.

#### Scenario: A clip's cuts on the event page
- **WHEN** the operator has saved a cut from `0` to `1.5` on `s1710001.mp4` of
  `2024-06-27 - Grillning med grannar`
- **THEN** the event page shows "1 cut · −1.5 s" beside `s1710001.mp4` and nothing beside its other clips
- **WHEN** the operator activates that indicator from the keyboard
- **THEN** it says that its list is shown, and lists the cut from `0:00` to `0:01.5`, 1.5 s long, "Cut by hand",
  with no control to change it

#### Scenario: An excluded clip shows no cuts
- **WHEN** `reel.yaml` excludes `s1710002.mp4` and holds a cut from `0` to `1.5` on it
- **THEN** the event page shows no cut indicator beside `s1710002.mp4`

#### Scenario: The cuts cannot be read
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` and the service does not answer the read of
  its cuts
- **THEN** the page shows its chapters and clips, with a note that the cuts could not be read because the
  service is not reachable, and nothing is announced as an alert

#### Scenario: Reading cuts changes nothing
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, opens a clip's cut list, refreshes the page
  and goes back to the list
- **THEN** every request the client made was a read, and no file under the library changed

### Requirement: Edit mode drags clips between chapters

While the event lists more than one chapter, a deleted one aside, the operator SHALL be able to drag a clip
on disk (active or new) that a chapter plays into any other listed chapter. The operator SHALL be able to
drop it there before any clip that chapter plays, or after the last of them. Both ways a clip is dragged
within its chapter SHALL do this:

- **with a mouse, pen or touch**, from the clip's handle. While the dragged clip is held near the window's
  top or bottom edge, the page SHALL scroll by itself, so that a chapter out of view can be reached. The
    speed SHALL grow with how far into the edge the pointer is, from nothing at the inner edge of the
    scrolling zone, and with the pointer at the window's very edge it SHALL be at least 600 and at most 2,000
    CSS pixels per second, however many rows the page holds.
- **from the keyboard**, on the clip's handle:
  - Down at a chapter's last position SHALL take the clip to the first position of the next listed chapter.
  - Up at a chapter's first position SHALL take it to after the last clip of the chapter before.
  - A deleted chapter's placeholder SHALL be passed over.
  - Page Down SHALL take the clip to the first position of the next listed chapter, and Page Up to the first
    position of the chapter before, wherever the clip is held. A chapter the clip does not play is entered at
    its first gap, before its first clip, and an empty one at its area. At the last chapter (Page Down) or the
    first (Page Up), and for a missing clip, which stays in its chapter, and while one chapter is listed, the
    key SHALL move nothing. When it moves the clip, the place the clip is then over (the line, or the empty
    chapter's area) and the dragged copy SHALL both be in the window, however far the page had to scroll to
    get there. A Page Down or Page Up pressed while a clip is lifted SHALL NOT otherwise scroll the page, whether
    or not it moved the clip.
  - Escape SHALL cancel and leave every chapter as it was, with the clip's handle in view again (its whole
    row, or its first line when the row is taller than the room left).

A chapter that plays no clip SHALL show, in Edit mode, an area for clips. While the event lists another
chapter, a deleted one aside, the area SHALL say that clips can be dragged into it. When the chapter is the
only one listed, the area SHALL say only what "Edit mode adds, renames, reorders and deletes chapters" states
for it, because no other chapter has a clip to drag. The area SHALL be shown whether or not a drag is under
way. A clip dropped on it SHALL become the chapter's first clip.

While a clip is dragged over another chapter:

- the page SHALL show where a drop puts it: a line at the place between two of that chapter's clips or after
  its last clip, or, for a chapter that plays no clip, its area marked as the target
- a copy of the clip SHALL follow the pointer and SHALL name the target chapter and the position that the drop
  gives the clip
- that chapter's clips SHALL NOT move to make room, and no part of the page SHALL change size or place;
  within the clip's own chapter, its other clips still make room, as before
- the clip's own row SHALL stay in its chapter, marked as the clip being moved, until it is dropped
- while the clip is held by a pointer, no other part of the page SHALL show that the pointer is over it,
  and the pointer SHALL show that it holds the clip
- in forced colors, the line and the copy's edge SHALL stay visible

Within its own chapter, a clip SHALL stay at its place while the pointer is over its own row, however tall
the row is: lifting a clip and releasing it there moves nothing.

A drop into another chapter SHALL be one edit. The clip leaves its chapter and joins the other one at the
position where it was dropped. Every other clip keeps its order. Then:

- its row SHALL show the chapter it came from, and it SHALL count once as a moved clip, in its new chapter's
  heading and in the save bar, as a clip moved with Move marked to… does
- a clip dragged back to the chapter and the position it had when Edit mode opened SHALL count as no move;
  with no other edit, the page SHALL show no unsaved changes
- it SHALL keep its cuts and its other per-clip properties. Its Cuts control SHALL be as it was, and its
  panel stays shown or hidden as it was and keeps any time typed but not added
- Save SHALL write it as it writes a clip moved with Move marked to… ("Saving an edit writes only what the operator
  changed"). Reset, the unsaved-changes question, a conflict and Overwrite SHALL treat it as any other edit

Every target in another chapter SHALL be announced to assistive technology, and so SHALL a drop and a
cancel. The announcement names the clip as its row named it when it was lifted. A target or a drop in another
chapter SHALL name that chapter, and SHALL give the position out of the number of clips that chapter would
then play. Within the clip's own chapter the announcements SHALL stay as "The event page reorders clips
within a chapter" states. While more than one chapter is listed, the instructions for a keyboard drag SHALL
say that the arrows cross into the chapter before or after, and that Page Down and Page Up jump to the next
or the previous chapter.

After a drop into another chapter, by pointer or keyboard, keyboard focus SHALL be on the moved clip's
handle in its new chapter. The handle and the row's first line (its handle, name and Cuts control) SHALL be
fully visible, not covered by the page header, the chapter's heading or the save bar. A row taller than that
space SHALL be scrolled so that its first line is (see "Edit mode keeps keyboard focus in view and never
drops it").

Some clips cannot be marked ("Edit mode marks clips to move together"), so Move marked to… never moves them,
and those SHALL NOT be taken into another chapter by a drag either:

- a missing clip: its drag SHALL stop at its own chapter's edge, from the keyboard too. While more than one
  chapter is listed, its lift SHALL say that it stays in its chapter.
- an ignored clip, and a missing clip the operator removed: neither has a handle

A release over a deleted chapter's placeholder SHALL move nothing and SHALL be announced as a drop that
changed nothing. While a save is in flight, or while a move of marked clips is being applied, no clip SHALL be
lifted, and a drop SHALL move nothing. Move marked to…, and Move up and Move down, SHALL work as they
did before.

In the Clips help ("Each explanation sits behind a Help toggle of its section"), Edit mode SHALL say how clips are moved:

- with one chapter: that a clip is dragged by its handle or moved with its arrows, and that a chapter can be
  added with Add chapter, below the chapters, after which clips can be dragged between chapters
- with more than one chapter: that a clip can also be dragged into another chapter, and that Move marked to… moves the marked clips to a chapter

On a coarse pointer a drag SHALL start only from the handle, as within a chapter. In a window 320 CSS pixels
wide or wider, and in both color schemes, no state of a drag SHALL make the page scroll horizontally. Under
reduced motion, no clip SHALL slide into place, and the dragged copy SHALL NOT slide between positions.

#### Scenario: Dragging a clip into the chapter above
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the operator drags `Kvällen/s1710003.mp4` by its
  handle up into `Main` and holds it over the upper half of `s1710001.mp4`
- **THEN** a line shows above `s1710001.mp4`, the dragged copy says it goes to `Main` at position 1 of 2, and
  `s1710001.mp4` has not moved
- **WHEN** the operator releases it there
- **THEN**
  - `Main` plays `Kvällen/s1710003.mp4` and then `s1710001.mp4`, the first marked as coming from `Kvällen`,
    and its heading says 1 clip moved
  - `Kvällen` plays `s1710002.mp4` and the new `s1710004.mp4`, and its heading counts no clip moved
  - keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`, and the row's first line is fully
    visible above the save bar
  - "s1710003.mp4 moved to “Main”, position 1 of 2" is announced
  - the save bar says that 1 clip moved and that saving adds 1 new clip to `reel.yaml`

#### Scenario: Saving a dragged clip
- **WHEN** after that drag the operator saves
- **THEN** `reel.yaml`'s default chapter lists `Kvällen/s1710003.mp4` and then `s1710001.mp4`, `Kvällen` lists
  `Kvällen/s1710002.mp4` and then `Kvällen/s1710004.mp4`, `s1710004.mp4` is still ignored, and no other line
  of the file changed

#### Scenario: Dragging a clip back leaves nothing to save
- **WHEN** after the drag into `Main` on `2024-08-20 - Två kapitel - Tjörn`, the operator drags
  `Kvällen/s1710003.mp4` back into `Kvällen` and releases it between `s1710002.mp4` and `s1710004.mp4`
- **THEN** both chapters play what they played when Edit mode opened, no row is marked as moved, and the page
  shows no unsaved changes

#### Scenario: Crossing into the next chapter from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator focuses the handle of `s1710001.mp4`, lifts the
  clip and presses Down
- **THEN** "s1710001.mp4 is over “Kvällen”, position 1 of 4" is announced, and a line shows above
  `s1710002.mp4` in `Kvällen`
- **WHEN** the operator presses Down again and drops the clip
- **THEN**
  - `Kvällen` plays `s1710002.mp4`, `s1710001.mp4`, `s1710003.mp4` and `s1710004.mp4`, with `s1710001.mp4`
    marked as coming from `Main`
  - `Main` plays no clip, still lists the ignored `s1710004.mp4`, and shows its area for clips dragged into it
  - "s1710001.mp4 moved to “Kvällen”, position 2 of 4" is announced
  - keyboard focus is on the handle of `s1710001.mp4` in `Kvällen`

#### Scenario: Crossing into the chapter before from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `Kvällen/s1710002.mp4` from the keyboard,
  presses Up once and drops it
- **THEN** "s1710002.mp4 is over “Main”, position 2 of 2" was announced, and `Main` plays `s1710001.mp4` and
  then `Kvällen/s1710002.mp4`

#### Scenario: Page Down jumps to the next chapter from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `s1710001.mp4` from the keyboard and presses
  Page Down
- **THEN** "s1710001.mp4 is over “Kvällen”, position 1 of 4" is announced, and a line shows above
  `s1710002.mp4` in `Kvällen`
- **WHEN** the operator presses Page Down again
- **THEN** the line has not moved and nothing is announced
- **WHEN** the operator presses Page Up
- **THEN** "s1710001.mp4 is over position 1 of 1." is announced, and the line in `Kvällen` is gone
- **WHEN** the operator drops the clip
- **THEN** "s1710001.mp4 dropped at position 1 of 1, unchanged." is announced, and both chapters are as they were

#### Scenario: Page Down and Page Up cross a long chapter in one press
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, `Kväll`, and the operator
  lifts the 200th clip of the first chapter from the keyboard and presses Page Down
- **THEN** "c0200.mp4 is over “Kväll”, position 1 of 4" is announced, and the line above `Kväll`'s first clip
  and the dragged copy are both in the window
- **WHEN** the operator presses Page Up
- **THEN** "c0200.mp4 is over position 1 of 400." is announced, and the first clip's row and the dragged copy
  are both in the window
- **WHEN** the operator presses Escape
- **THEN** the clip is back at position 200 of 400, with its handle in the window

#### Scenario: Page Up jumps to the chapter before from the keyboard
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `Kvällen/s1710004.mp4` from the keyboard
  (the third position of `Kvällen`), presses Page Up and drops it
- **THEN** "s1710004.mp4 is over “Main”, position 1 of 2" was announced, and `Main` plays `Kvällen/s1710004.mp4`
  and then `s1710001.mp4`

#### Scenario: Page keys with one chapter or a missing clip move nothing
- **WHEN** in a window 390 × 600 on `2024-06-27 - Grillning med grannar`, which has one chapter, the operator
  lifts `s1710001.mp4` from the keyboard and presses Page Down with the page scrolled to its top
- **THEN** the clip is still over its own place, nothing is announced, and the page has not scrolled
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator lifts `borttagen.mp4` and
  presses Page Down
- **THEN** the clip is still over its place in `Main`, and `Morgon` plays no clip

#### Scenario: Escape cancels a drag into another chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator lifts `s1710001.mp4` from the keyboard, presses
  Down twice, and presses Escape
- **THEN** both chapters are as they were, keyboard focus is on the handle of `s1710001.mp4`, fully visible,
  and "Move cancelled. s1710001.mp4 is back at position 1 of 1." is announced

#### Scenario: A tall row lifted and released in place
- **WHEN** in a window 390 × 844 on `2024-08-20 - Två kapitel - Tjörn`, with the Cuts panel of
  `Kvällen/s1710003.mp4` shown, the operator presses its handle, moves the pointer 10 pixels and releases it
- **THEN** "Picked up s1710003.mp4, position 2 of 3." and "s1710003.mp4 dropped at position 2 of 3,
  unchanged." are announced, and `Kvällen` plays `s1710002.mp4`, `s1710003.mp4` and `s1710004.mp4` as before

#### Scenario: Dragging a clip into an empty chapter
- **WHEN** on `2024-06-27 - Grillning med grannar`, the operator adds a chapter `Kvällen vid grillen`
- **THEN** the new chapter shows an area that says clips can be dragged into it
- **WHEN** the operator drags `s1710004.mp4` onto that area
- **THEN** the area is marked as the target, the dragged copy says it goes to `Kvällen vid grillen` at position
  1 of 1, and nothing else on the page has moved
- **WHEN** the operator releases it and saves
- **THEN** `reel.yaml` lists `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4` in the default chapter and
  `s1710004.mp4` in `Kvällen vid grillen`, and the save bar said that 1 chapter was added and 1 clip moved

#### Scenario: A deleted chapter takes no clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator marks all three clips of `Kvällen` and moves them to `Main`
  with Move marked to…, deletes `Kvällen`, adds a chapter `Morgon`, lifts `Kvällen/s1710004.mp4` (last in `Main`)
  from the keyboard and presses Down
- **THEN** "Kvällen/s1710004.mp4 is over “Morgon”, position 1 of 1" is announced: the deleted `Kvällen` was
  passed over
- **WHEN** the operator presses Escape, then drags `Kvällen/s1710004.mp4` with the mouse and releases it over
  the deleted `Kvällen`
- **THEN** no chapter changed, and the drop is announced as one that changed nothing

#### Scenario: A missing clip stays in its chapter
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator lifts `borttagen.mp4`
  from the keyboard
- **THEN** "Picked up borttagen.mp4, position 3 of 3. It is missing, so it stays in “Main”." is announced
- **WHEN** the operator presses Down and drops it
- **THEN** `borttagen.mp4` is still at position 3 of `Main`, and `Morgon` plays no clip

#### Scenario: A dragged clip keeps its cuts and what was typed
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens the Cuts of `Kvällen/s1710002.mp4`, adds a
  cut from 0 to 1.5 seconds, types `2` in the start field, and drags the clip into `Main` after `s1710001.mp4`
- **THEN** in `Main` the clip's Cuts panel is still shown, listing that cut, and its start field holds `2`;
  keyboard focus is on its handle, and the row's first line (handle, name, Cuts control) is fully visible,
  below the chapter's heading and above the save bar; the save bar says that a cut was typed on
  `Kvällen/s1710002.mp4` and not added, and Save says that it is unavailable

#### Scenario: No drag while a save is in flight
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a dragged clip not yet saved, the operator presses Save
  and the service has not answered yet
- **THEN** pressing Space on the handle of `s1710001.mp4` lifts nothing and announces nothing, a mouse drag
  from that handle moves nothing, and every chapter stays as it was

#### Scenario: Dragging by touch on a phone
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, a touch starts on the
  handle of `Kvällen/s1710002.mp4` and moves up into `Main` above `s1710001.mp4` before it lifts
- **THEN** `Main` plays `Kvällen/s1710002.mp4` first, and the page did not scroll horizontally
- **WHEN** a touch starts on that clip's name and moves up
- **THEN** the page scrolls, and no clip moves

#### Scenario: The edge scrolls fast enough to cross a long chapter, and no faster
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, the operator lifts the second
  chapter's first clip with the pointer, with the page scrolled to that chapter, and holds the pointer at the
  window's very top edge (its first pixel row) for 2 seconds
- **THEN** the page scrolled up between 1,200 and 4,000 CSS pixels over those 2 seconds (an average between 600
  and 2,000 per second)
- **WHEN** the operator moves the pointer out of the scrolling zone
- **THEN** the page stops scrolling
- **WHEN** the operator holds the pointer in the middle of the zone (a tenth of the window's height below its
  top edge) for 2 seconds
- **THEN** the page scrolls up by between a quarter and three quarters of what it scrolled at the very edge

#### Scenario: Reaching a chapter out of view
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, and the operator drags the
  second chapter's first clip up and holds it at the window's top edge
- **THEN** the page scrolls up by itself until the first chapter's first clip is in view
- **WHEN** the operator releases the clip over the upper half of that first clip
- **THEN** the clip is at position 1 of 401 in the first chapter, and the second chapter plays 2 clips

#### Scenario: The hint says how to reach other chapters
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, which has one chapter
- **THEN** the Clips help, opened, says that a chapter can be added with Add chapter, below the chapters,
  and that clips can then be dragged between chapters
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the Clips help says that a clip can be dragged into another chapter, and that Move marked to… moves the marked clips to a chapter

#### Scenario: Nothing shifts while dragging over another chapter
- **WHEN** in a window 320 pixels wide, in the light and in the dark scheme, on `2024-08-20 - Två kapitel -
  Tjörn`, the operator drags `s1710001.mp4` over `Kvällen` and holds it between `s1710002.mp4` and
  `s1710003.mp4`
- **THEN** every clip row and both chapter panels keep the size and place they had before the drag, the line
  between the two clips is visible beside the dragged copy, and the page does not scroll horizontally

### Requirement: The event page plays the event's rendered movie

When the event has a rendered movie, its page SHALL show a section headed "Movie" (a level-two heading) in the read
view, between the region that holds the verdict and the render controls and the event's chapters. The event has a
rendered movie exactly when its staleness verdict cites neither `no_manifest` nor `output`. The page SHALL decide
this from the event detail alone. An event without one SHALL show no movie section and SHALL make no request for a
movie. In Edit mode the page SHALL show no movie section. Leaving Edit mode reads the event again, and the section
returns with that read.

**Which file, and its version.** On each read of the event that shows the section, the page SHALL ask the service
for the first byte of the event's movie (`GET /api/v1/events/{event_id}/movie` with `Range: bytes=0-0`, never
served from or stored in the browser's cache). It SHALL take from that answer only what the service sent:
- the movie's entity-tag
- its size in bytes, from `Content-Range`
- its file name, from `Content-Disposition`

The player SHALL load the movie from the same route with that entity-tag, without its quotes, as the `v` query
parameter. The event id SHALL be encoded segment by segment, as on every events route. When a re-read the page
starts by itself (when the job it shows reaches a finished state, see "A shown screen re-reads in place when events
change") finds the same entity-tag, the player SHALL stay as it is, playing or paused, at its position. When it
finds a different one, the page SHALL replace the player with a new one at the new address. If the old player had
keyboard focus, the new one SHALL receive it. The old address SHALL never be used for the new file. Opening the page
and leaving Edit mode replace the page's content with placeholders while it reads (see "The event page shows the
event's chapters and clips"), and the section returns with a new player, paused at its start, at the address of
the entity-tag that read finds.

**A Refresh keeps the player.** An operator's Refresh of a page that shows the section SHALL replace the rest of
the page's content with placeholders, as every read of the event does, but SHALL keep the section and its
player while it reads, playing or paused, at its position. The player SHALL be the same one, not a new element at
the same address, and the Refresh SHALL NOT start, stop or seek it. When the read finds the same entity-tag, the
player SHALL stay as it is after it. When it finds a different one, the page SHALL replace the player with a new
one at the new address, with keyboard focus as above. When it finds that the event has no movie, or it fails, the
section SHALL go as it does for any read. While the read runs, the section SHALL show its heading and its player
and nothing that the read may change ("A read in progress is shown as a placeholder and announced"), and SHALL be
marked as busy; the verdict, the facts and the sentence return with the read's answer. A Refresh SHALL NOT request
any byte of the movie while the read runs.

**Nothing loads before Play.** Opening, refreshing or returning to the page SHALL NOT request any byte of the movie
other than the one-byte answer above, and SHALL NOT start playback. Playback SHALL start only from the operator's
action on the player, or on a chapter of the list under it. The player SHALL NOT loop and SHALL NOT be muted by the page. Its poster SHALL be the thumbnail
of the event's first played clip that is on disk, in the order the event page lists them, at the same address its
row uses. The page SHALL show no poster when there is no such clip, or when that thumbnail cannot be loaded.

**What the section says.**
- Whether the movie is **Current**, when the event is up to date, or **Outdated**, when it needs a render. Each is
  shown in words with an icon, never by color alone.
- For an outdated movie, a sentence that it was rendered before the event's latest changes and that a render
  brings it up to date.
- The movie's file name, as the service names it, and its size in the units the event page uses for clips. In the
  `output_renamed` case this is the movie under its old name. A fact the answer did not carry SHALL be left out,
  never guessed.
- When the event detail carries the movie's version (`movie.recorded_at`, when the render record was written, and
  `movie.fingerprint`, the short identity of the inputs it was made from), written as "Recorded" with that time in
  the one way the client writes times, then "version" and the fingerprint, in the same facts as the file's name
  and size. The time SHALL be kept exact in `<time dateTime>`. It is when the render finished for a rendered
  movie and when it was adopted for an adopted one, which the detail does not tell apart, so the page says
  "Recorded", not "Rendered". A version the detail did not carry (`movie` null) SHALL be left out, never
  guessed or replaced by the file's modification time.

**The player.**
- It SHALL be the browser's own media player with its native controls. It SHALL be named by the section's heading.
- The page SHALL add no keyboard shortcut of its own. The player SHALL be reachable with Tab, and SHALL show a
  visible focus indicator in both color schemes that nothing clips, on the player itself and on every Tab stop of
  its native controls.
- The page SHALL show no captions control. The player's own controls show no chapters: the movie's chapters are
  listed under the player when the event detail gives their times ("The movie player lists the rendered movie's
  chapters").
- It SHALL show the movie in a frame of 16:9 proportions that has its final size before any byte arrives. The
  frame SHALL be at most 768 CSS pixels wide, and no taller than the window leaves below the shared header, which
  stays in place while the page scrolls, and the section heading. A picture of other proportions SHALL be shown
  whole inside it, on a dark surround in both schemes.
- In a window from 320 to 1280 CSS pixels wide, the page SHALL NOT scroll horizontally, and the file name SHALL wrap
  rather than overflow.
- The section SHALL NOT animate, and its heading SHALL scroll with the page rather than stay in place over the
  player.

#### Scenario: A current movie
- **WHEN** the operator opens `2024-07-14 - Kalas`, which is up to date
- **THEN** the page shows a "Movie" section above its chapters that says "Current", names
  `2024-07-14 - Kalas.mp4` with its size, and shows a player whose poster is the thumbnail of `s1710002.mp4`
- **AND** the only request for the movie is one `Range: bytes=0-0` request, the player's address carries that
  answer's entity-tag as `v`, and after five seconds the player is paused at its start

#### Scenario: Playing from the keyboard
- **WHEN** the operator tabs from the page's Edit button to the player of `2024-07-14 - Kalas` and presses Space,
  waits two seconds, and presses Space again
- **THEN** the movie plays for those two seconds and then pauses, and the player shows a visible focus indicator
  throughout

#### Scenario: An outdated movie under its old name
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, whose title changed after its render, so its
  staleness cites `editorial` and `output_renamed`
- **THEN** the "Movie" section says "Outdated" with the sentence on what a render does, names the file under the
  old name `2024-06-27 - Grillning med Grannar.mp4`, and plays that file

#### Scenario: No movie, no section, no request
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, `2024-10-05 - Trasig`, `2024/Blandat` and
  `2024-07-14 - kalas` (which has no render record, although `2024-07-14 - Kalas`'s movie lies at its expected path)
- **THEN** none of these pages shows a "Movie" section, and none of them requests a movie

#### Scenario: A finished render replaces the player
- **WHEN** the operator plays the movie of `2024-06-21 - Midsommar - Dalarna` from the keyboard and pauses it,
  keyboard focus stays on the player, and a forced render of the event, started from elsewhere (another tab, or `POST
  /api/v1/jobs`), finishes while the page is shown
- **THEN** after the page's read the player loads from an address with the new file's entity-tag, keyboard focus is
  on the new player, and it plays the new movie

#### Scenario: A read that finds the same movie keeps playing
- **WHEN** the movie of `2024-06-27 - Grillning med grannar` is playing, and a forced render of the event is
  queued from elsewhere and cancelled before it starts, so the page reads the event again
- **THEN** the player is the same one, still playing, and its position did not jump back

#### Scenario: Edit mode shows no movie
- **WHEN** the operator opens Edit mode on `2024-06-27 - Grillning med grannar` and then leaves it
- **THEN** the "Movie" section is absent while Edit mode is open, and is shown again, paused at its start, after it
  closes

#### Scenario: The player at phone width
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in windows 320 and 390 pixels wide, in both
  color schemes
- **THEN** the page does not scroll horizontally, the frame spans the section's width at 16:9, and the file name
  and the outdated sentence wrap inside it

#### Scenario: The player in a wide window
- **WHEN** the operator opens `2024-07-14 - Kalas` in a window 1280 × 800 pixels and scrolls the frame into view
- **THEN** the frame is 768 × 432 pixels and lies whole between the bottom of the shared header, which stays in
  place while the page scrolls, and the bottom of the window

#### Scenario: Refresh keeps the movie playing
- **WHEN** the movie of `2024-07-14 - Kalas` is playing, 3 seconds in, and the operator presses Refresh
- **THEN** the page shows placeholders for the rest of its content while it reads, and the player is the same
  element, still playing, whose position never went back; after the read the "Movie" section says "Current" again
  and its player's address carries the same entity-tag as before
- **AND** the only request for the movie during and after the Refresh is one `Range: bytes=0-0` request, made when
  the read answered

#### Scenario: Refresh starts the player over
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and a forced render of the event, started from elsewhere,
  replaces its file, and then the operator presses Refresh
- **THEN** after the read the page shows a new player, paused at its start, at an address that carries the new
  entity-tag, and the old address is not used again

#### Scenario: Refresh finds no movie
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and its render record is removed from disk before the
  operator presses Refresh
- **THEN** after the read the page shows no "Movie" section, and keyboard focus stays on the Refresh button

#### Scenario: Refresh that fails takes the movie with the rest
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and the service is stopped before the operator presses Refresh
- **THEN** the page shows its failure as for any read, and no "Movie" section

#### Scenario: The movie's version is shown
- **WHEN** the operator opens `2024-07-14 - Kalas`, whose detail carries the version of its latest render
  (`recorded_at` 2026-10-03 14:02, fingerprint `a1b2c3d4e5f6`)
- **THEN** the "Movie" section's facts say `2024-07-14 - Kalas.mp4`, its size, and "Recorded Oct 3, 2:02 PM ·
  version a1b2c3d4e5f6", with the exact instant in the `<time>` element's `dateTime`

#### Scenario: A movie whose version is not recorded
- **WHEN** the operator opens an event whose staleness shows a movie but whose detail's `movie` is `null` (the
  service could not tell a version, for instance a record without a usable time)
- **THEN** the facts name the file and its size and say nothing of a time or a version

### Requirement: The movie player says what it cannot play

The movie section SHALL say, in words, why it cannot offer or play a movie, by cause. It SHALL never leave the
operator with a silent or black player and nothing said. It SHALL never show a fact it did not receive.

**When the movie cannot be fetched.** These answers to the one-byte request SHALL replace the player:
- **404:** the service has no movie file for the event (for example, something other than a file now lies where
  the movie belongs), with the service's detail.
- **502:** the movie could not be read, with the service's detail and the failure kind in words when the answer
  carries one. A movie file that cannot be read is named by its file name, never a server path.
- **416:** the movie file is empty.
- **No answer, or an answer the route does not publish:** the same words the event page uses for its own read.

These notes are part of the page's content and SHALL NOT be announced as alerts. The same holds when a re-read the
page starts by itself gets one of these answers. Focus is never dropped:
- Whenever a note replaces a player that had keyboard focus, the note SHALL receive it.
- Whenever a player replaces a note that had keyboard focus, the new player SHALL receive it.
- When a re-read finds that the event no longer has a rendered movie, and the section that disappears held keyboard
  focus, the page's heading SHALL receive it.

**When playback fails.** After the operator starts playback:
- **No picture.** When the browser has loaded the movie but reports no picture size, it plays the sound of a
  movie whose picture it cannot show, such as a legacy MPEG-4 movie adopted with `auto-reel adopt-renders`, and it
  raises no error. The section SHALL say that this browser cannot show the movie's picture and plays its sound
  only. It SHALL offer to download the movie, and the player SHALL stay.
- **A playback error.** The page SHALL ask the service for the first byte of the movie again, and answer by cause:
  - The entity-tag differs from the one the player loaded: the section SHALL say that the movie file changed while
    it played, and offer "Load the new movie". That control SHALL replace the player with one at the new address,
    without starting playback, and SHALL give it keyboard focus.
  - The entity-tag is the same: the section SHALL say that this browser could not play the movie, with the
    browser's error in words. When the browser reports a network error, it SHALL say instead that the movie could
    not be loaded, with that error in words, never that the browser cannot play it. Either way it SHALL offer to
    download the movie, and "Try again", which SHALL replace the player with a new one at the same address,
    without starting playback, and SHALL give it keyboard focus.
  - Any other answer: the note for that answer, as when the movie cannot be fetched, in place of the player.

These notes follow the operator's action, so each SHALL be announced once, when it appears: a failure assertively,
and the no-picture warning politely, through a region that exists before its words. Downloading SHALL
save the file under its own name. A control in these notes SHALL be reachable from the keyboard, and under a
coarse pointer SHALL take a tap anywhere in an area of at least 44 × 44 CSS pixels around it.

#### Scenario: Something other than a file where the movie belongs
- **WHEN** `2024-07-14 - Kalas`'s movie file is replaced on disk by a folder of the same name, so its staleness still
  cites no reason, and the operator opens its page
- **THEN** the "Movie" section says that the service has no movie file for this event, with the service's detail,
  shows no player, and no alert is announced

#### Scenario: A movie the service cannot read
- **WHEN** `2024-07-14 - Kalas`'s movie file cannot be read for lack of permission, and the operator opens its page
- **THEN** the "Movie" section says the movie could not be read, with a detail that names
  `2024-07-14 - Kalas.mp4` and the reason, contains no absolute path, and shows no player

#### Scenario: The service does not answer
- **WHEN** the one-byte request for `2024-07-14 - Kalas`'s movie gets no answer
- **THEN** the "Movie" section says the service is not reachable, with what to do, and shows no player

#### Scenario: A legacy movie plays its sound only
- **WHEN** an event's movie is a legacy MPEG-4 Part 2 file adopted with `auto-reel adopt-renders`, and the operator
  plays it in Chrome
- **THEN** the section says that this browser cannot show the movie's picture and plays its sound only, the player
  stays, and the offered download saves the file under its own name

#### Scenario: The movie file changes while it plays
- **WHEN** the operator plays a movie in Chrome, its file is replaced on disk by another movie, and the operator
  seeks past what was loaded, so the browser reports a playback error
- **THEN** the section says that the movie file changed while it played and offers "Load the new movie"
- **AND** activating it from the keyboard shows a paused player at the new file's address, with keyboard focus, and
  that player plays the new file

#### Scenario: Try again after a playback error
- **WHEN** the operator plays the movie of `2024-07-14 - Kalas` and the browser's requests for the movie fail while
  the one-byte request still answers with the same entity-tag
- **THEN** the section says that this browser could not play the movie, with the browser's error, and offers
  "Try again" and "Download the movie"
- **AND** once the requests answer again, activating "Try again" from the keyboard shows a paused player at the same
  address, with keyboard focus, and that player plays the movie

#### Scenario: A player that replaces a focused note takes the focus
- **WHEN** the movie file of `2024-06-27 - Grillning med grannar` cannot be read when the operator plays it from
  the keyboard, so a note replaces the player and receives keyboard focus, and the file is readable again when a
  forced render of the event, queued from elsewhere and cancelled, makes the page read the event again
- **THEN** a player replaces the note, and keyboard focus is on the new player

#### Scenario: Notes stay inside a phone-width window
- **WHEN** the section shows any of these notes in a window 320 pixels wide
- **THEN** the page does not scroll horizontally, and the note's words and detail wrap inside the section

### Requirement: Edit mode previews a clip on request

In Edit mode, the Cuts panel of every clip that offers one (an included or new clip on disk) SHALL offer a
**Watch** control as the panel's first control. Pressing it SHALL open the clip's preview, a player for the
clip, in the panel, above the clip's cuts, and pressing it while the preview is open SHALL close it. The
control SHALL be named "Watch <name>", where <name> is the clip's name as its row names it, and SHALL say to
assistive technology whether the preview is open. While the preview is open, the control SHALL show that a press
closes it: its words SHALL be "Hide player", and its name "Hide player of <name>". The preview SHALL be a region
named "Player for <name>".

**From the row.** In Edit mode, the thumbnail of every clip that offers a Cuts panel SHALL also be a button
named "Watch <name>" that opens the same preview in one press. Pressing it SHALL show the clip's Cuts panel
when it is hidden, open the preview there, closing any other, and move keyboard focus to the preview's Play.
Pressing it while the preview is open SHALL keep the preview open and move keyboard focus to its Play. The
thumbnail SHALL keep its box, its size and its place in the row: being a button changes no row's size or
position. It SHALL NOT start a drag: the drag handle stays a control of its own, and a clip moves only by its handle or
its move buttons. A thumbnail that could not be shown (its "No preview" box) SHALL open the preview all the
same.

**What it plays.** The preview SHALL play the clip's preview copy when the clip has a ready one, and the clip's
own file, the original, otherwise, as "A clip's preview plays its preview copy when one is ready" requires. The
original is the file the service serves from `GET /api/v1/events/{event_id}/media?clip=<identity>`. The event id
and the clip's full identity SHALL be sent exactly as the event detail gives them, and the clip's modification
time, exactly as the event detail gives it, as `v`. Until it plays, the preview SHALL show the clip's thumbnail. It SHALL NOT start playing by
itself. A preview opened with Watch, from the panel or the thumbnail, SHALL stand at the clip's start, also
after an earlier preview of the clip was closed elsewhere in it. A clip displayed in portrait, such as a phone
clip whose container rotates it, SHALL be shown whole, turned as a player shows it. Unless a scenario of this
requirement says that its clip has a ready preview copy, it SHALL be read for a clip that has none.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media or its preview copy, and
SHALL NOT create a video element for either, before the operator opens that clip's preview. This SHALL hold for any number of clips,
for Cuts panels that are shown, and on entering, scrolling and leaving Edit mode. Closing a preview SHALL
stop its playback and any loading of its file.

**One at a time.** Opening a preview SHALL close any other clip's preview, so that Edit mode never holds more
than one video element. Edit mode SHALL show no movie player: the event's "Movie" section belongs to the read
view, which Edit mode replaces.

**Keyboard and focus.** Opening a preview SHALL move keyboard focus to its Play control. The preview's
controls SHALL come in this keyboard order, each reachable and usable by keyboard alone:
1. **Close**, named "Close the player of <name>"
2. **Play** / **Pause**, which says which it does
3. the **playhead**, a slider over the clip's length
4. **Skip cuts**
5. **Set From**
6. **Set To**
7. **Play original** or **Play preview copy**, present only while the clip has a ready preview copy

Each control SHALL name the clip as its row names it. Close, and Escape pressed while keyboard focus is in the
preview, SHALL close the preview and move keyboard focus to the control that opened it: the Watch control, or
the clip's thumbnail. Hiding the Cuts panel SHALL close its preview, leaving keyboard focus on the Cuts
control. No control of a closed preview SHALL keep focus.

**Play** SHALL be usable from the moment the preview opens. Pressed before the browser has read the clip, it
SHALL play the clip once the browser can. A preview opened with Watch, its thumbnail or Try again SHALL announce,
once, that the clip is ready to play, with its length.

**The playhead.**
- Space on it SHALL play or pause the clip, as Play does, and SHALL NOT scroll the page.
- It SHALL take the Left and Down arrows to step back 0.1 seconds and the Right and Up arrows to step on 0.1
  seconds. Page Down and Page Up SHALL step one second, and Home and End SHALL go to the clip's start and
  end. Each step SHALL stay within the clip.
- A press or a drag along it SHALL move to the time under the pointer.
- It SHALL say its value to assistive technology as the time and the clip's length, in the format the Cuts
  panel writes times (`0:01.234 of 0:06.02`), and SHALL add when the time lies inside a cut. While the clip
  plays, the value it says SHALL change at most once a second.
- Until the preview has read the clip's length, the playhead, Set From and Set To SHALL say that they are
  unavailable and change nothing.

The preview SHALL show the playhead's time and the clip's length as a readout that says what it is and keeps its
width, as "Running times are written to a fixed width and say what they are" requires (`Clip 0:01.23 of 0:06.02`).
The slider's value text stays in the Cuts panel's format, above.

**Sizes and look.**
- The picture SHALL be shown whole in a box of fixed 16:9 proportions, as wide as the panel allows up to 640
  CSS pixels and never taller than 360. The box SHALL have that size before the clip's file is read, so that
  nothing on the page moves when it is.
- In a window 320 pixels wide or more, the preview SHALL NOT make the page scroll horizontally.
- When the primary pointer is coarse, each of its controls SHALL take a tap anywhere in an area of at least
  44 × 44 CSS pixels around it, reaching no other control. The playhead SHALL take a tap across its whole
  width in an area at least 44 pixels tall.
- It SHALL follow the page's color scheme in both schemes. No state of it SHALL be shown by color alone.
- It SHALL animate nothing. The playhead moves only with playback or a seek.

**What the browser cannot do, by cause.** Each of these SHALL be shown in the preview as a note, never as an
alert, and announced once through Edit mode's live region. Keyboard focus SHALL stay in the preview, on
Close when the control that held it went:
- **No sound.** When the original plays and the browser reports that it finds no audio it can play in the clip, the preview SHALL say
  that this browser finds no sound it can play in the clip, and that if a Sony camera recorded it, its sound
  is PCM, which Firefox does not play and Chrome does, and the render keeps it. The note SHALL NOT state as
  fact a cause or a sound the page does not know of: the clip may have no audio track at all. Playback SHALL
  be otherwise unchanged, never muted. The note SHALL NOT be shown while the preview copy plays. When the clip
  has a ready preview copy whose facts name an audio codec, the note SHALL add that the preview copy plays with
  sound and that Play preview copy plays it; when the facts name none (the clip has no audio), the note SHALL stay
  as it is and SHALL NOT promise sound from the copy.
- **No picture.** When the browser reads the clip but shows no picture of it, the preview SHALL say that this
  browser cannot show the clip's picture, and SHALL offer the clip's file as a download. Its controls SHALL
  stay.
- **It cannot play the clip.** (This is the original's. The preview copy's failures are the ones "A clip's
  preview plays its preview copy when one is ready" lists.) When the browser refuses the original, the page SHALL ask the service for the
  clip's first byte, once, to tell why. It SHALL then say:
  - that the clip is no longer on disk, with the service's detail, when the service answers that it is not a
    clip of the event
  - that the clip changed on disk since the page was read, when the service serves a file whose modification
    time differs from the one the event detail gave
  - in both of these cases, the advice to stop editing (saving first to keep the edits), so that the event is
    read again, and then to open the player again. The page SHALL NOT call this a refresh: in Edit mode the
    page's Refresh leaves Edit mode. The edits SHALL stay untouched until the operator acts.
  - that the clip's file is empty, when the service answers that the file has no first byte
  - that the clip could not be read, with the failure kind's words and the service's detail, when the service
    answers that it cannot read it
  - that this browser cannot play the clip's format, offering the file as a download, when the service serves
    it
  - that the service gave no usable answer, saying which, with a Try again that opens the preview anew, when it
    gives none. Try again SHALL move keyboard focus to the reopened preview's Play.

  A failure SHALL NOT be retried by itself.

**Within Edit mode.**
- Opening, closing, playing and seeking a preview SHALL write nothing and SHALL NOT count as an edit. They
  SHALL bring no save bar and SHALL NOT trigger the unsaved-changes question.
- While a save is in flight or a move of marked clips is pending, Set From and Set To SHALL say that they are unavailable
  and change nothing. Play, the playhead, Skip cuts and Close SHALL stay usable.
- A clip moved within its chapter SHALL keep its preview, playing or not.
- A clip moved into another chapter, by a drag or by Move marked to…, SHALL keep its preview open at the same time,
  paused. The reopened preview SHALL take no keyboard focus and SHALL NOT scroll the page. After a drop,
  keyboard focus is on the clip's handle, and the handle and the row's first line are fully visible, as
  "Edit mode drags clips between chapters" requires; a row made taller than the view by its preview is
  scrolled so that its first line is, and the preview under it may lie partly outside the view.
- Reset SHALL close every preview. Leaving Edit mode SHALL close it.

#### Scenario: Nothing loads until a preview is opened
- **WHEN** the operator opens Edit mode on `2024-09-15 - Stor dag`, whose root chapter plays 400 clips, scrolls
  to its end, and shows the Cuts panels of `c0001.mp4`, `c0200.mp4` and `c0400.mp4`
- **THEN** the page holds no video element and has made no media request
- **WHEN** the operator presses Watch in the panel of `c0400.mp4`
- **THEN** its preview opens with keyboard focus on "Play c0400.mp4", nothing plays, and every media request
  names `c0400.mp4` and carries its modification time as `v`

#### Scenario: Playing and seeking from the keyboard
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, using only the keyboard, the operator shows the
  Cuts panel of `s1710001.mp4`, presses Watch and then Space
- **THEN** the clip plays, and the control with focus is now named "Pause s1710001.mp4"
- **WHEN** the operator presses Space again, moves to the playhead, and presses Home, then Right three times
- **THEN** the clip is paused, and the playhead says `0:00.3 of 0:06.02` in a browser that reads the clip's
  length as 6.02 seconds
- **WHEN** the operator presses End, then Page Down
- **THEN** the playhead says `0:05.02 of 0:06.02`
- **WHEN** the operator presses Space on the playhead
- **THEN** the clip plays and the page does not scroll; Space again pauses it

#### Scenario: Opening another preview closes the first
- **WHEN** the preview of `s1710001.mp4` of `2024-06-27 - Grillning med grannar` is playing, and the operator
  shows the Cuts panel of `s1710002.mp4` and presses its Watch
- **THEN** the preview of `s1710001.mp4` is closed, its Watch control says that it is not open, and its file
  is no longer loading. The preview of `s1710002.mp4` is open, with keyboard focus on its Play.

#### Scenario: Closing gives focus back
- **WHEN** keyboard focus is on the playhead of an open preview and the operator presses Escape
- **THEN** the preview closes, and keyboard focus is on that clip's Watch control
- **WHEN** the operator opens it again and presses Close
- **THEN** the preview closes, and keyboard focus is on the Watch control again
- **WHEN** the operator opens it again and presses the clip's Cuts control
- **THEN** the panel and the preview are hidden, and keyboard focus stays on the Cuts control

#### Scenario: Watching from the row in one press
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, with every Cuts panel hidden, the operator tabs
  to the thumbnail of `s1710002.mp4`, which is named "Watch s1710002.mp4", and presses Enter
- **THEN** the clip's Cuts panel is shown with its preview open, keyboard focus is on "Play s1710002.mp4",
  nothing plays, and no other row changed its size; the rows above it did not move, and the rows after it
  moved down only by the height that the opened panel added to its row
- **WHEN** the operator presses Escape
- **THEN** the preview closes, its panel stays shown, and keyboard focus is on the thumbnail of `s1710002.mp4`
- **WHEN** the operator presses the thumbnail of `s1710001.mp4` with the pointer
- **THEN** the preview of `s1710001.mp4` opens, the one of `s1710002.mp4` is closed, and no drag starts: every
  clip keeps its place
- **WHEN** in Edit mode on `2024-10-05 - Trasig`, whose thumbnail shows "No preview", the operator presses the
  thumbnail of `trasig.mp4`
- **THEN** its preview opens and says that the clip's file is empty

#### Scenario: A portrait clip is shown whole
- **WHEN** the event `2024-05-19 - Provklipp` holds `h264-720p-rotate90-aac.mp4`, a 1280×720 clip that its
  container turns to portrait, and the operator opens its preview and plays it
- **THEN** the picture is taller than wide and wholly inside the preview's 16:9 box, with empty bands at its
  sides. The box is as large as the box of a landscape clip in the same panel would be.

#### Scenario: No sound for a Sony clip in Firefox
- **WHEN** in Firefox, which plays no PCM audio, the operator opens the preview of `sony-xavc-1080p25-pcm.mp4`
  of `2024-05-19 - Provklipp`, whose preview copy is not ready
- **THEN** the preview says that this browser finds no sound it can play in the clip, and that if a Sony
  camera recorded it, its sound is PCM, which Chrome plays and the render keeps. The note is announced once,
  and the clip plays its picture on request, not muted.
- **WHEN** the same preview is opened in Chrome
- **THEN** no such note is shown
- **WHEN** in Firefox, the operator opens the preview of a clip with no audio track whose preview copy is ready
  and whose facts name no audio codec
- **THEN** the note is shown without the sentence that the preview copy plays with sound

#### Scenario: A picture this browser cannot show
- **WHEN** in Chrome, the operator opens the preview of the HEVC clip `hevc-mov-rotate90-aac.mov` of
  `2024-05-19 - Provklipp`
- **THEN** the preview says that this browser cannot show the clip's picture and offers the clip as a
  download, and its controls stay
- **WHEN** in Firefox, which refuses that clip, the operator opens the same preview
- **THEN** the preview says that this browser cannot play the clip's format and offers the clip as a download

#### Scenario: An empty clip says so
- **WHEN** in Edit mode on `2024-10-05 - Trasig`, whose only clip `trasig.mp4` is an empty file, the operator
  opens its preview
- **THEN** the preview says that the clip's file is empty and that there is nothing to play. The page shows no
  alert, the words are announced once, and keyboard focus is in the preview.

#### Scenario: Try again opens the preview anew
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the service gives no answer when the operator
  opens the preview of `s1710001.mp4`, and then answers again
- **THEN** the preview says that the service is not reachable and offers Try again
- **WHEN** the operator presses Try again
- **THEN** the preview opens anew, ready to play, with keyboard focus on "Play s1710001.mp4", and Escape closes
  it

#### Scenario: A clip removed from disk since the page was read
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, `s1710004.mp4` is deleted from disk and the
  operator then opens its preview
- **THEN** the preview says that the clip is no longer on disk and advises stopping editing, saving first to
  keep the edits, to read the event again, and offers no download

#### Scenario: A clip changed on disk since the page was read
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, after the page was read, `s1710002.mp4` is
  replaced on disk by a file of the same name that no browser can play, and the operator opens its preview
- **THEN** the preview says that the clip changed on disk since the page was read and advises stopping editing,
  saving first to keep the edits, to read the event again, rather than blaming the clip's format. It offers no
  download, and the edits are as they were

#### Scenario: The preview follows its clip
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the preview of `s1710001.mp4` is paused at
  `0:02.5`, and the operator drags that clip into `Kvällen`
- **THEN** in `Kvällen`, the clip's Cuts panel is shown with its preview open, paused, at `0:02.5`
- **AND** keyboard focus is on the clip's handle, and the handle and the row's first line lie fully between the
  bottom of the page header or the chapter's heading and the top of the save bar, also in a window 390 × 844
  pixels
- **WHEN** the preview of `Kvällen/s1710002.mp4` is playing and the operator presses that clip's Move down
- **THEN** it keeps playing

#### Scenario: A pending save leaves playback alone
- **WHEN** on `2024-06-27 - Grillning med grannar`, with a cut added to `s1710001.mp4` and its preview open, the
  operator presses Save and the service has not answered yet
- **THEN** Set From and Set To say that they are unavailable, and pressing them changes no field, while Play,
  the playhead and Close still work and keyboard focus stays on Save

#### Scenario: Previewing is not an edit
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator opens the preview of
  `s1710002.mp4`, plays it, seeks it and closes it, and then presses the browser's Back
- **THEN** no save bar is shown at any time, and the page goes back to the event list without asking about
  unsaved changes

#### Scenario: Reset closes the preview
- **WHEN** on `2024-06-27 - Grillning med grannar`, with the title changed and the preview of `s1710001.mp4`
  open, the operator presses Reset
- **THEN** the preview is closed and its panel is hidden, and the page holds no video element

#### Scenario: A preview on a phone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide, and the
  operator opens the preview of `Kvällen/s1710002.mp4`
- **THEN** the page does not scroll horizontally, and the picture's box is 16:9 inside the panel. A tap anywhere
  in a 44 × 44 pixel area around Close, Play, Skip cuts, Set From and Set To reaches that control and no other.
  A tap anywhere along the playhead, up to 22 pixels above or below its centre line, moves it.

#### Scenario: The player's time says what it is and does not move
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar` the operator opens the preview of `s1710001.mp4`
  (6.02 s) and plays it to the end
- **THEN** the header reads `Clip 0:00.00 of 0:06.02`, then `Clip 0:01.50 of 0:06.02`, and `Clip 0:06.02 of 0:06.02`
  at the end; the readout's bounding box has the same width in every sample taken during the playthrough, and the
  close button does not move

### Requirement: A clip's preview sets cut times at the playhead and plays the clip as the movie will

**The cut bar.** Under the picture, the preview SHALL show a bar along the clip's length. It SHALL show:
- every cut the clip's panel lists that is not removed, read and added alike
- each cut that is removed until the save, drawn differently
- while the panel's fields hold a start and an end that the panel would accept as a cut, that typed span,
  drawn differently again
- the playhead

Each kind SHALL differ by its shape, not by its color alone, and a legend SHALL name each kind the bar shows.
A cut that runs past the clip's end SHALL be drawn up to that end. The bar SHALL follow every change to the
panel's cuts and fields at once.

**Set From and Set To.**
- **Set From** SHALL write the playhead's time into the panel's start field, and **Set To** into its end field.
  The playhead's time is the time of the file that plays, the original or its preview copy, which are the same.
- The time SHALL be written to the millisecond, in the format the panel writes times (`0:01.234`, `0:02.5`).
  The panel SHALL read it back as that same time.
- Keyboard focus SHALL stay on the pressed control, and the new value SHALL be announced.
- Neither SHALL add a cut. The written time SHALL count as a cut typed but not added: the clip's Cuts control
  SHALL say "typed", and the save bar SHALL hold Save back until the cut is added or its fields cleared, as for
  any typed time.

**Skip cuts** SHALL be a control that says whether it is on, and it SHALL start off.
- While it is on, playback SHALL show no frame that lies wholly inside a cut the panel lists that is not
  removed. Cuts are joined as the render joins them, overlapping or touching ones as one.
- Playback reaching a cut SHALL continue at the cut's end, jumping over each cut once, also when the cut ends
  between two frames. Playback SHALL never stall at a cut.
- A cut that runs to the clip's end, or that ends less than 0.1 seconds before the end the browser reads,
  SHALL stop playback, paused, at that cut's start. Browsers read a clip's length up to 60 ms longer than the
  render does, so a cut that ends where the render's clip ends counts as running to the end.
- Play pressed while the playhead is inside a cut SHALL start at that cut's end. When no footage follows it,
  or when the playhead is at the clip's end, Play SHALL start at the first footage of the clip outside every
  cut. When the cuts cover the whole clip, Play SHALL play nothing and SHALL say that the cuts cover the whole
  clip.
- While it is off, playback SHALL show every moment of the clip.
- In either state, moving the playhead into a cut while the clip is paused SHALL show that moment, so that a
  time can be set from inside a cut.

**The clip's length.** The page SHALL take a clip's length from its preview when the preview has read it, else
from the duration the event detail gives the clip when that is not null, and from nowhere else. The preview reads
it from the file that plays: as the browser reads it from the original's file, or, while the clip's preview copy
plays, as the duration in the copy's facts, which is the original's duration as the engine probed it ("A clip's
preview plays its preview copy when one is ready"). The preview's length SHALL win over the detail's whenever
both exist, because Set From and Set To write times in it, and a browser can read up to 60 ms more than the
probe's duration. A detail duration of `null` SHALL be treated as unknown, never as zero.
- Once it has the length, the clip's panel SHALL say where the clip ends beside its fields (`This clip ends at
  0:06.02`).
- The panel SHALL refuse a cut that ends after the clip's length, compared to the millisecond as the panel
  writes times. The refusal SHALL be at the end field, or at the start field when the start lies at or after
  the length, since no end could then fix it. It SHALL name the cut's time and the clip's length. A cut that
  ends exactly at the length SHALL be accepted.
- Each cut the panel lists that ends after the length SHALL be marked as running past the clip's end. Nothing
  SHALL refuse it, and its Undo SHALL NOT be refused for it.
- The page SHALL keep the length the preview read for the clip while Edit mode stays open: after the preview
  closes, after another opens, and after the clip moves to another chapter. It SHALL forget it when the
  clip's modification time changes, and when Edit mode closes. The detail's duration belongs to the clip's
  current file, so a replaced file's old duration SHALL NOT be used: the next detail gives the new one, or
  `null`.
- When the browser reads a different length for the original while it plays, the panel SHALL use the latest.
  What the browser reads from a preview copy SHALL NOT change the length.
- Neither length SHALL be saved, sent to the service or shown anywhere outside Edit mode.

#### Scenario: The bar shows the clip's cuts
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710003.mp4` a cut from 0 to 1.2
  seconds with the reason `black`, and in Edit mode the operator opens that clip's preview, adds a cut from
  `3` to `4` and removes the read cut
- **THEN** the bar shows the cut from 3 to 4 seconds as a cut and the span from 0 to 1.2 seconds as removed,
  each drawn differently, and the legend names a cut and a cut removed when you save

#### Scenario: Setting a cut at the playhead
- **WHEN** in the preview of `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, with the playhead at
  `0:01.2`, the operator presses Set From
- **THEN** the start field holds `0:01.2`, keyboard focus is on Set From, "From set to 0:01.2" is announced, the
  clip's Cuts control says "typed", and the save bar says that a cut was typed on `s1710001.mp4` but not added
- **WHEN** the operator moves the playhead to `0:02.5`, presses Set To, and then presses Add cut
- **THEN** the bar showed the typed span from 1.2 to 2.5 seconds before the addition. The panel then lists the
  cut from `0:01.2` to `0:02.5`, the Cuts control reads "1 cut · −1.3 s", and the save bar says that 1 cut was
  added.

#### Scenario: A time set while playing is written to the millisecond
- **WHEN** the preview of `s1710001.mp4` plays and the operator presses Set From while it plays
- **THEN** the start field holds the playhead's time at that moment, rounded to the millisecond and written
  without a trailing zero, such as `0:02.607`, and the panel accepts it

#### Scenario: Skipping cuts while playing
- **WHEN** `s1710002.mp4` of `2024-06-27 - Grillning med grannar` has a cut from `1` to `2`, and the operator
  turns Skip cuts on, moves the playhead to `0:00.5` and plays the clip
- **THEN** no frame between 1 and 2 seconds is shown, and playback continues from 2 seconds
- **WHEN** the operator turns Skip cuts off and plays the clip again from `0:00.5`
- **THEN** the frames between 1 and 2 seconds are shown

#### Scenario: A cut that ends between two frames is jumped over once
- **WHEN** `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, a 50 fps clip, has a cut from `1` to
  `2.01`, which ends between its frames at 2 and 2.02 seconds, and the operator turns Skip cuts on and plays
  the clip from `0:00.5`
- **THEN** playback goes on past 2.5 seconds within a second of reaching the cut, the cut is jumped over once,
  and no frame that lies wholly between 1 and 2.01 seconds is shown

#### Scenario: A cut to the clip's end ends playback
- **WHEN** `s1710002.mp4` also has a cut from `5` to `0:06.02`, where ffprobe and the render end the clip,
  Skip cuts is on, and the operator plays the clip from `0:04.5`, in Chrome, which reads the clip's length as
  6.02 seconds, and again in Firefox, which reads it as 6.08 seconds
- **THEN** in each, playback stops at 5 seconds, paused, with no frame after 5 seconds shown
- **WHEN** the operator presses Play again
- **THEN** playback starts from the clip's start

#### Scenario: Cuts over the whole clip leave nothing to play
- **WHEN** `s1710001.mp4` has one cut from `0` to its end (`0:06.02`, in a browser that reads that length),
  Skip cuts is on, and the operator presses Play
- **THEN** nothing plays, and the page says that the cuts cover the whole clip

#### Scenario: A cut past the clip's end is refused once its length is known
- **WHEN** in a browser that reads its length as 6.02 seconds, the operator opens the preview of
  `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, closes it, and adds a cut from `5` to `7`
- **THEN** the panel says that the clip ends at `0:06.02`. The cut is refused at the end field, which receives
  keyboard focus, saying that `0:07` is after the clip's end at `0:06.02`. No cut is added.
- **WHEN** the operator types `0:06.02` as the end and adds the cut
- **THEN** the cut from `0:05` to `0:06.02` is listed
- **WHEN** the operator adds a cut from `7` to `8` on the same clip, and then one from `0:06.02` to `7`
- **THEN** each is refused at the start field, saying that its start is at or after the clip's end

#### Scenario: A listed cut past the end is marked, not refused
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` a cut from 3723.125 to
  3725.5 seconds, and the operator opens that clip's preview
- **THEN** the cut is listed as running past the clip's end and is not drawn on the bar beyond it. Removing it
  and pressing its Undo is not refused.

#### Scenario: The length stays with the clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens and closes the preview of `s1710001.mp4`,
  marks that clip and moves it to `Kvällen` with
  Move marked to…, and adds a cut from `5` to `7` on it there
- **THEN** the cut is refused for ending after the clip's length

#### Scenario: The preview's length wins over the service's duration
- **WHEN** the detail gives `s1710001.mp4` of `2024-06-27 - Grillning med grannar` a duration of `6.02`, and in
  Firefox, which reads its length as 6.08 seconds, the operator opens the preview, presses Set To at the end of
  the clip and adds the cut from `5`
- **THEN** the panel says that the clip ends at `0:06.08`, and the cut from `0:05` to `0:06.08` is listed, not
  refused

#### Scenario: A listed cut past the end is marked from the service's duration
- **WHEN** the `reel.yaml` of `2024-06-27 - Grillning med grannar` gives `s1710002.mp4` a cut from 3723.125 to
  3725.5 seconds, the detail gives that clip a duration of `6.02`, and no preview was opened
- **THEN** the cut is listed as running past the clip's end, and removing it and pressing its Undo is not
  refused

#### Scenario: Cutting to the original's end while its preview copy plays
- **WHEN** the detail gives `s1710001.mp4` of `2024-06-27 - Grillning med grannar` a ready preview copy whose
  facts say `6.02` seconds, the browser reads the copy as 6.0 seconds, and the operator opens the preview, plays
  the copy, and adds a cut from `5` to `0:06.02`
- **THEN** the panel says that the clip ends at `0:06.02` and lists the cut, not refused

### Requirement: A cancel or a job read that meets a database outage says so
When the service answers a cancel request with a 503 whose problem body names the database as the failing
dependency, the page SHALL say that the cancel was not confirmed because the service can't reach its
database, with the service's detail. It SHALL NOT say that the job does not exist, that the cancel
succeeded, or show an outcome, and the job SHALL keep the state the page showed. It SHALL use the same
sentence for the database that the event list and the event page use for a failed read. A 503 that does not
name the database stays an unexpected answer, worded with the status it received.

The event list's row Render, whose answers are handled as the page's, SHALL tell a database outage in an
error notification that names the pressed event, says the render was not queued because the service can't
reach its database, and carries no link, since the failure is not about the event.

A read of one job (the background read that keeps a followed job current) that meets the same 503 SHALL show
nothing and SHALL keep the last job state the page knew: it MUST NOT drop the job as it does for a 404, and
MUST NOT raise a notification for a read the operator did not ask for.

The client SHALL tell these answers by the published status and the typed field naming the failing
dependency, defined as a case of the jobs request results, so that the client's type-check fails when a
caller does not handle it.

#### Scenario: The cancel is not confirmed because the database is down
- **WHEN** the operator presses Cancel on `2024/Blandat`'s queued job and the service answers 503 naming
  the database
- **THEN** the page says the cancel was not confirmed because the service can't reach its database, shows
  the service's detail, still shows the job as queued, and does not say the job no longer exists

#### Scenario: A row's Render meets the outage
- **WHEN** the operator presses Render on the `2024-08-20 - Två kapitel - Tjörn` row and the service answers
  503 naming the database
- **THEN** one error notification names that event by its title and date, says the render was not queued
  because the service can't reach its database, and has no link; the row offers Render again

#### Scenario: A background job read meets the outage
- **WHEN** the page follows the `running` job of `2024-06-27 - Grillning med grannar`, and a read of that
  job is answered 503 naming the database
- **THEN** the page keeps showing the job as it last knew it, shows no notification for that read, and does
  not report the job as gone

#### Scenario: A 503 that does not name the database is not worded as one
- **WHEN** the operator presses Cancel on `2024/Blandat`'s queued job and the service answers 503 without
  naming the database
- **THEN** the page says the cancel was not confirmed, with the status it received, and does not say that the
  service can't reach its database

### Requirement: A full stack of notifications never loses an error to a lesser one

The page SHALL hold at most three notifications. When a fourth arrives:

- if a success or info notification is held, the oldest of those SHALL be removed to make room, whatever the
  tone of the new one;
- if all three held are errors and the new one is an error, the oldest error SHALL be removed;
- if all three held are errors and the new one is a success or info, the new one SHALL NOT be shown, and no
  held error SHALL be removed or change.

A notification that is not shown SHALL leave no trace: nothing is announced, and no later notification is
affected by it.

#### Scenario: Three unread errors and an info notification
- **WHEN** on the event list, three error notifications are shown (three Render presses on
  `2024-07-14 - kalas`, each answered with the output-collision error, or three failed re-reads), and then a
  queued render of another event is canceled, which raises the info notification “Render canceled”
- **THEN** the three errors are still shown, in the same order, the info notification is not shown, and
  nothing is announced for it

#### Scenario: An error replaces the oldest of three errors
- **WHEN** three error notifications are shown and a fourth error arrives
- **THEN** the oldest is removed and the other two and the new one are shown

#### Scenario: A success makes room before an error is touched
- **WHEN** two errors and one success notification are shown and an info notification arrives
- **THEN** the success notification is removed, and both errors and the info notification are shown

### Requirement: A notification raised under a dialog is shown above it

While a modal dialog is open, a notification that is shown SHALL be visible above the dialog and its
backdrop: an error notification SHALL be fully readable there at any window width from 320 CSS pixels up.
It MAY not take focus or clicks until the dialog closes. Opening a dialog while notifications are already
shown SHALL leave them visible above it.

While a modal dialog is open, the clock that dismisses a success or info notification by itself SHALL be
stopped, so that none disappears before the operator can see it. When the last open dialog closes, each such
clock SHALL continue with the time it had left. An error notification stays until it is dismissed, as always.

#### Scenario: A render ends while Render anyway is open
- **WHEN** on `2023-06-23 - Midsommar - Dalarna`, which is up to date, the operator presses Render anyway, and
  while the dialog "Render anyway?" is open a render of `2024-08-20 - Två kapitel - Tjörn` fails
- **THEN** the error notification naming "Två kapitel" is visible above the dialog and its backdrop, in
  windows 1280 and 390 pixels wide, in the light and the dark theme, and still shown after the dialog is
  closed with Escape

#### Scenario: A success notification does not run out under a dialog
- **WHEN** a render of another event ends while the "Render anyway?" dialog is open, which raises the success
  notification “Rendered …”, and the operator waits more than 5 seconds before pressing Cancel
- **THEN** the notification was visible above the dialog throughout, and it is still shown when the dialog
  closes
- **AND** it disappears by itself about 5 seconds after the dialog closed

#### Scenario: A notification already shown when the dialog opens
- **WHEN** an error notification is shown on the event page and the operator then opens the Add chapter
  dialog
- **THEN** the error notification is still visible above the dialog

### Requirement: A closing dialog does not take focus from where the operator moved it

Closing a dialog SHALL return keyboard focus to the control that had it when the dialog opened, as long as
that control is still in the page and focus is still the dialog's: inside it, or on no control. When focus has
meanwhile moved to a control outside the dialog, closing the dialog SHALL leave it there.

#### Scenario: Escape returns focus to the opener
- **WHEN** the operator opens "Render anyway?" with the keyboard from the Render anyway button and presses
  Escape
- **THEN** the dialog is closed and keyboard focus is on Render anyway

#### Scenario: Cancel returns focus to the opener
- **WHEN** the operator opens "Render anyway?" with the keyboard and presses Cancel
- **THEN** the dialog is closed and keyboard focus is on Render anyway

#### Scenario: Focus moved before the dialog finished closing
- **WHEN** the operator closes the dialog with Escape and, in the same task as the dialog's close event (as
  a script listening to that event does), keyboard focus is moved to another control outside the dialog, such
  as Save
- **THEN** keyboard focus stays on that control and is not moved back to the control that opened the dialog

### Requirement: A clip that reel.yaml excludes is marked as excluded

A clip that `reel.yaml` excludes (`clips.<identity>.exclude: true`) is listed in its chapter and kept in the
document, but a render drops it from the movie. The event page and Edit mode SHALL say so for every such clip,
whatever its status, from the clip's `excluded` flag in the event read:

- Its row SHALL carry an **Excluded** status label, in words and with an icon of its own, never by color alone.
  The label SHALL be a status label like New and Missing, with the fill and edge those have.
- An excluded clip on disk SHALL show the Excluded label in place of the quiet word "Included", since the
  clip is not included in the movie. An excluded missing clip SHALL show both its Missing label and the
  Excluded label.
- The clip keeps its place and its position number in its chapter's list, as `reel.yaml` has it, on the
  event page and in Edit mode alike, so that the two screens number the same rows. Moving, dragging and
  removing a missing clip work on it as on any other.
- The clip counts of the facts line SHALL give the number of excluded clips ("1 excluded") when it is
  non-zero. The excluded clips stay among the clips counted, as the new and missing ones do.
- Its row SHALL show no cuts and offer none ("Edit mode lists, adds and removes a clip's cuts").

The client SHALL take the mark from the event read's `excluded` flag. It MUST NOT infer exclusion from the
editorial document read for Edit mode, so that both screens show the one fact the service reports.

#### Scenario: An excluded clip is marked on the event page
- **WHEN** the operator opens an event whose `reel.yaml` lists `s1710001.mp4`, `s1710002.mp4` and
  `s1710003.mp4` in one chapter and excludes `s1710002.mp4`
- **THEN** the chapter's table lists the three clips at positions 1, 2 and 3, `s1710002.mp4` with the
  Excluded label and the other two as "Included", and the facts line reads "3 clips" with "1 excluded"

#### Scenario: An excluded missing clip shows both labels
- **WHEN** `reel.yaml` lists `borta.mp4`, excludes it, and the file is not on disk
- **THEN** its row shows the Missing label and the Excluded label, no size and no time

#### Scenario: Edit mode marks the same clip
- **WHEN** the operator enters Edit mode on that event
- **THEN** `s1710002.mp4` is listed at position 2 with the Excluded label, and the Included word is not shown
  for it

#### Scenario: The mark is not by color alone
- **WHEN** the Excluded label is shown in light and in dark mode
- **THEN** it reads "Excluded" in words and has an icon, and its fill and edge differ from the Included word's

### Requirement: An event's page schedules its render, held back only by clips a render needs

An event's page SHALL offer, as explicit controls that name what they do:

- a **Render** control when the event needs a render, has no queued or running job, lists no missing clip
  that blocks a render, and the page is not in Edit mode
- when the event is up to date, has no queued or running job, lists no missing clip that blocks a render,
  and the page is not in Edit mode: its up-to-date state plus a secondary **Render anyway** control, which asks
  for confirmation before it forces a render

While the page is in Edit mode, it SHALL offer neither control and SHALL instead say that the edits must be
saved, or Edit mode left, before rendering: a render reads the saved `reel.yaml`, not the unsaved edits. A
queued or running job's progress and its Cancel control stay offered in Edit mode.

A missing clip *blocks* a render when `reel.yaml` names it and does not exclude it, because a render fails
on a missing clip that it plays. A missing clip that `reel.yaml` excludes does not block one: a render skips
it. The page SHALL take which missing clips block from the event read's `blocking_missing`, never from the
list of all missing clips. While the event lists a blocking missing clip, and the page is not in Edit mode,
the page SHALL offer neither control. It SHALL instead say, in words, that the clip is missing from disk and
that it must be restored, or removed in Edit mode, before rendering. For one blocking clip the words SHALL
name it; for several they SHALL give their number, and an excluded missing clip SHALL NOT be counted in
them. A queued or running job's progress and its Cancel control stay offered.

Pressing a control SHALL send one enqueue request, and SHALL NOT send another while that one is
unanswered. Until the answer arrives, the pressed control SHALL stay in place, keep keyboard focus, be
marked busy, and ignore further presses. The page SHALL handle every answer the service publishes:

- **job created:** the page follows the new job
- **up to date, not enqueued:** the page says there is nothing to render, and offers Render anyway
- **a job is already active for the event:** the page follows that job, not an error
- **another event claims the same movie file:** the page names each other event, with a link to its page,
  and says the fix: a distinct title or location in `reel.yaml`
- **unknown event:** the page says the event no longer exists
- **the project could not be scanned** (so the service could not check for another claimant): the page
  says so, with the service's detail, and that nothing was queued
- **the service cannot reach its database** (a 503 whose problem body names the database as the failing
  dependency): the page says the render was not queued because the service can't reach its database, with
  the service's detail
- **any other answer, or none:** the page says the render was not queued, with the status it received or
  that the service is not reachable. It MUST NOT name a cause the answer does not carry; a server error
  without a problem body is not reported as a database failure.

The page MUST tell these outcomes apart by the published status, conflict kind and failing dependency, not by
the problem's prose. Only an event page that shows the event's render state offers these controls; a page whose read
failed offers none.

Render anyway's confirmation asks about an event that is up to date and has no queued or running job. While
it is open and no enqueue request is in flight, if the page would no longer offer Render anyway (a queued or
running job for the event reaches the page, the event no longer reads as up to date, or a missing clip that blocks
a render now holds it back), the dialog SHALL close by itself and send nothing. Whenever a
dialog of the page's render region closes after the control that opened it is gone (Render anyway, once the
job it started shows, or any dialog that closed by itself), keyboard focus SHALL move to the page's job
status, whose words say how the job stands. Focus SHALL NOT fall to the document's body.

#### Scenario: A stale event is rendered
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, which needs a render, and presses Render
- **THEN** one job is enqueued for it, and the page shows that job as queued

#### Scenario: An up-to-date event is rendered only on purpose
- **WHEN** the operator opens `2024-06-21 - Midsommar - Dalarna`, which is up to date
- **THEN** the page shows it as up to date and offers Render anyway, and a render is enqueued only after
  the operator confirms it

#### Scenario: The event became fresh since the page was read
- **WHEN** the page of `2024/Blandat` showed it as needing a render, a job queued elsewhere then rendered
  it while the page had no live connection, and the operator presses Render
- **THEN** no job is enqueued, the page says there is nothing to render and offers Render anyway, and it
  re-reads to show the event as up to date

#### Scenario: A job is already active
- **WHEN** a job for `2024-08-02 - Badutflykt - Varberg` was enqueued elsewhere after the page was read,
  before the page learned of it, and the operator presses Render
- **THEN** the page shows that existing job's state, with no error and no second job

#### Scenario: Two events claim the same movie file
- **WHEN** the operator presses Render on `2024-07-14 - kalas`
- **THEN** no job is enqueued, and the page names `2024-07-14 - Kalas` as the other claimant, links to it,
  and says to give one of them a distinct title or location in `reel.yaml`

#### Scenario: A double click enqueues once
- **WHEN** the operator double-clicks Render on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** one enqueue request is sent

#### Scenario: Render keeps focus while it waits
- **WHEN** the operator presses Enter on Render on `2024-08-20 - Två kapitel - Tjörn`, and the service takes
  two seconds to answer
- **THEN** during those seconds focus stays on Render, which is marked busy, and pressing Enter again sends
  nothing

#### Scenario: Edit mode holds Render back
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, which needs a render, and enters Edit mode
- **THEN** the page offers no Render control and says to save or leave Edit mode to render, and once Edit
  mode ends, Render is offered again

#### Scenario: An unreadable event offers no Render
- **WHEN** the operator opens the page of `2024-02-30 - Omöjligt datum`, whose read fails
- **THEN** the page shows the failure and offers no Render control

#### Scenario: A missing clip holds Render back
- **WHEN** the operator opens `2024-09-01 - Sommarlov`, which needs a render and whose `reel.yaml` lists the
  missing `borttagen.mp4`
- **THEN** the page offers neither Render nor Render anyway, and says that `borttagen.mp4` is missing from
  disk and to restore it, or remove it in Edit mode

#### Scenario: Several missing clips are counted
- **WHEN** the operator opens `2024-09-02 - Två saknade`, whose `reel.yaml` lists two missing clips
- **THEN** the page offers no Render, and says that 2 clips are missing from disk and to restore them, or
  remove them in Edit mode

#### Scenario: An excluded missing clip does not hold Render back
- **WHEN** the operator opens `2024-09-03 - Utesluten`, which needs a render and whose `reel.yaml` lists the
  missing `borta.mp4` and excludes it
- **THEN** the page offers Render, and its warning above the chapters names `borta.mp4` as missing and
  excluded

#### Scenario: Only the missing clip a render needs is named
- **WHEN** the operator opens an event that lists the missing `borta.mp4`, which `reel.yaml` excludes, and
  the missing `borttagen.mp4`, which it does not
- **THEN** the page offers neither Render nor Render anyway, and says that `borttagen.mp4` is missing from
  disk and to restore it, or remove it in Edit mode, without naming or counting `borta.mp4`

#### Scenario: Edit mode's reason takes the place of the missing clip's
- **WHEN** the operator enters Edit mode on `2024-09-01 - Sommarlov`
- **THEN** the page says to save or leave Edit mode to render, and once Edit mode ends with nothing saved, it
  says again that `borttagen.mp4` is missing from disk

#### Scenario: A job queued for such an event can still be cancelled
- **WHEN** a job for `2024-09-02 - Två saknade` was queued before its page was opened, and no worker is
  running
- **THEN** the page shows the job waiting for a worker, with its Cancel control, says that clips are missing
  from disk, and offers no Render

#### Scenario: Confirming Render anyway keeps the keyboard's place
- **WHEN** the operator opens `2024-06-21 - Midsommar - Dalarna`, which is up to date, presses Render anyway
  with the keyboard, and confirms it with the keyboard
- **THEN** one job is enqueued, the page shows it queued, keyboard focus is on the page's job status, and the
  next Tab reaches Cancel

#### Scenario: Render anyway's question closes when a render starts elsewhere
- **WHEN** the Render anyway dialog is open on `2024-06-21 - Midsommar - Dalarna`, and a job for that event,
  queued by another client, reaches the page over the connection
- **THEN** the dialog closes by itself, the page sends no enqueue request, and it shows that job queued, with
  keyboard focus on its job status

#### Scenario: The database is down when Render is pressed
- **WHEN** the operator presses Render on `2024-06-27 - Grillning med grannar` and the service answers 503
  naming the database as the failing dependency
- **THEN** no job is shown, and the page says the render was not queued because the service can't reach its
  database, with the service's detail, and not that the project could not be scanned

#### Scenario: A server error without a problem body is not a database failure
- **WHEN** the operator presses Render on `2024-06-27 - Grillning med grannar` and the service answers 500
  with no problem body, or answers 503 without naming the database
- **THEN** the page says the render was not queued, with the status it received, and does not say that the
  service can't reach its database

### Requirement: A render the service refuses for a missing clip is told, and the screen re-reads
The service refuses an enqueue with a 409 whose conflict kind is `missing_clips` when the event plays a
clip that is missing from disk ("Enqueue refuses an event that plays a clip missing from disk"). Both
Render controls that send an enqueue request (the event page's Render and Render anyway, and a list row's
Render) SHALL handle that answer, in addition to the answers listed in "An event's page schedules its
render" and "The event list shows live job state and offers a render". The client SHALL tell it from the
other 409s by the published conflict kind, not by the problem's prose, and a `missing_clips` answer that
carries no list of clips SHALL be reported as an answer the client does not understand, as a 409 without
its kind is, never as "already active".

The refusal can only reach a screen whose read is out of date, because both screens already hold Render
back for the clips their read lists as missing. It means a played clip has gone missing since that read.
No job is enqueued and none is shown, and the screen SHALL re-read so that its own guard takes over:

- **On the event's page**, the render region SHALL say, in words with an error icon, that the render was not
  queued because the event plays clips that are missing from disk, SHALL name each clip the answer lists,
  and SHALL say to restore them, or remove them in Edit mode. The page SHALL then re-read the event. When
  the re-read lists the clips as blocking the render, the page offers neither Render nor Render anyway, as
  "An event's page schedules its render" requires, and keeps the refusal's words in view. When the re-read
  lists no blocking clip (the clips came back), the page offers Render again and the operator may press it.
  When the pressed control is gone after the re-read, keyboard focus SHALL move to the render region's job
  status, never to the document's body.
- **On a list row**, an error notification SHALL name the pressed event as the row's other notifications do
  (by its title followed by its date, or by its folder name when it has no title), SHALL say that its render
  was not queued because clips are missing from disk, SHALL name the clips (the first three, and their
  number when there are more), and SHALL link to the event's page. The list SHALL then re-read, so that the row shows its missing clips and says that they block its
  render in place of the Render control.

A refusal SHALL NOT create, show or announce a job, and SHALL NOT change the event's saved `reel.yaml`.

#### Scenario: The page learns of a clip that vanished after it was read
- **WHEN** the operator has `2024-09-04 - Hämtad` open, which needs a render and whose clips are all on disk,
  the clip `s1710004.mp4` is then deleted from its folder, and the operator presses Render
- **THEN** no job is enqueued, the page says that the render was not queued because `s1710004.mp4` is
  missing from disk and to restore it or remove it in Edit mode, and after its re-read the page offers
  neither Render nor Render anyway and lists `s1710004.mp4` among the clips missing from disk

#### Scenario: Keyboard focus survives the refusal
- **WHEN** the operator presses Enter on Render on that page, and the answer is the refusal
- **THEN** keyboard focus is on the render region's job status, and the next Tab reaches the next control
  of the page, not the top of the document

#### Scenario: The clip came back before the page re-read
- **WHEN** the refusal reaches the page, and the clip is on disk again by the time the page re-reads
- **THEN** the page offers Render again, and pressing it sends a new enqueue request

#### Scenario: Several clips are all named
- **WHEN** the refusal lists `Kväll/gone-a.mp4` and `gone-b.mp4`
- **THEN** the page names both

#### Scenario: A list row learns of the clip
- **WHEN** the list shows `2024-06-27 - Grillkväll med grannarna` offering Render, one of its clips is deleted
  from its folder, and the operator presses its Render
- **THEN** no job is enqueued, an error notification names “Grillkväll med grannarna” with its date, says
  that its render was not queued because the named clip is missing from disk, and links to its page
- **AND** after the list re-reads, the row shows 1 missing clip and says that missing clips block its
  render, and offers no Render

#### Scenario: A refusal without its clips is not understood
- **WHEN** the service answers an enqueue with a 409 whose conflict kind is `missing_clips` but whose body
  lists no clips
- **THEN** the screen says that the render was not queued and names the status it received, and it does not
  follow any job

#### Scenario: The refusal fits a phone-width window
- **WHEN** the page of `2024-09-04 - Hämtad` is shown 390 pixels wide and shows the refusal
- **THEN** the page does not scroll horizontally, and the refusal's words and the clip's name are fully
  visible

### Requirement: Edit mode's save bar is in the page before the first edit

Once Edit mode has read the editorial document, its save bar SHALL already be part of the page, hidden for as
long as there is nothing to save and no vanished event to explain. The first edit SHALL show it. It SHALL NOT
have to build it.

While the bar is hidden:

- it SHALL take no room in the page and draw nothing
- neither the keyboard nor assistive technology SHALL reach it: Tab SHALL NOT stop on its Reset or Save, and
  the page SHALL NOT list a region named "Unsaved changes"
- it SHALL NOT affect where notifications sit, which stay at the bottom of the window as on a page with no
  save bar, and the page SHALL NOT reserve room at its bottom for it

It SHALL be hidden again whenever nothing is left to save, as before: when every edit is undone, and after
Reset. Showing it SHALL change nothing else about it: what it says, where it is held or rests ("Edit mode's
save bar rests in the page when it would hide the editor"), and that no notification overlaps it ("Notifications
never cover the save bar").

The first edit SHALL cost no more than the next one. In a chapter that plays 400 clips, in a Chromium window
1280 × 900, the time from pressing Move down on a clip to the next painted frame, for the first edit made in
Edit mode, SHALL be at most 50 ms longer than the same press on another clip as the second edit made. The time
is the median of five runs, each in a fresh Edit mode.

#### Scenario: No save bar before the first edit
- **WHEN** in a window 1280 × 900, the operator opens Edit mode on `2024-06-27 - Grillning med grannar`, makes
  no edit, and presses Tab from the Title field through every control of the page
- **THEN** no stop is on a Reset or Save, the page lists no region named "Unsaved changes", and an error
  notification shown at that time sits at the bottom of the window, not raised for a bar

#### Scenario: The first edit shows the bar
- **WHEN** the operator then changes the title
- **THEN** the save bar is held at the window's bottom edge with the title "Unsaved changes", Reset and Save
  (which is its one primary action), and its summary names the changed title
- **AND** an error notification shown then sits above the bar and covers neither Reset nor Save

#### Scenario: An undone edit hides the bar again
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator moves `s1710001.mp4` down one
  place, and then moves it up one place
- **THEN** the save bar was shown after the first move and is hidden after the second, and the page shows no
  unsaved changes

#### Scenario: The first edit in a 400-clip chapter
- **WHEN** in a window 1280 × 900, Edit mode is open on an event whose one chapter plays 400 clips, the
  operator presses Move down on the first clip and then Move down on the second, and the five runs are timed
- **THEN** the median time to the next painted frame of the first press is at most 50 ms longer than the
  second's

### Requirement: Reset leaves keyboard focus on a heading that can be seen

Reset removes the save bar, with the control that was pressed, so keyboard focus SHALL move at once to the
page's heading, never to the page's body. When that heading is not fully visible below the page header, the
page SHALL then scroll the least distance that brings it fully into view, and keyboard focus SHALL stay on it.
When the heading is already fully visible, the page SHALL NOT scroll. This SHALL hold whichever way Reset was
pressed, whether the bar was held or resting, and at every window width from 320 CSS pixels up. The scroll
SHALL be instant: it SHALL NOT animate, with or without a reduced-motion preference.

#### Scenario: Reset from the bottom of a long page
- **WHEN** in windows 1280 × 900 and 390 × 844, in Edit mode on an event whose one chapter plays 400 clips, the
  operator moves its last clip up one place, with the page scrolled to the clip, and presses Reset from the
  keyboard
- **THEN** keyboard focus is on the page's heading, the heading is fully visible below the page header, and
  the clip is back in its place

#### Scenario: Reset with the heading already in view
- **WHEN** in a window 1280 × 900 with the page scrolled to its top, the operator changes the title of
  `2024-06-27 - Grillning med grannar` and presses Reset
- **THEN** keyboard focus is on the page's heading, and the page's scroll position is the same as before the
  press

#### Scenario: Reset with the bar resting
- **WHEN** in a window 320 × 256, the operator changes the title of `2024-06-27 - Grillning med grannar`,
  scrolls to the save bar resting after the last chapter, and presses Reset
- **THEN** keyboard focus is on the page's heading, and the heading is fully visible below the page header

### Requirement: Edit mode saves with Ctrl+S or Cmd+S

While Edit mode has read the event's editorial document, pressing **S** with Ctrl (or Cmd on a Mac), without
Shift or Alt, SHALL act as the Save control does, from wherever keyboard focus is on the page, including a
text field, a clip row's control, the header and the page's body. Reaching Save SHALL NOT take a Tab stop
for every control before it.

The key press SHALL NOT open the browser's own "Save page" dialog, whether or not anything is saved. Before
the document has been read, and while its read has failed, the press SHALL be left to the browser. A press
with Shift or Alt, a held key's repeats, and a press during an IME composition SHALL NOT save, and Shift or
Alt SHALL leave the browser's own meaning of the key alone.

When Save is available, the press SHALL send the same write the Save control sends (the same changes, the
same version check), SHALL announce "Saving…", and SHALL show the same outcomes: the "Saved" notification and
the event page when it is written, and the save bar's failure with its choices when it is not. The press
SHALL NOT move keyboard focus. Save is available under the rules of "Saving an edit writes only what the
operator changed" and "Edit mode's save bar stays compact and fits the window": the shortcut SHALL NOT
save in any state where the Save control is held back.

When Save is held back, the press SHALL send nothing and SHALL announce why:

- with nothing to save: "Nothing to save."
- with a date typed in part, or a cut typed and not added: "Not saved:" and what is unfinished
- after a conflict: that Reload latest or Overwrite with mine comes first
- after the event is found gone: that the event no longer exists
- while a clip is lifted by the drag and not yet dropped or cancelled: that the lifted clip comes first
  ("Not saved: drop or cancel the lifted clip first."), because the order shown is not yet the order that
  a write would carry

While a save is in flight, while a move of marked clips is still being applied, or while a dialog is open (including
the question "Discard unsaved changes?" and the confirmation of Overwrite with mine), the press SHALL send
nothing and say nothing. It SHALL NOT answer a dialog's question.

The Save control SHALL name the shortcut to assistive technology and in its tooltip, and the bar SHALL NOT
show more text for it.

#### Scenario: Saving from the first field
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location in the
  location field and, with keyboard focus still in that field, presses Ctrl+S
- **THEN** exactly one write is sent with the changed location, the live region says "Saving…", the browser's
  Save page dialog does not open, and the event page shows with a "Saved" notification

#### Scenario: Saving after a keyboard reorder without tabbing
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator lifts its first clip by its
  handle from the keyboard, moves it down one place, drops it, and with focus still on that handle presses
  Cmd+S (the meta key)
- **THEN** one write is sent with the new clip order, and no Tab was pressed between the drop and the save

#### Scenario: Nothing has changed
- **WHEN** in Edit mode on `2024-08-02 - Badutflykt - Varberg`, with no edit made, the operator presses Ctrl+S
- **THEN** no request is sent, the live region says "Nothing to save.", and the browser's Save page dialog
  does not open

#### Scenario: A date typed in part
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, clears
  the date's year and presses Ctrl+S
- **THEN** no request is sent, the live region says that the date is incomplete and that nothing was saved,
  and the Save control is still unavailable

#### Scenario: After a conflict the shortcut waits like Save
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, the
  event's `reel.yaml` is changed by hand, the operator saves and the save bar shows the conflict, and then
  the operator presses Ctrl+S
- **THEN** no request is sent, the live region says that Reload latest or Overwrite with mine comes first,
  and the confirmation of Overwrite with mine does not open

#### Scenario: A failed shortcut save keeps the field and the edits
- **WHEN** in Edit mode on `2024-08-02 - Badutflykt - Varberg`, the operator edits the title, presses Ctrl+S
  in the title field, and the request gets no answer
- **THEN** the save bar says that the service is not reachable and offers Retry, the edit is kept, and
  keyboard focus is still in the title field

#### Scenario: A second press during the save does nothing
- **WHEN** the operator presses Ctrl+S, and presses it again, and again as a held key repeats, before the
  service has answered the first
- **THEN** exactly one write is sent, and "Saving…" is announced once

#### Scenario: A dialog's question is not answered
- **WHEN** in Edit mode with unsaved changes, the operator presses Refresh so that "Discard unsaved
  changes?" opens, and presses Ctrl+S
- **THEN** no request is sent, nothing is announced, the dialog stays open with focus on Keep editing, and
  the edits are kept

#### Scenario: A lifted clip is not saved at its old place
- **WHEN** in Edit mode on `2024-06-27 - Grillning med grannar`, the operator changes the location, lifts
  its first clip with Space, moves it down one place with ArrowDown and, before dropping it, presses Ctrl+S
- **THEN** no request is sent, the live region says that the lifted clip must be dropped or cancelled first,
  and the clip is still lifted; after the drop, Ctrl+S sends one write with the location and the new order

#### Scenario: Other chords keep their meaning
- **WHEN** in Edit mode with unsaved changes, the operator presses Ctrl+Shift+S
- **THEN** the page does not save, and does not cancel the browser's own handling of the key

#### Scenario: The shortcut is named
- **WHEN** an unsaved change brings in the save bar
- **THEN** its Save control has the keyboard shortcut Control+S (Meta+S) declared to assistive technology,
  its tooltip reads "Save (Ctrl+S, or ⌘S on a Mac)", and the bar is not taller or wider than before at
  390 × 844

### Requirement: A clip's preview plays its preview copy when one is ready

**Which file plays.** The preview of a clip SHALL play the clip's **preview copy** when the event detail gives
the clip's proxy state as ready and gives the copy's facts a duration above zero, and SHALL play the clip's own
file, the **original**, in every other case: the state absent, stale or failed, a ready state without a usable
duration, or a detail that says nothing of a copy. The choice SHALL be made when the preview opens, from the
detail alone. For a clip whose state is not ready the page SHALL NOT request a preview copy, and SHALL NOT ask for
one to be built. The preview SHALL NOT change file by itself, also not after a failure.

**What it shows of that.** The preview SHALL say in words, under the picture, which file plays: "Playing the
preview copy" or "Playing the original". When the original plays because the state is stale, because it failed,
or because a ready state had no usable duration, the words SHALL give that reason ("its preview copy is out of
date", "its preview copy could not be built", "its preview copy has no usable length"). The words SHALL be
present from the moment the preview opens and SHALL NOT move the picture or the controls.

**The address.** The preview copy SHALL be played from
`GET /api/v1/events/{event_id}/proxy?clip=<identity>&v=<tag>`, the event id and the clip's full identity sent
exactly as the event detail gives them. `v` SHALL be the entity tag the service gives the copy's file, read by a
request for the copy's first byte made when the preview opens and before the picture is asked for, so that a
copy that was replaced is played from a new address. Nothing of the copy's file other than that one byte SHALL be
requested before the operator opens the preview. A copy's answer without an entity tag SHALL be treated as the
service giving no usable answer. The preview SHALL NOT request the copy's filmstrip.

**Play original and Play preview copy.** While the clip has a ready preview copy, the preview SHALL offer one
control that changes the file that plays, as the last of its controls in keyboard order. While the copy plays it
SHALL read "Play original" and be named "Play original of <name>"; while the original plays it SHALL read "Play
preview copy" and be named "Play preview copy of <name>". Pressing it SHALL:
- keep the playhead's time, to the millisecond, and the time shown, the cut bar and the playhead slider with it
- keep playing when the clip was playing, and stay paused when it was paused
- keep keyboard focus on the control, and announce "Playing the original of <name>." or "Playing the preview copy
  of <name>." through Edit mode's live region
- change nothing in the clip's cuts or fields, and count as no edit

The file chosen SHALL stay with the clip while its preview is open, also when the clip moves to another chapter,
and SHALL be forgotten when the preview closes: the next preview of the clip opens on the file the rule above
gives. The control SHALL be absent while the clip has no ready copy.

**Times mean the same in both files.** Time in the preview copy SHALL be time in the original: the preview copy
has the original's timing, so the playhead, the cut bar, Set From, Set To and Skip cuts SHALL act on the playhead
of whichever file plays, to the millisecond and in the same format, and no time SHALL be offset, scaled or
rounded differently for the copy.

**The clip's length** while the preview copy plays SHALL be the duration in the copy's facts, which is the
original's duration as the engine probed it, and SHALL NOT be the length the browser reads from the copy, which
differs from the original's by about 20 ms and can be the shorter. The playhead's end, the panel's "This clip ends
at" and the check on a cut's end SHALL use it. A browser's reading of the copy's length SHALL NOT change it.

**Sound.** The preview copy carries the clip's sound in a form every supported browser plays. While it plays, the
preview SHALL NOT show the note that the browser finds no sound; it SHALL NOT make up a cause for a silent copy.
The note belongs to the original, as "Edit mode previews a clip on request" says.

**When the preview copy cannot be played.** Each of these SHALL be shown in the preview as a note, never as an
alert, announced once through Edit mode's live region, with keyboard focus kept in the preview, and each SHALL
offer **Play original** beside any other action it offers:
- that the preview copy is no longer there, with the service's detail, when the service answers that it has no
  copy of the clip (the detail was read before the copy was removed)
- that the preview copy could not be read, with the failure kind's words and the service's detail
- that the preview copy is empty
- that this browser cannot play the preview copy, when the service serves it and the browser refuses it
- that the service gave no usable answer, saying which, with Try again, which asks for the copy anew and moves
  keyboard focus to the reopened preview's Play

The page SHALL NOT call a copy "changed on disk", and SHALL NOT compare the copy's modification time with the
clip's. Any Download offered in the preview SHALL be the original file. A failure SHALL NOT be retried by itself.
Pressing Play original SHALL open the original as the preview would have opened it without a copy, with
keyboard focus on its Play.

#### Scenario: A Sony clip has sound in Firefox
- **WHEN** in Firefox 155 or later, the event detail of `2024-05-19 - Provklipp` gives
  `sony-xavc-1080p25-pcm.mp4` a ready preview copy, and the operator opens its preview and presses Play
- **THEN** the preview says "Playing the preview copy", the sound it decodes is not silent, and it shows no note
  that the browser finds no sound
- **AND** the page has requested `…/proxy?clip=sony-xavc-1080p25-pcm.mp4&v=<tag>` and has made no request to
  `…/media` for that clip

#### Scenario: Play original keeps the time and the state
- **WHEN** the preview copy of `sony-xavc-1080p25-pcm.mp4` plays and the operator presses "Play original of
  sony-xavc-1080p25-pcm.mp4" while the playhead says `0:02.5`
- **THEN** the original plays on from `0:02.5`, the control now reads "Play preview copy", the preview says
  "Playing the original", "Playing the original of sony-xavc-1080p25-pcm.mp4." is announced, and keyboard focus
  is on the control
- **WHEN** this is Firefox, which finds no sound in the original
- **THEN** the preview shows the note that this browser finds no sound it can play, and the note says that the
  preview copy plays with sound
- **WHEN** the operator pauses and presses "Play preview copy" at `0:04.2`
- **THEN** the preview copy is shown paused at `0:04.2` and the note is gone

#### Scenario: Set From writes the same time from either file
- **WHEN** the operator seeks the preview copy of `s1710001.mp4` of `2024-06-27 - Grillning med grannar` to
  `0:02.5` and presses Set From, then presses Play original, seeks to `0:02.5` and presses Set From again
- **THEN** both presses write `0:02.5` into the start field and the panel accepts it

#### Scenario: A clip with no ready copy plays its original
- **WHEN** the detail gives `s1710002.mp4` the proxy state absent, and the operator opens its preview
- **THEN** the preview says "Playing the original", offers no Play original control, and the page has made no
  request to `…/proxy`
- **WHEN** the detail gives it the state stale
- **THEN** the preview says "Playing the original" and that its preview copy is out of date, and the page has
  made no request to `…/proxy`

#### Scenario: A copy that has gone since the page was read
- **WHEN** the detail gives `s1710001.mp4` a ready copy that the service no longer has, and the operator opens
  its preview
- **THEN** the preview says that the preview copy is no longer there, with the service's detail, as a note and
  not an alert, and offers Play original
- **WHEN** the operator presses Play original
- **THEN** the original is ready to play with keyboard focus on "Play s1710001.mp4"

#### Scenario: A cut to the original's end is accepted while the copy plays
- **WHEN** the detail gives a 50 fps clip of `2024-05-19 - Provklipp` the duration `25.003` in its facts, the
  preview copy reads 24.981 seconds in the browser, and the operator adds a cut from `20` to `0:25.003`
- **THEN** the panel says that the clip ends at `0:25.003` and lists the cut, not refused

#### Scenario: The choice follows the clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator has pressed Play original on `s1710001.mp4`, and
  drags that clip into `Kvällen`
- **THEN** its preview reopens in `Kvällen` paused at the same time, playing the original, and its control reads
  "Play preview copy"
- **WHEN** the operator closes the preview and opens it again
- **THEN** it plays the preview copy

#### Scenario: Play original is the last control
- **WHEN** using only the keyboard, the operator opens the preview of a clip with a ready copy and presses Tab
  from Close through Play, the playhead, Skip cuts, Set From and Set To
- **THEN** the next stop is "Play original of <name>", and it is the last stop of the preview

### Requirement: The movie player lists the rendered movie's chapters

When the event page shows the "Movie" section's player and the event detail gives the movie's chapters, the section
SHALL list them under the player, in a list headed "Chapters" (a level-three heading), in the order of their start
times. The page SHALL take the chapters only from the event detail: each chapter's name and its start in the
rendered movie, in seconds. It SHALL NOT compute, estimate or look up a start time anywhere else (not from the
current chapters and clips of the event, not from clip durations, not from the player's metadata). When the detail
gives no chapters, or gives them in a form the page cannot rely on, the section SHALL show no list, no heading and no
placeholder for one, and SHALL say nothing about it. The chapters are relied on only when there is at least one,
every start is a finite number of seconds of at least 0, the starts strictly increase, and every name is
text that is either empty or not only spaces. The empty name is the event's default chapter as the render
recorded it; the list writes it as the event page does ("Main" when another chapter is named, otherwise
"Clips"), and never invents any other name. A movie of one chapter has nothing to jump between: the section SHALL show no
list for it, as for no chapters (the usual event is one default chapter). The list is the movie's chapters as rendered: an outdated movie lists the chapters it has,
and the section SHALL say so in words with the list ("As rendered"), not by color alone.

**One row per chapter.** Each chapter SHALL be a row with a button as its only control. The row shows the chapter's
number, its name, and its start written as the client writes a place in a clip (`m:ss`, `h:mm:ss` from an hour,
with the fraction of a second only when there is one). The
button's accessible name SHALL be "Jump to chapter N, name, at start", followed by ", current chapter" on the row that
carries the mark, so that each word the button shows is in its name. A long name SHALL wrap inside the row.

**Jumping.** Activating a chapter's button SHALL move the player to that chapter's start, to the millisecond, and
start playback, whether or not the movie had been played before, and whether it was playing, paused or at its
start. A jump before the first Play SHALL NOT need the operator to press Play first. Keyboard focus SHALL stay on
the button. A movie that cannot play after a jump SHALL be said as for any playback failure ("The movie player says
what it cannot play"). The page SHALL add no keyboard shortcut for the list: its buttons are reached with Tab and
activated with Enter or Space, in the order of the chapters.

**The current chapter.** The list SHALL mark the chapter the player's position is in: the last chapter whose start is
at or before the position, where a position up to 60 milliseconds before a start counts as at it, because a
browser's seek may land a frame short. A position before that, ahead of the first chapter, marks none. The mark SHALL be words with an
icon ("Current chapter"), never color alone, and the row's button SHALL carry `aria-current="true"` while it is
marked. The mark SHALL follow the position whether the movie is playing, paused or moved with the player's own
controls, and SHALL stay on the right row within half a second of the position. Exactly one row, or none,
SHALL carry it. The page SHALL NOT announce the mark's moves: they happen while the movie plays.

**What the list stays with.** The list SHALL belong to the player it was shown under. When the movie's file is
replaced and the page shows a new player, the list SHALL show the chapters of the detail that read found. While the
page reads the event again the list SHALL stay as it is, with its buttons usable. When the operator loads the new
movie after the page found the file changed under a playing player, no read describes that file yet, so the page
SHALL show no list and no version line for it until a read of the event answers. When a re-read leaves the player
without a list while keyboard focus is in the list, focus SHALL go to the player; when it removes the whole section,
to the page's heading, as for the section. When the section shows a note in the player's place, it SHALL show no
list.

**Motion and size.** The list SHALL NOT animate: the mark moves without a transition, with or without a
preference for reduced motion, and a jump does not scroll the page. In a window from 320 to 1280 CSS pixels wide the
page SHALL NOT scroll horizontally. Under a coarse pointer each button SHALL take a tap anywhere in an area of at
least 44 × 44 CSS pixels around it. Each button SHALL show a visible focus indicator in both color schemes that
nothing clips.

#### Scenario: A list from the detail's chapter times
- **WHEN** the operator opens `2024-06-21 - Midsommar - Dalarna`, whose detail gives the chapters "Förberedelser"
  at 0 s, "Majstången" at 74 s and "Dans" at 301 s
- **THEN** under the player a "Chapters" list shows three rows, "1 Förberedelser 0:00", "2 Majstången 1:14" and
  "3 Dans 5:01", and the first row is marked "Current chapter"
- **AND** the buttons are named "Jump to chapter 2, Majstången, at 1:14" and so on

#### Scenario: Jumping before the first Play
- **WHEN** the operator opens that page and, without pressing Play, activates "Dans"
- **THEN** the movie starts playing from 301 s (within one frame), the "Dans" row is marked "Current chapter" and no
  other row is, and keyboard focus is still on the "Dans" button

#### Scenario: Jumping from the keyboard
- **WHEN** the operator tabs from the player to the list, tabs to the second button and presses Enter
- **THEN** the movie plays from 74 s, and the second row is marked; pressing Tab moves focus to the third button

#### Scenario: The mark follows the player's own controls
- **WHEN** the movie is paused, and the operator drags the player's own timeline to 310 s
- **THEN** within half a second "Dans" is the only marked row, and the page announced nothing

#### Scenario: The mark is words, not colour
- **WHEN** the operator views the list in both color schemes, and with forced colors
- **THEN** the marked row says "Current chapter" with an icon, its button has `aria-current="true"`, and the other
  rows have neither

#### Scenario: The default chapter is written as the event page writes it
- **WHEN** the operator opens an event whose detail gives the chapters "" at 0 s and "Dans" at 80 s
- **THEN** the list shows "1 Main 0:00" and "2 Dans 1:20", and the first button is named "Jump to chapter 1, Main,
  at 0:00"

#### Scenario: One chapter, nothing to jump to
- **WHEN** the operator opens an event whose detail gives the one chapter "" at 0 s
- **THEN** the section shows its player and facts and no "Chapters" heading or list

#### Scenario: No chapter data, no list
- **WHEN** the operator opens `2024-07-14 - Kalas`, whose movie was rendered before chapter times were recorded, so
  its detail gives no chapters
- **THEN** the "Movie" section shows its player and facts and no "Chapters" heading or list, and no chapter start
  is derived from the event's clips

#### Scenario: Chapters that cannot be relied on
- **WHEN** a detail gives chapters whose starts do not increase, or one whose name is only spaces, or a start that is not a
  number
- **THEN** the section shows no list at all, rather than the part that seems right

#### Scenario: An outdated movie lists what it has
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, whose chapters changed after its render
- **THEN** the "Chapters" list holds the chapters of the movie as rendered and says "As rendered"

#### Scenario: A new render replaces the list with its player
- **WHEN** a forced render of `2024-06-21 - Midsommar - Dalarna` finishes while its page is shown, and the read finds
  a new entity-tag and a fourth chapter
- **THEN** the page shows the new player and a list of four chapters, and the old player's position is not carried
  over to the marks

#### Scenario: Loading a changed movie shows no old chapters
- **WHEN** the movie's file is replaced from the command line while its page is open with a chapter list, the operator
  presses Play, the page says the file changed, and the operator presses "Load the new movie"
- **THEN** the new file is in the player, and the page shows neither the old render's chapter list nor its
  "Recorded … · version …" line

#### Scenario: The list at phone width
- **WHEN** the operator opens that page in windows 320 and 390 pixels wide, in both color schemes
- **THEN** the page does not scroll horizontally, a long chapter name wraps inside its row, and under a coarse
  pointer each button takes a tap anywhere in 44 × 44 pixels around it

#### Scenario: Reduced motion
- **WHEN** the operator has asked for reduced motion and activates "Dans"
- **THEN** the mark moves to its row at once, no transition or animation runs, and the page does not scroll

#### Scenario: A re-read removes the list while it has focus
- **WHEN** keyboard focus is on a chapter button and a re-read the page started by itself finds a movie with no
  chapters
- **THEN** the list is gone and keyboard focus is on the player

### Requirement: The event page watches a clip on request

In the event page's read view, the thumbnail of every clip whose file is on disk (a clip of any status but missing:
an included, new, ignored or excluded clip) SHALL carry a **play control**: a button laid over the thumbnail's box,
filling it, with a play glyph (a disc with a triangle) centred in it. The row of a missing clip SHALL offer none
and SHALL NOT keep room for one; its empty placeholder box stays as it is. The control SHALL be the row's one way to
open the player: the file cell SHALL hold no Watch button, only the clip's name and its cuts indicator. The control's
name SHALL be "Play <name>", where <name> is the clip's name as its row names it. While the clip's player is open the
control SHALL show the hide icon instead of the play glyph and its name SHALL be "Hide player of <name>", so that it
never shares a name with the open player's own Play / Pause button ("Play <name>" / "Pause <name>"). It SHALL say to
assistive technology whether the player is open and which region it controls. Pressing it SHALL open the clip's
player, and pressing it while the player is open SHALL close it. The thumbnail's image, its text alternative
"Frame from <name>", its box, its size, its dimming of an ignored clip and its "No preview" box SHALL be as "Every
clip row shows a frame from its clip" says; the control is over them, not instead of them, and it is offered on a
"No preview" box too.

**When the glyph is seen.** The control SHALL be operable at all times and SHALL be reached by Tab at all times,
whether its glyph is seen or not. The glyph SHALL be seen while the pointer is over the thumbnail, while the control
has keyboard focus, and while the player is open, and SHALL always be seen when the primary pointer is coarse. With a
fine pointer that is elsewhere and no focus on it, the glyph MAY be unseen. It SHALL appear at once, with no
animation. Open or closed SHALL NOT be shown by colour alone: the glyph changes and the name and `aria-expanded`
follow. A visible focus ring SHALL show on the control when it has keyboard focus, and the glyph and the ring SHALL be
legible over any frame, light or dark, and in forced-colors mode.

**The area.** The control SHALL fill the thumbnail's box, which is at least 80 × 45 CSS pixels, so that a press
anywhere on the frame reaches it, with a mouse and with a finger, and so that, when the primary pointer is coarse, it
takes a tap anywhere in an area of at least 44 × 44 CSS pixels and reaches no other control. It SHALL start no drag.

**Where the player opens.** The player SHALL open in a row of its own directly under the clip's row, as wide as the
table, as a region named "Player for <name>". That row SHALL be no clip: it SHALL carry no position, SHALL count in
no clip count, and SHALL exist only while the player is open. Opening it SHALL bring it into view whole when it
fits the window, moving the page no further than that takes, and SHALL move keyboard focus to the player's Play
control.

**The player is the preview Edit mode opens.** It is the same component. It SHALL play what "Edit mode previews a
clip on request" says the preview plays, choose its file, say which file plays, offer Play original, and show its
notes by cause, as "A clip's preview plays its preview copy when one is ready" says, with the differences that "A
clip watched on the event page is played, not edited" names and no others. A clip with a ready preview copy SHALL
therefore play it, with sound in Firefox; a clip without one SHALL play its original, and in Firefox a Sony clip's
original SHALL still carry the no-sound note.

**One at a time.** Opening a player SHALL close any other clip's player, so that the read view holds at most one clip
player, in any chapter. Pressing the control of a clip whose player is open SHALL close it.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media, its preview copy or its
filmstrip, and SHALL NOT create a video element for a clip, before the operator opens that clip's player. This SHALL
hold for any number of clips, and on opening the page, scrolling it, refreshing it, and leaving Edit mode. A play
control SHALL be made from the event detail alone. Closing a player SHALL stop its playback and any loading of its
file.

**Closing.** Close, and Escape pressed while keyboard focus is in the player, SHALL close it and move keyboard focus to
the clip's play control, whose glyph is then seen because it has keyboard focus. No control of a closed player SHALL keep focus.

**What a read of the event does to an open player.**
- A re-read the page starts by itself (when the job it shows reaches a finished state, see "A shown screen re-reads in
  place when events change") SHALL leave an open player as it is, playing or paused, at its position, when the clip is
  still on disk with the same modification time.
- When that re-read finds the clip on disk with another modification time, the player SHALL go on with the clip's
  new file, paused at the time it had reached; it SHALL NOT go on with the old file at the old address.
- When that re-read changes only what the detail says of the clip's preview copy (a copy was built or went stale
  meanwhile), the player SHALL stay on the file it plays and SHALL NOT change file by itself; the next player of the
  clip SHALL use the new state.
- When that re-read no longer lists the clip, or lists it as missing, the player SHALL close and its row SHALL go.
  If keyboard focus had been in the player, it SHALL move to the clip's row when the clip is still listed, and
  otherwise to the page's heading, as after any read that removes the control that held it.
- The operator's Refresh, and opening Edit mode, SHALL close the player, as they replace the page's content: the page
  SHALL NOT keep a player across a read that shows placeholders.

**Sizes and look.**
- In a window 320 CSS pixels wide or more, the play control and the open player SHALL NOT make the page scroll
  horizontally, with a clip whose name is 40 characters long.
- The player's box and controls SHALL be as "Edit mode previews a clip on request" sizes them (a fixed 16:9 box as wide
  as the table allows up to 640 CSS pixels and never taller than 360, with its size before the file is read); the row
  SHALL be as wide as the table in every layout the table has, including the narrow ones where each clip row is a
  grid.
- The control and the player SHALL follow the page's color scheme in both schemes. No state of either SHALL be shown
  by color alone: open or closed is said by the glyph, in the name and to assistive technology.
- They SHALL animate nothing.
- The control SHALL add no height to a row: it sits over the thumbnail and adds no line to the file cell, so that no
  clip row is taller than it was with its Watch button.

#### Scenario: A Sony clip is watched with sound in Firefox
- **WHEN** in Firefox 155 or later, the operator opens `2024-05-19 - Provklipp`, whose detail gives
  `sony-xavc-1080p25-pcm.mp4` a ready preview copy, presses "Play sony-xavc-1080p25-pcm.mp4" on its thumbnail and then the player's Play
- **THEN** a region named "Player for sony-xavc-1080p25-pcm.mp4" is open directly under that clip's row, it says
  "Playing the preview copy", the sound it decodes is not silent, and it shows no note that the browser finds no
  sound
- **AND** the control over the thumbnail now shows the hide icon, is named "Hide player of sony-xavc-1080p25-pcm.mp4"
  and says its player is open, and the page has made no request to `…/media` for that clip

#### Scenario: A clip without a ready copy plays its original
- **WHEN** the operator opens the player of `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose detail
  gives no ready preview copy
- **THEN** the player says "Playing the original", offers no Play original control, and the page has made no
  request to `…/proxy`

#### Scenario: A missing clip has no Watch
- **WHEN** `reel.yaml` of `2024-06-27 - Grillning med grannar` lists `borttagen.mp4` and the file is not on disk
- **THEN** the row of `borttagen.mp4` shows no play control over its empty placeholder box, and Tab does not stop in that row except on its
  cuts indicator if it has one

#### Scenario: An ignored and an excluded clip can be watched
- **WHEN** the operator opens `2024-08-20 - Två kapitel - Tjörn`, whose root clip `s1710004.mp4` `reel.yaml`
  ignores, and an event in which `reel.yaml` excludes `s1710002.mp4`
- **THEN** the thumbnail of each of those rows carries "Play <name>", and the player of the excluded clip shows no cuts

#### Scenario: Nothing loads until a Watch is pressed
- **WHEN** the operator opens `2024-09-15 - Stor dag`, whose root chapter plays 400 clips, scrolls to its end,
  refreshes the page, enters Edit mode and leaves it
- **THEN** after each of those the page holds no video element for a clip and has made no media, preview copy or
  filmstrip request
- **WHEN** the operator presses "Play c0400.mp4" on its thumbnail
- **THEN** the page holds one video element and its requests are for `c0400.mp4` alone

#### Scenario: Escape gives focus back to the row
- **WHEN** the operator opens a player with the keyboard (Enter on "Play s1710001.mp4"), then presses Escape
- **THEN** the player is closed and keyboard focus is on "Play s1710001.mp4", which shows the play glyph again
- **WHEN** the operator opens it again and presses the player's Close
- **THEN** keyboard focus is on that control again

#### Scenario: Opening another player closes the first
- **WHEN** the player of `s1710001.mp4` is open in `Main` and the operator presses "Play s1710002.mp4" on its thumbnail in
  `Kvällen`
- **THEN** the first player is closed, its control shows the play glyph and is named "Play s1710001.mp4", the second player is open and keyboard focus is on
  its Play, and the page holds one video element

#### Scenario: A job finishing leaves the open player playing
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the render job of the event reaches "Rendered", so that
  the page re-reads the event, and the clip is unchanged
- **THEN** the player keeps playing without a pause or a seek

#### Scenario: A copy built under an open player is not switched to
- **WHEN** the player of `sony-xavc-1080p25-pcm.mp4` plays its original, because its detail gave no copy, and a
  proxy job for the event finishes so that the re-read gives the clip a ready copy
- **THEN** the player keeps playing the original, without a pause or a seek, and says "Playing the original"
- **WHEN** the operator closes it and presses its play control again
- **THEN** the player says "Playing the preview copy"

#### Scenario: A clip replaced under an open player
- **WHEN** the player of `s1710001.mp4` is paused at `0:03.2` and a re-read finds the clip with a new modification
  time
- **THEN** the player goes on with the new file, paused at `0:03.2`, and no request after the re-read is for the old
  address
- **WHEN** keyboard focus was in that player (on its Play, say) before the re-read
- **THEN** keyboard focus is on the new player's Play, as after any read that removes the control that held it

#### Scenario: A clip that goes missing closes its player
- **WHEN** the player of `s1710001.mp4` is open with keyboard focus in it and a re-read finds the clip missing
- **THEN** the player and its row are gone, the clip's own row has no play control, and keyboard focus is on the
  clip's row
- **WHEN** instead that re-read no longer lists the clip at all
- **THEN** keyboard focus is on the page's heading

#### Scenario: Refresh and Edit mode close the player
- **WHEN** the operator has a player open and presses Refresh
- **THEN** the page shows its placeholders while it reads, and when it answers no player is open
- **WHEN** the operator has a player open and presses Edit
- **THEN** Edit mode opens with no player open, and its Cuts panels and Watch controls are as they were, and its thumbnails are the "Watch <name>" buttons they were

#### Scenario: Watching on a phone
- **WHEN** in a window 390 pixels wide with a coarse pointer, the operator opens a player under the clip row of
  `2024-05-19 - Provklipp`
- **THEN** the page does not scroll horizontally, every play control shows its glyph, a tap anywhere in an area of at
  least 44 × 44 CSS pixels over the thumbnail reaches that control and no other, and the player's box is as wide as
  the table up to 640 pixels

#### Scenario: The glyph shows on hover and on focus
- **WHEN** in a window 1280 pixels wide with a mouse, the operator opens `2024-06-27 - Grillning med grannar` and has
  not moved the pointer over a clip
- **THEN** no play glyph is seen, and Tab reaches "Play s1710001.mp4", whose glyph and focus ring are then seen
- **WHEN** the pointer moves over the thumbnail of `s1710002.mp4`
- **THEN** its glyph is seen at once, and it is gone again when the pointer leaves the thumbnail

#### Scenario: A press anywhere on the frame plays it
- **WHEN** the operator presses with a mouse on a corner of the thumbnail of `s1710001.mp4`, not on the glyph
- **THEN** the clip's player opens as it does for the glyph, and the row has not been dragged

#### Scenario: The open player's Play does not share the control's name
- **WHEN** the player of `s1710001.mp4` is open
- **THEN** the thumbnail's control is named "Hide player of s1710001.mp4", the player holds a button named "Play
  s1710001.mp4" or "Pause s1710001.mp4", and no two controls of the page share a name

#### Scenario: The file cell holds no button
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar` in a window 1280 pixels wide
- **THEN** the file cell of every clip row holds the clip's name and its cuts indicator and no button, and no row is
  taller than it was with its Watch button

### Requirement: A clip watched on the event page is played, not edited

The player of a clip in the event page's read view SHALL be read-only. It SHALL differ from Edit mode's preview in
these ways, and in no others:

- **No cut controls.** It SHALL have no Set From and no Set To, neither enabled nor disabled, and nothing in it SHALL
  write a cut field or a cut.
- **The keyboard order** SHALL be: **Close**, **Play** / **Pause**, the **playhead**, **Skip cuts** when the clip has
  cuts to skip, and **Play original** / **Play preview copy** when the clip has a ready preview copy. Each SHALL be
  reachable and usable by keyboard alone, and the control that changes the file SHALL be the last when it is offered,
  as "A clip's preview plays its preview copy when one is ready" says.
- **The cut bar shows the clip's cuts as the page lists them.** The cuts are the ones the event page read from the
  service for its cuts indicator, the cuts read last until a new read answers. The bar SHALL draw them as spans, with
  a legend that names only the kinds drawn (here only "Cut"), and the playhead's spoken value SHALL add "in cut N"
  when the time lies inside one, N being the cut's number in the clip's cut list on the page. A press or a drag along
  the bar SHALL move the playhead and SHALL NOT change a cut. A clip that `reel.yaml` excludes SHALL show no cuts
  on its bar, as the page shows none beside its name. When the page could not read the cuts, the bar SHALL show no
  cuts, the player SHALL offer no Skip cuts, and the page's note that the cuts could not be read SHALL stay the
  only word of it.
- **Skip cuts** SHALL be offered only for a clip that has at least one cut on its bar, and SHALL play the clip as
  the movie will, as "A clip's preview sets cut times at the playhead and plays the clip as the movie will" says of
  Skip cuts. Pressing it SHALL change no file and no state but the player's.
- **The live region.** The read view SHALL have one polite live region for its player, which carries what Edit mode's
  live region carries for a preview: that the clip is ready to play with its length, each note, each failure, and
  which file plays after Play original. Wherever a requirement for Edit mode's preview says "Edit mode's live
  region", the read view's is meant.
- **The advice after a clip that is gone or changed on disk** SHALL be to press Refresh to read the event again and
  then to watch the clip anew. The words SHALL NOT mention editing, saving or Edit mode. The player SHALL NOT
  refresh the page itself, and the failure SHALL NOT be retried by itself.
- **No cut check.** The player SHALL make no check of a cut against the clip's length, as it makes no cut.

Everything else SHALL be as it is in Edit mode, for the same reason: the file that plays, the address, the copy's
probe, the length of the clip while the copy plays, the one-line statement of which file plays, the notes (no sound
in this browser for the original; no picture), the failures by cause, the Download of the original, the Try again
that opens the player anew, the playhead's keys and words, the sizes and the look.

**It writes nothing.** Opening, closing, playing, seeking, Skip cuts and Play original SHALL write no file, enqueue or
cancel no job, send no request but the reads that play the clip, and SHALL NOT change the event page's content, its
counts or its verdict ("Reading a screen never changes state").

#### Scenario: A player without cut controls
- **WHEN** the operator opens the player of `s1710001.mp4` of `2024-06-27 - Grillning med grannar`, which has
  one cut from `0` to `1.5`
- **THEN** the player has Close, Play, the playhead and "Skip cuts of s1710001.mp4" and no Set From or Set To
  anywhere in it, and the bar draws the cut from `0:00` to `0:01.5` with a legend that reads "Cut"
- **WHEN** the operator seeks to `0:01` with the keyboard
- **THEN** the playhead says `0:01 of 0:06.02, in cut 1`, and the clip's cut list on the page is unchanged

#### Scenario: Skip cuts is a view option
- **WHEN** the operator presses "Skip cuts of s1710001.mp4" and then Play with the playhead at `0:00`
- **THEN** playback starts at `0:01.5`, and no frame inside the cut is shown
- **AND** a clip without cuts offers no Skip cuts

#### Scenario: Play original is the last stop
- **WHEN** using only the keyboard, the operator opens the player of a clip that has cuts and a ready preview copy and
  presses Tab from Close
- **THEN** the stops are Play, the playhead, Skip cuts and "Play original of <name>", in that order, and the last is
  "Play original of <name>"

#### Scenario: A clip with unreadable cuts has a plain bar
- **WHEN** the service does not answer the read of `2024-06-27 - Grillning med grannar`'s cuts and the operator
  opens a player
- **THEN** the page shows its note that the cuts could not be read, the player's bar draws no cut, and the player
  offers no Skip cuts

#### Scenario: A clip changed on disk says Refresh, not Stop editing
- **WHEN** the operator opens the player of a clip whose file the service no longer serves, because it was removed
  after the page was read
- **THEN** the player says that the clip is no longer on disk, with the service's detail, and that pressing Refresh
  reads the event again, and says nothing of editing or saving
- **AND** that note is announced once through the read view's live region, and the page has not refreshed

#### Scenario: Watching changes nothing
- **WHEN** the operator opens `2024-06-27 - Grillning med grannar`, watches `s1710001.mp4`, presses Play, seeks,
  turns Skip cuts on and off, closes the player and goes back to the list
- **THEN** every request the client made was a read, no file under the library changed, and the jobs the service
  lists are the same as before

### Requirement: The event page plays one video at a time

Whenever a video of the page starts to play while another video of the page is playing, the other SHALL be paused where
it is. This SHALL hold between any two of the page's players, in either order: the Movie section's player, a clip's
player in the read view, a clip's preview in Edit mode and the Timeline's video (Edit mode only), however the video was started (its
own controls, a keyboard key, a chapter jump in the Movie section's chapter list, a thumbnail's play control, the
Timeline's Play, or a player's Play after a thumbnail's control opened it). The rule SHALL be one rule for every video, held in
one place, and not a rule per pair of players: a player added to the page SHALL be covered by it without being named
in it. Neither video SHALL be closed, replaced, restarted or seeked by it, no word SHALL be announced for it, and
pausing SHALL be the only thing the page does: the video that was paused SHALL stay available and play on from its
position when its own Play is pressed. A video that Skip cuts seeks, or that plays on after a seek or after a change of
its file at a clip boundary, SHALL NOT count as starting. A video that is paused or ended SHALL NOT be touched.

#### Scenario: A clip started while the movie plays
- **WHEN** the Movie section's player plays at `1:12` and the operator presses Play in the open player of
  `s1710001.mp4`
- **THEN** the movie is paused at `1:12`, the clip plays, and the Movie section's player is still there

#### Scenario: A clip started from its thumbnail while the movie plays
- **WHEN** the Movie section's player plays at `1:12`, the operator presses "Play s1710001.mp4" on that clip's
  thumbnail, whose player opens paused, and then presses the player's Play
- **THEN** the movie is paused at `1:12` and stays there, the clip plays, and nothing has been closed

#### Scenario: The movie started while a clip plays
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the operator presses play in the Movie section's
  player
- **THEN** the clip's player is paused at `0:03.2`, stays open, and plays on from `0:03.2` when its Play is pressed,
  which pauses the movie

#### Scenario: A chapter jump starts the movie while a clip plays
- **WHEN** the player of `s1710001.mp4` plays at `0:03.2` and the operator presses the second chapter in the Movie
  section's chapter list
- **THEN** the movie plays from that chapter, the clip's player is paused at `0:03.2` and stays open

#### Scenario: Two clips never play together
- **WHEN** the player of `s1710001.mp4` plays and the operator presses "Play s1710002.mp4" on its thumbnail, and then the
  second player's Play
- **THEN** the first player has closed, as one player is open at a time, and only the second clip plays

#### Scenario: The Timeline and a clip's player
- **WHEN** in the read view the operator presses "Play s1710001.mp4" on a thumbnail and then the player's Play
- **THEN** the clip plays and no Timeline video exists to pause: the read view has no Timeline (`event-timeline`, "The
  Timeline is shown only in Edit mode, open from the start"); in Edit mode a clip's preview and the Timeline follow the
  next scenario

#### Scenario: Edit mode's preview and the Timeline
- **WHEN** in Edit mode a clip's preview plays and the operator presses Play on the Timeline
- **THEN** the preview closes as "Edit mode holds one video at a time" says, and only the Timeline plays

### Requirement: A trim made on the timeline is an edit of the same draft as a cut made in the Cuts panel

A cut changed on the Edit-mode Timeline ("Edit mode's cuts are trim handles") SHALL change the cut in the editor's draft, the one the clip's Cuts panel lists, and SHALL be saved, counted, guarded and undone as any other cut edit. There SHALL be no second list of cuts and no save path of the Timeline's own.

- **The cut keeps what it is.** A trimmed cut keeps its place in the clip's list, its number and its reason (a cut an analysis made keeps its reason; a trim does not make it `manual`). Only its start or end changes. The Cuts panel SHALL list the new times at once, and a cut trimmed back to the times it was read with SHALL leave nothing to save, so that an edit and its reverse show no save bar. A cut typed in the Cuts panel and then trimmed stays an added cut.
- **The save bar counts it.** The save bar SHALL say how many cuts were trimmed ("1 cut trimmed"), beside the cuts added and removed, counting a read cut whose saved start or end differs from the one read, on a clip whose saved cuts differ. A trim that leaves the saved cuts as they were SHALL count as nothing. Pressing Save SHALL send the same whole-document write under `If-Match` that every other edit sends, with the clip's changed `trims`: the service edits the span that changed in place and leaves the other spans, their comments and their style as authored ("A changed cut list edits only the spans that differ").
- **Guards and reset.** A trimmed cut SHALL make the event count as having unsaved changes (leaving Edit mode, navigating away and closing the tab ask first, Ctrl+S and Cmd+S save). Reset SHALL put every trimmed cut back to the times it was read with, and the Timeline SHALL show them.
- **A conflict.** When the save is refused because the event was changed elsewhere (412), the page SHALL show the conflict as for any edit, keeping the trims. "Reload latest (discard my changes)" SHALL discard the trims as it discards every edit (it leaves Edit mode and shows the event as read again; Edit mode entered again draws the cuts as saved), and "Overwrite with mine" SHALL write the trims over the latest.
- **Removed neighbours.** A removed cut is not a neighbour: a handle can be moved over the span of a removed cut. An Undo of that cut that would then overlap a cut is refused, as for a cut added in this Edit mode, and names the cut to remove first.
- **Past the clip.** The Timeline's clip length is its proxy's duration. A trim SHALL NOT write a cut that ends after it (a typed time past it is refused), and a cut read from `reel.yaml` that already ends after it is saved as read until its end is moved.
- **Nothing else is written.** Selecting a cut, moving the playhead, scrubbing, and a drag that was cancelled or that ended where it began SHALL write nothing and SHALL NOT count as an edit.

#### Scenario: A trim is saved as a change of one span
- **WHEN** on `2024-06-27 - Grillning med grannar`, `s1710001.mp4` has `trims: [{in: 1, out: 2.5, reason: black}]` with a comment on that line in `reel.yaml`, and the operator drags the cut's end to 3.5 s on the Timeline in Edit mode and presses Save
- **THEN** the save bar before saving says "1 cut trimmed", the write is one `PUT` under `If-Match`, and `reel.yaml` afterwards holds the same span with `out: 3.5`, `reason: black` and the comment, and nothing else changed

#### Scenario: A trim and its reverse leave nothing to save
- **WHEN** the operator trims a read cut's start from 1.0 s to 1.02 s with Right on its handle and then presses Left once on the same handle
- **THEN** the cut is back at 1.0 s, the Cuts panel lists it as read, and no save bar is shown

#### Scenario: A trimmed analysis cut keeps its reason
- **WHEN** a cut with the reason `freeze` is trimmed on the Timeline and saved
- **THEN** the span is written with the new times and the reason `freeze`

#### Scenario: The Cuts panel follows the Timeline
- **WHEN** the operator drags the start of cut 1 of `s1710001.mp4` to 0.5 s and the Cuts panel of that clip is shown
- **THEN** the panel lists cut 1 as 0:00.5 to 0:02.5, the Cuts control of the clip reads the new summary, and the edit is announced

#### Scenario: Reset puts the trims back
- **WHEN** two cuts are trimmed and the operator presses Reset
- **THEN** the Timeline draws both cuts at the times they were read with, no save bar remains, and no handle is selected

#### Scenario: A conflict keeps the trims
- **WHEN** the event's `reel.yaml` was changed elsewhere after Edit mode read it and the operator saves a trim
- **THEN** the page says that the event was changed elsewhere since the operator started editing and offers "Reload latest (discard my changes)" and "Overwrite with mine", and the Timeline still draws the trim
- **WHEN** the operator presses "Reload latest (discard my changes)"
- **THEN** the page leaves Edit mode with no trim kept, no save bar remains, and pressing Edit again shows a Timeline that draws the cuts of the reloaded document

#### Scenario: Undo of a removed cut over a trimmed one
- **WHEN** cut 1 (1.0 to 2.5 s) is removed, cut 2 is trimmed to start at 2.0 s, and the operator presses Undo on cut 1
- **THEN** the Undo is refused in cut 1's row, naming cut 2 as the one to remove first, and cut 1 stays removed

#### Scenario: A look at a cut is not an edit
- **WHEN** the operator tabs through every handle, selects a cut, scrubs the playhead and starts and cancels a drag
- **THEN** no save bar is shown and leaving Edit mode asks nothing

### Requirement: Edit mode marks clips to move together

In Edit mode, every clip that a chapter plays and that is on disk (active or new) SHALL have a **mark**: a
checkbox in the top-right corner of its thumbnail, named "Mark <name>", where <name> is the clip's name as its row
names it. A marked clip SHALL show a check icon inside the box, so that its state is not told by colour alone, and the
box SHALL be exposed to assistive technology as checked. Pressing the box, or Space on it, SHALL mark an unmarked clip
and unmark a marked one. The box SHALL be 24 CSS pixels square and SHALL lie inside the thumbnail's box, with its
top-right corner within 6 CSS pixels of the thumbnail's top-right corner, in the one-line layout and in the narrow
layout. The thumbnail's own size and place SHALL stay as they are ("Every clip row shows a frame from its clip").

When the browser's primary pointer is coarse, a tap anywhere in a 44 × 44 CSS pixel area around the box SHALL reach the
mark, taking precedence over the clip's Watch button where the two overlap; the rest of the thumbnail SHALL still open
the clip's preview. The areas of the mark and of the row's other controls SHALL NOT otherwise overlap. When the primary
pointer is fine, the mark SHALL keep the 24 pixel box and nothing around it.

Three kinds of clip SHALL have no mark, as a drag does not take them into another chapter ("Edit mode drags
clips between chapters"): a missing clip, an ignored clip, and a missing clip the operator removed. The Clips help SHALL
say so in a few words.

Marking is not an edit. It SHALL NOT show the save bar, SHALL NOT count as an unsaved change, SHALL NOT enable Reset or
Save, and SHALL NOT make leaving Edit mode ask first. Marks SHALL be kept per clip, whichever chapter it is in, and a
mark SHALL stay on its clip when another edit moves the clip (Move up, Move down, a drag of another clip), and when the
Cuts panel is opened or closed.

A line above the chapters SHALL always be present in Edit mode and SHALL hold the Clips help's toggle. How clips are marked, that dragging a marked
clip's handle moves all marked clips, and that Move marked to… moves them to a chapter SHALL be said in the Clips help, not in the line. While at least one clip is marked, the line SHALL show how many ("1 clip
marked", "3 clips marked") and a **Clear marks** button. The line SHALL keep its height whether or not it shows the
count, so that marking the first clip, and clearing the last mark, move no row.

Each change of a mark, and Clear marks, SHALL be announced once to assistive technology, with the clip's name and the
count ("s1710002.mp4 marked. 2 clips marked.", "s1710002.mp4 unmarked. No clips marked.", "Marks cleared."). Marks
SHALL end as follows:

- a clip that a drag or Move marked to… moves into another chapter, or that a group drag moves, SHALL be unmarked by that
  move; a drop that changes nothing SHALL leave every mark
- all marks SHALL end on a successful Save, on Reset, when Edit mode is left, and when the editor reads the event's
  `reel.yaml` again (Reload latest)
- a drag of an unmarked clip, Move up, Move down, adding, renaming or deleting a chapter, and cut edits SHALL leave
  marks as they are

The mark and Clear marks follow the busy-control rule: while a save is in flight or a move of marked clips is being applied, they
SHALL be aria-disabled and ignore presses, never `disabled`. A mark's keyboard focus ring SHALL be visible in both
color schemes and in forced colors. Pressing Clear marks SHALL move keyboard focus to that line, since the button leaves with the count.
The mark SHALL NOT start a drag, and a press on it SHALL NOT lift its row. Marking
a clip in a chapter that plays 400 clips, in a Chromium window 1280 × 900, SHALL reach the next painted frame within
100 ms (the median of five runs, each in a fresh Edit mode).

#### Scenario: Marking two clips
- **WHEN** in Edit mode on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` and then
  `Kvällen/s1710003.mp4` with the boxes at the top right of their frames
- **THEN**
  - each box shows a check icon and is exposed as checked, named "Mark s1710002.mp4" and "Mark s1710003.mp4"
  - the line above the chapters says "2 clips marked" and offers Clear marks
  - "s1710003.mp4 marked. 2 clips marked." was announced, and the save bar is not shown
  - no row moved when the first mark was made

#### Scenario: Missing and ignored clips have no mark
- **WHEN** on `2024-09-01 - Sommarlov` the operator looks at the row of the missing `borttagen.mp4`, and on
  `2024-08-20 - Två kapitel - Tjörn` at the row of the ignored `s1710004.mp4`
- **THEN** neither row has a mark, and the Clips help, opened, says that missing and ignored clips cannot be
  marked

#### Scenario: Marking by touch next to the Watch button
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, the operator taps in a
  44 × 44 pixel area centred on the box of `Kvällen/s1710002.mp4`, which sits over the top right of its Watch button
- **THEN** the clip is marked and its preview did not open
- **WHEN** the operator taps the middle of that thumbnail
- **THEN** the clip's preview opens and the mark is unchanged

#### Scenario: Marks are not an unsaved change
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710003.mp4`, and then
  leaves Edit mode
- **THEN** no question about unsaved changes was asked and the save bar was never shown
- **WHEN** the operator enters Edit mode again
- **THEN** no clip is marked and the line shows no count

#### Scenario: A mark with the keyboard only
- **WHEN** using only the keyboard on `2024-06-27 - Grillning med grannar`, the operator tabs to the mark of
  `s1710002.mp4`, which shows a focus ring, and presses Space, and then tabs to Clear marks and presses Enter
- **THEN** "s1710002.mp4 marked. 1 clip marked." and then "Marks cleared." were announced, and keyboard focus is on
  the line above the chapters (reachable by script, not by Tab), not lost to the page

#### Scenario: Marks are held while a save is pending
- **WHEN** on `2024-06-27 - Grillning med grannar`, after moving `s1710004.mp4` up one place, the operator presses
  Save and the service has not answered yet, and then presses a clip's mark
- **THEN** the mark does not change, and it is aria-disabled, not `disabled`

#### Scenario: A mark survives other edits and ends on Save
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710002.mp4`, moves `s1710001.mp4` down one
  place, shows the Cuts of `s1710002.mp4`, and then saves
- **THEN** `s1710002.mp4` was still marked after the move and after the Cuts panel, and after the save no clip is
  marked

#### Scenario: Marking in a long chapter
- **WHEN** in a Chromium window 1280 × 900, on an event whose one chapter plays 400 clips, the operator marks the
  200th clip, five times, each in a fresh Edit mode
- **THEN** the median time from the press to the next painted frame is at most 100 ms

### Requirement: Dragging a marked clip moves the whole marked group

While two or more clips are marked, lifting any marked clip SHALL lift all marked clips, in each of the ways a clip
is lifted ("The event page reorders clips within a chapter", "Edit mode drags clips between chapters"): by its handle
with a mouse, pen or touch, and from the keyboard on its handle. Only a marked clip's handle lifts a group. Lifting an
unmarked clip SHALL lift that clip alone, with the marks left as they are, and a drag of one marked clip while no other
is marked SHALL be a drag of that clip alone. A drag SHALL still start only from a handle, and a coarse-pointer
scroll that starts anywhere else SHALL scroll the page.

The **group** is every marked clip, from every listed chapter, in page order: the chapters as listed, and in each its
play order. A drop SHALL be one edit. The group SHALL leave the chapters it was in, and SHALL join the chapter it is
dropped in as one run, in its page order, at the place of the drop. The place is a **gap** of that chapter: the line
above one of its clips, or the line after its last clip, or the area of a chapter that plays none. The run SHALL go
before the first clip at or after the gap that is not itself in the group, or at the chapter's end when there is none.
Every clip that is not in the group SHALL keep its order and its chapter. A chapter that loses all its clips SHALL
play none.

Every chapter, the group's own too, is a target of gaps while a group is held:

- the page SHALL show the line at the gap, and for a chapter that plays none its area marked as the target, in the
  own chapter as in another
- no row SHALL move to make room, in any chapter, and no part of the page SHALL change size or place
- a copy of the lifted clip SHALL follow the pointer, naming the number of clips and the target chapter and the
  position the run would start at out of the number of clips that chapter would then play ("3 clips to “Main”,
  starting at position 1 of 4"); within the group's only chapter it SHALL name the position without the chapter
- every held row SHALL be marked as held, by words available to assistive technology and by dimming, and the lifted
  clip's own row SHALL be marked as the clip being moved; no row's position number SHALL change while the group is
  held
- in forced colors, the line and the copy's edge SHALL stay visible

After the drop:

- each moved clip SHALL show the chapter it came from instead of its old position when it changed chapter, and SHALL
  count once as a moved clip in its new chapter's heading and in the save bar, as a clip moved with Move marked to… does;
  within a chapter the page SHALL count the fewest clips that explain the new order, as for any reorder
- a clip that returns to the chapter and place it had when Edit mode opened SHALL count as no move; with no other
  edit, the page SHALL show no unsaved changes
- each clip SHALL keep its cuts and its other per-clip properties, its Cuts panel shown or hidden as it was, and any
  time typed but not added
- Save SHALL write the order as it writes the order after Move marked to…, and Reset, the unsaved-changes question, a
  conflict and Overwrite SHALL treat it as any other edit
- the moved clips SHALL be unmarked, and keyboard focus SHALL be on the lifted clip's handle in its new place, with the
  row's first line fully visible, below the page header and the chapter's heading and above the save bar
- a drop that leaves every chapter's order as it was SHALL change nothing, SHALL leave the marks, and SHALL be
  announced as unchanged

From the keyboard, a held group SHALL be moved through the gaps of every chapter in page order with the Up and Down
arrows, and to the first gap of the next or the previous chapter with Page Down and Page Up, as a clip is moved across
chapters; Escape SHALL cancel. The instructions for a keyboard drag SHALL say, while two or more clips are marked, that
a marked clip moves with all the marked clips.

Every lift, target, drop and cancel SHALL be announced to assistive technology: "Picked up 3 marked clips.", "3 marked
clips are over “Main”, starting at position 1 of 4.", "3 clips moved to “Main”, starting at position 1 of 4.", "3
marked clips dropped, unchanged." and "Move cancelled. 3 marked clips are back where they were." Within the group's
only chapter a target is spoken as "starting at position 2 of 4" without the chapter's name.

No group SHALL be lifted, and a drop SHALL move nothing, while a save is in flight or a move of marked clips is being applied.
A release over a deleted chapter's placeholder SHALL move nothing and SHALL be announced as unchanged. A cancelled
drag SHALL leave the marks. While a pointer holds a group, no other part of the page SHALL show the pointer over it
and the pointer SHALL show that it holds the clips, as for a clip. Under reduced motion the copy SHALL NOT slide between
positions. In a window 320 CSS pixels wide or wider, in both color schemes, no state of a group drag SHALL make the page
scroll horizontally. Dropping a group of 50 clips into another chapter on a page whose chapters play 400 clips SHALL
reach the next painted frame within 150 ms longer than dropping one clip there (the median of five runs, in a Chromium
window 1280 × 900).

#### Scenario: Dragging two marked clips into the chapter above
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4`, drags the handle of `Kvällen/s1710003.mp4` up into `Main` and holds it over the upper half
  of `s1710001.mp4`
- **THEN** a line shows above `s1710001.mp4`, the copy says "2 clips to “Main”, starting at position 1 of 3", the
  two held rows are dimmed and marked as held, and no row has moved
- **WHEN** the operator releases it
- **THEN**
  - `Main` plays `Kvällen/s1710002.mp4`, `Kvällen/s1710003.mp4` and then `s1710001.mp4`, the first two marked as
    coming from `Kvällen`, and its heading says 2 clips moved
  - `Kvällen` plays the new `s1710004.mp4` alone
  - no clip is marked and the line above the chapters shows no count
  - keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`
  - "2 clips moved to “Main”, starting at position 1 of 3." is announced
  - the save bar says that 2 clips moved and that saving adds 1 new clip to `reel.yaml`

#### Scenario: A group from two chapters lands as one run in page order
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `s1710001.mp4` (in `Main`) and
  `Kvällen/s1710003.mp4`, drags the handle of `Kvällen/s1710003.mp4` down, and releases it on the line after the last
  clip of `Kvällen`
- **THEN** `Kvällen` plays `Kvällen/s1710002.mp4`, the new `s1710004.mp4`, `s1710001.mp4` and then
  `Kvällen/s1710003.mp4` (the group in page order: `Main`'s clip first), `Main` plays no clip and shows its area for
  clips, and "2 clips moved to “Kvällen”, starting at position 3 of 4." is announced

#### Scenario: Moving a group within its own chapter
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710003.mp4`, drags the
  handle of `s1710001.mp4` and holds it between `s1710003.mp4` and `s1710004.mp4`
- **THEN** a line shows between those two clips, the copy says "2 clips, starting at position 2 of 4" without a chapter
  name, and no row moved to make room, including `s1710002.mp4`
- **WHEN** the operator releases it
- **THEN** the chapter plays `s1710002.mp4`, `s1710001.mp4`, `s1710003.mp4` and `s1710004.mp4`, the save bar counts
  the fewest clips that explain that order, nothing is marked, and "2 clips moved, starting at position 2 of 4." is
  announced
- **WHEN** the operator saves
- **THEN** `reel.yaml` lists the four clips in that order and no other line of the file changed

#### Scenario: A drop beside the group changes nothing
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710002.mp4` and `s1710003.mp4` and drops them on
  the line between them
- **THEN** the chapter plays what it played, "2 marked clips dropped, unchanged." is announced, the save bar is not
  shown, and both clips are still marked

#### Scenario: Dragging an unmarked clip moves only that clip
- **WHEN** on `2024-06-27 - Grillning med grannar` the operator marks `s1710001.mp4` and `s1710002.mp4`, and drags
  the handle of the unmarked `s1710004.mp4` above `s1710001.mp4`
- **THEN** the chapter plays `s1710004.mp4`, `s1710001.mp4`, `s1710002.mp4` and `s1710003.mp4`, the other rows made
  room while it was dragged as they did before this change, and `s1710001.mp4` and `s1710002.mp4` are still marked

#### Scenario: One marked clip drags as a clip
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks only `Kvällen/s1710003.mp4` and drags its handle
  up into `Main` over the upper half of `s1710001.mp4`
- **THEN** the copy says it goes to `Main` at position 1 of 2 as for any single clip, `Main` plays
  `Kvällen/s1710003.mp4` and then `s1710001.mp4`, and the clip is no longer marked

#### Scenario: A group dragged back leaves nothing to save
- **WHEN** after the first scenario on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4` in `Main` again and drags them back to the line above the new `s1710004.mp4` in `Kvällen`
- **THEN** both chapters play what they played when Edit mode opened, no row is marked as moved, and the page shows no
  unsaved changes

#### Scenario: A group with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, using only the keyboard, the operator marks `Kvällen/s1710002.mp4`
  and `Kvällen/s1710003.mp4`, focuses the handle of `Kvällen/s1710003.mp4`, lifts it with Space, presses Up
  until the gap above `s1710001.mp4` and drops it
- **THEN** "Picked up 2 marked clips." and "2 marked clips are over “Main”, starting at position 1 of 3." were
  announced before "2 clips moved to “Main”, starting at position 1 of 3.", `Main` plays the two clips and then
  `s1710001.mp4`, and keyboard focus is on the handle of `Kvällen/s1710003.mp4` in `Main`
- **WHEN** the operator repeats the lift on the marked clips in `Main` and presses Escape
- **THEN** "Move cancelled. 2 marked clips are back where they were." is announced, the order is unchanged, and the
  clips are still marked

#### Scenario: Page Down takes the group to the next chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` the operator marks `s1710001.mp4` and `Kvällen/s1710003.mp4`, lifts
  `s1710001.mp4` from the keyboard and presses Page Down
- **THEN** "2 marked clips are over “Kvällen”, starting at position 1 of 4." is announced and a line shows above
  `Kvällen/s1710002.mp4`

#### Scenario: No group while a save is in flight
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with two clips marked and an unsaved reorder, the operator presses
  Save and the service has not answered yet
- **THEN** pressing Space on a marked handle lifts nothing and announces nothing, a mouse drag from it moves
  nothing, and every chapter stays as it was

#### Scenario: A group dragged by touch
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, with `Kvällen/s1710002.mp4` and
  `Kvällen/s1710003.mp4` marked, a touch starts on the handle of the first and moves up into `Main` above
  `s1710001.mp4` before it lifts
- **THEN** `Main` plays both clips first, and the page did not scroll horizontally
- **WHEN** a touch starts on a marked clip's name and moves up
- **THEN** the page scrolls and no clip moves

#### Scenario: Reaching a long chapter with a group
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, `Kväll`, the operator marks the
  second chapter's first two clips, lifts one with the pointer and holds it at the window's top edge
- **THEN** the page scrolls up as for one clip ("Edit mode drags clips between chapters"), and releasing the group over
  the upper half of the first chapter's first clip puts both at positions 1 and 2 of 402 there, leaving `Kväll` with 1
  clip

#### Scenario: A held group changes nothing's size
- **WHEN** in a window 320 pixels wide, in the light and in the dark scheme, on `2024-08-20 - Två kapitel - Tjörn`, the
  operator holds the marked `s1710001.mp4` and `Kvällen/s1710003.mp4` over `Kvällen`, between `s1710002.mp4` and the new
  `s1710004.mp4`
- **THEN** every clip row and both chapter panels keep the size and place they had before the drag, the line between
  the two clips is visible beside the copy, no position number changed, and the page does not scroll horizontally

#### Scenario: A group drop is fast
- **WHEN** in a Chromium window 1280 × 900, on an event whose first chapter plays 400 clips and whose second plays 3, the
  operator marks 50 clips of the first chapter and drops them into the second, five times in a fresh Edit mode each
- **THEN** the median time from the release to the next painted frame is at most 150 ms longer than that of dropping
  one unmarked clip from the first chapter into the second

### Requirement: Running times are written to a fixed width and say what they are

Every time the client shows while something moves (the Timeline's readout under its video, the clip player's header,
the Timeline's trim tip and its movie stat) SHALL be written by one formatter, the **clock**, and
SHALL NOT be written in the form that the Cuts panel writes cut times in (`0:01.5`, `0:02.607`), which keeps its own
job: a cut's time, a typed field, a spoken word. The ruler's tick labels and the chapter list's start times do not
move while something plays and keep that form.

**One scale per readout.** A readout SHALL be written to a scale taken from the longest value it can show, not from
the value it shows. Minutes SHALL be zero-padded to the digits of the longest value's minutes (`0:09.50 of 0:39.84`
when the longest is under ten minutes, `09:59.99 of 12:30.00` when it is not), hours SHALL appear in every value of a
readout or in none (none unless the longest is an hour or more), and seconds SHALL always have two digits. The
fraction SHALL have the same number of digits in every value of every readout of that kind, trailing zeros kept:
two (centiseconds) for the Timeline's and the player's readouts and the summary line, three (milliseconds) for the
trim tip, which shows the time a cut will have. A value SHALL be cut down to those digits, never rounded up, so that
a position never reads later than its total. A value above the longest SHALL be shown as the longest. A value that
is not known (the player's length before the browser has read it) SHALL be shown as dashes in the same places
(`-:--.--`), never as `0:00`. A value that is negative or not a number SHALL NOT be written: it is an error, never a
made-up time.

**Constant width.** A running time SHALL occupy a width that depends on its scale and on nothing else: it SHALL have
a reserved width in the width of a digit of its monospace face, digits of equal width, and its text SHALL stay on
one line. While a clip plays, while the playhead is scrubbed or stepped, and when the playhead passes from one clip
into another, no readout's width and no readout's left edge SHALL change, and nothing after a readout on its line
SHALL move. A readout's width MAY change when its scale does, which only the set of clips (a Prepare job that ends,
a clip that goes) or the clip's length being read can cause, and SHALL NOT change at any other moment.

**Words.** A readout SHALL say what each number is in words that stay on the screen: the Timeline's reads `Clip
0:00.96 of 0:39.84 · Event 1:02.40 of 2:29.76`, the first pair being the time in the clip the playhead is in and that
clip's length, the second the time in the whole timeline (the clips end to end, before cuts) and its length. The
clip pair's scale SHALL be that of the event's longest clip and the event pair's that of the whole timeline's length,
so that passing from a 9-second clip into a 40-second one changes no width. The clip player's header reads `Clip
0:20.48 of 0:20.64`. The Timeline's movie stat reads `Movie 3:20.00 · footage 3:45.00 · cuts −0:33.00 · cards +0:08.00`, every time to the scale of the longest of them. The trim tip reads the time alone, to the scale of its clip's length, and the words it adds when
the edge snaps SHALL NOT move that time.

**The name.** The clip's name in the Timeline's readout SHALL be shown on one line and, when it does not fit, SHALL be
cut with an ellipsis and keep its whole text as its tooltip; it SHALL NOT wrap and SHALL NOT move a number. On a
window 390 CSS pixels wide the name MAY take its own line, and the numbers SHALL then keep their widths.

**Both schemes, every width.** The readouts SHALL meet the page's contrast in the light and the dark scheme and SHALL
NOT make the page scroll horizontally from 320 CSS pixels up.

#### Scenario: Crossing a clip does not move the line
- **WHEN** the Timeline of an event whose clips are 9.00 s, 40.00 s and 6.02 s (55.02 s in all) plays from 0:08 into
  the second clip
- **THEN** the readout reads `Clip 0:08.20 of 0:09.00 · Event 0:08.20 of 0:55.02`, then `Clip 0:00.10 of 0:40.00 ·
  Event 0:09.10 of 0:55.02`, and the width of every time and the left edge of both pairs are the same in the two
  samples

#### Scenario: Nine seconds to ten
- **WHEN** the playhead of a 12-second clip goes from `0:09.99` to `0:10.00`
- **THEN** the readout's text is `0:09.99` and `0:10.00` in cells of one width, and nothing after it moves

#### Scenario: A long name is cut, not pushed
- **WHEN** the clip the playhead is in is named `IMG_20240627_201530_BURST042_final_v2.mp4` and the window is 390
  pixels wide
- **THEN** the name is on one line ending in an ellipsis, its tooltip is the whole name, the numbers have their usual
  widths, and the page does not scroll horizontally

#### Scenario: A cell in the trim tip
- **WHEN** the operator drags a handle on a 6.02 s clip across `0:01.25` and `0:01.30`
- **THEN** the tip reads `0:01.250` then `0:01.300`, the same width, and when the edge snaps the snap words appear
  without moving the time

#### Scenario: The length is not read yet
- **WHEN** a clip player has just opened and the browser has not read the clip
- **THEN** the header reads `Clip 0:00.00 of -:--.--`, with the time in cells as wide as they will be, and when the
  length is read it reads `Clip 0:00.00 of 0:06.02` with no change in the first cell's width

#### Scenario: A spoken form is not padded
- **WHEN** a screen reader reads the Timeline's slider at the moment of the first scenario's second sample
- **THEN** its value text reads `s1710002.mp4, clip 0:00.1 of 0:40; event 0:09.1 of 0:55.02`, in the Cuts panel's
  form, and the visible readout is not the slider's value

### Requirement: A selected title card opens its inspector in Edit mode
Activating a title card in Edit mode, from its block on the Timeline (a press, Enter or Space) or from the **Edit Titlecard** button in its chapter's header bar, SHALL open that card's inspector in a modal dialog, over the page wherever the operator has scrolled to, named "Title card
for <chapter>" (the opening card: "Opening title card"). There SHALL be one card editor and one place for it, for the opening card and every chapter's alike: the inspector SHALL NOT
also be rendered in the page below the Timeline's track. The app's existing dialog component (`ui/Dialog`, the native `<dialog>`
with `showModal()`) SHALL be reused. The dialog SHALL hold the tabs, the Name and the card fields that "The title card dialog holds every name and every title-card setting" lists, and one live preview; the preview SHALL sit above the fields where the dialog is 600 CSS pixels
wide or narrower and beside them where it is wider. Opening it SHALL NOT scroll the page, SHALL NOT move the track, the ruler,
the playhead or the Timeline's video, and the page behind it SHALL NOT scroll while it is open. Focus SHALL move to the dialog's first
field when it opens and SHALL return to the button or block that opened it when it closes, unless the operator has already moved it to
a control outside the dialog. Escape and a Close button SHALL close it, as SHALL a "Done" button; none of them SHALL discard an
edit. Edits SHALL go into the page's one draft, as every other Edit-mode change does: the dialog has no Save or Cancel of its
own, and the save bar counts a changed card ("1 title card changed") while the dialog is open and after it is closed. The card's selection highlight, on its block and on its chapter's button, SHALL stay while the dialog is open and after it closes. Activating
a card that is already selected SHALL open the dialog again. At 600 CSS pixels wide or narrower the dialog SHALL be a full-screen
sheet. The dialog's Length field and the Timeline's length drag SHALL be two ways to edit the one draft `duration`. Every
control SHALL have a visible label and an accessible name, work with the keyboard alone, and be at least 44 × 44 CSS pixels where
the primary pointer is coarse. The dialog SHALL fit from 320 to 1280 CSS pixels wide without a horizontal page scroll, follow the
colour scheme, and add no motion when the operator prefers reduced motion. In the read view nothing changes: selecting a card
there opens no dialog and writes nothing.

#### Scenario: Opening from a row far down the page
- **WHEN** the page is scrolled to a chapter far below the Timeline and the operator presses that chapter's "Edit title card for <chapter>"
- **THEN** the dialog opens named "Title card for <chapter>" on "This title card" with focus in its Name field, the page has not
  scrolled, and the chapter's button and its block show as selected

#### Scenario: Selecting a card opens it
- **WHEN** the operator presses the title card block of the chapter `Reception` on the Timeline
- **THEN** the dialog opens named "Title card for Reception", the block and the chapter's Edit Titlecard button show as selected, and the keyboard reaches
  every field in reading order

#### Scenario: Editing and finishing
- **WHEN** the operator changes the title, sees the preview update, and presses Done
- **THEN** the dialog is closed, focus is back on the button that opened it, the save bar shows the change
  ("1 title card changed"), and Save writes `reel.yaml`

#### Scenario: Escape closes and keeps the edit
- **WHEN** the operator has typed a title and presses Escape
- **THEN** the dialog closes, focus returns to the button or block that opened it, the draft holds the edit, and the card stays selected

#### Scenario: Reopening the selected card
- **WHEN** the dialog has been closed and the operator presses the still-selected card again
- **THEN** the dialog opens again with the draft's values

#### Scenario: A narrow window
- **WHEN** the window is 390 CSS pixels wide, and again 320, and a card is open
- **THEN** the dialog is a full-screen sheet with the preview above the fields, nothing scrolls horizontally, and the page behind
  it does not scroll

#### Scenario: Selecting never moves the track
- **WHEN** a card is opened from its block and from its chapter's button, at 1280 and 390 px
- **THEN** the track's bounding box is the same before and after each and no inspector is in the page below it

#### Scenario: Switching and closing
- **WHEN** the dialog is open and the operator closes it, then presses another card
- **THEN** the other card's dialog opens, and the draft holds every edit made on both

### Requirement: A card's fields are overrides that follow the event style until set
Each of the inspector's fields SHALL be a per-card override. An unset field SHALL show the value it inherits as a
muted placeholder with the words "Event style" (the engine-resolved value the event detail reports), and a set field
SHALL offer **Use event style**, which clears it so the card inherits again. The title field SHALL, while empty, show
as its placeholder the chapter's current name in the draft, and for the opening card the event's current title in the
draft (the title read from the folder name when the draft's is blank), and SHALL say "Follows the chapter name"
(opening card: "Follows the event title"). Typing a title SHALL NOT change the chapter's name, the movie's chapter list
or the event's title. The subtitle SHALL be free text of any length that keeps its line breaks. The background SHALL be
a choice of Black or Video, with the words "Black: text on black, before the chapter" and "Video: text over the start of the
chapter's first clip" under them. The font SHALL be chosen from the service's font list (`GET /api/v1/fonts`) by its
display name, the default marked, and SHALL name no family the list does not hold (beside the families, one entry "Event style" clears the override). Title size and subtitle size SHALL be
numbers, the text colour a colour input with its hex value, the position a choice of Top, Center and Bottom. The page
SHALL apply none of the engine's value rules itself: it sends what was typed and shows the service's refusal. When the
event detail could not resolve a card (`card: null`), the inspector SHALL show the reported `card_error`, SHALL show
inherited values as unknown, and SHALL still let the operator set fields. The page SHALL NOT show a default of its own
for a value the service did not report.

#### Scenario: The background helper copy
- **WHEN** the inspector is open
- **THEN** the Background control's words are "Black: text on black, before the chapter" and "Video: text over the start of the chapter's first clip"

#### Scenario: Empty title follows the chapter name
- **WHEN** the chapter `Dag 2` has no title override and the operator renames it to `Dag två` in the draft
- **THEN** its inspector's title field is empty with the placeholder `Dag två` and "Follows the chapter name"

#### Scenario: A card title does not rename the chapter
- **WHEN** the operator types `Mottagningen` into the title of the chapter `Reception`'s card
- **THEN** the chapter is still `Reception` in the chapter list, in the Timeline's chapter band and in announcements,
  and the card's block shows `Mottagningen`

#### Scenario: Use event style clears an override
- **WHEN** the operator sets the text colour of a card and presses **Use event style** beside it
- **THEN** the colour input shows the inherited value muted with "Event style", and the draft holds no colour for the card

#### Scenario: The opening card is separate from the event title
- **WHEN** the operator types `Sommaren` into the opening card's title
- **THEN** the metadata form's Title field is unchanged, and clearing the opening card's title makes it follow the
  event's title again

#### Scenario: An unresolvable card is said so
- **WHEN** the detail reports `card_error: "look.title_card.position: …"` for a chapter
- **THEN** the inspector shows that message, its inherited values read "unknown", no default is shown in their place,
  and the operator can still set the position

#### Scenario: Fonts come from the list
- **WHEN** the inspector opens and the font list has nine entries
- **THEN** the font control offers those nine by display name, the default marked, and no other family (plus the "Event style" entry)

### Requirement: The preview is drawn by the service while the operator edits
The inspector SHALL show a preview of the draft card by posting it to `POST /api/v1/events/{event_id}/title-card/preview`
and showing the PNG the service returns, so that what is previewed is what the renderer draws. The request SHALL carry
the draft: the chapter's name, the non-empty overrides, the draft event title for the opening card, and, for a chapter
other than the opening one with no title override, the draft chapter name as the title, so a renamed or added chapter
previews as it will render. The page SHALL wait for about 250 ms without an edit before sending, SHALL cancel the request
it has superseded, SHALL ignore a response to a request it has superseded, and SHALL keep showing the previous image
(marked as updating) until the new one is ready, never an empty box between two images. For a Black card the image is
shown as is. For a Video card the page SHALL show the returned text over a frame of the clip the card sits over, taken
from the clip's thumbnail, and SHALL say that the frame is from the clip and not its exact start; with no clip that
plays or no thumbnail it SHALL show the text over a neutral pattern and say there is no clip frame. A title over 200 or a
subtitle over 400 characters SHALL not be sent: the field says it is too long to preview, the text is kept, and it still
saves. A failure SHALL be said in words by its cause at the preview, with the previous image kept: the field the service
names (400), the bound (422), the cause (502), that the service is busy and a retry (503, once after `Retry-After`), and
that the service did not answer. The preview SHALL be a labelled image with a text alternative that gives the card's
title and subtitle, and a change of its state SHALL be announced politely, not on every image.

#### Scenario: Editing previews after a pause
- **WHEN** the operator types a subtitle one character at a time faster than 250 ms apart
- **THEN** one request is sent after the last keystroke, carrying the whole subtitle, and the earlier pending
  requests were never sent

#### Scenario: A superseded request is dropped
- **WHEN** a request is in flight and the operator changes the font
- **THEN** the first request is cancelled, its response is never shown, and the image shown is the one for the new font

#### Scenario: The previous image stays while loading
- **WHEN** a request is pending
- **THEN** the previous image is still visible and marked as updating, and when the new image arrives it replaces it

#### Scenario: A video card over a frame of its clip
- **WHEN** the operator sets Video for a chapter whose first clip plays
- **THEN** the preview shows the returned text over that clip's thumbnail frame with the words that the frame is from
  the clip and not its exact start, and no request for a video file is made

#### Scenario: No clip to show it over
- **WHEN** a Video card's chapter has no clip that plays
- **THEN** the text is shown over a neutral pattern with "No clip frame to show it over"

#### Scenario: An over-long text is kept but not previewed
- **WHEN** the operator pastes a 450-character subtitle
- **THEN** no request is sent for it, the subtitle field says it is too long to preview (limit 400), the text stays,
  and the card still saves with it

#### Scenario: A refusal is said at the field
- **WHEN** the service answers 400 naming `card.title_font_size`
- **THEN** the size field shows the service's message, the preview keeps its previous image, and editing the size
  retires the message

#### Scenario: A busy service
- **WHEN** the service answers 503 with `Retry-After: 2`
- **THEN** the preview says the service is busy, retries once after two seconds, and says so in words if that fails too

### Requirement: Title-card edits are edits of the same draft
A change to a card in the inspector SHALL change the editor's draft, the one every other Edit-mode change shares, and
SHALL be saved, counted, guarded and undone as any other edit. There SHALL be no second save path. A card SHALL count
as changed when its overrides differ from the ones read, so an edit set back to its read value counts as nothing.
Pressing Save SHALL send the same whole-document `PUT` under `If-Match` that every edit sends, with a `card` only for
chapters whose card changed (a card left with no override sent as `{}`, which removes it) and no `card` for the others,
so an unchanged card is never rewritten. The save bar SHALL say how many cards changed ("1 title card changed",
"2 title cards changed") beside its other counts. Undo for a card, and Reset, SHALL restore the overrides as read.
Leaving Edit mode with an unsaved card change SHALL ask first, as for any unsaved edit. A card SHALL follow its chapter:
renaming a chapter in the draft SHALL keep its card edits, deleting a chapter SHALL drop them with it, and undoing the
deletion SHALL bring them back. A refusal by the service (400) SHALL show in the save bar's problem list and at the
field of the card it names, and SHALL keep the draft.

#### Scenario: The save bar counts cards
- **WHEN** the operator changes the subtitle of one card and the font of another
- **THEN** the save bar says "2 title cards changed" and enables Save

#### Scenario: Editing back to the read value is no change
- **WHEN** the operator changes a card's position and then sets it back to the one read
- **THEN** the save bar counts no card and, with nothing else changed, Save is unavailable

#### Scenario: Only the changed card is written
- **WHEN** an event with three chapters is saved after the operator changed one card
- **THEN** the write is one `PUT` under `If-Match`, its `chapters` carry a `card` for the one changed chapter and none
  for the other two, and `reel.yaml` afterwards differs only in that card

#### Scenario: Clearing every override removes the card
- **WHEN** the operator presses **Use event style** on every field of a chapter that had a card, and saves
- **THEN** the write carries `card: {}` for it and `reel.yaml` has no card for that chapter

#### Scenario: A rename carries the card
- **WHEN** the operator edits a card's subtitle and renames its chapter, then saves
- **THEN** the persisted renamed chapter holds the new subtitle and the old name no longer exists

#### Scenario: Undo and Reset
- **WHEN** the operator changes a card's font and presses Reset
- **THEN** the card's overrides are as read and the inspector shows the read font

#### Scenario: Leaving with a card changed
- **WHEN** the operator has changed a card and follows a link out of Edit mode
- **THEN** the page asks before leaving, as for any unsaved edit

#### Scenario: A refusal at the field
- **WHEN** the service answers a save with 400 naming `card.font_family` of the chapter `Dag 2`
- **THEN** the problem list names the chapter and the field, the font control of that chapter's inspector shows the
  message, and the draft is kept

#### Scenario: The default is not rewritten
- **WHEN** the operator opens an inspector, changes nothing, and saves another edit
- **THEN** the opened card's chapter has no `card` in the write

### Requirement: Edit mode edits the event's card style in one place

The title card dialog's second tab, **All title cards in this event**, SHALL edit the event-wide title-card style, the `look.title_card` of
`reel.yaml`, and it is the only place that does: the page SHALL NOT hold a "Card style for this event" section or any other control for it. It SHALL offer these
fields: font family, title size, subtitle size, text color, position (center, top or bottom), default length, and default background (Black or
Video), each with a **Use project default** button. The font family SHALL be chosen from the families the service lists (`GET /api/v1/fonts`), each shown
in its own face or with the service's preview image, never typed. A field the style leaves unset SHALL say that
it follows the project default, with the value in force when the page read it as a placeholder; when the
operator clears a value that the saved style set, the field SHALL say "Project default" without a number,
because the page does not know it, and SHALL NOT show a value it does not have. Every field SHALL be reachable
and operable with the keyboard, and have a label, and a tap area of at least 44 by 44 pixels while the
primary pointer is coarse. The tab SHALL be disabled with Edit mode's other edit controls while a save is in flight.

The dialog's one live preview, drawn by the service from the draft (not the saved) style and the card being edited, SHALL show an
event-style edit at once, under the same rules as the card preview: debounced, a stale request cancelled, the previous image kept while the next
loads, and a failure told in words. When the service cannot resolve the saved event style (the event detail's `title_card_error`), the dialog SHALL open on this tab
showing that error in words and the stored values as typed, so the operator can correct them.

#### Scenario: Setting a font and a colour for every card
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn` in Edit mode, the operator opens "Edit title card for Main", chooses the tab "All title cards in this event",
  picks the font `DM Serif Display` and sets the text color `#FFD700`
- **THEN** the preview shows the opening card in that face and color before anything is saved, and the save
  bar says the card style changed

#### Scenario: An unset field follows the project default
- **WHEN** the event's `reel.yaml` sets no `look.title_card` and the operator opens the tab
- **THEN** each field shows the project default value as a placeholder and none shows as set

#### Scenario: Use project default clears a field
- **WHEN** the saved style sets a title size of 80 and the operator presses Use project default on it
- **THEN** the field says "Project default" and the save bar counts the change

#### Scenario: A cleared value does not invent a default
- **WHEN** the saved style sets a title size of 80 and the operator clears the field
- **THEN** the field says "Project default" with no number, the preview shows the card without the size, and
  the save bar counts the change

#### Scenario: A style the engine refuses is told and correctable
- **WHEN** the event's `look.title_card.position` is hand-written as `middle` and the operator opens a title card dialog
- **THEN** the dialog opens on "All title cards in this event" showing the service's refusal naming `position` and `middle` in the field, and
  choosing `center` clears the refusal

#### Scenario: The control is usable at a narrow width
- **WHEN** the window is 320 pixels wide and the operator opens the tab
- **THEN** every field is fully visible without horizontal page scroll

### Requirement: A card says which fields it overrides and falls back to the event style

Each title card in Edit mode SHALL say in its dialog, above its fields, which of its fields it overrides: the names of the fields its draft sets ("Overrides font, color"), or "Uses the event
style" when it sets none. A field a card sets equal to the event style SHALL still count as an override. The
inspector's "Use event style" on a field SHALL remove that card's override of it, so the field then follows
the draft event style, not only the saved one, and the dialog's field and the card's preview SHALL show
the result without a save. A card's override of a field SHALL win over the event style, which SHALL win over
the project default.

#### Scenario: A card names its overrides
- **WHEN** the chapter `Kvällen` sets only `font_family` and `text_color` on its card
- **THEN** its dialog says "Overrides font, color" and the opening card's dialog says "Uses the event style"

#### Scenario: Use event style follows the draft style
- **WHEN** the event style's text color is edited to `#00FF00` and not saved, and the operator presses "Use event
  style" on the text color of `Kvällen`'s card
- **THEN** the inspector shows `#00FF00` as that card's color and its preview is drawn in it, and the card no
  longer lists color among its overrides

#### Scenario: A card's override beats a changed event style
- **WHEN** `Kvällen`'s card overrides the font and the operator changes the event style's font
- **THEN** `Kvällen`'s preview keeps its own font and every card without that override shows the new one

### Requirement: Saving the card style writes only look.title_card

A change to the event's card style SHALL be an edit of the same draft as every other, counted in the save bar
as "Card style changed", undone by Undo and Reset, and left in the draft by an edit that returns a field to
the value it was read with (no change to save). Saving SHALL write the editorial document as read with only
`look.title_card` changed: a field the operator set takes its value, a field the operator cleared is removed,
the keys of `look.title_card` the control does not edit and every other key of `look` go back as read, and
`look.title_card` is removed when the operator cleared its last field. A save that changes nothing in the
style SHALL send `look` as read. The same save SHALL carry the card overrides of the chapters by the card
inspector's rules. The service's refusal of a field, answered with a problem naming `look.title_card.<field>`,
SHALL be shown at that field and keep the operator's edits, like any failed save. No other control of this
change writes `reel.yaml`, and the page SHALL NOT keep any look editor from an earlier version of the page.

#### Scenario: Only the style changes
- **WHEN** on an event whose `reel.yaml` sets `look.title_card.fade_in: 0.5`, the operator sets the style's
  text color to `#FFFFFF` and saves
- **THEN** `reel.yaml` has `look.title_card` with `fade_in: 0.5` and `text_color: "#FFFFFF"`, and its metadata,
  chapters, per-clip properties and ignored clips are as before

#### Scenario: Clearing the last field removes the sub-map
- **WHEN** `look.title_card` holds only `font_family` and the operator clears it and saves
- **THEN** the saved `reel.yaml` has no `look.title_card`

#### Scenario: A style edited and put back is no change
- **WHEN** the operator changes the title size from 80 to 90 and back to 80
- **THEN** the save bar shows no changes and offers no Save

#### Scenario: The engine's refusal is shown at the field
- **WHEN** the operator enters a title size of `big` and saves, and the service answers 400 naming
  `look.title_card.title_font_size`
- **THEN** the message appears at the title size field, the operator's edits are kept, and `reel.yaml` is
  unchanged

### Requirement: Edit mode switches the event's title cards On or Off

The title card dialog's second tab, "All title cards in this event", SHALL hold, once for the event, a control named "Title cards" with the choices On and Off, and the page SHALL NOT hold a Title cards section of its own. The control SHALL be showing the
state a render would have: the draft's choice, else the event detail's `title_cards.enabled`, with the words that say
where that came from ("Default", "Set in this event", "Set by the project's config.yaml"). Choosing Off SHALL make
the draft's `look.decorators` the event's own list without `title`, keeping the other names and their order, and the
empty list when the event has none; choosing On SHALL make it a list with `title` first and the other names kept. The
choice SHALL be an edit of the same draft as every other: counted in the save bar ("Title cards turned off", "Title
cards turned on"), undone by Undo and Reset, and no change when put back to the state read. A save SHALL write the
document as read with only `look.decorators` (and `look.title_card`, by its own rule) changed and every other key of
`look` as read, and SHALL NOT remove the key unless the draft is back to the state read. Turning cards Off SHALL
keep every card's edits in the draft. When the source is `project`, the control SHALL say that saving writes this
event's own list over the project's. When `title_cards` is null (`look.decorators` is not a list), the control SHALL
be disabled and show the service's `title_cards_error`. The control SHALL be disabled with the other edit controls while
a save is in flight, operable by keyboard, labelled, at least 44 by 44 CSS pixels where the primary pointer is coarse,
legible in both colour schemes from 320 to 1280 px wide without horizontal scroll, and SHALL make the Timeline, the dialog's preview and the movie's length follow the choice before any save. While cards are Off the dialog SHALL say "Title cards are off for this event" above its tabs and keep every card field editable.

#### Scenario: Turning cards off
- **WHEN** on an event with no `look.decorators` the operator chooses Off and saves
- **THEN** one `PUT` under `If-Match` writes `look.decorators: []` and nothing else changes, and the next read says `title_cards: {enabled: false, source: "event"}`

#### Scenario: Other decorators are kept
- **WHEN** the event's `look.decorators` is `[chapter, title]`, the operator chooses Off, and saves
- **THEN** the written list is `[chapter]`

#### Scenario: Back to the state read is no change
- **WHEN** the operator chooses Off and then On on an event that read `source: "default"`
- **THEN** the save bar shows no change and `look` goes back exactly as read

#### Scenario: Turning cards back on
- **WHEN** the event read `look.decorators: []`, the operator chooses On and saves
- **THEN** the written list is `[title]`

#### Scenario: Card edits survive Off
- **WHEN** the operator changes a card's subtitle, chooses Off, and then On
- **THEN** the subtitle edit is still in the draft

#### Scenario: A list that is not a list
- **WHEN** the detail has `title_cards: null` and `title_cards_error` naming `look.decorators`
- **THEN** the control is disabled and shows that text

### Requirement: A choice that follows an inherited value shows it pressed in a muted style

Every segmented choice of the card dialog's "This title card" tab (Background, Position) and of the dialog's "All title cards in this event" tab (Default background, Position) that has no value of its own SHALL show the value it inherits as pressed, in a muted style
distinct from a chosen value and not by colour alone (a dashed outline), with the words "(event style)" for a
card's field and "(project default)" for the event style's, and SHALL expose it to assistive technology as the
inherited value, not as chosen. Pressing the inherited option SHALL set the field to that value as an override;
**Use event style** SHALL return it to the muted state. While the inherited value is unknown (`card: null`, or a
saved value the operator cleared) no option SHALL be shown pressed and the words SHALL say it is unknown.

#### Scenario: A card that follows the event style
- **WHEN** the event style's background is Video and a card sets none
- **THEN** Video is shown pressed in the muted style with "(event style)", Black is not, and the draft holds no background for the card

#### Scenario: Pressing the inherited option
- **WHEN** the operator presses the muted Video
- **THEN** the card sets Video as its own override (it is listed among its overrides) and the style is the chosen look

#### Scenario: The event style's own control
- **WHEN** the event's `look.title_card` sets no position and the project default is Center
- **THEN** the tab's Position shows Center muted with "(project default)"

#### Scenario: Unknown inherited value
- **WHEN** the operator cleared a saved size and the background of a card with `card: null`
- **THEN** no option is shown pressed and the words say the inherited value is unknown

### Requirement: The opening card's subtitle shows its default and can be set to none
The dialog's Subtitle field for the opening card SHALL, while the draft's subtitle is unset, show the resolved
card's `default_subtitle` as its placeholder with the words "Default" (lines joined by " / ", for example
`Default: 2024-08-20 / Plats: Tjörn`), and when that is empty `No subtitle`. The page SHALL NOT compose the default. The
field SHALL offer **No subtitle**, which sets the subtitle to the empty string, and **Use default**, which unsets it
(the key is removed on Save); the field SHALL keep the empty string and unset apart in the draft, in the dirty state
and in what Save and the preview send, so an explicit `""` is written as `""` and an unset subtitle is not written. A
subtitle typed into the field SHALL replace the default. For a chapter other than the opening one the field keeps its
"Event style: no subtitle" behaviour and offers neither button, since it has no default. The Timeline's card readout SHALL show the effective subtitle (`card.subtitle` of the detail, or the draft's
value when edited) and "No subtitle" only when it is empty. This requirement takes precedence over the sentence "The
subtitle SHALL be free text of any length that keeps its line breaks" only in adding the default; that sentence still holds.

#### Scenario: The default is the placeholder
- **WHEN** the opening card is selected for an event dated 2024-08-20 at `Tjörn` with no subtitle key
- **THEN** the Subtitle field is empty with the placeholder `Default: 2024-08-20 / Plats: Tjörn`, and **Use default** is not offered

#### Scenario: No subtitle writes the empty string
- **WHEN** the operator presses **No subtitle** and Saves
- **THEN** the request carries `subtitle: ""` for the default chapter, the field shows the placeholder `No subtitle` with **Use default** offered, and the Timeline's card readout says "No subtitle"

#### Scenario: Use default removes the key
- **WHEN** the card's saved subtitle is `""` and the operator presses **Use default** and Saves
- **THEN** the request carries no subtitle for that card, and the Timeline's card readout shows the date and place again

#### Scenario: Typing replaces the default
- **WHEN** the operator types `Hos mormor`
- **THEN** the preview and the Timeline's card readout show `Hos mormor` and no date or place

#### Scenario: A chapter card has no default controls
- **WHEN** a chapter other than the opening one is selected
- **THEN** the Subtitle field shows its existing placeholder and neither **No subtitle** nor **Use default** is offered

#### Scenario: The preview sends the empty string
- **WHEN** the draft's subtitle is `""`
- **THEN** the preview request carries `subtitle: ""`, and the image has no subtitle line

### Requirement: The event list and the event page show the event's poster
Each event of the event list SHALL show its poster as a cover image taken from `GET …/events/{id}/poster.jpg`,
and the event page's header SHALL show the same image larger. The image SHALL load lazily, SHALL sit in a box of
a fixed aspect ratio (16:9) that is reserved before it loads so that no row or header shifts when it arrives, and
SHALL have alternative text naming the event (and, on the page, whether the frame is the default or a chosen one).
An event the poster endpoint answers 404 for, or whose image fails to load, SHALL show a placeholder in the same
box that says there is no poster; a failure SHALL NOT hide the row, break the page or be shown by color alone.
Reading the images SHALL NOT change state, and a page of events SHALL NOT ask for more than the images in view
and near it. The cover SHALL keep its aspect at 390 px width and in both color schemes, the list's text SHALL stay
readable beside it, and the page SHALL announce nothing for a cover that loads.

#### Scenario: A list of events shows their covers
- **WHEN** the list shows events with and without a playable clip
- **THEN** the first show a cover image with alt text naming the event, the others a placeholder of the same
  size, and the rows do not move as the images load

#### Scenario: Images below the fold are not fetched
- **WHEN** the list is opened with more events than fit the window
- **THEN** only the covers in or near the viewport are requested until the page is scrolled

#### Scenario: A failed image does not break the row
- **WHEN** the poster endpoint answers 502 for one event
- **THEN** that row shows the placeholder, and the row's text and actions are all present

#### Scenario: The page header shows the poster
- **WHEN** an event with a chosen frame is opened
- **THEN** the header shows its image and the words "Chosen frame"; an event without one says "Default: first clip"

### Requirement: Edit mode chooses the event's poster on the Timeline
In Edit mode the Timeline SHALL offer **Use as poster**. Pressed, it SHALL set the draft's poster to the clip
under the playhead and the playhead's time in that clip, in seconds to the millisecond and before the clip's cuts
(a time inside a cut is allowed), and SHALL take the frame the Timeline's video shows as the draft picture of
the poster area. It SHALL be unavailable when the playhead is outside every clip (the playhead
never rests on a title-card block: it stays on footage), when the video has no decoded frame at the playhead, and while a save or a move of marked clips is pending. The reason SHALL be given in words as the button's tooltip and
accessible description and, when the operator presses the button while it cannot act, in a tip that takes no room in
the Timeline's toolbar and once through the Timeline's live region; it SHALL NOT be written as text beside the button,
and a reason that comes and goes (a seek's frame loading) SHALL NOT move any control of the toolbar (`event-timeline`,
"The Timeline's toolbar keeps its place while the Timeline seeks, loads and plays"). A snapshot that fails SHALL
change nothing and say so. Keyboard focus SHALL stay on the button and the
change SHALL be announced once.

Edit mode's **poster area** (a Poster panel above the Timeline; the page header's cover belongs to the read view) SHALL say what the poster is:
**Default: first clip** when the draft has no poster, **Chosen frame** when it has one as saved, and **Chosen
frame, not saved** for a draft that differs from the saved one. **Use default** SHALL remove the draft's poster and
SHALL be unavailable when there is none. The poster is a part of the one draft: Save writes `poster` with the
existing editorial write (`poster: {clip, at}`, or `null` to remove, and nothing when the poster was not
changed), Undo of the poster and Reset restore the saved one, an unmodified draft writes nothing, the save bar
says "poster changed", and Unsaved edits are never discarded silently. After a save the poster area shows the
image from the poster endpoint, not the snapshot. A poster whose clip the draft removes, moves out of the event
or ignores SHALL be marked in the poster area ("this clip does not play, the default is used") and SHALL NOT be
rewritten silently. A chosen clip that the detail reports with a `poster_note` SHALL show that note. Clips whose
rotation the page shows turned (`rotate`) SHALL be snapshotted and shown turned.

#### Scenario: Use as poster sets the draft from the playhead
- **WHEN** the playhead is at 0:12.500 of `s1710002.mp4` in Edit mode and Use as poster is pressed
- **THEN** the draft's poster is that clip at 12.5 s, the poster area shows that frame as "Chosen frame, not
  saved", the save bar says "Poster changed", and focus is still on the button

#### Scenario: Saving writes the poster once
- **WHEN** the draft's poster is changed and Save is pressed
- **THEN** one `PUT …/reel` carries `poster: {clip, at}`, a save of an unchanged poster carries none, and the poster
  area then shows the served image as "Chosen frame"

#### Scenario: Use default removes the chosen frame
- **WHEN** an event with a saved poster is edited, Use default is pressed and Save is pressed
- **THEN** the write carries `poster: null`, the area says "Default: first clip", and Reset before Save restores
  the saved poster

#### Scenario: The button is off where it cannot act
- **WHEN** a save is pending, an open clip preview holds the page's video, or the video has no decoded frame
- **THEN** Use as poster is unavailable, its tooltip and accessible description say why, and pressing it shows the
  reason in a tip and says it once, with no text added to the toolbar and no control moved

#### Scenario: A rotated clip is chosen turned
- **WHEN** the clip is shown turned and Use as poster is pressed on it
- **THEN** the draft picture is turned the same way

#### Scenario: The same behavior in Chrome and Firefox, in both schemes, at 1280 and 390 px
- **WHEN** the steps above are run in Chrome and in Firefox, light and dark, at 1280 and 390 px width
- **THEN** each has the same words and results, nothing overflows, and every control is large enough to touch

#### Scenario: Reading does not write
- **WHEN** the list, the page and Edit mode are opened and the Timeline's playhead is moved without pressing Use as
  poster
- **THEN** no request other than reads is sent

### Requirement: Edit mode moves the marked clips to a chapter

While the event lists more than one chapter, a deleted one aside, the line above the chapters that offers Clear marks
and Rotate marked left and right ("Edit mode marks clips to move together") SHALL also offer **Move marked to…**: a
group named by those words, holding a chapter picker and a button named **Move**. No chapter SHALL offer a Move clips
button, and the page SHALL NOT open a dialog to pick clips: the clips to move are the ones marked, and the page SHALL
NOT have a Pick all or a Pick marked control. When the event lists one chapter, the control SHALL NOT be offered, as no
other chapter has a place for a clip.

The picker SHALL be a native `select` named "Chapter to move the marked clips to". It SHALL list every chapter the
page lists, a deleted one aside, in the order the page lists them, each by the name its heading shows (the event's own
chapter as `Main`, as its heading reads), and it SHALL start on a first option that is no chapter, "Choose a chapter".
A chosen chapter that is then deleted SHALL return the picker to that option. Renaming a chapter SHALL change its name
in the list.

**Move** SHALL be `aria-disabled` (never `disabled`, as the busy-control rule says) and SHALL give its reason in words, named by `aria-describedby` and offered as the button's tooltip, and shown in the toolbar's one reason line ("The marks line is one aligned unit") only once Move is pressed in that state, in each of these states, and press nothing. No line of the reason SHALL be shown while Move is not pressed:

- no clip is marked: "Mark a clip to move it."
- no chapter is chosen: "Choose a chapter."
- a save is in flight, or a move of marked clips is pending: "Unavailable while saving."

Pressing Move with a clip marked and a chapter chosen SHALL be one edit, made by the group move of "Dragging a marked
clip moves the whole marked group" and not by logic of its own: the group is every marked clip, from every listed
chapter, in page order; it SHALL leave the chapters it was in and SHALL join the end of the chosen chapter as one run, in
page order. A marked clip that is already in the chosen chapter joins that run too, so the run is the last clips of the
chapter. Every clip that is not marked SHALL keep its order and its chapter. A chapter that loses all its clips SHALL
play none. A clip SHALL NOT be put back after its old predecessors when it returns to the chapter it was in when Edit
mode opened: a move to the end is the same edit as a drop at the end of that chapter.

After the move:

- every moved clip SHALL be unmarked (the group is every marked clip, so no mark is left)
- the move SHALL be announced once, politely, with the number of clips and the chosen chapter's name, "3 clips moved to
  “Dag 2”." or "1 clip moved to “Main”."
- each moved clip that changed chapter SHALL show, in its row, the chapter it came from instead of its old position,
  and SHALL count once as a moved clip in its new chapter's heading and in the save bar, as a clip dragged does; within
  a chapter, the page SHALL count the fewest clips that explain the new order
- a clip SHALL keep its cuts and its other per-clip properties, its Cuts panel shown or hidden as it was, any time
  typed but not added, and its preview open as "Edit mode previews a clip on request" says
- Save SHALL write the order as it writes a drag's, and Reset, the unsaved-changes question, a conflict and Overwrite
  SHALL treat the move as any other edit
- keyboard focus SHALL stay on Move, the chosen chapter SHALL stay chosen, and no row SHALL be scrolled out of the
  operator's view by the move

A move that changes no chapter's order (the marked clips already are the last of the chosen chapter, in page order)
SHALL leave the draft, the marks and the save bar as they are and SHALL be announced as "Nothing moved." A clip that
has no mark (a missing clip, an ignored clip, a removed one) is never moved by this control, as it is never marked.

Move marked to… SHALL stay beside dragging. A drag of a marked clip takes the marked group to the place where it is
dropped (see "Dragging a marked clip moves the whole marked group"), from the keyboard on a handle too; Move marked
to… takes the same group, always to the end of one chosen chapter, with a keyboard, a screen reader or a touch screen
and with no drag at all. A clip's Move up and Move down still never take it into another chapter (see "The event page
reorders clips within a chapter").

On a coarse pointer the picker and Move SHALL each take a tap anywhere in an area at least 44 CSS pixels tall that does
not overlap another control's. The group SHALL wrap in a window 320 CSS pixels wide, on its own row under the marks line's other controls, its label above the picker and the picker beside Move, without a horizontal page scroll, in both color schemes. The group SHALL keep its place and its
height whether or not a clip is marked, so that marking the first clip moves no row, and its focus ring SHALL be
visible in both color schemes and in forced colors. Reading a screen SHALL NOT change what is chosen.

#### Scenario: Moving two marked clips from different chapters to Test
- **WHEN** in Edit mode on an event whose chapters are `Main`, `Kvällen` and `Test`, the operator marks `Main/a.mp4`
  and `Kvällen/c.mp4`, chooses `Test` in the picker and presses Move
- **THEN**
  - `Test` plays what it played before and then `a.mp4` and `c.mp4`, last, in that page order
  - neither clip is marked and the line above the chapters shows no count
  - "2 clips moved to “Test”." was announced once
  - the save bar says that 2 clips moved
  - the picker still shows `Test`, and keyboard focus is on Move
- **WHEN** the operator presses Save
- **THEN** `reel.yaml` lists `a.mp4` and `c.mp4` last in `Test`'s clips and nothing else changed

#### Scenario: Move says why it is unavailable
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, with no clip marked
- **THEN** Move is `aria-disabled` and not `disabled`, and no line of words is beside it, "Mark a clip to move it." is its description and tooltip, and pressing it shows those words in the toolbar's reason line
- **WHEN** the operator marks `Kvällen/s1710002.mp4`
- **THEN** its description reads "Choose a chapter."
- **WHEN** the operator chooses `Main` and presses Move
- **THEN** `s1710002.mp4` is last in `Main`, marked as coming from `Kvällen`, unmarked, and "1 clip moved to “Main”." is
  announced

#### Scenario: Moving with the keyboard only
- **WHEN** using only the keyboard on `2024-08-20 - Två kapitel - Tjörn`, the operator marks `Kvällen/s1710002.mp4` with
  Space, tabs to the picker, chooses `Main` with the arrow keys, tabs to Move and presses Enter
- **THEN** `s1710002.mp4` is last in `Main`, "1 clip moved to “Main”." was announced, and keyboard focus is on Move

#### Scenario: The marked clips already are last
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves `Kvällen/s1710002.mp4` to `Main` and marks it
  again, chooses `Main` and presses Move
- **THEN** "Nothing moved." is announced, the clip is still marked, and the save bar counts what it counted before

#### Scenario: One chapter offers no move
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, whose clips are all in one chapter
- **THEN** the line above the chapters offers no Move marked to…, and no chapter offers a Move clips button

#### Scenario: The old per-chapter control is gone
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, in Chrome and in Firefox
- **THEN** the words "Move clips" appear nowhere on the page, in any chapter's controls, dialogs or accessible names

#### Scenario: Move waits for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a clip marked and a chapter chosen, the operator presses Save
  and the service has not answered yet, and then presses Move
- **THEN** Move is `aria-disabled` and says "Unavailable while saving.", and nothing moves

#### Scenario: A deleted chapter leaves the picker
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator chooses `Kvällen` in the picker and then deletes `Kvällen`
- **THEN** the picker lists `Main` only and shows "Choose a chapter"

#### Scenario: The control fits a phone
- **WHEN** on a touch screen 320 pixels wide, in the light and in the dark scheme, on
  `2024-08-20 - Två kapitel - Tjörn`, the operator looks at the line above the chapters
- **THEN** the picker and Move are on a line of their own, each takes a tap in an area at least 44 pixels tall, none
  overlaps another, and the page does not scroll horizontally

### Requirement: The title card dialog holds every name and every title-card setting

The title card dialog ("A selected title card opens its inspector in Edit mode") SHALL be the one place in Edit mode for a chapter's
name and for every title-card setting, the same for the event's own chapter and for every other chapter. The page SHALL hold no
other control for a name, a card or the event's card style. The dialog SHALL have one live preview of the card being edited, drawn by the
service from the draft ("The preview is drawn by the service while the operator edits"), visible whichever tab is shown, and two tabs in a
tab list named "Title card settings" (`role="tablist"`, each tab `role="tab"` with `aria-selected`, its panel `role="tabpanel"` named
by the tab). Left and Right Arrow, Home and End SHALL move between the tabs, and Tab SHALL move from the tab list into the shown panel.
Two tabs, not two stacked groups, keep the dialog the height of one tab and keep the preview in view while the operator edits either.

- **"This title card"** SHALL be shown when the dialog opens, except as the last bullet says. In this order it SHALL hold: the **Name**
  ("Edit mode adds, renames, reorders and deletes chapters"); **Card title (overrides the name)** with a **Use the name** button, only for a card
  whose draft has its own `title`, and no control that adds one; the **Subtitle**; **Background**; **Font**; **Title size**;
  **Subtitle size**; **Text colour**; **Position**; and **Length**. Each field but the Name SHALL have **Use event style** ("A card's fields are
  overrides that follow the event style until set"). The card's heading follows the Name: a card with no title of its own draws the name
  (the event's title for the opening card), and the preview, the dialog's name and the Timeline's blocks follow it as it is typed.
  Use the name SHALL remove the card's own title from the draft; the key goes from `reel.yaml` on Save.
- **Length** SHALL be a number field in seconds named "Length of the title card (seconds)", showing the card's length, else the event's default
  length as its placeholder with the words "Event style". It SHALL take whole tenths, from 0.5 to 60, and for a card over video no more than
  the first span of the chapter's anchor clip that the draft's cuts keep ("A black card's drag moves everything after it, and a video card's is bounded by its clip"), the limits the
  length drag has; a card whose limit makes it not adjustable SHALL say why and take no value. A typed length outside the limits, or not a number, SHALL be
  refused in words under the field that name the limits (never rounded to a value the operator did not type), SHALL keep the text, mark the field invalid and leave the draft as it was; an accepted one SHALL be written
  to the draft as it is typed, as the drag's release is, and a length equal to the one read SHALL count as no change. The field and the Timeline's length drag
  are two ways to edit the same `duration`: after a drag, the field shows the new length, and a length typed here is drawn on the Timeline
  at once. Use event style SHALL remove the card's `duration`.
- **"All title cards in this event"** SHALL hold the event-wide style fields of "Edit mode edits the event's card style in one place" and the
  Title cards On or Off switch of "Edit mode switches the event's title cards On or Off". Its edits SHALL change the preview of the card shown.
- A tab that holds a problem the operator cannot see, a refusal by the service at one of its fields or a field the dialog refused, SHALL say so in its label ("All title
  cards in this event, 1 problem"), and the dialog SHALL open on the first tab that holds one when the service's last answer named one.
- Every field SHALL work with the keyboard alone, have a visible label, be at least 44 × 44 CSS pixels where the primary pointer is coarse, and fit 320 to
  1280 CSS pixels without a horizontal page scroll in both colour schemes.

Every edit in either tab SHALL go into the page's one draft and be counted, saved, guarded and undone as every other Edit-mode edit: a
name as "chapter renamed" or "Title", a card as "title card changed", the style as "Card style changed", the switch as "Title cards turned off" or "Title cards
turned on". Save SHALL send the same whole-document `PUT` under `If-Match` that every edit sends, with only the keys of what changed.

#### Scenario: Two tabs, the name first
- **WHEN** the operator presses "Edit title card for Kvällen" on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the dialog opens on the tab "This title card" whose first field is the Name, named "Name of chapter Kvällen" and holding `Kvällen`,
  followed by Subtitle, Background, Font, Title size, Subtitle size, Text colour, Position and Length; the preview is shown above them at 390 px and beside
  them at 1280 px; and the tab "All title cards in this event" is one Arrow key away

#### Scenario: Switching tabs keeps the preview and the draft
- **WHEN** the operator types `Dag 2` in the Name field, moves to "All title cards in this event" with the Right Arrow, picks the text
  color `#FFD700`, and moves back
- **THEN** the preview was shown throughout and now shows `Dag 2` in `#FFD700`, the Name field still holds `Dag 2`, and the save bar says
  "1 chapter renamed" and "Card style changed"

#### Scenario: A card with its own title
- **WHEN** the chapter `Kvällen`'s card in `reel.yaml` has `title: Kväll på stranden` and the operator opens its dialog
- **THEN** the dialog shows the Name (`Kvällen`) and then "Card title (overrides the name)" holding `Kväll på stranden` with "Use the name"
- **WHEN** the operator presses Use the name
- **THEN** the field is gone, the preview draws `Kvällen`, and the next Save removes `title` from that card

#### Scenario: A card with no title of its own offers none to add
- **WHEN** the operator opens the dialog of a chapter whose card sets no `title`
- **THEN** there is no "Card title" field and no control that would add one, and the card's heading is the Name

#### Scenario: The same dialog for Main
- **WHEN** the operator opens "Edit title card for Main"
- **THEN** it has the same tabs and fields as a chapter's, its Name field is named "Title of the event" and edits the event's title, and its heading
  and the preview follow it

#### Scenario: Typing a length
- **WHEN** the operator types `6` in the Length field of a black card of 4.0 s
- **THEN** the draft holds `duration: 6.0`, the Timeline's card block is 6.0 s long, and the save bar counts one changed card
- **WHEN** the operator types `0.3`, and then `90`
- **THEN** each is refused under the field in words that name the limits 0.5 s and 60 s, the text is kept, and the card stays at 6.0 s

#### Scenario: A video card's length is bounded by its clip
- **WHEN** a card over video lies over a clip whose first kept span is 3.4 s and the operator types `5`
- **THEN** the field refuses it in words that name 3.4 s as the longest, and the draft is unchanged

#### Scenario: The drag and the field are one edit
- **WHEN** the operator drags a card's end edge to 6.0 s, releases, and opens the card's dialog
- **THEN** the Length field holds 6.0
- **WHEN** the operator types `7` and closes the dialog
- **THEN** the card block on the Timeline is 7.0 s long and Save writes `card.duration: 7.0`

#### Scenario: A problem in the other tab is shown on the tab
- **WHEN** the service answers a Save with 400 naming `look.title_card.title_font_size` and the operator opens a dialog
- **THEN** the dialog opens on "All title cards in this event", whose label says "1 problem", with the message at the field

#### Scenario: Nothing else on the page edits a name or a card
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`, in light and dark at 1280 and 390 px
- **THEN** the page holds no pencil, no click-to-rename title, no "Main title card" line, no card row, no "Card style for this event" section and no Title cards
  section; each chapter's section is its header bar and its clips

#### Scenario: One save writes the keys that changed
- **WHEN** the operator renames `Kvällen` to `Kväll`, edits the opening card's event title, sets the style's position to Top and turns the cards Off, in the dialogs, and saves
- **THEN** one `PUT` under `If-Match` is sent whose chapter is named `Kväll`, whose metadata title is the new title, whose `look.title_card.position` is `top`
  and whose `look.decorators` is `[]`, and no other key differs from `reel.yaml` as read

### Requirement: The marks line is one aligned unit

The line above the chapters that shows how clips are marked and offers Clear marks, Rotate marked left, Rotate marked right and Move marked
to… ("Edit mode marks clips to move together", "Edit mode moves the marked clips to a chapter") SHALL read as one calm, aligned toolbar from 320 to
1280 CSS pixels wide, in both colour schemes and for both kinds of pointer.

- **One control height.** Clear marks, both Rotate buttons, Move and the chapter picker SHALL have the same height, one size for the line (at least 44 CSS pixels
  where the primary pointer is coarse), and the same corner radius.
- **One axis.** Controls in a row SHALL have their vertical centres within 1 CSS pixel of each other, and a text beside them (the Help toggle, the count of marked clips, the label "Move marked to…") SHALL be centred on the same axis. No item SHALL sit higher or lower than
  its neighbours.
- **Consistent gaps.** The gap between two controls of a group, between two groups and between two rows SHALL each be one value, the same in every row and at every width.
- **Rows.** The first row SHALL hold the Clips help's toggle and, at its end, the count and Clear marks; the second SHALL hold Rotate marked left and right, then the Move marked to… group (label, picker,
  Move) where it fits; the reason SHALL be shown only after Move is pressed while it is unavailable, as one muted line below the controls, starting at the toolbar's left edge, and SHALL go when the marks, the chosen chapter or the save state change the reason. The reason SHALL NOT float beside Move. Marking or unmarking a clip SHALL move no row of the toolbar other than that line.
- **Narrow windows.** Where the toolbar does not fit a row, it SHALL wrap by whole groups: the Move group goes on a row of its own with the label above, the picker filling the
  row beside Move; Rotate marked left and right share a row where they fit and otherwise take a row each at the same width. Every wrapped row SHALL keep the one height and the
  one axis, and nothing SHALL scroll horizontally at 320 CSS pixels.
- The names, descriptions, `aria-disabled` states and reasons of the controls ("Edit mode moves the marked clips to a chapter") are unchanged.

#### Scenario: Controls in a row share a height and an axis
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` at 1280 px, light and dark, with one clip marked
- **THEN** the bounding boxes of Clear marks, Rotate marked left, Rotate marked right, the chapter picker and Move have the same height, and in each row the vertical centres of
  its controls, and of the label "Move marked to…" and the count, differ by at most 1 px

#### Scenario: The reason is one muted line below
- **WHEN** no clip is marked
- **THEN** no reason line is shown, and Move's description is "Mark a clip to move it."
- **WHEN** the operator presses Move
- **THEN** "Mark a clip to move it." is one muted line below the controls, aligned to the toolbar's left edge, and not beside Move
- **WHEN** the operator marks a clip
- **THEN** no row of the toolbar other than that line and no chapter below it moves, and the line says "Choose a chapter."

#### Scenario: The toolbar wraps in aligned rows
- **WHEN** the window is 390 px wide and again 320 px, light and dark
- **THEN** the Move group is on its own row with the label above and the picker beside Move, every row's controls share one height and one centre line (within 1 px), the
  reason line, when shown, is below them, and the page does not scroll horizontally

### Requirement: Each explanation sits behind a Help toggle of its section

The event page, in the read view and in Edit mode, SHALL keep instructional and explanatory text out of sight until asked for, and SHALL keep in sight every text that reports a state or needs an action. Each of these sections SHALL have **one** Help toggle in its header, a button named "Help" with an information icon: **Details** (Edit mode), **Poster** (Edit mode), **Timeline** (the read view and Edit mode), **Clips** (Edit mode: the row above the chapters, which holds the marks line) and the **Title cards** tab of the title card dialog. A section with no such text SHALL have no toggle.

The toggle SHALL be a `button` with `aria-expanded` and `aria-controls` naming its panel, operable by Enter and Space, with a target at least 44 CSS pixels high and wide, and with a visible focus ring. Pressed, it SHALL show the panel under the header: a calm, muted block that is not an alert, holds the section's explanations as paragraphs, and moves nothing above it. The panel SHALL stay in the document when closed (`hidden`), so that a control it describes keeps its `aria-describedby`. Closed is the default. Each section's state SHALL be kept per section (not per event) in `localStorage`, read when the section mounts, written when the toggle is pressed, and every access SHALL be guarded: a browser that refuses storage, or throws, SHALL leave the toggle working for the page visit, closed at the start, and SHALL show no error. The Timeline's state SHALL be one state for both modes.

Every text of these classes SHALL be in a panel and SHALL NOT be shown as a line of its own: the Details form's lead ("What reel.yaml says…", "Save writes these to reel.yaml…"), the Poster's "Pick the frame on the Timeline…", the Timeline's note that cards fade ("The Timeline fades a card…"), the note that dismissed suggestions return on reload, the cut fields' hint ("Enter takes a time; Escape puts the old one back"; the fields keep it as their `aria-describedby`), the Clips instructions ("Drag a clip by its handle…", "Mark clips with the box…", "The event's own chapter: …", "Ignored clips are not played and cannot be moved", "A missing clip is not on disk…"), the command that analyses an event (`auto-reel analyze <root>`, then Refresh), and the title cards tab's lead ("Every title card of this event follows these…"). The text SHALL be the same words as before. The classes that SHALL stay visible are: a refusal, an error or a warning; an unsaved or pending change and what saving will add ("Saving adds 2 new clips to reel.yaml"); a count ("2 clips marked", "1 ignored clip, not played"); the state words of a clip, a chapter, the poster and the render; a field's inherited-value hint; a reason an unavailable control gives (see "Edit mode moves the marked clips to a chapter"); the icon legend of the analysis lane; and the empty states of a chapter. Controls, fields, their names and what pressing them does SHALL NOT change.

#### Scenario: A section's help is closed, opens and closes
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn` with nothing stored
- **THEN** the Details, Poster, Timeline and Clips sections each show a Help button with `aria-expanded="false"` and no explanation is visible
- **WHEN** the operator presses the Clips Help button, by mouse and again by keyboard
- **THEN** `aria-expanded` is `true` and "Drag a clip by its handle…" is visible under the header; pressing it again hides the panel, which stays in the document

#### Scenario: The state persists across a reload
- **WHEN** the operator opens the Timeline help, reloads the page, and then opens the same event in the read view
- **THEN** the Timeline help is open in both, and the other sections' help is closed

#### Scenario: Storage that throws
- **WHEN** `localStorage` throws on every access
- **THEN** every Help button works for the page visit, starts closed, and no error is shown

#### Scenario: Action and state stay visible
- **WHEN** an event with a missing clip, with an unsaved edit and with an event that needs a render is opened in Edit mode with every help closed
- **THEN** the missing clip's status, the "Needs render" state with its reason, the save bar's unsaved changes and the marks count are visible, and the explanations are not

#### Scenario: Fewer paragraphs of explanation
- **WHEN** `2024-08-20 - Två kapitel - Tjörn` is opened in the read view and in Edit mode, in Chrome and in Firefox, light and dark, at 1280 and 390 px, with every help closed
- **THEN** the number of visible paragraphs of instructional text is lower than before the change in each, the numbers are reported, and nothing overflows horizontally

#### Scenario: A toggle is large enough to touch
- **WHEN** any Help button is measured at 390 px
- **THEN** it is at least 44 CSS pixels high and wide, and it has an accessible name that names its section

### Requirement: Edit mode's clip list draws only the rows near the view, without moving the page

Edit mode SHALL let the browser skip drawing the clip rows that are far out of view (CSS `content-visibility: auto`
on each row), giving every row not yet drawn a block size close to a drawn row's and every row once drawn the size it
was drawn at, so that the page's scroll height and the place of what is in view do not change as rows come into view.
In a clip list narrower than 20.25rem, where a row's own controls are wider than the row, rows SHALL be drawn as
before (not skipped), so that no control is cut off. Every row SHALL stay in the page while skipped: focusable by Tab, read by assistive technology, found by the browser's
find in page, a drop target for a drag, and reachable by keyboard reorder.

Rows coming into view SHALL NOT move the page: while the operator scrolls the list, the row at the top of the view SHALL
keep its place to within 1 px apart from the scroll itself. The page's scroll height after the whole list has been
scrolled through once SHALL differ from its height on opening by at most 5 %.

Nothing a row draws outside its own box SHALL be cut off by the skipping: the row's focus ring, the drop indicator and
the dragged row SHALL look as they did before, in the light and the dark scheme, at 1280 and at 390 px. Dragging a clip
(with the pointer and by keyboard), marking clips and moving the marked ones, Move up and Move down, rotating a clip, the
card dialog and the save bar SHALL work as before; after a drop, every row SHALL be drawn and take clicks where it
now is, never where it was.

#### Scenario: Scrolling a 400-clip list moves nothing
- **WHEN** Edit mode shows an event of 400 clips in one chapter at 1280 and at 390 px, and the page is scrolled from
  the top to the bottom in steps of half a view, waiting two frames after each step
- **THEN** after each step the top row in view is where the step put it to within 1 px, and the scroll height at the
  end differs from the scroll height on opening by at most 5 %

#### Scenario: A drag to the end of a long list lands where it was shown
- **WHEN** the operator drags the first clip of a 400-clip chapter to the last slot of the last chapter, the page
  scrolling on its own across rows that were never drawn
- **THEN** the clip is dropped in the slot the drop indicator showed, and the draft's order says so

#### Scenario: Keyboard reorder far down the list
- **WHEN** the operator moves a clip down the list by keyboard past rows that were never drawn
- **THEN** the moved row keeps keyboard focus, is in view with its focus ring whole, and the announcement names its new
  place

#### Scenario: A skipped row is still found
- **WHEN** the operator tabs through the list, or searches the page for the name of the 390th clip
- **THEN** each row is reached in order and the 390th clip's row is scrolled into view and shown

#### Scenario: Nothing is cut off
- **WHEN** a row has keyboard focus, a drag shows its drop indicator, or a clip is being dragged, in the light and the
  dark scheme at 1280 and at 390 px
- **THEN** the focus ring, the indicator and the dragged row are drawn whole, as on the page before this change

#### Scenario: A moved row takes its clicks where it is
- **WHEN** two marked clips are dragged to the top of another chapter in Chrome, so that the rows below them move down
- **THEN** a click on a moved row's mark box marks that row, and no other row's control takes the click
