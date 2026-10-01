## Why

On 2026-10-01 the operator decided what GUI v1 still needs before it is done: "A and B in this version, but i
want C a full editor in v2". **A** plays the rendered movie on the event page (`movie-player-screen`). **B**
plays a source clip in Edit mode, sets a cut's From/To at the playhead and plays the clip with its cuts
skipped (`clip-preview-screen`). **C**, the full timeline editor, moves from v3 to **v2**. This is **HLD §6
phase 8 (GUI v1)**.

A browser cannot play a file it cannot fetch. Today no route serves media bytes: the thumbnail route (D-11)
serves a 320×180 JPEG from a cache, and the events reads carry file facts only (HLD §4.9, probe-free read
model). As with every earlier screen, the API contract lands first and on its own, so both screens stay pure
`web/` changes (Principle VIII). This change is that contract: two read endpoints that stream an event's
clip and its rendered movie.

Real files decide the shape. The playback research (R0, `docs/research/browser-playback.md` once this change
lands) surveyed the 5,670 MP4/MOV files of the MOL archive and played representative samples in Chrome,
Firefox and WebKit:
- **Range is mandatory.** In about 76 % of the archive's files the `moov` index sits at the **end**, so a
  browser must fetch the tail before it can show anything. Seeking needs byte ranges too.
- **Files are large.** The largest clip is a 449 MB 4K50 recording at 119 Mb/s, and the movies are larger. A
  route that reads a file into memory, as the thumbnail route does for its 15 KB JPEG, would fall over: the
  legacy tool's lack of resource bounds is HLD §2's lesson.
- **The files play as they are, except one case.** H.264 with AAC plays in all three browsers, up to that 4K50
  clip. Every render of ours plays too: H.264 High, AAC, `faststart`. The exception is the Sony XAVC clips,
  52 % of the archive: their PCM audio plays in Chrome and WebKit, while Firefox plays the picture silently.
  Fixing that server-side would need a transcode or proxy path with its own cache, concurrency and
  invalidation. That is the §8.11 proxy work, which now opens GUI v2. So v1 serves the bytes unchanged, and
  the screens say what the browser cannot do.

The same user decision moves the timeline editor to v2. Its analysis review is built as overlays on the
timeline. That roadmap edit lands here, in HLD §4.10, because this change is the first of the three
(supervisor brief).

## What Changes

- **`GET /api/v1/events/{event_id}/media?clip=<identity>`** streams one clip of an event. The identity and
  the path guard are exactly the thumbnail route's: the clip must be one of the identities discovery lists
  for an event the events list shows. The identity is matched exactly, so nothing from the request is joined
  onto a path before it matched. MISSING clips, `original/` debris and anything outside the event answer
  **404**.
