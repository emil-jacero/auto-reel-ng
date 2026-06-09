## ADDED Requirements

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
