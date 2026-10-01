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
- counts of its clips, their total size, and its new, missing and ignored clips

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
page SHALL name them in a warning above the chapters.

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
  chapter and ignores the root clip `s1710004.mp4`, as a hand edit or a render's adoption of that NEW clip
  leaves it
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

#### Scenario: A slow list read
- **WHEN** the events list response takes two seconds
- **THEN** during those seconds the list shows placeholder rows and the announced message "Scanning events…",
  and no event from an earlier read

#### Scenario: A slow event read
- **WHEN** the operator opens `2024-09-01 - Sommarlov` and its read takes two seconds
- **THEN** during those seconds the page shows its heading, placeholder rows and the announced message
  "Reading event…"

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
"Edit mode drags clips between chapters") or moved with its chapter's Move clips control (see "Edit mode moves
clips to another chapter"). A missing clip's drag SHALL stop at its own chapter's edge. Among the clips
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
- **THEN** the control says that it is unavailable, nothing moves, and `Main` is unchanged: only a drag or Move
  clips takes a clip into another chapter

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
  jobs it carries.
- A job the client knew as queued or running that is absent from a new snapshot ended while the connection
  was down. The client SHALL read that job once from the service and show its real terminal state. It MUST
  NOT keep showing that job as active, and MUST NOT guess its outcome.
- After any close, including a normal one, the client SHALL reconnect:
  - after a randomized delay that grows with each failed attempt, capped at about 30 seconds
  - the delay resets only once a frame has arrived on the new connection
  - it reconnects at once when the browser reports it is back online
- The app header SHALL show the connection's state in words: live, connecting, or reconnecting. While live,
  it SHALL show how many jobs are rendering and how many are queued, leaving out a count that is zero.
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

#### Scenario: A lost connection says so
- **WHEN** the service stops answering while the app is open
- **THEN** the header shows that the client is reconnecting, without job counts, and it becomes live again,
  with no reload, once the service is back

### Requirement: An event's page schedules its render

An event's page SHALL offer, as explicit controls that name what they do:

- a **Render** control when the event needs a render, has no queued or running job, lists no clip that is
  missing from disk, and the page is not in Edit mode
- when the event is up to date, has no queued or running job, lists no clip that is missing from disk, and
  the page is not in Edit mode: its up-to-date state plus a secondary **Render anyway** control, which asks
  for confirmation before it forces a render

While the page is in Edit mode, it SHALL offer neither control and SHALL instead say that the edits must be
saved, or Edit mode left, before rendering: a render reads the saved `reel.yaml`, not the unsaved edits. A
queued or running job's progress and its Cancel control stay offered in Edit mode.

While the event lists a clip that `reel.yaml` names but that is missing from disk, and the page is not in
Edit mode, the page SHALL offer neither control, because a render fails on a missing clip that it plays.
This holds for every missing clip, including one that `reel.yaml` excludes and that a render would skip,
since the page's read does not say which missing clips are excluded. The page SHALL instead say, in words,
that the clip is missing from disk and that it must be restored, or removed in Edit mode, before rendering.
For one missing clip the words SHALL name it; for several they SHALL give their number. A queued or running
job's progress and its Cancel control stay offered.

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
- **any other answer, or none:** the page says the render was not queued, with the status it received or
  that the service is not reachable. It MUST NOT name a cause the answer does not carry; a server error
  without a problem body is not reported as a database failure.

The page MUST tell these outcomes apart by the published status and conflict kind, not by the problem's
prose. Only an event page that shows the event's render state offers these controls; a page whose read
failed offers none.

Render anyway's confirmation asks about an event that is up to date and has no queued or running job. While
it is open and no enqueue request is in flight, if the page would no longer offer Render anyway (a queued or
running job for the event reaches the page, the event no longer reads as up to date, or a missing clip now
holds the render back), the dialog SHALL close by itself and send nothing. Whenever a
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

