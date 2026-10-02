## MODIFIED Requirements

### Requirement: Staleness gate
The system SHALL provide a single gate that evaluates an event as **stale** if and only if one of these holds:
- no manifest exists;
- the current fingerprint differs from the manifest's;
- the event's **expected output** is not a regular file: it is missing, or a folder or other non-file is at that
  path. The expected output is the path the output-naming rule derives from the event's current metadata under
  the output directory in use.

The verdict SHALL carry the changed components (by comparing sub-hashes) as human-readable reasons. A force
request SHALL bypass the gate entirely. All staleness decisions in the system MUST go through this gate.

When the expected output is not a regular file, the verdict SHALL cite exactly one reason for it:
- **output renamed**, when all of these hold:
  - the file name the manifest records for the last render differs from the expected output's file name;
  - the recorded name is a bare file name, with no folder part, and is not empty, `.` or `..`;
  - a regular file with the recorded name exists where the output-naming rule places a movie of that name under
    the same output directory. That place is the year folder of the name's `YYYY-MM-DD` date prefix, or the output
    directory itself when the name has no date prefix.

  This means the event's name (its title, date or location) changed after the render that wrote the movie still on
  disk. The next render writes the expected output under the new name and leaves the recorded file where it is.
  Only another event's render can replace that file (see "A renamed event keeps its previous movie").
  Only the output directory in use is searched. A movie the last render wrote into another output directory is not
  looked for, so an event whose last render went elsewhere cites the missing-output reason.
- **missing output**, otherwise. Either the recorded name is the expected one, or no regular file with the
  recorded name is at that place, or the recorded value is not a bare file name. A recorded value that is not a
  bare file name, or that is empty, `.` or `..`, is never looked up: nothing is checked on disk for it.

The output-renamed reason MUST NOT change whether an event is stale. It is cited only where the missing-output reason
would otherwise have been cited. Every caller of the gate therefore makes the same stale or fresh decision with it as
without it: `render`, `enqueue`, `POST /api/v1/jobs`, `adopt-renders` and the worker's claim-time recheck. When the
expected output is a regular file, neither reason is cited, whatever name the manifest records.

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

#### Scenario: A folder at the expected path is a missing movie
- **WHEN** the manifest matches the current fingerprint and records the expected output's file name, but a folder
  is at the expected path where the movie belongs
- **THEN** the verdict is stale citing only the missing output, as it is for an absent file

#### Scenario: A folder at the expected path does not hide a kept movie
- **WHEN** the retitled Grillning has a folder at its new expected path, and its previous movie is still on disk
  under the recorded name
- **THEN** the verdict is stale citing `editorial` and `output_renamed`

#### Scenario: A movie in another output directory is not looked for
- **WHEN** `2024-06-27 - Grillning med grannar` was rendered into one output directory and retitled, and its verdict
  is then evaluated against a different output directory that holds no movie of the event
- **THEN** the verdict is stale citing `editorial` and `output`, and not `output_renamed`
- **AND** nothing outside the output directory in use is checked on disk

### Requirement: Manifest adoption
The system SHALL support explicit adoption: for an event whose output file exists as a regular file, writing a manifest at
the current fingerprint as the operator's assertion that the existing output reflects the current inputs.
Adoption MUST be explicit (operator-invoked), MUST skip events with no output file, and MUST NOT render
anything.

#### Scenario: Existing output is adopted
- **WHEN** adoption runs over an event with an output file and no manifest
- **THEN** a manifest at the current fingerprint is written and the event subsequently evaluates fresh

#### Scenario: Unrendered event is not adopted
- **WHEN** adoption runs over an event with no output file
- **THEN** no manifest is written and the event remains stale

#### Scenario: A folder at the output path is not adopted
- **WHEN** adoption runs over an event whose expected output path is a folder
- **THEN** no manifest is written, the event is reported as unrendered, and it remains stale

## ADDED Requirements

### Requirement: A render refuses a non-file at its output path
When the expected output path of an event exists but is not a regular file, such as a folder, a render of that
event SHALL fail with a typed render error that names the path. This SHALL hold whether or not an overwrite is
requested, so a skip never reports a non-file as an up-to-date movie. The render SHALL fail before it executes
any ffmpeg invocation, SHALL NOT remove or replace what is at the path, SHALL NOT write a manifest, and SHALL be
reported as that event's failure without stopping the other events of a batch. A dry run is unchanged: it builds
and reports the planned commands and checks nothing on disk.

#### Scenario: A folder where the movie belongs fails the render
- **WHEN** a forced render of an event whose expected output path is a folder is requested
- **THEN** the render fails with a render error naming that path, the folder and its contents are unchanged, no
  manifest is written, and no ffmpeg invocation was made

#### Scenario: Without overwrite a non-file is not a skip
- **WHEN** a render without overwrite is requested for an event whose expected output path is a folder
- **THEN** the render fails with the same error and does not report the render as skipped

#### Scenario: A batch continues past it
- **WHEN** a batch holds an event whose expected output path is a folder and a second, renderable event
- **THEN** the first is reported as failed with the error, and the second is rendered
