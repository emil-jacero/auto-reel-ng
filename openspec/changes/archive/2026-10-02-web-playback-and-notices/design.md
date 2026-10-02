## Context

See `proposal.md` for the three findings. All three live in the web client; none changes what the service
sends. The current state, re-checked against `main` 6a7fe16:

- `EventDetail.tsx` holds `LoadState = loading | ready | failed`. `load()` (first read, Refresh, the read after
  leaving Edit mode) sets `loading`, which drops the `ready` subtree: `ReadyView`, which renders `MoviePanel`,
  which renders the `<video>`. `load({ quiet: true })` (a job finishing) keeps `ready` and sets `updating`, and
  `MoviePanel`'s effect (`[eventId, event]`) then probes the movie again; the same entity-tag keeps the player
  (`MoviePlayer` is keyed by version).
- Edit mode swaps `ReadyView` for `EventEditor` inside the `ready` branch.
- `ClipThumb.tsx` renders `<img>` and maps `onError` to one neutral box. The service answers a clip's own failure
  as 502 with `thumbnail_failure: "thumbnail_failed"` and a cache or `config.yaml` fault as 502 with neither
  that field nor `failure` (`api/routes/events.py`: `_clip_failed` against `_thumbnail_failed`; `schema.d.ts`
  documents the split). `ProblemOut` already declares both fields, so no type changes.
- The cut editor's two hints are the constants `CUT_HINT` and `lengthHint(length)` in `cuts/times.ts`.
- `.page` and `.page-content` have the same `gap: var(--s-5)`, so a section moved from `.page-content` to be a
  direct child of `<main>` keeps its distance from its neighbours.

Gates, all merged before this change is implemented: `title-card-whole-clip-cut` (the hint's claim becomes true),
`thumbs-sidecar-metadata` (a failing clip's 502 is answered from a 60 s marker with the same kind, so the
further request below is cheap and carries the same classification), `api-excluded-clips-read-model` and
`api-job-summary-and-renamed-fields` (both edit `EventDetail.tsx`; this change touches its state, its Refresh
button, the top level of its `<main>` and `ReadyView`'s first child, and nothing they add).

## Goals / Non-Goals

**Goals:**
- A Refresh never stops, seeks or reloads a playing movie when the movie is still the same file.
- No earlier fact of the event is shown as current while a Refresh reads.
- The operator learns that "No preview" is the service's doing when it is, once, without alarm.
- Rows, the Edit-mode preview rules and every existing read keep their behaviour.

**Non-Goals:** as in `proposal.md` (a quiet Refresh, playback through Edit mode, any server change, a note for
pages with fewer than three previews, a retry control).

## Research & Decisions

### A Refresh keeps the Movie section, not the whole page
**Context**: `refresh-stops-movie-playback`. The triage's sketch is to route the manual Refresh through the
quiet path (`updating`), keeping `ReadyView` mounted, and to keep `MoviePanel` mounted but hidden in Edit mode.
**Explored**: `web/src/events/EventDetail.tsx` `load()`; the spec requirements "A read in progress is shown as a
placeholder and announced" (placeholders "SHALL NOT show an earlier state of the screen as current"; the quiet
re-read is the one exception, and only for reads the client starts by itself), "A shown screen re-reads in
place when events change" ("Unlike a first read or an operator's Refresh") and "Edit mode previews a clip on
request" ("Edit mode never holds more than one video element"; two scenarios say "the page holds no video
element"). A quiet Refresh would also be the read after leaving Edit mode, whose content (the clip table, the
verdict) is by definition older than the save that was just made.
**Decision**: keep the operator's Refresh as a placeholder read, and keep only the Movie section through it. Edit
mode is left as it is.
**Rationale**: the bug is that the player dies, not that the table flashes. A quiet Refresh would change three
requirements and make the one read an operator asks for the one that shows old data as current; the same
mechanism could not serve the leave-Edit read at all. A hidden Edit-mode player contradicts the one-video rule and
the two scenarios, and cannot honour "Playback SHALL start only from the operator's action": a playing hidden
movie cannot be paused, and a paused one gains only its position. The cost of the chosen route is one visible
trade-off, below.

