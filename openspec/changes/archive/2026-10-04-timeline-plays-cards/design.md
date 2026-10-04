## Context

The Timeline (`web/src/timeline/`) keeps **clip time** as the one time of the playhead, cuts, handles and marks; the
cards are only a drawing shift (`cards.ts`: `cardMap`, `trackX`, `clipTimeAt`, `trackLayout`). The playhead store holds a
`Position {clip, ms}`; `useTimelineVideo` owns the one `<video>`, swaps `src` at clip boundaries through the seek
coalescer and follows the frames with `requestVideoFrameCallback`, skipping cuts (`follow.ts`). The pointer handler in
`Timeline.tsx` turns a press inside a black card into a card selection and leaves the playhead alone. The page's
one-player rule (`playback/coordinator.ts`) is driven by the `play` event of a `<video>` and offers
`watchOtherStarts`. The inspector's preview (`edit/card/`) already calls `previewCard` with a debounced controller.

## Goals / Non-Goals

**Goals:** the Timeline shows and plays black and video cards like the movie; scrub and click work in a card; the
readouts count card time; blocks show their card; images are fetched politely and kept.

**Non-Goals:** see the proposal. No API change, no second video, no card sound.

## Research & Decisions

### One video, a card layer above it
**Context**: the card must replace the picture for its length and overlay it for a video card, without a gap at the hand-over.
**Explored**: `docs/research/` and the v2 synthesis (§3, the D-18 timeline decision, renumbered D-20) fixed one `<video>` with
a `src` swap and accepted a short flash; `title-card-blocks` and `title-card-over-video` (D-24) fix what a card is. A
canvas compositor, a second video and a pre-rendered card clip were considered.
**Decision**: the card is an `<img>` in a layer stacked over the same box as the `<video>` (same aspect box, `object-fit:
contain`), pointer-inert, `aria-hidden` (the readout and the slider carry the words). Opacity is set from the playhead
by a ref, not by React state, so a fade does not render the track. A black card hides the video by being opaque at
`opacity` 1 only; during its fade the page's dark player backdrop shows through, which is what the render's card on
black looks like (the render fades the card to black). A second video or a canvas would add a cost D-8 does not allow
for no gain.

### The card clock is the browser's frame clock
**Context**: nothing plays during a black card, so no media event advances the playhead.
**Decision**: a pure `play.ts` (stages, position on the track, opacity, hand-over, "time reached for an elapsed real
time", held to the length) and a small hook that drives it with `requestAnimationFrame` and `performance.now()`
deltas; elapsed time, not frame count, so a slow frame cannot stretch the card (a scenario tests it with an injected
clock). `document.hidden` pauses it. Pause stores the elapsed time; Play restarts from it.

### The hand-over is pre-seeked
**Decision**: when a card starts, and when a scrub or a seek lands in one, the hook asks the existing coalescer to
load and seek the hand-over clip at its first kept time while paused. When the card's time is up, if that seek has
completed the video starts and the card layer is removed on the first presented frame (`requestVideoFrameCallback`,
else `playing`); if not, the card holds its last frame (opacity 0 at its end is not applied past the length) until it
has. Evidence needed: the Playwright run must show no sampled frame of the page background between the two (a
scenario); a gap would show as a failed sample, not be hidden.

### The playhead in a card
**Decision**: `Position` gains an optional `card: { gap: number; ms: Ms } | null`; the `clip`/`ms` of a card position
are the anchor clip and 0 (its first kept time is *not* used, so the cut/handle consumers are unchanged and a card
position is "before the clip"). The slider's `aria-valuenow` is the track time including cards (already what the lane
uses). Frame steps use clip time and skip a card; seconds steps and Home/End use track time and may land in one.
Rejected: a separate card playhead (two playheads break the single-slider model and the readout).

### Card images: a sequential, polite fetch kept by key
**Context**: the endpoint allows two at once and answers 503 `Retry-After` beyond that (api-service, "The title-card
preview is bounded"); the inspector already holds one in flight for its own card.
**Decision**: a pure queue (`cardImages.ts`) keyed by `JSON.stringify(body + style)`: one request at a time, in play order,
503 waited out by its `Retry-After` (clamped 1 to 30 s, three tries), other failures said once and not retried; a
changed key enqueues only that card after the inspector's quiet time. Blob URLs are revoked on replace and on close. The
request body for a resolved card comes from the detail's `ResolvedCardOut` through the existing `previewRequest` (the
chapter name, the card's title, subtitle, background, duration and font); the draft style is passed only when it
differs from the saved one. The queue takes `fetch`, a timer and URL functions as arguments so `node:test` runs it.
The Timeline asks at one at a time, which leaves the other of the endpoint's two slots to the inspector.

### The fades are the engine's defaults
**Context**: `ResolvedCardOut` has no fade fields; `render/title/config.py` defaults are 2 s in, 2 s out, clamped so the
sum does not exceed the length.
**Decision**: mirror the defaults and the clamp in `play.ts`, name them and test them against the same numbers, and say the
limit (see Risks). Adding `fade_in`/`fade_out` to `ResolvedCardOut` would be an API change (a third package) and is a
follow-up.

### Coordinator
**Decision**: the card clock uses `watchOtherStarts` to pause when another video starts; the Timeline's own video is paused
during a card so `pauseOthers` has nothing to do for it. The Timeline's start during a card does pause other players
by the same rule as a start of its video: it calls the coordinator's pause-others with its own `<video>` as the starter
when the card clock begins.

## Risks / Trade-offs

- **Fade limit.** A project or event that sets `look.title_card.fade_in/out` plays on the Timeline with the default fades,
  and says so once. The picture is otherwise the render's.
- **A visible gap at the hand-over** if the proxy cannot be sought in time (a long GOP). Mitigation: pre-seek, hold the
  card until ready, and measure in both browsers; the proxy has `-bf 0` and a one-second GOP (D-21).
- **Preview cost.** N cards at one request each when the Timeline opens; the endpoint is light (no job slot, no
  ffmpeg). A long event with many chapters waits for them in order; the Timeline is usable meanwhile with the title
  on black.
- **A card in a cut-skipping play** is played whole; a cut cannot hide a black card, which sits before the footage.
- **Drift:** the card's wall-clock length and the movie's length differ only by the render's rounding to frames; the
  Timeline claims no frame accuracy in a card.
- **Bundle:** measure before and after and record it in the HLD note.
