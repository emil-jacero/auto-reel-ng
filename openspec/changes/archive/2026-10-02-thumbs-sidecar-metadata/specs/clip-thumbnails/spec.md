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

A clip that fails SHALL leave no thumbnail image behind: no `<key>.jpg`. It MAY leave the short-lived
failure marker that the requirement "A failed clip is remembered for 60 seconds" defines, and the
duration file that "The probed duration is recorded beside the thumbnail" defines. Neither is a thumbnail.

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
- **AND** no `<key>.jpg` for it exists in the cache

#### Scenario: A clip with no usable duration is not guessed at
- **WHEN** the probe of a clip succeeds but reports no duration
- **THEN** a thumbnail error is raised, naming the clip and the missing duration, and ffmpeg is not run

#### Scenario: A corrupt clip with a non-UTF-8 name reports the probe's failure
- **WHEN** the thumbnail of `caf\xe9.mp4`, a file of text whose name holds the raw byte `0xE9`, is requested
- **THEN** a thumbnail error is raised, naming the clip, whose cause is ffprobe's own message (for example
  `Invalid data found when processing input`) and not a decoding error
- **AND** no `<key>.jpg` for it exists in the cache

#### Scenario: A probe that hangs times out
- **WHEN** ffprobe has not exited 60 seconds after it started on `s1710003.mp4`
- **THEN** ffprobe is killed, a thumbnail error is raised naming the clip and the time-out, and ffmpeg is not
  run
- **AND** no `<key>.jpg` for it exists in the cache

#### Scenario: An extraction that hangs times out
- **WHEN** the probe of `s1710003.mp4` succeeds and ffmpeg has not exited 60 seconds after it started
- **THEN** ffmpeg is killed, and a thumbnail error is raised naming the clip, the requested time and the
  time-out
- **AND** no `<key>.jpg` for it exists in the cache, no temporary file remains, and no other timestamp is
  tried

#### Scenario: A truncated copy whose frame time lies past the cut
- **WHEN** a clip was cut short by an interrupted copy, the probe still reports its full duration, and
  `position × duration` lies past the last frame in the file
- **THEN** a thumbnail error is raised, naming the clip, the requested time and ffmpeg's error
- **AND** no other timestamp is tried, and no `<key>.jpg` is left behind

### Requirement: Thumbnails are cached outside the library

A thumbnail SHALL be stored as `<key>.jpg` in the thumbnail cache directory. `<key>` SHALL be the SHA-256
hex digest over all of:

- the clip's file name, with symlinks followed, so it is the name of the file itself and not of a link to it,
  and not the directory that holds it
- its size in bytes
- its modification time in nanoseconds
- the position
- the box
- a thumbnail format version that the engine bumps whenever extraction changes its output

A requested thumbnail whose file already exists SHALL be returned as it is, without running ffprobe or
ffmpeg. A clip whose size, modification time or file name changed SHALL get a new key and therefore a new
thumbnail. A clip that is moved or copied with its size and modification time preserved, or whose library is
mounted at another path, SHALL keep the key it had, so it does not get a new thumbnail. Two different files
that have the same name, size and modification time share a key and so a thumbnail: the directory is not
part of what tells clips apart.
The file SHALL be written atomically:

1. into a uniquely named temporary file in the cache directory
2. flushed to disk
3. renamed to `<key>.jpg`

A killed or failed extraction SHALL therefore never leave a partial `<key>.jpg`. Beside `<key>.jpg` the
cache directory MAY hold two small files with the same `<key>`, `<key>.json` and `<key>.fail`, that the
next two requirements define. They SHALL be written the same atomic way, through a uniquely named
temporary file, and SHALL be named by the same key, so a changed clip, file name, position, box or format
version gets new ones and the old ones are never read. The system SHALL:

- write no thumbnail state, sidecars included, into the library, `reel.yaml` or the database
- create the cache directory when it is absent
- evict nothing, so a file whose key no longer occurs, a sidecar or a thumbnail written under an earlier
  format version, stays in the cache directory unread

A cache directory that cannot be created, read or written SHALL be reported with a typed cache error,
naming the directory. That error SHALL be distinct from a clip's thumbnail error.

#### Scenario: A second request is served from the cache
- **WHEN** the thumbnail of `s1710002.mp4` in `2024-06-27 - Grillning med grannar` has been generated, and it
  is requested again with the same position
- **THEN** the same file is returned, and neither ffprobe nor ffmpeg runs

#### Scenario: A changed clip gets a new thumbnail
- **WHEN** a clip's modification time changes after its thumbnail was generated, and its thumbnail is
  requested again