### State: `loading` carries the event whose Movie section stays
**Context**: the player must outlive the `loading` state, which drops everything.
**Decision**: `loading` gains an optional `movie`, and the Movie section moves from `ReadyView` to a fixed slot
in `<main>`, between the header and the page's content.
```ts
type LoadOptions = { quiet?: boolean; keepMovie?: boolean }
type LoadState =
  | { status: 'loading'; editPlace: boolean; movie?: EventDetailData }   // movie: the section that stays
  | { status: 'ready'; event: EventDetailData; fetchedAt: Date; updating?: boolean }
  | ({ status: 'failed' } & Failure)

// in load(), the non-quiet branch:
{ status: 'loading', editPlace: …, movie: options.keepMovie && shown.status === 'ready' ? shown.event
                                           : options.keepMovie && shown.status === 'loading' ? shown.movie
                                           : undefined }
// the Refresh button: requestLeave(editing ? leaveEditMode : () => load({ keepMovie: true }))
// render, in <main>, after <header>:
// {movieEvent !== undefined && !editing && <MoviePanel eventId event={movieEvent} reading={loading} />}
//   movieEvent = ready ? state.event : loading ? state.movie : undefined
```
Only the Refresh button passes `keepMovie`; the mount read and `leaveEditMode` do not, so opening the page and
leaving Edit mode still show placeholders and a new player (the spec keeps both). A `failed` result drops the
event, so a failed read removes the section with the rest (`MoviePanel`'s existing layout cleanup moves focus
to the `<h1>` when the section held it). `ReadyView` no longer renders `MoviePanel`; its other children are
untouched. React keeps the element because the slot, the component type and the (absent) key do not change
between `ready` and `loading`; `MovieSection`'s effect depends on `event`, which is the same object while the
page reads, so no probe runs until the read answers, and then the existing rules apply: same entity-tag keeps the
`MoviePlayer`, a different one replaces it, no movie or a failed probe shows the existing note.
**Alternatives**: hoisting the `<video>` into a portal or a ref held by `EventDetail` (more machinery for the
same effect); a separate `movie` state beside `state` (two states that must be set together at every `setState`
in `load()`).

### The reading state of the section
**Context**: while the page reads, the section must not show an earlier verdict ("Current") or earlier facts.
**Decision**: `MoviePanel` takes `reading: boolean`. When set, the `<section>` carries `aria-busy` and
`data-reading`; `movie.css` sets `visibility: hidden` on the age pill and on every `.movie-facts` paragraph of
`.movie-panel[data-reading]`. The heading, the frame and the `<video>` are untouched.
**Rationale**: `visibility: hidden` keeps the layout (the page below does not jump when the answer returns) and
removes the text from the accessibility tree, so nothing stale is read out. The poster is the first played
clip's thumbnail from the earlier read; it is part of the player and is not a fact that the read can make
wrong in a way the operator could act on (the poster is replaced with the player on a new version anyway).

### The cut editor's words
**Decision**: both hints end the whole-clip sentence the same way. In `CUT_HINT`, "… and a cut over the whole
clip leaves the clip out of the movie. If it is its chapter’s title clip, the chapter’s title card moves to the
next clip that plays." In `lengthHint`, "… a cut must end by then, and a cut over the whole clip leaves the clip
out of the movie. If it is its chapter’s title clip, the chapter’s title card moves to the next clip that
plays." The second form is new for the known-length hint, which today does not say the card's fate but does say
the clip's.
**Rationale**: `ClipOut` carries no `is_title` (the title clip is resolved by the render plan, `event/resolution`
`_resolve_title`, with `title:` overrides), so the page cannot say it for a particular clip. A conditional
sentence is true for every clip, and the engine rule it describes (card before the chapter's first surviving
segment; none for a chapter with nothing left) is that of `title-card-whole-clip-cut`.

### How a failed thumbnail's cause is read
**Context**: `<img>` exposes no status and no body. `PerformanceResourceTiming.responseStatus` would give a 502
but not the kind that separates a clip from the service.
**Explored**: (a) loading every thumbnail with `fetch` and an object URL: it removes native lazy loading and the
browser's image cache handling and would put every success on a path that today is free; (b) the timing entry:
status only; (c) one `fetch` of the same address, only after an `<img>` error.
**Decision**: (c). `api/thumbnail.ts` gains the reader and the classification:
```ts
export type FailedThumbnail =
  | { kind: 'clip' }                        // 502 + thumbnail_failure: 'thumbnail_failed'
  | { kind: 'service' }                     // 502 with neither thumbnail_failure nor an event `failure`
  | { kind: 'unknown' }                     // any other answer (a 502 with `failure`: the event itself
                                            // could not be read), none, or a 200 (it works now)
export async function readFailedThumbnail(url: string, signal: AbortSignal): Promise<FailedThumbnail>
```
It uses `fetch(url, { cache: 'no-store', signal, priority: 'low' })` (behind the page's own requests, like the `<img>`), reads the JSON problem body of a 502 (`isProblem`,
`readJson`), cancels the body of any other answer unread, and never throws except `AbortError` (an abort is a
box that left the page, not an answer).
**Rationale**: the extra request exists only for a box that already failed, and the 60 s marker of
`thumbs-sidecar-metadata` answers a clip's own failure without a process; a cache fault fails before any
extraction. A page of 400 clips with a dead cache makes at most as many extra requests as it made failing ones,
and only for rows near the view (native lazy loading). The reading is not a retry: its answer is never shown as
an image, so "no automatic retry while the row stays shown" holds for the image.

