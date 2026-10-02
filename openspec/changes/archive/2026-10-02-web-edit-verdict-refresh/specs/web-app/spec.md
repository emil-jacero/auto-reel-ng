## MODIFIED Requirements

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
