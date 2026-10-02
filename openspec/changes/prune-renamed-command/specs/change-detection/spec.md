## ADDED Requirements

### Requirement: The render manifest remembers the movie names it superseded

Whenever the engine writes a render manifest (a successful render, and manifest adoption), it SHALL read the
event's previous manifest, if it is readable, and record in the new manifest a `superseded` list: the previous
manifest's `superseded` names plus the previous manifest's `output` when that differs from the new `output`,
without duplicates, in the order they were superseded, and without the new `output` itself. Each entry is a bare
movie file name, as `output` is. The list SHALL NOT be part of the fingerprint or of any staleness verdict, and
no reader SHALL treat a name in it as a claim on a file. The manifest schema version stays 1: a manifest without
the field reads as an empty list, and a field that is not a list of strings reads as an empty list without making
the manifest unreadable. An unreadable previous manifest contributes nothing (fail open). Writing the list SHALL
NOT delete, move or rename any movie.

#### Scenario: A rename and a render record the old name
- **WHEN** an event whose manifest records `2024-06-27 - Grillning med Grannar.mp4` is retitled and rendered
- **THEN** the new manifest records `2024-06-27 - Grillkväll med grannarna.mp4` as `output` and
  `["2024-06-27 - Grillning med Grannar.mp4"]` as `superseded`

#### Scenario: Several renames accumulate
- **WHEN** an event is rendered as A, retitled and rendered as B, retitled and rendered as C
- **THEN** its manifest records `output` C and `superseded` `[A, B]`

#### Scenario: A render under the same name adds nothing
- **WHEN** a stale event is rendered again without a name change, or adopted by `adopt-renders`
- **THEN** its `superseded` list is unchanged

#### Scenario: Renaming back removes the current name from the list
- **WHEN** an event rendered as A, then B, is retitled back and rendered as A
- **THEN** its manifest records `output` A and `superseded` `[B]`

#### Scenario: A manifest without the field reads as empty
- **WHEN** a version 1 manifest has no `superseded` field, or the field is `"x"`
- **THEN** it reads as a valid manifest with an empty list, and the event's verdict is unchanged

#### Scenario: Recording the list leaves the old movie alone
- **WHEN** the renamed event is rendered
- **THEN** the previous movie is on disk unchanged, as "A renamed event keeps its previous movie" requires
