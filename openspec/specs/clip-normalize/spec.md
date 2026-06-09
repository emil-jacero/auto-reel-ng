# clip-normalize Specification

## Purpose

Compose the ffmpeg command that turns one segment into a target-conforming intermediate: decode, fix
rotation and pixel aspect, scale + letterbox/pillarbox pad to the target canvas, tonemap HDR→SDR, composite
overlays, normalize audio, and encode — all built from `acceleration-profile` fragments with explicit
hardware↔system transfers and a guaranteed CPU fallback for every operation. Also decide, per segment,
whether it can skip normalization entirely (the stream-copy fast path).

## Requirements

### Requirement: Compose the normalize command from profile fragments

The engine SHALL build a segment's normalize command by requesting the relevant logical-op fragments from the
selected `AccelProfile` (decode, normalize=scale+pad, tonemap, overlay, encode) and composing them in order.
It SHALL use `insert_transfers()` to place `hwdownload`/`hwupload` markers wherever adjacent operations' frame
locations disagree, so no implicit GPU↔system round-trip is left unstated. The command SHALL target the
derived target spec (resolution, fps, codec, pixel format, SAR).

#### Scenario: VAAPI normalize chain is composed on AMD
- **WHEN** a non-conforming clip is normalized on a host whose selected profile is AMD VAAPI
- **THEN** the command uses the VAAPI decode, `scale_vaapi,pad_vaapi` normalize, and VAAPI encode fragments in order

#### Scenario: Frame-location transfer inserted around a CPU op
- **WHEN** a hardware-frame normalize feeds a CPU-only operation in the chain
- **THEN** the composed command contains an `hwdownload` before that operation (and an `hwupload` after, if a later op needs hardware frames)

### Requirement: Rotation and aspect normalization

The engine SHALL apply the segment's resolved rotation so footage is upright in the output, and SHALL force
square pixels (SAR 1:1) by scaling/padding to the target. When the selected profile lacks a working hardware
rotation path, the engine SHALL fall back to a CPU transpose for that segment. Padding SHALL preserve the
source aspect ratio (letterbox/pillarbox), centered, using the configured fill color.

#### Scenario: Rotated clip is uprighted
- **WHEN** a clip carries a 90-degree rotation
- **THEN** the normalized output is visually upright at the target resolution with SAR 1:1

#### Scenario: Rotation falls back to CPU when no hardware path
- **WHEN** the selected profile has no usable hardware rotation operation
- **THEN** the segment is rotated via a CPU transpose and the rest of the chain proceeds

### Requirement: HDR tonemapping with CPU fallback and slowness warning

When a segment's clip is flagged HDR (`media-probe`), the engine SHALL tonemap it to SDR before encoding. It
SHALL use the profile's hardware tonemap only when `can_tonemap_hw` is true; otherwise it SHALL use the CPU
`zscale,tonemap` fallback and SHALL emit a clear warning that the render will be substantially slower. SDR
clips SHALL NOT be tonemapped.

#### Scenario: HDR clip on AMD uses CPU tonemap and warns
- **WHEN** an HDR clip is normalized on a host where `can_tonemap_hw` is false
- **THEN** the command uses the CPU `zscale,tonemap` fallback and the engine logs a slowness warning

#### Scenario: SDR clip is not tonemapped
- **WHEN** a clip is not flagged HDR
- **THEN** no tonemap operation is added to its normalize command

### Requirement: Overlay compositing with CPU bridge fallback

For a segment carrying one or more `OverlaySpec` entries, the engine SHALL composite them during the normalize
pass. It SHALL use the profile's hardware overlay only when `can_overlay_hw` is true; otherwise it SHALL
composite via a CPU overlay bridge (downloading frames, overlaying, and re-uploading only as needed for that
segment), leaving overlay-free segments fully on the hardware path.

#### Scenario: Overlay on AMD uses the CPU bridge
- **WHEN** a segment with an overlay is normalized on a host where `can_overlay_hw` is false
- **THEN** the overlay is composited via the CPU bridge for that segment and overlay-free segments are unaffected

#### Scenario: Segment without overlays stays on the hardware path
- **WHEN** a segment has no overlays on a hardware-capable host
- **THEN** its normalize command contains no overlay operation and no overlay-driven transfer

### Requirement: Audio normalization and synthesized silence

