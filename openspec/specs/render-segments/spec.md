# render-segments Specification

## Purpose

Turn a fully-explicit `RenderPlan` into the ordered list of **segments** the renderer actually concatenates,
derive the **target spec** (the common canvas every segment must conform to), and expose a pluggable
**decorator** seam so "look" features (title cards now; intros, outros, transitions, watermarks later) can add
synthetic segments or attach overlays without modifying the pipeline core.

## Requirements

### Requirement: Segment list from the render plan

The engine SHALL flatten a `RenderPlan` into a deterministic, fully-ordered list of segments. Each included
`ResolvedClip` SHALL produce one segment when it has no trims, and one segment per **kept span** when it has
`cut_spans` (the footage between/around the removed spans), in source-time order. Cut spans that overlap or
touch SHALL be joined as one removal before the kept spans are taken, whatever order they are listed in, so the
kept spans are disjoint and no footage appears in two segments. The flattening SHALL follow the plan's
chapter and clip order exactly and SHALL NOT consult folder structure. Each segment SHALL record which chapter
it belongs to so chapter boundaries are recoverable after flattening.

#### Scenario: Untrimmed clip yields one segment
- **WHEN** a resolved clip has no cut spans
- **THEN** the segment list contains exactly one segment referencing that clip's full duration

#### Scenario: Trimmed clip yields one segment per kept span
- **WHEN** a resolved clip has a single cut span in the middle of the clip
- **THEN** the segment list contains two segments — the footage before the cut and the footage after it — in source-time order

#### Scenario: Overlapping cut spans are one removal
- **WHEN** a 10 s clip has cut spans 1 s to 3 s and 2 s to 5 s
- **THEN** the segment list contains two segments for it, 0 s to 1 s and 5 s to 10 s, and no footage between 1 s
  and 5 s appears in any segment

#### Scenario: Touching cut spans are one removal
- **WHEN** a 10 s clip has cut spans 1 s to 3 s and 3 s to 5 s
- **THEN** the segment list contains two segments for it, 0 s to 1 s and 5 s to 10 s, and no zero-length segment

#### Scenario: A cut span inside another adds nothing
- **WHEN** a 10 s clip has cut spans 1 s to 9 s and 2 s to 3 s
- **THEN** the segment list contains two segments for it, 0 s to 1 s and 9 s to 10 s

#### Scenario: The order cut spans are listed in does not matter
- **WHEN** a 10 s clip has cut spans 5 s to 8 s, 1 s to 3 s and 2 s to 6 s, in that order
- **THEN** the segment list contains the same two segments as for the sorted list, 0 s to 1 s and 8 s to 10 s

#### Scenario: Chapter membership is preserved
- **WHEN** a plan with two chapters is flattened
- **THEN** every segment records its source chapter, and the original chapter order and per-chapter clip order are preserved in the segment list

### Requirement: Source vs synthetic segments

A segment SHALL be either a **source** segment (a span of a real clip, carrying its identity, kept-span
in/out, and resolved `rotate`) or a **synthetic** segment (produced by a decorator, e.g. a title card),
identified by a producer reference rather than a source path. Both kinds SHALL be peers in the list and SHALL
be required to conform to the same target spec before concatenation.

#### Scenario: Source segment carries clip identity and span
- **WHEN** a source segment is created for a kept span of `Reception/00400.mp4`
- **THEN** the segment carries that identity, the span's in/out times, and the clip's resolved rotation

#### Scenario: Synthetic segment carries a producer, not a source path
- **WHEN** a decorator inserts a title segment
- **THEN** the segment is marked synthetic with a producer reference and has no source clip identity

### Requirement: Overlays are a first-class segment field

A segment SHALL carry an ordered list of `OverlaySpec` entries (possibly empty). An `OverlaySpec` SHALL
describe an image/source to composite, its position, and its active time range. Overlays SHALL be applied
during that segment's normalize pass. A segment with one or more overlays SHALL NOT be eligible for the
stream-copy fast path.

#### Scenario: Segment with no overlays
- **WHEN** a source segment is created and no decorator attaches an overlay
- **THEN** the segment's overlay list is empty

#### Scenario: Attached overlay is carried on the segment
- **WHEN** a decorator attaches an overlay to a segment
- **THEN** the segment's overlay list contains that `OverlaySpec` and the segment is marked ineligible for stream copy

### Requirement: Pluggable segment decorators

The engine SHALL apply an ordered sequence of **decorators** to the segment list, each a pure transform
`(plan, target, segments) -> segments`. A decorator SHALL act in one of two shapes: an **inserter** that adds
one or more synthetic segments at a defined position, or an **attacher** that adds an `OverlaySpec` to one or
more existing segments. Decorators SHALL be selected by name (resolved from the `look`/config layering, D-2)
and SHALL be registered in a registry so new decorators can be added without changing the pipeline core. The
engine SHALL ship a `none` decorator that returns the segment list unchanged.

