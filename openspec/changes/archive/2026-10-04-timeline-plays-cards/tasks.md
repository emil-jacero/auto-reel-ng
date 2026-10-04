## 1. timeline model

- [x] 1.1 Add `web/src/timeline/play.ts` (pure): stages from the card map, a position on the track and its track time,
  opacity from the (clamped) default fades, a video card's window, the hand-over, and the card clock's time reached for
  an elapsed time, refusing a bad length with a `ModelError`. Test with `node:test` in `play.test.ts`: every scenario of
  "The model plays a movie of clips and cards on one clock" (stages add up, a position in a card, round trip, opacity
  at 0 / 1,000 / 2,000 / 3,500 / 5,000 / 6,000 / 7,000 ms, clamped fades, hand-over after a leading cut, a video card's
  window edges, the clock held to the length, a bad length).
- [x] 1.2 Give `Position` the optional card field and make `positionAt`, `stepMs`, `stepFrames`, `startPosition`, the
  playhead store and `readout.ts` (`Card 0:01.20 of 0:07.00`, the Event time counting cards, the slider's value text) handle
  it. Test in `position.test.ts`, `readout.test.ts` and `labels.test.ts`: a position inside a card keeps the anchor clip
  and clip time 0, frame steps skip a card while second steps and Home/End land in one, the readout words and the
  value text are exact strings, and a clip position is unchanged (the existing cases still pass).

## 2. card images

- [x] 2.1 Add `web/src/timeline/cardImages.ts` (pure queue with injected fetch, timer and URL functions): the key from
  body and style, one request at a time in play order, 503 waited out by `Retry-After` (1 to 30 s, three tries), other
  failures said once and not retried, only the changed card refetched after the quiet time, URLs revoked on replace and
  close. Test with `node:test` in `cardImages.test.ts`: never two in flight, order, 503 then 200, the third 503 ends in a
  stated failure, 502 not retried, an edit refetches one card only, revocation counts.
- [x] 2.2 Wire it to the Timeline: a hook that builds each card's request from the detail (and the draft in Edit mode,
  with `previewRequest`), starts on open and stops on close, and gives the blocks and the player the image or the
  "title on black" fallback. Test with `node:test` for the request builder (the opening card sends the draft event
  title, the style only when it differs) and with Playwright (task 5) for the wiring.

## 3. blocks

- [x] 3.1 Draw the miniature in each card block (cover, the title when it fits, the accessible name and tooltip
  always, a 24 px minimum width that does not move the track, a light ring on black in the dark scheme) and remove the
  "plays footage only" note (`CARDS_NOT_PLAYED`) and its test. Test with `node:test` for the width rule (a pure function
  of the block's px) and the labels, and with Playwright at 1280 and 390 in light and dark (screenshots looked at).

## 4. playback

- [x] 4.1 Add the card layer and the card clock to `useTimelineVideo`: a black card replaces the picture and a video
  card overlays it with opacity from `play.ts`; the playhead advances in real time through a card; the hand-over clip
  is loaded and sought during the card and the card is removed on the first presented frame; Pause, Play and Space work
  inside a card; a hidden page pauses; another player's start pauses the Timeline in a card (`watchOtherStarts`) and
  the Timeline's own start pauses the others. Test with `node:test` for the hook's pure driver (an injected clock and
  video stand-in: elapsed time not frames, a slow frame, Pause and resume at 1.2 s, the hand-over waiting for the
  seek, another player's start), and with Playwright in task 5.
- [x] 4.2 Let a press or a drag on the ruler or the track put the playhead in a black card (a lane press still selects
  the card and now also moves the playhead), showing the card at that point, and announce the end of a scrub or a
  key step that ends in a card once. Test with `node:test` for the pointer-to-position mapping into a card (the press
  inside, at both edges, and a drag across) and for the single announcement.

## 5. browser verification

- [x] 5.1 Playwright (scripts in the scratchpad, never in the repo) in Chrome 154 and in Firefox 155 or newer, light
  and dark at 1280 and 390: play from 0 through the opening card into clip 1 (the card image is visible, the playhead
  moves for its length, then the video plays, no sampled background frame at the hand-over), a press into a mid card
  (image, `Card 0:01.00 of 0:04.00`, the Event readout counts the card), Pause and Play in a card, another player starting
  during a card, a video card's image over the playing video with its opacity changing, a 503 with `Retry-After`
  answered by a routed response, a zoomed-out card still pressable; the screenshots are looked at. Writes are
  intercepted as the brief says. Fails if any of these is not seen.

## 6. docs

- [x] 6.1 Update the HLD: §4.10 (replace the "Honest limits: the Timeline plays footage only" sentence of the
  `title-card-blocks` note, add a `timeline-plays-cards` note with the decisions above and the measured bundle size,
  and record the fade-defaults limit), §6 (the phase 8 status line), D-20 (the Timeline plays and shows the cards; one
  video plus a card layer; the card clock) and, since the card images use the preview endpoint, the note in D-21 or
  D-24 that the Timeline is a second client of it. Verify by a `grep` that no text says the Timeline plays footage
  only, and that `openspec validate timeline-plays-cards --strict` and `npm test`, `tsc` and the build pass.
