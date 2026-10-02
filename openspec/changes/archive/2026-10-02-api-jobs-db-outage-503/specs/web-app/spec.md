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

## ADDED Requirements

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
