## ADDED Requirements

### Requirement: A timed-overlay segment is split at its window

When normalizing a source segment that carries a timed overlay, the engine SHALL split it into a **head** and a
**tail** over the same clip, so the CPU overlay bridge covers only the overlay's window. The overlay's window
SHALL be the producer-materialized duration clamped to the segment's length. The head SHALL carry the overlay and
cover the segment from its start for `N / fps` seconds, where `fps` is the target frame rate and `N` is the
window's length in target frames, rounded up to a whole number of frames. The tail SHALL carry no overlay and
cover the rest of the segment, starting exactly where the head ends. A whole clip SHALL be split by its probed
duration. Both pieces SHALL be trimmed segments (never stream-copied) with the segment's chapter, identity,
`rotate` and source path; the tail SHALL NOT carry the overlay or its card input.

The segment SHALL NOT be split when the tail would be shorter than 1 s, nor when the window covers the whole
segment; it is then normalized whole, as before. A segment without a timed overlay SHALL be unchanged. The split
is internal to the segment's normalize step: the segment stays one entry for progress, copy eligibility, measured
durations and chapter aggregation, and a dry run SHALL list the head, the tail and the join commands a run executes.

The pieces SHALL be encoded video-only and joined into the segment's one intermediate by a join command that
stream-copies their video and encodes the segment's audio once, from the source, over the whole segment. The joined
result SHALL be frame-exact: it SHALL have the video frames the unsplit segment had, none dropped or duplicated, with
each frame at the same presentation time; the movie's duration and its chapter start and end times SHALL equal the
unsplit render's within one frame. The audio SHALL be continuous across the join: the movie's audio length SHALL be
within one AAC frame (1024 samples) of the unsplit render's, with no dropout or click at the join. A clip without an
audio track SHALL keep synthesized silence of the segment's length.

#### Scenario: A 180 s first clip under a 7 s card is split in two
- **WHEN** a segment of a 180 s clip carries a 7 s timed overlay and the target is 30 fps
- **THEN** the head is 0 s to 7 s carrying the overlay and the tail 7 s to 180 s with no overlay, and
  both are trimmed segments that are not copy-eligible

#### Scenario: The split lands on the frame grid
- **WHEN** a segment carries a 7.01 s timed overlay at 30 fps
- **THEN** the head ends at 211/30 s, the overlay's window stays 7.01 s, and the tail starts at 211/30 s

#### Scenario: A trimmed anchor splits inside its span
- **WHEN** the anchor is the span 12 s to 60 s of its clip and carries a 7 s timed overlay
- **THEN** the head is 12 s to 19 s and the tail 19 s to 60 s

#### Scenario: No frame is lost or repeated at the join
- **WHEN** a 20 s test clip with a frame counter burned in is rendered under a 7 s video card
- **THEN** ffprobe's frame count of the movie equals the unsplit render's, the presentation times are those of a
  constant frame rate, and the counter reads consecutively through the join

#### Scenario: Audio is continuous at the join
- **WHEN** a 20 s clip whose audio is a continuous 440 Hz tone is rendered under a 7 s video card
- **THEN** the movie's audio is within 1024 samples of the unsplit render's length and has no sample step at the
  join larger than twice the tone's own largest step

#### Scenario: A short remainder is not split
- **WHEN** a 7.5 s segment carries a 7 s timed overlay
- **THEN** it is not split and is normalized whole with the bridge over its 7.5 s, as before

#### Scenario: A window longer than the segment is not split
- **WHEN** a 7 s card is attached to a 3 s segment
- **THEN** the segment stays whole, the overlay window is clamped to 3 s, and the render result carries the same
  warning as before

#### Scenario: Segment without a timed overlay is unchanged
- **WHEN** a segment has no overlay, or only an untimed overlay
- **THEN** the segment list is the plan's, unchanged

#### Scenario: Dry run lists the head, the tail and the join
- **WHEN** an event with a video card on a long first clip is planned without running
- **THEN** the planned commands include one command for the head with the card input, one for the tail without,
  and the join that writes the segment's intermediate

#### Scenario: Chapter times are unchanged
- **WHEN** an event with a video card is rendered split and (with the split disabled in a test) unsplit
- **THEN** the chapters' start and end times agree within one frame

#### Scenario: Progress covers the pieces
- **WHEN** a split segment is encoded
- **THEN** the head reports its share of the segment's progress weight and the tail the rest, so progress still
  reaches the segment's full weight and never goes backward
