## ADDED Requirements

### Requirement: The event reads report excluded clips and the missing clips that block a render

`reel.yaml` can exclude a clip it lists (`clips.<identity>.exclude: true`): the clip stays in the document and
on disk, and a render drops it from the movie without probing it. The events reads SHALL carry that fact, and
the consequence for missing clips, so a client does not have to guess which of them matter.

**Detail.** Each clip in `GET /api/v1/events/{event_id}` SHALL carry `excluded`, a boolean that is true when
the document's `clips` map marks that identity `exclude: true`. It is false for every other clip, including a
NEW or an IGNORED clip (the document cannot hold properties for a clip no chapter lists) and every clip of an
event without a `reel.yaml`. `excluded` is a flag beside the clip's status, not a member of it: the closed
status vocabulary is unchanged, and an excluded clip reports its own status, so an excluded clip whose file is
gone reports `missing` and `excluded: true`.

The detail SHALL also carry `blocking_missing`, the identities of the clips that the document lists, that are
absent from disk and that it does not exclude, in the order of `missing`. A render fails on such a clip, so
this is the set that holds a render back. `missing` SHALL keep listing every missing clip, excluded or not, so
a client can still report all of them.

**List.** Each event in `GET /api/v1/events` SHALL carry, besides the counts it has:

- `clip_count`: the number of clips the event lists that are not ignored, which is every ACTIVE, NEW and
  MISSING clip. It is the number the event's detail page counts, so a list row and its page agree.
- `ignored_count`: the number of IGNORED clips, which `clip_count` does not include.
- `blocking_missing_count`: the number of clips in the detail's `blocking_missing`.

`missing_count` SHALL keep counting every missing clip, excluded or not.

These are read-model fields only. They are derived from disk and the document on each request, nothing is
probed, written or stored, and the staleness verdict is unchanged: `exclude` is already part of the document's
editorial hash, and a missing clip adds nothing to the clip-set component, which covers the clips on disk.

#### Scenario: An excluded clip is flagged
- **WHEN** an event's `reel.yaml` lists `a.mp4`, `b.mp4` and `c.mp4` in one chapter and excludes `b.mp4`, and
  all three are on disk
- **THEN** the detail lists the three with `excluded` false, true and false, and `status` `active` for each

#### Scenario: A NEW, an IGNORED and an undocumented clip are not excluded
- **WHEN** an event holds a NEW clip, an IGNORED clip, and (in another event) no `reel.yaml` at all
- **THEN** every one of those clips reports `excluded: false`

#### Scenario: An excluded missing clip does not block
- **WHEN** an event's `reel.yaml` lists the absent `gone.mp4`, excludes it, and lists nothing else absent
- **THEN** the detail reports `missing` as `["gone.mp4"]`, `blocking_missing` as `[]`, and the clip as status
  `missing` with `excluded: true`

#### Scenario: Only the non-excluded missing clip blocks
- **WHEN** the same event also lists the absent `gone2.mp4`, which it does not exclude
- **THEN** `missing` is `["gone.mp4", "gone2.mp4"]` and `blocking_missing` is `["gone2.mp4"]`

#### Scenario: The list agrees with the detail on how many clips there are
- **WHEN** an event holds `00400.mp4` and `00401.mp4`, which `reel.yaml` lists, and `00402.mp4`, which it
  ignores
- **THEN** the list row reports `clip_count` 2 and `ignored_count` 1, and the detail lists three clips of which
  two are not ignored

#### Scenario: The list counts blocking missing clips apart
- **WHEN** an event lists one excluded absent clip and one non-excluded absent clip
- **THEN** its list row reports `missing_count` 2 and `blocking_missing_count` 1

#### Scenario: Reading the flags writes and probes nothing
- **WHEN** an event with an excluded clip is read through the list and the detail, with `ffprobe` made to fail
- **THEN** both answer, no file under the event changes, and the staleness verdict equals the one read before
  this change for the same files
