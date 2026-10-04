## ADDED Requirements

### Requirement: The editorial document carries the event's poster
The editorial body that `PUT /api/v1/events/{event_id}/reel` accepts, that `GET …/reel` returns and that the write
echoes SHALL carry an optional top-level `poster`: `{clip, at}`, where `clip` is a clip identity as the event
detail lists it and `at` is a number of seconds into that clip, before its cuts, with the meaning the engine's
`poster` has in `reel.yaml`. `poster` absent SHALL keep the poster `reel.yaml` already holds, so a client that
does not know posters cannot erase one; `poster: null` SHALL remove it; `{clip, at}` SHALL set it. A document with
no poster SHALL be returned with `poster: null`.

The endpoint SHALL contain no poster validation of its own beyond the body model's check of shape and JSON types:
that `clip` is a clip identity and that `at` is a finite number of at least zero are the engine's rules (the
loader's `poster.clip` and `poster.at` checks). Whether `clip` is a clip the movie plays is not a write rule: the
engine falls back to the default frame for a poster whose clip is missing, ignored or excluded, and the detail
reports it (see below). A poster the engine refuses SHALL be a **400** problem body whose `detail` names the field
(`poster.clip` or `poster.at`), and nothing is written. A key the body model does not know in `poster` is rejected, naming it.
Whether `at` lies inside the clip's duration needs a probe and SHALL NOT be checked by the write. The write keeps
every property the editorial write has: comments and key order survive, an unmodified echo leaves `reel.yaml`
byte-for-byte unchanged, and a write that changes the poster makes the event stale through the editorial
component without enqueuing a job.

#### Scenario: A poster is saved and returned
- **WHEN** `PUT …/reel` sends `poster: {clip: "s1710002.mp4", at: 12.5}`
- **THEN** `reel.yaml` holds a top-level `poster` with those two keys, the response echoes it, and `GET …/reel`
  returns it

#### Scenario: A body that knows no poster keeps the poster
- **WHEN** a write omits `poster` while `reel.yaml` holds one
- **THEN** the poster in `reel.yaml` is unchanged

#### Scenario: Null removes the poster
- **WHEN** a write sends `poster: null` while `reel.yaml` holds one
- **THEN** `reel.yaml` has no `poster` and the response has `poster: null`

#### Scenario: A poster the engine refuses is a 400
- **WHEN** a write sends `poster: {clip: "s1710002.mp4", at: -2}`
- **THEN** the response is 400 and the `detail` names `poster.at`, and `reel.yaml` is unchanged

#### Scenario: A clip the movie does not play is accepted and reported
- **WHEN** a write sends `poster: {clip: "nope.mp4", at: 1}`
- **THEN** the write succeeds, and the detail then reports `source: default` with a `poster_note` naming `nope.mp4`

#### Scenario: An unmodified echo is a no-op
- **WHEN** an event whose commented `reel.yaml` holds a poster is read with `GET …/reel` and written back unmodified
- **THEN** `reel.yaml` is byte-for-byte unchanged

#### Scenario: A poster edit makes the event stale and enqueues nothing
- **WHEN** a fresh, rendered event is saved with a changed `poster.at`
- **THEN** the response's verdict is stale citing the editorial component, and no job exists

### Requirement: The event detail reports the event's poster
`GET /api/v1/events/{event_id}` SHALL report `poster`, the effective poster as the engine's own resolution of the
document gives it, not as the service or the client decides: an object `{clip, at, source}` where `source` is
`event` when `reel.yaml`'s poster names a clip the render plays (then `clip` and `at` are its values), and
`default` otherwise (then `clip` is the first played clip's identity and `at` is `null`, because the frame time
of the default depends on a duration the read does not probe). `poster` is `null` when the event has no clip a
render plays. When `reel.yaml` holds a poster whose clip is missing, ignored or excluded, `source` is `default`
and `poster_note` names the clip and the reason; otherwise `poster_note` is `null`.

When the poster in `reel.yaml` cannot be resolved (a hand-edited value the engine refuses) the detail SHALL still
answer 200 so the author can open the event and correct it: `poster` is `null` and `poster_error` names the field
and the reason; nothing is guessed in its place. Absence of an error is `poster_error: null`. The report SHALL be
probe-free and read-only and SHALL add no database read. The published OpenAPI schema SHALL carry `poster` with
`source` as a closed enumeration, and the checked-in generated web types SHALL match it.

#### Scenario: An event with a chosen frame
- **WHEN** `reel.yaml` holds `poster: {clip: "s1710002.mp4", at: 12.5}` and that clip is played
- **THEN** `poster` is `{clip: "s1710002.mp4", at: 12.5, source: "event"}` and `poster_note` is `null`

