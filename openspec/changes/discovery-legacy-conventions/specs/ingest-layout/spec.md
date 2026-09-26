## ADDED Requirements

### Requirement: An event marked with .reelignore is not an event

The built-in layouts SHALL NOT yield an event directory that contains a file named `.reelignore`. The marker's
contents are not read. Every command and read that enumerates events through a layout (scanning, rendering,
enqueueing, adoption, import, analysis, and the service's events list) SHALL therefore never see the
event. Each skipped event directory SHALL be logged once per walk at INFO level, naming the directory
and the marker, so a run reports what it left out rather than dropping it silently.

The marker SHALL apply to the event directory itself. A `.reelignore` at the year level of the `year-event`
layout, or at the project root, SHALL have no effect on which events are yielded. The skip SHALL be
reversible by deleting the marker: the next walk yields the event again, and nothing about it was changed
on disk.

#### Scenario: A hand-edited trip is left out of every walk
- **WHEN** `2017/2017-07-07 - Verona/` contains a `.reelignore` and `2017/2017-07-20 - Båttur/` does not
- **THEN** the `year-event` layout yields only the Båttur event, and a `render` of the project neither
  renders nor reports Verona as an event

#### Scenario: The flat layout honors the marker too
- **WHEN** the `flat` layout walks a root where one immediate subdirectory contains a `.reelignore`
- **THEN** that subdirectory is not yielded

#### Scenario: The skip is visible in the log
- **WHEN** `scan` runs over a project in which one event directory contains a `.reelignore`
- **THEN** an INFO log line names that directory as skipped because of `.reelignore`

#### Scenario: Removing the marker restores the event
- **WHEN** the `.reelignore` is deleted from a previously skipped event directory
- **THEN** the next walk yields the event, with its clips and any `reel.yaml` exactly as they were
