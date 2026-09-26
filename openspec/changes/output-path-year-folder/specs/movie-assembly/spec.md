## MODIFIED Requirements

### Requirement: Output naming and overwrite control

The engine SHALL write the movie to `<YYYY>/<title> - <location>.mp4` under the output directory, where
`YYYY` is the four-digit year of the event's metadata date and the location part is omitted when absent.
An event with no metadata date SHALL be written to `<title> - <location>.mp4` directly under the output
directory: the year folder is omitted, never guessed from the folder layout, the clips, or the clock. This
layout is carried over from auto-reel, which wrote `<output>/<year>/<name>` and used an empty year when the
date was absent. The engine SHALL create the year folder when it does not exist. Every component that
needs an event's output path (rendering, the staleness gate's call sites, adoption, job enqueue, the
worker, and the API) SHALL derive it by this one rule, so the rule cannot drift between call sites.

Output finalization SHALL be atomic: the assembled movie is written to a temporary name in the **same
directory as the final output path** (same filesystem) and moved into the final path with an atomic rename
only after post-render verification passes — so a file existing at the final output path guarantees a
complete, verified render, even across a hard kill (SIGKILL, OOM, power loss) mid-assembly. When the
output already exists, the engine SHALL skip rendering unless an explicit overwrite (force) is requested,
in which case it SHALL replace the file; the skip decision MAY trust bare existence because finalization is
atomic. A dry-run mode SHALL build and report the planned commands without executing them or writing
output, and SHALL NOT create the year folder.

#### Scenario: Output filename includes location when present
- **WHEN** an event dated `2024-06-21` has title `Midsummer` and location `Dalarna`
- **THEN** the output file is `<output>/2024/Midsummer - Dalarna.mp4`

#### Scenario: Output filename omits absent location
- **WHEN** an event dated `2023-12-24` has title `Julafton` and no location
- **THEN** the output file is `<output>/2023/Julafton.mp4`

#### Scenario: Same-titled events in different years do not share an output
- **WHEN** events dated `2023-06-23` and `2024-06-21` both have title `Midsommar` and no location
- **THEN** their outputs are `<output>/2023/Midsommar.mp4` and `<output>/2024/Midsommar.mp4` respectively,
  and rendering one leaves the other untouched

#### Scenario: Undated event renders at the output root
- **WHEN** an event in a `flat` layout has title `Sommarlov` and no metadata date
- **THEN** the output file is `<output>/Sommarlov.mp4` and no year folder is created

#### Scenario: Year comes from the metadata date, not the layout folder
- **WHEN** an event directory sits under the `2023/` layout folder but its `reel.yaml` date is `2024-01-01`
- **THEN** the output file is under `<output>/2024/`

#### Scenario: Missing year folder is created
- **WHEN** the output directory exists but has no `2024/` subfolder and a 2024 event is rendered
- **THEN** the `2024/` folder is created and the movie is finalized inside it

#### Scenario: Existing output is not overwritten by default
- **WHEN** the target output file already exists and overwrite is not requested
- **THEN** the engine skips the render and leaves the existing file untouched

#### Scenario: Dry run produces no output
- **WHEN** the engine runs a movie in dry-run mode
- **THEN** it reports the planned commands and writes no intermediate or output files, and creates no year
  folder

#### Scenario: Hard kill mid-assembly leaves nothing at the final path
- **WHEN** the process is killed without cleanup (e.g. SIGKILL) while the final movie is being assembled
- **THEN** no file exists at the final output path (at most a leftover temporary-name file remains)

#### Scenario: Verification precedes finalization
- **WHEN** post-render verification of the assembled movie fails
- **THEN** no file appears at the final output path

#### Scenario: Temporary output shares the output directory
- **WHEN** the engine assembles a movie for a 2024 event
- **THEN** the temporary output file is created in the final output's own directory, `<output>/2024/` (not the scratch/temp dir), so
  the finalizing rename is atomic on one filesystem
