## ADDED Requirements

### Requirement: A shown job is dated by the time that matches its state

Wherever a screen shows an event's job (a list row, or the event page's latest job and progress region), it
SHALL show one time with it, labelled for what it is and taken from the job as the service reported it:

- a job that ended (rendered, failed or canceled): when it finished, labelled as a finish time
- a running job: when it started, labelled as a start time
- a queued job: when it was queued, labelled as a queue time

The time SHALL NOT depend on how the client learned the job. A job known only from a screen's events read
SHALL be dated exactly as the same job received over the jobs connection or read on its own. So when a
screen that showed a job from a read later receives the same job with the same times, the shown time SHALL
NOT change, and a status region's words change only with the job's state. When the service reported no
time for the job's state, the client SHALL show when the job was queued, labelled as such, and MUST NOT
present that time, or any other, as a start or finish time. The client MUST NOT compute a time the service
did not report.

#### Scenario: A rendered row says when it finished, straight from the list read
- **WHEN** the operator opens the list in a new tab with no worker running, and the list shows
  `2024-06-27 - Grillning med grannar`, whose latest job rendered. A connection snapshot carries only
  active jobs, so the tab knows that job only from the list read.
- **THEN** its row shows that the job rendered, with "finished" and the job's finish time as
  `GET /api/v1/jobs/{id}` reports it
- **AND** no row whose job ended shows its time labelled "queued"

#### Scenario: A rendered event's page says when it rendered
- **WHEN** the operator opens, in a new tab, the page of `2024-06-27 - Grillning med grannar`, whose
  latest job rendered and is known to the tab only from the event read
- **THEN** the page's latest job shows that it rendered, with "finished" and the job's finish time as
  `GET /api/v1/jobs/{id}` reports it

#### Scenario: A failed event's page says when it failed, before and after its error is read
- **WHEN** the operator opens the page of `2024-10-05 - Trasig`, whose latest job failed at probe, and the
  page reads that job for its error text
- **THEN** as soon as the event is read, the page's latest job shows that it failed, with "finished" and
  the job's finish time
- **AND** when the job read answers, the error text appears beside it, and the shown status words and
  time do not change, so nothing is announced

#### Scenario: A job cancelled before it started is dated by its cancel
- **WHEN** a job for `2024-08-02 - Badutflykt - Varberg` was cancelled before any worker claimed it, and
  the operator then opens the list
- **THEN** its row shows that the job was canceled, with "finished" and the cancel time, and no start time

#### Scenario: A queued job still says when it was queued
- **WHEN** the list shows `2024/Blandat`, whose job is queued, with no worker running
- **THEN** its row shows the job waiting, with "queued" and the time it was queued

#### Scenario: A reload does not change a finished job's time
- **WHEN** the operator starts a render of `2024-08-20 - Två kapitel - Tjörn` from its page, the job is
  rendered while the page is open, and the operator then reloads the browser tab
- **THEN** the page shows the same "finished" time before the reload, from the connection, and after it,
  from the events read
