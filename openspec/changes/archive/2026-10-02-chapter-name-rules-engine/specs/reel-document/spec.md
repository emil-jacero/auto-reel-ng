## ADDED Requirements

### Requirement: Chapter names are unpadded, non-blank and unique ignoring case

A chapter's `name` SHALL be a string. The empty string is the name of the default chapter and is always
valid. Any other name SHALL be non-blank (not empty after `str.strip()`) and SHALL equal its own
`str.strip()`, so it has no leading or trailing whitespace. Two chapters SHALL NOT have names that are equal
under `str.casefold()`; the document is judged by that comparison alone, with no Unicode normalization, so
a name differing only in case from another is a duplicate and a name differing in any other character is
not. Loading a document that breaks any of these SHALL fail with the single parse error of "Fail-loud parse
and validation", naming the offending `chapters[i]` and, for a duplicate, both chapters and both names as
written. A name SHALL NOT be trimmed, case-folded or otherwise rewritten to make a document load.

A document that a writer is asked to write SHALL be checked by the same rules before anything is written,
so no write produces a `reel.yaml` that this requirement would refuse to load. A refused write leaves the
previous `reel.yaml`, if any, as it was.

#### Scenario: A whitespace-only chapter name is refused

- **WHEN** a `reel.yaml` lists chapters named `""` and `"  "`
- **THEN** loading fails with the parse error naming `chapters[1]`, saying the name is blank

#### Scenario: A padded chapter name is refused

- **WHEN** a `reel.yaml` lists a chapter named `" Party"` or `"Party "`
- **THEN** loading fails with the parse error naming that chapter and the name as written, and the
  document is not trimmed to load

#### Scenario: Names equal ignoring case are duplicates

- **WHEN** a `reel.yaml` lists chapters `Party` and `party`
- **THEN** loading fails with the parse error naming `chapters[1]` and `chapters[0]` and both names, saying
  they are the same ignoring case

#### Scenario: Case folding follows str.casefold

- **WHEN** a `reel.yaml` lists chapters `Straße` and `STRASSE`
- **THEN** loading fails with a duplicate chapter name error, because `str.casefold()` folds the sharp s

#### Scenario: Exact duplicates are still refused

- **WHEN** a `reel.yaml` lists two chapters both named `Reception`
- **THEN** loading fails with a duplicate chapter name error naming both

#### Scenario: The default chapter and ordinary names load

- **WHEN** a `reel.yaml` lists chapters `""`, `Reception` and `Dag 2`
- **THEN** it loads, and `""` is the default chapter

#### Scenario: Seeding folders that differ only by case writes nothing

- **WHEN** an event holds subfolders `Party/` and `party/`, each with a clip, and no `reel.yaml`, and the
  seeded document is written
- **THEN** the write fails with the duplicate chapter name error and no `reel.yaml` exists afterwards

#### Scenario: A writer refuses a padded name and keeps the old file

- **WHEN** an existing `reel.yaml` is replaced by a document with a chapter named `"Party "`
- **THEN** the write fails with the parse error and the `reel.yaml` on disk is unchanged