#### Scenario: An excluded missing clip still holds Render back
- **WHEN** the operator opens `2024-09-03 - Utesluten`, whose `reel.yaml` lists the missing `borta.mp4` and
  excludes it
- **THEN** the page offers neither Render nor Render anyway, and says that `borta.mp4` is missing from disk
  and to restore it, or remove it in Edit mode

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

### Requirement: A render's progress is shown live

Wherever a job is shown for an event, the client SHALL show the newest job it knows for that event. That is
the live state when the connection carries one, and otherwise the latest job the last read returned. For
one and the same job:

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
job's event directory. A row that needs a render, has no queued or running job, and lists no clip that is
missing from disk SHALL offer a compact **Render** control, whose accessible name names the event ("Render"
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

A row that needs a render, has no queued or running job, but lists a clip that is missing from disk SHALL
NOT offer Render, for the same reason as the event's page. In its place, the row SHALL say, in words with an
icon, that missing clips block its render. The row's count of missing clips stays shown.

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
mode makes takes its place, as an operator-started read.

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
- **THEN** the page does not re-read and the unsaved changes stay; once Edit mode ends, the page re-reads
  and shows the event as up to date

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
its row shows it. Outside Edit mode, and in Edit mode for a clip that offers no Cuts control (a missing,
removed or ignored clip), the thumbnail SHALL NOT be focusable. In Edit mode, the thumbnail of a clip that
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
- **THEN** in the read view no thumbnail is focusable
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

In a window 390 CSS pixels wide, the thumbnail SHALL stay in the clip's row beside its facts, without
horizontal scroll, and no fact of a row SHALL overlap another.

#### Scenario: A clip whose frame cannot be read says "No preview"
- **WHEN** the operator opens `2024-10-05 - Trasig`, whose only clip `trasig.mp4` is an empty file
- **THEN** the row shows the "No preview" placeholder with its icon, its status and facts read as before, the
  page shows no alert or toast about it, and the service received exactly one thumbnail request for
  `trasig.mp4`

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
page because, held, it would hide the editor, a notification MAY cover a control just above the bar, such as
the last clip row's; it still SHALL NOT overlap the bar.

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
- the Move clips dialog
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
  stays on disk.

For every other reason, the page SHALL show the reason's words alone, as the list does. That includes a
movie file that is missing from disk.

The words the page adds for a reason SHALL come from a mapping defined over the generated types' union of
staleness reasons, in the same way as the reasons' own words. When a reason is added, the client's
type-check then fails until it is decided whether the page says more about it. Neither screen SHALL name a
movie file that the service's response does not carry. The verdict and the render region SHALL name no movie
file. The one place the event's page names its movie file is its "Movie" section, which takes the name from the
movie route's own answer (see "The event page plays the event's rendered movie"). In this case that is the old
name.

#### Scenario: The page of a renamed event
- **WHEN** the title of `2024-06-27 - Grillning med grannar` was changed after its last render, its movie is
  still on disk under the old name, and the operator opens its page in a window 390 pixels wide
- **THEN** the page says it needs a render, "edited since last render, movie name changed", and, on a line
  of its own, "The next render saves the movie under its new name. The movie under its old name stays on
  disk."
- **AND** the render region names no movie file, the "Movie" section names the movie under its old name
  `2024-06-27 - Grillning med Grannar.mp4`, and the page does not scroll horizontally, in a window 390 or 320
  pixels wide and in either color scheme

#### Scenario: The list keeps the short words
- **WHEN** the operator opens the event list in a window 1280 pixels wide
- **THEN** the row of `2024-06-27 - Grillning med grannar` reads "edited since last render, movie name
  changed", and shows no sentence about the next render

#### Scenario: A missing movie gets no note
- **WHEN** the movie of `2024-06-21 - Midsommar - Dalarna` was deleted after its last render, and the
  operator opens its page
- **THEN** the page says it needs a render because the movie file is missing, and adds no sentence about the
  next render

#### Scenario: A new staleness reason fails the build at the page's mapping
- **WHEN** a staleness reason is added to the engine, and the schema and client types are regenerated
- **THEN** the client's type-check fails at the page's mapping until it is decided whether the page says more
  about the new reason

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
- **Rename** SHALL ask for a new name for a chapter. The event's own chapter (the default chapter, whose clips
  are the event folder's) SHALL NOT offer it. That chapter has no name of its own: its title card shows the
  event's title, and clips without a chapter of their own join it. While the event lists other chapters, the
  page SHALL say this beside it.
- **Move up** and **Move down** SHALL move a chapter one place among the chapters, and SHALL be offered only
  while the event lists more than one chapter. After such a move, keyboard focus SHALL stay on the pressed
  control. At either end, the control that cannot move further SHALL say that it is unavailable.
- **Delete** SHALL remove a chapter only once it plays no clip. Its clips must first be moved to another
  chapter, or removed when missing. The event's own chapter can be deleted only when, in addition, it lists no
  ignored clip that the page would list under it again after the save: one from the event folder, or from a
  folder no chapter is named after. Such a clip would bring the chapter back, holding only ignored clips.
  When a chapter cannot be deleted, pressing Delete SHALL change nothing and leave focus on Delete. The page
  SHALL show and announce why the chapter cannot be deleted.

Each chapter SHALL offer only the controls that apply to it. An event that lists one chapter, the event's own,
offers Add chapter and none of the others. The only chapter left, a deleted one aside, SHALL NOT offer Delete,
Move up, Move down or Move clips, so that an event never saves without a chapter.

When the browser's primary pointer is coarse, each of these controls, Add chapter and Undo SHALL take a tap
anywhere in an area of at least 44 × 44 CSS pixels around it that reaches no other control, as every button
does ("Every control is large enough to touch").

A name SHALL be accepted only when both of these hold, once the spaces around it are removed:

- it is not empty
- ignoring case, it differs from the name of every other chapter of the event, including a deleted chapter not
  yet saved, and from `Main`, the name the page shows for the event's own chapter

A refused name SHALL be explained at the name field, which keeps keyboard focus, and nothing SHALL change. The
name saved is the accepted name without the spaces around it. A chapter's name SHALL be described to the
operator as the words on its title card in the movie.

A chapter the page showed when Edit mode opened SHALL, once deleted, stay listed in its place until the edits
are saved, marked as deleted when the edits are saved. It lists none of its clips. Such a chapter offers an **Undo** control that returns it to its place, and keyboard focus SHALL move to that Undo. A
chapter the operator added in this Edit mode and then deletes SHALL simply be gone. A chapter that plays no
clip SHALL say so in Edit mode. It SHALL also say that clips can be dragged into it, or moved into it with
another chapter's Move clips (see "Edit mode drags clips between chapters").

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
  dragged into it or moved into it with Move clips; the first chapter's heading reads `Main` instead of
  `Clips`; keyboard focus is on the new chapter's heading; the addition is announced; and the save bar says
  "1 chapter added"

#### Scenario: A lone chapter offers only Add chapter
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`
- **THEN** its one chapter offers no Rename, Move up, Move down, Move clips or Delete, and the page offers Add
  chapter after it

#### Scenario: A name already taken, or no name, is refused
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator adds a chapter named `kvällen`, then one named
  only with spaces, then one named `main`
- **THEN** each is refused at the name field, which keeps keyboard focus. `kvällen` is refused because a
  chapter called `Kvällen` exists. The blank name is refused because a chapter needs a name. `main` is refused
  because `Main` is the page's name for the event's own chapter. No chapter is added.

#### Scenario: Renaming a chapter
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to ` Kväll på stranden `,
  with spaces around it
- **THEN** the chapter's heading reads `Kväll på stranden`. Keyboard focus is back on its Rename control. The
  rename is announced, and the save bar says that 1 chapter was renamed.

#### Scenario: The event's own chapter keeps no name
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** `Main` offers no Rename and says that it has no name of its own because its title card shows the
  event's title, while `Kvällen` offers Rename

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
- **THEN** `Kvällen vid grillen` offers Rename, but no Delete, Move up, Move down or Move clips, and the save bar
  says that 4 clips moved, 1 chapter was added and 1 chapter deleted

#### Scenario: Chapter controls on a phone
- **WHEN** the operator opens Edit mode on `2024-08-20 - Två kapitel - Tjörn` on a touch screen 320 pixels wide
- **THEN** a tap anywhere in a 44 × 44 pixel area around each of `Kvällen`'s Rename, Move clips, Move up,
  Move down and Delete, and around Add chapter, reaches that control and no other (centred on each, except
  that the areas of Move up and Move down meet at the edge they share, as a clip row's move pair's do), and
  the page does not scroll horizontally

#### Scenario: Chapter controls wait for a save
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, with a rename pending, the operator presses Save, and the
  service has not answered yet
- **THEN** Add chapter and every chapter's Rename, Move up, Move down, Move clips and Delete say that they are
  unavailable, and pressing them changes nothing

### Requirement: Edit mode moves clips to another chapter

While the event lists more than one chapter, a deleted one aside, each chapter SHALL offer **Move clips**. It
SHALL let the operator pick any of the clips the chapter plays that are on disk, and one of the other
chapters, and SHALL move the picked clips there. Two kinds of clip SHALL NOT be offered, and the page SHALL say
why:

- a missing clip, which stays in its chapter until its file is restored or it is removed from `reel.yaml`
- an ignored clip, which is not played

A chapter that plays no clip SHALL say that it has none to move. When exactly one other chapter is listed, it
SHALL be chosen already. A **Pick all** control SHALL pick every clip offered at once, or clear them all, and
SHALL show that it is mixed while only some are picked.

The moved clips SHALL join the end of the chosen chapter's play order, in the order they had. The one
exception is a clip that returns to the chapter it was in when Edit mode opened. It SHALL go right after
whichever of the clips that came before it then comes last in that chapter's play order now, or first when
none of them is still there. So clips moved to another chapter and back, with no move in between, leave
nothing to save.

After the move:

- keyboard focus SHALL be on the Move clips control that was used
- the move SHALL be announced with the number of clips and the chosen chapter's name
- each moved clip SHALL show, in its row, the chapter it came from, instead of its old position
- it SHALL count once as a moved clip, both in its new chapter's heading and in the save bar

A clip moved to another chapter keeps its per-clip properties. Asking to move with no clip picked, or with no
chapter chosen, SHALL say which is missing, move keyboard focus to it, and move nothing. Cancelling, or
pressing Escape, SHALL move nothing and SHALL return focus to Move clips.

Move clips SHALL stay offered beside dragging. A drag takes one clip into another chapter, to the place where
it is dropped (see "Edit mode drags clips between chapters"). Move clips moves any number of picked clips at
once. A clip's Move up and Move down still never take it into another chapter (see "The event page reorders
clips within a chapter").

#### Scenario: Moving two clips to Main
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Kvällen`, picks
  `s1710002.mp4` and `s1710003.mp4`, and moves them to `Main`
- **THEN**
  - `Main` plays `s1710001.mp4`, `Kvällen/s1710002.mp4` and `Kvällen/s1710003.mp4`, the last two marked as
    coming from `Kvällen`, and its heading says 2 clips moved
  - `Kvällen` plays `s1710004.mp4` alone, and its heading counts no clip moved
  - keyboard focus is on `Kvällen`'s Move clips
  - "2 clips moved to Main" is announced
  - the save bar says that 2 clips moved

#### Scenario: Moving a clip with the keyboard only
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, using only the keyboard, the operator activates Move clips on
  `Kvällen`
- **THEN** a dialog opens, named "Move clips from “Kvällen”", with keyboard focus on the box of `s1710002.mp4`.
  It lists `s1710002.mp4`, `s1710003.mp4` and the new `s1710004.mp4`, and offers `Main`, already chosen as the
  only other chapter.
- **WHEN** the operator checks that box with Space, then moves focus to the dialog's button that moves the
  clips, and presses Enter
- **THEN** the dialog closes, `Kvällen/s1710002.mp4` is last in `Main`, and keyboard focus is back on
  `Kvällen`'s Move clips

#### Scenario: Moving clips back leaves nothing to save
- **WHEN** after moving `s1710002.mp4` and `s1710003.mp4` from `Kvällen` to `Main` on
  `2024-08-20 - Två kapitel - Tjörn`, the operator moves both back to `Kvällen` with `Main`'s Move clips
- **THEN** `Kvällen` plays `s1710002.mp4`, `s1710003.mp4` and `s1710004.mp4` as read, and the page shows no
  unsaved changes

#### Scenario: Asking to move nothing
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, after adding a chapter `Morgon`, the operator opens Move clips
  on `Kvällen` and asks to move without picking a clip
- **THEN** the dialog stays open and says at the clips that one must be picked, with keyboard focus on the
  first clip's box
- **WHEN** the operator picks `s1710002.mp4` and asks again
- **THEN** the dialog says at the chapters that one must be chosen, with keyboard focus on the first chapter's
  choice, and nothing has moved

#### Scenario: Ignored and missing clips are not offered
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Main`
- **THEN** the dialog lists only `s1710001.mp4`, not the ignored `s1710004.mp4`
- **WHEN** on `2024-09-01 - Sommarlov`, after adding a chapter `Morgon`, the operator opens Move clips on `Main`
- **THEN** the dialog lists `s1710002.mp4` and `s1710004.mp4`, not the missing `borttagen.mp4`, and says that a
  missing clip stays in its chapter until its file is restored or it is removed

#### Scenario: Picking clips by touch
- **WHEN** on a touch screen 390 pixels wide, on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips
  on `Kvällen`
- **THEN** each clip's box and each chapter's choice takes a tap anywhere in a row at least 44 pixels tall and
  as wide as the dialog's list, the rows do not overlap, and the dialog fits the window without scrolling the
  page horizontally

#### Scenario: Picking every clip at once
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Kvällen` and checks Pick all
- **THEN** all three clips are picked and the dialog says 3 of 3 picked
- **WHEN** the operator then clears one clip
- **THEN** Pick all shows that it is mixed, and checking it again picks all three; checking it once more picks
  none

#### Scenario: Escape moves nothing
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Move clips on `Kvällen`, picks
  `s1710002.mp4`, and presses Escape
- **THEN** the dialog closes, both chapters are as they were, and keyboard focus is on `Kvällen`'s Move clips

### Requirement: Edit mode says what a chapter's name means for clips added later

A clip that appears in an event's folder after its `reel.yaml` exists joins, at the next render, the chapter
named exactly after the folder it is in, or the event's own chapter when no chapter has that name. So a
chapter's name decides where clips added to that folder later go. Edit mode SHALL say so wherever an edit
changes that. It SHALL say it in the name dialog, as the name is typed, and beside the chapter after the edit,
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

A folder counts only while it holds a clip on disk. The page SHALL compare a name with a folder's exactly, as
the render does. A name that differs from a folder's only in case attracts nothing from that folder, and the
page SHALL say so as for any other name.

#### Scenario: Renaming a chapter named after its folder
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator opens Rename on `Kvällen` and types `Kväll`
- **THEN** before the rename is confirmed, the dialog says that no chapter will be named after the folder
  `Kvällen`, so clips added to it later will join `Main`. After it is confirmed, the chapter `Kväll` says the
  same.

#### Scenario: A name that differs from the folder's only in case
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator renames `Kvällen` to `kvällen`
- **THEN** the rename is accepted, and the page says that no chapter will be named after the folder
  `Kvällen`, so clips added to it later will join `Main`

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
- **THEN** the dialog and then the chapter say that its 1 ignored clip will be listed under `Main`. After
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
clip's start, and may have a reason. In Edit mode, every included or new clip (a clip on disk that a chapter
lists, or will list once the edits are saved) SHALL offer a **Cuts** control. The control SHALL say how many
cuts the clip has and, when it has any, how much time they cut out. Pressing it SHALL show or hide a panel
under the clip's row and SHALL leave keyboard focus on the control. The control SHALL say to assistive
technology whether the panel is shown, and SHALL name the clip as its row names it. In the keyboard order, the
Cuts control SHALL come after the row's other controls, and the panel's controls straight after it.

