## MODIFIED Requirements

### Requirement: Output naming and overwrite control

The engine SHALL write the movie to `<title> - <location>.mp4` (location omitted when absent), carried over
from auto-reel. Output finalization SHALL be atomic: the assembled movie is written to a temporary name in
the **output directory** (same filesystem) and moved into the final path with an atomic rename only after
post-render verification passes — so a file existing at the final output path guarantees a complete,
verified render, even across a hard kill (SIGKILL, OOM, power loss) mid-assembly. When the output already
exists, the engine SHALL skip rendering unless an explicit overwrite (force) is requested, in which case it
SHALL replace the file; the skip decision MAY trust bare existence because finalization is atomic. A
dry-run mode SHALL build and report the planned commands without executing them or writing output.

#### Scenario: Output filename includes location when present
- **WHEN** an event has title `Midsummer` and location `Dalarna`
- **THEN** the output file is named `Midsummer - Dalarna.mp4`

#### Scenario: Existing output is not overwritten by default
- **WHEN** the target output file already exists and overwrite is not requested
- **THEN** the engine skips the render and leaves the existing file untouched

#### Scenario: Dry run produces no output
- **WHEN** the engine runs a movie in dry-run mode
- **THEN** it reports the planned commands and writes no intermediate or output files

#### Scenario: Hard kill mid-assembly leaves nothing at the final path
- **WHEN** the process is killed without cleanup (e.g. SIGKILL) while the final movie is being assembled
- **THEN** no file exists at the final output path (at most a leftover temporary-name file remains)

#### Scenario: Verification precedes finalization
- **WHEN** post-render verification of the assembled movie fails
- **THEN** no file appears at the final output path

#### Scenario: Temporary output shares the output directory
- **WHEN** the engine assembles a movie
- **THEN** the temporary output file is created in the output directory itself (not the scratch/temp dir),
  so the finalizing rename is atomic on one filesystem
