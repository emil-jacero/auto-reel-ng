## MODIFIED Requirements

### Requirement: Batch commands refuse colliding output paths

Before acting, `render`, `enqueue` and `adopt-renders` SHALL check the events they selected: every event,
fresh or stale, forced or not, whether or not it is a dry run. Any two or more events that resolve to the
same output path SHALL be treated as a **collision**. Paths SHALL be compared case-insensitively, so a
collision that a case-insensitive archive filesystem would create is caught even on a case-sensitive host.
Because a dated event's file name begins with its date, a collision needs two events with the same date,
title and location, or two undated events with the same title and location.

Every event in a collision SHALL be reported as an error. The report SHALL name the shared output path and
the other events that claim it. For these events the command MUST NOT render, enqueue, adopt, or overwrite
anything; an output file that already exists at the shared path SHALL be left untouched. Events outside
any collision SHALL proceed normally (per-event isolation). A command that reported at least one
collision SHALL exit non-zero. A collision SHALL NOT be resolved automatically by renaming, suffixing or
skipping one side. The operator resolves it by changing an event's `title` or `location` in `reel.yaml`.

The check covers only the events the command selected (for example, only the years named by `--years`).
Events outside the selection are not examined.

#### Scenario: Two same-titled events in one year collide
- **WHEN** `render` runs over events `2024/2024-06-21 - Midsommar` and `2024/2024-06-21 - midsommar`, both
  dated `2024-06-21` with title `Midsommar` and no location, plus a third, uniquely named 2024 event
- **THEN** both Midsommar events are reported as errors naming `2024/2024-06-21 - Midsommar.mp4` and each
  other, neither is rendered, the third event renders normally, and the command exits non-zero

#### Scenario: A fresh event's output is protected from a new same-named event
- **WHEN** a fresh event already owns `<output>/2024/2024-06-21 - Midsommar.mp4`, and a newly added event
  also resolves to date `2024-06-21` and title `Midsommar`
- **THEN** `render` reports both as colliding, the existing movie is byte-for-byte unchanged, and no
  manifest is written for either event

#### Scenario: Collision differing only in letter case
- **WHEN** two events resolve to `2024/2024-06-21 - Midsommar.mp4` and `2024/2024-06-21 - midsommar.mp4`
- **THEN** they are reported as a collision

#### Scenario: Same title in different years is not a collision
- **WHEN** events dated 2023 and 2024 both have title `Midsommar`
- **THEN** no collision is reported and both render to their own year folder

#### Scenario: Same title on different dates is not a collision
- **WHEN** events dated `2024-06-21` and `2024-06-22` both have title `Midsommar` and no location
- **THEN** no collision is reported and both render, each under its own date-prefixed name

#### Scenario: Two undated events with the same title collide
- **WHEN** two undated events both have title `Blandat` and no location
- **THEN** both are reported as colliding on `Blandat.mp4` at the output root

#### Scenario: Force does not override a collision
- **WHEN** `render --force` runs over two colliding events
- **THEN** both are reported as colliding and neither is rendered

#### Scenario: Dry run reports the collision
- **WHEN** `render --dry-run` runs over two colliding events
- **THEN** both are reported as colliding, no commands are printed for them, and the command exits
  non-zero

#### Scenario: Enqueue refuses colliding events
- **WHEN** `enqueue` runs over two colliding stale events
- **THEN** both are reported as colliding, no job row is inserted for either, other events are enqueued,
  and the command exits non-zero

#### Scenario: Adoption refuses a shared output
- **WHEN** `adopt-renders` runs over two colliding events and the shared output file exists
- **THEN** no manifest is written for either event (one file cannot be adopted as both movies), both are
  reported as colliding, and the command exits non-zero

## ADDED Requirements

### Requirement: adopt-renders previews without writing

`auto-reel adopt-renders` SHALL accept `--dry-run`. In dry-run mode it SHALL evaluate every selected event
exactly as a real run does, including the collision check and the staleness verdict, and report the
same outcome for each event: that it would be adopted, is already fresh, is unrendered (no output at its
derived path) or collides. It SHALL print the same totals and exit with the same code a real run would.
It MUST NOT write a manifest, create a directory, or change any file. Its output SHALL mark the run as a
dry run, so a preview is never mistaken for a completed adoption.

#### Scenario: Previewing adoption of a legacy archive
- **WHEN** `adopt-renders --dry-run` runs over an archive where three events have outputs at their derived
  paths and one does not
- **THEN** it reports three events it would adopt and one unrendered event, writes no manifest, and a
  following real `adopt-renders` adopts exactly those three

#### Scenario: A dry run leaves the archive untouched
- **WHEN** `adopt-renders --dry-run` runs over a read-only mounted archive
- **THEN** it completes without any write error, because it attempts no write

#### Scenario: A dry run still reports collisions
- **WHEN** `adopt-renders --dry-run` runs over two colliding events
- **THEN** both are reported as colliding, and the command exits non-zero as a real run would
