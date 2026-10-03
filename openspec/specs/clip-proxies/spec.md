# clip-proxies Specification

## Purpose
Give every clip on disk a small, smooth-seeking, always-playable copy (a proxy) with sound, kept in a rebuildable file
cache outside the library, so a browser can scrub, step and play it where the original cannot. A proxy is checked
before it is published, and the facts about its clip are recorded beside it. The source clip is only ever read.

## Requirements

### Requirement: A proxy is one H.264 and AAC MP4 made to a fixed contract

For a clip, the system SHALL produce one file, `proxy.mp4`, with these properties, in every case where it succeeds:

- **Container:** MP4 with the index at the front (`+faststart`), so a browser can start playing and seeking
  after the first request.
- **Video:** one stream, H.264 High profile, `yuv420p`, encoded by libx264 at preset `veryfast` and CRF 26. The
  proxy SHALL use **no B-frames** (`-bf 0`) and SHALL place a keyframe every `round(fps / 2)` frames (half a
  second), where `fps` is the clip's probed frame rate, with no extra keyframes at scene cuts. This is the one shape
  experiment E1 measured that clears the scrub gate on every source in both browsers. The proxy SHALL NOT be tuned for decode speed.
- **Timestamps:** the frames keep the source's timestamps (no frame is dropped, duplicated or retimed), so a
  variable-frame-rate clip stays variable and a time in the proxy is the same time in the source.
- **Audio:** when the clip has an audio stream, exactly one stream, AAC-LC at 128 kb/s, stereo, at the source's
  sample rate, from whatever the source codec is (PCM, MP3, AC-3 5.1, mono and AAC all become stereo AAC). The
  audio SHALL be encoded by ffmpeg's **native `aac` encoder**; the system SHALL NOT select `libfdk_aac` (HLD D-1),
  even when the ffmpeg build offers it. A clip with no audio stream SHALL give a proxy with none; the system
  SHALL NOT synthesize silence.

The proxy SHALL be made from the clip as the camera recorded it. The editorial `rotate` of `reel.yaml` is not
applied, only the container's own display rotation (the requirement on geometry).

The clip SHALL only be read. A change to the contract, meaning any of the values above or the encode arguments,
SHALL bump the proxy version (the requirement on the cache key), so proxies made to the old contract are never
read as current.

#### Scenario: A Sony clip with PCM audio gets AAC
- **WHEN** the proxy of `sony-xavc-1080p25-pcm.mp4` (H.264 1920x1080, 25 fps, `pcm_s16be` stereo) is made
- **THEN** `proxy.mp4` has one H.264 High `yuv420p` stream of 960x540 and one AAC-LC stream with two channels at
  48000 Hz, its index precedes its media data, and its video uses no B-frames and has a keyframe every 12 frames

#### Scenario: A clip without audio gets none
- **WHEN** the proxy of a clip that has only a video stream is made
- **THEN** `proxy.mp4` has one video stream and no audio stream, and its facts record no audio codec

#### Scenario: Mono and surround audio become stereo
- **WHEN** the proxies of a mono-audio clip and of a 5.1 AC-3 clip are made
- **THEN** each proxy has one AAC stream with two channels

#### Scenario: The AAC encoder is the native one
- **WHEN** the ffmpeg arguments for any encode path are built on a host whose ffmpeg also lists `libfdk_aac`
- **THEN** the audio encoder named in them is `aac`, and no argument mentions `libfdk`

#### Scenario: A variable-frame-rate phone clip keeps its timing
- **WHEN** the proxy of a phone clip whose frame rate varies (its average rate differs from its container's rate) is
  made
- **THEN** the proxy has as many video frames as the source, and its video starts and ends at the source's times
  within one frame

#### Scenario: A half-second keyframe interval follows the frame rate
- **WHEN** the proxies of a 25 fps clip and of a 50 fps clip are made
- **THEN** their keyframes lie every 12 and every 25 frames, which is half a second each

#### Scenario: Editorial rotation is not baked in
- **WHEN** a clip whose `reel.yaml` entry sets `rotate: 90` has its proxy made
- **THEN** the proxy is the same file it would be without that setting

### Requirement: The proxy's size is 540 on the short side, with square pixels and the display rotation applied

The proxy's picture SHALL be the clip's **display** picture: the coded size scaled to square pixels by the clip's
sample aspect ratio, then turned upright by the container's display rotation (a 90° or 270° rotation swaps the
sides). The sample aspect ratio SHALL count as square when the probe reports none. The proxy SHALL be written
with a square sample aspect ratio.

