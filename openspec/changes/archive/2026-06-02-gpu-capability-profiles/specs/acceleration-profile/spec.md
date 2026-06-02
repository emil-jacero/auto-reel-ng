## ADDED Requirements

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
