## ADDED Requirements

### Requirement: Clip proxy endpoint
The service SHALL expose `GET` and `HEAD /api/v1/events/{event_id}/proxy?clip=<identity>`, which serves one
clip's **proxy**: the `proxy.mp4` that the proxy cache holds for the clip as it is on disk now, with its bytes
unchanged. `event_id` and `clip` are the clip media endpoint's: the event identity the events routes use and
the clip's identity exactly as the event detail lists it, percent-encoded as a query value and matched
exactly. An OPTIONAL query parameter `v` SHALL be accepted and ignored, as on the clip media endpoint.

**Shared behavior.** Every clause of the requirement "Media files are streamed with ranges and validators" that
governs the clip media endpoint SHALL hold for this endpoint as it holds for that one: `GET` and `HEAD`
(`HEAD` is the `GET` without its body, for every status), whole file, ranges and `If-Range`, the 400 and 416
plain-text answers, `Last-Modified`, the strong `ETag`, `Cache-Control: private, no-cache`, the conditional
requests (`If-None-Match`, then `If-Modified-Since`), bounded reads, a client that disconnects, a file that is
gone or unreadable when opened, path-free problem details, no ETag or Cache-Control on a 404 or 502, and the
single authentication hook for every request. The differences are only these:
- `Content-Type` SHALL be `video/mp4`.
- `Content-Disposition: inline` SHALL carry the cache file's own name, `proxy.mp4`.
- The `ETag` and `Last-Modified` SHALL be those of the proxy file, so a proxy that is made again has a
  different `ETag`, and a client MAY read it with a `HEAD` and send it as `v`.

**Which proxy.** The clip's proxy SHALL be the one the proxy cache holds under the cache key of the clip file
as it is now: its resolved path (a symbolic link is followed), size and modification time, the proxy version
and the proxy settings. The cache directory SHALL be the configured `proxies.cache_dir`, else the default cache
directory outside the library. Consequently:
- a proxy made for an earlier version of the file (the clip was replaced or rewritten), or under another proxy
  version or other proxy settings, is not this clip's proxy
- two events that link the same file share its proxy
- a file that is not finished is never served: a proxy that is still being written is in a hidden build
  directory of the cache, not in the clip's entry

**Which clips are served.** The clip lookup SHALL be the clip media endpoint's: the identity SHALL be one of the
clips discovery finds on disk for an event the events list shows, IGNORED clips included, and `reel.yaml` SHALL
NOT be read. The following SHALL be answered 404 with a problem body naming the event, without opening any file
outside the cache entry of a listed clip: an unknown event or a folder that is not an event; a MISSING clip; a
file discovery skips; any identity that is not a discovered clip of that event, including one that points
outside the event.

**Absent is never a 200.** A listed clip that has no proxy SHALL be answered 404 with a problem body that names
the event, the clip's identity and that it has no proxy, and carries no `ETag` or `Cache-Control`. That covers a
clip that was never prepared, a cache directory that does not exist yet, an entry without a finished
`proxy.mp4`, a proxy made for a file the clip no longer is, and something other than a regular file at the
proxy's place. The service SHALL NOT answer such a request with 200, 202, 204, a placeholder body, a redirect or
the original clip's bytes.

**Failures.**
- A listed clip that cannot be read after the listing, because it is gone, SHALL be answered 404.
- An event folder that cannot be listed SHALL be answered 502 with the unreadable-disk failure kind the events
  reads use.
- An ingest layout that cannot be resolved, a `config.yaml` that cannot be read or a `proxies.cache_dir` it
  names that is not usable SHALL be answered 502 with no failure kind.
- A proxy file that exists but cannot be statted or opened, such as one the process lacks permission to read,
  SHALL be answered 502 with a problem body naming the event, the clip's identity and the operating system's
  reason, and no failure kind, before any byte of the file is sent. The detail SHALL NOT contain an absolute
  server path.

