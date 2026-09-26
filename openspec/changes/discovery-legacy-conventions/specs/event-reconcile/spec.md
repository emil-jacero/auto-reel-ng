## ADDED Requirements

### Requirement: Legacy folder conventions exclude clips from discovery

Discovery SHALL apply the folder conventions of the auto-reel archive when it lists an event's clips on disk:

- **`original/`:** an immediate subdirectory named `original`, compared case-insensitively, SHALL
  contribute no clips. It holds a camera's pre-conversion originals, whose converted copies are the
  event's clips.
- **`.reelignore` in a subdirectory:** an immediate subdirectory containing a file named `.reelignore`
  SHALL contribute no clips. The marker's contents are not read.
- **Depth:** clips SHALL be discovered only at the event root, which forms the default chapter, and in
  its immediate subdirectories, which form named chapters. A video file deeper than that, such as a
  chapter's own `original/`, SHALL NOT be discovered.

These rules SHALL define the disk listing that every consumer of an event's clips uses: seeding, reconcile,
the staleness fingerprint's clip-set component, the analysis cache, and the service's events reads. Files
they exclude SHALL NOT be moved, renamed, deleted or otherwise touched. A document that already references an
excluded clip SHALL have that clip reported as MISSING by reconcile, like any other referenced clip that is
not on the disk listing. It is not silently dropped from the document.

#### Scenario: Converted originals are not a chapter
- **WHEN** an event holds converted clips `00400.mp4` and `00401.mp4` at its root, and their camera
  originals `00400.MTS` and `00401.MTS` in `original/`
- **THEN** seeding produces one default chapter with the two `.mp4` clips and no `original` chapter, and
  the `.MTS` files are not NEW

#### Scenario: The originals folder is matched regardless of case
- **WHEN** an event's originals live in `Original/` rather than `original/`
- **THEN** they are excluded exactly as in `original/`

#### Scenario: An ignored chapter is skipped
- **WHEN** an event has chapters `2017-07-06/` and `dålig-kvalitet/`, and `dålig-kvalitet/` contains a
  `.reelignore`
- **THEN** discovery lists the clips of `2017-07-06/` as a chapter and none from `dålig-kvalitet/`

#### Scenario: Originals nested in a chapter stay undiscovered
- **WHEN** a per-day chapter `2017-07-10/` holds converted clips, plus their originals in
  `2017-07-10/original/`
- **THEN** only the converted clips are discovered for that chapter

#### Scenario: Changes to excluded files do not make an event stale
- **WHEN** a rendered event's `original/` folder gains or loses a file, and nothing else changes
- **THEN** the event's staleness verdict stays fresh

#### Scenario: A document already listing an excluded clip reports it missing
- **WHEN** an event's existing `reel.yaml` references `original/00400.MTS`
- **THEN** reconcile classifies that clip as MISSING, the document is not rewritten, and the file on disk
  is untouched
