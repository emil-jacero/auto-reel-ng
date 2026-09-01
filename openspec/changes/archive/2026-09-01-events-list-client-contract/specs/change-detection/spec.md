## MODIFIED Requirements

### Requirement: Staleness gate
The system SHALL provide a single gate that evaluates an event as **stale** if and only if: no manifest
exists, or the current fingerprint differs from the manifest's, or the recorded output file is missing
from the output directory. The verdict SHALL carry the changed components (by comparing sub-hashes) as
human-readable reasons. A force request SHALL bypass the gate entirely. All staleness decisions in the
system MUST go through this gate.

The reasons a verdict may cite SHALL come from a **closed, named vocabulary** owned by the gate: the
no-manifest and missing-output reasons, plus one reason per fingerprint component. The gate MUST NOT emit
a reason outside that vocabulary, and any consumer that publishes reasons — the CLI's output, the API's
responses — SHALL take the set from the gate rather than restating it, so the vocabulary has exactly one
source of truth. Adding, removing or renaming a reason is a change to this vocabulary and MUST be made
here.

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

#### Scenario: The vocabulary is closed
- **WHEN** any consumer enumerates the reasons a verdict can cite
- **THEN** it obtains exactly the no-manifest reason, the missing-output reason and one reason per
  fingerprint component, and no other value can appear in a verdict