**Scope.**
- The endpoint SHALL answer while the database is unreachable and SHALL declare no 503.
- It SHALL NOT run ffmpeg or ffprobe, write any file or create any directory (the cache directory included),
  enqueue a job, or change the events read model, the staleness verdict or any job.
- The OpenAPI schema SHALL publish, for `get` and for `head` alike: the required `clip` and optional `v` query
  parameters; `If-None-Match`, `If-Modified-Since`, `Range` and `If-Range` as optional header parameters; the
  200 and 206 as `video/mp4` binary content with the `ETag`, `Last-Modified`, `Cache-Control`, `Accept-Ranges`
  and `Content-Disposition` headers, and `Content-Range` on the 206; the 304 with `ETag` and `Cache-Control`; the
  400 and 416; the 404 and 502 in the shared problem body shape; the 422 for a missing `clip`; and no 503.

#### Scenario: A prepared clip's proxy
- **WHEN** the proxy cache holds a finished `proxy.mp4` for the clip `s1710001.mp4` of `2024/2024-06-27 -
  Grillning med grannar`, and the proxy is requested without `Range`
- **THEN** the response is 200 with the proxy file's bytes, `Content-Type: video/mp4`, a `Content-Length`
  equal to its size, `Accept-Ranges: bytes`, the `ETag` and `Last-Modified` of the proxy file, `Cache-Control:
  private, no-cache` and `Content-Disposition` naming `proxy.mp4`
- **AND** none of these is the clip's: the clip's `ETag` differs from the proxy's

#### Scenario: A seek reads a range of the proxy
- **WHEN** that proxy is requested with `Range: bytes=1000-`, again with `bytes=0-99` and `If-Range` set to its
  current `ETag`, and again with `If-Range: "an-older-tag"`
- **THEN** the first response is 206 with the bytes from offset 1000 and `Content-Range: bytes 1000-<size -
  1>/<size>`, the second is 206 with 100 bytes, and the third is 200 with the whole proxy

#### Scenario: The Sony PCM clip's proxy has AAC sound in Firefox
- **WHEN** the proxy of `sony-xavc-1080p25-pcm.mp4`, made by `auto-reel proxies`, is loaded in a `<video>` of
  the same origin in Chrome 154 and in Firefox 155 or later, and played for 3 seconds
- **THEN** each browser shows a picture, Firefox reports an audio track (`mozHasAudio`), and the decoded
  audio's peak, tapped from the element, is greater than 0 in both
- **AND** the original of the same clip, loaded from the clip media endpoint, still has no audio in Firefox

#### Scenario: The first frame is quick
- **WHEN** a fresh `<video preload="auto">` is given the Sony PCM clip's proxy URL on the dev host over the
  loopback interface, five times
- **THEN** the median time from setting `src` to the first presented frame is at most 100 ms

#### Scenario: A clip that was never prepared
- **WHEN** `s1710002.mp4` of `2024/2024-06-27 - Grillning med grannar` has no entry in the proxy cache, and its
  proxy is requested, with `GET` and with `HEAD`
- **THEN** both responses are 404 with a problem body naming the event and the clip, no body for the `HEAD`, and
  no `ETag` or `Cache-Control`
- **AND** neither the cache directory nor any file in it was created

#### Scenario: The cache directory does not exist yet
- **WHEN** `proxies.cache_dir` names a directory that does not exist and a proxy is requested
- **THEN** the response is 404, and the directory still does not exist

#### Scenario: A proxy that is still being written
- **WHEN** the clip's proxy is being encoded, so the cache holds only the encoder's hidden build directory and the
  clip has no entry, or an entry without a finished `proxy.mp4`
- **THEN** the response is 404, and no byte of the partly written file is sent

#### Scenario: A clip that was replaced since its proxy was made
- **WHEN** the proxy cache holds a proxy made for the clip `s1710001.mp4`, and the clip is then replaced by
  another recording (its size and modification time change), and the proxy is requested
- **THEN** the response is 404, although the old entry is still on disk