- **THEN** a new `<key>.jpg` is generated, and the earlier file is left in place

#### Scenario: A clip linked into several events shares one thumbnail
- **WHEN** `s1710001.mp4` in `2024-06-27 - Grillning med grannar` and `s1710001.mp4` in
  `2024-08-20 - Två kapitel - Tjörn` are symlinks to the same file, and their thumbnails are requested one
  after the other
- **THEN** both requests resolve to the same `<key>.jpg`, and ffmpeg runs only for the first

#### Scenario: A library copied or remounted elsewhere keeps its thumbnails
- **WHEN** the thumbnails of the clips in `2024-06-27 - Grillning med grannar` have been generated, and the
  library is then copied with `cp -a` to another directory, or mounted at another path, so that every clip
  keeps its size and modification time
- **THEN** each clip's thumbnail is requested at the new location with the same `<key>.jpg` as before, and
  neither ffprobe nor ffmpeg runs

#### Scenario: A renamed clip gets a new thumbnail
- **WHEN** `s1710001.mp4` is renamed to `s1710009.mp4` with its size and modification time kept, and its
  thumbnail is requested
- **THEN** a new `<key>.jpg` is generated, and the earlier file is left in place

#### Scenario: A thumbnail written under an earlier format version is not read
- **WHEN** the cache directory holds `<key>.jpg` files written under the previous thumbnail format version,
  and a thumbnail is requested after the engine's version was bumped
- **THEN** the thumbnail is generated under a new key, and the earlier files are left in place and unread

#### Scenario: An interrupted extraction leaves no thumbnail
- **WHEN** the extraction process is killed before it finishes
- **THEN** no `<key>.jpg` exists for that clip, and the next request generates it

#### Scenario: Two generations of one thumbnail at once
- **WHEN** two callers, such as `auto-reel thumbs` and the service, generate the thumbnail of the same clip
  at the same time
- **THEN** both get the same `<key>.jpg`, which is a complete JPEG, and no temporary file remains

#### Scenario: Nothing is written into the library
- **WHEN** thumbnails are generated for every clip of the dev library with the default cache directory
- **THEN** no file under the project root is created or modified, and each event's `reel.yaml` is
  byte-for-byte unchanged

#### Scenario: An unwritable cache directory is its own error
- **WHEN** the cache directory is on a read-only filesystem, and a thumbnail that is not yet cached is
  requested
- **THEN** a cache error naming the directory is raised, not a thumbnail error for the clip

## ADDED Requirements

### Requirement: The probed duration is recorded beside the thumbnail

When generating a thumbnail probes a clip and the probe reports a usable duration, the system SHALL record
that duration in `<key>.json` in the thumbnail cache directory, as a JSON object with one member,
`duration`, the number of seconds the probe reported. It SHALL write the file atomically, before it runs the
extraction, so that a clip that probed fine but has no frame at `position × duration` still has a known
duration. The system SHALL NOT write it when the probe failed or reported no usable duration.

A reader, `recorded_duration`, SHALL return that duration from the file with no ffprobe and no ffmpeg
process, and SHALL write nothing. It SHALL return no duration, never zero and never an estimate, when:

- the file is absent
- the file cannot be read
- the file is not a JSON object with a numeric `duration`
- the duration is not positive and finite

A cache hit SHALL still run no ffprobe, so it SHALL NOT create a missing duration file: a thumbnail made
before this requirement has none until its key changes. If the duration file cannot be written after the
cache directory was created, the system SHALL raise the typed cache error, not the clip's thumbnail error.

#### Scenario: A generated thumbnail leaves its duration beside it
- **WHEN** the thumbnail of `s1710001.mp4` in `2024-06-27 - Grillning med grannar` is generated, and the
  probe reports 61.44 s
- **THEN** `<key>.json` holds a `duration` of 61.44 next to `<key>.jpg`, and no temporary file remains

#### Scenario: The duration is read without a probe
- **WHEN** `recorded_duration` is called for that thumbnail's cache path
- **THEN** it returns 61.44, and neither ffprobe nor ffmpeg runs

#### Scenario: A clip with no frame at the requested time still has a duration
- **WHEN** a truncated copy probes at 27.84 s and ffmpeg gives no frame at 6.960 s
- **THEN** a thumbnail error is raised for the clip, and `<key>.json` holds a `duration` of 27.84

#### Scenario: A failed probe records no duration
- **WHEN** the probe of `trasig.mp4` in `2024-10-05 - Trasig` fails because the file is empty
- **THEN** no `<key>.json` is written

