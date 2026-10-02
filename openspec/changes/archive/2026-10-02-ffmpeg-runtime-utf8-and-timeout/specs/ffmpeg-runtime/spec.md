## MODIFIED Requirements

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

## ADDED Requirements

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
