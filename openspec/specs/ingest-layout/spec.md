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