#### Scenario: A cached thumbnail from before this requirement has no duration
- **WHEN** `<key>.jpg` exists with no `<key>.json`, and the thumbnail is requested
- **THEN** the thumbnail is returned with no ffprobe, no `<key>.json` is created, and `recorded_duration`
  returns no duration

#### Scenario: A damaged duration file is not a duration
- **WHEN** `<key>.json` holds `not json`, or `{"duration": 0}`, or `{"duration": "61"}`, or is unreadable
- **THEN** `recorded_duration` returns no duration and does not raise

#### Scenario: A changed clip does not inherit the old duration
- **WHEN** a clip's modification time changes after its duration was recorded
- **THEN** `recorded_duration` for the clip's new cache path returns no duration, and the old file is left
  in place

### Requirement: A failed clip is remembered for 60 seconds

When generating a thumbnail raises the clip's thumbnail error, because of a probe failure, no usable
duration, no frame or a time-out of the probe or the extraction, the system SHALL record the error's reason in `<key>.fail` in the thumbnail cache
directory, as a JSON object with one member, `reason`. For 60 seconds after that file was written, a request
for the same key whose `<key>.jpg` does not exist SHALL raise the thumbnail error for that clip with the
recorded reason, without running ffprobe or ffmpeg. The 60 seconds SHALL be a constant of the engine, not a
setting.

Reading a recorded failure SHALL NOT renew it: the window runs from the failed attempt. After the window,
or when the file is damaged or its modification time lies in the future, the clip SHALL be attempted
again. A successful generation SHALL remove the clip's `<key>.fail`. A `<key>.jpg` that exists SHALL be
returned whatever `<key>.fail` holds.

The system SHALL NOT record a failure for:

- the typed cache error, which is the cache's fault and not the clip's
- a clip that cannot be statted, which has no key
- an interrupted attempt

Failing to write `<key>.fail` SHALL NOT replace the clip's error: it is logged, and the clip's thumbnail
error is raised as it would have been. Reading a failure marker in an unreadable cache directory SHALL
raise the typed cache error, as reading `<key>.jpg` does.

A recorded failure SHALL carry the same typed error, the same reason and the same one-line cause as the
live failure did, to the CLI and to the service.

#### Scenario: A failing clip is not attempted again within the window
- **WHEN** the thumbnail of `trasig.mp4` in `2024-10-05 - Trasig` fails because the file is empty, and it is
  requested again 5 s later
- **THEN** the second request raises a thumbnail error with the same reason, and neither ffprobe nor ffmpeg
  runs
- **AND** `<key>.fail` exists and no `<key>.jpg` exists

#### Scenario: The window ends after 60 seconds
- **WHEN** a clip's recorded failure is 61 s old, and the clip is requested again
- **THEN** the probe and the extraction run again

#### Scenario: Reading does not extend the window
- **WHEN** a clip's recorded failure is 50 s old and it is requested, and then requested again 20 s later
- **THEN** the first request raises the recorded error without a process, and the second runs the probe and
  extraction again, because 70 s have passed since the failed attempt

#### Scenario: A repaired clip is not held back
- **WHEN** a clip failed, then was replaced by a good recording, changing its size and modification time,
  and its thumbnail is requested within the window
- **THEN** its key is a new one, there is no marker for it, and the thumbnail is generated

#### Scenario: A success removes the marker
- **WHEN** a clip's recorded failure is 90 s old and the next attempt succeeds
- **THEN** `<key>.jpg` exists and `<key>.fail` does not

#### Scenario: A cache fault is never remembered
- **WHEN** the cache directory is read-only, and an uncached clip is requested twice
- **THEN** each request raises the cache error naming the directory, and no `<key>.fail` is written

#### Scenario: A full disk is never remembered against a clip
- **WHEN** generating a thumbnail raises the cache error because the disk is full
- **THEN** no `<key>.fail` is written

#### Scenario: A marker that cannot be written does not hide the clip's error
- **WHEN** a clip fails to give a frame and `<key>.fail` cannot be written
- **THEN** the thumbnail error for the clip is raised with its real reason, and the failure to write the
  marker is logged

#### Scenario: A damaged marker is ignored
- **WHEN** `<key>.fail` holds `not json`, and the thumbnail is requested
- **THEN** the clip is attempted as if no marker existed

#### Scenario: The CLI reports a remembered failure as it reported the live one
- **WHEN** `auto-reel thumbs` fails on `trasig.mp4` and is run again 10 s later
- **THEN** the second run prints the same ERROR line for the clip and exits 1, and runs no ffprobe or
  ffmpeg for it
