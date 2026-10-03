## MODIFIED Requirements

### Requirement: `proxies` fills the proxy cache without touching the library

The `proxies` subcommand SHALL walk the project with the resolved layout, like `scan` and `thumbs`. It SHALL honour
`--years`, `--layout` and `.reelignore`. For every clip that discovery lists on disk in each event, it SHALL make
the clip's proxy (capability `clip-proxies`) unless a complete proxy entry is already cached, and, for every clip
whose proxy is ready afterwards, whether it was just generated or was already cached, its filmstrip (capability
`clip-filmstrips`) unless that filmstrip is already recorded. A clip whose proxy failed SHALL get no filmstrip
attempt and SHALL count in neither filmstrip figure. A clip whose proxy was made earlier by a command or a job
that did not make filmstrips SHALL get its filmstrip on the next run without its proxy being encoded again. The
clips it covers:

- root clips and chapter-subfolder clips
- IGNORED clips included
- not the `original/` debris, and not a `.reelignore`d chapter folder, which discovery already excludes

`proxies` SHALL NOT read or write `reel.yaml`, so a MISSING clip, which is not on disk, is never requested. It
SHALL NOT require an event to have a real date or title.

It SHALL select the acceleration profile once, as `render` does: the best usable accelerator, or the one `--device`
names (a vendor, `cpu`, or a device id). An override that cannot be satisfied SHALL stop the run with one error
naming it and a non-zero exit, before any encode. It SHALL run at most `--jobs N` encodes at once. `N` is a positive
integer with a default of `1`, since an encode uses several cores and the library is often on one USB disk; any
other value SHALL be a usage error. It SHALL print, in walk order:

- one line per event, with its generated, cached and failed counts, followed by the filmstrip counts as
  `; filmstrips: <g> generated, <c> cached, <f> failed`, omitting a zero count and the whole part when all three
  are zero. The proxy counts add up to the event's clips, and a proxy entry counts as generated at most once per
  event. The filmstrip counts add up to the event's clips minus its failed proxies. Clips whose proxy is one entry,
  such as several symlinks to one clip in an event, SHALL cause one encode and one filmstrip. The first of them in
  the event's listing order SHALL count as generated, and the others as cached, for the proxy and for the
  filmstrip.
- exactly one `ERROR  <event>/<clip>: <cause>` line per clip that failed, naming the clip once, whether its proxy
  or its filmstrip failed: the cause is one line, does not repeat the clip's path or quote the failing command, and
  a file name that is not valid UTF-8 is printed with its raw bytes escaped; the failing command and its stderr
  are logged at debug level
- a final summary with the totals of the proxies and of the filmstrips, the size of the proxies and of the
  filmstrips it generated, and the cache directory

A clip that fails SHALL NOT stop the run, nor SHALL an event whose folder cannot be listed; that event is reported
as `ERROR  <event>: <reason>`. A filmstrip that fails SHALL NOT change the clip's proxy count: the proxy still
counts as generated or cached. When clips that share one entry fail, each of them SHALL get its own `ERROR` line
and count as failed, and the encode SHALL still have been attempted only once.

The command SHALL exit `0` when nothing failed, and non-zero when any clip, filmstrip or event failed. A cache directory that
cannot be created or written, and an invalid `proxies` setting, SHALL each stop the run. The command SHALL then
print one error naming the directory or the key, and exit non-zero.

`proxies` SHALL write only into the proxy cache directory: no file under the project root is created or modified.
It SHALL therefore work on a library mounted read-only. An interrupted run (Ctrl-C) SHALL start no further encode
or filmstrip, SHALL stop the ffmpeg processes already running, whether they encode a proxy or cut a filmstrip, and
SHALL leave no `.part` directory and no incomplete entry behind, and no filmstrip published after the interrupt;
it exits non-zero.

#### Scenario: Filling the cache for the dev library
- **WHEN** `auto-reel proxies` runs for the first time over the dev library
- **THEN** every other clip on disk has a complete proxy entry and a filmstrip afterwards. A clip symlinked into
  an earlier event, or twice into one event, is counted as cached.
- **AND** exactly one `ERROR` line is printed, for `2024-10-05 - Trasig/trasig.mp4`, whose file is zero bytes
- **AND** the summary counts that clip as a failed proxy and counts no filmstrip for it, and the command exits
  non-zero

#### Scenario: Two links to one clip in one event are encoded once
- **WHEN** `proxies` reaches an event that holds `s1710004.mp4` and `Kvällen/s1710004.mp4`, both symlinks to one
  clip, and neither has a cached proxy
- **THEN** ffmpeg encodes that clip once and cuts its filmstrip once
- **AND** the event's line reads `2 clips, 1 generated, 1 cached; filmstrips: 1 generated, 1 cached`
- **AND** exactly one entry for it exists in the cache directory

#### Scenario: A MISSING clip is never requested
- **WHEN** `proxies` reaches an event whose `reel.yaml` lists `borttagen.mp4  # MISSING` and two clips on disk
- **THEN** proxies exist for the two clips, and nothing is requested and no line is printed for `borttagen.mp4`

