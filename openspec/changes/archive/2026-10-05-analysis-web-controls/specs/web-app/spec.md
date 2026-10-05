## ADDED Requirements

### Requirement: The event page shows the event's analysis state

The event page SHALL read the event's analysis (`GET /api/v1/events/{event_id}/analysis`) once when it opens,
again on every Refresh, and again when an `analysis` job of the event ends while the page is open; this one read
SHALL serve the page header and the Timeline alike (capability `event-timeline`). A re-read SHALL keep the
previous read shown until its answer arrives, and a read that leaving the page made pointless SHALL be abandoned.
The page SHALL NOT read it on a timer.

The page header SHALL show, in the read view and in Edit mode, on the line of the event's facts, a badge for the
event's analysis state as the service publishes it, so that it is visible before any proxy or Timeline exists:

- **never:** "Not analyzed", muted
- **stale:** "Analysis out of date"
- **analyzing:** while the job is queued, "Waiting to analyze" with a progress indicator with no value; while it
  runs, "Analyzing N clips…" (N the clips the read reports as analyzing; "Analyzing…" when it reports none) with
  a determinate bar and its percentage in whole percent, rounded down and held at 99% while running, as a
  render's progress is
- **failed:** "Analysis failed for N clips" (one clip: "1 clip"), with a warning tone, followed by the failed
  clips' names, at most three and then "and N more"
- **current:** no badge

A read that fails (404, 502, 503, no answer) SHALL show the badge "Analysis state unknown", muted, with the cause
in the page's words for its other reads as its description; it SHALL NOT block the page or its other reads.

Every state SHALL have a glyph and words, never colour alone. Every published analysis state SHALL have its
words in one mapping that the client's type check holds exhaustive: a state added to the service, once the
client types are regenerated, SHALL fail the type check until it is given words, and a value the build does not
know SHALL be shown as "Analysis state unknown", never as its slug.

While the jobs connection is live, the badge SHALL follow the event's newest `analysis` job the connection
carries, ahead of the read: a queued or running job shows the analyzing state with the job's live progress even
when the last read said otherwise. When that job ends, the page SHALL re-read the analysis once and show the
state the read reports, and its polite status region SHALL say "Analysis finished." or, when the read reports
failed clips, "Analysis failed for N clips." A job whose end the client learned only by reconciling after a
lost connection SHALL be re-read without that announcement. When the read reports analyzing but the live
connection carries no queued or running `analysis` job of the event, the page SHALL re-read once, never in a
loop. When a queued or running `analysis` job of the event that the badge follows starts after the read shown
(the read names no job, or another), the page SHALL re-read once for that job, so each clip row and the badge's
clip count say what the job analyzes.

An `analysis` job SHALL NOT be shown as a render: it SHALL NOT be the job a render region, a list row or a
render notification shows, SHALL NOT replace a render job as the newest, and SHALL NOT mark a shown render job as
ended.

#### Scenario: The badge shows before any proxy exists

- **WHEN** the operator opens the page of an event whose clips have no proxies and whose analysis state is
  never
- **THEN** the header's facts line shows "Not analyzed" with its glyph, and the page has made one request to
  `…/analysis`

#### Scenario: A current analysis shows no badge

- **WHEN** the service reports the event's analysis state as current
- **THEN** the header shows no analysis badge

#### Scenario: A running analysis shows live progress

- **WHEN** the connection is live and the event's `analysis` job runs at progress 0.42 while the read reports
  nine clips as analyzing
- **THEN** the header badge reads "Analyzing 9 clips…" with a bar at 42% and "42%", and the badge moves with
  each delta the connection carries, with no request to `…/analysis` on a timer

#### Scenario: The end of the job re-reads the analysis

- **WHEN** the event's running `analysis` job ends done while its page is open
- **THEN** the page makes one request to `…/analysis`, the badge shows the state it reports (no badge when
  current), and the status region says "Analysis finished."

#### Scenario: The start of a job re-reads the analysis once

- **WHEN** the operator presses Analyze on an event whose two clips read never, and its job is queued
- **THEN** the page makes one request to `…/analysis`, each clip row reads "Analyzing…", and once the job runs
  the badge reads "Analyzing 2 clips…"; no further request is made until the job ends

#### Scenario: Failed clips are named

- **WHEN** the service reports the analysis as failed for `C0007.MP4`
- **THEN** the header badge reads "Analysis failed for 1 clip" with a warning glyph, followed by `C0007.MP4`

#### Scenario: A new analysis state fails the build

- **WHEN** a value is added to the service's published analysis state and the client types are regenerated
- **THEN** the client's type check fails at the analysis state mapping until the value is given words

#### Scenario: An analysis job does not take a render's place

- **WHEN** the event's render finished and its `analysis` job is running
- **THEN** the page's render region still shows the render as rendered with its own time, and the list row of
  that event shows the same, not a running job

### Requirement: The operator re-analyzes an event from its page

