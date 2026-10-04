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
stream). A cover stream (a video stream with the `attached_pic` disposition) SHALL NOT count as the movie's
video stream, SHALL NOT be checked against the target spec, and SHALL NOT make the file "more than one
stream"; when a cover is expected, the file SHALL have exactly one such stream and it SHALL be `mjpeg`. If
verification fails, the engine SHALL raise a typed error rather than reporting success, because a stream-copy
concat can produce a player-broken file at exit 0.

#### Scenario: Verified output is reported as success
- **WHEN** the produced file re-probes as a single stream matching the target spec
- **THEN** the engine reports the render successful and returns the output path

#### Scenario: Silently broken output is caught
- **WHEN** the produced file re-probes as a variable-resolution or otherwise non-conforming stream despite a zero exit code
- **THEN** the engine raises a typed verification error rather than reporting success

#### Scenario: A cover is not a second video stream
- **WHEN** the produced file has the movie's video stream and one `mjpeg` `attached_pic` stream
- **THEN** verification passes and the movie's facts are those of the real video stream

#### Scenario: A missing or doubled cover is caught
- **WHEN** a cover is expected and the file has none, or two
- **THEN** the engine raises a typed verification error

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

The output file name SHALL always be exactly one path component. Within the title and the location, every
path separator (`/` and `\`) and every control character (including NUL) SHALL be replaced by `-` in the
file name only; the title and location as authored in `reel.yaml`, the API and on the title card are never
altered. A name built from a title or location containing separators therefore never creates a folder and
can never form a `..` component. Before rendering or planning a dry run, the engine SHALL verify that the
output path lies inside the output directory (a lexical check, so a symlinked year folder remains valid) and
SHALL fail the event with a typed render error, creating no directory or file, when it does not.

Output finalization SHALL be atomic: the assembled movie is written to a temporary name in the **same
directory as the final output path** (same filesystem) and moved into the final path with an atomic rename
only after post-render verification passes — so a file existing at the final output path guarantees a
complete, verified render, even across a hard kill (SIGKILL, OOM, power loss) mid-assembly. When the
output already exists, the engine SHALL skip rendering unless an explicit overwrite (force) is requested,
in which case it SHALL replace the file, except as "A render refuses to replace a movie another event records"
(change-detection) states; the skip decision MAY trust bare existence because finalization is atomic. A dry-run mode SHALL build and report the planned commands without executing them or writing
output, and SHALL NOT create the year folder.

#### Scenario: Output filename includes location when present
- **WHEN** an event dated `2024-06-21` has title `Midsummer` and location `Dalarna`
- **THEN** the output file is `<output>/2024/2024-06-21 - Midsummer - Dalarna.mp4`

#### Scenario: A slash in the title does not create a folder
- **WHEN** an event dated `2025-01-16` has title `Mid/sommar`
- **THEN** the output file is `<output>/2025/2025-01-16 - Mid-sommar.mp4`, no `2025-01-16 - Mid` folder is
  created, and the title in `reel.yaml` still reads `Mid/sommar`

#### Scenario: A slash in the location does not create a folder
- **WHEN** an event dated `2025-01-16` has title `T` and location `Gamla/stan`
- **THEN** the output file is `<output>/2025/2025-01-16 - T - Gamla-stan.mp4`

#### Scenario: A traversal title cannot escape the output directory
- **WHEN** an event dated `2025-01-16` has title `a/../../../escaped`
- **THEN** the output file is `<output>/2025/2025-01-16 - a-..-..-..-escaped.mp4`, and nothing is written
  outside the output directory

#### Scenario: Backslash and control characters are replaced
- **WHEN** an event has a title containing a backslash, a NUL or a newline
- **THEN** each of those characters appears as `-` in the file name, which remains one path component

#### Scenario: An output path outside the output directory is refused
- **WHEN** the output path computed for an event would resolve outside the output directory, including in
  dry-run mode
- **THEN** the engine fails that event with a typed render error and creates no directory, `.part` file or
  output

#### Scenario: A symlinked year folder is still valid
- **WHEN** `<output>/2024` is a symlink to another directory on the archive
- **THEN** a 2024 event renders into the link target and the containment check does not refuse it

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

### Requirement: Render progress is non-decreasing and weighted by expected work

The engine's overall render progress, delivered to `on_progress` as a fraction in `[0.0, 1.0]`, SHALL never
decrease: a callback value MUST be strictly greater than every value delivered before it for the same render,
and a value that would not exceed the highest one so far MUST NOT be delivered. This holds whatever re-runs
the pipeline performs — the re-normalization of stream-copied segments after a failed equivalence pre-flight,
or a segment whose normalize is attempted again — because only forward movement of the whole render counts.

Progress SHALL be weighted by expected work, not by step count:

- a segment that is normalized weighs its intended duration (the kept span, a synthetic segment's duration, or
  the clip's probed duration for a whole clip);
- a stream-copied segment weighs nothing and SHALL NOT report progress of its own;
- the final concat SHALL own a fixed small share at the top of the span, and `1.0` is delivered when the
  concat has finished;
- when at least one segment is copy-eligible, the engine SHALL reserve a share of the span for the possible
  re-encode pass, between the normalize pass and the concat share. The re-encode pass SHALL move progress
  forward from the highest value so far to the end of that share, weighted by the duration of the segments it
  re-encodes. When the pre-flight passes and no re-encode is needed, progress advances to the start of the
  concat share only after the pre-flight has passed. When no segment is copy-eligible, no share is reserved.

The weights are an estimate of work, not of wall-clock time; the guarantee of this requirement is monotonic,
bounded progress that reaches `1.0` only at the end of the concat, not linearity.

#### Scenario: Re-encode after a failed pre-flight does not move progress backwards
- **WHEN** four copy-eligible clips are stream-copied, the equivalence pre-flight then finds the set not
  uniform, and the four are re-normalized
- **THEN** the delivered fractions form a non-decreasing sequence, the re-encode pass moves progress forward
  from where the normalize pass stopped, and the sequence ends at `1.0`

#### Scenario: An all-copy event does not jump early
- **WHEN** an event of 32 copy-eligible clips renders and the pre-flight passes
- **THEN** no fraction is delivered before the pre-flight has passed, the next delivered value is the start of
  the concat share (not `32/33`), and `1.0` is delivered when the concat finishes

#### Scenario: Long and short segments are weighted by duration
- **WHEN** an event with no copy-eligible segment normalizes a 10-second segment and then a 30-second segment
- **THEN** progress after the first segment is one quarter of the way to the start of the concat share, not
  one half

#### Scenario: A retried segment does not move progress backwards
- **WHEN** a segment's normalize is attempted a second time after the first attempt reported part of its
  progress, and the second attempt reports from `0.0` again
- **THEN** no value below the highest already delivered is passed to `on_progress`, and progress resumes once
  the retry passes that point

#### Scenario: A mixed event spends its re-encode share only when needed
- **WHEN** an event with one title card, two normalized clips and three copy-eligible clips renders and the
  pre-flight passes on the first check
- **THEN** progress ends the normalize pass at the end of its share, advances to the start of the concat share
  once the pre-flight has passed, and no value is delivered inside the reserved re-encode share

### Requirement: Chapter times are recorded from the same measured timeline
After a render has been verified and finalized, the engine SHALL record in the render manifest the chapter
times of the movie it wrote: for each chapter, in movie order, its name, its start and end in integer
milliseconds, and the span of its title card. The times SHALL be computed from the measured durations of the
segments that were concatenated (the same values that produce the `[CHAPTER]` markers muxed into the movie),
by the same boundary arithmetic, so each recorded start and end equals the corresponding marker's START and END
in the movie's 1/1000 timebase, and the first chapter starts at 0, each next chapter starts where the previous
one ended, and the last chapter ends at the sum of the chapter durations. The title-card span SHALL start at the
chapter's start plus the measured durations of the chapter's segments before the card, and end at the chapter's
start plus those durations and the card segment's own measured duration, each rounded to milliseconds once from
the exact sum; so it lies inside its chapter and is within 1 ms of the card's measured duration. A chapter with
no title-card segment SHALL record `null`. The engine SHALL NOT use planned or nominal durations for any recorded
time. Recording SHALL NOT change the movie: the same inputs SHALL produce the same movie bytes with or without
the record.

#### Scenario: Two chapters, one trimmed
- **WHEN** a movie of two chapters is assembled where the first chapter's only clip has a cut, so its measured
  segments are 1.0 s and 0.5 s, and the second chapter's clip measures 2.0 s
- **THEN** the manifest records `[{start 0, end 1500}, {start 1500, end 3500}]` in milliseconds, and the
  movie's `[CHAPTER]` markers read back by ffprobe have the same four numbers

#### Scenario: Measured, not nominal
- **WHEN** a chapter's clip is nominally 1.0 s but its measured intermediate is 0.967 s
- **THEN** the recorded end of that chapter is 967, the same as its marker, not 1000

#### Scenario: A title card inside its chapter
- **WHEN** a chapter that begins with a 3.0 s title card followed by a 1.0 s clip is assembled as the second
  of two chapters, after a 2.0 s first chapter
- **THEN** the second chapter is recorded as start 2000, end 6000, and its title-card span as start 2000, end
  5000, and the first chapter's title-card span is `null`

#### Scenario: A title card that is not the chapter's first segment
- **WHEN** a chapter's title card was placed before its title clip, which is its second clip, and the first
  clip measures 1.0 s
- **THEN** the title-card span starts 1000 ms after the chapter's start, and ends inside the chapter

#### Scenario: Stream-copied segments are measured too
- **WHEN** every segment of the movie is copy-eligible and joined by stream copy
- **THEN** the recorded chapter times come from the measured durations of those source segments, as for a
  re-encoded set

#### Scenario: The last chapter ends where the movie ends
- **WHEN** a real two-chapter movie is rendered from small synthetic clips and probed
- **THEN** the last recorded end, in seconds, differs from the movie's probed duration by less than one frame
  period of the target frame rate

#### Scenario: A failed or skipped render records nothing
- **WHEN** a render fails verification, is skipped because the output exists, or is a dry run
- **THEN** no chapter times are written, and a previous manifest, if any, keeps its own

### Requirement: A poster frame is written beside the movie

Every successful render of an event with at least one played clip SHALL write a poster image
`<movie stem>-poster.jpg` in the movie's folder (`2024-06-27 - Grillkväll.mp4` gets
`2024-06-27 - Grillkväll-poster.jpg`) and SHALL embed the same image in the movie as its cover: one `mjpeg`
stream with the `attached_pic` disposition, the movie's own streams, chapters and metadata copied unchanged.

The frame is chosen as follows. With a `poster` in `reel.yaml` whose clip is played by the movie, it is the
frame of that ORIGINAL clip `at` seconds in, before trims. Otherwise (no `poster`; or its clip is missing,
ignored, excluded or not played, which SHALL log one render warning naming the clip and the reason and SHALL NOT
fail the render) it is the first played clip's frame at the thumbnail position (a fraction of the duration from
the engine's own probe). The frame SHALL honour the clip's display rotation and its `rotate`, normalise SAR,
be tone-mapped to SDR when the probe says HDR, be scaled to fit and padded to the movie's target size, and be
encoded as a JPEG at `-q:v 2`. When `poster.clip` is played but `at` is not less than that clip's probed
duration, or no frame exists at the chosen time, the render SHALL fail that event with a typed error naming the
clip, the time and the duration, before anything is encoded; no other time, no first frame and no placeholder
is used. An event with no played clip SHALL get neither sidecar nor cover.

The sidecar and the cover are part of the atomic finalize: the poster is extracted to a `.part` and verified (a
JPEG of the target size), the cover is embedded into a `.part` copy of the movie that is verified again, the
poster is renamed into place and the movie renamed last, then the manifest is written. A render killed at any
point SHALL leave no file that looks rendered and no manifest, and a re-run or forced run SHALL replace both
files.

#### Scenario: Default poster is the first played clip's thumbnail frame
- **WHEN** an event with no `poster` and a first clip of 40 s is rendered
- **THEN** `<stem>-poster.jpg` holds that clip's frame at 10 s, at the movie's size, and the movie has one `attached_pic` stream

#### Scenario: An explicit poster is taken before trims
- **WHEN** `poster: {clip: b.mp4, at: 30}` and `b.mp4` is cut to start at 20 s
- **THEN** the poster is `b.mp4` at 30 s of the original, not 30 s of the cut

#### Scenario: A rotated clip with non-1:1 SAR
- **WHEN** the poster clip carries display rotation 90 and `rotate: 90`
- **THEN** the poster is upright by the same turn the movie shows, with square pixels, at the movie's size

#### Scenario: A missing poster clip falls back with a warning
- **WHEN** `poster.clip` is ignored in `reel.yaml`
- **THEN** the render succeeds, logs a warning naming the clip, and the poster is the default frame

#### Scenario: A time past the end fails the event
- **WHEN** `poster: {clip: a.mp4, at: 90}` and `a.mp4` lasts 40 s
- **THEN** the event fails with an error naming `a.mp4`, 90 and 40, no `.part` is left and no manifest is written

#### Scenario: A kill mid-finalize leaves nothing rendered
- **WHEN** the process is killed after the poster `.part` is written and before the movie is renamed
- **THEN** no `<stem>.mp4` is new, no `-poster.jpg` is new, no manifest is written, and the event evaluates stale

#### Scenario: No played clip
- **WHEN** an event renders with every clip excluded
- **THEN** no poster sidecar exists and the manifest records `poster: null`

#### Scenario: The covered movie still plays
- **WHEN** the movie is opened through the existing media endpoint in Chrome and in Firefox
- **THEN** it plays, with its audio and its chapters

### Requirement: The manifest, the guard, prune and the scan treat the poster with its movie

The render manifest SHALL record `poster`, the bare file name of the sidecar written by that render, or `null`
when none was; schema version stays 1, a manifest without the field or with a field that is not a bare file name
reads as `null` without making the manifest unreadable, and the field is not part of the fingerprint. The sidecar
is a claim on a file: a render SHALL refuse, unforced, to replace a regular file at its sidecar path that another
event's manifest records as its `poster`, with the same typed error as for a claimed movie. `prune-renamed`
SHALL list and, with `--yes`, delete the sidecar of a superseded movie together with it, under the same checks as
for the movie (a regular file inside the output folder that no manifest or expected path claims); a sidecar
without its movie is not listed. A scan or render gate SHALL cite the existing `output` reason, with no probe,
when the manifest records a `poster` and no regular file of that name lies beside the movie; a manifest with
`poster: null` or without the field expects no sidecar. The editorial `poster` is a fingerprint input, and the
rendered output changes for identical inputs, so `RENDER_GRAPH_VERSION` SHALL be 11.

#### Scenario: The manifest names the sidecar
- **WHEN** an event is rendered with a poster
- **THEN** its manifest has `poster` equal to `<stem>-poster.jpg`

#### Scenario: A deleted sidecar makes the event stale
- **WHEN** the manifest records a poster and `<stem>-poster.jpg` is deleted
- **THEN** the scan reports the event stale with reason `output`, and a render writes it again

#### Scenario: An old manifest expects no sidecar
- **WHEN** a version 1 manifest has no `poster` field and the fingerprint matches
- **THEN** the event is fresh

#### Scenario: Another event's poster is not replaced
- **WHEN** event B is retitled to event A's old name and rendered without force while A's manifest records `<old stem>-poster.jpg`
- **THEN** B's render is refused with the claimed-file error naming A

#### Scenario: Prune takes the sidecar with its movie
- **WHEN** `prune-renamed --yes` deletes a superseded movie that has a `-poster.jpg` beside it
- **THEN** both files are deleted, and a sidecar whose movie is gone is not listed

#### Scenario: A poster edit makes the event stale
- **WHEN** `poster.at` changes in `reel.yaml`
- **THEN** the event is stale with the editorial component named
