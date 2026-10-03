# clip-filmstrips Specification

## Purpose
Give every proxied clip a filmstrip: one small JPEG sprite of frames taken from the clip's finished proxy,
with its tile geometry recorded beside it, so the timeline can draw a clip's picture without decoding any
video. The sprite is derived, rebuildable state in the proxy cache entry; the source clip is never read.

## Requirements

### Requirement: A filmstrip is one JPEG sprite cut from the proxy's keyframes

The system SHALL make a clip's filmstrip from the clip's finished proxy (`proxy.mp4` in the clip's proxy
cache entry) and from nothing else: it SHALL NOT read the source clip, and it SHALL NOT start before the
proxy is complete. It SHALL write one JPEG, `filmstrip.jpg`, into the same cache entry. The JPEG SHALL be a
grid of tiles with these properties:

- every tile is 90 px high, and as wide as the proxy's displayed shape gives at that height, rounded to an
  even width: 160 px for a 16:9 proxy, 50 px for a 540x960 portrait proxy
- the grid has at most 10 columns, filled left to right, then top to bottom
- the interval between tiles is `max(1, ceil(duration / 120))` whole seconds, where `duration` is the
  duration of the finished proxy's video stream as the system probes it, so a filmstrip never has more than
  120 tiles
- the number of tiles is `ceil(duration / interval)`, and never fewer than 1
- tile `k` is the latest keyframe of the proxy at or before `k × interval` seconds (the first keyframe for
  `k = 0`), so every tile is a real frame of the clip; where the proxy has no newer keyframe, consecutive
  tiles are the same frame
- the JPEG is encoded at quality `-q:v 5`

Frames SHALL be taken from keyframes only. A `duration` that the probe of the proxy fails to give, or that is
not a positive finite number, SHALL fail the filmstrip; the system SHALL NOT use the source's duration or a
default in its place. A proxy whose keyframes are further apart than the interval (a variable-frame-rate clip
whose picture stops changing, such as a phone video of a static scene) SHALL still get a filmstrip of the
full tile count: the keyframe on screen SHALL be shown in every tile it spans. The system SHALL NOT pad a tile
with black, and SHALL NOT show a frame that is not on screen at the tile's time.

#### Scenario: A 25 s landscape clip
- **WHEN** the proxy of a 25 s, 960x540 clip with a keyframe every half second has its filmstrip made
- **THEN** `filmstrip.jpg` is 1600x270, holding 25 tiles of 160x90 in 10 columns and 3 rows, and tile `k` is
  the keyframe at or just before second `k`

#### Scenario: A portrait clip
- **WHEN** the proxy is 540x960 and 12 s long
- **THEN** the tiles are 50x90, in 10 columns and 2 rows (12 tiles), so the JPEG is 500x180

#### Scenario: A clip longer than 120 s gets a wider interval
- **WHEN** the proxy is 130 s long, and then 3,720 s (62 minutes)
- **THEN** the 130 s clip has interval 2 s and 65 tiles (1600x630), and the 3,720 s clip has interval 31 s
  and 120 tiles

#### Scenario: A clip of exactly 120 s
- **WHEN** the proxy is 120.0 s long
- **THEN** the interval is 1 s and there are 120 tiles; at 120.5 s the interval is 2 s and there are 61

#### Scenario: Every tile is the frame it should be
- **WHEN** the filmstrip of a clip whose every frame shows its own time is made, and its tiles are read back
- **THEN** tile `k` shows the latest keyframe at or before `k` seconds, for every `k`, including the first
  tile (time 0) and the last

#### Scenario: Keyframes too far apart
- **WHEN** a 12 s variable-frame-rate proxy has frames for the first 3 s and the last 3 s only, so its
  keyframes are 6 s apart in the middle
- **THEN** the filmstrip is made with 12 tiles, no error is raised, and tiles 3 to 8 (seconds 3 to 8) each
  show the last keyframe before the gap, the picture that stays on screen
- **AND** a proxy with a single keyframe and a 3 s duration has 3 tiles that all show that keyframe

