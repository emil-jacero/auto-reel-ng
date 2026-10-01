## ADDED Requirements

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

## MODIFIED Requirements

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
