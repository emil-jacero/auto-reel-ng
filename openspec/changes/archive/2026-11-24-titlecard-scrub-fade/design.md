## Context

The Timeline draws a title card as a layer over its 16:9 stage (`timeline-plays-cards`, HLD D-20):
- **A black card's span:** an opaque black `<div>` in which only the card's image (or, while the image is missing,
  its title) fades.
- **A video card's window:** a transparent layer, with the image laid over the playing video.

`CardLayer.tsx` reads the playhead's store itself (`useSyncExternalStore`), so a playing card re-renders the layer
and not the track. It is wrapped in `memo` (`1dfa9b83`, the zoom-slider memoisation).

How the opacity is computed today:

| Step | Where | What |
|---|---|---|
| The fades | `play.ts` `fadesOf(lengthMs)` | the 2 s defaults, scaled together so their sum fits the length |
| Opacity at a time | `play.ts` `opacityAt(elapsedMs, lengthMs)` | 0 at the start, 1 between the fades, 0 at the end |
| What is shown | `play.ts` `shownAt(p, placements)` | `clip`, or `black` / `video` with chapter and opacity |
| What is drawn | `CardLayer.tsx` | `opacity = playing ? shown.opacity : 1` |

`Timeline.tsx` (about line 1330) passes `playing={video.playing}`. `video.playing` is React state in
`useTimelineVideo.ts`: only `play()` sets it, and `stopPlaying()` clears it. `scrubStart` pauses the card clock and
the video but leaves `playing` as it was. Every path that moves a paused playhead ends in `video.seekTo` with
`playing === false`: the ruler, empty-lane and grip drags and taps (`onScrub`), a press in a card block
(`placeInCard`), Previous/Next clip (`toClip`), the keys (`onKey`), Move to, suggestion jumps
(`overlays/useSuggestions.tsx`), and the effects that re-place the playhead after a read or a card edit.

Reproduced (investigation, 2026-11-23) by bundling the real `CardLayer` with esbuild and rendering it with
`react-dom/server`, for a 7 s black card and a 4 s video-card window:
- `playing=true`: `data-opacity` 0.000 / 0.500 / 1.000 / 0.500 at 0 / 1000 / 3500 / 6000 ms. The video card is
  0.500 1 s into its window.
- `playing=false`: 1.000 at every one of those positions.

History. `bc7758ab` (`timeline-plays-cards`, 2026-10-04) always applied `shown.opacity`. Its review fix `c2fd5d11`,
26 minutes later, added the gate ("A paused or scrubbed position in a card shows it in full; the fade is for
real-time play"). It did not change the spec, which still says "opacity from its fades at that time"
(`openspec/specs/event-timeline/spec.md`, "The playhead can be put in a card…"), or HLD D-20. The likely reason for
the gate is the empty frame described under "Open questions / defaults chosen": a paused playhead on a card's first
instant shows nothing of the card. `seamless-playback` did not touch `CardLayer`, `play.ts` or the `playing` prop.

## Goals / Non-Goals

**Goals:**
- The card layer shows the card's fade at every playhead position, as the movie does, played or not.
- Pause during a fade keeps the opacity reached.
- The rule sits in pure, tested code, so a play-state gate cannot come back unseen.

**Non-Goals:**
- A card's own `look.title_card` fades on the Timeline (HLD D-20's known limit; a separate follow-up).
- Any change to the hook (`useTimelineVideo.ts`), the card clock, the hand-over or the standby.

## Decisions

### D1. One pure function decides the card layer (`timeline/cardView.ts`)
```ts
import type { CardSpec, Placement } from './cards.ts'
import { shownAt } from './play.ts'
import type { Position } from './position.ts'

/** What the card layer draws at a position: nothing over a plain clip, else the card at its fade. */
export type CardView = {
  kind: 'black' | 'video'
  /** The chapter's saved name, or undefined when the spec is missing (as today's `spec?.chapter`). */
  chapter: string | undefined
  /** The fades' opacity at the position's time, in [0, 1]. Never a play-state override. */
  opacity: number
  /** The card image's object URL, or null while it is missing (then `title` is drawn on black). */
  url: string | null
  title: string
}

/** The image lookup the layer needs: `CardPictures` (useCardImages.ts) satisfies it structurally. */
export type PictureLookup = { get(chapter: string): { url: string | null } | null }

export function cardViewAt(
  p: Position,
  placements: readonly Placement[],
  specs: readonly CardSpec[],
  pictures: PictureLookup,
): CardView | null
```
- **Body.** It returns `null` when `shownAt(p, placements).kind === 'clip'`. Otherwise it returns `shown`'s kind and
  opacity, `specs[shown.chapter]?.chapter`, `pictures.get(spec?.chapter ?? '')?.url ?? null`, and
  `spec?.card?.title ?? ''`. This is the exact lookup `CardLayer.tsx` does today, minus the gate.
