## ADDED Requirements

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
