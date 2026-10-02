# change-detection Specification

## Purpose

Detect whether an event's rendered output is still current with its inputs — without probing media or
depending on the host or acceleration device — so the CLI, scheduler, and API can skip redundant renders,
gate enqueue/claim decisions, and let operators explicitly adopt an already-rendered archive.

## Requirements

### Requirement: Probe-free, host-independent render fingerprint
The system SHALL compute an event's render fingerprint as a hash over exactly four components, each with
its own sub-hash: **editorial** (the event's `reel.yaml` in canonical form, or the folder-seed equivalent
when absent), **defaults** (the resolved D-2 project look defaults), **clip_set** (the sorted on-disk clip
identities, each with its content signal — size + mtime_ns by default, sha256 under the existing hash
opt-in), and **engine** (the `RENDER_GRAPH_VERSION` constant + the ffmpeg version string). Computing the
fingerprint MUST NOT invoke ffprobe or read media content (beyond the opt-in hash), and the value MUST be
independent of the acceleration profile, device, or host — the same event state yields the same
fingerprint wherever it is computed.

#### Scenario: Unchanged event is fingerprint-stable
- **WHEN** the fingerprint is computed twice (including from different processes) with no disk change
  between
- **THEN** both values are byte-identical

#### Scenario: Each component moves the fingerprint
- **WHEN** exactly one of: a clip's content signal changes, `reel.yaml` is edited semantically, a project
  look default changes, or `RENDER_GRAPH_VERSION` is bumped
- **THEN** the fingerprint changes and only that component's sub-hash differs

#### Scenario: Device selection does not move the fingerprint
- **WHEN** the same event is evaluated under a CPU profile and a GPU profile
- **THEN** the fingerprints are identical

#### Scenario: No probing
- **WHEN** a fingerprint is computed
- **THEN** no ffprobe invocation occurs

### Requirement: Render manifest sidecar
The last successful render of an event SHALL be recorded in `render-manifest.json` under the event's
`.auto-reel/cache/` directory, containing: a manifest schema version, the fingerprint, the four component
sub-hashes, the output filename, the engine identity in readable form, and a written-at timestamp. The
sidecar SHALL be the sole persistent record of last-render state — no database copy. An unreadable or
schema-incompatible manifest SHALL be treated as absent (fail open to stale, never fail closed to skip).

#### Scenario: Manifest lives beside the analysis cache
- **WHEN** an event is successfully rendered with a fingerprint supplied
- **THEN** `<event>/.auto-reel/cache/render-manifest.json` exists with the fingerprint, sub-hashes, output
  name, engine identity, and timestamp

#### Scenario: Corrupt manifest fails open
- **WHEN** the manifest file contains invalid JSON
- **THEN** the event is evaluated as stale (as if no manifest existed) and no error aborts the caller

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
That covers two cases:
- a movie an earlier render of the event left under the name the event has again;
- a case-only change of name on a case-insensitive filesystem, where the new path names the previous movie's own
  file.

In both cases the expected output already exists, so the gate cites neither `output` nor `output_renamed`.