The proxy's **short side** SHALL be 540 pixels. A clip whose display short side is already 540 or less SHALL
keep its display size: the system SHALL NOT upscale. Each dimension SHALL be rounded to the nearest even
integer (at least 2), because the encoder needs it, so a proxy's long side is the nearest even number to the
display long side scaled by the same factor.

#### Scenario: Landscape clips
- **WHEN** proxies are made of 1920x1080, 3840x2160 and 1280x720 clips with square pixels
- **THEN** each proxy is 960x540

#### Scenario: A portrait clip keeps its orientation
- **WHEN** the proxy of a 1080x1920 clip is made
- **THEN** it is 540x960

#### Scenario: A phone clip held upright is turned upright
- **WHEN** the proxy of a 1280x720 clip whose container carries a display rotation of -90° is made
- **THEN** it is 540x960 and its picture is upright, not rotated, squashed or letterboxed

#### Scenario: An anamorphic clip is not squashed
- **WHEN** the proxy of a 720x576 clip with sample aspect ratio 16:15 is made
- **THEN** it is 720x540, and a circle in the source is a circle in the proxy

#### Scenario: A small clip is not upscaled
- **WHEN** the proxy of a 640x360 clip is made
- **THEN** it is 640x360, and a 720x480 clip gives 720x480

#### Scenario: An odd result is rounded to an even size
- **WHEN** a clip's display size is 1000x667, so the scaled long side is 809.6
- **THEN** its proxy is 810x540

### Requirement: Hardware decode is used where it is proven, and the CPU path is the guaranteed fallback

The system SHALL choose, per clip, one of two encode paths. Both SHALL encode the video with libx264.

- The **hybrid path** SHALL be used only when all of these hold: the selected acceleration profile decodes the
  clip's codec and pixel format on its hardware (the profile's own answer, HLD D-18), the clip is 8-bit H.264 or HEVC,
  the clip carries no display rotation, the clip is not HDR, and the profile's frames then live in a hardware
  frame context for which the engine knows a verified scale filter. It SHALL decode and scale on the accelerator,
  download the frames to system memory, and encode on the CPU. The proxy SHALL NOT be encoded by a hardware
  encoder.
- The **CPU path** SHALL be used for every other clip, and for every clip when the selected profile is the CPU
  profile (for example `--device cpu`) or the host has no usable accelerator. It SHALL decode in software, apply
  the display rotation, scale and encode. An HDR clip (PQ or HLG) SHALL be tone-mapped to SDR first, on the CPU,
  with the render's own chain, as a thumbnail is (HLD D-11).

A hybrid encode that exits with an error, and a hybrid output that fails the verification the next requirement
defines, SHALL each be discarded and the clip encoded once more on the CPU path. The first failure's one-line
cause SHALL be logged at warning level and recorded in the facts. A cancel and a stall SHALL NOT be retried. A CPU
encode that fails SHALL NOT be retried.

The encoder path SHALL NOT be part of the cache key: a proxy made on the CPU path is current for a host with a
GPU, and the reverse.

#### Scenario: An AMD host proxies a Sony clip on the hybrid path
- **WHEN** the proxy of an unrotated H.264 clip is made on a host whose profile decodes H.264 on its hardware
- **THEN** the arguments decode with the profile's hardware decode, scale on the accelerator, download the frames,
  and encode with libx264, and the facts record the path as `hybrid`

#### Scenario: A rotated clip takes the CPU path
- **WHEN** the proxy of a 1920x1080 HEVC clip with a display rotation of -90° is made on the same host
- **THEN** the arguments use software decode, rotate in the filter chain, and encode with libx264, and the proxy
  is 540x960 with an upright picture

#### Scenario: A legacy MPEG-4 clip takes the CPU path
- **WHEN** the proxy of an MPEG-4 Part 2 clip, which the hardware does not decode, is made
- **THEN** it takes the CPU path, with no hardware flag in the arguments

#### Scenario: A host without a GPU still makes every proxy
- **WHEN** the proxy of any clip is made with the CPU profile selected
- **THEN** it takes the CPU path and passes the same verification as a hybrid proxy

