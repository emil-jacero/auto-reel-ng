## MODIFIED Requirements

### Requirement: Rendered movie endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/movie`, which serves the event's rendered movie under
the shared media behavior. The rendered movie SHALL be the file the staleness gate counts as the event's movie,
and nothing else:
- the event SHALL have a readable render record (manifest); without one, it has no rendered movie
- when the event's expected output path, as its current title, date and location name it in the service's
  output directory, holds a file, the movie SHALL be that file
- otherwise, when the render record names a different, bare file name whose file exists where the output
  naming rule puts that name (the `output_renamed` case), the movie SHALL be that file
- the movie's path, with its `.` and `..` segments removed without touching the filesystem, SHALL lie inside
  the service's output directory. A title or render record that names `..` therefore never reaches a file
  outside it. Symbolic links inside the output directory are followed, as the gate follows them.

An event therefore has a rendered movie exactly when its staleness verdict cites neither `no_manifest` nor
`output`. There are two exceptions:
- a file removed between the two reads
- an expected path whose name climbs out of the output directory
A client SHALL be able to decide from the event detail alone whether to offer a player.

**Failures, by cause.** Each SHALL be a problem body naming the event:
- **404:**
  - an unknown event, or a folder the events list does not show as an event
  - an event with no render record
  - an event whose recorded movie is not on disk, whether under the expected or the recorded name
  - a render record whose recorded name is not a bare file name
  - a file at the expected path that this event has no render record for, such as one that another event of a
    case-only output collision rendered
  - something other than a regular file, such as a directory, at the expected path, with no movie under the
    recorded name: it is answered as absent and never served
- **502 with the events failure kind the event detail reports:** the event's `reel.yaml` cannot be parsed
  (`unparseable_reel_yaml`), the event has no real date or title (`unusable_metadata`), or its folder cannot be
  read (`unreadable_disk`).
- **502 with no kind:** an ingest layout that cannot be resolved.

#### Scenario: A fresh event's movie
- **WHEN** the movie of `2024/2024-07-14 - Kalas` is requested, an event rendered with no edit since
- **THEN** the response is 200 `video/mp4` with the bytes of `2024/2024-07-14 - Kalas.mp4` in the output
  directory, `Content-Disposition: inline` naming that file, and `Cache-Control: private, no-cache`

#### Scenario: A stale event still has its movie
- **WHEN** the movie of `2024/2024-08-02 - Badutflykt - Varberg` is requested, whose staleness cites `clip_set`
  because a NEW clip appeared after its render
- **THEN** the response is 200 with the movie of that last render

#### Scenario: A renamed event serves the movie under its old name
- **WHEN** `2024/2024-06-27 - Grillning med grannar` was rendered and its title was then changed in `reel.yaml`, so
  its staleness cites `editorial` and `output_renamed`, and its movie is requested
- **THEN** the response is 200 with the movie the last render wrote under the old name, and that name in
  `Content-Disposition`

#### Scenario: An event that was never rendered
- **WHEN** the movie of `2024/2024-09-01 - Sommarlov` or `2024/Blandat` is requested, events with no render record
- **THEN** the response is 404 with a problem body naming the event

#### Scenario: A failed render leaves no movie
- **WHEN** the movie of `2024/2024-10-05 - Trasig` is requested, whose only render failed
- **THEN** the response is 404

#### Scenario: Another event's movie at the same path is not this event's
- **WHEN** `2024/2024-07-14 - kalas`, which has no render record, names the same output file as the rendered
  `2024/2024-07-14 - Kalas`, and its movie is requested
- **THEN** the response is 404, although a file exists at its expected path

#### Scenario: A recorded movie that was deleted
- **WHEN** an event has a render record and neither the expected nor the recorded movie file exists any longer
- **THEN** the response is 404, and the event's staleness cites `output`

#### Scenario: A directory where the movie belongs is answered as absent
- **WHEN** `2024/2024-07-14 - Kalas` has a render record, and its expected movie path in the output directory is a
  directory rather than a file, and its movie is requested
- **THEN** the response is 404 with a problem body naming the event, and nothing under that directory is opened
- **AND** the event's staleness cites `output`, as it does for an absent file

#### Scenario: A render record cannot point outside the output directory
- **WHEN** an event's render record names `../elsewhere.mp4`, an absolute path or an empty name, and its expected
  movie is absent
- **THEN** the response is 404, and no file outside the output directory is opened

#### Scenario: A title cannot climb out of the output directory
- **WHEN** an event with a render record has the title `x/../../../outside` in its `reel.yaml`, and the folders
  exist so that its expected path resolves to an existing `outside.mp4` beside the output directory
- **THEN** the response is 404, and that file is not opened

#### Scenario: A symlinked folder in the output directory is followed
- **WHEN** the output directory's `2024` folder is a symbolic link to a folder on another disk that holds
  `2024-07-14 - Kalas.mp4`, and the movie of `2024/2024-07-14 - Kalas` is requested
- **THEN** the response is 200 with that file's bytes, as the event's staleness counts the movie as present

#### Scenario: An event the detail cannot read
- **WHEN** the movie of `2024/2024-02-30 - Omöjligt datum` is requested, whose folder date is not a real date
- **THEN** the response is 502 with the failure kind `unusable_metadata` and the detail the event detail gives

#### Scenario: An unparseable reel.yaml
- **WHEN** an event's `reel.yaml` cannot be parsed and its movie is requested
- **THEN** the response is 502 with the failure kind `unparseable_reel_yaml`

#### Scenario: Whether a movie exists matches the staleness verdict
- **WHEN** for each event the dev library's events list shows as an event (not as an error row), the event's
  staleness verdict and its movie are read
- **THEN** the movie answers 200 exactly for the events whose staleness cites neither `no_manifest` nor `output`,
  and 404 for the others