- **No play state.** The function has no `playing` parameter. To bring back a "full when paused" rule, someone would
  have to change its signature, and review would see that.
- **Imports.** `PictureLookup` is structural, so the module does not import `useCardImages.ts`, which imports React.
  The module stays runnable under `node --test --experimental-strip-types`. Its imports use the `.ts` extension, as
  `play.ts` does.
- **Name.** The file is `cardView.ts`, not `cardLayer.ts`. `Timeline.tsx` imports `./CardLayer` without an
  extension, and Vite resolves `.ts` before `.tsx`. On a case-insensitive file system, `./CardLayer` could then
  resolve to a `cardLayer.ts`.

### D2. `CardLayer.tsx` is a thin renderer
- **Props.** It keeps `memo`, its own `useSyncExternalStore(playhead.subscribe, playhead.get)`, and the props
  `playhead`, `placements`, `specs` and `pictures`. It drops `playing`.
- **Render.** It calls `cardViewAt(at, placements, specs, pictures)` and returns `null` for `null`. Otherwise it
  renders the same DOM as today:
  - `.tl-card-layer` with `data-kind`, `data-chapter`, `data-opacity={view.opacity.toFixed(3)}` and
    `aria-hidden="true"`;
  - the `<img>` or the `.tl-card-fallback` `<p>`, each with `style={{ opacity: view.opacity }}`.

  No CSS changes. The black layer stays opaque, so at opacity 0 a black card's span is black, never the clip
  loading behind it.
- **Header comment.** It says the layer shows the fades at every position (played, paused, scrubbed, stepped), and
  names `cardView.ts`.
- **Re-renders.** Dropping `playing` also stops the layer re-rendering when Play or Pause flips the hook's state.
  Nothing else in its re-render behaviour changes.

### D3. `Timeline.tsx` stops passing `playing`
Remove the `playing={video.playing}` line from the `<CardLayer …/>` element (about line 1330). Nothing else in
`Timeline.tsx` changes. `npm run check` catches any other caller that still passes the prop.

### D4. Pause during a fade needs no hook change
`pauseCard` (`useTimelineVideo.ts`) already freezes `card.ms` at `clock.stop(now)` and writes it to the playhead.
With D1 and D2, the layer shows `opacityAt(card.ms, lengthMs)` at that frozen time, the same value the last played
frame had. In a video card's window, a paused video keeps its `currentTime`, so the playhead's clip `ms` and the
opacity hold too.