### Counting: a context of the currently shown failures
**Decision**: `events/thumbHealth.ts` exports `useThumbHealth()` and a React context. The page holds a
`Map<src, key>` in state. A failed `LoadingThumb` runs an effect: read the answer; for a `service` answer
`report(src, SERVICE_CAUSE)`; on cleanup (unmount, new `src`) abort and `clear(src)`. The note is shown when any key
has at least `THUMB_NOTE_AT = 3` entries.
```ts
export const THUMB_NOTE_AT = 3   // a module constant, no config key
export type ThumbHealth = { report(src: string, key: string): void; clear(src: string): void }
export function useThumbHealth(): { health: ThumbHealth; unavailable: boolean }
```
`EventDetail` creates it, provides the context around its `<main>` content (so the read view's rows and Edit
mode's `ClipOrderList` rows report to the same page) and renders the note. `ClipThumb` outside a provider
reports to a no-op.
**Rationale**: counting what is mounted now makes the count correct without a reset rule: a Refresh drops the
rows and so the failures (the note leaves, and returns if the fault persists), entering Edit mode replaces the
read view's rows with the editor's (the same `src`s report again; keyed by `src`, nothing is counted twice), a
fixed cache plus Refresh clears it. The count is keyed by cause so that a cause added later never adds up with
this one; today the page has one, the service's. A 502 that carries an event `failure` (the event's `reel.yaml`
or folder became unreadable after the page loaded) is not counted: it would blame the thumbnail cache.
**Alternatives**: counting every non-`thumbnail_failed` failure under one key (merges unlike faults); a "first
failure decides" sample (a bad first clip would mask a service fault); sticky state with a reset on `load()`
(needs the reset to cover Edit mode as well).

### The note
**Decision**: one `Alert` with `tone="warn"` and `role="note"`, rendered in `<main>` straight after the Movie slot,
so it sits above the clips in the read view and in Edit mode (`labels.ts`: `PREVIEWS_UNAVAILABLE`, "Previews are
unavailable. The service could not make thumbnails; run `auto-reel thumbs` on the server to see why."). No
toast, no live region: the page already has "Reading event…" and "Updating…" as its announced messages, and a
missing preview is a convenience (the component header: "a thumbnail is a convenience").

## Failure behaviour, idempotency, concurrency

- Nothing here writes: no `reel.yaml`, no cache, no job. Every new request is a `GET` of an address the page
  already requested (Principle II; "Reading a screen never changes state").
- A Refresh pressed while a read runs is ignored, as today (`aria-disabled` while `loading`); one pressed while a
  quiet re-read runs aborts it (as today) and shows the placeholders with the section kept.
- A Refresh whose read answers 404, 502 or nothing shows the existing failure alert and removes the section; the
  player's media request, if any, is released with the element.
- An aborted further request (the box left the page) reports nothing. An answer that arrives after the box is
  gone is dropped by the effect's cleanup.
- Two Refreshes in a row, or Refresh then Edit: each is one `load()`; the section is kept only by the Refresh.
- No fingerprint input, schema, migration or `RENDER_GRAPH_VERSION` effect.

## Risks / Trade-offs

- **The marker's replay must carry the clip's kind.** If `thumbs-sidecar-metadata` answered a remembered failure
  without `thumbnail_failure`, every broken clip would count as a service fault after its first request. →
  Task 1.1 asks the running service for the same broken clip twice within 60 s and requires the kind both
  times; stop and report otherwise.
- **A stale poster or facts while reading.** The poster stays; the verdict and facts are hidden. → The poster is
  the player's, not the event's state; see "The reading state of the section".
- **One extra request per failed box.** → Bounded by the failed boxes near the view; cheap by the marker (clips)
  or by failing fast (cache). Not done for success.
- **A broken ffmpeg gives no note** (it is each clip's `thumbnail_failed`). → Out of scope; stated in the spec
  as "failures that are the clips' own SHALL never raise it".
- **A one- or two-clip event with a dead cache shows no note.** → The threshold of three is the triage's; a lower
  one would let one transient 502 claim "unavailable".
- **Merge shape with the two `EventDetail.tsx` gates.** → The task begins by re-reading the file on `main`; the
  edits are to `load()`, the Refresh `onClick`, the top level of `<main>` and `ReadyView`'s first child.
- **`visibility: hidden` on a pill that takes a tone from `data-tone`.** → Verified in light and dark at 1280 and
  390 in the browser check.

## Migration Plan

None: client code only, nothing persisted. Rollback is reverting the commit; the service is not involved.
HLD: D-15's "A Refresh stops playback in v1" becomes "A Refresh keeps the player; Edit mode shows no movie and
entering it ends playback"; D-11 gains a bullet for the page-level note; D-14's "a whole-clip cut leaves the clip
out" gains the title-card clause.
