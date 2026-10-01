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
- the event's **expected output** does not exist. The expected output is the path the output-naming rule derives
  from the event's current metadata under the output directory in use.

The verdict SHALL carry the changed components (by comparing sub-hashes) as human-readable reasons. A force
request SHALL bypass the gate entirely. All staleness decisions in the system MUST go through this gate.

When the expected output does not exist, the verdict SHALL cite exactly one reason for it:
- **output renamed**, when all of these hold:
  - the file name the manifest records for the last render differs from the expected output's file name;
  - the recorded name is a bare file name, with no folder part;
  - a regular file with the recorded name exists where the output-naming rule places a movie of that name under
    the same output directory. That place is the year folder of the name's `YYYY-MM-DD` date prefix, or the output
    directory itself when the name has no date prefix.

  This means the event's name (its title, date or location) changed after the render that wrote the movie still on
  disk. The next render writes the expected output under the new name and leaves the recorded file where it is.
- **missing output**, otherwise. Either the recorded name is the expected one, or no regular file with the
  recorded name is at that place, or the recorded value is not a bare file name. A recorded value that is not a
  bare file name is never looked up.

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
  `../Grillning.mp4`, an absolute path to an existing file, an empty string, or `2024` (the year folder itself)
- **THEN** the verdict cites `editorial` and `output`, and not `output_renamed`

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

### Requirement: Manifest adoption
The system SHALL support explicit adoption: for an event whose output file exists, writing a manifest at
the current fingerprint as the operator's assertion that the existing output reflects the current inputs.
Adoption MUST be explicit (operator-invoked), MUST skip events with no output file, and MUST NOT render
anything.

#### Scenario: Existing output is adopted
- **WHEN** adoption runs over an event with an output file and no manifest
- **THEN** a manifest at the current fingerprint is written and the event subsequently evaluates fresh

#### Scenario: Unrendered event is not adopted
- **WHEN** adoption runs over an event with no output file
- **THEN** no manifest is written and the event remains stale
</content>

### Requirement: A renamed event keeps its previous movie
When an event's output path has changed since its last render, because its title, date or location changed under
the output-naming rule, the engine MUST NOT delete, move, rename or overwrite the movie that render wrote.

The next successful render of the event SHALL:
- write its movie at the new expected output path;
- record the new file name in the manifest;
- leave the previous movie on disk, unchanged.

The event then evaluates fresh. The previous movie is an ordinary file in the output directory, and no later verdict
refers to it. Removing it is the operator's decision. This SHALL hold for a forced render too, and for every render
path: the CLI's `render` and the worker.

A render still replaces whatever file is at its own expected output path, as every render of a stale event does.
That covers two cases. One is a movie an earlier render left under the name the event has again. The other is a
case-only change of name on a case-insensitive filesystem, where the new path names the previous movie's own file.
In both cases the expected output already exists, so the gate cites neither `output` nor `output_renamed`.

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
