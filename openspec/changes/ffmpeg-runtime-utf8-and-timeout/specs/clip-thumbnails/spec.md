## MODIFIED Requirements

### Requirement: A thumbnail is one frame taken at a fraction of the clip's duration

The system SHALL take a clip's thumbnail from the single frame at `position × duration` seconds, as
ffmpeg's input seek reaches it. In a container with a seek index, such as MP4 or MOV, that is the frame at
that time. In one without, such as MPEG-TS, it MAY be the next keyframe after it. The
`duration` SHALL be the one the engine's media probe reports for that clip, and `position` SHALL be the
project's thumbnail position (default `0.25`). The system SHALL NOT guess a duration. If the probe fails, or
reports a duration that is not a positive finite number, the clip SHALL have no thumbnail.

Extraction SHALL be attempted exactly once, at that time. If no frame is produced there, the clip SHALL have
no thumbnail. The system SHALL NOT fall back to another timestamp, the first frame, or a placeholder image.
A clip that fails SHALL be reported with a typed thumbnail error. The error SHALL name the clip and the
cause:

- the probe failure
- the missing duration
- "no frame" at the requested time, with the failing ffmpeg command and its stderr
- or the time-out of the probe or of the extraction

A clip that fails SHALL leave no thumbnail file behind.

The probe and the extraction SHALL each be bounded to 60 seconds. A clip whose probe or extraction does not
finish within that bound, such as one on a stalled removable drive, SHALL have no thumbnail and SHALL be
reported with the typed thumbnail error, which states that the read timed out. The system SHALL stop the
ffprobe or ffmpeg process and SHALL return from the request, so that a stalled clip does not keep the
caller, or a service extraction slot, occupied. The bound is fixed and is not a `config.yaml` setting. A
timed-out clip SHALL NOT be retried at another timestamp.

A file name that is not valid UTF-8 SHALL NOT change how a clip fails. ffprobe and ffmpeg echo such a name
on stderr, and the failure SHALL be reported with the same cause as for any other name, with the name's
invalid bytes shown as backslash escapes.

#### Scenario: The default takes the frame a quarter of the way in
- **WHEN** the thumbnail of `s1710001.mp4` in `2024-06-27 - Grillning med grannar` is requested with no
  `thumbnails` settings, and the probe reports a duration of 61.44 s
- **THEN** the thumbnail is the frame at 15.360 s, not the clip's first frame

#### Scenario: A configured position moves the frame
- **WHEN** the project's `config.yaml` sets `thumbnails: {position: 0.5}`, and the thumbnail of a clip whose
  probed duration is 27.84 s is requested
- **THEN** the thumbnail is the frame at 13.920 s

#### Scenario: A zero-byte clip has no thumbnail
- **WHEN** the thumbnail of `trasig.mp4` in `2024-10-05 - Trasig` is requested, and the file is zero bytes
- **THEN** a thumbnail error is raised, naming `trasig.mp4` and reporting that the file is empty
- **AND** no thumbnail file for it exists in the cache

#### Scenario: A clip with no usable duration is not guessed at
- **WHEN** the probe of a clip succeeds but reports no duration
- **THEN** a thumbnail error is raised, naming the clip and the missing duration, and ffmpeg is not run

#### Scenario: A corrupt clip with a non-UTF-8 name reports the probe's failure
- **WHEN** the thumbnail of `caf\xe9.mp4`, a file of text whose name holds the raw byte `0xE9`, is requested
- **THEN** a thumbnail error is raised, naming the clip, whose cause is ffprobe's own message (for example
  `Invalid data found when processing input`) and not a decoding error
- **AND** no thumbnail file for it exists in the cache

#### Scenario: A probe that hangs times out
- **WHEN** ffprobe has not exited 60 seconds after it started on `s1710003.mp4`
- **THEN** ffprobe is killed, a thumbnail error is raised naming the clip and the time-out, and ffmpeg is not
  run
- **AND** no thumbnail file for it exists in the cache

#### Scenario: An extraction that hangs times out
- **WHEN** the probe of `s1710003.mp4` succeeds and ffmpeg has not exited 60 seconds after it started
- **THEN** ffmpeg is killed, and a thumbnail error is raised naming the clip, the requested time and the
  time-out
- **AND** no thumbnail file for it exists in the cache, no temporary file remains, and no other timestamp is
  tried

#### Scenario: A truncated copy whose frame time lies past the cut
- **WHEN** a clip was cut short by an interrupted copy, the probe still reports its full duration, and
  `position × duration` lies past the last frame in the file
- **THEN** a thumbnail error is raised, naming the clip, the requested time and ffmpeg's error
- **AND** no other timestamp is tried, and no thumbnail file is left behind
