## Context

See `proposal.md` for why. What this builds on:

- `web/src/movie/MoviePanel.tsx` (D-15): one `<video preload="none">` per file version (`key={version:attempt}`),
  `src` carrying the entity-tag as `v`, a `videoRef` already threaded to the player for focus, and `reading` that
  hides the facts while the page re-reads. Its facts line shows name and size from the one-byte probe.
- The two gates are in `origin/main` (archived 2026-10-03): `render-chapter-times` records each chapter's start
  (seconds in the rendered movie) and title-card span in `render-manifest.json`, `null` for an older manifest;
  `movie-facts-read` returns, in `EventDetailOut`, `movie`: `null` (no movie, or no usable record time) or
  `{ recorded_at, fingerprint, chapters }`, where `chapters` is `{ name, start }[]` or `null`/absent for unknown
  (a manifest from before chapter times, or an adopted movie), read-only and probe-free. `recorded_at` is when the
  render record was written (the render's finish, or the adoption's time), `fingerprint` the first 12 characters of
  the inputs' identity. A chapter's `name` is `""` for the event's default chapter (the page writes it "Main" or
  "Clips" as the event page does). These are the real names; the first draft of this design assumed others.
- Tests are `node:test` over pure `.ts` modules (`npm test`, `tsconfig.test.json`), as `cuts/times.test.ts`,
  `events/labels.test.ts`. There is no component test runner (D-8); behaviour in the browser is Playwright.
- Evidence relied on: the v1 playback research (`research/playback.md`): `preload="none"` makes zero requests
  and leaves `readyState 0` and `duration NaN` (so a jump before Play meets a player with no metadata); the v2
  synthesis (`research/v2/synthesis.md` §5, "Later or conditional" note: chapter times and the movie version
  are "not sequenced" with the proxy rows, so they are independent of them) and `timeline-library.md` (seek
  accuracy is browser-bounded and Firefox's length drifted up to 60 ms: the 60 ms slack below; the prototype's
  `list "Chapters"` accessibility tree is the model for the later chapter band, not for this list).

## Goals / Non-Goals

**Goals:**
- A keyboard- and touch-usable chapter jump list that is correct or absent, never guessed.
- One pure place that decides whether chapter data may be relied on and which chapter a position is in, so the
  later timeline chapter band (D-20) reuses it.
- The version of the movie visible next to its file facts.

**Non-Goals:**
- Chapter markers on the native timeline, `WebVTT` chapter tracks, captions: the browser's controls cannot
  show them reliably (D-15) and a track would be a second source of times.
- Proxies, the timeline, any `api/` change, any engine change, a new route.
- Comparing the detail's chapters with the event's current chapters (the list is the movie as rendered; the
  Outdated pill already says the event moved on).
- Keyboard shortcuts of the page's own (D-15 keeps none).

## Decisions

### D1. One accessor knows the detail's field names

`movie/facts.ts` exports `movieFacts(event: EventDetail): { chapters: ChapterMark[] | null; version:
MovieVersion | null }`, the only code that reads the generated field `event.movie` (and its `recorded_at`,
`fingerprint`, `chapters`). `ChapterMark = { name: string; start: number }`, `MovieVersion = { recordedAt: string;
fingerprint: string }`. The rest of the
client sees only these types, so a rename in the API is one `tsc` error in one file (as `api/movie.ts` does for
the movie route). *Alternative:* read the generated type in the component. Rejected: field names would spread
over three files and the validity rule below would have no home.

### D2. Reliability is decided once, in a pure function

`chapters.ts: usableChapters(raw): ChapterMark[] | null` returns the list only if it is non-empty, every start
is a finite number >= 0, starts strictly increase, and every name is a string that is empty (the default chapter) or not only whitespace; otherwise `null`. The
section shows nothing for `null`, and does not partly show a list (a list with one wrong start is worse than
none; Constitution I). *Alternative:* sort or drop the bad rows. Rejected: that is repair, i.e. guessing.
It does not require the first start to be 0 (a movie without a title card could start later) and does not check
against the player's duration (not known before Play, `preload="none"`).

### D3. The current chapter is a pure function of position

`currentChapterIndex(chapters, position, slack = 0.06): number | null`: the last index whose `start - slack <=
position`, or `null` before the first. The slack (1.5 frames at 25 fps, the order of the 60 ms Firefox drift the research measured) covers a seek landing a frame short, so that a jump to
a chapter's start never leaves the previous row marked after the seek lands a frame short. The player feeds it
from `timeupdate` and `seeked` (so a paused seek through the native controls updates it), kept in state as the
index, so a `timeupdate` that does not change the index does not render. `timeupdate` fires about 4 times a
second, which is the spec's half-second bound; no `requestAnimationFrame` loop. *Alternative:* mark by the
button last pressed. Rejected: wrong after the native controls move the position.

### D4. A jump is a seek plus play, safe at `readyState 0`

`jumpTo(video, start)`: if `video.readyState >= 1` set `currentTime = start` and `play()`; otherwise `play()`
(which loads the movie) and set `currentTime` once on the first `loadedmetadata` (a one-shot listener, removed
when the player unmounts or another jump replaces it). This does not rely on a browser keeping a "default start
position" set before metadata. A rejected `play()` promise is ignored when it is an `AbortError` (a newer jump
or a src change) and otherwise left to the `error` event the player already diagnoses. The click is the
operator's action, so D-15's rule that playback starts only from the operator holds; the spec says so.
Focus stays on the button (the list never calls `video.focus()`). *Alternative:* seek only, leave it paused.
Rejected: after pressing a chapter the operator expects to see it; pressing Play next is a needless step, and a
paused seek on a `preload="none"` player shows only the poster.

