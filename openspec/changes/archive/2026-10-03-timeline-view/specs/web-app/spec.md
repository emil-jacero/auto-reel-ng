## MODIFIED Requirements

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