#### Scenario: An HDR clip is tone-mapped on the CPU
- **WHEN** the probe flags a clip HLG
- **THEN** the CPU chain tone-maps it to SDR before it scales, on any profile

#### Scenario: A hybrid failure is redone on the CPU
- **WHEN** a hybrid encode exits with `Failed setup for format vaapi`
- **THEN** the clip is encoded on the CPU path, a proxy is published, the warning names the cause, and the facts
  record `cpu` as the path and the cause as the fallback reason

#### Scenario: A hybrid output that is the wrong size is redone on the CPU
- **WHEN** a hybrid encode exits 0 but its output is 540x960 where 960x540 was planned
- **THEN** the output is discarded, the clip is encoded on the CPU path, and a proxy is published only if that
  output passes the verification

#### Scenario: A stall is not retried
- **WHEN** a hybrid encode produces no progress for the stall limit and is killed
- **THEN** the clip fails with that cause, and no CPU encode is started

### Requirement: A proxy is verified before it is published

Before an encoded proxy is made visible, the system SHALL probe it and compare it with the source's probe. It SHALL
publish the proxy only when all of these hold:

- there is exactly one video stream, and it is H.264 `yuv420p` at the planned width and height with square pixels
- when the source has audio there is exactly one audio stream, and it is AAC with two channels; when the source has
  none, there is none
- the video stream's duration is within 50 ms of the source's video stream's duration (not the source container's,
  which spans the longest stream from the earliest start: audio that outruns the video, or a video that starts
  late, makes it longer; the container's duration is used only when the source gives no video stream duration)
- when the source container declares a video frame count, the proxy holds the same number of video frames

A failed check SHALL fail the clip with a typed proxy error that names the check, the value found and the value
expected, and the encode path. It SHALL leave no proxy behind. The system SHALL NOT widen a tolerance, skip a check
that failed, or substitute an assumed value for one it could not read; a check whose input does not exist (a
container that declares no frame count) is not made, and that is the only case in which a check is skipped.

#### Scenario: A good proxy passes
- **WHEN** a 24.96 s, 624-frame clip is proxied to 960x540 with 624 frames and a 24.96 s video stream
- **THEN** it passes and is published

#### Scenario: Missing audio is a failure
- **WHEN** a clip with a PCM track is encoded and the output has no audio stream
- **THEN** the clip fails naming the audio check, and no `proxy.mp4` is published

#### Scenario: A wrong size is a failure
- **WHEN** the CPU path's output is 960x540 for a clip whose plan is 540x960
- **THEN** the clip fails naming the dimension check, with 960x540 found and 540x960 expected

#### Scenario: A dropped frame is a failure
- **WHEN** the output holds 623 frames for a source that declares 624
- **THEN** the clip fails naming the frame-count check

#### Scenario: A drifting duration is a failure
- **WHEN** the output's video stream is 60 ms shorter than the source
- **THEN** the clip fails naming the duration check, while 40 ms shorter passes

#### Scenario: A container with no frame count skips only that check
- **WHEN** the source container declares no frame count, and the output has the right streams, size and duration
- **THEN** the proxy is published, and a debug line says the frame-count check was not possible

### Requirement: A proxy of a clip shorter than a second is made like any other

A clip whose probed duration is positive SHALL get a proxy, however short, including a clip of one frame. The
keyframe interval SHALL stay `round(fps / 2)` frames, so a proxy of fewer frames than that has one keyframe, at its start. The verification
SHALL apply unchanged. A clip with no positive probed duration SHALL fail with a typed proxy error, as a probe
failure does; the system SHALL NOT make a proxy of an assumed length.

Whether a clip is long enough to have a filmstrip is not decided here.

#### Scenario: A 0.48 s clip
- **WHEN** the proxy of a 12-frame, 0.48 s, 25 fps clip is made
- **THEN** a proxy of 12 frames with one keyframe is published and passes the verification

#### Scenario: A one-frame clip
- **WHEN** the proxy of a clip of a single frame at 30 fps is made
- **THEN** a one-frame proxy is published and passes the verification

#### Scenario: A clip with no duration
- **WHEN** the probe reports a duration of 0
- **THEN** the clip fails with a proxy error that says so, and no encode is started

