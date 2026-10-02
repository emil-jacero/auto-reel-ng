# clip-thumbnails Specification

## Purpose
Give every clip on disk a small still image, taken from a fraction of the way into the clip rather than its
first frame, so an operator can recognise a clip without opening it. Thumbnails are derived, rebuildable
state kept in a file cache outside the library; the source clip is only ever read.

## Requirements

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

### Requirement: A thumbnail fits a 320×180 box as the clip is displayed

A thumbnail SHALL be a JPEG image that fits inside a 320×180 pixel box and keeps the clip's displayed aspect
ratio. It SHALL be scaled as large as the box allows, so that it reaches the box on at least one side. The
displayed aspect ratio includes:

- the container's display rotation, so a clip recorded upright stays portrait
- the sample aspect ratio, so an anamorphic clip is not squashed

The clip's editorial `rotate` property SHALL NOT be applied. A clip that the engine's probe flags as HDR
is tone-mapped first, as the requirement "An HDR clip's thumbnail is tone-mapped to SDR" says. Extraction SHALL:

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
- **WHEN** the thumbnail of `s1710001.mp4`, an SDR clip, is generated at 15.360 s
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

A killed or failed extraction SHALL therefore never leave a partial `<key>.jpg`. The system SHALL:

- write no thumbnail state into the library, `reel.yaml` or the database
- create the cache directory when it is absent
- evict nothing, so a thumbnail file whose key no longer occurs, such as one written under an earlier format
  version, stays in the cache directory unread

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

### Requirement: An HDR clip's thumbnail is tone-mapped to SDR

A clip that the engine's media probe reports as HDR, meaning a PQ (`smpte2084`) or HLG (`arib-std-b67`)
transfer, SHALL have its frame tone-mapped to SDR on the CPU before it is scaled. The tone-map SHALL be the
chain the renderer uses for an HDR segment on the CPU, so a thumbnail and its movie agree. The chain SHALL come first in the
filter graph, ahead of the square-pixel and fit-in-box scaling. A clip that the probe does not report as HDR
SHALL be extracted with exactly the arguments of the requirement "A thumbnail fits a 320×180 box as the clip is displayed", unchanged. Whether a clip is HDR
SHALL come from the probe that a cache miss already runs: a cache hit SHALL still run neither ffprobe nor
ffmpeg, and the system SHALL NOT read the transfer function of a clip any other way.

A thumbnail that was cached before tone-mapping existed SHALL NOT be returned for any clip, because the
thumbnail format version changed with this requirement.

The system SHALL NOT supply colour primaries or a matrix that an HDR clip does not declare. If the tone-map
cannot be applied because the clip lacks them, the clip SHALL have no thumbnail and SHALL be reported with the
typed thumbnail error, naming the clip, the requested time and ffmpeg's cause.

#### Scenario: An HLG clip is tone-mapped
- **WHEN** the thumbnail of a 640×360 clip tagged BT.2020 primaries, `arib-std-b67` transfer and `bt2020nc`
  matrix is generated at 0.250 of its duration
- **THEN** ffmpeg runs once with `-vf zscale=t=linear:npl=100,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,scale=trunc(iw*sar/2)*2:ih,scale=320:180:force_original_aspect_ratio=decrease,setsar=1`
  and every other argument as for an SDR clip
- **AND** the result is a 320×180 JPEG

#### Scenario: A PQ clip is tone-mapped the same way
- **WHEN** the probe reports `smpte2084` for a clip and its thumbnail is generated
- **THEN** the filter graph starts with the same tone-map chain

#### Scenario: An SDR clip's arguments do not change
- **WHEN** the probe reports `bt709`, or no transfer, for a clip and its thumbnail is generated
- **THEN** the filter graph is `scale=trunc(iw*sar/2)*2:ih,scale=320:180:force_original_aspect_ratio=decrease,setsar=1`
  and contains no tone-map

#### Scenario: A cached HDR clip costs no probe
- **WHEN** the thumbnail of an HDR clip has been generated and is requested again
- **THEN** the same file is returned and neither ffprobe nor ffmpeg runs

#### Scenario: A picture cached before tone-mapping is not served
- **WHEN** the cache directory holds a range-clipped `<key>.jpg` of an HLG clip written before this
  requirement, and the thumbnail of that clip is requested
- **THEN** the request uses a different `<key>.jpg`, generates it tone-mapped, and leaves the earlier file in
  place and unread

#### Scenario: An HDR clip that declares only a transfer has no thumbnail
- **WHEN** the thumbnail of a clip tagged `smpte2084` with unspecified primaries and matrix is requested, and
  ffmpeg reports that it has no path between colour spaces
