## MODIFIED Requirements

### Requirement: Output naming and overwrite control

The engine SHALL write the movie for an event with a metadata date to
`<YYYY>/<YYYY-MM-DD> - <title> - <location>.mp4` under the output directory. Both `YYYY` (the year folder)
and `YYYY-MM-DD` (the ISO date that prefixes the file name) SHALL come from the event's metadata date, and
the location part SHALL be omitted when absent. This is the layout and naming auto-reel used for the
existing archive: its movie title was the date-prefixed title (`YYYY-MM-DD - Title`), to which it appended
the location, under a year folder. An existing legacy output therefore sits exactly where this rule looks for
it.

An event with no metadata date SHALL be written to `<title> - <location>.mp4` directly under the output
directory, with no date prefix and no year folder. The date is never guessed from the folder layout, the
clips, or the clock. The engine SHALL create the year folder when it does not exist. Every component that
needs an event's output path (rendering, the staleness gate's call sites, adoption, job enqueue, the
worker, and the API) SHALL derive it by this one rule, so the rule cannot drift between call sites.

The output file name SHALL always be exactly one path component. Within the title and the location, every
path separator (`/` and `\`) and every control character (including NUL) SHALL be replaced by `-` in the
file name only; the title and location as authored in `reel.yaml`, the API and on the title card are never
altered. A name built from a title or location containing separators therefore never creates a folder and
can never form a `..` component. Before rendering or planning a dry run, the engine SHALL verify that the
output path lies inside the output directory (a lexical check, so a symlinked year folder remains valid) and
SHALL fail the event with a typed render error, creating no directory or file, when it does not.

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
- **THEN** the output file is `<output>/2024/2024-06-21 - Midsummer - Dalarna.mp4`

#### Scenario: A slash in the title does not create a folder
- **WHEN** an event dated `2025-01-16` has title `Mid/sommar`
- **THEN** the output file is `<output>/2025/2025-01-16 - Mid-sommar.mp4`, no `2025-01-16 - Mid` folder is
  created, and the title in `reel.yaml` still reads `Mid/sommar`

#### Scenario: A slash in the location does not create a folder
- **WHEN** an event dated `2025-01-16` has title `T` and location `Gamla/stan`
- **THEN** the output file is `<output>/2025/2025-01-16 - T - Gamla-stan.mp4`

#### Scenario: A traversal title cannot escape the output directory
- **WHEN** an event dated `2025-01-16` has title `a/../../../escaped`
- **THEN** the output file is `<output>/2025/2025-01-16 - a-..-..-..-escaped.mp4`, and nothing is written
  outside the output directory

#### Scenario: Backslash and control characters are replaced
- **WHEN** an event has a title containing a backslash, a NUL or a newline
- **THEN** each of those characters appears as `-` in the file name, which remains one path component

#### Scenario: An output path outside the output directory is refused
- **WHEN** the output path computed for an event would resolve outside the output directory, including in
  dry-run mode
- **THEN** the engine fails that event with a typed render error and creates no directory, `.part` file or
  output

#### Scenario: A symlinked year folder is still valid
- **WHEN** `<output>/2024` is a symlink to another directory on the archive
- **THEN** a 2024 event renders into the link target and the containment check does not refuse it

#### Scenario: Output filename omits absent location
- **WHEN** an event dated `2023-12-24` has title `Julafton` and no location
- **THEN** the output file is `<output>/2023/2023-12-24 - Julafton.mp4`

#### Scenario: Same-titled events in different years do not share an output
- **WHEN** events dated `2023-06-23` and `2024-06-21` both have title `Midsommar` and no location
- **THEN** their outputs are `<output>/2023/2023-06-23 - Midsommar.mp4` and
  `<output>/2024/2024-06-21 - Midsommar.mp4` respectively, and rendering one leaves the other untouched

#### Scenario: Same-titled events on different days of one year do not share an output
- **WHEN** events dated `2024-12-08` and `2024-12-15` both have title `Dans Hemma` and location `Kungälv`
- **THEN** their outputs are `<output>/2024/2024-12-08 - Dans Hemma - Kungälv.mp4` and
  `<output>/2024/2024-12-15 - Dans Hemma - Kungälv.mp4`

#### Scenario: The legacy archive's names are reproduced exactly
- **WHEN** the event folder `2017-07-20 - Båttur med Liljan och Ralf`, with no `reel.yaml`, is seeded and
  its output path is derived
- **THEN** the path is `2017/2017-07-20 - Båttur med Liljan och Ralf.mp4`, byte-for-byte the name auto-reel
  wrote for it

#### Scenario: Undated event renders at the output root
- **WHEN** an event in a `flat` layout has title `Sommarlov` and no metadata date
- **THEN** the output file is `<output>/Sommarlov.mp4`, with no date prefix, and no year folder is created

#### Scenario: Year comes from the metadata date, not the layout folder
- **WHEN** an event directory sits under the `2023/` layout folder but its `reel.yaml` date is `2024-01-01`
- **THEN** the output file is `<output>/2024/2024-01-01 - <title>.mp4`

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
- **THEN** the temporary output file is created in the final output's own directory, `<output>/2024/` (not
  the scratch/temp dir), so the finalizing rename is atomic on one filesystem
