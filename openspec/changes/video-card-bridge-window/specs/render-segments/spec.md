## ADDED Requirements

### Requirement: A timed-overlay segment is split at its window

Before normalizing, the engine SHALL split every source segment that carries a timed overlay into a **head** and a
**tail** over the same clip, so the CPU overlay bridge covers only the overlay's window. The overlay's window
SHALL be the producer-materialized duration clamped to the segment's length. The head SHALL carry the overlay and
cover the segment from its start for `N / fps` seconds, where `fps` is the target frame rate and `N` is the
window's length in target frames, rounded up to a whole number of frames. The tail SHALL carry no overlay and
cover the rest of the segment, starting exactly where the head ends. A whole clip SHALL be split by its probed
duration. Both pieces SHALL be trimmed segments (never stream-copied) with the segment's chapter, identity,
`rotate` and source path; the tail SHALL NOT carry the overlay or its card input.

The segment SHALL NOT be split when the tail would be shorter than 1 s, nor when the window covers the whole
segment; it is then normalized whole, as before. A segment without a timed overlay SHALL be unchanged. The same
expanded segment list SHALL be used to plan (dry-run), to run, to weigh progress, and to aggregate chapter times,
so a dry run lists the commands a run executes.

The joined result SHALL be frame-exact: the head and tail together SHALL have the video frames the unsplit segment
had, none dropped or duplicated, with each frame at the same presentation time; the movie's duration and its
chapter start and end times SHALL equal the unsplit render's within one frame. The audio SHALL be continuous across
the join: the head's audio SHALL be exactly `round(H * sample_rate)` samples, and the movie's audio length SHALL
be within one AAC frame (1024 samples) of the unsplit render's, with no dropout or click at the join. A clip
without an audio track SHALL keep synthesized silence on both pieces.

#### Scenario: A 180 s first clip under a 7 s card is split in two
- **WHEN** a segment of a 180 s clip carries a 7 s timed overlay and the target is 30 fps
- **THEN** the plan has a head of 0 s to 7 s carrying the overlay and a tail of 7 s to 180 s with no overlay, and
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

#### Scenario: Dry run lists the head and the tail
- **WHEN** an event with a video card on a long first clip is planned without running
- **THEN** the planned commands include one command for the head with the card input and one for the tail without

#### Scenario: Chapter times are unchanged
- **WHEN** an event with a video card is rendered split and (with the split disabled in a test) unsplit
- **THEN** the chapters' start and end times agree within one frame
