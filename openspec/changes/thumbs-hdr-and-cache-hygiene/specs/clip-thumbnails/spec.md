## MODIFIED Requirements

### Requirement: A thumbnail fits a 320×180 box as the clip is displayed

A thumbnail SHALL be a JPEG image that fits inside a 320×180 pixel box and keeps the clip's displayed aspect
ratio. It SHALL be scaled as large as the box allows, so that it reaches the box on at least one side. The
displayed aspect ratio includes:

- the container's display rotation, so a clip recorded upright stays portrait
- the sample aspect ratio, so an anamorphic clip is not squashed

The clip's editorial `rotate` property SHALL NOT be applied. A clip that the engine's probe flags as HDR
is tone-mapped first, as the next requirement says. Extraction SHALL:

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

## ADDED Requirements

### Requirement: An HDR clip's thumbnail is tone-mapped to SDR

A clip that the engine's media probe reports as HDR, meaning a PQ (`smpte2084`) or HLG (`arib-std-b67`)
transfer, SHALL have its frame tone-mapped to SDR on the CPU before it is scaled. The tone-map SHALL be the
chain the renderer uses for an HDR segment on the CPU, so a thumbnail and its movie agree. The chain SHALL come first in the
filter graph, ahead of the square-pixel and fit-in-box scaling. A clip that the probe does not report as HDR
SHALL be extracted with exactly the arguments of the previous requirement, unchanged. Whether a clip is HDR
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