- **THEN** a thumbnail error is raised naming the clip, the requested time and that cause
- **AND** no other filter chain is tried, and no thumbnail file is left behind

### Requirement: A full cache disk is a cache error

When ffmpeg fails to write a thumbnail because the disk or quota that holds the cache directory is full, the
system SHALL report one typed cache error that names the cache directory and says that the disk is full. It
SHALL NOT report the failure as a thumbnail error of that clip. A failure is a full disk when ffmpeg's own
error output, not the clip's file name or the quoted command, says `No space left on device` or `Disk quota
exceeded`. The temporary file SHALL be removed, and no `<key>.jpg` SHALL be written.

`auto-reel thumbs` and the thumbnail route SHALL handle that error as they handle any cache error: the
command stops and prints one error without per-clip lines, and the route answers with the non-clip failure.
Once space is freed, a later request SHALL generate the missing thumbnails.

#### Scenario: A full disk stops the run once
- **WHEN** `auto-reel thumbs` runs over a library of 14 clips, and the first extraction fails with ffmpeg
  reporting `Error submitting a packet to the muxer: No space left on device`
- **THEN** one error names the cache directory and the full disk, the run stops and exits non-zero
- **AND** no `ERROR <event>/<clip>: no frame extracted` line is printed for any clip

#### Scenario: A full disk is not the clip's fault in the service
- **WHEN** the same failure happens while the thumbnail route generates an uncached clip's thumbnail
- **THEN** the response is 502 whose detail names the cache directory, with no thumbnail failure kind, and the
  cache holds no temporary file

#### Scenario: A quota is a full disk too
- **WHEN** ffmpeg reports `Disk quota exceeded` while writing a thumbnail
- **THEN** a cache error naming the cache directory is raised

#### Scenario: A clip named after the error is still the clip's error
- **WHEN** a clip called `No space left on device.mp4` fails with `Invalid data found when processing input`
- **THEN** a thumbnail error for that clip is raised, not a cache error

#### Scenario: Space freed, the next run completes
- **WHEN** space is freed after a stopped run and `auto-reel thumbs` runs again
- **THEN** the thumbnails that were missing are generated, and the ones that existed are counted as cached

### Requirement: Stale temporary files are swept from the cache

The system SHALL remove the hidden temporary files that a killed or crashed extraction leaves in the thumbnail
cache directory. A file SHALL be removed when all of these hold:

- its name is the engine's temporary-file name: a dot, 64 hex digits, a dot, 32 hex digits and `.tmp`
- it is a regular file in the cache directory itself
- its modification time is more than one day before the sweep

The sweep SHALL run at most once per process for a cache directory, the first time that process has to create
a thumbnail in it, so that both `auto-reel thumbs` and `auto-reel serve` perform it. It SHALL never remove a
younger file, which may belong to a concurrent writer, a `<key>.jpg` file, a directory, or a file of any other
name. It SHALL write nothing outside the cache directory. A sweep that cannot list the directory or remove a
file SHALL NOT fail the thumbnail request; it SHALL leave that file in place and go on.

#### Scenario: Old leftovers of a killed extraction are removed
- **WHEN** the cache directory holds `.<key>.<hex>.tmp` files two days old, left by an extraction killed with
  `SIGKILL`, and `auto-reel serve` generates the thumbnail of an uncached clip
- **THEN** the two-day-old temporaries are removed and the new thumbnail is written

#### Scenario: A young temporary is left alone
- **WHEN** the cache directory holds a `.<key>.<hex>.tmp` file modified five minutes ago, while another
  process extracts, and a thumbnail is generated
- **THEN** that file is still there afterwards

#### Scenario: Only the engine's temporaries are candidates
- **WHEN** the cache directory holds, all two days old, a `<key>.jpg`, `notes.tmp`, `.keep`, a directory named
  like a temporary file and a `.<key>.<hex>.tmp` symlink, and a thumbnail is generated
- **THEN** only the regular file with the engine's temporary name is removed

#### Scenario: The sweep runs once per process
- **WHEN** a process generates two thumbnails in one cache directory, and a two-day-old temporary appears
  between them
- **THEN** that temporary is still there after the second, and is removed by the next process that generates a
  thumbnail

#### Scenario: A sweep that cannot remove a file does not fail the request
- **WHEN** an old temporary cannot be removed
- **THEN** the thumbnail is generated, and the file stays in place

#### Scenario: A cache of hits writes and removes nothing
- **WHEN** every requested thumbnail is already cached
- **THEN** no temporary file is created, no sweep runs, and nothing is removed
