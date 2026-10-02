## MODIFIED Requirements

### Requirement: `auto-reel` entry point with subcommands

The system SHALL install a `console_scripts` entry point named `auto-reel` exposing the
subcommands `render`, `scan` (alias `list`), `analyze`, `import`, `enqueue`, `worker`, `jobs`, `serve`,
`adopt-renders`, `thumbs`, and `prune-renamed`. Invalid arguments or an unknown subcommand SHALL produce a non-zero exit and
a usage message.

#### Scenario: Entry point is installed

- **WHEN** the package is installed and `auto-reel --help` is run
- **THEN** the eleven subcommands are listed and the command exits zero

#### Scenario: Unknown subcommand fails

- **WHEN** `auto-reel frobnicate` is run
- **THEN** the command exits non-zero with a usage message

## ADDED Requirements

### Requirement: `prune-renamed` removes superseded movies only on request

`auto-reel prune-renamed <root>` SHALL accept the project options `render` accepts (`-o/--output`, `--layout`,
`--years`) and `--yes`. It SHALL find the **superseded movies** of the selected events: for an event whose render
manifest records a current movie that exists in the output directory as a regular file, every file name in the
manifest's `superseded` list (capability `change-detection`) that exists in the output directory, at the path
the output-naming rule (D-9) gives that name, as a regular file. It SHALL print each one with the event that
superseded it and the movie that replaced it, then a total. Without `--yes` it SHALL be a dry run: it
MUST NOT delete, move or write anything (no movie and no manifest), the output SHALL say the run was a dry run,
and the exit code SHALL be zero when no error was reported. With `--yes` it SHALL delete each listed file and
report it.

It MUST NOT list or delete a file that any other event of the project claims, whichever events `--years`
selected: another event's manifest records the file as its movie (the lookup the render guard uses), or another
event's current expected output path is that file. Paths SHALL be compared case-insensitively and after Unicode
NFC normalisation, as for output collisions. A file that is the replacing movie itself, or the same file as the
replacing movie (for example a case-only rename on a case-insensitive filesystem), SHALL never be listed. It
MUST NOT delete anything that is not a regular file (a folder, or a symbolic link), and MUST NOT delete a path
that does not lie inside the output directory after resolving symbolic links, whatever the manifest records. A
recorded name that is not a bare file name SHALL be ignored. An event whose manifest is absent or unreadable, whose
current movie is missing from the output directory (including a folder at its path), or that lists no
superseded name SHALL contribute nothing. The command MUST NOT render, probe, enqueue, or write a manifest or
`reel.yaml`.

A file that cannot be deleted SHALL be reported with the operating system's reason and the run SHALL continue
with the remaining files; the command SHALL then exit non-zero. A layout walk that fails SHALL end the command
before anything is deleted, with the reason and a non-zero exit. A file that is already gone is not an error and
is not reported.

#### Scenario: A dry run lists the superseded movie and deletes nothing
- **WHEN** `2024-06-27 - Grillning med grannar` was rendered, retitled to `Grillkväll med grannarna` and
  rendered again, so its manifest records the new name with the old name superseded, both files exist in
  `<output>/2024/`, and `prune-renamed <root>` runs
- **THEN** the output names `2024-06-27 - Grillning med Grannar.mp4`, the event, and
  `2024-06-27 - Grillkväll med grannarna.mp4` as its replacement, says it is a dry run, both files are still
  on disk unchanged, and the command exits zero

#### Scenario: `--yes` deletes only the old movie
- **WHEN** the same command runs with `--yes`
- **THEN** `2024-06-27 - Grillning med Grannar.mp4` is deleted and reported, the new movie and the event's
  manifest are byte-for-byte unchanged, and the command exits zero

#### Scenario: A second run finds nothing
- **WHEN** `prune-renamed --yes` has run and the command runs again
- **THEN** it reports no superseded movies, deletes nothing, and exits zero

#### Scenario: A renamed event that has not been re-rendered is untouched
- **WHEN** an event was retitled but not rendered since, so its manifest still records the old movie as its
  current one
- **THEN** that movie is not listed, with or without `--yes`

#### Scenario: The replacing movie must exist
- **WHEN** a manifest records a current movie that is missing from the output directory, or is a folder
- **THEN** that event's superseded movies are not listed

#### Scenario: A movie another event now owns is kept
- **WHEN** an event's old name is now the current movie of another event, recorded in that event's manifest
- **THEN** the file is not listed and is not deleted, even with `--yes`, and the other event's movie is unchanged

#### Scenario: A pending takeover of the old name keeps the file
- **WHEN** another event, not yet rendered, has the old name as its current expected output path
- **THEN** the file is not listed and is not deleted

#### Scenario: An owner outside `--years` still protects the file
- **WHEN** `prune-renamed --years 2024 --yes` runs and an event in 2023 records the superseded 2024 file as its movie
- **THEN** the file is not deleted

#### Scenario: A renamed-back event keeps its movie
- **WHEN** an event was renamed and rendered, and then renamed back to its first name and rendered
- **THEN** the movie it now owns is not listed, even though its name appears in an older superseded list

#### Scenario: A case-only rename does not delete the movie
- **WHEN** an event's superseded name differs from its current movie's only in letter case, on a filesystem
  where both name the same file
- **THEN** the file is not listed and not deleted

#### Scenario: Nothing outside the output directory is deleted
- **WHEN** a manifest's `superseded` holds `../../victim.mp4`, `a/b.mp4` or `..`, or the year folder of an old
  name is a symbolic link to a directory outside the output directory
- **THEN** nothing is listed or deleted for it, and the outside file is unchanged

#### Scenario: A symbolic link or a folder is not deleted
- **WHEN** the old name is a symbolic link, or a folder
- **THEN** it is not listed and not deleted

#### Scenario: A file that cannot be deleted is reported and the run continues
- **WHEN** `--yes` runs over two superseded movies and deleting the first fails with a permission error
- **THEN** the first is reported with the operating system's reason, the second is deleted, and the command
  exits non-zero

#### Scenario: Unwalkable layout deletes nothing
- **WHEN** the layout walk fails with an operating system error
- **THEN** the command prints the reason, deletes nothing, and exits non-zero

#### Scenario: An old manifest without a list contributes nothing
- **WHEN** an event's manifest has no `superseded` field
- **THEN** nothing is listed for it and no error is reported
