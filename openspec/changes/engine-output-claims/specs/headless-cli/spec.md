## MODIFIED Requirements

### Requirement: Batch commands refuse colliding output paths

Before acting, `render`, `enqueue` and `adopt-renders` SHALL check the events they selected: every event,
fresh or stale, forced or not, whether or not it is a dry run. Any two or more events that resolve to the
same output path SHALL be treated as a **collision**. Paths SHALL be compared case-insensitively, so a
collision that a case-insensitive archive filesystem would create is caught even on a case-sensitive host.
Because a dated event's file name begins with its date, a collision needs two events with the same date,
title and location. An event without a real date never reaches the check: it fails on its own first and
cannot claim a path.

Which events claim a path SHALL be decided by one rule, whichever surface checks. An event claims the output
path its resolved metadata gives it only when it can be loaded and is processable ("An event without a real
date and title fails on its own"). An event that fails in any other way, such as an unparseable `reel.yaml` or
a folder or file the process is not permitted to list or read, SHALL claim no path and SHALL fail on its own
with its reason. Such a failure MUST NOT abort the command and MUST NOT stop the collision check of any other
event. The same rule SHALL apply to the other surfaces that check for collisions: `POST /api/v1/jobs` and the
worker's claim-time recheck.

Every event in a collision SHALL be reported as an error. The report SHALL name the shared output path and
the other events that claim it. For these events the command MUST NOT render, enqueue, adopt, or overwrite
anything; an output file that already exists at the shared path SHALL be left untouched. Events outside
any collision SHALL proceed normally (per-event isolation). A command that reported at least one
collision SHALL exit non-zero. A collision SHALL NOT be resolved automatically by renaming, suffixing or
skipping one side. The operator resolves it by changing an event's `title` or `location` in `reel.yaml`.

The check covers only the events the command selected (for example, only the years named by `--years`).
Events outside the selection are not examined.

#### Scenario: Two same-titled events in one year collide
- **WHEN** `render` runs over events `2024/2024-06-21 - Midsommar` and `2024/2024-06-21 - midsommar`, both
  dated `2024-06-21` with title `Midsommar` and no location, plus a third, uniquely named 2024 event
- **THEN** both Midsommar events are reported as errors naming `2024/2024-06-21 - Midsommar.mp4` and each
  other, neither is rendered, the third event renders normally, and the command exits non-zero

#### Scenario: A fresh event's output is protected from a new same-named event
- **WHEN** a fresh event already owns `<output>/2024/2024-06-21 - Midsommar.mp4`, and a newly added event
  also resolves to date `2024-06-21` and title `Midsommar`
- **THEN** `render` reports both as colliding, the existing movie is byte-for-byte unchanged, and no
  manifest is written for either event

#### Scenario: Collision differing only in letter case
- **WHEN** two events resolve to `2024/2024-06-21 - Midsommar.mp4` and `2024/2024-06-21 - midsommar.mp4`
- **THEN** they are reported as a collision

#### Scenario: Same title in different years is not a collision
- **WHEN** events dated 2023 and 2024 both have title `Midsommar`
- **THEN** no collision is reported and both render to their own year folder

#### Scenario: Same title on different dates is not a collision
- **WHEN** events dated `2024-06-21` and `2024-06-22` both have title `Midsommar` and no location
- **THEN** no collision is reported and both render, each under its own date-prefixed name

#### Scenario: Two reel.yaml events with the same date and title collide
- **WHEN** event folders `2024/a` and `2024/b` each hold a `reel.yaml` with title `Blandat`, date
  `2024-11-02` and no location
- **THEN** both are reported as colliding on `2024/2024-11-02 - Blandat.mp4`

#### Scenario: Two undated events with the same title collide
- **WHEN** two events with folder name `Blandat` and no `reel.yaml` date are selected
- **THEN** no collision is reported: each fails on its own as an error for having no date, and neither
  claims an output path

#### Scenario: An unreadable sibling claims nothing and does not stop the check
- **WHEN** `render` runs over `2024/2024-06-21 - Midsommar`, `2024/2024-06-21 - midsommar` and
  `2024/2024-06-21 - Fest`, where the `Fest` folder has no `reel.yaml` and its permissions are `000`
- **THEN** `2024-06-21 - Fest` is reported as `ERROR` with the operating system's reason (permission denied)
  and no traceback, it claims no path, and the two Midsommar events are still reported as colliding with each
  other
- **AND** the command exits non-zero

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

### Requirement: An event without a real date and title fails on its own

An event SHALL be processable only when its resolved metadata has a real date and a title, and when that
date is not after the current day. When one of these fails, the event SHALL be reported as an error that
names the event, the reason and the fix. The reason is the folder name's stated problem when the date or
title was expected from the folder: an impossible date, a year only, no date, or no title. It can also be a
date in the future. The fix is to set the field in `reel.yaml` or to correct the folder name. An event
whose `reel.yaml` cannot be parsed SHALL be reported the same way, and so SHALL an event whose folder or
`reel.yaml` the process cannot list or read (permission denied, or another operating-system error): the reason
is the operating system's, and no traceback is printed.

`scan`, `render`, `enqueue` and `adopt-renders` SHALL isolate these errors per event. They SHALL:

- print `ERROR <event>: <reason>`
- process no further step for that event (no render, no job row, no manifest)
- continue with the remaining events
- exit non-zero when any event failed

No such error SHALL abort the whole command. A worker that claims a job for such an event SHALL fail that job
with the same reason. The service's events reads SHALL report it through their existing per-event problem
body.

#### Scenario: An impossible folder date fails only its event
- **WHEN** `render` runs over a year containing `2019-04-31 - Golfträning med Emil - Tjörn`, with no
  `reel.yaml`, and two valid events
- **THEN** the Golfträning event is reported as `ERROR` naming `2019-04-31` as not a real date and suggesting
  `metadata.date` in `reel.yaml`, both valid events render, and the command exits non-zero

#### Scenario: A year-only folder fails until reel.yaml supplies the date
- **WHEN** `scan` runs over `2004/2004 - Yngve berättar om skövde` with no `reel.yaml`
- **THEN** the event is reported as `ERROR` stating the folder name has a year only; and after
  `metadata.date: 2004-05-01` is added to its `reel.yaml`, the next `scan` lists it normally

#### Scenario: A future date is rejected
- **WHEN** an event resolves to a date after today
- **THEN** it is reported as `ERROR` naming the date as in the future

#### Scenario: A malformed reel.yaml no longer aborts the batch
- **WHEN** `scan` runs over three events and one has an unparseable `reel.yaml`
- **THEN** that event is reported as `ERROR` with the parse failure, the other two are listed, and the
  command exits non-zero

#### Scenario: An unreadable event folder fails only its event
- **WHEN** `scan` runs over three events and one is a folder with no `reel.yaml` whose permissions are `000`
- **THEN** that event is reported as `ERROR` with the permission-denied reason and no traceback, the other two
  are listed, and the command exits non-zero

#### Scenario: A failing event never reaches adoption
- **WHEN** `adopt-renders --dry-run` runs over an archive containing the three bad folder names
- **THEN** they are reported as `ERROR`, not as claimants of a shared `Untitled.mp4`, and every other event is
  evaluated as before