#### Scenario: Chapter subfolders and IGNORED clips are covered
- **WHEN** `proxies` reaches an event with root clips, one of them IGNORED in its `reel.yaml`, and `Kvällen/` clips
- **THEN** each of those clips has a proxy, and the event's line counts all of them

#### Scenario: Camera originals are skipped
- **WHEN** an event folder holds `s1710001.mp4` and `original/C0001.MTS`
- **THEN** only `s1710001.mp4` gets a proxy

#### Scenario: An event the render family refuses still gets proxies
- **WHEN** `proxies` reaches `2024-02-30 - Omöjligt datum`, whose folder date is impossible
- **THEN** its clip's proxy is made, and no `ERROR` line is printed for the event

#### Scenario: A second run generates nothing
- **WHEN** `proxies` runs again over the dev library with no clip changed
- **THEN** every clip that succeeded before is counted as cached, for its proxy and for its filmstrip, no ffmpeg
  or ffprobe runs for it, and `2024-10-05 - Trasig/trasig.mp4` is reported as failed again

#### Scenario: The library is left untouched
- **WHEN** `proxies` runs over the dev library
- **THEN** no file under the project root is created or modified, and every `reel.yaml` is byte-for-byte unchanged

#### Scenario: A read-only library
- **WHEN** `proxies` runs over a library whose directories cannot be written, like the MOL drive mounted
  read-only, with the cache directory elsewhere
- **THEN** every readable clip gets its proxy and its filmstrip, and no clip or event fails for lack of write
  access

#### Scenario: A host without a GPU
- **WHEN** `auto-reel proxies <root> --device cpu` runs on any host
- **THEN** every proxy takes the CPU path, and each passes the same verification

#### Scenario: A device that cannot be satisfied stops the run
- **WHEN** `--device nvidia` is given on a host with no NVIDIA device
- **THEN** the command prints one error naming the device, exits non-zero, and runs no ffmpeg

#### Scenario: Ctrl-C stops the run
- **WHEN** the operator presses Ctrl-C while `proxies` is encoding an event with many uncached clips
- **THEN** no clip still waiting is started, the running ffmpeg processes are stopped, no `.part` directory or
  partial entry remains, and the command exits non-zero

#### Scenario: Ctrl-C stops a filmstrip being cut
- **WHEN** the operator presses Ctrl-C while a clip's filmstrip is being cut
- **THEN** that ffmpeg process is stopped, no `filmstrip.jpg` is published for the clip, no `.part` directory
  remains, no `ERROR` line is printed for the clip, and the command exits non-zero

#### Scenario: An unwritable cache directory stops the run
- **WHEN** `config.yaml` sets `proxies: {cache_dir: /read-only/proxies}`, which cannot be created
- **THEN** the command prints one error naming that directory and exits non-zero
- **AND** no per-clip `ERROR` lines are printed

#### Scenario: An invalid setting stops the run before any encode
- **WHEN** `config.yaml` sets `proxies: {cache_dir: proxies}`, a relative path
- **THEN** the command prints a configuration error naming `proxies.cache_dir`, runs no ffmpeg, and exits non-zero

#### Scenario: A non-positive job count is a usage error
- **WHEN** `auto-reel proxies <root> --jobs 0` is run
- **THEN** the command exits non-zero with a usage message and runs no ffmpeg

#### Scenario: Another encode of the same clip is not a failure
- **WHEN** the service finished the proxy of a clip between the CLI's cache check and its own rename
- **THEN** the clip counts as generated or cached, not failed, and no `.part` directory remains

#### Scenario: First run over an event
- **WHEN** `auto-reel proxies` runs for the first time over `2020-07-24 - M-A 80 år - Kungälv` (25 clips,
  one of them 0.48 s)
- **THEN** 25 proxies and 25 filmstrips are generated, the 0.48 s clip's filmstrip has one tile, and the
  event's line reports `25 generated` for proxies and for filmstrips with no failure
- **AND** the command exits `0`

#### Scenario: A proxy without a filmstrip gets one
- **WHEN** an entry holds `proxy.mp4` and `facts.json` with no `filmstrip` member, and `proxies` runs
- **THEN** the proxy is counted as cached, the filmstrip as generated, and `proxy.mp4` is not rewritten

#### Scenario: A filmstrip fails and the run continues
- **WHEN** one clip's filmstrip fails and the other clips of the event succeed
- **THEN** exactly one `ERROR` line names that clip, the event's line counts one filmstrip failed
  (`...; filmstrips: 24 generated, 1 failed`), its proxy is still counted as generated or cached, the next event
  is processed, and the command exits non-zero

#### Scenario: A failed proxy gets no filmstrip attempt
- **WHEN** a clip's proxy cannot be encoded
- **THEN** that clip has a proxy `ERROR` line and no filmstrip line, and the filmstrip counts add up to the
  event's clips minus its failed proxies
