## ADDED Requirements

### Requirement: A clip's `rotate` is an extra clockwise turn

A clip's `rotate` property (`clips.<identity>.rotate` in `reel.yaml`) SHALL mean "turn this clip this many
degrees **clockwise** from how it plays now", where "how it plays now" is the picture a player shows after
applying the container's own display rotation. It SHALL be an extra turn **on top of** the display rotation and
SHALL NOT replace it: a clip that a player shows sideways is fixed by the turn that makes the player's picture
upright, whatever the clip's container says. An absent `rotate` and `rotate: 0` SHALL both mean no extra turn.
The value is the editorial decision and SHALL be remembered in the event's `reel.yaml`, which stays the only
home of it.

A document SHALL accept for `rotate` an integer that is a multiple of 90 (so 0, 90, 180 and 270, and also -90
and 360, which mean 270 and 0). Any other value, a boolean, a float and a string included, SHALL fail the load
with a parse error that names the clip identity and the key `rotate`; the same rule SHALL apply to a document
built by an editorial write. The value SHALL be written back as it was written, with the document's comments and
key order kept by the round-trip writer.

Where another requirement or spec calls `rotate` an "orientation override", this requirement governs.

#### Scenario: A turn is read as written
- **WHEN** a document sets `clips: {Reception/00400.mp4: {rotate: 90}}`
- **THEN** the clip's property `rotate` is 90, and resolving the document puts 90 on the clip in the plan

#### Scenario: No turn
- **WHEN** a clip has no `rotate`, or `rotate: 0`
- **THEN** the plan applies no extra turn to it, and the clip is fixed only by its display rotation

#### Scenario: A turn that is not a quarter turn is refused at load
- **WHEN** a document sets `rotate: 45` on `Reception/00400.mp4`
- **THEN** loading fails with a parse error naming `Reception/00400.mp4` and `rotate`, and no render is queued
  from that document

#### Scenario: A float, a string and a boolean are refused
- **WHEN** a document sets `rotate: 90.0`, `rotate: "90"` or `rotate: true`
- **THEN** loading fails with a parse error naming the clip and `rotate`

#### Scenario: An editorial write of a bad turn leaves the file alone
- **WHEN** an editorial write sets `rotate: 100` on a clip
- **THEN** the write fails loudly and the existing `reel.yaml` is unchanged

#### Scenario: A turn survives a round trip
- **WHEN** a document with `rotate: 270` and a comment beside it is read and written back with no edit
- **THEN** the file's bytes are unchanged
