## Why

Three findings from the 2026-10-02 bug triage (verified on `main` 6a7fe16) are the web client's playback and
notice behaviour on the event page. They share one screen (`EventDetail.tsx`, its Movie section and its clip
thumbnails) and one capability (`web-app`), and each leaves the operator with a worse picture than the
service gave:

1. **Refresh stops the movie that is playing** (`refresh-stops-movie-playback`). The operator's Refresh calls
   a plain `load()`, which sets the page state to `loading`. That unmounts the whole `ready` subtree, `ReadyView`,
   `MoviePanel` and its `<video>`, so a movie playing at 3:20 is torn down to read an event that, nearly
   always, has not changed. The spec states this as the accepted v1 behaviour ("It therefore stops playback"),
   and HLD D-15 repeats it ("A Refresh stops playback in v1"). It was a shortcut of `movie-player-screen`, not a
   requirement anyone needs: the Movie section already survives a re-read that finds the same entity-tag when
   the page re-reads in place, so keeping it through a Refresh costs nothing the player does not already
   handle.
2. **A chapter's title card is dropped by a whole-clip cut, and the cut editor does not say so**
   (`whole-clip-cut-drops-chapter-title-card`). The engine half is the merged gate change
   `title-card-whole-clip-cut`: when a cut covers a chapter's title clip entirely, the title card now moves to
   the chapter's next clip that plays. The cut editor's hint still says only that "a cut over the whole clip
   leaves the clip out of the movie" (`web/src/cuts/times.ts`, `CUT_HINT` and `lengthHint`), which is no longer
   the whole truth: the operator is not told what happens to the chapter's card.
3. **A service-wide thumbnail fault looks like a row of broken clips**
   (`thumbnail-failures-not-cached-and-service-wide-502`). `ClipThumb.tsx` maps every `<img>` error to the same
   neutral "No preview" box, "with no alert and no retry". The service already tells a clip's own failure from
   its own (a 502 with `thumbnail_failure: thumbnail_failed`, versus a 502 with no kind for a cache or
   `config.yaml` fault), but the page cannot read the 502 behind an `<img>`. With an unwritable thumbnail
   cache every box reads "No preview", the operator suspects every clip, and nothing says to look at the
   service. The engine half (the failure marker that makes a second request for a failing clip cheap) is the
   merged gate change `thumbs-sidecar-metadata`.

It belongs to HLD §6 phase 8 (GUI v1) as polish of D-11 (thumbnails), D-14 (cuts) and D-15 (the movie player),
and depends on no §8 research item. Its design reasoning for item 1 is in `design.md`: it deliberately differs
from the triage's sketch (a quiet Refresh) because a quiet Refresh would put the earlier state of the event on
screen as current, which "A read in progress is shown as a placeholder and announced" forbids.

## What Changes

- **Refresh keeps the Movie section's player.** While an operator's Refresh reads the event, the page keeps the
  "Movie" section it was showing, with its `<video>` as it is (same element, playing or paused, same position),
  and replaces the rest of the page's content with placeholders as today. The section shows only its heading
  and its player meanwhile: its verdict, file facts and outdated sentence belong to the earlier read and are
  hidden until the read answers. The read's answer then keeps the player (same entity-tag), replaces it (a new
  render) or removes the section (no movie, or a failed read), as every read already does. Opening the page and
  leaving Edit mode are unchanged: they still show placeholders and a new player paused at its start.
