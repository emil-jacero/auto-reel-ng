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

The engine SHALL apply a source segment's rotation so footage is upright in the output, and SHALL force
square pixels (SAR 1:1) by scaling/padding to the target. The rotation applied SHALL be the clip's **display
rotation** (the container's, as the probe reports it) **plus** the segment's resolved `rotate` (`reel-document`),
both measured clockwise and added modulo 360. The display rotation SHALL NOT be replaced by an explicit
`rotate`. The probe reports the display rotation as the display matrix's angle, which is counter-clockwise, so a
clip with a probed `rotation` of 270 (matrix -90) is turned 90 degrees clockwise.

The engine SHALL apply that total itself, in the filter chain, the same way on every profile. A clip with a
display rotation SHALL be opened with its automatic rotation off, so the turn happens exactly once, and the
output SHALL carry no display rotation of its own. The total turn SHALL be one CPU transpose chain: when the
selected profile keeps frames in hardware memory, the chain SHALL sit between the explicit download and upload
of the frames, and the engine SHALL NOT rely on a hardware rotation filter. A total of 0 SHALL add no rotation
stage. Padding SHALL preserve the source aspect ratio (letterbox/pillarbox), centered, using the configured
fill color; whether a clip needs padding SHALL be decided from the picture after the **total** turn, so a clip
turned back to its stored orientation is judged by its stored shape. When both a display rotation and a
`rotate` apply, the engine SHALL log the clip, both values and the total at info level.

#### Scenario: Rotated clip is uprighted
- **WHEN** a clip carries a 90-degree display rotation and its segment has no `rotate`
- **THEN** the normalized output is visually upright at the target resolution with SAR 1:1 and no display
  rotation of its own, on the CPU profile and on a hardware profile alike

#### Scenario: Rotation falls back to CPU when no hardware path
- **WHEN** the selected profile has no usable hardware rotation operation
- **THEN** the segment is rotated via a CPU transpose and the rest of the chain proceeds

#### Scenario: A hardware profile no longer renders a phone clip sideways
- **WHEN** a 1280x720 H.264 clip with a display matrix of -90 (probed rotation 270) is normalized on the AMD
  VAAPI profile with hardware decode and no `rotate`
- **THEN** the command opens the clip with automatic rotation off, downloads the frames, applies one clockwise
  transpose, and uploads them, and the output is upright (portrait, pillarboxed in the landscape canvas)

#### Scenario: `rotate` adds to the display rotation
- **WHEN** the same clip has `rotate: 90`
- **THEN** the total is 180 degrees: two clockwise transposes, the output is the upright picture turned a further
  quarter turn clockwise, and the same output results on the CPU profile

#### Scenario: `rotate` can turn a clip back
- **WHEN** a clip with a clockwise display rotation of 90 has `rotate: 270`
- **THEN** the total is 0, no rotation stage is emitted, the clip is judged by its stored 1280x720 shape for
  padding, and the output shows the picture as it is stored

#### Scenario: A clip without a display rotation
- **WHEN** a portrait clip with no display rotation has `rotate: 90`, `180` or `270`
- **THEN** the output is that clip turned that many degrees clockwise, with the arguments it had before this
  change (no automatic-rotation flag)

#### Scenario: Both rotations are logged
- **WHEN** a clip with a display rotation of 90 and `rotate: 90` is normalized
- **THEN** an info line names the clip, 90, 90 and a total of 180

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
the target spec. A clip requires rotation when it has a display rotation other than 0 **or** its segment has a
`rotate` that is not a multiple of 360, so a clip whose stored size already equals the target is still
normalized when it is displayed turned. A copy-eligible segment SHALL be passed through unchanged; every other
segment SHALL be normalized. Synthetic segments SHALL always be encoded to the target spec.

#### Scenario: Conforming untouched clip is copy-eligible
- **WHEN** a source segment covers an entire clip whose probed parameters already equal the target and has no overlays, rotation, or tonemap need
- **THEN** the engine marks it copy-eligible and does not normalize it

#### Scenario: Trimmed or decorated segment is not copy-eligible
- **WHEN** a segment is trimmed, carries an overlay, needs rotation/tonemap, or differs from the target spec
- **THEN** the engine marks it ineligible and normalizes it

#### Scenario: A display-rotated clip of the target's stored size is normalized
- **WHEN** a 1280x720, 30 fps, H.264, AAC 48 kHz stereo clip with a 90-degree display rotation is the only clip of
  an event whose target is 1280x720
- **THEN** it is marked ineligible, it is normalized upright, and the finished movie carries no display rotation

#### Scenario: A display rotation cancelled by `rotate` is still not copy-eligible
- **WHEN** a conforming clip has a 90-degree display rotation and its segment has `rotate: 90` (total turn 0)
- **THEN** the engine marks it ineligible and normalizes it; a display-rotated clip is never stream-copied

#### Scenario: A segment with `rotate` is not copy-eligible
- **WHEN** an otherwise conforming segment has `rotate: 180`
- **THEN** the engine marks it ineligible; with `rotate: 0` or no `rotate` it is eligible

#### Scenario: Synthetic segment is always encoded
- **WHEN** a synthetic segment is processed
- **THEN** it is encoded to the target spec and is never treated as copy-eligible

### Requirement: Fail loud on segment normalization failure

When a segment's normalize command fails, the engine SHALL raise a typed error identifying the segment and
carrying the underlying ffmpeg failure detail. The only softening is the single software-decode retry of a
hardware-decode initialisation failure; a retry that fails SHALL be raised with the same detail, and a failed
first attempt SHALL never be discarded without the warning that records it. It SHALL NOT silently drop the
segment or substitute a placeholder, because dropping a clip changes the edit.

#### Scenario: Normalize failure is surfaced, not swallowed
- **WHEN** a segment's normalize command exits non-zero
- **THEN** the engine raises a typed error naming the segment and exposing the ffmpeg exit code and stderr

#### Scenario: A recovered hardware-decode failure is still reported
- **WHEN** a segment's hardware-decode normalize fails with an initialisation error and the software retry succeeds
- **THEN** the render succeeds and a warning recording the first failure is logged and returned in the result

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

### Requirement: Decode is chosen per clip

The engine SHALL choose a source segment's decode fragment from the clip's probed codec and pixel format, by
asking the selected profile whether the clip is hardware-decodable (`acceleration-profile`). A clip the
hardware cannot decode SHALL be decoded in software and its frames SHALL reach a hardware filter or encoder
through an explicit `hwupload`, with the single named hardware device the chain needs, exactly as for a
segment whose hardware decode is unavailable. The rest of the chain (rotation, scale and pad, tonemap,
encode) SHALL be unchanged by the choice. A hardware-decodable clip SHALL produce the same command as before
this requirement. The choice SHALL NOT change what is rendered for any input that rendered before, and the
engine SHALL log the software decode of a clip the profile reported as not hardware-decodable at info level
(an expected, non-error condition).

#### Scenario: MPEG-4 clip on the AMD VAAPI profile
- **WHEN** a 16:9 `mpeg4` clip in an `.avi` container is normalized on a host whose selected profile is AMD
  VAAPI
- **THEN** the command has no `-hwaccel` flag, names one device with `-init_hw_device vaapi=va:<node>
  -filter_hw_device va`, applies `format=nv12,hwupload` before `scale_vaapi`, and encodes with the VAAPI encoder

#### Scenario: Rotated MPEG-4 clip needs both the transpose and the upload
- **WHEN** an `mpeg4` clip carrying a 90-degree rotation is normalized on the AMD VAAPI profile
- **THEN** the CPU `transpose` runs on the software-decoded frames, then `format=nv12,hwupload` precedes
  `scale_vaapi`, and one hardware device is named

#### Scenario: MPEG-4 clip that needs bars on a host with a faulty hardware pad
- **WHEN** a 4:3 `mpeg4` clip is normalized on an AMD host whose pad-fill flag is false
- **THEN** the chain is the CPU scale and pad on the software-decoded frames followed by a single
  `format=nv12,hwupload`, and the bars are black

#### Scenario: H.264 clip keeps the hardware decode
- **WHEN** an 8-bit `h264` `yuv420p` clip is normalized on the AMD VAAPI profile
- **THEN** the command is the same hardware-decode command it was before, with no `hwupload`

#### Scenario: 10-bit H.264 clip is decoded in software
- **WHEN** a `yuv420p10le` `h264` clip is normalized on the AMD VAAPI profile
- **THEN** it takes the software decode and `format=nv12,hwupload` path, so the encoder receives 8-bit frames

#### Scenario: CPU profile is unaffected
- **WHEN** an `mpeg4` clip is normalized on the CPU profile
- **THEN** the command is the CPU command it was before

#### Scenario: A vendor with no verified upload device keeps its hardware decode
- **WHEN** a clip outside the NVIDIA or Intel `hw_decode` table is normalized, and that profile has no
  verified device recipe for uploading system frames
- **THEN** the command is the hardware-decode command it was before this change, because the engine does not
  choose a software decode it cannot upload from

#### Scenario: A software decode that cannot be built fails loud
- **WHEN** a software decode is forced (the retry) for a profile with no verified upload device recipe
- **THEN** the engine raises a typed error that names the segment, the first ffmpeg failure and tells the user
  to render with `--device cpu`, and does not emit a command ffmpeg would reject

### Requirement: Hardware decode initialisation failure is retried once in software

When a source segment's hardware-decode normalize command fails with an ffmpeg hardware-decode initialisation
error (stderr containing `hwaccel initialisation returned error` or `Failed setup for format`), the engine
SHALL log a warning naming the segment, rebuild that one segment's command with software decode, and run it
once. The retry SHALL replace the failed attempt's output, SHALL apply to that segment only, and SHALL NOT
apply to a command that already used software decode, to a synthetic segment, or to any other failure. The
warning SHALL also be included in the render result's warnings. The engine SHALL NOT retry more than once per
segment.

#### Scenario: Table says hardware, driver says no
- **WHEN** an `h264` clip, listed as hardware-decodable, is normalized on a GPU whose decoder rejects its
  profile, and ffmpeg fails with `Failed setup for format vaapi: hwaccel initialisation returned error`
- **THEN** a warning naming the segment is logged, the segment is normalized again with software decode and
  succeeds, the other segments are untouched, and the render result carries the warning

#### Scenario: Unrelated failure is not retried
- **WHEN** a hardware-decode normalize fails with a stderr that does not mention a hardware-decode
  initialisation error (for example a corrupt input)
- **THEN** no retry runs and the engine raises the typed segment error

#### Scenario: Already-software segment is not retried
- **WHEN** a software-decode normalize fails
- **THEN** no retry runs and the engine raises the typed segment error

#### Scenario: Retry that fails is reported with both attempts
- **WHEN** the software-decode retry also fails
- **THEN** the engine raises a typed error naming the segment, carrying the retry's ffmpeg failure and stating
  that the hardware-decode attempt failed first; no movie file is finalized
