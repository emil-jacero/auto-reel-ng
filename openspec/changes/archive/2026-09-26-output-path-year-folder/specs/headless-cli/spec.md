## ADDED Requirements

### Requirement: Batch commands refuse colliding output paths

Before acting, `render`, `enqueue` and `adopt-renders` SHALL check the events they selected: every event,
fresh or stale, forced or not, whether or not it is a dry run. Any two or more events that resolve to the
same output path SHALL be treated as a **collision**. Paths SHALL be compared case-insensitively, so a
collision that a case-insensitive archive filesystem would create is caught even on a case-sensitive host.

Every event in a collision SHALL be reported as an error. The report SHALL name the shared output path and
the other events that claim it. For these events the command MUST NOT render, enqueue, adopt, or overwrite
anything; an output file that already exists at the shared path SHALL be left untouched. Events outside
any collision SHALL proceed normally (per-event isolation). A command that reported at least one
collision SHALL exit non-zero. A collision SHALL NOT be resolved automatically by renaming, suffixing or
skipping one side. The operator resolves it by changing an event's `title` or `location` in `reel.yaml`.

The check covers only the events the command selected (for example, only the years named by `--years`).
Events outside the selection are not examined.

#### Scenario: Two same-titled events in one year collide
- **WHEN** `render` runs over events `2024/2024-06-21 - Midsommar` and `2024/2024-06-22 - Midsommar`,
  both with title `Midsommar` and no location, plus a third, uniquely named 2024 event
- **THEN** both Midsommar events are reported as errors naming `2024/Midsommar.mp4` and each other, neither
  is rendered, the third event renders normally, and the command exits non-zero

#### Scenario: A fresh event's output is protected from a new same-named event
- **WHEN** a fresh event already owns `<output>/2024/Midsommar.mp4` and a newly added 2024 event also
  resolves to `Midsommar`
- **THEN** `render` reports both as colliding, the existing `Midsommar.mp4` is byte-for-byte unchanged, and
  no manifest is written for either event

#### Scenario: Collision differing only in letter case
- **WHEN** two 2024 events resolve to `2024/Midsommar.mp4` and `2024/midsommar.mp4`
- **THEN** they are reported as a collision

#### Scenario: Same title in different years is not a collision
- **WHEN** events dated 2023 and 2024 both have title `Midsommar`
- **THEN** no collision is reported and both render to their own year folder

#### Scenario: Force does not override a collision
- **WHEN** `render --force` runs over two colliding events
- **THEN** both are reported as colliding and neither is rendered

#### Scenario: Dry run reports the collision
- **WHEN** `render --dry-run` runs over two colliding events
- **THEN** both are reported as colliding, no commands are printed for them, and the command exits
  non-zero

#### Scenario: Enqueue refuses colliding events
- **WHEN** `enqueue` runs over two colliding stale events
- **THEN** both are reported as colliding, no job row is inserted for either, other events are enqueued,
  and the command exits non-zero

#### Scenario: Adoption refuses a shared output
- **WHEN** `adopt-renders` runs over two colliding events and the shared output file exists
- **THEN** no manifest is written for either event (one file cannot be adopted as both movies), both are
  reported as colliding, and the command exits non-zero

### Requirement: Default output directory sits outside the project root

When neither `-o/--output` nor `config.yaml`'s `output` is set, the output directory SHALL default to
the sibling folder `<parent>/<root-name>-output` of the project root (for example, project root
`/mnt/MOL/videos/sorted` → `/mnt/MOL/videos/sorted-output`). It MUST NOT default to a path inside the
project root: the ingest layouts walk the project root's subfolders, so rendered movies filed into year
folders there would be scanned back in as events. `render`, `scan`, `enqueue`, `adopt-renders`, the worker
and the API service SHALL all resolve the same default. An explicitly configured output directory is used
as given, even when it lies inside the project root.

#### Scenario: Default output is a sibling of the project root
- **WHEN** `render /data/videos/sorted` runs with no `-o` and no `output` in `config.yaml`
- **THEN** movies are written under `/data/videos/sorted-output/`, and nothing is created inside
  `/data/videos/sorted/` except event sidecars

#### Scenario: Rendered year folders are never scanned as events
- **WHEN** `render` has written `sorted-output/2024/Midsommar.mp4` using the default output directory and
  `scan` then runs over the same project root
- **THEN** no event named `2024` or containing `Midsommar.mp4` is reported

#### Scenario: Explicit output is honored
- **WHEN** `render <root> -o <root>/out` runs
- **THEN** movies are written under `<root>/out/` as given