### Requirement: The facts about the clip are written beside the proxy

Beside `proxy.mp4` the system SHALL write `facts.json`, a JSON object holding what the proxy run learned about the
source and about the proxy, so that a reader needs no probe. It SHALL hold at least:

- `proxy_version`, the proxy version the entry was made under
- `duration`, the source's probed duration in seconds (never the proxy's)
- `fps`, the source's frame rate as `{"num": …, "den": …}`, and `vfr`, true when the source's frame rate varies
  (its average and container rates differ by more than one percent), or `null` when the container gives no
  average rate to compare
- `frames`, the number of video frames in the proxy
- `width` and `height` of the proxy, and `source_width` and `source_height`, the coded size of the source
- `rotation`, the source's display rotation in degrees as the probe reports it (0 to 359, so a rotation of -90° is
  270), or `null` when it has none
- `audio_codec`, the source's audio codec name or `null` when it has no audio
- `encode_path`, `hybrid` or `cpu`, the path that produced the published proxy, and `fallback_reason`, the
  one-line cause of a failed hybrid attempt or `null`

A value the probe could not give SHALL be `null`, never a default. The file SHALL be written complete or not at
all (the requirement on the cache entry). The duration SHALL come from the run's own probe: the thumbnail
cache's recorded duration MAY be absent or from another version and SHALL NOT be read.

#### Scenario: Facts for a Sony clip
- **WHEN** the proxy of `sony-xavc-1080p25-pcm.mp4` is made
- **THEN** `facts.json` holds `duration` 24.96, `fps` 25/1, `vfr` false, `frames` 624, `width` 960, `height` 540,
  `source_width` 1920, `source_height` 1080, `rotation` null, `audio_codec` `pcm_s16be`

