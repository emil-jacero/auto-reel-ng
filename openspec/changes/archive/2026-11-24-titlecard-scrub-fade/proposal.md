## Why

The operator reported (2026-11-23): "When scrubbing the timeline over a title card, the fade in and fade out is no
longer shown. But when playing it shows correctly."

The cause is one line, on purpose. `web/src/timeline/CardLayer.tsx` sets the card layer's opacity with
`playing ? shown.opacity : 1`, and `Timeline.tsx` passes `playing={video.playing}`. `video.playing` is true only
between Play and Pause, so every other position shows the card at full opacity:
- a drag or a tap on the ruler, an empty lane or the playhead grip;
- a press in a black card's block, and a double-press that lands in a video card's window;
- Previous/Next clip, the arrow, Shift, Page, Home and End keys;
- Move to (typed time), a suggestion jump, and the re-placing of the playhead after a read or a card edit.

The pure logic is right. `play.ts` `shownAt` returns each position's fade opacity, for black cards and video-card
windows, and `play.test.ts` covers it. The component throws that value away while the Timeline is paused.

The gate came in with commit `c2fd5d11` ("fix(web): answer the timeline-plays-cards review", 2026-10-04), which says
"A paused or scrubbed position in a card shows it in full; the fade is for real-time play". It landed 26 minutes after
the feature commit `bc7758ab`, which always applied the fade. It changed neither the spec nor the HLD. The main spec
already says the opposite: "The playhead can be put in a card, and the readouts count card time" requires a press or
drag into a black card to "show that card's image there (opacity from its fades at that time)"
(`openspec/specs/event-timeline/spec.md`, line 1251). So the code contradicts the spec. The scenarios did not catch
it: "A drag across a card" only says the image "shows", and no scenario covers a key step, Home, a paused position in
a video card's window, or Pause during a fade.

The same gate has two side effects:
- Pressing Pause during a fade makes the card jump to full opacity.
- `scrubStart` does not clear `playing`, so a drag started while playing shows the fades, and the same drag started
  while paused does not. This is the play/scrub mismatch the operator saw.

The bug survived because the decision lived in a `.tsx` file, which `node:test` (strip-types, no TSX) cannot run.

## What Changes

- **The fades show at every playhead position.** The Timeline's card layer takes its opacity from the card's fades
  at the playhead's time, whether the Timeline is playing, paused, scrubbed, pressed, stepped or moved by a key. This
  holds for a black card's span and for a video card's window. A position at a card's first instant shows the card
  at opacity 0: black for a black card, the bare video under a video card. That is what the movie shows there.
- **Where that empty frame is seen (operator decision, 2026-11-23: show it faithfully).** A paused playhead lands
  on a card's first instant, or within one frame of it, far more often than on a scrub:
  - **every Edit page whose opening card is black opens on a black stage**, because the playhead starts at
    `trackStart` and Edit mode opens with the Timeline open; while the card's image loads, its fallback title is at
    opacity 0 too;
  - **Previous/Next clip into a chapter whose card is video** lands on the window's start, so that card shows at
    about opacity 0 and cannot be seen this way;
  - switching the playhead's card to video or off moves the playhead to the clip's start (the video window's start),
    and shortening the card below the playhead clamps it to the card's end: both at opacity 0;
  - a read that loses the playhead's clip goes back to the start, as on open; Home; a frame step into a card; a press
    at a card block's left edge.

  The operator chose (2026-11-23) to show these faithfully (design question 1, option A): the fades show at every
  position, paused, scrubbed, clicked or stepped, with no floor. The decision is recorded in design.md.
- **A keyboard activation of a black card block lands where the card is fully shown.** Enter on a focused
  black card block today puts the playhead on the card's first instant (the `click` has no pointer, so its position
  clamps to the left edge). It now puts the playhead at the end of the card's fade-in, so a keyboard-only operator
  lands on the card at full opacity, as a mouse press in the block's middle does.
- **Pause keeps the fade.** Pause during a fade leaves the card at the opacity it had. Play goes on from there.
- **The decision moves into pure code.** A new pure module `web/src/timeline/cardView.ts` decides what the card layer
  shows at a position: its kind, chapter, opacity, image URL or fallback title. It takes no play state, so a "full
  when paused" rule could only come back through a signature change that review would see. It is tested with
  `node:test`. `CardLayer.tsx` becomes a thin renderer of it, and loses its `playing` prop.
- **This reverts part of `c2fd5d11`.** Only the opacity bullet is reverted. That commit's other fixes (the held video,
  the 503 wait on an edited card) stay.

## Non-goals

- Carrying a card's own `look.title_card` `fade_in` / `fade_out` on the event detail. The Timeline keeps the engine's
  default fades (2 s each, clamped to the card's length), and the Help line about it stays (`labels.ts`, HLD D-20).
  That is a separate follow-up.
- A visibility floor, for example showing a paused card at least half visible (option B, declined by the operator on
  2026-11-23). See design, "Open questions / defaults chosen".
- Any change to `useTimelineVideo.ts`: `playing`, `scrubStart`, the card clock, the hand-over and the standby are
  untouched.
- The card blocks on the track and the inspector preview. They show the card in full, as they do today.
- The read view: it has no Timeline.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `event-timeline`:
  - MODIFIED "The playhead can be put in a card, and the readouts count card time". The fades show at every position
    in a card or in a video card's window, not only while playing. New scenarios cover a press mid-fade, a drag
    across a card's fades, the Edit page opening on an opening black card, Home and a frame step onto a card's first
    instant, a Left step back into a card's end, Next clip into a chapter with a video card, a keyboard activation of
    a black card block, and a paused position in a video card's window.
  - MODIFIED "The Timeline plays the title cards as the movie will". Pause during a fade keeps the opacity reached.

## Impact

- **Web only.**
  - New pure module `timeline/cardView.ts` with `cardView.test.ts`.
  - `timeline/CardLayer.tsx` renders `cardViewAt` and drops `playing`.
  - `timeline/play.ts` gains the pure `cardPressPart` (the part of a black card's block a click was at, `null` for a
    keyboard activation) and `cardPressMs` (where that puts the playhead, with the keyboard case);
    `timeline/CardLane.tsx` calls both.
  - `timeline/Timeline.tsx` no longer passes `playing` to `CardLayer`.
  - Docs: HLD D-20 (one sentence on the `timeline-plays-cards` bullet), §4.10 (a clause on the `timeline-plays-cards`
    summary), §6 item 10 ("`titlecard-scrub-fade` is built"), `web/README.md` (the file tree), and a `docs.test.ts`
    case asserting §4.10, §6 and D-20.
- **Unchanged:**
  - No API, engine, `reel.yaml` or `config.yaml` schema change, no Alembic migration and no rescan.
  - Rendered output, the staleness fingerprint and `RENDER_GRAPH_VERSION` do not change. The render already fades
    cards this way; this change makes the Timeline match it.
  - The CLI is untouched: this is how the browser draws a preview layer, with no engine capability for the CLI to
    reach (Principle V).
  - No new dependency.
- **Depends on** nothing in flight. It changes one line of `Timeline.tsx`, so it rebases easily on any other change
  to that file (such as the resizable-panes change planned beside it).
- **Size:** under half a day.