#### Scenario: The source is not read
- **WHEN** a filmstrip is made while the source clip's file is unreadable (the library is unmounted)
- **THEN** the filmstrip is made, and no process opens the source

### Requirement: A clip of one second or less gets a one-tile filmstrip

A clip whose proxy lasts one second or less, down to a single frame, SHALL have a filmstrip of exactly one
tile showing the proxy's first frame, with interval 1 and 1 column and 1 row. No clip SHALL be skipped for
being short, and no placeholder image SHALL stand in for a frame. The system SHALL NOT lose the last tile of
any clip: a clip of `d` seconds at interval 1 SHALL have `ceil(d)` tiles, never fewer, whatever its frame
rate and however short its tail after the last keyframe.

#### Scenario: The 0.48 s clip that failed in the research run
- **WHEN** the filmstrip of a 0.48 s, 12-frame clip, whose proxy has a single keyframe, is made
- **THEN** `filmstrip.jpg` is a 160x90 JPEG of its first frame, and `facts.json` records 1 tile
- **AND** no error is raised

#### Scenario: A clip of exactly one second
- **WHEN** a 1.00 s clip with 25 frames and one keyframe at 25 fps has its filmstrip made
- **THEN** the filmstrip has 1 tile

#### Scenario: A single-frame clip
- **WHEN** a clip with one frame (0.04 s at 25 fps) has its filmstrip made
- **THEN** the filmstrip has 1 tile of that frame

#### Scenario: The last tile is not dropped
- **WHEN** the proxies of a 25 s clip at 25 fps, a 12 s clip at 50 fps, a 1.04 s clip at 25 fps and a
  25.025 s clip at 29.97 fps are given filmstrips
- **THEN** they have 25, 12, 2 and 26 tiles; none is one tile short

### Requirement: The filmstrip's geometry is recorded in the entry's facts

After `filmstrip.jpg` is complete, the system SHALL record a `filmstrip` object in the cache entry's
`facts.json` with these members: `version` (the filmstrip format version), `tiles`, `interval` (seconds),
`columns`, `rows`, `tile_width`, `tile_height`, `width` and `height` (of the JPEG, in pixels), and `bytes`
(its size). A consumer SHALL be able to place tile `k` from the record alone: at column `k % columns` and row
`k // columns`, each `tile_width` by `tile_height`. The system SHALL preserve every other member of
`facts.json` as it was. If `facts.json` cannot be read as a JSON object, the system SHALL fail the filmstrip
with a typed error and SHALL NOT replace or repair the file.

Before the record exists, a filmstrip SHALL NOT be reported as present: a `filmstrip.jpg` that `facts.json`
does not describe is an unfinished one.

#### Scenario: The record matches the image
- **WHEN** a 25 s landscape clip's filmstrip is made
- **THEN** `facts.json` holds `filmstrip` with `tiles` 25, `interval` 1, `columns` 10, `rows` 3,
  `tile_width` 160, `tile_height` 90, `width` 1600, `height` 270, and `bytes` equal to the size of
  `filmstrip.jpg`
- **AND** every other member that `facts.json` held, such as the proxy's dimensions and audio codec, is
  unchanged

#### Scenario: A killed run between the image and the record
- **WHEN** the process is killed after `filmstrip.jpg` was renamed into place and before `facts.json` was
  updated
- **THEN** `facts.json` has no `filmstrip` member, so the filmstrip counts as absent, and the next run
  rebuilds it and records it

#### Scenario: An unreadable facts file
- **WHEN** `facts.json` holds text that is not a JSON object
- **THEN** the filmstrip fails with an error naming the clip, `facts.json` is left byte-for-byte as it was,
  and the proxy is untouched

### Requirement: A filmstrip is written atomically and verified