#### Scenario: Facts for a rotated phone clip
- **WHEN** the proxy of a 1280x720 clip with a display rotation of -90° is made
- **THEN** `width` is 540, `height` is 960, `source_width` is 1280, `source_height` is 720 and `rotation` is 270
  (the probe's spelling of -90°)

#### Scenario: A variable-frame-rate clip is flagged
- **WHEN** a clip's average frame rate is 30.0003 and its container rate is 30 (a difference of 0.001 %)
- **THEN** `vfr` is false, and a clip with an average of 24 and a container rate of 30 has `vfr` true

#### Scenario: The source's duration, not the proxy's
- **WHEN** the proxy's container reports 24.981 s for a source of 24.960 s
- **THEN** `duration` is 24.96

#### Scenario: A clip without audio
- **WHEN** the clip has no audio stream
- **THEN** `audio_codec` is null

### Requirement: Proxies are cached outside the library, one directory per clip

A clip's proxy SHALL live in an **entry directory** `<cache_dir>/<key>/` that holds `proxy.mp4` and `facts.json`.
The directory name `<key>` SHALL be the SHA-256 hex digest over all of:

- the clip's file name, with symlinks followed, so it is the name of the file itself and not of a link to it,
  and not the directory that holds it
- its size in bytes
- its modification time in nanoseconds
- the proxy version, which the engine bumps whenever the encode arguments, the contract or the facts change
  their output
- a digest of the contract's values (short side, CRF, preset, keyframe interval, audio rate and layout)

An entry is **complete** when its directory holds both files. A request for the proxy of a clip whose entry is
complete SHALL be answered from the entry, without running ffprobe or ffmpeg. A clip whose size, modification
time or file name changed, and a library that is moved, copied or remounted with its sizes and times kept, behave
as for thumbnails (HLD D-11): a changed clip gets a new key, and a moved library keeps its keys. Two different
files with the same name, size and modification time share a key.

An entry SHALL be published atomically. The system SHALL build it in a hidden directory
`.<key>.<unique>.part` inside the cache directory, write `proxy.mp4` and then `facts.json` into it, verify the
proxy there, flush both to disk, and rename the whole directory to `<key>`. A killed, cancelled or failed
encode SHALL therefore never leave a directory that looks complete. When the rename finds `<key>` already
present because another process finished first, the system SHALL discard its own build and return the existing
complete entry. A `<key>` directory that lacks either file SHALL be treated as absent and replaced.

The entry directory MAY later also hold `filmstrip.jpg`, written by another capability; this capability neither
writes nor reads it, and a proxy is complete without it.

The system SHALL:

- write no proxy state into the library, `reel.yaml` or the database
- create the cache directory when it is absent
- evict nothing, so an entry whose key no longer occurs, or that was made under an earlier proxy version, stays
  in the cache directory unread

A cache directory that cannot be created, read or written SHALL be reported with a typed cache error naming the
directory, distinct from a clip's proxy error.

#### Scenario: A second request is answered from the cache
- **WHEN** the proxy of a clip has been made and is requested again
- **THEN** the same entry is returned, and neither ffprobe nor ffmpeg runs

#### Scenario: A changed clip gets a new proxy
- **WHEN** a clip's modification time changes after its proxy was made
- **THEN** a new entry is made under a new key, and the old one is left in place

#### Scenario: A clip linked into several events shares one entry
- **WHEN** one file is symlinked into two events and both clips are requested one after the other
- **THEN** both resolve to the same entry, and ffmpeg ran once

#### Scenario: A remounted library keeps its proxies
- **WHEN** the library is copied with `cp -a` to another path and a clip's proxy is requested there
- **THEN** it resolves to the entry it had, and nothing runs

#### Scenario: A proxy made under an earlier version is not read
- **WHEN** the proxy version is bumped
- **THEN** the clip's proxy is made under a new key, and the old entry stays in the cache directory, unread

#### Scenario: A killed encode leaves no entry
- **WHEN** the ffmpeg process is killed before it finishes
- **THEN** no `<key>` directory exists for that clip, and the next request makes it

#### Scenario: Two builds of one proxy at once
- **WHEN** `auto-reel proxies` and the service build the proxy of the same clip at the same time
- **THEN** both return the same complete entry, one build is discarded, and no `.part` directory remains

#### Scenario: A complete entry that appears during the publish is kept
- **WHEN** another process renames its complete build into place after this build looked at the entry and before
  it replaced an incomplete leftover
- **THEN** the complete entry is kept, this build is discarded, and the complete entry is returned

#### Scenario: An incomplete directory is replaced
- **WHEN** `<key>/` exists but holds no `facts.json`
- **THEN** a request treats the proxy as absent, builds it, and the result is a complete entry

#### Scenario: Nothing is written into the library
- **WHEN** proxies are made for every clip of the dev library
- **THEN** no file under the project root is created or modified, and every `reel.yaml` is byte-for-byte
  unchanged

#### Scenario: An unwritable cache directory is its own error
- **WHEN** the cache directory is on a read-only filesystem and a proxy that is not yet cached is requested
- **THEN** a cache error naming the directory is raised, not a proxy error for the clip

#### Scenario: A full cache disk is a cache error
- **WHEN** ffmpeg reports `No space left on device` while writing into the cache directory
- **THEN** a cache error naming the directory is raised, not a proxy error for the clip, and no entry and no
  `.part` directory remains

### Requirement: A cancelled or stalled encode is stopped and leaves nothing

The system SHALL accept a progress callback and a cancel check for the encode of one clip. The progress it
reports SHALL be a fraction of the clip's duration that never decreases, including across a CPU retry. The cancel
check SHALL be polled while ffmpeg runs, and when it reports true the system SHALL kill ffmpeg, remove the hidden
build directory and raise ffmpeg's cancelled error, not a proxy error. An encode whose output time does not advance
for ten minutes SHALL be killed and fail with the stall as its cause. The probe and each ffprobe run SHALL be
bounded to 60 seconds. A slow encode that keeps advancing SHALL NOT be killed.

#### Scenario: Cancel mid-encode
- **WHEN** the cancel check returns true while a 12-minute clip is being encoded
- **THEN** ffmpeg is killed, no `.part` directory and no `<key>` directory remains, and the cancelled error is
  raised

#### Scenario: Progress after a retry never goes back
- **WHEN** a hybrid encode reported 0.8 and failed, and the CPU retry then starts from 0
- **THEN** no reported fraction is below 0.8, and the last one is 1.0

#### Scenario: A finished encode is not a published proxy
- **WHEN** a hybrid encode exits cleanly, its output fails verification, and the clip is encoded again on the CPU
- **THEN** 1.0 is reported only after the proxy is published, and the retry reports rising fractions below 1.0
  meanwhile

#### Scenario: A hang is a failure
- **WHEN** ffmpeg makes no progress for ten minutes
- **THEN** it is killed and the clip fails with a proxy error naming the stall, with no entry left

### Requirement: Stale build directories are swept from the cache

A hidden build directory (`.<key>.<unique>.part`) that is more than 24 hours old belongs to an encode that was
killed, since an encode that advances is never older. The system SHALL remove such directories from the cache
directory once per process, before it first builds there. It SHALL leave younger ones alone, since another
process may be building. A sweep that cannot remove a directory SHALL log it and go on, and SHALL NOT fail the
request.

#### Scenario: A killed build is swept
- **WHEN** the cache holds `.<key>.<unique>.part` last modified two days ago and a proxy is built
- **THEN** that directory is removed

#### Scenario: A live build is left alone
- **WHEN** the cache holds a `.part` directory modified a minute ago
- **THEN** it is left in place

### Requirement: Proxy settings come from the project config.yaml

The project `config.yaml` MAY carry a `proxies` mapping with one optional key.

- **`cache_dir`** SHALL be a path that is absolute once a leading `~` is expanded.
  - The default is `$XDG_CACHE_HOME/auto-reel/proxies` when `XDG_CACHE_HOME` is set to an absolute path.
  - Otherwise the default is `~/.cache/auto-reel/proxies`.

The cache directory, configured or default, SHALL lie outside the project root, and outside the project's
`input` directory when `config.yaml` sets one, compared by identity so another spelling or mount of a library
directory is refused too. A `proxies` value that is not a mapping, a non-string or relative `cache_dir`, and a
cache directory inside the project root or the `input` directory SHALL each raise the typed configuration error,
naming the key. They SHALL NOT be ignored. No other key is read; the contract's values are not settings.

#### Scenario: No settings use the defaults
- **WHEN** the project's `config.yaml` has no `proxies` key, and `XDG_CACHE_HOME` is unset
- **THEN** the cache directory is `~/.cache/auto-reel/proxies`

#### Scenario: XDG_CACHE_HOME moves the default
- **WHEN** `XDG_CACHE_HOME` is `/data/cache`, and `config.yaml` sets no `cache_dir`
- **THEN** the cache directory is `/data/cache/auto-reel/proxies`

#### Scenario: An explicit cache directory wins
- **WHEN** `config.yaml` sets `proxies: {cache_dir: ~/proxies}`
- **THEN** the cache directory is `proxies` in the user's home directory, whatever `XDG_CACHE_HOME` says

#### Scenario: A cache directory inside the library is refused
- **WHEN** `config.yaml` sets `proxies: {cache_dir: proxies}`, or an absolute path under the project root
- **THEN** a configuration error naming `proxies.cache_dir` is raised

#### Scenario: A default that falls inside the library is refused too
- **WHEN** `config.yaml` sets no `cache_dir`, and `XDG_CACHE_HOME` points inside the project root
- **THEN** a configuration error naming `proxies.cache_dir` is raised, telling the operator to set it

#### Scenario: A wrong-typed proxies map fails loud
- **WHEN** `config.yaml` sets `proxies: 3`
- **THEN** a configuration error naming `proxies` is raised

### Requirement: Proxies never change a render or a staleness verdict

Making, reading, replacing or deleting a proxy SHALL NOT change a rendered movie's bytes, its fingerprint or its
manifest. The staleness fingerprint SHALL NOT take any proxy file, key or fact as an input, the render SHALL NOT
read one, and no Postgres row SHALL record one. An editorial edit (an order, a cut, a chapter, a title) SHALL NOT
invalidate a proxy, since the key holds only the source file and the contract. The render graph version SHALL
NOT change with this capability.

#### Scenario: Deleting the whole cache changes no verdict
- **WHEN** an event is `fresh` and the proxy cache directory is deleted
- **THEN** the event is still `fresh`

#### Scenario: A cut edit leaves the proxy current
- **WHEN** a clip's cut is changed in `reel.yaml` after its proxy was made
- **THEN** the clip's proxy is still the complete entry for the same key

#### Scenario: Making proxies leaves the fingerprint alone
- **WHEN** the fingerprint of an event is computed before and after `auto-reel proxies` has run over it
- **THEN** the two are identical

### Requirement: A clip that cannot give a proxy is reported with its cause

A clip that cannot be statted, whose probe fails or reports no positive duration, whose encode fails on every
path that applies, or that fails verification SHALL fail with a typed proxy error. The error SHALL name the clip
and the cause, and carry the failing ffmpeg command and its stderr. A cause SHALL be kept distinct for: the
probe failure, the missing duration, an ffmpeg failure, a stall, a verification failure, and a time-out of a
probe. An audio stream that ffmpeg cannot decode SHALL fail the clip; the system SHALL NOT drop the audio to
succeed. One failed clip SHALL NOT affect another.

#### Scenario: An empty file
- **WHEN** a zero-byte `trasig.mp4` is requested
- **THEN** a proxy error names the clip and says the file is empty, and no ffmpeg runs

#### Scenario: An undecodable audio track
- **WHEN** a clip's audio codec cannot be decoded by ffmpeg
- **THEN** the clip fails with ffmpeg's cause, and no audio-less proxy is published in its place

#### Scenario: A vanished clip
- **WHEN** a clip is deleted between the listing and the request
- **THEN** the request fails with the operating system's reason, as a file that cannot be statted

### Requirement: A clip's proxy state is read from its cache entry
The engine SHALL classify a clip's proxy into exactly one of four states by looking only at the cache entry
and the failure marker for the clip's current cache key (the file's name, size and modification time, the
proxy version and the settings, as `proxy-encode` defines the key), without running any process, writing any
file or listing the cache directory:

- `ready`: the entry holds a non-empty proxy video, a non-empty filmstrip image and a recorded-facts file
  whose every required fact is present, of the right type, finite and in range, including the filmstrip's
  recorded geometry for the current filmstrip format, whose image is there with the size recorded. A fact the
  proxy job could not learn and recorded as `null` (the frame-rate variability, the rotation, the audio codec)
  is present. The state carries those facts.
- `failed`: the entry is not `ready`, its proxy video and facts are not both usable, and a failure marker for
  the key records a cause. The state carries the cause as one line with no server path. A marker is about
  the proxy: once a usable proxy and facts are published for the key, an earlier failure no longer describes
  the clip, and the state is decided by the filmstrip alone.
- `stale`: the entry is not `ready`, no failure marker exists, and the entry's recorded-facts file exists but
  cannot be used: invalid JSON, not an object, a required fact missing, mistyped, not finite or out of range,
  or the proxy or filmstrip file empty, or a `filmstrip` record that is malformed, of another format version or
  not the size of the image it describes.
- `absent`: anything else, including no entry at all and an entry that is incomplete because a file is not
  there yet (the proxy and its facts exist and the filmstrip is still being made: no `filmstrip` record, or a
  record whose image is not there).

The precedence SHALL be `ready`, then `failed`, then `stale`, then `absent`: a usable entry wins over an
older recorded failure, and a recorded failure wins over an unusable entry. A clip whose file changed since its
proxy was made has a different key and therefore reads `absent`; the reader SHALL NOT look for an entry made
for the previous file or an earlier proxy version. A cache that cannot be read for a reason other than the
entry or the cache directory not existing (permission denied, an I/O error) SHALL raise a typed error that
the caller reports as unknown; it SHALL NOT read as `absent`, and no state SHALL be returned for it.

