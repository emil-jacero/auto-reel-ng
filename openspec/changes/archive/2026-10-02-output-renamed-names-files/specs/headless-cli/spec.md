## MODIFIED Requirements

### Requirement: `scan`/`list` reports inventory without rendering

The `scan` subcommand SHALL report, per selected event, its clips and their reconcile
classification (`NEW`/`ACTIVE`/`IGNORED`/`MISSING`) and its staleness verdict — fresh, or stale with the
changed components as reasons — without running any render or ffmpeg encode. When the verdict cites `output_renamed`, the `stale:` line SHALL follow that reason with the movie file it found and the movie file the next render writes, each quoted: ``output_renamed (was '<previous movie>', now '<expected output>')``. The file names are those the verdict carries, without folder parts, and the whole `stale:` line stays on one line. A stale verdict that does not cite `output_renamed` prints its reasons exactly as before, and a fresh one prints `fresh`.

An event whose folder or
`reel.yaml` cannot be read for lack of permission SHALL be reported as an `ERROR` for that event, naming
the folder and the permission failure. It MUST NOT be listed as an empty or folder-seeded event, and it
MUST NOT end the command: the remaining
events are still listed and the command exits non-zero. Whether a `reel.yaml` exists SHALL be decided by the disk
answering, never by a lookup the disk refused.

#### Scenario: Scan lists events and clip status

- **WHEN** `scan` runs over a project
- **THEN** it prints each event with its clips classified, and writes no output files

#### Scenario: Missing referenced clip is surfaced

- **WHEN** an event's `reel.yaml` references a clip absent from disk
- **THEN** `scan` reports that clip as `MISSING`

#### Scenario: Staleness is reported with reasons

- **WHEN** `scan` runs over one fresh event and one event whose clips changed since its last render
- **THEN** the first is reported fresh and the second stale citing the clip-set component

#### Scenario: A renamed event's old and new movie files are named
- **WHEN** `scan` runs over `2024-06-27 - Grillning med grannar`, rendered as
  `2024-06-27 - Grillning med Grannar.mp4` and then retitled `Grillkväll med grannarna`
- **THEN** it prints `stale: editorial, output_renamed (was '2024-06-27 - Grillning med Grannar.mp4', now
  '2024-06-27 - Grillkväll med grannarna.mp4')` for that event
- **AND** it renders nothing and writes no file

#### Scenario: A deleted movie is not reported as renamed
- **WHEN** `scan` runs over an otherwise fresh event whose rendered movie was deleted with no edit
- **THEN** it prints `stale: output`, with no file names

#### Scenario: An event folder that cannot be searched is an error row
- **WHEN** `scan` runs over three events and one is a folder with mode `0600` (names listable, nothing
  inside it can be looked up) holding a `reel.yaml` titled `Real` and `a.mp4`
- **THEN** that event is reported as `ERROR` naming the permission failure, it is not listed with the
  folder-name title or as an event with no clips, the other two are listed, and the command exits non-zero

#### Scenario: An event folder that cannot be listed is an error row
- **WHEN** `scan` runs over a project and one event folder has mode `0300` and holds a `reel.yaml`
- **THEN** that event is reported as `ERROR` naming the permission failure rather than ending the command
  with a traceback, the other events are listed, and the command exits non-zero