The system SHALL write the sprite to a file in a hidden build directory of the proxy cache (the kind of
directory the cache already sweeps when a build is abandoned), verify it, flush it to disk, and only then
rename it into the cache entry as `filmstrip.jpg`. The verification SHALL find a file that is not empty
and is a JPEG image whose size is `columns × tile_width` by `rows × tile_height`. The updated
`facts.json` SHALL be written in the build directory and renamed over the old one the same way. A killed or
failed run SHALL NOT leave a `filmstrip.jpg` that is partial or does not match its plan; it MAY leave a hidden
build directory, which the proxy cache's stale-build sweep removes.

A run whose cancel check reports true, before it starts or while ffmpeg cuts the sprite (the check is polled
about once a second and ffmpeg is then killed), SHALL end as a cancellation, publish nothing and remove its
build directory.

#### Scenario: Canceled mid-extraction
- **WHEN** the cancel check handed to the filmstrip step reports true while ffmpeg is cutting the sprite
- **THEN** ffmpeg is killed, the step ends with a cancellation (not a filmstrip failure), no
  `filmstrip.jpg` is published, `facts.json` is unchanged and no build directory remains
- **AND** a cancel reported before the step starts runs no process at all

#### Scenario: Killed mid-extraction
- **WHEN** the ffmpeg process is killed while writing the sprite of a 3,720 s clip
- **THEN** no `filmstrip.jpg` exists in that entry, `facts.json` has no `filmstrip` member, and the proxy
  still plays

#### Scenario: A sprite of the wrong size is refused
- **WHEN** the produced JPEG is 1600x180 for a plan of 1600x270
- **THEN** it is not renamed into place, the filmstrip fails with an error that says what the size was and
  what it should have been, and the build directory is removed

### Requirement: A filmstrip is built once and rebuilt only by a format version change

When the entry's `facts.json` records a `filmstrip` whose `version` equals the engine's current filmstrip
format version, and `filmstrip.jpg` exists with the recorded size, the system SHALL return that record
without running ffprobe or ffmpeg. Otherwise it SHALL build the filmstrip from the existing proxy. The
engine SHALL bump the filmstrip format version whenever the tile spec or the extraction changes the sprite.
The filmstrip format version SHALL NOT be part of the proxy's cache key: a bump rebuilds the sprites only,
and no proxy is re-encoded. Making a filmstrip SHALL NOT change the proxy's file, the staleness fingerprint,
`RENDER_GRAPH_VERSION`, `reel.yaml`, or the database.

#### Scenario: A second request costs nothing
- **WHEN** a clip's filmstrip was made and is requested again
- **THEN** the same record is returned and neither ffprobe nor ffmpeg runs

#### Scenario: A format version bump rebuilds sprites only
- **WHEN** an entry holds a filmstrip recorded under version 1 and the engine is at version 2
- **THEN** the filmstrip is built again from the same `proxy.mp4`, the record shows version 2, and the
  proxy file's bytes, size and modification time are unchanged

#### Scenario: A missing image is rebuilt
- **WHEN** `facts.json` records a filmstrip but `filmstrip.jpg` has been deleted
- **THEN** the next request builds it again

### Requirement: A failed filmstrip leaves the proxy valid

A filmstrip that cannot be made SHALL be reported with a typed filmstrip error that names the clip and the
cause: the probe failure, a duration that is not a positive finite number, the failing ffmpeg command with
its stderr, keyframes too far apart, a size mismatch, or an unreadable `facts.json`. A proxy
cache directory that cannot be written, or a full disk, SHALL be reported as the proxy cache's error and not as
the clip's. The failure SHALL NOT delete, modify or invalidate the proxy, SHALL NOT change `facts.json`, and
SHALL leave no `filmstrip.jpg` and no build directory behind. The failure SHALL NOT be remembered: the next
request tries again.

#### Scenario: A corrupt proxy
- **WHEN** `proxy.mp4` in an entry cannot be probed
- **THEN** the filmstrip error names the clip and the probe failure, the entry's other files are unchanged,
  and no `filmstrip.jpg` exists

#### Scenario: Retry after a failure
- **WHEN** a filmstrip failed because the disk was full, and the space is then freed
- **THEN** the next request builds it
