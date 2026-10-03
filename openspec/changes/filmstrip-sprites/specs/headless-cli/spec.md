## ADDED Requirements

### Requirement: `proxies` also makes each clip's filmstrip

For every clip whose proxy is ready after the `proxies` subcommand handles it, whether it was just generated
or was already cached, the command SHALL make the clip's filmstrip (capability `clip-filmstrips`) unless that
filmstrip is already recorded. A clip whose proxy failed SHALL get no filmstrip attempt and SHALL count in
neither filmstrip figure. The command SHALL honour `--years`, `--layout`, `--device` and `.reelignore` and
SHALL write only into the proxy cache, exactly as for proxies, so it works on a library mounted read-only.

Each event's line SHALL carry the filmstrip counts beside the proxy counts: `filmstrips: <g> generated,
<c> cached, <f> failed`, omitting a zero count as the thumbnail line does. A clip whose filmstrip failed
SHALL get exactly one `ERROR  <event>/<clip>: <cause>` line, the cause cut to one line like a proxy's. The
final summary SHALL carry the totals. A filmstrip that failed SHALL NOT stop the run, and SHALL NOT change
the clip's proxy count: the proxy still counts as generated or cached. The command SHALL exit `0` when no
proxy and no filmstrip failed, and non-zero otherwise.

A second run SHALL generate no filmstrip for a clip whose filmstrip succeeded before. A clip whose proxy was
made earlier by a command or a job that did not make filmstrips SHALL get its filmstrip on the next run
without its proxy being encoded again.

#### Scenario: First run over an event
- **WHEN** `auto-reel proxies` runs for the first time over `2020-07-24 - M-A 80 år - Kungälv` (25 clips,
  one of them 0.48 s)
- **THEN** 25 proxies and 25 filmstrips are generated, the 0.48 s clip's filmstrip has one tile, and the
  event's line reports `25 generated` for proxies and for filmstrips with no failure
- **AND** the command exits `0`

#### Scenario: A second run generates nothing
- **WHEN** `proxies` runs again over the same library with no clip changed
- **THEN** every proxy and every filmstrip is counted as cached, and neither ffmpeg nor ffprobe runs for
  them

#### Scenario: A proxy without a filmstrip gets one
- **WHEN** an entry holds `proxy.mp4` and `facts.json` with no `filmstrip` member, and `proxies` runs
- **THEN** the proxy is counted as cached, the filmstrip as generated, and `proxy.mp4` is not rewritten

#### Scenario: A filmstrip fails and the run continues
- **WHEN** one clip's filmstrip fails and the other clips of the event succeed
- **THEN** exactly one `ERROR` line names that clip, the event's line counts one filmstrip failed, its proxy
  is still counted as generated or cached, the next event is processed, and the command exits non-zero

#### Scenario: A failed proxy gets no filmstrip attempt
- **WHEN** a clip's proxy cannot be encoded
- **THEN** that clip has a proxy `ERROR` line and no filmstrip line, and the filmstrip counts add up to the
  event's clips minus its failed proxies

#### Scenario: A read-only library
- **WHEN** `proxies` runs over a library mounted read-only with the cache directory elsewhere
- **THEN** every readable clip gets its proxy and filmstrip, and no file under the project root is created
  or modified
