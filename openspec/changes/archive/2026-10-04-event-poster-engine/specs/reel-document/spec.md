## ADDED Requirements

### Requirement: An event may carry a poster frame

A v0 document MAY carry an optional top-level `poster` mapping choosing the frame that stands for the event's
movie. It has two keys, both required when `poster` is a mapping: `clip`, a clip identity (an event-relative
path, as "Clip identity is the event-relative path"), and `at`, a number of seconds `>= 0` into the ORIGINAL
clip, measured before any trim or cut. An `at` of `0` is valid. A `poster` that is absent or `null` means the
default frame, and an empty mapping is not valid. The loader SHALL fail loud, with the parse error naming
`poster` or `poster.<key>`, on a `poster` that is not a mapping, a missing `clip` or `at`, a `clip` that is not a
non-blank string, an `at` that is not a number (a boolean is not a number), is negative, or is not finite, and on
any other key inside `poster`. It SHALL NOT drop, clamp or correct a value. Whether `clip` names a clip of the
event, and whether `at` lies inside that clip's duration, are NOT checked at load (a load makes no probe); the
render checks them ("A poster frame is written beside the movie").

The document's editorial hash SHALL include `poster` only when the document has one, so that a document without
it hashes exactly as it did before this requirement.

#### Scenario: A poster loads
- **WHEN** a document sets `poster: {clip: 2024/s1710002.mp4, at: 12.5}`
- **THEN** it loads with that clip and that time

#### Scenario: Time zero is valid
- **WHEN** a document sets `poster: {clip: a.mp4, at: 0}`
- **THEN** it loads

#### Scenario: A negative time fails loud
- **WHEN** a document sets `poster: {clip: a.mp4, at: -1}`
- **THEN** loading fails naming `poster.at`

#### Scenario: A missing clip fails loud
- **WHEN** a document sets `poster: {at: 3}`
- **THEN** loading fails naming `poster.clip`

#### Scenario: An unknown key fails loud
- **WHEN** a document sets `poster: {clip: a.mp4, at: 3, label: x}`
- **THEN** loading fails naming `poster.label`

#### Scenario: A clip that is not on disk still loads
- **WHEN** a document sets `poster.clip` to a path no file of the event matches
- **THEN** the document loads

#### Scenario: A document without a poster hashes as before
- **WHEN** a document has no `poster`
- **THEN** its editorial hash equals the one computed before posters existed, and a document that adds a poster has a different hash

### Requirement: The poster is carried by every writer

Every writer of `reel.yaml` SHALL keep the document's `poster`. The round-trip writer SHALL keep a loaded
`poster`, with its comments and key order, byte-stable, and a document built from typed fields SHALL write a
`poster` it has after `look` and before `chapters`. The editorial write operation SHALL treat `poster` in the
desired state as follows: no `poster` key, or `null`, leaves the existing poster exactly as written, comments
included, so a client that does not know posters cannot erase one by omission; an empty mapping removes it; a
mapping with keys is merged into the existing node key by key (a value that is equal stays as written with its
comment, a differing value is replaced). The merged document SHALL be validated before anything is written, so
an invalid poster is refused and the file left untouched, and a save that changes nothing SHALL write nothing.

#### Scenario: A commented poster round-trips byte-stable
- **WHEN** a `reel.yaml` with `poster:` and a comment on its `at` line is loaded and written back unchanged
- **THEN** the output is byte-for-byte the input

#### Scenario: A write that omits the poster keeps it
- **WHEN** an editorial write sends no `poster` for an event whose file has one
- **THEN** the poster's lines are unchanged

#### Scenario: An empty poster removes it
- **WHEN** an editorial write sends `poster: {}`
- **THEN** the persisted document has no `poster` key

#### Scenario: A changed time is merged
- **WHEN** the file has `poster: {clip: a.mp4, at: 3  # intro}` and the desired poster is `{clip: a.mp4, at: 9}`
- **THEN** the persisted poster has `clip: a.mp4` as written and `at: 9`

#### Scenario: An invalid poster is refused and nothing is written
- **WHEN** an editorial write sends `poster: {clip: a.mp4, at: -2}`
- **THEN** the write raises the parse error naming `poster.at`, and the file's bytes and modification time are unchanged
