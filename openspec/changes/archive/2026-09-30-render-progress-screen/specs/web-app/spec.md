## ADDED Requirements

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

- a **Render** control when the event needs a render, has no queued or running job, and the page is not in
  Edit mode
- when the event is up to date, has no queued or running job, and the page is not in Edit mode: its
  up-to-date state plus a secondary **Render anyway** control, which asks for confirmation before it
  forces a render

While the page is in Edit mode, it SHALL offer neither control and SHALL instead say that the edits must be
saved, or Edit mode left, before rendering: a render reads the saved `reel.yaml`, not the unsaved edits. A
queued or running job's progress and its Cancel control stay offered in Edit mode.

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

### Requirement: A render's progress is shown live

Wherever a job is shown for an event, the client SHALL show the newest job it knows for that event. That is
the live state when the connection carries one, and otherwise the latest job the last read returned. For
one and the same job, a finished state the client has learned SHALL never be replaced by an earlier queued
or running state. The job SHALL be shown as follows:

- **queued:** a progress indicator with no value, and the words "Waiting for a worker"
- **running with no progress reported yet:** a progress indicator with no value, and a starting state
- **running:** a determinate progress bar from the job's progress fraction, and its percentage
- **cancel requested, not yet stopped:** that it is cancelling
- **done:** that it rendered, with the job's time as the service reported it, labelled as a finish time
  only when the service reported one
- **failed:** that it failed; on the event's page also the job's own error text from the service
- **canceled:** that it was canceled, as a neutral state, not as an error

While running, the event's page SHALL show an estimate of the time left, computed from the progress
reported over time. It SHALL stay hidden until the job is past 5% and enough progress has been observed,
and it SHALL NOT be shown increasing. The client MUST NOT invent a percentage, a time or an error text the
service did not report. Progress changes SHALL NOT be announced to assistive technology on every update;
only state changes (queued, running, cancelling, and the terminal states) are announced.

A job that this tab started or attached to, and that finishes while the connection is live, SHALL raise a
notification: rendered, failed, or canceled. A job whose end the client learns only by reading it (after a
reconnect, or because a screen still showed it as active) SHALL NOT raise one, nor SHALL a job this tab
neither started nor attached to. One ending SHALL raise at most one notification: a cancel whose answer
already said the job was canceled or had finished raises no second one.

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

### Requirement: A queued or running render can be cancelled

While an event's job is queued or running, its page SHALL offer a **Cancel** control:

- a queued job is cancelled without a confirmation
- a running job is cancelled only after the operator confirms, in a dialog that says the partial render is
  discarded and any existing movie stays as it was. The dialog opens with focus on the action that keeps
  the job rendering.

A pressed cancel control SHALL send one request, and until the answer arrives it SHALL stay in place, keep
keyboard focus, be marked busy, and ignore further presses.

Once the service answers, the page SHALL say which outcome occurred, in words, through a mapping defined
over the generated cancel-outcome union. The client's type-check then fails when the vocabulary gains,
loses or renames a member. The client MUST NOT show an outcome slug verbatim. After a running job is
flagged for cancellation, the page SHALL show it as cancelling until the service reports it canceled or
finished. An unknown job SHALL be reported as not found.

#### Scenario: A queued job is cancelled at once
- **WHEN** the operator presses Cancel on `2024/Blandat`'s queued job
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

### Requirement: The event list shows live job state and offers a render

Each event row the list shows with its render state SHALL show that event's job as the progress
requirement describes. The job the connection carries SHALL be matched to the row whose event id equals the
job's event directory. A row that needs a render and has no queued or running job SHALL offer a compact
**Render** control, whose accessible name names the event ("Render" followed by the event's folder name),
so that a list of Render controls is told apart by assistive technology. At phone width, the row's job
state keeps its "Last job" label whenever the row shows a job, including one the connection reported
after the list was read, and a row that shows no job has no such label. The row's Render control, once
pressed, behaves as the page's: one request, focus kept, marked busy. Its answers are handled as on the
event's page, except as follows:

- when the event is up to date, a notification says so and links to the event's page. The list does not
  force a render.
- when another event claims the same movie file, an error notification names the other events and links to
  the pressed event's page.

Error rows under "Needs attention" SHALL NOT offer Render.

#### Scenario: A row shows a queued job live
- **WHEN** a job is enqueued for `2024-08-02 - Badutflykt - Varberg` from its page, and the operator returns
  to the list
- **THEN** its row shows the job queued, and its progress once a worker runs it, with no refresh

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

## MODIFIED Requirements

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
