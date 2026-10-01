## MODIFIED Requirements

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
