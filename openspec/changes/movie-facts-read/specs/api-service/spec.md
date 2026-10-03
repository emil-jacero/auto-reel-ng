## ADDED Requirements

### Requirement: The event detail reports the rendered movie's version and chapter times

`GET /api/v1/events/{event_id}` SHALL carry `movie`, always present, holding either `null` or an object. It
SHALL be read from the event's render manifest and the filesystem by reading and statting only: producing it
MUST NOT run `ffprobe` or `ffmpeg`, decode any file, or write, create or refresh any file, cache entry or
database row. The events **list** (`GET /api/v1/events`) SHALL NOT carry it.

**When it is null.** `movie` SHALL be `null` when the event has no rendered movie, and it SHALL be an object
otherwise. An event has a rendered movie by the same rule as `GET /api/v1/events/{event_id}/movie`, one rule
used by both: the file the staleness gate counts, whose path (with `.` and `..` removed lexically) lies inside
the service's output directory. `movie` is therefore non-null exactly when that route would find the file, save that a manifest
whose `written_at` is not a timezone-aware date-time gives `null` (no version can be told). A
manifest the engine cannot read, a movie that is gone or is not a file, and a path that climbs out of the output
directory each give `null`; none of them SHALL fail the detail, whose own failures (an unparseable `reel.yaml`,
unusable metadata, an unreadable folder) are unchanged.

**What it holds.** The object SHALL carry:

- `recorded_at`: the render manifest's `written_at`, a timezone-aware UTC date-time. It is when the render
  record was written: the engine writes it only after the atomic finalize verified the movie, so for a render
  it is when the render finished; for a movie `adopt-renders` recorded it is when it was adopted. It MUST NOT
  be replaced with the movie file's modification time, the current time or any other value.
- `fingerprint`: the first 12 hexadecimal characters of the manifest's combined fingerprint, the identity of
  the inputs that render was made from. It is not a hash of the movie's bytes: two renders of identical inputs
  share it and differ in `recorded_at`. `recorded_at` and `fingerprint` together are the movie's version.
- `chapters`: the chapter start times that render recorded in the manifest (change `render-chapter-times`),
  a list of objects with `name` and `start`, where `start` is seconds from the beginning of the rendered
  movie (the recorded millisecond count divided by 1000). The list SHALL be exactly the recorded one: same order, same names, same times, with no chapter
  added, dropped, renamed, sorted or clamped, and no entry for the title card. `chapters` SHALL be `null`,
  meaning unknown, when the manifest records no chapter times (a manifest written before that change, or a
  movie adopted rather than rendered) or when its recorded list is unreadable. It MUST NOT be an empty list
  to mean unknown, and the API MUST NOT compute, estimate or guess a time from the reel, the clips' durations
  or the movie. A recorded list that is empty is reported as empty.

`recorded_at`, `fingerprint` and `chapters` SHALL all come from one read of the manifest, so they always
describe the same render.

**The facts describe the movie on disk.** They are the last render's, not the current editorial state's: after
the title or a chapter name changes, or a clip is added, the event is stale and `movie.chapters` still lists
the chapters and names the last render produced, while `staleness` says the movie is outdated. The movie of a
renamed event (`output_renamed`) is the file under its old name, and its facts are that render's.

**Published schema.** The service's OpenAPI schema SHALL publish `movie` as an optional, nullable property of
the detail, and `recorded_at` and `fingerprint` as required properties of the object, `chapters` as optional
and nullable, and `name` and `start` as required properties of a chapter. A generated client therefore types
absent and `null` alike as "not known". Every existing property of the detail SHALL keep its name, type,
required status and value.

#### Scenario: A rendered event reports its movie's version and chapters
- **WHEN** `2024/2024-07-14 - Kalas`, rendered by an engine that records chapter times, with chapters `Ankomst`
  and `Tårtan` that start at 4.0 and 71.5 seconds in its movie, is read with `GET /api/v1/events/{event_id}`
- **THEN** `movie.chapters` is `[{"name": "Ankomst", "start": 4.0}, {"name": "Tårtan", "start": 71.5}]`
- **AND** `movie.recorded_at` equals the manifest's `written_at`, and `movie.fingerprint` is the first 12
  characters of the manifest's `fingerprint`

#### Scenario: A real small render feeds the detail
- **WHEN** an event of two real sample clips in two chapters is rendered by the engine and its detail is read
- **THEN** `movie` is non-null and its `chapters` has two entries whose `start` values equal the manifest's,
  the first smaller than the second