#### Scenario: A proxy made under another proxy version
- **WHEN** the proxy cache holds an entry for the clip made under an earlier proxy version or other proxy
  settings, and the proxy is requested
- **THEN** the response is 404

#### Scenario: A proxy that is made again gets a new entity-tag
- **WHEN** a clip's `proxy.mp4` is replaced by a different file at the same place, and the proxy is requested
  with the old `ETag` in `If-None-Match`
- **THEN** the response is 200 with the new file's bytes and a different `ETag`
- **AND** `v=old`, `v=new` and no `v` give identical bodies and the same `ETag`

#### Scenario: A HEAD gives the entity-tag a client puts in v
- **WHEN** the proxy is requested with `HEAD`, and then with `GET`
- **THEN** both carry the same `ETag`, the `HEAD` has the `Content-Length` of the file and no body

#### Scenario: Revalidation is a 304 without a body
- **WHEN** the proxy is requested with `If-None-Match` set to its `ETag`, and again with `If-Modified-Since` set
  to its `Last-Modified`
- **THEN** each response is 304 with the `ETag` and `Cache-Control: private, no-cache` and no body

#### Scenario: An IGNORED clip's proxy is served
- **WHEN** the proxy of the root clip `s1710004.mp4` of `2024/2024-08-20 - Två kapitel - Tjörn`, which its
  `reel.yaml` lists under `ignore`, is requested and the cache holds it
- **THEN** the response is 200

#### Scenario: A symlinked clip shares its target's proxy
- **WHEN** two events each hold a symbolic link to the same sample file, the cache holds the proxy made for it,
  and each event's proxy is requested
- **THEN** both responses are 200 with the same bytes

#### Scenario: Identities that are not clips of the event
- **WHEN** the proxy is requested for `borttagen.mp4` (MISSING) of `2024/2024-09-01 - Sommarlov`, for
  `clip=../2024-06-27 - Grillning med grannar/s1710001.mp4`, for a file under an event's `original/` folder, and
  for the year folder `2024`
- **THEN** each response is 404 with a problem body naming the requested id, and no file outside the cache entry
  of a listed clip is opened

#### Scenario: A clip that vanishes after the listing
- **WHEN** a listed clip is deleted between the event's listing and the moment its cache key is computed
- **THEN** the response is 404, never a 500

