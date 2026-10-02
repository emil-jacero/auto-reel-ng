## MODIFIED Requirements

### Requirement: Events read model is scanned from disk per request
`GET /api/v1/events` SHALL enumerate events by walking the configured ingest layout at request time, and
`GET /api/v1/events/{event_id}` SHALL parse the event's current `reel.yaml` (seeding metadata from the
folder name when absent, as `scan` does) — returning metadata, ordered chapters/clips, reconcile state
(NEW/MISSING), and the event's **staleness verdict** (fresh, or stale with the changed components as
reasons, from the staleness gate and render manifest). The event identity in URLs SHALL be the
root-relative event directory (URL-encoded). The service MUST NOT maintain a database copy of event or
clip state, and responses MUST reflect disk changes made since any previous request. Events reads SHALL be
read-only: no request may create or modify `reel.yaml` or the render manifest.

Each clip in the detail response SHALL additionally carry the clip file's **byte size** and **modification
time** (timezone-aware, UTC), read from the file's own directory entry. These are file facts, not media
facts: no clip may be decoded or probed to produce them, so the detail response stays probe-free. A clip the
document references but which is absent from disk SHALL report both as null rather than a substituted zero
or epoch — absence is reported, never fabricated. The events **list** response SHALL NOT carry per-clip
facts; it keeps its clip counts.

Each clip in the detail response SHALL also carry a **duration** in seconds, which is a media fact and the one
exception to "file facts only". It SHALL be the duration the engine's thumbnail operation already measured for
that exact file, read from the sidecar the thumbnail cache keeps beside the clip's cached thumbnail (the
clip-thumbnails capability), and SHALL never be obtained by decoding or probing a clip: reading the detail
response MUST NOT run `ffprobe` or `ffmpeg`, and MUST NOT write, create or refresh any cache entry. It SHALL be
`null`, meaning unknown, for a clip the document references but disk does not have, for a clip whose
thumbnail has not been made since its size or modification time last changed (the cache key covers both), and
for a clip whose sidecar cannot be read or does not hold a finite number above zero, and for every clip when
the project's `thumbnails` configuration cannot be resolved (the thumbnail endpoint reports that error itself).
A cache entry or configuration that cannot be used SHALL NOT fail the response and SHALL NOT be reported as a
zero or any other substitute; the clip's other facts are unaffected. The duration is the probe's number, so it can differ from the length a browser
reads from the same file by a few tens of milliseconds. The response schema SHALL publish the field as nullable
and optional, so a client built from it treats `null` and an absent field alike as "not known".

Every event in the **list** response SHALL carry the same staleness verdict shape as the detail response —
whether the event is stale, and when it is, the changed components as reasons — computed from the same
staleness gate and render manifest, so a client learns what needs rendering in one request rather than one
request per event. The verdict SHALL be derived from disk on every request and MUST NOT be read from, or
persisted to, the database. A list request MUST NOT compute the verdict from a completed job's existence:
a job that finished before the clips changed describes a render, not freshness.

Computing the list's verdicts SHALL NOT make the response more expensive than the facts require. The
resolved project look defaults are a per-request value, identical for every event in one response, and
SHALL be resolved once per request rather than per event. The clip-set component SHALL be computed from
the clips' size and modification time — the fingerprint's default, content-free signal; the events list
MUST NOT use the content-hash opt-in, so no clip's bytes are read to answer a list request. No event may
be probed or decoded, and no `reel.yaml`, render manifest or rendered output may be written.

#### Scenario: Disk edit is visible on the next request
- **WHEN** an event's `reel.yaml` title is edited on disk after a previous GET
- **THEN** the next `GET /api/v1/events/{event_id}` returns the new title

#### Scenario: Staleness is part of the event detail
- **WHEN** an event's clips changed since its last render
- **THEN** `GET /api/v1/events/{event_id}` reports it stale citing the clip-set component

#### Scenario: The list answers "what needs rendering?" in one request
- **WHEN** a project root holds three events — one rendered with an unchanged fingerprint, one whose clips
  changed since its last render, and one never rendered at all
- **THEN** a single `GET /api/v1/events` reports the first fresh, the second stale citing the clip-set
  component, and the third stale citing the absent manifest, with no follow-up detail request

#### Scenario: List and detail agree on the same event
- **WHEN** the same event is read through `GET /api/v1/events` and `GET /api/v1/events/{event_id}` with no
  disk change in between
