## MODIFIED Requirements

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

#### Scenario: A segment with `rotate` is not copy-eligible
- **WHEN** an otherwise conforming segment has `rotate: 180`
- **THEN** the engine marks it ineligible; with `rotate: 0` or no `rotate` it is eligible

#### Scenario: Synthetic segment is always encoded
- **WHEN** a synthetic segment is processed
- **THEN** it is encoded to the target spec and is never treated as copy-eligible
