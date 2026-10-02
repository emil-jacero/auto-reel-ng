## ADDED Requirements

### Requirement: A progress run is stopped when it stalls or is canceled

When the engine runs an ffmpeg command with `-progress` parsing, the caller MAY supply a stall limit and a
cancel check. Both are opt-in: a run given neither SHALL have no deadline on its encode and SHALL otherwise behave as
before. The bound on a process's exit after its progress output has closed (below) is not opt-in: it applies
to every progress run.

With a stall limit, the engine SHALL track ffmpeg's reported output time and SHALL treat the run as stalled
when that time has not advanced for the limit, measured from the moment the process was launched. Only a
reported output time strictly greater than any seen earlier in the run, or the end-of-run marker, counts as
advancing; repeated, unavailable or unrelated lines SHALL NOT. A stalled run SHALL be killed and SHALL raise
a typed error (a distinct subtype of the command-failure error, so a caller can tell a stall from an exit) stating that ffmpeg stalled, the limit, the executed command and the stderr captured so far.

With a cancel check, the engine SHALL call it about once a second while the process runs. When it reports
true the engine SHALL kill ffmpeg and SHALL raise a distinct typed error for the cancellation, not the
failure error, so a caller can tell a requested stop from a failed command. A cancel check that raises SHALL
kill ffmpeg and propagate its exception.

After killing ffmpeg for any of these reasons (including a failing progress callback) the engine SHALL wait
at most five seconds for the process to exit. A process that has not exited by then SHALL be logged as
unkillable, with its pid and command, and abandoned, and the original error SHALL still be raised: the
engine MUST NOT wait indefinitely for a process it has killed. A process that has closed its progress output
but has not exited five seconds later SHALL be killed and treated as stalled, whether or not a stall limit
was given.

#### Scenario: A hung ffmpeg is killed and reported
- **WHEN** ffmpeg reports `out_time_us=100000` once and then writes nothing, and the stall limit is 600 s
- **THEN** after 600 s without the output time advancing the process is killed and the run raises an error
  that says ffmpeg stalled, names the 600 s limit and the command, and no progress fraction beyond the one
  derived from `out_time_us=100000` was reported

#### Scenario: A steady encode is never stalled
- **WHEN** a 40-minute 4K clip is encoded for 25 minutes and ffmpeg reports an increasing output time every
  half second
- **THEN** the run completes normally and the stall limit never fires, however long the run takes

#### Scenario: A repeating output time does not count as progress
- **WHEN** ffmpeg keeps printing `out_time_us=2000000` and `progress=continue` every half second but the
  value never changes, and the stall limit is 600 s
- **THEN** the run is killed as stalled 600 s after the value last increased

#### Scenario: A hang before the first frame is a stall
- **WHEN** ffmpeg prints nothing at all (a clip on a mount that stopped answering) and the stall limit
  passes after launch
- **THEN** the run is killed and raises the stall error

#### Scenario: A cancel request stops a running encode
- **WHEN** the cancel check starts returning true while ffmpeg is encoding a segment
- **THEN** within about a second the process is killed and the cancellation error is raised, not the
  command-failure error

#### Scenario: No limit and no check changes nothing
- **WHEN** a progress run is made with no stall limit and no cancel check
- **THEN** it has no deadline on its encode: the callback receives a non-decreasing fraction and a non-zero
  exit raises the command-failure error carrying the exit code and stderr

#### Scenario: An unkillable process does not hang the failure
- **WHEN** a stalled ffmpeg is killed but is still not reaped five seconds later
- **THEN** the engine logs the pid and command, and the stall error is raised anyway

#### Scenario: A process that closes its output but never exits
- **WHEN** ffmpeg closes its progress output, as it does at the end of a run, and is still running five seconds
  later, with or without a stall limit
- **THEN** it is killed and the run raises the stall error rather than waiting for it indefinitely

#### Scenario: A failing cancel check is not swallowed
- **WHEN** the cancel check raises because the job database is unreachable
- **THEN** ffmpeg is killed and that exception propagates to the caller
