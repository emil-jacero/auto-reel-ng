## ADDED Requirements

### Requirement: Media files are streamed with ranges and validators
The clip media endpoint and the rendered movie endpoint SHALL serve a media file's bytes exactly as they are on
disk, with one shared HTTP behavior. The service SHALL NOT transcode, remux, probe or decode a file to serve
it. A clip whose audio a browser cannot decode, such as the PCM audio of a Sony XAVC clip, SHALL be served
unchanged.

**Whole file and ranges.**
- A request without `Range` SHALL be answered 200 with the whole file, a `Content-Length` equal to its size
  and `Accept-Ranges: bytes`.
- A request with one satisfiable byte range SHALL be answered 206 with exactly the requested bytes,
  `Content-Range: bytes <first>-<last>/<size>` and the matching `Content-Length`. This covers `bytes=<first>-<last>`,
  the open-ended `bytes=<first>-` that browsers send, and the suffix form `bytes=-<n>`.
- A last byte past the end of the file SHALL be read as the file's last byte, so `bytes=0-<huge>` is the
  whole file as 206. A suffix longer than the file SHALL likewise be the whole file as 206.
- A range whose first byte lies at or past the end of the file SHALL be answered 416 with `Content-Range:
  bytes */<size>`. This includes the empty suffix `bytes=-0` and any range on a zero-byte file.
- A `Range` header with no `=`, with no range in it, with a first byte after its last byte plus one, or
  naming a unit other than `bytes` SHALL be answered 400. The 400 and 416 bodies are plain text, not problem
  bodies.
- Any other `Range` value, including several ranges, SHALL be answered with 206, 400 or 416, never with a
  5xx, and SHALL NOT send a byte outside the file. Several ranges that do not overlap MAY be answered as one
  `multipart/byteranges` 206. Browsers send neither, so their exact answer is the framework's, not a
  contract.
- `If-Range` SHALL be honored: the range is served only when its validator is the file's current `ETag` or
  `Last-Modified`, and the whole file with 200 otherwise.

**Headers of a 200 or 206.**
- `Content-Type` SHALL follow the file name's extension, case-insensitively, from a fixed table that has an entry
  for every video extension the engine's discovery lists: `video/mp4` for `.mp4` and `.m4v`, and
  `video/quicktime` for `.mov`. It SHALL never depend on the host's MIME database.
- `Last-Modified` SHALL carry the file's modification time.
- A strong `ETag` SHALL change whenever the file's size or modification time changes. For a symlinked file, the
  size and time are those of the file the link points to.
- `Cache-Control: private, no-cache` SHALL be sent, so a browser revalidates before it reuses stored bytes.
- `Content-Disposition: inline` SHALL carry the file's own name. A name that percent-encoding would change, such
  as one with a space, punctuation or a letter outside ASCII (`2024-07-14 - Kalas.mp4` included), is sent only in
  the RFC 5987 `filename*=utf-8''<percent-encoded>` form. Any other name is sent as `filename="<name>"`.

**Conditional requests.**
- A request whose `If-None-Match` matches the current entity-tag SHALL be answered 304 with the `ETag` and
  `Cache-Control` and no body, whether or not it also carries `Range`. The match uses weak comparison, across
  every `If-None-Match` header line and comma-separated entry, and `*` matches any existing file.
- A non-matching `If-None-Match` SHALL be answered as if it were absent.
- `If-Modified-Since` SHALL NOT be evaluated.

**Version parameter.** Both endpoints SHALL accept an OPTIONAL query parameter `v`, an opaque string a client MAY
send to give a changed file a new URL. The service SHALL ignore its value: `v` SHALL NOT affect the lookup, the
headers or the status.

**Resources and failures.**
- The service SHALL read a file in bounded chunks while it sends it, and SHALL NOT hold a whole file in
  memory, so the memory a request uses does not grow with the file's size.
- A client that disconnects mid-file SHALL leave the service answering further requests.
- A file that the lookup found but that can no longer be found when it is opened SHALL be answered 404.
- A file that exists but cannot be read, for example for lack of permission, SHALL be answered 502 with a
  problem body naming the event and no failure kind. That answer SHALL come before any byte of the file is
  sent, never as a 200 that breaks off.
- A problem detail about a file that cannot be served (vanished or unreadable) SHALL name it by its
  event-relative identity or its file name, never by an absolute server path. An event folder that cannot be
  read is worded as the event detail words it.
- Every 404 and 502 is a problem body naming the event, and carries no `ETag` or `Cache-Control`.

**Scope.**
- Both endpoints SHALL answer while the database is unreachable, and SHALL declare no 503.
- They SHALL NOT run ffmpeg or ffprobe, write any file, or enqueue a job.
- Every request, each range request included, SHALL pass through the service's single authentication hook, as
  the thumbnail endpoint's requests do. A media element can then load these URLs with no custom header.
