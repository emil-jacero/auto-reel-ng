## ADDED Requirements

### Requirement: Aliases of one event directory are walked once

The built-in layouts SHALL yield each real event directory at most once. Event directories that
resolve to the same real path (a symlinked event folder, or an event reached through a symlinked
year folder) SHALL be collapsed to a single event. The kept path SHALL be the one reached without
crossing a symlink; if none is, the first in walk order SHALL be kept. The comparison SHALL cover the
whole walk, including years excluded by a year filter, and SHALL be applied after the `.reelignore`
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
