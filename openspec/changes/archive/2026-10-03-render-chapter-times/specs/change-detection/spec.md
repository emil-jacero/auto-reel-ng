## MODIFIED Requirements

### Requirement: Render manifest sidecar
The last successful render of an event SHALL be recorded in `render-manifest.json` under the event's
`.auto-reel/cache/` directory, containing: a manifest schema version, the fingerprint, the four component
sub-hashes, the output filename, the engine identity in readable form, a written-at timestamp, and the chapter
times of the rendered movie. The chapter times SHALL be a list with one entry per chapter, in movie order,
holding the chapter's name, its start and end in integer milliseconds in the rendered movie, and the span of its
title card (start and end in milliseconds) or `null` when the chapter has no title card; they are specified by
"Chapter times are recorded from the same measured timeline" (movie-assembly). A manifest written without a
render that measured them, such as manifest adoption, SHALL record no chapter times (`null`). The chapter times
SHALL NOT be part of the fingerprint or of any staleness verdict, and no reader SHALL treat them as a claim on a
file. The manifest schema version stays 1: a manifest without the field reads as no chapter times, and a field
that is not a well-formed list (every entry a name, whole-number start and end with `0 <= start <= end`, and a
title-card span that is `null` or lies inside its chapter) reads as no chapter times as a whole, without making
the manifest unreadable. A reader SHALL NOT repair, infer or partly keep a malformed list. The sidecar SHALL be
the sole persistent record of last-render state — no database copy. An unreadable or schema-incompatible
manifest SHALL be treated as absent (fail open to stale, never fail closed to skip).

#### Scenario: Manifest lives beside the analysis cache
- **WHEN** an event is successfully rendered with a fingerprint supplied
- **THEN** `<event>/.auto-reel/cache/render-manifest.json` exists with the fingerprint, sub-hashes, output
  name, engine identity, timestamp, and chapter times

#### Scenario: Corrupt manifest fails open
- **WHEN** the manifest file contains invalid JSON
- **THEN** the event is evaluated as stale (as if no manifest existed) and no error aborts the caller

#### Scenario: A manifest written before chapter times existed reads as none
- **WHEN** a version 1 manifest written by an earlier engine has no chapter-times field
- **THEN** it reads as a valid manifest with no chapter times, and the event's verdict is exactly what it was

#### Scenario: A malformed chapter list reads as none
- **WHEN** a version 1 manifest's chapter-times field is `"x"`, or a list whose second entry has a start
  after its end, or a non-integer start, or a title-card span outside its chapter
- **THEN** the manifest still reads as valid, with no chapter times at all (not the first entry), and the
  event's verdict is unchanged

#### Scenario: Adoption records no chapter times
- **WHEN** `adopt-renders` writes a manifest for a movie rendered before the gate existed
- **THEN** the manifest's chapter times are `null`, and no ffprobe of that movie is made to fill them

#### Scenario: Recording chapter times does not change the verdict
- **WHEN** an event is rendered, and then its fingerprint is computed again from unchanged inputs
- **THEN** the fingerprint equals the manifest's and the event evaluates fresh, as it did before chapter times
  were recorded

#### Scenario: A re-render replaces the chapter times
- **WHEN** an event rendered with two chapters is edited to three chapters and rendered again
- **THEN** its manifest records three chapters measured by the second render, none carried from the first
