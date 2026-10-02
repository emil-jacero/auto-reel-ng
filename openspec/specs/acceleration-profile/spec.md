# acceleration-profile Specification

## Purpose

Turn the verified capability inventory into a per-vendor acceleration-profile API: for each logical operation (decode, normalize=scale+pad, overlay, tonemap, encode) emit the correct ffmpeg argument fragments, track where output frames live so callers know when an `hwupload`/`hwdownload` round-trip is required, guarantee a CPU fallback for every operation, and auto-select the best usable accelerator with explicit override and a reserved per-job device selector.

## Requirements

### Requirement: Per-vendor argument fragments per logical operation

An acceleration profile SHALL, for each logical operation it supports (decode, normalize=scale+pad, overlay,
tonemap, encode), emit the correct ffmpeg argument fragments for its vendor. The engine SHALL provide profiles
for AMD (VAAPI), NVIDIA (CUDA/NVENC), Intel (QSV/VAAPI), and CPU. The AMD profile's fragments SHALL match the
verified spike results: hardware decode via `-hwaccel vaapi -hwaccel_output_format vaapi`, normalize via
`scale_vaapi,pad_vaapi`, and encode via the VAAPI encoders.

#### Scenario: AMD normalize fragment uses native scale+pad
- **WHEN** the AMD profile is asked for a normalize fragment to a target resolution
- **THEN** it emits a `scale_vaapi`+`pad_vaapi` fragment (not a CPU `scale,pad`)

#### Scenario: Encoder fragment matches selected codec
- **WHEN** a profile is asked to encode HEVC and its self-tested HEVC hardware encoder is usable
- **THEN** it emits that hardware encoder fragment for HEVC

### Requirement: Frame-location tracking

Each emitted operation SHALL declare where its output frames live (a hardware frame context vs system memory),
so a caller can determine when an explicit `hwupload`/`hwdownload` round-trip is required between operations.

#### Scenario: Hardware op reports hardware frames
- **WHEN** the AMD profile emits a `scale_vaapi` normalize op
- **THEN** the op declares its output frames reside in a VAAPI hardware frame context

#### Scenario: Mixed-location chain forces a transfer marker
- **WHEN** a hardware-frame output must feed an operation that only accepts system-memory frames
- **THEN** the profile signals that an `hwdownload`/`hwupload` transfer is required between them

### Requirement: Guaranteed CPU fallback

Every logical operation SHALL have a CPU implementation, and a profile SHALL fall back to it when the
hardware path for that operation is not usable (per the self-test). Tonemap and overlay in particular SHALL
fall back to CPU (`zscale,tonemap`; `overlay`) when the selected accelerator lacks them.

#### Scenario: Tonemap falls back to CPU on AMD
- **WHEN** the selected AMD accelerator reports `can_tonemap_hw=false` and a clip requires HDR→SDR
- **THEN** the profile emits the CPU `zscale,tonemap` fragment for that operation

#### Scenario: CPU-only host still produces every operation
- **WHEN** no hardware accelerator is usable
- **THEN** the CPU profile supplies a working fragment for decode, normalize, overlay, tonemap, and encode

### Requirement: Best-accelerator selection with override and reserved device targeting

The engine SHALL auto-select the best usable accelerator by capability (D-3) and SHALL accept an explicit
override naming a vendor or a specific enumerated device. Each render request SHALL carry an optional device
selector field (default = auto) reserved for future multi-GPU targeting (D-4); v1 behavior MAY simply use the
first usable device.

#### Scenario: Auto-pick chooses a usable hardware accelerator over CPU
- **WHEN** at least one hardware accelerator passes the self-test and no override is given
- **THEN** the engine selects that hardware accelerator rather than the CPU profile

#### Scenario: Explicit override is honored
- **WHEN** a request overrides selection to a specific vendor or device
- **THEN** the engine uses that profile/device if usable, or fails with a clear error if it is not

#### Scenario: Device selector defaults to auto
- **WHEN** a render request omits the device selector
- **THEN** the selector defaults to auto and the engine picks a usable device without requiring caller input

### Requirement: Clips are padded where the fill is correct

When normalizing a clip to the canvas, the caller SHALL tell the profile whether the clip needs padding. A
clip needs padding when its pixel aspect or its display aspect differs exactly from the canvas aspect. Both
are taken after rotation; display aspect also has the sample aspect ratio applied. Pixel aspect counts
because the scale fits by pixels and ignores the sample aspect ratio. Exactness means compared as a ratio,
not a rounded decimal.

The profile SHALL emit a hardware pad only when the pad-fill capability flag is true. When the clip needs
padding and the flag is false, the profile SHALL fall back to the CPU scale-and-pad for that clip, with the
frame transfers the chain requires. A clip that needs no padding SHALL keep the hardware scale path whatever
the flag says. No clip SHALL be rendered with a padded region of any colour other than the requested fill.

#### Scenario: A portrait clip gets black bars on a host with a faulty hardware pad
- **WHEN** a 1440×1920 phone clip is normalized to a 1920×1080 canvas on a host whose pad-fill flag is false
- **THEN** its bars are black: the clip is scaled and padded on the CPU between the hardware decode and the
  hardware encode

#### Scenario: A 16:9 clip stays on the GPU
- **WHEN** a 3840×2160 or 1280×720 clip is normalized to a 1920×1080 canvas on the same host
- **THEN** it is scaled on the GPU, with no CPU scale-or-pad stage and no frame transfer

#### Scenario: A nearly-16:9 clip is still padded correctly
- **WHEN** a 1920×1088 clip is normalized to a 1920×1080 canvas on the same host
- **THEN** it is treated as needing padding, and any padded rows are black

#### Scenario: A correct hardware pad is used for every clip
- **WHEN** the pad-fill flag is true
- **THEN** clips that need padding are padded on the GPU

### Requirement: A hardware decode shares its device with the filter graph

When a profile decodes on a hardware device, the decode SHALL use a named device that the filter graph also
uses. A CPU stage placed between the hardware decode and a hardware encode can then upload its frames back
to the device. The CPU stages concerned are padding, rotation, tonemap and an overlay bridge. The same
single device SHALL serve decode, filters and upload, so no second device is opened for one command.

#### Scenario: A rotated clip renders on the GPU path
- **WHEN** a clip with a 90° rotation is normalized with hardware decode and a hardware encoder, so a CPU
  `transpose` sits between them
- **THEN** the command succeeds and the output is upright, rather than failing because the upload has no
  device

#### Scenario: One device per command
- **WHEN** a hardware-decoded clip's normalize command is built
- **THEN** it initializes exactly one named hardware device, and uses it for decode and for the filter graph

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
