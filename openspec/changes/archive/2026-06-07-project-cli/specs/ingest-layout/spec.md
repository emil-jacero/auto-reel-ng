## ADDED Requirements

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
