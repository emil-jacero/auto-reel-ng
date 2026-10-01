## Supervisor decisions (2026-10-01)

- **A Refresh stops playback in v1:** accepted. It is a plain read that remounts `ReadyView` (decision "One address
  per movie file"). Keeping a playing movie across a Refresh is a follow-up (Open Questions).
- **No chapter jump list in v1.** A movie version (size and mtime) in the event detail and chapter times in the
  render manifest are v2 items, beside the proxy work (`media-endpoints` writes them into §4.10's v2 line).
- **The keyboard requirement's list of level-two headings** ("a year group, 'Needs attention', or a chapter",
  "The screens are operable by keyboard") is not amended for the "Movie" heading. This change's own requirement
  states the heading.
- **The section's pill stays the event's verdict** (2026-10-01, after implementation). It says Current or Outdated
  from the event read, also while a probe note says the service has no movie file. The pill states what the read
  found; the note explains what the later probe found. Hiding the pill under a note was considered and left out.
- **Fixtures for the render and cancel scenarios** (after implementation): `2024-06-21 - Midsommar - Dalarna` and
  `2024-06-27 - Grillning med grannar`, not Kalas, which `POST /api/v1/jobs` refuses with 409 `output_collision`
  on the dev library ("Verification fixtures").

## Context

See proposal.md, "Why". This change starts from `main` once `media-endpoints` (M1) is archived. Line numbers are
on `main` at `cb9e85f`, where M1 is archived (`openspec/changes/archive/2026-10-01-media-endpoints/`) and its code,
`web/openapi.json` and `schema.d.ts` have landed. The M1 facts below were re-checked against that archive and
code. Task 1.1 re-checks them in the running service.

**The route this page reads** (M1 spec "Rendered movie endpoint", "Media files are streamed with ranges and
validators"; M1 design "What the screens can rely on")
- `GET /api/v1/events/{event_id}/movie[?v=]` serves the file the staleness gate counts as the event's movie. It
  answers 200, 206 (with `Content-Range`), 304, 400, 404, 416 and 502. In OpenAPI the path has no `:path`
  converter, as for `/thumbnail`. `v` is optional and ignored.
- Headers on 200 and 206:
  - a strong `ETag: "<size hex>-<mtime_ns hex>"`
  - `Cache-Control: private, no-cache`
  - `Content-Disposition: inline` with `filename*=utf-8''<pct>` or `filename="<name>"`. Starlette chooses the form
    by whether `quote(name)` changes the name (`starlette/responses.py:320-325`, 1.3.1).
- The 416 is Starlette's: `Content-Range: bytes */<size>` and no `ETag` (`responses.py:372`).
- 404 and 502 are `ProblemOut` bodies with `event_id`; a 502 may carry `failure`. A 502 about the movie file
  names it by its file name, never its path. A 502 for an unreadable event folder is worded as the event detail
  words it.
- "Has a movie" is `!reasons.includes('no_manifest') && !reasons.includes('output')`. There are three edges where
  the route still answers 404: a race, a directory at the expected path, and a title that climbs out with `..`.
- The `ETag` changes whenever the file's size or mtime changes. The worker's atomic finalize `os.replace`s the
  movie, so every render gives the movie a new tag.

**The event page** (`web/src/events/EventDetail.tsx`)
- `ReadyView({ eventId, event })` (`:431-470`) is the read view: the missing-clips alert, the cuts note, then one
  `ChapterPanel` per chapter. The render region (`RenderPanel`, `:402-429`) sits in the page header above it.
- In Edit mode `EventEditor` replaces `ReadyView` (`:374-386`), so anything in `ReadyView` unmounts.
- A plain read (first open, Refresh, leaving Edit mode) replaces the content with placeholders (`load()`,
  `:110-162`), so `ReadyView` remounts.
- A quiet read keeps `ReadyView` mounted and hands it a new `event` object (`reread`, `:168-172`). It runs when
  the event's job ends, or when an enqueue answer shows the read is out of date (`RenderControl.tsx:239-252`,
  `:270-288`).
- The event's job is the newest job the jobs WebSocket store holds for the event id, whoever enqueued it
  (`jobs/useJob.ts:50-66`). A render started in another tab or with `POST /api/v1/jobs` therefore ends in a quiet
  read too.

**Shared pieces this change reuses**
- `api/thumbnail.ts:13-28` (`thumbnailUrl`): the pattern for a typed route constant, `satisfies keyof paths`, and
  `encodeEventId` (`route.ts:17`).
- `api/http.ts`: `isProblem` (`:7`), `readJson` (`:20`), `Unanswered` (`:32`), `unpublishedAnswer` (`:43`).
- `events/labels.ts`:
  - `FAILURE_LABEL` (`:45`), `UNANSWERED_CAUSE` (`:64`)
  - `unansweredFailure` (`:85`), whose hint says "press Refresh"
  - `failureDetail` (`:99`)
- `events/tones.ts`: `StatusLook` (`:13`), and `VERDICT_LOOK` (`:16`, ok/check and warn/refresh).
- `events/common.tsx`: `formatBytes` (`:69`) and `fileName` (`:18`).
- `ui/Alert.tsx`: its `role` prop is `alert`, `status` or `note`. Also `ui/Pill.tsx`, and the `btn` classes.
- CSS:
  - `.panel` is an inline-size container (`components.css:161`)
  - `.panel-header` is sticky at `top: var(--header-h)` (`:168-171`)
  - the coarse-pointer tap areas on `.btn` (`:829-838`) and the `alert-action` row gap (`:862-865`)
  - `:focus-visible` draws a 2px `--focus-ring` outline at a 2px offset (`base.css:69-72`)
  - `--page-max: 72rem`, `--header-h: 3rem`, `--panel-head-h: 2.75rem` (`tokens.css:95-98`)

**The rendered movie** (R0 §4, and the spike below)
- Renders are H.264 High with AAC and `-movflags +faststart` (`render/concat.py:110`). The normalize step turns a
  PCM clip into AAC, so a movie never carries the PCM audio that Firefox does not play.
- Renders carry real chapters, but the manifest records no times (`orchestrator.py:473` records only
  `output=output_path.name`).
- A legacy movie adopted with `adopt-renders` is whatever the legacy tool wrote, for example MPEG-4 Part 2 with
  MP3 (`samples/legacy-render-mpeg4-mp3.mp4`).

## Goals / Non-Goals

**Goals:**
- Play the movie the gate counts, from a page that loads none of its bytes until the operator asks.
- Never play a movie file through an address that served another version of it.
- Say every failure in words, by cause, with what helps, and never leave a black box with nothing said.
- Keep the edits to existing files to one mount point and one token.

**Non-Goals:**
- Any control the browser's native player does not offer, and any keyboard shortcut of the page's own.
- Anything that needs a probe: duration before Play, chapter times, codec checks.

## Research & Decisions

### R0 and this change's spike

**Context**: The brief asked for the player's behavior in real browsers against the real routes, before any
decision rested on it.

**Explored**:
- **R0** (`docs/research/browser-playback.md`, landed by M1): the archive survey, the samples in
  `auto-reel-media/samples/`, the browser matrix, the silent failure modes (`videoWidth === 0` for MPEG-4 Part 2 and
  HEVC in Chrome and Firefox), the render's faststart and chapters, and the `preload` request counts for clips.
- **This spike** (scratch only, session scratchpad `g-spec/movie-player-screen/`):
  - a dev library from `scripts/make_dev_library.py` on its own database
  - two added events:
    - `2022/2022-05-19 - Provklipp`: three symlinked samples, MSNV 720p, 1080p25 AAC and Sony PCM in a `Sony`
      chapter, rendered with `auto-reel render --years 2022` (75 s, two chapters, 125 MB)
    - `2016/2016-12-24 - Julafton - Tjörn`: its movie is a symlink to the legacy MPEG-4 sample, adopted with
      `auto-reel adopt-renders --years 2016`
  - the real `create_app` with M1's prototype routes, on port 8193, behind an ASGI wrapper that logged each
    request's range, `If-Range`, `If-None-Match`, status and bytes sent
  - Chrome 154 (channel `chrome`) and Firefox 132, in `mcr.microsoft.com/playwright/python:v1.49.0-noble` with
    `playwright install chrome`
  - a static mock of the planned section, using the repo's own stylesheets

  It measured:

  | question | Chrome 154 | Firefox 132 |
  |---|---|---|
  | `preload="none"`: requests in 5 s after the element appears | 0 | 0 |
  | `preload="metadata"`, Provklipp (125 MB, faststart) | 3 open-ended 206s (`bytes=0-`, then `bytes=3145728-` twice) sending 367 MB, plus 3 cache revalidations (304); then idle for 30 s | 1 × `bytes=0-` sending all 125 MB; then idle |
  | what the box shows with `preload="none"` | the poster, controls showing `0:00` | the poster, a play overlay, `0:00 / 0:00` |
  | what the box shows with `preload="metadata"` | the first frame (the first clip's picture, not a title card), `0:00 / 1:14` | the same, `0:00 / 1:15` |
  | Tab stops inside `<video controls>` | 3 before loading, at least 7 once loaded (`document.activeElement` is the `<video>` throughout) | 7 |
  | Space / Enter | play-pause / play-pause | play-pause / nothing |
  | arrows on the first stop | Left/Right seek by 0.75 s (about 1 % of 74.9 s); Down: volume −0.05 | Left/Right ±5 s; Down: volume −0.1 |
  | Home / End | start / end | start / end |
  | `:focus-visible` on the `<video>` | yes; the base outline applies | yes |
  | MP4 chapters as `textTracks` (Provklipp has two) | 0 | 0 |
  | axe-core (all rules) on a bare `<video controls>` | `video-caption` **incomplete** (needs review), not a violation | the same |
  | `<a href=movie download>` suggested name | `2022-05-19 - Provklipp.mp4` | the same |
  | 404 movie | `MediaError` 4 "Format error", no picture | `MediaError` 4 "404: Not Found" |
  | the legacy MPEG-4 movie | no error, `videoWidth` 0, duration 756.5 s (sound only) | the same, `mozHasAudio` true |
  | file replaced (`os.replace`) 2 s into playback, then a seek to 60 s | `MediaError` 3 `PIPELINE_ERROR_DECODE` | kept playing the old bytes it had buffered |
  | then a **new** `<video>` at the **same** URL | metadata of the new file (24.08 s), then `MediaError` 3 at a seek | — |
  | then a new `<video>` at a new URL (`?v=x1`) | plays the new file, no error | — |
  | `GET …/movie` with `Range: bytes=0-0`, 30 sequential requests | p50 2.6 ms, p95 4.0 ms; 206 with `ETag`, `Content-Range: bytes 0-0/<size>`, `Content-Disposition` | — |

- **Layout** (the mock, Chrome, Noto Sans per `web/README.md`). This used the frame rule below with `overflow:
  hidden` on the frame. It measured:

  | window | panel | frame | page `scrollWidth` |
  |---|---|---|---|
  | 1280 × 800 | 1152 | 768 × 432 (centered) | 1280 |
  | 768 × 800 | 707 | 673 × 378 | 768 |
  | 390 × 780 | 358 | 356 × 200 (edge to edge) | 390 |
  | 320 × 780 | 288 | 286 × 161 (edge to edge) | 320 |

  The values were the same in both schemes and under touch emulation. Two defects showed in the screenshots, and
  the decisions below fix them:
  - The frame's `overflow: hidden` clipped the video's focus outline, so no ring was visible.
  - The sticky panel header slid over the top of the video while scrolling.

**Decision**: Every claim below about a browser was observed in this spike or in R0. The verification tasks repeat
the claims the spec makes, in the real client.

**Rationale**: Every earlier screen change measured before it decided. Here the measurements reversed two
first guesses: `preload="metadata"` for a cheap first frame, and the job id as the movie's version.

### Nothing loads before Play: `preload="none"` and a thumbnail poster

**Context**: The brief asks for a poster ("thumbnail of first clip or none") and no autoplay. A page open must stay
cheap: the real movies live on a USB drive (MOL) and run to gigabytes.

**Explored**:
- **`preload="metadata"`.** It shows the real first frame and the duration before Play. Measured, it reads the
  whole 125 MB movie three times in Chrome and once in Firefox on every page open, on localhost. Over a slow drive
  the browser stops sooner, but every open still starts a read of the movie.
- **`preload="none"` with no poster**: a dark box with a play control.
- **`preload="none"` with the first played clip's thumbnail as poster.** The thumbnail is at most 320 × 180, so it
  is upscaled to 768 × 432 at most, and looks soft but recognizable in the mock. It is the address the clip's row
  already requests (`thumbnailUrl`, `v` = the clip's `mtime`), so the browser asks for it once.

**Decision**:
- `<video controls preload="none" poster={…}>`, with no `autoplay`, `loop` or `muted`. The page never calls
  `play()`.
- The poster is `thumbnailUrl(eventId, clip)` of the first clip, in the detail's chapter and clip order, whose
  status is `active` or `new`, which means it is played and on disk. With no such clip there is no `poster`. A
  poster that fails to load leaves the dark frame: the browser shows no broken image for it.

**Rationale**:
- Zero movie bytes on open, measured in both browsers. Play is the operator's request.
- **The poster is a frame from the event, not from the movie.** For an outdated movie the first clip may have
  moved since the render, and a movie's frame 0 can be a title card. Every way to show a frame of the movie itself
  costs a read of the movie or a probe. The poster is decoration, so the player is named by its heading, not by
  the poster.
- **The duration is unknown until Play.** Chrome then shows `0:00` and Firefox `0:00 / 0:00`. There is no
  probe-free source of the duration (HLD §4.9). The page adds nothing in its place, rather than a guess.

### One address per movie file: the one-byte probe

**Context**: In Chrome, a movie file replaced on disk fails at the old address with a decode error, even in a
freshly created element (spike). M1's `no-cache` revalidation does not prevent this. The spike's request log shows
the server side behaving as M1 specifies: the old element's next range request carried `If-Range` with the old tag
and got the whole new file as a 200, and the new element at the same URL got only 206s of the new file. The stale
state is therefore inside Chrome, kept per URL (its media cache is the likely holder). A render replaces the movie,
and the page often stays open while it does.

**Explored**:
- **The latest job's id or `finished_at` as `v`** (an earlier draft of M1's contract suggested `finished_at`;
  M1 now records the probe below). This misses a movie
  written by the CLI (`auto-reel render`, `adopt-renders`), which records no job. It also changes when a later job
  fails or is cancelled, which would remount a playing player for nothing.
- **A movie version in the event detail** (the file's `mtime` and size). That would be a stat in the read model,
  which §4.9 allows, but it is an `api/` change outside this web-only change, and M1 decided against media fields
  in the events reads. It is a v2 item beside the proxy work (supervisor decision).
- **Asking the route itself**, with one byte: `GET …/movie` with `Range: bytes=0-0` and `cache: 'no-store'`. It
  answers in a few milliseconds with the file's `ETag`, its size (`Content-Range`) and its name
  (`Content-Disposition`). It also proves that the movie is served, which covers the three edges where the
  detail's rule and the route disagree.

**Decision**: The page probes on every read of the event that shows the section, and the player's address carries
the tag:
- `MoviePanel` runs `probeMovie(eventId, signal)` in an effect keyed on `[eventId, event]`. The `event` object is
  new on every read, plain or quiet. The effect aborts on unmount and on a newer read.
- Only a quiet re-read reaches a mounted `MoviePanel`. A plain read (first open, Refresh, leaving Edit mode) shows
  placeholders in place of `ReadyView` (`EventDetail.tsx:120-127`, `:374-386`), so the panel unmounts, playback
  stops, and the read's answer mounts a new panel that probes afresh. This change keeps that seam as it is: a
  Refresh that kept a playing movie would need `load()` to keep `ReadyView` mounted, an edit to the page's read
  model outside this change.
- The player's `src` is `movieUrl(eventId, version)`, where `version` is the `ETag` with any `W/` and its quotes
  removed. The `<video>` lives in a `MoviePlayer` keyed by `version`.
- The answer to each probe:
  - **The same version as the shown player:** the facts may update, and the player stays: same element, same
    position, same play state.
  - **A new version:** a new `MoviePlayer` mounts at the new address. If the old `<video>` was
    `document.activeElement` when the answer arrived, the new one is focused after the commit (a ref, read in a
    layout effect keyed on the version). No toast: the render region already shows the job as rendered, and C5
    raises its "Rendered" toast for a render this tab started (`jobs/store.ts:396-409`).
  - **No movie** (404, 416, 502, no answer, an unpublished answer): the player is removed and the note for that
    cause is shown (see "Failures by cause"). If the removed `<video>` was `document.activeElement`, the note's
    wrapper (`tabIndex={-1}`) receives focus, as after a playback error.
- While the first probe of a mount is in flight, the frame shows the `<video>` with its poster and no `src`, so
  nothing shifts. Locally this takes about 3 ms (p95 4 ms).

```ts
// web/src/api/movie.ts
import { encodeEventId } from '../route'
import { contentRangeSize, dispositionName } from './headers'
import { isProblem, readJson, unpublishedAnswer } from './http'
import type { Problem, Unanswered } from './http'
import type { paths } from './schema'

/** The event's movie: the only module that knows its URL and its statuses. */
const MOVIE_PATH = '/api/v1/events/{event_id}/movie' satisfies keyof paths
type MovieQuery = NonNullable<paths[typeof MOVIE_PATH]['get']['parameters']['query']>

/** `version` is the file's entity-tag without quotes; null for the probe's own address. */
export function movieUrl(eventId: string, version: string | null): string {
  const path = MOVIE_PATH.replace('{event_id}', () => encodeEventId(eventId))
  if (version === null) {
    return path
  }
  const query: Record<string, string> = { v: version } satisfies MovieQuery
  return `${path}?${new URLSearchParams(query)}`
}

/** What one byte of the movie told: never a guessed fact (`null` when a header was absent). */
export type MovieFile = { version: string; size: number | null; name: string | null }

export type MovieProbe =
  | { kind: 'ok'; file: MovieFile }
  | { kind: 'empty' } // 416: the file has no bytes
  | { kind: 'problem'; problem: Problem } // 404 / 502 in the published shape
  | Unanswered

/** Ask for the movie's first byte. Rethrows `AbortError`. */
export async function probeMovie(eventId: string, signal: AbortSignal): Promise<MovieProbe>
```

`probeMovie`:
- sends `fetch(movieUrl(eventId, null), { headers: { Range: 'bytes=0-0' }, cache: 'no-store', signal })`
- 200 or 206 with an `ETag` → `ok`. It cancels the body (`response.body?.cancel()`). The size is from
  `Content-Range` on a 206 and from `Content-Length` on a 200.
- 416 → `empty`
- 404 or 502 with a problem body → `problem`
- a rejected fetch → `unreachable`; anything else → `unpublishedAnswer('GET', …)`

`api/headers.ts` holds the two parsers. It has no imports, so the ad hoc check runs them under `node
--experimental-strip-types` as they are:

```ts
/** `bytes 0-0/1234` or `bytes */1234` → 1234; null for anything else. */
export function contentRangeSize(value: string | null): number | null
/** `inline; filename*=utf-8''<pct>` → decoded, `inline; filename="<name>"` → name; null otherwise. */
export function dispositionName(value: string | null): string | null
```

`dispositionName` returns null for a malformed percent-escape. These two header forms are exactly the ones
Starlette writes, and the parsers accept no others.

**Rationale**:
- The address is a pure function of the file's version, so a changed file can never be read through an address
  that served another version. This is the one measured way Chrome stays correct.
- It covers every writer of the movie (worker, CLI render, `adopt-renders`, a hand copy) once the page reads the
  event again. A failed or cancelled job leaves the tag as it was, so a playing movie is not interrupted.
- One request of a few milliseconds per read, against Chrome's 367 MB for `preload="metadata"`. It is a read, so
  "Reading a screen never changes state" holds. It is not a read of the page's content, so it shows no placeholder
  ("A read in progress is shown as a placeholder", whose "other reads" clause covers it).
- The facts shown (name, size) come from the service's own headers. A missing header leaves its fact out.

### The browser's own player, and its keyboard model

**Context**: The brief asks for a keyboard model. D-8 rules out a media library, and the screens' rule is that
every control is reachable by keyboard with a visible focus.

**Explored**:
- **Custom controls** (play, a timeline slider, time, volume, fullscreen): several hundred lines, each control's
  ARIA and keyboard to get right in two engines, and a slider that must handle seeking without a duration until
  metadata loads.
- **Native controls plus page shortcuts** (J/K/L, arrows on the frame): measured, the native controls already
  consume Space and the arrows, so page handlers would double-seek in Firefox, and global keys would collide with
  Edit mode's fields and the drag keyboard.
- **Native controls alone.**

**Decision**: Native `controls`, nothing added. The keyboard model is the browser's, as measured:
- **Tab** reaches the player's controls in order (Chrome: 3 before loading, at least 7 once loaded; Firefox: 7),
  then leaves it. `document.activeElement` is the
  `<video>` throughout, and the page's `:focus-visible` outline draws around it.
- **Space** plays and pauses in both browsers. **Enter** does too in Chrome.
- **Home** and **End** jump to the start and the end.
- **Left** and **Right** seek: ±5 s in Firefox, about 1 % of the length in Chrome from the play control. Chrome's
  timeline control takes the arrows when focused.
- **Up** and **Down** change the volume.

Nothing in the page handles a key for the player. The verification exercises Tab, Space, Home and End, which both
browsers share.

**Rationale**: Each browser's model is what its users already know, it is accessible as shipped, and it costs no
code. The difference between the two browsers' seek steps is theirs, not the page's.

### The section: where, what it says, markup and copy

**Decision**: `MoviePanel` is the first child of `ReadyView`'s fragment. It renders nothing when
`hasMovie(event.staleness)` is false. So it sits after the render region and before the missing-clips alert, the
cuts note and the chapters: the movie belongs with the render story, and the clip notes stay with the clips.

```tsx
<section className="panel movie-panel" aria-labelledby={headingId}>
  <header className="panel-header">
    <h2 id={headingId}>Movie</h2>
    <Pill tone={MOVIE_AGE_LOOK[age].tone} icon={MOVIE_AGE_LOOK[age].icon}>{MOVIE_AGE_LABEL[age]}</Pill>
  </header>
  <div className="movie-body">
    {/* a fetch trouble: <div tabIndex={-1} ref={noteRef}><Alert role=…/></div> in place of the figure */}
    <div className="movie-figure">
      <div className="movie-frame">
        <video controls preload="none" poster={poster} src={src} aria-labelledby={headingId} />
      </div>
      {facts && <p className="movie-facts"><span className="movie-file">{name}</span> · {size}</p>}
      {age === 'outdated' && <p className="movie-facts">{OUTDATED_NOTE}</p>}
      {/* a playback trouble: <Alert role="alert" | "status" …/> */}
    </div>
  </div>
</section>
```

- **The age**, `web/src/movie/labels.ts`, exhaustive over `MovieAge = 'current' | 'outdated'`, which comes from
  `staleness.stale`:

  | age | label | tone / icon |
  |---|---|---|
  | `current` | Current | `ok` / `check` |
  | `outdated` | Outdated | `warn` / `refresh` (as `VERDICT_LOOK.stale`) |

  `OUTDATED_NOTE` is "Rendered before the latest changes to this event. Render it again to bring the movie up to
  date." It does not repeat the reasons: the render region above lists them, and its `output_renamed` note already
  says that the movie under the old name stays on disk.
- **The facts line** is `<name> · <size>`. The name is set in `--font-mono`, as file names are elsewhere, and the
  size uses `formatBytes`. A part the probe did not get is left out, and the line is left out when both are.
- **The accessible name** of the `<video>` is the heading, "Movie". The page's `h1` names the event.
- **`hasMovie(staleness)`** is `!staleness.reasons.includes('no_manifest') && !staleness.reasons.includes('output')`,
  with a comment citing M1's contract.
- **The renamed case and the existing spec.** "The event page says what a render does when the movie's name
  changed" ends in "the page names no movie file", which this section would break on Grillning. Its rule ("Neither
  screen SHALL name a movie file that the service's response does not carry") still holds, since the name comes
  from the movie route's `Content-Disposition`. The change modifies that requirement: the render region names no
  file, and the "Movie" section names the old one. `events/labels.ts`' `output_renamed` words and note are not edited.

**Rationale**: The page states the verdict once, in the render region. The section adds only what is about the
file: which file, how big, and whether it matches the event. Both are needed to read an outdated movie correctly.

### Failures by cause

**Context**: A `<video>` sees every failure as `MediaError` 4, or as nothing at all (R0, spike). The house rule is
failures by cause, in words, never a slug.

**Decision**: There are two kinds of trouble, both worded in `movie/labels.ts` (`MOVIE_TROUBLE: Record<MovieTrouble,
…>` with a title and a tone each):

| trouble | when | title | detail | action | where, role |
|---|---|---|---|---|---|
| `no_file` | probe 404 | The service has no movie file for this event. | the problem's `detail` | — | replaces the figure; `note`, or `alert` after Play |
| `unreadable` | probe 502 | The movie could not be read. | `failureDetail(eventId, detail)`, plus the `FAILURE_LABEL` pill when `failure` is set | — | as above |
| `empty` | probe 416 | The movie file is empty. | — | — | as above |
| (unanswered) | probe rejected or unpublished | `unansweredFailure(result).cause` | its `detail` ("…press Refresh") | — | as above |
| `no_picture` | `loadedmetadata` with `videoWidth === 0` | This browser cannot show this movie's picture. It plays the sound only. | Download it to watch it in another player. | Download the movie | under the frame; a `note`, its title said through an always-mounted `status` region |
| `cannot_play` | `error` (code other than 2), and a re-probe gives the same version | This browser could not play the movie. | `MEDIA_ERROR_WORDS[code]`, then `: <MediaError.message>` when it is not empty | Try again, Download the movie | under the frame; `alert` |
| `load_failed` | `error` with code 2 (network), and a re-probe gives the same version | The movie could not be loaded. | as `cannot_play` | Try again, Download the movie | under the frame; `alert` |
| `changed` | `error`, and a re-probe gives another version | The movie file changed while it played. | The file on disk is not the one that started playing. | Load the new movie | under the frame; `alert` |

- **Tones:** `no_file` `warn`; `unreadable`, `empty`, `cannot_play` and `load_failed` `err`; `no_picture` `warn`;
  `changed` `info`.
- **`MEDIA_ERROR_WORDS`** is a `Record<1 | 2 | 3 | 4, string>`:
  - 1: "Loading was stopped"
  - 2: "A network error interrupted loading"
  - 3: "The movie could not be decoded"
  - 4: "The browser does not support the file or its format"

  A code outside 1–4 reads "MediaError <code>". The browser's own message is shown as it is: it is a fact, often
  technical (`PIPELINE_ERROR_DECODE: …`).
- **"Download the movie"** is `<a className="btn btn-secondary" href={movieUrl(eventId, version)} download>`. The
  `download` attribute saves the file under the name in `Content-Disposition` (measured in both browsers). When
  `ui/Icon.tsx` already has a `download` icon on `main` (`clip-preview-screen` adds it), the link shows it before
  its words; this change adds no icon.
- **Words.** The titles use "cannot" and "could not", the repository's majority form, never "can't".
- **"Load the new movie"** is a `btn btn-primary` `<button>`. It mounts the new version's player without starting
  it, and focuses the new `<video>`.
- **Diagnosis.** On `error`, `MoviePlayer` runs `probeMovie` once and maps the answer as the table says. An answer
  of `problem`, `empty` or unanswered goes up to the panel, which removes the player and shows that note with
  `role="alert"`, because it follows the operator's own action. If the removed `<video>` had focus, the note's
  wrapper (`tabIndex={-1}`) receives it.
- **Roles.**
  - A probe trouble found by a read is a `note`: part of the content, never announced on open or Refresh ("The
    screens announce each change once").
  - A playback trouble appears once, in response to the operator's action, and is announced once. A warning
    (`no_picture`) is polite (`status`); a failure is assertive (`alert`).
- **Lifetimes.** A playback trouble lives in `MoviePlayer`'s state, so a new player starts clean. A re-read that
  finds the same version keeps it. A note never replaces the player for `no_picture`: the sound still plays.

**Rationale**:
- One extra probe tells "the file changed" (Chrome's real failure after a render) apart from "this browser cannot
  decode it" and from "the service has no file", which `MediaError` alone cannot.
- Every message names a cause and what helps. Recovery from the service-side causes is the page's Refresh, which
  re-reads the event and probes again; that is the hint the page already gives.

### Layout and the design system

**Decision**: `web/src/movie/movie.css`, all in `@layer screens`:

```css
.movie-panel > .panel-header {
  position: static; /* short section: its heading scrolls away rather than covering the player */
}
.movie-body {
  padding-inline: var(--s-4);
}
.movie-figure {
  /* 16:9, at most 48rem, and never taller than the window leaves below the header and this heading */
  inline-size: min(100%, 48rem, calc((100svh - var(--header-h) - var(--panel-head-h) - 2rem) * 16 / 9));
  display: grid;
  gap: var(--s-2);
  margin: 0 auto;
  padding-block: var(--s-4);
}
.movie-frame {
  aspect-ratio: 16 / 9;
}
.movie-frame video {
  display: block;
  inline-size: 100%;
  block-size: 100%;
  border-radius: var(--r-md);
  background: var(--media-bg);
}
.movie-facts {
  color: var(--fg-muted);
  font-size: var(--text-sm);
  overflow-wrap: anywhere;
}
.movie-file {
  color: var(--fg);
  font-family: var(--font-mono);
}
.movie-body > :not(.movie-figure) {
  margin-block: var(--s-4); /* a fetch trouble in place of the figure */
}
@container (width < 30rem) {
  .movie-body {
    padding-inline: 0;
  }
  .movie-figure {
    padding-block-start: 0;
  }
  .movie-frame video {
    border-radius: 0;
  }
  .movie-figure > :not(.movie-frame),
  .movie-body > :not(.movie-figure) {
    margin-inline: var(--s-4);
  }
}
```

- **The focus ring is not clipped.** No ancestor of the `<video>` up to the panel sets `overflow`. The radius sits
  on the video itself, which clips its own picture. The mock's `overflow: hidden` frame hid the outline.
- **No sticky heading over the player.** Chapter panels keep theirs; the movie section is short, and a sticky
  heading would cover the picture and could hide a focused control (the keyboard requirement).
- **One token.** `tokens.css` gains `--media-bg: light-dark(oklch(0% 0 0), oklch(0% 0 0));` under Neutrals, with
  the comment "behind a video picture: black in both schemes, as every player letterboxes". Whichever of this
  change and `clip-preview-screen` lands first adds it, with exactly this value and comment; the other finds it. It keeps the file's
  rule that every color is one `light-dark(<light>, <dark>)` value (`tokens.css:4-5`, `web/README.md` "Design
  system"), and its two halves are equal on purpose:
  - Native controls draw light glyphs that need a dark surround in the light scheme too. With no poster, Chrome's
    controls would be white on white.
  - Letterbox bands around a picture of other proportions read as part of the picture.

  `tokens.css` stays "the only place a color is chosen".
- **Measured widths** (mock, above): 768 × 432 at 1280, 673 × 378 at 768, edge to edge at 390 (356 × 200) and 320
  (286 × 161), with no horizontal scroll. The `svh` term matters only in short windows, such as a phone held
  landscape, where it keeps the native controls on screen.
- **Motion.** `movie.css` has no `transition` and no `animation`, so the motion grep prints nothing for
  `web/src/movie`. The native controls' own fading is the browser's. No autoplay; with no autoplay there is nothing
  for reduced motion to stop.
- **Touch.** Both actions are `.btn`, so the coarse-pointer 44 × 44 areas and the `alert-action` row gap apply as
  they are. The native controls size themselves for touch.

**Rationale**: The section reuses the panel, pill, alert and button primitives. Only the frame is new, and only one
color, a deliberate constant.

### Edit mode, re-reads and other screens

**Decision**:
- **Edit mode** unmounts `ReadyView`, and with it the player, which stops playback. Leaving Edit mode runs a plain
  read, which mounts the section again, paused at the start. This is the existing seam (C4/C5); the change adds
  nothing to it. M3 (`clip-preview-screen`) owns playback in Edit mode.
- **Quiet reads** keep the section. Its probe decides whether the player stays (same version) or is replaced (a new
  one).
- **Refresh** is a plain read: placeholders replace the content, so the section, and playback, start over. The
  spec states this rather than promising a kept player across a Refresh.
- **The event list** has no player, and no change.

**Rationale**: The movie is a reading of the event as rendered. The editor is about the document, and its preview is
D-16's.

### Captions and chapters

**Decision**:
- **No captions.** No `<track>`, so the native controls show no captions button. axe reports `video-caption` as
  "needs review" (incomplete), never as a violation (spike). The verification records it and requires zero
  violations.
- **No chapter list.** The movie has real chapters, but no client-side source of their times exists.

**Rationale**: Home video has no caption source, and auto-reel writes none. Recording chapter times at render time
is an engine change for the manifest, and then a field M1's route or the detail could carry: a v2 item beside the
proxy work (supervisor decision). Neither belongs in a web-only change.

### HLD: D-15

**Decision** (task 3.2): `docs/high-level-design.md` gains, after D-14:

> - **D-15 — The event page plays its rendered movie in GUI v1** (2026-10-01, change `movie-player-screen`). The
>   event page's read view shows the movie the staleness gate counts (`GET …/movie`, `media-endpoints`) in the
>   browser's native player, says whether it is current or outdated, and names its file and size. It loads none of
>   the movie until Play (`preload="none"`; the poster is the first played clip's thumbnail). Its address carries
>   the file's entity-tag as `v`, read with a one-byte range request on each read of the event, because Chrome
>   fails to play a replaced file at an address that served the old one. Failures are said by cause, including a
>   picture the browser cannot show (a legacy MPEG-4 movie plays its sound only). There are no custom controls or
>   shortcuts, no captions and no chapter list: the manifest records no chapter times and browsers expose none.
>   Chapter times in the render manifest and a movie version in the event detail are v2 items beside the proxy
>   work. A Refresh stops playback in v1. Edit mode shows no movie. (§4.10)

§4.10's v1 bullet gains "**the rendered movie on the event page** (**D-15**)". Slice row C gains "`movie-player-screen`
plays the event's rendered movie (D-15)". M1 adds §4.10's dated sentence on A and B. This task keeps it and
re-reads §4.10 on `main` first.

**Rationale**: The decision outlives the change: why `preload="none"`, why the probe, and why no chapters. A later
change (chapter times, or a movie version in the detail) needs to find it.

### File ownership

**Decision**:
- **New, owned here:**
  - `web/src/api/movie.ts` and `web/src/api/headers.ts`
  - `web/src/movie/MoviePanel.tsx` (with `MoviePlayer` inside), `web/src/movie/labels.ts` and
    `web/src/movie/movie.css`
- **Edited, localized:**
  - `web/src/events/EventDetail.tsx`: one import, and `<MoviePanel eventId={eventId} event={event} />` as
    `ReadyView`'s first child
  - `web/src/styles/tokens.css`: one token, with its comment, unless `clip-preview-screen` has added it already
  - `web/README.md`: the screens paragraph, the file tree, "Design system" (the token, and the frame's colour
    being a constant), and "Checks" (the movie is checked with Chrome or Firefox, never Playwright's bundled
    Chromium, which cannot decode H.264)
  - `docs/high-level-design.md`: D-15, §4.10's v1 bullet and slice row C
- **Not touched:** `package.json`, the lockfile, `ui/*`, `edit/*` (`cross-chapter-drag` and M3), `jobs/*`,
  `cuts/*`, `api/event*.ts`, `api/thumbnail.ts`, `openapi.json`, `schema.d.ts`, every Python file.

**Rationale**: M3 adds a clip player under `preview/`. Keeping this one in its own `movie/` directory, with its own
address module, keeps the two changes' files apart. Their trouble words are deliberately different vocabularies.
Both have a one-byte probe with the same answer mapping: whichever lands second reuses the other's status
mapping (task 1.1), and the response-to-kind table stays identical.

### Verification fixtures

**Context**: The dev library's movies are real renders of 6 s clips (9–28 s). The spec also needs a longer movie, a
legacy movie, a replaced file, and the three probe failures.

**Decision**: Fixtures are ad hoc, only in this agent's library copy (`dev-movie-player-screen`, port **8130**,
database `arel_movie_player_screen`), never committed, and never in `auto-reel-media/` (whose samples are only
symlinked):
- `2022/2022-05-19 - Provklipp`: `a-msnv.mp4` → `samples/h264-720p25-aac-msnv.mp4`, `b-1080p25.mp4` →
  `samples/h264-1080p25-aac.mp4`, `Sony/c0048.mp4` → `samples/sony-xavc-1080p25-pcm.mp4`. Rendered with
  `auto-reel render <library> -o <library-output> --years 2022`. This gives a 75 s movie with chapters, whose PCM
  source is AAC in the movie.
- `2016/2016-12-24 - Julafton - Tjörn`: `clip.mp4` → `samples/h264-720p25-aac-msnv.mp4`, and
  `library-output/2016/2016-12-24 - Julafton - Tjörn.mp4` → `samples/legacy-render-mpeg4-mp3.mp4`. Adopted with
  `auto-reel adopt-renders <library> -o <library-output> --years 2016`.
- Probe failures, each made and undone around its own check, on `2024-07-14 - Kalas`:
  - **404:** move the movie aside and `mkdir` a folder in its place
  - **502:** `chmod 000` the movie
  - **unanswered:** `page.route` aborts the probe
- A replaced file: `os.replace` of Provklipp's movie by a copy of Grillning's, undone afterwards.
- A render from elsewhere: `POST /api/v1/jobs` with `{"event_id": "2024/2024-06-21 - Midsommar - Dalarna", "force":
  true}` and a worker (`auto-reel worker <library> --device cpu`). `make_dev_library.py` leaves a queued `2024/Blandat` job with
  no worker, so that job is cancelled first (`auto-reel jobs cancel <library> <id>`): otherwise the worker renders
  Blandat too, and Blandat, a "no movie" fixture, gains a movie and a rewritten `reel.yaml`. For the cancelled
  case, on `2024-06-27 - Grillning med grannar`, no worker runs while the job is queued, and `POST
  /api/v1/jobs/{id}/cancel` follows. Neither runs on Kalas: `POST /api/v1/jobs` refuses it with 409
  `output_collision`, because `2024-07-14 - kalas` claims the same file (`jobs-project-guards`). Grillning's 24 s
  movie outlasts the cancel check; Midsommar's runs 6 s.
- **Browsers:** Chrome (channel `chrome`) for every playback check, in the mandated container with
  `playwright install chrome`. One Firefox pass covers what differs: the PCM-sourced movie plays its sound, Space
  plays, and nothing scrolls sideways.

**Rationale**: Each fixture makes one spec scenario observable. None changes the shared script or another agent's
library.

## Failure behavior and idempotency

- **The page never fails because of the movie.** The event read and the probe are independent. A failed probe
  changes the section, and nothing else.
- **No writes.** The probe and the player send only `GET`. The page writes nothing; M1's routes write nothing.
- **Re-reads are idempotent.** The same file gives the same tag and the same address. A quiet re-read also keeps
  the same player, so playback and the browser's cache survive. A Refresh remounts the section (above): playback
  stops, the new player is paused at its start, and the browser's cache for the unchanged address still serves.
- **A render while the page is open.** The worker's atomic finalize means the probe sees either the old file or the
  new one, never a partial one.
  - If the old player is playing when the file is replaced, Chrome may fail first (`changed`, "Load the new
    movie"). The quiet re-read that follows the job's end then replaces the player anyway.
  - Firefox keeps playing what it buffered until the re-read replaces the player.
- **`--force`, worker restarts and the queue** do not apply to a read. A restarted service answers the next probe;
  an in-flight probe that dies is `unreachable`, and Refresh repeats it.
- **No `RENDER_GRAPH_VERSION` bump**, no API change, no migration.

## Risks / Trade-offs

- **[The duration is unknown before Play]** Chrome shows `0:00` and Firefox `0:00 / 0:00` until the operator plays.
  → Accepted: the only cheap fix is a probe of the movie (§4.9) or the bytes `preload="metadata"` costs.
- **[A soft poster]** A 320 × 180 thumbnail upscaled to at most 768 × 432. → Accepted for v1: event poster frames
  are a v2 item (§4.10), and the poster is decoration.
- **[A playing movie stops when a render replaces it]** The new player starts paused at 0. → Accepted and
  deliberate: the old file is gone, and Chrome cannot keep playing it. Focus is kept, and the render region shows
  the job as rendered.
- **[A probe per read]** It costs one request (p50 2.6 ms locally). On the USB archive the route's lookup costs more,
  as M1's Risks note. → Accepted: it is one lookup and a stat per read, the same order as the detail read itself.
- **[Browser-specific keys]** Chrome and Firefox seek by different steps. → Accepted: native behavior is what each
  browser's users know. The spec requires only what both share.
- **[axe's `video-caption`]** It stays "needs review". → Accepted: there is no caption source, and the verification
  records it.
- **[Chrome's per-URL media state]** The spike showed that `Cache-Control: no-cache` does not stop Chrome from
  failing on a replaced file in a new element at the same URL, although the service sent it only the new file's
  bytes. → The address-per-version rule avoids it for the movie.
  M3's clip URLs carry the clip's `mtime` as `v`, which changes with the file. M1's research note
  (`docs/research/browser-playback.md`, its task 5.1) records this browser fact.
- **[M1 lands with different names]** → Task 1.1 checks the path, `v`, the headers and the statuses in the
  regenerated schema and against a running service. It stops and reports on any difference rather than renaming
  here.

## Migration Plan

- Rebuild `web/dist` with the `web/README.md` container command. No new package, so no `npm ci` is needed beyond the
  worktree's first one.
- Nothing is migrated. Rollback: revert the web change and the token; M1's routes stay usable by curl.

## Open Questions

None that change the specs, the approach or the tasks. Deferred, by supervisor decision:
- **A movie version in the event detail** (size and mtime, a stat) would remove the probe. With chapter times in the
  render manifest, it is a v2 item beside the proxy work.
- **Keeping a playing movie across a Refresh** needs `load()` to keep `ReadyView` mounted: a follow-up.

## Implementation deviations (accepted by the supervisor, 2026-10-01)

1. **A `<div className="movie-figure">`, not `<figure>` with `<figcaption>`.** The section's first sketch put the
   outdated sentence and the trouble alerts after the `<figcaption>`, which HTML does not allow: a `figcaption` is
   the first or last child of its `figure`. The `<video>` is named by the heading, so the figure added no meaning.
   The markup above shows the shipped form.
2. **Task 5.1's teardown** (stop `serve`, drop the database, remove the dev library) runs in the supervisor's
   cleanup step after the PR is merged, not inside the validation task, so the library stays available for review.
3. **The verification container** is the prebuilt Chrome image the supervisor named (`localhost/playback-research:
   chrome`, the Containerfile of `docs/research/browser-playback.md`) rather than `playwright install chrome` on
   each run, and the scripts send their `POST /api/v1/jobs` with Python's `urllib` from that container, not curl.
4. **Focus after a note replaces the player** moves to the note's wrapper when focus was anywhere in the player
   (the `<video>`, or a trouble note's Download or Load action), not only on the `<video>`. Likewise a new version
   takes focus to the new `<video>` when focus was anywhere in the old player.

Verification findings worth keeping for the next player change (`clip-preview-screen`):
- Any catch-all Playwright route (`**/*`, or a URL predicate) makes Playwright intercept the media range requests,
  and Chrome's playback then stalls at `currentTime` 0. The scripts route only the write endpoints
  (`**/api/v1/jobs`, `**/api/v1/jobs/**`, `**/reel`) to abort unintended writes, and log every request passively.
- With Playwright's sync API, `time.sleep` delivers no events: a request log read after it misses what happened
  during it. The scripts wait with `page.wait_for_timeout`.
- Chrome draws its native loading arc over the poster for a moment after the player mounts with its `src`
  (`networkState` 1, `readyState` 0, no request); it is gone within 1.5 s.

## Review fixes (2026-10-01, before the PR)

The review found no blocker; its minor findings changed this behaviour, recorded in the spec as well:
- **Focus is never dropped, in every direction.** `sectionHasFocus()` covers the player and the note in its place.
  A player that replaces a focused note (a re-read's probe answers `ok`) takes the focus, as a note that replaces
  a focused player already did. When a re-read finds no rendered movie and the section unmounts while it holds
  focus, a layout-effect cleanup (it runs while the section is still in the document) moves focus to the page's
  `h1`.
- **The no-picture warning is announced.** A polite live region that appears already filled is often not spoken,
  so `MoviePlayer` keeps an empty visually hidden `role="status"` paragraph mounted, which receives the title; the
  visible Alert is a `note`. This follows `ToastRegion` and `jobs/announce.ts` ("the region exists before its
  first message").
- **The ring on every Tab stop.** `:focus-visible` matches only the player's first stop. `.movie-frame
  video:focus-within` draws the same 2px ring on the native controls' inner stops (Chrome 7 once loaded, Firefox
  7). A pointer click on a control shows it too, which reads as the player's selection, so it is not limited.
- **Recovery after a playback error.** `cannot_play` offers "Try again" beside the download. It bumps an attempt
  counter in the player's key: a new paused player at the same address, focused. MediaError 2 (a network error) is
  `load_failed`, "The movie could not be loaded.", not the browser's inability. A real code 2 is hard to provoke
  on localhost (Chrome has the whole movie buffered), so the check simulates the element's `error` with code 2
  and lets the page's real diagnosis probe decide the words.
- **`MOVIE_AGE_LOOK` reuses `VERDICT_LOOK.fresh` and `.stale`**, so the Movie pill and the render region's pill
  cannot drift apart.
- `web/README.md`: the event page's sentence lists the Movie section in order, and its details are sentences of
  their own.

Verified with `check_review.py` (Chrome image and Firefox, 20 checks), and the earlier `check_read.py` (162),
`check_play.py` (19 + 9 for the render) and `check_fail.py` (30) re-run green. Firefox, on a page with nothing
focusable after the player, keeps `document.activeElement` on the `<video>` once Tab passes its last control
(focus moves to the browser's own interface); on a bare page with a button after the player, Tab leaves it after
7 stops.
