## ADDED Requirements

### Requirement: Manifest written on actual render success
When a render fingerprint is supplied with the job, the engine SHALL write the event's render manifest
immediately after output finalization (verification and atomic rename) succeeds. The manifest MUST NOT be
written on a skipped render, a dry run, or any failure; when no fingerprint is supplied (direct library
use), no manifest is written.

#### Scenario: Success writes the manifest after finalization
- **WHEN** a render with a supplied fingerprint completes and the output is renamed into place
- **THEN** the render manifest is written recording that fingerprint

#### Scenario: Skip does not touch the manifest
- **WHEN** the engine skips because the output exists and overwrite was not requested
- **THEN** the existing manifest (or its absence) is unchanged

#### Scenario: Failure leaves no new manifest
- **WHEN** a render fails at any stage after starting
- **THEN** no manifest is written and any pre-existing manifest is unchanged

#### Scenario: No fingerprint, no manifest
- **WHEN** a render runs without a supplied fingerprint
- **THEN** the render completes normally and writes no manifest
