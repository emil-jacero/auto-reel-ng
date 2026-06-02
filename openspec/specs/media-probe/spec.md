# media-probe Specification

## Purpose

Extract immutable, typed media metadata from each clip in a single ffprobe pass, failing loud rather than fabricating values, and capturing rotation, aspect ratio, HDR, frame rate, audio, and creation time.

## Requirements

### Requirement: Single-pass typed metadata extraction

The engine SHALL extract media metadata using exactly one `ffprobe -show_format -show_streams -print_format
json` invocation per file and SHALL return an immutable, typed metadata object. The object SHALL include:
duration, frame rate, video codec and profile, width, height, sample aspect ratio (SAR), display aspect ratio
(DAR), pixel format, video bitrate, and audio codec, sample rate, channel count, and channel layout. The
engine SHALL NOT use timing hacks (e.g. fixed sleeps) around probing.

#### Scenario: Valid file yields complete typed metadata
- **WHEN** a readable, non-empty video file is probed
- **THEN** the engine returns a typed metadata object populated from the single ffprobe JSON result

#### Scenario: No redundant probes
- **WHEN** metadata is extracted for one file
- **THEN** exactly one ffprobe process is invoked for that file

### Requirement: Fail loud, never fabricate

The engine SHALL raise a typed error when a file does not exist, is empty, has no video stream, or cannot be
parsed by ffprobe. It SHALL NOT substitute assumed values (such as 1920×1080 or 25 fps) for any field. A
caller iterating over many files SHALL be able to skip the failing file while continuing with the rest.

#### Scenario: Unprobeable file raises rather than guesses
- **WHEN** a file cannot be parsed by ffprobe or has no video stream
- **THEN** the engine raises a typed error and returns no metadata object

#### Scenario: Empty file is rejected
- **WHEN** a zero-byte file is probed
- **THEN** the engine raises a typed error identifying the file as empty

#### Scenario: Batch continues past a bad file
- **WHEN** one file in a set fails probing
- **THEN** the failure is reported for that file and the remaining files are still probed

### Requirement: Rotation and aspect-ratio capture

The engine SHALL capture rotation from the stream's display matrix / `rotation` tag and SHALL capture SAR and
DAR, so downstream normalization can correct sideways footage and non-square pixels. When rotation metadata
is absent, the engine SHALL report no rotation rather than assuming a value.

#### Scenario: Rotated clip reports its rotation
- **WHEN** a clip carries a 90-degree display-matrix rotation
- **THEN** the metadata reports a 90-degree rotation

#### Scenario: Non-square pixels are reported
- **WHEN** a clip has a SAR other than 1:1
- **THEN** the metadata reports the actual SAR and the derived DAR

### Requirement: HDR detection

The engine SHALL flag a clip as HDR when its color transfer characteristics indicate PQ (`smpte2084`) or HLG
(`arib-std-b67`), and SHALL expose the color transfer value. This flag exists so later stages can decide
whether tonemapping is required.

#### Scenario: PQ clip is flagged HDR
- **WHEN** a clip reports color transfer `smpte2084`
- **THEN** the metadata flags the clip as HDR and records the transfer value

#### Scenario: SDR clip is not flagged
- **WHEN** a clip reports a standard `bt709` transfer
- **THEN** the metadata does not flag the clip as HDR

### Requirement: Frame-rate resolution

The engine SHALL determine frame rate by preferring `avg_frame_rate` and falling back to `r_frame_rate`,
parsing the rational form, and SHALL reject implausible values (≤ 0 or > 1000) by raising rather than
silently substituting a default.

#### Scenario: Average frame rate preferred
- **WHEN** a clip exposes a valid `avg_frame_rate`
- **THEN** the metadata frame rate is derived from `avg_frame_rate`

#### Scenario: Implausible frame rate fails loud
- **WHEN** both frame-rate fields are zero or unparseable
- **THEN** the engine raises a typed error rather than assuming a frame rate

### Requirement: Audio and creation-time handling

The engine SHALL represent the absence of an audio stream explicitly (not as fabricated audio parameters) and
SHALL derive creation time from ffprobe format/stream tags, with an optional, explicitly enabled exiftool
fallback. exiftool SHALL NOT be invoked per clip by default.

#### Scenario: Video-only clip reports no audio
- **WHEN** a clip has no audio stream
- **THEN** the metadata explicitly indicates the absence of audio rather than default channel/bitrate values

#### Scenario: Creation time from tags without exiftool
- **WHEN** a clip carries a creation-time tag and the exiftool fallback is not enabled
- **THEN** the metadata creation time comes from the ffprobe tag and no exiftool process is spawned
