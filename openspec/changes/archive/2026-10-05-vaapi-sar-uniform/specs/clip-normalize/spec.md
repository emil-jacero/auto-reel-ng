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

Every normalized segment SHALL carry an explicit SAR of 1:1 in its output, on every profile (CPU, VAAPI, QSV,
NVENC) and for every total turn including 0: the normalize chain SHALL end by setting the sample aspect ratio to
1:1 rather than passing the source's through, so a source whose SAR is unset (`N/A`, `0:1` or absent) never yields
a segment with an unset SAR. This SHALL hold for an overlay-free segment, for the head of a segment under a video
card (the CPU overlay bridge) and for its tail on the hardware path. On a profile that keeps frames in hardware
memory the SAR SHALL be set without an added download or upload.

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

#### Scenario: A turned-back clip without a SAR is square on VAAPI
- **WHEN** a 1920x1080 clip with no SAR (`N/A`) and a display rotation of 90 has `rotate: 270` (total 0) and is
  normalized on the AMD VAAPI profile
- **THEN** the command's video chain sets the SAR to 1:1 after the hardware scale, adds no `hwdownload` or
  `hwupload` for it, and the segment probes `sample_aspect_ratio` 1:1

#### Scenario: Every profile's normalize sets SAR 1:1
- **WHEN** a source segment is normalized on the CPU, VAAPI, QSV or NVENC profile, with or without padding
- **THEN** its video chain sets the SAR to 1:1

#### Scenario: Both halves of a video-card anchor are square on VAAPI
- **WHEN** a clip without a SAR is the anchor of a video card and is normalized on the AMD VAAPI profile as a
  card-window head and a tail
- **THEN** the head's command and the tail's command both set the SAR to 1:1, and both segments probe
  `sample_aspect_ratio` 1:1

#### Scenario: The Provklipp case renders on VAAPI
- **WHEN** an event whose one chapter holds a 1080p25 H.264 clip and a HEVC clip with no SAR, a display rotation of
  90 and `rotate: 270` is rendered with the AMD VAAPI profile
- **THEN** the render succeeds, and every intermediate segment and the final movie probe `sample_aspect_ratio` 1:1

