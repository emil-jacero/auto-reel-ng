## MODIFIED Requirements

### Requirement: Clip thumbnail endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/thumbnail?clip=<identity>`. It returns one clip's
thumbnail as the engine's thumbnail operation produces it: a JPEG frame taken at the configured fraction of
the clip's duration and fitted within 320×180. `event_id` is the event identity the events routes use. `clip`
is a required query parameter carrying the clip's identity exactly as the event detail lists it, which is its
event-relative path, including any chapter folder. It is percent-encoded as a query value: as in any
form-encoded query, a literal `+` reads as a space. The identity SHALL be matched exactly, with no path or
Unicode normalization.

The endpoint SHALL accept an OPTIONAL query parameter `v`, an opaque string a client MAY send to give a
changed clip a new URL. The service SHALL ignore its value: `v` SHALL NOT affect the clip lookup, the
thumbnail's cache key, the `ETag` or the status.

**Which clips have a thumbnail.** A clip SHALL have a thumbnail when its identity is one of the clips the
engine's discovery finds on disk for that event, which is every clip the event detail lists that is not
MISSING, IGNORED clips included. The endpoint SHALL answer the following with 404 and a problem body naming
the event, without running ffmpeg or ffprobe and without reading any file outside the event:
- an unknown event, or a folder the events list does not show as an event, such as a year folder, an
  event's `original/` folder or a `.reelignore`d event
- a clip the event's document references but disk does not have (MISSING)
- a file discovery skips, such as one under `original/`
- any identity that is not a discovered clip of that event, including one that points outside the event

**Success and validators.**
- A 200 response SHALL carry the JPEG as `image/jpeg`, a strong `ETag` identifying the cache entry whose
  bytes it carries, and `Cache-Control: private, max-age=86400`.
- The entity-tag SHALL change whenever the clip file's size or modification time changes, the configured
  frame position changes, or the engine's thumbnail version changes.
- A request whose `If-None-Match` matches the current entity-tag, under weak comparison and across all its
  `If-None-Match` header lines, SHALL be answered 304 with the same `ETag` and `Cache-Control` and no body.
  That answer SHALL be given without extracting a frame, even when no thumbnail is cached on the server.

**Extraction.**
- A thumbnail already cached SHALL be served without extraction and without waiting behind extractions in
  progress.
- A missing thumbnail SHALL be generated on request through the engine's thumbnail operation, which caches
  it outside the library.
- At most two extractions SHALL run at once in one service process. Further requests SHALL wait for a
  slot, not fail.
- Concurrent requests that need the same thumbnail SHALL share a single extraction.
- A clip whose failure the engine recorded less than 60 seconds ago, and whose thumbnail is not cached,
  SHALL be answered with that failure without ffprobe or ffmpeg and without waiting for a slot. The 60
  seconds SHALL run from the failed attempt: a request that reads the recorded failure does not renew it.
- The endpoint SHALL NOT block the service's event loop on disk or ffmpeg work, so other endpoints keep
  answering while thumbnails are extracted.
- A requester that disconnects SHALL NOT abort an extraction that other requests share.

**Failures, by cause.** Each SHALL be a problem body naming the event:
- **502 with the thumbnail failure kind:** the engine cannot produce a thumbnail. For example, the clip is
  empty or undecodable, it has no frame at the configured position, or it can no longer be statted
  because it changed after the event was listed, or its failure was recorded less than 60 seconds ago. The
  detail SHALL name the clip by its requested identity and give the engine's reason cut to one line,
  without server paths, commands or tool output. A recorded failure SHALL answer exactly as the failed
  attempt did. No placeholder image is returned.
- **502 with the unreadable-disk failure kind the events reads use:** the event's folder cannot be listed.
- **502 whose detail names the problem, with no failure kind:** the thumbnail cache cannot be read or
  written, or the project `config.yaml` cannot be loaded or holds an invalid thumbnail setting.

A clip's failed extraction SHALL be remembered for 60 seconds, by the engine's failure marker, so the
next requests in that window for the same clip get the same 502 without a new attempt. After that window
the next request tries again. A cache or `config.yaml` fault, and a listing failure, SHALL NOT be
remembered: the next request for the same clip tries again. Problem responses SHALL carry no caching
headers.

**Scope.**
- The endpoint SHALL NOT need the database: it answers while the database is unreachable, and it declares
  no 503.
