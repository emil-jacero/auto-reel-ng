# render-segments Specification

## Purpose

Turn a fully-explicit `RenderPlan` into the ordered list of **segments** the renderer actually concatenates,
derive the **target spec** (the common canvas every segment must conform to), and expose a pluggable
**decorator** seam so "look" features (title cards now; intros, outros, transitions, watermarks later) can add
synthetic segments or attach overlays without modifying the pipeline core.

## ADDED Requirements

### Requirement: Segment list from the render plan

The engine SHALL flatten a `RenderPlan` into a deterministic, fully-ordered list of segments. Each included
`ResolvedClip` SHALL produce one segment when it has no trims, and one segment per **kept span** when it has
`cut_spans` (the footage between/around the removed spans), in source-time order. The flattening SHALL follow
the plan's chapter and clip order exactly and SHALL NOT consult folder structure. Each segment SHALL record
which chapter it belongs to so chapter boundaries are recoverable after flattening.

#### Scenario: Untrimmed clip yields one segment
- **WHEN** a resolved clip has no cut spans
- **THEN** the segment list contains exactly one segment referencing that clip's full duration

#### Scenario: Trimmed clip yields one segment per kept span
- **WHEN** a resolved clip has a single cut span in the middle of the clip
- **THEN** the segment list contains two segments — the footage before the cut and the footage after it — in source-time order

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

The engine SHALL derive a **target spec** — the common canvas every segment conforms to — from the resolved
`look`, the first clip's probe facts, and the selected acceleration profile's usable encoders. The target spec
SHALL include: video resolution (from `look.target_resolution`), frame rate (from the first clip's probed
fps), the chosen video codec and pixel format, sample aspect ratio (1:1), and common audio parameters (sample
rate, channel count, codec). When the look requests a codec the selected profile cannot encode and CPU
fallback is also unavailable, the engine SHALL fail loud rather than substitute a different codec.

#### Scenario: Resolution and fps come from look and first clip
- **WHEN** the look sets `target_resolution: [1920, 1080]` and the first clip is probed at 30 fps
- **THEN** the target spec is 1920×1080 at 30 fps

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
