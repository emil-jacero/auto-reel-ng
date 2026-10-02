## ADDED Requirements

### Requirement: Hardware decode is used only for clips the hardware can decode

An acceleration profile SHALL state, for a given source codec and pixel format, whether its hardware decoder
can decode that clip. A clip is hardware-decodable only when the accelerator's hardware decode passed the
startup self-test, the codec is one its hardware decoder handles, the pixel format is 4:2:0, and the bit depth
does not exceed what the decoder handles for that codec. When the pixel format is unknown the answer SHALL
depend on the codec alone; the engine SHALL NOT assume a pixel format the probe did not report. The profile
SHALL emit its hardware decode fragment only for a hardware-decodable clip; for any other clip it SHALL emit
the CPU decode fragment (no hardware flags, frames in system memory) and leave the rest of the chain to the
usual frame-location transfers. The CPU profile SHALL always emit the CPU decode fragment.

The set of codecs and bit depths a hardware decoder handles SHALL be part of the cached capability data, so
that a cache written without it is not reused.

#### Scenario: An MPEG-4 Part 2 clip on AMD decodes in software
- **WHEN** the AMD profile is asked for the decode fragment of an `mpeg4` clip (`yuv420p`) on a host whose
  hardware decode passed the self-test with an h264/hevc/vp9/av1 decoder set
- **THEN** it emits the CPU decode fragment, with no `-hwaccel` flag and frames in system memory

#### Scenario: An H.264 clip on AMD still decodes in hardware
- **WHEN** the AMD profile is asked for the decode fragment of an 8-bit `h264` `yuv420p` clip
- **THEN** it emits the VAAPI decode fragment, `-hwaccel vaapi -hwaccel_device va -hwaccel_output_format vaapi`,
  exactly as before

#### Scenario: A 10-bit H.264 clip is not hardware-decodable on AMD
- **WHEN** the AMD profile is asked about an `h264` clip in `yuv420p10le`, whose decoder limit for `h264` is 8-bit
- **THEN** it reports the clip as not hardware-decodable and emits the CPU decode fragment

#### Scenario: A 10-bit HEVC clip is hardware-decodable on AMD
- **WHEN** the AMD profile is asked about an `hevc` clip in `yuv420p10le`, whose decoder limit for `hevc` is 10-bit
- **THEN** it reports the clip as hardware-decodable

#### Scenario: A 4:2:2 clip is not hardware-decodable
- **WHEN** a profile is asked about an `h264` clip in `yuv422p`
- **THEN** it reports the clip as not hardware-decodable whatever the codec table says

#### Scenario: An unknown pixel format is decided by codec alone
- **WHEN** a profile is asked about an `h264` clip whose probe reported no pixel format
- **THEN** it reports the clip as hardware-decodable, and does not invent a pixel format

#### Scenario: A host whose hardware decode failed its self-test decodes everything in software
- **WHEN** an accelerator's hardware decode did not pass the self-test
- **THEN** no clip is reported hardware-decodable and every decode fragment is the CPU one

#### Scenario: An older capability cache is re-detected
- **WHEN** the on-disk capability cache was written before the decoder set was recorded
- **THEN** it is not reused and the host is detected and self-tested again