- **AND** `movie.recorded_at` is not later than the time of the read

#### Scenario: A manifest from before chapter times has a movie and no chapter list
- **WHEN** `2024/2024-06-27 - Grillning med grannar` has a readable manifest without chapter times and its movie
  file exists, and its detail is read
- **THEN** `movie` is an object with `recorded_at` and `fingerprint`, and `movie.chapters` is `null`
- **AND** `movie.chapters` is not `[]`

#### Scenario: A movie adopted rather than rendered reports no chapters
- **WHEN** an event whose pre-gate movie `adopt-renders` recorded is read
- **THEN** `movie.recorded_at` is the manifest's `written_at` (the adoption time), and `movie.chapters` is `null`

#### Scenario: An unrendered event has no movie
- **WHEN** `2024/2024-09-01 - Sommarlov` or `2024/Blandat`, events with no render record, is read
- **THEN** `movie` is `null`, with the key present

#### Scenario: A deleted movie file leaves no movie facts
- **WHEN** an event has a readable manifest and neither the expected nor the recorded movie file exists
- **THEN** `movie` is `null`, the detail answers 200, and the staleness cites `output`

#### Scenario: A directory where the movie belongs is no movie
- **WHEN** an event has a readable manifest and the expected movie path is a directory, with no movie under the
  recorded name
- **THEN** `movie` is `null`

#### Scenario: An unreadable manifest is treated as absent
- **WHEN** an event's `render-manifest.json` is malformed, of an unknown version or truncated, and a file stands
  at the expected movie path
- **THEN** `movie` is `null` and the detail answers 200 with the staleness citing `no_manifest`

#### Scenario: A record without a usable time reports no movie
- **WHEN** an event's readable manifest has a `written_at` that is not a date-time, or one without a UTC offset,
  and its movie file exists
- **THEN** `movie` is `null` and the detail answers 200

#### Scenario: A stale event keeps the last render's chapters
- **WHEN** `2024/2024-08-02 - Badutflykt - Varberg` was rendered with a chapter `Bad`, its `reel.yaml` then
  renames that chapter to `Badet` and adds a clip, and its detail is read
- **THEN** the staleness cites `editorial` and `clip_set`, the detail's own `chapters` name `Badet`, and
  `movie.chapters` still names `Bad` with the starts the render recorded

#### Scenario: A renamed event reports the facts of the movie under its old name
- **WHEN** `2024/2024-06-27 - Grillning med grannar` was rendered and its title then changed, so its staleness
  cites `output_renamed`, and its detail is read
- **THEN** `movie` is non-null and holds the manifest's `recorded_at`, `fingerprint` and `chapters`, the facts
  of the file the last render wrote under the old name

#### Scenario: A re-render changes the version
- **WHEN** an event's detail is read, the event is rendered again with `--force` and no edit, and the detail is
  read again
- **THEN** `movie.fingerprint` is the same in both reads and `movie.recorded_at` is later in the second

#### Scenario: A title cannot make the detail report a file outside the output directory
- **WHEN** an event with a render record has the title `x/../../../outside` and the folders exist so that its
  expected path resolves to an existing `outside.mp4` beside the output directory
- **THEN** `movie` is `null`, as `GET …/movie` answers 404 for it

#### Scenario: The detail and the movie route agree for every event
- **WHEN** for each event the dev library's events list shows (not as an error row), the detail's `movie` and
  `GET /api/v1/events/{event_id}/movie` are read
- **THEN** `movie` is non-null exactly for the events whose route answers 200

#### Scenario: Reading the movie facts probes and writes nothing
- **WHEN** an event with a manifest that records chapters is read with every subprocess launch made to raise
  and the event directory and output directory snapshotted before and after
- **THEN** the detail answers 200 with `movie` filled, no process is launched, and no file under either
  directory is created, changed or removed

#### Scenario: The list does not carry the movie
- **WHEN** `GET /api/v1/events` lists the same events
- **THEN** no row has a `movie` key, and every row keeps the keys and values it had before

#### Scenario: The schema publishes the movie object
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the detail's properties include `movie`, which is not required
- **AND** the movie object's required properties are exactly `recorded_at` and `fingerprint`, its `chapters` is
  nullable and not required, and a chapter's required properties are exactly `name` and `start`
- **AND** the committed `web/openapi.json` equals the generated one