Another event whose current name is the renamed event's old name is not a third case: the kept movie is recorded
in the renamed event's manifest, so that other event's render is refused unless forced ("A render refuses to
replace a movie another event records"). A forced render of it does replace the kept movie, and the renamed
event's verdict then still cites `output_renamed`, although the file under its old name is now the other
event's movie.

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

#### Scenario: Another event taking the old name does not replace the kept movie
- **WHEN** `2024-06-27 - Grillning med grannar` was retitled and not yet rendered, so its manifest still records
  the old name, and a different event is retitled to that old name and rendered without force while the old movie
  is on disk
- **THEN** the other event's render is refused with the claimed-movie error naming the renamed event, and the old
  movie is unchanged

### Requirement: Fingerprinting does not raise on an editorial or defaults map

Computing any fingerprint component, including the editorial hash that the API also serves as its ETag,
SHALL NOT raise because a mapping in the hashed content has keys that are not strings, or keys of mixed
types that cannot be ordered. For every input whose hash can be computed without this rule, the hash SHALL
be exactly the value it was before; the rule SHALL only supply a hash where none could be computed. Two
mappings that differ only in a key's type (`{1: x}` and `{"1": x}`) or in the presence of a key SHALL NOT be
conflated by the fallback.

#### Scenario: Native-key content hashes are unchanged

- **WHEN** an editorial dict or a defaults map has only string keys, or only integer keys, or only boolean keys
- **THEN** its hash equals the SHA-256 of its sorted-key JSON text, as it did before this requirement

#### Scenario: A date key does not crash the defaults hash

- **WHEN** the fingerprint is computed for a `look_defaults` map containing a `datetime.date` key
- **THEN** a fingerprint is returned, it is identical across two computations (including in two processes),
  and it differs from the fingerprint of the same map with a different value

#### Scenario: Mixed int and str keys do not crash the editorial hash

- **WHEN** `editorial_hash` is computed for a document whose `look` has the keys `1` and `"b"`
- **THEN** a hash is returned and a change to either value moves it

#### Scenario: Keys that differ only in type are not conflated

- **WHEN** the hash fallback is used for `{1: "a", "1": "b"}` and for `{1: "b", "1": "a"}`
- **THEN** the two hashes differ

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

### Requirement: A render refuses to replace a movie another event records

Before a render replaces a regular file at its event's expected output path, and unless the render is forced, the
engine SHALL check whether the render manifest of any *other* event of the project records exactly that file as
its output. The events checked are those of the project's own layout walk, whole: the CLI's `--years` filter
narrows what is rendered, never who may claim. The comparison is on the full path,
NFC-normalised and case-insensitive, and an event's recorded name is placed by the naming rule
(`recorded_output_path`), so a recorded name is a match only when it is a bare file name. A manifest that cannot
be read claims nothing. The event being rendered is never its own claimant, and a file its own manifest records is its own movie, so
it is not refused even while another event's manifest still records the same file. An unparseable or unprocessable
`reel.yaml` of the other event does not stop its manifest from claiming.

When another event claims the file, the render SHALL fail that event with a typed engine error that names the
file and the claiming event(s) and says that a forced render replaces it. The refusal SHALL be decided before
anything is rendered or probed for the event: no `.part`, no manifest and no ffmpeg invocation, and, in the
worker, no clip adopted into its `reel.yaml`. (The CLI's reconcile step runs before its gate for every event, so
it may already have seeded or adopted into `reel.yaml`, as it does for an event refused by the collision rule; the
refusal itself writes nothing.) It SHALL NOT stop the other events of a batch. It SHALL hold for the CLI's `render` and for
the worker; a forced render (`--force`, a job's `force`) SHALL skip the check, and so SHALL a dry run, which
checks nothing on disk. A render that would create a new file, or whose output path holds a file nobody records,
replaces nothing and is unaffected. The engine SHALL NOT delete, move or rename the claimed movie in any case.

This rule is separate from the output-collision rule: two events whose *current* paths are equal remain refused
whether or not the render is forced.

The claim holds for as long as the other event's manifest records the file; it ends when that event renders
under another name, or when the file is gone. The refusal is evaluated against the manifests as they are when the
event is built, so in one batch an event taking the old name of a renamed event that is also in the batch is
refused, and succeeds in a later run.

#### Scenario: An event taking a renamed event's old name is refused
- **WHEN** `2024-06-27 - Grillning med grannar` was rendered, then retitled `Grillkväll` and not yet re-rendered,
  and a second event dated `2024-06-27` is titled `Grillning med grannar` and rendered without force
- **THEN** the second event fails with an error naming `2024/2024-06-27 - Grillning med grannar.mp4` and the
  retitled event, the file is unchanged with no `.part` beside it, no manifest is written for the second event,
  and the exit status of `render` is non-zero

#### Scenario: The owner of a movie is not refused for a stale record
- **WHEN** a forced render gave event A the movie `F`, event B's manifest still records `F` too, and A is rendered
  again without force
- **THEN** A is not refused, in the CLI or the worker

#### Scenario: A claimant outside the years filter still claims
- **WHEN** `render --years 2024` renders an event whose output file is recorded by an event filed under a
  folder the filter excludes
- **THEN** the render is refused and names that event

#### Scenario: The other events of the batch still render
- **WHEN** the refused event shares a `render` batch with a renderable third event
- **THEN** the third event is rendered and reported, and the refused one is reported as failed

#### Scenario: Force replaces the claimed movie
- **WHEN** the same render is requested with `--force`, or the worker claims a job with `force` set
- **THEN** the file is replaced by the second event's movie and the second event's manifest is written

#### Scenario: A worker job is refused with the same text
- **WHEN** the worker claims a job for the second event without force
- **THEN** the job ends `failed` with the claimed-movie text as its error, and its `reel.yaml` is unchanged

#### Scenario: Once the renamed event re-renders the name is free
- **WHEN** the retitled event is rendered under its new name, and the second event is then rendered without force
- **THEN** the second event replaces the old-named file, because no manifest records it any longer

#### Scenario: A file nobody records is replaced as before
- **WHEN** an event's stale output path holds a movie that no other event's manifest records
- **THEN** an unforced render replaces it

#### Scenario: A case-insensitive match is a claim
- **WHEN** the other event's manifest records `2024-06-27 - grillning med grannar.mp4` and the file at the
  render's path differs from it only in case
- **THEN** the render is refused

#### Scenario: An unreadable manifest claims nothing
- **WHEN** the other event's `render-manifest.json` is not valid JSON
- **THEN** the render is not refused on its account

#### Scenario: A recorded path is not a match
- **WHEN** another event's manifest records `..` or a name containing a path separator
- **THEN** it claims no file

#### Scenario: An unparseable reel.yaml does not hide a claim
- **WHEN** the other event's `reel.yaml` does not parse but its manifest records the file
- **THEN** the render is refused and names that event

#### Scenario: A walk that fails refuses the worker job
- **WHEN** the layout walk of the project fails while the worker checks a replacing job
- **THEN** the job fails with the walk's error and renders nothing

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
