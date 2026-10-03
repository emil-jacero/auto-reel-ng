## Purpose
Describe the proxy cache the engine keeps for each clip (D-21): the entry that holds a clip's playable proxy,
filmstrip and recorded facts, and the read-only classification of that entry that the API and CLI use to say
whether a clip is prepared. This change adds the reading side; `proxy-encode` and `filmstrip-sprites` add the
writing side of the same capability.

## ADDED Requirements

### Requirement: A clip's proxy state is read from its cache entry
The engine SHALL classify a clip's proxy into exactly one of four states by looking only at the cache entry
and the failure marker for the clip's current cache key (the file's name, size and modification time, the
proxy version and the settings, as `proxy-encode` defines the key), without running any process, writing any
file or listing the cache directory:

- `ready`: the entry holds a non-empty proxy video, a non-empty filmstrip image and a recorded-facts file
  whose every required fact is present, of the right type, finite and in range, including the filmstrip's
  recorded geometry for the current filmstrip format, whose image is there with the size recorded. A fact the
  proxy job could not learn and recorded as `null` (the frame-rate variability, the rotation, the audio codec)
  is present. The state carries those facts.
- `failed`: the entry is not `ready` and a failure marker for the key records a cause. The state carries the
  cause as one line with no server path.
- `stale`: the entry is not `ready`, no failure marker exists, and the entry's recorded-facts file exists but
  cannot be used: invalid JSON, not an object, a required fact missing, mistyped, not finite or out of range,
  or the proxy or filmstrip file empty, or a `filmstrip` record that is malformed, of another format version or
  not the size of the image it describes.
- `absent`: anything else, including no entry at all and an entry that is incomplete because a file is not
  there yet (the proxy and its facts exist and the filmstrip is still being made: no `filmstrip` record, or a
  record whose image is not there).

The precedence SHALL be `ready`, then `failed`, then `stale`, then `absent`: a usable entry wins over an
older recorded failure, and a recorded failure wins over an unusable entry. A clip whose file changed since its
proxy was made has a different key and therefore reads `absent`; the reader SHALL NOT look for an entry made
for the previous file or an earlier proxy version. A cache that cannot be read for a reason other than the
entry or the cache directory not existing (permission denied, an I/O error) SHALL raise a typed error that
the caller reports as unknown; it SHALL NOT read as `absent`, and no state SHALL be returned for it.

The facts SHALL be exactly those the proxy job recorded; the reader SHALL NOT probe the proxy, SHALL NOT
default a missing fact, and SHALL NOT repair a damaged one (Principle I). The proxy cache is not an input of
the staleness fingerprint and reading it SHALL NOT change any render verdict.

#### Scenario: A complete entry is ready
- **WHEN** an entry holds a proxy video, a filmstrip image and facts for a 25 s 1080p25 clip
- **THEN** the state is `ready` and carries a duration of 25 s, 25/1 frames per second, the displayed size, the
  rotation, the audio codec and the filmstrip's tile geometry exactly as recorded

#### Scenario: A clip with no entry and no marker is absent
- **WHEN** the cache holds nothing for the clip's key
- **THEN** the state is `absent`, and the cache directory is unchanged

#### Scenario: A proxy awaiting its filmstrip is absent, not stale
- **WHEN** an entry holds a proxy video and recorded facts but no filmstrip image yet
- **THEN** the state is `absent` (nothing is usable yet), not `stale`

#### Scenario: Damaged facts make the entry stale
- **WHEN** an entry's recorded-facts file is truncated, or is valid JSON without `duration`, or records a
  duration of `0`, or a negative width, or a rotation of `360`
- **THEN** the state is `stale` and carries no facts, and nothing is repaired or written

#### Scenario: An empty proxy file makes the entry stale
- **WHEN** an entry's facts are valid but its proxy video is zero bytes
- **THEN** the state is `stale`

#### Scenario: A fact recorded as null is not damage
- **WHEN** a complete entry's facts record `rotation` `null`, `vfr` `null` and `audio_codec` `null`
- **THEN** the state is `ready` and the three facts are `null`, not defaulted

#### Scenario: A filmstrip the record does not describe makes the entry stale
- **WHEN** an entry's `filmstrip` record says the image has 41200 bytes and `filmstrip.jpg` has 7, or is empty,
  or the record is of another format version
- **THEN** the state is `stale`

#### Scenario: A filmstrip record whose image is gone is absent
- **WHEN** an entry's facts record a filmstrip and `filmstrip.jpg` is not there
- **THEN** the state is `absent`, as for a proxy still awaiting its filmstrip

#### Scenario: A recorded failure with nothing usable is failed
- **WHEN** the failure marker for the key records `Output has no audio stream` and no entry exists
- **THEN** the state is `failed` with that cause, and the cause is free of absolute paths

#### Scenario: A later success outranks an earlier failure
- **WHEN** a failure marker exists for the key and a complete entry exists too
- **THEN** the state is `ready`

#### Scenario: A failure outranks an unusable entry
- **WHEN** a failure marker exists for the key and the entry's facts are damaged
- **THEN** the state is `failed`

#### Scenario: A version bump moves every clip to absent
- **WHEN** the proxy version is raised after a clip's entry was made
- **THEN** the clip's key differs, the state is `absent`, and the old entry is neither read nor deleted

#### Scenario: An unreadable cache is an error, not absence
- **WHEN** the entry directory exists but cannot be searched (permission denied)
- **THEN** reading raises the typed cache error and returns no state

#### Scenario: Reading runs no process
- **WHEN** a state is read with every process-starting facility made to raise
- **THEN** the state is returned and nothing was started

### Requirement: A failed proxy attempt is recorded for the clip's key
When an attempt to make a clip's proxy fails because of the clip (its probe, the encode, or its post-encode
verification; not a cache error, a cancel, or the filmstrip step, whose failure `clip-filmstrips` says is not
remembered), the engine SHALL record the cause in a failure marker for the clip's current cache key, written
atomically (a temporary file, then a rename) and best effort: failing to write the marker SHALL NOT replace
the attempt's own error and SHALL log a warning. The recorded cause SHALL be one line and SHALL NOT contain an
absolute file path. A successful attempt SHALL NOT need to remove a marker, because a ready entry outranks it;
a marker belongs to one key, so a changed file or a new proxy version never inherits it. The marker SHALL have
no expiry: it is cleared by success, and a retry (`auto-reel proxies` or a proxy job) always attempts the clip
again regardless of the marker.

#### Scenario: A failed encode leaves a marker and no entry
- **WHEN** preparing a clip fails because the encode exits non-zero
- **THEN** a failure marker for the clip's key holds a one-line cause, no entry directory exists, and no
  `.part` file remains

#### Scenario: A clip that cannot be probed is recorded
- **WHEN** preparing a clip fails because its probe fails
- **THEN** a failure marker for the clip's key holds the cause, and no entry exists

#### Scenario: A retry is not blocked by an earlier marker
- **WHEN** a clip has a failure marker and `auto-reel proxies` runs again on its event
- **THEN** the clip is attempted again, and on success the state reads `ready`

#### Scenario: A marker that cannot be written does not hide the real error
- **WHEN** an attempt fails and the cache directory is read-only
- **THEN** the attempt reports its own failure, a warning names the unwritable cache, and no second error is raised

#### Scenario: The cause carries no server path
- **WHEN** the encoder's message includes `/var/home/emil/library/2020/ev/C0047.MP4`
- **THEN** the recorded cause names the file by its name only
