## ADDED Requirements

### Requirement: Persist detections to a sidecar cache

The system SHALL persist analysis results for a clip to a sidecar under `.auto-reel/cache/` in the
event directory (HLD §4.5), and SHALL retrieve them on a subsequent run instead of re-detecting.
The cache SHALL NOT live in `reel.yaml`.

#### Scenario: Cold run writes the cache

- **WHEN** analysis runs on a clip with no cached entry
- **THEN** detection runs and the resulting segments are written to the `.auto-reel/cache/` sidecar

#### Scenario: Warm run reads the cache

- **WHEN** analysis runs on a clip whose cached entry is still valid
- **THEN** the cached segments are returned and no ffmpeg detection pass is run

### Requirement: Invalidate the cache when the clip changes

Each cache entry SHALL be keyed by the clip identity together with a content-change signal
(file size + modification time, or a content hash). When that signal differs from the cached
value, the entry SHALL be treated as stale and detection SHALL re-run. The key shape SHALL be
chosen to remain compatible with the future render-fingerprint work (§8.14) without attempting to
solve it here.

#### Scenario: Modified clip re-runs detection

- **WHEN** a clip's content-change signal differs from the value stored in its cache entry
- **THEN** the cached entry is ignored, detection re-runs, and the entry is rewritten

#### Scenario: Missing or unreadable cache entry re-runs detection

- **WHEN** no cache entry exists for a clip, or the entry cannot be read or parsed
- **THEN** detection runs as if cold and a fresh entry is written

### Requirement: Analysis is an explicit pass, never auto-run on scan

The analysis pass SHALL be invoked explicitly and SHALL NOT be triggered implicitly by event
scanning (`scan_event`), so that scanning a project stays cheap.

#### Scenario: Scanning does not analyze

- **WHEN** an event directory is scanned
- **THEN** no detection ffmpeg passes are run and no cache entries are written as a side effect
