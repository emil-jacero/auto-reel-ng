# ingest-layout Specification

## Purpose

Map a project root directory to its event directories via a named, pluggable layout. A layout yields per-event directory paths and folder-name metadata hints without scanning clip contents. Built-in `year-event` and `flat` layouts are registered by name, the `year-event` layout supports an optional year filter, and additional layouts can be added to the registry and selected by name from configuration.

## Requirements

### Requirement: Map a project root to events via a named layout

The system SHALL provide a layout abstraction that takes a project root directory and yields the
event directories within it. A layout SHALL be selectable by name and SHALL return, per event, the
event directory path and any folder-name metadata hints. Layouts SHALL NOT scan clip contents —
that remains `scan_event`'s job.

#### Scenario: Year-event layout walks `<year>/<event>/`

- **WHEN** the `year-event` layout is applied to a root containing `2024/2024-06-21 - Midsummer/`
- **THEN** it yields one event for that directory

#### Scenario: Flat layout walks events directly under the root

- **WHEN** the `flat` layout is applied to a root whose immediate subdirectories are event dirs
- **THEN** it yields one event per immediate subdirectory and does not descend a year level

#### Scenario: Unknown layout name fails loud

- **WHEN** a layout is requested by a name that is not registered
- **THEN** the system raises a typed error naming the unknown layout, rather than silently
  yielding no events

### Requirement: Year filter

The `year-event` layout SHALL accept an optional set of years and, when given, SHALL yield only
events under the matching year directories.

#### Scenario: Years filter restricts the walk

- **WHEN** the `year-event` layout runs with a year filter of `2024`
- **THEN** events under `2024/` are yielded and events under other year directories are not

#### Scenario: No filter yields all years

- **WHEN** the `year-event` layout runs with no year filter
- **THEN** events under every year directory are yielded

### Requirement: Layouts are a pluggable registry

Layouts SHALL be registered by name in a registry so that additional layouts can be added later
and selected by name from configuration, without modifying the walk callers.

#### Scenario: Built-ins are registered

- **WHEN** the registry is consulted
- **THEN** both `year-event` and `flat` resolve to their layout implementations

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

### Requirement: Aliases of one event directory are walked once

The built-in layouts SHALL yield each real event directory at most once. Event directories that
resolve to the same real path (a symlinked event folder, or an event reached through a symlinked
year folder) SHALL be collapsed to a single event. The kept path SHALL be the one reached without
crossing a symlink; if none is, the first in walk order SHALL be kept. The comparison SHALL cover the
whole walk, including years excluded by a year filter (an excluded year that cannot be listed
SHALL be logged at WARNING and skipped, not fail the walk), and SHALL be applied after the `.reelignore`
skip. Every other path SHALL be dropped, and each dropped path SHALL be logged once per walk at
WARNING level, naming the dropped path, the kept path and the real target.

A dropped alias SHALL NOT be an event for any command or read that enumerates events through a
layout: it SHALL NOT be scanned, seeded, written, enqueued, rendered or listed, and no file SHALL be
created or modified in the real directory on its behalf. The layout SHALL NOT write anything.
Symlinks that point outside the project root and are not duplicated by another row are unaffected.

#### Scenario: Symlinked alias beside its target is dropped
- **WHEN** `2024/2024-07-20 - Kalas/` holds clips and `2024/2024-07-20 - Fest` is a symlink to it,
  and the `year-event` layout walks the root
- **THEN** only `Kalas` is yielded, and a WARNING names `Fest`, the kept `Kalas` and its real path

#### Scenario: The real directory wins even when the alias sorts first
- **WHEN** the `flat` layout walks a root where `Fest` (symlink) sorts before `Kalas` (real)
- **THEN** `Kalas` is yielded and `Fest` is not

#### Scenario: Seeding never reaches the target through an alias
- **WHEN** the repro library above is prepared and persisted for every event the layout yields
- **THEN** `Kalas/reel.yaml` is created once with the title `Kalas`, never `Fest`; and when it
  already exists its bytes are unchanged

#### Scenario: Alias in another year, with a year filter
- **WHEN** `2025/2024-07-20 - Kalas` is a symlink to `2024/2024-07-20 - Kalas` and the `year-event`
  layout runs with a year filter of `2025`
- **THEN** no event is yielded and the WARNING names the alias and the kept `2024` path

#### Scenario: Filtering by the name of a symlinked year
- **WHEN** `2023` is a symlink to `2024` and the `year-event` layout runs with a year filter of `2023`
- **THEN** no event is yielded and the WARNING names the dropped `2023/` path and the kept `2024/` path

#### Scenario: An unreadable year outside the filter
- **WHEN** a year directory outside the year filter cannot be listed
- **THEN** it is logged at WARNING and skipped, and the selected years are yielded; a selected
  year that cannot be listed still raises its `OSError`

#### Scenario: Symlinked year directory
- **WHEN** `2023` is a symlink to `2024` and the layout walks the root with no filter
- **THEN** each event under `2024/` is yielded once, under `2024/`, and the `2023/` paths are dropped

#### Scenario: Unduplicated symlink is kept
- **WHEN** an event folder is a symlink to a directory outside the project root and no other row
  resolves to it
- **THEN** it is yielded as an event and nothing is logged

#### Scenario: An ignored target takes its aliases with it
- **WHEN** the real event contains a `.reelignore` and a symlink alias points to it
- **THEN** neither is yielded, and no alias WARNING is emitted

#### Scenario: Listed-event lookup of a dropped alias
- **WHEN** a service read that accepts only ids the events list shows (for example the media
  endpoints) is asked for the id of a dropped alias
- **THEN** the lookup reports the event as not found, and the events list does not show it
