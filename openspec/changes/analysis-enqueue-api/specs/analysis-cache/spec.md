## ADDED Requirements

### Requirement: A clip's analysis state is read from the disk without decoding
The system SHALL derive each clip's analysis state from the clip's current content-change signal (size and
modification time, from a `stat`), its sidecar cache entry and the failure the analysis job recorded for it, reading
nothing but directory entries and the sidecar's JSON: no ffmpeg or ffprobe process, no decode, no write. For the clip
as it is now, the state SHALL be, by the first rule that holds:

- `current` when its cache entry is valid for the current signal;
- `failed` when a failure is recorded for the current signal;
- `stale` when an entry or a recorded failure exists for another signal, or an entry file exists that cannot be
  parsed or is of another entry version;
- `never` when neither an entry file nor a recorded failure exists.

An entry or failure record that exists but cannot be read (any error other than its absence, such as permission
denied), or a clip that cannot be statted, SHALL raise a typed error and SHALL NOT be reported as any state
(Principle I). The clips considered SHALL be every clip file the event's folder lists (ignored and excluded clips
included, as the analysis job walks them); `reel.yaml` is not read.

An event SHALL need analysis when at least one of its clips reads `never` or `stale`; a clip that reads `failed`
does not make the event need analysis until the clip changes or a forced job runs. The event's disk state SHALL be,
by the first rule that holds: `current` when it has no clips or every clip is `current`; `never` when every clip is
`never`; `stale` when any clip is `never` or `stale`; otherwise `failed`. This one rule SHALL decide which events the
service's analysis enqueues treat as fresh, and SHALL be the engine function any other selection of events to
analyze (the worker's automatic sweep) uses.

#### Scenario: A clip analyzed as it is now is current
- **WHEN** `2023/2023-06-23 - Midsommar - Dalarna/C0001.MP4` has an entry written for its current size and mtime
- **THEN** its state is `current`, and no process was started to tell

#### Scenario: A replaced clip is stale
- **WHEN** the clip is replaced by a re-exported file of another size after its entry was written
- **THEN** its state is `stale`, and the event needs analysis

#### Scenario: A clip that failed stays failed until it changes
- **WHEN** the analysis job recorded a failure for `2024/Blandat/broken.mp4` under its current signal and its other
  clips are `current`
- **THEN** the clip reads `failed`, the event's state is `failed`, and the event does not need analysis
- **AND** once `broken.mp4` is replaced by another file, it reads `stale` and the event needs analysis

#### Scenario: A corrupt entry is stale, an unreadable one is an error
- **WHEN** a clip's entry file holds truncated JSON
- **THEN** the clip reads `stale`
- **AND** when the entry file instead cannot be opened (permission denied), reading the state raises and no state is
  reported for the event

#### Scenario: A partly analyzed event is stale
- **WHEN** an event has two `current` clips and a newly added clip that reads `never`
- **THEN** the event's state is `stale` and it needs analysis

#### Scenario: An event with no clips needs nothing
- **WHEN** an event folder holds no clip files
- **THEN** its state is `current` and it does not need analysis
