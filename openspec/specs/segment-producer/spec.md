# segment-producer Specification

## Purpose

Provide a generic, name-keyed registry that materializes a synthetic segment's content by its `producer`
reference — returning the rendered image/inputs, duration, and fade timing the normalize step needs — so
synthetic segments can be encoded to the target spec without the pipeline core knowing about titles. The title
card registers the first producer; future look features (intro/outro/transition bumpers) reuse the same seam.

## Requirements

### Requirement: Name-keyed producer registry

The engine SHALL maintain a registry of synthetic-segment **producers** keyed by name, parallel to the
decorator registry. A synthetic `Segment` SHALL identify its producer by a registry key (`Segment.producer`).
New producers SHALL be registrable by name without changing the pipeline core, so future synthetic look
features (intro, outro, transition bumpers) reuse the same seam. The title card SHALL register the first
producer.

#### Scenario: Producer resolved by name
- **WHEN** a synthetic segment carries a producer key that is registered
- **THEN** the engine resolves the matching producer for that segment

#### Scenario: New producer registered without core changes
- **WHEN** a producer is registered under a new name
- **THEN** synthetic segments referencing that name resolve to it without modifying the segment/normalize core

### Requirement: Unknown producer fails loud

When a synthetic segment references a producer name that is not registered, the engine SHALL raise a typed
error naming the unknown producer and the registered names. It SHALL NOT silently skip the segment or drop it
from the render, because dropping a synthetic segment changes the edit.

#### Scenario: Unregistered producer name fails loud
- **WHEN** a synthetic segment's producer key is not present in the registry
- **THEN** the engine raises a typed error naming the unknown producer rather than skipping the segment

### Requirement: A producer materializes a synthetic segment's content

A producer SHALL materialize a synthetic segment into the inputs the normalize step needs: a rendered image
(or source) path, the segment's duration, and the fade-in/fade-out timing for the segment. The materialized
result SHALL carry everything required to encode the segment to the target spec, and SHALL NOT itself invoke
encoding (that is the normalize step's job), keeping production pure and side-effect-scoped to producing its
asset.

#### Scenario: Title producer yields image, duration, and fades
- **WHEN** the title producer materializes a title segment
- **THEN** it returns the rendered card image path, the card duration, and the configured fade-in/out timings

#### Scenario: Materialized result targets the spec
- **WHEN** a synthetic segment is materialized for a 1920×1080 target
- **THEN** the materialized asset and metadata are sufficient for the normalize step to encode a 1920×1080 segment conforming to the target spec
