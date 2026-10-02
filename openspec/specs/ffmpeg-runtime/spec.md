# ffmpeg-runtime Specification

## Purpose

Resolve and validate the ffmpeg/ffprobe runtime, execute commands with structured errors and progress reporting, and expose raw capability text for downstream detection.

## Requirements

### Requirement: Binary discovery and configuration

The engine SHALL resolve the `ffmpeg` and `ffprobe` executables in a fixed precedence order: explicit
configuration (constructor argument or environment variable) first, then the bundled jellyfin-ffmpeg default
location, then the system `PATH`. The resolved paths SHALL be exposed for logging. If neither executable can
be resolved, the engine SHALL raise a clear, typed error naming which binary is missing.

#### Scenario: Explicit configuration wins over PATH
- **WHEN** an explicit ffmpeg path is provided via config or environment variable and a different ffmpeg also exists on PATH
- **THEN** the engine uses the explicitly configured path

#### Scenario: Falls back to PATH when no explicit config
- **WHEN** no explicit path is configured and no bundled binary is present, but `ffmpeg` and `ffprobe` are on PATH
- **THEN** the engine resolves both from PATH

#### Scenario: Missing binary fails loudly
- **WHEN** neither configuration, bundled default, nor PATH yields an `ffprobe` executable
- **THEN** the engine raises a typed error that names `ffprobe` as the missing binary

### Requirement: Minimum version enforcement

The engine SHALL determine the ffmpeg version from `ffmpeg -version` and SHALL assert it is **≥ 7.1** before
any processing. A build older than 7.1, or one whose version cannot be parsed, SHALL cause a clear, typed
error that states the detected version and the required minimum.

#### Scenario: Supported version is accepted
- **WHEN** the resolved ffmpeg reports version 7.1 or newer
- **THEN** the version check passes and the engine proceeds

#### Scenario: Old version is rejected
- **WHEN** the resolved ffmpeg reports a version older than 7.1
- **THEN** the engine raises a typed error stating both the detected version and the 7.1 minimum

### Requirement: Command execution with structured errors

The engine SHALL execute ffmpeg/ffprobe commands and, on non-zero exit, SHALL raise a typed error carrying
the exit code, the command, and captured stderr. Successful execution SHALL return captured stdout/stderr.
The engine SHALL NOT swallow failures or substitute default results.

The engine SHALL decode the output of every ffmpeg/ffprobe invocation it makes (a plain run, a run that
streams `-progress`, and the `-version` query) as UTF-8, and a byte that is not valid UTF-8, such as the
Latin-1 `0xE9` of a file name written by an older tool, SHALL appear in the text as its backslash escape
(`\xe9`). Decoding SHALL NOT raise, so a command that fails on such a file name still surfaces as the typed
error with its stderr, and never as a decoding error or an empty stderr.

#### Scenario: Failed command surfaces details
- **WHEN** an ffmpeg command exits non-zero
- **THEN** the engine raises a typed error exposing the exit code, the executed command, and the stderr text

#### Scenario: Successful command returns output
- **WHEN** an ffmpeg command exits zero
- **THEN** the engine returns its captured output without modification, except that bytes that are not
  valid UTF-8 are shown as backslash escapes

#### Scenario: A non-UTF-8 file name in stderr still gives the typed error
- **WHEN** an ffmpeg or ffprobe command exits non-zero after writing `Error opening /lib/caf\xe9.mp4` to
  stderr, where `\xe9` is the raw byte `0xE9`
- **THEN** the engine raises the typed error carrying the exit code and the command
- **AND** its stderr text contains the literal characters `caf\xe9.mp4`
- **AND** no decoding error is raised

#### Scenario: A non-UTF-8 byte on a progress run keeps stderr
- **WHEN** an ffmpeg run that streams `-progress` writes a non-UTF-8 byte to stderr and exits non-zero
- **THEN** the engine raises the typed error whose stderr text includes that output, escaped
- **AND** no background reader dies with a decoding error

### Requirement: Progress reporting

The engine SHALL support running an encode with `-progress` parsing and SHALL invoke an optional caller
callback with monotonic progress derived from the reported `out_time`/`total duration`. Absence of a callback
SHALL NOT change command behavior.

#### Scenario: Progress callback receives updates
- **WHEN** a long-running ffmpeg command is executed with a progress callback supplied
- **THEN** the callback is invoked one or more times with a non-decreasing fraction between 0.0 and 1.0

### Requirement: Raw capability text exposure

The engine SHALL expose the raw text output of `ffmpeg -hwaccels`, `-encoders`, `-decoders`, and `-filters`
for consumption by later capability-detection logic. This requirement covers retrieval only; interpreting the
text into an acceleration profile is out of scope for this capability.

#### Scenario: Capability text is retrievable
- **WHEN** a caller requests the encoders listing
- **THEN** the engine returns the unmodified `ffmpeg -encoders` text output

### Requirement: A command can be bounded in time

The engine SHALL let a caller bound the run time of the ffmpeg and ffprobe commands it runs through one
runtime. When a bounded command has not exited within its bound, the engine SHALL kill the child process
and SHALL raise a typed error, a kind of the command-failure error, that states the bound and the command.
The engine SHALL return from the call within a short, fixed grace period after the kill even when the
operating system has not yet reaped the child (for example a read stalled in the kernel on a removable
drive), so that the caller's thread is released. A command with no bound SHALL behave as before: it waits
for the child to exit. The engine SHALL NOT bound any command unless a caller asks for it.

#### Scenario: A hung command is killed and reported
- **WHEN** a command is run with a 0.5 s bound and the binary sleeps for 60 s
- **THEN** the call raises the timeout error naming the 0.5 s bound and the command, within a few seconds
- **AND** the child process no longer runs

#### Scenario: A command that finishes within its bound is unaffected
- **WHEN** a command is run with a 30 s bound and exits zero after 0.1 s
- **THEN** the engine returns its output as it would for an unbounded command

#### Scenario: A child that cannot be killed does not hold the caller
- **WHEN** a bounded command is past its bound and the child does not exit after being killed
- **THEN** the call still raises the timeout error once the grace period has passed

#### Scenario: Commands are unbounded by default
- **WHEN** a command is run through a runtime that was given no bound
- **THEN** the engine waits for the child to exit, however long that takes

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
