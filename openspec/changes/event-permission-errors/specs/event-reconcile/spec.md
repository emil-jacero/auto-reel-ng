## ADDED Requirements

### Requirement: An event folder that cannot be searched is not an empty event

When the engine lists an event's clips on disk, it SHALL NOT read a refusal from the disk as an absence. An
entry that the listing can name but cannot look up, because the folder holding it denies the search
permission, SHALL fail the listing with the operating-system permission error naming the path. This covers
the event root, an immediate subdirectory of the event that may hold a chapter, and the lookup of a
`.reelignore` marker inside such a subdirectory. A listing SHALL NOT be returned that is empty or short only
because the engine was not permitted to look.

An entry the disk positively says is not there stays skipped, exactly as before: a dangling symlink, a
non-video file, and a subdirectory without videos. Seeding is a listing, so it raises the same way.

The service SHALL report such an event the way it reports any event whose files cannot be read: the events
list answers 200 with a row for that event carrying the `unreadable_disk` failure kind, the other events
unaffected, and the event detail answers 502 with the same kind. The ingest walk that finds the events is
not changed: the folder is still listed there, so it can be reported.

#### Scenario: A folder that is listable but not searchable fails the listing
- **WHEN** event folder `2024-06-21 - Fest` has mode `0600` and holds `a.mp4` and a `reel.yaml`, and its clips
  are listed or the folder is seeded
- **THEN** the listing raises a permission error naming the path, and no empty listing or empty seed is
  returned

#### Scenario: A chapter subfolder that cannot be searched fails the listing
- **WHEN** event folder `2024-06-21 - Fest` is searchable and holds root clips and a `Reception/` subdirectory
  with mode `0600` holding videos
- **THEN** the listing raises a permission error naming `Reception`, and it does not return the root clips
  alone as though `Reception` had none

#### Scenario: The events list reports the event instead of an empty summary
- **WHEN** a project holds `2024-06-21 - Midsommar` and a `0600` `2024-07-04 - Barbecue`, both with clips,
  and the events list is requested
- **THEN** the answer is 200 with one summary for Midsommar and one error row for Barbecue whose failure
  kind is `unreadable_disk`; the detail for Barbecue answers 502 with that kind

#### Scenario: A symlinked clip into a folder that cannot be searched fails the listing
- **WHEN** an event holds `clip.mp4`, a symlink whose target lies inside a folder the process cannot search
- **THEN** the listing raises a permission error naming the clip rather than omitting it

#### Scenario: Entries the disk says are absent are still skipped
- **WHEN** a searchable event folder holds `dangling.mp4`, a symlink to a file that does not exist, a
  `notes.txt`, and one real clip
- **THEN** the listing contains only the real clip and no error is raised
