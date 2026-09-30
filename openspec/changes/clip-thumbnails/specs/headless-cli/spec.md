## MODIFIED Requirements

### Requirement: `auto-reel` entry point with subcommands

The system SHALL install a `console_scripts` entry point named `auto-reel` exposing the
subcommands `render`, `scan` (alias `list`), `analyze`, `import`, `enqueue`, `worker`, `jobs`, `serve`,
`adopt-renders`, and `thumbs`. Invalid arguments or an unknown subcommand SHALL produce a non-zero exit and
a usage message.

#### Scenario: Entry point is installed

- **WHEN** the package is installed and `auto-reel --help` is run
- **THEN** the ten subcommands are listed and the command exits zero

#### Scenario: Unknown subcommand fails

- **WHEN** `auto-reel frobnicate` is run
- **THEN** the command exits non-zero with a usage message

## ADDED Requirements

### Requirement: `thumbs` fills the thumbnail cache without touching the library

The `thumbs` subcommand SHALL walk the project with the resolved layout, like `scan`. It SHALL honour
`--years`, `--layout` and `.reelignore`. For every clip that discovery lists on disk in each event, it
SHALL generate the clip's thumbnail (capability `clip-thumbnails`) unless that thumbnail is already cached.
The clips it covers:

- root clips and chapter-subfolder clips
- IGNORED clips included
- not the `original/` debris, and not a `.reelignore`d chapter folder, which discovery already excludes

`thumbs` SHALL NOT read or write `reel.yaml`, so a MISSING clip, which is not on disk, is never requested.
It SHALL NOT require an event to have a real date or title.

It SHALL run at most `--jobs N` extractions at once. `N` is a positive integer with a default of `2`; any
other value SHALL be a usage error. It SHALL print, in walk order:

- one line per event, with its generated, cached and failed counts
- one `ERROR  <event>/<clip>: <reason>` line per clip that failed, naming the clip once: the reason does
  not repeat its path
- a final summary with the totals and the cache directory

A clip that fails SHALL NOT stop the run. Nor SHALL an event whose folder cannot be listed; that event is
reported as `ERROR  <event>: <reason>`.

The command SHALL exit `0` when nothing failed, and non-zero when any clip or event failed. A cache
directory that cannot be created or written, and an invalid `thumbnails` setting, SHALL each stop the run.
The command SHALL then print one error naming the directory or the key, and exit non-zero.

`thumbs` SHALL write only into the thumbnail cache directory: no file under the project root is created or
modified. It SHALL therefore work on a library mounted read-only. An interrupted run (Ctrl-C) SHALL start
no further extraction and SHALL leave no partial thumbnail behind.

#### Scenario: Filling the cache for the dev library
- **WHEN** `auto-reel thumbs` runs for the first time over the dev library
- **THEN** every other clip on disk has a thumbnail afterwards. A clip symlinked into an earlier event may
  be counted as cached.
- **AND** exactly one `ERROR` line is printed, for `2024-10-05 - Trasig/trasig.mp4`, whose file is zero
  bytes
- **AND** the summary counts that clip as failed, and the command exits non-zero

#### Scenario: A MISSING clip is never requested
- **WHEN** `thumbs` reaches `2024-09-01 - Sommarlov`, whose `reel.yaml` lists `s1710002.mp4`, `s1710004.mp4`
  and `borttagen.mp4  # MISSING`, and only the first two are on disk
- **THEN** thumbnails exist for `s1710002.mp4` and `s1710004.mp4`
- **AND** nothing is requested and no line is printed for `borttagen.mp4`

#### Scenario: Chapter subfolders and IGNORED clips are covered
- **WHEN** `thumbs` reaches `2024-08-20 - Två kapitel - Tjörn`, which holds the root clips `s1710001.mp4` and
  `s1710004.mp4` (IGNORED in its `reel.yaml`) and the `Kvällen/` clips `s1710002.mp4`, `s1710003.mp4` and
  `s1710004.mp4`
- **THEN** each of those five clips has a thumbnail, and the event's line counts five clips

#### Scenario: Camera originals are skipped
- **WHEN** an event folder holds `s1710001.mp4` and `original/C0001.MTS`
- **THEN** only `s1710001.mp4` gets a thumbnail

#### Scenario: An event the render family refuses still gets thumbnails
- **WHEN** `thumbs` reaches `2024-02-30 - Omöjligt datum`, whose folder date is impossible
- **THEN** its clip's thumbnail is generated, and no `ERROR` line is printed for the event

#### Scenario: A second run generates nothing
- **WHEN** `thumbs` runs again over the dev library with no clip changed
- **THEN** every clip that succeeded before is counted as cached, no thumbnail is generated, and
  `2024-10-05 - Trasig/trasig.mp4` is reported as failed again

#### Scenario: The library is left untouched
- **WHEN** `thumbs` runs over the dev library
- **THEN** no file under the project root is created or modified, and every `reel.yaml` is byte-for-byte
  unchanged

#### Scenario: A read-only library
- **WHEN** `thumbs` runs over a library whose directories cannot be written, like the MOL drive mounted
  read-only, with the cache directory elsewhere
- **THEN** every readable clip gets its thumbnail, and no clip or event fails for lack of write access

#### Scenario: Ctrl-C stops the run
- **WHEN** the operator presses Ctrl-C while `thumbs` is extracting an event with many uncached clips
- **THEN** no clip still waiting in the queue is started, no temporary file or partial `<key>.jpg` remains,
  and the command exits non-zero

#### Scenario: An unwritable cache directory stops the run
- **WHEN** `config.yaml` sets `thumbnails: {cache_dir: /read-only/thumbs}`, which cannot be created
- **THEN** the command prints one error naming that directory and exits non-zero
- **AND** no per-clip `ERROR` lines are printed

#### Scenario: An invalid setting stops the run before any extraction
- **WHEN** `config.yaml` sets `thumbnails: {position: 1.5}`
- **THEN** the command prints a configuration error naming `thumbnails.position`, runs no ffmpeg, and exits
  non-zero

#### Scenario: A non-positive job count is a usage error
- **WHEN** `auto-reel thumbs <root> --jobs 0` is run
- **THEN** the command exits non-zero with a usage message and runs no ffmpeg
