## Purpose

Prepare clips for browser playback and timeline editing: a 540p proxy, its filmstrip and the facts about the
clip, kept in a cache outside the library and made by the CLI or by a worker job.

## ADDED Requirements

### Requirement: A clip's proxy and filmstrip are prepared as one operation that reports progress and can be canceled
Preparing a clip SHALL be one operation that makes the clip's proxy (when its entry is not complete) and then its
filmstrip (when none is recorded), for a caller that wants both: the worker's proxy job. It SHALL accept an optional
progress callback and an optional cancel check, and return the clip's entry and its filmstrip. The callback SHALL
receive the fraction of that one clip done, non-decreasing, and SHALL receive `1.0` only when the proxy and the
filmstrip are both complete; a clip whose proxy and filmstrip are already complete SHALL report `1.0` without
starting a process. The cancel check SHALL be passed to every ffmpeg run of the operation and SHALL be checked
between the proxy and the filmstrip; when it reports true the running process SHALL be terminated and the
cancellation error of the engine, distinct from a failure of the clip, SHALL be raised, with no temporary file left
in the cache. A failure of the proxy SHALL skip the filmstrip; a failure of the filmstrip SHALL leave the finished
proxy in the cache and be raised as the filmstrip's own error. Without a callback or a check the behaviour is that
of the two calls made one after the other.

#### Scenario: Progress rises to one after the filmstrip
- **WHEN** a clip with no entry is prepared with a progress callback
- **THEN** the callback receives increasing fractions below `1.0` while the proxy is encoded and while the
  filmstrip is cut, and `1.0` only after `filmstrip.jpg` is recorded

#### Scenario: A complete entry reports one at once
- **WHEN** a clip whose proxy and filmstrip are complete is prepared with a progress callback
- **THEN** `1.0` is received, and no ffmpeg or ffprobe process starts

#### Scenario: A proxy without a filmstrip only cuts the filmstrip
- **WHEN** a clip has a complete proxy and no recorded filmstrip, and is prepared
- **THEN** the proxy is not encoded again, the filmstrip is cut, and `1.0` is received after it

#### Scenario: Cancel terminates the encode and leaves nothing
- **WHEN** the cancel check turns true while a long clip is encoding
- **THEN** the ffmpeg process ends within about two seconds, the cancellation error is raised rather than a
  failure, and the cache directory holds exactly the files it held before

#### Scenario: Cancel between the proxy and the filmstrip
- **WHEN** the cancel check turns true after the proxy was published and before the filmstrip starts
- **THEN** the cancellation error is raised, no filmstrip process starts, and the finished proxy stays

#### Scenario: A failed proxy gets no filmstrip attempt
- **WHEN** the proxy of a clip cannot be made
- **THEN** the proxy's error is raised and no filmstrip process starts
