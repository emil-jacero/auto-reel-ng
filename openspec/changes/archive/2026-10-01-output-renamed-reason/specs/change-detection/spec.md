## MODIFIED Requirements

### Requirement: Staleness gate
The system SHALL provide a single gate that evaluates an event as **stale** if and only if one of these holds:
- no manifest exists;
- the current fingerprint differs from the manifest's;
- the event's **expected output** does not exist. The expected output is the path the output-naming rule derives
  from the event's current metadata under the output directory in use.

The verdict SHALL carry the changed components (by comparing sub-hashes) as human-readable reasons. A force
request SHALL bypass the gate entirely. All staleness decisions in the system MUST go through this gate.

When the expected output does not exist, the verdict SHALL cite exactly one reason for it:
- **output renamed**, when all of these hold:
  - the file name the manifest records for the last render differs from the expected output's file name;
  - the recorded name is a bare file name, with no folder part, and is not empty, `.` or `..`;
  - a regular file with the recorded name exists where the output-naming rule places a movie of that name under
    the same output directory. That place is the year folder of the name's `YYYY-MM-DD` date prefix, or the output
    directory itself when the name has no date prefix.

  This means the event's name (its title, date or location) changed after the render that wrote the movie still on
  disk. The next render writes the expected output under the new name and leaves the recorded file where it is.
  Only another event's render can replace that file (see "A renamed event keeps its previous movie").
- **missing output**, otherwise. Either the recorded name is the expected one, or no regular file with the
  recorded name is at that place, or the recorded value is not a bare file name. A recorded value that is not a
  bare file name, or that is empty, `.` or `..`, is never looked up: nothing is checked on disk for it.

The output-renamed reason MUST NOT change whether an event is stale. It is cited only where the missing-output reason
would otherwise have been cited. Every caller of the gate therefore makes the same stale or fresh decision with it as
without it: `render`, `enqueue`, `POST /api/v1/jobs`, `adopt-renders` and the worker's claim-time recheck. When the
expected output exists, neither reason is cited, whatever name the manifest records.

The reasons a verdict may cite SHALL come from a **closed, named vocabulary** owned by the gate: the no-manifest,
missing-output and output-renamed reasons, plus one reason per fingerprint component. The gate MUST NOT emit a reason
outside that vocabulary. Any consumer that publishes reasons, such as the CLI's output or the API's responses, SHALL
take the set from the gate rather than restating it, so the vocabulary has exactly one source of truth. Adding,
removing or renaming a reason is a change to this vocabulary and MUST be made here.

#### Scenario: Fresh event
- **WHEN** the manifest matches the current fingerprint and the output file exists
- **THEN** the verdict is fresh with no reasons

#### Scenario: Missing output is always stale
- **WHEN** the manifest matches the current fingerprint and records the expected output's file name, but that
  file is absent
- **THEN** the verdict is stale citing only the missing output

#### Scenario: Reasons name the changed components
- **WHEN** a clip was replaced and `reel.yaml` was edited since the last render
- **THEN** the stale verdict's reasons include the clip-set and editorial components (and not defaults or
  engine)

#### Scenario: Missing referenced clip makes the event stale, not blocked
- **WHEN** a clip referenced by `reel.yaml` is absent from disk
- **THEN** the clip-set component differs, the event is stale, and downstream rendering proceeds with the
  MISSING clip reported loud (per the existing adoption policy) — the gate never suppresses the render

#### Scenario: A retitled event cites the rename, not a missing movie
- **WHEN** `2024-06-27 - Grillning med grannar` was rendered to
  `<output>/2024/2024-06-27 - Grillning med Grannar.mp4`, its manifest records that name, and its `reel.yaml`
  title was then changed to `Grillkväll med grannarna`, so the expected output
  `<output>/2024/2024-06-27 - Grillkväll med grannarna.mp4` does not exist
- **THEN** the verdict is stale citing `editorial` and then `output_renamed`, and it does not cite `output`
- **AND** `auto-reel scan` prints `stale: editorial, output_renamed` for that event

#### Scenario: A changed location is a rename in the same year folder
- **WHEN** the fresh `2024-06-21 - Midsommar - Dalarna`, rendered to
  `<output>/2024/2024-06-21 - Midsommar - Dalarna.mp4`, has its location changed to `Leksand`
- **THEN** the verdict is stale citing `editorial` and `output_renamed`