### D5. A keyboard activation of a black card block lands where the fade-in ends
`CardLane.tsx` turns a press in a black card's block into a track time from `event.clientX`. A `click` from Enter or
Space on the focused block has no pointer (`event.detail === 0`, `clientX === 0`), so today `part` clamps to 0 and
the playhead lands on the card's first instant: under option A, a black stage. A keyboard activation has no position
to honour, so it should land where the card is first fully shown.
- **Rule.** A pure `cardPressMs(startMs, widthMs, part: number | null): Ms` in `play.ts` (beside `fadesOf`) gives
  `startMs + min(0.999, max(0, part)) * widthMs` for a pointer press (today's arithmetic) and
  `startMs + fadesOf(widthMs).inMs` for `part === null` (opacity 1 there, the end of the fade-in).
- **Wiring.** `CardLane.tsx` gets `part` from a second pure function in `play.ts`,
  `cardPressPart(detail, clientX, left, width): number | null`: `null` when `detail === 0`, else today's
  `(clientX - left) / width` (0 when `width` is 0). It passes `part` to `cardPressMs`. The block's `onOpen` and its
  video-card behaviour are unchanged.
- **Why `detail`.** It is 0 for a keyboard-synthesised `click` in Chrome and Firefox, and the clip blocks already
  tell a keyboard press from a pointer press this way (`Track.tsx`, "a click with no pointer (detail 0)"). A
  programmatic `.click()` gets the same landing, which is harmless. Space on a focused card block can be taken by the
  workspace's Play (`blockYieldsSpace`); where the block does get the `click`, the same rule applies.

## Research & Decisions

### Delete the gate in place, or extract a pure helper
**Context**: the fix itself is about four lines in two files.
**Explored**:
- Delete `playing` and the ternary in `CardLayer.tsx`, and the prop in `Timeline.tsx`.
- The same, plus a pure `cardViewAt` with `node:test` tests (D1).

**Decision**: extract.
**Rationale**: the bug lasted seven weeks because the wrong decision sat in a `.tsx` file that no test can run. The
helper is about 25 lines. It makes the "no play state" property part of the signature and lets the layer's whole
decision be tested: the picture fallback, the video window, and positions frozen by Pause.

### Where the helper lives
**Explored**: add it to `play.ts` beside `shownAt`; a new module.
**Decision**: a new `cardView.ts`.
**Rationale**: `play.ts` is the play clock and knows nothing of specs or pictures. Joining the image lookup there would
widen its imports for one consumer.

## Open questions / defaults chosen

The investigation left three decisions to the operator. Questions 2 and 3 adopt the recommended default and can be
reversed in review. Question 1 changes what the operator sees on every Edit page open, so it took the operator's
explicit decision, recorded below as "Operator decision" (tasks.md 0.2).

1. **Faithful fade at every paused position, or a visibility floor.** *Decided by the operator (2026-11-23): A
   (faithful).*
   - **Where a paused playhead lands at opacity 0 (or within one frame of it).** Review (2026-11-23) traced every path
     that puts a paused playhead on a card's first instant. The first four are the common ones, and are where an
     editor navigates to:
     1. **The page opening.** `Timeline.tsx` (about line 337) creates the playhead at `trackStart(…)`, which is the
        opening card's first instant when that card is black. Edit mode opens with the Timeline open (HLD §4.10,
        `edit-mode-declutter`). So **every Edit page whose opening card is black opens on a black stage.** The card
        images are fetched when the Timeline opens, so while the image loads the fallback title is also at opacity 0:
        nothing on the stage says a card is there.
     2. **Previous/Next clip into a chapter whose card is video.** `clipStep` (`position.ts`) goes to the clip's
        `firstKeptMs`, and `cardPlacements` puts the video window's `atMs` at the first kept span's start: the same
        instant, or within one frame of it. The window then shows at opacity 0 to about 0.02 (one 30 fps frame of a 2 s
        fade-in), so **a video card can never be seen by stepping to its clip.** (Next clip into a chapter whose card
        is black lands on the clip and skips the card, so it is unaffected.)
     3. **The card-edit effect** (`Timeline.tsx`, about lines 650-665). With the playhead in a black card, switching
        that card to video or switching the cards off moves the playhead to `keptPosition(facts, at.clip, 0)`, which is
        the video window's start when the card became video: the card vanishes right after the edit. Shortening the
        card below the playhead's `card.ms` clamps the playhead to the new `lengthMs`, the card's last instant: also
        opacity 0. This clamp is the only path that lands on a black card's last instant.
     4. **A read that loses the playhead's clip** (`afterRead` gives `'start'`, about line 643) goes to `trackStart`,
        as in (1).
     5. Home onto an opening black card; Move to 0:00.
     6. A frame step (Right) from the last frame of the clip before a card lands on the card's first instant.
     7. A press at a black card block's left edge, and **activating the block from the keyboard** (Tab to it, then
        Enter): that `click` has `clientX === 0`, so `CardLane.tsx`'s `part` clamps to 0 and the playhead
        lands on the first instant. Mouse users land where they pressed; keyboard-only operators always land on black.
        This change fixes this one either way (D5).

     The reachable entry from the right is a Left step from a clip's first frame, which lands 0.1 s before the card's
     end (`stepFramesOnTrack`), at opacity 0.05 for a 4 s card. End never lands in a card: it is the last clip's last
     frame.
   - **Option A: faithful (chosen).** The layer shows `opacityAt` at every position, with no play state. Cases
     (1) to (6) above show a black stage (black card) or the bare video (video card). The readouts still say where the
     playhead is: the Clip readout reads "Card 0:00.00 of …", the slider's value text names the title card, and the
     card stays visible on its track block. One Right (0.1 s) shows the fade-in starting. *Why:* it is what the
     render outputs and what the spec already says; one position has one look however the playhead got there; and
     `cardViewAt` keeps no play state, so the gate that caused the bug cannot come back. *Cost:* the page-open black
     stage of (1) and the invisible video card of (2) are what an editor sees most often while paused.
   - **Rejected by the operator: option B, faithful with a floor on a paused card's first instant.** While paused,
     a position within one step of a card's start (a black card's `card.ms < CARD_STEP_MS`, or a video window's
     clip time within one frame of `atMs`) is drawn at a floor (for example full opacity); everywhere else, and
     always while playing, the fades are faithful. *For:* it covers (1) to (7) without touching the landing
     positions, and a scrub almost never sits exactly on a first instant, so the reported scrub fade is still fixed.
     *Against:* `cardViewAt` needs a play-state input again (the property D1 is built on), so a future "full when
     paused" widening is one condition away; the first Right from Home goes from full to 0.05, a visible jump the
     movie does not have; and the frame shown at Home is not the movie's first frame.
   - **Rejected: fade while dragging, full on discrete landings** (click, key, Home). It brings back the play/scrub
     mismatch the operator reported, and splits one position into two looks depending on how the playhead got there.
   - **Rejected: move the landings** (open, Home and Next clip land where the fade-in ends). Home and Next clip are
     specified as the movie's first instant and the clip's first kept frame; moving them would make the readouts lie
     about where the movie starts. The keyboard activation of (7) is the exception, because it has no pointer
     position to honour (D5).
   - **Recorded in the spec** (scenarios "The Edit page opens on an opening black card", "Next clip into a chapter
     with a video card", "Home onto the opening card shows its first instant"), so a reviewer does not "fix" option A
     back.
   - **Operator decision (2026-11-23): option A, faithful fades at every position** (paused, scrubbed, clicked,
     stepped), with no floor. The empty frames of (1) to (6) are accepted as what the movie shows there. The
     keyboard-activation fix of (7) (D5: Enter, or a `click` with `detail === 0`, on a black card block puts the
     playhead where the fade-in ends) stays in this change.
2. **Pure-helper extraction or the minimal deletion.** *Default chosen: extract* (Research & Decisions above).
3. **Scope.** *Default chosen: the scrub/paused fade only.* Carrying `look.title_card` `fade_in` / `fade_out` on the
   event detail, so the Timeline shows a card's own fades, is HLD D-20's known limit (`labels.ts`, the Help line). It
   is tracked as a separate follow-up and not done here.

## Risks / Trade-offs

- **[An opacity-0 frame reads as "the card is missing"]** → Under option A this is not rare. Every Edit page whose
  opening card is black opens on a black stage (the playhead starts at `trackStart`), and so does the page after a
  read that loses the playhead's clip; Previous/Next clip into a chapter with a video card shows that card at about
  opacity 0; switching the playhead's card to video or off, or shortening it below the playhead, leaves the card
  invisible; and a keyboard activation of a black card block would land on black (fixed here, D5). The readout says
  "Card 0:00.00 of …" and the slider's value text names the title card, so the position is never silent, but the
  stage is. The operator accepted this (question 1, option A, 2026-11-23), and the delta spells these cases out as
  scenarios.
- **[A check expects `data-opacity="1.000"` at a paused card position]** → A grep found no reader of `data-opacity`
  outside `CardLayer.tsx` and `timeline.css`. The scripted headed gates that sample the stage (the card hand-over, the
  scrub frame rate) run while playing or across clips, and are unaffected. The headless check in task 3.1 re-runs the
  card hand-over sampling to confirm it.
- **[The extraction costs the memo or the store read]** → D2 keeps `memo` and the component's own
  `useSyncExternalStore`, so a playing card still re-renders only the layer (HLD D-20, `1dfa9b83`).
- **[Reverting a reviewed decision looks like churn]** → The proposal cites `c2fd5d11` and the spec line it
  contradicted. HLD D-20 gets an "Amended … `titlecard-scrub-fade`" sentence.
- **[The hook is touched by accident]** → D4 needs no hook change, and tasks.md forbids one. `playing` and
  `scrubStart` serve the seamless-playback hand-over and resume-after-scrub.

## Failure behaviour

None new. A missing spec or picture falls back as today: `chapter` undefined, the title (or `''`) on black, at the
same opacity. `cardViewAt` throws only where `shownAt` already throws (a bad card length, `ModelError` naming the
title card), so the layer fails as loudly as it does today.
