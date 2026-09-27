# movie-assembly Specification

## Purpose

Join the normalized (and copy-eligible) segments into one movie file: verify the set is truly uniform before
trusting a stream-copy concat (never relying on ffmpeg's exit code), write real `ffmetadata` chapter markers
derived from measured segment durations, mux them in, verify the finished file matches the target spec, and
isolate failures so one bad event does not abort the batch.

## Requirements

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

The engine SHALL write the movie for an event with a metadata date to
`<YYYY>/<YYYY-MM-DD> - <title> - <location>.mp4` under the output directory. Both `YYYY` (the year folder)
and `YYYY-MM-DD` (the ISO date that prefixes the file name) SHALL come from the event's metadata date, and
the location part SHALL be omitted when absent. This is the layout and naming auto-reel used for the
existing archive: its movie title was the date-prefixed title (`YYYY-MM-DD - Title`), to which it appended
the location, under a year folder. An existing legacy output therefore sits exactly where this rule looks for
it.

An event with no metadata date SHALL be written to `<title> - <location>.mp4` directly under the output
directory, with no date prefix and no year folder. The date is never guessed from the folder layout, the
clips, or the clock. The engine SHALL create the year folder when it does not exist. Every component that
needs an event's output path (rendering, the staleness gate's call sites, adoption, job enqueue, the
worker, and the API) SHALL derive it by this one rule, so the rule cannot drift between call sites.

Output finalization SHALL be atomic: the assembled movie is written to a temporary name in the **same
directory as the final output path** (same filesystem) and moved into the final path with an atomic rename
only after post-render verification passes — so a file existing at the final output path guarantees a
complete, verified render, even across a hard kill (SIGKILL, OOM, power loss) mid-assembly. When the
output already exists, the engine SHALL skip rendering unless an explicit overwrite (force) is requested,
in which case it SHALL replace the file; the skip decision MAY trust bare existence because finalization is
atomic. A dry-run mode SHALL build and report the planned commands without executing them or writing
output, and SHALL NOT create the year folder.

#### Scenario: Output filename includes location when present
- **WHEN** an event dated `2024-06-21` has title `Midsummer` and location `Dalarna`
- **THEN** the output file is `<output>/2024/2024-06-21 - Midsummer - Dalarna.mp4`

#### Scenario: Output filename omits absent location
- **WHEN** an event dated `2023-12-24` has title `Julafton` and no location
- **THEN** the output file is `<output>/2023/2023-12-24 - Julafton.mp4`

#### Scenario: Same-titled events in different years do not share an output
- **WHEN** events dated `2023-06-23` and `2024-06-21` both have title `Midsommar` and no location
- **THEN** their outputs are `<output>/2023/2023-06-23 - Midsommar.mp4` and
  `<output>/2024/2024-06-21 - Midsommar.mp4` respectively, and rendering one leaves the other untouched

#### Scenario: Same-titled events on different days of one year do not share an output
- **WHEN** events dated `2024-12-08` and `2024-12-15` both have title `Dans Hemma` and location `Kungälv`
- **THEN** their outputs are `<output>/2024/2024-12-08 - Dans Hemma - Kungälv.mp4` and
  `<output>/2024/2024-12-15 - Dans Hemma - Kungälv.mp4`

#### Scenario: The legacy archive's names are reproduced exactly
- **WHEN** the event folder `2017-07-20 - Båttur med Liljan och Ralf`, with no `reel.yaml`, is seeded and
  its output path is derived
- **THEN** the path is `2017/2017-07-20 - Båttur med Liljan och Ralf.mp4`, byte-for-byte the name auto-reel
  wrote for it

#### Scenario: Undated event renders at the output root
- **WHEN** an event in a `flat` layout has title `Sommarlov` and no metadata date
- **THEN** the output file is `<output>/Sommarlov.mp4`, with no date prefix, and no year folder is created

#### Scenario: Year comes from the metadata date, not the layout folder
- **WHEN** an event directory sits under the `2023/` layout folder but its `reel.yaml` date is `2024-01-01`
- **THEN** the output file is `<output>/2024/2024-01-01 - <title>.mp4`

#### Scenario: Missing year folder is created
- **WHEN** the output directory exists but has no `2024/` subfolder and a 2024 event is rendered
- **THEN** the `2024/` folder is created and the movie is finalized inside it

#### Scenario: Existing output is not overwritten by default
- **WHEN** the target output file already exists and overwrite is not requested
- **THEN** the engine skips the render and leaves the existing file untouched

#### Scenario: Dry run produces no output
- **WHEN** the engine runs a movie in dry-run mode
- **THEN** it reports the planned commands and writes no intermediate or output files, and creates no year
  folder

#### Scenario: Hard kill mid-assembly leaves nothing at the final path
- **WHEN** the process is killed without cleanup (e.g. SIGKILL) while the final movie is being assembled
- **THEN** no file exists at the final output path (at most a leftover temporary-name file remains)

#### Scenario: Verification precedes finalization
- **WHEN** post-render verification of the assembled movie fails
- **THEN** no file appears at the final output path

#### Scenario: Temporary output shares the output directory
- **WHEN** the engine assembles a movie for a 2024 event
- **THEN** the temporary output file is created in the final output's own directory, `<output>/2024/` (not
  the scratch/temp dir), so the finalizing rename is atomic on one filesystem

### Requirement: Manifest written on actual render success
When a render fingerprint is supplied with the job, the engine SHALL write the event's render manifest
immediately after output finalization (verification and atomic rename) succeeds. The manifest MUST NOT be
written on a skipped render, a dry run, or any failure; when no fingerprint is supplied (direct library
use), no manifest is written.

#### Scenario: Success writes the manifest after finalization
- **WHEN** a render with a supplied fingerprint completes and the output is renamed into place
- **THEN** the render manifest is written recording that fingerprint

#### Scenario: Skip does not touch the manifest
- **WHEN** the engine skips because the output exists and overwrite was not requested
- **THEN** the existing manifest (or its absence) is unchanged

#### Scenario: Failure leaves no new manifest
- **WHEN** a render fails at any stage after starting
- **THEN** no manifest is written and any pre-existing manifest is unchanged

#### Scenario: No fingerprint, no manifest
- **WHEN** a render runs without a supplied fingerprint
- **THEN** the render completes normally and writes no manifest

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
