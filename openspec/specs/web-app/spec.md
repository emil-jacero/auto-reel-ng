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
the facts and the description. Each chapter keeps its level-two heading, and each clip row keeps the facts
the table shows: its position, file name, status in words, size and modification time, with absent facts
shown as absent. The event's verdict and latest job stay shown. Leaving Edit mode, by any path, SHALL read
the event again and show the tables. Only the operator's own actions SHALL end Edit mode or change what it
holds: a read of the event that the page would start by itself while Edit mode is open SHALL NOT discard
the edits.

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
clip's file name and its position out of the number of clips the chapter plays (its ignored clips, and the
missing clips the operator removed, are not counted). A clip SHALL NOT be movable into another chapter: a
dragged clip stops at its own chapter's edge. The page SHALL count as moved the fewest clips whose
moves explain the new order, so that moving one clip from position 1 to position 5 moves one clip, not five.
Each clip counted as moved SHALL show its position from when Edit mode opened.

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
- **WHEN** on `2024-08-20 - Två kapitel - Tjörn`, the operator drags `Kvällen/s1710003.mp4` upward toward the
  `Main` chapter, past the top of `Kvällen`, and releases it
- **THEN** the dragged row stopped at the top edge of `Kvällen`, the clip is now first in `Kvällen`, and
  `Main` is unchanged

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
- when saving a new order would add NEW clips to `reel.yaml`, how many
- a **Reset** control, which restores what was read
- a **Save** control

An edit that is undone, such as a clip moved and moved back or a removal undone, SHALL leave no change to
save.

Saving SHALL write the editorial document exactly as Edit mode read it, with only the operator's edits
applied:

- **Edited metadata fields** take their new values.
- **A chapter whose order changed, or from which the operator removed a missing clip,** is written in the
  order shown, with its ignored clips and its removed clips left out, and its other missing clips and its NEW
  clips kept in place.
- **A removed clip's own per-clip properties** (its trims, title-clip choice, rotation and exclusion) are
  left out with it, since `reel.yaml` no longer lists the clip.
- **Everything else** is written exactly as read: every other chapter, every other per-clip property, the
  ignored clips and the look.

When `reel.yaml` names no chapters, either because the event has no `reel.yaml` or because its `reel.yaml`
sets none, one exception applies. A save that changes an order SHALL write every chapter as shown, each
without its ignored clips, and a save that changes only metadata SHALL still write no chapters.

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
state, so the render region does not grow when the first percentage arrives.

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

### Requirement: A queued or running render can be cancelled

While an event's job is queued or running, its page SHALL offer a **Cancel** control:

- a queued job is cancelled without a confirmation while the connection is live
- a running job is cancelled only after the operator confirms, in a dialog that says the partial render is
  discarded and any existing movie stays as it was. So is a job the page shows as queued while the
  connection is not live, since it may have started meanwhile; that dialog also says the render may have
  started. The dialog opens with focus on the action that keeps the job rendering.

While the dialog is open and no cancel request is in flight, if the job ends, or a cancel of it is requested
elsewhere, the dialog SHALL close by itself and send nothing. Keyboard focus SHALL then move to the page's
job status, whose words say how the job stands.

A pressed cancel control SHALL send one request, and until the answer arrives it SHALL stay in place, keep
keyboard focus, be marked busy, and ignore further presses.

Once the service answers, the page SHALL say which outcome occurred, in words, through a mapping defined
over the generated cancel-outcome union. The client's type-check then fails when the vocabulary gains,
loses or renames a member. The client MUST NOT show an outcome slug verbatim. After a running job is
flagged for cancellation, the page SHALL show it as cancelling until the service reports it canceled or
finished. An unknown job SHALL be reported as not found.

#### Scenario: A queued job is cancelled at once
- **WHEN** the operator presses Cancel on `2024/Blandat`'s queued job while the connection is live
- **THEN** no confirmation is asked, one notification says the job was canceled before it started, and the
  page shows the job as canceled

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

- when a job is created, a notification says that the event's render was queued; when a job is already
  queued or running for the event, a notification says so. The row then shows that job, and when the
  removed Render had keyboard focus, focus moves to the row's event link.
- when the event is up to date, a notification says so and links to the event's page. The list does not
  force a render.
- when another event claims the same movie file, an error notification names the other events and links to
  the pressed event's page.

A row's notifications SHALL name the pressed event as the progress requirement's notifications do: by its
title followed by its date, or by its folder name when it has no title. The output-collision notification
is the exception: it SHALL name the pressed event and the other events by their folder names, since events
that claim the same movie file share their date, title and location.

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
  and one notification, which assistive technology announces, says that the render of "Badutflykt",
  2024-08-02, was queued

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
removes it from `reel.yaml`. The control SHALL say that it removes the clip, SHALL name the clip's file to
assistive technology, and SHALL be reachable with the keyboard. No other clip SHALL offer one: a clip that is
on disk (included, NEW or ignored) is never removed this way, and nothing else in the client removes a clip
from `reel.yaml`.

Removing a clip SHALL:

- take it out of its chapter's play order, so that the chapter's remaining clips are numbered, and their
  positions announced, without it
- list it under its chapter, after the clips the chapter plays, as removed from `reel.yaml` when the edits
  are saved. The listing keeps its file name and its status in words, and offers an **Undo** control that
  names the clip's file to assistive technology.
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
its row shows it. The thumbnail SHALL NOT be focusable, and SHALL NOT start a drag of its own. In Edit mode
a clip moves only by its handle or its move buttons, and its thumbnail moves with its row.

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
move with it. A control that receives keyboard focus SHALL NOT be left under a notification at any scroll
position, including there, while one notification is shown, or two in a window at least 844 pixels tall.

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