#### Scenario: An event with no poster uses its first played clip
- **WHEN** `reel.yaml` has no `poster`, the first chapter's first clip is ignored and the next is played
- **THEN** `poster` is `{clip: <the next clip>, at: null, source: "default"}`

#### Scenario: A chosen clip that no longer plays falls back with a note
- **WHEN** the poster's clip is listed in `ignore` or is MISSING
- **THEN** `source` is `default`, `poster_note` names the clip and says why, and the detail is 200

#### Scenario: An event with no playable clip has no poster
- **WHEN** every clip of the event is ignored or missing
- **THEN** `poster` is `null` and `poster_error` is `null`

#### Scenario: A bad poster does not lock the event
- **WHEN** `reel.yaml` holds `poster: {clip: 3, at: "x"}`
- **THEN** the detail is 200, `poster` is `null` and `poster_error` names `poster`, while the clips, chapters and
  verdict are reported as usual

#### Scenario: The read is read-only and probe-free
- **WHEN** the detail is read
- **THEN** no file is written, no subprocess starts and no database read is added

### Requirement: Event poster endpoint
The service SHALL expose `GET /api/v1/events/{event_id}/poster.jpg`, which returns the event's effective poster
(the detail's `poster`) as a JPEG. It SHALL take no query parameter that changes the picture; an optional `v` is
ignored. The picture SHALL come, in this order, from:
1. the rendered sidecar `<movie stem>-poster.jpg`, only when the event's staleness verdict is not stale and the
   render manifest claims that sidecar; the bytes are served as they are
2. a frame drawn at the poster's `at` from the clip's proxy when the clip's proxy is ready (for a default poster,
   the first played clip's thumbnail frame)
3. the same frame drawn from the original clip by the engine's poster extraction

A draw SHALL be cached outside the library, in the thumbnail cache directory, keyed by the clip's size and
modification time, the frame time, the drawn size and the engine's poster version, so a repeat is served without
ffmpeg or ffprobe. The 200 response SHALL carry a strong `ETag` identifying the bytes it carries and
`Cache-Control: private, no-cache`; a request whose `If-None-Match` matches the current tag SHALL be answered 304
without extracting a frame, even when nothing is cached. Draws SHALL share the thumbnails' extraction cap (two at
once in one process) and single-flight, SHALL NOT block the event loop, and SHALL NOT be aborted by a requester
that disconnects. A failure the engine recorded less than 60 seconds ago for the same frame SHALL be answered
with that failure without ffmpeg.

Failures, each a problem body naming the event: **404** for an unknown event, a folder the events list does not
show as an event, and an event whose `poster` is `null`; **502 with the thumbnail failure kind** when the engine
cannot produce the frame (empty or undecodable clip, no frame at `at`, `at` beyond the clip's end), the detail
naming the clip and giving the reason cut to one line without paths or commands; **502** for an unlistable folder
or an unreadable cache or `config.yaml`. No placeholder image is returned and problems carry no caching headers.
The endpoint SHALL NOT need the database, SHALL NOT write into the library, SHALL NOT enqueue a job, and SHALL
publish its 200 (`image/jpeg` with the headers), 304, 404 and 502 in the OpenAPI schema.

#### Scenario: A fresh render's sidecar is served
- **WHEN** a rendered, fresh event whose manifest claims `…-poster.jpg` is requested
- **THEN** the response is 200 with the sidecar's bytes, and no ffmpeg or ffprobe process starts

#### Scenario: A stale event draws the chosen frame from the proxy
- **WHEN** the event is stale after its poster changed, the chosen clip's proxy is ready, and the endpoint is
  requested
- **THEN** the response is 200 `image/jpeg` of the frame at `at`, drawn from the proxy, and no file is created
  under the event's folder

#### Scenario: No proxy draws from the original
- **WHEN** the clip has no proxy and the endpoint is requested
- **THEN** the frame is drawn from the original and a repeat request starts no process

#### Scenario: A chosen frame is told apart from the default
- **WHEN** the same event is requested before and after a save that sets a poster at a different frame
- **THEN** the second response has a different `ETag` and a different picture

#### Scenario: Revalidation costs no extraction
- **WHEN** the endpoint is requested with `If-None-Match` set to the earlier `ETag`, with a cold cache
- **THEN** the response is 304 and no frame is extracted

#### Scenario: An event without a playable clip is 404
- **WHEN** every clip is ignored
- **THEN** the response is 404 with a problem body naming the event, without ffmpeg

#### Scenario: A frame past the end of the clip is a named failure
- **WHEN** `poster.at` is beyond the clip's duration
- **THEN** the response is 502 with the thumbnail failure kind, the detail names the clip, and a second request
  within 60 seconds is answered without ffmpeg

#### Scenario: The database is down
- **WHEN** the database is unreachable
- **THEN** the endpoint answers as usual and declares no 503