The facts SHALL be exactly those the proxy job recorded; the reader SHALL NOT probe the proxy, SHALL NOT
default a missing fact, and SHALL NOT repair a damaged one (Principle I). The proxy cache is not an input of
the staleness fingerprint and reading it SHALL NOT change any render verdict.

#### Scenario: A complete entry is ready
- **WHEN** an entry holds a proxy video, a filmstrip image and facts for a 25 s 1080p25 clip
- **THEN** the state is `ready` and carries a duration of 25 s, 25/1 frames per second, the displayed size, the
  rotation, the audio codec and the filmstrip's tile geometry exactly as recorded

#### Scenario: A clip with no entry and no marker is absent
- **WHEN** the cache holds nothing for the clip's key
- **THEN** the state is `absent`, and the cache directory is unchanged

#### Scenario: A proxy awaiting its filmstrip is absent, not stale
- **WHEN** an entry holds a proxy video and recorded facts but no filmstrip image yet
- **THEN** the state is `absent` (nothing is usable yet), not `stale`

#### Scenario: Damaged facts make the entry stale
- **WHEN** an entry's recorded-facts file is truncated, or is valid JSON without `duration`, or records a
  duration of `0`, or a negative width, or a rotation of `360`
- **THEN** the state is `stale` and carries no facts, and nothing is repaired or written