The panel SHALL list the clip's cuts in their order, each with its number in the list, its start and end, its
length and its reason in words. A clip without cuts SHALL say that the whole clip plays. A missing clip SHALL
show, in its row, how many cuts it has, and SHALL offer no Cuts control: its file is not on disk to cut, and
removing it from `reel.yaml` takes its cuts with it. Once the operator removes it, its row SHALL NOT show its
cuts any more, since the save drops them. An ignored clip SHALL have no cuts and no Cuts control.

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

**The clip's length.** No read of the service gives a clip's length. The page knows it only once the clip's
preview has read it from the clip's file in this Edit mode ("Edit mode previews a clip on request"). Until
then, the panel SHALL say that the page does not know the clip's length, that a cut that runs past the clip's
end stops there, and that a cut over the whole clip leaves the clip out of the movie, and it SHALL NOT refuse
a cut for its length. Once the page knows the length, the panel SHALL state it beside its fields, SHALL refuse
a cut that ends after it, and SHALL mark each listed cut that ends after it ("A clip's preview sets cut times
at the playhead and plays the clip as the movie will").

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
- **WHEN** on `s1710002.mp4` of `2024-06-27 - Grillning med grannar`, whose preview was not opened in this Edit
  mode, the operator adds a cut from `5` to `7`
- **THEN** the cut is accepted and listed, and the panel says that the page does not know the clip's length and
  that a cut that runs past the clip's end stops there

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
  `Kvällen/s1710002.mp4`, which `Kvällen` names `s1710002.mp4`, adds nothing, and moves that clip to `Main`
  with Move clips
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

The event page SHALL show, beside the name of each clip that has cuts in `reel.yaml`, how many cuts it has and
how much time they cut out ("2 cuts · −4.5 s"), counted as Edit mode counts them. On request, the page SHALL
show the clip's cuts there, as Edit mode lists them, without any control that changes them. A clip without
cuts SHALL show nothing more than before. The indicator SHALL be operable from the keyboard. It SHALL say to
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
  top or bottom edge, the page SHALL scroll by itself, so that a chapter out of view can be reached.
- **from the keyboard**, on the clip's handle:
  - Down at a chapter's last position SHALL take the clip to the first position of the next listed chapter.
  - Up at a chapter's first position SHALL take it to after the last clip of the chapter before.
  - A deleted chapter's placeholder SHALL be passed over.
  - Escape SHALL cancel and leave every chapter as it was, with the clip's handle in view again (its whole
    row, or its first line when the row is taller than the room left).