- **The cut editor says where a whole-clip cut sends the title card.** The hint under the Cuts fields (before
  and after the clip's length is known) adds that when the clip is its chapter's title clip, the chapter's
  title card moves to the next clip of the chapter that plays.
- **A page-level "Previews are unavailable" note.** For each thumbnail that fails to show, the page makes one
  further request for the same address to read the answer. A 502 with no thumbnail failure kind is counted by
  its `failure` field; a `thumbnail_failed` 502 (the clip's own), any other status or no answer is counted
  nowhere. At three or more thumbnails with the same counted answer the page shows one quiet note, in the read
  view and in Edit mode, saying that previews are unavailable and where to look (`auto-reel thumbs`). Rows keep
  their neutral "No preview" box and the note is never an alert or a toast.
- **Spec and docs:** four MODIFIED requirements in `web-app` (see Capabilities); HLD D-15 ("A Refresh stops
  playback in v1"), D-11 and D-14 are brought in line.
- **Tests:** node unit tests (`npm test`) for the pure parts (the failed-thumbnail reader, the counting rule and
  the cut hints), real-browser Playwright checks from the session scratchpad (never committed), `tsc --noEmit`
  and `npm run build`.

### Rendered output, fingerprint, schema

None. The client is the only package touched: no engine code, so `RENDER_GRAPH_VERSION` is unchanged (the
engine bump for item 2 is in `title-card-whole-clip-cut`) and the staleness fingerprint inputs are unchanged. No
`reel.yaml` or `config.yaml` change, no Alembic migration, no rescan. The OpenAPI document and `schema.d.ts`
are untouched: the page reads `thumbnail_failure` and `failure` from the problem body the generated types
already declare. No new dependency.

### Packages and surfaces

`web/` only. The CLI and the API gain nothing (Principle V holds: no behaviour is added to `api/`).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `web-app`:
  - "The event page plays the event's rendered movie": a Refresh keeps the player.
  - "A read in progress is shown as a placeholder and announced": the player is the second exception, and shows
    nothing of the earlier read meanwhile.
  - "Thumbnails never hold up or break a page": the page-level note, and the one further request that reads why
    a thumbnail failed.
  - "Edit mode lists, adds and removes a clip's cuts": the hint says where a whole-clip cut sends the title card.

## Non-goals

- **A quiet Refresh** (keeping all content, marked as updating). It would show a stale clip table, verdict and
  facts as current while the operator waits for the answer to the very question Refresh asks. See `design.md`.
- **Keeping playback through Edit mode.** Edit mode shows no Movie section and, by "Edit mode previews a clip on
  request", holds at most one video element, a clip's preview. Entering Edit mode still ends the movie, and
  leaving it still returns a player paused at its start. The triage's sketch to keep a hidden player would
  contradict two scenarios of that requirement ("the page holds no video element") for little: a movie that
  keeps sounding behind a hidden mode cannot be paused, and one that is paused there only keeps its position.
- **Any engine, API or schema change**: the title-card re-anchoring is `title-card-whole-clip-cut`; the failure
  marker is `thumbs-sidecar-metadata`; no new failure kind is added by either.
- **Telling a broken ffmpeg from a broken clip.** The engine reports a missing or broken ffmpeg binary as each
  clip's own `thumbnail_failed` (`thumbs-sidecar-metadata`, design), so it raises no note. Reclassifying it is an
  engine decision.
- **A note for pages with fewer than three previews.** The threshold is a constant of three; a one- or
  two-clip event whose cache is unwritable keeps its boxes and no note.
- **A retry control, a dismiss control or a per-clip reason** for failed thumbnails.
- **The cut editor knowing which clip is a title clip.** The detail does not carry it (`is_title` is a render
  plan fact); the hint is conditional and the same for every clip.

## Impact

- `web/src/events/EventDetail.tsx` (state, the Movie slot, the note), `web/src/movie/MoviePanel.tsx` and
  `web/src/movie/movie.css` (the reading state), `web/src/events/ClipThumb.tsx`, `web/src/events/thumbs.css`,
  a new `web/src/events/thumbHealth.ts` (a counting hook and context), `web/src/api/thumbnail.ts` (the probe of
  a failed address), `web/src/events/labels.ts` (the note's words), `web/src/cuts/times.ts` (the two hints),
  `web/README.md`.
- `docs/high-level-design.md`: D-11, D-14, D-15.
- Gates (merged before this change is implemented): `title-card-whole-clip-cut`, `thumbs-sidecar-metadata`,
  `api-excluded-clips-read-model` and `api-job-summary-and-renamed-fields`. The last two edit `EventDetail.tsx`
  (`ReadyView`, `ChapterPanel`, the render panel and `Counts`), so this change is written against the file as
  they leave it and keeps its own edits to the page's state, its Refresh handler and its main's top level.
