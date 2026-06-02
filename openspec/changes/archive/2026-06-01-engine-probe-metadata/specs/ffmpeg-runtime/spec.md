## ADDED Requirements

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

#### Scenario: Failed command surfaces details
- **WHEN** an ffmpeg command exits non-zero
- **THEN** the engine raises a typed error exposing the exit code, the executed command, and the stderr text

#### Scenario: Successful command returns output
- **WHEN** an ffmpeg command exits zero
- **THEN** the engine returns its captured output without modification

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
