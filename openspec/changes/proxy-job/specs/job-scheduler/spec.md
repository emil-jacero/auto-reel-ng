## ADDED Requirements

### Requirement: A proxy job prepares every clip of its event
A worker that claims a job of kind `proxy` SHALL prepare the proxy and then the filmstrip of every clip that
discovery lists in the job's event folder, in listing order, using the proxy cache settings of the job's own
project. The clips are the ones on disk, as for `thumbs`: IGNORED clips are included, the event's `reel.yaml`
is neither read nor written, and a clip that `reel.yaml` lists but the disk lacks is never requested. Clips that
resolve to one cache entry (symlinks to one file) SHALL be prepared once. A clip whose entry is already complete
SHALL cost no ffmpeg or ffprobe process. A clip of under one second is prepared like any other (the filmstrip rule
gives it a one-tile sprite). The job SHALL end `done` when every clip is prepared, and `failed` otherwise
("A clip that fails does not stop the others").

#### Scenario: Every listed clip is prepared in order
- **WHEN** a `proxy` job is claimed for an event whose folder lists `a.mp4`, `b.mp4` and `ch/c.mp4`, none cached
- **THEN** the proxy and the filmstrip of `a.mp4`, then `b.mp4`, then `ch/c.mp4` are made in the project's
  proxy cache and the job ends `done`

#### Scenario: Editorial state does not choose the clips
- **WHEN** the event's `reel.yaml` lists only `a.mp4`, marks `b.mp4` as ignored, and lists `gone.mp4` that is
  not on disk, and a `proxy` job runs
- **THEN** `a.mp4` and `b.mp4` are prepared, `gone.mp4` is never requested, and `reel.yaml` is byte-for-byte
  unchanged

#### Scenario: A fully cached event completes without work
- **WHEN** a `proxy` job is claimed for an event whose clips all have complete entries
- **THEN** no ffmpeg or ffprobe process starts, the job's progress is `1.0` and it ends `done`

#### Scenario: Linked clips are prepared once
- **WHEN** two files of the event are symlinks to one clip
- **THEN** one entry is made, and both are counted as prepared

#### Scenario: A sub-second clip is prepared
- **WHEN** an event's only clip is shorter than one second
- **THEN** its proxy and its one-tile filmstrip exist and the job ends `done`

### Requirement: A proxy job touches nothing but the proxy cache
A `proxy` job SHALL write only into the proxy cache directory: not `reel.yaml`, not a clip, not the output
directory, not a render manifest, and no file under the project root. It SHALL NOT apply the render-only claim
checks (the output-collision recheck, the running-output refusal, the claimed-movie refusal, the claim-time
staleness recheck, and the stall rule of segment encodes), because it writes none of the paths they protect. It
SHALL NOT record a fingerprint, and finishing it SHALL NOT change any event's staleness verdict. A render job
and a proxy job for one event MAY run at the same time.

#### Scenario: A colliding or stale event still gets proxies
- **WHEN** a `proxy` job is claimed for an event whose output path another event also claims, and another
  event is stale and a third is fresh
- **THEN** each job prepares its clips and ends `done`; none is failed for a collision or completed early as fresh

#### Scenario: The library is not written
- **WHEN** a `proxy` job runs against a read-only library
- **THEN** it succeeds and no file under the project root is created, changed or removed

#### Scenario: Preparing proxies does not make an event stale
- **WHEN** an event is fresh and a `proxy` job for it ends `done`
- **THEN** the event's staleness verdict is still fresh, and its render manifest is unchanged

#### Scenario: A render and a proxy job of one event coexist
- **WHEN** a `render` job for `2024/Midsommar` is running and a `proxy` job for the same event is enqueued
- **THEN** the proxy job is accepted and claimed, and both end `done` without either blocking the other

### Requirement: A proxy job's settings come from its own project
A `proxy` job SHALL resolve the proxy cache directory and encoding settings from the `config.yaml` of the job's
recorded project root, not from the project the worker was started near. A project configuration that does not
load, or a cache directory the settings refuse (for example one inside the library), SHALL fail the job before any
ffmpeg process starts, with the settings' own message, and the worker SHALL continue with other jobs.

