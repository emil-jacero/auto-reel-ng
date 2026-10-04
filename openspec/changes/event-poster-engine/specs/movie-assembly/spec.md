## ADDED Requirements

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

## MODIFIED Requirements

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