- **`GET /api/v1/events/{event_id}/movie`** streams the event's **rendered movie**: the file the staleness gate
  counts as the event's movie.
  - It needs a readable render manifest. When the expected output path holds a file, it is that file.
    Otherwise it is the movie the last render recorded under the event's old name (the `output_renamed`
    case).
  - Anything else is a **404**: no render record, a recorded movie that is gone, a file at the expected
    path with no render record of this event (such as a case-only output collision's), or a path whose title
    climbs out of the output directory with `..` (a title is writable through `PUT …/reel`).
  - A movie therefore exists exactly when the event's staleness cites neither `no_manifest` nor `output`. The
    movie screen can rely on that rule and needs no new field.
- **One HTTP behaviour for both**, on Starlette's `FileResponse`, which never holds a file in memory:
  - **200** for the whole file and **206** for one byte range, with `Content-Range`. **416** with `Content-Range:
    bytes */<size>` for a range past the end.
  - `Accept-Ranges: bytes`.
  - A `Content-Type` taken from the file extension, from a fixed table that covers every extension discovery
    lists (never the host's `mimetypes`).
  - `Content-Length` and `Last-Modified`.
  - A strong `ETag` derived from the file's size and modification time, which `If-Range` is checked against.
  - `Cache-Control: private, no-cache`.
  - `Content-Disposition: inline` with the file's own name (RFC 5987 `filename*` for any name with a space,
    punctuation or a non-ASCII letter).
  - **304** when `If-None-Match` matches, evaluated before any range, because `FileResponse` does not do it
    and Chrome revalidates a `no-cache` movie with it.
  - An optional, ignored `v` query parameter, as on the thumbnail route.
- **Failures by cause** in the shared problem shape:
  - **404:** an unknown event, an unlisted clip, or no movie. A file that vanishes between the lookup and the
    stat is also a 404.
  - **502 with the events failure kind:** the event folder cannot be listed (`unreadable_disk`). For the movie,
    also an unparseable `reel.yaml` or unusable metadata, as the detail reports them.
  - **502 without a kind:** a file that can be statted but not opened. The route opens the file before it
    answers, so this is a problem body and not a 200 that breaks off. The detail is free of server paths.
- **No database, no ffmpeg, no writes.** Both routes answer while Postgres is down, declare no 503, never
  probe or decode, and write nothing anywhere.
- **Auth parity, by construction.** A `<video src>` sends no custom headers, just like `<img src>`. Every
  request, each Range request included, passes the one middleware hook (D-A8), exactly as the thumbnail's
  requests do.
- **PCM audio: nothing server-side in v1.** The clip is served unchanged as `video/mp4`. Firefox plays it
  silently. The clip preview screen says so, and the audio path joins the §8.11 proxy research for v2.
- **Every response is published** in OpenAPI: `video/*` content on 200 and 206, the headers, 304, 400, 404,
  416, 502, and the `clip`, `v`, `If-None-Match`, `Range` and `If-Range` parameters. `web/openapi.json` and
  `web/src/api/schema.d.ts` are regenerated. **No client code reads them yet.**
- **`staleness/` exposes the gate's own rule.** A new `rendered_output(event_dir, output_path)` returns the
  movie file the gate counts, and the gate's `output_renamed` check is rewritten on top of it, so the route
  and the gate cannot disagree. Gate behavior is unchanged.
- **HLD.**
  - §4.9 gets the media routes beside the thumbnail sentence.
  - §4.10 gets the roadmap edit: the full timeline editor moves from v3 to v2, analysis review is built as
    overlays on that timeline, and v2 starts with the §8.11 proxy research and the choice of a timeline
    library under D-8.
  - The roadmap edit carries through to §6 phases 9–10, D-8's rationale, D-11's and D-14's "stay v3"
    sentences and §8.11 (which gains the PCM-audio item).
  - A new research note, `docs/research/browser-playback.md`, records R0.

## Non-goals

- **The screens.** The movie player is `movie-player-screen`, which records D-15, and the clip preview is
  `clip-preview-screen`, which records D-16.
- **Transcoding, remuxing or proxies of any kind.** That means no AAC remux for PCM clips, no HLS, no
  low-resolution preview. All of it is §8.11, now v2.
- **A chapter list for the movie.** The manifest records no chapter times, and browsers do not expose MP4
  chapters to `<video>` (R0 §4). A probe of the movie on request would break the probe-free read model. Recording
  the times at render time, and a movie version in the event detail, are v2 items beside the proxy work.
- **Media facts in the events reads.** There is no duration, codec or "has a movie" field: the staleness
  verdict already answers "has a movie", and duration stays the browser's `loadedmetadata`.
- **HEAD.** FastAPI registers GET only, so HEAD answers 405, or 404 when the built client is mounted. **If-
  Modified-Since** is not evaluated either: browsers send `If-None-Match` when they hold an `ETag`. Multipart
  ranges are not refused: they are `FileResponse`'s own behavior, and browsers do not send them.
- **Serving a movie with no render record.** That includes an un-adopted legacy movie at the expected path:
  `auto-reel adopt-renders` records it first. It also excludes movies rendered with `-o` into a directory other
  than the service's output directory.
- **Problem bodies for 400 and 416.** Starlette answers a malformed or unsatisfiable `Range` in plain text,
  inside its own response after the route's lookup. The answers are published as they are. Range values
  browsers never send (an empty `bytes=5-4`, a set with one unsatisfiable range) keep Starlette's answers, which
  never send a byte outside the file (design Risks).
- **Auth.** v1 stays open on localhost (D-A8). A future token scheme must be cookie- or query-based, because
  neither `<img>` nor `<video>` can send `Authorization`. That is recorded in §4.9, not built.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `api-service`:
  - ADDED `Requirement: Media files are streamed with ranges and validators`: the HTTP behaviour both routes
    share
  - ADDED `Requirement: Clip media endpoint`: which clips are served, and its failures
  - ADDED `Requirement: Rendered movie endpoint`: which file the movie is, and its failures

## Impact

- **Packages:** `staleness/` and `api/`.
  - `staleness/gate.py`: `rendered_output` and the shared renamed-output check, exported from
    `auto_reel_ng.staleness`
  - new `api/media.py`: the extension table, `MediaFile`, the two lookups and the response helper
  - new `api/routes/media.py`: the two routes, included before the events router
  - `api/events_read.py`: `listed_clip`, the thumbnail lookup's first three steps, now shared
  - `api/app.py`: the router order
  - regenerated `web/openapi.json` and `web/src/api/schema.d.ts`
  - docs: `README.md`, `docs/high-level-design.md` and the new `docs/research/browser-playback.md`
- **CLI vs API (Principle V):** API only, with no engine capability added.
  - The clip route serves a file that discovery, and therefore `auto-reel scan`, lists.
  - The movie route serves the file that the gate, and therefore `scan` and `render`, already decides is
    the event's movie (`output` / `output_renamed`). `rendered_output` makes that decision callable instead
    of restating it in `api/`.
  - What is left is request and response shaping: the lookup, headers, validators and status mapping.
- **Rendered output:** unchanged. **No `RENDER_GRAPH_VERSION` bump.** The staleness fingerprint inputs and every
  gate verdict are unchanged: the gate's refactor is behavior-preserving, and its existing tests stay green.
- **Schemas:** no `reel.yaml` or `config.yaml` change. **No Alembic migration**, no rescan.
- **Wire:**
  - two new paths
  - no new schema component and no new problem field: 404 and 502 reuse `ProblemOut` with `event_id` and,
    where the reads already give it, `failure`
  - every existing response is unchanged, and the regenerated types compile against the existing client
- **New third-party dependencies:** none. `FileResponse` is Starlette's (installed 1.3.1), and nothing in `web/`
  changes.
- **Size (Principle VIII):** two routes, one helper module, one engine helper, one capability delta, ten tasks
  in two packages, plus regenerated artifacts and docs.
- **Dependencies (gate):** none. `cross-chapter-drag` is in flight and also edits HLD §4.10. Whichever change
  archives second re-bases its §4.10 text on `main` (task 5.2).
