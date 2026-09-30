## Purpose

Give every clip on disk a small still image, taken from a fraction of the way into the clip rather than its
first frame, so an operator can recognise a clip without opening it. Thumbnails are derived, rebuildable
state kept in a file cache outside the library; the source clip is only ever read.

## ADDED Requirements

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
- or "no frame" at the requested time, with the failing ffmpeg command and its stderr

A clip that fails SHALL leave no thumbnail file behind.

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

#### Scenario: A truncated copy whose frame time lies past the cut
- **WHEN** a clip was cut short by an interrupted copy, the probe still reports its full duration, and
  `position × duration` lies past the last frame in the file
- **THEN** a thumbnail error is raised, naming the clip, the requested time and ffmpeg's error
- **AND** no other timestamp is tried, and no thumbnail file is left behind

### Requirement: A thumbnail fits a 320×180 box as the clip is displayed

A thumbnail SHALL be a JPEG image that fits inside a 320×180 pixel box and keeps the clip's displayed aspect
ratio. It SHALL be scaled as large as the box allows, so that it reaches the box on at least one side. The
displayed aspect ratio includes:

- the container's display rotation, so a clip recorded upright stays portrait
- the sample aspect ratio, so an anamorphic clip is not squashed

The clip's editorial `rotate` property SHALL NOT be applied. Extraction SHALL:

- seek on the input, with `-ss <t>` placed before `-i`
- decode on the CPU, with no hardware acceleration argument
- map only the clip's first video stream
- emit exactly one frame

The source clip SHALL only be read, never modified.

#### Scenario: A 1080p camera clip fills the box
- **WHEN** the thumbnail of a 1920×1080 clip with a 1:1 sample aspect ratio is generated
- **THEN** the image is a 320×180 JPEG

#### Scenario: A portrait clip stays portrait
- **WHEN** the thumbnail is generated of a clip coded 1080×1920, or of a clip coded 1920×1080 whose
  container carries a 90° display rotation
- **THEN** the image is 101×180, taller than it is wide

#### Scenario: An anamorphic clip is not squashed
- **WHEN** the thumbnail of a 720×576 clip with a 64:45 sample aspect ratio (16:9 displayed) is generated
- **THEN** the image is 320×180, not 225×180

#### Scenario: A 4K clip is scaled down
- **WHEN** the thumbnail of a 3840×2160 clip is generated
- **THEN** the image is 320×180

#### Scenario: The extraction command
- **WHEN** the thumbnail of `s1710001.mp4` is generated at 15.360 s
- **THEN** ffmpeg runs once with the arguments `-hide_banner -nostdin -v error -ss 15.360 -i <clip>
  -map 0:v:0 -frames:v 1 -vf
  scale=trunc(iw*sar/2)*2:ih,scale=320:180:force_original_aspect_ratio=decrease,setsar=1 -c:v mjpeg
  -q:v 5 -f image2 -update 1 -y <temporary file in the cache directory>`, where `<clip>` is the clip's
  resolved, absolute path
- **AND** no `-hwaccel` argument appears

#### Scenario: A percent sign in the cache path is taken literally
- **WHEN** the cache directory is named `p%d`, and a thumbnail is generated
- **THEN** the thumbnail is written inside `p%d`, and no directory `p1` is written to

#### Scenario: The source clip is untouched
- **WHEN** a thumbnail is generated for a clip
- **THEN** the clip's bytes, size and modification time are unchanged

### Requirement: Thumbnails are cached outside the library

A thumbnail SHALL be stored as `<key>.jpg` in the thumbnail cache directory. `<key>` SHALL be the SHA-256
hex digest over all of:

- the clip's resolved path, with symlinks followed
- its size in bytes
- its modification time in nanoseconds
- the position
- the box
- a thumbnail format version that the engine bumps whenever extraction changes its output

A requested thumbnail whose file already exists SHALL be returned as it is, without running ffprobe or
ffmpeg. A clip whose size or modification time changed SHALL get a new key and therefore a new thumbnail.
The file SHALL be written atomically:

1. into a uniquely named temporary file in the cache directory
2. flushed to disk
3. renamed to `<key>.jpg`

A killed or failed extraction SHALL therefore never leave a partial `<key>.jpg`. The system SHALL:

- write no thumbnail state into the library, `reel.yaml` or the database
- create the cache directory when it is absent
- evict nothing

A cache directory that cannot be created or written SHALL be reported with a typed cache error, naming the
directory. That error SHALL be distinct from a clip's thumbnail error.

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

### Requirement: Thumbnail settings come from the project config.yaml

The project `config.yaml` MAY carry a `thumbnails` mapping with two optional keys.

- **`position`** SHALL be a number strictly between 0 and 1. The default is `0.25`.
- **`cache_dir`** SHALL be a path that is absolute once a leading `~` is expanded.
  - The default is `$XDG_CACHE_HOME/auto-reel/thumbnails` when `XDG_CACHE_HOME` is set to an absolute path.
  - Otherwise the default is `~/.cache/auto-reel/thumbnails`.

The cache directory, configured or default, SHALL lie outside the project root, and outside the project's
`input` directory when `config.yaml` sets one.

A `thumbnails` value that is not a mapping, a wrong-typed or out-of-range `position`, a relative
`cache_dir`, and a cache directory inside the project root or the `input` directory SHALL each raise the
typed configuration error, naming the key. They SHALL NOT be ignored or clamped.

#### Scenario: No settings use the defaults
- **WHEN** the project's `config.yaml` has no `thumbnails` key, and `XDG_CACHE_HOME` is unset
- **THEN** the position is `0.25`, and the cache directory is `~/.cache/auto-reel/thumbnails`

#### Scenario: XDG_CACHE_HOME moves the default
- **WHEN** `XDG_CACHE_HOME` is `/var/cache/emil`, and `config.yaml` sets no `cache_dir`
- **THEN** the cache directory is `/var/cache/emil/auto-reel/thumbnails`

#### Scenario: An explicit cache directory wins
- **WHEN** `config.yaml` sets `thumbnails: {cache_dir: ~/thumbs}`
- **THEN** the cache directory is `thumbs` in the user's home directory, whatever `XDG_CACHE_HOME` says

#### Scenario: An out-of-range position fails loud
- **WHEN** `config.yaml` sets `thumbnails: {position: 1.5}`, `{position: 0}` or `{position: "a quarter"}`
- **THEN** a configuration error naming `thumbnails.position` is raised, and nothing is extracted

#### Scenario: A cache directory inside the library is refused
- **WHEN** `config.yaml` sets `thumbnails: {cache_dir: thumbs}`, or an absolute path under the project root
- **THEN** a configuration error naming `thumbnails.cache_dir` is raised

#### Scenario: A cache directory on the archive's input folder is refused
- **WHEN** the project's `config.yaml` sets `input: /run/media/emil/MOL/Videos/Sorted` and
  `thumbnails: {cache_dir: /run/media/emil/MOL/Videos/Sorted/.thumbs}`
- **THEN** a configuration error naming `thumbnails.cache_dir` is raised, although the directory lies outside
  the project root

#### Scenario: A default that falls inside the library is refused too
- **WHEN** `config.yaml` sets no `cache_dir`, and `XDG_CACHE_HOME` points inside the project root
- **THEN** a configuration error naming `thumbnails.cache_dir` is raised, telling the operator to set it
