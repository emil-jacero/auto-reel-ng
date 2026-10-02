## ADDED Requirements

### Requirement: A referenced clip missing from disk fails its event by identity
Before it probes any clip, the build path shared by `render` and the worker SHALL check that every clip
the event's `reel.yaml` references and has not excluded is present in the event folder. When one or more are
absent, the event SHALL fail with one error that names every missing clip by its identity (its path
relative to the event folder), in the order `reel.yaml` lists them, and says how to fix it: restore the
file, or remove the clip from the event (in Edit mode or in `reel.yaml`). The error MUST NOT contain an
absolute path of the machine, and MUST NOT stop at the first missing clip. No ffprobe, no ffmpeg process, no
output and no manifest SHALL follow for that event. A clip that is excluded is not checked, and a clip that
is on disk but not listed is not affected. `render` SHALL report the failure as `ERROR <event>: <the error>`
for that event only, continue with the remaining events, and exit non-zero; a worker that claims a job for
such an event SHALL fail the job with the same text as the job error. `scan` keeps reporting the clip as
`MISSING`, and a `MISSING` clip is still never removed from `reel.yaml`.

#### Scenario: One missing clip is named with the fix
- **WHEN** `render` runs over an event whose `reel.yaml` lists `clip1.avi` and `borttagen.mp4`, and
  `borttagen.mp4` is not on disk
- **THEN** the event is reported as `ERROR` naming `borttagen.mp4` as listed in `reel.yaml` but missing and
  telling the user to restore it or remove it from the event, the text has no absolute path, nothing is
  rendered for it, and the command exits non-zero

#### Scenario: Every missing clip is listed at once
- **WHEN** an event lists `a.mp4`, `b.mp4`, `Dag 2/c.mp4` and `d.mp4`, and `b.mp4` and `Dag 2/c.mp4` are
  absent
- **THEN** one error names `b.mp4` and `Dag 2/c.mp4`, in that order, and not `a.mp4` or `d.mp4`

#### Scenario: An excluded missing clip is not an error
- **WHEN** a clip that `reel.yaml` marks `exclude: true` is absent from disk and every other clip is present
- **THEN** the event renders normally

#### Scenario: The job error is the same text
- **WHEN** a worker claims a job for the event with the missing `borttagen.mp4`
- **THEN** the job is `failed` and its error equals the text `render` printed for that event, with no
  `File does not exist` and no absolute path

#### Scenario: Other events in the batch still render
- **WHEN** `render` runs over three events and only one has a missing clip
- **THEN** the other two render, and the exit code reflects the one failure

#### Scenario: A broken symlink counts as missing
- **WHEN** a listed clip is a symlink whose target no longer exists
- **THEN** it is reported as missing with the others, not as a probe failure