#### Scenario: Two projects, two caches
- **WHEN** two `proxy` jobs of different projects run, and the projects name different `proxies.cache_dir` values
- **THEN** each project's clips are prepared in its own cache directory

#### Scenario: A refused cache directory fails the job
- **WHEN** a `proxy` job is claimed for a project whose `proxies.cache_dir` is inside its library
- **THEN** the job ends `failed` with the refusal's message and no ffmpeg process starts

### Requirement: A clip that fails does not stop the others
When preparing one clip of a `proxy` job fails, the worker SHALL record the clip and its one-line cause, and
SHALL go on to the event's remaining clips. After the last clip the job SHALL end `failed` when any clip failed,
with an error that states how many of how many clips failed and names the failed clips and their causes (a long list
MAY be shortened to its first clips and a count); clips prepared before and after the failure SHALL stay in the
cache. A fault of the cache itself (the directory cannot be created, read or written, or the disk is full) is not a
clip's failure: it SHALL end the job at once as `failed` with that cause. A failure SHALL NOT stop the worker or
affect other jobs, and no entry of a failed clip SHALL exist half written. Nothing is invented for a failed clip.

#### Scenario: One bad clip among three
- **WHEN** the second of three clips cannot be encoded
- **THEN** the first and third are prepared, the job ends `failed` with an error of the form
  "1 of 3 clips failed: <clip>: <cause>", and the second clip has no cache entry

#### Scenario: A re-enqueue redoes only the failure
- **WHEN** the failed clip is fixed and a new `proxy` job is enqueued for the event
- **THEN** only that clip is encoded; the other two cost no ffmpeg process, and the job ends `done`

#### Scenario: A full cache ends the job at once
- **WHEN** the cache disk is full while the first of three clips is written
- **THEN** the job ends `failed` naming the cache fault, the second and third clips are not attempted, and the
  job's capacity token is released

#### Scenario: An unexpected error is still a failure
- **WHEN** preparing a clip raises an error that is not one of the engine's typed errors
- **THEN** the job ends `failed` with the error's type and message, its token is released, and the worker keeps
  claiming

### Requirement: Proxy job progress is weighted by source size and never decreases
A `proxy` job's `progress` SHALL be the share of the event's clip bytes already prepared: each clip weighs its
source file size (a file of size zero weighs one byte), a finished clip counts fully (a cached one too), and the
clip in flight counts its own progress fraction. The proxy and filmstrip of one clip together make that clip's
fraction. The value SHALL be written through the same throttle as a render's, SHALL NOT decrease while the job
runs, SHALL stay below `1.0` until the last clip is finished, and SHALL reach `1.0` no later than the transition
to `done`. Computing it SHALL NOT require a probe.

#### Scenario: Progress is weighted by size
- **WHEN** an event holds a 900 MB clip and a 100 MB clip, in that order, and the first has finished
- **THEN** the stored progress is about `0.9`, not `0.5`

#### Scenario: Progress moves inside a clip
- **WHEN** a clip is half encoded and it is the only clip
- **THEN** the stored progress rises toward `0.5` before the clip finishes

#### Scenario: Cached clips advance the bar without going back
- **WHEN** the first and third of three equal clips are cached and the second is encoded
- **THEN** the progress never decreases and ends at `1.0`

#### Scenario: Done means one
- **WHEN** a `proxy` job ends `done`
- **THEN** its stored progress is `1.0`

### Requirement: A proxy job holds one CPU token and only `worker.proxy_slots` run at once
A `proxy` job SHALL hold exactly one token of the CPU pool for its full duration and no GPU token, so a
GPU-classified render runs beside it. At most `worker.proxy_slots` proxy jobs SHALL be in flight in one worker; the
setting defaults to `1`, layers over the built-in default like the other `worker.*` keys, and a value that is not an
integer of at least one fails loud naming `worker.proxy_slots`. The token is released on every outcome (`done`,
`failed`, `canceled`, requeued).

#### Scenario: One proxy job at a time by default
- **WHEN** two `proxy` jobs are queued and the worker uses the default `proxy_slots`
- **THEN** the second is not claimed until the first has ended

#### Scenario: A GPU render runs beside a proxy job
- **WHEN** a `proxy` job is running and a GPU-classified `render` job is claimed
- **THEN** the render starts without waiting for the proxy job

