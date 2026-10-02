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
