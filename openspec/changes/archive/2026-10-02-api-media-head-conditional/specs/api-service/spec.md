## MODIFIED Requirements

### Requirement: Media files are streamed with ranges and validators
The clip media endpoint and the rendered movie endpoint SHALL serve a media file's bytes exactly as they are on
disk, with one shared HTTP behavior. The service SHALL NOT transcode, remux, probe or decode a file to serve
it. A clip whose audio a browser cannot decode, such as the PCM audio of a Sony XAVC clip, SHALL be served
unchanged.

**Methods.** Both endpoints SHALL answer `GET` and `HEAD`, with and without the built web client mounted.
A `HEAD` request SHALL be answered with the status and the headers that a `GET` of the same URL and request
headers is answered with, `Content-Length`, `Content-Range`, `Content-Type`, `ETag`, `Last-Modified` and
`Cache-Control` included, and with no body. That covers every status the endpoints give: 200, 206, 304, 400,
404, 416 and 502. A `HEAD` SHALL run the same lookup and open the file once, as a `GET` does, so it never
answers 200 or 206 for a file a `GET` would answer 404 or 502 for.

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
- Any other `Range` value, including several ranges, SHALL be answered with 200 (the whole file, the header
  ignored), 206, 400 or 416, never with a 5xx, and SHALL NOT send a byte outside the file. Several ranges that
  do not overlap MAY be answered as one `multipart/byteranges` 206. Browsers send neither, so their exact
  answer is the framework's, not a contract.
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
- A non-matching `If-None-Match` SHALL be answered as if the request carried no conditional header: 200 or
  206 as the `Range` header decides, and `If-Modified-Since` SHALL NOT then be evaluated.
- A request without `If-None-Match` whose `If-Modified-Since` is a valid HTTP-date at or after the file's
  modification time, truncated to whole seconds as `Last-Modified` carries it, SHALL be answered 304 with the
  `ETag` and `Cache-Control` and no body, whether or not it also carries `Range`. A date in the future is
  valid. A date before the file's modification time SHALL be answered as if it were absent.
- An `If-Modified-Since` that is not a valid HTTP-date, or that is sent on more than one header line, SHALL be
  ignored. `If-Modified-Since` SHALL be evaluated for `GET` and `HEAD` alike.
- `If-Range` SHALL still be checked only after these preconditions, on a request that was not answered 304.

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
- Both endpoints SHALL publish in the service's OpenAPI schema, for `get` and for `head` alike:
  - the `v` query parameter, and `If-None-Match`, `If-Modified-Since`, `Range` and `If-Range` as optional
    header parameters
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

#### Scenario: A HEAD is the GET without its body
- **WHEN** the clip `s1710001.mp4` is requested with `HEAD`, and again with `HEAD` and `Range: bytes=0-99`
- **THEN** the first response is 200 with a `Content-Length` equal to the file's size, `Content-Type: video/mp4`,
  `Accept-Ranges: bytes`, the `ETag`, `Last-Modified` and `Cache-Control` a `GET` gives, and no body
- **AND** the second is 206 with `Content-Range: bytes 0-99/<size>`, `Content-Length: 100` and no body

#### Scenario: A HEAD is answered with and without the built web client
- **WHEN** the movie of `2024/2024-07-14 - Kalas` is requested with `HEAD`, once by a service with no built
  web client and once by a service that serves a built `web/dist`
- **THEN** both responses are 200 with the movie's `Content-Length` and `ETag` and no body, never 405 or the
  static mount's 404

#### Scenario: A HEAD fails as a GET fails
- **WHEN** `HEAD` is sent for `borttagen.mp4` (MISSING) of `2024/2024-09-01 - Sommarlov`, for the movie of the
  never-rendered `2024/Blandat`, and for a listed clip whose permissions deny reading
- **THEN** the responses are 404, 404 and 502, the statuses a `GET` gives, with no body and no `ETag` or
  `Cache-Control`

#### Scenario: Revalidation by date is a 304 without a body
- **WHEN** the clip `s1710001.mp4` is requested with `If-Modified-Since` set to the `Last-Modified` of an earlier
  response, again with `If-Modified-Since: Wed, 01 Jan 2099 00:00:00 GMT`, and again as `HEAD` with the first
  date and `Range: bytes=0-`
- **THEN** each response is 304 with the file's `ETag`, `Cache-Control: private, no-cache` and no body

#### Scenario: A file modified since the stored date is sent again
- **WHEN** a clip last modified on `Sat, 15 Jun 2024 10:00:00 GMT` is requested with `If-Modified-Since: Fri, 14
  Jun 2024 10:00:00 GMT`
- **THEN** the response is 200 with the whole file

#### Scenario: If-None-Match decides alone when it is present
- **WHEN** a clip is requested with `If-None-Match: "an-older-tag"` and `If-Modified-Since: Wed, 01 Jan 2099
  00:00:00 GMT`, and again with its current `ETag` in `If-None-Match` and a date before its modification time
- **THEN** the first response is 200 with the whole file, and the second is 304

#### Scenario: A date that is not a date is ignored
- **WHEN** a clip is requested with `If-Modified-Since: yesterday`, and again with two `If-Modified-Since` lines,
  each a valid date after the file's modification time
- **THEN** both responses are 200 with the whole file

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
- **THEN** the `get` and the `head` operation of both media paths declare the optional `v` query parameter and the
  optional `If-None-Match`, `If-Modified-Since`, `Range` and `If-Range` header parameters, and publish:
  - 200 and 206 as `video/*` binary content, with `Content-Range` on the 206
  - 304
  - 400 and 416
  - 404 and 502 in the shared problem body shape
  - no 503
