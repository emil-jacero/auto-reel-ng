# analysis-cache Specification

## Purpose

Persist clip analysis results to a sidecar cache under `.auto-reel/cache/` so repeat runs reuse detections instead of re-running ffmpeg, keyed by clip identity plus a content-change signal so the cache invalidates when a clip changes (with a key shape compatible with future render-fingerprint work). Analysis remains an explicit pass that is never triggered implicitly by event scanning, keeping scans cheap.

## Requirements

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

The analysis pass SHALL run only as `auto-reel analyze` or as an `analysis` job (enqueued by a user, the CLI, the
API, or the worker's automatic analysis sweep). It SHALL NOT be triggered implicitly by event scanning
(`scan_event`), by `auto-reel scan`, or by any API read (the event list, the event detail, the analysis read), so
that scanning a project and reading it stay cheap. Deciding whether a clip needs analysis SHALL itself be cheap: it
uses the clip's `stat` signal and its sidecar entry only, never ffprobe, ffmpeg or a content hash.

#### Scenario: Scanning does not analyze

- **WHEN** an event directory is scanned
- **THEN** no detection ffmpeg passes are run and no cache entries are written as a side effect

#### Scenario: Reading analysis does not analyze

- **WHEN** the API reads an event's analysis while some of its clips have no entry
- **THEN** no ffmpeg or ffprobe process starts and no cache entry is written

#### Scenario: A job may run the pass

- **WHEN** an `analysis` job for an event, enqueued by any of its submitters, is claimed by the worker
- **THEN** the pass runs for the event's clips that need it and their entries are written

### Requirement: A clip's cache entry is current, a failure marker, or missing

For a clip and its current content-change signal, the sidecar SHALL be in exactly one of three states:

- **current**: an entry of this format version for that signal, holding the clip's segments (possibly none);
- **failed**: a **failure marker** for that signal: the entry's file, keyed like an entry by the clip identity and
  signal, carrying a one-line cause and no segments;
- **missing**: anything else: no file, an unreadable or unparseable file, another format version, or an entry or
  marker for a different signal (the clip changed since).

A failure marker SHALL NOT be an analysis result: every reader of results SHALL treat a `failed` clip as having no
entry. A clip that is `failed` SHALL NOT be analyzed again by a non-forced run; it is analyzed again when its signal
changes (it becomes `missing`) or by a forced run, and a success SHALL replace the marker with an entry. A clip
that needs analysis is exactly a `missing` one; the `analysis` job and the worker's automatic sweep SHALL decide it
by the same function.

#### Scenario: A marker is readable but not a result

- **WHEN** a clip's analysis failed and its marker was written, and the clip is unchanged
- **THEN** the clip's state is `failed` with the recorded cause, the results read for it is none, and it is not
  among the clips that need analysis

#### Scenario: A changed clip makes its marker irrelevant

- **WHEN** a clip with a failure marker is replaced (its size or modification time changes)
- **THEN** the clip's state is `missing` and it is among the clips that need analysis

#### Scenario: Stale and new clips need analysis, current ones do not

- **WHEN** an event holds a clip with a current entry, a clip whose entry was written for an earlier signal, and a
  clip with no entry
- **THEN** exactly the second and third need analysis, decided without ffprobe, ffmpeg or reading clip contents

### Requirement: Sidecar entries are written atomically

Every write of an entry or a failure marker SHALL be atomic: the content is written to a temporary file in the same
cache directory, flushed, and renamed over the entry, so a concurrent reader sees the previous entry or the complete
new one, never a partial one. A temporary file a killed writer left behind SHALL NOT be read as an entry and SHALL
NOT make a later run fail; a failed write SHALL remove its temporary file.

#### Scenario: A concurrent reader never sees half an entry

- **WHEN** a clip's entry is rewritten while another process reads it
- **THEN** the reader gets the previous segments or the new ones, never a parse error or a truncated list

#### Scenario: A leftover temporary file is ignored

- **WHEN** the cache directory holds a temporary file from a killed writer
- **THEN** reads ignore it and a later analysis of the clip writes its entry normally
