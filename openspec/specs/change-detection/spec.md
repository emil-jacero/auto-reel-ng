# change-detection Specification

## Purpose

Detect whether an event's rendered output is still current with its inputs — without probing media or
depending on the host or acceleration device — so the CLI, scheduler, and API can skip redundant renders,
gate enqueue/claim decisions, and let operators explicitly adopt an already-rendered archive.

## Requirements

### Requirement: Probe-free, host-independent render fingerprint
The system SHALL compute an event's render fingerprint as a hash over exactly four components, each with
its own sub-hash: **editorial** (the event's `reel.yaml` in canonical form, or the folder-seed equivalent
when absent), **defaults** (the resolved D-2 project look defaults), **clip_set** (the sorted on-disk clip
identities, each with its content signal — size + mtime_ns by default, sha256 under the existing hash
opt-in), and **engine** (the `RENDER_GRAPH_VERSION` constant + the ffmpeg version string). Computing the
fingerprint MUST NOT invoke ffprobe or read media content (beyond the opt-in hash), and the value MUST be
independent of the acceleration profile, device, or host — the same event state yields the same
fingerprint wherever it is computed.

#### Scenario: Unchanged event is fingerprint-stable
- **WHEN** the fingerprint is computed twice (including from different processes) with no disk change
  between
- **THEN** both values are byte-identical

#### Scenario: Each component moves the fingerprint
- **WHEN** exactly one of: a clip's content signal changes, `reel.yaml` is edited semantically, a project
  look default changes, or `RENDER_GRAPH_VERSION` is bumped
- **THEN** the fingerprint changes and only that component's sub-hash differs

#### Scenario: Device selection does not move the fingerprint
- **WHEN** the same event is evaluated under a CPU profile and a GPU profile
- **THEN** the fingerprints are identical

#### Scenario: No probing
- **WHEN** a fingerprint is computed
- **THEN** no ffprobe invocation occurs

### Requirement: Render manifest sidecar
The last successful render of an event SHALL be recorded in `render-manifest.json` under the event's
`.auto-reel/cache/` directory, containing: a manifest schema version, the fingerprint, the four component
sub-hashes, the output filename, the engine identity in readable form, and a written-at timestamp. The
sidecar SHALL be the sole persistent record of last-render state — no database copy. An unreadable or
schema-incompatible manifest SHALL be treated as absent (fail open to stale, never fail closed to skip).

#### Scenario: Manifest lives beside the analysis cache
- **WHEN** an event is successfully rendered with a fingerprint supplied
- **THEN** `<event>/.auto-reel/cache/render-manifest.json` exists with the fingerprint, sub-hashes, output
  name, engine identity, and timestamp

#### Scenario: Corrupt manifest fails open
- **WHEN** the manifest file contains invalid JSON
- **THEN** the event is evaluated as stale (as if no manifest existed) and no error aborts the caller

### Requirement: Staleness gate
The system SHALL provide a single gate that evaluates an event as **stale** if and only if: no manifest
exists, or the current fingerprint differs from the manifest's, or the recorded output file is missing
from the output directory. The verdict SHALL carry the changed components (by comparing sub-hashes) as
human-readable reasons. A force request SHALL bypass the gate entirely. All staleness decisions in the
system MUST go through this gate.

#### Scenario: Fresh event
- **WHEN** the manifest matches the current fingerprint and the output file exists
- **THEN** the verdict is fresh with no reasons

#### Scenario: Missing output is always stale
- **WHEN** the manifest matches the current fingerprint but the output file is absent
- **THEN** the verdict is stale citing the missing output

#### Scenario: Reasons name the changed components
- **WHEN** a clip was replaced and `reel.yaml` was edited since the last render
- **THEN** the stale verdict's reasons include the clip-set and editorial components (and not defaults or
  engine)

#### Scenario: Missing referenced clip makes the event stale, not blocked
- **WHEN** a clip referenced by `reel.yaml` is absent from disk
- **THEN** the clip-set component differs, the event is stale, and downstream rendering proceeds with the
  MISSING clip reported loud (per the existing adoption policy) — the gate never suppresses the render

### Requirement: Manifest adoption
The system SHALL support explicit adoption: for an event whose output file exists, writing a manifest at
the current fingerprint as the operator's assertion that the existing output reflects the current inputs.
Adoption MUST be explicit (operator-invoked), MUST skip events with no output file, and MUST NOT render
anything.

#### Scenario: Existing output is adopted
- **WHEN** adoption runs over an event with an output file and no manifest
- **THEN** a manifest at the current fingerprint is written and the event subsequently evaluates fresh

#### Scenario: Unrendered event is not adopted
- **WHEN** adoption runs over an event with no output file
- **THEN** no manifest is written and the event remains stale
</content>
