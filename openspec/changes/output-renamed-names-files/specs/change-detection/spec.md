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

A verdict that cites the output-renamed reason SHALL also name the two movie files it refers to, so that no consumer
has to work them out again from the event's metadata:
- the **previous movie**, the file name of the regular file the gate found for the recorded name. It is the name of
  that file as found, not the manifest's recorded string, so it is a bare file name of a file that exists;
- the **expected output**, the file name of the event's expected output, which the next render writes.

Both are file names without a folder part. They differ from each other, because the output-renamed reason requires
the recorded name to differ from the expected one. A verdict that does not cite the output-renamed reason, whether
fresh or stale for any other reason, SHALL carry neither name. Carrying the names MUST NOT change the verdict's
`stale` flag or its reasons.

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
- **AND** the verdict names the previous movie `2024-06-27 - Grillning med Grannar.mp4` and the expected output
  `2024-06-27 - Grillkväll med grannarna.mp4`
- **AND** `auto-reel scan` prints `stale: editorial, output_renamed (was '2024-06-27 - Grillning med Grannar.mp4',
  now '2024-06-27 - Grillkväll med grannarna.mp4')` for that event, on one line

#### Scenario: A changed location is a rename in the same year folder
- **WHEN** the fresh `2024-06-21 - Midsommar - Dalarna`, rendered to
  `<output>/2024/2024-06-21 - Midsommar - Dalarna.mp4`, has its location changed to `Leksand`
- **THEN** the verdict is stale citing `editorial` and `output_renamed`
- **AND** it names the previous movie `2024-06-21 - Midsommar - Dalarna.mp4` and the expected output
  `2024-06-21 - Midsommar - Leksand.mp4`

#### Scenario: A date moved to another year is a rename across year folders
- **WHEN** `2023-06-23 - Midsommar - Dalarna`, rendered to `<output>/2023/2023-06-23 - Midsommar - Dalarna.mp4`,
  has its date changed to `2022-06-23`, so the expected output is
  `<output>/2022/2022-06-23 - Midsommar - Dalarna.mp4`
- **THEN** the verdict cites `output_renamed`, because the recorded movie is still in the `2023` year folder
- **AND** it names the previous movie `2023-06-23 - Midsommar - Dalarna.mp4` and the expected output
  `2022-06-23 - Midsommar - Dalarna.mp4`, each without its year folder

#### Scenario: A renamed event whose old movie was deleted is missing its movie
- **WHEN** the retitled Grillning's `<output>/2024/2024-06-27 - Grillning med Grannar.mp4` is deleted as well
- **THEN** the verdict cites `editorial` and `output`, and not `output_renamed`

#### Scenario: A verdict that does not cite the rename names no files
- **WHEN** the verdict is fresh, or cites only `no_manifest`, only `output`, or only fingerprint components
  (including the retitled Grillning whose old movie was deleted, which cites `editorial` and `output`)
- **THEN** it carries neither a previous-movie name nor an expected-output name
- **AND** `auto-reel scan` prints its `stale:` or `fresh` line exactly as before

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

#### Scenario: The names do not change the decision
- **WHEN** the same retitled event is evaluated, once as the gate does now and once ignoring the two names
- **THEN** the `stale` flag and the reasons are identical

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
- **AND** it names the previous movie as found on disk and the expected output, whose path holds a folder

#### Scenario: A movie in another output directory is not looked for
- **WHEN** `2024-06-27 - Grillning med grannar` was rendered into one output directory and retitled, and its verdict
  is then evaluated against a different output directory that holds no movie of the event
- **THEN** the verdict is stale citing `editorial` and `output`, and not `output_renamed`
- **AND** nothing outside the output directory in use is checked on disk