- It SHALL NOT write anything into the library: no `reel.yaml`, no render manifest, no file beside the
  clips.
- It SHALL NOT enqueue a job.
- The events list and the event detail SHALL gain no thumbnail field, and they stay probe-free. A client
  builds the thumbnail URL from the event id and the clip identity it already holds, and MAY add the clip's
  modification time from the event detail as `v`.
- The endpoint SHALL publish in the service's OpenAPI schema:
  - its required `clip` and optional `v` query parameters
  - its optional `If-None-Match` request header
  - its 200 as `image/jpeg`, with the `ETag` and `Cache-Control` headers
  - its 304
  - its 404 and 502 in the shared problem body shape

#### Scenario: A clip's thumbnail is served from the cache outside the library
- **WHEN** `GET /api/v1/events/2024/2024-06-27%20-%20Grillning%20med%20grannar/thumbnail?clip=s1710001.mp4`
  is requested for the first time
- **THEN** the response is 200 `image/jpeg` whose body is a JPEG no larger than 320×180, with an `ETag` and
  `Cache-Control: private, max-age=86400`. The thumbnail is stored in the configured cache directory, and no
  file is created or changed under the event's folder.

#### Scenario: A repeat request is served from the cache
- **WHEN** the same Grillning clip is requested again without `If-None-Match`
- **THEN** the response is 200 with a byte-identical body and the same `ETag`, and no ffmpeg or ffprobe
  process is started

#### Scenario: The version parameter changes nothing on the server
- **WHEN** the same Grillning clip is requested with `v=2024-06-27T14:03:11.123456Z`, and again with
  `v=other`
- **THEN** both responses are 200 with byte-identical bodies and the same `ETag` as a request without `v`,
  and no second extraction runs

#### Scenario: Revalidation costs no extraction
- **WHEN** the Grillning clip is requested with `If-None-Match` set to the `ETag` of the earlier response,
  or to the same tag prefixed `W/`
- **THEN** the response is 304 with that `ETag` and the same `Cache-Control`, no body, and no ffmpeg or
  ffprobe process is started

#### Scenario: A changed clip gets a new entity-tag
- **WHEN** a clip's file is replaced by another recording, changing its size and modification time, and it
  is requested with the old `ETag` in `If-None-Match`
- **THEN** the response is 200 with the new frame and a different `ETag`

#### Scenario: A clip in a chapter folder
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for `clip=Kv%C3%A4llen%2Fs1710002.mp4`
- **THEN** the response is 200 `image/jpeg` for the clip in the `Kvällen` chapter folder

#### Scenario: An identity with spaces, punctuation and Swedish letters
- **WHEN** an event holds the chapter folder `Kväll, del 2` with the clip `a+b & c #1.mp4`, and the
  thumbnail is requested with `clip=Kv%C3%A4ll%2C%20del%202%2Fa%2Bb%20%26%20c%20%231.mp4`
- **THEN** the response is 200 `image/jpeg` for that clip
- **AND** the same identity sent with a literal `+` is looked up as `a b & c #1.mp4` and answers 404

#### Scenario: An IGNORED clip still has a thumbnail
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for its root clip `s1710004.mp4`,
  which its `reel.yaml` lists under `ignore`
- **THEN** the response is 200 `image/jpeg`

#### Scenario: A MISSING clip has no thumbnail
- **WHEN** the event `2024/2024-09-01 - Sommarlov` is asked for `borttagen.mp4`, which its `reel.yaml`
  references but disk does not have
- **THEN** the response is 404 with a problem body naming the event, and no ffmpeg or ffprobe process is
  started

#### Scenario: An identity outside the event is not a clip of the event
- **WHEN** the event `2024/2024-07-14 - Kalas` is asked for `clip=../2024-06-27 - Grillning med grannar/s1710001.mp4`
- **THEN** the response is 404 and no file outside the Kalas folder is read

#### Scenario: A path that only normalizes to a clip is not its identity
- **WHEN** the event `2024/2024-08-20 - Två kapitel - Tjörn` is asked for `clip=Kvällen/../s1710001.mp4`
- **THEN** the response is 404, although `s1710001.mp4` is a clip of that event

#### Scenario: Unknown event
- **WHEN** the endpoint names an event id that does not resolve under the configured project root
- **THEN** the response is 404 with a problem body

