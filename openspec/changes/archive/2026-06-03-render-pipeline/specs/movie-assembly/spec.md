# movie-assembly Specification

## Purpose

Join the normalized (and copy-eligible) segments into one movie file: verify the set is truly uniform before
trusting a stream-copy concat (never relying on ffmpeg's exit code), write real `ffmetadata` chapter markers
derived from measured segment durations, mux them in, verify the finished file matches the target spec, and
isolate failures so one bad event does not abort the batch.

## ADDED Requirements

### Requirement: Equivalence pre-flight before stream-copy concat

Before concatenating with stream copy, the engine SHALL verify — via `ffprobe`, over the full segment set —
that all segments share the copy-critical parameters: video `codec_name`, `profile`, `width`, `height`,
`sample_aspect_ratio`, `pix_fmt`, and `time_base`, plus audio `codec_name`, `sample_rate`, `channels`, and
`channel_layout`. Only when every segment matches SHALL the engine use stream-copy concat. The engine SHALL
NOT use the ffmpeg exit code to decide copy safety, because mismatched resolution/SAR mux at exit 0 while
breaking playback.

#### Scenario: Uniform set concatenates by stream copy
- **WHEN** all segments share the copy-critical video and audio parameters
- **THEN** the engine concatenates them with the concat demuxer and `-c copy`

#### Scenario: Mismatch forces re-encode rather than a silent-broken copy
- **WHEN** the probed segments differ in resolution or SAR
- **THEN** the engine does not stream-copy them and instead re-encodes to a uniform set before joining

#### Scenario: Exit code is never the copy-safety signal
- **WHEN** deciding whether to stream-copy
- **THEN** the decision is made from probe data before running concat, not from a concat command's exit status

### Requirement: Chapter markers from measured durations

The engine SHALL generate an `ffmetadata` file containing one `[CHAPTER]` entry per chapter, with start/end
timestamps computed from the **measured** durations of that chapter's segments (probed from the produced
intermediates), and SHALL mux the chapter metadata into the output container. Chapter names SHALL come from the
plan's chapters. The chapter timeline SHALL exactly match the concatenated segment timeline.

#### Scenario: Chapters reach the container
- **WHEN** a movie with two chapters is assembled
- **THEN** the output container carries two `[CHAPTER]` markers whose boundaries match the cumulative measured segment durations

#### Scenario: Chapter boundaries follow measured, not nominal, durations
- **WHEN** a chapter's segments were trimmed so their real durations differ from the source clip durations
- **THEN** the chapter boundaries are computed from the measured intermediate durations

### Requirement: Post-render output verification

After assembly, the engine SHALL re-probe the produced file and SHALL assert it matches the target spec
(resolution, codec, pixel format, SAR) and is a single continuous stream (no variable-resolution/aspect
stream). If verification fails, the engine SHALL raise a typed error rather than reporting success, because a
stream-copy concat can produce a player-broken file at exit 0.

#### Scenario: Verified output is reported as success
- **WHEN** the produced file re-probes as a single stream matching the target spec
- **THEN** the engine reports the render successful and returns the output path

#### Scenario: Silently broken output is caught
- **WHEN** the produced file re-probes as a variable-resolution or otherwise non-conforming stream despite a zero exit code
- **THEN** the engine raises a typed verification error rather than reporting success

### Requirement: Output naming and overwrite control

The engine SHALL write the movie to `<title> - <location>.mp4` (location omitted when absent), carried over
from auto-reel. When the output already exists, the engine SHALL skip rendering unless an explicit overwrite
(force) is requested, in which case it SHALL replace the file. A dry-run mode SHALL build and report the planned
commands without executing them or writing output.

#### Scenario: Output filename includes location when present
- **WHEN** an event has title `Midsummer` and location `Dalarna`
- **THEN** the output file is named `Midsummer - Dalarna.mp4`

#### Scenario: Existing output is not overwritten by default
- **WHEN** the target output file already exists and overwrite is not requested
- **THEN** the engine skips the render and leaves the existing file untouched

#### Scenario: Dry run produces no output
- **WHEN** the engine runs a movie in dry-run mode
- **THEN** it reports the planned commands and writes no intermediate or output files

### Requirement: Per-event failure isolation

When rendering a batch of events, a failure rendering one event SHALL be caught, reported with its cause, and
SHALL NOT abort the remaining events. Each event's render SHALL be isolated so partial/failed output does not
corrupt other events.

#### Scenario: One failed event does not stop the batch
- **WHEN** one event in a batch fails to render
- **THEN** the failure is reported for that event and the remaining events are still rendered

#### Scenario: Failed render leaves no half-written output presented as done
- **WHEN** an event's render fails partway
- **THEN** the engine does not present an incomplete output as a successful render
