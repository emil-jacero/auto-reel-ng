## MODIFIED Requirements

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

## ADDED Requirements

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