The event page SHALL offer **Re-analyze** ("Analyze" while the event's analysis state is never) in the read
view's header actions, beside Refresh and Edit, and in Edit mode beside the Timeline's analysis badge (capability
`event-timeline`). Pressing it SHALL send `POST /api/v1/events/{event_id}/analysis` with `force: true` and no
confirmation: the suggestions are found again from the clips, a cut already approved stays in the event's cuts,
and the event's `reel.yaml` is not written. The Timeline help SHALL say so.

While the request is in flight the control SHALL be busy, keeping keyboard focus. While the event's analysis is
queued or running the control SHALL be unavailable (`aria-disabled`, keeping focus) with its reason, "Analysis is
already queued or running.", as its description; pressing it then SHALL send nothing. The page SHALL tell the
answers apart by the published status and conflict kind, never by the problem's prose:

- **accepted (a job):** the job is shown at once as the badge's analyzing state, without waiting for the
  connection, and the status region says "Analysis queued."
- **already active (409 `active_job` naming the job):** the badge shows that job as analyzing; nothing is said
  to have failed
- **nothing to analyze (200, the event has no clips to analyze):** the status region says "Nothing to analyze."
  and the badge keeps its state
- **unknown event or unreadable folder (404, 502):** an alert in the page's words for these reads, with the
  service's detail
- **the job database unavailable (503 naming the database):** an alert that the job could not be queued
  because the database is unavailable, and nothing is shown as queued
- **no answer, or an answer the route does not publish:** an alert that says so, and nothing is shown as queued

At 390 px the header's actions SHALL wrap without horizontal overflow, each a target of at least 44 by 44 CSS
pixels, in light and dark schemes.

#### Scenario: Re-analyze queues a forced analysis

- **WHEN** an event's analysis is current and the operator presses Re-analyze in the read view
- **THEN** one `POST …/analysis` is sent with `{"force": true}`, no dialog opens, the badge reads "Waiting to
  analyze", and the status region says "Analysis queued."

#### Scenario: A never analysed event offers Analyze

- **WHEN** the event's analysis state is never
- **THEN** the control reads "Analyze", and pressing it sends the same request

#### Scenario: Re-analyze is unavailable while analyzing

- **WHEN** the event's `analysis` job is running and the operator presses Re-analyze
- **THEN** no request is sent, the control keeps focus, and its description reads "Analysis is already queued
  or running."

#### Scenario: A job already active

- **WHEN** the service answers the press with a 409 whose conflict kind names an active analysis job
- **THEN** the badge shows that job as analyzing and no alert says the press failed

#### Scenario: The database is down

- **WHEN** the service answers with a 503 naming the database
- **THEN** an alert says the analysis could not be queued because the database is unavailable, and the badge
  keeps its state

#### Scenario: Re-analyze in Edit mode keeps the draft

- **WHEN** the operator has an unsaved cut in Edit mode and presses Re-analyze beside the Timeline's badge
- **THEN** the draft and its unsaved cut are kept, nothing is saved, and when the job ends the lane shows the
  new suggestions with their states derived from the draft's cuts

### Requirement: The event list analyzes every event that needs it

The event list's header SHALL offer **Analyze all** beside the Needs render filter and Refresh. Pressing it SHALL
send `POST /api/v1/analysis` (no force) with no confirmation: the service queues an analysis job for every event
whose analysis is never run or out of date and that has no analysis job queued or running, and it starts no
render. While the request is in flight the control SHALL be busy, keeping keyboard focus, and a second press
SHALL send nothing.

The answer SHALL be shown as a line on the list's header and said once through a polite status region:
"Queued N events." (one event: "Queued 1 event."), followed, when the service reports them, by "N already
queued." and, when it reports events it could not read, "N could not be read." with their names in a list
that can be expanded; when it queued none and could read every event, "Nothing to analyze: every event is analyzed or already
queued." The line SHALL stay until the next press of Analyze all or the next Refresh. A 503 naming the database,
no answer, or an answer the route does not publish SHALL show an alert that nothing was queued, in the words the
list uses for its other failures. The list's rows and their render states SHALL NOT change because of the
press; the header's analysis count shows the queued jobs ("The client follows render jobs live over one
connection").

At 390 px the list header's controls SHALL wrap without horizontal overflow, each a target of at least 44 by 44
CSS pixels, in light and dark schemes.

#### Scenario: Analyze all queues the events that need it

- **WHEN** twelve events were never analysed or are out of date, one has an analysis job queued, and the
  operator presses Analyze all
- **THEN** one `POST /api/v1/analysis` is sent, the header line reads "Queued 12 events. 1 already queued.", and
  the header's analysis count shows 13 to analyze once the connection carries the jobs

#### Scenario: Nothing to analyze

- **WHEN** every event's analysis is current and the operator presses Analyze all
- **THEN** the line reads "Nothing to analyze: every event is analyzed or already queued."

#### Scenario: Analyze all never renders

- **WHEN** the operator presses Analyze all with events that need a render
- **THEN** no render job is created, and every row keeps its render state

#### Scenario: A press while busy sends nothing

- **WHEN** the operator presses Analyze all twice before the first answer arrives
- **THEN** exactly one `POST /api/v1/analysis` is sent

## MODIFIED Requirements

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
  `proxy` job is counted in neither. It SHALL also show, as a count of its own, how many events have an
  `analysis` job queued or running ("N to analyze"), with a glyph of its own that is not a render status's
  glyph, so that the count stays told apart at phone width where only glyphs and numbers show; it is left out
  when zero, and an `analysis` job is counted in neither render count.
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

#### Scenario: Analysis jobs have their own count
- **WHEN** the connection is live, one render is running, one `analysis` job is running and eleven are queued
- **THEN** the header shows 1 rendering, no queued count, and 12 to analyze with the analysis glyph, and at
  390 px each count is its glyph and its number, the words kept for assistive technology