- Both endpoints SHALL publish in the service's OpenAPI schema:
  - the `v` query parameter, and `If-None-Match`, `Range` and `If-Range` as optional header parameters
  - their 200 and 206 as `video/*` binary content, with the `ETag`, `Last-Modified`, `Cache-Control`,
    `Accept-Ranges` and `Content-Disposition` headers, and `Content-Range` on the 206
  - their 304 with `ETag` and `Cache-Control`
  - their 400 and their 416 with `Content-Range`
  - their 404 and 502 in the shared problem body shape, and no 503

#### Scenario: A browser fetches the tail of a clip whose index is at the end
- **WHEN** an event holds the Sony XAVC clip `sony-xavc-1080p25-pcm.mp4` (153 MB, `moov` after `mdat`) and its
  media is requested with `Range: bytes=152000000-`
- **THEN** the response is 206 with exactly the bytes from offset 152000000 to the end, `Content-Range: bytes
  152000000-<size - 1>/<size>`, `Content-Type: video/mp4` and `Accept-Ranges: bytes`

#### Scenario: The whole file, then a range of it
- **WHEN** the Grillning clip `s1710001.mp4` is requested without `Range`, and again with `Range: bytes=0-99`
- **THEN** the first response is 200 with the whole file and a `Content-Length` equal to its size, and the second
  is 206 with the file's first 100 bytes and `Content-Range: bytes 0-99/<size>`

#### Scenario: A range past the end
- **WHEN** a clip of size N is requested with `Range: bytes=<N>-`
- **THEN** the response is 416 with `Content-Range: bytes */<N>` and no file bytes

#### Scenario: An empty clip is served as it is
- **WHEN** the zero-byte clip `trasig.mp4` of `2024/2024-10-05 - Trasig` is requested without `Range`, and again
  with `Range: bytes=0-`
- **THEN** the first response is 200 with an empty body and the second is 416 with `Content-Range: bytes */0`,
  and nothing is probed

#### Scenario: A malformed range
- **WHEN** a clip is requested with `Range: lines=0-1`, again with `Range: bytes=abc`, and again with `Range:
  bytes=5-3`
- **THEN** each response is 400 with a plain-text body

#### Scenario: Ranges a browser does not send stay bounded
- **WHEN** a clip of size N is requested with `bytes=-<N + 5>`, `bytes=0-<N * 10>`, `bytes=-0`, `bytes=0-0,2-2` and
  `bytes=5-4`
- **THEN** the first two are 206 with the whole file, `bytes=-0` is 416, `bytes=0-0,2-2` is a 206
  `multipart/byteranges` body holding bytes 0 and 2, and no answer is a 5xx or carries a byte the range does
  not name

#### Scenario: If-Range keeps a resumed download consistent
- **WHEN** a clip is requested with `Range: bytes=0-99` and `If-Range` set to its current `ETag`, and again with
  `If-Range: "an-older-tag"`
- **THEN** the first response is 206 with 100 bytes and the second is 200 with the whole file

#### Scenario: Revalidation is a 304 without a body
- **WHEN** the movie of `2024/2024-07-14 - Kalas` is requested with `If-None-Match` set to the `ETag` of an
  earlier response, with the same tag prefixed `W/`, or with a list that contains it, each also carrying `Range:
  bytes=0-`
- **THEN** each response is 304 with that `ETag`, `Cache-Control: private, no-cache` and no body

#### Scenario: A replaced file gets a new entity-tag
- **WHEN** a clip's file is replaced by another recording, changing its size and modification time, and it is
  requested with the old `ETag` in `If-None-Match`
- **THEN** the response is 200 with the new file's bytes and a different `ETag`

#### Scenario: Content type by extension, never the host's
- **WHEN** an event holds `hevc-mov-rotate90-aac.mov` and `CLIP.MP4`, and each is requested
- **THEN** the first is served as `video/quicktime` and the second as `video/mp4`, on any host

#### Scenario: The file's name travels with it
- **WHEN** the clip `Kväll, del 2/a+b & c #1.mp4` is requested
- **THEN** the response carries `Content-Disposition: inline` with `filename*=utf-8''a%2Bb%20%26%20c%20%231.mp4`

#### Scenario: A large file is streamed, not loaded
- **WHEN** the 449 MB clip `h264-4k50-aac-119mbps.mp4` is downloaded whole from a running service
- **THEN** every byte arrives, and the service's resident memory grows by far less than the file's size

#### Scenario: An unreadable file is a problem, not a broken 200
- **WHEN** a listed clip's file exists but its permissions deny reading, and it is requested
- **THEN** the response is 502 with a problem body naming the event and the clip's identity and the operating
  system's reason, with no failure kind and no absolute server path, and no status line of 200 or 206 is sent

#### Scenario: The version parameter changes nothing
- **WHEN** the same clip is requested with `v=2024-06-27T14:03:11.123456Z`, again with `v=other`, and again without `v`
- **THEN** all three responses are 200 with identical bodies and the same `ETag`