A chapter that plays no clip SHALL show, in Edit mode, an area that says clips can be dragged into it. The
area SHALL be shown whether or not a drag is under way. A clip dropped on it SHALL become the chapter's first
clip.

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
  heading and in the save bar, as a clip moved with Move clips does
- a clip dragged back to the chapter and the position it had when Edit mode opened SHALL count as no move;
  with no other edit, the page SHALL show no unsaved changes
- it SHALL keep its cuts and its other per-clip properties. Its Cuts control SHALL be as it was, and its
  panel stays shown or hidden as it was and keeps any time typed but not added
- Save SHALL write it as it writes a clip moved with Move clips ("Saving an edit writes only what the operator
  changed"). Reset, the unsaved-changes question, a conflict and Overwrite SHALL treat it as any other edit

Every target in another chapter SHALL be announced to assistive technology, and so SHALL a drop and a
cancel. The announcement names the clip as its row named it when it was lifted. A target or a drop in another
chapter SHALL name that chapter, and SHALL give the position out of the number of clips that chapter would
then play. Within the clip's own chapter the announcements SHALL stay as "The event page reorders clips
within a chapter" states. While more than one chapter is listed, the instructions for a keyboard drag SHALL
say that the arrows cross into the chapter before or after.

After a drop into another chapter, by pointer or keyboard, keyboard focus SHALL be on the moved clip's
handle in its new chapter. The handle and the row's first line (its handle, name and Cuts control) SHALL be
fully visible, not covered by the page header, the chapter's heading or the save bar. A row taller than that
space SHALL be scrolled so that its first line is (see "Edit mode keeps keyboard focus in view and never
drops it").

Move clips does not offer some clips, and those SHALL NOT be taken into another chapter by a drag either:

- a missing clip: its drag SHALL stop at its own chapter's edge, from the keyboard too. While more than one
  chapter is listed, its lift SHALL say that it stays in its chapter.
- an ignored clip, and a missing clip the operator removed: neither has a handle

A release over a deleted chapter's placeholder SHALL move nothing and SHALL be announced as a drop that
changed nothing. While a save is in flight, or while a Move clips move is being applied, no clip SHALL be
lifted, and a drop SHALL move nothing. The Move clips control and its dialog, and Move up and Move down,
SHALL work as they did before.

Above the chapters, Edit mode SHALL say how clips are moved:

- with one chapter: that a clip is dragged by its handle or moved with its arrows, and that a chapter can be
  added with Add chapter, below the chapters, after which clips can be dragged between chapters
- with more than one chapter: that a clip can also be dragged into another chapter, and that a chapter's Move
  clips moves several clips at once

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
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator moves all three clips of `Kvällen` to `Main`
  with Move clips, deletes `Kvällen`, adds a chapter `Morgon`, lifts `Kvällen/s1710004.mp4` (last in `Main`)
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

#### Scenario: Reaching a chapter out of view
- **WHEN** an event holds 400 clips in its own chapter and 3 in a second chapter, and the operator drags the
  second chapter's first clip up and holds it at the window's top edge
- **THEN** the page scrolls up by itself until the first chapter's first clip is in view
- **WHEN** the operator releases the clip over the upper half of that first clip
- **THEN** the clip is at position 1 of 401 in the first chapter, and the second chapter plays 2 clips

#### Scenario: The hint says how to reach other chapters
- **WHEN** Edit mode opens on `2024-06-27 - Grillning med grannar`, which has one chapter
- **THEN** the hint above the chapters says that a chapter can be added with Add chapter, below the chapters,
  and that clips can then be dragged between chapters
- **WHEN** Edit mode opens on `2024-08-20 - Två kapitel - Tjörn`
- **THEN** the hint says that a clip can be dragged into another chapter, and that a chapter's Move clips moves
  several clips at once

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
keyboard focus, the new one SHALL receive it. The old address SHALL never be used for the new file. A Refresh, like
opening the page or leaving Edit mode, replaces the page's content with placeholders while it reads (see "The event
page shows the event's chapters and clips"). It therefore stops playback, and the section returns with a new
player, paused at its start, at the address of the entity-tag that read finds.

**Nothing loads before Play.** Opening, refreshing or returning to the page SHALL NOT request any byte of the movie
other than the one-byte answer above, and SHALL NOT start playback. Playback SHALL start only from the operator's
action on the player. The player SHALL NOT loop and SHALL NOT be muted by the page. Its poster SHALL be the thumbnail
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

**The player.**
- It SHALL be the browser's own media player with its native controls. It SHALL be named by the section's heading.
- The page SHALL add no keyboard shortcut of its own. The player SHALL be reachable with Tab, and SHALL show a
  visible focus indicator in both color schemes that nothing clips, on the player itself and on every Tab stop of
  its native controls.
- The page SHALL show no captions control and no chapter list. No chapter times reach the client: the service
  gives none, and the browser exposes none of the movie's chapters.
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

#### Scenario: Refresh starts the player over
- **WHEN** the movie of `2024-07-14 - Kalas` is playing and the operator presses Refresh
- **THEN** the page shows its placeholders while it reads, and then a "Movie" section whose player is paused at its
  start, at an address that carries the same entity-tag as before

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

**What it plays.** The preview SHALL play the clip's own file as the service serves it from
`GET /api/v1/events/{event_id}/media?clip=<identity>`. The event id and the clip's full identity SHALL be
sent exactly as the event detail gives them, and the clip's modification time, exactly as the event detail
gives it, as `v`. Until it plays, the preview SHALL show the clip's thumbnail. It SHALL NOT start playing by
itself. A preview opened with Watch, from the panel or the thumbnail, SHALL stand at the clip's start, also
after an earlier preview of the clip was closed elsewhere in it. A clip displayed in portrait, such as a phone
clip whose container rotates it, SHALL be shown whole, turned as a player shows it.

**Nothing loads before it is asked for.** The page SHALL NOT request a clip's media, and SHALL NOT create a
video element for it, before the operator opens that clip's preview. This SHALL hold for any number of clips,
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

The preview SHALL show the time and the clip's length in that same format.

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
- **No sound.** When the browser reports that it finds no audio it can play in the clip, the preview SHALL say
  that this browser finds no sound it can play in the clip, and that if a Sony camera recorded it, its sound
  is PCM, which Firefox does not play and Chrome does, and the render keeps it. The note SHALL NOT state as
  fact a cause or a sound the page does not know of: the clip may have no audio track at all. Playback SHALL
  be otherwise unchanged, never muted.
- **No picture.** When the browser reads the clip but shows no picture of it, the preview SHALL say that this
  browser cannot show the clip's picture, and SHALL offer the clip's file as a download. Its controls SHALL
  stay.
- **It cannot play the clip.** When the browser refuses the clip, the page SHALL ask the service for the
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
- While a save is in flight or a Move clips is pending, Set From and Set To SHALL say that they are unavailable
  and change nothing. Play, the playhead, Skip cuts and Close SHALL stay usable.
- A clip moved within its chapter SHALL keep its preview, playing or not.
- A clip moved into another chapter, by a drag or by Move clips, SHALL keep its preview open at the same time,
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
  of `2024-05-19 - Provklipp`
- **THEN** the preview says that this browser finds no sound it can play in the clip, and that if a Sony
  camera recorded it, its sound is PCM, which Chrome plays and the render keeps. The note is announced once,
  and the clip plays its picture on request, not muted.
- **WHEN** the same preview is opened in Chrome
- **THEN** no such note is shown

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

**The clip's length.** The page SHALL take a clip's length from its preview, as the browser reads it from the
clip's file, and from nowhere else.
- Once it has the length, the clip's panel SHALL say where the clip ends beside its fields (`This clip ends at
  0:06.02`).
- The panel SHALL refuse a cut that ends after the clip's length, compared to the millisecond as the panel
  writes times. The refusal SHALL be at the end field, or at the start field when the start lies at or after
  the length, since no end could then fix it. It SHALL name the cut's time and the clip's length. A cut that
  ends exactly at the length SHALL be accepted.
- Each cut the panel lists that ends after the length SHALL be marked as running past the clip's end. Nothing
  SHALL refuse it, and its Undo SHALL NOT be refused for it.
- The page SHALL keep the length for the clip while Edit mode stays open: after the preview closes, after
  another opens, and after the clip moves to another chapter. It SHALL forget it when the clip's modification
  time changes, and when Edit mode closes.
- When the browser reads a different length for the clip while it plays, the panel SHALL use the latest.
- The length SHALL NOT be saved, sent to the service or shown anywhere outside Edit mode.

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
  moves that clip to `Kvällen` with Move clips, and adds a cut from `5` to `7` on it there
- **THEN** the cut is refused for ending after the clip's length
