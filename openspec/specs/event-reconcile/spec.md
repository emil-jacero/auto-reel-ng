# event-reconcile Specification

## Purpose

Seed a complete v0 document on first discovery using folder structure only as a hint (subdirectories become chapters, root clips the default chapter, folder name seeds metadata), then provide a pure reconcile function that classifies every clip on disk against the document as NEW, MISSING, ACTIVE, or IGNORED without mutating disk or document. Seeding is reconcile against an empty document, and apply-operations ("add to chapter", "ignore") mutate only the document — never the filesystem — so dismissals live in `reel.yaml` and survive a rebuild of any derived index.

## Requirements

### Requirement: Discovery seeds a complete document from folder structure

On first discovery of an event directory, the engine SHALL seed a complete v0 document using folder structure
only as a hint: subdirectories become chapters, root-level clips become the default chapter, and folder-name
metadata (`YYYY-MM-DD - Title [- Location]`) seeds `metadata`. After seeding, structure SHALL live in the
document and folder layout SHALL NOT be consulted again to determine structure.

#### Scenario: Subdirectories seed chapters
- **WHEN** an event directory with a `Reception/` subdir and root-level clips is first discovered
- **THEN** the seeded document has a default chapter for the root clips and a `Reception` chapter for the subdir clips

#### Scenario: Folder name seeds metadata
- **WHEN** an event directory named `2024-06-21 - Midsummer - Dalarna` is seeded
- **THEN** the document's metadata has title `Midsummer`, date `2024-06-21`, and location `Dalarna`

### Requirement: Reconcile classifies disk against the document

The engine SHALL provide a pure reconcile function over a disk clip listing and a document that classifies
every clip as exactly one of: NEW (present on disk, not referenced in the document, not in `ignore`), MISSING
(referenced in the document, absent from disk), ACTIVE (referenced and present), or IGNORED (present on disk
and listed in `ignore`). Reconcile SHALL NOT mutate the document or the filesystem.

#### Scenario: New disk file is classified NEW
- **WHEN** a clip exists on disk, is not referenced in the document, and is not ignored
- **THEN** reconcile classifies it as NEW

#### Scenario: Missing referenced clip is reported, never dropped
- **WHEN** the document references a clip whose file is absent from disk
- **THEN** reconcile classifies it as MISSING and reports it rather than removing it from the document

#### Scenario: Ignored disk file is classified IGNORED
- **WHEN** a disk file's identity appears in the document's `ignore` list
- **THEN** reconcile classifies it as IGNORED and does not classify it as NEW

### Requirement: Seeding is reconcile against an empty document

The engine SHALL treat first-discovery seeding as reconcile against an absent or empty document, so the same
mechanism handles initial seeding and later drift. Against an empty document, every disk clip SHALL be NEW
and become part of the seeded structure.

#### Scenario: Empty document yields all-NEW
- **WHEN** reconcile runs against an absent/empty document for an event directory
- **THEN** every clip on disk is classified NEW and seeding produces a document referencing them

### Requirement: Apply operations mutate the document, not the filesystem

Reconcile SHALL offer apply-operations that return a mutated document: "add" places a NEW clip into a named
chapter, and "ignore" records a clip's identity in the document's `ignore` list. Both SHALL operate only on
the document; source files SHALL NOT be moved, renamed, or deleted. Dismissals SHALL be stored in `reel.yaml`
(not a derived store) so they survive a rebuild of any derived index.

#### Scenario: Add places a NEW clip into a chapter
- **WHEN** the operator applies "add" for a NEW clip targeting chapter `Reception`
- **THEN** the returned document references that clip in `Reception` and the source file is unchanged on disk

#### Scenario: Ignore is recorded in the document
- **WHEN** the operator applies "ignore" for a NEW clip
- **THEN** the returned document lists that clip's identity in `ignore`, and a subsequent reconcile classifies it as IGNORED rather than NEW

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
