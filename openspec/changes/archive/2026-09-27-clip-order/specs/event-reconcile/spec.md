## ADDED Requirements

### Requirement: Clips enter a document in the configured sort order

Whenever clips are added to an event's document from disk, they SHALL be placed in the order given by the
project's **sort rule**. This happens when a document is seeded, and when NEW clips are adopted into an
existing document. The rule SHALL be applied per chapter, to the clips entering that chapter:

- **`datetime`**, the default: ascending file modification time. Clips with equal modification times keep
  the `filename` order. The time SHALL come from the file's own directory entry. No clip is probed or
  decoded to order it.
- **`filename`**: natural, case-insensitive order of the clip's file name. Digit runs compare as numbers,
  and letters compare without regard to case.
- **`reverse`**, when set, SHALL reverse the resulting order.

Chapters SHALL keep their existing order: the default chapter first, then subfolders by name. The rule SHALL
NOT re-sort clips already in a document. After seeding, clip order is editorial, and it changes only when
`reel.yaml` is edited. NEW clips adopted into an existing chapter SHALL be appended after its existing
clips, in rule order among themselves.

#### Scenario: Two cameras are interleaved by time
- **WHEN** an event without a `reel.yaml` holds `S1600003.MP4` (modified 14:32), `P1110550.MP4` (16:36) and
  `S1600005.MP4` (16:35), and the rule is `datetime`
- **THEN** the seeded default chapter is `S1600003.MP4`, `S1600005.MP4`, `P1110550.MP4`

#### Scenario: Filename order is natural and ignores case
- **WHEN** an event holds `IMG_4933.mp4`, `img_4863.mp4`, `clip10.mp4` and `clip2.mp4`, and the rule is
  `filename`
- **THEN** the seeded order is `clip2.mp4`, `clip10.mp4`, `img_4863.mp4`, `IMG_4933.mp4`

#### Scenario: Equal times fall back to the filename order
- **WHEN** two clips have identical modification times and the rule is `datetime`
- **THEN** they are ordered by the `filename` order

#### Scenario: Reverse flips the order
- **WHEN** the rule is `filename` with `reverse: true`
- **THEN** the seeded order is the `filename` order reversed

#### Scenario: An existing order is never re-sorted
- **WHEN** an event's `reel.yaml` lists clips in a hand-chosen order that differs from the rule
- **THEN** scanning, rendering and adoption leave that order unchanged

#### Scenario: NEW clips are appended in rule order
- **WHEN** two clips are added to an event whose `reel.yaml` already lists three
- **THEN** the two are adopted after the three, in the rule's order between themselves

#### Scenario: Ordering never probes
- **WHEN** an event is seeded under the `datetime` rule during a scan
- **THEN** no clip is probed or decoded