#### Scenario: The token is released on failure
- **WHEN** a `proxy` job fails, and a CPU-classified job is queued behind it
- **THEN** the next job starts at once

#### Scenario: A bad `proxy_slots` fails loud
- **WHEN** `config.yaml` sets `worker: {proxy_slots: 0}` or `worker: {proxy_slots: "two"}`
- **THEN** the worker refuses to start with an error naming `worker.proxy_slots`

### Requirement: A queued render is claimed before any proxy job
A worker SHALL claim a queued `render` job before any queued `proxy` job, whichever is older and whatever their
`priority`, and SHALL claim a `proxy` job only while fewer than `worker.proxy_slots` proxy jobs are in flight. A
queued proxy job SHALL NOT use up the in-flight capacity that a queued render needs to be claimed. Among jobs of one
kind the order is unchanged (`priority` descending, then oldest first). A running proxy job is never interrupted
for a render.

#### Scenario: A newer render is claimed first
- **WHEN** a `proxy` job was queued an hour ago and a `render` job was queued a minute ago
- **THEN** the next claim is the `render` job, then the `proxy` job

#### Scenario: A waiting proxy job does not block a render
- **WHEN** a `proxy` job is running, a second `proxy` job is queued, and a `render` job is then queued
- **THEN** the second proxy job stays `queued` and the `render` job is claimed

#### Scenario: Order within a kind is unchanged
- **WHEN** three `proxy` jobs are queued at the same priority
- **THEN** they are claimed oldest first, one at a time

#### Scenario: A running proxy job is not preempted
- **WHEN** a `render` job is queued while a `proxy` job is running
- **THEN** the proxy job keeps running to its end

### Requirement: Cancelling a proxy job stops its encode and leaves the cache clean
The worker SHALL check a `proxy` job's `cancel_requested` flag between clips and about once a second while a clip
is being encoded. When it is set the worker SHALL stop the preparation, by terminating the running ffmpeg process if a
clip is in progress, and transition the job `running → canceled`. No temporary or `.part` file of the job SHALL
remain in the proxy cache, no incomplete entry SHALL exist, and entries of clips finished before the cancel SHALL
stay. A cancellation SHALL NOT be recorded as a failed clip.

#### Scenario: Cancel inside a clip's encode
- **WHEN** `cancel_requested` is set while the second of three long clips is encoding
- **THEN** within about two seconds that ffmpeg process is gone, the job ends `canceled`, the third clip is not
  started, the first clip's entry remains, and the cache holds no `.part` or temporary file

#### Scenario: Cancel between clips
- **WHEN** `cancel_requested` is set while the worker moves from one clip to the next
- **THEN** the next clip is not started and the job ends `canceled`

#### Scenario: A canceled job can be enqueued again
- **WHEN** a canceled `proxy` job's event is enqueued again
- **THEN** a new job is created and prepares only the clips without an entry

### Requirement: A proxy job survives a restart
A graceful shutdown (SIGINT or SIGTERM) SHALL requeue an in-flight `proxy` job like any job, stop its ffmpeg process,
and leave no `.part` file of it in the proxy cache. Startup reconciliation SHALL requeue a `proxy` job orphaned by a
crash like any `running` job. A requeued `proxy` job SHALL, when claimed again, cost no ffmpeg process for any clip
that was finished before. A temporary file left by a killed process SHALL NOT make the re-run fail or yield an
incomplete entry.

#### Scenario: SIGTERM requeues a proxy job
- **WHEN** the worker receives SIGTERM while a `proxy` job encodes its second clip
- **THEN** the job returns to `queued` before the process exits and the cache holds no `.part` file of it

#### Scenario: A crash is recovered
- **WHEN** a worker is killed while a `proxy` job runs, and a new worker starts
- **THEN** the job is requeued and claimed, the first clip (finished earlier) costs no ffmpeg process, the
  clip that was in flight is encoded again, and the job ends `done`

#### Scenario: A leftover temporary file is harmless
- **WHEN** the cache holds a stale temporary file of a clip a killed process was writing
- **THEN** a later `proxy` job for the event prepares that clip normally and ends `done`
