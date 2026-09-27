## ADDED Requirements

### Requirement: An event without a real date and title fails on its own

An event SHALL be processable only when its resolved metadata has a real date and a title, and when that
date is not after the current day. When one of these fails, the event SHALL be reported as an error that
names the event, the reason and the fix. The reason is the folder name's stated problem when the date or
title was expected from the folder: an impossible date, a year only, no date, or no title. It can also be a
date in the future. The fix is to set the field in `reel.yaml` or to correct the folder name. An event
whose `reel.yaml` cannot be parsed SHALL be reported the same way.

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

#### Scenario: A failing event never reaches adoption
- **WHEN** `adopt-renders --dry-run` runs over an archive containing the three bad folder names
- **THEN** they are reported as `ERROR`, not as claimants of a shared `Untitled.mp4`, and every other event is
  evaluated as before