### D5. The list lives inside the player's figure, keyed with it

`ChapterList` is rendered by `MoviePlayer` (so it dies and is born with the `key` = file version/attempt; its
mark state resets with a new player), after the facts and before the trouble notes, only when `file !== null`
(a jump needs an address) and `usableChapters(...)` is non-null. It takes `chapters`, `videoRef`, `outdated`.
During `reading` the list is *not* hidden (unlike the facts): hiding would drop focus from a focused button, and
a re-read that changes the chapters also changes the file, which replaces the player anyway (its list with it).
A re-read that leaves a player without a list while focus is in the list: `ChapterList`'s layout-effect cleanup
moves focus to `videoRef.current` when it holds focus. On removal of the whole section `MovieSection`'s existing
cleanup (a parent, so React runs it before its children's) has already moved focus to the page heading, so the
list's cleanup then finds focus outside it and does nothing. Pinned by a Playwright check (task 4.1).

### D6. Markup and words

The default chapter's name `""` is written by `chapterHeading(name, hasNamed)` in `events/labels.ts`, which
`EventDetail` also uses, so the two screens agree. A `<div className="movie-chapters">` with `<h3>Chapters</h3>`, an `<ol>`, and
per row a `<li>` with one `<button type="button">` holding number, name, start (`<span>`s) and, when marked, the
`Pill`-style "Current chapter" with the icon from `ui/Icon`. The accessible name is set by `aria-label`: "Jump to
chapter 2, Majstången, at 1:14" (`jumpLabel()` in `chapters.ts`, tested), `aria-current="true"` only while
marked. The start is `formatTime` from `cuts/times.ts` (reuse; it prints the fraction only when present). No
live region. The "As rendered" caption sits beside the heading only when `age === 'outdated'`; its words are
`CHAPTERS_AS_RENDERED` in `labels.ts` (a plain string, as `OUTDATED_NOTE`).

### D7. The version in the facts

`movieVersionWords(version)` in `facts.ts`: "Recorded {formatInstant(recordedAt)} · version {fingerprint}"
with the exact instant in `<time dateTime>` ("Recorded", not "Rendered": `recorded_at` is the adoption time for an
adopted movie and the detail does not tell the two apart); a missing piece is left out (a version without a
parseable time shows only "version {fingerprint}"; no version, nothing). `formatInstant` already returns an unparseable value as given,
so no made-up time. It is a second `movie-facts` paragraph line (not the entity-tag `v`, which names the file on
disk; the two are different facts and the page keeps them apart).

### D8. CSS: no motion, container-sized

Rows are `display: grid` (`auto 1fr auto`), `overflow-wrap: anywhere` on the name, no `overflow` on any ancestor
of a button (the focus ring must not clip; the existing `.movie-frame` rule's reasoning). The mark changes a
background token and shows the word + icon; there is no `transition`/`animation` at all, so the `web/README.md`
motion greps pass trivially and `prefers-reduced-motion` needs no branch (verified under emulation anyway).
`@media (pointer: coarse)` raises the button's `min-block-size` to 44 px as the other movie controls do. Colours
come from tokens only (the README colour grep stays empty). The list is as wide as `.movie-figure`.

### D9. HLD

D-15's sentence "no custom controls or shortcuts, no captions and no chapter list: the manifest records no chapter
times and browsers expose none" is amended (dated, this change): the list exists when the detail gives chapter
times; still no captions, no shortcuts. §4.10's v2 sentence ("chapter times in the render manifest (a chapter
list for the movie player) and a movie version in the event detail") is marked delivered by
`render-chapter-times`, `movie-facts-read`, `movie-chapter-list`. D-20 gets one line: the timeline's chapter band
reuses `usableChapters`. D-21 is untouched (no proxy involved). §6's GUI v2 line gets a "chapter jump list
shipped" note. Done in the same change, in task 5.1.

## Risks / Trade-offs

- [The gates' field names differ from the assumed ones] -> D1 isolates them; task 1.1 stops if the detail does
  not carry both chapters and a version, rather than adapting the behaviour.
- [A jump at `readyState 0` is browser-dependent] -> the one-shot `loadedmetadata` path (D4) is the portable one;
  Playwright in Chrome 154 and Firefox >= 155 jumps before the first Play (task 4.1). If a browser needs more
  (a second seek after `canplay`) that is a task-4.1 finding to report, not a silent workaround.
- [Seek lands a frame short, marking the previous chapter] -> the 60 ms slack (D3), covered by a unit test at
  `start - 0.06`, `start - 0.061`.
- [The movie file was replaced after the detail was read, so times belong to the older render] -> the two reads
  are independent for one tick (probe vs detail); both are re-made on every read and the player is keyed by the
  entity-tag, so the window is the same one D-15 already has for the facts. The list carries no promise beyond
  "as rendered" and the version line lets the operator see it.
- [A legacy/adopted movie with a wrong `chapters` value] -> out of scope: `render-chapter-times` records `null`
  for what it did not compute; this page trusts the engine's `null` and shows nothing.
- [Long chapter lists (dozens of rows) push the chapters below down] -> accepted for a read view of events with
  a handful of chapters; no inner scrolling, which would clip focus
  rings and need motion handling. Revisit only on evidence.

## Open Questions

None that change the specs or the tasks. (Whether title-card spans deserve their own marker is for the timeline.)
