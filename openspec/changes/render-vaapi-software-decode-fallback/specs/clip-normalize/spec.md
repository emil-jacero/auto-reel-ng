## ADDED Requirements

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

## MODIFIED Requirements

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