#### Scenario: A proxy the process cannot read
- **WHEN** a clip's `proxy.mp4` exists but its permissions deny reading, and it is requested
- **THEN** the response is 502 with a problem body naming the event, the clip's identity and `Permission
  denied`, with no failure kind and no absolute server path, and no status line of 200 or 206 is sent

#### Scenario: A configuration that cannot be read
- **WHEN** the project's `config.yaml` cannot be parsed, or `proxies.cache_dir` names a place inside the
  library, and a proxy is requested
- **THEN** the response is 502 with a problem body and no failure kind

#### Scenario: An event folder that cannot be listed
- **WHEN** the event's folder cannot be listed and a proxy is requested
- **THEN** the response is 502 with the failure kind `unreadable_disk`

#### Scenario: No database, no ffmpeg, no writes
- **WHEN** the database is unreachable, the process is not allowed to start a subprocess, and a prepared proxy
  and an absent one are requested
- **THEN** the first is 200 and the second is 404, never 503, and a snapshot of every path, size and
  modification time under the library and the cache directory is equal before and after

#### Scenario: Every range request passes the authentication hook
- **WHEN** an authentication check is registered at the hook point, and a proxy is requested once without
  `Range` and twice with different ranges
- **THEN** the check runs for each of the three requests, and a request it rejects is answered by the check and
  receives no file bytes

#### Scenario: The schema publishes the proxy responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the `get` and the `head` operation of `/api/v1/events/{event_id}/proxy` declare the required `clip`
  and the optional `v` query parameters and the optional `If-None-Match`, `If-Modified-Since`, `Range` and
  `If-Range` header parameters, and publish 200 and 206 as `video/mp4` binary content, 304, 400, 404, 416, 422
  and 502, with the problem body shape for 404 and 502 and no 503

### Requirement: Clip filmstrip endpoint
The service SHALL expose `GET` and `HEAD /api/v1/events/{event_id}/filmstrip?clip=<identity>`, which serves one
clip's **filmstrip**: the `filmstrip.jpg` sprite that the proxy cache holds in the clip's entry, with its bytes
unchanged. Its parameters, the clip lookup, the choice of the cache entry (the requirement "Clip proxy
endpoint", "Which proxy"), the shared media behavior, the failures and the scope SHALL be those of the clip
proxy endpoint, with these differences:
- `Content-Type` SHALL be `image/jpeg`, and `Content-Disposition: inline` SHALL name `filmstrip.jpg`.
- The `ETag` and `Last-Modified` SHALL be those of the filmstrip file.
- The 200 and 206 SHALL be published as `image/jpeg` binary content.
- The filmstrip SHALL be served whenever a finished `filmstrip.jpg` is in the clip's entry, whether or not the
  entry's `proxy.mp4` is present, and an entry that holds a proxy but no filmstrip SHALL be answered 404. A clip
  that has a proxy but no filmstrip is therefore an ordinary case: a clip whose sprite step has not run yet or
  failed. (A clip shorter than one second has a one-tile sprite like any other.)

The endpoint SHALL NOT read the sprite's tile geometry or any other fact; those are part of the clip's proxy
state in the event detail.

#### Scenario: A prepared clip's filmstrip
- **WHEN** the clip `s1710001.mp4` of `2024/2024-06-27 - Grillning med grannar` has a finished `filmstrip.jpg`
  in the proxy cache and the filmstrip is requested
- **THEN** the response is 200 with the file's bytes, `Content-Type: image/jpeg`, `Content-Disposition`
  naming `filmstrip.jpg`, the file's `ETag` and `Last-Modified`, and `Cache-Control: private, no-cache`
- **AND** an `<img>` of the same origin loads it and reports a natural width and height greater than 0

#### Scenario: A range and a revalidation of the filmstrip
- **WHEN** the filmstrip is requested with `Range: bytes=0-99`, and again with `If-None-Match` set to its `ETag`
- **THEN** the first response is 206 with the file's first 100 bytes and `Content-Range: bytes 0-99/<size>`,
  and the second is 304 with no body

#### Scenario: A clip with a proxy and no filmstrip yet
- **WHEN** the clip `s1710001.mp4` has a finished `proxy.mp4` and no `filmstrip.jpg` in its entry, and its proxy
  and its filmstrip are requested
- **THEN** the proxy is 200 and the filmstrip is 404 with a problem body naming the event and the clip, and no
  `ETag` or `Cache-Control`

#### Scenario: A sub-second clip has a one-tile filmstrip
- **WHEN** the clip `kort.mp4`, 0.48 s long, was prepared by the proxy work, and its proxy and filmstrip are
  requested
- **THEN** both are 200, and the filmstrip body is a JPEG

#### Scenario: A filmstrip for a clip that was never prepared
- **WHEN** a listed clip has no entry in the proxy cache and its filmstrip is requested
- **THEN** the response is 404, and nothing was created in the cache directory

#### Scenario: A filmstrip of a replaced clip
- **WHEN** a clip has been replaced since its filmstrip was made, and the filmstrip is requested
- **THEN** the response is 404

#### Scenario: A filmstrip the process cannot read
- **WHEN** a clip's `filmstrip.jpg` exists but its permissions deny reading
- **THEN** the response is 502 with a problem body naming the event and the clip, no failure kind and no
  absolute server path

#### Scenario: The schema publishes the filmstrip responses
- **WHEN** the service's OpenAPI schema is generated
- **THEN** the `get` and the `head` operation of `/api/v1/events/{event_id}/filmstrip` declare the same
  parameters as the proxy operations, and publish 200 and 206 as `image/jpeg` binary content, 304, 400, 404,
  416, 422 and 502, and no 503