The engine SHALL normalize each segment's audio to the target audio parameters (sample rate, channel count,
codec) so the concatenation step can join without re-encoding audio, avoiding the AAC-priming gap observed in
the concat spike. When a clip has no audio stream (`media-probe` reports absence), the engine SHALL synthesize
a silent track matching the target audio parameters and the segment's duration, so a mixed audio/no-audio set
stays A/V-aligned.

#### Scenario: Audio resampled to target parameters
- **WHEN** a clip's audio differs from the target audio parameters
- **THEN** the normalized segment's audio matches the target sample rate, channel count, and codec

#### Scenario: Video-only clip gets synthesized silence
- **WHEN** a clip has no audio stream
- **THEN** the normalized segment contains a silent audio track matching the target audio parameters and the segment duration

### Requirement: Trims realized as kept spans

The engine SHALL realize a segment's kept span by seeking to its in-point and limiting to its out-point during
normalization, so removed (trimmed) footage never reaches the output. Multiple kept spans of one clip SHALL be
normalized as separate segments.

#### Scenario: Kept span excludes trimmed footage
- **WHEN** a segment represents the footage after a cut span ending at 3.2s
- **THEN** the normalized output begins at 3.2s of the source and contains none of the removed span

### Requirement: Per-segment copy eligibility

The engine SHALL decide, per segment, whether it can skip normalization (the stream-copy fast path). A segment
SHALL be copy-eligible only when it is a **source** segment that is **untrimmed** (covers the whole clip), has
**no overlays**, requires **no rotation or tonemap**, and whose probed video and audio parameters are equal to
the target spec. A copy-eligible segment SHALL be passed through unchanged; every other segment SHALL be
normalized. Synthetic segments SHALL always be encoded to the target spec.

#### Scenario: Conforming untouched clip is copy-eligible
- **WHEN** a source segment covers an entire clip whose probed parameters already equal the target and has no overlays, rotation, or tonemap need
- **THEN** the engine marks it copy-eligible and does not normalize it

#### Scenario: Trimmed or decorated segment is not copy-eligible
- **WHEN** a segment is trimmed, carries an overlay, needs rotation/tonemap, or differs from the target spec
- **THEN** the engine marks it ineligible and normalizes it

#### Scenario: Synthetic segment is always encoded
- **WHEN** a synthetic segment is processed
- **THEN** it is encoded to the target spec and is never treated as copy-eligible

### Requirement: Fail loud on segment normalization failure

When a segment's normalize command fails, the engine SHALL raise a typed error identifying the segment and
carrying the underlying ffmpeg failure detail. It SHALL NOT silently drop the segment or substitute a
placeholder, because dropping a clip changes the edit.

#### Scenario: Normalize failure is surfaced, not swallowed
- **WHEN** a segment's normalize command exits non-zero
- **THEN** the engine raises a typed error naming the segment and exposing the ffmpeg exit code and stderr

### Requirement: Synthetic segment materialization via a producer

The engine SHALL materialize a synthetic segment through its registered `segment-producer` and compose a
target-conforming normalize command from the result, instead of rejecting synthetic segments. The command
SHALL loop the producer's rendered image for the segment duration, apply a fade-in and fade-out over the
producer-supplied fade timings, synthesize a silent audio track matching the target audio parameters and the
segment duration (reusing the video-only silence path), and encode to the target codec, pixel format, frame
rate, and resolution. The synthetic path SHALL be **overlay-free** — it SHALL NOT use `overlay`/`overlay_vaapi`
or a CPU overlay bridge — so a card renders fully through the encode path on every vendor, including AMD where
`overlay_vaapi` is unavailable. A synthetic segment that has no registered producer SHALL fail loud (per the
`segment-producer` capability), never silently.

#### Scenario: Title segment is encoded from its rendered image
- **WHEN** a synthetic title segment is normalized
- **THEN** the command loops the producer's card image for the segment duration, encodes it to the target codec/resolution/fps, and includes a silent audio track matching the target audio parameters

#### Scenario: Card fades applied
- **WHEN** a synthetic title segment specifies a fade-in and fade-out
- **THEN** the normalize command applies a fade-in over the start and a fade-out over the end of the card

#### Scenario: Synthetic path uses no overlay
- **WHEN** a synthetic segment is normalized on a host where `can_overlay_hw` is false
- **THEN** the command contains no overlay operation and no overlay-driven transfer, and still produces a target-conforming segment

#### Scenario: Chosen codec is honored
- **WHEN** the target spec's video codec is AV1 and a synthetic title segment is normalized
- **THEN** the synthetic segment is encoded with the target's AV1 encoder, not a separate hardcoded codec