#### Scenario: An empty proxy file makes the entry stale
- **WHEN** an entry's facts are valid but its proxy video is zero bytes
- **THEN** the state is `stale`

#### Scenario: A fact recorded as null is not damage
- **WHEN** a complete entry's facts record `rotation` `null`, `vfr` `null` and `audio_codec` `null`
- **THEN** the state is `ready` and the three facts are `null`, not defaulted

#### Scenario: A filmstrip the record does not describe makes the entry stale
- **WHEN** an entry's `filmstrip` record says the image has 41200 bytes and `filmstrip.jpg` has 7, or is empty,
  or the record is of another format version
- **THEN** the state is `stale`

#### Scenario: A filmstrip record whose image is gone is absent
- **WHEN** an entry's facts record a filmstrip and `filmstrip.jpg` is not there
- **THEN** the state is `absent`, as for a proxy still awaiting its filmstrip

#### Scenario: A recorded failure with nothing usable is failed
- **WHEN** the failure marker for the key records `Output has no audio stream` and no entry exists
- **THEN** the state is `failed` with that cause, and the cause is free of absolute paths

#### Scenario: A later success outranks an earlier failure
- **WHEN** a failure marker exists for the key and a complete entry exists too
- **THEN** the state is `ready`

#### Scenario: A published proxy supersedes an earlier failure while its filmstrip is pending
- **WHEN** a failure marker exists for the key and the entry holds a usable proxy and facts but no filmstrip yet
- **THEN** the state is `absent`, not `failed`

#### Scenario: A failure outranks an unusable entry
- **WHEN** a failure marker exists for the key and the entry's facts are damaged
- **THEN** the state is `failed`

#### Scenario: A version bump moves every clip to absent
- **WHEN** the proxy version is raised after a clip's entry was made
- **THEN** the clip's key differs, the state is `absent`, and the old entry is neither read nor deleted

#### Scenario: An unreadable cache is an error, not absence
- **WHEN** the entry directory exists but cannot be searched (permission denied)
- **THEN** reading raises the typed cache error and returns no state

#### Scenario: Reading runs no process
- **WHEN** a state is read with every process-starting facility made to raise
- **THEN** the state is returned and nothing was started

### Requirement: A failed proxy attempt is recorded for the clip's key
When an attempt to make a clip's proxy fails because of the clip (its probe, the encode, or its post-encode
verification; not a cache error, a cancel, or the filmstrip step, whose failure `clip-filmstrips` says is not
remembered), the engine SHALL record the cause in a failure marker for the clip's current cache key, written
atomically (a temporary file, then a rename) and best effort: failing to write the marker SHALL NOT replace
the attempt's own error and SHALL log a warning. The recorded cause SHALL be one line and SHALL NOT contain an
absolute file path. A successful attempt SHALL NOT need to remove a marker, because a ready entry outranks it;
a marker belongs to one key, so a changed file or a new proxy version never inherits it. The marker SHALL have
no expiry: it is cleared by success, and a retry (`auto-reel proxies` or a proxy job) always attempts the clip
again regardless of the marker.

#### Scenario: A failed encode leaves a marker and no entry
- **WHEN** preparing a clip fails because the encode exits non-zero
- **THEN** a failure marker for the clip's key holds a one-line cause, no entry directory exists, and no
  `.part` file remains

#### Scenario: A clip that cannot be probed is recorded
- **WHEN** preparing a clip fails because its probe fails
- **THEN** a failure marker for the clip's key holds the cause, and no entry exists

#### Scenario: A retry is not blocked by an earlier marker
- **WHEN** a clip has a failure marker and `auto-reel proxies` runs again on its event
- **THEN** the clip is attempted again, and on success the state reads `ready`

#### Scenario: A marker that cannot be written does not hide the real error
- **WHEN** an attempt fails and the cache directory is read-only
- **THEN** the attempt reports its own failure, a warning names the unwritable cache, and no second error is raised

#### Scenario: The cause carries no server path
- **WHEN** the encoder's message includes `/var/home/emil/library/2020/ev/C0047.MP4`
- **THEN** the recorded cause names the file by its name only
