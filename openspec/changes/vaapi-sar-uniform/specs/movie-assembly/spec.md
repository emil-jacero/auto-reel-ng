## MODIFIED Requirements

### Requirement: Equivalence pre-flight before stream-copy concat

Before concatenating with stream copy, the engine SHALL verify — via `ffprobe`, over the full segment set —
that all segments share the copy-critical parameters: video `codec_name`, `profile`, `width`, `height`,
`sample_aspect_ratio`, `pix_fmt`, and `time_base`, plus audio `codec_name`, `sample_rate`, `channels`, and
`channel_layout`. Only when every segment matches SHALL the engine use stream-copy concat. The engine SHALL
NOT use the ffmpeg exit code to decide copy safety, because mismatched resolution/SAR mux at exit 0 while
breaking playback.

The `sample_aspect_ratio` SHALL be compared **normalized**, by the same rule copy eligibility uses: an absent,
empty, `N/A` or `0:1` value (an unset SAR, displayed as square) SHALL count as `1:1`. Any other value SHALL be
compared as probed, so a segment with a concrete non-square SAR still differs from a 1:1 one. No other field
SHALL be normalized.

#### Scenario: Uniform set concatenates by stream copy
- **WHEN** all segments share the copy-critical video and audio parameters
- **THEN** the engine concatenates them with the concat demuxer and `-c copy`

#### Scenario: Mismatch forces re-encode rather than a silent-broken copy
- **WHEN** the probed segments differ in resolution or SAR
- **THEN** the engine does not stream-copy them and instead re-encodes to a uniform set before joining

#### Scenario: Exit code is never the copy-safety signal
- **WHEN** deciding whether to stream-copy
- **THEN** the decision is made from probe data before running concat, not from a concat command's exit status

#### Scenario: An unset SAR matches 1:1
- **WHEN** two segments agree on every copy-critical field except that one probes `sample_aspect_ratio` `N/A`
  (or `0:1`, or none) and the other `1:1`
- **THEN** the set is uniform and is joined by stream copy without a re-encode or a render error

#### Scenario: A real SAR difference still blocks the copy
- **WHEN** one segment probes `sample_aspect_ratio` `4:3` and another `1:1`, all else equal
- **THEN** the set is not uniform
