## ADDED Requirements

### Requirement: Claim-time staleness recheck
After claiming a job and rebuilding its plan, the worker SHALL re-evaluate the staleness gate against
current disk state — unless the job's `force` flag is set. A job whose event evaluates fresh SHALL be
completed as `done` without rendering (its progress set to 1.0); a stale (or forced) job SHALL render
with output replacement (the gate verdict, not bare file existence, decides). This catches both disk
changes made while the job was queued and reverts to the last-rendered state, and it absorbs requeued
already-finished orphans by manifest verification rather than file existence.

#### Scenario: Reverted event skips at claim time
- **WHEN** an event is enqueued stale, then restored on disk to exactly its last-rendered state before a
  worker claims the job
- **THEN** the claim-time recheck evaluates fresh and the job completes `done` without any ffmpeg process

#### Scenario: Forced job never rechecks
- **WHEN** a job with `force = true` is claimed for a fresh event
- **THEN** the worker renders it, replacing the existing output

#### Scenario: Requeued finished orphan absorbed by manifest
- **WHEN** a job that finished its render (manifest written) is orphaned before its status transition and
  requeued by reconciliation
- **THEN** the re-claiming worker evaluates it fresh and completes it `done` without re-rendering

#### Scenario: Stale job replaces outdated output
- **WHEN** a claimed job's event has an existing output but a differing fingerprint
- **THEN** the worker renders and the output is replaced (no skip on bare existence)