#### Scenario: A folder that is not an event
- **WHEN** the endpoint names the year folder `2024` with `clip=2024-06-27 - Grillning med grannar/s1710001.mp4`,
  or the folder `2024/2024-06-27 - Grillning med grannar/original` with a file in it
- **THEN** each response is 404 with a problem body naming the requested id, and no ffmpeg or ffprobe
  process is started

#### Scenario: An undecodable clip fails loud with the thumbnail kind
- **WHEN** the event `2024/2024-10-05 - Trasig` is asked for its zero-byte clip `trasig.mp4`
- **THEN** the response is 502 with the thumbnail failure kind, and a detail naming `trasig.mp4` and
  reporting that the file is empty. No image is produced. A second request within 60 seconds answers the
  same 502 without starting ffprobe or ffmpeg, and one after that window tries again.

#### Scenario: A corrupt clip's detail is one line without server paths
- **WHEN** an event holds a clip of random bytes, or an mp4 whose media data is cut short behind an intact
  index, and each is requested
- **THEN** each response is 502 with the thumbnail failure kind, and its detail is the clip's identity
  followed by a one-line cause: no newline, no ffmpeg or ffprobe command, and no path of the server
- **AND** the service's log keeps the full reason, with the failing command and its output

#### Scenario: A cache that cannot be written is the service's fault, not the clip's
- **WHEN** the configured thumbnail cache directory is read-only and an uncached clip is requested
- **THEN** the response is 502 whose detail names the operating-system error, with no thumbnail failure
  kind
- **AND** the same request made again tries again, because a cache fault is not remembered

#### Scenario: A recorded failure is answered without extraction or a slot
- **WHEN** `trasig.mp4` in `2024/2024-10-05 - Trasig` has failed, two other extractions hold both slots, and
  the clip is requested again 5 s later
- **THEN** the response is 502 with the thumbnail failure kind and the same detail as the first, without
  waiting for either extraction, and no ffmpeg or ffprobe process is started for it

#### Scenario: A recorded failure expires
- **WHEN** `trasig.mp4` failed 61 s ago, and the clip is requested
- **THEN** the probe runs again and the response is whatever that attempt gives

#### Scenario: A cached thumbnail wins over a recorded failure
- **WHEN** a clip has both `<key>.jpg` and a recorded failure of the same key
- **THEN** the response is 200 `image/jpeg`

#### Scenario: A read-only library still gets thumbnails
- **WHEN** the library is mounted read-only, as the MOL archive often is, and an uncached clip of
  `2024/2024-06-27 - Grillning med grannar` is requested
- **THEN** the response is 200 `image/jpeg`, and the thumbnail is written only into the cache directory

#### Scenario: Extraction is bounded
- **WHEN** a client requests the thumbnails of twelve distinct uncached clips at once
- **THEN** every request is answered 200, and at no moment are more than two extractions running in the
  service process

#### Scenario: Concurrent requests share one extraction
- **WHEN** five requests for the same uncached clip arrive at once
- **THEN** exactly one extraction runs, and all five responses are 200 with identical bodies and `ETag`s

#### Scenario: A cached thumbnail does not wait for a slot
- **WHEN** two slow extractions hold both slots and a thumbnail that is already cached is requested
- **THEN** that thumbnail is answered 200 without waiting for either extraction to finish

#### Scenario: Other endpoints keep answering during extraction
- **WHEN** extractions occupy both slots and further thumbnail requests are waiting for a slot
- **THEN** `GET /api/v1/events` is still answered without waiting for any extraction

#### Scenario: No database needed
- **WHEN** the database is unreachable and a clip of `2024/2024-06-27 - Grillning med grannar` is requested
- **THEN** the response is 200 `image/jpeg`, never a 503

#### Scenario: The read model gains no field
- **WHEN** `GET /api/v1/events` and `GET /api/v1/events/{event_id}` are served after this endpoint exists
- **THEN** their responses carry no thumbnail field, and no clip is probed or decoded to answer them

#### Scenario: The schema publishes the thumbnail responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the thumbnail route declares a required `clip` query parameter, an optional string query
  parameter `v` and an optional `If-None-Match` header parameter, and publishes:
  - a 200 as `image/jpeg` with the `ETag` and `Cache-Control` headers
  - a 304
  - 404 and 502 in the shared problem body shape
  - no 503