#### Scenario: No database needed
- **WHEN** the database is unreachable and a clip of `2024/2024-06-27 - Grillning med grannar` and the movie of
  `2024/2024-07-14 - Kalas` are requested
- **THEN** both are answered 200, never 503

#### Scenario: Every range request passes the authentication hook
- **WHEN** an authentication check is registered at the hook point, and a clip is requested once without `Range`
  and twice with different ranges
- **THEN** the check runs for each of the three requests, and a request it rejects is answered by the check and
  receives no file bytes

#### Scenario: The schema publishes the media responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** both media paths declare the optional `v` query parameter and the optional `If-None-Match`, `Range` and
  `If-Range` header parameters, and publish:
  - 200 and 206 as `video/*` binary content, with `Content-Range` on the 206
  - 304
  - 400 and 416
  - 404 and 502 in the shared problem body shape
  - no 503

### Requirement: Clip media endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/media?clip=<identity>`, which serves one clip's file
under the shared media behavior. `event_id` is the event identity the events routes use. `clip` is a required
query parameter carrying the clip's identity exactly as the event detail lists it: its event-relative path,
chapter folder included, percent-encoded as a query value. The identity SHALL be matched exactly, with no path
or Unicode normalization.

**Which clips are served.** A clip SHALL be served when its identity is one of the clips the engine's discovery
finds on disk for an event the events list shows. That is every clip the event detail lists that is not
MISSING, IGNORED clips included: the same set the thumbnail endpoint serves. The endpoint SHALL answer the
following with 404 and a problem body naming the event, without opening any file outside the event:
- an unknown event, or a folder the events list does not show as an event, such as a year folder, an
  event's `original/` folder or a `.reelignore`d event
- a clip the event's document references but disk does not have (MISSING)
- a file discovery skips, such as one under `original/`
- any identity that is not a discovered clip of that event, including one that points outside the event

**Failures.**
- An event folder that cannot be listed SHALL be answered 502 with the unreadable-disk failure kind the
  events reads use.
- An ingest layout that cannot be resolved SHALL be answered 502 with no kind.
- The event's `reel.yaml` SHALL NOT be read, so a broken `reel.yaml` does not stop a clip from being served.

#### Scenario: A clip in a chapter folder
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for `clip=Kv%C3%A4llen%2Fs1710002.mp4`
- **THEN** the response is 200 with the bytes of that clip in the `Kvällen` chapter folder

#### Scenario: An identity with spaces, punctuation and Swedish letters
- **WHEN** an event holds the chapter folder `Kväll, del 2` with the clip `a+b & c #1.mp4`, and its media is
  requested with `clip=Kv%C3%A4ll%2C%20del%202%2Fa%2Bb%20%26%20c%20%231.mp4`
- **THEN** the response is 200 with that clip's bytes
- **AND** the same identity sent with a literal `+` is looked up as `a b & c #1.mp4` and answers 404

#### Scenario: An IGNORED clip is still served
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for its root clip `s1710004.mp4`, which its
  `reel.yaml` lists under `ignore`
- **THEN** the response is 200

#### Scenario: A symlinked clip serves the file it points to
- **WHEN** a clip of the event is a symbolic link to a sample file outside the library
- **THEN** the response is 200 with the target file's bytes, and its `ETag` and `Last-Modified` follow the target
  file's size and modification time

#### Scenario: A MISSING clip is not served
- **WHEN** the event `2024/2024-09-01 - Sommarlov` is asked for `borttagen.mp4`, which its `reel.yaml` references
  but disk does not have
- **THEN** the response is 404 with a problem body naming the event

#### Scenario: An identity outside the event is not a clip of the event
- **WHEN** the event `2024/2024-09-01 - Sommarlov` is asked for
  `clip=../2024-06-27 - Grillning med grannar/s1710001.mp4`, or for `clip=Kvällen/../s1710001.mp4` on
  `2024/2024-08-20 - Två kapitel - Tjörn`
- **THEN** each response is 404, and no file outside the asked event's discovered clips is opened

#### Scenario: A folder that is not an event
- **WHEN** the endpoint names the year folder `2024` with `clip=2024-06-27 - Grillning med grannar/s1710001.mp4`,
  or the folder `2024/2024-06-27 - Grillning med grannar/original` with a file in it
- **THEN** each response is 404 with a problem body naming the requested id

#### Scenario: A clip that vanishes after the listing
- **WHEN** a listed clip is deleted between the event's listing and the moment its file is opened
- **THEN** the response is 404, never a 500

#### Scenario: A missing clip parameter
- **WHEN** the endpoint is requested without `clip`
- **THEN** the response is the service's 422 validation error

#### Scenario: A broken reel.yaml does not stop a clip
- **WHEN** an event's `reel.yaml` cannot be parsed and one of its clips on disk is requested
- **THEN** the response is 200 with that clip's bytes

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
`output`. There are three exceptions:
- a file removed between the two reads
- a directory, not a file, at the expected path, which the gate counts as present
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