#### Scenario: Inserter adds a synthetic segment
- **WHEN** an inserter decorator runs against a segment list
- **THEN** the returned list contains the original segments plus the inserted synthetic segment(s) at the decorator's chosen position, in deterministic order

#### Scenario: Attacher adds an overlay
- **WHEN** an attacher decorator runs against a segment list
- **THEN** the returned list has the same segments with the new `OverlaySpec` attached to the targeted segment(s)

#### Scenario: Default decorator is a no-op
- **WHEN** the `none` decorator is applied
- **THEN** the segment list is returned unchanged

#### Scenario: Unknown decorator name fails loud
- **WHEN** the resolved configuration names a decorator that is not registered
- **THEN** the engine raises a typed error naming the unknown decorator rather than silently skipping it

### Requirement: Target spec derivation

The engine SHALL derive a **target spec**, the common canvas every segment conforms to, from:

- the resolved `look`
- the probe facts of **all** clips in the render plan
- the selected acceleration profile's usable encoders

The target spec SHALL include:

- **video resolution:** from `look.target_resolution`, a `[width, height]` pair, defaulting to 1920×1080
- **frame rate:** from `look.fps`, a positive number, defaulting to the highest probed fps among the plan's
  clips
- the chosen video codec and pixel format
- sample aspect ratio (1:1)
- common audio parameters (sample rate, channel count, codec)

No property of the canvas SHALL be taken from a clip because of its position in the plan. A clip whose
dimensions or orientation differ from the canvas SHALL be fitted into it (aspect preserved, padded), never
used to choose it.

A `look.target_resolution` that is not a pair of positive integers, or a `look.fps` that is not a positive
number, SHALL fail loud, naming the key and the offending value. When the look requests a codec the
selected profile cannot encode and CPU fallback is also unavailable, the engine SHALL fail loud rather than
substitute a different codec.

#### Scenario: Resolution and fps come from look and first clip
- **WHEN** the look sets `target_resolution: [1920, 1080]` and `fps: 30`, and the first clip is probed at
  25 fps
- **THEN** the target spec is 1920×1080 at 30 fps: the look decides, not the first clip

#### Scenario: A portrait first clip does not make a portrait movie
- **WHEN** the look sets no resolution, and the plan's first clip is a 720×1280 phone clip followed by
  1920×1080 camera clips
- **THEN** the target spec is 1920×1080, and the phone clip is pillarboxed into it

#### Scenario: A 4K clip does not make a 4K movie by default
- **WHEN** the look sets no resolution and the plan mixes 3840×2160 and 1920×1080 clips
- **THEN** the target spec is 1920×1080, and the 4K clips are downscaled

#### Scenario: The highest frame rate wins by default
- **WHEN** the look sets no fps and the plan's clips are probed at 25, 50 and 30 fps, with the 25 fps clip
  first
- **THEN** the target spec's frame rate is 50

#### Scenario: A uniform event keeps the stream-copy path
- **WHEN** the look sets neither key, and every clip is a 1920×1080 H.264 clip at 50 fps whose other stream
  parameters already match the target
- **THEN** the target spec is 1920×1080 at 50 fps, and the clips are copy-eligible exactly as before

#### Scenario: An event-level override wins over the library default
- **WHEN** `config.yaml` sets `target_resolution: [1920, 1080]` and one event's `reel.yaml` sets
  `target_resolution: [3840, 2160]`
- **THEN** that event's target spec is 3840×2160, and the others' are 1920×1080

#### Scenario: A malformed fps fails loud
- **WHEN** the look sets `fps: "fifty"` or `fps: 0`
- **THEN** the engine raises a typed error naming `look.fps` and the value, and no segment is rendered

#### Scenario: AV1 target honored when profile supports it
- **WHEN** the look requests AV1 and the selected profile reports a usable AV1 encoder
- **THEN** the target spec's codec is AV1 using that encoder (D-5)

#### Scenario: Unencodable codec fails loud
- **WHEN** the look requests a codec for which neither the selected profile nor the CPU fallback has a usable encoder
- **THEN** the engine raises a typed error rather than picking a different codec

### Requirement: Deterministic segment construction

Segment-list construction and decorator application SHALL be deterministic: the same plan, clip facts, target
spec, and decorator configuration SHALL always yield the same ordered segment list, with all ordering total
and independent of map/dict iteration order.

#### Scenario: Repeated construction is identical
- **WHEN** the same plan and configuration are flattened and decorated twice
- **THEN** the two segment lists are identical in order and content

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

#### Scenario: A source slower than the target keeps the unsplit picture at the seam
- **WHEN** a 25 fps first clip with a 7.5 s card is rendered into a 30 fps movie, split and unsplit
- **THEN** every frame, including the first frame of the tail, shows the same source frame as the unsplit render