- **THEN** both report the identical verdict and the identical reasons

#### Scenario: A completed job is not freshness
- **WHEN** an event's most recent job completed successfully and a clip was then added to its directory
- **THEN** the list still reports that event stale, even though it carries a completed latest job

#### Scenario: A list request reads no clip content
- **WHEN** `GET /api/v1/events` is served for a project whose events hold large clips
- **THEN** the verdicts are derived from the clips' size and modification time, and no clip's bytes are read
  to produce them

#### Scenario: Project look defaults are resolved once per list request
- **WHEN** `GET /api/v1/events` is served for a project root holding many events and a `config.yaml`
- **THEN** the project configuration is read and resolved once for that request, not once per event, and
  every event's verdict is computed against that one resolved value

#### Scenario: A list request writes nothing
- **WHEN** `GET /api/v1/events` is served for a project containing events that have no `reel.yaml` and no
  render manifest
- **THEN** the verdicts are returned and no `reel.yaml`, manifest or output file is created

#### Scenario: Event identity round-trips with spaces and non-ASCII characters
- **WHEN** an event directory is named `2024/2024-06-21 - Midsommar i Dalarna`
- **THEN** the URL-encoded id returned by the list endpoint fetches that event's detail

#### Scenario: Unknown event yields 404
- **WHEN** `GET /api/v1/events/{event_id}` names a directory that does not exist under the root
- **THEN** the response is 404 with a problem body

#### Scenario: Scan failure is loud, never fabricated
- **WHEN** an event's `reel.yaml` is unparseable
- **THEN** the response is an error naming the failing event, not an empty or partial success

#### Scenario: Clips carry the file facts a reorder view needs
- **WHEN** an event holds three clips named `P1000123.MP4`, `P1000124.MP4` and `P1000125.MP4`, written to
  disk in an order that does not match their names
- **THEN** each clip in the detail response carries its own byte size and modification time, so a client can
  present them in the order they were shot rather than the order they are named

#### Scenario: A clip missing from disk reports no file facts
- **WHEN** the document references a clip whose file has been deleted or renamed
- **THEN** that clip is still reported MISSING, and its size and modification time are both null

#### Scenario: A disk-only NEW clip carries file facts like any other
- **WHEN** a clip exists on disk but is not yet referenced by `reel.yaml`
- **THEN** it appears in the detail response as NEW, carrying its size and modification time

#### Scenario: A clip with a cached thumbnail reports its duration
- **WHEN** the thumbnail of `P1000123.MP4` (6.02 s long) was made earlier, and `GET /api/v1/events/{event_id}`
  is served
- **THEN** that clip carries a duration of `6.02`, taken from the thumbnail cache's sidecar, and neither
  `ffprobe` nor `ffmpeg` ran

#### Scenario: A clip whose thumbnail was never made reports a null duration
- **WHEN** the detail is read for an event whose clips have no cached thumbnail
- **THEN** each clip carries a duration of `null`, along with its size and modification time, and nothing was
  written into the thumbnail cache

#### Scenario: A replaced file does not keep the old file's duration
- **WHEN** the thumbnail of `P1000123.MP4` was made, then the file was replaced by another of the same name with
  a different size or modification time
- **THEN** the detail reports a duration of `null` for it until a thumbnail of the new file is made

#### Scenario: An unusable sidecar is unknown, not an error
- **WHEN** a clip's duration sidecar is present but holds invalid JSON, a duration of `0`, a negative number or a
  non-number
- **THEN** the detail response is still a success, that clip's duration is `null`, and every other clip keeps
  its own

#### Scenario: An unusable thumbnails configuration leaves durations unknown
- **WHEN** the project's `config.yaml` sets `thumbnails.position` to `2`, which the thumbnail endpoint refuses,
  and the event detail is read
- **THEN** the detail is still a success, every clip's duration is `null`, and the clips' other facts and the
  rest of the response are unchanged

#### Scenario: A missing clip has no duration
- **WHEN** the document references a clip whose file has been deleted or renamed
- **THEN** that clip is reported MISSING with a duration of `null`, alongside its null size and modification
  time

#### Scenario: File facts cost no probe
- **WHEN** an event's clips are truncated, header-damaged, or otherwise undecodable
- **THEN** the detail response still returns their size and modification time and does not fail, because no
  clip was decoded to produce them