#### Scenario: A date moved to another year is a rename across year folders
- **WHEN** `2023-06-23 - Midsommar - Dalarna`, rendered to `<output>/2023/2023-06-23 - Midsommar - Dalarna.mp4`,
  has its date changed to `2022-06-23`, so the expected output is
  `<output>/2022/2022-06-23 - Midsommar - Dalarna.mp4`
- **THEN** the verdict cites `output_renamed`, because the recorded movie is still in the `2023` year folder

#### Scenario: A renamed event whose old movie was deleted is missing its movie
- **WHEN** the retitled Grillning's `<output>/2024/2024-06-27 - Grillning med Grannar.mp4` is deleted as well
- **THEN** the verdict cites `editorial` and `output`, and not `output_renamed`

#### Scenario: A deleted movie is still reported missing
- **WHEN** the fresh `2024-07-14 - Kalas` has its `<output>/2024/2024-07-14 - Kalas.mp4` deleted, with no edit
- **THEN** the verdict is stale citing only `output`

#### Scenario: An existing expected movie is never reported renamed
- **WHEN** an event's expected output exists, and its manifest records a different name whose file also exists
- **THEN** the verdict cites neither `output` nor `output_renamed`; any other reason it cites comes from the
  fingerprint components

#### Scenario: A recorded value that is not a bare file name is never looked up
- **WHEN** the retitled Grillning's manifest has been hand-edited so that its recorded output is
  `../Grillning.mp4`, an absolute path to an existing file, an empty string, `.`, `..`, or `2024` (the year folder
  itself)
- **THEN** the verdict cites `editorial` and `output`, and not `output_renamed`
- **AND** for an empty string, `.` and `..` the gate checks nothing on disk

#### Scenario: The rename reason never changes the decision
- **WHEN** the retitled Grillning, whose verdict cites `output_renamed`, goes through `auto-reel render`,
  `auto-reel enqueue`, `POST /api/v1/jobs` and the worker's claim-time recheck
- **THEN** each treats it as stale, exactly as it treated the same event when its verdict cited `output`:
  `render` renders it, `enqueue` and `POST /api/v1/jobs` enqueue it, and the worker renders the claimed job
- **AND** an event whose expected output exists is fresh or stale exactly as before, whatever name its manifest
  records

#### Scenario: The vocabulary is closed
- **WHEN** any consumer enumerates the reasons a verdict can cite
- **THEN** it obtains exactly the no-manifest reason, the missing-output reason, the output-renamed reason and one
  reason per fingerprint component, and no other value can appear in a verdict

## ADDED Requirements

### Requirement: A renamed event keeps its previous movie
When an event's output path has changed since its last render, because its title, date or location changed under
the output-naming rule, the engine MUST NOT delete, move, rename or overwrite the movie that render wrote, except
as stated below.

The next successful render of the event SHALL:
- write its movie at the new expected output path;
- record the new file name in the manifest;
- leave the previous movie on disk, unchanged.

The event then evaluates fresh. The previous movie is an ordinary file in the output directory, and no later verdict
refers to it. Removing it is the operator's decision. This SHALL hold for a forced render too, and for every render
path: the CLI's `render` and the worker.

A render still replaces whatever file is at its own expected output path, as every render of a stale event does.
That covers three cases:
- a movie an earlier render of the event left under the name the event has again;
- a case-only change of name on a case-insensitive filesystem, where the new path names the previous movie's own
  file;
- another event whose current name is the renamed event's old name. Its render replaces the kept movie, because
  the output-collision check compares only the events' current paths. The renamed event's verdict then still cites
  `output_renamed`, although the file under its old name is now the other event's movie.

In the first two cases the expected output already exists, so the gate cites neither `output` nor
`output_renamed`.

#### Scenario: A render after a retitle writes beside the old movie
- **WHEN** the retitled `2024-06-27 - Grillning med grannar` is rendered
- **THEN** `<output>/2024/2024-06-27 - Grillkväll med grannarna.mp4` is written and verified
- **AND** `<output>/2024/2024-06-27 - Grillning med Grannar.mp4` still exists, with its size and modification time
  unchanged
- **AND** the manifest records `2024-06-27 - Grillkväll med grannarna.mp4`
- **AND** the next verdict for the event is fresh

#### Scenario: A forced render keeps the old movie too
- **WHEN** a renamed event is rendered with force
- **THEN** the new movie is written at the expected path and the previous movie is left unchanged

#### Scenario: A failed render after a rename changes nothing
- **WHEN** the render of a renamed event fails or is cancelled
- **THEN** the previous movie and the manifest are unchanged, no file exists at the new expected path, and the
  verdict still cites `output_renamed`
